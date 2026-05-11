#!/usr/bin/env python3
"""Generate localised Open Graph images (1200×630 PNG).

Produces:
  public/og-default.png    — RU master (rewritten with text overlay)
  public/og-default-en.png — EN master
  public/og-pepperoni.png  — RU pepperoni landing
  public/og-pepperoni-en.png — EN pepperoni landing
  public/og-kazylyk.png    — RU kazylyk landing
  public/og-kazylyk-en.png — EN kazylyk landing
  public/og-bakery.png     — RU bakery landing
  public/og-bakery-en.png  — EN bakery landing
  public/og-pizzeria.png   — RU pizza landing
  public/og-pizzeria-en.png — EN pizza landing
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
LOGO = PUBLIC / "images" / "logo.png"

W, H = 1200, 630
BG_TOP = (27, 122, 61)       # Brand green
BG_BOTTOM = (20, 92, 46)
ACCENT = (255, 255, 255)
SUB = (220, 240, 225)
BADGE_BG = (255, 211, 77)    # Halal gold
BADGE_TXT = (40, 25, 0)


# Font helpers
def font(size, weight="bold"):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if weight == "bold" else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight == "bold" else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def gradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    px = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return base


def draw_text(img, xy, text, fnt, fill, shadow=True):
    d = ImageDraw.Draw(img)
    if shadow:
        d.text((xy[0] + 2, xy[1] + 2), text, font=fnt, fill=(0, 0, 0, 110))
    d.text(xy, text, font=fnt, fill=fill)


def draw_badge(img, x, y, text, fnt):
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), text, font=fnt)
    pad = 16
    w = bbox[2] - bbox[0] + pad * 2
    h = bbox[3] - bbox[1] + pad
    d.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=BADGE_BG)
    d.text((x + pad, y + pad // 2 - 2), text, font=fnt, fill=BADGE_TXT)
    return w


def compose(title, subtitle, badge, out_path):
    img = gradient(W, H, BG_TOP, BG_BOTTOM)

    # Subtle vignette overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for r in range(0, 280, 12):
        a = max(0, 30 - r // 12)
        x0, y0 = W - 560 + r, -180 + r
        x1, y1 = W + 200 - r, 360 - r
        if x1 > x0 and y1 > y0:
            od.ellipse([x0, y0, x1, y1], outline=(255, 255, 255, a), width=2)
    img.paste(overlay, (0, 0), overlay)

    # Logo
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        logo.thumbnail((180, 180))
        img.paste(logo, (60, 60), logo)

    # Brand text top
    f_brand = font(34)
    draw_text(img, (260, 80), "Kazan Delicacies", f_brand, ACCENT)
    f_brand_sub = font(22, "regular")
    draw_text(img, (260, 130), "Halal meat & Tatar pastry — pepperoni.tatar", f_brand_sub, SUB)

    # Main title
    f_title = font(68)
    # Wrap title
    d = ImageDraw.Draw(img)
    words = title.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textbbox((0, 0), test, font=f_title)[2] > W - 120:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    y = 280
    for line in lines[:3]:
        draw_text(img, (60, y), line, f_title, ACCENT)
        y += 80

    # Subtitle
    f_sub = font(28, "regular")
    draw_text(img, (60, y + 20), subtitle, f_sub, SUB)

    # Badge
    f_badge = font(22)
    badge_y = H - 90
    draw_badge(img, 60, badge_y, badge, f_badge)

    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"OK {out_path}  ({out_path.stat().st_size//1024} KB)")


PRESETS = [
    ("og-default.png",       "Халяль колбасы, пепперони, выпечка",      "77 SKU оптом · Казань · доставка по РФ и СНГ",  "HALAL #614A/2024"),
    ("og-default-en.png",    "Halal Sausages, Pepperoni, Pastries",      "77 SKUs wholesale · Kazan · RU + CIS export",   "HALAL #614A/2024"),
    ("og-pepperoni.png",     "Халяль пепперони для пиццерий",            "Не скручивается · термостабильный · оптом",     "Без свинины · HALAL"),
    ("og-pepperoni-en.png",  "Halal Pepperoni for Pizzerias",            "Oven-stable · no curling · wholesale",          "Pork-free · HALAL"),
    ("og-kazylyk.png",       "Казылык — конская колбаса премиум",        "Подарочные коробки · халяль · Татарстан",       "HALAL · ручная нарезка"),
    ("og-kazylyk-en.png",    "Kazylyk — Premium Horse-meat Sausage",     "Gift boxes · halal · Tatarstan tradition",      "HALAL · hand-sliced"),
    ("og-bakery.png",        "Татарская выпечка оптом",                  "Эчпочмак, самса, чак-чак, губадия · халяль",    "19 SKU · халяль"),
    ("og-bakery-en.png",     "Tatar Pastry Wholesale",                   "Echpochmak, samsa, chak-chak, gubadia · halal", "19 SKUs · halal"),
    ("og-pizzeria.png",      "Для пиццерий — халяль пепперони",          "Контракт · СТМ · единый вкус по сети",          "Кейс: Aslam / ОМПК"),
    ("og-pizzeria-en.png",   "For Pizzerias — Halal Pepperoni",          "Contract · Private Label · taste consistency",  "Case: Aslam / OMPK"),
]


def main():
    for name, title, sub, badge in PRESETS:
        compose(title, sub, badge, PUBLIC / name)


if __name__ == "__main__":
    main()
