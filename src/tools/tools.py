import pandas as pd
import os
import subprocess

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