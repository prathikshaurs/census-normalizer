"""
Tests for the normalizer and validator
"""
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from normalizer import (map_columns, coerce_date, coerce_gender,
                        coerce_relationship, coerce_zip, normalize_file)
from validator import validate


def test_fuzzy_column_mapping_unseen_headers():
    df = pd.DataFrame(columns=["Subscriber ID", "Given Name", "Surname",
                               "Birthdate", "Sex", "Relation", "Postal", "St"])
    m = map_columns(df)
    assert m["Subscriber ID"] == "employee_id"
    assert m["Given Name"] == "first_name"
    assert m["Surname"] == "last_name"
    assert m["Birthdate"] == "date_of_birth"
    assert m["Sex"] == "gender"
    assert m["Postal"] == "zip_code"


def test_date_formats_all_parse():
    for s in ["1985-03-12", "03/12/1985", "03-12-1985", "1985/03/12"]:
        d, err = coerce_date(s)
        assert d == date(1985, 3, 12), (s, d, err)
        assert err is None


def test_future_dob_rejected():
    future = (date.today() + timedelta(days=30)).strftime("%m/%d/%Y")
    d, err = coerce_date(future)
    assert d is None
    assert "future" in err


def test_gender_variants():
    assert coerce_gender("M")[0] == "M"
    assert coerce_gender("Male")[0] == "M"
    assert coerce_gender("1")[0] == "M"
    assert coerce_gender("2")[0] == "F"
    assert coerce_gender("")[0] == "U"


def test_relationship_variants():
    assert coerce_relationship("EE")[0] == "employee"
    assert coerce_relationship("Employee+Spouse")[0] == "spouse"
    assert coerce_relationship("Dependent")[0] == "child"


def test_zip_leading_zero_restored():
    z, err = coerce_zip("2118")      # MA zip that lost its leading 0
    assert z == "02118"
    assert err is None


def test_zip_float_string_cleaned():
    z, _ = coerce_zip("47008.0")     # pandas float artifact
    assert z == "47008"


def test_orphan_dependent_detected():
    df = pd.DataFrame([
        {"group_id": "G1", "employee_id": "E1", "first_name": "A", "last_name": "B",
         "date_of_birth": "1980-01-01", "gender": "M", "relationship": "employee",
         "zip_code": "10001", "state": "NY", "row_issues": ""},
        {"group_id": "G1", "employee_id": "E2", "first_name": "C", "last_name": "D",
         "date_of_birth": "2015-01-01", "gender": "F", "relationship": "child",
         "zip_code": "10001", "state": "NY", "row_issues": ""},  # no E2 employee
    ])
    report, flagged = validate(df)
    checks = {c["check"]: c["count"] for c in report["checks"]}
    assert checks.get("orphan_dependent") == 1
    assert report["ready_for_underwriting"] is False


def test_clean_file_scores_100():
    df = pd.DataFrame([
        {"group_id": "G1", "employee_id": "E1", "first_name": "A", "last_name": "B",
         "date_of_birth": "1980-01-01", "gender": "M", "relationship": "employee",
         "zip_code": "10001", "state": "NY", "row_issues": ""},
    ])
    report, flagged = validate(df)
    assert report["quality_score"] == 100.0
    assert report["ready_for_underwriting"] is True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} tests passed")
