from src.constants import PLAYBOOK, EMBEDDINGS, VALIDATE_CMD

def build_prompt(run_id: str) -> str:

    icasa_search = ""
    if EMBEDDINGS:
        icasa_search = """ICASA variable search:
To find which target variable a source column belongs to, you can search the ICASA variable catalog semantically with a short description in words (what the column holds, its unit, the crop). Each hit lists the variable name, target table, unit, data type and range. Hits are candidates only: always check them against /app/data/target/harmonization_template/scheme/variables.csv and the template README before you use one.
  python -m src.memory.semantic_search icasa "<short description>" -n 5

"""

    memory = ""
    search_rule = ""
    log_start = "Log"
    if PLAYBOOK:
        search_rule = "Before logging, search memory for an earlier rule that already covers the case, and apply it if it does. In that case do not log a question. "
        log_start = "Otherwise log"
        if EMBEDDINGS:
            memory_access = "playbook.py and semantic_search"
            memory_search = """- Before you start processing the data, search the playbook in two ways. Semantic search takes a short description in words (what the column holds, its unit, the crop, the problem) and returns the closest entries:
  python -m src.memory.semantic_search playbook "<short description>" -n 5
  A lower distance means a closer match. Treat hits as leads and check that they apply to your data.
  Keyword search is for exact terms such as column names, filenames and codes. Search one keyword at a time:
  python /app/src/memory/playbook.py search "<keyword>"
"""
        else:
            memory_access = "playbook.py"
            memory_search = """- Before you start processing the data, search the playbook by keyword. Use exact terms such as column names, filenames and codes. Search one keyword at a time:
  python /app/src/memory/playbook.py search "<keyword>"
"""
        memory = f"""Memory:
Lessons and corrections from earlier runs are stored in the playbook. Use {memory_access} for all memory access, and never edit the JSON files in /app/src/memory/data directly.
{memory_search}- After you have verified your output, propose a playbook entry only if one of your checks caught a problem and you fixed it. Your proposal goes to a review queue and is not added to the playbook during this run. If nothing went wrong, skip it. Write one proposal per distinct problem, each with a single lesson, so every entry covers one issue. If you fixed several unrelated problems, run the propose command once per problem. Use title for a short name of the problem, when-to-use for the situation in which the entry applies, guidance for what to do, and background for what happened and which check revealed it. Choose keywords that name the specific problem (the variable, table or error type), not broad words like validation, weather or soil:
  python /app/src/memory/playbook.py propose --run-id {run_id} --title "..." --when-to-use "..." --guidance "..." --background "..." --outcome success --keywords kw1 kw2 kw3

"""

    return f"""Your task is described in /app/input/README.md. Read it first and follow it. Also read /app/data/target/harmonization_template/README.md fully.


Before finishing, verify your output and fix any problems you find. Validate only with the official validator, and do not write your own validation script:
    {VALIDATE_CMD}
Run it after your last change to the output, and fix every error it reports before you finish.
Never delete or skip source rows just to make the validator pass. Fix the cause in your build logic instead. The validator accepts empty tables, so it does not show whether your output is complete. Before finishing, compare the row count of each output table with what the source data contains, and investigate every table that is empty or far smaller than expected. Do not finish while any table with matching source data is empty.

Work through this checklist. Do not finish until every step is done.
1. Before building anything, list every file under /app/input (all workbooks, soil files, weather files and any other file type) and open each file type to see what it contains. Write down which output tables each source file feeds. Do not leave a source file type unread.
2. Build the tables from the real source data. Do not generate placeholder rows or IDs to satisfy the validator.
3. Every ID and link column must be filled from the source (for example plot, treatment, genotype, weather station, soil profile and field IDs). A blank link column is an error even if the validator does not report it. If the source states an identifier explicitly (for example a weather station ID in a metadata sheet), keep it as given. Do not replace it with an ID inferred from file names, years or naming patterns. If you believe it is wrong, keep it as given and record a question with log_question instead of overriding it.
4. Plots, Plot_seasons and Treatments must have one row per distinct plot, plot-season and treatment in the source. Check the counts against the source before moving on.
5. Before finishing, print a table with, for every one of the 35 output tables: the row count and the source file it comes from. Fix every table that has source data but no rows or far fewer rows than the source. Before you report any table as empty or write "no source records", scan the cell comments of every workbook (openpyxl: cell.comment.text on all sheets, including hidden rows). Comments can hold dated management, chemical, tillage, mulch and observation records. For each empty table, list the workbook, cell and comment text you checked in /app/workspace/empty_table_review.md. A table may stay empty only if both the sheet scan and the comment scan find nothing for its variables. Before finishing, list every column or code in every source file (including weather files) that you did not map to a target variable, with the reason. If the target scheme has a variable with a matching code, definition or unit, map it. Never drop a source column silently.
6. Run the official validator after your last change. If it reports any error, keep working. Do not stop with an invalid or incomplete package.
7. Never call bash with an empty command. Put your reasoning in your reply, not in a tool call.
8. Before every tool call, write one or two sentences in your reply saying what you are about to do and why. After a result that changes your plan, say in one sentence what you learned. Do not leave your reply empty when you call a tool. Before you report any table as empty, check the Excel cell comments as well as the cell values.

{icasa_search}{memory}Open questions:
You have a tool log_question. No human answers during the run, so never wait for an answer. Use it instead of guessing silently when a numeric value from the input falls outside the MinVal/MaxVal of its ICASA variable (/app/data/target/harmonization_template/scheme/icasa_variable.csv). {search_rule}{log_start} one question per issue, not one per value. If several values in the same column are out of range in the same way (for example, they all look like cm instead of m), log one question about the whole column and apply your assumption to every matching value. Put the file, column, rows and value in context, and put the allowed range, what you will do instead and why in assumed_answer. Then continue immediately with that assumption. Do not log the same question twice. Do not log questions about values inside their range.

"""