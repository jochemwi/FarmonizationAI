"""
Compare agent output against ground truth.
Run AFTER the agent has produced benchmark/output/harmonized.xlsx.

Per table:
  name_score    % of ground-truth columns present in the output with the exact name
  value_score   match rate on columns present in both (NaN if a key column is missing)
  row_coverage  fraction of ground-truth rows found in the output (NaN if a key is missing)
"""
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import CONFIG_NAME, MODEL_NAME, PROMPT_VERSION, DATA_VERSION

GT = Path("benchmark/ground_truth.xlsx")
OUT = Path("benchmark/output/harmonized.xlsx")
RESULTS = Path("benchmark/results/runs.csv")

if not OUT.exists():
    print("No agent output found at benchmark/output/harmonized.xlsx, run the harness first.")
    sys.exit(1)

gt = pd.read_excel(GT, sheet_name=None)
out = pd.read_excel(OUT, sheet_name=None)

TABLES = ["FIELDS", "TRTMENTS", "FERTILIZERS", "IRRIGATION", "SOIL_INITIAL", "SUMMARY", "BIOMASS_OBS"]
KEY_COLS = {
    "FIELDS":       ["EXNAME"],
    "TRTMENTS":     ["EXNAME", "TRTNO"],
    "FERTILIZERS":  ["EXNAME", "TRTNO"],
    "IRRIGATION":   ["EXNAME", "TRTNO"],
    "SOIL_INITIAL": ["EXNAME", "TRTNO", "ICBL"],
    "SUMMARY":      ["EXNAME", "TRTNO", "RP"],
    "BIOMASS_OBS":  ["EXNAME", "TRTNO", "RP"],
}


def norm_key(s):
    """Make key columns comparable: numbers as floats, everything else as stripped strings."""
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().all():
        return num.astype(float).astype(str)
    return s.astype(str).str.strip()


def as_text(s):
    if pd.api.types.is_datetime64_any_dtype(s):
        s = s.dt.strftime("%Y-%m-%d")
    return s.astype(str).str.strip()


results = []

for table in TABLES:
    if table not in gt:
        continue
    g = gt[table]
    keys = KEY_COLS[table]
    r = {"table": table, "rows_gt": len(g), "rows_out": None,
         "name_score": 0.0, "value_score": np.nan, "row_coverage": np.nan}

    if table not in out:
        r["status"] = "MISSING_IN_OUTPUT"
        r["row_coverage"] = 0.0
        results.append(r)
        continue

    o = out[table]
    r["rows_out"] = len(o)
    r["name_score"] = round(100 * sum(c in o.columns for c in g.columns) / len(g.columns), 1)

    if any(k not in o.columns for k in keys):
        r["status"] = "MISSING_KEYS"
        results.append(r)
        continue

    g = g.copy()
    o = o.copy()
    for k in keys:
        g[k] = norm_key(g[k])
        o[k] = norm_key(o[k])
    o = o.drop_duplicates(subset=keys)

    common_cols = [c for c in g.columns if c in o.columns and c not in keys]
    merged = g.merge(o[keys + common_cols], on=keys, how="left",
                     suffixes=("_gt", "_out"), indicator=True)
    found = merged["_merge"] == "both"
    r["row_coverage"] = round(float(found.mean()), 3)

    col_scores = []
    for col in common_cols:
        gcol, ocol = merged[f"{col}_gt"][found], merged[f"{col}_out"][found]
        if len(gcol) == 0:
            continue
        if pd.api.types.is_numeric_dtype(g[col]):
            match = np.isclose(gcol.astype(float), pd.to_numeric(ocol, errors="coerce"),
                               rtol=0.01, equal_nan=True)
        else:
            match = (as_text(gcol) == as_text(ocol)).to_numpy()
        col_scores.append(match.mean())

    r["value_score"] = round(float(np.mean(col_scores)) * 100, 1) if col_scores else np.nan
    r["status"] = "OK"
    results.append(r)

print("\n=== EVALUATION RESULTS ===\n")
print(f"  {'table':14s} {'names':>7s} {'values':>7s} {'rows':>7s}  status")
for r in results:
    v = "-" if pd.isna(r["value_score"]) else f"{r['value_score']:.1f}"
    c = "-" if pd.isna(r["row_coverage"]) else f"{r['row_coverage'] * 100:.0f}%"
    print(f"  {r['table']:14s} {r['name_score']:7.1f} {v:>7s} {c:>7s}  {r['status']}")

names = [r["name_score"] for r in results]
values = [r["value_score"] for r in results if not pd.isna(r["value_score"])]
covs = [r["row_coverage"] for r in results if not pd.isna(r["row_coverage"])]
n_missing_keys = sum(r["status"] == "MISSING_KEYS" for r in results)

row = {
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "config": CONFIG_NAME,
    "model": MODEL_NAME,
    "prompt_version": PROMPT_VERSION,
    "data_version": DATA_VERSION,
    "name_score": round(float(np.mean(names)), 1) if names else None,
    "value_score": round(float(np.mean(values)), 1) if values else None,
    "row_coverage": round(float(np.mean(covs)), 3) if covs else None,
    "tables_missing_keys": n_missing_keys,
    "tables_with_values": len(values),
}
for r in results:
    t = r["table"]
    row[f"name_{t}"] = r["name_score"]
    row[f"value_{t}"] = None if pd.isna(r["value_score"]) else r["value_score"]
    row[f"rows_out_{t}"] = r["rows_out"]
    row[f"status_{t}"] = r["status"]

print(f"\n  NAME SCORE {row['name_score']}   VALUE SCORE {row['value_score']} "
      f"(over {len(values)} tables)   missing-key tables: {n_missing_keys}")

RESULTS.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame([row]).to_csv(RESULTS, mode="a", header=not RESULTS.exists(), index=False)
print(f"\n  Logged to {RESULTS}")
