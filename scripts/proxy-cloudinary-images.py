#!/usr/bin/env python3
"""
Replace direct Cloudinary image URLs in product pages with proxy URLs
through /api/health?u=<url>. Keeps og:image and twitter:image as original
(search engines crawl from non-Russian IPs).
"""
import os, re, sys
from urllib.parse import quote

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'public')
PRODUCTS_DIR = os.path.join(PUBLIC_DIR, 'products')

CLOUDINARY_RE = re.compile(
    r'(src|href|content)\s*=\s*"https://res\.cloudinary\.com'
    r'(/[^"]*?)"'
)

def should_proxy(tag_attr, full_url):
    """Keep og:image and twitter:image as direct Cloudinary URLs."""
    if 'og:image' in full_url or 'twitter:image' in full_url:
        return False
    if 'schema.org' in full_url:
        return False
    if tag_attr == 'content' and ('og:image' in full_url or 'twitter:image' in full_url):
        return False
    return True

def replace_url(match):
    tag_attr = match.group(1)  # src, href, or content
    cloudinary_path = match.group(2)
    full_url = f"https://res.cloudinary.com{cloudinary_path}"
    
    if not should_proxy(tag_attr, full_url):
        return match.group(0)
    
    proxy_url = f"/api/health?u={quote(full_url, safe='')}"
    return f'{tag_attr}="{proxy_url}"'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    modified = CLOUDINARY_RE.sub(replace_url, content)
    
    if modified != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(modified)
        return True
    return False

def main():
    if not os.path.isdir(PRODUCTS_DIR):
        print(f"Products dir not found: {PRODUCTS_DIR}")
        sys.exit(1)
    
    changed = 0
    for fname in sorted(os.listdir(PRODUCTS_DIR)):
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(PRODUCTS_DIR, fname)
        if process_file(fpath):
            changed += 1
            print(f"  ✓ {fname}")
    
    print(f"\nUpdated {changed} product page(s).")

if __name__ == '__main__':
    main()
