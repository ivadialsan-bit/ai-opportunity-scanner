from __future__ import annotations

import argparse
import sys
from datetime import datetime

from scanner.config import get_city
from scanner.export_csv import export_leads_csv
from scanner.filters import apply_sales_filters
from scanner.offers import enrich_offer
from scanner.osm_overpass import build_overpass_query, fetch_overpass, parse_elements
from scanner.scoring import score_lead


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-opportunity-scanner",
        description="MVP CLI scanner for public business opportunities. Manual outreach only.",
    )
    parser.add_argument("--city", required=True, help="Город: Волгоград, Краснодар, Ростов-на-Дону, Астрахань, Саратов")
    parser.add_argument("--query", required=True, help="Ниша / поисковый запрос, например: кондиционеры")
    parser.add_argument("--source", default="osm", choices=["osm", "overpass"], help="Источник данных")
    parser.add_argument("--limit", type=int, default=50, help="Лимит объектов из Overpass")
    parser.add_argument("--output", default="", help="Путь CSV. Если пусто — results/<city>_<query>_<timestamp>.csv")
    parser.add_argument("--debug-query", action="store_true", help="Показать OverpassQL запрос")
    parser.add_argument("--include-chains", action="store_true", help="Не исключать федеральные сети")
    parser.add_argument("--min-confidence", default="medium", choices=["low", "medium", "high"], help="Минимальное качество совпадения с нишей")
    parser.add_argument("--no-require-contact", action="store_true", help="Оставлять лиды без телефона/сайта/email")
    return parser


def safe_filename(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("ё", "е")
    )


def main() -> int:
    args = build_parser().parse_args()

    try:
        city = get_city(args.city)
        limit = max(1, min(args.limit, 200))
        query = build_overpass_query(city, args.query, limit=limit)

        if args.debug_query:
            print("========== OVERPASS QUERY ==========")
            print(query)

        print(f"Scanning source={args.source} city={city.name} query={args.query} limit={limit}")

        data = fetch_overpass(query, source=args.source)
        leads = parse_elements(data, city=city, niche=args.query, source=args.source)

        enriched_all = [enrich_offer(score_lead(lead)) for lead in leads]
        enriched = apply_sales_filters(
            enriched_all,
            exclude_chains=not args.include_chains,
            min_confidence=args.min_confidence,
            require_contact=not args.no_require_contact,
        )
        enriched.sort(key=lambda x: x.lead_score, reverse=True)

        if args.output:
            output = args.output
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"results/{safe_filename(city.name)}_{safe_filename(args.query)}_{ts}.csv"

        path = export_leads_csv(enriched, output)

        print("========== RESULT ==========")
        print(f"raw_leads_found={len(leads)}")
        print(f"sales_leads_found={len(enriched)}")
        print(f"csv={path}")
        print(f"filters=exclude_chains:{not args.include_chains}, min_confidence:{args.min_confidence}, require_contact:{not args.no_require_contact}")

        if enriched:
            print("========== TOP 10 ==========")
            for idx, lead in enumerate(enriched[:10], start=1):
                print(f"{idx}. score={lead.lead_score} | {lead.name} | phone={lead.phone or '-'} | website={lead.website or '-'}")
        else:
            print("No leads found. This can happen with OSM. Try another city/query or later add 2GIS/Google/Yandex API.")

        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
