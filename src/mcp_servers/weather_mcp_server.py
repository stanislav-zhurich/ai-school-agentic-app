"""MCP server providing weather data via Open-Meteo and its Geocoding API (no API key required)."""

from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("open-meteo-weather")

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> human-readable description
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def _weather_desc(code: int) -> str:
    return _WMO_CODES.get(code, f"Unknown (code {code})")


def _geocode(city: str) -> tuple[float, float, str] | None:
    """Return (latitude, longitude, display_name) for a city name, or None if not found."""
    try:
        resp = httpx.get(
            _GEO_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        r = results[0]
        parts = [r.get("name", city)]
        if r.get("admin1"):
            parts.append(r["admin1"])
        if r.get("country"):
            parts.append(r["country"])
        return r["latitude"], r["longitude"], ", ".join(parts)
    except (httpx.RequestError, httpx.HTTPStatusError, KeyError):
        return None


@mcp.tool()
def get_current_weather(city: str) -> str:
    """Get the current weather conditions for a city.

    Args:
        city: City name in English, e.g. 'London', 'Tokyo', 'New York'.
    """
    loc = _geocode(city)
    if loc is None:
        return f"Could not find location: '{city}'. Try a different spelling or a nearby larger city."
    lat, lon, display = loc

    try:
        resp = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,"
                    "precipitation,weather_code,cloud_cover,"
                    "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
                ),
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return f"Weather API error: {e}"

    data = resp.json()
    c = data.get("current", {})
    units = data.get("current_units", {})

    lines = [
        f"Current weather in {display}:",
        f"  Condition:    {_weather_desc(c.get('weather_code', 0))}",
        f"  Temperature:  {c.get('temperature_2m')} {units.get('temperature_2m', '°C')}"
        f"  (feels like {c.get('apparent_temperature')} {units.get('apparent_temperature', '°C')})",
        f"  Humidity:     {c.get('relative_humidity_2m')} {units.get('relative_humidity_2m', '%')}",
        f"  Cloud cover:  {c.get('cloud_cover')} {units.get('cloud_cover', '%')}",
        f"  Precipitation:{c.get('precipitation')} {units.get('precipitation', 'mm')}",
        f"  Wind:         {c.get('wind_speed_10m')} {units.get('wind_speed_10m', 'km/h')}"
        f"  gusts {c.get('wind_gusts_10m')} {units.get('wind_gusts_10m', 'km/h')},"
        f"  direction {c.get('wind_direction_10m')}°",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_weather_forecast(
    city: str,
    days: int = 7,
) -> str:
    """Get a daily weather forecast for a city.

    Args:
        city: City name in English, e.g. 'Paris', 'Sydney'.
        days: Number of forecast days (1–16). Default: 7.
    """
    days = max(1, min(days, 16))
    loc = _geocode(city)
    if loc is None:
        return f"Could not find location: '{city}'. Try a different spelling or a nearby larger city."
    lat, lon, display = loc

    try:
        resp = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum,precipitation_probability_max,"
                    "wind_speed_10m_max,wind_gusts_10m_max"
                ),
                "timezone": "auto",
                "forecast_days": days,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return f"Weather API error: {e}"

    data = resp.json()
    daily = data.get("daily", {})
    units = data.get("daily_units", {})

    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    precip_prob = daily.get("precipitation_probability_max", [])
    wind_max = daily.get("wind_speed_10m_max", [])

    lines = [f"{days}-day forecast for {display}:", ""]
    for i, date in enumerate(dates):
        desc = _weather_desc(codes[i] if i < len(codes) else 0)
        hi = t_max[i] if i < len(t_max) else "?"
        lo = t_min[i] if i < len(t_min) else "?"
        pr = precip[i] if i < len(precip) else "?"
        pp = precip_prob[i] if i < len(precip_prob) else "?"
        wm = wind_max[i] if i < len(wind_max) else "?"
        tu = units.get("temperature_2m_max", "°C")
        pu = units.get("precipitation_sum", "mm")
        wu = units.get("wind_speed_10m_max", "km/h")
        lines.append(
            f"  {date}  {desc}\n"
            f"    Temp: {lo}{tu} – {hi}{tu}  |  "
            f"Precip: {pr}{pu} ({pp}%)  |  "
            f"Wind max: {wm}{wu}"
        )
    return "\n".join(lines)


@mcp.tool()
def search_location(query: str) -> str:
    """Search for a location by name and return its coordinates and details.
    Useful for disambiguating cities with the same name.

    Args:
        query: Location name to search for, e.g. 'Springfield' or 'Valencia Spain'.
    """
    try:
        resp = httpx.get(
            _GEO_URL,
            params={"name": query, "count": 5, "language": "en", "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return f"Geocoding error: {e}"

    if not results:
        return f"No locations found for '{query}'."

    lines = [f"Locations matching '{query}':"]
    for r in results:
        parts = [r.get("name", "")]
        if r.get("admin1"):
            parts.append(r["admin1"])
        if r.get("country"):
            parts.append(r["country"])
        name = ", ".join(p for p in parts if p)
        lines.append(f"  {name}  (lat={r['latitude']}, lon={r['longitude']})")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
