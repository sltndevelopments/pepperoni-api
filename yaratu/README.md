# Yaratu static build

The checked-in `data/products.json` snapshot is the canonical build input when no
Google Sheets configuration is present.

## Commands

- `npm run build` — rebuild `site/dist` from the allowlist.
- `npm test` — run data, HTML, discovery and privacy checks.
- `npm run check` — build and test.
- `npm run sync` — sync the canonical snapshot, then validate it strictly.

## Google Sheets sync

Private Sheet (preferred):

- `YARATU_SHEET_FILE_ID` — Google Drive file ID. The documented default is
  `1TpXixm6QcPjHGv6yQKLVFaUTGdJ5YzxpwN7vkkUiFJU`.
- Set exactly one of `YARATU_GOOGLE_SERVICE_ACCOUNT_JSON` or
  `YARATU_GOOGLE_SERVICE_ACCOUNT_B64`.
- Share the Sheet with the service-account email. No secret is stored in this repository.

Public fallback:

- `YARATU_SHEETS_URL` — published CSV URL; it may contain a `{gid}` placeholder.
- `YARATU_SHEETS_GID` — published tab GID.

`data/sheets_template.csv` is the import template and current fully reviewed export.
Sync fails closed if any row is unpublished, contains `REQUIRED`, lacks the required
review/provenance statuses, or has inconsistent halal evidence.

`.github/workflows/sync-yaratu-products.yml` checks the private Sheet hourly. It
commits `data/products.json` and the gated `site/dist` artifact to `main` only when
the validated snapshot changes; production deployment continues from `origin/main`.
