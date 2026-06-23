#!/usr/bin/env python3
"""
AI Opportunity Scanner — CLI запуск
Использование:
  python scan.py --city Краснодар --niches сантехника,электрика,красота
  python scan.py --city Москва --niches ремонт --sources avito,yandex
  python scan.py --city Краснодар --niches все --sources avito
"""
from __future__ import annotations

import argparse
import sys
from scanner.multi_scan import run_multi_scan, ALL_NICHES


def main() -> int:
    p = argparse.ArgumentParser(description="AI Opportunity Scanner")
    p.add_argument("--city", required=True, help="Город: Краснодар, Москва, Ростов-на-Дону...")
    p.add_argument(
        "--niches", required=True,
        help='Ниши через запятую или "все": сантехника,электрика,красота'
    )
    p.add_argument(
        "--sources", default="avito,zoon,yandex",
        help="Источники через запятую: avito,zoon,yandex (по умолчанию все)"
    )
    p.add_argument("--limit", type=int, default=30, help="Лимит лидов на источник на нишу")
    p.add_argument("--output", default="results", help="Папка для CSV")
    args = p.parse_args()

    niches_input = args.niches.strip().lower()
    if niches_input in ("все", "all", "все_ниши"):
        niches = ALL_NICHES
    else:
        niches = [n.strip() for n in niches_input.split(",") if n.strip()]

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    print(f"Город: {args.city}")
    print(f"Ниши: {niches}")
    print(f"Источники: {sources}")
    print(f"Лимит: {args.limit} лидов / источник / ниша")

    path = run_multi_scan(
        city=args.city,
        niches=niches,
        sources=sources,
        limit_per_source=args.limit,
        output_dir=args.output,
    )

    if path:
        print(f"\nCSV готов: {path}")
        return 0
    else:
        print("\nЛиды не найдены.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
