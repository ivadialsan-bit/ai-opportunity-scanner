from __future__ import annotations

import base64
import secrets
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import (
    get_dashboard_stats,
    get_events,
    get_lead,
    get_next_lead_id,
    import_shortlist_csv,
    init_db,
    insert_scanned_leads,
    latest_shortlist_path,
    list_leads,
    update_lead,
    migrate_operator_v2,
    has_contact,
)

from scanner.config import get_city
from scanner.filters import apply_sales_filters
from scanner.offers import enrich_offer
from scanner.osm_overpass import build_overpass_query, fetch_overpass, parse_elements
from scanner.scoring import score_lead
from app.dgis_source import scan_2gis


app = FastAPI(title="AI Sales Cockpit")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _unauthorized_response() -> PlainTextResponse:
    return PlainTextResponse(
        "Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="AI Sales Cockpit"'},
    )


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    expected_user = os.getenv("COCKPIT_USER", "")
    expected_pass = os.getenv("COCKPIT_PASS", "")

    if not expected_user or not expected_pass:
        return await call_next(request)

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Basic "):
        return _unauthorized_response()

    try:
        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return _unauthorized_response()

    if not (
        secrets.compare_digest(username, expected_user)
        and secrets.compare_digest(password, expected_pass)
    ):
        return _unauthorized_response()

    return await call_next(request)


STATUSES = [
    "Новый",
    "Нужна проверка контакта",
    "Позвонил",
    "Не ответили",
    "Неверный контакт",
    "ЛПР найден",
    "Интерес",
    "Просит пример",
    "КП отправлено",
    "Повторный контакт",
    "Оплачено",
    "Отказ",
]


NICHES = [
    "кондиционеры",
    "сплит-системы",
    "автокондиционеры",
    "ремонт холодильников",
    "сантехник",
    "электрик",
    "эвакуатор",
    "натяжные потолки",
    "окна",
    "двери",
    "клининг",
    "ремонт квартир",
]


CITIES = [
    "Волгоград",
    "Краснодар",
    "Ростов-на-Дону",
    "Астрахань",
    "Саратов",
]


@app.on_event("startup")
def startup() -> None:
    init_db()
    migrate_operator_v2()
    if os.getenv("COCKPIT_AUTO_IMPORT", "1") == "1":
        path = latest_shortlist_path()
        if path:
            import_shortlist_csv(path)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    stats = get_dashboard_stats()
    leads = list_leads(status="", q="", city="")[:10]
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "leads": leads,
            "demo_url": "http://5.129.200.18:8080/demo-48h/",
        },
    )


@app.get("/scanner", response_class=HTMLResponse)
def scanner_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "scanner.html",
        {
            "request": request,
            "cities": CITIES,
            "niches": NICHES,
            "result": None,
        },
    )


