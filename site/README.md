# Maintaining the product website

This is the public GitHub Pages introduction to **Better Agent Dashboard**. It is
not the operational Dashboard served by Python. No credentials, live API calls,
analytics or remote scripts belong here.

## Sources

- `scripts/build_product_site.py`: bilingual product copy and semantic HTML layout.
  Run `python3 scripts/build_product_site.py` after editing it; `site/index.html`
  is its deterministic generated output.
- `styles.css`: site tokens and responsive components. See [DESIGN.md](DESIGN.md).
- `lang.js` / `app.js`: URL / saved-language selection, mobile navigation and the
  screenshot gallery. Without JavaScript the English page and both images work.
- [images/README.md](images/README.md): actual UI screenshot source, synthetic data
  disclosure and regeneration instructions.
- [English README](../README.md), [繁中 README](../README.zh-TW.md) and
  [setup guides](../docs/getting-started.md): detailed reader and operator paths.

The old externally generated `page.json` and unused flow renderer were removed.
Do not regenerate this page with the external project-page kit: it describes an
older MCP / CLI-only product. The original project palette, mark and language
bootstrap were retained from the repository's previous project-page-kit site
(https://github.com/teddashh/teddashh.github.io/tree/main/kit).

Keep both languages aligned. Update the evidence baseline only when the referenced
candidate actually passed. Treat managed installation as required behavior still
in development until installed acceptance proves it. Do not invent tool counts,
use fixture screenshots as live evidence, or label validation artifacts as a signed
release. Platform claims must distinguish desktop client, central service and Fleet.

## Preview and verification

From the repository root:

```bash
python3 scripts/build_product_site.py
python3 scripts/check_product_site.py
python3 -m http.server 18745 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:18745/` or `?lang=zh-TW`; stop the server when finished.
For responsive browser verification, install `desktop/` dependencies and the
Playwright Chromium browser, then run:

```bash
SITE_SCREENSHOT_DIR="$HOME/agent-work/artifacts/product-site-review" node scripts/verify_product_site.mjs
```

The script owns an ephemeral loopback server with the production `/bat-agent-connector/`
base path, closes it on exit, checks both languages at 390 / 768 / 1440px, gallery,
keyboard / mobile navigation, persistence, no-JavaScript fallback and the 404 page.
It saves screenshots and a JSON result for inspection; images are not test basetemps.

## Publishing

The existing GitHub Pages workflow validates a PR before deployment. A main push
with site changes validates again and deploys `site/` through GitHub Pages. Review
local screenshots and the source commit, then verify the live page after deployment.
No separate hosting service or framework is required.
