#!/usr/bin/env python3
"""
Patch existing blog articles:
  1. Fix canonical: api.pepperoni.tatar → pepperoni.tatar
  2. Add OG + Twitter card meta tags (for Telegram/WhatsApp previews)
  3. Fix schema URLs: api.pepperoni.tatar → pepperoni.tatar

Run: python scripts/patch_blog_meta.py
"""

import re
from pathlib import Path

PUBLIC = Path(__file__).parent.parent / "public"

OG_TEMPLATE_RU = """\
<meta property="og:type" content="article">
<meta property="og:site_name" content="Казанские Деликатесы">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://res.cloudinary.com/duygfl3vz/image/upload/f_auto,q_auto,w_1200,h_630,c_fill/v1/og-blog-default.jpg">
<meta property="og:locale" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="https://res.cloudinary.com/duygfl3vz/image/upload/f_auto,q_auto,w_1200,h_630,c_fill/v1/og-blog-default.jpg">
"""

OG_TEMPLATE_EN = """\
<meta property="og:type" content="article">
<meta property="og:site_name" content="Kazan Delicacies">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://res.cloudinary.com/duygfl3vz/image/upload/f_auto,q_auto,w_1200,h_630,c_fill/v1/og-blog-default.jpg">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="https://res.cloudinary.com/duygfl3vz/image/upload/f_auto,q_auto,w_1200,h_630,c_fill/v1/og-blog-default.jpg">
"""


def extract_meta(html: str, tag: str) -> str:
    m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extract_meta_attr(html: str, name: str) -> str:
    m = re.search(rf'<meta\s+name="description"\s+content="([^"]+)"', html)
    if m:
        return m.group(1)
    return ""


def patch_file(path: Path, lang: str) -> bool:
    html = path.read_text(encoding="utf-8")
    changed = False

    # 1. Fix canonical and schema URLs
    if "api.pepperoni.tatar" in html:
        html = html.replace("https://api.pepperoni.tatar/", "https://pepperoni.tatar/")
        html = html.replace("https://api.pepperoni.tatar", "https://pepperoni.tatar")
        changed = True

    # 2. Add OG tags if missing
    if 'property="og:title"' not in html:
        title = extract_meta(html, "title")
        desc  = extract_meta_attr(html, "description")
        # fallback description from article lead
        if not desc:
            m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            desc = m.group(1) if m else title

        slug = path.stem
        if lang == "ru":
            url  = f"https://pepperoni.tatar/blog/{slug}"
            og   = OG_TEMPLATE_RU.format(title=title, desc=desc[:160], url=url)
        else:
            url  = f"https://pepperoni.tatar/en/blog/{slug}"
            og   = OG_TEMPLATE_EN.format(title=title, desc=desc[:160], url=url)

        html = html.replace("</head>", og + "</head>", 1)
        changed = True

    if changed:
        path.write_text(html, encoding="utf-8")
    return changed


def main():
    fixed_canonical = 0
    added_og = 0

    for path in sorted((PUBLIC / "blog").glob("*.html")):
        if patch_file(path, "ru"):
            fixed_canonical += 1

    for path in sorted((PUBLIC / "en" / "blog").glob("*.html")):
        if patch_file(path, "en"):
            added_og += 1

    print(f"✅ Blog RU: patched {fixed_canonical} files")
    print(f"✅ Blog EN: patched {added_og} files")
    print(f"   → fixed api.pepperoni.tatar canonicals + added OG/Twitter tags")


if __name__ == "__main__":
    main()
