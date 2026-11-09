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
configurable_model = init_chat_model("openai:gpt-6-luna", reasoning_effort="high", temperature=0)

# Tools
tools = [bash, ask_human] #append when more tools get made
tools_by_name = {t.name: t for t in tools}
model_with_tools = configurable_model.bind_tools(tools)


# State
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    validation: dict


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
FILL_API = "/app/data/target/v8/fill_api.py"


def validate_node(state: MessagesState):
    directory = Path(SUBMISSION_DIR)
    present = len(list(directory.glob("*.csv"))) if directory.is_dir() else 0
    proc = subprocess.run(
        [sys.executable, FILL_API, "--validate-package", SUBMISSION_DIR, "--complete"],
        capture_output=True, text=True,
    )
    stderr_lines = proc.stderr.strip().splitlines()
    return {"validation": {
        "status": "valid" if proc.returncode == 0 else "invalid",
        "exit_code": proc.returncode,
        "tables_present": f"{present}/35",
        "stdout": proc.stdout.strip(),
        "error": stderr_lines[-1] if stderr_lines else "",
        "message": proc.stderr[-2000:],
    }}

def should_continue(state: MessagesState) -> Literal["tool_node", "ask_node", "validate_node"]:
    tool_calls = state["messages"][-1].tool_calls
    if any(tc["name"] == "ask_human" for tc in tool_calls):
        return "ask_node"
    if tool_calls:
        return "tool_node"
    return "validate_node"

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
agent_builder.add_edge("validate_node", END)
agent = agent_builder.compile(checkpointer=InMemorySaver())