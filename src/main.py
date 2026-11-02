from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from langfuse import Langfuse, get_client

from src.harness_phase_1 import agent
from src.prompt import build_prompt
from src.config import CONFIG_NAME, MODEL_NAME, PROMPT_VERSION


# Langfuse client, reads keys from .env
langfuse = get_client()
# create trace id (run_id)
run_id = Langfuse.create_trace_id()
print(f"run_id: {run_id}")

# Callback handler that sends all steps agent does to Langfuse
langfuse_handler = CallbackHandler()

# initial prompt with run ID as first message to the agent
messages = [HumanMessage(content=build_prompt(run_id))]

# wrap the run under run_id
with langfuse.start_as_current_observation(
    as_type="span",
    name="FarmonizationAI-run",
    trace_context={"trace_id": run_id},
):
    # run the agent loop
    result = agent.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})

# print the conversation: prompt, model replies and tool results
for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")

# print validation result that validate_node added to the state
print("validation:", result["validation"])