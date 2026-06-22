from __future__ import annotations

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
    import_shortlist_csv,
    init_db,
    insert_scanned_leads,
    latest_shortlist_path,
    list_leads,
    update_lead,
)

from scanner.config import get_city
from scanner.filters import apply_sales_filters
from scanner.offers import enrich_offer
from scanner.osm_overpass import build_overpass_query, fetch_overpass, parse_elements
from scanner.scoring import score_lead


app = FastAPI(title="AI Sales Cockpit")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


STATUSES = [
    "new",
    "called",
    "no_answer",
    "wrong_contact",
    "decision_maker_found",
    "interested",
    "example_requested",
    "offer_sent",
    "follow_up",
    "paid",
    "rejected",
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

    result = {
        "city": city_obj.name,
        "niche": niche,
        "source": source,
        "raw_count": len(raw_leads),
        "sales_count": len(filtered),
        "imported": imported,
        "top": filtered[:10],
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
) -> HTMLResponse:
    leads = list_leads(status=status, q=q, city=city)
    return templates.TemplateResponse(
        "leads.html",
        {
            "request": request,
            "leads": leads,
            "statuses": STATUSES,
            "selected_status": status,
            "selected_city": city,
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
