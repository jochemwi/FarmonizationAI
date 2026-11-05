def build_prompt(run_id: str) -> str:
    return f"""Your task is described in /app/input/README.md. Read it first and follow it.

Before finishing, verify your output yourself and fix any problems you find.

Memory:
Lessons and corrections from earlier runs are stored in memory. Use memory.py for all memory access, and never edit the JSON files in /app/src/memory/data directly.
- Before you start processing the data, search memory for keywords from the data (column names, units, crops, treatments):
  python /app/src/memory/memory.py search "<keyword>"
  Search one keyword at a time.
- After you have verified your output, record a reflection only if one of your checks caught a problem and you fixed it. Describe the problem, the check that revealed it, and the fix. If nothing went wrong, skip it:
  python /app/src/memory/memory.py add --run-id {run_id} --title "..." --situation "..." --what-happened "..." --lesson "..." --outcome success --keywords kw1 kw2 kw3

Human-in-the-loop:
You have a tool ask_human. Use it instead of guessing when a numeric value from the input falls outside the MinVal/MaxVal of its ICASA variable (/app/data/target/v8/scheme/icasa_variable.csv). Before asking, search memory for an earlier human answer that already covers the case, and reuse it if it does. When you ask, set trigger="out_of_range", put the file, column and value in source_context, and put the allowed range and your preferred option in agent_proposal. Ask one focused question at a time. Wait for the answer, then apply it. Do not ask about values inside their range.
After you receive the answer, record it with:
  python /app/src/memory/memory.py add-hitl --kind <column_mapping|unit|value_recode|other> --title "..." --when-to-use "<general rule for when this applies>" --keywords kw1 kw2 kw3 --correction "<what to do, derived from the answer>" --rationale "<why, derived from the answer>" --limits "<when it does not apply>" --user-answer "<the human's answer, verbatim>" --priority <must|should> --trigger <same trigger you asked with> --source-context "<same as in ask_human>" --agent-proposal "<same as in ask_human>"
Write correction, rationale and limits only from what the human said, and do not add reasoning of your own. Use the human's exact words for --user-answer.
"""
## TODO: add refelction based on traces later