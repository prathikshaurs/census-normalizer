"""
End-to-end pipeline: raw broker file -> normalize -> validate -> clean output + report
"""

import os
import json
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from normalizer import normalize_file
from validator import validate

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "output")
os.makedirs(OUT_DIR, exist_ok=True)


def load_any(path):
    if path.endswith(".xlsx"):
        return pd.read_excel(path)
    return pd.read_csv(path, dtype=str)


def run_one(path, group_id):
    fname = os.path.basename(path)
    raw = load_any(path)
    clean, mapping = normalize_file(raw, group_id=group_id, source_file=fname)
    report, flagged = validate(clean)
    return raw, clean, mapping, report, flagged


def main():
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith((".csv", ".xlsx")))
    summary = []
    for i, f in enumerate(files, 1):
        path = os.path.join(RAW_DIR, f)
        group_id = f"G{i:03d}"
        raw, clean, mapping, report, flagged = run_one(path, group_id)

        out_csv = os.path.join(OUT_DIR, f.rsplit(".", 1)[0] + "_clean.csv")
        clean.to_csv(out_csv, index=False)
        with open(os.path.join(OUT_DIR, f.rsplit(".", 1)[0] + "_report.json"), "w") as fh:
            json.dump(report, fh, indent=2, default=str)

        print(f"\n=== {f}  (group {group_id}) ===")
        print(f"  raw columns:      {list(raw.columns)}")
        print(f"  mapped -> canon:  {mapping}")
        print(f"  rows: {report['rows_total']}  clean: {report['rows_clean']}  "
              f"flagged: {report['rows_flagged']}")
        print(f"  quality score:    {report['quality_score']}/100   "
              f"ready_for_underwriting={report['ready_for_underwriting']}")
        for c in report["checks"]:
            print(f"    [{c['severity']:>8}] {c['check']}: {c['count']}  ({c['message']})")

        summary.append({
            "file": f, "group_id": group_id,
            "rows": report["rows_total"],
            "score": report["quality_score"],
            "critical": report["critical_issues"],
            "warnings": report["warning_issues"],
            "ready": report["ready_for_underwriting"],
        })

    with open(os.path.join(OUT_DIR, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\nWrote clean files + reports to data/output/")


if __name__ == "__main__":
    main()
