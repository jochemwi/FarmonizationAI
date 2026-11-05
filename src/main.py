from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from langfuse import Langfuse, get_client
from langgraph.types import Command


from src.harness_phase_1 import agent
from src.prompt import build_prompt


load_dotenv()

langfuse = get_client()
run_id = Langfuse.create_trace_id()
print(f"run_id: {run_id}")

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content=build_prompt(run_id))]

with langfuse.start_as_current_observation(
    as_type="span",
    name="harmonization-run",
    trace_context={"trace_id": run_id},
):
    result = agent.invoke(
        {"messages": messages},
        config={
            "callbacks": [langfuse_handler],
            "configurable": {"thread_id": run_id},
        },
    )

    while result.get("__interrupt__"):
        ask = result["__interrupt__"][0].value  # the args the agent passed to ask_human
        print("\n--- AGENT NEEDS YOUR INPUT ---")
        print(f"Question: {ask.get('question')}")
        print(f"Trigger: {ask.get('trigger')}")
        print(f"Context: {ask.get('source_context')}")
        print(f"Agent proposal: {ask.get('agent_proposal')}")
        answer = input("Your answer: ")
        result = agent.invoke(
            Command(resume=answer),
            config={
                "callbacks": [langfuse_handler],
                "configurable": {"thread_id": run_id},
            },
        )

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")

print("validation:", result["validation"])