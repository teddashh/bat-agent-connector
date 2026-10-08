// BAT Dashboard: a client of /api/v1 only. Every change is an operation with an Idempotency-Key; text from
// sessions is always set with textContent (never parsed as HTML).
import { t } from "./i18n.js";

const TOKEN_KEY = "batc.dashboard.token";
const state = { token: null, caps: null, lastEvent: 0, listeners: new Set() };

function loadToken() {
  try { return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
function saveToken(token, remember) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    if (remember) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage may be unavailable; the token stays in memory */ }
}
function clearToken() {
  try { sessionStorage.removeItem(TOKEN_KEY); localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}

// ------------------------------------------------------------------ DOM helpers
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const chip = (text, cls = "") => h("span", { class: `chip ${cls}` }, text);
function when(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString();
}
async function draftId(scope, request) {
  // A draft is the exact request: resending it (lost reply, double click) reuses its key, a different text does not.
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(request)));
  return `${scope}.${[...new Uint8Array(digest).slice(0, 12)].map(b => b.toString(16).padStart(2, "0")).join("")}`;
}
const TERMINAL = ["succeeded", "failed", "cancelled"];
async function keyFor(scope) {
  // One idempotency key per draft: a retry of the same draft reuses it, so the action happens once. The server
  // keeps keys for good, so once the operation a key made has finished, the same draft is a new request.
  const k = `batc.key.${scope}`;
  let saved = null;
  try {
    const raw = localStorage.getItem(k);
    try { saved = JSON.parse(raw); } catch { saved = raw ? { key: raw } : null; } // a bare key from an older page
  } catch { saved = null; }
  if (saved?.key && saved.op) {
    try {
      const op = (await api("GET", `/operations/${saved.op}`)).operation;
      if (TERMINAL.includes(op.status)) saved = null;
    } catch (e) { if (e.status === 404) saved = null; } // unreachable: keep the key, a retry must not act twice
  }
  if (saved?.key) return saved.key;
  const key = crypto.randomUUID();
  try { localStorage.setItem(k, JSON.stringify({ key })); } catch { /* ignore */ }
  return key;
}
function rememberOp(scope, key, op) {
  try { localStorage.setItem(`batc.key.${scope}`, JSON.stringify({ key, op })); } catch { /* ignore */ }
}
function dropKey(scope) { try { localStorage.removeItem(`batc.key.${scope}`); } catch { /* ignore */ } }

// ------------------------------------------------------------------ API
class ApiError extends Error {
  constructor(status, code, message) { super(message || code); this.status = status; this.code = code; }
}
async function api(method, path, body, key) {
  if (!state.token) throw new ApiError(401, "UNAUTHORIZED", t("need_token"));
  const headers = { Authorization: `Bearer ${state.token}` };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (key) headers["Idempotency-Key"] = key;
  const res = await fetch(`/api/v1${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error?.code, data.error?.message);
  return data;
}
function errorBox(e) {
  const text = e.status === 403 && e.code === "FORBIDDEN" ? t("forbidden_scope") : `${e.code || ""} ${e.message || e}`;
  return h("p", { class: "error" }, text);
}
async function submit(action, target, params, preconditions, scope) {
  const request = { action, target, params, preconditions };
  scope = await draftId(scope, request);
  const key = await keyFor(scope);
  try {
    const out = await api("POST", "/operations?wait=3", request, key);
    if (TERMINAL.includes(out.operation.status)) dropKey(scope); else rememberOp(scope, key, out.operation.operation_id);
    return out.operation;
  } catch (e) {
    if (e.status && e.status < 500) dropKey(scope); // refused, nothing stored: the next attempt is a new request
    throw e;
  }
}

// ------------------------------------------------------------------ live events (fetch-based SSE: it can send Authorization)
function onEvents(fn) { state.listeners.add(fn); return () => state.listeners.delete(fn); }
async function streamEvents() {
  const live = document.getElementById("live");
  for (;;) {
    if (!state.token) { live.className = "live down"; live.textContent = ""; await sleep(2000); continue; }
    try {
      const res = await fetch(`/api/v1/events/stream?after=${state.lastEvent}`,
        { headers: { Authorization: `Bearer ${state.token}` } });
      if (!res.ok || !res.body) throw new Error(String(res.status));
      live.className = "live ok"; live.textContent = "live";
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, cut); buf = buf.slice(cut + 2);
          const data = block.split("\n").filter(l => l.startsWith("data: ")).map(l => l.slice(6)).join("\n");
          if (!data) continue;
          const ev = JSON.parse(data);
          state.lastEvent = Math.max(state.lastEvent, ev.seq);
          for (const fn of state.listeners) fn(ev);
        }
      }
    } catch { /* reconnect below */ }
    live.className = "live down"; live.textContent = "offline";
    await sleep(3000);
  }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
function debounce(fn, ms) { let id; return () => { clearTimeout(id); id = setTimeout(fn, ms); }; }

// ------------------------------------------------------------------ shared pieces
function sessionBadges(s) {
  return [
    chip(s.host),
    s.api_access === "managed" ? chip(t("managed"), "managed") : chip(t("read_only"), "readonly"),
    s.stale ? chip(`${t("stale")} · ${t("stale_reason_" + s.stale_reason)}`, "stale") : null,
    s.pending ? chip(t("pending_" + s.pending.kind), "stale") : null,
  ];
}
function light(s) {
  const cls = s.pending ? "pending" : s.streaming ? "streaming" : s.loaded ? "ok" : "";
  return h("span", { class: `light ${cls}`, title: s.streaming ? t("state_streaming") : s.loaded ? t("state_loaded") : t("state_unloaded") });
}
function sessionRow(s) {
  return h("div", { class: "row" }, light(s),
    h("div", { class: "grow" },
      h("a", { class: "title", href: `#/session/${encodeURIComponent(s.host)}/${encodeURIComponent(s.session_id)}` },
        s.title || s.session_id),
      h("div", { class: "muted" }, [s.workspace, s.agent_kind, s.worktree_branch].filter(Boolean).join(" · "))),
    ...sessionBadges(s),
    h("span", { class: "muted" }, when(s.last_activity_at)));
}
const epoch = x => (x ? new Date(x * 1000).toISOString() : "");
function opStatus(op) {
  return h("span", { class: `status-${op.status}` }, t("op_" + op.status));
}
function opRow(op) {
  return h("div", { class: "row" },
    h("div", { class: "grow" },
      h("a", { class: "title", href: `#/op/${op.operation_id}` }, op.action),
      h("div", { class: "muted" }, [op.actor, when(epoch(op.created_at))].join(" · ")),
      op.status_reason ? h("div", { class: "muted" }, op.status_reason) : null),
    opStatus(op), op.error_code ? chip(op.error_code, "bad") : null);
}

// ------------------------------------------------------------------ views
async function viewHome(main) {
  const tab = sessionStorage.getItem("batc.tab") || "needs";
  const panel = h("div", { class: "panel" });
  const tabs = h("div", { class: "tabs" },
    h("button", { class: tab === "needs" ? "on" : "", onclick: () => { sessionStorage.setItem("batc.tab", "needs"); route(); } }, t("tab_needs_you")),
    h("button", { class: tab === "confirm" ? "on" : "", onclick: () => { sessionStorage.setItem("batc.tab", "confirm"); route(); } }, t("tab_to_confirm")));
  main.append(h("h1", {}, t("nav_home")), tabs, panel);
  const render = async () => {
    panel.replaceChildren(h("p", { class: "muted" }, t("loading")));
    try {
      if (tab === "needs") {
        const [sessions, ops, hosts, decide] = await Promise.all([
          api("GET", "/sessions?attention=true&limit=50"),
          api("GET", "/operations?status=needs_attention,uncertain&limit=50"),
          api("GET", "/hosts"), api("GET", "/work-items?pending=true&limit=50")]);
        const bad = hosts.hosts.filter(x => x.stale);
        const rows = [
          ...bad.map(x => h("div", { class: "row" }, h("span", { class: "light bad" }),
            h("div", { class: "grow" }, h("div", { class: "title" }, `${t("unreachable_hosts")}: ${x.host}`),
              h("div", { class: "muted" }, x.error || t("stale_reason_" + x.stale_reason))))),
          ...decide.work_items.map(workItemRow), ...sessions.sessions.map(sessionRow), ...ops.operations.map(opRow)];
        panel.replaceChildren(...(rows.length ? rows : [h("p", { class: "muted" }, t("empty_needs_you"))]));
      } else {
        const ops = await api("GET", "/operations?status=accepted,running,waiting_checks,waiting_external&limit=50");
        panel.replaceChildren(...(ops.operations.length ? ops.operations.map(opRow)
          : [h("p", { class: "muted" }, t("empty_to_confirm"))]));
      }
    } catch (e) { panel.replaceChildren(errorBox(e)); }
  };
  await render();
  return onEvents(debounce(render, 500));
}

async function viewSessions(main) {
  const q = new URLSearchParams(sessionStorage.getItem("batc.sessions") || "");
  const hostSel = h("select", {}, h("option", { value: "" }, t("all_hosts")));
  const accessSel = h("select", {}, h("option", { value: "" }, t("all_access")),
    h("option", { value: "managed" }, t("only_managed")), h("option", { value: "read_only" }, t("only_read_only")));
  const list = h("div", { class: "panel" });
  const more = h("button", { class: "secondary", hidden: true }, t("load_more"));
  main.append(h("h1", {}, t("nav_sessions")), h("div", { class: "filters" }, hostSel, accessSel), list, more);
  try {
    for (const x of (await api("GET", "/hosts")).hosts) hostSel.append(h("option", { value: x.host }, x.host));
  } catch (e) { list.replaceChildren(errorBox(e)); return; }
  hostSel.value = q.get("host") || ""; accessSel.value = q.get("access") || "";
  let cursor = null;
  const load = async (reset) => {
    const p = new URLSearchParams({ limit: "50" });
    if (hostSel.value) p.set("host", hostSel.value);
    if (accessSel.value) p.set("access", accessSel.value);
    sessionStorage.setItem("batc.sessions", p.toString());
    if (!reset && cursor) p.set("cursor", cursor);
    try {
      const page = await api("GET", `/sessions?${p}`);
      const rows = page.sessions.map(sessionRow);
      if (reset) list.replaceChildren(...rows); else list.append(...rows);
      cursor = page.next_cursor; more.hidden = !cursor;
    } catch (e) { list.replaceChildren(errorBox(e)); }
  };
  hostSel.onchange = accessSel.onchange = () => load(true);
  more.onclick = () => load(false);
  await load(true);
  const reload = debounce(() => load(true), 800);
  return onEvents(ev => { if (ev.resource_type === "session" || ev.resource_type === "host") reload(); });
}

