from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler

from src.harness_phase_1 import agent
from src.prompt import build_prompt
from src.config import CONFIG_NAME, MODEL_NAME, PROMPT_VERSION

load_dotenv()

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content=build_prompt())]

result = agent.invoke(
    {"messages": messages},
    config={
        "callbacks": [langfuse_handler],
        "metadata": {"langfuse_tags": [f"config:{CONFIG_NAME}", f"model:{MODEL_NAME}", f"prompt:{PROMPT_VERSION}"]},
    },
)

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")
