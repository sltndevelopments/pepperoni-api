#!/usr/bin/env python3
"""Read-only report of verified Googlebot hits in nginx combined logs.

A hit counts only when the User-Agent contains "Googlebot" and the client IP
is inside the snapshotted Google ranges in data/googlebot_ip_ranges.json.
The snapshot is the official list from
https://developers.google.com/static/search/apis/ipranges/googlebot.json
(field creationTime). Nothing is fetched at runtime.

nginx on this host logs the combined format and does not record $host, so
pepperoni.tatar, api.pepperoni.tatar and the bare IP are not separated.
"""
from __future__ import annotations

import argparse
import gzip
import ipaddress
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RANGES = ROOT / "data" / "googlebot_ip_ranges.json"
DEFAULT_PUBLIC = ROOT / "public"
STATUS_KEYS = ("200", "301", "404", "410", "5xx", "other")

LINE_RE = re.compile(
    r'^(\S+) \S+ \S+ \[(\d{2}/\w{3}/\d{4}):[^\]]*\] '
    r'"(\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "(.*)"\s*$'
)
ATTR_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
TEXT_SUFFIXES = {
    ".html", ".txt", ".xml", ".json", ".js", ".css", ".svg", ".md", ".yml", ".yaml",
}
SITE_HOSTS = {"pepperoni.tatar", "www.pepperoni.tatar", "api.pepperoni.tatar"}
MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def load_networks(path: Path) -> tuple[str, list[ipaddress._BaseNetwork]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    networks = []
    for item in payload.get("prefixes", []):
        cidr = item.get("ipv4Prefix") or item.get("ipv6Prefix")
        if cidr:
            networks.append(ipaddress.ip_network(cidr, strict=False))
    return str(payload.get("creationTime") or ""), networks


def ip_in_ranges(ip: str, networks: list[ipaddress._BaseNetwork]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def status_bucket(code: int) -> str:
    if code in (200, 301, 404, 410):
        return str(code)
    if 500 <= code <= 599:
        return "5xx"
    return "other"


def iso_day(raw: str) -> str:
    day, mon, year = raw.split("/")
    return f"{year}-{MONTHS[mon]:02d}-{int(day):02d}"


def request_path(raw: str) -> str:
    path = raw.split("?", 1)[0]
    path = urllib.parse.unquote(path)
    if not path.startswith("/"):
        path = "/" + path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def first_segment(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    return "/" + parts[0] if parts else "/"


def iter_log_lines(log_dir: Path):
    files = []
    current = log_dir / "access.log"
    previous = log_dir / "access.log.1"
    if current.is_file():
        files.append(current)
    if previous.is_file():
        files.append(previous)
    files.extend(sorted(path for path in log_dir.glob("access.log.*.gz") if path.is_file()))
    for path in files:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                yield line.rstrip("\n")


def normalize_ref(raw: str) -> str | None:
    raw = raw.strip()
    if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    if raw.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(raw)
        host = (parsed.hostname or "").lower()
        if host not in SITE_HOSTS:
            return None
        path = parsed.path or "/"
    else:
        path = raw
    return request_path(path)


def public_link_targets(public_dir: Path) -> set[str]:
    targets: set[str] = set()
    if not public_dir.is_dir():
        return targets
    for path in public_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in ATTR_RE.finditer(text):
            target = normalize_ref(match.group(1))
            if target:
                targets.add(target)
    return targets


def build_report(log_dir: Path, public_dir: Path, ranges_path: Path) -> dict:
    created, networks = load_networks(ranges_path)
    by_day: dict[str, Counter] = defaultdict(Counter)
    gone = Counter()
    missing = Counter()
    verified = 0
    excluded_ua = 0
    for line in iter_log_lines(log_dir):
        match = LINE_RE.match(line)
        if not match:
            continue
        ip, day, _method, raw_path, status_raw, ua = match.groups()
        if "googlebot" not in ua.lower():
            continue
        if not ip_in_ranges(ip, networks):
            excluded_ua += 1
            continue
        verified += 1
        bucket = status_bucket(int(status_raw))
        by_day[iso_day(day)][bucket] += 1
        path = request_path(raw_path)
        if bucket == "410":
            gone[first_segment(path)] += 1
        elif bucket == "404":
            missing[path] += 1
    linked = public_link_targets(public_dir)
    totals = Counter()
    days = {}
    for day in sorted(by_day):
        row = {key: by_day[day].get(key, 0) for key in STATUS_KEYS}
        days[day] = row
        totals.update(row)
    not_found = []
    for path, count in sorted(missing.items(), key=lambda item: (-item[1], item[0])):
        has_link = path in linked
        not_found.append({
            "path": path,
            "count": count,
            "linked_from_public": has_link,
            "mark": "есть ссылка в public/" if has_link else "ссылок нет",
        })
    return {
        "note": "nginx combined log has no $host; hosts are not separated",
        "ranges_file": str(ranges_path),
        "ranges_creation_time": created,
        "verified_requests": verified,
        "excluded_googlebot_ua_outside_ranges": excluded_ua,
        "days": days,
        "status_totals": {key: totals.get(key, 0) for key in STATUS_KEYS},
        "gone_by_segment": dict(sorted(gone.items(), key=lambda item: (-item[1], item[0]))),
        "not_found": not_found,
    }


def render_text(report: dict) -> str:
    lines = [
        "Verified Googlebot crawl report",
        report["note"],
        f"Ranges: {report['ranges_file']} (creationTime {report['ranges_creation_time']})",
        f"Verified requests: {report['verified_requests']}",
        (
            "Excluded (Googlebot UA, IP outside ranges): "
            f"{report['excluded_googlebot_ua_outside_ranges']}"
        ),
        "",
        "By day",
        "date        200   301   404   410   5xx  other",
    ]
    for day, row in report["days"].items():
        lines.append(
            f"{day}  {row['200']:4d}  {row['301']:4d}  {row['404']:4d}  "
            f"{row['410']:4d}  {row['5xx']:4d}  {row['other']:4d}"
        )
    totals = report["status_totals"]
    lines.append(
        f"{'total':<10}  {totals['200']:4d}  {totals['301']:4d}  {totals['404']:4d}  "
        f"{totals['410']:4d}  {totals['5xx']:4d}  {totals['other']:4d}"
    )
    lines.extend(["", "410 by first path segment"])
    if report["gone_by_segment"]:
        for segment, count in report["gone_by_segment"].items():
            lines.append(f"{count:6d}  {segment}")
    else:
        lines.append("(none)")
    lines.extend(["", "404 paths"])
    if report["not_found"]:
        for item in report["not_found"]:
            lines.append(f"{item['count']:6d}  {item['mark']}  {item['path']}")
    else:
        lines.append("(none)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=Path("/var/log/nginx"))
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--ranges", type=Path, default=DEFAULT_RANGES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.log_dir.is_dir():
        print(f"log dir not found: {args.log_dir}", file=sys.stderr)
        return 1
    if not args.ranges.is_file():
        print(f"ranges file not found: {args.ranges}", file=sys.stderr)
        return 1
    report = build_report(args.log_dir, args.public, args.ranges)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
