import json
import shutil
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent))
from agent_builder import AgentBuilder
from tools.registry import REGISTRY

EXAMPLE_FLOW = Path(__file__).parent / "example_flow.json"
CURRENT_AGENT = Path(__file__).parent / "data" / "current_agent.json"


def _load() -> dict[str, Any]:
    if CURRENT_AGENT.exists():
        return json.loads(CURRENT_AGENT.read_text())
    return json.loads(EXAMPLE_FLOW.read_text())


app = FastAPI(title="Prosper Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/agent")
async def get_agent() -> dict[str, Any]:
    return _load()


@app.get("/api/tools")
async def get_tools() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": schema.description}
        for name, schema in REGISTRY.items()
    ]


@app.post("/api/agent")
async def save_agent(request: Request) -> dict[str, Any]:
    payload = await request.json()
    try:
        AgentBuilder.from_dict(payload)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    CURRENT_AGENT.write_text(json.dumps(payload, indent=2))
    return {"ok": True}


if __name__ == "__main__":
    # Seed current_agent.json from example if missing
    if not CURRENT_AGENT.exists():
        shutil.copy(EXAMPLE_FLOW, CURRENT_AGENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
