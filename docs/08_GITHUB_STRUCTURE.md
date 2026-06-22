# GITHUB_STRUCTURE

## Репозиторий

Рекомендуемое имя:

ai-opportunity-scanner

## Структура

```text
ai-opportunity-scanner/
  README.md
  .env.example
  .gitignore
  docker-compose.yml
  Dockerfile
  requirements.txt

  docs/
    00_CHATGPT_PROJECT_INSTRUCTIONS.md
    01_MASTER_CONTEXT.md
    02_STACK_AND_ARCHITECTURE.md
    03_ROADMAP.md
    04_SALES_PLAYBOOK.md
    05_LEAD_SCORING_SPEC.md
    06_SOURCES_AND_RISKS.md
    07_FIRST_48_HOURS.md

  app/
    main.py
    config.py
    database.py
    models.py
    schemas.py

    sources/
      __init__.py
      twogis.py
      google_places.py
      yandex_orgs.py
      osm.py

    scoring/
      __init__.py
      lead_score.py

    enrichment/
      __init__.py
      website_checker.py

    sales/
      __init__.py
      message_generator.py
      offer_selector.py

    export/
      __init__.py
      csv_export.py

    cli/
      scan_city.py

  data/
    .gitkeep

  tests/
    test_lead_score.py
```

## Ветки

- main — стабильная версия;
- dev — разработка;
- feature/source-2gis — источник 2GIS;
- feature/scoring — скоринг;
- feature/export — экспорт.

## Правило коммитов

Каждый коммит должен отвечать на вопрос:
“Как это приближает к лидам, продажам или выполнению оплаченного заказа?”
