"""Semantic search over the synced collections.
Usage: python -m src.memory.semantic_search <icasa|playbook> "<query>" [-n 5]"""
import argparse
import json

from src.memory.vector_store import embed, get_client


def search(name, query, n=5):
    col = get_client().get_collection(name)
    res = col.query(query_embeddings=embed([query]), n_results=n,
                    include=["documents", "metadatas", "distances"])
    hits = []
    for i, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
        meta = {k: v for k, v in meta.items() if k != "hash"}
        hits.append({"id": i, "distance": round(dist, 3), "text": doc, "metadata": meta})
    return hits


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Semantic search over ICASA and the playbook")
    parser.add_argument("collection", choices=["icasa", "playbook"])
    parser.add_argument("query")
    parser.add_argument("-n", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(search(args.collection, args.query, args.n), indent=2, ensure_ascii=False))
    