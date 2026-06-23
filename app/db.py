from __future__ import annotations

import csv
import glob
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any


DB_PATH = Path("app/data/cockpit.sqlite3")


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def now_msk() -> str:
    return datetime.now(ZoneInfo("Europe/Moscow")).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S МСК")


def utc_to_msk(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo("Europe/Moscow")).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S МСК")
    except Exception:
        return ""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                city TEXT NOT NULL,
                niche TEXT NOT NULL,
                source TEXT NOT NULL,
                raw_count INTEGER NOT NULL DEFAULT 0,
                sales_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'done',
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                scan_run_id INTEGER,
                status TEXT NOT NULL DEFAULT 'new',
                next_action TEXT NOT NULL DEFAULT 'call_or_manual_message',
                city TEXT NOT NULL DEFAULT '',
                niche TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                website TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                osm_type TEXT NOT NULL DEFAULT '',
                osm_id TEXT NOT NULL DEFAULT '',
                lead_score INTEGER NOT NULL DEFAULT 0,
                sales_priority INTEGER NOT NULL DEFAULT 0,
                target_confidence TEXT NOT NULL DEFAULT '',
                opportunity_flags TEXT NOT NULL DEFAULT '',
                priority_reason TEXT NOT NULL DEFAULT '',
                suggested_offer TEXT NOT NULL DEFAULT '',
                first_message TEXT NOT NULL DEFAULT '',
                call_notes TEXT NOT NULL DEFAULT '',
                decision_maker TEXT NOT NULL DEFAULT '',
                pain_confirmed TEXT NOT NULL DEFAULT '',
                offer_sent TEXT NOT NULL DEFAULT '',
                price_discussed TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                UNIQUE(city, name, phone, website)
            );

            CREATE TABLE IF NOT EXISTS lead_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT ''
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def latest_shortlist_path() -> str | None:
    files = sorted(
        glob.glob("results/outreach_shortlist_*.csv"),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def import_shortlist_csv(path: str) -> int:
    init_db()
    imported = 0
    ts = now_iso()

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        with connect() as conn:
            for row in reader:
                payload = {
                    "created_at": ts,
                    "updated_at": ts,
                    "status": "new",
                    "next_action": "call_or_manual_message",
                    "city": row.get("city", ""),
                    "niche": row.get("niche", "кондиционеры"),
                    "name": row.get("name", ""),
                    "phone": row.get("phone", ""),
                    "email": row.get("email", ""),
                    "website": row.get("website", ""),
                    "address": row.get("address", ""),
                    "source": row.get("source", "osm"),
                    "osm_type": row.get("osm_type", ""),
                    "osm_id": str(row.get("osm_id", "")),
                    "lead_score": int(row.get("lead_score") or 0),
                    "sales_priority": int(row.get("sales_priority") or 0),
                    "target_confidence": row.get("target_confidence", ""),
                    "opportunity_flags": row.get("opportunity_flags", ""),
                    "priority_reason": row.get("priority_reason", ""),
                    "suggested_offer": row.get("suggested_offer", ""),
                    "first_message": row.get("first_message", ""),
                }

                try:
                    conn.execute(
                        """
                        INSERT INTO leads (
                            created_at, updated_at, status, next_action,
                            city, niche, name, phone, email, website, address,
                            source, osm_type, osm_id,
                            lead_score, sales_priority, target_confidence,
                            opportunity_flags, priority_reason, suggested_offer, first_message
                        )
                        VALUES (
                            :created_at, :updated_at, :status, :next_action,
                            :city, :niche, :name, :phone, :email, :website, :address,
                            :source, :osm_type, :osm_id,
                            :lead_score, :sales_priority, :target_confidence,
                            :opportunity_flags, :priority_reason, :suggested_offer, :first_message
                        )
                        """,
                        payload,
                    )
                    imported += 1
                except sqlite3.IntegrityError:
                    continue

    return imported


def get_dashboard_stats() -> dict[str, int]:
    init_db()
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        new = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status IN ('new','Новый')"
        ).fetchone()[0]
        interested = conn.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE status IN (
                'interested','example_requested','offer_sent','follow_up',
                'Интерес','Просит пример','КП отправлено','Повторный контакт'
            )
            """
        ).fetchone()[0]
        paid = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status IN ('paid','Оплачено')"
        ).fetchone()[0]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        contacted_today = conn.execute(
            "SELECT COUNT(DISTINCT lead_id) FROM lead_events WHERE created_at >= ?", (today,)
        ).fetchone()[0]
        talked_today = conn.execute(
            """SELECT COUNT(DISTINCT lead_id) FROM lead_events
               WHERE created_at >= ? AND note LIKE '%status=Интерес%'
               OR note LIKE '%status=КП%' OR note LIKE '%status=Оплач%'""", (today,)
        ).fetchone()[0]
        kp_today = conn.execute(
            """SELECT COUNT(DISTINCT lead_id) FROM lead_events
               WHERE created_at >= ? AND note LIKE '%status=КП отправлено%'""", (today,)
        ).fetchone()[0]
    return {
        "total": total, "new": new, "interested": interested, "paid": paid,
        "contacted_today": contacted_today,
        "talked_today": talked_today,
        "kp_today": kp_today,
    }


def list_leads(
    status: str = "",
    q: str = "",
    city: str = "",
    lead_source: str = "",
    contact_filter: str = "",
) -> list[dict[str, Any]]:
    init_db()

    where = []
    params: dict[str, Any] = {}

    contact_expr = """
    (
        TRIM(COALESCE(phone,'')) != ''
        OR TRIM(COALESCE(email,'')) != ''
        OR TRIM(COALESCE(website,'')) != ''
    )
    """

    if status:
        where.append("status = :status")
        params["status"] = status

    if city:
        where.append("city = :city")
        params["city"] = city

    if lead_source:
        if lead_source == "osm":
            where.append("source IN ('osm','overpass')")
        else:
            where.append("source = :lead_source")
            params["lead_source"] = lead_source

    if contact_filter == "with_contact":
        where.append(contact_expr)
    elif contact_filter == "without_contact":
        where.append(f"NOT {contact_expr}")
    elif contact_filter == "needs_check":
        where.append("status = 'Нужна проверка контакта'")

    if q:
        where.append("(name LIKE :q OR phone LIKE :q OR email LIKE :q OR website LIKE :q OR priority_reason LIKE :q OR recommended_product LIKE :q)")
        params["q"] = f"%{q}%"

    sql = "SELECT * FROM leads"
    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += """
    ORDER BY
      CASE
        WHEN status='Новый' THEN 0
        WHEN status='Интерес' THEN 1
        WHEN status='Просит пример' THEN 2
        WHEN status='КП отправлено' THEN 3
        WHEN status='Нужна проверка контакта' THEN 9
        ELSE 5
      END,
      sales_priority DESC,
      lead_score DESC,
      id DESC
    LIMIT 500
    """

    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_lead(lead_id: int) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        lead = row_to_dict(conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())
    if not lead:
        return None
    try:
        from app.scripts import generate_scripts
        scripts = generate_scripts(
            name=lead.get("name", ""),
            niche=lead.get("niche", ""),
            city=lead.get("city", ""),
            website=lead.get("website", ""),
            phone=lead.get("phone", ""),
            email=lead.get("email", ""),
            flags=lead.get("opportunity_flags", ""),
            product=lead.get("recommended_product", ""),
            price=lead.get("recommended_price", ""),
        )
        lead.update(scripts)
    except Exception:
        pass
    # квалификация — рекомендуемые продукты
    try:
        from app.qualification import qualify, PRODUCTS, QUALIFICATION_QUESTIONS
        flags = lead.get("opportunity_flags", "")
        recs = qualify(
            has_website=bool(lead.get("website")),
            has_socials="vk_present" in flags,
            has_bot=False,
            niche=lead.get("niche", ""),
            rating=float(lead.get("rating") or 0),
            source=lead.get("source", ""),
        )
        lead["qualify_recs"] = recs
        lead["all_products"] = PRODUCTS
        lead["qualify_questions"] = QUALIFICATION_QUESTIONS
    except Exception:
        pass
    return lead


def get_events(lead_id: int) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM lead_events WHERE lead_id=? ORDER BY id DESC",
                (lead_id,),
            ).fetchall()
        ]


def update_lead(lead_id: int, fields: dict[str, Any], event_note: str = "") -> None:
    init_db()
    allowed = {
        "status",
        "next_action",
        "call_notes",
        "decision_maker",
        "pain_confirmed",
        "offer_sent",
        "price_discussed",
        "result",
    }

    clean = {k: v for k, v in fields.items() if k in allowed}
    clean["updated_at"] = now_iso()
    clean["updated_at_msk"] = now_msk()
    clean["last_contact_at_msk"] = now_msk()

    set_clause = ", ".join([f"{k}=:{k}" for k in clean])
    clean["id"] = lead_id

    with connect() as conn:
        conn.execute(f"UPDATE leads SET {set_clause} WHERE id=:id", clean)

        if event_note:
            conn.execute(
                """
                INSERT INTO lead_events (lead_id, created_at, event_type, note)
                VALUES (?, ?, ?, ?)
                """,
                (lead_id, now_iso(), "manual_update", event_note),
            )


def insert_scanned_leads(city: str, niche: str, source: str, raw_count: int, leads: list[Any]) -> int:
    init_db()
    ts = now_iso()

    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO scan_runs (created_at, city, niche, source, raw_count, sales_count, status)
            VALUES (?, ?, ?, ?, ?, ?, 'done')
            """,
            (ts, city, niche, source, raw_count, len(leads)),
        )
        scan_run_id = cur.lastrowid

        imported = 0

        for lead in leads:
            payload = {
                "created_at": ts,
                "updated_at": ts,
                "scan_run_id": scan_run_id,
                "status": "new",
                "next_action": "call_or_manual_message",
                "city": getattr(lead, "city", ""),
                "niche": getattr(lead, "niche", ""),
                "name": getattr(lead, "name", ""),
                "phone": getattr(lead, "phone", ""),
                "email": getattr(lead, "email", ""),
                "website": getattr(lead, "website", ""),
                "address": getattr(lead, "address", ""),
                "source": getattr(lead, "source", ""),
                "osm_type": getattr(lead, "osm_type", ""),
                "osm_id": str(getattr(lead, "osm_id", "")),
                "lead_score": int(getattr(lead, "lead_score", 0) or 0),
                "sales_priority": int(getattr(lead, "lead_score", 0) or 0),
                "target_confidence": next((f.replace("target_confidence_", "") for f in getattr(lead, "opportunity_flags", []) if f.startswith("target_confidence_")), ""),
                "opportunity_flags": ";".join(getattr(lead, "opportunity_flags", []) or []),
                "priority_reason": ";".join(getattr(lead, "opportunity_flags", []) or []),
                "suggested_offer": getattr(lead, "suggested_offer", ""),
                "first_message": getattr(lead, "first_message", ""),
            }

            try:
                conn.execute(
                    """
                    INSERT INTO leads (
                        created_at, updated_at, scan_run_id, status, next_action,
                        city, niche, name, phone, email, website, address,
                        source, osm_type, osm_id,
                        lead_score, sales_priority, target_confidence,
                        opportunity_flags, priority_reason, suggested_offer, first_message
                    )
                    VALUES (
                        :created_at, :updated_at, :scan_run_id, :status, :next_action,
                        :city, :niche, :name, :phone, :email, :website, :address,
                        :source, :osm_type, :osm_id,
                        :lead_score, :sales_priority, :target_confidence,
                        :opportunity_flags, :priority_reason, :suggested_offer, :first_message
                    )
                    """,
                    payload,
                )
                imported += 1
            except sqlite3.IntegrityError:
                continue

        return imported


