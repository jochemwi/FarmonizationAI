"""Turn source data (ICASA csv, later HITL and reflections) into {id: (text, metadata)} for syncing."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root on the host and /app in the container
ICASA_CSV = ROOT / "data" / "target" / "harmonization_template" / "scheme" / "icasa_variable.csv"

# What gets embedded: what the variable is. Identifiers and decision notes stay out.
ICASA_TEXT_FIELDS = ["Variable_Name", "Description", "Unit_or_type", "Group", "SubGroup"]
# What is stored next to the vector, so a search hit is usable without reopening the csv.
ICASA_META_FIELDS = ["Variable_Name", "Target_Sheet", "Unit_or_type", "Data_type", "MinVal", "MaxVal"]


def icasa_items():
    items = {}
    with ICASA_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("adapt_operation") or "") == "reject":
                continue  # rejected variables have no target field, so the agent can't map to them
            text = "\n".join(
                f"{name}: {row[name].strip()}"
                for name in ICASA_TEXT_FIELDS
                if (row.get(name) or "").strip()
            )
            items[row["var_uid"]] = (text, {name: (row.get(name) or "") for name in ICASA_META_FIELDS})
    return items


def _memory_items(kind, meta_fields):
    from src.memory.embeddings import embed_text
    from src.memory.memory import list_entries
    items = {}
    for entry in list_entries(kind):
        meta = {name: str(entry.get(name, "")) for name in meta_fields}
        items[entry["id"]] = (embed_text(kind, entry), meta)
    return items


def hitl_items():
    # the payload (correction, limits) is stored next to the vector so a search hit is usable on its own
    return _memory_items("hitl", ["title", "kind", "priority", "correction", "limits"])


def reflection_items():
    return _memory_items("reflection", ["title", "outcome", "lesson"])
