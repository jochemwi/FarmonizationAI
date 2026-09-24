import operator
from typing import Literal
from typing_extensions import TypedDict, Annotated

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langfuse.langchain import CallbackHandler

from src.tools.tools import *

# load API keys from .env
load_dotenv()

# Setup
langfuse_handler = CallbackHandler() #initiate langfuse for logging
configurable_model = init_chat_model("openai:gpt-5.6-luna", temperature=0)
# configurable_model = init_chat_model("anthropic:claude-haiku-4-5-20251001", temperature=0) # default (cheapest) model, changable with the config

# Tools
tools = [bash] #append when more tools get made
tools_by_name = {t.name: t for t in tools}
model_with_tools = configurable_model.bind_tools(tools)


# State
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


# Nodes
def llm_call(state: MessagesState):
    return {
        "messages": [
            model_with_tools.invoke(
                [SystemMessage(content="You are a helpful data assistant.")] # change text based on role (expend when we use multiple agents)
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def tool_node(state: MessagesState):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        t = tools_by_name[tool_call["name"]]
        observation = t.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END


# Build graph
agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")
agent = agent_builder.compile()