from __future__ import annotations

from scanner.models import Lead


BASE_OFFER = "Цифровая точка заявки за 48 часов"


def build_suggested_offer(lead: Lead) -> str:
    parts = [
        BASE_OFFER,
        "мини-страница заявки",
        "кнопки связи",
        "FAQ",
        "тексты услуг",
        "таблица учёта заявок",
    ]

    if "no_website" in lead.opportunity_flags:
        parts.insert(1, "нет сайта/посадочной страницы в открытых данных")
    if "no_phone" in lead.opportunity_flags:
        parts.append("проверка видимости контактов")

    return "; ".join(parts)


def build_first_message(lead: Lead) -> str:
    company = lead.name or "вашей компании"
    city = lead.city

    pain = "не нашёл удобную страницу заявки в открытых данных"
    if lead.website:
        pain = "вижу, что контакты есть, но можно отдельно усилить точку заявки и обработку обращений"
    if not lead.phone:
        pain = "не увидел быстрый телефон/точку связи в открытых данных"

    return (
        f"Здравствуйте. Нашёл {company} в {city} по теме кондиционеров/сплит-систем. "
        f"Коротко: {pain}. "
        f"Могу за 48 часов собрать простую цифровую точку заявки: мини-страницу, кнопки связи, FAQ, "
        f"тексты услуг, скрипт звонка/переписки и таблицу учёта заявок. "
        f"Без обещаний гарантированного роста — только быстрый порядок в приёме заявок. "
        f"Мини-пилот от 5 900 ₽. Актуально показать пример?"
    )


def enrich_offer(lead: Lead) -> Lead:
    lead.suggested_offer = build_suggested_offer(lead)
    lead.first_message = build_first_message(lead)
    return lead
