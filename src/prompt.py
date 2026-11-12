def build_prompt(run_id: str) -> str:
    return f"""Your task is described in /app/input/README.md. Read it first and follow it. Also read /app/data/target/harmonization_template/README.md fully.


Before finishing, verify your output and fix any problems you find. Validate only with the official validator, and do not write your own validation script:
    PYTHONPATH=/app/data/target python /app/data/target/harmonization_template/fill_api.py --validate-package /app/output/submission --complete --final
Run it after your last change to the output, and fix every error it reports before you finish.
Never delete or skip source rows just to make the validator pass. Fix the cause in your build logic instead. The validator accepts empty tables, so it does not show whether your output is complete. Before finishing, compare the row count of each output table with what the source data contains, and investigate every table that is empty or far smaller than expected. Do not finish while any table with matching source data is empty.

Work through this checklist. Do not finish until every step is done.
1. Before building anything, list every file under /app/input (all workbooks, soil files, weather files and any other file type) and open each file type to see what it contains. Write down which output tables each source file feeds. Do not leave a source file type unread.
2. Build the tables from the real source data. Do not generate placeholder rows or IDs to satisfy the validator.
3. Every ID and link column must be filled from the source (for example plot, treatment, genotype, weather station, soil profile and field IDs). A blank link column is an error even if the validator does not report it.
4. Plots, Plot_seasons and Treatments must have one row per distinct plot, plot-season and treatment in the source. Check the counts against the source before moving on.
5. Before finishing, print a table with, for every one of the 35 output tables: the row count and the source file it comes from. Fix every table that has source data but no rows or far fewer rows than the source. Before you report any table as empty or write "no source records", scan the cell comments of every workbook (openpyxl: cell.comment.text on all sheets, including hidden rows). Comments can hold dated management, chemical, tillage, mulch and observation records. For each empty table, list the workbook, cell and comment text you checked in /app/workspace/empty_table_review.md. A table may stay empty only if both the sheet scan and the comment scan find nothing for its variables.6. Run the official validator after your last change. If it reports any error, keep working. Do not stop with an invalid or incomplete package.
7. Never call bash with an empty command. Put your reasoning in your reply, not in a tool call.
8. Before every tool call, write one or two sentences in your reply saying what you are about to do and why. After a result that changes your plan, say in one sentence what you learned. Do not leave your reply empty when you call a tool. Before you report any table as empty, check the Excel cell comments as well as the cell values.

Memory:
Lessons and corrections from earlier runs are stored in memory. Use memory.py for all memory access, and never edit the JSON files in /app/src/memory/data directly.
- Before you start processing the data, search memory for keywords from the data (column names, units, crops, treatments):
  python /app/src/memory/memory.py search "<keyword>"
  Search one keyword at a time.
- After you have verified your output, record a reflection only if one of your checks caught a problem and you fixed it. Describe the problem, the check that revealed it, and the fix. If nothing went wrong, skip it. Write one reflection per distinct problem, each with a single lesson, so every entry covers one issue. If you fixed several unrelated problems, run the add command once per problem. Choose keywords that name the specific problem (the variable, table or error type), not broad words like validation, weather or soil:
  python /app/src/memory/memory.py add --run-id {run_id} --title "..." --situation "..." --what-happened "..." --lesson "..." --outcome success --keywords kw1 kw2 kw3

Human-in-the-loop:
You have a tool ask_human. Use it instead of guessing when a numeric value from the input falls outside the MinVal/MaxVal of its ICASA variable (/app/data/target/harmonization_template/scheme/icasa_variable.csv). Before asking, search memory for an earlier human answer that already covers the case, and reuse it if it does. When you ask, set trigger="out_of_range", put the file, column and value in source_context, and put the allowed range and your preferred option in agent_proposal. Ask one focused question at a time. If several values in the same column are out of range in the same way (for example, they all look like cm instead of m), ask once about the whole column, list the affected rows in source_context, and apply the answer to every matching value. Do not ask again per value. Wait for the answer, then apply it. Do not ask about values inside their range.
After you receive the answer, record it with:
  python /app/src/memory/memory.py add-hitl --kind <column_mapping|unit|value_recode|other> --title '...' --when-to-use '<general rule for when this applies>' --keywords kw1 kw2 kw3 --correction '<what to do, derived from the answer>' --rationale '<why, derived from the answer>' --limits '<when it does not apply>' --user-answer '<the answer from the human, verbatim>' --priority <must|should> --trigger <same trigger you asked with> --source-context '<same as in ask_human>' --agent-proposal '<same as in ask_human>'
Wrap every add-hitl argument in single quotes. Do not use backticks inside them, and write any apostrophe inside an argument as a typographic apostrophe (’).
Write correction, rationale and limits only from what the human said, and do not add reasoning of your own. Use the human's exact words for --user-answer.

"""
## TODO: add refelction based on traces later