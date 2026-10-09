import {updateRequest} from "./transport/index.ts";

export async function mountUpdates(main, {h, t}) {
  const panel = h("section", {class: "panel", "aria-label": t("update_title")});
  const content = h("div"), message = h("p", {role: "status", class: "muted"});
  panel.append(h("h2", {}, t("update_title")), content, message); main.append(panel);
  let disposed = false, busy = false, readable = false, value;
  const active = () => !disposed && panel.isConnected;
  const phases = new Set(["idle", "checking", "available", "up_to_date", "check_failed", "downloading", "download_failed", "verified", "stopping_fleet", "installation_unknown"]);
  const render = () => {
    if (!active()) return;
    if (!value) {
      content.replaceChildren(h("button", {class: "secondary", disabled: busy, onclick: () => request({action: "status"})}, t("update_read")));
      return;
    }
    const blocked = busy || !readable || !value.available || ["checking", "downloading", "stopping_fleet", "installation_unknown"].includes(value.phase);
    const candidate = value.candidate;
    content.replaceChildren(
      h("p", {}, t("update_current", {version: value.current_version})),
      h("p", {class: "muted"}, !value.available ? t(value.code === "UPDATE_PLATFORM_UNSUPPORTED" ? "update_platform" : "update_unsigned") : t("update_phase_" + value.phase)),
      ...(candidate ? [h("dl", {class: "kv"}, h("dt", {}, t("update_candidate")), h("dd", {}, candidate.version),
        h("dt", {}, t("pub_sha")), h("dd", {class: "mono"}, candidate.source_sha))] : []),
      ...(value.installation ? [h("p", {}, t("update_requested", {version: value.installation.to_version}))] : []),
      ...(value.available ? [h("p", {class: "muted"}, t("update_help")), h("div", {class: "actions"},
        h("button", {class: candidate ? "secondary" : "primary", disabled: blocked, onclick: () => request({action: "check"})}, t("update_check")),
        ...(candidate ? [h("button", {class: "primary", disabled: blocked || value.phase === "verified", onclick: () => request({action: "download", candidate_id: candidate.candidate_id})}, t("update_download")),
          h("button", {class: value.phase === "verified" ? "primary" : "secondary", disabled: blocked || value.phase !== "verified", onclick: () => request({action: "install", candidate_id: candidate.candidate_id})}, t("update_install"))] : []),
        h("button", {class: "secondary", disabled: busy, onclick: () => request({action: "status"})}, t("update_read")))] : []));
  };
  const request = async input => {
    if (busy || !active()) return;
    busy = true; readable = false; message.textContent = ""; render();
    try {
      const next = await updateRequest(input);
      if (!active()) return;
      if (!next || typeof next.current_version !== "string" || typeof next.available !== "boolean" || !phases.has(next.phase)
          || next.candidate && ["candidate_id", "version", "source_sha"].some(k => typeof next.candidate[k] !== "string")) throw new Error("UPDATE_STATUS_INVALID");
      value = next; readable = true;
      if (next.code && next.available && !next.installation) message.textContent = `${t("update_problem")} ${next.code}`;
    } catch {
      if (active()) message.textContent = t(input.action === "install" ? "update_unknown" : "update_read_failed");
    } finally {busy = false; render();}
  };
  await request({action: "status"});
  return () => {disposed = true; panel.remove();};
}
