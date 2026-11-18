"""Text selection and hashing for embeddings. No API calls in this file."""
import hashlib

# Fields that make an entry findable. The payload (correction, rationale, user_answer) is not embedded.
EMBED_FIELDS = {
    "hitl": ["title", "when_to_use", "keywords", "source_context"],
    "reflection": ["title", "situation", "lesson", "keywords"],
}


def embed_text(kind, entry):
    """The exact text that gets embedded (and hashed) for one entry."""
    parts = []
    for name in EMBED_FIELDS[kind]:
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