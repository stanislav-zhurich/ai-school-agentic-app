"""Tests for agent loop tool-routing logic (mocked LLM + MCP servers)."""


import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_school_agentic_app.agent import _resolve, _tool_result_text, _truncate


# --- Unit tests for helpers ---

class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", limit=100) == "hello"

    def test_long_string_truncated(self):
        long = "x" * 200
        result = _truncate(long, limit=100)
        assert len(result) < 210
        assert "truncated" in result

    def test_exact_limit_unchanged(self):
        s = "a" * 50
        assert _truncate(s, limit=50) == s


class TestToolResultText:
    def test_list_of_text_items(self):
        items = [MagicMock(text="line1"), MagicMock(text="line2")]
        assert _tool_result_text(items) == "line1\nline2"

    def test_single_text_item(self):
        item = MagicMock(text="result")
        assert _tool_result_text(item) == "result"

    def test_list_of_dicts(self):
        items = [{"text": "hello"}, {"text": "world"}]
        assert _tool_result_text(items) == "hello\nworld"

    def test_string_fallback(self):
        assert _tool_result_text("raw string") == "raw string"


class TestResolve:
    def test_found(self):
        server = MagicMock()
        registry = {"weather__get_current": (server, "get_current")}
        s, name = _resolve("weather__get_current", registry)
        assert s is server
        assert name == "get_current"

    def test_not_found_raises(self):
        with pytest.raises(KeyError, match="weather__missing"):
            _resolve("weather__missing", {})


# --- Integration-style test with fully mocked LLM + servers ---

def _make_tool_call(id_: str, name: str, args: dict):
    tc = MagicMock()
    tc.id = id_
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def _make_choice(tool_calls=None, content=None):
    msg = MagicMock()
    msg.tool_calls = tool_calls
    msg.content = content
    msg.model_dump = MagicMock(return_value={"role": "assistant", "content": content})
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_agent_calls_weather_tool():
    """Agent routes a weather question to the weather server."""
    weather_server = AsyncMock()
    weather_server.name = "weather"

    tool_mock = MagicMock()
    tool_mock.name = "get_current_weather"
    tool_mock.description = "Get current weather"
    tool_mock.inputSchema = {"type": "object", "properties": {"location": {"type": "string"}}}
    weather_server.list_tools = AsyncMock(return_value=[tool_mock])

    call_result = MagicMock()
    call_result.isError = False
    call_result.content = [MagicMock(text='{"temperature": 22, "city": "Berlin"}')]
    weather_server.call_tool = AsyncMock(return_value=call_result)

    tool_call = _make_tool_call("tc1", "weather__get_current_weather", {"location": "Berlin"})
    first_resp = _make_choice(tool_calls=[tool_call])
    final_resp = _make_choice(content="Berlin is 22°C right now.")

    with patch("ai_school_agentic_app.agent.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(side_effect=[first_resp, final_resp])

        with patch("ai_school_agentic_app.agent.get_openai_api_key", return_value="test-key"):
            from ai_school_agentic_app.agent import run_agent
            result = await run_agent("What is the weather in Berlin?", [weather_server])

    assert result.answer == "Berlin is 22°C right now."
    assert len(result.trace) == 1
    assert result.trace[0].server == "weather"
    assert result.trace[0].tool == "get_current_weather"
    assert result.trace[0].ok is True


@pytest.mark.asyncio
async def test_agent_no_tool_call_returns_directly():
    """Agent returns LLM answer directly when no tool calls are made."""
    server = AsyncMock()
    server.name = "weather"
    server.list_tools = AsyncMock(return_value=[])

    direct_resp = _make_choice(content="I don't know the weather.")

    with patch("ai_school_agentic_app.agent.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=direct_resp)

        with patch("ai_school_agentic_app.agent.get_openai_api_key", return_value="test-key"):
            from ai_school_agentic_app.agent import run_agent
            result = await run_agent("Some question", [server])

    assert result.answer == "I don't know the weather."
    assert result.trace == []
