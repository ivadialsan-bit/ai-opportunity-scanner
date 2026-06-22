from __future__ import annotations

import re
from scanner.models import Lead


CHAIN_TOKENS = [
    "м.видео",
    "mvideo",
    "мвидео",
    "эльдорадо",
    "eldorado",
    "samsung",
    "dns",
    "днс",
    "citilink",
    "ситилинк",
    "леруа",
    "leroy",
    "ozon",
    "wildberries",
    "яндекс маркет",
]


GENERIC_BAD_NAMES = [
    "сплит-системы",
    "кондиционеры",
    "электроника",
    "бытовая техника",
]


TARGET_STRONG_PATTERNS = [
    r"кондиц",
    r"сплит",
    r"split",
    r"климат",
    r"climat",
    r"hvac",
    r"вентиляц",
    r"air.?condition",
    r"охлажден",
    r"холод",
]


WEAK_LOCAL_CATEGORIES = [
    "appliance",
    "electronics",
    "trade",
]


def _norm(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


def _combined_text(lead: Lead) -> str:
    tags_text = " ".join([str(k) + " " + str(v) for k, v in lead.tags.items()])
    return _norm(" ".join([
        lead.name or "",
        lead.website or "",
        lead.address or "",
        tags_text,
    ]))


def has_contact(lead: Lead) -> bool:
    return bool(lead.phone or lead.website or lead.email)


def is_chain_lead(lead: Lead) -> bool:
    text = _combined_text(lead)
    return any(token in text for token in CHAIN_TOKENS)


def is_generic_bad_name(lead: Lead) -> bool:
    name = _norm(lead.name or "")
    return name in GENERIC_BAD_NAMES


def target_confidence(lead: Lead) -> str:
    text = _combined_text(lead)

    for pattern in TARGET_STRONG_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return "high"

    shop = _norm(str(lead.tags.get("shop", "")))
    craft = _norm(str(lead.tags.get("craft", "")))
    service = _norm(str(lead.tags.get("service", "")))

    if (
        has_contact(lead)
        and not is_chain_lead(lead)
        and (
            shop in WEAK_LOCAL_CATEGORIES
            or craft
            or service
        )
    ):
        return "medium"

    return "low"


def dedupe_leads(leads: list[Lead]) -> list[Lead]:
    result: list[Lead] = []
    seen: set[str] = set()

    for lead in leads:
        key = "|".join([
            _norm(lead.name or ""),
            _norm(lead.phone or ""),
            _norm(lead.website or ""),
            str(round(lead.lat or 0, 5)),
            str(round(lead.lon or 0, 5)),
        ])

        if key in seen:
            continue

        seen.add(key)
        result.append(lead)

    return result


def apply_sales_filters(
    leads: list[Lead],
    exclude_chains: bool = True,
    min_confidence: str = "medium",
    require_contact: bool = True,
) -> list[Lead]:
    order = {"low": 1, "medium": 2, "high": 3}
    min_value = order.get(min_confidence, 2)

    result: list[Lead] = []

    for lead in dedupe_leads(leads):
        confidence = target_confidence(lead)
        lead.opportunity_flags.append(f"target_confidence_{confidence}")

        if is_generic_bad_name(lead):
            lead.opportunity_flags.append("excluded_generic_bad_name")
            continue

        if is_chain_lead(lead):
            lead.opportunity_flags.append("excluded_chain_candidate")
            if exclude_chains:
                continue

        if require_contact and not has_contact(lead):
            lead.opportunity_flags.append("excluded_no_contact")
            continue

        if order.get(confidence, 1) < min_value:
            lead.opportunity_flags.append("excluded_low_target_confidence")
            continue

        result.append(lead)

    return result
