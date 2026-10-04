"""Apply the agreed fixes to target_schema.csv and write target_schema_clean.csv."""
from pathlib import Path

import pandas as pd
import pint

SRC = Path("data/ontology/target/target_schema.csv")
DST = Path("data/ontology/target/target_schema_clean.csv")

DROP_CODES = {"RMTVAR"}  # pointer row, not a real variable

# Map unit strings from the source data to versions that pint can parse
UNIT_FIXES = { 
    "cm***3/cm***3": "cm**3/cm**3",
    "g/cm***3": "g/cm**3",
    "degree_C": "degC",
    "kg[N]/ha": "kg/ha",
    "kg[P]/ha": "kg/ha",
    "kg[K]/ha": "kg/ha",
    "%": "percent",
}

def main() -> None:
    df = pd.read_csv(SRC, dtype=str)

    # drop rows that are not real variables
    df = df[~df["Code_Display"].isin(DROP_CODES)].copy()

    # unit syntax (Unit_or_type keeps the original, e.g. kg[N]/ha)
    df["Unit_pint"] = df["Unit_pint"].replace(UNIT_FIXES)
    df.loc[df["Code_Display"] == "SPAD", "Unit_pint"] = "dimensionless"

    # Data_type fixes
    df.loc[df["Code_Display"].isin(["DEW", "EAID"]), "Data_type"] = "single"

    # required must be 0/1: the two conditional rows become 0, Dew_point is set to 0
    conditional = df["Required"] == "0-1-1900"
    df.loc[conditional, "Comment"] = "Conditionally required"
    df.loc[conditional, "Required"] = "0"
    df.loc[df["Code_Display"] == "DEW", "Required"] = "0"

    validate(df)
    df.to_csv(DST, index=False, encoding="utf-8")
    print(f"wrote {len(df)} rows -> {DST}")


def validate(df: pd.DataFrame) -> None:
    ureg = pint.UnitRegistry()
    bad_units = []
    for u in df["Unit_pint"].unique():
        try:
            ureg.Unit(u)
        except Exception:
            bad_units.append(u)
    assert not bad_units, f"unparseable units: {bad_units}"
    assert set(df["Data_type"]) <= {"single", "text"}, df["Data_type"].unique()
    assert set(df["Required"]) <= {"0", "1"}, df["Required"].unique()
    assert df["Code_Display"].is_unique, "duplicate codes"


if __name__ == "__main__":
    main()