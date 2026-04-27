"""Typer CLI: `ask` (one-shot) and `chat` (REPL) commands."""


import asyncio
from contextlib import AsyncExitStack

import typer
from rich.console import Console
from rich.table import Table

from .agent import run_agent
from .config import NEWS_SPEC, WEATHER_SPEC
from .mcp_client import MCPServer

app = typer.Typer(
    name="ai-school-agent",
    help="Weather + News agent powered by MCP and OpenAI function-calling.",
    add_completion=False,
)
console = Console()


async def _with_servers(question: str, show_trace: bool) -> None:
    async with AsyncExitStack() as stack:
        weather = await stack.enter_async_context(MCPServer(WEATHER_SPEC))
        news = await stack.enter_async_context(MCPServer(NEWS_SPEC))

        with console.status("[bold green]Thinking…"):
            result = await run_agent(question, [weather, news])

    console.print()
    console.rule("[bold cyan]Answer")
    console.print(result.answer)

    if show_trace and result.trace:
        console.print()
        console.rule("[bold cyan]Tool trace")
        table = Table("Step", "Server", "Tool", "OK", "ms", show_header=True)
        for log in result.trace:
            table.add_row(
                str(log.step),
                log.server,
                log.tool,
                "✓" if log.ok else "✗",
                f"{log.duration_ms:.0f}",
            )
        console.print(table)


@app.command()
def ask(
    question: str = typer.Argument(..., help="The question to answer."),
    trace: bool = typer.Option(False, "--trace", "-t", help="Show tool-call trace."),
) -> None:
    """Answer a single question and exit."""
    asyncio.run(_with_servers(question, trace))


async def _chat_loop() -> None:
    async with AsyncExitStack() as stack:
        weather = await stack.enter_async_context(MCPServer(WEATHER_SPEC))
        news = await stack.enter_async_context(MCPServer(NEWS_SPEC))
        console.print("[bold green]Chat started. Type 'exit' or 'quit' to stop.[/]")

        while True:
            try:
                question = console.input("[bold]You:[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if question.lower() in {"exit", "quit", ""}:
                break

            with console.status("[bold green]Thinking…"):
                result = await run_agent(question, [weather, news])

            console.print(f"[bold cyan]Agent:[/] {result.answer}")
            console.print()


@app.command()
def chat() -> None:
    """Start an interactive REPL session."""
    asyncio.run(_chat_loop())
