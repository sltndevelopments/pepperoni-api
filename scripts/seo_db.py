#!/usr/bin/env python3
"""
SEO Agent Database — SQLite schema and helpers.
Stores GSC + Yandex query data, opportunities, and generated content log.
DB file: data/seo_data.db (relative to repo root)
"""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "seo_data.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS gsc_queries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at  TEXT NOT NULL,
            date        TEXT NOT NULL,
            query       TEXT NOT NULL,
            page        TEXT,
            country     TEXT,
            device      TEXT,
            clicks      INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            ctr         REAL DEFAULT 0,
            position    REAL DEFAULT 0,
            UNIQUE(date, query, page, country, device)
        );

        CREATE TABLE IF NOT EXISTS yandex_queries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at  TEXT NOT NULL,
            date        TEXT NOT NULL,
            query       TEXT NOT NULL,
            clicks      INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            ctr         REAL DEFAULT 0,
            position    REAL DEFAULT 0,
            UNIQUE(date, query)
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            type        TEXT NOT NULL,  -- quick_growth | low_ctr | new_query | commercial_gap
            source      TEXT NOT NULL,  -- gsc | yandex
            query       TEXT NOT NULL,
            page        TEXT,
            position    REAL,
            impressions INTEGER,
            ctr         REAL,
            status      TEXT DEFAULT 'new',  -- new | in_progress | done | skipped
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS generated_content (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            type        TEXT NOT NULL,  -- article | geo_page | title_update | meta_update
            lang        TEXT NOT NULL,  -- ru | en
            query       TEXT,
            slug        TEXT,
            file_path   TEXT,
            title       TEXT,
            status      TEXT DEFAULT 'draft',  -- draft | published | rejected
            claude_model TEXT,
            tokens_used INTEGER
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            report_date TEXT NOT NULL,
            summary_md  TEXT,
            email_sent  INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_gsc_date   ON gsc_queries(date);
        CREATE INDEX IF NOT EXISTS idx_gsc_query  ON gsc_queries(query);
        CREATE INDEX IF NOT EXISTS idx_yandex_date ON yandex_queries(date);
        CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
    """)
    conn.commit()
    conn.close()
    print(f"✅ DB initialised at {DB_PATH}")


if __name__ == "__main__":
    init_db()
