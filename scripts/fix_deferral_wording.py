#!/usr/bin/env python3
"""Replace fixed deferral day counts with contract-based wording site-wide."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

RU_PHRASE = "согласно договору"
EN_PHRASE = "as per contract"


def _sub_paren_days_after_deferral(text: str) -> str:
    """(... до N дней ...) only when отсроч* appears shortly before."""

    def repl(match: re.Match[str]) -> str:
        start = max(0, match.start() - 120)
        if "отсроч" not in text[start:match.start()].lower():
            return match.group(0)
        return f" ({RU_PHRASE})"

    return re.sub(
        r"\(\s*до\s+\d+(?:[\s\-–—]\d+)?(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?\s*\)",
        repl,
        text,
        flags=re.I,
    )


def _sub_range_days_after_deferral(text: str) -> str:
    """(от N до M дней) only when отсроч* appears shortly before."""

    def repl(match: re.Match[str]) -> str:
        start = max(0, match.start() - 120)
        if "отсроч" not in text[start:match.start()].lower():
            return match.group(0)
        return f"({RU_PHRASE})"

    return re.sub(
        r"\(\s*от\s+\d+(?:[\s\-–—]\d+)?\s+до\s+\d+(?:[\s\-–—]\d+)?(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?\s*\)",
        repl,
        text,
        flags=re.I,
    )


def _apply(text: str) -> str:
    replacements: list[tuple[str, str]] = [
        # RU — specific first
        (
            r"с\s+отсрочк(?:ой|ою)\s+платежа\s+до\s+\d+(?:[\s\-–—]\d+)?"
            r"(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?",
            f"с отсрочкой платежа {RU_PHRASE}",
        ),
        (r"с\s+отсрочка\s+платежа", f"с отсрочкой платежа"),
        (
            r"отсрочк(?:ой|ою|а|е|и)?\s+платежа\s+\d+(?:[\s\-–—]\d+)?\s*дн(?:ей|я|ь)?",
            f"отсрочка платежа {RU_PHRASE}",
        ),
        (
            r"отсрочк(?:ой|ою|а|и|у|е)?\s+платежа[^.<]{0,100}?\s+до\s+\d+(?:[\s\-–—]\d+)?"
            r"(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?",
            f"отсрочка платежа {RU_PHRASE}",
        ),
        (
            r"систем[аы]\s+отсрочки\s+платежа\s+до\s+\d+(?:[\s\-–—]\d+)?"
            r"(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?",
            f"система отсрочки платежа {RU_PHRASE}",
        ),
        (
            r"отсрочк(?:ой|ою|а|и|у|е)?\s+до\s+\d+(?:[\s\-–—]\d+)?"
            r"(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?",
            f"отсрочка {RU_PHRASE}",
        ),
        (
            r"да[ёe]м\s+отсрочк(?:у|ой)\s+\d+(?:[\s\-–—]\d+)?"
            r"(?:\s+календарных)?(?:\s+дн(?:ей|я|ь))?",
            f"даём отсрочку {RU_PHRASE}",
        ),
        (
            r"Отсрочк(?:а|и|у|ой|ою)\s+\d+(?:[\s\-–—]\d+)?\s*дн(?:ей|я|ь)?"
            r"(?:\s*\([^)]*\))?",
            f"Отсрочка {RU_PHRASE}",
        ),
        (r"net\s*\d+[\s\-–—]+\d+\s*дн(?:ей|я|ь)?", RU_PHRASE),
        (r"net-\d+", RU_PHRASE),
        (
            r'<div class="num">\d+(?:[\s\-–—]\d+)?\s*дн(?:ей|я|ь)?</div>'
            r'<div class="lbl">отсрочка после пилота</div>',
            f'<div class="num">{RU_PHRASE.capitalize()}</div>'
            f'<div class="lbl">отсрочка платежа</div>',
        ),
        # EN
        (r"Net\s*\d+[\s\-–—]+\d+\s*days(?:\s+after\s+pilot)?", EN_PHRASE),
        (r"Net\s*\d+\s*days(?:\s+after\s+pilot)?", EN_PHRASE),
        (r"net-\d+(?:\s+payment\s+terms)?", EN_PHRASE),
        (r"\d+[\s\-–—]+\d+\s*days\s+deferred\s+payment", f"deferred payment {EN_PHRASE}"),
        (r"30-day\s+deferred\s+payment", f"deferred payment {EN_PHRASE}"),
        (
            r"deferred\s+payment\s+of\s+up\s+to\s+\d+[\s\-–—]+\d+\s*days",
            f"deferred payment {EN_PHRASE}",
        ),
        (
            r"deferred\s+payment\s+of\s+\d+[\s\-–—]+\d+\s*days",
            f"deferred payment {EN_PHRASE}",
        ),
        (r"deferred\s+payment\s+of\s+\d+\s*days", f"deferred payment {EN_PHRASE}"),
        (r"net\s*\d+[\s\-–—]+\d+\s*days", EN_PHRASE),
        (r"with\s+net-\d+\s+payment\s+terms", f"with payment terms {EN_PHRASE}"),
        (r"include\s+net-\d+\s+payment\s+terms", f"include payment terms {EN_PHRASE}"),
        (r"Payment terms include net-\d+", f"Payment terms {EN_PHRASE}"),
        (r"Do you work on net-\d+ terms\?", f"Do you offer deferred payment terms {EN_PHRASE}?"),
        (r"work on net-\d+ terms\?", f"offer deferred payment {EN_PHRASE}?"),
        (
            r"Отсрочка\s+\d+(?:[\s\-–—]\d+)?\s*дн(?:ей|я|ь)?(?:\s+после\s+пилота)?",
            f"Отсрочка {RU_PHRASE}",
        ),
        (r"отсрочк(?:ой|ою|е|у|а|и)?\s+до\s+\d+(?:[\s\-–—]\d+)?(?:\s+дн(?:ей|я|ь))?", f"отсрочка {RU_PHRASE}"),
        (r"отсрочке\s+до\s+\d+(?:[\s\-–—]\d+)?(?:\s+дн(?:ей|я|ь))?", f"отсрочке {RU_PHRASE}"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?-day invoicing", f"payment terms {EN_PHRASE}"),
        (
            r"net\s*\d+(?:[\s\-–—]\d+)? or net\s*\d+(?:[\s\-–—]\d+)? arrangements",
            f"payment terms {EN_PHRASE} arrangements",
        ),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.I)

    text = _sub_paren_days_after_deferral(text)
    text = _sub_range_days_after_deferral(text)

    grammar: list[tuple[str, str]] = [
        (r"система отсрочка платежа", "система отсрочки платежа"),
        (r"возможность отсрочка платежа", "возможность отсрочки платежа"),
        (r"предусмотрен отсрочка платежа", "предусмотрена отсрочка платежа"),
        (r"условия отсрочка платежа", "условия отсрочки платежа"),
        (r"индивидуальные условия отсрочка платежа", "индивидуальные условия отсрочки платежа"),
        (
            rf"отсрочка платежа {re.escape(RU_PHRASE)} (?:календарного дня|рабочих дней)",
            f"отсрочка платежа {RU_PHRASE}",
        ),
        (
            rf"отсрочка {re.escape(RU_PHRASE)} банковских дней",
            f"отсрочка {RU_PHRASE}",
        ),
        (r"  +\(согласно договору\)", f" ({RU_PHRASE})"),
    ]
    for pattern, repl in grammar:
        text = re.sub(pattern, repl, text, flags=re.I)

    en_net: list[tuple[str, str]] = [
        (r"Payment terms are net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)?", f"Payment terms are {EN_PHRASE}"),
        (r"Net payment terms are net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)?", f"Payment terms are {EN_PHRASE}"),
        (r"flexible payment terms, including net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)?", f"flexible payment terms {EN_PHRASE}"),
        (r"with net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? available", f"with payment terms {EN_PHRASE}"),
        (r"with net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for", f"with payment terms {EN_PHRASE} for"),
        (r"terms are net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for", f"terms are {EN_PHRASE} for"),
        (r"require .*?net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for", f"require payment terms {EN_PHRASE} for"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for approved", f"{EN_PHRASE} for approved"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for established", f"{EN_PHRASE} for established"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for recurring", f"{EN_PHRASE} for recurring"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for first-time", f"{EN_PHRASE} for first-time"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for new", f"{EN_PHRASE} for new"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for repeat", f"{EN_PHRASE} for repeat"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for private-label", f"{EN_PHRASE} for private-label"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for qualified", f"{EN_PHRASE} for qualified"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for HoReCa", f"{EN_PHRASE} for HoReCa"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for export", f"{EN_PHRASE} for export"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for international", f"{EN_PHRASE} for international"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for containerized", f"{EN_PHRASE} for containerized"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for container", f"{EN_PHRASE} for container"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for credit", f"{EN_PHRASE} for credit"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for accounts", f"{EN_PHRASE} for accounts"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for buyers", f"{EN_PHRASE} for buyers"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for partners", f"{EN_PHRASE} for partners"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for clients", f"{EN_PHRASE} for clients"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for orders", f"{EN_PHRASE} for orders"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for invoices", f"{EN_PHRASE} for invoices"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for contract", f"{EN_PHRASE} for contract"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for long-term", f"{EN_PHRASE} for long-term"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for annual", f"{EN_PHRASE} for annual"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for recurring", f"{EN_PHRASE} for recurring"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for repeat", f"{EN_PHRASE} for repeat"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for select", f"{EN_PHRASE} for select"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for EU", f"{EN_PHRASE} for EU"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for CIS", f"{EN_PHRASE} for CIS"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for MENA", f"{EN_PHRASE} for MENA"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for Gulf", f"{EN_PHRASE} for Gulf"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for Middle East", f"{EN_PHRASE} for Middle East"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for SE Asia", f"{EN_PHRASE} for SE Asia"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for Russia", f"{EN_PHRASE} for Russia"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for regional", f"{EN_PHRASE} for regional"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for high-volume", f"{EN_PHRASE} for high-volume"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for verified", f"{EN_PHRASE} for verified"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? for approved credit", f"{EN_PHRASE} for approved credit"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? after", f"{EN_PHRASE} after"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? thereafter", f"{EN_PHRASE} thereafter"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? payment terms", f"payment terms {EN_PHRASE}"),
        (r"net\s*\d+(?:[\s\-–—]\d+)?(?:\s*day)? terms", f"payment terms {EN_PHRASE}"),
        (r"offer net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)?", f"offer payment terms {EN_PHRASE}"),
        (r"Established suppliers offer net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? terms", f"Established suppliers offer payment terms {EN_PHRASE}"),
    ]
    for pattern, repl in en_net:
        text = re.sub(pattern, repl, text, flags=re.I)

    # Early-payment lines: only strip trailing net-N when it's the deferral term
    text = re.sub(
        r"with early payment discounts of \d+% for net \d+",
        lambda m: m.group(0).split(" for net")[0],
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(\d+% prepayment for new accounts, )net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? (for established)",
        rf"\1payment terms {EN_PHRASE} \2",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(50% advance for new accounts, with )net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? (available)",
        rf"\1payment terms {EN_PHRASE} \2",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(Payment terms include )net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? (for)",
        rf"\1payment terms {EN_PHRASE} \2",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"We offer flexible terms: net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)? (for)",
        rf"We offer flexible terms: payment terms {EN_PHRASE} \1",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"flexible payment terms \(net\s*\d+(?:[\s\-–—]\d+)?(?:\s*days?)?",
        f"flexible payment terms ({EN_PHRASE}",
        text,
        flags=re.I,
    )

    # Cleanup doubled phrases
    text = re.sub(rf"{re.escape(RU_PHRASE)}\s*\({re.escape(RU_PHRASE)}\)", RU_PHRASE, text)
    text = re.sub(rf"{re.escape(EN_PHRASE)}\s*\({re.escape(EN_PHRASE)}\)", EN_PHRASE, text, flags=re.I)

    en_ru_leaks: list[tuple[str, str]] = [
        (r"with согласно договору payment terms", f"with payment terms {EN_PHRASE}"),
        (r"согласно договору payment terms", f"payment terms {EN_PHRASE}"),
        (r"and согласно договору for", f"and payment terms {EN_PHRASE} for"),
        (r"согласно договору for established", f"{EN_PHRASE} for established"),
        (r"on согласно договору terms", f"on deferred payment terms {EN_PHRASE}"),
        (r"for согласно договору terms", f"for payment terms {EN_PHRASE}"),
        (r"qualify for согласно договору terms", f"qualify for payment terms {EN_PHRASE}"),
        (r"include согласно договору", f"include payment terms {EN_PHRASE}"),
        (r"Do you work on согласно договору terms\?", f"Do you offer deferred payment {EN_PHRASE}?"),
    ]
    for pattern, repl in en_ru_leaks:
        text = re.sub(pattern, repl, text, flags=re.I)

    return text


def fix_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = _apply(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    roots = [PUBLIC, ROOT / "data" / "product_overrides"]
    changed = 0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.html")):
            if fix_file(path):
                changed += 1
                print(path.relative_to(ROOT))
    print(f"\nUpdated {changed} files.")


if __name__ == "__main__":
    main()
