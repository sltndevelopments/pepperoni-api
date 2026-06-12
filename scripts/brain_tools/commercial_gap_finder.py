"""
commercial_gap_finder: Находит коммерческие запросы (купить/оптом/цена/поставщик/halal+wholesale)
с позицией 5-25, у которых нет выделенной целевой страницы.
Читает GSC-данные, сопоставляет ранжируемую страницу с релевантностью запроса,
выявляет упущенные возможности для монетизации.
"""

import json
from pathlib import Path
from collections import defaultdict
import re

ROOT = Path(__file__).parents[2]


def load_gsc_data():
    """Загружает данные из GSC (data/gsc_queries.json)"""
    gsc_file = ROOT / "data" / "gsc_queries.json"
    if not gsc_file.exists():
        return []
    try:
        with open(gsc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def load_pages():
    """Загружает список страниц из public/"""
    pages = {}
    public_dir = ROOT / "public"
    if not public_dir.exists():
        return pages
    
    for html_file in public_dir.rglob("*.html"):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read().lower()
                rel_path = html_file.relative_to(public_dir)
                pages[str(rel_path)] = content
        except (IOError, UnicodeDecodeError):
            pass
    
    return pages


def is_commercial_query(query):
    """Проверяет, содержит ли запрос коммерческие маркеры"""
    query_lower = query.lower()
    commercial_markers = [
        r"\bкупить\b",
        r"\bцена\b",
        r"\bоптом\b",
        r"\bоптовая\b",
        r"\bпоставщик\b",
        r"\bпоставка\b",
        r"\bwholesale\b",
        r"\bhalal.*wholesale\b",
        r"\bwholesale.*halal\b",
        r"\bкупить.*оптом\b",
        r"\bоптом.*цена\b",
        r"\bпоставщик.*халяль\b",
        r"\bхалял.*поставщик\b",
    ]
    
    for marker in commercial_markers:
        if re.search(marker, query_lower):
            return True
    return False


def extract_keywords_from_query(query):
    """Извлекает ключевые слова из запроса для сопоставления со страницей"""
    words = re.findall(r"\b[а-яa-z]+\b", query.lower())
    return set(words)


def page_matches_query(page_content, query_keywords):
    """Проверяет, содержит ли страница ключевые слова запроса"""
    if not query_keywords:
        return False
    
    matched = 0
    for keyword in query_keywords:
        if keyword in page_content:
            matched += 1
    
    return matched >= max(1, len(query_keywords) // 2)


def main() -> None:
    gsc_data = load_gsc_data()
    pages = load_pages()
    
    if not gsc_data:
        print(json.dumps({"error": "No GSC data found", "gaps": []}))
        return
    
    gaps = []
    
    for item in gsc_data:
        query = item.get("query", "")
        position = item.get("position", 0)
        impressions = item.get("impressions", 0)
        page = item.get("page", "")
        
        if not query or position < 5 or position > 25:
            continue
        
        if not is_commercial_query(query):
            continue
        
        query_keywords = extract_keywords_from_query(query)
        
        is_home_or_irrelevant = (
            page == "/" or 
            page == "index.html" or 
            not page or
            not page_matches_query(pages.get(page, ""), query_keywords)
        )
        
        if is_home_or_irrelevant:
            gaps.append({
                "query": query,
                "impressions": impressions,
                "position": position,
                "current_page": page if page else "index.html",
                "status": "no_landing"
            })
    
    gaps.sort(key=lambda x: x["impressions"], reverse=True)
    top_gaps = gaps[:20]
    
    result = {
        "total_commercial_gaps": len(gaps),
        "top_20_gaps": top_gaps
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()