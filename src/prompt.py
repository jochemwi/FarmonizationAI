def build_prompt(run_id: str) -> str:
    return f"""Your task is described in /app/input/README.md. Read it first and follow it.

Before finishing, verify your output and fix any problems you find. Validate only with the official validator, and do not write your own validation script:
  python /app/data/target/v8/fill_api.py --validate-package /app/output/submission --complete
Run it after your last change to the output, and fix every error it reports before you finish.
Never delete or skip source rows just to make the validator pass. Fix the cause in your build logic instead. The validator accepts empty tables, so it does not show whether your output is complete. Before finishing, compare the row count of each output table with what the source data contains, and investigate every table that is empty or far smaller than expected. Do not finish while any table with matching source data is empty.
Memory:
Lessons and corrections from earlier runs are stored in memory. Use memory.py for all memory access, and never edit the JSON files in /app/src/memory/data directly.
- Before you start processing the data, search memory for keywords from the data (column names, units, crops, treatments):
  python /app/src/memory/memory.py search "<keyword>"
  Search one keyword at a time.
- After you have verified your output, record a reflection only if one of your checks caught a problem and you fixed it. Describe the problem, the check that revealed it, and the fix. If nothing went wrong, skip it. Write one reflection per distinct problem, each with a single lesson, so every entry covers one issue. If you fixed several unrelated problems, run the add command once per problem. Choose keywords that name the specific problem (the variable, table or error type), not broad words like validation, weather or soil:
  python /app/src/memory/memory.py add --run-id {run_id} --title "..." --situation "..." --what-happened "..." --lesson "..." --outcome success --keywords kw1 kw2 kw3

Human-in-the-loop:
You have a tool ask_human. Use it instead of guessing when a numeric value from the input falls outside the MinVal/MaxVal of its ICASA variable (/app/data/target/v8/scheme/icasa_variable.csv). Before asking, search memory for an earlier human answer that already covers the case, and reuse it if it does. When you ask, set trigger="out_of_range", put the file, column and value in source_context, and put the allowed range and your preferred option in agent_proposal. Ask one focused question at a time. If several values in the same column are out of range in the same way (for example, they all look like cm instead of m), ask once about the whole column, list the affected rows in source_context, and apply the answer to every matching value. Do not ask again per value. Wait for the answer, then apply it. Do not ask about values inside their range.
After you receive the answer, record it with:
  python /app/src/memory/memory.py add-hitl --kind <column_mapping|unit|value_recode|other> --title '...' --when-to-use '<general rule for when this applies>' --keywords kw1 kw2 kw3 --correction '<what to do, derived from the answer>' --rationale '<why, derived from the answer>' --limits '<when it does not apply>' --user-answer '<the answer from the human, verbatim>' --priority <must|should> --trigger <same trigger you asked with> --source-context '<same as in ask_human>' --agent-proposal '<same as in ask_human>'
Wrap every add-hitl argument in single quotes. Do not use backticks inside them, and write any apostrophe inside an argument as a typographic apostrophe (’).
Write correction, rationale and limits only from what the human said, and do not add reasoning of your own. Use the human's exact words for --user-answer.

"""
## TODO: add refelction based on traces later