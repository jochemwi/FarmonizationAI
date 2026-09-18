from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langfuse.langchain import CallbackHandler

from src.harness_phase_1 import agent

load_dotenv()

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content="Did this message arrive? Confirm with message: All set!")]
result = agent.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")