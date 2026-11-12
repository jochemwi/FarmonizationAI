"""Embedding calls (OpenAI via LangChain) and the Chroma client."""
from pathlib import Path

import chromadb
from langchain_openai import OpenAIEmbeddings

EMBED_MODEL = "text-embedding-3-small"
CHROMA_DIR = Path(__file__).parent / "data" / "chroma"


def embed(texts):
    """Embed a list of texts; returns a list of vectors."""
    return OpenAIEmbeddings(model=EMBED_MODEL).embed_documents(texts)


def get_client():
    """Persistent Chroma store inside the writable memory folder."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))
