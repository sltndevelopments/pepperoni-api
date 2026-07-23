"""SQLite-хранилище московских лидов. Без новых зависимостей."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from model import (
    DISTRIBUTORS,
    LOST_REASON_TO_STATUS,
    STATUSES,
    fmt_lead_id,
    next_business_deadline,
    utcnow,
    validate_status,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "moscow_leads.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    id             TEXT NOT NULL UNIQUE,
    source         TEXT NOT NULL,
    company        TEXT NOT NULL DEFAULT '',
    contact        TEXT NOT NULL DEFAULT '',
    phone          TEXT NOT NULL DEFAULT '',
    city           TEXT NOT NULL DEFAULT '',
    request        TEXT NOT NULL DEFAULT '',
    volume         TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'new',
    status_changed_at TEXT NOT NULL,
    next_step      TEXT NOT NULL DEFAULT '',
    deadline       TEXT,
    distributor    TEXT,
    note           TEXT NOT NULL DEFAULT '',
    lost_reason    TEXT,
    external_ref   TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_external
    ON leads(external_ref) WHERE external_ref IS NOT NULL AND external_ref != '';
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_deadline ON leads(deadline);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id    TEXT NOT NULL,
    at         TEXT NOT NULL,
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_lead ON events(lead_id);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Store:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _row(self, row: sqlite3.Row | None) -> dict | None:
        if not row:
            return None
        return dict(row)

    def create_lead(
        self,
        *,
        source: str,
        company: str = "",
        contact: str = "",
        phone: str = "",
        city: str = "",
        request: str = "",
        volume: str = "",
        note: str = "",
        external_ref: str | None = None,
        deadline: str | None = None,
        next_step: str = "связаться",
        actor: str = "system",
    ) -> dict:
        now = utcnow().isoformat()
        dl = deadline or next_business_deadline()
        with self._conn() as conn:
            if external_ref:
                existing = conn.execute(
                    "SELECT * FROM leads WHERE external_ref=?", (external_ref,)
                ).fetchone()
                if existing:
                    return dict(existing)
            cur = conn.execute(
                """INSERT INTO leads
                   (id, source, company, contact, phone, city, request, volume,
                    status, status_changed_at, next_step, deadline, distributor,
                    note, lost_reason, external_ref, created_at, updated_at)
                   VALUES ('', ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, NULL, ?, NULL, ?, ?, ?)""",
                (
                    source, company, contact, phone, city, request, volume,
                    now, next_step, dl, note, external_ref, now, now,
                ),
            )
            seq = int(cur.lastrowid)
            lead_id = fmt_lead_id(seq)
            conn.execute("UPDATE leads SET id=? WHERE seq=?", (lead_id, seq))
            conn.execute(
                "INSERT INTO events (lead_id, at, actor, action, detail) VALUES (?,?,?,?,?)",
                (lead_id, now, actor, "created", json.dumps({"source": source}, ensure_ascii=False)),
            )
            row = conn.execute("SELECT * FROM leads WHERE seq=?", (seq,)).fetchone()
        return dict(row)

    def get(self, lead_id: str) -> dict | None:
        with self._conn() as conn:
            return self._row(conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())

    def get_by_seq(self, seq: int) -> dict | None:
        with self._conn() as conn:
            return self._row(conn.execute("SELECT * FROM leads WHERE seq=?", (seq,)).fetchone())

    def list_leads(
        self,
        *,
        status: str | None = None,
        active_only: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        q = "SELECT * FROM leads WHERE 1=1"
        args: list[Any] = []
        if status:
            q += " AND status=?"
            args.append(status)
        if active_only:
            q += " AND status NOT IN ('won','lost','no_demand')"
        q += " ORDER BY updated_at DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(q, args).fetchall()]

    def set_status(
        self,
        lead_id: str,
        status: str,
        *,
        actor: str = "arbi",
        distributor: str | None = None,
        clear_distributor: bool = False,
        lost_reason: str | None = None,
        note: str | None = None,
        next_step: str | None = None,
        deadline: str | None = None,
        bump_status_changed: bool = True,
    ) -> dict:
        if not validate_status(status):
            raise ValueError(f"invalid status: {status}")
        if status == "passed_to_distributor":
            if distributor not in DISTRIBUTORS:
                raise ValueError(f"distributor required: {DISTRIBUTORS}")
        lead = self.get(lead_id)
        if not lead:
            raise KeyError(lead_id)
        now = utcnow().isoformat()
        fields: dict[str, Any] = {
            "status": status,
            "updated_at": now,
        }
        if bump_status_changed and status != lead.get("status"):
            fields["status_changed_at"] = now
        if clear_distributor:
            fields["distributor"] = None
        elif distributor is not None:
            fields["distributor"] = distributor
        if lost_reason is not None:
            fields["lost_reason"] = lost_reason
        if note is not None:
            fields["note"] = note
        if next_step is not None:
            fields["next_step"] = next_step
        if deadline is not None:
            fields["deadline"] = deadline
        # Авто-шаг по статусу, если не задан явно.
        if next_step is None:
            defaults = {
                "contacted": "уточнить потребность / образцы",
                "samples_sent": "дождаться ОС / назначить встречу",
                "meeting_done": "решить: дистр или прямая отгрузка",
                "passed_to_distributor": "запросить ОС у дистрибьютора",
                "first_shipment": "контроль повторной отгрузки",
                "repeat_shipment": "сопровождение",
                "won": "—",
                "lost": "—",
                "no_demand": "—",
            }
            if status in defaults:
                fields["next_step"] = defaults[status]
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE leads SET {sets} WHERE id=?",
                (*fields.values(), lead_id),
            )
            conn.execute(
                "INSERT INTO events (lead_id, at, actor, action, detail) VALUES (?,?,?,?,?)",
                (
                    lead_id,
                    now,
                    actor,
                    "status",
                    json.dumps(
                        {
                            "from": lead["status"],
                            "to": status,
                            "distributor": None if clear_distributor else distributor,
                            "lost_reason": lost_reason,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        return self.get(lead_id)  # type: ignore[return-value]

    def apply_lost_reason(self, lead_id: str, reason_key: str, *, actor: str = "arbi") -> dict:
        status = LOST_REASON_TO_STATUS.get(reason_key)
        if not status:
            raise ValueError(f"unknown lost reason: {reason_key}")
        return self.set_status(lead_id, status, actor=actor, lost_reason=reason_key)

    def bump_deadline(self, lead_id: str, days: int = 3, *, actor: str = "arbi") -> dict:
        from model import extend_deadline

        lead = self.get(lead_id)
        if not lead:
            raise KeyError(lead_id)
        new_dl = extend_deadline(lead.get("deadline"), days=days)
        now = utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE leads SET deadline=?, updated_at=? WHERE id=?",
                (new_dl, now, lead_id),
            )
            conn.execute(
                "INSERT INTO events (lead_id, at, actor, action, detail) VALUES (?,?,?,?,?)",
                (lead_id, now, actor, "deadline", json.dumps({"deadline": new_dl}, ensure_ascii=False)),
            )
        return self.get(lead_id)  # type: ignore[return-value]

    def take_back_from_distributor(self, lead_id: str, *, actor: str = "arbi") -> dict:
        return self.set_status(
            lead_id,
            "meeting_done",
            actor=actor,
            clear_distributor=True,
            next_step="вернуть в работу / связаться с клиентом",
            deadline=next_business_deadline(),
        )

    def mark_os_requested(self, lead_id: str, *, actor: str = "arbi") -> dict:
        now = utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE leads SET next_step=?, updated_at=? WHERE id=?",
                ("ожидаем ОС от дистрибьютора", now, lead_id),
            )
            conn.execute(
                "INSERT INTO events (lead_id, at, actor, action, detail) VALUES (?,?,?,?,?)",
                (lead_id, now, actor, "ask_os", "{}"),
            )
        return self.get(lead_id)  # type: ignore[return-value]

    def stuck_at_distributor(self, *, hours: int = 72) -> list[dict]:
        cutoff = (utcnow().timestamp() - hours * 3600)
        out = []
        for lead in self.list_leads(status="passed_to_distributor", limit=500):
            try:
                changed = datetime_from_iso(lead["status_changed_at"])
            except Exception:
                continue
            if changed.timestamp() <= cutoff:
                out.append(lead)
        return out

    def due_reminders(self) -> list[dict]:
        today = (utcnow() + __import__("datetime").timedelta(hours=3)).date().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM leads
                   WHERE status NOT IN ('won','lost','no_demand')
                     AND deadline IS NOT NULL AND deadline <= ?
                   ORDER BY deadline ASC""",
                (today,),
            ).fetchall()
        return [dict(r) for r in rows]

    def events(self, lead_id: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE lead_id=? ORDER BY id ASC LIMIT ?",
                (lead_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_meta(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def stats_since(self, since_iso: str) -> dict[str, int]:
        """Счётчики по событиям смены статуса с since_iso."""
        with self._conn() as conn:
            created = conn.execute(
                "SELECT COUNT(*) AS n FROM leads WHERE created_at>=?", (since_iso,)
            ).fetchone()["n"]
            contacted = conn.execute(
                """SELECT COUNT(*) AS n FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='contacted'""",
                (since_iso,),
            ).fetchone()["n"]
            samples = conn.execute(
                """SELECT COUNT(*) AS n FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='samples_sent'""",
                (since_iso,),
            ).fetchone()["n"]
            meetings = conn.execute(
                """SELECT COUNT(*) AS n FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='meeting_done'""",
                (since_iso,),
            ).fetchone()["n"]
            first = conn.execute(
                """SELECT COUNT(*) AS n FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='first_shipment'""",
                (since_iso,),
            ).fetchone()["n"]
            repeat = conn.execute(
                """SELECT COUNT(*) AS n FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='repeat_shipment'""",
                (since_iso,),
            ).fetchone()["n"]
            dist_rows = conn.execute(
                """SELECT json_extract(detail,'$.distributor') AS d, COUNT(*) AS n
                   FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='passed_to_distributor'
                   GROUP BY d""",
                (since_iso,),
            ).fetchall()
        dist = {r["d"] or "?": r["n"] for r in dist_rows}
        active = len(self.list_leads(active_only=True, limit=5000))
        return {
            "new": created,
            "contacted": contacted,
            "samples_sent": samples,
            "meetings": meetings,
            "first_shipment": first,
            "repeat_shipment": repeat,
            "in_work": active,
            "dist_gfc": dist.get("GFC", 0),
            "dist_sweetlife": dist.get("SweetLife", 0),
            "dist_direct": dist.get("direct", 0),
            "dist_total": sum(dist.values()),
        }

    def conversion_new_to_first(self, *, days: int = 30) -> float:
        from datetime import timedelta

        since = (utcnow() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            created = conn.execute(
                "SELECT COUNT(*) AS n FROM leads WHERE created_at>=?", (since,)
            ).fetchone()["n"]
            first = conn.execute(
                """SELECT COUNT(DISTINCT lead_id) AS n FROM events
                   WHERE action='status' AND at>=?
                     AND json_extract(detail,'$.to')='first_shipment'""",
                (since,),
            ).fetchone()["n"]
        if not created:
            return 0.0
        return round(100.0 * first / created, 1)


def datetime_from_iso(value: str):
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# Validate statuses exist at import time (grep-friendly constant use).
assert set(STATUSES) >= {
    "new", "contacted", "samples_sent", "meeting_done", "passed_to_distributor",
    "first_shipment", "repeat_shipment", "won", "lost", "no_demand",
}
