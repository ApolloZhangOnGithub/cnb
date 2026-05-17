# Troubleshooting: fetching c-n-b.space

## Symptom

`curl https://platform.c-n-b.space/...` or `python -m urllib3 ...` hangs, times out, or returns an Aliyun "Beaver" 403 ICP page. Same for `blog.c-n-b.space`, `docs.c-n-b.space`, and the apex `c-n-b.space`.

## Cause

The server side is healthy — HSTS is on (`Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`) and HTTPS responds 200/302 normally.

What goes wrong is the local network path:

1. The user's HTTP client picks up a system / corp / school proxy (MacPacket on `127.0.0.1:1082`, Aliyun, etc.).
2. That proxy intercepts the request. For HTTPS it usually either fails the TLS handshake (no MITM cert installed) or rewrites DNS to a sinkhole (`198.18.x.x`).
3. For plain HTTP, an upstream ICP scanner returns a fixed 403 ("Beaver") because `c-n-b.space` is hosted in mainland China.

## Workaround for tongxue: `bin/fetch-site`

The repo ships a small script that bypasses every locally-installed proxy by going straight to the origin IP over a raw TLS socket via `openssl s_client`.

```bash
bin/fetch-site https://platform.c-n-b.space/docs/zh
bin/fetch-site https://blog.c-n-b.space/posts/123
bin/fetch-site --head https://c-n-b.space/
```

Allowed hosts are pinned (`platform.c-n-b.space`, `blog.c-n-b.space`, `docs.c-n-b.space`, `c-n-b.space`). Other hosts intentionally error out — for them, normal `curl` / `requests` is fine.

## Workaround by hand

If you can't run `bin/fetch-site`:

```bash
# HEAD
printf 'HEAD / HTTP/1.1\r\nHost: platform.c-n-b.space\r\nConnection: close\r\n\r\n' \
  | openssl s_client -connect platform.c-n-b.space:443 \
      -servername platform.c-n-b.space -quiet 2>/dev/null
```

Replace path and `Host:` to fetch a body. `-quiet` suppresses the certificate dump so the response starts with `HTTP/1.1`.

## What does **not** work

- `curl --noproxy '*'` — only bypasses `$http_proxy`/`$https_proxy`; system-wide pf / PAC redirects still hijack the connection.
- Switching to `requests` / `urllib3` / `httpx` — they all honour the same OS proxy settings.
- `curl --insecure` — doesn't help; the issue is interception, not certificate validation.

## Long-term fix

`Strict-Transport-Security: max-age=...; preload` is already served. We can't submit `c-n-b.space` to the Chromium HSTS preload list yet because:

- `http://c-n-b.space` returns a 403 from the upstream Beaver instead of a 301/302 to `https://`. Preload requires an HTTP → HTTPS redirect at the apex.
- `platform.c-n-b.space` currently serves a certificate whose CN is `docs.c-n-b.space`, so [hstspreload.org](https://hstspreload.org/?domain=c-n-b.space) rejects the chain as invalid.

Fix both (apex 80→443 redirect, multi-SAN cert), then submit. Until then, use `bin/fetch-site`.
