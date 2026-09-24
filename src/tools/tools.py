import pandas as pd
import os

from langchain.tools import tool

@tool
def get_column_names(filepath: str) -> str:
    """Gets the column names of a CSV file. If the file is not found, suggests similar files.

    Args:
        filepath: location of the csv
    """
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        return str(list(df.columns))
    
    # Search for similar files
    filename = os.path.basename(filepath)
    similar = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".csv") and filename.lower() in f.lower() or f.lower() in filename.lower():
                similar.append(os.path.join(root, f))
    
    if similar:
        return f"File '{filepath}' not found. Did you mean: {', '.join(similar)}?"
    return f"File '{filepath}' not found and no similar files found."

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