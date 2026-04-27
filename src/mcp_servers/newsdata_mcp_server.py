"""MCP server exposing Google News RSS as tools (no API key required)."""

import xml.etree.ElementTree as ET
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("google-news")

_BASE = "https://news.google.com/rss"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; news-mcp/1.0)"}


def _fetch_rss(url: str, params: dict) -> str:
    try:
        resp = httpx.get(url, params=params, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Google News error {e.response.status_code}: {e.response.text[:200]}"
    except httpx.RequestError as e:
        return f"Network error contacting Google News: {e}"
    return resp.text


def _parse_and_format(xml_text: str, limit: int) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return f"Failed to parse RSS feed: {e}"

    items = root.findall(".//item")[:limit]
    if not items:
        return "No articles found."

    lines: list[str] = []
    for i, item in enumerate(items, 1):
        title = (item.findtext("title") or "(no title)").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        description = (item.findtext("description") or "").strip()

        header = f"{i}. {title}"
        if source:
            header += f"  [{source}]"
        lines.append(header)
        if pub_date:
            lines.append(f"   Published: {pub_date}")
        if description and description != title:
            lines.append(f"   {description[:300]}")
        if link:
            lines.append(f"   {link}")

    return "\n".join(lines)


@mcp.tool()
def get_latest_news(
    language_country: str = "en-US:US",
    size: int = 10,
) -> str:
    """Get the latest top headlines from Google News RSS.

    Args:
        language_country: Language and country code in 'hl-GL:ceid' format,
                          e.g. 'en-US:US', 'en-GB:GB', 'de-DE:DE'. Default: 'en-US:US'.
        size: Number of articles to return (1-20). Default: 10.
    """
    hl, ceid = _parse_lang_country(language_country)
    params = {"hl": hl, "gl": ceid.split(":")[0] if ":" in ceid else ceid, "ceid": ceid}
    xml_text = _fetch_rss(_BASE, params)
    return _parse_and_format(xml_text, max(1, min(size, 20)))


@mcp.tool()
def search_news(
    query: str,
    language_country: str = "en-US:US",
    size: int = 10,
) -> str:
    """Search Google News RSS for articles matching a query.

    Args:
        query: Search keywords or phrase. Supports quoted phrases and
               boolean operators (AND, OR, -exclude). Example: 'AI AND robots'.
        language_country: Language and country code in 'hl-GL:ceid' format,
                          e.g. 'en-US:US', 'en-GB:GB', 'de-DE:DE'. Default: 'en-US:US'.
        size: Number of articles to return (1-20). Default: 10.
    """
    hl, ceid = _parse_lang_country(language_country)
    params = {
        "q": query,
        "hl": hl,
        "gl": ceid.split(":")[0] if ":" in ceid else ceid,
        "ceid": ceid,
    }
    xml_text = _fetch_rss(f"{_BASE}/search", params)
    return _parse_and_format(xml_text, max(1, min(size, 20)))


def _parse_lang_country(lang_country: str) -> tuple[str, str]:
    """Split 'en-US:US' into ('en-US', 'US:en') as Google expects."""
    if ":" in lang_country:
        hl, country = lang_country.split(":", 1)
    else:
        hl, country = lang_country, "US"
    # Google ceid format is 'COUNTRY:LANG', e.g. 'US:en'
    lang_short = hl.split("-")[0]
    ceid = f"{country}:{lang_short}"
    return hl, ceid


if __name__ == "__main__":
    mcp.run()
