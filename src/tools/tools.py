import subprocess

from langchain_core.tools import tool

# max number of characters returned to the model, this way the context does not get filled quickly
MAX_OUTPUT = 4000
# seconds a command may run before its stopped
TIMEOUT = 60

@tool
def bash(command: str, description: str) -> str:
    """
    Run a shell command. Always provide a description of what the command does.
    Returns combined stdout and stderr. Output is truncated if too long.
    """

    try:
        # run the command in a shell and wait for it to finish
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            timeout=TIMEOUT,
        )

        output = result.stdout

        # truncate from the front, keep the tail (errors usually at the end)
        if len(output) > MAX_OUTPUT:
            output = f"[...truncated {len(output) - MAX_OUTPUT} chars...]\n" + output[-MAX_OUTPUT:]

        # non-zero exit code means the command failed. Give the exit code and show the output
        if result.returncode != 0:
            return f"exit code {result.returncode}\n{output}"

        # return the output, or a note if there was none (empty reply is confusing for LLMs)
        return output or "(no output)"

    except subprocess.TimeoutExpired:
        return f"error: command timed out after {TIMEOUT} seconds"
    # return the error as text instead of crashing the agent
    except Exception as e:
        return f"error: {e}"