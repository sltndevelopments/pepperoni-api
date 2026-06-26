#!/usr/bin/env python3
"""Deploy health check — verifies that a git push reached the live site.

Usage (inside seo-agent-vps.sh):

  # Before git add/commit — generate token and inject stamp:
  python3 scripts/deploy_check.py --inject

  # After git push — verify stamp appears on live site (2 retries × 90s):
  python3 scripts/deploy_check.py --verify

  # Check that critical homepage sections are present:
  python3 scripts/deploy_check.py --check-sections

How it works:
  --inject  Generates a short random token, writes it as an HTML comment
            <!-- kd-stamp:TOKEN --> into <head> of public/index.html, and
            stores the token in data/.deploy_stamp (gitignored — local only).
            The stamped index.html IS committed and pushed; .deploy_stamp is NOT.

  --verify  Reads token from data/.deploy_stamp.  If the file is absent, the
            push was not made by this pipeline → skip silently (no false alert).
            Otherwise curls pepperoni.tatar twice (90s apart) looking for the
            token.  If neither attempt finds it → notify_emergency().

The token is a 10-char hex string derived from the current timestamp + random,
so it's unique per commit and has no chicken-and-egg dependency on the hash.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import sys
import time
import urllib.request
from pathlib import Path

ROOT  = Path(__file__).parent.parent
DATA  = ROOT / "data"
PUBLIC = ROOT / "public"

STAMP_FILE   = DATA / ".deploy_stamp"   # gitignored — local token store
INDEX_HTML   = PUBLIC / "index.html"
LIVE_URL     = os.environ.get("DEPLOY_CHECK_URL", "https://pepperoni.tatar/")
RETRY_SLEEP  = int(os.environ.get("DEPLOY_CHECK_SLEEP", "90"))   # seconds
TIMEOUT      = int(os.environ.get("DEPLOY_CHECK_TIMEOUT", "15"))


def _generate_token() -> str:
    """Short unique token independent of commit hash (avoids chicken-and-egg)."""
    raw = secrets.token_bytes(8) + str(time.time()).encode()
    return hashlib.sha256(raw).hexdigest()[:10]


def inject(token: str | None = None) -> str:
    """Write stamp into index.html <head> and into .deploy_stamp.

    Returns the token used.  Safe to call multiple times — replaces old stamp.

    FAIL-CLOSED: runs structural invariant checks before writing the stamp.
    If any invariant is violated the inject is ABORTED and an emergency alert
    is sent — we never push broken/haram content to production.
    """
    if token is None:
        token = _generate_token()

    # ── Pre-commit invariant gate (structural only — fast, no LLM) ───────────
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import invariants as inv_mod
        violations = inv_mod.verify_invariants(semantic=False)
        if violations:
            msgs = []
            for v in violations:
                msgs.append(f"[{v['id']}]: " + "; ".join(v["violations"][:2]))
            alert = (
                "🚨 deploy_check: inject ABORTED — invariant violation(s):\n"
                + "\n".join(f"• {m}" for m in msgs)
                + "\nFix the violation before committing."
            )
            print(alert, file=sys.stderr)
            try:
                from telegram_notify import notify_emergency
                notify_emergency(alert)
            except Exception:
                pass
            # Raise so the calling shell script sees a non-zero exit
            raise SystemExit(3)
    except SystemExit:
        raise
    except Exception as e:
        # Import or check failure: fail-closed — do not silently skip
        alert = f"🚨 deploy_check: invariant check failed ({e}) — inject ABORTED"
        print(alert, file=sys.stderr)
        try:
            from telegram_notify import notify_emergency
            notify_emergency(alert)
        except Exception:
            pass
        raise SystemExit(3)

    try:
        html = INDEX_HTML.read_text(encoding="utf-8")
    except FileNotFoundError:
        print("⚠️  deploy_check: index.html not found — skip inject")
        return token

    stamp_comment = f"<!-- kd-stamp:{token} -->"

    # Remove any previous stamp first (idempotent)
    html = re.sub(r"<!-- kd-stamp:[0-9a-f]+ -->", "", html)

    # Insert right after <head> (or <head ...>)
    html = re.sub(r"(<head[^>]*>)", rf"\1\n  {stamp_comment}", html, count=1, flags=re.I)

    INDEX_HTML.write_text(html, encoding="utf-8")

    # Store token locally (gitignored) so --verify can read it
    DATA.mkdir(exist_ok=True)
    STAMP_FILE.write_text(token, encoding="utf-8")

    print(f"🔖 deploy_check: stamp injected → token={token}")
    return token


def _curl_has_stamp(token: str) -> bool:
    """Return True if live site's HTML contains the stamp token."""
    try:
        req = urllib.request.Request(
            LIVE_URL,
            headers={"User-Agent": "deploy-check/1.0", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(131072).decode("utf-8", errors="replace")
        return f"kd-stamp:{token}" in body
    except Exception as e:
        print(f"  deploy_check curl error: {e}")
        return False


def verify() -> bool:
    """Check that the stamp reached the live site. Returns True if OK.

    If .deploy_stamp is absent (manual push or other script) → skip, return True.
    Two attempts spaced RETRY_SLEEP seconds apart before firing emergency alert.
    """
    if not STAMP_FILE.exists():
        print("ℹ️  deploy_check: no .deploy_stamp — not a pipeline push, skip")
        return True

    token = STAMP_FILE.read_text(encoding="utf-8").strip()
    if not token:
        return True

    for attempt in (1, 2):
        print(f"🔍 deploy_check: attempt {attempt}/2 — looking for kd-stamp:{token}")
        if _curl_has_stamp(token):
            print(f"✅ deploy_check: stamp found on live site (attempt {attempt})")
            STAMP_FILE.unlink(missing_ok=True)
            return True
        if attempt == 1:
            print(f"   not found yet — waiting {RETRY_SLEEP}s before retry …")
            time.sleep(RETRY_SLEEP)

    # Both attempts failed — fire emergency
    msg = (
        f"🚨 Деплой не дошёл в прод!\n"
        f"Токен <code>{token}</code> не найден на {LIVE_URL} после двух проверок.\n"
        f"Проверь Vercel dashboard — возможно провалился деплой."
    )
    print(f"🚨 deploy_check: FAILED — {msg}")
    try:
        from telegram_notify import notify_emergency
        notify_emergency(msg)
    except Exception as e:
        print(f"  notify_emergency failed: {e}")

    STAMP_FILE.unlink(missing_ok=True)
    return False


def check_homepage_sections() -> bool:
    """Verify that critical B2B sections exist in public/index.html.

    Checks for invariant homepage-sections-intact:
    - id="segments"  (Кому поставляем — 6 B2B segment cards)
    - id="partners"  (С кем работаем — partner tiles)

    Returns True if both present, False (+ Telegram alert) if any missing.
    """
    required = ['id="segments"', 'id="partners"']
    try:
        html = INDEX_HTML.read_text(encoding="utf-8")
    except FileNotFoundError:
        print("⚠️  deploy_check: index.html not found — skip section check")
        return True

    missing = [p for p in required if p not in html]
    if not missing:
        print("✅ deploy_check: homepage sections intact (segments + partners)")
        return True

    # Auto-repair: regenerate index.html from gen-index.py (which now contains the sections)
    gen_script = ROOT / "scripts" / "gen-index.py"
    repaired = False
    if gen_script.exists():
        try:
            import subprocess
            result = subprocess.run(
                ["python3", str(gen_script)],
                capture_output=True, text=True, timeout=30,
                cwd=str(ROOT)
            )
            if result.returncode == 0:
                # Re-check after regeneration
                html2 = INDEX_HTML.read_text(encoding="utf-8")
                still_missing = [p for p in missing if p not in html2]
                if not still_missing:
                    print("✅ deploy_check: auto-repaired homepage sections via gen-index.py")
                    return True
                missing = still_missing
                repaired = False
            else:
                print(f"  gen-index.py failed: {result.stderr[:200]}")
        except Exception as e:
            print(f"  auto-repair failed: {e}")

    msg = (
        "🚨 homepage-sections-intact нарушен!\n"
        + "\n".join(f"  • отсутствует: {p}" for p in missing)
        + f"\nФайл: {INDEX_HTML}\n"
        + ("Авторемонт через gen-index.py не помог. " if not repaired else "")
        + "Секции «Кому поставляем» / «С кем работаем» пропали из index.html."
    )
    print(f"🚨 deploy_check: {msg}")
    try:
        from telegram_notify import notify_emergency
        notify_emergency(msg)
    except Exception as e:
        print(f"  notify_emergency failed: {e}")
    return False


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--help"

    if cmd == "--inject":
        token = inject()
        sys.exit(0)

    elif cmd == "--verify":
        ok = verify()
        sys.exit(0 if ok else 1)

    elif cmd == "--test-inject":
        # Unit test: inject, then check file contains stamp
        token = inject("testtoken01")
        html = INDEX_HTML.read_text(encoding="utf-8")
        assert f"kd-stamp:testtoken01" in html, "FAIL: stamp not in index.html"
        assert STAMP_FILE.read_text().strip() == "testtoken01", "FAIL: stamp file mismatch"
        print("✅ --test-inject PASS")

    elif cmd == "--test-verify-fail":
        # Unit test: write a fake token that won't be on live site → should alert
        STAMP_FILE.write_text("fakefake00", encoding="utf-8")
        os.environ["DEPLOY_CHECK_SLEEP"] = "1"  # speed up for test
        ok = verify()
        print(f"--test-verify-fail result: ok={ok} (expected False)")
        assert not ok, "FAIL: expected emergency alert for fake token"
        print("✅ --test-verify-fail PASS (emergency would have fired)")

    elif cmd == "--check-sections":
        ok = check_homepage_sections()
        sys.exit(0 if ok else 1)

    else:
        print(__doc__)
        sys.exit(1)
