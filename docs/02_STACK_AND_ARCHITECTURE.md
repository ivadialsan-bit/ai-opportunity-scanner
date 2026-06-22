# STACK_AND_ARCHITECTURE

## Выбор стека

### MVP

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 или SQLModel
- Alembic
- Pydantic
- Docker Compose
- httpx
- pandas
- python-dotenv
- simple HTML/JS admin or Jinja templates
- CSV export

## Почему так

FastAPI подходит для быстрого API и Python-инструментов.
PostgreSQL лучше SQLite для дальнейшего хранения лидов, статусов, контактов, аудитов и истории.
Docker Compose упрощает запуск на Timeweb VPS.
CSV нужен сразу, потому что продажи можно начать без UI.

## Источники данных

### Основные

1. 2GIS Places API
2. Google Places API
3. Yandex Organization Search API

### Вспомогательный

4. OpenStreetMap / Overpass

## Что не использовать как основу

- HTML scraping Яндекс.Карт;
- HTML scraping 2GIS;
- HTML scraping Авито;
- обход капч;
- массовые авторассылки.

## Архитектура MVP

services:
- api: FastAPI
- db: PostgreSQL
- worker: простой Python-скрипт или background task
- exporter: CSV generation

modules:
- sources/
  - twogis.py
  - google_places.py
  - yandex_orgs.py
  - osm.py
- scoring/
  - lead_score.py
- enrichment/
  - website_checker.py
  - landing_detector.py
  - contact_detector.py
- sales/
  - offer_selector.py
  - message_generator.py
- storage/
  - models.py
  - repository.py
- cli/
  - scan_city.py

## Минимальная модель данных

Lead:
- id
- source
- source_id
- company_name
- city
- category
- phone
- website
- address
- rating
- reviews_count
- has_website
- has_booking
- has_messenger
- opportunity_flags
- lead_score
- suggested_offer
- first_message
- status
- created_at
- updated_at

LeadStatus:
- new
- checked
- contacted
- replied
- audit_sent
- offer_sent
- paid
- rejected
- bad_fit

## Первый запуск

1. Запустить scan по городу и нише.
2. Получить CSV.
3. Отобрать score 70+.
4. Проверить 30–50 вручную.
5. Делать мини-аудиты.
6. Продавать.
