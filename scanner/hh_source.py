from __future__ import annotations
import json, time, random, urllib.request, urllib.parse, urllib.error
from dataclasses import dataclass, field
from typing import Any

@dataclass
class HHLead:
    source: str = "hh"
    city: str = ""
    niche: str = ""
    name: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    url: str = ""
    email: str = ""
    lead_score: int = 0
    opportunity_flags: list = field(default_factory=list)
    suggested_offer: str = ""
    first_message: str = ""

HEADERS = {
    "User-Agent": "AI-Opportunity-Scanner/1.0 (scanner@ivadi.dev)",
    "Accept": "application/json",
    "HH-User-Agent": "AI-Opportunity-Scanner/1.0 (scanner@ivadi.dev)",
}

# Ключевые слова: компании которые ищут аутсорс
OUTSOURCE_QUERIES = [
    "SMM менеджер", "контент менеджер", "дизайнер", "графический дизайнер",
    "копирайтер", "таргетолог", "маркетолог", "веб дизайнер",
    "контент маркетолог", "специалист по рекламе",
]

AREA_IDS = {
    "Москва": "1", "Санкт-Петербург": "2", "Новосибирск": "4",
    "Екатеринбург": "3", "Казань": "88", "Нижний Новгород": "66",
    "Челябинск": "104", "Самара": "78", "Уфа": "99", "Ростов-на-Дону": "76",
    "Краснодар": "53", "Омск": "68", "Красноярск": "54", "Воронеж": "26",
    "Пермь": "72", "Волгоград": "24", "Саратов": "79", "Тюмень": "89",
    "Краснодарский край": "1438", "Россия": "113",
}

def _score(lead: HHLead) -> HHLead:
    score = 50  # HH лиды изначально тёплые
    flags = ["source_hh", "outsource_signal"]
    if lead.website:
        score += 10; flags.append("website_present")
    else:
        score += 20; flags.append("no_website")
    if lead.name:
        score += 15; flags.append("company_known")
    lead.lead_score = min(score, 100)
    lead.opportunity_flags = flags
    return lead

def _build_offer(lead: HHLead, query: str) -> HHLead:
    company = lead.name or "ваша компания"
    city = lead.city
    if "дизайн" in query.lower() or "smm" in query.lower():
        lead.suggested_offer = "AI-контент пакет + дизайн за 3 дня вместо найма"
        lead.first_message = (
            f"Здравствуйте! Вижу что «{company}» ищет {query} — значит нужен контент и дизайн на постоянной основе. "
            f"Предлагаю альтернативу найму: AI-контент пакет — 30 постов + дизайн + Reels сценарии за 3 дня. "
            f"Дешевле сотрудника в 5–10 раз, результат быстрее. От 9 900 ₽. Показать примеры?"
        )
    else:
        lead.suggested_offer = "AI-маркетинг аутсорс вместо найма сотрудника"
        lead.first_message = (
            f"Здравствуйте! Вижу что «{company}» ищет {query}. "
            f"Есть альтернатива: AI-автоматизация маркетинга — контент, дизайн, тексты, рекламные материалы. "
            f"Результат за 48 часов, без найма и оклада. От 9 900 ₽/месяц. Актуально рассмотреть?"
        )
    return lead

def scan_hh(city: str, limit: int = 30) -> tuple[list[HHLead], str]:
    area_id = AREA_IDS.get(city, "113")
    leads: list[HHLead] = []
    seen: set[str] = set()
    note = ""

    for query in OUTSOURCE_QUERIES:
        if len(leads) >= limit:
            break
        params = {
            "text": query,
            "area": area_id,
            "per_page": "10",
            "page": "0",
            "only_with_salary": "false",
            "employment": "full,part",
        }
        url = "https://api.hh.ru/vacancies?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            for item in data.get("items", []):
                employer = item.get("employer") or {}
                name = (employer.get("name") or "").strip()
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                emp_url = employer.get("alternate_url", "")
                site = employer.get("site_url", "")
                lead = HHLead(
                    city=city, niche=query,
                    name=name,
                    website=site or "",
                    url=emp_url,
                    address=city,
                )
                lead = _score(lead)
                lead = _build_offer(lead, query)
                leads.append(lead)
                if len(leads) >= limit:
                    break
            time.sleep(random.uniform(0.3, 0.7))
        except Exception as ex:
            note = f"HH ошибка: {ex}"
            break

    return leads[:limit], note
