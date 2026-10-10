import {renderMessage} from "./message-format.js";

// Scrolling never marks messages read. Personal receipts require an explicit action.
export function conversationPanel({h, t, when, guard, readingActions = null}) {
  const viewport = h("div", {class: "conversation-scroll", tabindex: "0", role: "region", "aria-label": t("messages")});
  const status = h("span", {class: "muted", role: "status"}), fallback = h("div", {class: "conversation-copy"});
  const notice = h("p", {class: "muted", role: "status", hidden: true}, t("message_anchor_missing"));
  const latest = h("button", {class: "mini", type: "button", hidden: true, onclick: () => {
    if (olderWindow && readingActions) {run(() => readingActions.latest()); return;}
    viewport.scrollTop = viewport.scrollHeight; notice.hidden = true; indicator();
  }}, t("message_latest"));
  const progress = h("span", {class: "muted", role: "status", "data-conversation-reading": ""});
  const mark = h("button", {class: "mini", type: "button", onclick: () => {
    const messages = visible().filter(row => row.reading?.can_mark && row.reading?.unread)
      .map(row => ({message_id: row.id, revision: row.reading.revision}));
    if (messages.length) run(() => readingActions.mark(messages));
  }}, t("conversation_mark"));
  const remember = h("button", {class: "mini", type: "button", onclick: () => {
    const row = visible()[0];
    if (row?.reading) run(() => readingActions.remember({message_id: row.id, revision: row.reading.revision,
      offset: Math.round(row.node.getBoundingClientRect().top - viewport.getBoundingClientRect().top)}, reading?.position?.version || 0));
  }}, t("conversation_remember"));
  const older = h("button", {class: "mini", type: "button", hidden: true,
    onclick: () => run(() => readingActions.older())}, t("conversation_older"));
  const box = h("section", {class: "panel conversation"},
    h("div", {class: "muted"}, t("message_window")), notice, viewport,
    h("div", {class: "conversation-toolbar"}, status, latest),
    readingActions ? h("div", {class: "actions"}, progress, mark, remember, older) : null, fallback);
  let rows = new Map(), initialized = false, disposed = false, copyAttempt = 0, reading = null, busy = false, olderWindow = false;
  const alive = () => {if (disposed) return false; try {guard(); return true;} catch {return false;}};
  const atBottom = () => viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight <= 48;
  const visible = () => {
    if (document.visibilityState !== "visible") return [];
    const bounds = viewport.getBoundingClientRect(), top = Math.max(bounds.top, 0), bottom = Math.min(bounds.bottom, innerHeight);
    return [...rows.values()].filter(row => {
      const rect = row.node.getBoundingClientRect();
      return bottom > top && rect.bottom > top && rect.top < bottom;
    });
  };
  const indicator = () => {
    latest.hidden = !olderWindow && atBottom();
    if (!readingActions) return;
    mark.disabled = busy || !visible().some(row => row.reading?.can_mark && row.reading?.unread);
    remember.disabled = busy || !visible()[0]?.reading;
    older.disabled = busy;
  };
  const run = async action => {
    if (!alive() || busy) return;
    busy = true; indicator();
    try {await action(); if (alive()) status.textContent = t("conversation_saved");}
    catch (error) {if (alive()) status.textContent = error.message || String(error);}
    finally {busy = false; if (alive()) indicator();}
  };
  viewport.addEventListener("scroll", indicator, {passive: true});
  window.addEventListener("scroll", indicator, {passive: true});
  window.addEventListener("resize", indicator);
  const copy = async text => {
    if (!alive()) return;
    const attempt = ++copyAttempt;
    status.textContent = ""; fallback.replaceChildren();
    try {await navigator.clipboard.writeText(text); if (alive() && attempt === copyAttempt) status.textContent = t("message_copied");}
    catch {
      if (!alive() || attempt !== copyAttempt) return;
      const input = h("textarea", {readonly: true, "aria-label": t("message_copy_source")}, text);
      // Textarea.value normalizes CRLF. A whole-source manual copy still uses the
      // original string; partial selections keep the browser's normal behavior.
      input.addEventListener("copy", event => {
        if (alive() && event.clipboardData && input.selectionStart === 0 && input.selectionEnd === input.value.length) {
          event.clipboardData.setData("text/plain", text); event.preventDefault();
        }
      });
      fallback.replaceChildren(h("p", {class: "muted"}, t("message_copy_manual")), input,
        h("button", {class: "mini", type: "button", onclick: () => fallback.replaceChildren()}, t("cancel")));
      input.focus(); input.select();
    }
  };
  const update = (messages, state = null) => {
    if (!alive()) return;
    const top = viewport.getBoundingClientRect().top;
    const anchor = [...rows.entries()].find(([, row]) => row.node.getBoundingClientRect().bottom > top);
    const selection = window.getSelection();
    const readingSelection = selection && !selection.isCollapsed && viewport.contains(selection.anchorNode);
    const follow = !initialized || !state?.preserve && atBottom() && !readingSelection;
    const offset = anchor ? anchor[1].node.getBoundingClientRect().top - top : 0, scrollTop = viewport.scrollTop;
    const next = new Map(), occurrences = new Map();
    for (const message of messages) {
      const text = typeof message.text === "string" ? message.text : "";
      const identity = JSON.stringify(message.id != null ? ["id", message.id] : ["text", message.role, message.ts, text]);
      const occurrence = occurrences.get(identity) || 0; occurrences.set(identity, occurrence + 1);
      const key = JSON.stringify([identity, occurrence]);
      let row = rows.get(key);
      if (!row) {
        row = {text: null, meta: null, body: h("div", {class: "message-body"}), who: h("span", {class: "who"})};
        row.node = h("article", {class: "msg"}, h("div", {class: "message-meta"}, row.who,
          h("button", {class: "mini", type: "button", onclick: () => copy(row.text)}, t("message_copy"))), row.body);
      }
      const meta = `${message.role || ""} · ${when(message.ts)}`;
      if (row.meta !== meta) {row.who.textContent = meta; row.meta = meta;}
      row.node.className = `msg${message.role === "user" ? " user" : ""}`;
      row.id = message.id; row.reading = message.reading;
      row.node.dataset.messageId = typeof message.id === "string" ? message.id : "";
      if (row.text !== text) {row.body.replaceChildren(...renderMessage(h, t, text, copy)); row.text = text;}
      next.set(key, row);
    }
    // Keep unchanged nodes in place so refresh does not erase focus or selected text.
    const retained = new Set([...next.values()].map(row => row.node));
    for (const node of [...viewport.childNodes]) if (!retained.has(node)) node.remove();
    let position = viewport.firstChild;
    for (const row of next.values()) {
      if (row.node === position) position = position.nextSibling;
      else viewport.insertBefore(row.node, position);
    }
    while (position) {const old = position; position = old.nextSibling; old.remove();}
    if (!next.size) viewport.replaceChildren(h("p", {class: "muted"}, t("no_messages")));
    if (follow) {viewport.scrollTop = viewport.scrollHeight; notice.hidden = true;}
    else if (anchor && next.has(anchor[0])) viewport.scrollTop += next.get(anchor[0]).node.getBoundingClientRect().top - viewport.getBoundingClientRect().top - offset;
    else {viewport.scrollTop = scrollTop; if (anchor) notice.hidden = false;}
    rows = next;
    if (state?.restore) {
      const row = [...rows.values()].find(row => row.id === state.restore.message_id);
      if (row) {
        viewport.scrollTop += row.node.getBoundingClientRect().top - viewport.getBoundingClientRect().top - state.restore.offset;
        notice.hidden = false; notice.textContent = t("conversation_restored");
      } else {notice.hidden = false; notice.textContent = t("message_anchor_missing");}
    }
    if (state?.latest) {viewport.scrollTop = viewport.scrollHeight; notice.hidden = true;}
    if (readingActions && state) {
      reading = state.reading; older.hidden = state.next_offset == null; olderWindow = Boolean(state.olderWindow);
      progress.textContent = reading?.unread_count == null ? t("conversation_unknown")
        : t(reading.complete ? "conversation_unread" : "conversation_partial", {count: reading.unread_count});
      progress.title = t("conversation_count_note");
    }
    initialized = true; indicator();
  };
  return {box, update, dispose() {
    disposed = true; viewport.removeEventListener("scroll", indicator);
    window.removeEventListener("scroll", indicator); window.removeEventListener("resize", indicator);
  }};
}
