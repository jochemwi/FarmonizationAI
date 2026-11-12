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
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from src.tools.tools import bash, ask_human

# load API keys from .env
load_dotenv()

# Setup
langfuse_handler = CallbackHandler() #initiate langfuse for logging
configurable_model = init_chat_model("openai:gpt-6.1-sol", reasoning={"effort": "high", "summary": "detailed"}, use_responses_api=True, temperature=0)

# Tools
tools = [bash, ask_human] #append when more tools get made
tools_by_name = {t.name: t for t in tools}
model_with_tools = configurable_model.bind_tools(tools)

# Validator rounds: how many times the agent may be sent back to work after validation fails
MAX_VAL_ROUNDS = 3

# State
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    validation: dict
    validation_rounds: int

# Nodes
def llm_call(state: MessagesState):
    system = SystemMessage(content="You are a helpful data assistant. Working directory is /app. Source files: /app/src/, data: /app/data/, write intermediates to /app/workspace/, final output to /app/output/. Use absolute paths.")
    
    # inject tree discovery as first turn if not already done
    messages = state["messages"]
    if state.get("llm_calls", 0) == 0:
        messages = [HumanMessage(content="Run: find /app -maxdepth 3 | sort")] + messages
    
    return {
        "messages": [model_with_tools.invoke([system] + messages)],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def tool_node(state: MessagesState):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        try:
            t = tools_by_name[tool_call["name"]]
            observation = t.invoke(tool_call["args"])
        except Exception as e:
            observation = f"Tool call failed: {e}. Fix the arguments and call the tool again."
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}

def ask_node(state: MessagesState):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        if tool_call["name"] == "ask_human":
            answer = interrupt(tool_call["args"])
            result.append(ToolMessage(
                content=f"Human answer: {answer}",
                tool_call_id=tool_call["id"],
            ))
        else:
            result.append(ToolMessage(
                content="Not executed because ask_human was called in the same turn. Call this tool again after the human's answer.",
                tool_call_id=tool_call["id"],
            ))
    return {"messages": result}

SUBMISSION_DIR = "/app/output/submission"
FILL_API = "/app/data/target/harmonization_template/fill_api.py"


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


def validate_node(state: MessagesState):
    directory = Path(SUBMISSION_DIR)
    present = len(list(directory.glob("*.csv"))) if directory.is_dir() else 0
    proc = subprocess.run(
        [sys.executable, FILL_API, "--validate-package", SUBMISSION_DIR, "--complete", "--final"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(Path(FILL_API).parents[1])},
    )
    stderr_lines = proc.stderr.strip().splitlines()
    v = {
        "status": "valid" if proc.returncode == 0 else "invalid",
        "exit_code": proc.returncode,
        "tables_present": f"{present}/35",
        "stdout": proc.stdout.strip(),
        "error": stderr_lines[-1] if stderr_lines else "",
        "message": proc.stderr[-2000:],
        "empty_tables": empty_tables(),
    }
    rounds = state.get("validation_rounds", 0) + 1
    # valid package; empty tables get one review nudge (rounds == 1), after that they count as reviewed
    done = v["status"] == "valid" and (not v["empty_tables"] or rounds > 1)
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
    if not done and rounds <= MAX_VAL_ROUNDS:
        update["messages"] = [HumanMessage(content=f"""You stopped, but the package is not confirmed complete yet. The official validator result is: {v['status']}.

Validator output:
{v['message']}

Tables with a header but no data rows: {v['empty_tables']}

- For every empty table, check the source data in /app/input for matching data, including the cell comments of every workbook, not only the cell values. If there is matching source data, build the table from it. If there is none, leave it empty and list the table, the workbook, the cell and the comment text you checked in /app/workspace/empty_table_review.md.
- Fix reference errors (an ID used in one table but not defined in another) by building the table that defines the ID from the source data. Never fix them by deleting rows or inventing placeholder rows.
- If the validator rejects parent records that no plot-season context uses, fix it by building the missing plot-season context from the source data. Never fix it by deleting the parent records.
- Never delete or skip source rows just to make the validator pass.
- After your last change, run the official validator and fix every error before you finish:
  PYTHONPATH=/app/data/target python /app/data/target/harmonization_template/fill_api.py --validate-package /app/output/submission --complete --final
- Never call bash with an empty command.""")]
    return update

def should_continue(state: MessagesState) -> Literal["tool_node", "ask_node", "validate_node"]:
    tool_calls = state["messages"][-1].tool_calls
    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return "ask_node"
    if tool_calls:
        return "tool_node"
    return "validate_node"


def after_validate(state: MessagesState) -> Literal["llm_call", "__end__"]:
    v = state["validation"]
    if v["done"]:
        return END
    if state["validation_rounds"] > MAX_VAL_ROUNDS:
        return END
    return "llm_call"

# Build graph
agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_edge("tool_node", "llm_call")
agent_builder.add_node("validate_node", validate_node)
agent_builder.add_node("ask_node", ask_node)
agent_builder.add_edge("ask_node", "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", "ask_node", "validate_node"])
agent_builder.add_conditional_edges("validate_node", after_validate, ["llm_call", END])
agent = agent_builder.compile(checkpointer=InMemorySaver())