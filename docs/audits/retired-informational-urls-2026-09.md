# Retired informational URLs — 2026-09-26

Decision for this sprint: keep HTTP 410. No 301, no restore, no FAQ added to `/vetchina-optom`.

Numbers below are `impressions_28d` / `clicks_28d` stored in `data/url_consolidation_map.json` (`gsc_latest_date`: 2026-08-23). They are not a fresh 90-day Search Console window.

| URL | Status | Stored 28d evidence | Successor checked | Decision |
|---|---|---|---|---|
| `/blog/vetchina-fileynaya-halyal` | 410 | 193 impressions, 0 clicks | `/vetchina-optom` is the wholesale ham catalog («Ветчина халяль — оптовый каталог»). It does not answer «ветчина это халяль» or the fillet-ham article. | Keep 410 |
| `/blog/vetchina-eto-halal` | 410 | 0 impressions, 0 clicks | Same commercial catalog. Not an equivalent informational page. | Keep 410 |
| `/blog/kuritsa-halyal-chem-otlichaetsya` | 410 | 227 impressions, 1 click | No landing that answers how halal chicken differs. Homepage is not a successor. | Keep 410 |

Checks on this branch:

- None of the three URLs appear in `public/sitemap.xml`.
- No current HTML under `public/` links to them.
- Removed from the active `rewrite_pages` queue in `data/strategy.json`.
- `data/ab_tests.json` already marks the ham experiment `interrupted_by_strategy_reset`. `data/experiments.json` keeps historical rows. Those ledgers were not rewritten.
