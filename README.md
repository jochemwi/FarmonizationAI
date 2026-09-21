# harmonizationAI

## Proposed folder structure
```text
harmonizationAI/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
│
├── data/
│   ├── ontology/
│   │   └── icasa_variables.json
│   ├── chroma/
│   └── test.csv
│
├── output/
│
├── Notebooks/
│   └── playground.ipynb
│
├── pre_testing/
│   └── LangGraph.py
│
└── src/
    ├── main.py
    │
    ├── agent/
    │   ├── state.py
    │   ├── provider.py
    │   ├── react_loop.py
    │   ├── agent_loop.py
    │   ├── hitl.py
    │   ├── tui.py
    │   └── reflexion.py
    │
    ├── rag/
    │   ├── vector_store.py
    │   ├── og_rag.py
    │   └── custom_messages.py
    │
    ├── tools/
    │   ├── __init__.py
    │   ├── tools.py
    │   ├── bash_tool.py
    │   ├── code_write.py
    │   └── og_rag_tool.py
    │
    ├── eval/
    │   ├── sanity_check.py
    │   ├── og_eval.py
    │   ├── llm_eval.py
    │   └── human_eval.py
    │
    ├── memory/
    │   ├── storage.py
    │   ├── session_state.py
    │   └── compaction.py
    │
    └── downstream/
        └── nq_prediction.py
```
