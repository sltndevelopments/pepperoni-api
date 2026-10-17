#!/usr/bin/env python3
"""Metrika queue stub in <head> on every delayed-analytics page.

init is queued in <head> (first call, once). tag.js stays delayed. Goals
fired before load (micro_form_start, lead submit) land on ym.a after init.
This test never fetches mc.yandex.ru or googletagmanager.com.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from landing_chrome import DELAYED_ANALYTICS, YM_INIT, YM_QUEUE_STUB, ym_queue_stub  # noqa: E402

fail = 0
STUB_BODY = "window.ym=window.ym||function(){(ym.a=ym.a||[]).push(arguments)}"
INIT_RE = re.compile(r"""ym\(\s*107064141\s*,\s*['"]init['"]""")
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


def stub_js() -> str:
    match = re.search(r"<script>(.*?)</script>", YM_QUEUE_STUB, re.I | re.S)
    return match.group(1) if match else ""


def main() -> int:
    js = stub_js()
    check(STUB_BODY in YM_QUEUE_STUB.replace(" ", ""),
          "landing_chrome stub matches the Metrika queue")
    check("ym.l=+new Date" in YM_QUEUE_STUB,
          "landing_chrome stub stamps ym.l")
    check(YM_INIT in YM_QUEUE_STUB, "landing_chrome stub queues init")
    check(STUB_BODY in js and YM_INIT in js and js.find(STUB_BODY) < js.find(YM_INIT),
          "init is queued right after the queue line")
    check("tag.js" not in YM_QUEUE_STUB and "mc.yandex.ru" not in YM_QUEUE_STUB,
          "queue stub does not load tag.js")
    check("googletagmanager" not in YM_QUEUE_STUB,
          "queue stub does not load GTM")
    check(ym_queue_stub() == YM_QUEUE_STUB, "ym_queue_stub() returns the snippet")
    check(not INIT_RE.search(DELAYED_ANALYTICS),
          "delayed loader does not call ym init")

    chrome = (SCRIPTS / "landing_chrome.py").read_text(encoding="utf-8")
    cat = (SCRIPTS / "gen_category_pages.py").read_text(encoding="utf-8")
    index_src = (SCRIPTS / "gen-index.py").read_text(encoding="utf-8")
    check("ym_queue_stub()" in cat, "category generator emits the stub")
    check("ym_queue_stub()" in index_src, "homepage generator emits the stub")
    check("function loadAnalytics" in chrome, "tag.js still loads from delayed analytics")
    check("mc.yandex.ru/metrika/tag.js" in DELAYED_ANALYTICS,
          "delayed loader still fetches tag.js after load")

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
        body = html.split("</head>", 1)[1] if "</head>" in html else ""
        compact = head.replace(" ", "")
        inits = INIT_RE.findall(html)
        check(STUB_BODY in compact, f"{rel} has ym queue stub in <head>")
        check("ym.l=+new Date" in head, f"{rel} stamps ym.l in <head>")
        check(INIT_RE.search(head) is not None, f"{rel} queues ym init in <head>")
        check(len(inits) == 1, f"{rel} has exactly one ym init (got {len(inits)})")
        check(INIT_RE.search(body) is None, f"{rel} delayed loader has no ym init")
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
const stub = process.argv[1];
const ctx = {
  window: {},
  document: { createElement() { throw new Error('blocked createElement'); },
              getElementsByTagName() { return [{ parentNode: { insertBefore() { throw new Error('blocked insert'); } } }]; },
              scripts: [] },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(stub, ctx);
vm.runInContext("ym(107064141,'reachGoal','micro_form_start');", ctx);
vm.runInContext("ym(107064141,'reachGoal','lead_form_submit');", ctx);
vm.runInContext(
  "(function(m,i){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};})(window,'ym');",
  ctx
);
const q = ctx.ym.a || [];
const calls = q.map(a => Array.from(a));
const methods = calls.map(a => a[1]);
if (typeof ctx.ym !== 'function') { console.log('NOFN'); process.exit(2); }
if (methods[0] !== 'init') { console.log('FIRST ' + JSON.stringify(methods)); process.exit(1); }
if (methods.filter(m => m === 'init').length !== 1) {
  console.log('DUP ' + JSON.stringify(methods)); process.exit(1);
}
if (methods.indexOf('reachGoal') < 0 || calls.every(a => a[2] !== 'micro_form_start')) {
  console.log('LOST ' + JSON.stringify(calls)); process.exit(1);
}
console.log('QUEUED ' + methods.join(','));
""",
            js,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check(node.returncode == 0 and "QUEUED" in node.stdout,
          f"init is first on ym.a, then goals ({node.stdout.strip() or node.stderr.strip()})")

    if fail:
        print(f"test_ym_queue_stub: {fail} FAIL")
        return 1
    print("test_ym_queue_stub: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
