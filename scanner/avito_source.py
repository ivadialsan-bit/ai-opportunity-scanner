from __future__ import annotations

import json
import re
import time
import random
import urllib.parse
import urllib.request
import urllib.error
from typing import Any
from dataclasses import dataclass, field


@dataclass
class AvitoLead:
    source: str = "avito"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    url: str = ""
    price: str = ""
    description: str = ""
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""


NICHE_QUERIES: dict[str, list[str]] = {
    "сантехника": ["сантехник", "сантехника", "водопровод", "канализация", "унитаз", "труба"],
    "электрика": ["электрик", "электрика", "проводка", "щиток", "розетки"],
    "ремонт": ["ремонт квартир", "отделка", "штукатурка", "поклейка обоев", "плитка"],
    "клининг": ["уборка квартир", "клининг", "уборка офиса", "мытьё окон"],
    "грузоперевозки": ["грузоперевозки", "грузчики", "переезд", "газель"],
    "красота": ["маникюр", "брови", "ресницы", "косметолог", "визажист"],
    "автосервис": ["автосервис", "шиномонтаж", "ремонт авто", "покраска авто"],
    "фитнес": ["персональный тренер", "фитнес тренер", "йога", "пилатес"],
    "фотограф": ["фотограф", "фотосессия", "видеограф", "видеосъёмка"],
    "бухгалтерия": ["бухгалтер", "бухгалтерия", "налоги", "1С"],
}

CITY_SLUGS: dict[str, str] = {
    "москва": "moskva",
    "санкт-петербург": "sankt-peterburg",
    "питер": "sankt-peterburg",
    "краснодар": "krasnodar",
    "екатеринбург": "ekaterinburg",
    "новосибирск": "novosibirsk",
    "казань": "kazan",
    "ростов-на-дону": "rostov-na-donu",
    "нижний новгород": "nizhniy_novgorod",
    "челябинск": "chelyabinsk",
    "самара": "samara",
    "уфа": "ufa",
    "волгоград": "volgograd",
    "пермь": "perm",
    "красноярск": "krasnoyarsk",
    "воронеж": "voronezh",
    "саратов": "saratov",
    "тюмень": "tyumen",
    "тольятти": "tolyatti",
    "ижевск": "izhevsk",
    "барнаул": "barnaul",
    "ульяновск": "ulyanovsk",
    "иркутск": "irkutsk",
    "хабаровск": "khabarovsk",
    "ярославль": "yaroslavl",
    "владивосток": "vladivostok",
    "махачкала": "makhachkala",
    "томск": "tomsk",
    "оренбург": "orenburg",
    "кемерово": "kemerovo",
    "россия": "rossiya",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.avito.ru/",
    "Cache-Control": "no-cache",
}


def _get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        try:
            import gzip
            return gzip.decompress(raw).decode("utf-8", errors="ignore")
        except Exception:
            return raw.decode("utf-8", errors="ignore")


