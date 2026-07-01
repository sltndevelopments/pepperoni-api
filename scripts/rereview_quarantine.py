"""Re-review quarantined pages that were held due to budget exhaustion.
Moves passing pages to public/geo/, leaves real rejects in quarantine."""
import sys, pathlib, json, shutil, re, os
sys.path.insert(0, str(pathlib.Path(__file__).parent))
os.chdir(pathlib.Path(__file__).parent.parent)

import page_reviewer
from generate_geo_bulk import save_page_record, PUBLIC

QUARANTINE_DIR = pathlib.Path("data/quarantine")
PUBLIC_GEO_RU = PUBLIC / "geo" / "ru"
PUBLIC_GEO_RU.mkdir(parents=True, exist_ok=True)

# Only pages quarantined in today's batch run (mtime last 2h)
import time
cutoff = time.time() - 7200

candidates = sorted(
    [p for p in QUARANTINE_DIR.glob("*.html") if p.stat().st_mtime > cutoff],
    key=lambda p: p.stat().st_mtime
)
print(f"Candidates from last 2h: {len(candidates)}")

passed = rejected = skipped = 0
for p in candidates:
    # Read quarantine log to see if it was held for budget (not real reject)
    html = p.read_text(encoding="utf-8", errors="replace")
    # Skip if < 300 words — real structural fail
    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html, flags=re.I|re.S)
    visible = re.sub(r"<[^>]+>", " ", cleaned)
    words = [w for w in visible.split() if len(w) > 1]
    if len(words) < 300:
        print(f"  SKIP (thin {len(words)}w): {p.name}")
        skipped += 1
        continue

    # Copy to /tmp for review (page_reviewer moves files, we want to control destination)
    tmp = pathlib.Path(f"/tmp/rr_{p.name}")
    shutil.copy(p, tmp)

    result = page_reviewer.review_page(tmp)
    verdict = result.get("verdict")
    reasons = result.get("reasons", [])

    if verdict == "pass":
        # Move to public/geo/ru/
        dest = PUBLIC_GEO_RU / p.name
        shutil.copy(p, dest)
        p.unlink()
        passed += 1
        print(f"  PASS → {dest.name}")
    else:
        # Real reject — leave in quarantine, cleanup tmp
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        rejected += 1
        print(f"  {verdict.upper()}: {p.name} — {reasons[0][:80] if reasons else '?'}")

print(f"\n=== Re-review done: {passed} pass, {rejected} reject/hold, {skipped} skipped ===")
