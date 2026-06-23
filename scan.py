#!/usr/bin/env python3
"""
AI Opportunity Scanner
Использование:
  python3 scan.py --city Краснодар --niches сантехника,красота
  python3 scan.py --city Москва --niches все --limit 30
  python3 scan.py --city Краснодар --niches все --key ВАШ_КЛЮЧ_2GIS
"""
from __future__ import annotations
import argparse, sys, os
from scanner.multi_scan import run_multi_scan, ALL_NICHES


def main() -> int:
    p = argparse.ArgumentParser(description="AI Opportunity Scanner — 2GIS edition")
    p.add_argument("--city", required=True, help="Город: Краснодар, Москва, Ростов-на-Дону...")
    p.add_argument("--niches", required=True, help='Ниши: сантехника,красота или "все"')
    p.add_argument("--sources", default="2gis", help="Источники: 2gis (default)")
    p.add_argument("--limit", type=int, default=50, help="Лимит лидов на нишу (default: 50)")
    p.add_argument("--key", default=os.getenv("DGIS_API_KEY", "demo"), help="2GIS API ключ")
    p.add_argument("--output", default="results", help="Папка для CSV")
    args = p.parse_args()

    ni = args.niches.strip().lower()
    niches = ALL_NICHES if ni in ("все", "all") else [n.strip() for n in ni.split(",") if n.strip()]
    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    print(f"Город    : {args.city}")
    print(f"Ниши     : {niches}")
    print(f"Источники: {sources}")
    print(f"2GIS key : {'demo' if args.key == 'demo' else args.key[:8]+'...'}")
    print(f"Лимит    : {args.limit} лидов / ниша")

    path = run_multi_scan(
        city=args.city,
        niches=niches,
        sources=sources,
        limit_per_source=args.limit,
        output_dir=args.output,
        dgis_key=args.key,
    )
    if path:
        print(f"\nГотово: {path}")
        return 0
    print("\nЛиды не найдены.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
