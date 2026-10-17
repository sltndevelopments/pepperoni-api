#!/usr/bin/env python3
"""Gates for the shared kd-landing design system on listed commercial pages."""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from landing_chrome import LANDINGS, apply_chrome, stylesheet_link, topbar_html  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html_of(rel: str) -> str:
    return (ROOT / "public" / rel).read_text(encoding="utf-8")


def core_facts(html: str) -> dict:
    """Title, robots, canonical, JSON-LD — chrome must not change these."""
    title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    desc = re.search(r'<meta name="description" content="([^"]*)"', html, re.I)
    robots = re.search(r'<meta name="robots" content="([^"]*)"', html, re.I)
    canon = re.search(r'<link rel="canonical" href="([^"]*)"', html, re.I)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    lds = []
    for blob in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S | re.I
    ):
        try:
            lds.append(json.loads(blob))
        except json.JSONDecodeError:
            lds.append(blob.strip())
    return {
        "title": title.group(1).strip() if title else "",
        "desc": desc.group(1) if desc else "",
        "robots": robots.group(1) if robots else "",
        "canonical": canon.group(1) if canon else "",
        "h1": re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else "",
        "ld": lds,
    }


def git_show(rel: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:public/{rel}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


# Generated pages must not auto-commit. Only these four public JSON files
# may appear in an automatic `git add` (SKU-count reconcile output).
ALLOWED_PUBLIC_ADD = {
    "public/manifest.json",
    "public/.well-known/ai-plugin.json",
    "public/.well-known/mcp.json",
    "public/ai.json",
}

_COMMENT_LINE = re.compile(r"^\s*(#|//)")
_GIT_ADD_PY = re.compile(
    r'\[\s*[\'"]git[\'"]\s*,\s*[\'"]add[\'"]\s*,(.*?)\]',
    re.S,
)
_GIT_COMMIT_PY = re.compile(
    r'\[\s*[\'"]git[\'"]\s*,\s*[\'"]commit[\'"]\s*,(.*?)\]',
    re.S,
)
_PY_STR = re.compile(r'''['"]([^'"]+)['"]''')


def active_shell(text: str) -> str:
    """Drop comments and join backslash-continued lines (sh/yml/py)."""
    joined: list[str] = []
    buf = ""
    for raw in text.splitlines():
        if _COMMENT_LINE.match(raw):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        joined.append(buf + line)
        buf = ""
    if buf.strip():
        joined.append(buf)
    return "\n".join(joined)


def format_hits(hits: list[str]) -> str:
    if not hits:
        return ""
    preview = "; ".join(hits[:6])
    extra = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
    return f": {preview}{extra}"


def _is_dot_path(tok: str) -> bool:
    return tok in {".", "./"}


def _public_path(tok: str) -> str | None:
    cleaned = tok.strip("'\"")
    cleaned = cleaned.lstrip("./")
    if cleaned == "public" or cleaned.startswith("public/") or cleaned.startswith("public\\"):
        return cleaned.replace("\\", "/")
    return None


def _add_forbidden(rel: str, args: list[str]) -> list[str]:
    hits: list[str] = []
    paths: list[str] = []
    update_only = False
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in {"-A", "--all"}:
            hits.append(f"{rel}: git add -A/--all")
        elif tok in {"-u", "--update"}:
            update_only = True
        elif tok in {"-f", "--force", "-n", "--dry-run", "-v", "--verbose",
                     "-p", "--patch", "--ignore-errors", "--intent-to-add",
                     "--renormalize", "--refresh", "--ignore-removal"}:
            pass
        elif tok == "--":
            paths.extend(args[i + 1:])
            break
        elif tok.startswith("-"):
            pass
        else:
            paths.append(tok)
        i += 1
    if update_only and not paths:
        hits.append(f"{rel}: git add -u with no path (would stage public/)")
    for path in paths:
        if _is_dot_path(path):
            hits.append(f"{rel}: git add .")
            continue
        pub = _public_path(path)
        if pub and pub not in ALLOWED_PUBLIC_ADD:
            hits.append(f"{rel}: git add {pub}")
    return hits


def _commit_forbidden(rel: str, args: list[str]) -> list[str]:
    for tok in args:
        if tok in {"-a", "--all", "-am"}:
            return [f"{rel}: git commit -a"]
        if tok.startswith("-") and not tok.startswith("--") and "a" in tok[1:]:
            return [f"{rel}: git commit -a"]
    return []


def _shlex_args(rest: str) -> list[str]:
    try:
        return shlex.split(rest, posix=True)
    except ValueError:
        return rest.split()


def _scan_shell_text(rel: str, text: str) -> list[str]:
    hits: list[str] = []
    active = active_shell(text)
    for line in active.splitlines():
        if "print(" in line or "echo " in line or "log " in line:
            continue
        add_m = re.search(r"\bgit\s+add\b(.*)$", line)
        if add_m:
            hits.extend(_add_forbidden(rel, _shlex_args(add_m.group(1))))
        commit_m = re.search(r"\bgit\s+commit\b(.*)$", line)
        if commit_m:
            hits.extend(_commit_forbidden(rel, _shlex_args(commit_m.group(1))))
    return hits


def _scan_python(rel: str, text: str) -> list[str]:
    hits = _scan_shell_text(rel, text)
    for match in _GIT_ADD_PY.finditer(text):
        args = _PY_STR.findall(match.group(1))
        hits.extend(_add_forbidden(rel, args))
    for match in _GIT_COMMIT_PY.finditer(text):
        args = _PY_STR.findall(match.group(1))
        hits.extend(_commit_forbidden(rel, args))
    return hits


def _scan_workflow(rel: str, text: str) -> list[str]:
    hits = _scan_shell_text(rel, text)
    # git-auto-commit-action file_pattern is a commit of those paths.
    in_pattern = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if re.match(r"file_pattern\s*:", stripped):
            in_pattern = True
            inline = stripped.split(":", 1)[1].strip()
            if inline and inline != "|" and inline != ">":
                pub = _public_path(inline)
                if pub and pub not in ALLOWED_PUBLIC_ADD:
                    hits.append(f"{rel}: file_pattern {pub}")
            continue
        if in_pattern:
            if not raw.startswith(" ") and not raw.startswith("\t"):
                in_pattern = False
                continue
            if stripped.startswith("#") or not stripped:
                continue
            if stripped.endswith(":") and not stripped.startswith("public"):
                in_pattern = False
                continue
            pub = _public_path(stripped)
            if pub and pub not in ALLOWED_PUBLIC_ADD:
                hits.append(f"{rel}: file_pattern {pub}")
    return hits


def scan_public_git_adds() -> list[str]:
    hits: list[str] = []
    scripts = ROOT / "scripts"
    for path in sorted(scripts.rglob("*")):
        if not path.is_file() or path.suffix not in {".sh", ".py"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel == "scripts/test_landing_design.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            hits.extend(_scan_python(rel, text))
        else:
            hits.extend(_scan_shell_text(rel, text))
    workflows = ROOT / ".github" / "workflows"
    if workflows.is_dir():
        for path in sorted(workflows.iterdir()):
            if not path.is_file() or path.suffix not in {".yml", ".yaml"}:
                continue
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            hits.extend(_scan_workflow(rel, text))
    # Dedup while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for hit in hits:
        if hit not in seen:
            seen.add(hit)
            unique.append(hit)
    return unique


def main() -> int:
    css = (ROOT / "public" / "assets" / "kd-landing.css").read_text(encoding="utf-8")
    check("--brand:#16723c" in css.replace(" ", "") or "--brand: #16723c" in css,
          "shared CSS has jerky brand token")
    check(".kd-topbar" in css and "backdrop-filter" in css, "shared CSS has sticky topbar")
    check("body.kd-landing" in css and "body.kd-landing h1" in css,
          "shared CSS scopes overrides to .kd-landing")

    from content_plan_pages import shell  # noqa: E402
    sample = shell("ru", "demo-slug", "T", "D", "H1", "<p>body</p>",
                   [("Q?", "A.")])
    check("/assets/kd-landing.css" in sample, "content_plan shell links shared CSS")
    check('class="kd-landing"' in sample, "content_plan shell sets body class")
    check("kd-topbar" in sample, "content_plan shell emits topbar")

    from commercial_page import page as wrap  # noqa: E402
    comm = wrap(lang="ru", title="T", description="D",
                canonical="https://pepperoni.tatar/price",
                hreflang_ru="https://pepperoni.tatar/price",
                hreflang_en="https://pepperoni.tatar/en/price",
                nav_html="<nav></nav>", body="<h1>Прайс</h1>", slug="price")
    check("/assets/kd-landing.css" in comm and "kd-topbar" in comm,
          "commercial_page inherits shared chrome")

    src = (ROOT / "scripts" / "gen_category_pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in src and "topbar_html(" in src,
          "gen_category_pages uses shared chrome")

    check(len(LANDINGS) == 22, f"22 listed landings (got {len(LANDINGS)})")

    for rel, lang, slug in LANDINGS:
        html = html_of(rel)
        check("/assets/kd-landing.css" in html, f"{rel} links shared CSS")
        check("kd-landing" in html and "kd-topbar" in html, f"{rel} has chrome")
        check(html.count("<h1") == html.lower().count("<h1"), f"{rel} h1 well-formed")
        h1n = len(re.findall(r"<h1\b", html, re.I))
        check(h1n == 1, f"{rel} still one H1 ({h1n})")
        again = apply_chrome(html, lang, slug)
        check(again == apply_chrome(again, lang, slug), f"{rel} apply is idempotent")
        old = git_show(rel)
        if old is None:
            check(False, f"{rel} exists in HEAD for fact compare")
            continue
        check(core_facts(old) == core_facts(html),
              f"{rel} title/desc/robots/canonical/h1/JSON-LD unchanged")

    # Chrome helpers stay fact-free
    bar = topbar_html("ru", "price")
    check("tel:+79872170202" in bar and "info@" not in bar.split("tel:")[0],
          "topbar uses canonical phone")
    check('class="kd-navwrap"' in bar and 'class="kd-navtoggle"' in bar,
          "topbar has details/summary hamburger")
    check('href="/delivery"' in bar and 'href="/about"' in bar,
          "RU topbar has Доставка and О компании")
    en_bar = topbar_html("en", "price")
    check('href="/en/delivery"' in en_bar and 'href="/en/about"' in en_bar,
          "EN topbar has Delivery and About")
    check('class="kd-langs"' in bar and 'href="/en/price"' in bar,
          "RU topbar has language switch to EN")
    check('class="kd-langs"' in en_bar and 'href="/price"' in en_bar,
          "EN topbar has language switch to RU")
    compact = css.replace(" ", "").replace("\n", "")
    check(".kd-topnav--wide" in css and ".kd-navwrap{display:none;}" in compact,
          "desktop CSS shows wide nav and hides the hamburger")
    check(".kd-topnav--wide{display:none;}" in compact
          and ".kd-navwrap{display:block;" in compact,
          "CSS shows hamburger panel under 900px instead of hiding nav")
    check(stylesheet_link().startswith("<!-- kd-landing-css:start -->"),
          "stylesheet marker present")

    uz_src = (ROOT / "scripts" / "content_plan_pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in uz_src and 'topbar_html(lang, "export/uzbekistan")' in uz_src,
          "write_uzbekistan emits shared chrome")
    exp_src = (ROOT / "scripts" / "gen_export_pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in exp_src and "topbar_html(" in exp_src,
          "gen_export_pages emit shared chrome")
    geo_src = (ROOT / "scripts" / "gen-geo-pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in geo_src and "topbar_html(" in geo_src,
          "gen-geo-pages emit shared chrome")

    no_public_auto_commit_hits = scan_public_git_adds()
    check(not no_public_auto_commit_hits,
          "scripts and workflows do not git-add public/ HTML "
          f"(except allowed JSON){format_hits(no_public_auto_commit_hits)}")

    agent_sh = (ROOT / "scripts" / "seo-agent-vps.sh").read_text(encoding="utf-8")
    check("deploy_check.py --inject" not in active_shell(agent_sh)
          and "deploy_check.py --verify" not in active_shell(agent_sh),
          "seo-agent-vps.sh does not run deploy_check --inject/--verify")
    check("git reset -q" in agent_sh and r"^public/.*\.html$" in agent_sh,
          "seo-agent-vps.sh unstages public/**/*.html before commit")
    sweep_src = (ROOT / "scripts" / "tech_debt_sweep.py").read_text(encoding="utf-8")
    check("deploy_check.py" not in sweep_src
          or "--inject" not in sweep_src and "--verify" not in sweep_src,
          "tech_debt_sweep.py does not call deploy_check --inject/--verify")

    former = {
        "price.html": ["/", "/kak-zakazat", "/delivery", "/about", "/en/price"],
        "kak-zakazat.html": ["/", "/price", "/delivery", "/about", "/en/kak-zakazat"],
        "en/price.html": ["/en/", "/en/kak-zakazat", "/en/delivery", "/en/about", "/price"],
        "en/kak-zakazat.html": ["/en/", "/en/price", "/en/delivery", "/en/about", "/kak-zakazat"],
    }
    for rel, hrefs in former.items():
        page = html_of(rel)
        missing = [h for h in hrefs if f'href="{h}"' not in page]
        check(not missing, f"{rel} keeps former nav links {hrefs}")

    if fail:
        print(f"test_landing_design: {fail} FAIL")
        return 1
    print("test_landing_design: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
