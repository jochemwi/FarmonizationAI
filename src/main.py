from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langfuse.langchain import CallbackHandler

from src.harness_phase_1 import agent

load_dotenv()

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content="make a file called test.py in the " \
"output folder. write a script where test.csv is loaded and the average age is printed" \
"tell me your reasoning per step" \
"and add comments next to each step")]
result = agent.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")