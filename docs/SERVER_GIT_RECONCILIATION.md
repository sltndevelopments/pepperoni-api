# Server ↔ git reconciliation (step 1)

The Selectel VPS (`37.9.4.101`, `/var/www/pepperoni/repo`) is the production
runtime. `origin/main` is the source of truth for code. The working tree on
the server is routinely dirty: `sync-vps.sh` (every 10 minutes) regenerates
catalog HTML, `products.json`, feeds and sitemaps, and the daily
`seo-agent-vps.sh` / `seo-worker.sh` write runtime JSON under `data/`.
PR #15 counted about **185 paths** outside git.

This document is the plan. Step 1 is **measurement only**.

## What step 1 does

Workflow: `.github/workflows/vps-git-reconciliation.yml`. Triggers:

- `workflow_dispatch`
- `push` to `main` filtered on `ops/recon-trigger.txt` (merge of that file
  runs the job; no `pull_request`, so PRs do not SSH to prod)

The repo is **public**: Actions logs and artifacts are world-readable. The
runner therefore never writes the plaintext tar. SSH stdout is piped into
`scripts/seal_vps_git_recon.py`, which keeps the tar in memory, prints
**aggregate counts only** (`untracked`, `ignored`, `modified`,
`cron_entries`, `systemd_entries`), and encrypts with `age` to the committed
recipient `ops/recon-age.pub`. The artifact is **only**
`recon-report.tar.age`. Decrypt locally with the matching age identity
(private key is not in git).

It uses the same `VPS_HOST` / `VPS_SSH_KEY` secrets as `deploy-vps.yml`,
SSHs as root, and runs `scripts/vps_git_recon_readonly.sh` **piped from the
runner**. The script on the VPS copy of `main` is never required.

The job **must not** modify the server: no `git add`, `commit`, `reset`,
`checkout`, `clean`, `stash`, `pull`, or `push`; no `rm` / `mkdir` / file
writes or shell redirects on the VPS. Every `git` invocation sets
`GIT_OPTIONAL_LOCKS=0` so git does not create an index lock. The collector
prints a **tar stream on stdout**. An empty `git-status-porcelain.txt` inside
the tar is a clean tree and is accepted. Members (inside the encrypted tar):

- `git-status-porcelain.txt` and `git-status-porcelain-ignored.txt`
- `untracked.txt` / `ignored.txt` (the out-of-git set)
- `git-diff-stat.txt` / `git-diff-numstat.txt` (tracked-but-modified)
- `crontab.txt` and `systemd.txt` (timers/services that write into the repo:
  `sync-vps.sh`, `seo-agent-vps.sh`, `seo-worker.sh`, and any unit whose
  `WorkingDirectory` or `ExecStart` mentions `/var/www/pepperoni/repo`)
- `mtimes.txt` — last-modified time and size of each dirty path

## Open PR #15 — what to do with it

[PR #15](https://github.com/sltndevelopments/pepperoni-api/pull/15)
(`cursor/phase1-measurement-safety-4c9b`) is a **draft** “PHASE 1 Measurement
& Safety” branch. It already diagnosed the 185-path drift
(`docs/PHASE1-VPS-DRIFT.md` on that branch) and proposed index-safety rails.

**Do not merge PR #15 as a way to copy the VPS dirty tree into git.** Those
paths are mostly cron output and runtime state. Treat #15 as historical
diagnosis. After this read-only report exists:

1. Keep #15 draft, or close it once the rails it proposed are already on
   `main` (many of them landed later).
2. Do not cherry-pick VPS-only HTML / `products.json` / `data/*.json` from
   that branch or from the server.
3. Rebase or reopen only the still-missing safety patches, as their own PRs.

## Backup before any later write

Step 2+ is out of scope here. Before anyone classifies or deletes:

1. On the VPS, as a snapshot **outside** the repo (example):
   `tar -C /var/www/pepperoni -czf /root/pepperoni-repo-backup-$(date -u +%Y%m%dT%H%M%SZ).tgz repo`
2. Keep the artifact from this workflow next to that tarball.
3. Never `git reset --hard` by hand to “clean” the tree. Deploy already does
   `git reset --hard origin/main` on push; that updates tracked files and
   leaves untracked runtime state alone.

## Classification buckets

Every path on the artifact gets exactly one label:

| Bucket | Meaning | Typical examples |
|---|---|---|
| `generated-by-cron` | A scheduled job rewrites it from Sheets or other SoT. Not a hand edit. | `public/products.json`, product cards, category HTML, `public/prices.*`, `llms.txt`, sitemap after `sync-vps.sh`; SEO agent HTML committed in the morning |
| `should-be-in-git` | Source, config, or a page that must travel with `main`. Missing from the repo is drift. | Scripts, workflows, `data/invariants.json`, hand-authored docs, nginx snippets that are the policy |
| `junk` | Safe to ignore or delete after backup. | `__pycache__`, stray `.tmp`, leftover test files, duplicate downloads |

Runtime ledgers (`data/daily_ledger.json`, `data/opus_budget.json`,
`data/llm_costs.json`, SQLite DBs, `data/logs/`) stay **out of git**. Deploy
already preserves the spend ledgers across `reset --hard`.

## Decision rules

1. **Sheets remain the catalog SoT.** A path that `sync-vps.sh` regenerates
   is `generated-by-cron`, even if git also tracks a stale copy.
2. **Do not add the 185-path dump to git** to make `git status` clean.
3. If a tracked file’s VPS copy is newer *and* the content is only a catalog
   regenerate, the next deploy’s `reset --hard` + `sync-vps.sh` is the
   intended path — do not commit the VPS bytes from SSH.
4. If a tracked file’s VPS copy contains a hotfix that is not on `main`,
   copy the *diff* into a PR from a laptop/CI checkout. The VPS is not a
   development remote.
5. `junk` is deleted only after the backup in the previous section and only
   for paths that no cron/unit still writes.
6. Secrets (`.env`, `seo-agent.env`, keys) are never committed. Confirm they
   are gitignored.

## Order of steps (cron stays on)

Catalog sync on the VPS is what keeps live prices honest. **Leave cron
running** until another writer exists (for example CI that syncs Sheets and
deploys the result). Stopping `sync-vps.sh` would freeze `api.pepperoni.tatar`
on the last git snapshot.

1. **Now:** merging a change to `ops/recon-trigger.txt` (or dispatching
   the workflow) encrypts the report and prints counts in the job log.
   Do not change the server. Decrypt the `.age` artifact privately before
   labelling paths.
2. Label every path on the artifact with the three buckets. Human review.
3. For `should-be-in-git`: PR from a clean checkout, then deploy as usual.
4. For `generated-by-cron`: keep generating on the VPS. Optionally gitignore
   more of the runtime set so `git status` is readable. Do **not** turn cron
   off.
5. For `junk`: delete after backup, only when nothing still writes the path.
6. Only after a non-VPS catalog pipeline is in production (Sheets → CI →
   `origin/main` → deploy, or an equivalent) consider moving `sync-vps.sh`
   off the 10-minute crontab.

`seo-agent-vps.sh` (daily) and `seo-worker.sh` stay on the same rule: they
may write runtime state; they must not become a second source of truth for
allowlisted HTML.

## Related

- `docs/vps-drift.md` — older deploy-key / `rsync` diagnosis
- `docs/HEADLESS-ARCHITECTURE.md` — VPS is the production host
- `.github/workflows/deploy-vps.yml` — `git reset --hard origin/main` +
  `sync-vps.sh` on every push to `main`
