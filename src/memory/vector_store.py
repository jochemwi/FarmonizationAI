"""Local embeddings (sentence-transformers) and the Chroma client."""
import os
import atexit
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

import chromadb

from src.constants import EMBED_MODEL
from src.memory.memory import list_entries

CHROMA_DIR = Path(os.getenv("CHROMA_DIR") or Path(__file__).parent / "data" / "chroma")

@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


def embed(texts):
    """Embed a list of texts locally; returns a list of vectors."""
    return _model().encode(texts, normalize_embeddings=True).tolist()

# Fields that make an entry findable: the situation, keywords, where it came up, and what to do.
EMBED_FIELDS = ["title", "when_to_use", "keywords", "source_context", "guidance"]


def embed_text(entry):
    """The exact text that gets embedded (and hashed) for one entry."""
    parts = []
    for name in EMBED_FIELDS:
        value = entry.get(name)
        if not value:
            continue
        if isinstance(value, list):
            value = " ".join(value)
        parts.append(f"{name}: {value}")
    return "\n".join(parts)


def entry_hash(text, model):
    """Fingerprint of the embedded text plus the model name."""
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


def get_client():
    """Persistent Chroma store. A read-only snapshot is opened through a temporary copy,
    because Chroma writes lock files next to its database."""
    if os.access(CHROMA_DIR.parent, os.W_OK):  # building a snapshot
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        path = CHROMA_DIR
    elif CHROMA_DIR.exists():  # read-only snapshot during a run
        tmp = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, tmp, True)
        path = Path(tmp) / "chroma"
        shutil.copytree(CHROMA_DIR, path)
    else:
        raise RuntimeError("No embedding index in this configuration")
    return chromadb.PersistentClient(path=str(path))


def sync_collection(client, name, items):
    """items: {id: (text, metadata)}. Embeds only new or changed entries and removes stale ones.
    Metadata values must be str, int, float or bool (no lists)."""
    col = client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
    stored = col.get(include=["metadatas"])
    stored_hash = {i: (m or {}).get("hash") for i, m in zip(stored["ids"], stored["metadatas"])}
    new_hash = {i: entry_hash(text, EMBED_MODEL) for i, (text, _) in items.items()}
    todo = [i for i, h in new_hash.items() if stored_hash.get(i) != h]
    stale = [i for i in stored_hash if i not in items]

    if stale:
        col.delete(ids=stale)
    if todo:
        texts = [items[i][0] for i in todo]
        col.upsert(
            ids=todo,
            embeddings=embed(texts),
            documents=texts,
            metadatas=[{**items[i][1], "hash": new_hash[i]} for i in todo],
        )
    return {"embedded": len(todo), "removed": len(stale), "unchanged": len(items) - len(todo)}


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
    items = {}
    for entry in list_entries():
        meta = {name: str(entry.get(name, "")) for name in PLAYBOOK_META_FIELDS}
        items[entry["id"]] = (embed_text(entry), meta)
    return items
