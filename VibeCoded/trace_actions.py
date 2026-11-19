"""Group the steps of one run into actions.

Input:  a JSON list of Langfuse observations (from fetch_trace.py or an events export).
Output: a JSON file {label: {"actions": [...], "duration_min": float}}.

An iteration is one llm_call generation plus the tool call that follows it.
An action is a run of iterations that ends when
  - the harness validator is run (kind "validate"),
  - the build script is written or run (kind "build"),
  - the agent logs a question with log_question (kind "question", its own action),
  - the run ends (kind "final").
Leftover iterations at the end of the run are kind "explore".

Example:
    python trace_actions.py run.json --label Embeddings -o actions.json
"""
import argparse
import json
import re
from datetime import datetime, timezone

# Longest text kept per field (characters). Raise them if the viewer still shows a trailing ' …'.
MAX_TEXT = 4000
MAX_QUESTION = 4000
MAX_COMMAND = 30000
MAX_OUTPUT = 20000


def ts(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def load(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def category(command):
    if "python -m src.memory.semantic_search" in command:
        return "semantic search"
    if "memory.py search" in command:
        return "keyword search"
    if "memory.py propose" in command:
        return "memory proposal"
    if "--validate-package" in command:
        return "validator"
    if re.search(r"build\.py|cat > /app/workspace", command):
        return "build script"
    return "other bash"


def clip(text, n):
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    return text if len(text) <= n else text[:n].rstrip() + " …"


def usage_of(e):
    u = load(e.get("usageDetails")) or {}
    return (u.get("input") or 0, u.get("output") or 0) if isinstance(u, dict) else (0, 0)


def build_actions(events):
    t0 = min(ts(e["startTime"]) for e in events if e.get("startTime"))
    mins = lambda t: round((t - t0) / 60, 3)
    gens = sorted([e for e in events if e["type"] == "GENERATION"], key=lambda e: ts(e["startTime"]))
    tools = sorted([e for e in events if e["type"] == "TOOL"], key=lambda e: ts(e["startTime"]))

    iterations = []
    for i, g in enumerate(gens):
        g_start, g_end = ts(g["startTime"]), ts(g["endTime"])
        nxt = ts(gens[i + 1]["startTime"]) if i + 1 < len(gens) else float("inf")
        o = load(g["output"])
        content = o.get("content") if isinstance(o, dict) else None
        text, reasoning = "", []
        if isinstance(content, list):
            for b in content:
                if b.get("type") == "text" and not text:
                    text = b["text"].strip()
                if b.get("type") == "reasoning":
                    reasoning += [s["text"].strip("* ") for s in b.get("summary", [])]
        elif isinstance(content, str):
            text = content.strip()
        calls = (o.get("tool_calls") or []) if isinstance(o, dict) else []
        call = calls[0] if calls else None
        tin, tout = usage_of(g)
        it = {"n": i + 1, "start_min": mins(g_start),
              "llm": {"dur_s": round(g_end - g_start, 1), "text": clip(text, MAX_TEXT), "reasoning": reasoning[:6],
                      "in_tokens": tin, "out_tokens": tout, "cost_usd": round(g.get("totalCost") or 0, 4)},
              "tool": None, "question": ""}
        if call and call["name"] == "log_question":
            q = call["args"].get("question", "") if isinstance(call["args"], dict) else ""
            it["question"] = clip(q, MAX_QUESTION)
            it["end_min"] = mins(g_end)
        elif call:
            args = call["args"] if isinstance(call["args"], dict) else {}
            command = args.get("command", "")
            t = next((t for t in tools if g_end - 1 <= ts(t["startTime"]) < nxt), None)
            result = clip(load(t["output"]), MAX_OUTPUT) if t else ""
            it["tool"] = {"name": call["name"], "description": args.get("description") or clip(command, 90),
                          "command": clip(command, MAX_COMMAND), "output": result, "category": category(command),
                          "dur_s": round(ts(t["endTime"]) - ts(t["startTime"]), 1) if t else 0}
            it["end_min"] = mins(ts(t["endTime"])) if t else mins(g_end)
        else:
            it["end_min"] = mins(g_end)
        iterations.append(it)

    actions, cur = [], []

    def close(kind):
        nonlocal cur
        if not cur:
            return
        last = cur[-1]
        if kind == "question":
            q = last["question"].split("\n")[0]
            title = "Asks: " + (q if len(q) <= 130 else q[:130].rsplit(" ", 1)[0] + " …")
        elif kind == "final":
            title = "Final answer"
        else:
            title = last["tool"]["description"] if last["tool"] else "Explore"
        start, end = cur[0]["start_min"], last["end_min"]
        actions.append({"id": len(actions) + 1, "title": title, "kind": kind, "start_min": start,
                        "end_min": end, "dur_s": round((end - start) * 60, 1),
                        "iterations": cur})
        cur = []

    for it in iterations:
        if it["question"]:
            close("explore")
            cur = [it]
            close("question")
        elif it["tool"] is None:
            cur.append(it)
            close("final")
        else:
            cur.append(it)
            cat = it["tool"]["category"]
            if cat == "validator":
                close("validate")
            elif cat == "build script":
                close("build")
    close("explore")
    return {"actions": actions, "duration_min": max(a["end_min"] for a in actions)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("events", help="JSON list of observations")
    ap.add_argument("--label", default="Run", help="Name of this run in the output")
    ap.add_argument("-o", "--out", default="actions.json")
    args = ap.parse_args()
    events = json.load(open(args.events, encoding="utf-8"))
    result = build_actions(events)
    json.dump({args.label: result}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    acts = result["actions"]
    steps = sum(len(a["iterations"]) for a in acts)
    questions = sum(a["kind"] == "question" for a in acts)
    print(f"{args.label}: {len(acts)} actions, {steps} steps, {questions} questions, "
          f"{result['duration_min']:.1f} min")


if __name__ == "__main__":
    main()
