# kazylyk.com — VPS runbook

Static brand site in `kazylyk/`. Production is the Selectel VPS, same as
pepperoni.tatar and yaratu.com. Cloudflare stays **DNS only**. Do not enable
the orange proxy, Pages, or Workers for this hostname.

## Files

- Site root in the repo: `kazylyk/`
- Nginx template: `deploy/nginx/kazylyk.conf`
- Suggested document root: `/var/www/kazylyk/current`

This first version has no generator and no deploy script. Copy the `kazylyk/`
tree to the document root after `origin/main` contains the files you want live.

## TLS

Certificate must cover `kazylyk.com` and `www.kazylyk.com`. Obtain it with
DNS-01 before publishing an HTTP-only vhost.

```text
/etc/letsencrypt/live/kazylyk.com/fullchain.pem
/etc/letsencrypt/live/kazylyk.com/privkey.pem
```

## DNS cutover (operator)

After nginx serves the site on the VPS (`curl --resolve kazylyk.com:443:127.0.0.1 https://kazylyk.com/`):

```text
kazylyk.com      A      37.9.4.101    (proxy off)
www.kazylyk.com  CNAME  kazylyk.com   (proxy off)
```

Do not change live DNS from this document without an explicit operator step.
