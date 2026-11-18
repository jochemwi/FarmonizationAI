"""Turn source data (ICASA csv and the playbook) into {id: (text, metadata)} for syncing."""
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


# stored next to the vector, so a search hit is usable on its own
PLAYBOOK_META_FIELDS = ["title", "type", "guidance", "limits"]


def playbook_items():
    from src.memory.embeddings import embed_text
    from src.memory.memory import list_entries
    items = {}
    for entry in list_entries():
        meta = {name: str(entry.get(name, "")) for name in PLAYBOOK_META_FIELDS}
        items[entry["id"]] = (embed_text(entry), meta)
    return items