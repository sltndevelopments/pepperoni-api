"""
cannibalization_finder: Detect keyword cannibalization in GSC data.

Finds commercial queries where multiple site pages compete for rankings.
Analyzes GSC performance data to identify queries with ≥2 pages showing
(impressions >5), marking them as cannibalization issues.

Output: JSON report with cannibalized queries, affected URLs, and positions.
"""

import json
from pathlib import Path
from collections import defaultdict


def main() -> None:
    root = Path(__file__).parents[2]
    data_dir = root / "data"
    
    # Load GSC data if available
    gsc_file = data_dir / "gsc_data.json"
    if not gsc_file.exists():
        print(json.dumps({"error": "gsc_data.json not found", "cannibalization": []}))
        return
    
    try:
        with open(gsc_file, "r", encoding="utf-8") as f:
            gsc_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        print(json.dumps({"error": "Failed to read gsc_data.json", "cannibalization": []}))
        return
    
    # Load commercial keywords list if available
    keywords_file = data_dir / "commercial_keywords.json"
    commercial_keywords = set()
    if keywords_file.exists():
        try:
            with open(keywords_file, "r", encoding="utf-8") as f:
                kw_data = json.load(f)
                if isinstance(kw_data, list):
                    commercial_keywords = set(kw_data)
                elif isinstance(kw_data, dict) and "keywords" in kw_data:
                    commercial_keywords = set(kw_data["keywords"])
        except (json.JSONDecodeError, IOError):
            pass
    
    # Parse GSC data: group by query, collect URLs with impressions
    query_pages = defaultdict(list)
    
    if isinstance(gsc_data, list):
        for record in gsc_data:
            if not isinstance(record, dict):
                continue
            query = record.get("query", "").strip().lower()
            url = record.get("page", "").strip()
            impressions = record.get("impressions", 0)
            position = record.get("position", 0)
            
            if not query or not url or impressions <= 5:
                continue
            
            # Filter by commercial keywords if list exists
            if commercial_keywords and query not in commercial_keywords:
                continue
            
            query_pages[query].append({
                "url": url,
                "impressions": impressions,
                "position": position
            })
    elif isinstance(gsc_data, dict):
        for query, records in gsc_data.items():
            query_lower = query.strip().lower()
            if commercial_keywords and query_lower not in commercial_keywords:
                continue
            
            if isinstance(records, list):
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    url = record.get("page", "").strip()
                    impressions = record.get("impressions", 0)
                    position = record.get("position", 0)
                    
                    if url and impressions > 5:
                        query_pages[query_lower].append({
                            "url": url,
                            "impressions": impressions,
                            "position": position
                        })
    
    # Identify cannibalization: queries with ≥2 pages
    cannibalization = []
    for query, pages in sorted(query_pages.items()):
        if len(pages) >= 2:
            # Sort by position (lower is better)
            pages_sorted = sorted(pages, key=lambda x: x.get("position", 999))
            cannibalization.append({
                "query": query,
                "page_count": len(pages),
                "pages": pages_sorted
            })
    
    # Sort by page count (descending) then by query
    cannibalization.sort(key=lambda x: (-x["page_count"], x["query"]))
    
    result = {
        "total_cannibalized_queries": len(cannibalization),
        "cannibalization": cannibalization[:50]  # Top 50 for digest
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()