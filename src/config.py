import os

CONFIGS = {
    "base":     {"icasa": False, "ontology": False, "storage": False},
    "icasa":    {"icasa": True,  "ontology": False, "storage": False},
    "ontology": {"icasa": True,  "ontology": True,  "storage": False},
    "storage":  {"icasa": True,  "ontology": True,  "storage": True},
}

CONFIG_NAME = os.getenv("FARMONIZER_CONFIG", "icasa")
MODEL_NAME = os.getenv("FARMONIZER_MODEL", "openai:gpt-5.6-sol")

if CONFIG_NAME not in CONFIGS:
    raise ValueError(f"Unknown FARMONIZER_CONFIG '{CONFIG_NAME}', choose from {list(CONFIGS)}")

COMPONENTS = CONFIGS[CONFIG_NAME]
PROMPT_VERSION = "v1"
