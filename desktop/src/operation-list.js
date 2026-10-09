// Refresh the loaded window through central cursors. No counts imply a global total.
export function operationList({h, t, api, guard, row, statuses}) {
  let rows = [], before = null, pages = 1, queue = Promise.resolve(), pending = 0, failed = false;
  const list = h("div", {class: "panel", "data-operation-list": ""}), count = h("p", {class: "muted", "data-operation-count": ""}),
    status = h("div", {role: "status"});
  const current = () => {try {guard(); return true;} catch {return false;}};
  const update = () => {more.hidden = before === null; more.disabled = pending > 0 || failed; refresh.disabled = pending > 0;};
  const more = h("button", {class: "secondary", onclick: () => load(true).catch(() => {})}, t("operations_more"));
  const refresh = h("button", {class: "secondary", onclick: () => load().catch(() => {})}, t("refresh"));
  const box = h("div", {}, count, list, status, h("div", {class: "actions"}, more, refresh));
  function load(append = false) {
    pending++; update();
    const job = queue.catch(() => {}).then(async () => {
      guard(); if (append && before === null) return;
      const first = [...list.children].find(el => el.getBoundingClientRect().bottom >= 0);
      const anchor = first?.dataset.operationId, top = first?.getBoundingClientRect().top;
      let next = append ? before : null, candidate = append ? [...rows] : [], read = 0;
      const targetPages = append ? 1 : pages;
      for (let i = 0; i < targetPages; i++) {
        const params = new URLSearchParams({limit: "100"});
        if (statuses) params.set("status", statuses);
        if (next !== null) params.set("before", String(next));
        const result = await api("GET", "/operations?" + params); guard();
        if (!Array.isArray(result.operations) || result.operations.some(op => !/^op_[0-9a-f]{32}$/.test(op?.operation_id)) ||
            result.next_before !== null && result.next_before !== undefined &&
            (typeof result.next_before !== "number" || !Number.isFinite(result.next_before) || result.next_before <= 0 ||
              next !== null && result.next_before >= next || result.operations.length === 0)) throw new Error(t("operations_invalid_page"));
        candidate.push(...result.operations); read++; next = result.next_before ?? null;
        if (next === null) break;
      }
      guard(); rows = [...new Map(candidate.map(op => [op.operation_id, op])).values()];
      pages = append ? pages + read : read; before = next; failed = false;
      list.replaceChildren(...(rows.length ? rows.map(op => {const el = row(op); el.dataset.operationId = op.operation_id; return el;}) :
        [h("p", {class: "muted"}, t("operations_empty"))]));
      count.textContent = t("operations_loaded", {count: rows.length}); status.replaceChildren();
      const restored = [...list.children].find(el => el.dataset.operationId === anchor);
      if (restored && top !== undefined) window.scrollBy(0, restored.getBoundingClientRect().top - top);
    }).catch(error => {
      if (current()) {failed = true; status.replaceChildren(h("p", {class: "error"}, error.message));}
      throw error;
    }).finally(() => {pending--; if (current()) update();});
    queue = job; return job;
  }
  update(); return {box, load};
}
