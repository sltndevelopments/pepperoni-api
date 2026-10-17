#!/usr/bin/env python3
"""Export GSC + Yandex query data as a tar on stdout.

Public repo: stdout is the tar only. Never print queries, URLs, or API
bodies. Counts are printed by the sealer from meta.txt. Errors are
fixed strings; tracebacklimit is 0 so an unexpected exception cannot
leak a stack or message into Actions logs.
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.tracebacklimit = 0

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_gsc_queries import (  # noqa: E402
    SITE_URL,
    _load_gsc_key,
    get_access_token,
)
from fetch_yandex_queries import (  # noqa: E402
    api_get,
    fetch_queries as yandex_popular,
    resolve_host_id,
    resolve_user_id,
)
import fetch_yandex_queries as yandex_mod  # noqa: E402

DAYS = 90
GSC_ROW_CAP = 25000
HTTP_TIMEOUT = 8
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 0.4
UNAVAILABLE = "unavailable"


def _fail(code: int, msg: str) -> int:
    sys.stderr.write(f"{msg}\n")
    return code


@contextmanager
def _quiet_stderr():
    old = sys.stderr
    sys.stderr = io.StringIO()
    try:
        yield
    finally:
        sys.stderr = old


@contextmanager
def _short_timeout():
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(HTTP_TIMEOUT)
    try:
        yield
    finally:
        socket.setdefaulttimeout(old)


def _retry(fn):
    last: BaseException | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF * (2 ** attempt))
    assert last is not None
    raise last


def _http_json(url: str, *, token: str | None = None, oauth: str | None = None,
               data: bytes | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if oauth:
        headers["Authorization"] = f"OAuth {oauth}"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError:
        raise RuntimeError("http")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise RuntimeError("http")


def _tar_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w|") as tf:
        for name, blob in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(blob)
            info.mode = 0o600
            tf.addfile(info, io.BytesIO(blob))
    return buf.getvalue()


def _gsc_window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    end = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    start = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    return start, end


def _yandex_window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    end = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    start = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    return start, end


def fetch_gsc_analytics(token: str, start: str, end: str) -> list[dict]:
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(SITE_URL, safe='')}/searchAnalytics/query"
    )
    rows: list[dict] = []
    start_row = 0
    while len(rows) < GSC_ROW_CAP:
        remain = min(5000, GSC_ROW_CAP - len(rows))
        body = json.dumps({
            "startDate": start,
            "endDate": end,
            "dimensions": ["query", "page", "country", "device"],
            "rowLimit": remain,
            "startRow": start_row,
        }).encode()
        data = _http_json(url, token=token, data=body)
        batch = data.get("rows") or []
        rows.extend(batch)
        if len(batch) < remain:
            break
        start_row += remain
    return rows[:GSC_ROW_CAP]


def fetch_gsc_index_counts(token: str) -> tuple[int, int]:
    """Indexed ≈ unique pages in analytics; excluded from sitemap submitted."""
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(SITE_URL, safe='')}/sitemaps"
    )
    data = _http_json(url, token=token)
    submitted = 0
    for sm in data.get("sitemap") or []:
        for content in sm.get("contents") or []:
            try:
                submitted += int(content.get("submitted") or 0)
            except (TypeError, ValueError):
                continue
    return submitted, 0


def normalize_gsc_rows(raw: list[dict]) -> list[dict]:
    out = []
    for row in raw:
        keys = row.get("keys") or []
        out.append({
            "query": keys[0] if len(keys) > 0 else "",
            "page": keys[1] if len(keys) > 1 else "",
            "country": keys[2] if len(keys) > 2 else "",
            "device": keys[3] if len(keys) > 3 else "",
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position", 0),
        })
    return out


def normalize_yandex_rows(raw: list[dict]) -> list[dict]:
    out = []
    for q in raw:
        text = q.get("query_text") or ""
        raw_ind = q.get("indicators") or {}
        if isinstance(raw_ind, dict):
            ind = raw_ind
        else:
            ind = {
                item["query_indicator"]: item["value"]
                for item in raw_ind
                if isinstance(item, dict)
                and "query_indicator" in item
                and "value" in item
            }
        pos = ind.get("AVG_SHOW_POSITION")
        if pos in (None, "", 0, 0.0, "0", "0.0"):
            pos = None
        else:
            try:
                pos = float(pos)
            except (TypeError, ValueError):
                pos = None
        out.append({
            "query": text,
            "shows": int(float(ind.get("TOTAL_SHOWS", 0) or 0)),
            "clicks": int(float(ind.get("TOTAL_CLICKS", 0) or 0)),
            "avg_position": pos,
        })
    return out


def fetch_yandex_url_queries(token: str, user_id: str, host_id: str,
                             date_from: str, date_to: str) -> list[dict]:
    """Per-URL queries if Webmaster exposes them; empty when the API has none."""
    host = urllib.parse.quote(host_id, safe="")
    path = (
        f"/user/{user_id}/hosts/{host}/search-queries/popular-by-url"
        f"?query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS"
        f"&query_indicator=AVG_SHOW_POSITION"
        f"&order_by=TOTAL_SHOWS"
        f"&date_from={date_from}&date_to={date_to}&limit=1&offset=0"
    )
    with _quiet_stderr():
        data = api_get(token, path)
    if not data or data.get("error_code") or "queries" not in data:
        return []
    rows = []
    for item in data.get("queries") or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "url": item.get("url") or item.get("page") or "",
            "query": item.get("query_text") or item.get("query") or "",
            "shows": item.get("shows") or 0,
            "clicks": item.get("clicks") or 0,
            "avg_position": item.get("avg_position"),
        })
    return rows


def fetch_yandex_index_counts(token: str, user_id: str, host_id: str) -> tuple[int, int]:
    host = urllib.parse.quote(host_id, safe="")
    with _quiet_stderr():
        data = api_get(token, f"/user/{user_id}/hosts/{host}/summary")
    if not data:
        raise RuntimeError("yandex-summary")
    try:
        indexed = int(data.get("searchable_pages_count") or 0)
        excluded = int(data.get("excluded_pages_count") or 0)
    except (TypeError, ValueError):
        raise RuntimeError("yandex-summary")
    return indexed, excluded


def collect_gsc(sa_raw: str) -> dict:
    def _go() -> dict:
        sa = json.loads(sa_raw)
        with _quiet_stderr():
            gsc_token = get_access_token(sa)
        gsc_start, gsc_end = _gsc_window()
        raw_gsc = fetch_gsc_analytics(gsc_token, gsc_start, gsc_end)
        sitemap_submitted, _ = fetch_gsc_index_counts(gsc_token)
        gsc_rows = normalize_gsc_rows(raw_gsc)
        gsc_indexed = len({r["page"] for r in gsc_rows if r.get("page")})
        gsc_excluded = max(0, sitemap_submitted - gsc_indexed) if sitemap_submitted else 0
        return {
            "rows": gsc_rows,
            "indexed": gsc_indexed,
            "excluded": gsc_excluded,
        }
    return _retry(_go)


def collect_yandex(ya_token: str) -> dict:
    def _go() -> dict:
        with _short_timeout(), _quiet_stderr():
            user_id = resolve_user_id(ya_token)
            if not user_id:
                raise RuntimeError("yandex")
            host_id = resolve_host_id(ya_token, user_id)
            if not host_id:
                raise RuntimeError("yandex")
            yandex_mod.USER_ID = user_id
            yandex_mod.HOST_ID = host_id
            ya_start, ya_end = _yandex_window()
            raw_ya = yandex_popular(ya_token, ya_start, ya_end)
            ya_indexed, ya_excluded = fetch_yandex_index_counts(
                ya_token, user_id, host_id)
            ya_urls = fetch_yandex_url_queries(
                ya_token, user_id, host_id, ya_start, ya_end)
        return {
            "rows": normalize_yandex_rows(raw_ya),
            "urls": ya_urls,
            "indexed": ya_indexed,
            "excluded": ya_excluded,
        }
    return _retry(_go)


def _pack(gsc: dict | None, ya: dict | None) -> dict[str, bytes]:
    gsc_rows = (gsc or {}).get("rows") or []
    ya_rows = (ya or {}).get("rows") or []
    ya_urls = (ya or {}).get("urls") or []
    gsc_indexed = int((gsc or {}).get("indexed") or 0)
    gsc_excluded = int((gsc or {}).get("excluded") or 0)
    ya_indexed = int((ya or {}).get("indexed") or 0)
    ya_excluded = int((ya or {}).get("excluded") or 0)
    gsc_status = "ok" if gsc is not None else UNAVAILABLE
    ya_status = "ok" if ya is not None else UNAVAILABLE
    meta = (
        f"gsc={gsc_status}\n"
        f"yandex={ya_status}\n"
        f"gsc_rows={len(gsc_rows)}\n"
        f"yandex_rows={len(ya_rows)}\n"
        f"yandex_url_rows={len(ya_urls)}\n"
        f"gsc_indexed={gsc_indexed}\n"
        f"gsc_excluded={gsc_excluded}\n"
        f"yandex_indexed={ya_indexed}\n"
        f"yandex_excluded={ya_excluded}\n"
        f"gsc_days={DAYS}\n"
        f"gsc_row_cap={GSC_ROW_CAP}\n"
    ).encode()
    return {
        "meta.txt": meta,
        "gsc-queries.json": json.dumps(gsc_rows, ensure_ascii=False).encode(),
        "yandex-queries.json": json.dumps(ya_rows, ensure_ascii=False).encode(),
        "yandex-url-queries.json": json.dumps(ya_urls, ensure_ascii=False).encode(),
        "index-counts.json": json.dumps({
            "gsc_indexed": gsc_indexed,
            "gsc_excluded": gsc_excluded,
            "yandex_indexed": ya_indexed,
            "yandex_excluded": ya_excluded,
            "gsc": gsc_status,
            "yandex": ya_status,
        }).encode(),
    }


def collect() -> dict[str, bytes]:
    sa_raw = _load_gsc_key()
    ya_token = os.environ.get("YANDEX_WM_TOKEN", "").strip()
    if not sa_raw:
        raise SystemExit(_fail(2, "search-queries-export: missing gsc key"))
    if not ya_token:
        raise SystemExit(_fail(2, "search-queries-export: missing yandex token"))

    gsc = None
    ya = None
    try:
        gsc = collect_gsc(sa_raw)
    except Exception:
        sys.stderr.write("search-queries-export: gsc unavailable\n")
    try:
        ya = collect_yandex(ya_token)
    except Exception:
        sys.stderr.write("search-queries-export: yandex unavailable\n")
    if gsc is None and ya is None:
        raise SystemExit(_fail(1, "search-queries-export: all sources failed"))
    return _pack(gsc, ya)


def main() -> int:
    sys.tracebacklimit = 0
    try:
        files = collect()
        sys.stdout.buffer.write(_tar_bytes(files))
        return 0
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    except Exception as exc:
        sys.stderr.write(f"search-queries-export: {type(exc).__name__}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
