# Custom Domain Operations

The public cnb introduction site is served by GitHub Pages at:

<https://c-n-b.space/>

GitHub Pages remains the hosting layer. DNS should point the apex domain to GitHub Pages, with `www` redirecting through Pages:

| Name | Type | Value |
|------|------|-------|
| `@` | `A` | `185.199.108.153` |
| `@` | `A` | `185.199.109.153` |
| `@` | `A` | `185.199.110.153` |
| `@` | `A` | `185.199.111.153` |
| `@` | `AAAA` | `2606:50c0:8000::153` |
| `@` | `AAAA` | `2606:50c0:8001::153` |
| `@` | `AAAA` | `2606:50c0:8002::153` |
| `@` | `AAAA` | `2606:50c0:8003::153` |
| `www` | `CNAME` | `apollozhangongithub.github.io` |

For GoDaddy-hosted DNS, use the helper with a profile-specific credential set. This keeps the Norway and US GoDaddy accounts separate:

```bash
export GODADDY_NO_API_KEY=...
export GODADDY_NO_API_SECRET=...
bin/configure-godaddy-pages-dns --profile godaddy-no
```

The helper also accepts `GODADDY_US_API_KEY` / `GODADDY_US_API_SECRET` for a US account, or a JSON profile file at `~/.config/cnb/godaddy-profiles.json`:

```json
{
  "profiles": {
    "godaddy-no": {
      "api_key": "...",
      "api_secret": "...",
      "api_base": "https://api.godaddy.com"
    },
    "godaddy-us": {
      "api_key": "...",
      "api_secret": "..."
    }
  }
}
```

Use `--dry-run` before changing records when moving a domain between accounts.
