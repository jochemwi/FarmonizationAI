"""Build icasa.json from the raw ICASA CSVs and the cleaned target schema.

    python -m src.rag.build_icasa --scope target   # only the target-schema variables
    python -m src.rag.build_icasa --scope all      # all of ICASA + target-only extras
"""
import argparse
from pathlib import Path

import pandas as pd

from src.rag.icasa_schema import IcasaVariable

# set directories
ICASA_DIR = Path("data/ontology/icasa")
RAW = ICASA_DIR / "raw"
TARGET_CSV = Path("data/ontology/target/target_schema_clean.csv")
OUT = ICASA_DIR / "icasa.json"

ICASA_FILES = ["Measured_data", "Management_info", "Metadata", "Soils_data", "Weather_data"]

# Convert pandas NaN into Python None (so empty cells become null in the JSON)
def none_if_nan(value):
    return None if pd.isna(value) else value

# Read a column from a row, giving None for missing or empty values
def get_value(row: pd.Series, column: str):
    return none_if_nan(row.get(column, None))


def load_icasa() -> pd.DataFrame:
    frames = []                                         # start with an empty list

    for name in ICASA_FILES:                            # go through the file names
        path = RAW / f"{name}.csv"                      # e.g. data/ontology/icasa/raw/Metadata.csv
        df = pd.read_csv(path, dtype=str)               # read it, keeping every value as text
        frames.append(df)                               # add this table to the list

    combined = pd.concat(frames, ignore_index=True)     # stack all five tables into one
    return combined

#
def make_record(icasa: pd.Series | None, target: pd.Series | None) -> IcasaVariable:
    """Combine one ICASA row into a record,
        and/or one target row into a record.
        Target values win for the fields it defines; ICASA supplies the rest."""
    icasa_row = icasa if icasa is not None else pd.Series(dtype=object)
    target_row = target if target is not None else pd.Series(dtype=object)


    return IcasaVariable(
        id=get_value(icasa_row, "var_uid"),
        name=get_value(target_row, "Variable_Name") or get_value(icasa_row, "Variable_Name"),
        code=get_value(target_row, "Code_Display") or get_value(icasa_row, "Code_Display"),
        description=get_value(target_row, "Description") or get_value(icasa_row, "Description"),
        unit=get_value(target_row, "Unit_or_type") or get_value(icasa_row, "Unit_or_type"),
        unit_pint=get_value(target_row, "Unit_pint"),
        data_type=get_value(target_row, "Data_type") or get_value(icasa_row, "Data_type"),
        min=get_value(icasa_row, "MinVal"),
        max=get_value(icasa_row, "MaxVal"),
        dataset=get_value(icasa_row, "Dataset"),
        subset=get_value(icasa_row, "Subset"),
        group=get_value(icasa_row, "Group"),
        subgroup=get_value(icasa_row, "SubGroup"),
        required=get_value(target_row, "Required"),
        file=get_value(target_row, "File"),
        topic=get_value(target_row, "Topic"),
        example=get_value(target_row, "Example"),
        comment=get_value(target_row, "Comment"),
        in_icasa=icasa is not None,
        in_target=target is not None,
    )


def main(scope: str) -> None:
    icasa = load_icasa()
    target = pd.read_csv(TARGET_CSV, dtype=str)

    # the join key is the code, so it must be unique on the ICASA side
    duplicated_icasa_codes = set(icasa["Code_Display"][icasa["Code_Display"].duplicated(keep=False)])
    target_codes_with_duplicates = set(target["Code_Display"]) & duplicated_icasa_codes
    assert not target_codes_with_duplicates, f"target codes that match several ICASA rows: {sorted(target_codes_with_duplicates)}"
    icasa_by_code = icasa.set_index("Code_Display", drop=False)
    target_by_code = target.set_index("Code_Display", drop=False)

    records = []
    if scope == "target":
        for code, target_row in target_by_code.iterrows():
            icasa_row = icasa_by_code.loc[code] if code in icasa_by_code.index else None
            records.append(make_record(icasa_row, target_row))
    else:  # all: every ICASA row, then the target-only (custom) variables
        for _, icasa_row in icasa.iterrows():
            code = icasa_row["Code_Display"]
            target_row = target_by_code.loc[code] if code in target_by_code.index else None
            records.append(make_record(icasa_row, target_row))
        icasa_codes = set(icasa["Code_Display"])
        for code, target_row in target_by_code.iterrows():
            if code not in icasa_codes:
                records.append(make_record(None, target_row))

    OUT.write_text( # write to json
        "[" + ",\n".join(record.model_dump_json() for record in records) + "]", encoding="utf-8"
    )
    # validity check
    icasa_count = sum(record.in_icasa for record in records)
    target_count = sum(record.in_target for record in records)
    print(f"scope={scope}: wrote {len(records)} records "
          f"(in_icasa={icasa_count}, in_target={target_count}) -> {OUT}")

# decide wether full ICASA or FieldBigData is chosen
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["target", "all"], default="target")
    main(ap.parse_args().scope)
