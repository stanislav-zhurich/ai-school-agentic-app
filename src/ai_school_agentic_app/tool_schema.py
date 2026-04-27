"""Convert MCP tool definitions to OpenAI function-calling schemas with namespacing."""


from typing import Any

from mcp.types import Tool

from .mcp_client import MCPServer

# Maps namespaced_tool_name -> (MCPServer, original_tool_name)
ToolRegistry = dict[str, tuple[MCPServer, str]]


def _namespace(server_name: str, tool_name: str) -> str:
    return f"{server_name}__{tool_name}"


def _mcp_tool_to_openai(namespaced_name: str, tool: Tool) -> dict[str, Any]:
    """Convert one MCP Tool to the OpenAI tools-list entry format."""
    schema: dict[str, Any] = tool.inputSchema if tool.inputSchema else {}

    # OpenAI requires "type": "object" at the top level
    if schema.get("type") != "object":
        schema = {"type": "object", "properties": schema, "required": []}

    # Remove JSON Schema keywords OpenAI doesn't accept at the top level
    schema.pop("$schema", None)

    return {
        "type": "function",
        "function": {
            "name": namespaced_name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


async def build_tool_registry(servers: list[MCPServer]) -> tuple[list[dict[str, Any]], ToolRegistry]:
    """
    Fetch tools from all servers, namespace them, and return:
      - openai_tools: list ready to pass as `tools=` to the LLM
      - registry: mapping from namespaced name back to (server, original_name)
    """
    openai_tools: list[dict[str, Any]] = []
    registry: ToolRegistry = {}

    for server in servers:
        tools = await server.list_tools()
        for tool in tools:
            ns_name = _namespace(server.name, tool.name)
            registry[ns_name] = (server, tool.name)
            openai_tools.append(_mcp_tool_to_openai(ns_name, tool))

    return openai_tools, registry
