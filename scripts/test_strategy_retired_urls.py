#!/usr/bin/env python3
"""Regression: retired consolidation URLs never stay in rewrite_pages."""
from __future__ import annotations

import unittest

from check_strategy_retired_urls import drop_retired_rewrite_pages, retired_status_by_url

CONSOLIDATION = {
    "entries": [
        {"url": "/blog/vetchina-fileynaya-halyal", "status": "410"},
        {"url": "/old-landing", "status": "301"},
        {"url": "/hidden", "status": "noindex"},
        {"url": "/pepperoni", "status": "keep"},
    ]
}


class DropRetiredRewritePagesTest(unittest.TestCase):
    def test_drops_410_301_noindex_and_keeps_indexable(self) -> None:
        retired = retired_status_by_url(CONSOLIDATION)
        pages = [
            {"path": "/blog/vetchina-fileynaya-halyal", "reason": "переписать"},
            {"path": "https://pepperoni.tatar/old-landing", "reason": "redirect"},
            {"path": "/hidden/", "reason": "noindex"},
            {"path": "/pepperoni", "reason": "живой лендинг"},
        ]
        kept, dropped = drop_retired_rewrite_pages(pages, retired)
        self.assertEqual([item["path"] for item in kept], ["/pepperoni"])
        self.assertEqual(
            dropped,
            [
                ("/blog/vetchina-fileynaya-halyal", "410"),
                ("https://pepperoni.tatar/old-landing", "301"),
                ("/hidden/", "noindex"),
            ],
        )
        print("410 target → dropped")
        print("301 target → dropped")
        print("noindex target → dropped")
        print("indexable target → preserved")


if __name__ == "__main__":
    unittest.main()
