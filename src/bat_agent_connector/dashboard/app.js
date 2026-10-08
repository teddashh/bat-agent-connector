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
function keyFor(scope) {
  // One idempotency key per draft: a retry of the same draft reuses it, so the action happens once.
  const k = `batc.key.${scope}`;
  try {
    let v = localStorage.getItem(k);
    if (!v) { v = crypto.randomUUID(); localStorage.setItem(k, v); }
    return v;
  } catch { return crypto.randomUUID(); }
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
  const key = keyFor(scope);
  try {
    const out = await api("POST", "/operations?wait=3", request, key);
    const done = ["succeeded", "failed", "cancelled"].includes(out.operation.status);
    if (done) dropKey(scope);
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
        const [sessions, ops, hosts] = await Promise.all([
          api("GET", "/sessions?attention=true&limit=50"),
          api("GET", "/operations?status=needs_attention,uncertain&limit=50"),
          api("GET", "/hosts")]);
        const bad = hosts.hosts.filter(x => x.stale);
        const rows = [
          ...bad.map(x => h("div", { class: "row" }, h("span", { class: "light bad" }),
            h("div", { class: "grow" }, h("div", { class: "title" }, `${t("unreachable_hosts")}: ${x.host}`),
              h("div", { class: "muted" }, x.error || t("stale_reason_" + x.stale_reason))))),
          ...sessions.sessions.map(sessionRow), ...ops.operations.map(opRow)];
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
  let row;
  try { row = (await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}`)).session; }
  catch (e) { head.replaceChildren(errorBox(e)); return; }
  head.replaceChildren(h("h1", {}, row.title || sid), h("div", { class: "actions" }, ...sessionBadges(row)),
    h("dl", { class: "kv" },
      h("dt", {}, t("host")), h("dd", {}, row.host), h("dt", {}, t("workspace")), h("dd", {}, row.workspace || ""),
      h("dt", {}, "Session"), h("dd", {}, h("code", {}, row.session_id)),
      h("dt", {}, t("agent")), h("dd", {}, [row.agent_kind, row.model].filter(Boolean).join(" · ")),
      h("dt", {}, "Provenance"), h("dd", {}, t("provenance_" + row.provenance)),
      h("dt", {}, t("observed")), h("dd", {}, when(row.observed_at))));
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
  const list = h("div", {});
  const status = h("div", { class: "muted" });
  // A checkpoint never changes, so its row is built once: a reload on a new event keeps an open form and its draft.
  const rows = new Map();
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
    const form = h("div", { hidden: true }, instr, h("div", { class: "actions" }, agent, go), out);
    return h("div", { class: "row" },
      h("div", { class: "grow" },
        h("div", { class: "title" }, h("code", {}, cp.commit_sha.slice(0, 12)), " ", cp.branch || ""),
        h("div", { class: "muted" }, [when(epoch(cp.captured_at)), cp.actor,
          t("excerpt_count", { n: cp.excerpt_messages })].join(" · ")),
        cp.dirty ? h("div", { class: "error" }, t("dirty_warning", { n: cp.dirty })) : null, form),
      h("button", { class: "secondary", disabled: !can, title: can ? null : t("checkpoint_unavailable"),
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
  const create = h("button", { class: "secondary", onclick: async () => {
    create.disabled = true;
    try {
      const op = await submit("checkpoint.create", { host, session_id: sid }, { last_n: 20 }, {}, `checkpoint.${host}.${sid}`);
      status.replaceChildren(...[opStatus(op), op.error_code ? chip(op.error_code, "bad") : null,
        op.status_reason].filter(Boolean).flatMap(x => [x, " "]));
      await load();
    } catch (e) { status.replaceChildren(errorBox(e)); }
    create.disabled = false;
  } }, t("create_checkpoint"));
  const box = h("div", { class: "panel" }, h("h2", {}, t("checkpoints")), h("p", { class: "muted" }, t("checkpoint_help")),
    can ? null : h("p", { class: "muted" }, t("checkpoint_unavailable")), h("div", { class: "actions" }, create), status, list);
  return { box, load };
}

async function viewDelivery(main) {
  const repo = h("input", { placeholder: "owner/name", value: sessionStorage.getItem("batc.repo") || "" });
  const num = h("input", { placeholder: "123", inputmode: "numeric", size: 6, value: sessionStorage.getItem("batc.pr") || "" });
  const card = h("div", { class: "panel" });
  main.append(h("h1", {}, t("nav_delivery")),
    h("div", { class: "filters" }, repo, num, h("button", { class: "primary", onclick: () => load() }, t("load_pr"))), card);
  const caps = state.caps || {};
  if (!repo.value && caps.repositories?.length) repo.value = caps.repositories[0].repository;
  const load = async () => {
    sessionStorage.setItem("batc.repo", repo.value); sessionStorage.setItem("batc.pr", num.value);
    if (!repo.value || !/^\d+$/.test(num.value)) return;
    card.replaceChildren(h("p", { class: "muted" }, t("loading")));
    try {
      const pr = (await api("GET", `/repositories/${repo.value}/pulls/${num.value}`)).pull_request;
      const status = h("div", {});
      const target = { repository: pr.repository, pull_number: Number(pr.pull_number) };
      const pre = { expected_head_sha: pr.head_sha };
      const run = async (action, extra, scope) => {
        try {
          const op = await submit(action, { ...target, ...extra.target }, extra.params || {}, extra.pre ?? pre, scope);
          status.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
        } catch (e) { status.replaceChildren(errorBox(e)); }
      };
      const blocked = pr.state !== "open" || pr.draft || pr.merged;
      const buttons = [h("button", { class: "primary", disabled: blocked || !pr.merge.allowed,
        onclick: () => run("github.pr.merge", { params: { method: pr.merge.default_method } }, `merge.${pr.repository}.${pr.pull_number}.${pr.head_sha}`) }, t("merge"))];
      for (const r of pr.recipes) {
        buttons.push(h("button", { class: "secondary", disabled: blocked,
          onclick: () => run("delivery.merge_and_deploy", { target: { recipe: r.name }, params: { method: pr.merge.default_method } },
            `merge_deploy.${pr.repository}.${pr.pull_number}.${pr.head_sha}.${r.name}`) }, t("merge_and_deploy_to", { env: r.environment })));
        if (pr.merged && pr.merge_commit_sha) buttons.push(h("button", { class: "secondary",
          onclick: async () => {
            try {
              const op = await submit("deployment.start", { recipe: r.name }, { source_sha: pr.merge_commit_sha }, {},
                `deploy.${r.name}.${pr.merge_commit_sha}`);
              status.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
            } catch (e) { status.replaceChildren(errorBox(e)); }
          } }, t("deploy_to", { env: r.environment })));
      }
      card.replaceChildren(
        h("h2", {}, h("a", { href: pr.html_url, target: "_blank", rel: "noopener" }, `#${pr.pull_number} ${pr.title || ""}`)),
        h("dl", { class: "kv" },
          h("dt", {}, t("head")), h("dd", {}, h("code", {}, `${pr.head_ref} @ ${pr.head_sha}`)),
          h("dt", {}, t("base")), h("dd", {}, h("code", {}, `${pr.base_ref} @ ${pr.base_sha}`)),
          h("dt", {}, t("mergeable")), h("dd", {}, `${pr.state}${pr.draft ? " · draft" : ""} · ${pr.mergeable_state || "?"}`),
          h("dt", {}, t("checks")), h("dd", {}, t("checks_summary", pr.checks)),
          pr.merged ? [h("dt", {}, t("merged_sha")), h("dd", {}, h("code", {}, pr.merge_commit_sha))] : null),
        h("div", { class: "actions" }, ...buttons), status);
    } catch (e) { card.replaceChildren(errorBox(e)); }
  };
  await load();
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
      const op = (await api("GET", `/operations/${id}`)).operation;
      const refs = op.external_refs || {};
      const retry = refs.merged_sha && op.action === "delivery.merge_and_deploy" && op.status === "failed"
        ? h("button", { class: "primary", onclick: async () => {
          try {
            const o = await submit("deployment.start", { recipe: op.target.recipe }, { source_sha: refs.merged_sha }, {},
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
      const cancel = !["succeeded", "failed", "cancelled"].includes(op.status)
        ? h("button", { class: "danger", onclick: async () => {
          try { await api("POST", `/operations/${id}/cancel`, {}); render(); } catch (e) { panel.append(errorBox(e)); }
        } }, t("cancel"))
        : null;
      panel.replaceChildren(h("h1", {}, op.action),
        h("p", { class: "op-status" }, opStatus(op), " ", op.error_code ? chip(op.error_code, "bad") : null),
        h("dl", { class: "kv" },
          h("dt", {}, t("actor")), h("dd", {}, `${op.actor} (${op.entry})`),
          h("dt", {}, t("created")), h("dd", {}, when(epoch(op.created_at))),
          op.status_reason ? [h("dt", {}, t("reason")), h("dd", {}, op.status_reason)] : null,
          h("dt", {}, "Target"), h("dd", {}, h("code", {}, JSON.stringify(op.target))),
          Object.keys(refs).length ? [h("dt", {}, "Refs"), h("dd", {}, h("code", {}, JSON.stringify(refs)))] : null,
          op.result ? [h("dt", {}, "Result"), h("dd", {}, h("code", {}, JSON.stringify(op.result)))] : null),
        h("h2", {}, t("steps")),
        ...op.steps.map(s => h("div", { class: "row" }, h("div", { class: "grow" }, s.name),
          h("span", { class: `status-${s.status}` }, s.status), s.error ? chip(s.error.code || t("error"), "bad") : null)),
        h("div", { class: "actions" }, opened, resume, retry, cancel));
    } catch (e) { panel.replaceChildren(errorBox(e)); }
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

// ------------------------------------------------------------------ router
const NAV = [["home", "nav_home"], ["sessions", "nav_sessions"], ["delivery", "nav_delivery"],
  ["operations", "nav_operations"], ["settings", "nav_settings"]];
let teardown = null;
let generation = 0;
async function route() {
  const mine = ++generation;
  if (teardown) { teardown(); teardown = null; }
  const [name, ...rest] = (location.hash.replace(/^#\//, "") || "home").split("/").map(decodeURIComponent);
  document.getElementById("nav").replaceChildren(...NAV.map(([k, label]) =>
    h("a", { href: `#/${k}`, class: name === k ? "on" : "" }, t(label))));
  const main = document.getElementById("main");
  main.replaceChildren();
  if (!state.token && name !== "settings") { main.append(h("p", { class: "note" }, t("need_token"))); viewSettings(main); return; }
  const views = { home: viewHome, sessions: viewSessions, delivery: viewDelivery, operations: viewOperations,
    session: viewSession, op: viewOperation, settings: viewSettings };
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
