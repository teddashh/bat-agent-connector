// Guided configuration of the owned central. Secrets stay in input memory until staged.
// Durable operations retain their exact request/key; reopening never starts a new intent.
export function managedSetupPanel({h, t, api, guard, namespace, errorBox, opStatus, onConfigured}) {
  const key = `batc.managed.setup.${namespace}`;
  let saved = {}, snapshot = null, busy = false, disposed = false, operation = null;
  try { saved = JSON.parse(localStorage.getItem(key) || "{}"); } catch { /* fresh draft */ }
  if (!saved || typeof saved !== "object" || Array.isArray(saved)) saved = {};
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
    return value;
  }
  const validIntent = intent => intent && typeof intent.key === "string" && intent.key.length <= 200 &&
    ["setup.host", "setup.repository"].includes(intent.request?.action) &&
    /^[0-9a-f]{64}$/.test(intent.request?.preconditions?.config_revision) &&
    intent.request?.params && typeof intent.request.params === "object" &&
    intent.request?.target && Object.keys(intent.request.target).length === 1 &&
    typeof intent.request.target[intent.request.action === "setup.host" ? "host" : "repository"] === "string" &&
    (!intent.operation_id || /^op_[0-9a-f]{32}$/.test(intent.operation_id));
  const damaged = !!saved.intent && !validIntent(saved.intent);
  const alive = () => {try {guard(); return !disposed;} catch {return false;}};
  const persist = () => {guard(); localStorage.setItem(key, JSON.stringify(saved));};
  const terminal = () => ["succeeded", "failed", "cancelled"].includes(operation?.status);
  const message = h("div", {role: "status"}), summary = h("div"), receipt = h("div");
  const unsaved = h("span", {class: "chip", hidden: true}, t("setup_unsaved"));
  const fields = new Map();
  const input = (name, label, options = {}) => {
    const secret = options.type === "password";
    const node = h("input", {autocomplete: "off", maxlength: secret ? 4096 : 1024, ...options});
    if (!secret) node.value = typeof saved[name] === "string" ? saved[name] : "";
    node.addEventListener("input", () => {
      if (!alive()) return;
      if (!secret) {saved[name] = node.value; try {persist();} catch (error) {message.replaceChildren(errorBox(error));}}
      unsaved.hidden = false;
    });
    fields.set(name, node);
    return h("label", {}, t(label), node);
  };
  const checkbox = (name, label) => {
    const node = h("input", {type: "checkbox"}); node.checked = saved[name] === true;
    node.addEventListener("change", () => {if (!alive()) return; saved[name] = node.checked; persist(); unsaved.hidden = false;});
    fields.set(name, node);
    return h("label", {}, node, " ", t(label));
  };
  const profile = h("select", {"aria-label": t("setup_profile")});
  profile.addEventListener("change", () => {
    if (!alive() || saved.intent) return;
    const selected = snapshot?.profiles?.find(row => row.id === profile.value);
    saved.import_profile_id = selected?.id || "";
    if (selected) for (const name of ["url", "fingerprint", "profile_id"]) {
      fields.get(name).value = selected[name] || ""; saved[name] = fields.get(name).value;
    }
    persist(); unsaved.hidden = false;
  });
  const hostForm = h("form", {"data-setup-host": "", onsubmit: event => {event.preventDefault(); run("host");}},
    h("h3", {}, t("setup_host_title")), h("p", {class: "muted"}, t("setup_host_help")),
    h("label", {}, t("setup_profile"), profile),
    h("div", {class: "capture-fields"}, input("host", "setup_host_name", {required: true, maxlength: 64}),
      input("url", "setup_host_url", {type: "url", required: true, placeholder: "wss://host:9876/"}),
      input("fingerprint", "setup_fingerprint", {required: true}),
      input("profile_id", "setup_workspace_profile", {placeholder: "default"}),
      input("bat_secret", "setup_bat_token", {type: "password"})),
    h("p", {class: "muted"}, t("setup_trust_help")),
    h("details", {}, h("summary", {}, t("setup_managed_work")),
      checkbox("writes", "setup_allow_messages"), checkbox("orchestrate", "setup_allow_start"),
      h("div", {class: "capture-fields"}, input("managed_roots", "setup_managed_roots"), input("ssh_alias", "setup_ssh_alias")),
      h("p", {class: "muted"}, t("setup_roots_help"))),
    h("button", {type: "submit", class: "primary"}, t("setup_save_host")));
  const repoForm = h("form", {"data-setup-repository": "", onsubmit: event => {event.preventDefault(); run("repository");}},
    h("h3", {}, t("setup_repository_title")), h("p", {class: "muted"}, t("setup_repository_help")),
    h("div", {class: "capture-fields"}, input("repository", "setup_repository", {required: true, placeholder: "owner/repository"}),
      input("repository_host", "setup_host_name", {required: true}), input("workspace_id", "setup_workspace_id", {required: true}),
      input("remote_url", "setup_remote_url", {required: true, placeholder: "git@github.com:owner/repository.git"}),
      input("github_secret", "setup_github_token", {type: "password"})),
    h("div", {class: "actions"}, checkbox("allow_integrate", "setup_allow_integrate"),
      checkbox("allow_merge", "setup_allow_merge"), checkbox("allow_pr_update", "setup_allow_pr_update")),
    h("button", {type: "button", class: "secondary", onclick: () => workspaces().catch(showError)}, t("setup_find_workspaces")),
    h("div", {"data-setup-workspaces": ""}),
    h("button", {type: "submit", class: "primary"}, t("setup_save_repository")));
  const refreshButton = h("button", {class: "secondary", onclick: () => refresh().catch(showError)}, t("setup_refresh"));
  const retry = h("button", {class: "secondary", hidden: true, onclick: () => recover().catch(showError)}, t("setup_recover"));
  const next = h("button", {class: "secondary", hidden: true, onclick: () => {
    if (!alive() || damaged || !terminal() && !saved.intent?.refused) return;
    saved.intent = null; operation = null; persist(); update(); refresh().catch(showError);
  }}, t("setup_next_change"));
  const box = h("section", {class: "panel managed-setup", "data-managed-setup": ""},
    h("h2", {}, t("setup_title"), " ", unsaved), h("p", {class: "muted"}, t("setup_resume_help")), summary,
    h("div", {class: "actions"}, refreshButton, retry, next), message, receipt,
    h("details", {open: true}, h("summary", {}, t("setup_host_title")), hostForm),
    h("details", {}, h("summary", {}, t("setup_repository_title")), repoForm),
    h("a", {href: "#/projects"}, t("setup_open_projects")));
  function showError(error) {if (alive()) {message.replaceChildren(errorBox(error)); update();}}
  function update() {
    if (!alive()) return;
    const locked = busy || !snapshot || !!saved.intent || snapshot.busy;
    for (const field of [...fields.values(), profile, ...box.querySelectorAll("button[type=submit]")]) field.disabled = !!locked;
    refreshButton.disabled = busy; retry.hidden = !saved.intent || terminal(); retry.disabled = busy;
    next.hidden = !saved.intent || !terminal() && !saved.intent.refused; next.disabled = busy || damaged;
    if (damaged) retry.disabled = true;
    receipt.replaceChildren();
    if (operation) receipt.append(opStatus(operation), " ", h("a", {href: `#/op/${operation.operation_id}`}, t("setup_operation")));
    else if (saved.intent) receipt.append(h("p", {class: "note"}, t("setup_uncertain")));
  }
  function accept(candidate) {
    const intent = saved.intent;
    if (!candidate || candidate.action !== intent.request.action ||
        !equal(candidate.target, intent.request.target) || !equal(candidate.params, intent.request.params) ||
        !equal(candidate.preconditions, intent.request.preconditions) ||
        candidate.idempotency_key && candidate.idempotency_key !== intent.key ||
        intent.operation_id && candidate.operation_id !== intent.operation_id) throw Error(t("setup_receipt_mismatch"));
    operation = candidate; intent.operation_id = candidate.operation_id; persist();
    if (candidate.status === "succeeded") {unsaved.hidden = true; Promise.resolve(onConfigured?.()).catch(showError);}
    update();
  }
  async function sendOriginal() {
    const intent = saved.intent;
    const result = intent.operation_id ? await api("GET", `/operations/${encodeURIComponent(intent.operation_id)}`)
      : await api("POST", "/operations?wait=3", intent.request, intent.key);
    guard(); accept(result.operation);
  }
  async function recover() {
    if (!alive() || busy || !saved.intent || damaged || saved.intent.refused) return;
    busy = true; update();
    try {await sendOriginal(); await refresh();}
    finally {busy = false; if (alive()) update();}
  }
  async function run(kind) {
    const form = kind === "host" ? hostForm : repoForm;
    if (!alive() || busy || !snapshot || saved.intent || !form.reportValidity()) return;
    busy = true; update(); message.replaceChildren();
    try {
      persist(); // refuse to submit an intent that cannot survive reload
      const value = name => fields.get(name).value.trim();
      const checked = name => fields.get(name).checked;
      const tokenField = fields.get(kind === "host" ? "bat_secret" : "github_secret");
      let secretRef;
      if (tokenField.value) {
        const staged = await api("POST", "/managed/setup/secrets", {kind: kind === "host" ? "bat" : "github", value: tokenField.value});
        guard(); secretRef = staged.secret_ref; tokenField.value = "";
      }
      const params = kind === "host" ? {url: value("url"), fingerprint: value("fingerprint"),
        profile_id: value("profile_id") || "default", writes: checked("writes"), orchestrate: checked("orchestrate"),
        managed_roots: value("managed_roots").split(/\r?\n|;/).map(item => item.trim()).filter(Boolean),
        ...(value("ssh_alias") ? {ssh_alias: value("ssh_alias")} : {}),
        ...(!secretRef && saved.import_profile_id ? {import_profile_id: saved.import_profile_id} : {})}
        : {host: value("repository_host"), workspace_id: value("workspace_id"), remote_url: value("remote_url"),
          allow_integrate: checked("allow_integrate"), allow_merge: checked("allow_merge"), allow_pr_update: checked("allow_pr_update")};
      if (secretRef) params.secret_ref = secretRef;
      saved.intent = {key: crypto.randomUUID(), request: {action: `setup.${kind}`,
        target: kind === "host" ? {host: value("host")} : {repository: value("repository")}, params,
        preconditions: {config_revision: snapshot.revision}}};
      persist(); await sendOriginal(); await refresh();
    } catch (error) {
      if (alive() && saved.intent && !saved.intent.operation_id &&
          ["CONFIGURATION_CHANGED", "SETUP_BUSY", "PRECONDITION_REQUIRED"].includes(error.code)) {
        saved.intent.refused = error.code; persist();
      }
      showError(error);
    }
    finally {busy = false; if (alive()) update();}
  }
  async function workspaces() {
    const host = fields.get("repository_host").value.trim();
    if (!host || busy || !alive()) return;
    const result = await api("GET", `/workspaces?host=${encodeURIComponent(host)}`); guard();
    const rows = result.workspaces || [];
    box.querySelector("[data-setup-workspaces]").replaceChildren(...rows.map(row =>
      h("button", {class: "secondary", type: "button", onclick: () => {
        if (!alive() || saved.intent) return;
        fields.get("workspace_id").value = row.workspace_id || row.id;
        saved.workspace_id = fields.get("workspace_id").value; persist(); unsaved.hidden = false;
      }}, `${row.name || row.title || row.workspace_id || row.id} · ${row.workspace_id || row.id}`)));
  }
  async function refresh() {
    const result = await api("GET", "/managed/setup"); guard();
    if (disposed) return;
    snapshot = result;
    summary.replaceChildren(h("p", {}, t("setup_counts", {hosts: result.hosts?.length || 0, repositories: result.repositories?.length || 0})),
      ...(result.hosts || []).map(row => h("p", {}, h("strong", {}, row.name), " · ",
        t(row.connected ? "setup_connected" : "setup_unverified"), " · ", row.url)),
      ...[result.busy ? h("p", {class: "note warn"}, t("setup_busy")) : null].filter(Boolean),
      ...[result.profiles_error ? h("p", {class: "muted"}, t("setup_profiles_unavailable")) : null].filter(Boolean));
    profile.replaceChildren(h("option", {value: ""}, t("setup_manual_profile")),
      ...(result.profiles || []).map(row => h("option", {value: row.id}, row.name || row.id)));
    profile.value = saved.import_profile_id || "";
    update();
  }
  return {box, async load() {try {await refresh(); if (saved.intent?.operation_id) await recover();} catch (error) {showError(error);}},
    dispose() {disposed = true; for (const name of ["bat_secret", "github_secret"]) fields.get(name).value = "";}};
}
