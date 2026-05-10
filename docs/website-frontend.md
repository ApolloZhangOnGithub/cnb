# Website frontend

The public website is a static page under `site/`. It is intentionally separate from the Python package and does not require a frontend build step.

## Source files

| Path | Purpose |
|------|---------|
| `site/index.html` | Static page markup and content structure. |
| `site/styles.css` | Visual system, layout, and responsive behavior. |
| `site/app.js` | Small client-side interactions such as the install-command copy button. |
| `site/favicon.svg` | Browser favicon. |
| `site/CNAME` | GitHub Pages custom domain target. |

## Local preview

From the repository root:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory site
```

Then open:

```text
http://127.0.0.1:4173/
```

Opening `site/index.html` directly also works for layout review, but the browser may block clipboard writes on `file://`. In that case the copy button selects the install command instead of reporting a hard failure.

## Publishing

The tracked `site/` directory is the source for the public GitHub Pages site at `https://c-n-b.space`. Publishing is handled by the repository Pages workflow/configuration on `master`.

If the local preview has changed but `https://c-n-b.space` has not, confirm the static site files were committed and pushed, then check the repository Pages publishing configuration and workflow run.

## Verification

Use Playwright to check the static page in desktop and mobile viewports:

```sh
python3 - <<'PY'
from pathlib import Path
from playwright.sync_api import sync_playwright

url = Path("site/index.html").resolve().as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, viewport in [
        ("desktop", {"width": 1440, "height": 1000}),
        ("mobile", {"width": 390, "height": 844}),
    ]:
        page = browser.new_page(viewport=viewport)
        messages = []
        page.on("console", lambda msg: messages.append((msg.type, msg.text)))
        page.on("pageerror", lambda err: messages.append(("pageerror", str(err))))
        page.goto(url, wait_until="load")
        overflow = page.evaluate(
            """() => {
              const doc = document.documentElement;
              const visibleOverflow = [];
              for (const el of document.querySelectorAll('body *')) {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                if (
                  style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  rect.width > 0 &&
                  rect.height > 0 &&
                  rect.right - doc.clientWidth > 1
                ) {
                  visibleOverflow.push(el.className || el.tagName.toLowerCase());
                }
              }
              return {
                scrollWidth: doc.scrollWidth,
                clientWidth: doc.clientWidth,
                visibleOverflow: visibleOverflow.slice(0, 10),
              };
            }"""
        )
        print(f"{name}: title={page.title()!r} scroll={overflow} console={messages}")
        page.close()
    browser.close()
PY
```

Expected result:

- No console messages or page errors.
- `scrollWidth` equals `clientWidth` in both desktop and mobile viewports.
- `visibleOverflow` is empty.

Also run:

```sh
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path

HTMLParser().feed(Path("site/index.html").read_text())
print("html parser ok")
PY

git diff --check -- site/index.html site/styles.css site/app.js docs/website-frontend.md
```

## Current design direction

The current page uses a restrained product-site style:

- dark local-command-center hero;
- static dashboard and board previews instead of marketing illustration;
- compact cards for repeated documentation and capability items;
- responsive mobile layout with decorative hero panels disabled to preserve readability;
- no build pipeline, generated assets, or external runtime dependencies.
