# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install   # create backend/.venv and install dependencies
make run       # start the voice agent at http://localhost:7860/client
make clean     # remove venv and __pycache__ dirs
make help      # list all targets
```

Environment: copy `backend/.env.example` to `backend/.env` and fill in `OPENAI_API_KEY` and `ELEVENLABS_API_KEY`.

There are no automated tests. To exercise the agent, run `make run`, open the printed URL, click **Connect**, and talk.

## Architecture

The project is a voice scheduling agent built on [Pipecat](https://github.com/pipecat-ai/pipecat). The key design principle is **agent as data**: the conversation graph is a JSON file, not Python code. Swapping agents means pointing `AGENT_FLOW` in `bot.py` at a different JSON file.

### Data flow

```
example_flow.json  →  AgentBuilder  →  Pipecat Flows NodeConfig graph  →  FlowManager (runtime)
```

1. **`backend/bot.py`** — wires the Pipecat pipeline: WebRTC transport → ElevenLabs STT → OpenAI LLM → ElevenLabs TTS → WebRTC output. It is generic; it never touches graph logic directly. On client connect it calls `flow_manager.initialize(builder.build_initial_node())`.

2. **`backend/agent_builder/schema.py`** — three dataclasses that define the declarative contract:
   - `AgentConfig`: top-level (name, persona, voice_id, model, initial_node, list of nodes)
   - `Node`: a conversational state — mirrors Pipecat Flows' `NodeConfig` fields (`role_message`, `task_messages`, `pre/post_actions`) plus an `edges` list and an `end` flag
   - `Edge`: a transition exposed to the LLM as a tool call (function name, description, target node, JSON-schema properties to collect)

3. **`backend/agent_builder/builder.py`** — `AgentBuilder` loads + validates a JSON/dict and compiles it into Pipecat Flows objects. Key method: `build_initial_node()` returns the entry `NodeConfig`; downstream nodes are built lazily on each transition. Each edge becomes a `FlowsFunctionSchema` whose handler stores collected args into `flow_manager.state` and returns the next `NodeConfig`.

4. **`backend/example_flow.json`** — the reference agent (a clinic appointment scheduler): 4 nodes (greeting → collect_details → offer_times → confirm), using hardcoded time slots. This is the starting point for Phase 2 work.

5. **`backend/data/catalog.json`** — a synthetic clinic catalog (~8 locations, ~50 providers, ~82 appointment types) for Phase 2 context-management work. It is intentionally large and messy. See `backend/data/README.md` for the full schema and the booking rules a correct agent must honor (location/provider/capability gating, referral requirements, new-patient restrictions, duplicate names).

### Agent JSON schema

```jsonc
{
  "name": "...",
  "persona": "...",          // global role_message for all nodes
  "voice_id": "...",         // ElevenLabs voice ID
  "model": "gpt-4o",
  "initial_node": "greeting",
  "nodes": [{
    "name": "greeting",
    "task_messages": [{"role": "developer", "content": "..."}],
    "role_message": "...",   // optional node-level override of persona
    "edges": [{
      "function": "choose_intent",   // tool name the LLM calls
      "description": "...",
      "target": "collect_details",   // next node name
      "properties": { ... },         // JSON-schema props to collect
      "required": [...]
    }],
    "pre_actions": [...],
    "post_actions": [...],
    "end": false             // true → adds end_conversation post_action
  }]
}
```

## Phase 2 context

The challenge work (not yet started) involves building a context-management layer so the agent can navigate `catalog.json` reliably without injecting the full catalog into every prompt. The existing `example_flow.json` uses hardcoded time slots — Phase 2 replaces those with real catalog lookups.