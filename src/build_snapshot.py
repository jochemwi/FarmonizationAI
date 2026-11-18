"""Build the memory snapshot for one config into /app/snapshot.
PLAYBOOK=1 copies playbook.json. EMBEDDINGS=1 builds a Chroma index (icasa, plus playbook when PLAYBOOK=1)."""
import os
import shutil
from pathlib import Path

from src.memory.memory import PLAYBOOK
from src.memory.sources import icasa_items, playbook_items
from src.memory.vector_store import EMBED_MODEL, get_client, sync_collection

SNAPSHOT = Path(os.environ.get("SNAPSHOT_DIR", "/app/snapshot"))


def flag(name):
    return os.environ.get(name, "0") == "1"


def main():
    # start from an empty folder (the mount point itself stays)
    for p in SNAPSHOT.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()

    if flag("PLAYBOOK"):
        shutil.copy(PLAYBOOK, SNAPSHOT / "playbook.json")
    if flag("EMBEDDINGS"):
        client = get_client()
        print(f"embedding model: {EMBED_MODEL}")
        print("icasa:", sync_collection(client, "icasa", icasa_items()))
        if flag("PLAYBOOK"):
            print("playbook:", sync_collection(client, "playbook", playbook_items()))
    print("snapshot contains:", sorted(p.name for p in SNAPSHOT.iterdir()))


if __name__ == "__main__":
    main()