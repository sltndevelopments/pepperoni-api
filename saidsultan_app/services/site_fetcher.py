"""
Загрузка и парсинг сайта для анализа.
"""
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MAX_CONTENT_LEN = 3000


def _normalize_url(url: str) -> str:
    """Добавляет https:// если нет схемы."""
    s = (url or "").strip()
    if not s:
        return ""
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    return s


def _extract_text(soup: BeautifulSoup) -> str:
    """
    Извлекает только основной контент страницы.
    Удаляет nav, header, footer, script, style, aside и элементы с role navigation/banner.
    Предпочитает <main>, иначе body.
    """
    # Удаляем служебные теги
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    # Удаляем по ARIA-ролям (навигация, баннер)
    for tag in soup.find_all(attrs={"role": re.compile(r"navigation|banner", re.I)}):
        tag.decompose()
    # Удаляем по типичным id (header, footer, nav, menu)
    for tag in soup.find_all(id=re.compile(r"(header|footer|navbar|sidebar|^nav$|^menu$)", re.I)):
        tag.decompose()
    # Предпочитаем main, иначе body
    main = soup.find("main")
    root = main if main else (soup.find("body") or soup)
    text = root.get_text(separator=" ", strip=True) if root else ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_brand(soup: BeautifulSoup, url: str) -> str:
    """
    Извлекает название бренда из <title> или первого <h1>.
    URL — только запасной вариант.
    """
    # Из title: берём часть до | или — (часто "Название | Сайт" или "Название — Описание")
    if soup.title:
        title = soup.title.get_text(strip=True)
        if title:
            for sep in [" | ", " — ", " - ", " |", " —", " -"]:
                if sep in title:
                    brand = title.split(sep)[0].strip()
                    if brand and len(brand) > 1:
                        return brand
            return title[:80].strip()
    # Из первого h1
    h1 = soup.find("h1")
    if h1:
        brand = h1.get_text(strip=True)
        if brand and len(brand) > 1:
            return brand[:80]
    # Запасной вариант — из URL (домен)
    if url:
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        netloc = (parsed.netloc or "").replace("www.", "")
        return netloc.split(".")[0] or "компания"
    return "компания"


async def fetch_site(url: str) -> dict:
    """
    GET запрос на сайт, извлечение текста через BeautifulSoup.
    Возвращает: {title, description, content (первые 3000 символов)}
    """
    normalized = _normalize_url(url)
    if not normalized:
        return {"title": "", "description": "", "content": "", "brand": "", "error": "Пустой URL"}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            r = await client.get(normalized)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        return {"title": "", "description": "", "content": "", "brand": "", "error": str(e)}

    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    description = ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta and meta.get("content"):
        description = meta["content"].strip()

    # Бренд извлекаем до _extract_text, чтобы h1 не удалился (если внутри header)
    brand = _extract_brand(soup, normalized)
    content = _extract_text(soup)[:MAX_CONTENT_LEN]
    return {"title": title, "description": description, "content": content, "brand": brand}
