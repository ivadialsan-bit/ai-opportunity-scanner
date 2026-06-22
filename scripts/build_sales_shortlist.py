from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from datetime import datetime
from pathlib import Path


BLACKLIST_TOKENS = [
    "м.видео",
    "мвидео",
    "mvideo",
    "эльдорадо",
    "eldorado",
    "samsung",
    "xiaomi",
    "mi-shop",
    "haier",
    "redmond",
    "sony",
    "restore",
    "re:premium",
    "stores-apple",
    "dns",
    "днс",
    "citilink",
    "ситилинк",
    "этм",
    "etm.ru",
    "евраз",
    "evraz",
    "мосплитка",
    "mosplitka",
    "holodilnik",
    "holodilnik.ru",
    "loudsound",
    "karcher",
    "керхер",
    "vsesmart",
    "всёсмарт",
    "astmarket",
]


POSITIVE_TOKENS = [
    "кондиц",
    "сплит",
    "split",
    "климат",
    "climat",
    "hvac",
    "вентиляц",
    "холод",
    "тепло",
    "air condition",
    "air_condition",
]


OUTPUT_FIELDS = [
    "sales_priority",
    "city",
    "name",
    "phone",
    "email",
    "website",
    "address",
    "target_confidence",
    "lead_score",
    "priority_reason",
    "first_message",
    "source",
    "osm_type",
    "osm_id",
]


def norm(value: str) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def combined(row: dict[str, str]) -> str:
    return norm(" ".join([
        row.get("name", ""),
        row.get("website", ""),
        row.get("address", ""),
        row.get("tags_json", ""),
        row.get("opportunity_flags", ""),
    ]))


def has_blacklist(row: dict[str, str]) -> bool:
    text = combined(row)
    return any(token in text for token in BLACKLIST_TOKENS)


def has_positive(row: dict[str, str]) -> bool:
    text = combined(row)
    return any(token in text for token in POSITIVE_TOKENS)


def has_contact(row: dict[str, str]) -> bool:
    return bool(row.get("phone") or row.get("email") or row.get("website"))


def no_website(row: dict[str, str]) -> bool:
    return not bool(row.get("website"))


def priority(row: dict[str, str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    try:
        score += int(row.get("lead_score", "0"))
    except ValueError:
        pass

    if row.get("target_confidence") == "high":
        score += 30
        reasons.append("high_confidence")

    if has_positive(row):
        score += 25
        reasons.append("positive_hvac_terms")

    if no_website(row):
        score += 30
        reasons.append("no_website")

    if row.get("phone"):
        score += 15
        reasons.append("phone_present")

    if row.get("email"):
        score += 10
        reasons.append("email_present")

    if row.get("address"):
        score += 5
        reasons.append("address_present")

    if has_blacklist(row):
        score -= 1000
        reasons.append("blacklisted_chain_or_noise")

    if not has_contact(row):
        score -= 500
        reasons.append("no_contact")

    return score, reasons


def row_key(row: dict[str, str]) -> str:
    return "|".join([
        norm(row.get("city", "")),
        norm(row.get("name", "")),
        norm(row.get("phone", "")),
        norm(row.get("website", "")),
    ])


def find_latest_merged() -> str:
    files = sorted(
        glob.glob("results/sales_leads_5_cities_*.csv"),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError("Не найден results/sales_leads_5_cities_*.csv")
    return files[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="", help="Merged CSV. Если пусто — берём последний sales_leads_5_cities_*.csv")
    parser.add_argument("--output", default="", help="Output shortlist CSV")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--min-priority", type=int, default=100)
    args = parser.parse_args()

    input_path = args.input or find_latest_merged()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or f"results/outreach_shortlist_{ts}.csv"

    rows: list[dict[str, str]] = []

    with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p, reasons = priority(row)

            if p < args.min_priority:
                continue

            if has_blacklist(row):
                continue

            if not has_contact(row):
                continue

            if row.get("target_confidence") != "high" and not no_website(row):
                continue

            row["sales_priority"] = str(p)
            row["priority_reason"] = ";".join(reasons)
            rows.append(row)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in sorted(rows, key=lambda r: int(r["sales_priority"]), reverse=True):
        key = row_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    deduped = deduped[: max(1, args.limit)]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for row in deduped:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})

    print("========== SHORTLIST RESULT ==========")
    print(f"input={input_path}")
    print(f"output={output_path}")
    print(f"shortlist_count={len(deduped)}")
    print()
    print("========== TOP SHORTLIST ==========")

    for i, row in enumerate(deduped[:20], start=1):
        print(
            f"{i}. priority={row.get('sales_priority')} | "
            f"{row.get('city')} | {row.get('name')} | "
            f"phone={row.get('phone') or '-'} | "
            f"email={row.get('email') or '-'} | "
            f"website={row.get('website') or '-'} | "
            f"reason={row.get('priority_reason')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
