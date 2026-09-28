# harmonizationAI

Agentic AI framework for harmonising heterogeneous agricultural field trial datasets to the ICASA standard.


## First time setup (ONLY)

**1. Clone the repo**
```bash
git clone https://github.com/jochemwi/FarmonizationAI
cd harmonizationAI
```

**2. Create `.env` file**
```bash
cp .env.example .env
```
**2.1 Fill in  API keys**
```
OPENAI_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

**3. Create the output folder**
```bash
mkdir output
```

**4. Build the Docker image**
```bash
docker compose up -d --build
```

Only need to re-run `--build` again if `requirements.txt` or `Dockerfile` changes. Otherwise:

## Every time

**Start the container**
```bash
docker compose up -d
```

**Run the agent**
```bash
docker compose exec harness python -m src.main
```

**Stop the container**
```bash
docker compose down
```

---

## Project structure

```
harmonizationAI/
├── data/               # raw input data — read only inside Docker
├── output/             # generated scripts and cleaned output
├── src/
│   ├── main.py         # entry point
│   ├── harness_phase_1.py  # LangGraph agent graph
│   ├── tools/
│   │   └── tools.py    # bash, get_column_names, ...
│   └── rag/
│       └── vector_store.py  # Chroma stub
├── tests/              # pytest tests
├── Dockerfile
└── docker-compose.yml
```

---

## Running tests

```bash
pytest tests/
```

Slow tests (e.g. timeout test) are marked `@pytest.mark.slow` and can be skipped:

```bash
pytest tests/ -m "not slow"
```

## Proposed folder structure
```text
harmonizationAI/
├── .github/
│   └── workflows/
│       └── tests.yml
├── .devcontainer/
│   └── devcontainer.json
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
├── .gitignore
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
├── tests/
│   ├── __init__.py
│   └── test_agent.py
│
└── src/
    ├── __init__.py
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
