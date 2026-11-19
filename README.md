# harmonizationAI

Agentic AI framework for harmonising heterogeneous agricultural field trial datasets to the ICASA standard.

## First time setup

**1. Clone the repo**
```bash
git clone https://github.com/jochemwi/FarmonizationAI
cd harmonizationAI
```

**2. Create a `.env` file** in the repo root (there is no template) with:
```
OPENAI_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

**3. Run it.** `make run` builds the images, builds the memory snapshot, runs the agent and archives the result.

## Configs

A config is a file in `configs/` that switches memory features on or off. Select one with `CONFIG=<name>` (default: `icasa`).

| Config | Playbook | Embeddings |
|---|---|---|
| `icasa` | off | off |
| `icasa_playbook` | on | off |
| `icasa_embedding` | off | on |
| `icasa_playbook_embedding` | on | on |

## Commands

```bash
make run CONFIG=icasa_playbook_embedding   # snapshot, agent run, archive
make snapshot CONFIG=...                   # only build the memory snapshot
make archive CONFIG=...                    # copy the last output to runs/
make obs                                   # latest Langfuse trace -> observability/viewer.html
make test                                  # tests in a one-off container
make test-fast                             # same, skipping slow tests
make clean                                 # empty output/ and workspace/
docker compose down                        # stop the containers
```

`make obs` accepts `LABEL=`, `TRACE=<trace id>` and `NOOPEN=1`.

## How it works

- `src/harness.py`: the LangGraph graph. The agent works with bash and `log_question`; after it stops, the official validator runs and sends it back to work if the package is incomplete.
- `src/prompt.py`: builds the task prompt for the chosen config.
- `src/memory/`: the playbook (`playbook.py`, a CLI), embeddings and the Chroma index (`vector_store.py`) and semantic search (`semantic_search.py`).
- The agent never writes to the playbook. It proposes entries to `output/playbook_proposals.json`, and you promote them with `python src/memory/playbook.py add`. Questions it would have asked go to `output/questions.json`.
- The agent's only network exit is the proxy in `proxy/`, which has a host allowlist.

## Project structure

```
harmonizationAI/
├── configs/            # Ablation configs (PLAYBOOK / EMBEDDINGS on or off)
├── data/target/        # Target schema package and validator (read-only in container)
├── input/              # The task README and the source data
├── proxy/              # Proxy with host allowlist
├── src/
│   ├── constants.py    # Paths, validator command, experiment settings
│   ├── harness.py      # LangGraph graph
│   ├── main.py         # Entry point (run by make run)
│   ├── prompt.py       # Task prompt
│   ├── build_snapshot.py  # Memory snapshot for one config
│   ├── memory/         # Playbook, embeddings, semantic search
│   └── tools/          # Agent tools
├── tests/
├── VibeCoded/          # AI-generated Langfuse trace analysis (make obs)
├── Makefile
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

Not in git: `output/`, `workspace/`, `runs/`, `memory_snapshots/`, `observability/`, `literature/`.