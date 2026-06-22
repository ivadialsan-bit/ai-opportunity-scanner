from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CityConfig:
    name: str
    bbox: tuple[float, float, float, float]  # south, west, north, east


SUPPORTED_CITIES: dict[str, CityConfig] = {
    "volgograd": CityConfig("Волгоград", (48.55, 44.30, 48.90, 44.75)),
    "волгоград": CityConfig("Волгоград", (48.55, 44.30, 48.90, 44.75)),

    "krasnodar": CityConfig("Краснодар", (44.92, 38.80, 45.15, 39.15)),
    "краснодар": CityConfig("Краснодар", (44.92, 38.80, 45.15, 39.15)),

    "rostov-on-don": CityConfig("Ростов-на-Дону", (47.10, 39.55, 47.35, 39.95)),
    "ростов-на-дону": CityConfig("Ростов-на-Дону", (47.10, 39.55, 47.35, 39.95)),
    "ростов": CityConfig("Ростов-на-Дону", (47.10, 39.55, 47.35, 39.95)),

    "astrakhan": CityConfig("Астрахань", (46.25, 47.85, 46.45, 48.15)),
    "астрахань": CityConfig("Астрахань", (46.25, 47.85, 46.45, 48.15)),

    "saratov": CityConfig("Саратов", (51.45, 45.80, 51.65, 46.20)),
    "саратов": CityConfig("Саратов", (51.45, 45.80, 51.65, 46.20)),
}


SOURCE_ENDPOINTS: dict[str, str] = {
    "osm": "https://overpass-api.de/api/interpreter",
    "overpass": "https://overpass-api.de/api/interpreter",
}


NICHE_PATTERNS: dict[str, list[str]] = {
    "кондиционеры": [
        "кондиционер",
        "кондиционеры",
        "сплит",
        "split",
        "климат",
        "climate",
        "вентиляц",
        "холод",
        "air.?condition",
        "hvac",
    ],
    "сплит-системы": [
        "кондиционер",
        "кондиционеры",
        "сплит",
        "split",
        "климат",
        "climate",
        "вентиляц",
        "air.?condition",
        "hvac",
    ],
}


def normalize_key(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


def get_city(city: str) -> CityConfig:
    key = normalize_key(city)
    if key not in SUPPORTED_CITIES:
        supported = ", ".join(sorted({c.name for c in SUPPORTED_CITIES.values()}))
        raise ValueError(f"Город пока не поддержан: {city}. Поддержаны: {supported}")
    return SUPPORTED_CITIES[key]


def get_patterns(query: str) -> list[str]:
    key = normalize_key(query)
    return NICHE_PATTERNS.get(key, [query.strip()])
