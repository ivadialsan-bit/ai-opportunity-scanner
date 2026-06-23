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
    return {"total": total, "new": new, "interested": interested, "paid": paid}


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
        return row_to_dict(conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())


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


def _recommend_product(flags: str, website: str, phone: str, email: str) -> tuple[str, str, str]:
    f = (flags or "").lower()
    site = (website or "").strip()
    has_phone = bool((phone or "").strip())
    has_email = bool((email or "").strip())

    if "no_website" in f or not site:
        if has_phone and has_email:
            return (
                "Цифровая точка заявки за 48 часов",
                "9 900 ₽",
                "Нет сайта/страницы заявки, но есть телефон и email. Быстрее всего продать мини-страницу, кнопки связи, FAQ и учёт заявок.",
            )
        return (
            "Мини-точка заявки за 48 часов",
            "5 900 ₽",
            "Нет сайта/страницы заявки. Нужен минимальный пилот: страница, кнопка связи, 5 FAQ и первый скрипт ответа.",
        )

    if "website_present" in f or site:
        return (
            "AI Sales Patch для существующего сайта",
            "14 900 ₽",
            "Сайт есть. Продавать не сайт с нуля, а усиление заявки: CTA, FAQ, тексты услуг, скрипт переписки и таблицу учёта.",
        )

    return (
        "Диагностика цифровой точки заявки",
        "5 900 ₽",
        "Данных мало. Начинать с ручной диагностики карточки/сайта и короткого мини-пилота.",
    )


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

        rows = conn.execute(
            """
            SELECT id, created_at, updated_at, status, next_action,
                   opportunity_flags, website, phone, email, source
            FROM leads
            """
        ).fetchall()

        for r in rows:
            product, price, reason = _recommend_product(
                r["opportunity_flags"],
                r["website"],
                r["phone"],
                r["email"],
            )

            source = (r["source"] or "").lower()
            if source in ("osm", "overpass"):
                source_label = "OpenStreetMap / Overpass fallback"
            elif source == "2gis":
                source_label = "2ГИС API"
            elif source == "yandex":
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
                  source_label=?
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
                    r["id"],
                ),
            )


def has_contact(lead: object) -> bool:
    return bool(
        str(getattr(lead, "phone", "") or "").strip()
        or str(getattr(lead, "email", "") or "").strip()
        or str(getattr(lead, "website", "") or "").strip()
    )
