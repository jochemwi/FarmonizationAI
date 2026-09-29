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

### Every time

**Run the agent**
```bash
make run
```

**Run tests**
```bash
make test
```

**Fast tests**
```bash
make test-fast
```

**Stop the container**
```bash
docker compose down
```

## Project structure

```
FarmonizationAI/
├── .devcontainer/          # Dev container config
├── .github/                # GitHub Actions / CI
├── .vscode/                # Editor settings
├── data/                   # Input field trial CSVs (read-only in container)
├── literature/             # Papers and reference material
├── notebooks/              # Exploratory Jupyter notebooks
├── output/                 # Agent output (repairs, logs)
├── src/
│   ├── agent/              # LangGraph ReAct agent loop
│   ├── downstream/         # Post-processing / export
│   ├── eval/               # Evaluation pipeline (4-level)
│   ├── memory/             # Memory / checkpointing
│   ├── rag/                # OG-RAG vector store + retriever
│   ├── tools/              # Tool definitions (bash, file I/O, etc.)
│   ├── harness_phase_1.py  # Phase 1 harness entry point
│   ├── main.py             # Main entry point (called by Makefile)
│   └── __init__.py
├── tests/                  # Pytest test suite
├── .env                    # API keys (not committed)
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── Makefile                # `make run`, `make test`, `make test-fast`
├── README.md
└── requirements.txt
```

