import subprocess
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

from src.constants import BASH_MAX_OUTPUT, BASH_TIMEOUT_S

@tool
def bash(command: str, description: str) -> str:
    """
    Run a shell command. Always provide a description of what the command does.
    Returns combined stdout and stderr. Output is truncated if too long.
    """

    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            timeout=BASH_TIMEOUT_S,
            start_new_session=True      # allows killing the whole process group
        )

        output = result.stdout or ""

        # truncate from the front, keep the tail (errors usually at the end)
        if len(output) > BASH_MAX_OUTPUT:
            output = f"[...truncated {len(output) - BASH_MAX_OUTPUT} chars...]\n" + output[-BASH_MAX_OUTPUT:]

        if result.returncode != 0:
            return f"exit code {result.returncode}\n{output}"

        return output or "(no output)"

    except subprocess.TimeoutExpired:
        return f"error: command timed out after {BASH_TIMEOUT_S} seconds"
    except Exception as e:
        return f"error: {e}"

@tool
def log_question(question: str, context: str, assumed_answer: str) -> str:
    """Record a question for the human to review after the run. Nobody answers during the run.

    question: what you would ask, in one or two sentences.
    context: file, sheet, column and rows, the value, and the target table and variable concerned.
    assumed_answer: what you will do instead, and why.
    """
    path = Path(os.environ.get("QUESTIONS_FILE", "/app/output/questions.json"))
    path.parent.mkdir(parents=True, exist_ok=True)

    entries = json.loads(path.read_text()) if path.exists() else []
    qid = f"q{len(entries) + 1:03d}"
    entries.append({
        "id": qid,
        "run_id": os.environ.get("RUN_ID", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "context": context,
        "assumed_answer": assumed_answer,
    })

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    os.replace(tmp, path)  # atomic, so a crash never leaves a half-written file

    return (f"Recorded as {qid}. No answer will come during this run. "
            "Continue now with your assumed answer and apply it consistently.")