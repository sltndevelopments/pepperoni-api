"""
cannibalization_detector: Выявляет каннибализацию ключевых слов в GSC.

Читает отчёт GSC (query×page за 28 дней) из data/gsc_report.json,
группирует по запросу, находит случаи, когда ≥2 разных URL имеют
impressions>10 по одному запросу (признак внутренней конкуренции).
Выводит топ-20 проблемных запросов по суммарным показам.
Результат сохраняет в data/cannibalization_detector.json.
"""

import json
from pathlib import Path
from collections import defaultdict


def main() -> None:
    root = Path(__file__).parents[2]
    gsc_file = root / "data" / "gsc_report.json"
    
    if not gsc_file.exists():
        print(json.dumps({"error": "gsc_report.json not found", "cannibals": []}))
        return
    
    try:
        with open(gsc_file, "r", encoding="utf-8") as f:
            gsc_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(json.dumps({"error": f"Failed to read GSC: {e}", "cannibals": []}))
        return
    
    # Ожидаем структуру: {"rows": [{"query": "...", "page": "...", "impressions": N}, ...]}
    rows = gsc_data.get("rows", [])
    if not rows:
        print(json.dumps({"error": "No rows in gsc_report", "cannibals": []}))
        return
    
    # Группируем по query: query -> {page -> impressions}
    query_pages = defaultdict(lambda: defaultdict(int))
    query_total_impressions = defaultdict(int)
    
    for row in rows:
        query = row.get("query", "").strip()
        page = row.get("page", "").strip()
        impressions = row.get("impressions", 0)
        
        if not query or not page or impressions <= 0:
            continue
        
        query_pages[query][page] += impressions
        query_total_impressions[query] += impressions
    
    # Находим каннибализацию: query с ≥2 URL, у которых impressions>10
    cannibals = []
    
    for query, pages_dict in query_pages.items():
        # Считаем URL с impressions > 10
        competing_urls = [
            (page, impr)
            for page, impr in pages_dict.items()
            if impr > 10
        ]
        
        if len(competing_urls) >= 2:
            cannibals.append({
                "query": query,
                "total_impressions": query_total_impressions[query],
                "competing_urls_count": len(competing_urls),
                "urls": sorted(competing_urls, key=lambda x: x[1], reverse=True)
            })
    
    # Сортируем по суммарным показам, берём топ-20
    cannibals.sort(key=lambda x: x["total_impressions"], reverse=True)
    cannibals = cannibals[:20]
    
    # Выводим в stdout (компактный JSON)
    result = {
        "total_cannibals_found": len(cannibals),
        "top_20": cannibals
    }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    
    # Сохраняем в data/
    output_file = root / "data" / "cannibalization_detector.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except IOError:
        pass


if __name__ == "__main__":
    main()