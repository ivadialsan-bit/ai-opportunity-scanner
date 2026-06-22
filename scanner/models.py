from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Lead:
    source: str
    city: str
    niche: str
    osm_type: str
    osm_id: int
    name: str
    lat: float | None
    lon: float | None
    address: str
    phone: str
    website: str
    email: str
    tags: dict[str, Any] = field(default_factory=dict)
    lead_score: int = 0
    opportunity_flags: list[str] = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""
