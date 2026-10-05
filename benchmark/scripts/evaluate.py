"""
Compare agent output against ground truth.
Run AFTER the agent has produced output/harmonized.xlsx.
"""
import sys
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import CONFIG_NAME, MODEL_NAME, PROMPT_VERSION, DATA_VERSION

GT = Path("benchmark/ground_truth.xlsx")
OUT = Path("benchmark/output/harmonized.xlsx")
RESULTS = Path("benchmark/results/runs.csv")

if not OUT.exists():
    print("No agent output found at benchmark/output/harmonized.xlsx — run the harness first.")
    exit(1)

gt  = pd.read_excel(GT,  sheet_name=None)
out = pd.read_excel(OUT, sheet_name=None)

TABLES = ["FIELDS", "TRTMENTS", "FERTILIZERS", "IRRIGATION", "SOIL_INITIAL", "SUMMARY", "BIOMASS_OBS"]
KEY_COLS = {
    "FIELDS":       ["EXNAME", "TRTNO"],
    "TRTMENTS":     ["EXNAME", "TRTNO"],
    "FERTILIZERS":  ["EXNAME", "TRTNO"],
    "IRRIGATION":   ["EXNAME", "TRTNO"],
    "SOIL_INITIAL": ["EXNAME", "TRTNO", "ICBL"],
    "SUMMARY":      ["EXNAME", "TRTNO", "RP"],
    "BIOMASS_OBS":  ["EXNAME", "TRTNO", "RP"],
}

results = []

for table in TABLES:
    if table not in gt:
        results.append({"table": table, "status": "MISSING_IN_GT"})
        continue
    if table not in out:
        results.append({"table": table, "status": "MISSING_IN_OUTPUT", "score": 0})
        continue

    g = gt[table]
    o = out[table]

    keys = [k for k in KEY_COLS[table] if k in g.columns and k in o.columns]
    common_cols = [c for c in g.columns if c in o.columns and c not in keys]

    if not keys or not common_cols:
        results.append({"table": table, "status": "NO_COMPARABLE_COLS", "score": 0})
        continue

    g_merged = g.set_index(keys)[common_cols]
    o_merged = o.set_index(keys)[common_cols]
    aligned  = g_merged.join(o_merged, how="inner", lsuffix="_gt", rsuffix="_out")

    scores = []
    for col in common_cols:
        gt_col  = aligned[f"{col}_gt"]
        out_col = aligned[f"{col}_out"]

        if pd.api.types.is_numeric_dtype(gt_col):
            match = np.isclose(gt_col.astype(float), out_col.astype(float), rtol=0.01, equal_nan=True)
        else:
            match = gt_col.astype(str).str.strip() == out_col.astype(str).str.strip()

        scores.append(match.mean())

    score = round(np.mean(scores) * 100, 1)
    results.append({"table": table, "status": "OK", "score": score,
                    "rows_gt": len(g), "rows_out": len(o), "cols_compared": len(common_cols)})

print("\n=== EVALUATION RESULTS ===\n")
total_scores = []
for r in results:
    if r.get("score") is not None:
        total_scores.append(r["score"])
        print(f"  {r['table']:15s}  {r['score']:5.1f}%  ({r.get('rows_out','?')}/{r.get('rows_gt','?')} rows, {r.get('cols_compared','?')} cols)")
    else:
        print(f"  {r['table']:15s}  {r['status']}")

if total_scores:
    print(f"\n  OVERALL SCORE: {round(np.mean(total_scores), 1)}%")

row = {
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "config": CONFIG_NAME,
    "model": MODEL_NAME,
    "prompt_version": PROMPT_VERSION,
    "data_version": DATA_VERSION,
    "overall": round(np.mean(total_scores), 1) if total_scores else None,
}
for r in results:
    row[f"score_{r['table']}"] = r.get("score")
    row[f"rows_out_{r['table']}"] = r.get("rows_out")
row["rows_gt"] = {r["table"]: r.get("rows_gt") for r in results}.get("SUMMARY")

RESULTS.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame([row]).to_csv(RESULTS, mode="a", header=not RESULTS.exists(), index=False)
print(f"\n  Logged to {RESULTS}")