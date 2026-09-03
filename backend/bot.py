#
# Voice pipeline — Prosper AI Software Engineer Challenge
#
# The runnable voice agent: WebRTC transport + ElevenLabs STT/TTS + OpenAI LLM,
# driven by a Pipecat Flows node graph. This file is generic — it loads an agent
# definition (JSON) via AgentBuilder and runs it. Swapping the agent is a data
# change (edit/replace the JSON), not a code change.
#
#   example_flow.json  ->  AgentBuilder  ->  Pipecat Flows graph  ->  FlowManager
#
# Run:  python bot.py   then open http://localhost:7860/client
#

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner
from pipecat_flows import FlowManager

from agent_builder import AgentBuilder
from db import close_pool, init_pool
from db.redis import close_redis, get_redis, init_redis

# Load .env next to this file, so the bot runs the same from the repo root or backend/.
load_dotenv(Path(__file__).parent / ".env")


def _agent_flow() -> Path:
    """Use the saved agent if present, fall back to the bundled example."""
    current = Path(__file__).parent / "data" / "current_agent.json"
    return current if current.exists() else Path(__file__).parent / "example_flow.json"


transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(
    transport: BaseTransport, runner_args: RunnerArguments, builder: AgentBuilder
) -> None:
    config = builder.config
    logger.info(f"Starting '{config.name}' with {len(config.nodes)} nodes")

    stt = ElevenLabsRealtimeSTTService(api_key=os.environ["ELEVENLABS_API_KEY"])
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        settings=ElevenLabsTTSService.Settings(voice=config.voice_id),
    )
    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], model=config.model)

    context = LLMContext()
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    flow_manager = FlowManager(
        llm=llm,
        context_aggregator=context_aggregator,
        worker=worker,
        transport=transport,
    )

    # Allow individual nodes to specify a per-node model override via
    # {"type": "set_model", "model": "..."} in their pre_actions list.
    async def _set_model(action: dict, flow_manager: FlowManager) -> None:
        model = action.get("model")
        if model:
            llm._settings.model = model
            logger.info(f"LLM model → {model}")

    flow_manager.register_action("set_model", _set_model)

    # Compress slot-search JSON payloads in context when the caller has already
    # selected a slot. Replaces large options arrays with a one-line summary,
    # keeping context lean for the confirm_booking and goodbye nodes.
    async def _compress_slot_results(action: dict, flow_manager: FlowManager) -> None:
        for msg in context.messages:
            if msg.get("role") != "developer":
                continue
            try:
                outer = json.loads(msg["content"])
                if outer.get("type") != "async_tool" or outer.get("status") != "finished":
                    continue
                result = json.loads(outer.get("result", "{}"))
                if "options" not in result:
                    continue
                n = len(result["options"])
                outer["result"] = json.dumps({
                    "status": result["status"],
                    "note": f"[{n} slot options shown — slot selected, context trimmed]",
                })
                msg["content"] = json.dumps(outer)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        logger.info("Compressed slot search results in context")

    flow_manager.register_action("compress_slot_results", _compress_slot_results)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        session_id = str(uuid.uuid4())
        flow_manager.state["session_id"] = session_id
        logger.info(f"Client connected — session {session_id}")
        await flow_manager.initialize(builder.build_initial_node())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        session_id = flow_manager.state.get("session_id")
        if session_id:
            redis = get_redis()
            keys = await redis.keys(f"session:{session_id}:*")
            if keys:
                await redis.delete(*keys)
                logger.info(f"Cleaned up {len(keys)} Redis keys for session {session_id}")
        logger.info("Client disconnected")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Entry point invoked by the Pipecat dev runner (and Pipecat Cloud)."""
    await init_pool()
    await init_redis()
    try:
        transport = await create_transport(runner_args, transport_params)
        builder = AgentBuilder.from_json(_agent_flow())
        await run_bot(transport, runner_args, builder)
    finally:
        await close_pool()
        await close_redis()


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
