"""
Take the perfect ground truth and deliberately corrupt it to mimic real-world messy data.
Output: data/synthetic_messy.xlsx — this is what the agent sees.
"""
import pandas as pd
import random
from pathlib import Path

random.seed(99)

SRC = Path("benchmark/data/ground_truth.xlsx")
OUT = Path("benchmark/data/synthetic_messy.xlsx")

gt = pd.read_excel(SRC, sheet_name=None)  # all tabs

fields     = gt["FIELDS"].copy()
treatments = gt["TRTMENTS"].copy()
fertilizers= gt["FERTILIZERS"].copy()
irrigation = gt["IRRIGATION"].copy()
soil       = gt["SOIL_INITIAL"].copy()
summary    = gt["SUMMARY"].copy()
biomass    = gt["BIOMASS_OBS"].copy()

# ── 1. DECOMPOSE UIDs ──────────────────────────────────────────────────────────
# Split EXNAME into separate Experiment + Crop + Year columns, drop EXNAME
for df in [fields, treatments, fertilizers, irrigation, soil, summary, biomass]:
    df[["Experiment", "Crop_code", "Year"]] = df["EXNAME"].str.split("_", expand=True)
    df.drop(columns=["EXNAME"], inplace=True)

# ── 2. SCRAMBLE DATE FORMATS ───────────────────────────────────────────────────
DATE_FORMATS = [
    lambda d: d,                          # YYYY-MM-DD (keep some)
    lambda d: d.replace("-", "/"),        # YYYY/MM/DD
    lambda d: f"{d[8:]}/{d[5:7]}/{d[:4]}",  # DD/MM/YYYY
    lambda d: f"{d[5:7]}-{d[8:]}-{d[2:4]}",  # MM-DD-YY
    lambda d: pd.Timestamp(d).strftime("%b %d %Y"),  # Sep 20 2022
]

def corrupt_date(val):
    if pd.isna(val): return val
    return random.choice(DATE_FORMATS)(str(val))

for df, cols in [
    (fertilizers, ["FDATE"]),
    (irrigation,  ["IDATE"]),
    (summary,     ["HDATE", "ADAT"]),
    (biomass,     ["OBDAT"]),
]:
    for col in cols:
        df[col] = df[col].apply(corrupt_date)

# ── 3. WRONG UNITS ─────────────────────────────────────────────────────────────
# ── 3. WRONG UNITS ─────────────────────────────────────────────────────────────
def corrupt_yield(row):
    if row["TRNO"] % 2 == 0:
        return round(row["HWAH"] / 1000, 3), "ton/ha"
    return row["HWAH"], "kg/ha"

summary[["HWAH", "HWAH_unit"]] = summary.apply(
    corrupt_yield, axis=1, result_type="expand"
)

# ── 4. PARTIAL COORDINATES — drop COUNTRY for half the rows ───────────────────
fields.loc[0, "COUNTRY"] = None   # only 1 row here; drop country

# ── 5. RENAME / MISNAME COLUMNS ───────────────────────────────────────────────
fields.rename(columns={
    "FL_LAT": "Latitude", "FL_LONG": "Longitude",
    "SLDP": "SoilDepth_cm", "SLTX": "SoilTexture"
}, inplace=True)

soil.rename(columns={
    "ICBL": "depth_cm", "ICH2O": "VWC", "ICNO3": "NO3_ppm", "ICNH4": "NH4_ppm"
}, inplace=True)

fertilizers.rename(columns={"FEAMN": "N_applied_kg_ha"}, inplace=True)

summary.rename(columns={"HWAH": "grain_yield", "CWAH": "total_biomass"}, inplace=True)

# ── 6. SPLIT INTO MESSY TABS WITH NON-STANDARD NAMES ─────────────────────────
# Merge some tables together, give tabs confusing names
field_soil = pd.merge(fields, soil, on=["TRNO", "Experiment", "Crop_code", "Year"], how="outer")
treat_fert = pd.merge(treatments, fertilizers,
                      on=["TRNO", "Experiment", "Crop_code", "Year"], how="outer")

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    field_soil.to_excel(w,  sheet_name="Site & Soil Data",    index=False)
    treat_fert.to_excel(w,  sheet_name="Mgmt_Treatments",     index=False)
    irrigation.to_excel(w,  sheet_name="Irrigation",          index=False)
    summary.to_excel(w,     sheet_name="Yield Results 2022",  index=False)
    biomass.to_excel(w,     sheet_name="Biomass_Observations",index=False)

print(f"Messy dataset written to {OUT}")
print("\nCorruptions applied:")
print("  ✓ EXNAME decomposed → Experiment / Crop_code / Year")
print("  ✓ Date formats scrambled (5 different formats mixed)")
print("  ✓ HWAH: even treatments in ton/ha, odd in kg/ha")
print("  ✓ COUNTRY dropped from field location")
print("  ✓ Column names renamed away from ICASA standard")
print("  ✓ FIELDS+SOIL merged into one tab, TRTMENTS+FERTILIZERS merged")
print("  ✓ Tab names non-standard")