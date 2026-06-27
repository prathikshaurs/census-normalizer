# Census Normalizer

**Turn any broker's messy census file into one clean, validated schema the underwriting engine can price — and flag the rows a human needs to review before a quote goes out.**

When a broker requests a quote, they send an employee **census file**. Every broker formats it differently: columns named `DOB` vs `Date of Birth` vs `birth_date`, gender as `M/F` vs `Male/Female` vs `1/2`, relationships as `EE/SP/CH` vs `Employee/Spouse/Child`, ZIP codes that lost their leading zeros in Excel, dates in five different formats. Today someone cleans each file by hand before underwriting can touch it. That manual step is the bottleneck between *"broker sends a file"* and *"quote in minutes."*

This project automates that step.

---

## What it does

```
  Messy broker file (any format, CSV or XLSX)
        │
        ▼
  ① Column mapping      fuzzy-match arbitrary headers → canonical fields
        │                (synonym dictionary + string similarity, no per-broker code)
        ▼
  ② Value coercion      standardize dates, gender, relationship, ZIP, state, names
        │                (dbt-style staging → canonical model)
        ▼
  ③ Validation          duplicate members, missing DOB/ZIP, orphan dependents,
        │                coercion issues  (Great Expectations–style checks)
        ▼
  Clean canonical census  +  quality score (0–100)  +  row-level issue report
```

The canonical output is the **"source of truth"** the underwriting API reads from — never the raw broker file.

## Why it generalizes

The column mapping is driven by a synonym dictionary plus fuzzy string similarity, so a **broker format the tool has never seen** still maps correctly without a code change. Drop in a new file with `Subscriber ID` / `Given Name` / `Postal` and it resolves them to `employee_id` / `first_name` / `zip_code` on its own.

## Validation checks (what gets flagged)

| Check | Severity | Why it matters for underwriting |
|---|---|---|
| `duplicate_member` | warning | Same person counted twice inflates the group |
| `missing_dob` | critical | Can't age-rate without a birth date |
| `missing_zip` | critical | Can't area-rate without a location |
| `orphan_dependent` | critical | A spouse/child with no matching employee = broken household |
| `value_coercion_issue` | warning | A value needed cleaning or couldn't be fully standardized |

A file with **zero critical issues** is marked `ready_for_underwriting: true`. Anything else routes to a human with the exact rows and reasons highlighted.

## Quickstart

```bash
pip install -r requirements.txt

# 1) generate synthetic broker files (100% fake data, no PHI)
python src/generate_synthetic_censuses.py

# 2) run the full pipeline on all sample files
python src/pipeline.py

# 3) (optional) run the API + dashboard
uvicorn api:app --reload --port 8000   # from inside src/
# then open http://localhost:8000
```

No live server? Open `dashboard/standalone_demo.html` in any browser — it has the sample results embedded.

## API

```
POST /normalize        multipart file upload (CSV/XLSX) → clean rows + mapping + quality report
GET  /                 the dashboard
GET  /sample/{name}    serve a bundled sample file (broker_a … broker_d)
```

Example response (trimmed):
```json
{
  "column_mapping": {"id": "employee_id", "fname": "first_name", "birth_date": "date_of_birth"},
  "report": {
    "quality_score": 76.7,
    "ready_for_underwriting": false,
    "checks": [
      {"check": "missing_dob", "severity": "critical", "count": 1, "row_index": [10]},
      {"check": "orphan_dependent", "severity": "critical", "count": 1, "row_index": [60]}
    ]
  }
}
```

## Stack

Python · pandas · FastAPI · dbt-style staging→canonical modeling · Great Expectations–style validation. All open source, no paid tooling.

## Layout

```
census-normalizer/
├── src/
│   ├── generate_synthetic_censuses.py   # 4 fake broker formats (Faker)
│   ├── schema.py                        # canonical objects (Group→Member→Dependent)
│   ├── normalizer.py                    # column mapping + value coercion
│   ├── validator.py                     # data-quality checks + scoring
│   ├── pipeline.py                      # end-to-end runner
│   └── api.py                           # FastAPI app
├── dashboard/
│   ├── index.html                       # live dashboard (talks to API)
│   └── standalone_demo.html             # self-contained, no server needed
├── data/raw/                            # generated synthetic inputs
├── data/output/                         # clean files + JSON reports
├── notebooks/demo.ipynb                 # walkthrough
└── tests/test_normalizer.py
```

## A note on data

Every census file here is **synthetic**, generated with Faker. No real member data, no PHI. The normalizer is built so that swapping in real data would never require loosening the validation that protects it.
