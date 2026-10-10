# Product screenshots

These PNGs are unedited screenshots of the actual shared browser frontend at the
`15b2048de5c2ec3a31e0845ce76a79b612d1c32e` product baseline (2026-10-10).
They use the repository's synthetic attention and published-dispatch fixtures.
No customer hosts, credentials, conversations or production delivery results are shown.
They illustrate the UI; they do not establish native installation or live acceptance.

To regenerate after a frontend change:

1. Install `desktop/` dependencies with `npm ci` and build with `npm run build:all`.
2. From `desktop/`, run `BATC_UI_TEST_PORT=18746 node tests/static-server.mjs`.
3. From the repository root, run `node --experimental-strip-types scripts/capture_site.mjs`.
4. Stop the fixture server, inspect all four images and update this source baseline.

`attention-en/zh.png` show separate attention categories. `dispatch-en/zh.png` show
the actual project dispatch form. Both are captured at 1240 × 820, in English and
Traditional Chinese. The website labels these images as demonstration data.
