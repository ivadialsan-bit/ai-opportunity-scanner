from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import requests


SEARCH_URL = "https://catalog.api.2gis.com/3.0/items"
BYID_URL = "https://catalog.api.2gis.com/3.0/items/byid"


def meta_code(data: dict[str, Any]) -> int:
    try:
        return int(data.get("meta", {}).get("code", 0))
    except Exception:
        return 0


def text(v: Any) -> str:
    return str(v or "").strip()


def rubrics_text(item: dict[str, Any]) -> str:
    parts = []
    for r in item.get("rubrics") or []:
        if isinstance(r, dict):
            parts.append(text(r.get("name")))
            parts.append(text(r.get("alias")))
    return " ".join(parts).lower()


def address_text(item: dict[str, Any]) -> str:
    for k in ("full_address_name", "address_name"):
        if text(item.get(k)):
            return text(item.get(k))

    addr = item.get("address") or {}
    if isinstance(addr, dict):
        for k in ("formatted_address_name", "full_address_name"):
            if text(addr.get(k)):
                return text(addr.get(k))

    return ""


def contacts(item: dict[str, Any]) -> tuple[str, str, str]:
    phones, emails, sites = [], [], []

    for group in item.get("contact_groups") or []:
        for c in group.get("contacts") or []:
            ctype = text(c.get("type") or c.get("name")).lower()

            for v in c.get("values") or []:
                if isinstance(v, dict):
                    value = text(v.get("value") or v.get("text") or v.get("url") or v.get("uri"))
                else:
                    value = text(v)

                if not value:
                    continue

                low = value.lower()

                if "phone" in ctype or "тел" in ctype:
                    phones.append(value)
                elif "email" in ctype or "mail" in ctype or "@" in value:
                    emails.append(value)
                elif "site" in ctype or "web" in ctype or value.startswith("http"):
                    sites.append(value)
                elif "." in low and " " not in low:
                    sites.append(value)

    return (
        "; ".join(sorted(set(phones))),
        "; ".join(sorted(set(emails))),
        "; ".join(sorted(set(sites))),
    )


def keywords(niche: str) -> list[str]:
    n = niche.lower()

    if any(x in n for x in ["кондиц", "сплит", "климат"]):
        return ["кондицион", "сплит", "климат", "холод", "вентиляц"]

    if "сант" in n:
        return ["сантех", "вод", "канализац", "трубы"]

    if "элект" in n:
        return ["элект", "проводк", "щит", "свет"]

    if "эваку" in n:
        return ["эвакуатор", "эвакуац", "автопомощ"]

    if "потол" in n:
        return ["потол", "натяж"]

    return [w for w in n.split() if len(w) >= 4]


def relevant(item: dict[str, Any], niche: str) -> bool:
    ks = keywords(niche)
    hay = " ".join([
        text(item.get("name")),
        rubrics_text(item),
        text(item.get("type")),
    ]).lower()

    return any(k in hay for k in ks) if ks else True


def score(phone: str, email: str, site: str, address: str) -> int:
    s = 30

    if phone:
        s += 30
    if email:
        s += 10
    if site:
        s += 15
    else:
        s += 30
    if address:
        s += 10
    if not (phone or email or site):
        s -= 20

    return max(s, 0)


def flags(phone: str, email: str, site: str, address: str) -> list[str]:
    out = ["source_2gis"]

    out.append("phone_present" if phone else "no_phone")
    out.append("website_present" if site else "no_website")

    if email:
        out.append("email_present")
    if address:
        out.append("address_present")

    if phone or email or site:
        out.append("target_confidence_high")
    else:
        out.append("target_confidence_medium")
        out.append("needs_manual_contact_check")

    return out


def first_message(name: str, niche: str, site: str) -> str:
    product = "AI Sales Patch для существующего сайта" if site else "Цифровая точка заявки за 48 часов"

    return (
        f"Здравствуйте. Нашёл вашу компанию «{name}» по направлению: {niche}.\n\n"
        "Не продаю рекламу и не обещаю рост заявок. "
        f"Делаю быстрый продукт: {product}: мини-страница/CTA, кнопки связи, FAQ, тексты услуг, "
        "скрипт звонка/переписки и таблица учёта обращений.\n\n"
        "Есть пример: http://5.129.200.18:8080/demo-48h/\n\n"
        "Мини-пилот от 5 900 ₽. Актуально показать, как это может выглядеть под вашу компанию?"
    )


def search_page(key: str, city: str, niche: str, page: int, page_size: int) -> list[dict[str, Any]]:
    params = {
        "q": f"{niche} {city}",
        "key": key,
        "page": page,
        "page_size": page_size,
        "locale": "ru_RU",
        "type": "branch",
        "fields": "items.address_name,items.full_address_name,items.rubrics",
    }

    r = requests.get(SEARCH_URL, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()

    if meta_code(data) != 200:
        raise RuntimeError(str(data.get("meta", {}).get("error", data))[:500])

    return (data.get("result") or {}).get("items") or []


def byid(key: str, item_id: str) -> dict[str, Any]:
    params = {
        "id": item_id,
        "key": key,
        "locale": "ru_RU",
        "fields": "items.address_name,items.full_address_name,items.address,items.rubrics,items.contact_groups",
    }

    r = requests.get(BYID_URL, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()

    if meta_code(data) != 200:
        return {}

    items = (data.get("result") or {}).get("items") or []
    return items[0] if items else {}


def scan_2gis(city: str, niche: str, limit: int = 30) -> tuple[list[Any], int, str]:
    key = os.getenv("DGIS_API_KEY", "").strip()

    if not key:
        raise RuntimeError("DGIS_API_KEY is empty")

    limit = max(1, min(int(limit or 30), 50))
    page_size = min(10, limit)
    pages = min(5, (limit * 2 + page_size - 1) // page_size)

    raw_items = []

    for page in range(1, pages + 1):
        raw_items.extend(search_page(key, city, niche, page, page_size))

    leads = []
    seen = set()

    for base in raw_items:
        item_id = text(base.get("id"))
        detail = byid(key, item_id) if item_id else {}
        item = {**base, **detail}

        if not relevant(item, niche):
            continue

        name = text(item.get("name"))
        if not name or name.lower() in seen:
            continue

        seen.add(name.lower())

        phone, email, site = contacts(item)
        address = address_text(item)

        lead = SimpleNamespace(
            city=city,
            niche=niche,
            name=name,
            phone=phone,
            email=email,
            website=site,
            address=address,
            source="2gis",
            osm_type="2gis_branch",
            osm_id=item_id,
            lead_score=score(phone, email, site, address),
            opportunity_flags=flags(phone, email, site, address),
            suggested_offer="AI Sales Patch / Цифровая точка заявки",
            first_message=first_message(name, niche, site),
        )

        leads.append(lead)

        if len(leads) >= limit:
            break

    note = ""
    if leads and all(not l.phone for l in leads):
        note = "Контакты из 2ГИС не пришли. Вероятно, у ключа нет доступа к items.contact_groups. Лиды добавлены для ручной проверки."

    if not leads and raw_items:
        note = "2ГИС нашёл организации, но фильтр релевантности отсёк выдачу. Попробуй более точную нишу."

    return leads, len(raw_items), note
