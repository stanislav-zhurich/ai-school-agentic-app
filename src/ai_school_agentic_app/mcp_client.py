"""Async MCP client wrapper for stdio-transport MCP servers."""


import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Tool

from .config import MCPServerSpec


class MCPServer:
    """Manages the lifecycle of a single stdio MCP server subprocess."""

    def __init__(self, spec: MCPServerSpec) -> None:
        self.spec = spec
        self.name = spec.name
        self._session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()

    async def start(self) -> None:
        params = StdioServerParameters(
            command=self.spec.command,
            args=self.spec.args,
            env=self.spec.env or None,
        )
        stdio_transport = await self._exit_stack.enter_async_context(stdio_client(params))
        read, write = stdio_transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

    async def stop(self) -> None:
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self) -> "MCPServer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError(f"MCPServer '{self.name}' is not started.")
        return self._session

    async def list_tools(self) -> list[Tool]:
        session = self._require_session()
        response = await session.list_tools()
        return response.tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> CallToolResult:
        session = self._require_session()
        return await session.call_tool(tool_name, arguments)


async def start_all(specs: list[MCPServerSpec]) -> tuple[MCPServer, ...]:
    """Start multiple MCP servers concurrently and return them."""
    servers = [MCPServer(spec) for spec in specs]
    await asyncio.gather(*(s.start() for s in servers))
    return tuple(servers)
