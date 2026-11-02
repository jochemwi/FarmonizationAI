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

from src.tools.tools import bash

# load API keys from .env
load_dotenv()

# the model the agent uses
configurable_model = init_chat_model("openai:gpt-5.6-luna", temperature=0) # temperature = 0 for most stable output

# all tools the agent can call
tools = [bash]
# lookup table, so tool_node can find a tool by the name the model gives
tools_by_name = {t.name: t for t in tools}
# tell the model which tools exist
model_with_tools = configurable_model.bind_tools(tools)


# state (the data that is passed between the nodes of the graph)
class MessagesState(TypedDict):
    # the whole conversation. New messages are added to the list, not replaced
    messages: Annotated[list[AnyMessage], operator.add]
    # how many times the model has been called
    llm_calls: int
    # result of the validation_node
    validation: dict


# Node 1 (continue, or finished?)
def llm_call(state: MessagesState):
    system = SystemMessage(content="You are a helpful data harmanization agent. Working directory is /app. Source files: /app/src/, data: /app/data/, write intermediates to /app/workspace/, final output to /app/output/. Use absolute paths.")
    
    # for the first call, add list of all files, so the model sees the folder layout
    messages = state["messages"]
    if state.get("llm_calls", 0) == 0:
        messages = [HumanMessage(content="Run: find /app -maxdepth 3 | sort")] + messages

    # call the model and count this call for llm_calls
    return {
        "messages": [model_with_tools.invoke([system] + messages)],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }

# Node 2 (run the tool the model asks for)
def tool_node(state: MessagesState):
    result = []
    # the last message contains a list of the models tool calls to be executed (if any)
    for tool_call in state["messages"][-1].tool_calls:
        # find the tool by name and run it with the arguments from the model
        t = tools_by_name[tool_call["name"]]
        observation = t.invoke(tool_call["args"])
        # send the output to the model, linked to the tool call (by its id)
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}

# location agent writes final output and the validation nodes checks it
SUBMISSION_DIR = "/app/output/submission"
FILL_API = "/app/data/target/v8/fill_api.py"

# Node 3 (check final output with fill_api.py) -> #TODO: remove from future version since we will not use a synthetic data set, possibly replace with de set of 50.
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

# decide check weather model has tool calls left, if not run the validation node and end run
def should_continue(state: MessagesState) -> Literal["tool_node", "validate_node"]:
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return "validate_node"

# create the graph with the state defined above
agent_builder = StateGraph(MessagesState)
# add nodes with the names used in the edges
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
# start with the model
agent_builder.add_edge(START, "llm_call")
# after the tools have run, return back to the model
agent_builder.add_edge("tool_node", "llm_call")
agent_builder.add_node("validate_node", validate_node)
# after the model: should_continue decideds wether to: run a tool or validate_node
agent_builder.add_conditional_edges("llm_call", should_continue)
# the check is the last step
agent_builder.add_edge("validate_node", END)
# turn the graph into something you can run with agent.invoke() for main
agent = agent_builder.compile()