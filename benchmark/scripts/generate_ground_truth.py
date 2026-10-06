"""
Generate a perfect ICASA-compliant ground truth dataset.
Saved to data/ground_truth.xlsx — keep this hidden from the agent.
"""
import pandas as pd
from pathlib import Path

OUT = Path("benchmark/ground_truth.xlsx")
OUT.parent.mkdir(exist_ok=True)

# --- FIELDS ---
fields = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "FL_LAT": 52.0116, "FL_LONG": 5.6642,
     "COUNTRY": "Netherlands", "FL_SILT": 35.0, "FL_CLAY": 18.0, "FL_SAND": 47.0,
     "SLDP": 120, "FLHST": "IB001", "SLTX": "Sandy loam"},
])

# --- TREATMENTS ---
treatments = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "TRTNO": t, "TNAME": f"N{n}kg",
     "NFACT": 1, "IRFACT": 1, "SMFACT": 1}
    for t, n in enumerate([0, 60, 120, 180], start=1)
])

# --- FERTILIZERS ---
fertilizers = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "TRTNO": t, "FDATE": "2022-05-10",
     "FECD": "FE005", "FEACD": "AP002", "FEDEP": 5, "FEAMN": n}
    for t, n in enumerate([0, 60, 120, 180], start=1)
])

# --- IRRIGATION ---
irrigation = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "TRTNO": t, "IDATE": "2022-06-15",
     "IROP": "IR004", "IRVAL": 25}
    for t in range(1, 5)
])

# --- SOIL INITIAL ---
soil = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "TRTNO": t, "ICBL": d,
     "ICH2O": 0.28, "ICNO3": 12.5, "ICNH4": 2.1}
    for t in range(1, 5) for d in [10, 20, 40, 60, 100]
])

# --- SUMMARY (yield outcomes) ---
import random
random.seed(42)
summary = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "TRTNO": t, "RP": r,
     "HWAH": round(4000 + n * 18 + random.gauss(0, 150), 1),
     "CWAH": round(9000 + n * 30 + random.gauss(0, 300), 1),
     "HDATE": "2022-09-20", "ADAT": "2022-07-01"}
    for t, n in enumerate([0, 60, 120, 180], start=1)
    for r in range(1, 6)
])

# --- BIOMASS OBS ---
biomass = pd.DataFrame([
    {"EXNAME": "MZ_NL_2022", "TRTNO": t, "RP": r,
     "OBDAT": "2022-08-01", "LAID": round(3.2 + t * 0.3, 2),
     "CWAD": round(6000 + t * 400 + random.gauss(0, 200), 1)}
    for t in range(1, 5) for r in range(1, 6)
])

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    fields.to_excel(w, sheet_name="FIELDS", index=False)
    treatments.to_excel(w, sheet_name="TRTMENTS", index=False)
    fertilizers.to_excel(w, sheet_name="FERTILIZERS", index=False)
    irrigation.to_excel(w, sheet_name="IRRIGATION", index=False)
    soil.to_excel(w, sheet_name="SOIL_INITIAL", index=False)
    summary.to_excel(w, sheet_name="SUMMARY", index=False)
    biomass.to_excel(w, sheet_name="BIOMASS_OBS", index=False)

print(f"Ground truth written to {OUT}")