async function viewSession(main, host, sid) {
  const head = h("div", { class: "panel" });
  const msgs = h("div", { class: "panel" });
  const controls = h("div", { class: "panel" });
  main.append(head, controls, h("h2", {}, t("messages")), msgs);
  let row, from, linked;
  try { ({ session: row, started_from: from, work_items: linked } = await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}`)); }
  catch (e) { head.replaceChildren(errorBox(e)); return; }
  if (!head.isConnected) return; // the user navigated away while this loaded; never add to the next page
  head.replaceChildren(h("h1", {}, row.title || sid), h("div", { class: "actions" }, ...sessionBadges(row)),
    h("dl", { class: "kv" },
      h("dt", {}, t("host")), h("dd", {}, row.host), h("dt", {}, t("workspace")), h("dd", {}, row.workspace || ""),
      h("dt", {}, "Session"), h("dd", {}, h("code", {}, row.session_id)),
      h("dt", {}, t("agent")), h("dd", {}, [row.agent_kind, row.model].filter(Boolean).join(" · ")),
      h("dt", {}, "Provenance"), h("dd", {}, t("provenance_" + row.provenance)),
      h("dt", {}, t("observed")), h("dd", {}, when(row.observed_at))));
  if (from) {
    head.append(h("p", { class: "note" }, t("started_from", { commit: from.commit_sha.slice(0, 12) }), " ",
      h("a", { href: `#/session/${encodeURIComponent(from.source_host)}/${encodeURIComponent(from.source_session_id)}` },
        t("source_session")), " · ", h("a", { href: `#/op/${from.operation_id}` }, from.operation_id)));
  }
  if (linked?.length) head.append(linkedItems(linked));
  const scope = `send.${host}.${sid}`;
  const cps = checkpointPanel(host, sid);
  main.insertBefore(cps.box, msgs.previousSibling);
  if (row.api_access !== "managed") {
    controls.replaceChildren(h("p", { class: "note" }, t("read_only_note")));
  } else {
    const box = h("textarea", { placeholder: t("send_placeholder") });
    try { box.value = localStorage.getItem(`batc.draft.${scope}`) || ""; } catch { /* ignore */ }
    box.oninput = () => { try { localStorage.setItem(`batc.draft.${scope}`, box.value); } catch { /* ignore */ } };
    const status = h("div", { class: "muted" });
    // BAT refuses a direct send while a turn runs; queueing puts the message behind it instead.
    const queue = h("input", { type: "checkbox", checked: row.streaming });
    const send = h("button", { class: "primary", onclick: async () => {
      if (!box.value.trim()) return;
      send.disabled = true;
      try {
        const op = await submit("session.send", { host, session_id: sid }, { text: box.value, queue: queue.checked }, {},
          scope);
        status.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
        if (op.status === "succeeded") { box.value = ""; try { localStorage.removeItem(`batc.draft.${scope}`); } catch { /* ignore */ } }
      } catch (e) { status.replaceChildren(errorBox(e)); }
      send.disabled = false;
    } }, t("send"));
    const stop = h("button", { class: "danger", onclick: async () => {
      try {
        const op = await submit("session.interrupt", { host, session_id: sid }, { mode: "soft" }, {}, `interrupt.${host}.${sid}`);
        status.replaceChildren(opStatus(op));
      } catch (e) { status.replaceChildren(errorBox(e)); }
    } }, t("interrupt"));
    controls.replaceChildren(box, h("div", { class: "actions" }, send, stop,
      h("label", { class: "muted" }, queue, " ", t("queue_behind"))), status);
    if (row.pending) {
      const pend = row.pending;
      const answerScope = `answer.${host}.${sid}.${pend.toolUseId || ""}`;
      const answer = async params => {
        try { status.replaceChildren(opStatus(await submit("session.answer", { host, session_id: sid },
          { ...params, tool_use_id: pend.toolUseId }, {}, answerScope))); }
        catch (e) { status.replaceChildren(errorBox(e)); }
      };
      const pendingBox = h("div", { class: "panel" }, h("div", { class: "title" }, t("pending_" + pend.kind)));
      if (pend.kind === "permission") {
        pendingBox.append(h("p", {}, h("code", {}, pend.toolName || "")), h("p", { class: "msg" }, pend.input_preview || ""),
          h("div", { class: "actions" },
            h("button", { class: "primary", onclick: () => answer({ permission: "allow" }) }, t("allow")),
            h("button", { class: "danger", onclick: () => answer({ permission: "deny" }) }, t("deny"))));
      } else {
        // One field per question; options become a picker, free text stays possible.
        const fields = (pend.questions || []).map(q => {
          const input = h("input", { placeholder: t("answer") });
          const picks = (q.options || []).map(o => h("button", { class: "secondary", onclick: () => { input.value = o; } }, o));
          pendingBox.append(h("p", {}, q.header ? h("strong", {}, `${q.header} · `) : null, q.question),
            picks.length ? h("div", { class: "actions" }, ...picks) : null, h("div", { class: "actions" }, input));
          return input;
        });
        pendingBox.append(h("div", { class: "actions" }, h("button", { class: "primary",
          onclick: () => answer({ answers: fields.map(f => f.value) }) }, t("answer"))));
      }
      controls.prepend(pendingBox);
    }
  }
  const loadMessages = async () => {
    try {
      const read = await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}/messages?last_n=30`);
      const items = read.messages.map(m => h("div", { class: `msg ${m.role === "user" ? "user" : ""}` },
        h("span", { class: "who" }, `${m.role || ""} · ${when(m.ts)}`), m.text || ""));
      msgs.replaceChildren(...(items.length ? items : [h("p", { class: "muted" }, t("no_messages"))]));
    } catch (e) { msgs.replaceChildren(errorBox(e)); }
  };
  await Promise.all([loadMessages(), cps.load()]);
  const reload = debounce(loadMessages, 800);
  const reloadCps = debounce(cps.load, 800);
  return onEvents(ev => {
    if (ev.resource_id === `${host}/${sid}`) reload();
    if (ev.resource_type === "checkpoint") reloadCps();
  });
}

// A checkpoint records this session's commit and recent conversation (read-only); continuing starts a new
// managed session at that commit in a connector clone. The person's session and folder are never written.
function checkpointPanel(host, sid) {
  const can = (state.caps?.features?.checkpoints || []).includes(host);
  const mayStart = (state.caps?.scopes || []).includes("start"); // continuing starts an agent: its own grant
  const list = h("div", {});
  const status = h("div", { class: "muted" });
  // A checkpoint never changes, so its row is built once: a reload on a new event keeps an open form and its draft.
  const rows = new Map();
  let preview = null; // what the source looks like now (read-only): the commit picker and "source moved on"
  const row = cp => rows.get(cp.checkpoint_id) || rows.set(cp.checkpoint_id, buildRow(cp)).get(cp.checkpoint_id);
  const buildRow = cp => {
    const instr = h("textarea", { placeholder: t("continue_placeholder") });
    const agent = h("select", {}, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
    const out = h("div", { class: "muted" });
    const go = h("button", { class: "primary", onclick: async () => {
      if (!instr.value.trim()) return;
      go.disabled = true;
      try {
        const op = await submit("checkpoint.continue", { checkpoint_id: cp.checkpoint_id },
          { instructions: instr.value, agent: agent.value }, {}, `continue.${cp.checkpoint_id}`);
        out.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
      } catch (e) { out.replaceChildren(errorBox(e)); }
      go.disabled = false;
    } }, t("start_agent_work"));
    const form = h("div", { hidden: true }, h("p", { class: "muted" }, t("confined_note")), instr,
      h("div", { class: "actions" }, agent, go), out);
    return h("div", { class: "row" },
      h("div", { class: "grow" },
        h("div", { class: "title" }, h("code", {}, cp.commit_sha.slice(0, 12)), " ", cp.branch || ""),
        h("div", { class: "muted" }, [when(epoch(cp.captured_at)), cp.actor,
          t("excerpt_count", { n: cp.excerpt_messages })].join(" · ")),
        cp.dirty ? h("div", { class: "error" }, t("dirty_warning", { n: cp.dirty }))
          : cp.dirty === null ? h("div", { class: "muted" }, t("dirty_unknown")) : null,
        preview && preview.head !== cp.commit_sha ? h("div", { class: "muted" }, t("source_advanced")) : null, form),
      h("button", { class: "secondary", disabled: !can || !mayStart,
        title: !can ? t("checkpoint_unavailable") : mayStart ? null : t("needs_start_scope"),
        onclick: () => { form.hidden = !form.hidden; } }, t("continue_from_checkpoint")));
  };
  const load = async () => {
    try {
      const p = new URLSearchParams({ host, session_id: sid, limit: "10" });
      const page = await api("GET", `/checkpoints?${p}`);
      list.replaceChildren(...(page.checkpoints.length ? page.checkpoints.map(row)
        : [h("p", { class: "muted" }, t("no_checkpoints"))]));
    } catch (e) { list.replaceChildren(errorBox(e)); }
  };
  const pick = h("select", { "aria-label": t("commit"), hidden: true });
  const note = h("textarea", { placeholder: t("checkpoint_note_placeholder"), hidden: true });
  const loadPreview = async () => {
    try {
      preview = (await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}/checkpoint-preview`)).preview;
      pick.replaceChildren(...preview.commits.map(c => h("option", { value: c.hash }, `${c.hash.slice(0, 10)} · ${c.message}`)));
      pick.hidden = note.hidden = false;
      if (preview.dirty) status.replaceChildren(h("span", { class: "error" }, t("dirty_warning", { n: preview.dirty })));
    } catch { preview = null; } // no preview: the button records HEAD, as before
  };
  const create = h("button", { class: "secondary", onclick: async () => {
    create.disabled = true;
    try {
      const params = { last_n: 20, ...(preview ? { commit: pick.value } : {}), ...(note.value.trim() ? { note: note.value.trim() } : {}) };
      const op = await submit("checkpoint.create", { host, session_id: sid }, params, {}, `checkpoint.${host}.${sid}`);
      if (op.status === "succeeded") note.value = "";
      status.replaceChildren(...[opStatus(op), op.error_code ? chip(op.error_code, "bad") : null,
        op.status_reason].filter(Boolean).flatMap(x => [x, " "]));
      await load();
    } catch (e) { status.replaceChildren(errorBox(e)); }
    create.disabled = false;
  } }, t("create_checkpoint"));
  const box = h("div", { class: "panel" }, h("h2", {}, t("checkpoints")), h("p", { class: "muted" }, t("checkpoint_help")),
    can ? null : h("p", { class: "muted" }, t("checkpoint_unavailable")),
    can && !mayStart ? h("p", { class: "muted" }, t("needs_start_scope")) : null, note,
    h("div", { class: "actions" }, pick, create), status, list);
  return { box, load: async () => { await loadPreview(); await load(); } };
}

