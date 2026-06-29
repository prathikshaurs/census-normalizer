"""
The normalizer: messy broker file in -> clean canonical census out.

Two stages, mirroring a dbt staging -> canonical model:
  1) map_columns()   : fuzzy-match each broker's arbitrary headers to canonical fields
  2) coerce_values() : standardize dates, gender, relationship, zip, state, names

No hard-coded per-broker rules, the mapping is driven by a synonym dictionary plus
fuzzy string similarity, so a NEW broker format the script has never seen still maps
correctly without a code change. That generalization is the whole point.
"""

import re
from datetime import datetime, date
from difflib import SequenceMatcher

import pandas as pd

from schema import GENDER_DOMAIN, RELATIONSHIP_DOMAIN


# ---- synonym dictionary: canonical_field -> known header variants ----
HEADER_SYNONYMS = {
    "employee_id": ["empid", "emp id", "employee identifier", "id", "emp_id",
                    "subscriber id", "member id", "employee id"],
    "first_name": ["first name", "fname", "member first name", "name first",
                   "first", "given name"],
    "last_name": ["last name", "lname", "member last name", "name last",
                  "last", "surname", "family name"],
    "date_of_birth": ["dob", "date of birth", "birth_date", "birthdate",
                      "birth date", "dateofbirth"],
    "gender": ["gender", "sex", "gender code"],
    "relationship": ["relationship", "relationship to subscriber", "rel",
                     "coverage tier", "tier", "relation"],
    "zip_code": ["zip", "zipcode", "zip code", "postal code", "postal"],
    "state": ["state", "st", "home state", "state code"],
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(s).strip().lower()).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def map_columns(df: pd.DataFrame, threshold: float = 0.82):
    """Return {raw_header: canonical_field} using synonyms + fuzzy fallback."""
    mapping = {}
    used = set()
    for raw in df.columns:
        n = _norm(raw)
        best_field, best_score = None, 0.0
        for field, variants in HEADER_SYNONYMS.items():
            if field in used:
                continue
            # exact synonym hit wins outright
            if n in variants:
                best_field, best_score = field, 1.0
                break
            for v in variants:
                score = _similar(n, v)
                if score > best_score:
                    best_field, best_score = field, score
        if best_field and best_score >= threshold:
            mapping[raw] = best_field
            used.add(best_field)
    return mapping


# ---------- value coercion helpers ----------

def coerce_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return None, "missing date_of_birth"
    if isinstance(val, (datetime, date)):
        d = val if isinstance(val, date) and not isinstance(val, datetime) else val.date()
        return _validate_dob(d)
    s = str(val).strip()
    fmts = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d",
            "%m/%d/%y", "%d-%m-%Y", "%b %d %Y", "%B %d, %Y"]
    for f in fmts:
        try:
            return _validate_dob(datetime.strptime(s, f).date())
        except ValueError:
            continue
    return None, f"unparseable date '{s}'"


def _validate_dob(d):
    if d > date.today():
        return None, f"future DOB {d.isoformat()}"
    if d.year < 1900:
        return None, f"implausible DOB {d.isoformat()}"
    return d, None


def coerce_gender(val):
    if val is None or str(val).strip() == "":
        return "U", "missing gender -> set to U"
    s = str(val).strip().lower()
    if s in {"m", "male", "1"}:
        return "M", None
    if s in {"f", "female", "2"}:
        return "F", None
    return "U", f"unknown gender '{val}' -> U"


def coerce_relationship(val):
    if val is None or str(val).strip() == "":
        return "employee", "missing relationship -> assumed employee"
    s = str(val).strip().lower()
    if s in {"ee", "employee", "employee only", "subscriber", "self", "emp"}:
        return "employee", None
    if s in {"sp", "spouse", "employee+spouse", "husband", "wife", "partner"}:
        return "spouse", None
    if s in {"ch", "child", "dependent", "employee+child", "son", "daughter", "dep"}:
        return "child", None
    return "employee", f"unknown relationship '{val}' -> employee"


def coerce_zip(val):
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return None, "missing zip_code"
    raw = str(val).strip()
    if raw.endswith(".0"):          # pandas read numeric zip as float
        raw = raw[:-2]
    s = re.sub(r"[^0-9]", "", raw)
    if s == "":
        return None, f"non-numeric zip '{val}'"
    if len(s) < 5:
        s = s.zfill(5)        # restore dropped leading zeros
    if len(s) > 5:
        s = s[:5]
    return s, None


def coerce_state(val):
    if val is None or str(val).strip() == "":
        return None, "missing state"
    s = str(val).strip().upper()
    if len(s) != 2:
        return s, f"non-standard state '{val}'"
    return s, None


def clean_name(val):
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip().title()


def normalize_file(df: pd.DataFrame, group_id: str, source_file: str = ""):
    """Map columns then coerce values. Returns (clean_df, column_mapping)."""
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    mapping = map_columns(df)
    renamed = df.rename(columns=mapping)

    records = []
    for _, row in renamed.iterrows():
        issues = []
        dob, e = coerce_date(row.get("date_of_birth"))
        if e: issues.append(e)
        gender, e = coerce_gender(row.get("gender"))
        if e: issues.append(e)
        rel, e = coerce_relationship(row.get("relationship"))
        if e: issues.append(e)
        zip_code, e = coerce_zip(row.get("zip_code"))
        if e: issues.append(e)
        state, e = coerce_state(row.get("state"))
        if e: issues.append(e)

        records.append({
            "group_id": group_id,
            "employee_id": str(row.get("employee_id", "")).strip(),
            "first_name": clean_name(row.get("first_name")),
            "last_name": clean_name(row.get("last_name")),
            "date_of_birth": dob.isoformat() if dob else None,
            "gender": gender,
            "relationship": rel,
            "zip_code": zip_code,
            "state": state,
            "source_file": source_file,
            "row_issues": "; ".join(issues),
        })

    clean_df = pd.DataFrame(records)
    return clean_df, mapping
