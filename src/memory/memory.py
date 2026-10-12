    """Persistent memory helper: HITL corrections and reflections (JSON files)."""
    import json
    import os
    import tempfile
    from pathlib import Path
    from datetime import date
    import argparse

    DATA_DIR = Path(__file__).parent / "data"
    FILES = {
        "hitl": DATA_DIR / "hitl.json",
        "reflection": DATA_DIR / "reflections.json",
    }

    def load(kind):
        """Return the list of entries for a memory type; empty list if the file doesn't exist yet."""
        path = FILES[kind]
        if not path.exists():
            return []
        return json.loads(path.read_text())


    def save(kind, entries):
        """Write atomically: temp file in the same folder, then rename over the original."""
        path = FILES[kind]
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp, path)

    PREFIX = {"hitl": "h", "reflection": "r"}

    def next_id(kind, entries):
        """h001, h002, ... / r001, r002, ... based on the highest existing number."""
        nums = [int(e["id"][1:]) for e in entries if e["id"][1:].isdigit()]
        return f"{PREFIX[kind]}{max(nums, default=0) + 1:03d}"

    REQUIRED = {
        "hitl": {"kind", "title", "when_to_use", "keywords", "correction",
                "rationale", "limits", "user_answer", "priority"},
        "reflection": {"run_id", "title", "situation", "what_happened",
                    "lesson", "outcome", "keywords"},
    }
    OPTIONAL = {
        "hitl": {"schema_bindings"},
        "reflection": set(),
    }
    ENUMS = {
        "hitl": {
            "kind": {"column_mapping", "unit", "value_recode", "other"},
            "priority": {"must", "should"},
        },
        "reflection": {"outcome": {"success", "failure"}},
    }
    PROVENANCE = {"hitl": "HITL", "reflection": "reflection"}

    def validate(kind, fields):
        """Raise ValueError on missing, unknown or invalid fields."""
        missing = REQUIRED[kind] - fields.keys()
        if missing:
            raise ValueError(f"missing fields: {sorted(missing)}")
        unknown = fields.keys() - REQUIRED[kind] - OPTIONAL[kind]
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        for name, allowed in ENUMS[kind].items():
            if fields[name] not in allowed:
                raise ValueError(f"{name} must be one of {sorted(allowed)}, got {fields[name]!r}")

    def add(kind, /, **fields):
        """Create a new active entry with auto-filled id, created date, provenance and status."""
        validate(kind, fields)
        entries = load(kind)
        entry = {
            "id": next_id(kind, entries),
            "created": date.today().isoformat(),
            "provenance": PROVENANCE[kind],
            **({"schema_bindings": []} if kind == "hitl" else {}),
            **fields,
            "status": "active",
        }
        entries.append(entry)
        save(kind, entries)
        return entry

    def list_entries(kind):
        """Active entries only."""
        active = []
        for e in load(kind):
            if e["status"] == "active":
                active.append(e)
        return active

    def search(query):
        """Case-insensitive keyword search over active entries of both types."""
        q = query.lower()
        results = []
        for kind in FILES:
            for e in list_entries(kind):
                if q in json.dumps(e).lower():
                    results.append({"type": kind, **e})
        return results

    def main():
        parser = argparse.ArgumentParser(description="Persistent memory: HITL corrections and reflections")
        sub = parser.add_subparsers(dest="command", required=True)

        p_add = sub.add_parser("add", help="add a reflection")
        p_add.add_argument("--run-id", required=True)
        p_add.add_argument("--title", required=True)
        p_add.add_argument("--situation", required=True)
        p_add.add_argument("--what-happened", required=True)
        p_add.add_argument("--lesson", required=True)
        p_add.add_argument("--outcome", required=True, choices=sorted(ENUMS["reflection"]["outcome"]))
        p_add.add_argument("--keywords", required=True, nargs="+")

        p_hitl = sub.add_parser("add-hitl", help="add a HITL correction")
        p_hitl.add_argument("--kind", required=True, choices=sorted(ENUMS["hitl"]["kind"]))
        p_hitl.add_argument("--title", required=True)
        p_hitl.add_argument("--when-to-use", required=True)
        p_hitl.add_argument("--keywords", required=True, nargs="+")
        p_hitl.add_argument("--correction", required=True)
        p_hitl.add_argument("--rationale", required=True)
        p_hitl.add_argument("--limits", required=True)
        p_hitl.add_argument("--user-answer", required=True)
        p_hitl.add_argument("--priority", required=True, choices=sorted(ENUMS["hitl"]["priority"]))
        p_hitl.add_argument("--schema-bindings", nargs="*")

        p_list = sub.add_parser("list", help="list active entries")
        p_list.add_argument("kind", choices=["hitl", "reflection"])

        p_search = sub.add_parser("search", help="keyword search over active entries")
        p_search.add_argument("query")

        args = parser.parse_args()
        if args.command == "add":
            entry = add(
                "reflection",
                run_id=args.run_id,
                title=args.title,
                situation=args.situation,
                what_happened=args.what_happened,
                lesson=args.lesson,
                outcome=args.outcome,
                keywords=args.keywords,
            )
            print(f"added {entry['id']}")
        elif args.command == "add-hitl":
            fields = dict(
                kind=args.kind,
                title=args.title,
                when_to_use=args.when_to_use,
                keywords=args.keywords,
                correction=args.correction,
                rationale=args.rationale,
                limits=args.limits,
                user_answer=args.user_answer,
                priority=args.priority,
            )
            if args.schema_bindings:
                fields["schema_bindings"] = args.schema_bindings
            entry = add("hitl", **fields)
            print(f"added {entry['id']}")
        elif args.command == "list":
            print(json.dumps(list_entries(args.kind), indent=2))
        elif args.command == "search":
            print(json.dumps(search(args.query), indent=2))


    if __name__ == "__main__":
        main()