def get_next_lead_id(status: str = "Новый") -> int | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM leads
            WHERE status IN (?, 'new', 'Новый')
              AND (
                TRIM(COALESCE(phone,'')) != ''
                OR TRIM(COALESCE(email,'')) != ''
                OR TRIM(COALESCE(website,'')) != ''
              )
            ORDER BY sales_priority DESC, lead_score DESC, id ASC
            LIMIT 1
            """,
            (status,),
        ).fetchone()

        if row:
            return int(row[0])

        row = conn.execute(
            """
            SELECT id FROM leads
            WHERE (
                TRIM(COALESCE(phone,'')) != ''
                OR TRIM(COALESCE(email,'')) != ''
                OR TRIM(COALESCE(website,'')) != ''
              )
            ORDER BY sales_priority DESC, lead_score DESC, id ASC
            LIMIT 1
            """
        ).fetchone()

        return int(row[0]) if row else None



def _ensure_leads_column(conn: sqlite3.Connection, column_sql: str) -> None:
    column_name = column_sql.split()[0]
    existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE leads ADD COLUMN {column_sql}")


def _status_ru(value: str) -> str:
    mapping = {
        "new": "Новый",
        "called": "Позвонил",
        "no_answer": "Не ответили",
        "wrong_contact": "Неверный контакт",
        "decision_maker_found": "ЛПР найден",
        "interested": "Интерес",
        "example_requested": "Просит пример",
        "offer_sent": "КП отправлено",
        "follow_up": "Повторный контакт",
        "paid": "Оплачено",
        "rejected": "Отказ",
    }
    return mapping.get(value, value or "Новый")


def _next_action_ru(value: str) -> str:
    mapping = {
        "call_or_manual_message": "Позвонить / если не ответили — ручное сообщение",
        "call": "Позвонить",
        "manual_message": "Отправить ручное сообщение",
        "follow_up": "Повторить контакт",
    }
    return mapping.get(value, value or "Позвонить / если не ответили — ручное сообщение")


def _recommend_product(flags: str, website: str, phone: str, email: str, niche: str = "", name: str = "") -> tuple[str, str, str, str, str]:
    """
    Возвращает: (product, price, reason, call_opener, what_to_sell)
    Логика: анализируем цифровые дыры конкретного бизнеса и назначаем оффер.
    """
    f = (flags or "").lower()
    site = (website or "").strip()
    has_phone = bool((phone or "").strip())
    has_email = bool((email or "").strip())
    n = (niche or "").lower()

    # Определяем тип бизнеса по нише
    is_service = any(x in n for x in ["сантехник", "электрик", "ремонт", "клининг", "кровля", "фундамент", "потолк", "окна", "двери", "заборы", "вентиляц", "водоснаб"])
    is_beauty = any(x in n for x in ["маникюр", "педикюр", "салон", "парикмахер", "брови", "ресниц", "косметол", "массаж", "эпиляц", "тату"])
    is_auto = any(x in n for x in ["автосервис", "шиномонтаж", "автозапч", "эвакуатор", "детейлинг", "автостекл"])
    is_food = any(x in n for x in ["доставка еды", "кейтеринг", "торты", "кафе", "ресторан"])
    is_b2b = any(x in n for x in ["бухгалтер", "юрист", "реклама", "печать", "полиграф"])
    is_fitness = any(x in n for x in ["фитнес", "тренажер", "тренер", "йога"])
    is_edu = any(x in n for x in ["репетитор", "детский центр", "автошкол"])
    is_medical = any(x in n for x in ["стоматол", "ветерин", "клиник"])

    # ── ДЫРА 1: нет сайта ──
    if not site:
        if is_beauty:
            product = "Страница онлайн-записи за 48 часов"
            price = "7 900 ₽"
            reason = "Нет сайта → клиенты не могут записаться онлайн, уходят туда где можно. Продаём страницу с кнопкой записи + расписание + портфолио работ."
            what = "Страница записи + портфолио работ + кнопка WhatsApp/Telegram"
            opener = f"Нашёл вас — занимаетесь {niche}. Вижу нет страницы онлайн-записи. Клиенты ищут мастера вечером, когда вы не берёте трубку. Могу сделать страницу записи за 48 часов — от 7 900 ₽. Показать пример?"
        elif is_auto:
            product = "Карточка автосервиса + онлайн-запись"
            price = "6 900 ₽"
            reason = "Нет сайта → клиент ищет СТО в интернете и не находит. Нужна страница с услугами, ценами и формой записи."
            what = "Мини-сайт с услугами + форма записи + кнопки связи"
            opener = f"Здравствуйте. Нашёл ваш {niche or 'автосервис'} — нет страницы в интернете. Клиенты ищут СТО онлайн, не находят — звонят конкурентам. Сделаю страницу с ценами и онлайн-записью за 48ч. От 6 900 ₽. Актуально?"
        elif is_food:
            product = "Меню-бот + страница доставки"
            price = "9 900 ₽"
            reason = "Нет сайта → заказы только по телефону. Telegram-бот с меню закрывает заказы 24/7 без участия персонала."
            what = "Telegram-бот с меню + онлайн-заказ + уведомление владельцу"
            opener = f"Здравствуйте! Нашёл вас в интернете — принимаете заказы только по телефону? Сделаю Telegram-бот с меню: клиент выбирает, вы получаете уведомление. За 48 часов, от 9 900 ₽. Покажу пример?"
        elif is_fitness:
            product = "Бот записи на тренировки"
            price = "9 900 ₽"
            reason = "Нет сайта → запись через звонок или WhatsApp. Бот закрывает запись 24/7, шлёт напоминания, освобождает время тренера."
            what = "Telegram-бот с расписанием + запись + напоминания клиентам"
            opener = f"Здравствуйте. Вижу нет онлайн-записи на тренировки. Клиенты пишут в WhatsApp в любое время — это отнимает время. Сделаю бот: клиент сам записывается, вы получаете уведомление. 48 часов, от 9 900 ₽. Интересно?"
        elif is_b2b:
            product = "Продающая страница + форма заявки"
            price = "9 900 ₽"
            reason = "B2B без сайта = потеря доверия. Клиенты проверяют исполнителя онлайн перед звонком. Нужна страница с кейсами и формой."
            what = "Лендинг с кейсами + форма заявки + автоответ на email"
            opener = f"Здравствуйте. Нашёл вас по направлению {niche or 'услуги'} — нет сайта. В B2B клиент сначала ищет исполнителя онлайн. Сделаю страницу с кейсами и формой за 48 часов. От 9 900 ₽."
        else:
            # универсальный сервис (сантехник, электрик, ремонт и т.д.)
            product = "Цифровая точка заявки за 48 часов"
            price = "5 900 ₽" if not has_email else "7 900 ₽"
            reason = f"Нет сайта → клиент находит вас на картах, хочет оставить заявку онлайн — не может. Уходит к конкуренту у которого есть форма."
            what = "Мини-страница + форма заявки + уведомление в Telegram"
            opener = f"Здравствуйте. Нашёл вас на картах — занимаетесь {niche or 'услугами'}. Нет страницы для онлайн-заявок — клиенты уходят туда где можно оставить заявку в 2 клика. Сделаю за 48 часов. От 5 900 ₽. Показать пример?"

        return product, price, reason, opener, what

    # ── ДЫРА 2: сайт есть, но нет соцсетей/активности ──
    if site and "no_vk" in f:
        if is_beauty:
            product = "AI-контент для соцсетей + онлайн-запись"
            price = "12 900 ₽"
            reason = "Сайт есть, но нет соцсетей. Клиенты бьюти-ниши выбирают мастера по портфолио в VK/TG. Без постов — нет доверия."
            what = "30 постов с фото работ + AI-тексты + настройка VK/TG канала"
            opener = f"Здравствуйте. Сайт есть — хорошо. Но в {niche or 'вашей нише'} клиенты выбирают по портфолио в соцсетях. Сделаю 30 постов с AI-текстами за 3 дня. От 12 900 ₽. Актуально?"
        else:
            product = "AI-контент пакет — 30 постов за 3 дня"
            price = "9 900 ₽"
            reason = "Сайт есть, соцсети пустые. Клиенты проверяют активность компании перед звонком. 30 постов с AI-картинками закроют этот пробел."
            what = "30 постов для VK/TG + AI-картинки + контент-план на месяц"
            opener = f"Здравствуйте. Сайт есть, вижу соцсети не ведутся. Клиенты проверяют активность — видят тишину, звонят конкуренту. Сделаю 30 постов с AI-картинками за 3 дня. От 9 900 ₽."
        return product, price, reason, opener, what

    # ── ДЫРА 3: всё есть — продаём автоматизацию ──
    if is_beauty:
        product = "Telegram-бот онлайн-записи"
        price = "14 900 ₽"
        reason = "Сайт и соцсети есть. Следующий шаг — автоматизация записи. Бот принимает заявки 24/7, шлёт напоминания, снижает отмены на 30%."
        what = "Telegram-бот записи + напоминания + интеграция с расписанием"
        opener = "Здравствуйте. Вижу и сайт и соцсети — хорошая база. Следующий шаг: бот онлайн-записи. Клиент записывается в 3 клика в любое время. Снижает отмены на треть. От 14 900 ₽. Показать как работает?"
    elif is_food:
        product = "Telegram-бот заказов + автоматические рассылки"
        price = "19 900 ₽"
        reason = "Полная цифровая база. Продаём автоматизацию: бот принимает заказы, рассылки поднимают повторные продажи."
        what = "Бот заказов + автоматические акции + лояльность клиентов"
        opener = "Здравствуйте. Вижу хорошую цифровую базу. Следующий шаг — автоматизация: бот принимает заказы, автоматически шлёт акции постоянным клиентам. От 19 900 ₽. Интересно?"
    else:
        product = "AI Sales Patch — усиление заявки"
        price = "14 900 ₽"
        reason = "Сайт и соцсети есть. Продаём усиление конверсии: онлайн-запись, AI-чат, автоответы, скрипты переписки."
        what = "Онлайн-запись + AI-чат на сайте + скрипты ответов + аналитика"
        opener = f"Здравствуйте. Вижу и сайт и соцсети. Можно усилить — добавить онлайн-запись прямо с сайта и AI-чат который отвечает клиентам пока вы заняты. От 14 900 ₽. Показать пример?"

    return product, price, reason, opener, what


def migrate_operator_v2() -> None:
    init_db()
    with connect() as conn:
        _ensure_leads_column(conn, "created_at_msk TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "updated_at_msk TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "last_contact_at_msk TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "recommended_product TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "recommended_price TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "recommended_reason TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "source_label TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "what_to_sell TEXT NOT NULL DEFAULT ''")
        _ensure_leads_column(conn, "call_opener TEXT NOT NULL DEFAULT ''")

        rows = conn.execute(
            """
            SELECT id, created_at, updated_at, status, next_action,
                   opportunity_flags, website, phone, email, source, niche, name
            FROM leads
            """
        ).fetchall()

        for r in rows:
            product, price, reason, opener, what = _recommend_product(
                r["opportunity_flags"],
                r["website"],
                r["phone"],
                r["email"],
                r["niche"] if "niche" in r.keys() else "",
                r["name"] if "name" in r.keys() else "",
            )

            source = (r["source"] or "").lower()
            if source in ("osm", "overpass"):
                source_label = "OpenStreetMap / Overpass fallback"
            elif "2gis" in source:
                source_label = "2ГИС API"
            elif "yandex" in source:
                source_label = "Яндекс Карты API"
            else:
                source_label = r["source"] or "не указан"

            conn.execute(
                """
                UPDATE leads
                SET
                  status=?,
                  next_action=?,
                  created_at_msk=CASE WHEN created_at_msk='' THEN ? ELSE created_at_msk END,
                  updated_at_msk=CASE WHEN updated_at_msk='' THEN ? ELSE updated_at_msk END,
                  recommended_product=?,
                  recommended_price=?,
                  recommended_reason=?,
                  source_label=?,
                  what_to_sell=?,
                  call_opener=?
                WHERE id=?
                """,
                (
                    _status_ru(r["status"]),
                    _next_action_ru(r["next_action"]),
                    utc_to_msk(r["created_at"]) or now_msk(),
                    utc_to_msk(r["updated_at"]) or now_msk(),
                    product,
                    price,
                    reason,
                    source_label,
                    what,
                    opener,
                    r["id"],
                ),
            )


def has_contact(lead: object) -> bool:
    return bool(
        str(getattr(lead, "phone", "") or "").strip()
        or str(getattr(lead, "email", "") or "").strip()
        or str(getattr(lead, "website", "") or "").strip()
    )
