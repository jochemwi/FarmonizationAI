from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langfuse.langchain import CallbackHandler

from src.harness_phase_1 import agent

load_dotenv()

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content="Run `ls data/` and tell me what files are there.")]
result = agent.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")