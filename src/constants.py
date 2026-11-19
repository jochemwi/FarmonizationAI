'''
Constants for the Harness

'''

import os

# Model settings
MODEL_NAME = "openai:gpt-6.1-sol"
REASONING = {"effort": "high", "summary": "detailed"}
EMBED_MODEL = os.getenv("EMBEDDING_MODEL") or "avsolatorio/GIST-all-MiniLM-L6-v2"

# Paths
FILL_API = "/app/data/target/harmonization_template/fill_api.py"
SUBMISSION_DIR = "/app/output/submission"
VALIDATE_ARGS = ["--validate-package", SUBMISSION_DIR, "--complete", "--final"]
VALIDATE_CMD = f"PYTHONPATH=/app/data/target python {FILL_API} {' '.join(VALIDATE_ARGS)}"

# Validation settings
MAX_VAL_ROUNDS = 3
EMPTY_TABLE_REVIEW_ROUNDS = 3

PLAYBOOK = os.getenv("PLAYBOOK") == "1"
EMBEDDINGS = os.getenv("EMBEDDINGS") == "1"

BASH_MAX_OUTPUT = 4000
BASH_TIMEOUT_S = 60

