"""Real weather via Open-Meteo (free, no API key).

Geocodes the configured city once, then fetches current conditions. Wrapped
with timeout + retry + in-memory TTL cache + graceful degradation: any
failure returns None and the HUD shows a friendly fallback rather than
freezing.

Env:
  WEATHER_CITY   city name to geocode (default "Sofia")
  WEATHER_LAT    optional: skip geocoding by providing coordinates directly
  WEATHER_LON
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Optional, Tuple

import httpx

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_CACHE_TTL = 600  # seconds
_cache: dict[str, tuple[float, dict]] = {}
_geo_cache: dict[str, Tuple[float, float]] = {}

# WMO weather interpretation codes → (label, emoji).
_WMO = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    61: ("Light rain", "🌦️"),
    63: ("Rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Light snow", "🌨️"),
    73: ("Snow", "🌨️"),
    75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Rain showers", "🌦️"),
    81: ("Rain showers", "🌧️"),
    82: ("Violent showers", "⛈️"),
    85: ("Snow showers", "🌨️"),
    86: ("Snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm + hail", "⛈️"),
    99: ("Thunderstorm + hail", "⛈️"),
}


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> Optional[dict]:
    """GET with 2 retries and short timeouts; returns None on failure."""
    for attempt in range(2):
        try:
            r = await client.get(url, params=params, timeout=6.0)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 0:
                await asyncio.sleep(0.5)
    return None


async def _geocode(client: httpx.AsyncClient, city: str) -> Optional[Tuple[float, float]]:
    lat_env, lon_env = os.getenv("WEATHER_LAT"), os.getenv("WEATHER_LON")
    if lat_env and lon_env:
        return float(lat_env), float(lon_env)
    if city in _geo_cache:
        return _geo_cache[city]
    data = await _get_json(
        client, _GEO_URL, {"name": city, "count": 1, "language": "en", "format": "json"}
    )
    if not data or not data.get("results"):
        return None
    res = data["results"][0]
    coords = (float(res["latitude"]), float(res["longitude"]))
    _geo_cache[city] = coords
    return coords


async def get_weather(city: str) -> Optional[dict]:
    """Returns {tempC, label, emoji, city} or None (caller shows fallback)."""
    now = time.time()
    cached = _cache.get(city)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    try:
        async with httpx.AsyncClient() as client:
            coords = await _geocode(client, city)
            if not coords:
                return None
            lat, lon = coords
            data = await _get_json(
                client,
                _FORECAST_URL,
                {"latitude": lat, "longitude": lon,
                 "current": "temperature_2m,weather_code"},
            )
            if not data or "current" not in data:
                return None
            cur = data["current"]
            code = int(cur.get("weather_code", -1))
            label, emoji = _WMO.get(code, ("—", "🌡️"))
            result = {
                "tempC": round(float(cur["temperature_2m"])),
                "label": label,
                "emoji": emoji,
                "city": city,
            }
            _cache[city] = (now, result)
            return result
    except Exception:
        return None
