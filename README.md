# ai-school-agentic-app

A hand-rolled agent that answers weather and news questions by calling two MCP servers via the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

```
User → CLI → Agent Loop → LLM (function-calling)
                       ↘ MCP weather client → Open-Meteo MCP server
                       ↘ MCP news client    → RSS/Feed MCP server
```

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python ≥ 3.11** | Managed by [uv](https://docs.astral.sh/uv/) |
| **uv** | `pip install uv` or see [uv install docs](https://docs.astral.sh/uv/getting-started/installation/) |
| **Node.js ≥ 18** | Required to run the MCP servers via `npx` |
| **OpenAI API key** | Set in `.env` as `OPENAI_API_KEY` |

---

## Setup

```powershell
# 1. Clone / enter the project
cd ai-school-agentic-app

# 2. Install dependencies (creates .venv automatically)
uv sync

# 3. Configure environment
copy .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

---

## Running the agent

### Single question

```powershell
uv run ai-school-agent ask "What is the weather in Berlin right now?"
```

Show the tool-call trace:

```powershell
uv run ai-school-agent ask "Latest tech news headlines" --trace
```

### Interactive chat

```powershell
uv run ai-school-agent chat
```

---

## Running the evaluation

```powershell
uv run ai-school-eval
```

This runs all rows in `eval/dataset.jsonl`, prints a summary table with tool-routing accuracy and safety pass rate, and writes a timestamped JSON report to `eval/results/`.

Run only the first 4 rows for a quick smoke-test:

```powershell
uv run ai-school-eval --limit 4
```

---

## Project structure

```
src/ai_school_agentic_app/
├── config.py        # env vars + MCPServerSpec definitions
├── mcp_server.py    # async stdio MCP client wrapper
├── tool_schema.py   # MCP Tool → OpenAI function schema conversion
├── agent.py         # hand-rolled agent loop + StepLog
├── prompts.py       # system prompt
└── cli.py           # Typer: ask / chat commands

eval/
├── dataset.jsonl    # 16 labeled evaluation rows
├── rubric.md        # groundedness rubric (1–3 scale)
├── run_eval.py      # eval runner (routing accuracy + safety)
└── results/         # timestamped JSON reports (git-ignored)

tests/
├── test_tool_schema.py    # unit tests for schema conversion
└── test_agent_routing.py  # agent loop tests with mocked LLM
```

---

## Running tests

```powershell
uv run pytest
```

Lint:

```powershell
uv run ruff check src/ eval/ tests/
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key. |
| `LLM_MODEL` | `gpt-4o-mini` | Any OpenAI chat-completion model. |
| `NEWS_FEED_URLS` | BBC + Reuters RSS | Comma-separated RSS/Atom URLs for the news MCP server. |

---

## Swapping components

**Different news feeds** — set `NEWS_FEED_URLS` in `.env`:

```
NEWS_FEED_URLS=https://rss.nytimes.com/services/xml/rss/nyt/World.xml,https://feeds.skynews.com/feeds/rss/world.xml
```

**Different LLM provider** — update `agent.py` to use `anthropic` or another SDK; the agent loop is provider-agnostic aside from the `openai` import.

**Different MCP weather server** — update `WEATHER_SPEC` in `config.py` with the new `command` and `args`.
