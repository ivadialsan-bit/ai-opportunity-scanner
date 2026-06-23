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
class DGisLead:
    source: str = "2gis"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    whatsapp: str = ""
    website: str = ""
    email: str = ""
    vk: str = ""
    address: str = ""
    url: str = ""
    rating: str = ""
    reviews_count: str = ""
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

DGIS_NICHES: dict[str, list[str]] = {
    "сантехника":     ["сантехник", "сантехника", "водопровод"],
    "электрика":      ["электрик", "электрика", "проводка"],
    "ремонт":         ["ремонт квартир", "отделка", "строительство"],
    "клининг":        ["уборка", "клининг", "химчистка"],
    "красота":        ["маникюр", "салон красоты", "косметолог"],
    "автосервис":     ["автосервис", "шиномонтаж", "СТО"],
    "фитнес":         ["фитнес", "тренажерный зал", "персональный тренер"],
    "грузоперевозки": ["грузоперевозки", "грузчики", "переезд"],
    "фотограф":       ["фотограф", "фотостудия", "видеосъемка"],
    "бухгалтерия":    ["бухгалтер", "бухгалтерия", "бухгалтерские услуги"],
    "кондиционеры":   ["кондиционер", "кондиционеры", "климат"],
    "натяжные потолки": ["натяжные потолки", "потолки"],
    "двери":          ["установка дверей", "двери"],
    "окна":           ["пластиковые окна", "окна пвх"],
    "юрист":          ["юрист", "адвокат", "юридические услуги"],
    "медицина":       ["стоматология", "клиника", "медицинский центр"],
    "ветеринар":      ["ветеринар", "ветклиника", "зоо"],
    "кафе":           ["кафе", "ресторан", "доставка еды"],
    "туризм":         ["турагентство", "туры", "путевки"],
    "детский":        ["детский сад", "репетитор", "развивающий центр"],
}


def _extract_contacts(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    phone = whatsapp = website = email = vk = ""
    for group in item.get("contact_groups") or []:
        for c in group.get("contacts") or []:
            ctype = c.get("type", "")
            value = c.get("value", "") or c.get("text", "")
            if not value:
                continue
            if ctype == "phone" and not phone:
                phone = c.get("value", "").strip()
            elif ctype == "whatsapp" and not whatsapp:
                # извлекаем номер из wa.me ссылки
                wa = value.replace("https://wa.me/", "").split("?")[0]
                whatsapp = "+" + wa if wa.startswith("7") else wa
            elif ctype == "website" and not website:
                real = c.get("value", "")
                if "link.2gis.ru" in real:
                    # реальный URL в конце редиректа
                    parts = real.split("?")
                    website = parts[-1] if parts else real
                else:
                    website = real
            elif ctype == "email" and not email:
                email = value
            elif ctype == "vkontakte" and not vk:
                vk = value
    return phone, whatsapp, website, email, vk


def _score_and_enrich(lead: DGisLead) -> DGisLead:
    score = 20
    flags = ["source_2gis"]

    if lead.phone:
        score += 30
        flags.append("phone_present")
    else:
        flags.append("no_phone")

    if lead.whatsapp:
        score += 10
        flags.append("whatsapp_present")

    if not lead.website:
        score += 25
        flags.append("no_website")
    else:
        flags.append("website_present")

    if lead.email:
        score += 5
        flags.append("email_present")

    if lead.address:
        score += 5
        flags.append("address_present")

    if not lead.vk:
        flags.append("no_vk")
    else:
        flags.append("vk_present")

    # горячий лид: есть телефон но нет сайта
    if lead.phone and not lead.website:
        flags.append("hot_target")
        score += 5

    try:
        r = float(lead.rating or 0)
        if 0 < r < 4.0:
            flags.append("low_rating_opportunity")
    except Exception:
        pass

    lead.lead_score = min(score, 100)
    lead.opportunity_flags = flags

    # оффер и сообщение
    contact_channel = f"WhatsApp {lead.whatsapp}" if lead.whatsapp else f"телефон {lead.phone}"

    if not lead.website:
        lead.suggested_offer = "Лендинг + онлайн-заявка + Telegram-уведомление за 48ч"
        lead.first_message = (
            f"Здравствуйте! Нашёл «{lead.name}» в {lead.city} через 2ГИС. "
            f"Вижу нет сайта — клиенты не могут оставить заявку онлайн, теряете обращения. "
            f"Сделаю мини-страницу с формой заявки и мгновенным уведомлением вам в Telegram за 48 часов. "
            f"Мини-пилот от 4 900 ₽. Показать пример под вашу нишу?"
        )
    elif not lead.vk:
        lead.suggested_offer = "AI-контент для соцсетей (VK/TG) — 30 постов"
        lead.first_message = (
            f"Здравствуйте! Нашёл «{lead.name}» в {lead.city}. "
            f"Сайт есть, но соцсети не видно — клиенты проверяют отзывы и активность перед заказом. "
            f"Сделаю 30 постов с AI-картинками для VK или Telegram за 3 дня. "
            f"От 5 900 ₽. Актуально?"
        )
    else:
        lead.suggested_offer = "AI-автоматизация контента + бот для онлайн-записи"
        lead.first_message = (
            f"Здравствуйте! Изучил «{lead.name}» в {lead.city}. "
            f"Вижу и сайт и соцсети — хорошая база. "
            f"Могу добавить онлайн-запись через Telegram-бот и автоматический контент. "
            f"Клиенты записываются сами, вы получаете уведомления. От 9 900 ₽."
        )

    return lead


def _fetch_page(query: str, key: str, page: int, page_size: int) -> list[dict]:
    q = urllib.parse.quote(query)
    url = (
        f"https://catalog.api.2gis.com/3.0/items"
        f"?q={q}&key={key}&type=branch&page={page}&page_size={page_size}"
        f"&fields=items.address_name,items.rubrics,items.contact_groups,items.reviews,items.rating"
        f"&locale=ru_RU"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))

    meta_code = data.get("meta", {}).get("code", 0)
    if meta_code != 200:
        raise RuntimeError(f"2GIS API error: {data.get('meta', {}).get('error', data)}")

    return data.get("result", {}).get("items") or []


