"""Unit tests for MCP → OpenAI tool schema conversion."""


from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_school_agentic_app.tool_schema import _mcp_tool_to_openai, _namespace, build_tool_registry


def _make_tool(name: str, description: str = "A tool", schema: dict | None = None):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = schema or {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
    }
    return tool


class TestNamespace:
    def test_format(self):
        assert _namespace("weather", "get_current") == "weather__get_current"

    def test_news_format(self):
        assert _namespace("news", "fetch_headlines") == "news__fetch_headlines"


class TestMcpToolToOpenAI:
    def test_basic_conversion(self):
        tool = _make_tool("get_weather")
        result = _mcp_tool_to_openai("weather__get_weather", tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "weather__get_weather"
        assert result["function"]["description"] == "A tool"
        assert "parameters" in result["function"]

    def test_parameters_are_object_type(self):
        tool = _make_tool("get_weather")
        result = _mcp_tool_to_openai("weather__get_weather", tool)
        assert result["function"]["parameters"]["type"] == "object"

    def test_no_schema_wrapped_as_object(self):
        tool = _make_tool("simple_tool", schema={})
        result = _mcp_tool_to_openai("weather__simple_tool", tool)
        assert result["function"]["parameters"]["type"] == "object"

    def test_schema_dollar_schema_removed(self):
        tool = _make_tool(
            "typed_tool",
            schema={"$schema": "http://json-schema.org/draft-07/schema", "type": "object", "properties": {}},
        )
        result = _mcp_tool_to_openai("news__typed_tool", tool)
        assert "$schema" not in result["function"]["parameters"]

    def test_non_object_schema_wrapped(self):
        tool = _make_tool("raw_tool", schema={"location": {"type": "string"}})
        result = _mcp_tool_to_openai("weather__raw_tool", tool)
        assert result["function"]["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_build_tool_registry():
    server = AsyncMock()
    server.name = "weather"
    server.list_tools = AsyncMock(
        return_value=[
            _make_tool("get_current_weather"),
            _make_tool("get_forecast"),
        ]
    )

    openai_tools, registry = await build_tool_registry([server])

    assert len(openai_tools) == 2
    assert "weather__get_current_weather" in registry
    assert "weather__get_forecast" in registry
    assert registry["weather__get_current_weather"][0] is server
    assert registry["weather__get_current_weather"][1] == "get_current_weather"


@pytest.mark.asyncio
async def test_build_tool_registry_multiple_servers():
    weather_server = AsyncMock()
    weather_server.name = "weather"
    weather_server.list_tools = AsyncMock(return_value=[_make_tool("get_weather")])

    news_server = AsyncMock()
    news_server.name = "news"
    news_server.list_tools = AsyncMock(return_value=[_make_tool("get_headlines")])

    openai_tools, registry = await build_tool_registry([weather_server, news_server])

    assert len(openai_tools) == 2
    assert "weather__get_weather" in registry
    assert "news__get_headlines" in registry
    # No collisions
    assert registry["weather__get_weather"][0] is weather_server
    assert registry["news__get_headlines"][0] is news_server
