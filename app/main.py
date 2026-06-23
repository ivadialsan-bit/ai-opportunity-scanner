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
from scanner.yandex_source import scan_yandex


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
    # Ремонт и строительство
    "сантехник", "электрик", "ремонт квартир", "натяжные потолки",
    "окна пвх", "двери установка", "плиточник", "штукатурка обои",
    "кровля", "фундамент", "заборы ворота", "ландшафтный дизайн",
    # Климат и инженерия
    "кондиционеры монтаж", "отопление котлы", "вентиляция",
    "водоснабжение скважина", "канализация септик",
    # Красота и здоровье
    "маникюр педикюр", "салон красоты", "парикмахер", "брови ресницы",
    "косметолог", "массаж", "эпиляция", "тату пирсинг",
    # Авто
    "автосервис ремонт", "шиномонтаж", "автозапчасти", "эвакуатор",
    "детейлинг полировка", "автостекла",
    # Грузоперевозки
    "грузоперевозки газель", "переезд грузчики",
    # Питание
    "доставка еды", "кейтеринг", "торты на заказ",
    # Образование
    "репетитор", "детский центр развития", "автошкола",
    # Домашние сервисы
    "клининг уборка", "химчистка мебели", "ремонт бытовой техники",
    "ремонт телефонов", "ремонт компьютеров",
    # B2B сервисы
    "бухгалтер", "юрист", "дизайн интерьера", "фотограф видеограф",
    "реклама вывески", "печать полиграфия",
    # Медицина и вет
    "стоматология", "ветеринарная клиника",
    # Туризм и досуг
    "турагентство", "гостиница хостел",
    # Фитнес
    "фитнес тренажерный зал", "персональный тренер йога",
]

CITIES = [
    # Миллионники
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Челябинск", "Самара", "Уфа", "Ростов-на-Дону",
    "Краснодар", "Омск", "Красноярск", "Воронеж", "Пермь",
    # 500k+
    "Волгоград", "Саратов", "Тюмень", "Тольятти", "Ижевск",
    "Барнаул", "Ульяновск", "Иркутск", "Хабаровск", "Ярославль",
    "Владивосток", "Махачкала", "Томск", "Оренбург", "Кемерово",
    # 300k+
    "Астрахань", "Рязань", "Пенза", "Липецк", "Тула",
    "Киров", "Чебоксары", "Калининград", "Брянск", "Курск",
    "Иваново", "Магнитогорск", "Тверь", "Белгород", "Сочи",
    "Нижний Тагил", "Архангельск", "Владимир", "Чита", "Сургут",
    "Ставрополь", "Улан-Удэ", "Мурманск", "Смоленск", "Кострома",
    "Новокузнецк", "Вологда", "Таганрог", "Калуга", "Нальчик",
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
    source: str = Form("yandex"),
    limit: int = Form(30),
    require_contact: str = Form("on"),
) -> HTMLResponse:
    from dataclasses import asdict
    limit = max(1, min(int(limit), 100))
    api_note = ""
    all_leads = []
    seen = set()

    sources = source.split(",") if "," in source else [source]

    for src in sources:
        src = src.strip()
        try:
            if src == "yandex":
                leads_raw, note = scan_yandex(city, niche, limit=limit)
            elif src == "2gis":
                from app.dgis_source import scan_2gis as _scan_2gis
                leads_raw, raw_count, note = _scan_2gis(city=city, niche=niche, limit=limit)
            else:
                continue

            if note:
                api_note = note

            for lead in leads_raw:
                try:
                    d = asdict(lead)
                except Exception:
                    d = lead.__dict__ if hasattr(lead, '__dict__') else {}
                phone = d.get("phone", "") or ""
                name = d.get("name", "") or ""
                key = f"{name.lower()}|{phone}"
                if key not in seen and name:
                    seen.add(key)
                    all_leads.append(lead)
        except Exception as ex:
            api_note = str(ex)

    # фильтр по контакту
    if require_contact:
        filtered = [l for l in all_leads if getattr(l, "phone", "") or getattr(l, "email", "") or getattr(l, "website", "")]
    else:
        filtered = all_leads

    filtered.sort(key=lambda x: getattr(x, "lead_score", 0), reverse=True)

    imported = insert_scanned_leads(
        city=city,
        niche=niche,
        source="+".join(sources),
        raw_count=len(all_leads),
        leads=filtered,
    )
    migrate_operator_v2()

    result = {
        "city": city,
        "niche": niche,
        "source": "+".join(sources),
        "raw_count": len(all_leads),
        "sales_count": len(filtered),
        "imported": imported,
        "top": filtered[:15],
        "api_note": api_note,
    }

    return templates.TemplateResponse(
        "scanner.html",
        {"request": request, "cities": CITIES, "niches": NICHES, "result": result},
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
    stats = get_dashboard_stats()
    return templates.TemplateResponse(
        "lead_detail.html",
        {
            "request": request,
            "lead": lead,
            "events": events,
            "stats": stats,
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


from fastapi import UploadFile, File
import tempfile, shutil


@app.get("/import-csv", response_class=HTMLResponse)
def import_csv_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "import_csv.html", {"request": request}
    )


@app.post("/import-csv")
async def import_csv_upload(
    request: Request,
    file: UploadFile = File(...),
) -> HTMLResponse:
    if not file.filename.endswith(".csv"):
        return templates.TemplateResponse(
            "import_csv.html",
            {"request": request, "error": "Нужен .csv файл", "imported": 0},
        )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    from app.db import import_shortlist_csv
    imported = import_shortlist_csv(tmp_path)
    migrate_operator_v2()

    return templates.TemplateResponse(
        "import_csv.html",
        {"request": request, "imported": imported, "filename": file.filename},
    )
