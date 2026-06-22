from __future__ import annotations

import csv
import glob
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("app/data/cockpit.sqlite3")


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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
        new = conn.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0]
        interested = conn.execute("SELECT COUNT(*) FROM leads WHERE status IN ('interested','example_requested','offer_sent','follow_up')").fetchone()[0]
        paid = conn.execute("SELECT COUNT(*) FROM leads WHERE status='paid'").fetchone()[0]
    return {"total": total, "new": new, "interested": interested, "paid": paid}


def list_leads(status: str = "", q: str = "", city: str = "") -> list[dict[str, Any]]:
    init_db()
    where = []
    params: dict[str, Any] = {}

    if status:
        where.append("status = :status")
        params["status"] = status

    if city:
        where.append("city = :city")
        params["city"] = city

    if q:
        where.append("(name LIKE :q OR phone LIKE :q OR email LIKE :q OR website LIKE :q OR priority_reason LIKE :q)")
        params["q"] = f"%{q}%"

    sql = "SELECT * FROM leads"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sales_priority DESC, lead_score DESC, id DESC LIMIT 500"

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
