"""
SQLite-хранилище: лиды, инбокс, черновики, сигналы.

Все runtime-данные в sales-agent/data/ — изолированы от public/ и Vercel.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "agent.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS leads (
    id          TEXT PRIMARY KEY,
    inn         TEXT,
    name        TEXT NOT NULL,
    region      TEXT,
    tier        TEXT DEFAULT '—',
    fit_score   INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'new',
    source      TEXT,
    profile     TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_tier ON leads(tier);
CREATE INDEX IF NOT EXISTS idx_leads_inn ON leads(inn);

CREATE TABLE IF NOT EXISTS threads (
    id              TEXT PRIMARY KEY,
    lead_id         TEXT REFERENCES leads(id),
    channel         TEXT NOT NULL,
    external_id     TEXT,
    status          TEXT DEFAULT 'open',
    last_message_at TEXT,
    meta            TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    thread_id   TEXT REFERENCES threads(id),
    direction   TEXT NOT NULL,
    channel     TEXT NOT NULL,
    subject     TEXT,
    body        TEXT,
    meta        TEXT DEFAULT '{}',
    gate_status TEXT DEFAULT 'internal',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);

CREATE TABLE IF NOT EXISTS drafts (
    id              TEXT PRIMARY KEY,
    lead_id         TEXT REFERENCES leads(id),
    channel         TEXT NOT NULL,
    subject         TEXT,
    body            TEXT NOT NULL,
    sequence_step   INTEGER DEFAULT 0,
    sequence_id     TEXT,
    status          TEXT DEFAULT 'draft',
    fit_check       TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);

CREATE TABLE IF NOT EXISTS approvals (
    id          TEXT PRIMARY KEY,
    draft_id    TEXT REFERENCES drafts(id),
    action      TEXT NOT NULL,
    title       TEXT,
    detail      TEXT,
    payload     TEXT DEFAULT '{}',
    status      TEXT DEFAULT 'pending',
    decided_by  TEXT,
    created_at  TEXT NOT NULL,
    decided_at  TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    payload     TEXT DEFAULT '{}',
    processed   INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_processed ON signals(processed);

CREATE TABLE IF NOT EXISTS audit_log (
    id          TEXT PRIMARY KEY,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    detail      TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS orchestrator_runs (
    id          TEXT PRIMARY KEY,
    phase       TEXT,
    plan        TEXT DEFAULT '{}',
    result      TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    key          TEXT PRIMARY KEY,
    content_hash TEXT,
    sent_at      TEXT NOT NULL,
    count        INTEGER DEFAULT 1
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class Store:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self):
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

    def upsert_lead(
        self,
        name: str,
        *,
        inn: str | None = None,
        region: str | None = None,
        tier: str = "—",
        fit_score: int = 0,
        status: str = "new",
        source: str | None = None,
        profile: dict | None = None,
        lead_id: str | None = None,
    ) -> str:
        now = _now()
        profile_json = json.dumps(profile or {}, ensure_ascii=False)
        with self._conn() as conn:
            if lead_id:
                conn.execute(
                    """UPDATE leads SET name=?, inn=?, region=?, tier=?, fit_score=?,
                       status=?, source=?, profile=?, updated_at=? WHERE id=?""",
                    (name, inn, region, tier, fit_score, status, source, profile_json, now, lead_id),
                )
                return lead_id
            if inn:
                row = conn.execute(
                    "SELECT id, name, tier, fit_score, status, profile FROM leads WHERE inn=?",
                    (inn,),
                ).fetchone()
                if row:
                    lid = row["id"]
                    # --- merge rules for discovery re-import ---
                    # status  : never overwrite (contacted/handed_off/bounced must survive)
                    merged_status = row["status"] or status
                    # name    : only fill if current is empty / placeholder
                    cur_name = (row["name"] or "").strip()
                    merged_name = cur_name if cur_name and cur_name not in ("", "Без названия") else name
                    # tier    : only promote, never demote
                    _tier_rank = {"S": 4, "A": 3, "B": 2, "C": 1, "—": 0}
                    merged_tier = (
                        tier if _tier_rank.get(tier, 0) > _tier_rank.get(row["tier"] or "—", 0)
                        else (row["tier"] or tier)
                    )
                    # fit_score: only raise
                    merged_score = max(fit_score, row["fit_score"] or 0)
                    # profile : merge — _agent is sacred, new fields fill gaps
                    try:
                        old_p = json.loads(row["profile"] or "{}")
                    except Exception:
                        old_p = {}
                    new_p = dict(profile or {})
                    # preserve _agent entirely
                    if "_agent" in old_p:
                        new_p["_agent"] = old_p["_agent"]
                    # keep old values for keys not in new profile (e.g. existing contacts)
                    for k, v in old_p.items():
                        if k not in new_p and k != "_agent":
                            new_p[k] = v
                    merged_profile = json.dumps(new_p, ensure_ascii=False)
                    conn.execute(
                        """UPDATE leads SET name=?, region=?, tier=?, fit_score=?,
                           status=?, source=?, profile=?, updated_at=? WHERE id=?""",
                        (merged_name, region, merged_tier, merged_score,
                         merged_status, source, merged_profile, now, lid),
                    )
                    return lid
            lid = lead_id or _new_id()
            conn.execute(
                """INSERT INTO leads (id, inn, name, region, tier, fit_score, status, source, profile, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (lid, inn, name, region, tier, fit_score, status, source, profile_json, now, now),
            )
            return lid

    def list_leads(
        self,
        *,
        status: str | None = None,
        tier: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        q = "SELECT * FROM leads WHERE 1=1"
        args: list[Any] = []
        if status:
            q += " AND status=?"
            args.append(status)
        if tier:
            q += " AND tier=?"
            args.append(tier)
        q += " ORDER BY fit_score DESC, updated_at DESC LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        with self._conn() as conn:
            rows = conn.execute(q, args).fetchall()
        return [_row_lead(r) for r in rows]

    def get_lead(self, lead_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return _row_lead(row) if row else None

    def add_signal(self, source: str, signal_type: str, payload: dict) -> str:
        sid = _new_id()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO signals (id, source, signal_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (sid, source, signal_type, json.dumps(payload, ensure_ascii=False), _now()),
            )
        return sid

    def unprocessed_signals(self, limit: int = 100) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM signals WHERE processed=0 ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_signal(r) for r in rows]

    def mark_signal_processed(self, signal_id: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE signals SET processed=1 WHERE id=?", (signal_id,))

    def add_inbound(
        self,
        channel: str,
        body: str,
        *,
        subject: str | None = None,
        lead_id: str | None = None,
        external_id: str | None = None,
        meta: dict | None = None,
    ) -> str:
        """Сообщение во входящий инбокс."""
        now = _now()
        tid = _new_id()
        mid = _new_id()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO threads (id, lead_id, channel, external_id, last_message_at, meta)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tid, lead_id, channel, external_id, now, json.dumps(meta or {}, ensure_ascii=False)),
            )
            conn.execute(
                """INSERT INTO messages (id, thread_id, direction, channel, subject, body, meta, gate_status, created_at)
                   VALUES (?, ?, 'in', ?, ?, ?, ?, 'internal', ?)""",
                (mid, tid, channel, subject, body, json.dumps(meta or {}, ensure_ascii=False), now),
            )
        return mid

    def add_outbound(
        self,
        lead_id: str,
        channel: str,
        body: str,
        *,
        subject: str | None = None,
        external_id: str | None = None,
        meta: dict | None = None,
    ) -> str:
        """Сообщение в исходящий лог (после реальной отправки).

        Переиспользует открытый thread по lead_id+channel, если есть,
        иначе создаёт новый — симметрично add_inbound.
        """
        now = _now()
        mid = _new_id()
        with self._conn() as conn:
            tid = None
            if lead_id:
                row = conn.execute(
                    """SELECT id FROM threads WHERE lead_id=? AND channel=?
                       ORDER BY last_message_at DESC LIMIT 1""",
                    (lead_id, channel),
                ).fetchone()
                if row:
                    tid = row["id"]
            if not tid:
                tid = _new_id()
                conn.execute(
                    """INSERT INTO threads (id, lead_id, channel, external_id, last_message_at, meta)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (tid, lead_id, channel, external_id, now, json.dumps(meta or {}, ensure_ascii=False)),
                )
            else:
                conn.execute("UPDATE threads SET last_message_at=? WHERE id=?", (now, tid))
            conn.execute(
                """INSERT INTO messages (id, thread_id, direction, channel, subject, body, meta, gate_status, created_at)
                   VALUES (?, ?, 'out', ?, ?, ?, ?, 'sent', ?)""",
                (mid, tid, channel, subject, body, json.dumps(meta or {}, ensure_ascii=False), now),
            )
        return mid

    def patch_message_meta(self, message_id: str, patch: dict) -> None:
        with self._conn() as conn:
            row = conn.execute("SELECT meta FROM messages WHERE id=?", (message_id,)).fetchone()
            if not row:
                return
            meta = _parse_json_field(row["meta"])
            meta.update(patch)
            conn.execute(
                "UPDATE messages SET meta=? WHERE id=?",
                (json.dumps(meta, ensure_ascii=False), message_id),
            )

    def inbox(self, limit: int = 50, *, unprocessed_interest: bool = False) -> list[dict]:
        with self._conn() as conn:
            q = """SELECT m.*, t.lead_id, l.name AS lead_name
                   FROM messages m
                   JOIN threads t ON m.thread_id = t.id
                   LEFT JOIN leads l ON t.lead_id = l.id
                   WHERE m.direction='in'"""
            if unprocessed_interest:
                q += " AND (m.meta NOT LIKE '%interest_scanned%' OR m.meta IS NULL OR m.meta='{}')"
            q += " ORDER BY m.created_at DESC LIMIT ?"
            rows = conn.execute(q, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def create_draft(
        self,
        lead_id: str,
        channel: str,
        body: str,
        *,
        subject: str | None = None,
        sequence_step: int = 0,
        sequence_id: str | None = None,
        fit_check: dict | None = None,
        status: str = "draft",
    ) -> str:
        now = _now()
        did = _new_id()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO drafts (id, lead_id, channel, subject, body, sequence_step, sequence_id,
                   status, fit_check, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    did, lead_id, channel, subject, body, sequence_step, sequence_id,
                    status, json.dumps(fit_check or {}, ensure_ascii=False), now, now,
                ),
            )
        return did

    def list_drafts(self, status: str | None = None, limit: int = 50) -> list[dict]:
        q = """SELECT d.*, l.name AS lead_name, l.tier, l.fit_score
               FROM drafts d LEFT JOIN leads l ON d.lead_id = l.id WHERE 1=1"""
        args: list[Any] = []
        if status:
            q += " AND d.status=?"
            args.append(status)
        q += " ORDER BY d.created_at DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            rows = conn.execute(q, args).fetchall()
        return [_row_draft(r) for r in rows]

    def get_draft(self, draft_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT d.*, l.name AS lead_name FROM drafts d
                   LEFT JOIN leads l ON d.lead_id = l.id WHERE d.id=?""",
                (draft_id,),
            ).fetchone()
        return _row_draft(row) if row else None

    def update_draft_status(self, draft_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE drafts SET status=?, updated_at=? WHERE id=?",
                (status, _now(), draft_id),
            )

    def create_approval(
        self,
        draft_id: str,
        action: str,
        title: str,
        detail: str = "",
        payload: dict | None = None,
    ) -> str:
        aid = _new_id()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO approvals (id, draft_id, action, title, detail, payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (aid, draft_id, action, title, detail, json.dumps(payload or {}, ensure_ascii=False), _now()),
            )
            conn.execute(
                "UPDATE drafts SET status='pending', updated_at=? WHERE id=?",
                (_now(), draft_id),
            )
        return aid

    def list_approvals(self, status: str = "pending", limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT a.*, d.channel, d.subject, d.body, d.lead_id, l.name AS lead_name
                   FROM approvals a
                   JOIN drafts d ON a.draft_id = d.id
                   LEFT JOIN leads l ON d.lead_id = l.id
                   WHERE a.status=? ORDER BY a.created_at ASC LIMIT ?""",
                (status, limit),
            ).fetchall()
        return [_row_approval(r) for r in rows]

    def decide_approval(self, approval_id: str, approved: bool, decided_by: str = "console") -> dict | None:
        status = "approved" if approved else "rejected"
        now = _now()
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if not row or row["status"] != "pending":
                return None
            conn.execute(
                "UPDATE approvals SET status=?, decided_by=?, decided_at=? WHERE id=?",
                (status, decided_by, now, approval_id),
            )
            draft_status = "approved" if approved else "rejected"
            conn.execute(
                "UPDATE drafts SET status=?, updated_at=? WHERE id=?",
                (draft_status, now, row["draft_id"]),
            )
        return _row_approval(row)

    def take_approved_for_send(self) -> list[dict]:
        """Одобренные черновики, готовые к отправке (вызывается после гейта)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT d.*, a.id AS approval_id, a.action, l.name AS lead_name
                   FROM drafts d
                   JOIN approvals a ON a.draft_id = d.id AND a.status='approved'
                   JOIN leads l ON d.lead_id = l.id
                   WHERE d.status='approved'""",
            ).fetchall()
        return [_row_draft(r) for r in rows]

    def mark_draft_sent(self, draft_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE drafts SET status='sent', updated_at=? WHERE id=?",
                (_now(), draft_id),
            )

    def audit(self, actor: str, action: str, entity_type: str | None = None,
              entity_id: str | None = None, detail: dict | None = None) -> str:
        aid = _new_id()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO audit_log (id, actor, action, entity_type, entity_id, detail, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (aid, actor, action, entity_type, entity_id,
                 json.dumps(detail or {}, ensure_ascii=False), _now()),
            )
        return aid

    def audit_tail(self, limit: int = 30) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_audit(self, actor: str, action: str, *, limit: int = 20,
                     hours: int = 24) -> list[dict]:
        """Свежие записи аудита по actor+action за последние `hours` часов."""
        from datetime import datetime, timedelta, timezone
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM audit_log
                   WHERE actor=? AND action=? AND created_at>=?
                   ORDER BY created_at DESC LIMIT ?""",
                (actor, action, since, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_orchestrator_run(self, phase: str, plan: dict, result: dict) -> str:
        rid = _new_id()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO orchestrator_runs (id, phase, plan, result, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (rid, phase, json.dumps(plan, ensure_ascii=False),
                 json.dumps(result, ensure_ascii=False), _now()),
            )
        return rid

    def list_hot_leads(self, limit: int = 20) -> list[dict]:
        hot = ("hot", "escalated", "replied", "meeting", "proposal")
        placeholders = ",".join("?" * len(hot))
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT * FROM leads WHERE status IN ({placeholders})
                    ORDER BY updated_at DESC LIMIT ?""",
                (*hot, limit),
            ).fetchall()
        return [_row_lead(r) for r in rows]

    def stats(self) -> dict:
        with self._conn() as conn:
            leads = conn.execute("SELECT COUNT(*) AS c FROM leads").fetchone()["c"]
            pending = conn.execute(
                "SELECT COUNT(*) AS c FROM approvals WHERE status='pending'"
            ).fetchone()["c"]
            drafts = conn.execute(
                "SELECT COUNT(*) AS c FROM drafts WHERE status IN ('draft','pending')"
            ).fetchone()["c"]
            inbox_n = conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE direction='in'"
            ).fetchone()["c"]
            signals = conn.execute(
                "SELECT COUNT(*) AS c FROM signals WHERE processed=0"
            ).fetchone()["c"]
            hot_n = conn.execute(
                "SELECT COUNT(*) AS c FROM leads WHERE status IN ('hot','escalated','replied','meeting','proposal')"
            ).fetchone()["c"]
        return {
            "leads": leads,
            "hot_leads": hot_n,
            "pending_approvals": pending,
            "open_drafts": drafts,
            "inbox_messages": inbox_n,
            "unprocessed_signals": signals,
        }

    # ------------------------------------------------------------------ #
    #  Журнал уведомлений — дедупликация проактивных пушей                #
    # ------------------------------------------------------------------ #

    def should_notify(
        self,
        key: str,
        content_hash: str,
        cooldown_hours: float = 24.0,
    ) -> bool:
        """True если нужно слать уведомление.

        Логика (три условия, любое достаточно):
          1. Ключа ещё нет в журнале (первый раз).
          2. content_hash изменился — есть что-то новое.
          3. Прошло ≥ cooldown_hours с последней отправки.
        Если cooldown_hours == 0 — проверяется только хэш (без временного лимита).
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT content_hash, sent_at FROM notifications WHERE key=?",
                (key,),
            ).fetchone()
        if row is None:
            return True
        if row["content_hash"] != content_hash:
            return True
        if cooldown_hours <= 0:
            return False
        try:
            prev = datetime.fromisoformat(row["sent_at"])
        except Exception:
            return True
        elapsed = (datetime.now(timezone.utc) - prev).total_seconds()
        return elapsed >= cooldown_hours * 3600

    def record_notification(self, key: str, content_hash: str) -> None:
        """UPSERT по key — обновить хэш, время и счётчик."""
        now = _now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO notifications (key, content_hash, sent_at, count)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(key) DO UPDATE SET
                     content_hash = excluded.content_hash,
                     sent_at      = excluded.sent_at,
                     count        = notifications.count + 1""",
                (key, content_hash, now),
            )


def _parse_json_field(val: str | None) -> dict:
    if not val:
        return {}
    try:
        return json.loads(val)
    except Exception:
        return {}


def _row_lead(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["profile"] = _parse_json_field(d.get("profile"))
    return d


def _row_draft(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["fit_check"] = _parse_json_field(d.get("fit_check"))
    return d


def _row_approval(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["payload"] = _parse_json_field(d.get("payload"))
    return d


def _row_signal(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["payload"] = _parse_json_field(d.get("payload"))
    return d
