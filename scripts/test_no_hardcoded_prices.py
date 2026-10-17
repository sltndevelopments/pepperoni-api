#!/usr/bin/env python3
"""Gate: no price may be hardcoded. Sheet → products.json is the only source.

Part A — source (every scripts/**/*.py, scripts/**/*.{mjs,js}, lib/**, templates/**):
tokenize Python (STRING + FSTRING_* on 3.12+) and scan JS/templates as text.
Fail on currency-marked tokens and numeric assignments to price/PRICE/rub/usd names.

Part B — generated HTML / meta / llms / wholesale lists / JSON-LD / feeds:
currency-marked amounts near a KD-NNN must equal that SKU; Offers require
sku/url → SKU mapping; unbound paragraph/meta prices need a SKU or stamp marker.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tokenize
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PUBLIC = ROOT / "public"
LIB = ROOT / "lib"
TEMPLATES = ROOT / "templates"
sys.path.insert(0, str(SCRIPTS))
from catalog_prices import (  # noqa: E402
    catalog,
    header_unit,
    infer_unit,
    iter_jsonld_nodes,
    iter_ld_offers,
    num,
    rub,
    sku_amounts,
    sku_amounts_for,
)

ALLOW_SOURCE = {
    (ROOT / "public" / "products.json").resolve(),
    (SCRIPTS / "sync-sheets.py").resolve(),
    (SCRIPTS / "sync-sheets.mjs").resolve(),
}

# Per-file allowlist: only these negative-assertion / non-catalog files
# may contain the listed tokens. Not a global substring skip.
FORBIDDEN_STALE_OK: dict[str, frozenset[str]] = {
    "scripts/test_review_fixes.py": frozenset({"$0.91", "68,77", "68.77"}),
    "scripts/test_no_hardcoded_prices.py": frozenset({
        "$0.91", "68,77", "68.77", "$34.68", "$1", "$2",
    }),
    "scripts/check_catalog_sanity.py": frozenset({"$34.68"}),
    "scripts/pplx_client.py": frozenset({"SEARCH_FEE_USD = 0.005"}),
    "scripts/market_pulse.py": frozenset({"$0"}),
    "scripts/telegram_bot.py": frozenset({"$0.01"}),
    "scripts/test_vps_git_recon.py": frozenset({"$1", "$2"}),
}

STRING_TYPES = {tokenize.STRING}
if hasattr(tokenize, "FSTRING_MIDDLE"):
    STRING_TYPES.add(tokenize.FSTRING_MIDDLE)
    STRING_TYPES.add(tokenize.FSTRING_START)
    STRING_TYPES.add(tokenize.FSTRING_END)

# Longest-first so 1,854.27 / 3531,79 win over a tail fragment.
_AMT = (
    r"(?<![\d.,\-A-Za-z])"
    r"(?:\d{1,3}(?:,\d{3})+\.\d{2}"
    r"|\d{1,3}(?:[ \u00a0\u202f]\d{3})+[.,]\d{2}"
    r"|\d+[.,]\d{1,2}"
    r"|\d{2,5})"
    r"(?![\d])"
)
MONEY_IN_STRING = re.compile(
    rf"""
    (?:
        {_AMT}\s*(?:₽|руб(?:\.|лей)?|\bRUB\b)
        | (?:₽|руб(?:\.|лей)?|\bRUB\b)\s*{_AMT}
        | (?<![\w\\'\"])\$(?!0(?:\.0+)?\b){_AMT}
        | \bUSD\s+{_AMT}
        | {_AMT}\s+USD\b
        | \bKZT\s+{_AMT}
        | {_AMT}\s+KZT\b
        | ["']price["']\s*:\s*["']?\d+(?:\.\d+)?["']?
    )
    """,
    re.X | re.I,
)

def is_price_name(name: str) -> bool:
    if re.search(r"price", name, re.I):
        return True
    return name in {"rub", "usd", "RUB", "USD", "kzt", "KZT"}
SKU_RE = re.compile(r"\bKD-\d{3}\b", re.I)
STAMP_SKU_RE = re.compile(
    r'data-catalog-price=["\'](KD-\d{3})["\']',
    re.I,
)
NUMERIC_PRICE_STR = re.compile(r"^\d+(?:[.,]\d+)?$")
LD_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
META_RE = re.compile(
    r'<meta\s+[^>]*(?:name|property)=["\'](?:description|og:description|twitter:description)["\'][^>]*>',
    re.I,
)
P_RE = re.compile(r"<p\b[^>]*>.*?</p>", re.I | re.S)
CURRENCY_AMOUNT = re.compile(
    rf"""
    (?:
        (?P<a1>{_AMT})\s*(?P<c1>₽|руб(?:\.|лей)?|RUB|USD|KZT)
        | (?P<c2>USD|KZT|RUB|₽|руб(?:\.|лей)?)\s*(?P<a2>{_AMT})
        | \$(?P<a3>{_AMT})
    )
    """,
    re.X | re.I,
)
SKIP_AFTER_AMOUNT = re.compile(
    r"^\s*(?:M\b|млн|млрд|/\$|/ч\b|/h\b)"
)
SKIP_KG_ONLY = re.compile(r"^\s*(?:/кг|/kg\b)")
AFTER_PIECE = re.compile(r"^\s*(?:/шт|/pc\b|/pcs\b)")
TABLE_RE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.I | re.S)
TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
TH_RE = re.compile(r"<th\b[^>]*>(.*?)</th>", re.I | re.S)
TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.I | re.S)
SKIP_GENERATED_PAGES = {
    "dashboard.html",
    "en/dashboard.html",
}
LOCALE_SKIP = ("hy/", "tg/", "ka/", "kk/", "ky/", "uz/", "az/", "zh/", "ar/", "he/",
               "1/", "2/", "3/", "4/", "5/")


def close(a: float | None, b: float | None, tol: float = 0.011) -> bool:
    if a is None or b is None:
        return False
    if abs(a - b) <= tol:
        return True
    # Cards/index often show 61.81 as 62 ₽
    if abs(a - round(a)) < 1e-9 and abs(round(b) - a) <= 0.5:
        return True
    return False


def accepted_amounts() -> set[float]:
    out: set[float] = set()
    rubs: list[float] = []
    pack: list[float] = []
    for sku, row in catalog()["by_sku"].items():
        out |= sku_amounts(sku)
        rubs.append(rub(sku))
        pack_price = num((row.get("offers") or {}).get("price"))
        if pack_price:
            pack.append(pack_price)
    if rubs:
        out.add(round(min(rubs), 2))
        out.add(round(max(rubs), 2))
        out.add(round(sum(rubs) / len(rubs), 2))
    if pack:
        out.add(round(sum(pack) / len(pack), 2))
    return out


def _rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _stale_ok(rel: str, token: str) -> bool:
    allowed = FORBIDDEN_STALE_OK.get(rel)
    return bool(allowed) and any(stale in token for stale in allowed)


def source_files() -> list[Path]:
    files: list[Path] = []
    files.extend(SCRIPTS.rglob("*.py"))
    files.extend(SCRIPTS.rglob("*.mjs"))
    files.extend(SCRIPTS.rglob("*.js"))
    if LIB.is_dir():
        files.extend(LIB.rglob("*.mjs"))
        files.extend(LIB.rglob("*.js"))
    if TEMPLATES.is_dir():
        files.extend(p for p in TEMPLATES.rglob("*") if p.is_file())
    out, seen = [], set()
    for path in files:
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in ALLOW_SOURCE or resolved in seen:
            continue
        if "__pycache__" in path.parts:
            continue
        if path.name in {
            "test_no_hardcoded_prices.py",
            "test_no_hardcoded_prices_mutation.py",
            "test_stamp_catalog_prices.py",
            "test_blog_price_per_piece.py",
        }:
            continue
        seen.add(resolved)
        out.append(path)
    return sorted(out)


def _strip_string_token(raw: str) -> str:
    body = raw
    i = 0
    while i < len(body) and body[i] in "rRuUfFbB":
        i += 1
    body = body[i:]
    if len(body) >= 2 and body[0] in {'"', "'"}:
        quote = body[0]
        if body.startswith(quote * 3) and body.endswith(quote * 3):
            return body[3:-3]
        return body[1:-1]
    return raw


def _dict_price_key(tokens: list, i: int) -> bool:
    """True for {"primary_price_rub": "274"} — a price-ish key, then :, then a number string."""
    j = i - 1
    while j >= 0 and tokens[j].type in {tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT}:
        j -= 1
    if j < 0 or tokens[j].string != ":":
        return False
    k = j - 1
    while k >= 0 and tokens[k].type in {tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT}:
        k -= 1
    if k < 0 or tokens[k].type != tokenize.STRING:
        return False
    return bool(re.search(r"price", tokens[k].string, re.I))


def scan_python_source(rel: str, src: bytes) -> list[str]:
    hits = []
    try:
        tokens = list(tokenize.tokenize(iter(src.splitlines(True)).__next__))
    except tokenize.TokenError as exc:
        return [f"{rel} tokenize error: {exc}"]
    for i, tok in enumerate(tokens):
        if tok.type in STRING_TYPES:
            body = _strip_string_token(tok.string) if tok.type == tokenize.STRING else tok.string
            if tok.type in {getattr(tokenize, "FSTRING_START", -1),
                            getattr(tokenize, "FSTRING_END", -2)}:
                body = tok.string
            for m in MONEY_IN_STRING.finditer(body):
                token = m.group(0)
                if _stale_ok(rel, token):
                    continue
                hits.append(f"{rel}:{tok.start[0]} hardcoded {token!r}")
            if NUMERIC_PRICE_STR.match(body.strip()) and _dict_price_key(tokens, i):
                hits.append(f"{rel}:{tok.start[0]} hardcoded price string {body!r}")
        if tok.type == tokenize.NAME and is_price_name(tok.string):
            j = i + 1
            while j < len(tokens) and tokens[j].type in {tokenize.NL, tokenize.NEWLINE,
                                                         tokenize.INDENT, tokenize.DEDENT,
                                                         tokenize.COMMENT}:
                j += 1
            if j < len(tokens) and tokens[j].string == "=":
                k = j + 1
                while k < len(tokens) and tokens[k].type in {tokenize.NL, tokenize.NEWLINE,
                                                             tokenize.COMMENT}:
                    k += 1
                if k < len(tokens) and tokens[k].type == tokenize.NUMBER:
                    hits.append(
                        f"{rel}:{tok.start[0]} hardcoded {tok.string} = {tokens[k].string}"
                    )
                elif k < len(tokens) and tokens[k].type == tokenize.STRING:
                    body = _strip_string_token(tokens[k].string)
                    if NUMERIC_PRICE_STR.match(body.strip()):
                        hits.append(
                            f"{rel}:{tok.start[0]} hardcoded {tok.string} = {tokens[k].string}"
                        )
    hits.extend(scan_python_ast(rel, src))
    return hits


def _ast_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _ast_numeric_price(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return None
        if isinstance(node.value, (int, float)):
            return repr(node.value) if isinstance(node.value, float) else str(node.value)
        if isinstance(node.value, str) and NUMERIC_PRICE_STR.match(node.value.strip()):
            return json.dumps(node.value)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"str", "int", "float"} and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and not isinstance(arg.value, bool):
                return f"{node.func.id}({arg.value})"
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and NUMERIC_PRICE_STR.match(arg.value.strip())
            ):
                return f"{node.func.id}({arg.value!r})"
    return None


def scan_python_ast(rel: str, src: bytes) -> list[str]:
    """Catch price = str(274) and price: str = \"274\" (tokenize misses both)."""
    hits: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return hits

    class Visitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign) -> None:
            lit = _ast_numeric_price(node.value)
            if lit:
                for target in node.targets:
                    name = _ast_name(target)
                    if name and is_price_name(name):
                        hits.append(f"{rel}:{node.lineno} hardcoded {name} = {lit}")
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is None:
                return self.generic_visit(node)
            lit = _ast_numeric_price(node.value)
            name = _ast_name(node.target)
            if lit and name and is_price_name(name):
                ann = ast.unparse(node.annotation) if node.annotation is not None else ""
                suffix = f": {ann} = {lit}" if ann else f" = {lit}"
                hits.append(f"{rel}:{node.lineno} hardcoded {name}{suffix}")
            self.generic_visit(node)

    Visitor().visit(tree)
    return hits


def scan_text_source(rel: str, text: str) -> list[str]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in MONEY_IN_STRING.finditer(line):
            token = m.group(0)
            if _stale_ok(rel, token):
                continue
            hits.append(f"{rel}:{i} hardcoded {token!r}")
        for m in re.finditer(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)\b", line
        ):
            if is_price_name(m.group(1)):
                hits.append(f"{rel}:{i} hardcoded {m.group(1)} = {m.group(2)}")
        for m in re.finditer(
            r"""\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"](\d+(?:[.,]\d+)?)['\"]""",
            line,
        ):
            if is_price_name(m.group(1)):
                hits.append(f"{rel}:{i} hardcoded {m.group(1)} = {m.group(2)!r}")
    return hits


def scan_source_text(rel: str, text: str) -> list[str]:
    if rel.endswith(".py"):
        return scan_python_source(rel, text.encode("utf-8"))
    return scan_text_source(rel, text)


def scan_source_file(path: Path) -> list[str]:
    rel = _rel(path)
    if path.suffix == ".py":
        return scan_python_source(rel, path.read_bytes())
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return scan_text_source(rel, text)


def parse_ld(html: str, rel: str = "") -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    issues: list[str] = []
    for raw in LD_RE.findall(html):
        try:
            node = json.loads(raw)
        except json.JSONDecodeError as exc:
            if rel:
                issues.append(f"{rel} malformed JSON-LD: {exc}")
            continue
        out.extend(n for n in iter_jsonld_nodes(node) if isinstance(n, dict))
    return out, issues


def _amount(m: re.Match) -> float | None:
    raw = m.group("a1") or m.group("a2") or m.group("a3")
    if not raw:
        return None
    if raw.count(",") == 1 and raw.count(".") == 1 and raw.index(",") < raw.index("."):
        raw = raw.replace(",", "")
    return num(raw)


def _nearby_skus(text: str, start: int, end: int, window: int = 220) -> set[str]:
    chunk = text[max(0, start - window):end + window]
    return {s.upper() for s in SKU_RE.findall(chunk)}


def _card_sku(rel: str) -> str:
    m = re.search(r"(?:^|/)products/(kd-\d{3})\.html$", rel, re.I)
    return m.group(1).upper() if m else ""


def check_amount(rel: str, amount: float, skus: set[str], accepted: set[float],
                 stamp_sku: str | None, unbound_ok: bool,
                 unit: str | None = None, field: str | None = None) -> str | None:
    if stamp_sku:
        try:
            allowed = sku_amounts_for(stamp_sku, unit, field)
        except KeyError:
            return f"{rel} stamped {amount} for unknown {stamp_sku}"
        if any(close(amount, x, 0.051) for x in allowed):
            return None
        return f"{rel} stamped {amount} for {stamp_sku} != products.json"
    if skus:
        for sku in skus:
            try:
                allowed = sku_amounts_for(sku, unit, field)
            except KeyError:
                return f"{rel} {amount} next to unknown {sku}"
            if any(close(amount, x, 0.051) for x in allowed):
                return None
        if unbound_ok and unit is None and field is None and round(amount, 2) in accepted:
            return None
        return f"{rel} {amount} next to {sorted(skus)} != products.json"
    if unbound_ok and round(amount, 2) in accepted:
        return None
    if unbound_ok:
        return f"{rel} {amount} is not a catalog amount"
    return f"{rel} {amount} has no KD-NNN / stamp (hardcoded visible price)"


def _stamp_at(text: str, start: int) -> tuple[str | None, str | None]:
    window = text[max(0, start - 500):start]
    for tag in reversed(list(re.finditer(r"<([A-Za-z][\w:-]*)\b[^>]*>", window))):
        raw = tag.group(0)
        found = re.search(r'data-catalog-price=["\'](KD-\d{3})["\']', raw, re.I)
        if not found:
            continue
        if re.search(rf"</{re.escape(tag.group(1))}\b", window[tag.end():], re.I):
            continue
        field_m = re.search(r'data-price-field=["\']([^"\']+)["\']', raw, re.I)
        return found.group(1).upper(), (field_m.group(1) if field_m else None)
    return None, None


def _stamp_sku_at(text: str, start: int) -> str | None:
    sku, _field = _stamp_at(text, start)
    return sku


def _visible_html(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
    return html


def scan_visible_text(rel: str, text: str, accepted: set[float],
                      *, unbound_ok: bool = True,
                      page_skus: set[str] | None = None) -> list[str]:
    issues = []
    card = _card_sku(rel)
    page_skus = page_skus or {s.upper() for s in SKU_RE.findall(text)}
    for m in CURRENCY_AMOUNT.finditer(text):
        amount = _amount(m)
        if amount is None or amount <= 0:
            continue
        after = text[m.end():m.end() + 12]
        if SKIP_AFTER_AMOUNT.match(after):
            continue
        stamp_sku, stamp_field = _stamp_at(text, m.start())
        skus = _nearby_skus(text, m.start(), m.end())
        if stamp_sku:
            skus.add(stamp_sku)
        if card:
            skus.add(card)
        if SKIP_KG_ONLY.match(after) and not skus:
            continue
        after_ctx = re.sub(r"<[^>]+>", " ", text[m.end():m.end() + 40])
        cut = re.search(r"[\n\r)(]|\d{2,}", after_ctx)
        if cut:
            after_ctx = after_ctx[:cut.start()]
        before_ctx = re.sub(r"<[^>]+>", " ", text[max(0, m.start() - 24):m.start()])
        unit = infer_unit(after_ctx)
        if unit is None and re.search(
            r"(?:без\s*ндс|excl(?:\.?\s*vat)?)\s*$", before_ctx, re.I
        ):
            unit = "excl"
        if AFTER_PIECE.match(after):
            unit = "piece"
        elif SKIP_KG_ONLY.match(after) and skus:
            unit = "kg"
        hit = check_amount(rel, amount, skus, accepted, stamp_sku, unbound_ok,
                           unit=unit, field=stamp_field)
        if hit:
            issues.append(hit)
    return issues


def scan_html_loose_text(rel: str, html: str, accepted: set[float]) -> list[str]:
    """Paragraphs and meta: amount must match a SKU on the page, or be stamped."""
    issues = []
    page_skus = {s.upper() for s in SKU_RE.findall(html)}
    for block in list(META_RE.findall(html)) + list(P_RE.findall(html)):
        if not CURRENCY_AMOUNT.search(block):
            continue
        issues.extend(scan_visible_text(rel, block, accepted, unbound_ok=False,
                                       page_skus=page_skus))
    return issues


def _td_amount(cell: str) -> float | None:
    text = unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ").strip()
    if text in {"", "—", "-", "–", "−"}:
        return None
    stripped = re.sub(
        r"(?:₽|руб(?:\.|лей)?|RUB|USD|KZT|/шт|/pc|/pcs|/кг|/kg|/упак\.?|/pack)",
        "",
        text,
        flags=re.I,
    )
    stripped = re.sub(r"\s+", "", stripped)
    if not re.fullmatch(
        r"\d{1,3}(?:,\d{3})+\.\d{2}|\d+[.,]\d{1,2}|\d{2,5}",
        stripped,
    ):
        return None
    return num(stripped)


def scan_price_tables(rel: str, html: str, accepted: set[float]) -> list[str]:
    """Rows under ₽/RUB/Цена/Price headers: each numeric td vs the row SKU."""
    issues = []
    for table in TABLE_RE.findall(html):
        rows = TR_RE.findall(table)
        if not rows:
            continue
        headers: list[str] = []
        for row in rows:
            found = [unescape(re.sub(r"<[^>]+>", " ", h)) for h in TH_RE.findall(row)]
            if found:
                headers = found
                break
        if not any(re.search(r"₽|RUB|Цена|Price", h, re.I) for h in headers):
            continue
        units = [header_unit(h) for h in headers]
        for row in rows:
            tds = TD_RE.findall(row)
            if not tds:
                continue
            row_text = unescape(re.sub(r"<[^>]+>", " ", row))
            skus = {s.upper() for s in SKU_RE.findall(row_text)}
            if not skus:
                continue
            for i, td in enumerate(tds):
                unit = units[i] if i < len(units) else None
                if i >= len(units):
                    unit = "any"
                if unit in {None, "skip"}:
                    continue
                amount = _td_amount(td)
                if amount is None:
                    continue
                hit = check_amount(
                    rel, amount, skus, accepted, None, False,
                    unit=None if unit == "any" else unit,
                )
                if hit:
                    issues.append(hit)
    return issues


def scan_offers(rel: str, html: str) -> list[str]:
    issues = []
    by_sku = catalog()["by_sku"]
    for raw in LD_RE.findall(html):
        try:
            root = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(f"{rel} malformed JSON-LD: {exc}")
            continue
        for sku, offer in iter_ld_offers(root):
            price = num(offer.get("price"))
            currency = offer.get("priceCurrency")
            if price is None:
                continue
            if not sku:
                issues.append(f"{rel} Offer price {price} has no sku/url → SKU mapping")
                continue
            if sku not in by_sku:
                issues.append(f"{rel} Offer sku {sku} is not in products.json")
                continue
            if currency and currency != "RUB":
                issues.append(f"{rel} {sku} Offer currency {currency} (catalog RUB)")
            if not close(price, rub(sku)):
                issues.append(f"{rel} {sku} Offer {price} != products.json {rub(sku)}")
    return issues


def scan_feeds() -> list[str]:
    issues = []
    by_sku = catalog()["by_sku"]
    yml = PUBLIC / "yml.xml"
    if yml.is_file():
        body = yml.read_text(encoding="utf-8")
        for sku, inner in re.findall(r'<offer id="(KD-\d{3})"[^>]*>(.*?)</offer>', body, re.S):
            if sku not in by_sku:
                continue
            price = num((re.search(r"<price>([^<]+)</price>", inner) or [None, None])[1])
            if price is not None and not close(price, rub(sku), 0.51):
                issues.append(f"yml.xml {sku} <price>{price} != {rub(sku)}")
    feed = PUBLIC / "products-feed.xml"
    if feed.is_file():
        body = feed.read_text(encoding="utf-8")
        for item in re.findall(r"<item>(.*?)</item>", body, re.S):
            sku_m = re.search(r"<g:id>(KD-\d{3})</g:id>", item)
            price_m = re.search(r"<g:price>([0-9.]+)\s*(\w+)</g:price>", item)
            if not sku_m or not price_m:
                continue
            sku = sku_m.group(1)
            if sku not in by_sku:
                continue
            price, currency = num(price_m.group(1)), price_m.group(2)
            if currency != "RUB":
                issues.append(f"products-feed.xml {sku} g:price {currency}")
            if price is not None and not close(price, rub(sku)):
                issues.append(f"products-feed.xml {sku} g:price {price} != {rub(sku)}")
    return issues


def scan_generated(accepted: set[float]) -> list[str]:
    issues = []
    locale_skip = LOCALE_SKIP
    for path in PUBLIC.rglob("*.html"):
        rel = path.relative_to(PUBLIC).as_posix()
        if rel.startswith(locale_skip) or rel in SKIP_GENERATED_PAGES:
            continue
        html = path.read_text(encoding="utf-8")
        issues.extend(scan_offers(rel, html))
        visible = _visible_html(html)
        issues.extend(scan_visible_text(rel, visible, accepted, unbound_ok=True))
        issues.extend(scan_price_tables(rel, visible, accepted))

    for path in list(PUBLIC.rglob("llms*.txt")) + list(PUBLIC.rglob(".well-known/llms*.txt")):
        rel = path.relative_to(PUBLIC).as_posix()
        issues.extend(scan_visible_text(rel, path.read_text(encoding="utf-8"), accepted,
                                       unbound_ok=True))

    for rel in (
        "wholesale-price-list.md",
        "wholesale-price-list-ru.md",
        "wholesale-price-list.txt",
        "wholesale-price-list-ru.txt",
    ):
        path = PUBLIC / rel
        if path.is_file():
            issues.extend(scan_visible_text(rel, path.read_text(encoding="utf-8"), accepted,
                                           unbound_ok=True))

    issues.extend(scan_feeds())
    # Dedup
    seen, uniq = set(), []
    for item in issues:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def collect_issues() -> list[str]:
    hits = []
    for path in source_files():
        hits.extend(scan_source_file(path))
    hits.extend(scan_generated(accepted_amounts()))
    return hits


def main() -> int:
    source_hits = []
    for path in source_files():
        source_hits.extend(scan_source_file(path))
    print(f"no_hardcoded_prices source: {len(source_files())} files, {len(source_hits)} hit(s)")
    fail = 0
    for hit in source_hits[:80]:
        print(f"  FAIL {hit}")
        fail += 1
    if len(source_hits) > 80:
        print(f"  … {len(source_hits) - 80} more")
        fail += len(source_hits) - 80

    accepted = accepted_amounts()
    gen_hits = scan_generated(accepted)
    print(f"no_hardcoded_prices generated: {len(gen_hits)} mismatch(es), "
          f"{len(accepted)} accepted catalog amounts")
    for hit in gen_hits[:80]:
        print(f"  FAIL {hit}")
        fail += 1
    if len(gen_hits) > 80:
        print(f"  … {len(gen_hits) - 80} more")
        fail += len(gen_hits) - 80

    if fail:
        print(f"test_no_hardcoded_prices: {fail} FAIL")
        return 1
    print("test_no_hardcoded_prices: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