async function viewDelivery(main) {
  freshPage();
  const repo = h("input", { placeholder: "owner/name", value: sessionStorage.getItem("batc.repo") || "" });
  const num = h("input", { placeholder: "123", inputmode: "numeric", size: 6, value: sessionStorage.getItem("batc.pr") || "" });
  const card = h("div", { class: "panel delivery-card" });
  const groups = new Map();
  for (const r of state.caps?.deploy_recipes || []) {
    const key = JSON.stringify([r.repository.toLowerCase(), r.environment]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  const environments = [...groups.values()].map(environmentCard);
  main.append(h("h1", {}, t("nav_delivery")), ...environments.map(e => e.card));
  let selectedMethod = "";
  let reviewedPreview = null;
  main.append(h("h2", {}, t("dep_pull_request")),
    h("div", { class: "filters delivery-controls" }, repo, num,
      h("button", { class: "secondary", onclick: () => load() }, t("load_pr"))), card);
  if (!repo.value && state.caps?.repositories?.length) repo.value = state.caps.repositories[0].repository;
  const load = async (flash = null, fromEvent = false) => {
    const opens = drawerOpens;
    // Explicit PR loads only replace this card; another environment's open panel cannot hold them.
    const holdCard = () => card.querySelector(".drawer:not([hidden])") || (fromEvent && holdRender(true, opens));
    sessionStorage.setItem("batc.repo", repo.value); sessionStorage.setItem("batc.pr", num.value);
    if (!repo.value || !/^\d+$/.test(num.value)) return;
    try {
      const query = new URLSearchParams();
      if (selectedMethod) query.set("method", selectedMethod);
      if (fromEvent) query.set("from_event", "true");
      const pr = (await api("GET", `/repositories/${repo.value}/pulls/${num.value}?${query}`)).pull_request;
      if (holdCard()) { idleReload = () => load(null, true); return; }
      const status = h("div", { "aria-live": "polite" });
      const target = { repository: pr.repository, pull_number: Number(pr.pull_number) };
      if (!fromEvent || !reviewedPreview) reviewedPreview = pr.merge_preview;
      const pv = reviewedPreview;
      const scopeChanged = pr.merge_preview.digest !== pv.digest;
      const pre = { expected_head_sha: pv.target.head_sha, expected_base_sha: pv.target.base_sha, preview_digest: pv.digest };
      const params = { method: pv.method, preview_id: pv.preview_id };
      const run = async (action, extra, scope) => {
        try {
          const op = await submit(action, { ...target, ...extra.target }, extra.params || params, extra.pre ?? pre, scope);
          const receipt = op.result?.merge || op.result || op.external_refs?.merge_receipt;
          fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id),
            receipt?.base_moved ? h("p", { class: "note warn" }, t("merged_newer_base", { count: receipt.other_commits_count })) : null);
        } catch (e) { fill(status, errorBox(e)); }
      };
      const blocked = pr.state !== "open" || pr.draft || pr.merged || pv.blocking.length > 0 || scopeChanged;
      const method = h("select", { "aria-label": t("merge_method"), onchange: () => { selectedMethod = method.value; load(); } },
        ...pr.merge.methods.map(m => h("option", { value: m, selected: m === pv.method }, m)));
      const buttons = [h("button", { class: "primary", "data-testid": "merge-submit",
        disabled: blocked || !pr.merge.allowed || !may("merge"),
        onclick: () => run("github.pr.merge", {}, `merge.${pv.preview_id}`) }, t("merge"))];
      for (const r of pr.recipes) {
        buttons.push(h("button", { class: "secondary", disabled: blocked || !pr.merge.allowed || !may("merge") || !may("deploy") || !state.caps?.deploy_recipes?.find(c => c.name === r.name)?.readiness?.ready,
          onclick: async () => {
            try {
              const deploymentPreview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(r.name)}`)).preview;
              await run("delivery.merge_and_deploy", { target: { recipe: r.name }, pre: { ...pre, ...deploymentPreview.preconditions } }, `merge_deploy.${pv.preview_id}.${r.name}`);
            } catch (e) { fill(status, errorBox(e)); }
          } },
        t("merge_and_deploy_to", { env: r.environment })));
        if (pr.merged && pr.merge_commit_sha) buttons.push(h("button", { class: "secondary", disabled: !may("deploy") || !state.caps?.deploy_recipes?.find(c => c.name === r.name)?.readiness?.ready,
          onclick: async () => {
            try {
              const deploymentPreview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(r.name)}`)).preview;
              const op = await submit("deployment.start", { recipe: r.name }, { source_sha: pr.merge_commit_sha }, deploymentPreview.preconditions, `deploy.${r.name}.${pr.merge_commit_sha}`);
              fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
            } catch (e) { fill(status, errorBox(e)); }
          } }, t("deploy_to", { env: r.environment })));
      }
      const commitList = h("details", { class: "row-details" }, h("summary", {}, t("merge_commit_range", { count: pv.commits.length })),
        h("ul", {}, ...pv.commits.map(c => h("li", {}, h("code", {}, c.sha), " ", c.message))));
      const affected = pv.affected_prs.map(p => h("div", { class: "row" },
        h("div", { class: "grow" }, h("a", { href: p.html_url, target: "_blank", rel: "noopener" }, `#${p.number} ${p.title || ""}`),
          " · ", t("scope_" + p.reason), h("div", {}, h("code", {}, p.head_sha || ""))),
        chip(t(p.effect === "branch_rebase" ? "scope_stack_rebase" : p.effect === "dependency" ? "scope_dependency" : p.would_merge ? "scope_would_merge" : "scope_candidate"), p.would_merge ? "warn" : "")));
      fill(card,
        h("h2", {}, h("a", { href: pr.html_url, target: "_blank", rel: "noopener" }, `#${pr.pull_number} ${pr.title || ""}`)),
        h("dl", { class: "kv" },
          h("dt", {}, t("head")), h("dd", {}, h("code", {}, `${pr.head_ref} @ ${pr.head_sha}`)),
          h("dt", {}, t("base")), h("dd", {}, h("code", {}, `${pr.base_ref} @ ${pr.base_sha}`)),
          h("dt", {}, t("mergeable")), h("dd", {}, `${pr.state}${pr.draft ? " · draft" : ""} · ${pr.mergeable_state || "?"}`),
          h("dt", {}, t("checks")), h("dd", {}, t("checks_summary", pr.checks)),
          pr.merged ? [h("dt", {}, t("merged_sha")), h("dd", {}, h("code", {}, pr.merge_commit_sha))] : null),
        metadataDrawer(pr, load),
        scopeChanged ? h("p", { class: "note warn" }, t("merge_scope_reload")) : null,
        h("h2", {}, t("merge_scope")), h("label", {}, t("merge_method"), " ", method),
        h("p", { class: "muted" }, t("merge_preview_fixed"), " ", h("code", {}, pv.preview_id)), commitList,
        affected.length ? h("div", {}, ...affected) : h("p", { class: "muted" }, t("scope_single_pr")),
        ...pv.blocking.map(b => h("p", { class: "note warn" }, h("code", {}, b.code), " · ", b.message)),
        ...pv.warnings.map(w => h("p", { class: "muted" }, w)),
        h("div", { class: "actions" }, ...buttons), status, flash instanceof Node ? flash : null,
        pr.integration?.allowed ? integrationPanel(pr, load) : null);
    } catch (e) { if (!holdCard()) fill(card, errorBox(e)); }
  };
  const reload = async (fromEvent = true) => { await Promise.all(environments.map(e => e.load(fromEvent))); await load(null, fromEvent); };
  await reload(false);
  return liveReload(reload, ["operation", "integration", "deployment", "deployment_environment"]);
}

