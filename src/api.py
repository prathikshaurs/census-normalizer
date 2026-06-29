"""
Census Normalizer API - the 'Underwriting API' framing.

POST /normalize   : upload a messy broker census (CSV/XLSX) ->
                    returns clean canonical rows + column mapping + quality report
GET  /            : serves the dashboard

Run:  uvicorn api:app -reload -port 8000   (from src/)
"""

import io
import os
import sys
import math

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse


def json_safe(obj):
    # Recursively replacing NaN/NaT/inf with None so the payload is valid JSON
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if obj is pd.NaT:
        return None
    try:
        if pd.isna(obj):
            return None
    except (ValueError, TypeError):
        pass
    return obj

sys.path.insert(0, os.path.dirname(__file__))
from normalizer import normalize_file
from validator import validate

app = FastAPI(title="Census Normalizer", version="1.0")

DASHBOARD = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")


@app.get("/", response_class=HTMLResponse)
def home():
    if os.path.exists(DASHBOARD):
        with open(DASHBOARD) as fh:
            return fh.read()
    return "<h1>Census Normalizer API</h1><p>POST a census to /normalize</p>"


@app.get("/sample/{name}")
def sample(name: str):
    from fastapi.responses import FileResponse
    raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    mapping = {
        "broker_a": "broker_a_census.csv",
        "broker_b": "broker_b_census.csv",
        "broker_c": "broker_c_census.csv",
        "broker_d": "broker_d_census.xlsx",
    }
    fname = mapping.get(name)
    if not fname:
        raise HTTPException(status_code=404, detail="unknown sample")
    path = os.path.join(raw_dir, fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="sample not generated yet")
    return FileResponse(path, filename=fname)


@app.post("/normalize")
async def normalize(file: UploadFile = File(...), group_id: str = "G001"):
    content = await file.read()
    name = file.filename or "upload"
    try:
        if name.endswith(".xlsx"):
            raw = pd.read_excel(io.BytesIO(content))
        else:
            raw = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    clean, mapping = normalize_file(raw, group_id=group_id, source_file=name)
    report, flagged = validate(clean)

    preview_records = clean.head(50).to_dict("records")

    payload = {
        "file": name,
        "group_id": group_id,
        "column_mapping": mapping,
        "unmapped_columns": [c for c in map(str, raw.columns) if c not in mapping],
        "report": report,
        "clean_preview": preview_records,
        "rows_total": len(clean),
    }
    return JSONResponse(json_safe(payload))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
