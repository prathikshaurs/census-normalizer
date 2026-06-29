"""
Validation + data-quality scoring on the CLEAN canonical census.

These are exactly the checks Arlo's JD calls out: duplicate records, mismatched
member IDs, orphan dependents (a dependent with no matching employee), missing
critical fields, and structural problems that would otherwise reach underwriting
silently and bias a quote.

Output: a structured report + a 0-100 quality score, so an underwriter sees what
needs human review instead of hand-checking every row.
"""

import pandas as pd


def validate(clean_df: pd.DataFrame):
    df = clean_df.copy()
    n = len(df)
    checks = []
    flagged_rows = set()

    def add(name, severity, mask, message):
        idx = list(df.index[mask]) if mask is not None else []
        for i in idx:
            flagged_rows.add(i)
        checks.append({
            "check": name,
            "severity": severity,        # critical | warning
            "count": len(idx),
            "row_index": idx,
            "message": message,
        })

    # 1) exact duplicate members
    dup_mask = df.duplicated(
        subset=["employee_id", "first_name", "last_name", "date_of_birth", "relationship"],
        keep="first",
    )
    add("duplicate_member", "warning", dup_mask,
        "Exact duplicate member rows (same person appears more than once)")

    # 2) missing date of birth (can't rate without age)
    add("missing_dob", "critical", df["date_of_birth"].isna(),
        "Member missing date of birth -- cannot age-rate")

    # 3) missing zip (can't area-rate)
    add("missing_zip", "critical", df["zip_code"].isna(),
        "Member missing ZIP -- cannot area-rate")

    # 4) orphan dependents: spouse/child whose employee_id has no 'employee' row
    emp_ids = set(df.loc[df["relationship"] == "employee", "employee_id"])
    dep_mask = df["relationship"].isin(["spouse", "child"])
    orphan_mask = dep_mask & ~df["employee_id"].isin(emp_ids)
    add("orphan_dependent", "critical", orphan_mask,
        "Dependent has no matching employee/subscriber in the file")

    # 5) row-level coercion issues surfaced by the normalizer
    if "row_issues" in df.columns:
        issue_mask = df["row_issues"].fillna("").str.len() > 0
        add("value_coercion_issue", "warning", issue_mask,
            "Value needed cleaning or could not be fully standardized")

    # 6) employees with no dependents flagged spouse/child mismatch is fine;
    #    but a group with zero employee rows is a structural red flag
    if len(emp_ids) == 0 and n > 0:
        add("no_subscribers", "critical", pd.Series([True] * n, index=df.index),
            "File contains no employee/subscriber rows at all")

    # ---- scoring ----
    critical = sum(c["count"] for c in checks if c["severity"] == "critical")
    warnings = sum(c["count"] for c in checks if c["severity"] == "warning")
    # critical issues weigh 3x warnings; normalize against row count
    penalty = (critical * 3 + warnings) / max(n, 1)
    score = max(0, round(100 * (1 - min(penalty, 1)), 1))

    report = {
        "rows_total": n,
        "rows_clean": n - len(flagged_rows),
        "rows_flagged": len(flagged_rows),
        "critical_issues": critical,
        "warning_issues": warnings,
        "quality_score": score,
        "checks": [c for c in checks if c["count"] > 0],
        "ready_for_underwriting": critical == 0,
    }
    return report, sorted(flagged_rows)
