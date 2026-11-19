import csv
import os
import operator
from typing import Literal
from typing_extensions import TypedDict, Annotated

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END

from src.tools.tools import bash, log_question
from src.constants import FILL_API, SUBMISSION_DIR, VALIDATE_ARGS, VALIDATE_CMD, MAX_VAL_ROUNDS, EMPTY_TABLE_REVIEW_ROUNDS, MODEL_NAME, REASONING

# load API keys from .env
load_dotenv()

# Setup
model = init_chat_model(MODEL_NAME, reasoning=REASONING, use_responses_api=True, temperature=0)
# Tools
tools = [bash, log_question] 
tools_by_name = {t.name: t for t in tools}
model_with_tools = model.bind_tools(tools)

# State
class HarnessState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    validation: dict
    validation_rounds: int

# Nodes
def llm_call(state: HarnessState):
    system = SystemMessage(content="You are a helpful data assistant. Working directory is /app. Source data: /app/input/, target schema and validator: /app/data/, write intermediates to /app/workspace/, final output to /app/output/. Use absolute paths.")

    # inject tree discovery as first turn if not already done
    messages = state["messages"]
    if state.get("llm_calls", 0) == 0:
        messages = [HumanMessage(content="Run: find /app -maxdepth 3 | sort")] + messages
    
    return {
        "messages": [model_with_tools.invoke([system] + messages)],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def tool_node(state: HarnessState):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        try:
            t = tools_by_name[tool_call["name"]]
            observation = t.invoke(tool_call["args"])
        except Exception as e:
            observation = f"Tool call failed: {e}. Fix the arguments and call the tool again."
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


TEMPLATE_DIR = Path(FILL_API).parent / "template"

def empty_tables() -> list[str]:
    # tables (csv files) in the submission that have a header but no data rows
    directory = Path(SUBMISSION_DIR)
    empty = []
    if directory.is_dir():
        for f in sorted(directory.glob("*.csv")):
            with open(f, newline="", encoding="utf-8-sig", errors="replace") as fh:
                rows = sum(1 for _ in csv.reader(fh))
            if rows <= 1:
                empty.append(f.stem)
    return empty


def validate_node(state: HarnessState):
    directory = Path(SUBMISSION_DIR)
    present = len(list(directory.glob("*.csv"))) if directory.is_dir() else 0
    proc = subprocess.run(
        [sys.executable, FILL_API, *VALIDATE_ARGS],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(Path(FILL_API).parents[1])},
    )
    stderr_lines = proc.stderr.strip().splitlines()
    v = {
        "status": "valid" if proc.returncode == 0 else "invalid",
        "exit_code": proc.returncode,
        "tables_present": f"{present}/{len(list(TEMPLATE_DIR.glob('*.csv')))}",
        "stdout": proc.stdout.strip(),
        "error": stderr_lines[-1] if stderr_lines else "",
        "message": proc.stderr[-2000:],
        "empty_tables": empty_tables(),
    }
    rounds = state.get("validation_rounds", 0) + 1
    # valid package; empty tables get up to EMPTY_TABLE_REVIEW_ROUNDS review nudges, after that they count as reviewed
    done = v["status"] == "valid" and (not v["empty_tables"] or rounds > EMPTY_TABLE_REVIEW_ROUNDS)
    v["done"] = done
    if done and v["empty_tables"]:
        v["outcome"] = "done_empty_tables_reviewed"
    elif done:
        v["outcome"] = "done"
    elif rounds > MAX_VAL_ROUNDS:
        v["outcome"] = "cap_reached"
    else:
        v["outcome"] = "nudged"
    update = {"validation": v, "validation_rounds": rounds}
    if v["outcome"] == "nudged":
        update["messages"] = [HumanMessage(content=f"""You stopped, but the package is not confirmed complete yet. The official validator result is: {v['status']}.

Validator output:
{v['message']}

Tables with a header but no data rows: {v['empty_tables']}

- For every empty table, check the source data in /app/input for matching data, including the cell comments of every workbook, not only the cell values. If there is matching source data, build the table from it. If there is none, leave it empty and list the table, the workbook, the cell and the comment text you checked in /app/workspace/empty_table_review.md.
- Fix reference errors (an ID used in one table but not defined in another) by building the table that defines the ID from the source data. Never fix them by deleting rows or inventing placeholder rows.
- If the validator rejects parent records that no plot-season context uses, fix it by building the missing plot-season context from the source data. Never fix it by deleting the parent records.
- Never delete or skip source rows just to make the validator pass.
- After your last change, run the official validator and fix every error before you finish:
  {VALIDATE_CMD}
- Never call bash with an empty command.""")]
    return update

def should_continue(state: HarnessState) -> Literal["tool_node", "validate_node"]:
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        return "tool_node"
    return "validate_node"


def after_validate(state: HarnessState) -> Literal["llm_call", "__end__"]:
    if state["validation"]["outcome"] == "nudged":
        return "llm_call"
    return END

# Build graph
agent_builder = StateGraph(HarnessState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_edge("tool_node", "llm_call")
agent_builder.add_node("validate_node", validate_node)
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", "validate_node"])
agent_builder.add_conditional_edges("validate_node", after_validate, ["llm_call", END])
agent = agent_builder.compile()
