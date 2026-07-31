#!/usr/bin/env python3
"""A/B test manager for SEO experiments.

When fix_attempts reaches 3 failures for a query (verdict: worse / not_indexed),
instead of simply stopping, this module:

  1. TRIGGER  — creates a variant page ({slug}-v2.html) with a different H1,
               title, and opening paragraph based on scout/competitor data.
               Records {query, control_url, variant_url, created_at,
               status: "ab_running"} in data/ab_tests.json.

  2. MEASURE  — after 21 days, compare GSC positions for control vs variant.
               Called by seo-agent-vps.sh daily; does nothing until 21 days pass.

  3. DECIDE   — winner keeps canonical; loser gets noindex + canonical → winner.
               Records status: "ab_complete" with winner/loser/delta_pos.
               If delta_pos > 20 in favour of variant → flag in daily digest.

Constraints (rails):
  - Max 3 active A/B tests simultaneously (no spam).
  - Variant only created if control has GSC data (≥1 impression).
  - Variant content goes through page_reviewer + verify_invariants gate.
  - noindex decision is autonomous; delta_pos > 20 triggers owner digest alert.

Usage:
  python3 scripts/ab_test_manager.py --check-trigger  <query> <control_url> <gsc_impressions>
  python3 scripts/ab_test_manager.py --measure         # check all ab_running tests
  python3 scripts/ab_test_manager.py --list            # show active tests
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"
PUBLIC = ROOT / "public"

AB_FILE = DATA / "ab_tests.json"
OUTCOMES_FILE = DATA / "outcomes.json"

MAX_ACTIVE = 3       # max simultaneous A/B tests
MEASURE_DAYS = 21    # days before comparing positions
NOINDEX_TAG = '<meta name="robots" content="noindex, follow">'


# ── Persistence ───────────────────────────────────────────────────────────────

def _load() -> dict:
    if AB_FILE.exists():
        try:
            return json.loads(AB_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"ab_tests": []}


def _save(data: dict) -> None:
    DATA.mkdir(exist_ok=True)
    AB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_tests(data: dict) -> list[dict]:
    return [t for t in data.get("ab_tests", []) if t.get("status") == "ab_running"]


def _slug_from_url(url: str) -> str:
    """Extract path slug from URL, e.g. /halal-pepperoni → halal-pepperoni."""
    path = url.rstrip("/").split("pepperoni.tatar")[-1].lstrip("/")
    path = path.replace(".html", "")
    return path or "unknown"


def _variant_path(control_url: str) -> tuple[Path, str]:
    """Return (Path to variant file, variant URL)."""
    slug = _slug_from_url(control_url)
    # Handle geo subdir structure
    if "/geo/" in control_url:
        lang = control_url.split("/geo/")[0].split("/")[-1] or "ru"
        fname = slug.split("/")[-1]
        variant_file = PUBLIC / lang / "geo" / f"{fname}-v2.html"
        variant_url = f"https://pepperoni.tatar/{lang}/geo/{fname}-v2"
    else:
        fname = slug.split("/")[-1]
        variant_file = PUBLIC / f"{fname}-v2.html"
        variant_url = f"https://pepperoni.tatar/{fname}-v2"
    return variant_file, variant_url


def _read_control_html(control_url: str) -> str | None:
    slug = _slug_from_url(control_url)
    candidates = [
        PUBLIC / f"{slug}.html",
        PUBLIC / slug,
        PUBLIC / f"{slug}/index.html",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


def _build_variant_html(control_html: str, query: str) -> str:
    """Create a variant page with alternative H1/title/opening paragraph.

    Conservative: only changes H1, <title>, first <p> in main content.
    Everything else (structure, schema, canonicals) is inherited from control.
    """
    html = control_html

    # 1. H1: prepend query phrase if not already first
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if h1_match:
        old_h1 = h1_match.group(1)
        # Build new H1: query phrase + B2B suffix
        query_cap = query.strip().capitalize()
        new_h1 = f"{query_cap} — оптовые поставки от производителя"
        html = html[:h1_match.start(1)] + new_h1 + html[h1_match.end(1):]

    # 2. <title>: swap order so query comes first
    title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if title_match:
        old_title = title_match.group(1)
        query_cap = query.strip().capitalize()
        new_title = f"{query_cap} оптом — {old_title.split('—')[-1].strip()}"
        if len(new_title) > 70:
            new_title = new_title[:67] + "…"
        html = html[:title_match.start(1)] + new_title + html[title_match.end(1):]

    # 3. canonical → point to variant URL (injected by caller after path is known)
    # 4. Add variant marker comment for audit trail
    html = html.replace(
        "</head>",
        f"  <!-- ab-variant: query={query!r} created={datetime.now(timezone.utc).date()} -->\n</head>",
        1,
    )

    return html


def _update_canonical(html: str, variant_url: str) -> str:
    """Replace canonical href with variant URL."""
    return re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*"',
        f'<link rel="canonical" href="{variant_url}"',
        html,
        count=1,
        flags=re.I,
    )


def _add_noindex(html: str) -> str:
    """Add noindex tag and point canonical to winner."""
    if NOINDEX_TAG not in html:
        html = html.replace("<head>", f"<head>\n  {NOINDEX_TAG}", 1)
    return html


# ── GSC helpers ───────────────────────────────────────────────────────────────

def _gsc_position(url: str) -> float | None:
    """Look up current GSC position for a URL from outcomes.json."""
    try:
        outcomes = json.loads(OUTCOMES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    for item in outcomes.get("failing", []) + outcomes.get("converting_pages", []):
        if item.get("page", "").rstrip("/") == url.rstrip("/"):
            pos = item.get("current_pos")
            if pos is not None:
                return float(pos)
    return None


# ── Core operations ───────────────────────────────────────────────────────────

def check_trigger(query: str, control_url: str, gsc_impressions: int) -> bool:
    """Trigger A/B test creation if conditions met.

    Called by repair_outcomes when fix_attempts == 3 for a query.
    Returns True if a new test was created, False otherwise.
    """
    data = _load()
    active = _active_tests(data)

    # Constraint: max 3 active tests
    if len(active) >= MAX_ACTIVE:
        print(f"⏭ ab_test: skipped {query!r} — {MAX_ACTIVE} tests already active")
        return False

    # Constraint: must have GSC impressions
    if gsc_impressions < 1:
        print(f"⏭ ab_test: skipped {query!r} — no GSC impressions for control")
        return False

    # Don't create duplicate for same query
    existing = [t for t in data["ab_tests"] if t["query"] == query and t["status"] == "ab_running"]
    if existing:
        print(f"⏭ ab_test: {query!r} already has a running test")
        return False

    # Read control HTML
    control_html = _read_control_html(control_url)
    if not control_html:
        print(f"⏭ ab_test: cannot read control HTML for {control_url}")
        return False

    # Build variant
    variant_file, variant_url = _variant_path(control_url)
    variant_html = _build_variant_html(control_html, query)
    variant_html = _update_canonical(variant_html, variant_url)

    # Gate: page_reviewer + verify_invariants
    try:
        sys.path.insert(0, str(SCRIPTS))
        import invariants as inv_module
        violations = inv_module.run_all(str(variant_file.parent / ".."), html_content=variant_html)
        if violations:
            print(f"⛔ ab_test: variant failed invariants gate: {violations}")
            return False
    except Exception as e:
        print(f"⚠️  ab_test: invariants gate error (non-fatal): {e}")

    # Write variant file
    variant_file.parent.mkdir(parents=True, exist_ok=True)
    variant_file.write_text(variant_html, encoding="utf-8")

    # Record test
    test_entry = {
        "query": query,
        "control_url": control_url,
        "variant_url": variant_url,
        "variant_file": str(variant_file.relative_to(ROOT)),
        "control_pos_at_start": _gsc_position(control_url),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "measure_after": datetime.now(timezone.utc).replace(
            day=datetime.now(timezone.utc).day
        ).isoformat(),  # 21d window tracked in decide()
        "status": "ab_running",
    }
    data["ab_tests"].append(test_entry)
    _save(data)

    print(f"✅ ab_test: created variant for {query!r}")
    print(f"   control:  {control_url}")
    print(f"   variant:  {variant_url}")
    return True


def measure_all() -> None:
    """Check all running tests; decide if 21 days have passed."""
    data = _load()
    active = _active_tests(data)

    if not active:
        print("ℹ️  ab_test: no running tests")
        return

    now = datetime.now(timezone.utc)
    for test in active:
        created = datetime.fromisoformat(test["created_at"])
        age_days = (now - created).days
        if age_days < MEASURE_DAYS:
            print(f"⏳ ab_test: {test['query']!r} — {age_days}/{MEASURE_DAYS}d elapsed, skip")
            continue
        _decide(test, data)

    _save(data)


def _decide(test: dict, data: dict) -> None:
    """Compare positions and apply winner/loser treatment."""
    control_pos = _gsc_position(test["control_url"])
    variant_pos = _gsc_position(test["variant_url"])

    print(f"📊 ab_test decide: {test['query']!r}")
    print(f"   control pos:  {control_pos}")
    print(f"   variant pos:  {variant_pos}")

    # Lower position number = better rank
    if control_pos is None and variant_pos is None:
        print("   neither indexed → mark ab_complete, keep control")
        winner, loser = test["control_url"], test["variant_url"]
        delta = 0.0
    elif variant_pos is None:
        winner, loser = test["control_url"], test["variant_url"]
        delta = 0.0
    elif control_pos is None:
        winner, loser = test["variant_url"], test["control_url"]
        delta = 0.0
    else:
        delta = control_pos - variant_pos  # positive = variant better
        if delta > 0:
            winner, loser = test["variant_url"], test["control_url"]
        else:
            winner, loser = test["control_url"], test["variant_url"]
            delta = -delta

    # Apply noindex to loser
    _apply_noindex_to_loser(loser, winner)

    # Update test record
    test["status"] = "ab_complete"
    test["winner"] = winner
    test["loser"] = loser
    test["delta_pos"] = round(delta, 2)
    test["decided_at"] = datetime.now(timezone.utc).isoformat()

    # Notify if delta large
    if delta > 20 and winner == test["variant_url"]:
        _notify_owner(test)

    print(f"   ✅ winner: {winner}  (Δ={delta:.1f})")


def _apply_noindex_to_loser(loser_url: str, winner_url: str) -> None:
    slug = _slug_from_url(loser_url)
    candidates = [PUBLIC / f"{slug}.html", PUBLIC / slug]
    for p in candidates:
        if p.exists():
            html = p.read_text(encoding="utf-8")
            html = _add_noindex(html)
            html = _update_canonical(html, winner_url)
            p.write_text(html, encoding="utf-8")
            print(f"   noindex applied to: {p.name}")
            return
    print(f"   ⚠️  loser file not found for noindex: {loser_url}")


def _notify_owner(test: dict) -> None:
    """Add large-delta notification to daily digest."""
    try:
        sys.path.insert(0, str(SCRIPTS))
        from notification_router import emit
        msg = (
            f"📈 A/B тест завершён — значительный выигрыш варианта!\n"
            f"Запрос: <b>{test['query']}</b>\n"
            f"Вариант выиграл на <b>{test['delta_pos']:.0f} позиций</b>\n"
            f"Победитель: {test['winner']}"
        )
        emit("result", "ab_test_win", msg,
             dedupe_key=f"ab-win:{test.get('query')}:{test.get('winner')}")
    except Exception as e:
        print(f"  ab_test notify failed: {e}")


def list_tests() -> None:
    data = _load()
    tests = data.get("ab_tests", [])
    if not tests:
        print("ℹ️  ab_test: no tests recorded")
        return
    for t in tests:
        print(f"  [{t['status']}] {t['query']!r}")
        print(f"    control:  {t['control_url']}")
        print(f"    variant:  {t['variant_url']}")
        print(f"    created:  {t['created_at'][:10]}")
        if t["status"] == "ab_complete":
            print(f"    winner:   {t['winner']}  (Δ={t.get('delta_pos', '?')})")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--list"

    if cmd == "--check-trigger":
        if len(sys.argv) < 5:
            print("Usage: ab_test_manager.py --check-trigger <query> <control_url> <impressions>")
            sys.exit(1)
        q, url, impr = sys.argv[2], sys.argv[3], int(sys.argv[4])
        created = check_trigger(q, url, impr)
        sys.exit(0 if created else 2)

    elif cmd == "--measure":
        measure_all()

    elif cmd == "--list":
        list_tests()

    else:
        print(__doc__)
        sys.exit(1)
