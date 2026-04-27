"""Hand-rolled agent loop: LLM function-calling → MCP tool dispatch → repeat."""


import json
import time
from typing import Any

from openai import AsyncAzureOpenAI
from pydantic import BaseModel

from .config import get_azure_api_version, get_azure_endpoint, get_llm_model, get_openai_api_key
from .mcp_client import MCPServer
from .prompts import system_message
from .tool_schema import ToolRegistry, build_tool_registry

MAX_STEPS = 6
MAX_TOOL_CALLS_PER_STEP = 5
MAX_TOOL_OUTPUT_CHARS = 8_000


class StepLog(BaseModel):
    step: int
    server: str
    tool: str
    namespaced_tool: str
    args: dict[str, Any]
    ok: bool
    duration_ms: float


class AgentResult(BaseModel):
    answer: str
    trace: list[StepLog]


def _truncate(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated, {len(text) - limit} chars omitted]"


def _tool_result_text(content: Any) -> str:
    """Extract plain text from MCP CallToolResult content."""
    if isinstance(content, list):
        parts = []
        for item in content:
            if hasattr(item, "text"):
                parts.append(item.text)
            elif isinstance(item, dict):
                parts.append(item.get("text", json.dumps(item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if hasattr(content, "text"):
        return content.text
    return str(content)


async def run_agent(
    question: str,
    servers: list[MCPServer],
    *,
    max_steps: int = MAX_STEPS,
) -> AgentResult:
    client = AsyncAzureOpenAI(
        api_key=get_openai_api_key(),
        azure_endpoint=get_azure_endpoint(),
        api_version=get_azure_api_version(),
    )
    model = get_llm_model()

    openai_tools, registry = await build_tool_registry(servers)
    messages: list[dict[str, Any]] = [system_message(), {"role": "user", "content": question}]
    trace: list[StepLog] = []

    for step in range(max_steps):
        response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            tools=openai_tools if openai_tools else None,  # type: ignore[arg-type]
            tool_choice="auto" if openai_tools else None,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))  # type: ignore[arg-type]

        if not msg.tool_calls:
            return AgentResult(answer=msg.content or "", trace=trace)

        for tc in msg.tool_calls[:MAX_TOOL_CALLS_PER_STEP]:
            ns_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            server, original_name = _resolve(ns_name, registry)
            t0 = time.perf_counter()
            result = await server.call_tool(original_name, args)
            elapsed = (time.perf_counter() - t0) * 1000

            trace.append(
                StepLog(
                    step=step,
                    server=server.name,
                    tool=original_name,
                    namespaced_tool=ns_name,
                    args=args,
                    ok=not result.isError,
                    duration_ms=round(elapsed, 1),
                )
            )

            tool_text = _truncate(_tool_result_text(result.content))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_text,
                }
            )

    # Fallback: ask LLM to summarise with what it has
    final = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
    )
    answer = final.choices[0].message.content or "(max steps reached)"
    return AgentResult(answer=answer, trace=trace)


def _resolve(ns_name: str, registry: ToolRegistry) -> tuple[MCPServer, str]:
    if ns_name in registry:
        return registry[ns_name]
    raise KeyError(f"Tool {ns_name!r} not found in registry. Available: {list(registry)}")
