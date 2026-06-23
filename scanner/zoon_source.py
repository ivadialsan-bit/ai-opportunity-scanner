from __future__ import annotations

import re
import time
import random
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field


@dataclass
class ZoonLead:
    source: str = "zoon"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    url: str = ""
    rating: str = ""
    reviews: str = ""
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Referer": "https://zoon.ru/",
}

ZOON_CITY_SLUGS: dict[str, str] = {
    "москва": "msk",
    "санкт-петербург": "spb",
    "питер": "spb",
    "краснодар": "krd",
    "екатеринбург": "ekb",
    "новосибирск": "nsk",
    "казань": "kzn",
    "ростов-на-дону": "rnd",
    "нижний новгород": "nnov",
    "самара": "smr",
    "уфа": "ufa",
    "волгоград": "vlg",
    "пермь": "prm",
    "красноярск": "krsk",
    "воронеж": "vrn",
    "саратов": "sar",
    "тюмень": "tmn",
    "иркутск": "irk",
    "хабаровск": "khv",
    "ярославль": "yar",
    "владивосток": "vld",
}

ZOON_NICHE_SLUGS: dict[str, str] = {
    "сантехника": "remont/santehniki",
    "электрика": "remont/elektrika",
    "ремонт": "remont/kvartir",
    "клининг": "cleaning",
    "красота": "beauty/nogti",
    "автосервис": "auto/avtoservis",
    "фитнес": "sport/fitness",
    "бухгалтерия": "business/buhgalteriya",
    "грузоперевозки": "transport/gruzoperevozki",
    "фотограф": "foto",
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


def _parse_zoon_html(html: str, city: str, niche: str) -> list[ZoonLead]:
    leads: list[ZoonLead] = []

    blocks = re.findall(
        r'<article[^>]*class="[^"]*minicard-item[^"]*"[^>]*>(.*?)</article>',
        html, re.DOTALL
    )
    if not blocks:
        blocks = re.findall(
            r'<div[^>]*class="[^"]*minicard[^"]*"[^>]*>(.*?)</div>\s*</div>',
            html, re.DOTALL
        )

    for block in blocks:
        lead = ZoonLead(city=city, niche=niche)

        name_m = re.search(r'class="[^"]*name[^"]*"[^>]*>([^<]{3,80})<', block)
        if name_m:
            lead.name = name_m.group(1).strip()

        url_m = re.search(r'href="(https://zoon\.ru/[^"]+)"', block)
        if url_m:
            lead.url = url_m.group(1)

        phone_m = re.search(r'(?:tel:|\+7|8)[\s\-\(]?(\d[\d\s\-\(\)]{6,14}\d)', block)
        if phone_m:
            lead.phone = phone_m.group(0).replace("tel:", "").strip()

        addr_m = re.search(r'class="[^"]*address[^"]*"[^>]*>([^<]{5,100})<', block)
        if addr_m:
            lead.address = addr_m.group(1).strip()

        rating_m = re.search(r'class="[^"]*rating[^"]*"[^>]*>([\d.,]+)<', block)
        if rating_m:
            lead.rating = rating_m.group(1)

        web_m = re.search(r'href="(https?://(?!zoon\.ru)[^"]+)"', block)
        if web_m:
            lead.website = web_m.group(1)

        if not lead.name:
            continue

        score = 20
        flags = ["source_zoon"]
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
        if lead.rating and float(lead.rating.replace(",", ".") or 0) < 4.0:
            flags.append("low_rating_opportunity")

        lead.lead_score = min(score, 100)
        lead.opportunity_flags = flags

        if not lead.website:
            lead.suggested_offer = "Лендинг + форма заявки за 48ч"
            lead.first_message = (
                f"Здравствуйте! Нашёл «{lead.name}» на Zoon.ru в {city}. "
                f"Вижу нет отдельного сайта — клиенты уходят к конкурентам у кого есть. "
                f"Сделаю страницу с онлайн-заявкой и уведомлением вам в Telegram за 48 часов. "
                f"От 4 900 ₽. Актуально?"
            )
        else:
            lead.suggested_offer = "AI-контент + онлайн-запись"
            lead.first_message = (
                f"Здравствуйте! Видел вас на Zoon.ru, ниша — {niche}. "
                f"Могу усилить: добавить онлайн-запись и AI-контент для соцсетей. "
                f"От 6 900 ₽. Показать пример?"
            )

        leads.append(lead)

    return leads


def scan_zoon(city: str, niche: str, limit: int = 30, pages: int = 3) -> tuple[list[ZoonLead], str]:
    city_key = city.strip().lower()
    city_slug = ZOON_CITY_SLUGS.get(city_key)
    niche_slug = ZOON_NICHE_SLUGS.get(niche.strip().lower())

    if not city_slug:
        return [], f"Город '{city}' не поддержан в Zoon. Добавь в ZOON_CITY_SLUGS."
    if not niche_slug:
        niche_encoded = urllib.parse.quote(niche)
        base_url = f"https://zoon.ru/{city_slug}/?search={niche_encoded}"
    else:
        base_url = f"https://zoon.ru/{city_slug}/{niche_slug}/"

    leads: list[ZoonLead] = []
    seen: set[str] = set()
    note = ""

    for page in range(1, pages + 1):
        url = base_url if page == 1 else f"{base_url}?page={page}"
        try:
            html = _get(url)
            page_leads = _parse_zoon_html(html, city, niche)

            for lead in page_leads:
                key = lead.name.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    leads.append(lead)
                if len(leads) >= limit:
                    break

            if len(leads) >= limit:
                break

            time.sleep(random.uniform(1.5, 3.0))

        except urllib.error.HTTPError as e:
            note = f"Zoon HTTP {e.code} на странице {page}"
            break
        except Exception as ex:
            note = f"Zoon ошибка: {ex}"
            break

    leads.sort(key=lambda x: x.lead_score, reverse=True)
    return leads[:limit], note
