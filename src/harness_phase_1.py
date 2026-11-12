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
from langchain.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
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

# Finisher (fresh agent, bash only: no ask_human, because interrupt() inside a node would re-run the node on resume)
finisher_model = configurable_model.bind_tools([bash])
MAX_FINISHER_ROUNDS = 2
MAX_FINISHER_STEPS = 40


# State
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    validation: dict
    finisher_rounds: int


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
        [sys.executable, FILL_API, "--validate-package", SUBMISSION_DIR, "--complete"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(Path(FILL_API).parents[1])},
    )
    stderr_lines = proc.stderr.strip().splitlines()
    return {"validation": {
        "status": "valid" if proc.returncode == 0 else "invalid",
        "exit_code": proc.returncode,
        "tables_present": f"{present}/35",
        "stdout": proc.stdout.strip(),
        "error": stderr_lines[-1] if stderr_lines else "",
        "message": proc.stderr[-2000:],
        "empty_tables": empty_tables(),
    }}


def finisher_node(state: MessagesState, config: RunnableConfig):
    # fresh agent: own short context, continues from the existing build.py and output
    rounds = state.get("finisher_rounds", 0) + 1
    v = state["validation"]
    system = SystemMessage(content="You are a helpful data assistant. Working directory is /app. Source files: /app/src/, data: /app/data/, write intermediates to /app/workspace/, final output to /app/output/. Use absolute paths.")
    task = HumanMessage(content=f"""An earlier agent worked on the task described in /app/input/README.md but did not finish. Finish it.

Its work is in /app/workspace (for example build.py) and /app/output/submission. Reuse and extend it. Do not rebuild what already works.

Current official validator result: {v.get('status')}
Last validator output:
{v.get('message')}
Tables with a header but no data rows: {v.get('empty_tables')}

Do the following:
1. Run the official validator yourself to see the full list of errors:
      PYTHONPATH=/app/data/target python /app/data/target/harmonization_template/fill_api.py --validate-package /app/output/submission --complete --final
2. For every empty table, check the source data in /app/input (all workbooks, soil files and weather files) for matching data. If there is matching source data, build the table from it. If there is none, leave it empty.
3. Reference errors (an ID used in one table but not defined in another) are fixed by building the table that defines the ID from the source data. Never fix them by deleting rows or inventing placeholder rows.
4. Never delete or skip source rows just to make the validator pass.
5. Run the official validator after your last change and fix every error before you finish. Do not write your own validation script.
6. Never call bash with an empty command.
When done, reply with a short summary of what you fixed and what is still wrong.""")
    messages = [task]
    final_text = ""
    steps = 0
    stop_reason = "step cap reached"
    for _ in range(MAX_FINISHER_STEPS):
        response = finisher_model.invoke([system] + messages, config=config)
        steps += 1
        messages.append(response)
        final_text = response.content if isinstance(response.content, str) else "".join(b.get("text", "") for b in response.content if isinstance(b, dict))
        if not response.tool_calls:
            stop_reason = "model finished" if final_text.strip() else "model returned an empty reply"
            break
        for tool_call in response.tool_calls:
            try:
                observation = bash.invoke(tool_call["args"])
            except Exception as e:
                observation = f"Tool call failed: {e}. Fix the arguments and call the tool again."
            messages.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {
        "messages": [AIMessage(content=f"[finisher round {rounds}] steps={steps}/{MAX_FINISHER_STEPS}, stop={stop_reason}. {final_text}")],
        "finisher_rounds": rounds,
    }


def should_continue(state: MessagesState) -> Literal["tool_node", "ask_node", "validate_node"]:
    tool_calls = state["messages"][-1].tool_calls
    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return "ask_node"
    if tool_calls:
        return "tool_node"
    return "validate_node"


def after_validate(state: MessagesState) -> Literal["finisher_node", "__end__"]:
    if state.get("finisher_rounds", 0) >= MAX_FINISHER_ROUNDS:
        return END
    v = state["validation"]
    if v["status"] == "valid" and not v["empty_tables"]:
        return END
    return "finisher_node"

# Build graph
agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_edge("tool_node", "llm_call")
agent_builder.add_node("validate_node", validate_node)
agent_builder.add_node("ask_node", ask_node)
agent_builder.add_node("finisher_node", finisher_node)
agent_builder.add_edge("ask_node", "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", "ask_node", "validate_node"])
agent_builder.add_conditional_edges("validate_node", after_validate, ["finisher_node", END])
agent_builder.add_edge("finisher_node", "validate_node")
agent = agent_builder.compile(checkpointer=InMemorySaver())