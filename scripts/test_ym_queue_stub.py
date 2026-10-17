#!/usr/bin/env python3
"""Metrika queue stub in <head> on every delayed-analytics page.

tag.js stays delayed. Goals fired before load (micro_form_start, lead submit)
must land on ym.a, not throw. The stub does not fetch mc.yandex.ru.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from landing_chrome import YM_QUEUE_STUB, ym_queue_stub  # noqa: E402

fail = 0
STUB_BODY = "window.ym=window.ym||function(){(ym.a=ym.a||[]).push(arguments)}"
DELAYED_PAGES = (
    "sosiski-dlya-hotdog.html",
    "en/sosiski-dlya-hotdog.html",
    "kotlety-dlya-burgerov.html",
    "sosiski-halyal-optom.html",
    "index.html",
    "en/index.html",
)


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    check(STUB_BODY in YM_QUEUE_STUB.replace(" ", ""),
          "landing_chrome stub matches the Metrika queue")
    check("ym.l=+new Date" in YM_QUEUE_STUB,
          "landing_chrome stub stamps ym.l")
    check("tag.js" not in YM_QUEUE_STUB and "mc.yandex.ru" not in YM_QUEUE_STUB,
          "queue stub does not load tag.js")
    check(ym_queue_stub() == YM_QUEUE_STUB, "ym_queue_stub() returns the snippet")

    chrome = (SCRIPTS / "landing_chrome.py").read_text(encoding="utf-8")
    cat = (SCRIPTS / "gen_category_pages.py").read_text(encoding="utf-8")
    index_src = (SCRIPTS / "gen-index.py").read_text(encoding="utf-8")
    check("ym_queue_stub()" in cat, "category generator emits the stub")
    check("ym_queue_stub()" in index_src, "homepage generator emits the stub")
    check("function loadAnalytics" in chrome, "tag.js still loads from delayed analytics")

    found = sorted(
        path.relative_to(PUBLIC).as_posix()
        for path in PUBLIC.rglob("*.html")
        if "function loadAnalytics" in path.read_text(encoding="utf-8")
    )
    check(found == sorted(DELAYED_PAGES),
          f"delayed-analytics pages are the hubs plus / ({found})")

    for rel in DELAYED_PAGES:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        head = html.split("</head>", 1)[0]
        compact = head.replace(" ", "")
        check(STUB_BODY in compact, f"{rel} has ym queue stub in <head>")
        check("ym.l=+new Date" in head, f"{rel} stamps ym.l in <head>")
        check("metrika/tag.js" not in head, f"{rel} does not fetch tag.js from <head>")
        check("mc.yandex.ru/metrika/tag.js" in html,
              f"{rel} still loads tag.js after load")
        check("setTimeout(loadAnalytics" in html or "requestIdleCallback" in html,
              f"{rel} keeps tag.js behind the delayed-analytics gate")

    node = subprocess.run(
        [
            "node",
            "-e",
            r"""
const vm = require('vm');
const ctx = { window: {} };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(
  "window.ym=window.ym||function(){(ym.a=ym.a||[]).push(arguments)};ym.l=+new Date;",
  ctx
);
vm.runInContext("ym(107064141,'reachGoal','micro_form_start');", ctx);
vm.runInContext("ym(107064141,'reachGoal','lead_form_submit');", ctx);
vm.runInContext(
  "(function(m,i){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};})(window,'ym');",
  ctx
);
const q = ctx.ym.a || [];
const names = q.map(a => Array.from(a)[2]);
if (typeof ctx.ym !== 'function') { console.log('NOFN'); process.exit(2); }
if (names.indexOf('micro_form_start') < 0 || names.indexOf('lead_form_submit') < 0) {
  console.log('LOST ' + JSON.stringify(names));
  process.exit(1);
}
console.log('QUEUED ' + names.join(','));
""",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check(node.returncode == 0 and "QUEUED" in node.stdout,
          f"pre-load reachGoal stays on ym.a ({node.stdout.strip() or node.stderr.strip()})")

    if fail:
        print(f"test_ym_queue_stub: {fail} FAIL")
        return 1
    print("test_ym_queue_stub: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