def scan_2gis(
    city: str,
    niche: str,
    limit: int = 50,
    key: str = "demo",
) -> tuple[list[DGisLead], str]:

    niche_key = niche.strip().lower()
    queries = DGIS_NICHES.get(niche_key, [niche.strip()])

    leads: list[DGisLead] = []
    seen: set[str] = set()
    note = ""

    for query in queries:
        if len(leads) >= limit:
            break

        full_query = f"{query} {city}"
        page = 1
        page_size = min(20, limit)

        while len(leads) < limit:
            try:
                items = _fetch_page(full_query, key, page, page_size)
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    note = "2GIS demo key: нет доступа к contact_groups. Нужен платный ключ для телефонов."
                else:
                    note = f"2GIS HTTP {e.code}"
                break
            except Exception as ex:
                note = f"2GIS ошибка: {ex}"
                break

            if not items:
                break

            for item in items:
                name = (item.get("name") or "").strip()
                if not name:
                    continue

                phone, whatsapp, website, email, vk = _extract_contacts(item)

                # дедупликация по имени + телефону
                dedup_key = f"{name.lower()}|{phone}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                lead = DGisLead(
                    city=city,
                    niche=niche,
                    name=name,
                    phone=phone,
                    whatsapp=whatsapp,
                    website=website,
                    email=email,
                    vk=vk,
                    address=item.get("address_name", ""),
                    url=f"https://2gis.ru/search/{urllib.parse.quote(name)}",
                    rating=str(item.get("reviews", {}).get("rating", "") or ""),
                    reviews_count=str(item.get("reviews", {}).get("count", "") or ""),
                )
                lead = _score_and_enrich(lead)
                leads.append(lead)

                if len(leads) >= limit:
                    break

            if len(items) < page_size:
                break

            page += 1
            time.sleep(random.uniform(0.5, 1.2))

    leads.sort(key=lambda x: x.lead_score, reverse=True)
    return leads[:limit], note