function deploymentIdentity(identity, empty = "dep_no_version") {
  if (!identity?.source_sha && !identity?.artifact_id) return h("p", { class: "muted" }, t(empty));
  return h("div", { class: "deployment-identity" },
    identity.source_sha ? h("code", {}, identity.source_sha) : null,
    identity.artifact_id ? h("p", {}, t("dep_artifact", { id: identity.artifact_id }),
      identity.artifact_digest ? [" · ", h("code", {}, identity.artifact_digest)] : null) : null);
}
function deploymentState(value) {
  return chip(t(`dep_state_${value || "unverified"}`), ["failed", "needs_attention", "uncertain"].includes(value) ? "bad"
    : value === "succeeded" ? "ok" : "warn");
}
function deploymentTime(value) { return value ? when(Number(value) * 1000) : t("dep_not_observed"); }
function heldDetails(title, children, onOpen) {
  let counted = false;
  const details = h("details", { class: "row-details", ontoggle: () => {
    if (details.open !== counted) {
      counted = details.open;
      if (counted) { drawerOpens += 1; if (onOpen) onOpen(); }
      setEditing(editing + (counted ? 1 : -1));
    }
  } }, h("summary", {}, title), ...children);
  details.closeHeld = () => {
    if (counted) { counted = false; setEditing(editing - 1); }
    details.open = false;
  };
  return details;
}
function deploymentReceipt(dep) {
  const body = h("div", {});
  let read = false;
  const details = heldDetails(t("dep_operation_details"), [body], async () => {
    if (read) return;
    read = true;
    try {
      const op = (await api("GET", `/operations/${dep.operation_id}`)).operation;
      const saved = op.external_refs?.deployment_id && op.external_refs.deployment_id !== dep.deployment_id
        ? (await api("GET", `/deployments/${op.external_refs.deployment_id}`)).deployment : dep;
      const values = [[t("dep_operation"), h("a", { href: `#/op/${op.operation_id}` }, op.operation_id)],
        [t("dep_status"), opStatus(op)], [t("dep_run"), saved.run_id], [t("dep_attempt"), saved.run_attempt],
        [t("dep_error_code"), op.error_code || saved.error_code || saved.reconciliation_error]];
      fill(body, h("dl", { class: "kv" }, ...values.filter(([, v]) => v !== null && v !== undefined && v !== "")
        .flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, value)])),
        op.status_reason ? h("p", {}, op.status_reason) : null,
        ...(op.steps || []).map(s => h("div", { class: "row" }, h("code", {}, s.name), h("code", {}, s.status))));
    } catch (e) { fill(body, errorBox(e)); read = false; }
  });
  return details;
}
function deploymentLimits(limits) {
  return h("div", { class: "deployment-limits" }, h("span", { class: "muted" }, t("dep_not_undone")),
    limits?.length ? h("ul", {}, ...limits.map(value => h("li", {}, value))) : h("p", { class: "muted" }, t("dep_no_limits")));
}
function deploymentPreviewSummary(preview) {
  return h("p", { class: "muted", "data-testid": "deployment-preview-generation" },
    t("dep_preview_generation", { env: preview.environment, generation: preview.environment_generation }));
}
function deploymentIntent(dep, kind, reload) {
  const out = h("div", { "aria-live": "polite" });
  const d = drawer();
  let busy = false, accepted = false, preview = null;
  const scope = `deployment.${kind}.${dep.deployment_id}`;
  const confirm = h("button", { class: kind === "rollback" ? "danger" : "primary", disabled: true,
    "data-testid": `deployment-${kind}-confirm`, onclick: async () => {
      if (busy || accepted || !preview) return;
      busy = true; confirm.disabled = true;
      try {
        const action = kind === "rollback" ? "deployment.rollback" : "deployment.start";
        const params = kind === "rollback" ? { deployment_id: dep.deployment_id }
          : { source_sha: dep.identity.source_sha, retry_of: dep.deployment_id };
        let op = await submit(action, { recipe: dep.recipe }, params, preview.preconditions, scope);
        while (["accepted", "running"].includes(op.status) && d.box.isConnected && !d.box.hidden) {
          await sleep(1000);
          op = (await api("GET", `/operations/${op.operation_id}`)).operation;
        }
        if (["DEPLOY_PREVIEW_REQUIRED", "ENVIRONMENT_CHANGED", "RECIPE_CHANGED"].includes(op.error_code)) {
          fill(out, h("p", { class: "note warn" }, t("dep_stale_preview")), deploymentReceipt({ operation_id: op.operation_id }));
          await refreshPreview();
        } else {
          accepted = true;
          fill(out, h("p", {}, opStatus(op), " · ", h("a", { href: `#/op/${op.operation_id}` }, t("dep_open_operation"))),
            deploymentReceipt({ operation_id: op.operation_id }));
        }
      } catch (e) {
        fill(out, h("p", { class: "error" }, t("dep_refused")), heldDetails(t("dep_operation_details"), [errorBox(e)]));
        if (["DEPLOY_PREVIEW_REQUIRED", "ENVIRONMENT_CHANGED", "RECIPE_CHANGED"].includes(e.code)) {
          out.prepend(h("p", { class: "note warn" }, t("dep_stale_preview")));
          await refreshPreview();
        }
      } finally { busy = false; confirm.disabled = accepted || !preview?.readiness?.ready; }
    } }, t(kind === "rollback" ? "dep_confirm_rollback" : "dep_confirm_retry"));
  const previewBox = h("div", {});
  async function refreshPreview() {
    preview = null;
    confirm.disabled = true;
    try {
      preview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(dep.recipe)}`)).preview;
      fill(previewBox, deploymentPreviewSummary(preview),
        preview.readiness?.ready ? null : h("p", { class: "note warn" }, t("dep_missing_verification")));
      confirm.disabled = busy || accepted || !preview.readiness?.ready;
    } catch (e) { fill(previewBox, errorBox(e)); }
  }
  fill(d.box, h("h3", {}, t(kind === "rollback" ? "dep_rollback_review" : "dep_retry_review")),
    deploymentIdentity(dep.identity), h("p", {}, `${dep.repository} · ${dep.environment}`),
    kind === "rollback" ? deploymentLimits(dep.rollback?.not_undone) : h("p", { class: "muted" }, t("dep_retry_only")),
    previewBox, out, h("div", { class: "actions" }, confirm,
      h("button", { class: "secondary", onclick: () => {
        d.box.querySelectorAll("details[open]").forEach(el => el.closeHeld?.());
        d.close(); reload();
      } }, t("close"))));
  const button = h("button", { class: "secondary", "data-testid": `deployment-${kind}`, onclick: () => {
    if (!d.box.hidden) return;
    d.open(); refreshPreview();
  } }, t(kind === "rollback" ? "dep_rollback" : "dep_retry", { sha: (dep.identity?.source_sha || "").slice(0, 8) }));
  return { button, box: d.box };
}
function deploymentRecord(dep, env, reload, compact = false) {
  if (!dep) return h("p", { class: "muted" }, t("dep_no_version"));
  const r = (state.caps?.deploy_recipes || []).find(r => r.name === dep.recipe);
  dep = { ...dep, repository: dep.repository || r?.repository || "",
    environment: dep.environment || r?.environment || env.environment || t("dep_no_version") };
  const canDeploy = Boolean(state.caps?.features?.deploy && r?.readiness?.ready
    && (state.caps?.actions || []).some(a => a.action === "deployment.start" && a.allowed) && may("deploy"));
  const disabledReason = !may("deploy") ? "dep_needs_scope" : !r ? "dep_missing_recipe"
    : !r.readiness?.ready ? "dep_missing_verification" : "dep_disabled";
  const actions = [], drawers = [];
  if (!compact && dep.rollback_eligible && !dep.is_current) {
    const intent = deploymentIntent(dep, "rollback", reload);
    intent.button.disabled = !canDeploy || !(state.caps?.actions || []).some(a => a.action === "deployment.rollback" && a.allowed);
    actions.push(intent.button); drawers.push(intent.box);
    if (intent.button.disabled) actions.push(h("span", { class: "muted" }, t(disabledReason)));
  }
  if (!compact && dep.state === "failed") {
    if (dep.provider_terminal && !dep.legacy && dep.identity?.source_sha) {
      const intent = deploymentIntent(dep, "retry", reload);
      intent.button.disabled = !canDeploy;
      actions.push(intent.button); drawers.push(intent.box);
      if (!canDeploy) actions.push(h("span", { class: "muted" }, t(disabledReason)));
    } else actions.push(h("span", { class: "muted" }, t(dep.provider_terminal ? "dep_retry_unavailable" : "dep_provider_pending")));
  }
  let rollbackReason = dep.rollback_reason;
  let providerUrl = null;
  try {
    const url = new URL(dep.provider_url);
    if (url.protocol === "https:") providerUrl = url.href;
  } catch { /* malformed and relative provider links are not navigable */ }
  if (rollbackReason === "ROLLBACK_ARTIFACT_UNAVAILABLE" && dep.identity?.artifact_expires_at
      && Date.parse(dep.identity.artifact_expires_at) <= Date.now()) rollbackReason = "ROLLBACK_ARTIFACT_EXPIRED";
  return h("div", { class: "deployment-record", "data-deployment": dep.deployment_id },
    h("div", { class: "deployment-record-heading" }, deploymentState(dep.state), h("span", { class: "muted" }, dep.recipe)),
    deploymentIdentity(dep.identity),
    compact ? h("p", {}, h("a", { href: `#/op/${dep.operation_id}` }, t("dep_open_operation")))
      : h("p", { class: "muted" }, `${dep.environment} · ${deploymentTime(dep.created_at)}`),
    dep.state === "superseded" ? h("p", {}, t("dep_superseded"), " ",
      env.desired ? h("a", { href: `#/op/${env.desired.operation_id}` }, t("dep_new_desired")) : null, " · ",
      providerUrl ? h("a", { href: providerUrl, target: "_blank", rel: "noopener" }, t("dep_provider_run")) : null) : null,
    (dep.state === "needs_attention" || dep.reconciliation_error) ? h("p", { class: "note warn" }, t("dep_attention")) : null,
    !compact && rollbackReason ? h("p", { class: "muted" }, t(`dep_${rollbackReason}`)) : null,
    !compact && dep.rollback_eligible && !dep.is_current ? deploymentLimits(dep.rollback?.not_undone) : null,
    actions.length ? h("div", { class: "actions" }, ...actions) : null,
    deploymentReceipt(dep), ...drawers);
}
function environmentCard(group) {
  const card = h("section", { class: "panel delivery-card environment-card", "data-environment": group[0].environment });
  const cursors = [null];
  let page = 0, next = null, loading = false;
  async function load(fromEvent = false) {
    const opens = drawerOpens;
    if (editing || (fromEvent && typing())) { idleReload = () => load(true); return; }
    if (loading) return;
    loading = true;
    try {
      const query = new URLSearchParams({ recipe: group[0].name, limit: "5" });
      if (cursors[page]) query.set("cursor", cursors[page]);
      const [environment, history] = await Promise.all([
        api("GET", `/deployment-environments?recipe=${encodeURIComponent(group[0].name)}`),
        api("GET", `/deployment-environments/history?${query}`)]);
      if (holdRender(fromEvent, opens) || editing) { idleReload = () => load(true); return; }
      const env = environment.environment;
      next = history.next_cursor;
      const observed = env.observed || env.current?.evidence?.runtime?.observed;
      const needs = env.attention || env.desired?.state === "needs_attention" || env.desired?.reconciliation_error
        || env.current?.state === "needs_attention" || env.current?.reconciliation_error;
      const previous = h("button", { class: "secondary", disabled: page === 0, "data-testid": "history-previous",
        onclick: () => { if (loading) return; previous.disabled = more.disabled = true; page -= 1; load(); } }, t("dep_previous"));
      const more = h("button", { class: "secondary", disabled: !next, "data-testid": "history-next",
        onclick: () => { if (loading) return; previous.disabled = more.disabled = true; cursors[++page] = next; load(); } }, t("dep_next"));
      const verified = env.last_verified;
      fill(card, h("div", { class: "deployment-card-heading" }, h("h2", {}, group[0].environment),
        needs ? chip(t("dep_attention"), "warn") : null), h("p", { class: "muted" }, group[0].repository, " · ", t("dep_generation", { generation: env.desired_generation })),
        needs ? h("p", { class: "note warn" }, t(env.attention === "ENVIRONMENT_VERSION_DRIFT" ? "dep_drift" : "dep_attention_help")) : null,
        h("div", { class: "deployment-versions" },
          h("div", {}, h("h3", {}, t("dep_desired")), deploymentRecord(env.desired, env, load, true)),
          h("div", {}, h("h3", {}, t("dep_observed")), deploymentIdentity(observed),
            h("p", { class: "muted" }, t("dep_observed_at", { time: deploymentTime(observed?.observed_at || env.current?.evidence?.runtime?.checked_at) })),
            env.current?.evidence?.runtime?.summary ? h("p", { class: "muted" }, runtimeSummary(env.current.evidence.runtime)) : null)),
        h("div", { class: "deployment-last-verified" }, h("h3", {}, t("dep_last_verified")), deploymentIdentity(verified?.identity),
          h("p", { class: "muted" }, t("dep_verified_at", { time: deploymentTime(verified?.evidence?.runtime?.checked_at) })),
          verified?.evidence?.runtime?.summary ? h("p", { class: "muted" }, runtimeSummary(verified.evidence.runtime)) : null,
          verified ? deploymentReceipt(verified) : null),
        h("h3", {}, t("dep_history")), h("div", { "data-testid": "deployment-history" },
          ...(history.items.length ? history.items.map(dep => deploymentRecord(dep, env, load)) : [h("p", { class: "muted" }, t("dep_no_history"))])),
        !history.items.length && group.every(r => !r.rollback?.supported) ? h("p", { class: "muted" }, t("dep_ROLLBACK_UNSUPPORTED")) : null,
        h("div", { class: "actions deployment-pagination" }, previous, h("span", { class: "muted" }, t("dep_page", { page: page + 1 })), more));
    } catch (e) { if (!holdRender(fromEvent, opens) && !editing) fill(card, errorBox(e)); }
    finally { loading = false; }
  }
  return { card, load };
}
function runtimeSummary(evidence) {
  return t(evidence.version_checked ? evidence.health_checked ? "dep_version_health" : "dep_version_only" : "dep_health_only");
}

function metadataDrawer(pr, reload) {
  const title = h("input", { value: pr.title || "", "data-testid": "metadata-title" });
  const body = h("textarea", { "data-testid": "metadata-body" }, pr.body || "");
  const initialBody = body.value; // textarea normalizes CRLF; an untouched body must still be omitted
  const out = h("div", { "aria-live": "polite" });
  let d;
  const save = h("button", { class: "primary", "data-testid": "metadata-save", onclick: async () => {
    const params = {};
    if (title.value !== (pr.title || "")) params.title = title.value;
    if (body.value !== initialBody) params.body = body.value;
    if (!Object.keys(params).length) return;
    save.disabled = true;
    try {
      const op = await submit("github.pr.update", { repository: pr.repository, pull_number: pr.pull_number }, params,
        { expected_metadata_digest: pr.metadata_digest }, `pr_metadata.${pr.repository}.${pr.pull_number}.${pr.metadata_digest}`);
      const diff = op.external_refs?.metadata_difference;
      const contents = diff ? h("details", { class: "row-details", open: true }, h("summary", {}, t("metadata_diff")),
        ...[["metadata_before", diff.observed ? diff.before : { title: pr.title, body: pr.body }],
          ["metadata_intended", diff.after || diff.intended], ["metadata_observed", diff.observed || diff.before]]
          .map(([label, value]) => h("div", {}, h("strong", {}, t(label)), h("pre", { class: "pre" }, JSON.stringify(value, null, 2))))) : null;
      fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id),
        op.error_code ? chip(op.error_code, "bad") : null, contents,
        h("p", { class: "muted" }, t("metadata_result_help")));
      idleReload = () => reload();
    } catch (e) { fill(out, errorBox(e)); save.disabled = false; }
  } }, t("save"));
  const close = h("button", { class: "secondary", "data-testid": "metadata-close", onclick: () => d.close() }, t("close"));
  d = drawer(h("label", {}, t("metadata_title"), title), h("label", {}, t("description"), body),
    h("p", { class: "muted" }, t("metadata_race_limit")), h("div", { class: "actions" }, save, close), out);
  return h("div", {}, h("button", { class: "secondary", "data-testid": "metadata-edit",
    disabled: !pr.metadata_update.allowed || !may("integrate"),
    title: !may("integrate") ? t("needs_integrate_scope") : !pr.metadata_update.allowed ? t("metadata_disabled") : null,
    onclick: () => d.open() }, t("metadata_edit")), d.box);
}

