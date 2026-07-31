# Lead Userbot Droplet

MTProto lead reader that closes the SEO→lead loop. Documented here because it is
**not** covered by the main VPS deploy and was previously an undocumented drift
point.

## Why a separate droplet

Telegram MTProto is network-blocked from the Selectel VPS (`37.9.4.101`) — probes
to every Telegram DC/port failed, and the provided SOCKS5 proxies also blocked
MTProto. A DigitalOcean droplet (Amsterdam, `178.62.250.104`) has open MTProto,
so the Telethon **user** account runs there. It must be a user account, not a
bot: Telegram bots can never read messages sent by *other* bots, and the leads
group is fed by 5 channel bots.

## Layout on the droplet (`/opt/leadbot`)

```
/opt/leadbot/
  repo/                     git clone of pepperoni-api (code comes ONLY from here)
    scripts/lead_userbot.py service entrypoint
    scripts/lead_listener.py parsing + storage (shared with VPS)
    data/leads.json         -> symlink to /opt/leadbot/data/leads.json
    tg-state/               -> symlink to /opt/leadbot/tg-state
  data/leads.json           persistent lead store (NOT in git)
  tg-state/lead_userbot.session  Telethon session (NOT in git)
  leadbot.env               TG_API_ID / TG_API_HASH / LEADS_GROUP_ID / session path
```

`leadbot.service` runs `repo/scripts/lead_userbot.py --loop`. Runtime data lives
outside the clone and is symlinked in, so a clean checkout can never wipe leads
or the session.

## Data flow

```
site form / 5 channel bots → leads group (Telegram)
  → userbot (droplet) parses → /opt/leadbot/data/leads.json
  → VPS cron scripts/sync_leads_from_droplet.sh (every 5 min, scp+validate+atomic)
  → repo/data/leads.json on VPS → brain digest reads real, attributed leads
```

Attribution: the site form sends an explicit `🧪 Эксперимент: exp-…` line;
`lead_listener._landing_and_experiment` trusts that id directly (falls back to
mapping the landing URL against the active experiment registry).

## Deploy (the only code channel: git pull)

From the droplet (or via the VPS as a jump host):

```
bash /opt/leadbot/repo/infra/scripts/leadbot-droplet-deploy.sh
```

It does `git pull --rebase origin main`, re-asserts the runtime symlinks, and
restarts the service. **Never** `git reset --hard` here (would drop the symlinks
and any local safety) — same rule as the VPS producer node in `CLAUDE.md §6`.

> Reminder: after changing `lead_listener.py` / `lead_userbot.py`, run this
> deploy on the droplet too — the VPS `deploy-vps.yml` action does not touch it.

## Health

The VPS watchdog (`scripts/lead_pipeline_watchdog.py`, cron every 10 min) checks
`systemctl is-active leadbot.service` on this droplet over SSH and alerts the
owner (Telegram emergency) if it is down.

## Related: Moscow field CRM (`moscow-leads/`)

Inbound cards from this group are also bridged into `moscow-leads/` (Arbi
status buttons, 72h distributor rule, Friday digest). That package runs on the
**VPS** (`deploy/moscow-lead-bot.service`), not on this droplet. See
`moscow-leads/README.md`.
