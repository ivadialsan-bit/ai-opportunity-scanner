from __future__ import annotations

import csv
import json
from pathlib import Path

from scanner.models import Lead


CSV_FIELDS = [
    "lead_score",
    "city",
    "niche",
    "name",
    "phone",
    "website",
    "email",
    "address",
    "lat",
    "lon",
    "source",
    "osm_type",
    "osm_id",
    "target_confidence",
    "opportunity_flags",
    "suggested_offer",
    "first_message",
    "tags_json",
]


def export_leads_csv(leads: list[Lead], output_path: str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for lead in leads:
            writer.writerow(
                {
                    "lead_score": lead.lead_score,
                    "city": lead.city,
                    "niche": lead.niche,
                    "name": lead.name,
                    "phone": lead.phone,
                    "website": lead.website,
                    "email": lead.email,
                    "address": lead.address,
                    "lat": lead.lat,
                    "lon": lead.lon,
                    "source": lead.source,
                    "osm_type": lead.osm_type,
                    "osm_id": lead.osm_id,
                    "target_confidence": next((f.replace("target_confidence_", "") for f in lead.opportunity_flags if f.startswith("target_confidence_")), ""),
                    "opportunity_flags": ";".join(lead.opportunity_flags),
                    "suggested_offer": lead.suggested_offer,
                    "first_message": lead.first_message,
                    "tags_json": json.dumps(lead.tags, ensure_ascii=False, sort_keys=True),
                }
            )

    return path