// "Update PR results": put chosen results into this PR's head branch with one normal push (never forced; the
// person's folders are never touched). Sources come only from a preview that lists every commit that would enter.
function integrationPanel(pr, reloadCard) {
  const box = h("div", { class: "panel" });
  const may = (state.caps?.scopes || []).includes("integrate");
  const hosts = pr.integration.hosts;
  box.append(h("h2", {}, t("update_pr_results")), h("p", { class: "muted" }, t("update_pr_help")));
  if (!may) { box.append(h("p", { class: "note" }, t("needs_integrate_scope"))); return box; }
  if (!hosts.length) { box.append(h("p", { class: "note" }, t("integration_no_host"))); return box; }
  const target = { host: hosts[0], repository: pr.repository, pull_number: Number(pr.pull_number) };
  const selected = []; // [{kind, id, label}] in order
  const pickList = h("div", {});
  const order = h("div", {});
  const previewBox = h("div", {});
  const status = h("div", {});
  let doc = null;
  let generation = 0;
  const rerender = () => {
    order.replaceChildren(...selected.map((s, i) => h("div", { class: "row" },
      h("div", { class: "grow" }, `${i + 1}. `, chip(t("kind_" + s.kind)), " ", h("code", {}, s.label)),
      h("button", { class: "secondary", disabled: i === 0, onclick: () => { selected.splice(i - 1, 0, selected.splice(i, 1)[0]); changed(); } }, "↑"),
      h("button", { class: "secondary", disabled: i === selected.length - 1, onclick: () => { selected.splice(i + 1, 0, selected.splice(i, 1)[0]); changed(); } }, "↓"),
      h("button", { class: "secondary", onclick: () => { selected.splice(i, 1); changed(); } }, "×"))));
  };
  const freshHead = async () => { // the card's head is stale after the PR moved: re-read it before previewing again
    try { pr.head_sha = (await api("GET", `/repositories/${pr.repository}/pulls/${pr.pull_number}`)).pull_request.head_sha; }
    catch { /* the preview then reports the real head */ }
  };
  const runPreview = async () => {
    const mine = ++generation;
    doc = null;
    if (!selected.length) { previewBox.replaceChildren(); return; }
    previewBox.replaceChildren(h("p", { class: "muted" }, t("previewing")));
    try {
      let op = await submit("integration.preview", target, { sources: selected.map(({ kind, id }) => ({ kind, id })) },
        { expected_head_sha: pr.head_sha }, `preview.${pr.repository}.${pr.pull_number}`);
      while (!TERMINAL.includes(op.status) && op.status !== "needs_attention" && box.isConnected && mine === generation) {
        await sleep(1000);
        op = (await api("GET", `/operations/${op.operation_id}`)).operation;
      }
      if (mine !== generation || !box.isConnected) return;
      if (op.status !== "succeeded") {
        previewBox.replaceChildren(h("p", { class: "error" }, `${op.error_code || op.status} ${op.status_reason || ""}`));
        return;
      }
      doc = op.result;
      renderPreview();
    } catch (e) { if (mine === generation) previewBox.replaceChildren(errorBox(e)); }
  };
  const changed = debounce(() => { rerender(); runPreview(); }, 600);
  const add = (kind, id, label) => {
    if (!selected.some(s => s.kind === kind && s.id === id)) selected.push({ kind, id, label });
    changed();
  };
  const plain = w => h("li", {}, w.text);
  const renderPreview = () => {
    const expired = Date.now() / 1000 > doc.expires_at || doc.target.head_sha !== pr.head_sha;
    const conflictAt = doc.sources.find(s => s.predicted === "conflict");
    const go = h("button", { class: "primary", disabled: !doc.ready || expired, onclick: async () => {
      go.disabled = true;
      try {
        const req = { action: "integration.apply", target, params: { preview_id: doc.preview_id },
          preconditions: { expected_head_sha: doc.target.head_sha, preview_digest: doc.digest } };
        follow((await api("POST", "/operations?wait=3", req, "integrate." + doc.preview_id)).operation);
      } catch (e) { status.replaceChildren(errorBox(e)); go.disabled = false; }
    } }, conflictAt ? t("start_integration_conflict", { n: conflictAt.seq }) : t("update_pr_results"));
    previewBox.replaceChildren(...[
      h("p", {}, h("code", {}, `${doc.repository} #${doc.pull_number} · ${doc.target.head_ref} @ ${doc.target.head_sha.slice(0, 12)}`),
        " → ", t("normal_push"), " · ", t("push_access_" + doc.target.push_access)),
      ...doc.sources.map(s => h("details", { class: "row-details" },
        h("summary", {}, `${s.seq}. `, chip(t("plan_" + (s.predicted || "not_predicted")), s.predicted === "conflict" ? "bad" : ""),
          " ", h("code", {}, s.label), " · ", t("n_commits", { n: s.commits_total }), " · ", t("n_files", { n: s.files_total }),
          s.conflict_files.length ? h("span", { class: "error" }, " · ", s.conflict_files.join(", ")) : null),
        h("ul", {}, ...s.commits.map(c => h("li", {}, h("code", {}, c.sha.slice(0, 10)), ` ${c.subject} — ${c.author}`,
          c.origin === "foreign" ? h("span", { class: "error" }, " · ", t("foreign_commit")) : null))),
        s.warnings.length ? h("ul", { class: "muted" }, ...s.warnings.map(plain)) : null)),
      doc.overlaps.length ? h("p", { class: "muted" }, t("overlapping_files"), " ",
        doc.overlaps.map(o => `${o.path} (${o.seqs.join(", ")}${o.also_changed_on_pr ? ", PR" : ""})`).join("; ")) : null,
      doc.blocking.length ? h("ul", { class: "error" }, ...doc.blocking.map(plain)) : null,
      doc.warnings.length ? h("ul", { class: "muted" }, ...doc.warnings.map(plain)) : null,
      h("p", { class: "muted" }, expired ? t("preview_expired") : t("previewed_at", { time: when(epoch(doc.observed_at)) }),
        " ", h("a", { href: "#", onclick: ev => { ev.preventDefault(); runPreview(); } }, t("preview_again"))),
      h("div", { class: "actions" }, go)].filter(Boolean)); // replaceChildren would print a null as "null"
  };
  const follow = async op => {
    for (;;) {
      if (!box.isConnected) return;
      status.replaceChildren(integrationStatus(op, {
        resume: async () => {
          try { follow((await api("POST", `/operations/${op.operation_id}/resume`, {})).operation); }
          catch (e) { status.append(errorBox(e)); }
        },
        cancel: async () => { await api("POST", `/operations/${op.operation_id}/cancel`, {}); await freshHead(); runPreview(); } }));
      if (TERMINAL.includes(op.status) || op.status === "needs_attention") break;
      await sleep(1500);
      op = (await api("GET", `/operations/${op.operation_id}`)).operation;
    }
    if (op.status === "succeeded") reloadCard(integrationStatus(op, {})); // the card shows the new head
    else if (["TARGET_HEAD_CHANGED", "SOURCE_CHANGED"].includes(op.error_code)) { await freshHead(); runPreview(); }
  };
  const branch = h("input", { placeholder: t("branch_on_github") });
  (async () => {
    try {
      const c = await api("GET", `/integrations/candidates?host=${encodeURIComponent(target.host)}`);
      const row = (kind, id, label, chips) => h("div", { class: "row" },
        h("div", { class: "grow" }, h("code", {}, label), " ", ...chips),
        h("button", { class: "secondary", onclick: () => add(kind, id, label) }, t("add")));
      const delivered = x => x.delivered_to.length ? [chip(t("delivered_to", { n: x.delivered_to[0].pull_number }), "ok")] : [];
      pickList.replaceChildren(
        h("h3", {}, t("agent_results")),
        ...(c.agent_results.length ? c.agent_results.map(r => row("checkpoint_run", r.id, r.branch,
          [r.streaming ? chip(t("still_working"), "warn") : chip(t("done"), "ok"), ...delivered(r)]))
          : [h("p", { class: "muted" }, t("none"))]),
        h("h3", {}, t("your_checkpoints")),
        ...(c.checkpoints.length ? c.checkpoints.map(r => row("checkpoint", r.id, `${r.branch || "?"} @ ${r.commit_sha.slice(0, 10)}`,
          [r.note ? h("span", { class: "muted" }, r.note.slice(0, 60)) : null, ...delivered(r)]))
          : [h("p", { class: "muted" }, t("none"))]),
        h("div", { class: "actions" }, branch, h("button", { class: "secondary", onclick: () => {
          if (branch.value.trim()) add("branch", branch.value.trim(), branch.value.trim());
          branch.value = "";
        } }, t("add_branch"))));
    } catch (e) { pickList.replaceChildren(errorBox(e)); }
  })();
  box.append(pickList, h("h3", {}, t("selected_in_order")), order, previewBox, status);
  return box;
}

function integrationStatus(op, act) {
  const code = op.error_code;
  const text = op.status === "succeeded"
    ? t("integration_done", { old: op.result.old_head.slice(0, 7), new: op.result.new_head.slice(0, 7),
      n: op.result.added_commits ?? "?" })
    : op.status === "needs_attention" ? (t("integration_" + code) !== "integration_" + code ? t("integration_" + code) : op.status_reason)
      : op.status === "uncertain" ? t("integration_uncertain")
        : op.status === "waiting_external" ? ((op.external_refs || {}).conflict ? t("integration_waiting_resolver")
          : (op.external_refs || {}).pushed_sha ? t("integration_waiting") : op.status_reason || t("integration_running"))
          : op.status === "failed" ? `${code}: ${op.status_reason || ""}` : t("integration_running");
  const conflict = ["INTEGRATION_CONFLICT", "RESOLUTION_INCOMPLETE", "RESOLUTION_INVALID"].includes(code);
  const out = h("div", {});
  const handoff = conflict && (state.caps?.scopes || []).includes("start")
    ? h("button", { class: "secondary", onclick: async () => {
      try {
        const o = await submit("integration.handoff", { operation_id: op.operation_id }, { agent: "claude" }, {},
          `handoff.${op.operation_id}`);
        out.append(h("p", {}, opStatus(o), " ", t("handoff_started"), " ",
          h("a", { href: `#/op/${o.operation_id}` }, o.operation_id)));
      } catch (e) { out.append(errorBox(e)); }
    } }, t("hand_to_agent")) : null;
  const buttons = op.status === "needs_attention" ? [
    h("button", { class: "primary", onclick: act.resume }, t("resume")), handoff,
    h("button", { class: "danger", onclick: act.cancel }, t("cancel_and_preview"))].filter(Boolean) : [];
  out.append(h("p", {}, opStatus(op), " ", text, " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id)),
    h("div", { class: "actions" }, ...buttons));
  return out;
}

async function viewOperations(main) {
  const list = h("div", { class: "panel" });
  main.append(h("h1", {}, t("nav_operations")), list);
  const render = async () => {
    try { list.replaceChildren(...(await api("GET", "/operations?limit=100")).operations.map(opRow)); }
    catch (e) { list.replaceChildren(errorBox(e)); }
  };
  await render();
  const reload = debounce(render, 500);
  return onEvents(ev => { if (ev.resource_type === "operation") reload(); });
}

async function viewOperation(main, id) {
  const panel = h("div", { class: "panel" });
  main.append(panel);
  const render = async () => {
    try {
      const { operation: op, work_items: linked } = await api("GET", `/operations/${id}`);
      const refs = op.external_refs || {};
      const retry = refs.merged_sha && op.action === "delivery.merge_and_deploy" && op.status === "failed"
        ? h("button", { class: "primary", onclick: async () => {
          try {
            const preview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(op.target.recipe)}`)).preview;
            const o = await submit("deployment.start", { recipe: op.target.recipe }, { source_sha: refs.merged_sha }, preview.preconditions,
              `deploy.${op.target.recipe}.${refs.merged_sha}`);
            location.hash = `#/op/${o.operation_id}`;
          } catch (e) { panel.append(errorBox(e)); }
        } }, t("retry_deploy")) : null;
      const resume = op.status === "needs_attention"
        ? h("button", { class: "primary", title: t("resume_help"), onclick: async () => {
          try { await api("POST", `/operations/${id}/resume`, {}); render(); } catch (e) { panel.append(errorBox(e)); }
        } }, t("resume")) : null;
      const opened = op.result?.session_id && op.result?.host
        ? h("a", { class: "secondary", href: `#/session/${encodeURIComponent(op.result.host)}/${encodeURIComponent(op.result.session_id)}` },
          t("open_new_session")) : null;
      let receipts = null;
      if (op.action === "integration.apply") {
        const rows = (await api("GET", `/integrations/${id}`)).receipts;
        receipts = [h("h2", {}, t("receipts")), ...rows.map(r => h("div", { class: "row" },
          h("div", { class: "grow" }, `${r.seq}. ${t("kind_" + r.source_kind)} `, h("code", {}, r.source_id.slice(0, 15)), " ",
            h("code", {}, `${r.pinned_sha.slice(0, 10)} → ${(r.integrated_sha || "").slice(0, 10)}`),
            r.conflict_files ? h("span", { class: "error" }, " ", r.conflict_files.join(", ")) : null),
          chip(r.method || "-"), chip(t("receipt_" + r.effective_status), r.effective_status === "delivered" ? "ok" : "")))];
      }
      const cancel = !TERMINAL.includes(op.status)
        ? h("button", { class: "danger", onclick: async () => {
          try { await api("POST", `/operations/${id}/cancel`, {}); render(); } catch (e) { panel.append(errorBox(e)); }
        } }, t("cancel"))
        : null;
      fill(panel, h("h1", {}, op.action),
        h("p", { class: "op-status" }, opStatus(op), " ", op.error_code ? chip(op.error_code, "bad") : null),
        ...(linked?.length ? [linkedItems(linked)] : []),
        h("dl", { class: "kv" },
          h("dt", {}, t("actor")), h("dd", {}, `${op.actor} (${op.entry})`),
          h("dt", {}, t("created")), h("dd", {}, when(epoch(op.created_at))),
          op.status_reason ? [h("dt", {}, t("reason")), h("dd", {}, op.status_reason)] : null,
          h("dt", {}, "Target"), h("dd", {}, h("code", {}, JSON.stringify(op.target))),
          Object.keys(refs).length ? [h("dt", {}, "Refs"), h("dd", {}, h("code", {}, JSON.stringify(refs)))] : null,
          op.result ? [h("dt", {}, "Result"), h("dd", {}, h("code", {}, JSON.stringify(op.result)))] : null),
        ...(receipts || []),
        (op.result?.merge || op.result || refs.merge_receipt)?.base_moved
          ? h("p", { class: "note warn" }, t("merged_newer_base", { count: (op.result?.merge || op.result || refs.merge_receipt).other_commits_count })) : null,
        refs.write_acknowledged && refs.verification_pending ? h("p", { class: "note warn" }, t("metadata_pending")) : null,
        h("h2", {}, t("steps")),
        ...op.steps.map(s => h("div", { class: "row" }, h("div", { class: "grow" }, s.name),
          h("span", { class: `status-${s.status}` }, s.status), s.error ? chip(s.error.code || t("error"), "bad") : null)),
        h("div", { class: "actions" }, opened, resume, retry, cancel));
    } catch (e) { fill(panel, errorBox(e)); }
  };
  await render();
  return onEvents(ev => { if (ev.resource_id === id) render(); });
}

