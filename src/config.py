import os

CONFIGS = {
    "base":     {"ontology": False, "storage": False},
    "ontology": {"ontology": True,  "storage": False},
    "storage":  {"ontology": False, "storage": True},
}

CONFIG_NAME = os.getenv("FARMONIZER_CONFIG", "base")
MODEL_NAME = os.getenv("FARMONIZER_MODEL", "openai:gpt-5.6-sol")
TOKEN_LIMIT = int(os.getenv("FARMONIZER_TOKEN_LIMIT", "4000000"))

if CONFIG_NAME not in CONFIGS:
    raise ValueError(f"Unknown FARMONIZER_CONFIG '{CONFIG_NAME}', choose from {list(CONFIGS)}")

COMPONENTS = CONFIGS[CONFIG_NAME]
PROMPT_VERSION = "v1"
DATA_VERSION = "v1"
