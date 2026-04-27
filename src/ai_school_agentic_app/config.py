"""Environment config and MCP server specifications."""


import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set.")
    return value


@dataclass(frozen=True)
class MCPServerSpec:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


# --- LLM / Azure OpenAI settings ---

_AZURE_DEFAULT_ENDPOINT = "https://ai-proxy.lab.epam.com"
_AZURE_DEFAULT_API_VERSION = "2024-10-21"
_AZURE_DEFAULT_DEPLOYMENT = "gpt-4o"


def get_openai_api_key() -> str:
    return _require("OPENAI_API_KEY")


def get_azure_endpoint() -> str:
    return os.getenv("AZURE_OPENAI_ENDPOINT", _AZURE_DEFAULT_ENDPOINT)


def get_azure_api_version() -> str:
    return os.getenv("AZURE_OPENAI_API_VERSION", _AZURE_DEFAULT_API_VERSION)


def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", _AZURE_DEFAULT_DEPLOYMENT)


# --- MCP server specs ---

WEATHER_SPEC = MCPServerSpec(
    name="weather",
    command="uv",
    args=["run", "src/mcp_servers/weather_mcp_server.py"],
)

NEWS_SPEC = MCPServerSpec(
    name="news",
    command="uv",
    args=["run", "src/mcp_servers/newsdata_mcp_server.py"],
)
