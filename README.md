# Prosper Voice Agent

A user can edit the node graph and place a test call from the UI, similar to existing products like ElevenLabs Agents or Retell AI.
A Pipecat voice pipeline (WebRTC + ElevenLabs STT/TTS + OpenAI LLM) whose conversation is a node graph built with Pipecat Flows.
An agent is defined declaratively as JSON and compiled into a runnable flow at runtime by an AgentBuilder, and can be exercised through a browser test call.

## Quickstart

### Docker (recommended)

Requires **Docker** and API keys.

```bash
cp backend/.env.example backend/.env   # fill in OPENAI_API_KEY and ELEVENLABS_API_KEY
make docker                            # build and start all services
```

Then open `http://localhost:3000`, click **Connect**, allow mic access, and talk to the agent.

### Local development

Requires **Python 3.11+**, **Node.js 18+**, and **Docker** (for Postgres + Redis).

```bash
cp backend/.env.example backend/.env   # fill in OPENAI_API_KEY and ELEVENLABS_API_KEY
make install                           # create venv, install Python + frontend deps
make db-reset                          # start Docker services, apply schema, seed data
make run-all                           # start everything: backend, API, and frontend dev server
```

Then open `http://localhost:3000`.

## Make commands

| Command | Description |
|---|---|
| `make install` | Create `backend/.venv`, install Python deps, install frontend npm deps |
| `make docker` | Build and start all services via Docker Compose (`http://localhost:3000`) |
| `make docker-down` | Stop and remove all Docker services |
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
| `backend/bot.py` | The voice pipeline (WebRTC + ElevenLabs STT/TTS + OpenAI LLM). Loads an agent JSON via `AgentBuilder` and runs it. |
| `backend/api.py` | REST API for the builder UI — saves/loads the agent JSON and serves the agent graph. |
| `backend/agent_builder/` | `schema.py` = the declarative `AgentConfig` / `Node` / `Edge` contract; `builder.py` = `AgentBuilder`, which compiles JSON into a Pipecat Flows graph, injects per-node model overrides, and prepends session state on each transition. |
| `backend/tools/` | All LLM-callable tools: `scheduling/` (classify, capture preference, book slot), `filters/` (init search, filter by location/provider/time/date, get next options, clear filter), `lookup/` (provider, location, appointment type). |
| `backend/db/` | Postgres pool, Redis client, schema migrations, and seeding from `catalog.json` / `calendar.json`. |
| `backend/data/current_agent.json` | The active agent definition — edited by the builder UI and loaded at bot startup. |
| `backend/data/catalog.json` | A deliberately large clinic catalog (locations, providers, appointment types, booking rules). See [`backend/data/README.md`](backend/data/README.md). |
| `frontend/` | React builder UI — node graph editor and WebRTC test call. |
| `frontend/nginx.conf` | nginx reverse proxy config for the Docker setup — routes `/start`, `/api/offer`, `/sessions` to the bot and `/api` to the REST API. |
| `docker-compose.yml` | Full service stack: postgres, redis, seed (one-shot), bot, api, frontend. |

To run a different agent, point `AGENT_FLOW` in `bot.py` at another JSON file.