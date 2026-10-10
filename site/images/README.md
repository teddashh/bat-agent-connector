# Product screenshots

These PNGs are unedited screenshots of the actual shared browser frontend's
project workspace redesign (2026-10-10, issue #79). The corresponding source and
capture script are committed alongside the images; Git history pins that source.
They use `desktop/tests/workspace-fixture.ts` and the published-dispatch fixture.
No customer hosts, credentials, conversations or production delivery results are shown.
They illustrate the UI; they do not establish native installation or live acceptance.

To regenerate after a frontend change:

1. Install `desktop/` dependencies with `npm ci` and build with `npm run build:all`.
2. From `desktop/`, run `BATC_UI_TEST_PORT=18746 node tests/static-server.mjs`.
3. From the repository root, run `node --experimental-strip-types scripts/capture_site.mjs`.
4. Stop the fixture server and inspect all four images.

`workspace-en/zh.png` show the project tree, conversation, reply and result inspector
in the existing dark theme. `dispatch-en/zh.png` show project dispatch in the light
theme. Both are captured at 1240 × 820, in English and Traditional Chinese. The
website labels these images as demonstration data.
