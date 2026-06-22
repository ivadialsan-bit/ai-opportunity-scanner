from __future__ import annotations

from scanner.models import Lead


def score_lead(lead: Lead) -> Lead:
    score = 0
    flags: list[str] = []

    if lead.name:
        score += 15
    else:
        flags.append("no_name")

    if lead.phone:
        score += 25
        flags.append("phone_present")
    else:
        flags.append("no_phone")

    if lead.website:
        score += 5
        flags.append("website_present")
    else:
        score += 25
        flags.append("no_website")

    if lead.email:
        score += 5
        flags.append("email_present")

    if lead.address:
        score += 10
        flags.append("address_present")

    if lead.lat is not None and lead.lon is not None:
        score += 5
        flags.append("geo_present")

    flags.append("source_osm_limited")

    if not lead.website and lead.phone:
        flags.append("high_manual_contact_priority")

    lead.lead_score = max(0, min(100, score))
    lead.opportunity_flags = flags
    return lead
