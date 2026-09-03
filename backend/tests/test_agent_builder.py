from unittest.mock import MagicMock

import pytest

from agent_builder.builder import AgentBuilder

_MINIMAL = {
    "name": "Test Agent",
    "persona": "You are a test agent.",
    "voice_id": "voice123",
    "model": "gpt-4o",
    "initial_node": "start",
    "nodes": [
        {
            "name": "start",
            "task_messages": [{"role": "developer", "content": "Say hello."}],
            "edges": [
                {
                    "function": "go_next",
                    "description": "Proceed to end.",
                    "target": "end",
                    "properties": {"caller_name": {"type": "string"}},
                    "required": ["caller_name"],
                }
            ],
        },
        {
            "name": "end",
            "task_messages": [{"role": "developer", "content": "Say goodbye."}],
            "edges": [],
            "end": True,
        },
    ],
}


def test_loads_valid_config():
    builder = AgentBuilder.from_dict(_MINIMAL)
    assert builder.config.name == "Test Agent"
    assert len(builder.config.nodes) == 2


def test_raises_on_unknown_initial_node():
    bad = {**_MINIMAL, "initial_node": "nonexistent"}
    with pytest.raises(ValueError, match="initial_node"):
        AgentBuilder.from_dict(bad)


def test_raises_on_bad_edge_target():
    nodes = [
        {
            "name": "start",
            "task_messages": [{"role": "developer", "content": "Hi."}],
            "edges": [
                {
                    "function": "go",
                    "description": "Go.",
                    "target": "nowhere",
                    "properties": {},
                    "required": [],
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="nowhere"):
        AgentBuilder.from_dict({**_MINIMAL, "nodes": nodes})


def test_build_initial_node_structure():
    builder = AgentBuilder.from_dict(_MINIMAL)
    node = builder.build_initial_node()
    assert node["name"] == "start"
    assert "functions" in node
    assert "task_messages" in node
    assert node["task_messages"][0]["content"] == "Say hello."


def test_end_node_gets_end_conversation_action():
    builder = AgentBuilder.from_dict(_MINIMAL)
    end_node = builder._make_node(builder._nodes_by_name["end"])
    post_actions = end_node.get("post_actions", [])
    assert any(a.get("type") == "end_conversation" for a in post_actions)


def test_non_end_node_has_no_end_conversation():
    builder = AgentBuilder.from_dict(_MINIMAL)
    start_node = builder.build_initial_node()
    post_actions = start_node.get("post_actions", [])
    assert not any(a.get("type") == "end_conversation" for a in post_actions)


async def test_edge_handler_stores_args_and_returns_next_node():
    builder = AgentBuilder.from_dict(_MINIMAL)
    edge = builder._nodes_by_name["start"].edges[0]
    schema = builder._make_edge_function(edge)

    fm = MagicMock()
    fm.state = {}
    result, next_node = await schema.handler({"caller_name": "Alice"}, fm)

    assert fm.state["caller_name"] == "Alice"
    assert result["status"] == "success"
    assert result["caller_name"] == "Alice"
    assert next_node["name"] == "end"


async def test_edge_handler_unknown_args_stored_in_state():
    builder = AgentBuilder.from_dict(_MINIMAL)
    edge = builder._nodes_by_name["start"].edges[0]
    schema = builder._make_edge_function(edge)

    fm = MagicMock()
    fm.state = {"existing_key": "preserved"}
    await schema.handler({"caller_name": "Bob"}, fm)

    assert fm.state["existing_key"] == "preserved"
    assert fm.state["caller_name"] == "Bob"