from __future__ import annotations

import csv
import os
import time
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any

from scanner.avito_source import scan_avito, AvitoLead, NICHE_QUERIES
from scanner.zoon_source import scan_zoon
from scanner.yandex_source import scan_yandex_maps


ALL_NICHES = list(NICHE_QUERIES.keys())


def _to_dict(lead: Any) -> dict:
    try:
        return asdict(lead)
    except Exception:
        return lead.__dict__


def run_multi_scan(
    city: str,
    niches: list[str],
    sources: list[str] = None,
    limit_per_source: int = 30,
    output_dir: str = "results",
) -> str:
    if sources is None:
        sources = ["avito", "zoon", "yandex"]

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_safe = city.replace(" ", "_").replace("-", "_").lower()
    niches_safe = "_".join(n[:8] for n in niches[:3])
    outpath = os.path.join(output_dir, f"{city_safe}_{niches_safe}_{ts}.csv")

    all_leads: list[dict] = []
    seen_names: set[str] = set()
    stats: dict[str, dict] = {}

    for niche in niches:
        print(f"\n{'='*50}")
        print(f"НИША: {niche} | ГОРОД: {city}")
        print(f"{'='*50}")

        for source in sources:
            print(f"\n  Источник: {source.upper()}...")
            t0 = time.time()

            try:
                if source == "avito":
                    leads, note = scan_avito(city, niche, limit=limit_per_source)
                elif source == "zoon":
                    leads, note = scan_zoon(city, niche, limit=limit_per_source)
                elif source == "yandex":
                    leads, note = scan_yandex_maps(city, niche, limit=limit_per_source)
                else:
                    print(f"  Неизвестный источник: {source}")
                    continue
            except Exception as ex:
                print(f"  ОШИБКА: {ex}")
                stats.setdefault(source, {}).setdefault(niche, {"found": 0, "note": str(ex)})
                continue

            elapsed = round(time.time() - t0, 1)
            unique = 0

            for lead in leads:
                d = _to_dict(lead)
                key = f"{d.get('name','').lower().strip()}|{d.get('phone','').strip()}"
                if key and key not in seen_names:
                    seen_names.add(key)
                    all_leads.append(d)
                    unique += 1

            stats.setdefault(source, {})[niche] = {
                "found": len(leads),
                "unique_added": unique,
                "time_sec": elapsed,
                "note": note,
            }
            print(f"  Найдено: {len(leads)} | Добавлено уникальных: {unique} | {elapsed}s")
            if note:
                print(f"  NOTE: {note}")

    if not all_leads:
        print("\nЛиды не найдены.")
        return ""

    all_leads.sort(key=lambda x: x.get("lead_score", 0), reverse=True)

    fieldnames = [
        "lead_score", "source", "city", "niche", "name",
        "phone", "website", "address", "url", "price",
        "rating", "reviews_count", "opportunity_flags",
        "suggested_offer", "first_message",
    ]

    with open(outpath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for lead in all_leads:
            if isinstance(lead.get("opportunity_flags"), list):
                lead["opportunity_flags"] = "|".join(lead["opportunity_flags"])
            writer.writerow({k: lead.get(k, "") for k in fieldnames})

    print(f"\n{'='*50}")
    print(f"ИТОГ: {len(all_leads)} уникальных лидов → {outpath}")
    print(f"{'='*50}")
    for src, niches_stat in stats.items():
        for niche, s in niches_stat.items():
            print(f"  {src}/{niche}: найдено={s['found']}, добавлено={s.get('unique_added',0)}, {s['time_sec']}s")
            if s.get("note"):
                print(f"    NOTE: {s['note']}")

    return outpath
