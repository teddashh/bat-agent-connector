# Third-party notices

## Project Hub

The project and work item rules in `src/bat_agent_connector/work_items.py` are ported from Project Hub v4.68.2
(<https://github.com/kieiken/project-hub>, commit `031aedd4bf62ef4bb1e6199c31aa9c4323a116bb`):

| Project Hub file | Ported to | What was kept |
|---|---|---|
| `hub/lib/hierarchy.js` | `work_items.py` (`project.update`, `work_item.update`) | renames keep IDs and relations; a change names the version it was read at |
| `hub/lib/project-order.js`, `hub/public/project-order.js` | `work_items.siblings`, `_check_order`, `_save_order` | one saved order per parent, pins first, the order you saw as a precondition, archived entries keep their slot, unplaced branches after their source |
| `hub/lib/completion.js` | `work_items.completion`, `work_item.approve`, `work_item.continue` | an agent's done is a claim a person approves against a content fingerprint; a content change asks again; "keep working" holds for the current steps |
| `hub/lib/task-ids.js` | `work_items.py` IDs | IDs are never reused |

The offline importer in `src/bat_agent_connector/hub_import.py` also ports rules from the same pinned commit:

| Project Hub file | Ported to | What was kept / changed |
|---|---|---|
| `hub/lib/frontmatter.js` | `parse_doc`, `_value`, `_comment`, `_split` | limited strings/booleans/list/map dialect; Python rejects malformed, duplicate or unsupported input instead of silently defaulting |
| `hub/lib/store.js`, `hub/lib/hierarchy.js`, `hub/lib/task-ids.js` | `snapshot`, `normalize`, `record_key` | directory/file identities, full request body, steps, ID-first/unique-name relations; no Store construction or runtime execution |
| `hub/lib/project-order.js`, `hub/public/project-order.js`, `hub/public/app.js` | `normalize`, `_near`, `_merge_order` | display parents, derived placement, updated order, saved project groups and pins; invalid relations block, existing Connector slots are preserved |
| `hub/lib/completion.js` | `hub_hash`, `normalize` | full-file CRLF-normalized SHA-256 and compact steps hash; historical approvals never grant Connector approval; no migration seeding |
| `hub/lib/chat.js` | read-only request-history extraction | user JSONL rows retained as provenance; no replay, dispatch or ChatRunner |

Changes are listed in [docs/design/work-items.md](docs/design/work-items.md) and
[docs/design/hub-import.md](docs/design/hub-import.md). The fixtures are synthetic. Project Hub's license:

```
MIT License

Copyright (c) 2026 kieiken
Copyright (c) 2019-2020 Discord Bot Portal JP

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
