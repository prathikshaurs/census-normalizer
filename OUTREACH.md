# Census Normalizer — a project I built for Arlo

Hi, I'm Prathiksha, and I'm applying for the Data Engineer role at Arlo. Instead of  just sending a resume, I wanted to build something against a problem you actually have. This is a working prototype, not a slide.

## The problem I picked

Across your job description, the same theme keeps showing up: turning complex, heterogeneous inputs — TPA feeds, carrier data, census files, claims, eligibility, enrollment — into clean, trustworthy "source of truth" tables that the underwriting engine can price from. And the whole promise of the platform is turning a multi-week quoting process into something that happens in minutes.

The piece I zeroed in on is the **broker census file**. When a broker wants a quote, they send the employee roster — and every broker formats it differently. Columns named `DOB` vs `Date of Birth` vs `birth_date`, gender as `M/F` vs `Male/Female` vs `1/2`, relationships as `EE/SP/CH` vs `Employee/Spouse/Child`, ZIP codes that lost their leading zeros in Excel, dates in five formats. Someone has to reconcile each one before underwriting can touch it. That manual cleanup sits right on the critical path between "broker sends a file" and "quote in minutes."

## What I built

A pipeline + API that takes a messy census file in any format and returns a clean, validated, schema-conformed dataset ready for the underwriting API — plus a data-quality report that flags exactly the rows a human needs to review.

Three stages, modeled the way an underwriting data layer thinks about the world (Group → Member → Dependent), mirroring a dbt staging → canonical flow:

1. **Column mapping** — fuzzy-matches each broker's arbitrary headers to canonical fields using a synonym dictionary plus string similarity. No per-broker rules: a format the tool has never seen still maps correctly. (Tested explicitly — it resolves `Subscriber ID` / `Given Name` / `Postal` with zero code changes.)
2. **Value coercion** — standardizes dates across formats, gender, relationship codes, restores dropped leading zeros on ZIPs, trims Excel whitespace, rejects impossible/future birthdates.
3. **Validation + scoring** — Great Expectations–style checks for the failures that actually bias a quote: duplicate members, missing DOB/ZIP, and **orphan dependents** (a spouse or child with no matching employee in the file). Outputs a 0–100 quality score and a `ready_for_underwriting` verdict.

I built it on the same stack your JD names: **Python, pandas, FastAPI, dbt-style modeling, Great Expectations.** All synthetic data, no PHI — and built so that swapping in real data would never mean loosening the validation that protects it.

## See it in 60 seconds

- **No setup:** open `dashboard/standalone_demo.html` and click the `broker_c (messy)` sample. You'll see the messy headers map to canonical fields, the score drop to 76.7 with "needs review," and the bad rows highlighted — including the orphan dependent at the bottom.
- **Run it:** `pip install -r requirements.txt` → `python src/generate_synthetic_censuses.py` → `python src/pipeline.py`
- **The API:** `uvicorn api:app` exposes `POST /normalize` returning clean rows + mapping + quality report.
- Repo + README + tests + a walkthrough notebook are all included.

## Why I'm sharing this

I could have written "experienced with messy healthcare data and data quality" on a resume. I'd rather show it working against your real bottleneck. I'd love to talk about where the actual census/TPA ingestion pain is hardest for your team right now, and how I'd help.

— Prathiksha · prathikshamurs@gmail.com
