"""Build the memory snapshot for one config into /app/snapshot.
PLAYBOOK=1 copies playbook.json. EMBEDDINGS=1 builds a Chroma index (icasa, plus playbook when PLAYBOOK=1)."""
import shutil
from pathlib import Path

from src.constants import PLAYBOOK, EMBEDDINGS, EMBED_MODEL
from src.memory.playbook  import PLAYBOOK as PLAYBOOK_FILE
from src.memory.vector_store import icasa_items, playbook_items, get_client, sync_collection

SNAPSHOT = Path("/app/snapshot")


def main():
    # start from an empty folder (the mount point itself stays)
    for p in SNAPSHOT.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()

    if PLAYBOOK:
        shutil.copy(PLAYBOOK_FILE, SNAPSHOT / "playbook.json")
    if EMBEDDINGS:
        client = get_client()
        print(f"embedding model: {EMBED_MODEL}")
        print("icasa:", sync_collection(client, "icasa", icasa_items()))
        if PLAYBOOK:
            print("playbook:", sync_collection(client, "playbook", playbook_items()))
    print("snapshot contains:", sorted(p.name for p in SNAPSHOT.iterdir()))


if __name__ == "__main__":
    main()