# Synthetic Hub import fixtures (B05)

These files use the on-disk layout of Project Hub v4.68.2,
`kieiken/project-hub@031aedd4bf62ef4bb1e6199c31aa9c4323a116bb` (MIT):

- `hub/lib/store.js`, `frontmatter.js`, `task-ids.js`: `Product/<id>/PROJECT.md`, `.ai/tasks/<id>.md`, limited frontmatter, Markdown sections and legacy task names.
- `hub/lib/hierarchy.js`, `hub/lib/project-order.js`, `hub/public/project-order.js`, `hub/public/app.js`: ID/name references, saved project groups, project pins, derived display parents and task ordering.
- `hub/lib/completion.js`: `_hub/completion.json`, migration marker, SHA-256 of the full task file (CRLF normalized), and compact `JSON.stringify(steps)` for continued decisions.
- `hub/lib/chat.js`: user request rows in `.ai/chat/<task>.jsonl`.

Every name, request, historical actor and URL is synthetic. URLs use `example.invalid`; there are no hosts, credentials, tokens, emails, provider sessions or personal conversations. The `basic` tree has four projects and eight tasks, including the same legacy `t` task name in two projects, name-based project parenting, same-project and cross-project derived tasks, a pinned project, a matched historical completion, a stale completion and a continued decision.

The `date-id` tree separately preserves a date/sequence task filename with matching frontmatter `id`.

Deliberate differences: task names are descriptive legacy names rather than reserved date/sequence IDs, dates are fixed, the marker is a fixture label, and the `Acceptance`/`驗收條件` headings are this adapter's explicit extraction convention (Hub has no native acceptance field). One assistant row demonstrates exclusion from request history; this is not a runtime transcript. Non-HTTP references and code URLs exercise preservation without opening or materializing them. Tests mutate temporary copies to cover damaged/missing files, unsafe filesystem objects, conflicts and recovery; they never execute Hub's `Store`, which can write completion data on reads.
