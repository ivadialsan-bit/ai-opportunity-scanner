from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from typing import Any


def _to_dict(lead: Any) -> dict:
    try:
        from dataclasses import asdict
        return asdict(lead)
    except Exception:
        return lead.__dict__


ALL_NICHES = [
    "сантехника", "электрика", "ремонт", "клининг", "красота",
    "автосервис", "фитнес", "грузоперевозки", "фотограф", "бухгалтерия",
    "кондиционеры", "натяжные потолки", "двери", "окна", "юрист",
    "медицина", "ветеринар", "кафе", "туризм", "детский",
]

FIELDNAMES = [
    "lead_score", "source", "city", "niche", "name",
    "phone", "whatsapp", "website", "email", "vk",
    "address", "url", "rating", "reviews_count",
    "opportunity_flags", "suggested_offer", "first_message",
]


def run_multi_scan(
    city: str,
    niches: list[str],
    sources: list[str] = None,
    limit_per_source: int = 50,
    output_dir: str = "results",
    dgis_key: str = "demo",
) -> str:
    if sources is None:
        sources = ["2gis"]

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_safe = city.replace(" ", "_").replace("-", "_").lower()[:12]
    niches_safe = "_".join(n[:8] for n in niches[:3])
    outpath = os.path.join(output_dir, f"{city_safe}_{niches_safe}_{ts}.csv")

    all_leads: list[dict] = []
    seen_keys: set[str] = set()
    stats: list[str] = []

    for niche in niches:
        print(f"\n{'='*50}")
        print(f"НИША: {niche} | ГОРОД: {city}")
        print(f"{'='*50}")

        for source in sources:
            print(f"\n  [{source.upper()}] сканирую...")
            t0 = time.time()

            try:
                if source == "2gis":
                    from scanner.dgis_source import scan_2gis
                    leads_raw, note = scan_2gis(city, niche, limit=limit_per_source, key=dgis_key)
                elif source == "avito":
                    from scanner.avito_source import scan_avito
                    leads_raw, note = scan_avito(city, niche, limit=limit_per_source)
                elif source == "zoon":
                    from scanner.zoon_source import scan_zoon
                    leads_raw, note = scan_zoon(city, niche, limit=limit_per_source)
                else:
                    print(f"  Неизвестный источник: {source}")
                    continue
            except Exception as ex:
                print(f"  ОШИБКА: {ex}")
                stats.append(f"{source}/{niche}: ERROR {ex}")
                continue

            elapsed = round(time.time() - t0, 1)
            added = 0

            for lead in leads_raw:
                d = _to_dict(lead)
                key = f"{d.get('name','').lower().strip()}|{d.get('phone','').strip()}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    if isinstance(d.get("opportunity_flags"), list):
                        d["opportunity_flags"] = "|".join(d["opportunity_flags"])
                    all_leads.append(d)
                    added += 1

            msg = f"{source}/{niche}: найдено={len(leads_raw)}, добавлено={added}, {elapsed}s"
            if note:
                msg += f" | {note}"
            stats.append(msg)
            print(f"  Найдено: {len(leads_raw)} | Уникальных: {added} | {elapsed}s")
            if note:
                print(f"  NOTE: {note}")

    if not all_leads:
        print("\nЛиды не найдены.")
        return ""

    # сортировка: горячие (hot_target) наверх, потом по score
    all_leads.sort(
        key=lambda x: (
            "hot_target" in str(x.get("opportunity_flags", "")),
            x.get("lead_score", 0)
        ),
        reverse=True
    )

    with open(outpath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for lead in all_leads:
            writer.writerow({k: lead.get(k, "") for k in FIELDNAMES})

    print(f"\n{'='*50}")
    print(f"ИТОГ: {len(all_leads)} уникальных лидов")
    print(f"CSV: {outpath}")
    print(f"{'='*50}")
    for s in stats:
        print(f"  {s}")

    # топ-5 горячих
    hot = [l for l in all_leads if "hot_target" in str(l.get("opportunity_flags",""))]
    if hot:
        print(f"\nТОП ГОРЯЧИХ ({len(hot)} лидов):")
        for l in hot[:5]:
            print(f"  {l.get('lead_score')} | {l.get('name')} | {l.get('phone')} | {l.get('address','')[:40]}")

    return outpath
