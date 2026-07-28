#!/usr/bin/env python3
"""Build responsive avif/webp/jpg variants for category-landing photos.

Usage:
  python3 scripts/optimize_category_landing_images.py sosiski

Reads image paths from data/category_landing/{slug}.json (hero, saga, bands, trust)
and writes siblings next to each source:
  name-480.jpg / .webp / .avif
  name-768.*
  name-1200.*
  name-1600.*

Requires Pillow. AVIF optional (pillow-heif); falls back to webp+jpg only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
CONFIG_DIR = ROOT / "data" / "category_landing"
WIDTHS = (480, 768, 1200, 1600)


def collect_paths(cfg: dict) -> list[str]:
    paths: list[str] = []
    hero = cfg.get("hero") or {}
    if hero.get("image"):
        paths.append(hero["image"])
    if (cfg.get("meta") or {}).get("og_image"):
        paths.append(cfg["meta"]["og_image"])
    for ch in (cfg.get("saga") or {}).get("chapters") or []:
        if ch.get("image"):
            paths.append(ch["image"])
    for b in cfg.get("band_images") or []:
        if b.get("src"):
            paths.append(b["src"])
    trust = cfg.get("trust") or {}
    if trust.get("photo"):
        paths.append(trust["photo"])
    # unique preserve order
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def optimize_one(rel: str) -> None:
    from PIL import Image

    src = PUBLIC / rel.lstrip("/")
    if not src.is_file():
        raise FileNotFoundError(src)
    img = Image.open(src).convert("RGB")
    stem = src.stem
    parent = src.parent
    for w in WIDTHS:
        im = img.copy()
        if im.width > w:
            ratio = w / im.width
            im = im.resize((w, max(1, int(im.height * ratio))), Image.Resampling.LANCZOS)
        base = parent / f"{stem}-{w}"
        im.save(base.with_suffix(".jpg"), "JPEG", quality=78, optimize=True, progressive=True)
        im.save(base.with_suffix(".webp"), "WEBP", quality=76, method=4)
        try:
            im.save(base.with_suffix(".avif"), "AVIF", quality=55)
        except Exception:
            pass
        print(f"  {base.name}.*")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    args = ap.parse_args()
    cfg_path = CONFIG_DIR / f"{args.slug}.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    paths = collect_paths(cfg)
    print(f"Optimizing {len(paths)} sources for {args.slug}")
    for p in paths:
        print(p)
        optimize_one(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
