from src.config import COMPONENTS

PROMPT_VERSION = "v1"


def build_prompt(run_id: str) -> str:
    if COMPONENTS["storage"]:
        memory = f"""
Memory:
Lessons and corrections from earlier runs are stored in memory. Use memory.py for all memory access, and never edit the JSON files in /app/src/memory/data directly.
- Before you start processing the data, search memory for keywords from the data (column names, units, crops, treatments):
  python /app/src/memory/memory.py search "<keyword>"
  Search one keyword at a time.
- After you have verified your output, record a reflection only if one of your checks caught a problem and you fixed it. Describe the problem, the check that revealed it, and the fix. If nothing went wrong, skip it:
  python /app/src/memory/memory.py add --run-id {run_id} --title "..." --situation "..." --what-happened "..." --lesson "..." --outcome success --keywords kw1 kw2 kw3
"""
    else:
        memory = ""

    return f"""Your task is described in /app/input/README.md. Read it first and follow it.

Before finishing, verify your output yourself and fix any problems you find.
{memory}"""

# TODO: add reflection based on traces later