def _extract_next_data(html: str) -> dict[str, Any] | None:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _extract_initial_data(html: str) -> dict[str, Any] | None:
    for pattern in [
        r'window\.__initialData__\s*=\s*({.*?});\s*</script>',
        r'window\.__listing_state__\s*=\s*({.*?});\s*</script>',
        r'"items"\s*:\s*(\[.*?\])',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return None


def _score(lead: AvitoLead) -> AvitoLead:
    score = 20
    flags = ["source_avito"]

    if lead.phone:
        score += 30
        flags.append("phone_present")
    else:
        score += 15
        flags.append("no_phone")

    if not lead.website:
        score += 25
        flags.append("no_website")
    else:
        flags.append("website_present")

    if lead.address:
        score += 10
        flags.append("address_present")

    if lead.price:
        score += 5
        flags.append("price_known")

    if not lead.website and lead.phone:
        flags.append("hot_target")

    lead.lead_score = min(score, 100)
    lead.opportunity_flags = flags
    return lead


def _build_offer(lead: AvitoLead) -> AvitoLead:
    niche_label = lead.niche or "вашей сфере"

    if not lead.website:
        lead.suggested_offer = f"Лендинг + форма заявки + Telegram-уведомление — нет сайта"
        lead.first_message = (
            f"Здравствуйте! Нашёл вас на Авито по теме «{niche_label}» в {lead.city}. "
            f"Вижу, нет отдельной страницы для онлайн-заявок — клиенты теряются. "
            f"Могу сделать простую страницу с формой заявки и уведомлением вам в Telegram за 48 часов. "
            f"Пилот от 4 900 ₽. Показать пример?"
        )
    else:
        lead.suggested_offer = f"AI Sales Patch — усилить существующий сайт"
        lead.first_message = (
            f"Здравствуйте! Нашёл вас на Авито по теме «{niche_label}». "
            f"Вижу сайт есть, но можно усилить: добавить онлайн-запись, "
            f"AI-чат для ответов на вопросы и автоматические напоминания клиентам. "
            f"Всё за 48 часов. От 7 900 ₽. Актуально?"
        )
    return lead


def _parse_items_from_html(html: str, city: str, niche: str) -> list[AvitoLead]:
    leads: list[AvitoLead] = []

    data = _extract_next_data(html)
    if data:
        try:
            items = (
                data.get("props", {})
                .get("initialState", {})
                .get("items", {})
                .get("items", [])
            )
            if not items:
                catalog = data.get("props", {}).get("initialState", {}).get("catalog", {})
                items = catalog.get("items", [])

            for item in items:
                lead = AvitoLead(city=city, niche=niche)
                lead.name = item.get("title", "") or item.get("name", "")
                lead.url = "https://www.avito.ru" + (item.get("urlPath", "") or item.get("url", ""))
                lead.price = str(item.get("priceDetailed", {}).get("string", "") or item.get("price", ""))
                lead.address = (
                    item.get("geo", {}).get("formattedAddress", "")
                    or item.get("location", {}).get("name", "")
                )

                phones = item.get("contacts", {}).get("phone", [])
                if phones:
                    lead.phone = phones[0] if isinstance(phones, list) else str(phones)

                lead = _score(lead)
                lead = _build_offer(lead)
                if lead.name:
                    leads.append(lead)
        except Exception:
            pass

    if not leads:
        titles = re.findall(r'"title"\s*:\s*"([^"]{5,80})"', html)
        urls = re.findall(r'"urlPath"\s*:\s*"(/[^"]+)"', html)
        prices = re.findall(r'"string"\s*:\s*"([^"]*(?:₽|руб)[^"]*)"', html)

        for i, title in enumerate(titles[:30]):
            lead = AvitoLead(city=city, niche=niche)
            lead.name = title
            lead.url = "https://www.avito.ru" + urls[i] if i < len(urls) else ""
            lead.price = prices[i] if i < len(prices) else ""
            lead = _score(lead)
            lead = _build_offer(lead)
            leads.append(lead)

    return leads


def scan_avito(city: str, niche: str, limit: int = 30, pages: int = 3) -> tuple[list[AvitoLead], str]:
    city_key = city.strip().lower()
    city_slug = CITY_SLUGS.get(city_key, city_key.replace(" ", "_").replace("-", "_"))

    query_variants = NICHE_QUERIES.get(niche.strip().lower(), [niche.strip()])
    query = query_variants[0]

    encoded_query = urllib.parse.quote(query)
    leads: list[AvitoLead] = []
    seen_names: set[str] = set()
    note = ""

    for page in range(1, pages + 1):
        url = (
            f"https://www.avito.ru/{city_slug}/predlozheniya_uslug"
            f"?q={encoded_query}&p={page}"
        )
        try:
            html = _get(url)
            page_leads = _parse_items_from_html(html, city, niche)

            for lead in page_leads:
                key = lead.name.lower().strip()
                if key and key not in seen_names:
                    seen_names.add(key)
                    leads.append(lead)
                    if len(leads) >= limit:
                        break

            if len(leads) >= limit:
                break

            sleep_time = random.uniform(2.0, 4.0)
            time.sleep(sleep_time)

        except urllib.error.HTTPError as e:
            if e.code == 429:
                note = f"Авито: rate limit на странице {page}. Добавь задержку или смени IP."
                break
            elif e.code == 403:
                note = f"Авито: блок по IP/UA на странице {page}. Нужен прокси или смена User-Agent."
                break
            else:
                note = f"Авито HTTP {e.code} на странице {page}"
                break
        except Exception as ex:
            note = f"Авито ошибка: {ex}"
            break

    leads.sort(key=lambda x: x.lead_score, reverse=True)
    return leads[:limit], note
