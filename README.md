# Prosper Voice Agent

A user can edit the node graph and place a test call from the UI, similar to existing products like ElevenLabs Agents or Retell AI.
A Pipecat voice pipeline (WebRTC + ElevenLabs STT/TTS + OpenAI LLM) whose conversation is a node graph built with Pipecat Flows. 
An agent is defined declaratively as JSON and compiled into a runnable flow at runtime by an AgentBuilder, and can be exercised through a browser test call. 

## Quickstart

Requires **Python 3.11+**, **Node.js 18+**, and **Docker** (for Postgres + Redis).

```bash
cp backend/.env.example backend/.env   # fill in OPENAI_API_KEY and ELEVENLABS_API_KEY
make install                           # create venv, install Python + frontend deps
make db-reset                          # start Docker services, apply schema, seed data
make run-all                           # start everything: backend, API, and frontend dev server
```

Then open `http://localhost:3000`, click **Connect**, allow mic access, and talk to the agent.

## Make commands

| Command | Description |
|---|---|
| `make install` | Create `backend/.venv`, install Python deps, install frontend npm deps |
| `make run-all` | Start DB + Redis (Docker), voice backend, REST API, and frontend dev server |
| `make run` | Voice agent backend only (`http://localhost:7860/client`) |
| `make run-api` | REST API only (`http://localhost:8000`) — required for the Save/Connect flow |
| `make dev` | Frontend dev server only (`http://localhost:3000`) |
| `make test` | Run the backend test suite |
| `make db-up` | Start PostgreSQL + Redis via Docker Compose |
| `make db-down` | Stop Docker Compose services |
| `make db-seed` | Seed the DB from `catalog.json` and `calendar.json` |
| `make db-reset` | Full reset: tear down volumes, rebuild schema, re-seed |
| `make clean` | Remove venv, `__pycache__`, and frontend build artefacts |
| `make help` | Print all available targets |

## Layout

| Path | Responsibility |
| --- | --- |
| `backend/bot.py` | The voice pipeline (WebRTC + ElevenLabs STT/TTS + OpenAI LLM). Loads an agent JSON via `AgentBuilder` and runs it. No graph logic lives here. |
| `backend/agent_builder/` | All agent-building code. `schema.py` = the declarative `AgentConfig` / `Node` / `Edge` contract; `builder.py` = `AgentBuilder`, which loads + validates the JSON and compiles it into a Pipecat Flows graph. |
| `backend/example_flow.json` | The example agent **as data** — a clinic scheduler. The starting point for the Phase 2 context-management work. |
| `backend/data/catalog.json` | A deliberately large, deliberately messy clinic catalog (locations, providers, appointment types, booking rules) for the Phase 2 work. See [`backend/data/README.md`](backend/data/README.md). |

To run a different agent, point `AGENT_FLOW` in `bot.py` at another JSON file.