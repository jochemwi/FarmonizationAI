"""Persistent memory helper: the playbook (one JSON file) and the agent's proposal queue."""
import argparse
import json
import os
import tempfile
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PLAYBOOK = DATA_DIR / "playbook.json"


def proposals_path():
    """Per-run review queue the agent writes to (untracked, outside the memory folder)."""
    return Path(os.environ.get("PROPOSALS_FILE", "/app/output/playbook_proposals.json"))


def read_json(path):
    """Return the list of entries in a file; empty list if the file doesn't exist yet."""
    if not path.exists():
        return []
    return json.loads(path.read_text())


def write_json(path, entries):
    """Write atomically: temp file in the same folder, then rename over the original."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.chmod(tmp, 0o644)  # mkstemp creates 0600; make readable for the host user and git
    with os.fdopen(fd, "w") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, path)


def load():
    return read_json(PLAYBOOK)


def save(entries):
    write_json(PLAYBOOK, entries)


def next_id(entries, prefix="p"):
    """p001, p002, ... based on the highest existing number."""
    nums = [int(e["id"][len(prefix):]) for e in entries if e["id"][len(prefix):].isdigit()]
    return f"{prefix}{max(nums, default=0) + 1:03d}"


REQUIRED = {"type", "title", "keywords", "when_to_use", "guidance", "background"}
OPTIONAL = {"limits", "kind", "priority", "trigger", "source_context",
            "agent_proposal", "user_answer", "run_id", "outcome"}
ENUMS = {
    "type": {"HITL", "reflection"},
    "kind": {"column_mapping", "unit", "value_recode", "other"},
    "priority": {"must", "should"},
    "trigger": {"low_similarity", "small_margin", "out_of_range", "other"},
    "outcome": {"success", "failure"},
}


def validate(fields):
    """Raise ValueError on missing, unknown or invalid fields."""
    missing = REQUIRED - fields.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    unknown = fields.keys() - REQUIRED - OPTIONAL
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    for name, allowed in ENUMS.items():
        if name in fields and fields[name] not in allowed:
            raise ValueError(f"{name} must be one of {sorted(allowed)}, got {fields[name]!r}")


def new_entry(entries, prefix, status, fields):
    """Auto-fill id, created date and status around the given fields."""
    return {
        "id": next_id(entries, prefix),
        "created": date.today().isoformat(),
        "type": fields["type"],
        "status": status,
        **{k: v for k, v in fields.items() if k != "type"},
    }


def add(**fields):
    """Add an active entry to the playbook (for the owner, not the agent)."""
    validate(fields)
    entries = load()
    entry = new_entry(entries, "p", "active", fields)
    entries.append(entry)
    save(entries)
    return entry


def propose(**fields):
    """Agent-facing: append a proposed entry to the proposals file. The playbook is not touched."""
    fields = {"type": "reflection", **fields}
    validate(fields)
    path = proposals_path()
    entries = read_json(path)
    entry = new_entry(entries, "pr", "proposed", fields)
    entries.append(entry)
    write_json(path, entries)
    return entry


def list_entries(entry_type=None):
    """Active playbook entries, optionally only one type."""
    return [e for e in load()
            if e["status"] == "active" and (entry_type is None or e["type"] == entry_type)]


def search(query):
    """Case-insensitive keyword search over active entries."""
    q = query.lower()
    return [e for e in list_entries() if q in json.dumps(e).lower()]


def set_status(entry_id, status):
    """Change the status of one entry and return it."""
    entries = load()
    for e in entries:
        if e["id"] == entry_id:
            e["status"] = status
            save(entries)
            return e
    raise ValueError(f"no entry with id {entry_id}")


def delete(entry_id):
    """Remove one entry from the playbook."""
    entries = load()
    kept = [e for e in entries if e["id"] != entry_id]
    if len(kept) == len(entries):
        raise ValueError(f"no entry with id {entry_id}")
    save(kept)


def add_entry_args(parser):
    parser.add_argument("--title", required=True)
    parser.add_argument("--when-to-use", required=True)
    parser.add_argument("--guidance", required=True)
    parser.add_argument("--background", required=True)
    parser.add_argument("--keywords", required=True, nargs="+")


def entry_fields(args):
    fields = {
        "title": args.title,
        "when_to_use": args.when_to_use,
        "guidance": args.guidance,
        "background": args.background,
        "keywords": args.keywords,
    }
    for name in ("limits", "run_id", "outcome"):
        value = getattr(args, name, None)
        if value:
            fields[name] = value
    return fields


def main():
    parser = argparse.ArgumentParser(description="Persistent memory: the playbook and the agent's proposal queue")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add an entry to the playbook (for the owner; the agent uses propose)")
    p_add.add_argument("--type", required=True, choices=sorted(ENUMS["type"]))
    add_entry_args(p_add)
    p_add.add_argument("--limits")
    p_add.add_argument("--run-id")
    p_add.add_argument("--outcome", choices=sorted(ENUMS["outcome"]))

    p_prop = sub.add_parser("propose", help="propose an entry for review (written to the proposals file, not the playbook)")
    p_prop.add_argument("--run-id", required=True)
    add_entry_args(p_prop)
    p_prop.add_argument("--outcome", required=True, choices=sorted(ENUMS["outcome"]))

    p_list = sub.add_parser("list", help="list active entries")
    p_list.add_argument("--type", choices=sorted(ENUMS["type"]))

    p_search = sub.add_parser("search", help="keyword search over active entries")
    p_search.add_argument("query")

    p_deact = sub.add_parser("deactivate", help="set an entry to inactive (kept in the file, skipped by list and search)")
    p_deact.add_argument("id")

    p_del = sub.add_parser("delete", help="permanently remove an entry")
    p_del.add_argument("id")

    args = parser.parse_args()
    if args.command == "add":
        entry = add(type=args.type, **entry_fields(args))
        print(f"added {entry['id']}")
    elif args.command == "propose":
        entry = propose(**entry_fields(args))
        print(f"proposed {entry['id']} (written to {proposals_path()}, not the playbook)")
    elif args.command == "list":
        print(json.dumps(list_entries(args.type), indent=2))
    elif args.command == "search":
        print(json.dumps(search(args.query), indent=2))
    elif args.command == "deactivate":
        entry = set_status(args.id, "inactive")
        print(f"deactivated {entry['id']}")
    elif args.command == "delete":
        delete(args.id)
        print(f"deleted {args.id}")


if __name__ == "__main__":
    main()