function viewSettings(main) {
  const input = h("input", { type: "password", autocomplete: "off", size: 40, placeholder: "batc_…" });
  const remember = h("input", { type: "checkbox" });
  const info = h("p", { class: "muted" });
  if (state.caps) info.textContent = t("connected_as", { actor: state.caps.actor, scopes: state.caps.scopes.join(", ") });
  main.append(h("h1", {}, t("nav_settings")), h("div", { class: "panel" },
    h("label", {}, t("token")), h("div", { class: "filters" }, input,
      h("button", { class: "primary", onclick: async () => {
        state.token = input.value.trim();
        try {
          state.caps = await api("GET", "/capabilities");
          saveToken(state.token, remember.checked);
          location.hash = "#/home";
        } catch (e) { state.token = null; info.replaceChildren(errorBox(e)); }
      } }, t("connect")),
      h("button", { class: "secondary", onclick: () => { clearToken(); state.token = null; state.caps = null; route(); } }, t("disconnect"))),
    h("label", {}, remember, " ", t("remember")), h("p", { class: "muted" }, t("token_help")), info));
}

// ------------------------------------------------------------------ projects and work items
// The connector's own records. A change names what the page read (version, fingerprint, sibling order or pin), so a
// stale page is refused and reloads instead of overwriting someone else's edit.
const may = scope => (state.caps?.scopes || []).includes(scope);
function fill(el, ...kids) { el.replaceChildren(...kids.flat(2).filter(x => x !== null && x !== undefined && x !== false)); }
const PROJECT_ERRORS = ["VERSION_CONFLICT", "ORDER_CHANGED", "PIN_CHANGED", "CONTENT_CHANGED", "NAME_TAKEN",
  "HAS_CHILDREN", "PARENT_ARCHIVED", "PINNED_FIRST", "STEPS_OPEN", "CYCLE", "LINK_TARGET_NOT_FOUND", "NOTHING_TO_DECIDE"];
function problem(code, message) {
  return h("p", { class: "error" }, PROJECT_ERRORS.includes(code) ? t("wi_err_" + code) : `${code || ""} ${message || ""}`);
}
// The page read is stale: re-render, keep the message (and an edit form's draft) on screen.
const STALE = ["VERSION_CONFLICT", "ORDER_CHANGED", "PIN_CHANGED", "CONTENT_CHANGED"];
let lastFailure = null;
// Run one management change; returns the finished operation, or shows why not in `out` and returns null
// (lastFailure holds the error code). `out` should sit outside what the caller re-renders afterwards.
async function change(out, action, target, params, pre, scope) {
  lastFailure = null;
  try {
    const op = await submit(action, target, params, pre, scope);
    if (op.status === "succeeded") { fill(out); return op; }
    lastFailure = op.error_code || op.status;
    if (TERMINAL.includes(op.status)) fill(out, problem(op.error_code, op.status_reason));
    else fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
  } catch (e) {
    lastFailure = e.code || "ERROR";
    fill(out, e.status === 403 ? errorBox(e) : problem(e.code, e.message));
  }
  return null;
}
function manageNote() { return may("manage") ? null : h("p", { class: "note" }, t("needs_manage_scope")); }
function indent(el, depth) { el.style.setProperty("--depth", String(depth)); return el; } // CSP: no style attributes
function stateChip(c) {
  const cls = { done: "ok", awaiting_approval: "warn", doing: "info", waiting: "warn" }[c.display_state] || "";
  return chip(t("wi_state_" + c.display_state), cls);
}
function counts(c) {
  return [c.doing ? chip(`${t("wi_state_doing")} ${c.doing}`, "info") : null,
    c.awaiting_approval ? chip(`${t("wi_state_awaiting_approval")} ${c.awaiting_approval}`, "warn") : null,
    chip(t("wi_done_of", { done: c.done, total: c.total }), c.total && c.done === c.total ? "ok" : "")];
}
// ↑ ↓ and pin for one entry among its siblings; pinned entries never cross unpinned ones.
function orderButtons(sibs, i, key, run) {
  const me = sibs[i];
  const swap = j => () => {
    const before = sibs.map(x => x[key]);
    const order = before.slice(); [order[i], order[j]] = [order[j], order[i]];
    run("order", before, order);
  };
  const can = j => j >= 0 && j < sibs.length && sibs[j].pinned === me.pinned;
  return [h("button", { class: "mini", title: t("move_up"), "aria-label": t("move_up"), disabled: !can(i - 1), onclick: swap(i - 1) }, "↑"),
    h("button", { class: "mini", title: t("move_down"), "aria-label": t("move_down"), disabled: !can(i + 1), onclick: swap(i + 1) }, "↓"),
    h("button", { class: `mini ${me.pinned ? "on" : ""}`, title: me.pinned ? t("unpin") : t("pin"),
      "aria-label": me.pinned ? t("unpin") : t("pin"), onclick: () => run("pin", me.pinned) }, me.pinned ? "★" : "☆")];
}
// A row's "…" opens a small form under it. While any is open, live reloads wait (a draft is never lost) and run
// once the last one closes.
let editing = 0, idleReload = null, drawerOpens = 0;
function setEditing(n) {
  editing = Math.max(0, n);
  if (!editing && idleReload) { const fn = idleReload; idleReload = null; fn(); }
}
function drawer(...children) {
  const box = h("div", { class: "drawer", hidden: true }, ...children);
  const toggle = h("button", { class: "mini", title: t("more"), "aria-label": t("more"), onclick: () => {
    box.hidden = !box.hidden;
    if (!box.hidden) drawerOpens += 1;
    setEditing(editing + (box.hidden ? -1 : 1));
  } }, "…");
  const open = () => { if (box.hidden) toggle.click(); };
  return { box, toggle, open, close: () => { if (!box.hidden) toggle.click(); } };
}
function freshPage() { editing = 0; idleReload = null; } // a render rebuilt every drawer closed
// Views' render(fromEvent): a live reload never rebuilds under an open drawer, and no render rebuilds under a
// drawer opened while it was fetching (the person started typing after the click that asked for it).
function typing() { // a field in the page has focus: a live reload would throw away what is being typed
  const a = document.activeElement;
  return Boolean(a?.closest?.("#main")) && (a.tagName === "TEXTAREA" || a.tagName === "SELECT"
    || (a.tagName === "INPUT" && !["checkbox", "radio", "button", "submit"].includes(a.type)));
}
function holdRender(fromEvent, opensAtStart) {
  return (editing > 0 && (fromEvent || drawerOpens !== opensAtStart)) || (fromEvent && typing());
}
document.addEventListener("focusout", () => setTimeout(() => {
  if (!editing && !typing() && idleReload) { const fn = idleReload; idleReload = null; fn(); }
}, 0));
function liveReload(fn, kinds) {
  const later = debounce(() => { if (editing || typing()) idleReload = () => fn(true); else fn(true); }, 500);
  return onEvents(ev => { if (kinds.includes(ev.resource_type)) later(); });
}

async function viewProjects(main) {
  freshPage();
  const out = h("div", {});
  const tree = h("div", { class: "panel" });
  const archived = h("div", {});
  const name = h("input", { placeholder: t("new_project_name"), maxlength: 80 });
  const add = h("button", { class: "primary", disabled: !may("manage"), onclick: async () => {
    if (!name.value.trim()) return;
    add.disabled = true;
    const op = await change(out, "project.create", {}, { name: name.value.trim() }, {}, "project.create");
    add.disabled = false;
    if (op) { name.value = ""; location.hash = `#/project/${op.result.project_id}`; }
  } }, t("add_project"));
  const showArchived = h("input", { type: "checkbox" });
  main.append(h("h1", {}, t("nav_projects")), h("p", { class: "muted" }, t("projects_help")), manageNote() || "",
    h("div", { class: "filters" }, name, add), out, tree,
    h("label", { class: "muted" }, showArchived, " ", t("show_archived")), archived);
  const render = async (fromEvent = false) => {
    const opens = drawerOpens;
    try {
      const data = await api("GET", `/projects${showArchived.checked ? "?include_archived=true" : ""}`);
      if (!tree.isConnected) return;
      if (holdRender(fromEvent, opens)) { idleReload = () => render(true); return; }
      freshPage();
      const rows = [];
      const walk = (sibs, depth, parent) => sibs.forEach((p, i) => {
        const msg = out; // outside the tree: it survives the re-render below
        const run = async (what, before, order) => {
          if (what === "order") await change(msg, "project.order", {}, { parent_id: parent, order }, { before }, `project.order.${parent}`);
          else await change(msg, "project.pin", { project_id: p.project_id }, { pinned: !before }, { before }, `project.pin.${p.project_id}`);
          render();
        };
        const rename = h("input", { value: p.name, maxlength: 80 });
        const sub = h("input", { placeholder: t("new_sub_project"), maxlength: 80 });
        const d = drawer(
          h("div", { class: "filters" }, rename, h("button", { class: "secondary", onclick: async () => {
            const ok = await change(msg, "project.update", { project_id: p.project_id }, { name: rename.value.trim() },
              { expected_version: p.version }, `project.rename.${p.project_id}`);
            if (ok || STALE.includes(lastFailure)) render();
          } }, t("rename"))),
          h("div", { class: "filters" }, sub, h("button", { class: "secondary", onclick: async () => {
            if (!sub.value.trim()) return;
            if (await change(msg, "project.create", {}, { name: sub.value.trim(), parent_id: p.project_id }, {},
              `project.create.${p.project_id}`)) { d.close(); render(); }
          } }, t("add_project"))),
          h("div", { class: "actions" }, h("button", { class: "danger", onclick: async () => {
            const ok = await change(msg, "project.update", { project_id: p.project_id }, { archived: true },
              { expected_version: p.version }, `project.archive.${p.project_id}`);
            if (ok || STALE.includes(lastFailure)) render();
          } }, t("archive"))));
        rows.push(indent(h("div", { class: "row tree" },
          h("div", { class: "grow" }, h("a", { class: "title", href: `#/project/${p.project_id}` }, p.name),
            p.description ? h("div", { class: "muted clamp" }, p.description) : null),
          ...counts(p.counts),
          may("manage") ? h("span", { class: "tree-actions" }, ...orderButtons(sibs, i, "project_id", run), d.toggle) : null), depth),
        d.box);
        walk(p.children, depth + 1, p.project_id);
      });
      walk(data.projects, 0, "");
      fill(tree, ...(rows.length ? rows : [h("p", { class: "muted" }, t("no_projects"))]));
      fill(archived, ...(data.archived || []).map(p => h("div", { class: "row" },
        h("div", { class: "grow" }, h("span", { class: "muted" }, p.name)),
        h("button", { class: "secondary", disabled: !may("manage"), onclick: async () => {
          await change(out, "project.update", { project_id: p.project_id }, { archived: false },
            { expected_version: p.version }, `project.restore.${p.project_id}`);
          render();
        } }, t("restore")))));
    } catch (e) { fill(tree, errorBox(e)); }
  };
  showArchived.onchange = () => render();
  await render();
  return liveReload(render, ["project", "work_item"]);
}

