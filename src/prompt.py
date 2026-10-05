from src.config import COMPONENTS

SCHEMA_PATH = "/app/data/ontology/icasa/icasa.json"
PROMPT_VERSION = "v1"

def build_prompt() -> str:
    if COMPONENTS["icasa"]:
        harmonize = f"Harmonize the data to ICASA standard format using the schema at {SCHEMA_PATH}."
    else:
        harmonize = (
            "Harmonize the data to ICASA standard format, using ICASA code names. "
            "No schema file is provided; rely on your own knowledge of ICASA."
        )

    return f"""
You are given a messy agricultural field trial dataset at /app/input/synthetic_messy.xlsx.

Your task:
1. Read all tabs in the file and understand the structure.
2. {harmonize}
3. Reconstruct the EXNAME field by combining Experiment_Crop_code_Year columns.
4. Standardize all dates to YYYY-MM-DD format.
5. Convert all yield values to kg/ha (check the HWAH_unit column).
6. Map non-standard column names back to ICASA field names.
7. Output the result as /app/output/harmonized.xlsx with one tab per ICASA table:
   FIELDS, TRTMENTS, FERTILIZERS, IRRIGATION, SOIL_INITIAL, SUMMARY, BIOMASS_OBS.
8. Before finishing, verify the full output, not just the first rows. For every tab:
   - print the row count and the unique values per column
   - print the number of missing values per column
   - check that dates are all YYYY-MM-DD and numeric values are in plausible ranges
   Fix any problems you find and re-run the checks.
"""
