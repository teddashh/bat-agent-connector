import { readFile, writeFile } from "node:fs/promises";
const index = new URL("../../src/bat_agent_connector/dashboard/index.html", import.meta.url);
const html = (await readFile(index, "utf8"))
  .replace(/<script type="module"[^>]*src="\.\/app.js"><\/script>/, '<script type="module" src="/dashboard/app.js"></script>')
  .replace('href="./app.css"', 'href="/dashboard/app.css"');
await writeFile(index, "<!-- Generated from desktop/index.html and desktop/src; npm run build:browser. -->\n" + html);
const css = new URL("../../src/bat_agent_connector/dashboard/app.css", import.meta.url);
await writeFile(css, "/* Generated from desktop/src/app.css; npm run build:browser. Do not edit. */\n" + await readFile(css, "utf8"));
// Preserve the existing server's four-file allowlist. Translations are bundled in app.js.
await writeFile(new URL("../../src/bat_agent_connector/dashboard/i18n.js", import.meta.url),
  "// Generated compatibility asset. Translations now build from desktop/src/i18n.js into app.js.\n");