async function viewProject(main, pid) {
  freshPage();
  let draft = null; // the project form's values after a stale save, put back into the reloaded form
  const head = h("div", { class: "panel" });
  const items = h("div", { class: "panel" });
  const out = h("div", {});
  const archived = h("div", {});
  const showArchived = h("input", { type: "checkbox" });
  const title = h("input", { placeholder: t("new_item_title"), maxlength: 120 });
  const add = h("button", { class: "primary", disabled: !may("manage"), onclick: async () => {
    if (!title.value.trim()) return;
    add.disabled = true;
    const op = await change(out, "work_item.create", { project_id: pid }, { title: title.value.trim() }, {}, `wi.create.${pid}`);
    add.disabled = false;
    if (op) { title.value = ""; render(); }
  } }, t("add_item"));
  main.append(manageNote() || "", out, head, h("h2", {}, t("work_items")), h("div", { class: "filters" }, title, add), items,
    h("label", { class: "muted" }, showArchived, " ", t("show_archived")), archived);
  const render = async (fromEvent = false) => {
    const opens = drawerOpens;
    let data;
    try { data = await api("GET", `/projects/${pid}${showArchived.checked ? "?include_archived=true" : ""}`); }
    catch (e) { fill(head, errorBox(e)); return; }
    if (!head.isConnected) return;
    if (holdRender(fromEvent, opens)) { idleReload = () => render(true); return; }
    freshPage();
    const p = data.project;
    const msg = out;
    const v = draft || { name: p.name, description: p.description, repositories: p.repositories, task_project: p.task_project || "" };
    const f = {
      name: h("input", { value: v.name, maxlength: 80 }),
      description: h("textarea", {}, v.description),
      repositories: h("input", { value: v.repositories.join(", "), placeholder: "owner/name, owner/name" }),
      task_project: h("input", { value: v.task_project, placeholder: t("task_project") }),
    };
    const d = drawer(h("label", {}, t("name")), f.name, h("label", {}, t("description")), f.description,
      h("label", {}, t("repositories")), f.repositories, h("label", {}, t("task_project")), f.task_project,
      h("div", { class: "actions" }, h("button", { class: "primary", onclick: async () => {
        const params = { name: f.name.value.trim(), description: f.description.value,
          repositories: f.repositories.value.split(/[\s,]+/).filter(Boolean), task_project: f.task_project.value.trim() };
        const ok = await change(msg, "project.update", { project_id: pid }, params, { expected_version: p.version },
          `project.edit.${pid}`);
        if (!ok && STALE.includes(lastFailure)) draft = params;
        if (ok || draft) render();
      } }, t("save"))));
    fill(head, 
      h("div", { class: "muted" }, h("a", { href: "#/projects" }, t("nav_projects")),
        ...data.path.flatMap(x => [" / ", h("a", { href: `#/project/${x.project_id}` }, x.name)])),
      h("h1", {}, p.name, " ", p.archived ? chip(t("archived"), "warn") : null),
      p.description ? h("p", { class: "pre" }, p.description) : null,
      h("div", { class: "actions" }, ...counts(p.counts), ...p.repositories.map(r => chip(r)),
        p.task_project ? chip(`Task Service: ${p.task_project}`) : null, may("manage") && !p.archived ? d.toggle : null),
      d.box,
      data.sub_projects.length ? h("p", {}, t("sub_projects"), ": ",
        ...data.sub_projects.flatMap((x, i) => [i ? " · " : "", h("a", { href: `#/project/${x.project_id}` }, x.name)])) : null);
    if (draft) { draft = null; d.open(); }
    const rows = [];
    const walk = (sibs, depth, parent) => sibs.forEach((w, i) => {
      const rowMsg = out; // outside the tree: it survives the re-render below
      const run = async (what, before, order) => {
        if (what === "order") await change(rowMsg, "work_item.order", { project_id: pid }, { parent_id: parent, order }, { before }, `wi.order.${pid}.${parent}`);
        else await change(rowMsg, "work_item.pin", { work_item_id: w.work_item_id }, { pinned: !before }, { before }, `wi.pin.${w.work_item_id}`);
        render();
      };
      const child = h("input", { placeholder: t("new_child_item"), maxlength: 120 });
      const branch = h("input", { placeholder: t("new_branch_item"), maxlength: 120 });
      const create = (input, params, scope) => h("button", { class: "secondary", onclick: async () => {
        if (!input.value.trim()) return;
        if (await change(rowMsg, "work_item.create", { project_id: pid }, { title: input.value.trim(), ...params }, {}, scope)) render();
      } }, t("add_item"));
      const dr = drawer(
        h("div", { class: "filters" }, child, create(child, { parent_id: w.work_item_id }, `wi.child.${w.work_item_id}`)),
        h("div", { class: "filters" }, branch, create(branch, { parent_id: parent || null, derived_from: w.work_item_id },
          `wi.branch.${w.work_item_id}`)),
        h("div", { class: "actions" }, h("button", { class: "danger", onclick: async () => {
          const ok = await change(rowMsg, "work_item.update", { work_item_id: w.work_item_id }, { archived: true },
            { expected_version: w.version }, `wi.archive.${w.work_item_id}`);
          if (ok || STALE.includes(lastFailure)) render();
        } }, t("archive_with_children"))));
      const done = w.steps.filter(s => s.done).length;
      rows.push(indent(h("div", { class: "row tree" }, stateChip(w.completion),
        h("div", { class: "grow" }, h("a", { class: "title", href: `#/item/${w.work_item_id}` }, w.title),
          w.derived_from ? h("span", { class: "muted" }, " ⑂") : null),
        w.steps.length ? chip(`${done}/${w.steps.length}`) : null,
        w.completion.pending ? chip(t("needs_decision"), "warn") : null,
        may("manage") && !p.archived ? h("span", { class: "tree-actions" }, ...orderButtons(sibs, i, "work_item_id", run), dr.toggle) : null), depth),
      dr.box);
      walk(w.children, depth + 1, w.work_item_id);
    });
    walk(data.work_items, 0, "");
    fill(items, ...(rows.length ? rows : [h("p", { class: "muted" }, t("no_items"))]));
    fill(archived, ...(data.archived || []).map(w => h("div", { class: "row" },
      h("div", { class: "grow" }, h("a", { class: "muted", href: `#/item/${w.work_item_id}` }, w.title)),
      h("button", { class: "secondary", disabled: !may("manage") || p.archived, onclick: async () => {
        await change(out, "work_item.update", { work_item_id: w.work_item_id }, { archived: false },
          { expected_version: w.version }, `wi.restore.${w.work_item_id}`);
        render();
      } }, t("restore")))));
    add.disabled = !may("manage") || p.archived;
  };
  showArchived.onchange = () => render();
  await render();
  return liveReload(render, ["project", "work_item"]);
}

function linkTarget(l) {
  const x = l.target || {};
  if (!x.found) return h("span", { class: "muted" }, l.ref, " · ", t("link_missing"));
  if (l.kind === "session") {
    const [host, ...rest] = l.ref.split("/");
    return h("span", {}, h("a", { href: `#/session/${encodeURIComponent(host)}/${encodeURIComponent(rest.join("/"))}` }, x.title || l.ref),
      " ", chip(x.api_access === "managed" ? t("managed") : t("read_only"), x.api_access === "managed" ? "managed" : "readonly"),
      x.gone ? chip(t("stale_reason_gone"), "stale") : null);
  }
  if (l.kind === "operation") {
    return h("span", {}, h("a", { href: `#/op/${l.ref}` }, x.action), " ", h("span", { class: `status-${x.status}` }, t("op_" + x.status)),
      x.session ? [" · ", h("a", { href: `#/session/${encodeURIComponent(x.session.host)}/${encodeURIComponent(x.session.session_id)}` }, t("open_new_session"))] : null);
  }
  if (l.kind === "checkpoint") {
    return h("span", {}, h("a", { href: `#/session/${encodeURIComponent(x.host)}/${encodeURIComponent(x.source_session_id)}` },
      h("code", {}, x.commit_sha.slice(0, 12))), " ", x.branch || "", " · ", x.host);
  }
  if (l.kind === "task") return h("span", {}, h("code", {}, l.ref.slice(0, 12)), " ", x.project, " · ", x.state);
  return h("a", { href: `https://github.com/${x.repository}/pull/${x.number}`, target: "_blank", rel: "noopener" },
    `${x.repository}#${x.number}`);
}

