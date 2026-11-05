import subprocess
from typing import Literal

from langchain_core.tools import tool

@tool
def bash(command: str, description: str) -> str:
    """
    Run a shell command. Always provide a description of what the command does.
    Returns combined stdout and stderr. Output is truncated if too long.
    """
    MAX_OUTPUT = 4000

    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            timeout=60,
            start_new_session=True      # allows killing the whole process group
        )

        output = result.stdout or ""

        # truncate from the front, keep the tail (errors usually at the end)
        if len(output) > MAX_OUTPUT:
            output = f"[...truncated {len(output) - MAX_OUTPUT} chars...]\n" + output[-MAX_OUTPUT:]

        if result.returncode != 0:
            return f"exit code {result.returncode}\n{output}"

        return output or "(no output)"

    except subprocess.TimeoutExpired:
        return "error: command timed out after 60 seconds"
    except Exception as e:
        return f"error: {e}"

@tool
def ask_human(
        question: str,
        trigger: Literal["low_similarity", "small_margin", "out_of_range", "other"],
        source_context: str,
        agent_proposal: str,
) -> str:
    """Ask the human to decide when you are unsure. Use it when a value is outside
    the min/max of its ICASA variable, or (to be added later) when the best mapping has a low
    similarity or a small margin over the runner-up.

    question: what you need decided, in one or two sentences.
    trigger: why you are asking.
    source_context: file, column and value that caused the question.
    agent_proposal: your candidate answers with scores or limits, and your preferred one.
    """
    return "ask_human is handled by the ask node, not executed here."