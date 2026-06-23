from __future__ import annotations

import json
import re
import time
import random
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field


@dataclass
class YandexLead:
    source: str = "yandex_maps"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    url: str = ""
    rating: str = ""
    reviews_count: str = ""
    work_hours: str = ""
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""


HEADERS_YANDEX = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "application/json,text/javascript,*/*;q=0.01",
    "Referer": "https://yandex.ru/maps/",
    "X-Requested-With": "XMLHttpRequest",
}


def _build_yandex_search_url(city: str, niche: str, page: int = 0) -> str:
    query = f"{niche} {city}"
    params = {
        "text": query,
        "type": "biz",
        "lang": "ru_RU",
        "results": "20",
        "skip": str(page * 20),
        "origin": "maps-search-form",
    }
    return "https://yandex.ru/maps/api/search?" + urllib.parse.urlencode(params)


def _parse_yandex_response(data: dict, city: str, niche: str) -> list[YandexLead]:
    leads = []
    features = data.get("features") or []
    if not features:
        features = data.get("data", {}).get("features") or []

    for feature in features:
        props = feature.get("properties", {})
        lead = YandexLead(city=city, niche=niche)

        lead.name = props.get("name", "") or props.get("CompanyMetaData", {}).get("name", "")

        meta = props.get("CompanyMetaData", {})
        lead.address = meta.get("address", "") or props.get("description", "")
        lead.url = meta.get("url", "")
        lead.website = meta.get("url", "")

        phones = meta.get("Phones", [])
        if phones:
            lead.phone = phones[0].get("formatted", "") if isinstance(phones[0], dict) else str(phones[0])

        rating_data = meta.get("rating", {})
        if isinstance(rating_data, dict):
            lead.rating = str(rating_data.get("ratings", "") or rating_data.get("score", ""))
            lead.reviews_count = str(rating_data.get("reviews", ""))

        hours = meta.get("Hours", {})
        if hours:
            lead.work_hours = hours.get("text", "")

        if not lead.name:
            continue

        score = 20
        flags = ["source_yandex_maps"]
        if lead.phone:
            score += 30; flags.append("phone_present")
        else:
            flags.append("no_phone")
        if not lead.website:
            score += 25; flags.append("no_website")
        else:
            flags.append("website_present")
        if lead.address:
            score += 10; flags.append("address_present")
        try:
            r = float(lead.rating or 0)
            if 0 < r < 4.0:
                flags.append("low_rating_opportunity")
        except Exception:
            pass
        if not lead.work_hours:
            flags.append("no_schedule_online")

        lead.lead_score = min(score, 100)
        lead.opportunity_flags = flags

        if not lead.website:
            lead.suggested_offer = "Лендинг + онлайн-запись за 48ч"
            lead.first_message = (
                f"Здравствуйте! Нашёл «{lead.name}» на Яндекс Картах в {city}. "
                f"Вижу нет сайта — клиенты не могут оставить заявку онлайн. "
                f"Сделаю мини-страницу с формой записи и уведомлением вам в Telegram за 48 часов. "
                f"Мини-пилот от 4 900 ₽. Показать пример?"
            )
        else:
            lead.suggested_offer = "AI-контент + бот для записи"
            lead.first_message = (
                f"Здравствуйте! Нашёл вас на Яндекс Картах, ниша — {niche}. "
                f"Могу добавить онлайн-запись и настроить AI-контент для соцсетей. "
                f"48 часов, от 6 900 ₽. Актуально?"
            )

        leads.append(lead)

    return leads


def scan_yandex_maps(city: str, niche: str, limit: int = 30, pages: int = 2) -> tuple[list[YandexLead], str]:
    leads: list[YandexLead] = []
    seen: set[str] = set()
    note = ""

    for page in range(pages):
        url = _build_yandex_search_url(city, niche, page)
        try:
            req = urllib.request.Request(url, headers=HEADERS_YANDEX)
            with urllib.request.urlopen(req, timeout=12) as r:
                raw = r.read().decode("utf-8", errors="ignore")

            try:
                data = json.loads(raw)
            except Exception:
                m = re.search(r'\{.*"features".*\}', raw, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                else:
                    note = f"Яндекс: не удалось разобрать JSON на странице {page+1}"
                    break

            page_leads = _parse_yandex_response(data, city, niche)

            for lead in page_leads:
                key = lead.name.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    leads.append(lead)
                if len(leads) >= limit:
                    break

            if len(leads) >= limit:
                break

            time.sleep(random.uniform(2.0, 3.5))

        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                note = f"Яндекс: блок запросов (HTTP {e.code}). Нужны задержки или прокси."
            else:
                note = f"Яндекс HTTP {e.code}"
            break
        except Exception as ex:
            note = f"Яндекс ошибка: {ex}"
            break

    leads.sort(key=lambda x: x.lead_score, reverse=True)
    return leads[:limit], note