async function viewWorkItem(main, wid) {
  freshPage();
  const notice = h("div", {}); // outside the panel: a refusal stays on screen after the panel re-renders
  const panel = h("div", {});
  let draft = null; // the edit form's values after a stale save, put back into the reloaded form
  // Fields made once and moved into each render: a re-render never throws away what is being typed.
  const newStep = h("input", { placeholder: t("new_step"), maxlength: 300 });
  const kind = h("select", {}, ...["session", "checkpoint", "operation", "task", "pull_request"].map(k =>
    h("option", { value: k }, t("link_" + k))));
  const ref = h("input", { placeholder: t("link_ref_hint") });
  kind.onchange = () => { ref.placeholder = t("link_ref_" + kind.value); };
  kind.onchange();
  main.append(manageNote() || "", notice, panel);
  const render = async (fromEvent = false) => {
    const opens = drawerOpens;
    let data;
    try { data = await api("GET", `/work-items/${wid}`); }
    catch (e) { fill(panel, errorBox(e)); return; }
    if (!panel.isConnected) return;
    if (holdRender(fromEvent, opens)) { idleReload = () => render(true); return; }
    freshPage();
    const w = data.work_item, c = w.completion;
    const live = !w.archived && !data.project.archived;
    const pre = { expected_version: w.version };
    const update = (params, scope) => change(notice, "work_item.update", { work_item_id: wid }, params, pre, scope);
    const decide = async (action, scope) => { await change(notice, action, { work_item_id: wid }, {}, { expected_fingerprint: c.fingerprint }, scope); render(); };
    // completion: an agent's "done" is a claim; a person accepts it for the content shown here
    const approve = h("button", { class: "primary", disabled: !live || !may("approve"), title: may("approve") ? null : t("needs_approve_scope"),
      onclick: () => decide("work_item.approve", `wi.approve.${wid}.${c.fingerprint}`) }, c.pending ? t("accept_done") : t("mark_done"));
    const keepGoing = h("button", { class: "secondary", disabled: !live || !may("manage"),
      onclick: () => decide("work_item.continue", `wi.continue.${wid}.${c.fingerprint}`) }, t("keep_working"));
    let banner = null;
    if (c.approved) banner = h("p", { class: "note ok" }, t("approved_by", { who: c.approved_by, time: when(epoch(c.approved_at)) }));
    else if (c.pending && w.state === "done") banner = h("div", { class: "note warn" }, h("p", {}, t("claimed_done", { who: c.claimed_by || "?" })),
      h("div", { class: "actions" }, approve, keepGoing), may("approve") ? null : h("p", { class: "muted" }, t("needs_approve_scope")));
    else if (c.pending) banner = h("div", { class: "note warn" }, h("p", {}, t("steps_all_checked")), h("div", { class: "actions" }, approve, keepGoing));
    const stateSel = h("select", { disabled: !live || !may("manage") }, ...["todo", "doing", "waiting"].map(s =>
      h("option", { value: s, selected: w.state === s }, t("wi_state_" + s))));
    if (w.state === "done") stateSel.prepend(h("option", { value: "done", selected: true }, t("wi_state_" + c.display_state)));
    stateSel.onchange = async () => { await update({ state: stateSel.value }, `wi.state.${wid}`); render(); };
    // content: goal, the request verbatim, acceptance
    const v = { ...w, ...(draft || {}) };
    const f = { title: h("input", { value: v.title, maxlength: 120 }), goal: h("textarea", {}, v.goal),
      request: h("textarea", {}, v.request), acceptance: h("textarea", {}, v.acceptance) };
    const d = drawer(h("label", {}, t("title")), f.title, h("label", {}, t("goal")), f.goal, h("label", {}, t("request")), f.request,
      h("label", {}, t("acceptance")), f.acceptance, h("div", { class: "actions" }, h("button", { class: "primary", onclick: async () => {
        const params = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, k === "title" ? el.value.trim() : el.value])
          .filter(([k, v]) => v !== w[k]));
        if (!Object.keys(params).length) { d.close(); return; }
        const ok = await update(params, `wi.edit.${wid}`);
        if (!ok && STALE.includes(lastFailure)) draft = params;
        if (ok || draft) render();
      } }, t("save"))));
    const section = (label, text) => text ? [h("h2", {}, label), h("div", { class: "panel pre" }, text)] : [];
    // steps: checking one is an edit like any other (an unchecked step reopens a done item)
    const setSteps = async (steps, added) => {
      if (await update({ steps }, `wi.steps.${wid}`) && added) newStep.value = "";
      render();
    };
    const stepRows = w.steps.map((s, i) => h("div", { class: "step" },
      h("label", {}, h("input", { type: "checkbox", checked: s.done, disabled: !live || !may("manage"),
        onchange: () => setSteps(w.steps.map((x, j) => (j === i ? { ...x, done: !x.done } : x))) }), " ", s.text),
      live && may("manage") ? h("button", { class: "mini", title: t("remove"), "aria-label": t("remove"),
        onclick: () => setSteps(w.steps.filter((_, j) => j !== i)) }, "×") : null));
    const addStep = h("button", { class: "secondary", disabled: !live || !may("manage"), onclick: () => {
      if (newStep.value.trim()) setSteps([...w.steps, { text: newStep.value.trim(), done: false }], true);
    } }, t("add"));
    // links: the sessions, checkpoints, operations, tasks and PRs that carried this item
    const link = async (params, scope, typed) => {
      if (await change(notice, "work_item.link", { work_item_id: wid }, params, {}, scope)) {
        if (typed) ref.value = "";
        render();
      }
    };
    const linkRows = data.links.map(l => h("div", { class: "row" }, chip(t("link_" + l.kind)),
      h("div", { class: "grow" }, linkTarget(l), l.note ? h("div", { class: "muted" }, l.note) : null,
        h("div", { class: "muted" }, `${l.linked_by} · ${when(epoch(l.linked_at))}`)),
      l.kind === "checkpoint" && l.target?.found && live ? continueFrom(w, l.ref, notice) : null,
      live && may("manage") ? h("button", { class: "mini", title: t("remove"), "aria-label": t("remove"),
        onclick: () => link({ kind: l.kind, ref: l.ref, remove: true }, `wi.unlink.${wid}.${l.kind}.${l.ref}`) }, "×") : null));
    const brief = x => h("div", { class: "row" }, chip(t("wi_state_" + x.display_state)),
      h("a", { class: "grow", href: `#/item/${x.work_item_id}` }, x.title));
    fill(panel, 
      h("div", { class: "muted" }, h("a", { href: "#/projects" }, t("nav_projects")), " / ",
        h("a", { href: `#/project/${data.project.project_id}` }, data.project.name),
        ...data.path.flatMap(x => [" / ", h("a", { href: `#/item/${x.work_item_id}` }, x.title)])),
      h("h1", {}, w.title, " ", stateChip(c), w.archived ? [" ", chip(t("archived"), "warn")] : null),
      data.derived_from ? h("p", { class: "muted" }, t("derived_from"), " ",
        h("a", { href: `#/item/${data.derived_from.work_item_id}` }, data.derived_from.title)) : null,
      banner,
      h("div", { class: "actions" }, h("label", {}, t("state"), " ", stateSel),
        !c.pending && !c.approved && live ? approve : null, live && may("manage") ? d.toggle : null),
      d.box,
      ...section(t("goal"), w.goal), ...section(t("request"), w.request), ...section(t("acceptance"), w.acceptance),
      h("h2", {}, t("steps_title")), h("div", { class: "panel" }, ...(stepRows.length ? stepRows : [h("p", { class: "muted" }, t("no_steps"))]),
        live && may("manage") ? h("div", { class: "filters" }, newStep, addStep) : null),
      h("h2", {}, t("links")), h("div", { class: "panel" },
        ...(linkRows.length ? linkRows : [h("p", { class: "muted" }, t("no_links"))]),
        live && may("manage") ? h("div", { class: "filters" }, kind, ref, h("button", { class: "secondary", onclick: () => {
          if (ref.value.trim()) link({ kind: kind.value, ref: ref.value.trim() }, `wi.link.${wid}`, true);
        } }, t("link"))) : null),
      data.children.length ? [h("h2", {}, t("children")), h("div", { class: "panel" }, ...data.children.map(brief))] : null,
      data.derived.length ? [h("h2", {}, t("derived")), h("div", { class: "panel" }, ...data.derived.map(brief))] : null,
      h("h2", {}, t("history")), h("div", { class: "panel" }, ...data.events.map(ev => h("div", { class: "row" },
        h("div", { class: "grow" }, t("ev_" + ev.kind.replace(".", "_")), h("div", { class: "muted" }, eventDetail(ev.body))),
        h("span", { class: "muted" }, `${ev.actor || ""} · ${when(epoch(ev.created_at))}`)))));
    if (draft) { draft = null; d.open(); }
  };
  await render();
  return liveReload(render, ["work_item"]);
}

// Start agent work from a linked checkpoint, with this item's words as the instructions; the new operation is
// linked back so the item lists the run.
function continueFrom(w, checkpointId, notice) {
  const text = [w.title, w.goal, w.request && `${t("request")}:\n${w.request}`, w.acceptance && `${t("acceptance")}:\n${w.acceptance}`,
    w.steps.length ? `${t("steps_title")}:\n${w.steps.map(s => `- [${s.done ? "x" : " "}] ${s.text}`).join("\n")}` : ""]
    .filter(Boolean).join("\n\n");
  const instr = h("textarea", {}, text);
  const agent = h("select", {}, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
  const out = h("div", {});
  const go = h("button", { class: "primary", onclick: async () => {
    go.disabled = true;
    let op;
    try {
      op = await submit("checkpoint.continue", { checkpoint_id: checkpointId }, { instructions: instr.value, agent: agent.value }, {},
        `continue.${checkpointId}`);
    } catch (e) { fill(out, errorBox(e)); go.disabled = false; return; }
    // Started (or refused for good): this form never starts another agent. Its result stays here; the item lists
    // the run once the form closes and the page reloads.
    fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
    if (TERMINAL.includes(op.status) && op.status !== "succeeded") return;
    const linked = await change(notice, "work_item.link", { work_item_id: w.work_item_id }, { kind: "operation", ref: op.operation_id }, {},
      `wi.link.${w.work_item_id}.${op.operation_id}`);
    if (linked) out.append(" · ", t("linked_back"));
  } }, t("start_agent_work"));
  const d = drawer(h("p", { class: "muted" }, t("confined_note")), instr, h("div", { class: "actions" }, agent, go), out);
  // Starting needs start; linking the run back needs manage. Without both, nothing starts (an unlinked run is untracked).
  const why = !may("start") ? t("needs_start_scope") : !may("manage") ? t("needs_manage_scope") : null;
  const open = h("button", { class: "secondary", disabled: Boolean(why), title: why, onclick: () => d.toggle.click() },
    t("start_from_checkpoint"));
  return h("div", { class: "grow" }, open, d.box);
}
function eventDetail(b) {
  if (b.fields) return b.fields.map(f => t(f === "steps" ? "steps_title" : f)).join(", ");
  if (b.from && b.to) return `${t("wi_state_" + b.from)} → ${t("wi_state_" + b.to)}${b.note ? ` · ${b.note}` : ""}`;
  if (b.kind && b.ref) return `${t("link_" + b.kind)} ${b.ref}`;
  return b.note || "";
}
function linkedItems(items) {
  return h("p", { class: "muted" }, t("linked_items"), ": ",
    ...items.flatMap((x, i) => [i ? " · " : "", h("a", { href: `#/item/${x.work_item_id}` }, x.title)]));
}
function workItemRow(w) {
  return h("div", { class: "row" }, stateChip(w.completion),
    h("div", { class: "grow" }, h("a", { class: "title", href: `#/item/${w.work_item_id}` }, w.title),
      h("div", { class: "muted" }, [w.project_name, w.completion.claimed_by && t("claimed_by", { who: w.completion.claimed_by })]
        .filter(Boolean).join(" · "))),
    chip(t("needs_decision"), "warn"));
}

// ------------------------------------------------------------------ router
const NAV = [["home", "nav_home"], ["projects", "nav_projects"], ["sessions", "nav_sessions"], ["delivery", "nav_delivery"],
  ["operations", "nav_operations"], ["settings", "nav_settings"]];
let teardown = null;
let generation = 0;
async function route() {
  const mine = ++generation;
  if (teardown) { teardown(); teardown = null; }
  freshPage();
  const [name, ...rest] = (location.hash.replace(/^#\//, "") || "home").split("/").map(decodeURIComponent);
  document.getElementById("nav").replaceChildren(...NAV.map(([k, label]) =>
    h("a", { href: `#/${k}`, class: name === k ? "on" : "" }, t(label))));
  const main = document.getElementById("main");
  main.replaceChildren();
  if (!state.token && name !== "settings") { main.append(h("p", { class: "note" }, t("need_token"))); viewSettings(main); return; }
  const views = { home: viewHome, projects: viewProjects, project: viewProject, item: viewWorkItem, sessions: viewSessions,
    delivery: viewDelivery, operations: viewOperations, session: viewSession, op: viewOperation, settings: viewSettings };
  const off = await (views[name] || viewHome)(main, ...rest);
  if (mine !== generation) { if (off) off(); return; } // the user navigated away while this view loaded
  teardown = off || null;
}

async function start() {
  state.token = loadToken();
  if (state.token) {
    try { state.caps = await api("GET", "/capabilities"); }
    catch { state.token = null; }
  }
  try { state.lastEvent = (await api("GET", "/events?limit=0")).head_cursor; } catch { /* not connected yet */ }
  window.addEventListener("hashchange", route);
  route();
  streamEvents();
}
start();
