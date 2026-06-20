# VPS Code Drift — Root Cause & Canonical Fix

_Written 2026-06-20. Status: diagnosed, not yet fixed._

---

## Context

The VPS at `37.9.4.101` is the production runtime for all SEO agents
(`seo-agent-vps.sh`, `generate_geo_bulk.py`, `page_reviewer.py`, etc.).
The canonical source of truth is `origin/main` on GitHub.

During GEO-format sample generation (2026-06-20) three divergences between
VPS and `origin/main` were observed, causing scripts synced via `rsync` to
conflict with the VPS environment.

---

## Root Cause 1 — VPS cannot pull from GitHub autonomously

### Symptom
`git pull origin main` on the VPS fails:
```
fatal: could not read Username for 'https://github.com': No such device or address
```

### Root
The VPS git remote is `https://github.com/…`. GitHub PAT authentication
(`http.extraheader`) is written by `deploy-vps.yml` **only during the
GitHub Actions deploy run**. Between deploys (i.e. when cron-launched SEO
agents run `git pull` or `git push`) the credential is absent — the config
key may still be set but the PAT itself is scoped to the Actions runner
environment, not the VPS process tree.

### Canonical Fix
Switch the VPS git remote to **SSH** with a dedicated deploy key:

1. Generate an Ed25519 deploy key on the VPS:
   ```bash
   ssh-keygen -t ed25519 -C "vps-seo-agent" -f /root/.ssh/gh_deploy_key -N ""
   ```
2. Add the public key to the GitHub repo as a **Deploy Key** (Settings →
   Deploy keys → Add key). Read+Write needed so the agent can push commits.
3. Configure the VPS remote:
   ```bash
   cd /var/www/pepperoni/repo
   git remote set-url origin git@github.com:sltndevelopments/pepperoni-api.git
   ```
4. Add to `/root/.ssh/config`:
   ```
   Host github.com
     IdentityFile /root/.ssh/gh_deploy_key
     StrictHostKeyChecking no
   ```
5. Update `deploy-vps.yml` "Deploy via git sync" step to use the same SSH
   remote (the `appleboy/ssh-action` already connects via `VPS_SSH_KEY`; the
   `git fetch origin main` there will use the deploy key on the VPS itself).
6. Remove the `http.extraheader` block from "Write SEO Agent env file" step
   — it is no longer needed once SSH remote is set.

After this fix, the VPS can `git pull origin main` at any time without
relying on a transient PAT injected by Actions.

---

## Root Cause 2 — `call_claude` on VPS is a diverged version (DeepSeek, no `temperature`)

### Symptom
`page_reviewer.py` in `origin/main` calls:
```python
call_claude(prompt, system=_CRITERIA, max_tokens=512,
            model="claude-sonnet-4-6", temperature=0.1)
```
VPS `claude_client.py::call_claude` signature does **not** accept
`temperature` (it routes to DeepSeek, not Anthropic), so the reviewer
raises `TypeError` on every invocation → `hold` verdict for all pages.

### Root
The VPS has a locally-modified `claude_client.py` that diverges from
`origin/main`. Because `git reset --hard origin/main` runs **only** during
the GitHub Actions deploy (not at cron time), any manual edit or hotfix
applied directly on the VPS persists between deploys — exactly the kind of
drift `git reset --hard` is supposed to prevent but only does once per push.

**Immediate fix already committed to `origin/main`:** removed `temperature=`
kwarg from `page_reviewer.py` (commit `a786751a`, merged into
`temperature`-removal in `page_reviewer.py`).

### Canonical Fix (same as Root Cause 1)
Once the SSH deploy key is set up, `deploy-vps.yml` can `git reset --hard
origin/main` reliably on every push. That guarantees `claude_client.py` and
all other scripts match `origin/main` within minutes of a commit.

No manual hotfixes on the VPS. The VPS is an ephemeral runtime, not a
development environment.

---

## Root Cause 3 — `data/invariants.json` not deployed to VPS

### Symptom
`invariants.py` on VPS fails to load:
```
invariants: cannot load registry: [Errno 2] No such file or directory:
  '/var/www/pepperoni/repo/data/invariants.json'
```

### Root
`data/` is in `.gitignore` as a blanket exclusion (runtime state: DB, logs,
caches). `invariants.json` is code-adjacent config — a protected registry
of solved invariants — not runtime state. It should travel with the code.

**Actual finding:** `git ls-files data/invariants.json` on `origin/main`
confirms the file **IS already tracked** (not in `.gitignore`). The file is
absent on the VPS for a different reason: `git reset --hard origin/main`
only runs during GitHub Actions deploys. Any code push from a VPS cron job
that does **not** re-run the deploy workflow leaves the VPS on a stale tree.
On 2026-06-20 the VPS HEAD was `f3267c8` (a cron-authored commit) while
`origin/main` was `a786751a` — 2 commits ahead. The VPS was **ahead** of
origin (it had pushed), but had never received a `git reset --hard` since
those commits. The file was added to origin/main in a session where it had
never been deployed to VPS via the Actions workflow.

### Canonical Fix
Ensure `deploy-vps.yml` triggers after **every** push to `main`, including
agent-authored cron commits. Currently this is the case (`on: push: branches:
[main]`) but GH Actions skips triggering a new workflow run when the push is
made by the `GITHUB_TOKEN` / PAT of the same workflow. Agent commits use
`GH_PAT` (a separate PAT secret) — confirm this PAT is not the same as the
`GITHUB_TOKEN` used by the workflow runner, otherwise the deploy won't trigger.

As an additional safety net, add an explicit `data/invariants.json` copy to
the "Install SEO Agent cron" step in `deploy-vps.yml` so the file is
guaranteed to exist regardless of git HEAD state:

---

## Summary — One canonical deploy path

| Layer | Mechanism | Status |
|---|---|---|
| Code push → VPS | `deploy-vps.yml` → `git reset --hard origin/main` | ✅ works, runs on push |
| VPS → GitHub (agent commits) | `git push origin main` via PAT | ⚠️ breaks between deploys |
| VPS autonomous `git pull` | Not possible (HTTPS, no persistent credential) | ❌ root cause 1 |
| `invariants.json` on VPS | Not deployed (`.gitignore` exclusion) | ❌ root cause 3 |

**Target state:**
- VPS remote = SSH + deploy key → `git pull/push` work anytime
- `deploy-vps.yml` removes the `http.extraheader` PAT injection (redundant)
- `data/invariants.json` unignored → deploys with every push
- `rsync` as a code delivery channel is **prohibited** (masks drift, bypasses
  git history, creates the very divergence documented here)
