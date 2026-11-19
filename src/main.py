import os
import json
from datetime import datetime, timezone
from pathlib import Path

from langchain.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from langfuse import Langfuse, get_client


from src.harness import agent
from src.prompt import build_prompt
from src.constants import PLAYBOOK, EMBEDDINGS


langfuse = get_client()
run_id = Langfuse.create_trace_id()
os.environ["RUN_ID"] = run_id
print(f"run_id: {run_id}")

Path("/app/output/run_info.json").write_text(json.dumps({
    "run_id": run_id,
    "config": os.getenv("CONFIG", "unknown"),
    "playbook": PLAYBOOK,
    "embeddings": EMBEDDINGS,
    "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}, indent=2))

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content=build_prompt(run_id))]

with langfuse.start_as_current_observation(
    as_type="span",
    name="harmonization-run",
    trace_context={"trace_id": run_id},
):
    result = agent.invoke(
        {"messages": messages},
        config={"callbacks": [langfuse_handler]},
    )

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")

print("validation:", result["validation"])