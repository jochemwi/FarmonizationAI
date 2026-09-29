from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langfuse.langchain import CallbackHandler

from src.harness_phase_1 import agent

load_dotenv()

langfuse_handler = CallbackHandler()

messages = [HumanMessage(content="""
You are given a messy agricultural field trial dataset at /app/data/synthetic_messy.xlsx.

Your task:
1. Read all tabs in the file and understand the structure.
2. Harmonize the data to ICASA standard format using the schema at /app/src/rag/icasa_schema.json.
3. Reconstruct the EXNAME field by combining Experiment_Crop_code_Year columns.
4. Standardize all dates to YYYY-MM-DD format.
5. Convert all yield values to kg/ha (check the HWAH_unit column).
6. Map non-standard column names back to ICASA field names.
7. Output the result as /app/output/harmonized.xlsx with one tab per ICASA table:
   FIELDS, TRTMENTS, FERTILIZERS, IRRIGATION, SOIL_INITIAL, SUMMARY, BIOMASS_OBS.
8. Before finishing, verify the full output, not just the first rows. For every tab:
   - print the row count and the unique values per column
   - print the number of missing values per column
   - check that dates are all YYYY-MM-DD and numeric values are in plausible ranges
   Fix any problems you find and re-run the checks.
""")]
result = agent.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})

for m in result["messages"]:
    print(f"[{m.type}]: {m.content}")
