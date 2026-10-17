#!/usr/bin/env python3
"""LCP hubs: no font preload, no eager lead-form.js; lazy loader injects once."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PUBLIC = ROOT / "public"
sys.path.insert(0, str(SCRIPTS))

from landing_chrome import (  # noqa: E402
    LCP_RENDER_SLUGS,
    font_lcp_hints,
    lead_form_tag,
    lazy_lead_form_script,
)

fail = 0
HUBS = (
    "sosiski-dlya-hotdog.html",
    "en/sosiski-dlya-hotdog.html",
    "kotlety-dlya-burgerov.html",
    "sosiski-halyal-optom.html",
)
BLOCKED = ("mc.yandex.ru", "googletagmanager", "googleadservices")


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    check(LCP_RENDER_SLUGS == {
        "sosiski-dlya-hotdog",
        "kotlety-dlya-burgerov",
        "sosiski-halyal-optom",
    }, "lazy loader applies to the four hub slugs")

    hints = font_lcp_hints("sosiski-dlya-hotdog")
    check("font-display:swap" in hints.replace(" ", ""), "font-face keeps swap")
    check('rel="preload"' not in hints and "as=\"font\"" not in hints,
          "font_lcp_hints no longer preloads f0.woff2")

    tag = lead_form_tag("sosiski-dlya-hotdog")
    check("<script src=" not in tag and "lead-form.js" in tag,
          "LCP hubs inline the lazy loader, not a script src")
    check("kd-lead-form-lazy" in tag, "lazy snippet has a stable id")
    other = lead_form_tag("kazylyk")
    check("lead-form.js" in other and "defer" in other,
          "non-hub pages still defer lead-form.js")

    lead_js = (PUBLIC / "assets" / "lead-form.js").read_text(encoding="utf-8")
    # conversion_async.js must not start at parse — only inside ensureAdsConvReady.
    before_fn = lead_js.split("function ensureAdsConvReady", 1)[0]
    check("loadScriptOnce" not in before_fn or "conversion_async.js" not in before_fn
          or "loadScriptOnce(ADS_CONV_SRC" not in before_fn,
          "lead-form.js does not load conversion_async.js on parse")
    check("loadScriptOnce(ADS_CONV_SRC" in lead_js.split("function ensureAdsConvReady", 1)[-1],
          "lead-form.js loads conversion_async.js inside ensureAdsConvReady")
    check("ensureAdsConvReady" in lead_js and "conversion_async.js" in lead_js,
          "lead-form.js loads conversion_async.js at submit")
    check("window.__leadFormJs = true" in lead_js.replace(" ", "")
          or "window.__leadFormJs=true" in lead_js.replace(" ", ""),
          "lead-form.js marks itself loaded")

    for rel in HUBS:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        head = html.split("</head>", 1)[0]
        check(
            not re.search(r'<script(?![^>]*id="kd-lead-form-lazy")[^>]*\ssrc=["\']/assets/lead-form\.js', html, re.I),
            f"{rel} has no <script src=lead-form.js>",
        )
        check('id="kd-lead-form-lazy"' in html, f"{rel} inlines #kd-lead-form-lazy")
        check('action="/lead-submit"' in html, f"{rel} form action is /lead-submit")
        check('method="POST"' in html, f"{rel} form method is POST")
        font_preloads = [
            tag for tag in re.findall(r"<link[^>]+>", head, re.I)
            if re.search(r'rel=["\']preload["\']', tag, re.I) and "f0.woff2" in tag
        ]
        check(not font_preloads, f"{rel} has no f0.woff2 preload")
        if "sosiski-halyal-optom" in rel or "kotlety-dlya-burgerov" in rel:
            check("<picture>" in html and 'type="image/webp"' in html,
                  f"{rel} hero uses a WebP picture")
            check('width="640"' in html and 'height="427"' in html,
                  f"{rel} hero declares 640×427")
            check(".webp" in html, f"{rel} references a .webp srcset")
            # JSON-LD Product.image stays JPEG
            ld = "".join(re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.I | re.S
            ))
            if "Product" in ld:
                check(".webp" not in ld or "image/webp" not in ld,
                      f"{rel} Product.image is not switched to WebP")

    lazy_src = (SCRIPTS / "lead_form_lazy.js").read_text(encoding="utf-8")
    node = subprocess.run(
        [
            "node",
            "-e",
            r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(process.argv[1], 'utf8');
const scripts = [];
const observed = [];
const listeners = {};
const forms = [{ matches(sel){ return sel === 'form.lead-form'; }, closest(){ return this; } }];
const fakeIo = function(cb, opts){
  this.cb = cb; this.opts = opts; this.observed = observed;
  fakeIo.last = this;
};
fakeIo.prototype.observe = function(el){ observed.push(el); };
fakeIo.prototype.disconnect = function(){ this.dead = true; };
const ctx = {
  window: {},
  document: {
    currentScript: { getAttribute(name){ return name === 'data-src' ? '/assets/lead-form.js' : null; } },
    createElement(tag){
      if (tag !== 'script') throw new Error('blocked createElement ' + tag);
      const el = { src: '', async: false, onload: null, onerror: null };
      scripts.push(el);
      return el;
    },
    head: { appendChild(el){ scripts.at(-1).appended = true; } },
    documentElement: {},
    querySelectorAll(sel){ return sel === 'form.lead-form' ? forms : []; },
    addEventListener(type, fn){ (listeners[type] = listeners[type] || []).push(fn); },
    readyState: 'complete',
  },
  IntersectionObserver: fakeIo,
  setTimeout(fn){ ctx.__timeouts = ctx.__timeouts || []; ctx.__timeouts.push(fn); return 1; },
  requestIdleCallback: null,
  Event: function(type){ this.type = type; this.bubbles = true; },
};
ctx.window = ctx;
ctx.globalThis = ctx;
ctx.__peppLeadFormLazyTest = true;
vm.createContext(ctx);
vm.runInContext(src, ctx);
if (typeof ctx.__peppInjectLeadForm !== 'function') { console.log('NOINJECT'); process.exit(1); }
if (typeof ctx.__peppArmLeadFormLazy !== 'function') { console.log('NOARM'); process.exit(1); }
ctx.__peppArmLeadFormLazy();
ctx.__peppInjectLeadForm();
ctx.__peppInjectLeadForm();
if (scripts.length !== 1) { console.log('DUP ' + scripts.length); process.exit(1); }
if (scripts[0].src !== '/assets/lead-form.js') { console.log('SRC ' + scripts[0].src); process.exit(1); }
if (!fakeIo.last || fakeIo.last.opts.rootMargin !== '600px 0px') {
  console.log('IO ' + JSON.stringify(fakeIo.last && fakeIo.last.opts)); process.exit(1);
}
if (!listeners.focusin || !listeners.pointerdown || !listeners.touchstart || !listeners.submit) {
  console.log('EV ' + Object.keys(listeners)); process.exit(1);
}
if (!ctx.__timeouts || !ctx.__timeouts.length) { console.log('NOIDLE'); process.exit(1); }
const blocked = ['mc.yandex.ru','googletagmanager','googleadservices'];
const dumped = JSON.stringify(scripts) + src;
for (const host of blocked) {
  if (dumped.includes(host)) { console.log('HOST ' + host); process.exit(1); }
}
console.log('LAZY_OK injects=1 io=600 triggers=focusin,pointerdown,touchstart,idle');
""",
            str(SCRIPTS / "lead_form_lazy.js"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check(node.returncode == 0 and "LAZY_OK" in node.stdout,
          f"lazy loader injects once and arms the triggers"
          f" ({node.stdout.strip() or node.stderr.strip()})")
    check(all(host not in lazy_src for host in BLOCKED),
          "lazy loader source does not mention blocked analytics hosts")
    check(all(host not in lazy_lead_form_script() for host in BLOCKED),
          "inlined lazy snippet does not mention blocked analytics hosts")

    if fail:
        print(f"test_hub_lcp_lazy: {fail} FAIL")
        return 1
    print("test_hub_lcp_lazy: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
