from __future__ import annotations

import json
import time
import random
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from typing import Any


@dataclass
class YandexLead:
    source: str = "yandex"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    url: str = ""
    rating: str = ""
    reviews_count: str = ""
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""


# Публичный ключ Яндекс Карт (открытый, без регистрации)
YANDEX_SEARCH_API = "https://search-maps.yandex.ru/v1/"
YANDEX_API_KEY = "1f50b6bd-18b5-4ce0-9017-b9b05e5f2d2b"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://yandex.ru/maps/",
}

YANDEX_NICHES: dict[str, list[str]] = {
    "сантехника":       ["сантехник", "сантехника Краснодар"],
    "электрика":        ["электрик", "электромонтаж"],
    "ремонт":           ["ремонт квартир", "отделочные работы"],
    "клининг":          ["уборка квартир", "клининг"],
    "красота":          ["маникюр", "салон красоты"],
    "автосервис":       ["автосервис", "шиномонтаж"],
    "фитнес":           ["фитнес клуб", "тренажерный зал"],
    "грузоперевозки":   ["грузоперевозки", "газель грузчики"],
    "фотограф":         ["фотограф", "фотостудия"],
    "бухгалтерия":      ["бухгалтер", "бухгалтерские услуги"],
    "кондиционеры":     ["кондиционеры монтаж", "климат оборудование"],
    "натяжные потолки": ["натяжные потолки"],
    "двери":            ["установка дверей"],
    "окна":             ["пластиковые окна"],
    "юрист":            ["юрист", "адвокат"],
    "медицина":         ["стоматология", "медицинский центр"],
    "ветеринар":        ["ветеринарная клиника"],
    "кафе":             ["кафе", "доставка еды"],
    "туризм":           ["турагентство"],
    "детский":          ["детский центр", "репетитор"],
}


def _fetch(query: str, skip: int = 0, results: int = 10) -> dict[str, Any]:
    params = {
        "text": query,
        "type": "biz",
        "lang": "ru_RU",
        "results": str(results),
        "skip": str(skip),
        "apikey": YANDEX_API_KEY,
    }
    url = YANDEX_SEARCH_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def _extract_phone(feature: dict) -> str:
    props = feature.get("properties", {})
    meta = props.get("CompanyMetaData", {})
    phones = meta.get("Phones", [])
    for p in phones:
        if isinstance(p, dict):
            formatted = p.get("formatted", "") or p.get("number", "")
            if formatted:
                return formatted
    return ""


def _extract_website(feature: dict) -> str:
    props = feature.get("properties", {})
    meta = props.get("CompanyMetaData", {})
    url = meta.get("url", "")
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


def _extract_address(feature: dict) -> str:
    props = feature.get("properties", {})
    meta = props.get("CompanyMetaData", {})
    addr = meta.get("address", "")
    if not addr:
        addr = props.get("description", "")
    return addr


def _extract_rating(feature: dict) -> tuple[str, str]:
    props = feature.get("properties", {})
    meta = props.get("CompanyMetaData", {})
    rating_data = meta.get("rating", {})
    if isinstance(rating_data, dict):
        rating = str(rating_data.get("ratings", "") or rating_data.get("score", ""))
        reviews = str(rating_data.get("reviews", ""))
        return rating, reviews
    return "", ""


def _score_and_enrich(lead: YandexLead) -> YandexLead:
    score = 20
    flags = ["source_yandex"]

    if lead.phone:
        score += 30
        flags.append("phone_present")
    else:
        flags.append("no_phone")

    if not lead.website:
        score += 25
        flags.append("no_website")
    else:
        flags.append("website_present")

    if lead.address:
        score += 5
        flags.append("address_present")

    if lead.phone and not lead.website:
        score += 5
        flags.append("hot_target")

    try:
        r = float(lead.rating or 0)
        if 0 < r < 4.0:
            flags.append("low_rating_opportunity")
    except Exception:
        pass

    lead.lead_score = min(score, 100)
    lead.opportunity_flags = flags

    if not lead.website:
        lead.suggested_offer = "Лендинг + онлайн-заявка + Telegram-уведомление за 48ч"
        lead.first_message = (
            f"Здравствуйте! Нашёл «{lead.name}» в {lead.city} на Яндекс Картах. "
            f"Вижу нет сайта — клиенты не могут оставить заявку онлайн. "
            f"Сделаю мини-страницу с формой заявки и уведомлением в Telegram за 48 часов. "
            f"От 4 900 ₽. Показать пример?"
        )
    else:
        lead.suggested_offer = "AI-контент + бот для онлайн-записи"
        lead.first_message = (
            f"Здравствуйте! Нашёл «{lead.name}» в {lead.city}. "
            f"Сайт есть — можно усилить онлайн-записью через Telegram-бот "
            f"и AI-контентом для соцсетей. От 7 900 ₽. Актуально?"
        )

    return lead


def scan_yandex(
    city: str,
    niche: str,
    limit: int = 50,
) -> tuple[list[YandexLead], str]:

    niche_key = niche.strip().lower()
    queries = YANDEX_NICHES.get(niche_key, [f"{niche.strip()} {city}"])
    queries = queries[:1]  # только первый запрос — быстрее

    leads: list[YandexLead] = []
    seen: set[str] = set()
    note = ""

    for query_tmpl in queries:
        if len(leads) >= limit:
            break

        # добавляем город если его нет в запросе
        query = query_tmpl if city.lower() in query_tmpl.lower() else f"{query_tmpl} {city}"
        skip = 0
        page_size = 10

        while len(leads) < limit:
            try:
                data = _fetch(query, skip=skip, results=page_size)
            except urllib.error.HTTPError as e:
                note = f"Яндекс HTTP {e.code}"
                break
            except Exception as ex:
                note = f"Яндекс ошибка: {ex}"
                break

            features = data.get("features", [])
            if not features:
                break

            for feature in features:
                props = feature.get("properties", {})
                meta = props.get("CompanyMetaData", {})
                name = (meta.get("name") or props.get("name") or "").strip()
                if not name:
                    continue

                phone = _extract_phone(feature)
                website = _extract_website(feature)
                address = _extract_address(feature)
                rating, reviews = _extract_rating(feature)

                # URL на Яндекс Картах
                org_url = meta.get("url", "")
                maps_url = f"https://yandex.ru/maps/org/{urllib.parse.quote(name)}"

                dedup = f"{name.lower()}|{phone}"
                if dedup in seen:
                    continue
                seen.add(dedup)

                lead = YandexLead(
                    city=city,
                    niche=niche,
                    name=name,
                    phone=phone,
                    website=website,
                    address=address,
                    url=maps_url,
                    rating=rating,
                    reviews_count=reviews,
                )
                lead = _score_and_enrich(lead)
                leads.append(lead)

                if len(leads) >= limit:
                    break

            total_found = data.get("properties", {}).get("ResponseMetaData", {}).get("SearchResponse", {}).get("found", 0)
            skip += page_size

            if skip >= min(total_found, limit * 2):
                break

            time.sleep(random.uniform(0.3, 0.7))

    leads.sort(key=lambda x: x.lead_score, reverse=True)
    return leads[:limit], note
