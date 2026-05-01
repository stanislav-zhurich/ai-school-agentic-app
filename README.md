# AI School Agentic App

A Python agent that answers questions about **current weather** and **latest news** using a hand-rolled LLM function-calling loop backed by two local MCP servers.

---

## Goal

Demonstrate how to build an agentic application from first principles:

- An **agent loop** that drives an Azure OpenAI model with function-calling
- Two **MCP (Model Context Protocol) servers** that expose real-world data as typed tools
- A **CLI** for both one-shot questions and an interactive REPL
- An **evaluation suite** for measuring routing accuracy and answer quality

No paid API keys are required for the data sources — weather comes from [Open-Meteo](https://open-meteo.com/) and news from [Google News RSS](https://news.google.com/rss).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        CLI (Typer)                       │
│            ask "…"  /  chat (REPL)                       │
└────────────────────────┬────────────────────────────────┘
                         │ question
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     Agent Loop                           │
│  1. Build tool registry from connected MCP servers       │
│  2. Call Azure OpenAI (gpt-4o) with tools                │
│  3. Dispatch tool calls → MCP servers                    │
│  4. Feed results back; repeat until final answer         │
└───────────┬─────────────────────────┬───────────────────┘
            │ stdio (subprocess)       │ stdio (subprocess)
            ▼                         ▼
┌─────────────────────┐   ┌─────────────────────────────┐
│  Weather MCP Server │   │      News MCP Server        │
│  (Open-Meteo API)   │   │   (Google News RSS)         │
│                     │   │                             │
│  • get_current_     │   │  • get_latest_news          │
│    weather          │   │  • search_news              │
│  • get_weather_     │   └─────────────────────────────┘
│    forecast         │
│  • search_location  │
└─────────────────────┘

External APIs (no key required):
  https://api.open-meteo.com          — weather forecasts
  https://geocoding-api.open-meteo.com — city → coordinates
  https://news.google.com/rss         — news headlines & search
```

Each MCP server runs as a **child process** connected to the agent over stdio. The agent starts them on demand, queries their tool catalogue, and shuts them down when done.

---

## Project Structure

```
ai-school-agentic-app/
│
├── src/
│   ├── ai_school_agentic_app/      # Main application package
│   │   ├── agent.py                # Agent loop (LLM + tool dispatch)
│   │   ├── cli.py                  # Typer CLI (ask / chat commands)
│   │   ├── config.py               # Env config & MCP server specs
│   │   ├── mcp_client.py           # Async MCP client wrapper (stdio)
│   │   ├── prompts.py              # System prompt
│   │   └── tool_schema.py          # Tool registry builder
│   │
│   └── mcp_servers/                # Standalone MCP server scripts
│       ├── weather_mcp_server.py   # Open-Meteo weather & geocoding
│       └── newsdata_mcp_server.py  # Google News RSS headlines
│
├── eval/
│   ├── dataset.jsonl               # Evaluation questions with labels
│   ├── rubric.md                   # Rubric for scoring answers
│   ├── results/                    # Auto-generated JSON reports
│   └── run_eval.py                 # Evaluation runner CLI
│
├── tests/
│   ├── test_agent_routing.py
│   └── test_tool_schema.py
│
├── .env                            # Local secrets (not committed)
├── .env.example                    # Template for .env
├── pyproject.toml                  # Dependencies & entry points
└── .vscode/launch.json             # Debug configurations
```

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| [Python 3.11+](https://www.python.org/) | Runtime |
| [uv](https://docs.astral.sh/uv/) | Package manager & script runner |
| [Node.js 18+](https://nodejs.org/) | Required only for the MCP Inspector UI |
| Azure OpenAI API key | LLM backend |

Install `uv` if you don't have it:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Installation

```powershell
# 1. Clone the repository
git clone <repo-url>
cd ai-school-agentic-app

# 2. Create virtual environment and install all dependencies
uv sync
```

That's it. `uv sync` reads `pyproject.toml`, creates `.venv/`, and installs the package in editable mode along with all dependencies.

---

## Configuration

Copy the example file and fill in your Azure OpenAI key:

```powershell
copy .env.example .env
```

Edit `.env`:

```env
# Required
OPENAI_API_KEY=your-azure-api-key-here

# Optional — defaults shown below
# AZURE_OPENAI_ENDPOINT=https://ai-proxy.lab.epam.com
# AZURE_OPENAI_API_VERSION=2024-10-21
# LLM_MODEL=gpt-4o
```

Alternatively, set `OPENAI_API_KEY` as a system / user environment variable — the app will pick it up automatically.

---

## Running the Application

### One-shot question

```powershell
uv run ai-school-agent ask "What is the weather in Tokyo?"
```

With tool-call trace:

```powershell
uv run ai-school-agent ask "What is the weather in Tokyo?" --trace
```

### Interactive REPL (chat)

```powershell
uv run ai-school-agent chat
```

Type `exit` or `quit` to stop the session.

### Example questions

```
What is the weather in London?
Give me a 5-day forecast for Paris.
What are the latest news headlines?
Search news about artificial intelligence.
What's the weather in Berlin and any news from Germany?
```

> **Windows terminal tip:** prefix commands with `$env:PYTHONUTF8="1";` to avoid encoding issues with special characters in output.

---

## Debugging in Cursor / VS Code

Three debug configurations are provided in `.vscode/launch.json`:

| Configuration | What it runs |
|---------------|-------------|
| `ask: What is the weather in London?` | One-shot weather question with `--trace` |
| `ask: Latest news` | One-shot news question with `--trace` |
| `chat REPL` | Interactive chat session |

**To start debugging:**

1. Open the **Run & Debug** panel (`Ctrl+Shift+D`)
2. Select a configuration from the dropdown
3. Press **F5**

Output (including the tool trace table) appears in the **integrated terminal** panel.

You can set breakpoints anywhere in `agent.py`, `mcp_client.py`, or the MCP server scripts.

---

## MCP Inspector (Visual Tool Tester)

The MCP Inspector lets you browse and call individual MCP tools interactively through a browser UI — useful for testing tools in isolation before running the full agent.

### Start the inspector

```powershell
# Inspect the weather server
uv run mcp dev src/mcp_servers/weather_mcp_server.py

# Inspect the news server
uv run mcp dev src/mcp_servers/newsdata_mcp_server.py
```

Then open the URL printed in the terminal (usually `http://localhost:6274`).

### Using the inspector UI

1. **Tools tab** — lists all tools exposed by the server with their input schemas
2. Click any tool name to expand it
3. Fill in the parameters (e.g. `city: "London"` for `get_current_weather`)
4. Click **Run** — the result appears immediately below

### Available tools per server

**Weather server** (`weather_mcp_server.py`):

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_current_weather` | `city: str` | Current conditions: temp, humidity, wind, cloud cover |
| `get_weather_forecast` | `city: str`, `days: int` (1–16) | Daily high/low, precipitation, wind for N days |
| `search_location` | `query: str` | Geocode a place name; returns up to 5 matches with coordinates |

**News server** (`newsdata_mcp_server.py`):

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_latest_news` | `language_country: str`, `size: int` | Top headlines from Google News RSS |
| `search_news` | `query: str`, `language_country: str`, `size: int` | Search Google News by keyword or phrase |

> **Note:** Node.js must be installed for the inspector UI to open in the browser. The proxy server (port 6277) and UI server (port 6274) are started automatically.

---

## Running Tests

```powershell
uv run pytest
```

Run with verbose output:

```powershell
uv run pytest -v
```

---

## Running the Evaluation Suite

The evaluation suite measures tool-routing accuracy and answer quality across a labelled dataset.

```powershell
uv run ai-school-eval
```

Options:

```powershell
# Run only the first 5 questions
uv run ai-school-eval --limit 5

# Use a custom dataset file
uv run ai-school-eval --dataset path/to/dataset.jsonl

# Save the report to a specific path
uv run ai-school-eval --output eval/results/my_run.json
```

The runner prints a summary table with per-question routing, safety, and must-mention scores, then writes a full JSON report to `eval/results/`.

---

## Key Design Decisions

**Sync vs async tool functions in MCP servers**
The MCP server scripts (`weather_mcp_server.py`, `newsdata_mcp_server.py`) use synchronous `httpx` calls inside `@mcp.tool()` functions. This is intentional: each MCP server runs in its own subprocess driven by `FastMCP`, which manages its own event loop. Using sync HTTP keeps the server code simple and avoids nested event-loop issues. The agent side (`mcp_client.py`, `agent.py`) is fully async.

**Tool namespacing**
Tool names are prefixed with the server name (`weather__get_current_weather`, `news__search_news`) to avoid collisions when both servers expose similarly-named functions.

**No external API keys for data**
Both data sources are free and keyless: Open-Meteo for weather, Google News RSS for news.
