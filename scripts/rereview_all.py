"""Re-review ALL quarantined pages.
Pages that pass go to public/geo/ru/; real rejects stay in quarantine."""
import sys, pathlib, json, shutil, re, os, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
os.chdir(pathlib.Path(__file__).parent.parent)

import page_reviewer

QUARANTINE_DIR = pathlib.Path("data/quarantine")
PUBLIC_GEO_RU  = pathlib.Path("public/geo/ru")
PUBLIC_GEO_RU.mkdir(parents=True, exist_ok=True)

candidates = sorted(QUARANTINE_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime)
print(f"Quarantine total: {len(candidates)} pages")

passed = rejected = skipped = 0
for p in candidates:
    html = p.read_text(encoding="utf-8", errors="replace")
    # Skip thin pages — real structural fail, no point re-reviewing
    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html, flags=re.I|re.S)
    visible = re.sub(r"<[^>]+>", " ", cleaned)
    words = [w for w in visible.split() if len(w) > 1]
    if len(words) < 300:
        print(f"  SKIP (thin {len(words)}w): {p.name}")
        skipped += 1
        continue

    # Copy to /tmp for review so quarantine() inside page_reviewer
    # doesn't move it to an unexpected location
    tmp = pathlib.Path(f"/tmp/rr_{p.name}")
    shutil.copy(p, tmp)

    result = page_reviewer.review_page(tmp)
    verdict = result.get("verdict")
    reasons = result.get("reasons", [])

    if verdict == "pass":
        dest = PUBLIC_GEO_RU / p.name
        shutil.copy(p, dest)
        p.unlink()
        passed += 1
        print(f"  PASS → {dest.name}")
    else:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        rejected += 1
        r0 = reasons[0][:90] if reasons else "?"
        print(f"  {verdict.upper()}: {p.name} — {r0}")

print(f"\n=== Re-review done: {passed} pass, {rejected} reject/hold, {skipped} skipped (thin) ===")
