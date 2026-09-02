# Prosper Voice Agent

A user can edit the node graph and place a test call from the UI, similar to existing products like ElevenLabs Agents or Retell AI.
A Pipecat voice pipeline (WebRTC + ElevenLabs STT/TTS + OpenAI LLM) whose conversation is a node graph built with Pipecat Flows. 
An agent is defined declaratively as JSON and compiled into a runnable flow at runtime by an AgentBuilder, and can be exercised through a browser test call. 

## Quickstart

Requires **Python 3.11+**. Run from the repo root:

```bash
make install
make run
```

Open the URL it prints (default `http://localhost:7860/client`), click **Connect**, allow mic access, and talk to the agent. `Ctrl+C` to stop. (`make help` lists all targets.)\
\
Remember to update the `.env` file accordingly.

## Layout

| Path | Responsibility |
| --- | --- |
| `backend/bot.py` | The voice pipeline (WebRTC + ElevenLabs STT/TTS + OpenAI LLM). Loads an agent JSON via `AgentBuilder` and runs it. No graph logic lives here. |
| `backend/agent_builder/` | All agent-building code. `schema.py` = the declarative `AgentConfig` / `Node` / `Edge` contract; `builder.py` = `AgentBuilder`, which loads + validates the JSON and compiles it into a Pipecat Flows graph. |
| `backend/example_flow.json` | The example agent **as data** — a clinic scheduler. The starting point for the Phase 2 context-management work. |
| `backend/data/catalog.json` | A deliberately large, deliberately messy clinic catalog (locations, providers, appointment types, booking rules) for the Phase 2 work. See [`backend/data/README.md`](backend/data/README.md). |

To run a different agent, point `AGENT_FLOW` in `bot.py` at another JSON file.