@app.post("/scanner", response_class=HTMLResponse)
def run_scanner(
    request: Request,
    city: str = Form(...),
    niche: str = Form(...),
    source: str = Form("osm"),
    limit: int = Form(50),
    min_confidence: str = Form("medium"),
    require_contact: str = Form("on"),
    exclude_chains: str = Form("on"),
) -> HTMLResponse:
    limit = max(1, min(int(limit), 200))
    api_note = ""

    if source == "2gis":
        scanned, raw_count, api_note = scan_2gis(city=city, niche=niche, limit=limit)

        if bool(require_contact):
            filtered = [lead for lead in scanned if has_contact(lead)]
            if not filtered:
                api_note = (
                    api_note
                    or "2ГИС нашёл компании, но контакты не пришли по текущему API-ключу. "
                       "Для импорта в очередь прозвона нужен доступ к items.contact_groups."
                )
        else:
            filtered = scanned

        imported = insert_scanned_leads(
            city=city,
            niche=niche,
            source="2gis",
            raw_count=raw_count,
            leads=filtered,
        )

        migrate_operator_v2()

        result = {
            "city": city,
            "niche": niche,
            "source": "2ГИС API",
            "raw_count": raw_count,
            "sales_count": len(filtered),
            "imported": imported,
            "top": filtered[:10],
            "api_note": api_note,
        }

        return templates.TemplateResponse(
            "scanner.html",
            {
                "request": request,
                "cities": CITIES,
                "niches": NICHES,
                "result": result,
            },
        )

    city_obj = get_city(city)

    query = build_overpass_query(city_obj, niche, limit=limit)
    data = fetch_overpass(query, source=source)
    raw_leads = parse_elements(data, city=city_obj, niche=niche, source=source)

    enriched_all = [enrich_offer(score_lead(lead)) for lead in raw_leads]
    filtered = apply_sales_filters(
        enriched_all,
        exclude_chains=bool(exclude_chains),
        min_confidence=min_confidence,
        require_contact=bool(require_contact),
    )
    filtered.sort(key=lambda x: x.lead_score, reverse=True)

    imported = insert_scanned_leads(
        city=city_obj.name,
        niche=niche,
        source=source,
        raw_count=len(raw_leads),
        leads=filtered,
    )

    migrate_operator_v2()

    result = {
        "city": city_obj.name,
        "niche": niche,
        "source": source,
        "raw_count": len(raw_leads),
        "sales_count": len(filtered),
        "imported": imported,
        "top": filtered[:10],
        "api_note": api_note,
    }

    return templates.TemplateResponse(
        "scanner.html",
        {
            "request": request,
            "cities": CITIES,
            "niches": NICHES,
            "result": result,
        },
    )


@app.get("/leads", response_class=HTMLResponse)
def leads_page(
    request: Request,
    status: str = "",
    q: str = "",
    city: str = "",
    lead_source: str = "",
    contact_filter: str = "",
) -> HTMLResponse:
    leads = list_leads(
        status=status,
        q=q,
        city=city,
        lead_source=lead_source,
        contact_filter=contact_filter,
    )

    return templates.TemplateResponse(
        "leads.html",
        {
            "request": request,
            "leads": leads,
            "statuses": STATUSES,
            "selected_status": status,
            "selected_city": city,
            "selected_source": lead_source,
            "selected_contact_filter": contact_filter,
            "q": q,
            "cities": CITIES,
            "demo_url": "http://5.129.200.18:8080/demo-48h/",
        },
    )


@app.get("/leads/{lead_id}", response_class=HTMLResponse)
def lead_detail(request: Request, lead_id: int) -> HTMLResponse:
    lead = get_lead(lead_id)
    if not lead:
        return HTMLResponse("Lead not found", status_code=404)

    events = get_events(lead_id)
    return templates.TemplateResponse(
        "lead_detail.html",
        {
            "request": request,
            "lead": lead,
            "events": events,
            "statuses": STATUSES,
            "demo_url": "http://5.129.200.18:8080/demo-48h/",
        },
    )


@app.post("/leads/{lead_id}/update")
def update_lead_post(
    lead_id: int,
    status: str = Form(...),
    next_action: str = Form(""),
    call_notes: str = Form(""),
    decision_maker: str = Form(""),
    pain_confirmed: str = Form(""),
    offer_sent: str = Form(""),
    price_discussed: str = Form(""),
    result: str = Form(""),
) -> RedirectResponse:
    event_note = f"status={status}; next_action={next_action}; result={result}"
    update_lead(
        lead_id,
        {
            "status": status,
            "next_action": next_action,
            "call_notes": call_notes,
            "decision_maker": decision_maker,
            "pain_confirmed": pain_confirmed,
            "offer_sent": offer_sent,
            "price_discussed": price_discussed,
            "result": result,
        },
        event_note=event_note,
    )
    return RedirectResponse(f"/leads/{lead_id}", status_code=303)


@app.post("/import-shortlist")
def import_shortlist() -> RedirectResponse:
    path = latest_shortlist_path()
    if path:
        import_shortlist_csv(path)
    return RedirectResponse("/leads", status_code=303)


@app.get("/health")
def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.get("/next-lead")
def next_lead_redirect() -> RedirectResponse:
    lead_id = get_next_lead_id("Новый")
    if lead_id:
        return RedirectResponse(f"/leads/{lead_id}", status_code=303)
    return RedirectResponse("/leads", status_code=303)
