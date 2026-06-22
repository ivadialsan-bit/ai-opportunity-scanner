from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any

from scanner.config import CityConfig, SOURCE_ENDPOINTS, get_patterns
from scanner.models import Lead


DEFAULT_TIMEOUT_SECONDS = 45
USER_AGENT = "AIOpportunityScanner/0.1 manual-research-contact"


def _build_regex(patterns: list[str]) -> str:
    escaped: list[str] = []
    for item in patterns:
        item = item.strip()
        if not item:
            continue
        if any(ch in item for ch in [".?", "|", ".*"]):
            escaped.append(item)
        else:
            escaped.append(re.escape(item))
    return "|".join(escaped) or "кондиционер|сплит|климат"


def build_overpass_query(city: CityConfig, niche: str, limit: int) -> str:
    south, west, north, east = city.bbox
    regex = _build_regex(get_patterns(niche))

    return f"""
[out:json][timeout:25];
(
  node({south},{west},{north},{east})["name"~"{regex}",i];
  way({south},{west},{north},{east})["name"~"{regex}",i];
  relation({south},{west},{north},{east})["name"~"{regex}",i];

  node({south},{west},{north},{east})["operator"~"{regex}",i];
  way({south},{west},{north},{east})["operator"~"{regex}",i];
  relation({south},{west},{north},{east})["operator"~"{regex}",i];

  node({south},{west},{north},{east})["brand"~"{regex}",i];
  way({south},{west},{north},{east})["brand"~"{regex}",i];
  relation({south},{west},{north},{east})["brand"~"{regex}",i];

  node({south},{west},{north},{east})["description"~"{regex}",i];
  way({south},{west},{north},{east})["description"~"{regex}",i];
  relation({south},{west},{north},{east})["description"~"{regex}",i];

  node({south},{west},{north},{east})["shop"~"appliance|electronics|trade",i];
  way({south},{west},{north},{east})["shop"~"appliance|electronics|trade",i];

  node({south},{west},{north},{east})["craft"~"hvac|air_conditioning|electrician",i];
  way({south},{west},{north},{east})["craft"~"hvac|air_conditioning|electrician",i];

  node({south},{west},{north},{east})["service"~"{regex}",i];
  way({south},{west},{north},{east})["service"~"{regex}",i];
);
out center {limit};
"""


def fetch_overpass(query: str, source: str = "osm") -> dict[str, Any]:
    endpoint = SOURCE_ENDPOINTS.get(source)
    if not endpoint:
        raise ValueError(f"Источник пока не поддержан: {source}. Используй: osm")

    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        method="POST",
    )

    time.sleep(1.0)

    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _tag(tags: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value)
    return ""


def _address(tags: dict[str, Any]) -> str:
    chunks = [
        _tag(tags, "addr:city"),
        _tag(tags, "addr:street"),
        _tag(tags, "addr:housenumber"),
    ]
    return ", ".join([x for x in chunks if x])


def parse_elements(data: dict[str, Any], city: CityConfig, niche: str, source: str) -> list[Lead]:
    leads: list[Lead] = []
    seen: set[tuple[str, int]] = set()

    for item in data.get("elements", []):
        osm_type = str(item.get("type", ""))
        osm_id = int(item.get("id", 0))
        key = (osm_type, osm_id)
        if key in seen:
            continue
        seen.add(key)

        tags = item.get("tags", {}) or {}
        name = _tag(tags, "name", "operator", "brand")
        if not name:
            continue

        lat = item.get("lat")
        lon = item.get("lon")
        if (lat is None or lon is None) and isinstance(item.get("center"), dict):
            lat = item["center"].get("lat")
            lon = item["center"].get("lon")

        lead = Lead(
            source=source,
            city=city.name,
            niche=niche,
            osm_type=osm_type,
            osm_id=osm_id,
            name=name,
            lat=float(lat) if lat is not None else None,
            lon=float(lon) if lon is not None else None,
            address=_address(tags),
            phone=_tag(tags, "phone", "contact:phone"),
            website=_tag(tags, "website", "contact:website", "url"),
            email=_tag(tags, "email", "contact:email"),
            tags=tags,
        )
        leads.append(lead)

    return leads
