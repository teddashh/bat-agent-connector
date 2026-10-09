import {renderMessage} from "./message-format.js";

// This is view-local reading state, never a central event cursor or read receipt.
export function conversationPanel({h, t, when, guard}) {
  const viewport = h("div", {class: "conversation-scroll", tabindex: "0", role: "region", "aria-label": t("messages")});
  const status = h("span", {class: "muted", role: "status"}), fallback = h("div", {class: "conversation-copy"});
  const notice = h("p", {class: "muted", role: "status", hidden: true}, t("message_anchor_missing"));
  const latest = h("button", {class: "mini", type: "button", hidden: true, onclick: () => {
    viewport.scrollTop = viewport.scrollHeight; notice.hidden = true; indicator();
  }}, t("message_latest"));
  const box = h("section", {class: "panel conversation"},
    h("div", {class: "muted"}, t("message_window")), notice, viewport,
    h("div", {class: "conversation-toolbar"}, status, latest), fallback);
  let rows = new Map(), initialized = false, disposed = false, copyAttempt = 0;
  const alive = () => {if (disposed) return false; try {guard(); return true;} catch {return false;}};
  const atBottom = () => viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight <= 48;
  const indicator = () => {latest.hidden = atBottom();};
  viewport.addEventListener("scroll", indicator, {passive: true});
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
  const update = messages => {
    if (!alive()) return;
    const top = viewport.getBoundingClientRect().top;
    const anchor = [...rows.entries()].find(([, row]) => row.node.getBoundingClientRect().bottom > top);
    const selection = window.getSelection();
    const readingSelection = selection && !selection.isCollapsed && viewport.contains(selection.anchorNode);
    const follow = !initialized || atBottom() && !readingSelection;
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
    rows = next; initialized = true; indicator();
  };
  return {box, update, dispose() {disposed = true; viewport.removeEventListener("scroll", indicator);}};
}
