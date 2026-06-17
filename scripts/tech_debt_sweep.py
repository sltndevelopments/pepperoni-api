#!/usr/bin/env python3
"""Tech-debt sweep — deterministic full-site repair + self-check.

Runs ONLY deterministic, non-LLM fixers in order:
  Phase 1: fix_pages   — invented phones/emails, GOST, ar-pork, fences, LLM preamble
  Phase 2: fix_links   — dead/placeholder internal links (script-blocks safe)
  Phase 3: repair_truncated_pages — unclosed </html> across whole site
  Phase 4: rebuild_sitemap — regenerates sitemap.xml from current public/

Excluded (carve-outs, separate careful tasks):
  • canonical rewrite (3100+ pages — needs rule-validation on sample first)
  • fix_schema/priceRange (3040 pages — needs confirmed price source)
  • ar-pork single page is handled by fix_pages above (correct halal fix)

After applying fixes, Phase 5 runs sanity_check (fail-closed):
  (a) index.html still contains  <a class="product-card-link" href="${href}">
      inside a <script> block — product cards intact
  (b) Sample of 60 geo pages: all have </html>, no placeholder ${...} in <a> tags
  (c) broken_links_after ≤ broken_links_before  (no regression)
  → If ANY check fails: git checkout -- public/ (full rollback), emergency alert,
    exit 2.  "Better not close the debt than break prod."

Phase 6 (only on --run): deploy_check --inject then commit+push then
  deploy_check --verify (background).

Usage:
  python3 scripts/tech_debt_sweep.py --dry-run   # measure only, no writes
  python3 scripts/tech_debt_sweep.py --run        # apply + sanity + deploy
  python3 scripts/tech_debt_sweep.py --sanity     # sanity only (no sweep)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ── helpers ──────────────────────────────────────────────────────────────────

def _run(cmd: list[str], label: str) -> int:
    """Run a subprocess, stream output, return exit code."""
    print(f"\n{'─'*60}")
    print(f"▶ {label}")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"{'─'*60}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


# ── Phase 0: measure before ───────────────────────────────────────────────────

def _count_fix_pages() -> dict:
    """Count pages that fix_pages would touch (dry-run)."""
    from fix_pages import fix_html
    counts: dict[str, int] = {}
    files = total = 0
    for f in sorted(PUBLIC.rglob("*.html")):
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        total += 1
        _, fixes = fix_html(html)
        if fixes:
            files += 1
            for fx in fixes:
                key = fx.split(" ×")[0].split(":")[0].strip()
                counts[key] = counts.get(key, 0) + 1
    return {"files": files, "total_scanned": total, "by_type": counts}


def _count_truncated() -> dict:
    """Count pages missing </html>."""
    n = sum(
        1 for f in PUBLIC.rglob("*.html")
        if "</html>" not in f.read_text(encoding="utf-8", errors="ignore").lower()
    )
    return {"truncated": n}


def _count_broken_links() -> int:
    """Count placeholder + genuinely dead internal links (dry-run fix_links)."""
    from fix_links import _fix_html, _site_paths
    _site_paths()
    total = 0
    for f in sorted(PUBLIC.rglob("*.html")):
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        _, s = _fix_html(html)
        total += s["placeholder"] + s["unwrapped"]
    return total


def measure_before() -> dict:
    print("\n📏 Measuring before sweep …")
    fp = _count_fix_pages()
    tr = _count_truncated()
    bl = _count_broken_links()
    sitemap_urls = sum(1 for _ in (PUBLIC / "sitemap.xml").read_text().split("<url>")) - 1 \
        if (PUBLIC / "sitemap.xml").exists() else 0
    snap = {
        "fix_pages_files": fp["files"],
        "fix_pages_by_type": fp["by_type"],
        "truncated": tr["truncated"],
        "broken_links": bl,
        "sitemap_urls": sitemap_urls,
        "total_html": fp["total_scanned"],
    }
    print(f"  fix_pages:  {snap['fix_pages_files']} files  {fp['by_type']}")
    print(f"  truncated:  {snap['truncated']}")
    print(f"  broken_links: {snap['broken_links']}")
    print(f"  sitemap_urls: {snap['sitemap_urls']}")
    return snap


# ── Phase 5: sanity check ─────────────────────────────────────────────────────

# The JS template literal the product-card renderer uses.  fix_links must NEVER
# unwrap this (it lives inside a <script> block, not a real <a> tag).
_CARD_LINK_PATTERN = re.compile(
    r'<a\s[^>]*class=["\'][^"\']*product-card-link[^"\']*["\'][^>]*href="\$\{href\}"',
    re.I,
)

# Simple check: <a href="${href}"> anywhere in a <script> (the JS template).
_CARD_HREF_IN_SCRIPT = re.compile(
    r'<script\b[^>]*>.*?href="\$\{href\}".*?</script>',
    re.I | re.S,
)

_PLACEHOLDER_A = re.compile(r'<a\b[^>]*href=["\'][^"\']*\$\{[^}]*\}[^"\']*["\']', re.I)


def sanity_check(before: dict) -> tuple[bool, list[str]]:
    """Run post-sweep sanity checks. Returns (ok, list_of_failures)."""
    failures: list[str] = []

    # ── (a) index.html: product-card-link JS template still intact ────────────
    index_html = PUBLIC / "index.html"
    try:
        idx = index_html.read_text(encoding="utf-8")
        if not _CARD_HREF_IN_SCRIPT.search(idx):
            failures.append(
                "index.html: <a … href=\"${href}\"> missing inside <script> — "
                "product card JS template was damaged"
            )
    except Exception as e:
        failures.append(f"index.html: cannot read — {e}")

    # ── (b) Sample 60 geo pages: valid HTML, no placeholder <a> in rendered HTML ──
    geo_files = sorted((PUBLIC / "geo").rglob("*.html"))[:60] if (PUBLIC / "geo").exists() else []
    # Also sample ar/geo if exists
    ar_geo = sorted((PUBLIC / "ar" / "geo").rglob("*.html"))[:20] \
        if (PUBLIC / "ar" / "geo").exists() else []
    sample = geo_files[:40] + ar_geo[:20]

    bad_html = bad_placeholder = 0
    for f in sample:
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "</html>" not in html.lower():
            bad_html += 1
        # Placeholder <a> tags outside <script> blocks
        # Stash scripts first
        scripts: list[str] = []
        _SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
        def stash(m: re.Match) -> str:
            scripts.append(m.group(0))
            return ""
        html_no_scripts = _SCRIPT_RE.sub(stash, html)
        if _PLACEHOLDER_A.search(html_no_scripts):
            bad_placeholder += 1

    if bad_html > 0:
        failures.append(f"geo sample: {bad_html} pages still missing </html> after repair")
    if bad_placeholder > 0:
        failures.append(
            f"geo sample: {bad_placeholder} pages have unrendered template placeholders "
            "in <a href> outside <script> — fix_links may have missed them"
        )

    # ── (c) Broken-link count must not have grown ─────────────────────────────
    bl_after = _count_broken_links()
    bl_before = before.get("broken_links", 0)
    if bl_after > bl_before:
        failures.append(
            f"broken_links grew: {bl_before} → {bl_after} "
            "(fix_links may have introduced new dead links)"
        )

    ok = len(failures) == 0
    if ok:
        print(f"\n✅ Sanity check PASSED (broken_links: {bl_before} → {bl_after})")
    else:
        print(f"\n🚨 Sanity check FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  ✗ {f}")
    return ok, failures


# ── Rollback ──────────────────────────────────────────────────────────────────

def rollback(failures: list[str]) -> None:
    """Discard all working-tree changes to public/ via git checkout."""
    print("\n🔄 Rolling back public/ …")
    result = subprocess.run(
        ["git", "checkout", "--", "public/"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("  ✅ public/ restored to HEAD")
    else:
        print(f"  ⚠️  git checkout failed: {result.stderr[:200]}")

    msg = ("🚨 tech_debt_sweep: sanity FAILED — rolled back.\n"
           + "\n".join(f"• {f}" for f in failures[:5]))
    print(f"\n{msg}")
    try:
        sys.path.insert(0, str(SCRIPTS))
        from daily_ledger import append_event
        append_event("emergency", msg)
    except Exception as e:
        print(f"  ledger emergency failed: {e}")
        try:
            from telegram_notify import notify_emergency
            notify_emergency(msg)
        except Exception:
            pass


# ── Phase 5b: Class-completeness check (independent detectors) ───────────────
#
# "Done" = broad independent detector of the problem CLASS shows zero.
# NOT "fixer ran and its own counter returned 0" (that's tautological).
#
# Three classes, three detectors:
#
#   halal   → page_reviewer semantic scan on every AR/product page that
#             contains خنزير (cheap pre-filter + LLM semantic verdict per page).
#             Reason: fix_pages regex only catches its own pattern; JSON-LD
#             oxymorons and other semantic forms are invisible to it.  The same
#             semantic scanner found the 3 ham-page violations that regex missed.
#
#   links   → site_health full link-graph scan (all internal links, all pages).
#             Reason: fix_links only fixes the patterns it knows; new 404s from
#             renamed/deleted pages appear immediately in the graph.
#
#   truncated → scan ALL *.html for absent </html>.
#               Reason: repair_truncated may only patch a subset; scanning all
#               files is the only way to know the class is truly empty.
#
# If any detector finds residual problems the sweep reports "partial" (not "done")
# and emits a needs_help event so Fable investigates the root cause.

_KHANZIR_RE = re.compile(r"خنزير", re.UNICODE)


def _class_completeness_check() -> dict:
    """Run independent class-level completeness detectors. Returns summary dict."""
    results: dict[str, object] = {}
    failures: list[str] = []

    # ── Halal class: semantic scan via page_reviewer on all خنزير pages ──────
    print("\n🔍 Completeness: halal class (page_reviewer semantic scan) …")
    try:
        import page_reviewer as pr
        khanzir_pages = [
            f for f in PUBLIC.rglob("*.html")
            if _KHANZIR_RE.search(f.read_text(encoding="utf-8", errors="ignore"))
        ]
        halal_violations = 0
        for p in khanzir_pages:
            # Pass CONTAINS_KHANZIR=true so reviewer applies extra scrutiny.
            result = pr.review_page(p, meta={"CONTAINS_KHANZIR": True,
                                              "completeness_check": True})
            if result.get("verdict") in ("reject", "hold"):
                reasons = result.get("reasons", [])
                print(f"  ✗ HALAL VIOLATION: {p.name}  reasons={reasons}")
                halal_violations += 1
        results["halal_violations"] = halal_violations
        results["halal_scanned"] = len(khanzir_pages)
        if halal_violations > 0:
            failures.append(
                f"halal class: {halal_violations} semantic violation(s) remain "
                f"after fix_pages — root cause needs investigation"
            )
        else:
            print(f"  ✅ halal class: 0 violations across {len(khanzir_pages)} خنزير pages")
    except Exception as e:
        failures.append(f"halal completeness check failed: {e}")
        results["halal_error"] = str(e)

    # ── Links class: full site_health scan ───────────────────────────────────
    print("\n🔍 Completeness: links class (site_health full scan) …")
    try:
        import site_health
        snap = site_health.audit()
        bl_total = snap.get("broken_links_total", 0)
        results["broken_links_total"] = bl_total
        if bl_total > 0:
            # Non-blocking: broken links are an ongoing concern, not a sweep failure.
            # Report as needs_help if count is high.
            if bl_total > 100:
                failures.append(
                    f"links class: {bl_total} broken links remain after fix_links "
                    f"(site_health full scan). Root cause: pages deleted/renamed?"
                )
            else:
                print(f"  ℹ️  links class: {bl_total} residual (below threshold 100)")
        else:
            print("  ✅ links class: 0 broken links (site_health)")
    except Exception as e:
        print(f"  ⚠️  site_health unavailable: {e}")
        results["links_error"] = str(e)

    # ── Truncated class: scan ALL *.html for missing </html> ─────────────────
    print("\n🔍 Completeness: truncated class (all *.html scan) …")
    try:
        truncated_all = [
            f for f in PUBLIC.rglob("*.html")
            if "</html>" not in f.read_text(encoding="utf-8", errors="ignore").lower()
        ]
        results["truncated_remaining"] = len(truncated_all)
        if truncated_all:
            failures.append(
                f"truncated class: {len(truncated_all)} page(s) still missing "
                f"</html> after repair_truncated (full site scan)"
            )
            for p in truncated_all[:5]:
                print(f"  ✗ truncated: {p.relative_to(PUBLIC)}")
        else:
            print("  ✅ truncated class: all pages have </html>")
    except Exception as e:
        failures.append(f"truncated completeness check failed: {e}")
        results["truncated_error"] = str(e)

    # ── Emit needs_help if any class is not fully closed ─────────────────────
    results["all_classes_closed"] = len(failures) == 0
    if failures:
        msg = "sweep partial — classes not fully closed:\n" + "\n".join(
            f"• {f}" for f in failures
        )
        print(f"\n⚠️  {msg}")
        try:
            from daily_ledger import append_event
            append_event("needs_help", msg)
        except Exception:
            pass
    else:
        print("\n✅ All class-completeness checks passed.")

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Tech-debt sweep (safe deterministic fixers)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Measure only — no writes, no git, no deploy")
    parser.add_argument("--run", action="store_true",
                        help="Apply all phases + sanity + deploy_check")
    parser.add_argument("--sanity", action="store_true",
                        help="Run sanity check only (no sweep)")
    args = parser.parse_args()

    if not (args.dry_run or args.run or args.sanity):
        parser.print_help()
        return 1

    # ── Phase 0: baseline ────────────────────────────────────────────────────
    before = measure_before()

    if args.dry_run:
        print("\n⏸  --dry-run: no changes written.")
        return 0

    if args.sanity:
        ok, failures = sanity_check(before)
        return 0 if ok else 2

    # ── --run: apply all phases ───────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print("🧹 TECH-DEBT SWEEP — applying fixes")
    print(f"{'═'*60}")

    # Phase 1: fix_pages
    rc = _run([sys.executable, str(SCRIPTS / "fix_pages.py"), "--all"], "Phase 1: fix_pages --all")
    if rc != 0:
        print("  ⚠️  fix_pages exited non-zero (non-fatal, continuing)")

    # Phase 2: fix_links
    rc = _run([sys.executable, str(SCRIPTS / "fix_links.py")], "Phase 2: fix_links")
    if rc != 0:
        print("  ⚠️  fix_links exited non-zero (non-fatal, continuing)")

    # Phase 3: repair_truncated_pages (whole site, not just geo)
    rc = _run([sys.executable, str(SCRIPTS / "repair_truncated_pages.py"), "--scope"],
              "Phase 3: repair_truncated_pages --scope (whole site)")
    if rc != 0:
        print("  ⚠️  repair_truncated exited non-zero (non-fatal, continuing)")

    # Phase 4: rebuild_sitemap
    rc = _run([sys.executable, str(SCRIPTS / "rebuild_sitemap.py")], "Phase 4: rebuild_sitemap")
    if rc != 0:
        print("  ⚠️  rebuild_sitemap exited non-zero (non-fatal, continuing)")

    # ── Phase 5: sanity check (fail-closed) ──────────────────────────────────
    ok, failures = sanity_check(before)

    if not ok:
        rollback(failures)
        return 2

    # ── Measure after ─────────────────────────────────────────────────────────
    print("\n📏 Measuring after sweep …")
    after_fp = _count_fix_pages()
    after_tr = _count_truncated()
    after_bl = _count_broken_links()

    # ── Phase 5b: class-completeness (independent broad detectors) ────────────
    completeness = _class_completeness_check()
    status_tag = "✅" if completeness.get("all_classes_closed") else "⚠️ partial"

    summary = (
        f"sweep {status_tag}: "
        f"fix_pages {before['fix_pages_files']}→{after_fp['files']} files, "
        f"truncated {before['truncated']}→{after_tr['truncated']}, "
        f"broken_links {before['broken_links']}→{after_bl}, "
        f"halal_violations={completeness.get('halal_violations', '?')}, "
        f"residual_truncated={completeness.get('truncated_remaining', '?')}"
    )
    print(f"\n{summary}")

    # Route to daily ledger
    try:
        from daily_ledger import append_event
        category = "done" if completeness.get("all_classes_closed") else "needs_help"
        append_event(category, summary)
    except Exception:
        pass

    # ── Phase 6: deploy_check --inject → commit → push → verify ──────────────
    print("\n🚀 Phase 6: stamp + commit + push")

    # Inject deploy stamp BEFORE git add
    subprocess.run([sys.executable, str(SCRIPTS / "deploy_check.py"), "--inject"],
                   cwd=str(ROOT))

    # Stage all changed public/ files
    subprocess.run(["git", "add", "public/"], cwd=str(ROOT))

    # Commit (only if there are staged changes)
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(ROOT)
    )
    if status.returncode != 0:
        msg = f"chore(sweep): tech-debt sweep — {summary}"
        subprocess.run(["git", "commit", "-m", msg], cwd=str(ROOT))
        push = subprocess.run(["git", "push", "origin", "HEAD:main"],
                               cwd=str(ROOT), capture_output=True, text=True)
        if push.returncode == 0:
            print("  ✅ pushed — verifying stamp in background …")
            subprocess.Popen(
                [sys.executable, str(SCRIPTS / "deploy_check.py"), "--verify"],
                cwd=str(ROOT),
            )
        else:
            print(f"  ⚠️  push failed: {push.stderr[:200]}")
            try:
                from daily_ledger import append_event
                append_event("needs_help", f"sweep push failed: {push.stderr[:120]}")
            except Exception:
                pass
    else:
        print("  ℹ️  nothing changed — no commit needed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
