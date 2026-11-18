"""Sync ICASA and the playbook into Chroma. Only new or changed entries are embedded."""
from src.memory.sources import icasa_items, playbook_items
from src.memory.vector_store import EMBED_MODEL, get_client, sync_collection


def main():
    client = get_client()
    print(f"embedding model: {EMBED_MODEL}")
    for name, loader in (("icasa", icasa_items), ("playbook", playbook_items)):
        print(f"{name}: {sync_collection(client, name, loader())}")


if __name__ == "__main__":
    main()