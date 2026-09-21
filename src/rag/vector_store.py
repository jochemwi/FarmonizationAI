import os

import chromadb

client = chromadb.PersistentClient(path="data/chroma/test")

collection = client.create_collection(name="my_collection")