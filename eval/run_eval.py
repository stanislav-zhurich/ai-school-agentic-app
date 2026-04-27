"""Evaluation runner: measures tool-routing accuracy, safety, and optional rubric."""


import asyncio
import json
import sys
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

# Allow running as `uv run eval/run_eval.py` or via the script entry-point.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_school_agentic_app.agent import run_agent  # noqa: E402
from ai_school_agentic_app.config import NEWS_SPEC, WEATHER_SPEC  # noqa: E402
from ai_school_agentic_app.mcp_client import MCPServer  # noqa: E402

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"

console = Console()
cli = typer.Typer(add_completion=False)


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _observed_domains(trace: list[Any]) -> set[str]:
    domains: set[str] = set()
    for step in trace:
        if step.namespaced_tool.startswith("weather__"):
            domains.add("weather")
        elif step.namespaced_tool.startswith("news__"):
            domains.add("news")
    return domains


def _expected_domains(expected_domain: str) -> set[str]:
    if expected_domain == "both":
        return {"weather", "news"}
    return {expected_domain}


def _routing_score(observed: set[str], expected: set[str]) -> float:
    return 1.0 if observed == expected else 0.0


def _safety_pass(answer: str, forbidden: list[str] | None) -> bool:
    if not forbidden:
        return True
    lower = answer.lower()
    return not any(f.lower() in lower for f in forbidden)


def _must_mention_pass(answer: str, must_mention: list[str] | None) -> bool:
    if not must_mention:
        return True
    lower = answer.lower()
    return all(m.lower() in lower for m in must_mention)


async def _run_all(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit:
        rows = rows[:limit]

    results: list[dict[str, Any]] = []

    async with AsyncExitStack() as stack:
        weather = await stack.enter_async_context(MCPServer(WEATHER_SPEC))
        news = await stack.enter_async_context(MCPServer(NEWS_SPEC))

        for row in rows:
            row_id = row["id"]
            question = row["question"]
            console.print(f"  [dim]Running {row_id}:[/dim] {question[:70]}")

            try:
                agent_result = await run_agent(question, [weather, news])
                answer = agent_result.answer
                trace = agent_result.trace
                error = None
            except Exception as exc:  # noqa: BLE001
                answer = ""
                trace = []
                error = str(exc)
                console.print(f"    [red]ERROR: {error}[/red]")

            observed = _observed_domains(trace)
            expected = _expected_domains(row["expected_domain"])
            routing = _routing_score(observed, expected)
            safety = _safety_pass(answer, row.get("forbidden"))
            mentions = _must_mention_pass(answer, row.get("must_mention"))

            results.append(
                {
                    "id": row_id,
                    "question": question,
                    "expected_domain": row["expected_domain"],
                    "observed_domains": sorted(observed),
                    "routing_score": routing,
                    "safety_pass": safety,
                    "must_mention_pass": mentions,
                    "answer": answer,
                    "trace": [t.model_dump() for t in trace],
                    "error": error,
                }
            )

    return results


def _print_summary(results: list[dict[str, Any]]) -> None:
    table = Table(title="Eval Results", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Domain", style="dim")
    table.add_column("Routing", justify="center")
    table.add_column("Safety", justify="center")
    table.add_column("Mentions", justify="center")

    routing_scores = []
    safety_scores = []

    for r in results:
        routing_scores.append(r["routing_score"])
        safety_scores.append(float(r["safety_pass"]))
        table.add_row(
            r["id"],
            r["expected_domain"],
            "✓" if r["routing_score"] == 1.0 else "✗",
            "✓" if r["safety_pass"] else "✗",
            "✓" if r["must_mention_pass"] else "✗",
        )

    console.print(table)
    n = len(results)
    console.print(f"\n[bold]Routing accuracy:[/bold] {sum(routing_scores)/n:.1%}  ({int(sum(routing_scores))}/{n})")
    console.print(f"[bold]Safety pass rate:[/bold]  {sum(safety_scores)/n:.1%}  ({int(sum(safety_scores))}/{n})")


@cli.command()
def main(
    dataset: Path = typer.Option(DATASET_PATH, "--dataset", "-d", help="Path to dataset.jsonl"),
    limit: int = typer.Option(0, "--limit", "-n", help="Run only the first N rows (0 = all)"),
    output: Path = typer.Option(
        RESULTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}Z.json",
        "--output",
        "-o",
        help="Output JSON report path",
    ),
) -> None:
    """Run the evaluation suite and write a JSON report."""
    console.rule("[bold cyan]AI-School Agent Eval")
    rows = _load_dataset(dataset)
    console.print(f"Loaded [bold]{len(rows)}[/bold] rows from {dataset}")

    results = asyncio.run(_run_all(rows, limit or None))

    _print_summary(results)

    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset),
        "n": len(results),
        "routing_accuracy": sum(r["routing_score"] for r in results) / len(results),
        "safety_pass_rate": sum(float(r["safety_pass"]) for r in results) / len(results),
        "rows": results,
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\n[green]Report written to:[/green] {output}")


if __name__ == "__main__":
    cli()
