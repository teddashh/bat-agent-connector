// Generated from desktop/src. Run: cd desktop && npm ci && npm run build:browser. Do not edit.
//#region \0rolldown/runtime.js
var __defProp = Object.defineProperty;
var __esmMin = (fn, res, err) => () => {
	if (err) throw err[0];
	try {
		return fn && (res = fn(fn = 0)), res;
	} catch (e) {
		throw err = [e], e;
	}
};
var __exportAll = (all, no_symbols) => {
	let target = {};
	for (var name in all) __defProp(target, name, {
		get: all[name],
		enumerable: true
	});
	if (!no_symbols) __defProp(target, Symbol.toStringTag, { value: "Module" });
	return target;
};
//#endregion
//#region src/state/sessions.js
var text$3 = (value) => typeof value === "string" ? value : "";
function workspaceGroup(session) {
	const host = text$3(session.host), id = text$3(session.workspace_id), name = text$3(session.workspace);
	return {
		key: JSON.stringify([
			host,
			id ? "id" : name ? "label" : "unknown",
			id || name
		]),
		host,
		id,
		name
	};
}
function groupedSessions(sessions) {
	const groups = new Map();
	for (const session of sessions) {
		const group = workspaceGroup(session);
		if (!groups.has(group.key)) groups.set(group.key, {
			...group,
			sessions: []
		});
		groups.get(group.key).sessions.push(session);
	}
	return [...groups.values()].sort((a, b) => a.host.localeCompare(b.host) || (a.name || a.id).localeCompare(b.name || b.id) || a.key.localeCompare(b.key));
}
function matchesSession(session, query) {
	const haystack = [
		session.title,
		session.session_id,
		session.host,
		session.workspace,
		session.workspace_id,
		session.agent_kind,
		session.model,
		session.worktree_branch,
		...Array.isArray(session.connector_metadata?.labels) ? session.connector_metadata.labels : []
	].map(text$3).join("\n").toLocaleLowerCase();
	return query.trim().toLocaleLowerCase().split(/\s+/).every((word) => haystack.includes(word));
}
function runtimeStale(session) {
	return Boolean(session.stale || session.fields_stale || session.state?.evidence?.activity?.stale);
}
function sessionActivity(session) {
	if (session.pending) return {
		key: "pending_" + session.pending.kind,
		tone: "stale"
	};
	if (session.state?.lifecycle === "ended") return {
		key: "obs_value_ended",
		tone: ""
	};
	if (session.gone_at || ["gone", "missing"].includes(session.state?.enumeration)) return {
		key: "sessions_not_seen",
		tone: "stale"
	};
	if (runtimeStale(session)) return {
		key: "sessions_stale",
		tone: "stale"
	};
	if (session.streaming === true) return {
		key: "obs_value_streaming",
		tone: "info"
	};
	if (session.streaming === false) return {
		key: "obs_value_not_streaming",
		tone: ""
	};
	return {
		key: "sessions_activity_unknown",
		tone: ""
	};
}
//#endregion
//#region src/workspace-nav.js
function workspaceNavigation({ h, t, api, guard, onEvents, namespace, errorBox }) {
	const key = `batc.tree.${namespace}`;
	let saved = [], hasPreference = false;
	try {
		const raw = sessionStorage.getItem(key);
		saved = JSON.parse(raw || "[]");
		hasPreference = raw !== null;
	} catch {}
	const expanded = new Set(Array.isArray(saved) ? saved : []), projects = new Map();
	let roots = [], disposed = false, serial = Promise.resolve(), selected = location.hash, revealProject = null;
	const status = h("div", {
		class: "workspace-tree-status",
		role: "status"
	});
	const tree = h("div", { class: "workspace-tree" });
	let sessionPages = 1, sessionsLoaded = false;
	const sessionRows = h("div", { class: "workspace-tree" });
	const more = h("button", {
		class: "mini",
		hidden: true,
		onclick: () => {
			sessionPages++;
			refresh().catch(() => {});
		}
	}, t("load_more"));
	const sessionTree = h("details", { class: "workspace-session-tree" }, h("summary", {}, t("nav_sessions")), sessionRows, more);
	const search = h("input", {
		type: "search",
		"aria-label": t("workspace_search"),
		placeholder: t("workspace_search")
	});
	const box = h("aside", {
		class: "workspace-nav",
		"aria-label": t("workspace_navigation")
	}, h("div", { class: "workspace-nav-heading" }, h("strong", {}, t("nav_projects")), h("a", {
		href: "#/projects",
		title: t("workspace_manage"),
		"aria-label": t("workspace_manage")
	}, "+")), search, status, h("div", { class: "workspace-tree-scroll" }, tree, sessionTree), h("div", { class: "workspace-nav-footer" }, h("a", { href: "#/sessions" }, t("workspace_all_sessions")), h("a", { href: "#/projects" }, t("workspace_manage"))));
	const alive = () => {
		guard();
		if (disposed) throw new Error("Navigation disposed");
	};
	const persist = () => {
		try {
			sessionStorage.setItem(key, JSON.stringify([...expanded]));
		} catch {}
	};
	const link = (href, label, state = null) => h("a", {
		href,
		class: "workspace-tree-link",
		"data-tree-key": href,
		"aria-current": selected === href ? "page" : null
	}, h("span", {
		class: `workspace-dot ${state?.tone || ""}`,
		"aria-hidden": "true"
	}), h("span", { class: "workspace-tree-label" }, label), state ? h("span", { class: "workspace-tree-state" }, t(state.key)) : null);
	const workLink = (pid, item) => link(`#/work/${[
		pid,
		item.kind,
		item.id
	].map(encodeURIComponent).join("/")}`, item.title || item.branch || item.action || item.id, sessionActivity(item.session || {}));
	const render = () => {
		if (disposed) return;
		const focus = tree.contains(document.activeElement) ? document.activeElement?.dataset.treeKey : null;
		const query = search.value.trim().toLocaleLowerCase();
		const matches = (text) => !query || String(text || "").toLocaleLowerCase().includes(query);
		const itemNodes = (items) => (items || []).flatMap((item) => {
			const children = itemNodes(item.children);
			if (!matches(item.title) && !children.length) return [];
			return [h("li", {}, link(`#/item/${encodeURIComponent(item.work_item_id)}`, item.title, {
				key: "wi_state_" + (item.completion?.display_state || item.state),
				tone: item.completion?.pending ? "stale" : ""
			}), children.length ? h("ul", {}, ...children) : null)];
		});
		const projectNodes = (items) => items.flatMap((project) => {
			const id = project.project_id, data = projects.get(id), children = projectNodes(project.children || []);
			const work = (data?.work || []).filter((item) => matches(item.title || item.branch || item.action || item.id));
			const items = itemNodes(data?.work_items);
			if (!matches(project.name) && !children.length && !work.length && !items.length) return [];
			const open = expanded.has(id) || Boolean(query);
			return [h("li", {}, h("div", { class: "workspace-project-row" }, h("button", {
				class: "workspace-tree-toggle",
				"data-tree-key": id,
				"aria-label": t(open ? "workspace_collapse" : "workspace_expand", { name: project.name }),
				"aria-expanded": String(open),
				onclick: () => {
					if (expanded.has(id)) expanded.delete(id);
					else expanded.add(id);
					persist();
					render();
					if (expanded.has(id)) refresh().catch(() => {});
				}
			}, open ? "▾" : "▸"), link(`#/project/${encodeURIComponent(id)}`, project.name), project.counts?.pending ? h("span", { class: "workspace-tree-state" }, t("workspace_needs_you")) : null), h("ul", { hidden: !open }, ...children, ...items, ...work.map((item) => h("li", {}, workLink(id, item))), !data ? h("li", { class: "muted workspace-tree-empty" }, t("workspace_expand_load")) : !children.length && !items.length && !work.length ? h("li", { class: "muted workspace-tree-empty" }, t("workspace_no_work")) : null))];
		});
		const nodes = projectNodes(roots);
		tree.replaceChildren(h("ul", {}, ...nodes));
		if (!nodes.length) tree.append(h("p", { class: "muted" }, t(query ? "workspace_no_match" : "no_projects")));
		if (focus) [...tree.querySelectorAll("[data-tree-key]")].find((node) => node.dataset.treeKey === focus)?.focus({ preventScroll: true });
		filterSessions();
	};
	const filterSessions = () => {
		const query = search.value.trim().toLocaleLowerCase();
		for (const group of sessionRows.querySelectorAll(":scope > div")) {
			for (const row of group.querySelectorAll("a")) row.hidden = Boolean(query) && !group.querySelector("p").textContent.toLocaleLowerCase().includes(query) && !row.textContent.toLocaleLowerCase().includes(query);
			group.hidden = [...group.querySelectorAll("a")].every((row) => row.hidden);
		}
	};
	const refresh = () => {
		const run = serial.catch(() => {}).then(async () => {
			alive();
			try {
				const data = await api("GET", "/projects");
				alive();
				roots = data.projects || [];
				if (!roots.length) projects.clear();
				if (!hasPreference && !expanded.size && roots.length) {
					expanded.add(roots[0].project_id);
					hasPreference = true;
					persist();
				}
				const ids = new Set();
				const walk = (list, ancestors = []) => {
					for (const p of list) {
						ids.add(p.project_id);
						if (p.project_id === revealProject) [...ancestors, p.project_id].forEach((id) => expanded.add(id));
						walk(p.children || [], [...ancestors, p.project_id]);
					}
				};
				walk(roots);
				if (revealProject !== null) {
					revealProject = null;
					persist();
				}
				for (const id of projects.keys()) if (!ids.has(id) || !expanded.has(id)) projects.delete(id);
				for (const id of expanded) if (ids.has(id)) {
					const detail = await api("GET", `/projects/${encodeURIComponent(id)}`);
					alive();
					projects.set(id, detail);
				}
				if (!roots.length && !sessionsLoaded && [
					"#/home",
					"#/sessions",
					"#/",
					""
				].includes(selected)) sessionTree.open = true;
				if (sessionTree.open) {
					const rows = new Map(), cursors = new Set();
					let cursor = null;
					for (let page = 0; page < sessionPages; page++) {
						const data = await api("GET", "/sessions?order=id&include_gone=true&limit=50" + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""));
						alive();
						for (const session of data.sessions || []) rows.set(JSON.stringify([session.host, session.session_id]), session);
						cursor = data.next_cursor;
						if (!cursor) break;
						if (cursors.has(cursor)) throw new Error(t("attention_invalid"));
						cursors.add(cursor);
					}
					const focused = sessionRows.contains(document.activeElement) ? document.activeElement.getAttribute("href") : null;
					sessionRows.replaceChildren(...groupedSessions([...rows.values()]).map((group) => h("div", {}, h("p", { class: "muted workspace-session-group" }, group.host, " · ", group.name || group.id || t("obs_unknown")), ...group.sessions.map((session) => link(`#/session/${[session.host, session.session_id].map(encodeURIComponent).join("/")}`, session.title || session.session_id, sessionActivity(session))))), h("p", { class: "muted" }, t("attention_loaded", { count: rows.size })));
					if (focused) [...sessionRows.querySelectorAll("a")].find((a) => a.getAttribute("href") === focused)?.focus({ preventScroll: true });
					more.hidden = !cursor;
					sessionsLoaded = true;
					filterSessions();
				}
				status.replaceChildren();
				render();
			} catch (error) {
				alive();
				status.replaceChildren(errorBox(error), h("p", { class: "muted" }, t("workspace_stale")), h("button", {
					class: "mini",
					onclick: () => refresh().catch(() => {})
				}, t("workspace_refresh")));
				throw error;
			}
		});
		serial = run;
		return run;
	};
	search.addEventListener("input", render);
	sessionTree.addEventListener("toggle", () => {
		if (sessionTree.open && !sessionsLoaded) refresh().catch(() => {});
	});
	box.addEventListener("click", (event) => {
		if (event.target.closest("a")) {
			const mobileOpen = document.body.classList.contains("workspace-nav-open");
			document.body.classList.remove("workspace-nav-open");
			document.getElementById("workspace-menu")?.setAttribute("aria-expanded", "false");
			if (mobileOpen) document.getElementById("main")?.focus({ preventScroll: true });
		}
	});
	const escape = (event) => {
		if (event.key === "Escape" && document.body.classList.contains("workspace-nav-open")) {
			document.body.classList.remove("workspace-nav-open");
			const menu = document.getElementById("workspace-menu");
			menu?.setAttribute("aria-expanded", "false");
			menu?.focus();
		}
	};
	document.addEventListener("keydown", escape);
	const off = onEvents((event) => [
		"project",
		"work_item",
		"session",
		"execution",
		"task",
		"operation",
		"integration"
	].includes(event.resource_type) ? refresh() : void 0);
	refresh().catch(() => {});
	return {
		box,
		select(hash) {
			selected = hash;
			const [type, pid] = hash.replace(/^#\//, "").split("/");
			if ([
				"project",
				"dispatch",
				"work"
			].includes(type) && pid) {
				revealProject = decodeURIComponent(pid);
				refresh().catch(() => {});
			}
			for (const node of box.querySelectorAll("a")) if (node.getAttribute("href") === hash) node.setAttribute("aria-current", "page");
			else node.removeAttribute("aria-current");
		},
		dispose() {
			disposed = true;
			off();
			document.removeEventListener("keydown", escape);
			box.remove();
		}
	};
}
var init_tslib_es6 = __esmMin((() => {}));
async function invoke(cmd, args = {}, options) {
	return window.__TAURI_INTERNALS__.invoke(cmd, args, options);
}
function isTauri() {
	return !!(globalThis || window).isTauri;
}
var init_core = __esmMin((() => {
	init_tslib_es6();
}));
//#endregion
//#region src/transport/index.ts
async function restoreBrowserSession() {
	if (nativeDesktop) return false;
	const response = await fetch("/api/v1/browser-session", {
		credentials: "same-origin",
		mode: "same-origin",
		cache: "no-store",
		redirect: "error"
	});
	if (!response.ok) return false;
	const data = await response.json();
	if (typeof data.csrf !== "string" || data.csrf.length < 32) return false;
	browserCsrf = data.csrf;
	return true;
}
function browserAuthHeaders(token) {
	if (token !== "managed-browser-session") return { Authorization: `Bearer ${token}` };
	if (!browserCsrf) throw new Error("Browser session needs to be restored");
	return { "X-Batc-CSRF": browserCsrf };
}
function forgetBrowserSession() {
	if (!browserCsrf) return;
	const headers = {
		...browserAuthHeaders(browserSessionToken),
		"Content-Type": "application/json"
	};
	browserCsrf = null;
	return fetch("/api/v1/browser-session/logout", {
		method: "POST",
		credentials: "same-origin",
		mode: "same-origin",
		redirect: "error",
		headers,
		body: "{}"
	});
}
async function nativeStatus() {
	const status = await invoke("native_status");
	nativeFileSupport = status.file_transfers === true;
	return status;
}
async function connectorRequest(method, path, body, key, browserToken) {
	if (nativeDesktop) return invoke("connector_request", { input: {
		method,
		path,
		body: body ?? null,
		idempotency_key: key ?? null
	} });
	const headers = browserAuthHeaders(browserToken);
	if (body !== void 0) headers["Content-Type"] = "application/json";
	if (key) headers["Idempotency-Key"] = key;
	const res = await fetch(`/api/v1${path}`, {
		method,
		headers,
		credentials: "same-origin",
		redirect: "error",
		body: body === void 0 ? void 0 : JSON.stringify(body)
	});
	return {
		status: res.status,
		data: await res.json().catch(() => ({}))
	};
}
async function connectorUploadArtifact(operationId, bytes, browserToken) {
	if (!/^op_[0-9a-f]{32}$/.test(operationId)) throw new Error("Invalid artifact upload operation ID");
	if (nativeDesktop) {
		if (bytes.byteLength > 16777216) throw new Error("Artifact exceeds the native 16 MiB upload limit");
		return invoke("connector_upload_artifact", bytes, { headers: { "x-batc-upload-operation": operationId } });
	}
	const res = await fetch(`/api/v1/artifacts/uploads/${operationId}/content`, {
		method: "POST",
		redirect: "error",
		credentials: "same-origin",
		headers: {
			...browserAuthHeaders(browserToken),
			"Content-Type": "application/octet-stream"
		},
		body: bytes
	});
	return {
		status: res.status,
		data: await res.json().catch(() => ({}))
	};
}
var nativeDesktop, nativeFileSupport, browserSessionToken, browserCsrf, nativeFilesStatus, nativeFilesPick, nativeFilesUpload, nativeFilesDropTarget, nativeFilesControl, nativeFilesSave, nativeFilesPreview, nativeConnect, nativeDisconnect, nativeEnroll, nativeReloadConfiguration, nativeSetupConfiguration, nativeForgetCredential, openExternal, fleetAvailability, fleetBootstrap, tailscaleControl, fleetControl, fleetRequest, updateRequest;
var init_transport = __esmMin((() => {
	init_core();
	nativeDesktop = isTauri();
	nativeFileSupport = false;
	browserSessionToken = "managed-browser-session";
	browserCsrf = null;
	nativeFilesStatus = () => invoke("native_files_status");
	nativeFilesPick = (draftId) => invoke("native_files_pick", { draftId });
	nativeFilesUpload = (handleId) => invoke("native_files_upload", { handleId });
	nativeFilesDropTarget = (draftId, enabled) => invoke("native_files_drop_target", {
		draftId,
		enabled
	});
	nativeFilesControl = (transferId, action) => invoke("native_files_control", {
		transferId,
		action
	});
	nativeFilesSave = (reference) => invoke("native_files_save", { reference });
	nativeFilesPreview = (reference) => invoke("native_files_preview", { reference });
	nativeConnect = () => invoke("connector_connect");
	nativeDisconnect = () => invoke("connector_disconnect");
	nativeEnroll = () => invoke("connector_enroll", { locale: navigator.language.toLowerCase().startsWith("zh") ? "zh-TW" : "en-US" });
	nativeReloadConfiguration = () => invoke("connector_reload_configuration");
	nativeSetupConfiguration = (config) => invoke("connector_setup_configuration", {
		config,
		locale: navigator.language.toLowerCase().startsWith("zh") ? "zh-TW" : "en-US"
	});
	nativeForgetCredential = () => invoke("connector_forget_credential");
	openExternal = (url) => invoke("open_external", { url });
	fleetAvailability = () => invoke("fleet_availability");
	fleetBootstrap = (input) => invoke("fleet_bootstrap", { input });
	tailscaleControl = (input) => invoke("tailscale_control", { input });
	fleetControl = (input) => invoke("fleet_control", { input });
	fleetRequest = (input) => invoke("fleet_request", { input });
	updateRequest = (input) => invoke("desktop_update", { input });
}));
//#endregion
//#region src/attention.js
init_transport();
async function attentionView({ main, h, t, api, guard, caps, storageKey, route, onEvents, debounceRefresh, errorBox, sessionRow, workItemRow, opRow }) {
	const unread = caps?.features?.work_item_reads?.version === 1;
	const saved = sessionStorage.getItem(storageKey) || sessionStorage.getItem("batc.tab");
	const tab = saved === "confirm" || saved === "active" ? "active" : saved === "unread" && unread ? "unread" : "needs";
	const tabs = h("div", {
		class: "tabs attention-tabs",
		role: "group",
		"aria-label": t("nav_home")
	}, ...[
		"needs",
		"active",
		...unread ? ["unread"] : []
	].map((value) => h("button", {
		class: value === tab ? "on" : "",
		"aria-pressed": String(value === tab),
		onclick: () => {
			guard();
			sessionStorage.setItem(storageKey, value);
			route();
		}
	}, t("attention_tab_" + value))));
	const empty = h("section", {
		class: "panel",
		hidden: true
	}, h("p", {}, t("empty_needs_you")), h("p", { class: "muted" }, t("empty_next_work")), h("div", { class: "actions" }, h("a", { href: "#/projects" }, t("sessions_projects")), caps?.scopes?.includes("start") && caps?.actions?.some((a) => a.action === "session.start" && a.allowed === true) ? h("a", { href: "#/start" }, t("start_title_page")) : null));
	const sections = [];
	const add = (key, path, field, row, options = {}) => {
		const list = h("div", {}), status = h("div", { role: "status" });
		const count = h("span", { class: "muted" }), more = h("button", {
			class: "secondary",
			hidden: true
		}, t("load_more"));
		const section = h("section", {
			class: "panel attention-section",
			"aria-label": t("attention_" + key)
		}, h("h2", {}, t("attention_" + key)), h("p", { class: "muted" }, t("attention_" + key + "_note")), status, list, h("div", { class: "actions attention-footer" }, count, more, key === "problems" || key === "active" ? h("a", { href: "#/operations/" + (key === "problems" ? "attention" : "active") }, t(key === "problems" ? "operations_view_attention" : "operations_view_active")) : null));
		const state = {
			key,
			path,
			field,
			row,
			...options,
			section,
			list,
			status,
			count,
			more,
			pages: 1,
			size: null,
			busy: false
		};
		more.onclick = () => refresh(state, state.pages + 1).catch(() => {});
		sections.push(state);
		return section;
	};
	const hostRow = (x) => h("div", { class: "row" }, h("div", { class: "grow" }, h("div", { class: "title" }, x.host), h("div", { class: "muted" }, x.error || t("stale_reason_" + x.stale_reason))));
	main.append(h("h1", {}, t("nav_home")), tabs, empty, ...tab === "needs" ? [
		add("replies", "/sessions?attention=true&limit=50", "sessions", sessionRow),
		add("completion", "/work-items?pending=true&limit=50", "work_items", workItemRow),
		add("problems", "/operations?status=needs_attention,uncertain&limit=50", "operations", opRow, {
			cursor: "next_before",
			param: "before"
		}),
		add("hosts", "/hosts", "hosts", hostRow, { filter: (x) => x.stale })
	] : tab === "active" ? [add("active", "/operations?status=accepted,running,waiting_checks,waiting_external&limit=50", "operations", opRow, {
		cursor: "next_before",
		param: "before"
	})] : [add("unread", "/work-items?unread=true&limit=50", "work_items", workItemRow)]);
	let serial = Promise.resolve();
	const load = async (section, wanted) => {
		guard();
		section.busy = true;
		section.more.disabled = true;
		if (section.size === null) section.status.replaceChildren(h("p", { class: "muted" }, t("loading")));
		try {
			let cursor = null, pages = 0;
			const items = new Map(), seen = new Set();
			do {
				const data = await api("GET", section.path + (cursor == null ? "" : `&${section.param || "cursor"}=${encodeURIComponent(cursor)}`));
				guard();
				if (!Array.isArray(data[section.field])) throw new Error(t("attention_invalid"));
				for (const row of data[section.field]) if (!section.filter || section.filter(row)) items.set(row.work_item_id || row.operation_id || (row.session_id ? JSON.stringify([row.host, row.session_id]) : row.host), row);
				cursor = data[section.cursor || "next_cursor"] ?? null;
				pages++;
				if (cursor !== null && seen.has(cursor)) throw new Error(t("attention_invalid"));
				seen.add(cursor);
			} while (cursor !== null && pages < wanted);
			section.pages = pages;
			section.size = items.size;
			section.list.replaceChildren(...items.size ? [...items.values()].map(section.row) : [h("p", { class: "muted" }, t("attention_empty"))]);
			section.count.textContent = t("attention_loaded", { count: items.size });
			section.status.replaceChildren();
			section.more.hidden = cursor === null;
			section.section.dataset.fresh = "true";
		} catch (error) {
			guard();
			section.section.dataset.fresh = "false";
			section.status.replaceChildren(errorBox(error), h("p", { class: "muted" }, t("attention_not_updated")));
			throw error;
		} finally {
			section.busy = false;
			section.more.disabled = false;
		}
	};
	const refresh = (only, wanted) => {
		const work = serial.catch(() => {}).then(async () => {
			guard();
			const results = await Promise.allSettled((only ? [only] : sections).map((s) => load(s, only ? wanted : s.pages)));
			guard();
			empty.hidden = tab !== "needs" || !sections.every((s) => s.size === 0 && s.section.dataset.fresh === "true");
			const failed = results.find((r) => r.status === "rejected");
			if (failed) throw failed.reason;
		});
		serial = work;
		return work;
	};
	await refresh().catch(() => {});
	try {
		guard();
	} catch {
		return;
	}
	return onEvents(debounceRefresh(() => refresh(), 500));
}
//#endregion
//#region src/delivery-input.js
function parsePullRequest(value) {
	try {
		const url = new URL(value.trim());
		if (url.protocol !== "https:" || url.hostname !== "github.com" || url.port || url.username || url.password) return null;
		const match = /^\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)\/pull\/([1-9][0-9]{0,8})\/?$/.exec(url.pathname);
		return match ? {
			repository: match[1],
			number: match[2]
		} : null;
	} catch {
		return null;
	}
}
//#endregion
//#region src/session-labels.js
var object$5 = (v) => v && typeof v === "object" && !Array.isArray(v);
var version$1 = (v) => Number.isSafeInteger(v) && v >= 0;
var opId$3 = (v) => typeof v === "string" && /^op_[0-9a-f]{32}$/.test(v);
var equal$6 = (a, b) => a === b || Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => equal$6(v, b[i])) || object$5(a) && object$5(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$6(a[k], b[k]));
function validLabels(v) {
	return Array.isArray(v) && v.length <= 8 && new Set(v).size === v.length && v.every((x) => typeof x === "string" && x === x.trim() && [...x].length >= 1 && [...x].length <= 40 && !/[\p{C}\u2028\u2029]/u.test(x));
}
var metadata = (v) => object$5(v) && version$1(v.version) && validLabels(v.labels);
function sessionLabelsPanel({ h, t, api, caps, guard, target, storageKey, errorBox, opStatus }) {
	const path = `/sessions/${encodeURIComponent(target.host)}/${encodeURIComponent(target.session_id)}`;
	const valid = (request) => request?.action === "session.labels.set" && equal$6(request.target, target) && object$5(request.params) && Object.keys(request.params).length === 1 && validLabels(request.params.labels) && object$5(request.preconditions) && Object.keys(request.preconditions).length === 1 && version$1(request.preconditions.expected_version);
	let saved = {}, current = null, operation = null, busy = false, submission = null, refreshing = null, readable = false, damaged = false;
	try {
		const raw = JSON.parse(localStorage.getItem(storageKey));
		if (raw && typeof raw.text === "string" && raw.text.length <= 1e3 && version$1(raw.base_version)) saved = {
			text: raw.text,
			base_version: raw.base_version
		};
		if (raw?.intent) {
			const proven = valid(raw.intent.request) && typeof raw.intent.key === "string" && raw.intent.key.length > 0 && raw.intent.key.length <= 200;
			saved.intent = {
				request: proven ? raw.intent.request : null,
				key: proven ? raw.intent.key : null,
				operation_id: opId$3(raw.intent.operation_id) ? raw.intent.operation_id : null
			};
			if (proven) {
				saved.text = raw.intent.request.params.labels.join("\n");
				saved.base_version = raw.intent.request.preconditions.expected_version;
			}
			if (proven && !saved.intent.operation_id && raw.intent.refused === "METADATA_VERSION_CONFLICT") saved.intent.refused = raw.intent.refused;
		} else if (raw && !Object.hasOwn(saved, "text")) damaged = true;
	} catch {
		damaged = true;
	}
	const live = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = () => {
		guard();
		localStorage.setItem(storageKey, JSON.stringify(saved));
	};
	const permitted = () => caps()?.scopes?.includes("manage") && caps()?.actions?.some((a) => a.action === "session.labels.set" && a.allowed === true);
	const terminal = () => [
		"succeeded",
		"failed",
		"cancelled"
	].includes(operation?.status);
	const input = h("textarea", {
		"aria-label": t("labels_input"),
		rows: 3,
		maxlength: 1e3
	});
	input.value = saved.text || "";
	const tags = h("div", { class: "actions" }), message = h("div", { role: "status" }), result = h("div"), restriction = h("p", { class: "muted" });
	const error = (e) => {
		if (live()) {
			message.replaceChildren(errorBox(e));
			update();
		}
	};
	const parsed = () => input.value.trim() === "" ? [] : input.value.split("\n").map((v) => v.trim());
	const accept = (candidate) => {
		guard();
		const intent = saved.intent;
		if (!intent || !opId$3(candidate?.operation_id) || candidate.action !== "session.labels.set" || !equal$6(candidate.target, target) || candidate.actor !== caps()?.actor || intent.operation_id && candidate.operation_id !== intent.operation_id || intent.key && candidate.idempotency_key !== intent.key || intent.request && !equal$6({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request)) throw Error(t("labels_wrong_receipt"));
		if (candidate.status === "succeeded" && (!equal$6({
			host: candidate.result?.host,
			session_id: candidate.result?.session_id
		}, target) || !metadata(candidate.result?.connector_metadata) || intent.request && (!equal$6(candidate.result.connector_metadata.labels, intent.request.params.labels) || candidate.result.connector_metadata.version !== intent.request.preconditions.expected_version + 1))) throw Error(t("labels_wrong_receipt"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		persist();
		update();
	};
	const apply = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!live() || busy || refreshing || !readable || !permitted() || damaged || saved.intent?.operation_id || saved.intent && (!saved.intent.request || saved.intent.refused)) return;
			const values = parsed();
			if (!validLabels(values)) {
				error(Error(t("labels_limits")));
				return;
			}
			const previous = saved;
			if (!saved.intent) saved = {
				text: input.value,
				base_version: saved.base_version ?? current.version,
				intent: {
					key: crypto.randomUUID(),
					operation_id: null,
					request: {
						action: "session.labels.set",
						target: { ...target },
						params: { labels: values },
						preconditions: { expected_version: saved.base_version ?? current.version }
					}
				}
			};
			try {
				persist();
			} catch (e) {
				saved = previous;
				error(e);
				return;
			}
			busy = true;
			update();
			const intent = saved.intent;
			submission = (async () => {
				try {
					const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(data.operation);
					message.replaceChildren();
				} catch (e) {
					if (live()) {
						if (e.code === "METADATA_VERSION_CONFLICT" && e.status === 409) {
							intent.refused = e.code;
							try {
								persist();
							} catch {}
						}
						error(e);
					}
				} finally {
					busy = false;
					if (live()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
			if (live()) try {
				await refresh(true);
			} catch (e) {
				error(e);
			}
		}
	}, t("labels_save"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(error)
	}, t("permissions_check"));
	const renew = h("button", {
		class: "secondary",
		onclick: () => {
			if (!live() || busy || refreshing || !readable || !permitted() || saved.intent && !terminal() && !saved.intent.refused) return;
			const previous = saved;
			const text = operation?.status === "succeeded" ? current.labels.join("\n") : saved.text ?? current.labels.join("\n");
			saved = {
				text,
				base_version: current.version
			};
			try {
				persist();
			} catch (e) {
				saved = previous;
				error(e);
				return;
			}
			damaged = false;
			operation = null;
			input.value = text;
			message.replaceChildren();
			update();
		}
	}, t("labels_review_current"));
	input.oninput = () => {
		if (!live() || saved.intent || !readable) {
			input.value = saved.text || "";
			return;
		}
		saved = {
			text: input.value,
			base_version: saved.base_version ?? current.version
		};
		try {
			persist();
		} catch (e) {
			error(e);
		}
		update();
	};
	const editor = h("details", {}, h("summary", {}, t("labels_edit")));
	let mounted = false;
	editor.addEventListener("toggle", () => {
		if (editor.open && !mounted) {
			editor.append(h("p", { class: "muted" }, t("labels_help")), h("label", {}, t("labels_input"), input), h("p", { class: "muted" }, t("labels_limits")), h("div", { class: "actions" }, apply, check, renew), restriction, result, message);
			mounted = true;
			update();
		}
	});
	const box = h("section", {
		class: "panel",
		"data-session-labels": ""
	}, h("h2", {}, t("labels_title")), tags, editor);
	function update() {
		if (!live()) return;
		const fixed = Boolean(saved.intent);
		tags.replaceChildren(...current?.labels.length ? current.labels.map((v) => h("span", { class: "chip" }, v)) : [h("span", { class: "muted" }, t(current ? "labels_empty" : "labels_unreadable"))]);
		input.disabled = fixed || busy || Boolean(refreshing) || !readable || !permitted() || damaged;
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.disabled = busy || Boolean(refreshing) || !readable || !permitted() || damaged || Boolean(fixed && !saved.intent.request) || !validLabels(parsed());
		apply.textContent = t(fixed ? "permissions_retry" : "labels_save");
		check.textContent = t(fixed ? "permissions_check" : "labels_refresh");
		check.disabled = busy || Boolean(refreshing);
		renew.hidden = fixed ? !terminal() && !saved.intent.refused : !damaged && !(current && saved.base_version !== void 0 && saved.base_version !== current.version);
		renew.disabled = busy || Boolean(refreshing) || !readable || !permitted();
		restriction.textContent = !permitted() ? t("labels_scope") : !readable ? t("labels_unreadable") : saved.base_version !== void 0 && saved.base_version !== current.version ? t("labels_changed") : "";
		result.replaceChildren();
		if (fixed) {
			result.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "labels_refused" : "permissions_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null), h("p", { class: "muted" }, t("labels_fixed", { version: saved.intent.request?.preconditions.expected_version ?? "?" })));
			if (operation?.status === "succeeded") result.append(h("p", {}, t("labels_saved")));
			if (!saved.intent.request && !saved.intent.operation_id) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		}
		if (damaged) result.append(h("p", { class: "error" }, t("labels_damaged")));
	}
	async function refresh(fresh = false) {
		guard();
		if (!caps()?.actions?.some((a) => a.action === "session.labels.set")) {
			readable = false;
			update();
			return;
		}
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		refreshing = (async () => {
			if (saved.intent?.operation_id) {
				const data = await api("GET", `/operations/${saved.intent.operation_id}`);
				guard();
				accept(data.operation);
			}
			const data = await api("GET", path);
			guard();
			if (!(data.session?.host === target.host && data.session?.session_id === target.session_id || !data.session && data.cleanup?.some((item) => item.kind === "session" && item.host === target.host && item.session_id === target.session_id)) || !metadata(data.connector_metadata)) throw Error(t("labels_unreadable"));
			current = data.connector_metadata;
			readable = true;
			if (!Object.hasOwn(saved, "text") && !saved.intent && !damaged) input.value = current.labels.join("\n");
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			readable = false;
			error(e);
			throw e;
		} finally {
			refreshing = null;
			if (live()) update();
		}
	}
	update();
	return {
		box,
		refresh,
		update
	};
}
async function readArtifactContent(reference, size, token, signal) {
	if (nativeDesktop || !/^art_[0-9a-f]{32}$/.test(reference.artifact_id) || !Number.isSafeInteger(reference.revision) || reference.revision < 1 || !/^[0-9a-f]{64}$/.test(reference.digest) || !Number.isSafeInteger(size) || size < 0 || size > 16777216) throw new Error("Artifact content exceeds the supported bound or has an invalid reference");
	const response = await fetch(`/api/v1/artifacts/${reference.artifact_id}/revisions/${reference.revision}/content`, {
		method: "GET",
		headers: browserAuthHeaders(token),
		redirect: "error",
		cache: "no-store",
		credentials: token === "managed-browser-session" ? "same-origin" : "omit",
		mode: "same-origin",
		signal: AbortSignal.any([signal, AbortSignal.timeout(3e4)])
	});
	if (response.status !== 200 || response.redirected || response.headers.get("Content-Length") !== String(size) || !response.body) {
		await response.body?.cancel();
		throw new Error("Artifact content response does not match the exact revision");
	}
	const bytes = new Uint8Array(size), reader = response.body.getReader();
	let offset = 0;
	try {
		for (;;) {
			const part = await reader.read();
			if (part.done) break;
			if (offset + part.value.length > size) throw new Error("Artifact content exceeds its declared size");
			bytes.set(part.value, offset);
			offset += part.value.length;
		}
		if (offset !== size) throw new Error("Artifact content is incomplete");
	} catch (error) {
		await reader.cancel().catch(() => {});
		throw error;
	} finally {
		reader.releaseLock();
	}
	const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((value) => value.toString(16).padStart(2, "0")).join("");
	signal.throwIfAborted();
	if (hash !== reference.digest) throw new Error("Artifact content digest does not match the exact revision");
	return bytes;
}
//#endregion
//#region src/message-format.js
var lineText = (line) => line.replace(/\r?\n$/, "");
function tableCells(line) {
	let text = line.trim(), cell = "", ticks = 0, separators = 0;
	const cells = [];
	if (text.startsWith("|")) text = text.slice(1);
	for (let i = 0; i < text.length; i++) {
		const char = text[i];
		if (char === "\\" && text[i + 1] === "|") {
			cell += "|";
			i++;
			continue;
		}
		if (char === "`") {
			let end = i + 1;
			while (text[end] === "`") end++;
			const count = end - i;
			if (!ticks) ticks = count;
			else if (ticks === count) ticks = 0;
			cell += text.slice(i, end);
			i = end - 1;
			continue;
		}
		if (char === "|" && !ticks) {
			cells.push(cell.trim());
			cell = "";
			separators++;
		} else cell += char;
	}
	if (cell || !text.endsWith("|")) cells.push(cell.trim());
	return separators ? cells : null;
}
function messageBlocks(source) {
	if (source.length > 2e5) return [{
		kind: "text",
		text: source
	}];
	const lines = source.match(/[^\n]*\n|[^\n]+$/g) || [];
	if (lines.length > 4e3) return [{
		kind: "text",
		text: source
	}];
	const blocks = [], plain = [];
	const flush = () => {
		if (plain.length) blocks.push({
			kind: "text",
			text: plain.splice(0).join("")
		});
	};
	for (let i = 0; i < lines.length;) {
		const fence = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)$/.exec(lineText(lines[i]));
		if (fence && !(fence[1][0] === "`" && fence[2].includes("`"))) {
			flush();
			const endFence = new RegExp(`^ {0,3}${fence[1][0]}{${fence[1].length},}[ \\t]*$`);
			const body = [];
			i++;
			while (i < lines.length && !endFence.test(lineText(lines[i]))) body.push(lines[i++]);
			if (i < lines.length) i++;
			blocks.push({
				kind: "code",
				language: fence[2].trim(),
				text: body.join("")
			});
			continue;
		}
		const header = tableCells(lineText(lines[i])), divider = i + 1 < lines.length ? tableCells(lineText(lines[i + 1])) : null;
		if (header?.length && header.length <= 40 && divider?.length === header.length && divider.every((cell) => /^:?-{3,}:?$/.test(cell))) {
			flush();
			const rows = [];
			i += 2;
			while (i < lines.length && rows.length < 100) {
				const cells = tableCells(lineText(lines[i]));
				if (!cells || cells.length !== header.length) break;
				rows.push(cells);
				i++;
			}
			blocks.push({
				kind: "table",
				header,
				rows
			});
			continue;
		}
		plain.push(lines[i++]);
	}
	flush();
	return blocks;
}
function inline(h, text) {
	if (text.length > 8192) return [text];
	const nodes = [];
	let from = 0;
	for (const match of text.matchAll(/`([^`\n]+)`|\*\*([^*\n]+)\*\*/g)) {
		nodes.push(text.slice(from, match.index), h(match[1] === void 0 ? "strong" : "code", {}, match[1] ?? match[2]));
		from = match.index + match[0].length;
	}
	nodes.push(text.slice(from));
	return nodes;
}
function renderMessage(h, t, source, copy) {
	return messageBlocks(source).map((block) => {
		if (block.kind === "code") return h("div", { class: "message-code" }, h("div", { class: "message-code-bar" }, h("span", { class: "muted" }, block.language || t("message_code")), h("button", {
			class: "mini",
			type: "button",
			onclick: () => copy(block.text)
		}, t("message_copy_code"))), h("pre", {
			tabindex: "0",
			"aria-label": t("message_code")
		}, h("code", {}, block.text)));
		if (block.kind === "table") return h("div", {
			class: "message-table",
			tabindex: "0",
			role: "region",
			"aria-label": t("message_table")
		}, h("table", {}, h("thead", {}, h("tr", {}, ...block.header.map((cell) => h("th", { scope: "col" }, ...inline(h, cell))))), h("tbody", {}, ...block.rows.map((row) => h("tr", {}, ...row.map((cell) => h("td", {}, ...inline(h, cell))))))));
		return h("div", { class: "message-text" }, ...inline(h, block.text));
	});
}
//#endregion
//#region src/conversation.js
function conversationPanel({ h, t, when, guard }) {
	const viewport = h("div", {
		class: "conversation-scroll",
		tabindex: "0",
		role: "region",
		"aria-label": t("messages")
	});
	const status = h("span", {
		class: "muted",
		role: "status"
	}), fallback = h("div", { class: "conversation-copy" });
	const notice = h("p", {
		class: "muted",
		role: "status",
		hidden: true
	}, t("message_anchor_missing"));
	const latest = h("button", {
		class: "mini",
		type: "button",
		hidden: true,
		onclick: () => {
			viewport.scrollTop = viewport.scrollHeight;
			notice.hidden = true;
			indicator();
		}
	}, t("message_latest"));
	const box = h("section", { class: "panel conversation" }, h("div", { class: "muted" }, t("message_window")), notice, viewport, h("div", { class: "conversation-toolbar" }, status, latest), fallback);
	let rows = new Map(), initialized = false, disposed = false, copyAttempt = 0;
	const alive = () => {
		if (disposed) return false;
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const atBottom = () => viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight <= 48;
	const indicator = () => {
		latest.hidden = atBottom();
	};
	viewport.addEventListener("scroll", indicator, { passive: true });
	const copy = async (text) => {
		if (!alive()) return;
		const attempt = ++copyAttempt;
		status.textContent = "";
		fallback.replaceChildren();
		try {
			await navigator.clipboard.writeText(text);
			if (alive() && attempt === copyAttempt) status.textContent = t("message_copied");
		} catch {
			if (!alive() || attempt !== copyAttempt) return;
			const input = h("textarea", {
				readonly: true,
				"aria-label": t("message_copy_source")
			}, text);
			input.addEventListener("copy", (event) => {
				if (alive() && event.clipboardData && input.selectionStart === 0 && input.selectionEnd === input.value.length) {
					event.clipboardData.setData("text/plain", text);
					event.preventDefault();
				}
			});
			fallback.replaceChildren(h("p", { class: "muted" }, t("message_copy_manual")), input, h("button", {
				class: "mini",
				type: "button",
				onclick: () => fallback.replaceChildren()
			}, t("cancel")));
			input.focus();
			input.select();
		}
	};
	const update = (messages) => {
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
			const identity = JSON.stringify(message.id != null ? ["id", message.id] : [
				"text",
				message.role,
				message.ts,
				text
			]);
			const occurrence = occurrences.get(identity) || 0;
			occurrences.set(identity, occurrence + 1);
			const key = JSON.stringify([identity, occurrence]);
			let row = rows.get(key);
			if (!row) {
				row = {
					text: null,
					meta: null,
					body: h("div", { class: "message-body" }),
					who: h("span", { class: "who" })
				};
				row.node = h("article", { class: "msg" }, h("div", { class: "message-meta" }, row.who, h("button", {
					class: "mini",
					type: "button",
					onclick: () => copy(row.text)
				}, t("message_copy"))), row.body);
			}
			const meta = `${message.role || ""} · ${when(message.ts)}`;
			if (row.meta !== meta) {
				row.who.textContent = meta;
				row.meta = meta;
			}
			row.node.className = `msg${message.role === "user" ? " user" : ""}`;
			if (row.text !== text) {
				row.body.replaceChildren(...renderMessage(h, t, text, copy));
				row.text = text;
			}
			next.set(key, row);
		}
		const retained = new Set([...next.values()].map((row) => row.node));
		for (const node of [...viewport.childNodes]) if (!retained.has(node)) node.remove();
		let position = viewport.firstChild;
		for (const row of next.values()) if (row.node === position) position = position.nextSibling;
		else viewport.insertBefore(row.node, position);
		while (position) {
			const old = position;
			position = old.nextSibling;
			old.remove();
		}
		if (!next.size) viewport.replaceChildren(h("p", { class: "muted" }, t("no_messages")));
		if (follow) {
			viewport.scrollTop = viewport.scrollHeight;
			notice.hidden = true;
		} else if (anchor && next.has(anchor[0])) viewport.scrollTop += next.get(anchor[0]).node.getBoundingClientRect().top - viewport.getBoundingClientRect().top - offset;
		else {
			viewport.scrollTop = scrollTop;
			if (anchor) notice.hidden = false;
		}
		rows = next;
		initialized = true;
		indicator();
	};
	return {
		box,
		update,
		dispose() {
			disposed = true;
			viewport.removeEventListener("scroll", indicator);
		}
	};
}
//#endregion
//#region src/i18n.js
var STRINGS = {
	"zh-TW": {
		managed_browser_connected: "已連線至本機 Connector",
		managed_browser_help: "此瀏覽器沿用桌面的個人身分。登出後，可從桌面選單重新開啟 Dashboard。",
		workspace_navigation: "專案與工作",
		workspace_search: "搜尋已載入的專案與工作",
		workspace_manage: "新增／管理專案",
		workspace_all_sessions: "所有工作階段",
		workspace_tools: "管理工具",
		workspace_connection: "連線 / Fleet",
		workspace_expand: "展開 {name}",
		workspace_collapse: "收合 {name}",
		workspace_needs_you: "待你處理",
		workspace_expand_load: "展開以載入工作",
		workspace_no_work: "尚未建立工作",
		workspace_no_match: "已載入的工作沒有符合項目。",
		workspace_stale: "工作樹尚未更新，保留上次讀取的資料。",
		workspace_work_details: "工作與成果",
		workspace_result: "成果與交付",
		workspace_result_empty: "尚無明確關聯的成果。可從下方保留 checkpoint。",
		workspace_work_missing: "目前專案資料中找不到這筆工作，請重新整理工作樹。",
		workspace_refresh: "重新讀取工作樹",
		connection_details: "連線詳細資訊與設定檔",
		delivery_repository_input: "儲存庫或 GitHub PR 網址",
		needs_manage_access: "目前帳號可以查看，但沒有編輯專案的權限。請向管理員取得具有專案管理權限的帳號，再到「連線」更換憑證。",
		empty_next_work: "要開始新的工作，請選擇專案派工，或建立工作階段。",
		start_dispatched: "已啟動",
		session_access_unknown: "尚未確認這個工作階段的來源與管理權限。取得有效資料前，暫停操作。",
		session_origin: "來源",
		delivery_pr_number: "PR 編號",
		delivery_choose_pr: "請填入儲存庫與 PR 編號，或貼上 GitHub PR 網址。",
		delivery_pr_unavailable: "目前無法讀取這個 PR 的完整資料。請重新讀取。",
		pub_branch_help: "輸入分支名稱，例如 main；也可貼上完整的 refs/heads/main。",
		pub_branch_invalid: "分支名稱無效。請使用 main 或 feature/name，不接受 tag、commit 或其他 refs。",
		delivery_result_unverified: "成果尚未驗證",
		delivery_observed_at: "最後觀測：{time}",
		delivery_unobserved: "尚無活動觀測",
		delivery_source_context: "已帶入原工作的成果來源。請選擇 repository 與 PR，再加入預覽。",
		delivery_source_unavailable: "目前無法確認可整合的成果來源。",
		delivery_review_result: "檢視成果並加入 PR",
		delivery_project_work: "派出的工作",
		delivery_no_work: "尚無明確關聯的派工紀錄。",
		delivery_dispatch_state: "派工狀態：",
		kind_execution: "中央派工",
		kind_task_command: "Task Service 成果",
		delivery_dispatch_accepted: "已受理",
		delivery_worktree_branch: "分支",
		delivery_worktree_path: "工作目錄",
		delivery_worktree_owner: "建立依據",
		delivery_worktree_sessions: "關聯工作階段",
		delivery_worktree_recorded: "中央目前保存的關聯；活動狀態以各工作階段的觀測為準。",
		delivery_worktree_cleanup: "整理資格需要最新預覽。預覽會列出使用中的工作、未交付成果、資源保留與其他阻擋原因。",
		delivery_merge_read_receipts: "查核已保存回執",
		delivery_merge_recovery: "Worktree merge 復原",
		delivery_merge_held: "此操作尚無釋放資源的回執。以下兩個工作目錄依原操作保留；請保留原 operation ID。",
		delivery_merge_source: "來源 worktree",
		delivery_merge_destination: "目的工作目錄",
		delivery_merge_ack: "已保存正面 ACK",
		delivery_merge_no_ack: "尚無正面 ACK 證據",
		delivery_merge_safe_reads: "可讀取 session、檢查 Git 與操作紀錄，或使用既有停止／中斷功能。查核回執不會重送未知的 merge。",
		delivery_merge_closeout: "安全結案需要原步驟的正面 ACK 與原資源保留身分。完全遺失 ACK 的人工裁決尚未提供；不要用目前 HEAD 猜測結果或清除 reservation。",
		delivery_setup_title: "首次連接與使用方式",
		delivery_setup_central: "首次使用時填入既有中央服務的位址與預期身分，在原生視窗確認後保存。已有設定可重新載入。",
		delivery_setup_identity: "連線後確認實際身分與權限。主機是否就緒，請查看 Fleet 的各項原因。",
		delivery_setup_mode: "只管理遠端工作可直接使用 Dashboard。需要 Windows 本機連線與 BAT 啟動時，再於 Fleet 選擇連線、profile 與登入啟動項目。Mac 可作為 Dashboard 使用。",
		delivery_fleet_current_backend: "目前 Fleet backend：{backend}",
		delivery_fleet_legacy_default: "舊設定未指定 backend 時仍使用 PowerShell。若要改由 Rust 管理，請使用下方的遷移預覽；安裝新版 Dashboard 不會自行遷移。",
		message_code: "程式碼",
		message_table: "訊息表格",
		message_copy_code: "複製程式碼",
		message_copy: "複製原文",
		message_copied: "已複製。",
		message_copy_source: "要複製的原文",
		message_copy_manual: "無法自動複製，請選取並複製以下原文。",
		message_latest: "回到最新訊息",
		message_window: "最近 30 則訊息",
		message_anchor_missing: "原本閱讀的位置已不在這次載入的訊息中。",
		tailscale_request: "原開啟請求",
		tailscale_title: "Tailscale",
		tailscale_open: "開啟 Tailscale",
		tailscale_refresh: "重新檢查 Tailscale",
		tailscale_browser: "請在本機的 Tailscale 完成登入。Windows 桌面版可直接開啟 Tailscale。",
		tailscale_unsupported: "此平台尚未提供 Tailscale 原生開啟功能。",
		tailscale_missing: "未找到標準安裝位置中的 Tailscale。請先安裝 Windows 版。",
		tailscale_incomplete: "Tailscale 安裝不完整。請檢查 Windows 版安裝。",
		tailscale_unknown: "目前無法確認 Tailscale 狀態。",
		tailscale_needs_login: "Tailscale 需要登入。",
		tailscale_needs_approval: "此裝置仍需管理員核准。",
		tailscale_stopped: "Tailscale 已停止連線。",
		tailscale_starting: "Tailscale 正在連線。",
		tailscale_running: "Tailscale 正在執行。各主機連線狀態請見 Fleet。",
		tailscale_help: "開啟後，從 Windows 通知區的 Tailscale 圖示選擇登入。返回這裡時會重新檢查狀態。",
		tailscale_uncertain: "開啟結果尚未確認。請先查看通知區；原請求已保留，不會自動再次開啟。",
		tailscale_started: "已啟動 Tailscale 程式。請查看通知區；這不代表已完成登入。",
		tailscale_not_started: "此次請求未啟動 Tailscale。",
		tailscale_retry: "查回或重試原請求",
		tailscale_new: "準備另一次開啟",
		tailscale_damaged: "儲存的請求無法讀取。請先在 Tailscale 中確認狀態。",
		tailscale_read_failed: "無法確認最新狀態或開啟結果。請重新檢查；原請求保留。",
		bat_review_again: "重新預覽原選擇",
		bat_preview_expired: "此預覽尚未送出。重新開啟頁面後，須明確重新預覽原 profile，才能啟動 BAT。",
		bat_handoff: "在 BAT 中查看",
		bat_copy_title: "複製完整標題",
		bat_copy_id: "複製完整 ID",
		bat_copied: "已複製。",
		bat_copy_manually: "請選取並複製以下完整內容。",
		bat_open: "在 BAT 中開啟",
		bat_browser: "請在 BAT 中搜尋上方完整標題或 ID。桌面版可選擇並開啟 BAT profile。",
		bat_profile: "BAT profile",
		bat_choose: "明確選擇 profile",
		bat_search_help: "選擇你要開啟的 profile，再於 BAT 搜尋完整標題或 ID。這不會直接定位到此工作階段。",
		bat_review: "預覽所選 profile",
		bat_launch: "開啟所選 profile",
		bat_retry: "查證並重試原開啟請求",
		bat_read: "查回原開啟結果",
		bat_new: "選擇另一個 profile",
		bat_chosen: "已選擇：{profile}",
		bat_reviewed: "請確認此 profile；按下開啟後才會啟動 BAT。",
		bat_preferences: "不變更已儲存的 Fleet 視窗、登入或連線選擇。遠端 profile 的連線須已選取。",
		bat_problem: "目前無法繼續：",
		bat_missing: "本機 BAT 啟動功能或設定尚未就緒。請檢查桌面連線設定。",
		bat_wrong_receipt: "回應與原 profile 開啟請求不符；原請求保留。",
		bat_unknown: "結果尚未確認。查回原請求，不會自動再開啟 BAT。",
		bat_no_receipt: "尚未找到原開啟回執。保留原請求；重新啟動程式不會自動重送。",
		bat_saved_invalid: "已儲存的開啟請求不完整，無法安全建立另一筆。請先查明原啟動狀態。",
		labels_refresh: "重新讀取標籤",
		labels_title: "標籤",
		labels_edit: "編輯標籤",
		labels_input: "標籤（每行一個）",
		labels_help: "標籤只用於 Dashboard 整理，不會修改 BAT 標題或工作階段。",
		labels_limits: "最多 8 個標籤，每個最多 40 個字；空白清單可清除標籤。",
		labels_empty: "尚無標籤",
		labels_save: "儲存標籤",
		labels_saved: "已儲存這次標籤變更。",
		labels_scope: "需要 manage 權限才能編輯標籤。",
		labels_unreadable: "尚未讀到可確認的標籤資料，暫時無法儲存。",
		labels_changed: "標籤已有新版本，原草稿保留。請檢視目前標籤後再準備變更。",
		labels_review_current: "檢視目前版本並準備變更",
		labels_refused: "原請求因版本變更被拒絕，尚未套用。",
		labels_fixed: "原請求固定使用標籤版本 {version}。",
		labels_wrong_receipt: "回執與原標籤請求不符。",
		labels_damaged: "儲存的草稿無法讀取。請檢視目前版本後明確重新準備變更。",
		update_title: "桌面更新",
		update_current: "目前版本：{version}",
		update_candidate: "可用版本",
		update_check: "檢查更新",
		update_download: "下載並驗證",
		update_install: "安裝並重新啟動",
		update_read: "查詢更新狀態",
		update_unsigned: "此測試安裝包尚未啟用簽章更新。",
		update_platform: "此平台尚未提供桌面更新。",
		update_help: "驗證通過後才能安裝。安裝時會暫停本機連線；遠端工作會持續執行。",
		update_problem: "更新暫時無法繼續：",
		update_read_failed: "無法確認更新狀態，請重新查詢。",
		update_unknown: "安裝結果尚未確認。請查詢狀態；不會自動再次安裝。",
		update_requested: "已要求安裝 {version}。請重新開啟程式確認版本；若仍是舊版，請檢查安裝程式的結果。",
		update_phase_idle: "尚未檢查更新。",
		update_phase_checking: "正在檢查更新…",
		update_phase_available: "有新版本可下載。",
		update_phase_up_to_date: "目前沒有較新的版本。",
		update_phase_check_failed: "檢查更新未成功。",
		update_phase_downloading: "正在下載並驗證簽章…",
		update_phase_download_failed: "下載或簽章驗證未成功。",
		update_phase_verified: "簽章與版本已驗證，可安裝此版本。",
		update_phase_stopping_fleet: "正在準備安裝並停止本機連線…",
		update_phase_installation_unknown: "已保存原安裝請求，等待確認安裝結果。",
		bootstrap_title: "中央服務啟動",
		bootstrap_help: "只查核並啟用已配置的既有 Connector 服務；不重啟服務，也不建立新的資料庫。",
		bootstrap_configured: "已有固定啟動設定",
		bootstrap_missing: "尚未配置啟動方式",
		bootstrap_auto_on: "已設定不可用時自動查核啟動",
		bootstrap_auto_off: "未啟用自動啟動",
		bootstrap_healthy: "中央服務目前可用，不需要啟動。",
		bootstrap_blocked: "需先確認已選連線、目前 owner 與服務不可用的最新觀測。登入、權限或版本問題不會觸發服務啟動。",
		bootstrap_prepared: "已保存原請求，尚未傳送遠端查核。",
		bootstrap_querying: "正在查核原請求；尚未確認服務狀態。",
		bootstrap_ensure_requested: "已記錄啟動請求；回應未全部確認，只能查證原結果。",
		bootstrap_needs_attention: "有限查核仍未確認結果，需檢查既有部署。原請求保留，不會再送啟動。",
		bootstrap_service_running: "既有服務的執行身分已確認。這是服務證據，並不表示中央登入或 API 已通過。",
		bootstrap_unknown: "結果尚未確認。請讀取原請求；重新開啟此頁不會再送啟動。",
		bootstrap_request: "原請求",
		bootstrap_queries: "已查核 {count}／4 次",
		bootstrap_changed: "原請求屬於先前的固定設定，目前僅能讀取。",
		bootstrap_prepare: "準備固定服務請求",
		bootstrap_ensure: "查核並啟用既有服務",
		bootstrap_reconcile: "繼續查證原結果",
		bootstrap_read: "讀取原請求",
		bootstrap_refresh: "更新啟動狀態",
		bootstrap_separate: "一般中央連線與身分驗證持續獨立進行。本機回執不等於中央已接受操作。",
		bootstrap_working: "正在查核本機回執…",
		bootstrap_unproven: "無法確認回應與原請求一致。",
		task_title: "工作執行",
		task_unknown: "派工狀態未確認",
		task_state_queued: "排隊中",
		task_state_dispatching: "派工中",
		task_state_accepted: "已受理",
		task_state_running: "執行中",
		task_state_waiting_permission: "等待授權",
		task_state_quota_limited: "額度受限",
		task_state_human_owned: "人工處理中",
		task_state_needs_ted: "等待人工決定",
		task_state_verifying: "驗證中",
		task_state_done: "已完成",
		task_state_failed: "失敗",
		task_state_uncertain: "結果待確認",
		task_controls: "執行控制",
		task_pause: "暫停派工",
		task_resume: "恢復派工",
		task_abort: "同時中斷目前這一輪",
		task_control_help: "暫停會停止後續派工；目前這一輪預設繼續。恢復後仍須通過原有檢查。",
		task_control_unavailable: "需先讀取目前執行狀態，並具有 operate 權限及這項操作能力。已結束的執行不能重新派工。",
		task_control_new: "準備另一筆控制",
		task_control_fixed: "原請求固定使用控制版本 {version}。結果不明時只查回或重試原請求。",
		task_control_invalid: "回應與原執行控制請求不符。",
		task_control_refused: "執行版本已變動，原請求未受理。請重新查看狀態後準備另一筆控制。",
		task_control_recorded: "控制操作已完成；目前執行狀態以上方最新讀回為準。這不代表工作已完成。",
		task_paused: "已暫停派工",
		task_dispatch_enabled: "未暫停派工",
		task_open_session: "查看目前工作階段",
		task_evidence: "執行識別與完整紀錄",
		operations_more: "載入較早的操作",
		operations_loaded: "已載入 {count} 筆操作（非總數）",
		operations_all: "全部操作",
		operations_empty: "這個範圍尚無操作。",
		operations_invalid_page: "分頁回應無效；保留已載入的操作。",
		operations_view_attention: "查看需要處理的操作",
		operations_view_active: "查看執行中操作",
		orch_waiting_children: "正在查回原有子操作",
		orch_body_limit: "完整請求超過中央的 200,000 位元組上限。請縮短項目原文；目前尚未提交。",
		orch_title: "安排工作執行",
		orch_relay: "轉交原始指示",
		orch_planner: "啟動規劃者",
		orch_items: "執行已檢視項目",
		orch_failover: "改由 Codex 接續",
		orch_help_relay: "將你的原文與中央整理的轉交背景送往一個固定的受管理工作階段。若它無法接收，這個表單不會另建替代工作階段。",
		orch_help_planner: "在新 worktree 啟動一個唯讀 Codex 規劃者。讀取回覆後，再另外輸入並逐項檢視要執行的工作。",
		orch_help_items: "依下列逐項原文建立各自獨立的受管理 worktree。不會自動匯入規劃者回覆，也不會停止規劃者。",
		orch_help_failover: "由 Codex 接續一個閒置且配額耗盡的受管理 Claude 工作階段。中央會檢查所有寫入者與任務擁有權；保留來源分頁與 worktree，不提供強制或任務中途切換。",
		orch_preparation: "請檢視這些選定輸入。提交後，中央才會準備並記錄固定的轉交背景、計畫或交接內容；此頁不是對話或交接內容的預覽。",
		orch_session: "固定的受管理工作階段",
		orch_choose_session: "選擇受管理工作階段",
		orch_message: "原始指示",
		orch_instructions: "補充交接指示（選填）",
		orch_max_items: "規劃項目上限（1–16）",
		orch_item_title: "項目 {n} 標題",
		orch_item_prompt: "項目 {n} 指示",
		orch_item: "項目 {n}",
		orch_title_label: "標題",
		orch_prompt_label: "完整指示原文",
		orch_remove_item: "移除項目 {n}",
		orch_add_item: "新增另一個項目",
		orch_reload: "重新讀取可用目標",
		orch_loading: "正在讀取中央目標…",
		orch_selection_help: "只選用最新觀測的 Connector 管理工作階段或中央固定工作區 ID。中央仍會在產生影響前重新檢查政策。",
		orch_truncated: "只顯示前 200 筆，並非完整清單。可從「工作階段」開啟未列於此頁的固定工作階段。",
		orch_empty: "此主機未傳回可選目標。人工、過期、來源不明，以及有任務關聯的切換來源均不列入。",
		orch_discovery_failed: "目標識別尚未確認。請重新讀取後再提交。",
		orch_review_relay: "我已檢視這個固定工作階段與原始指示。",
		orch_review_planner: "我已檢視工作區、原始指示與規劃項目上限。",
		orch_review_items: "我已檢視工作區、agent 與上述每一項完整原文。",
		orch_review_failover: "我已檢視這個固定 Claude 來源。配額、閒置或共用擁有權檢查未通過時，中央會拒絕執行。",
		orch_apply_relay: "轉交至此工作階段",
		orch_apply_planner: "啟動規劃者",
		orch_apply_items: "執行已檢視項目",
		orch_apply_failover: "要求由 Codex 接續",
		orch_new: "準備另一筆請求",
		orch_invalid_result: "操作回應與原請求或識別不符。",
		orch_unavailable: "需要 {scopes} 權限與中央明確允許此功能；新請求也需要最新目標與主機可寫證據。",
		orch_fixed: "保留原輸入與 key。受理後的查回只讀取這筆操作；結果不明不代表可以另送新請求或另建子操作。",
		orch_partial: "尚未證明整筆請求完成。進一步操作前，請檢視原操作與逐項回執。",
		orch_receipts: "個別操作回執",
		orch_child: "轉交訊息操作",
		orch_steps: "準備與執行回執",
		orch_item_progress: "已確認 {total} 個檢視項目中的 {count} 個接受初始指示；不代表任務完成。",
		orch_relay_accepted: "目標已接受轉交指示；不代表工作已完成。",
		orch_planner_started: "規劃者已接受指示，請讀取其回覆：",
		orch_handoff_accepted: "Codex 已接受交接指示：",
		orch_successor_unconfirmed: "已保留接續者識別，但尚未證明交接指示已被接受：",
		bulk_title: "批次核准",
		bulk_choose_host: "選擇主機",
		bulk_workspace: "工作區名稱或 ID（選填）",
		bulk_preview: "預覽待核准請求",
		bulk_scope: "範圍限於所選主機，可再指定工作區。只處理這次明確勾選的請求。",
		bulk_effect: "每筆勾選的請求都會設為允許，並通知 BAT 不再詢問同類請求。這不是單次允許；變更權限模式則需另外選擇。",
		bulk_select: "核准 {id}",
		bulk_mode: "{id} 的後續權限模式",
		bulk_no_mode: "不變更權限模式",
		bulk_apply: "核准已選請求",
		bulk_selected: "已選 {count} 筆",
		bulk_check: "查回批次結果",
		bulk_new: "檢視另一批請求",
		bulk_empty: "這個範圍目前沒有待核准請求。",
		bulk_blocked: "不可納入批次",
		bulk_truncated: "這次只檢查前 50 個工作階段，並非完整清單。請縮小工作區範圍後再預覽。",
		bulk_fixed: "保留原請求、選擇與操作識別。新出現的請求不會自動加入這一批。",
		bulk_expired: "預覽已過期。請重新預覽並勾選。",
		bulk_refused: "這筆請求在受理前被拒絕。可重新檢視另一批請求。",
		bulk_invalid_preview: "預覽回應與所選範圍不符。",
		bulk_invalid_result: "操作回應與原批次請求不符。",
		bulk_all_proven: "每筆核准與所選權限變更都有接受回執；這不代表工作已完成。",
		bulk_partial: "尚未證明全部項目成功。請查看逐筆回執與原操作。",
		bulk_item_complete: "所選操作已接受",
		bulk_item_incomplete: "尚未全部確認",
		bulk_answer: "核准",
		bulk_permissions: "權限",
		bulk_full_prompt: "完整請求與識別資料",
		pub_title: "從已發佈版本建立工作",
		pub_intro: "選擇已綁定的 GitHub 儲存庫與目標工作區，從明確的已發佈版本開始。",
		pub_binding: "儲存庫 · 主機 · 工作區 ID",
		pub_choose: "選擇已綁定的工作區",
		pub_ref: "已發佈分支 ref",
		pub_prompt: "原始指示",
		pub_head_only: "目前只接受指定分支的精確最新提交。若預覽後分支改變，中央會停止，而不替換你選定的版本。",
		pub_preview: "預覽已發佈版本",
		pub_loading: "正在讀取版本…",
		pub_invalid_preview: "版本預覽與所選儲存庫、工作區或分支不符。",
		pub_invalid_result: "操作回應與原版本、工作區或請求不符。",
		pub_apply: "從此版本開始",
		pub_new: "準備另一個已發佈版本",
		pub_isolation: "建立新的受管理 clone、worktree 與工作階段；不更新或接管既有人工工作目錄。",
		pub_reviewed: "請確認以下來源與完整提交 SHA：",
		pub_sha: "固定提交 SHA",
		pub_unavailable: "需要 observe 與 start 權限，以及中央明確允許此操作。",
		pub_no_bindings: "中央尚未設定儲存庫與工作區的明確綁定。",
		pub_fixed: "保留原提交、目標、指示與操作 key。查回只讀取原操作，不追蹤新的分支 head，也不另外啟動工作階段。",
		start_title_page: "開始新工作階段",
		start_intro: "在選定主機與工作區建立獨立的受管理工作階段。",
		dispatch_title: "專案快速派工",
		dispatch_back: "回到專案",
		dispatch_advanced: "進階設定",
		dispatch_intro: "選擇專案已綁定的目的地，確認已發布版本，再帶著原始指示與附件開始工作。",
		dispatch_project_help: "只顯示此專案已明確綁定的儲存庫、主機與工作區。不會自動建立工作項目或 Task Service 任務。",
		dispatch_no_bindings: "此專案沒有可用的目的地。請先在專案設定儲存庫，並在中央設定對應的主機與工作區綁定。",
		dispatch_archived: "此專案已封存，不能派送新工作。既有操作仍可查回。",
		dispatch_project_unavailable: "無法確認目前專案。草稿保留，確認前不會派工。",
		dispatch_unsupported: "中央尚未支援專案快速派工。請先更新中央服務。",
		dispatch_fixed_inputs: "這筆操作固定使用下列附件版本；查回不會重傳或另開工作。",
		start_choose_host: "選擇主機",
		start_workspace: "工作區",
		start_choose_workspace: "選擇工作區",
		start_agent: "Agent",
		start_model: "模型（選填）",
		start_model_default: "使用主機或 agent 的預設模型",
		start_title: "標題（選填）",
		start_prompt: "原始指示（選填）",
		start_reload_workspaces: "重新讀取工作區",
		start_loading_workspaces: "正在讀取中央工作區清單…",
		start_discovery_failed: "工作區清單尚未確認。請重新讀取後再選擇。",
		start_no_workspaces: "此主機目前未傳回工作區。",
		start_truncated: "只顯示前 200 個工作區；此清單不代表所有工作區。",
		start_workspace_help: "使用中央傳回的固定工作區 ID；主機仍會檢查儲存庫與權限。",
		start_isolation: "使用新 worktree。此操作不會接管既有人工或任務工作階段。",
		start_prompt_help: "原文會完整保留。留白只啟動工作階段，不會自動產生指示。",
		start_apply: "開始工作階段",
		start_new: "準備另一個工作階段",
		start_unavailable: "需要 observe 與 start 權限，以及中央允許啟動的主機。",
		start_invalid_result: "操作回應與原啟動請求不符。",
		start_unknown: "提交結果尚未確認；原請求與 key 已保留。",
		start_fixed: "主機、工作區、選項與原文已固定。查回不會重新啟動；結果不明時只能重試同一筆請求。",
		start_refused: "請求在受理前被拒絕。可明確準備另一筆請求。",
		start_started: "已確認啟動：",
		start_without_prompt: "未要求傳送初始指示。",
		start_prompt_accepted: "已確認初始指示被接受。",
		start_prompt_unknown: "已啟動，但初始指示是否被接受尚未確認。請檢視逐步回執；不要另開工作階段重送。",
		sessions_label: "標題",
		sessions_workspace: "工作區",
		sessions_workspace_id: "工作區 ID",
		sessions_id: "工作階段 ID",
		sessions_title: "工作階段",
		sessions_intro: "依主機與工作區整理工作階段，保留人工工作與過往紀錄。",
		sessions_search: "搜尋已載入的工作階段",
		sessions_workspaces: "已載入的工作區",
		sessions_scope_note: "數量只計算已載入的頁面。",
		sessions_all_loaded: "全部已載入",
		sessions_loaded_count: "{count} 筆",
		sessions_projects: "前往專案與工作項目",
		sessions_workspace_unknown: "工作區未記錄",
		sessions_workspace_unverified: "未記錄工作區 ID",
		sessions_scope_missing: "所選工作區目前沒有資料",
		sessions_no_matches: "目前範圍沒有符合的工作階段。",
		sessions_more_hint: "還有頁面尚未載入。可載入更多，或調整搜尋與篩選。",
		sessions_empty_hint: "可調整搜尋、主機或存取方式；未出現在這裡不代表工作已結束。",
		sessions_showing: "顯示 {shown} 筆 · 已載入 {loaded} 筆",
		sessions_page_note: "搜尋與工作區選擇只套用到已載入頁面。",
		sessions_manual: "人工建立",
		sessions_connector: "Connector 建立",
		sessions_origin_unknown: "來源未確認",
		sessions_access_unknown: "存取方式未確認",
		sessions_details: "狀態與紀錄",
		sessions_runtime_stale: "活動與待回覆資訊尚未重新確認。",
		sessions_not_seen: "最近掃描未見",
		sessions_stale: "觀測待更新",
		sessions_activity_unknown: "活動狀態未確認",
		permissions_title: "Session 權限",
		permissions_mode: "要求的模式",
		permissions_default: "一般權限",
		permissions_allow_all: "全部允許",
		permissions_apply: "套用權限",
		permissions_check: "查回原操作",
		permissions_new: "建立另一筆變更",
		permissions_retry: "重試原請求",
		permissions_details: "檢視操作與逐步回執",
		permissions_help: "選擇要套用的權限。這裡不表示目前實際模式；主機政策與隔離限制仍然適用。",
		permissions_default_help: "使用一般核准流程，保留需要確認的操作提示。",
		permissions_allow_help: "略過 agent 的操作核准提示，包括寫入與命令執行。主機仍可拒絕此變更。",
		permissions_unavailable: "需要最新 Session 資料、operate 權限，以及中央明確允許此操作與主機寫入。",
		permissions_unknown: "結果尚未確認。原請求已保留。",
		permissions_fixed: "保留同一筆模式、Session 與操作。部分完成或結果不明時，請先檢視回執。",
		permissions_invalid_result: "操作回應與原權限請求不符。",
		permissions_damaged: "已儲存的請求不完整。請先在操作紀錄確認結果。",
		permissions_accepted: "BAT 已接受要求的設定；尚未獨立查證執行中的 agent 已套用。",
		permissions_next_turn: "Codex 於下一輪使用這個設定。",
		permissions_refused: "這筆請求在受理前被拒絕。可明確建立另一筆變更；原請求不會自動重試。",
		ar_content_download: "下載此版本",
		ar_content_downloaded: "已驗證此版本的 SHA-256，並交由瀏覽器下載。",
		ar_content_help: "讀取固定版本，不會建立審閱記錄。文字預覽最多 256 KiB；靜態 PNG 最多 2 MiB／100 萬像素；下載最多 16 MiB。",
		ar_content_changed: "檔案回覆與固定版本不符。請重新查核原操作。",
		ar_content_limit: "此檔案超過 16 MiB 的用戶端讀取上限。",
		ar_content_reading: "正在讀取與查核固定版本…",
		ar_content_verified: "此預覽來自 SHA-256 已驗證的固定版本。",
		ar_content_preview_limit: "此檔案不支援預覽，請下載或另存新檔後檢視。",
		ar_content_native_unavailable: "這個桌面版本未提供原生檔案讀取功能。",
		ar_nav: "附件成果",
		ar_title: "附件成果與審閱",
		ar_open: "擷取與審閱這次執行的檔案",
		ar_help: "保存一個管理中來源的固定檔案版本，再明確記錄對該版本的審閱。原工作樹與執行狀態不會因此改變。",
		ar_capture_title: "保存來源檔案",
		ar_review_title: "審閱固定版本",
		ar_execution: "中央執行證據",
		ar_choose_execution: "選擇已接受的執行或指令",
		ar_evidence_kind: "證據類型",
		ar_operation: "執行操作",
		ar_command: "Task Service 指令",
		ar_task_id: "完整任務 ID",
		ar_evidence_id: "完整操作或指令 ID",
		ar_exact_evidence: "輸入較早的完整證據 ID…",
		ar_more_executions: "更多執行紀錄",
		ar_refresh_sources: "重新讀取執行證據",
		ar_source_unavailable: "來源須為目前由 Connector 管理的完整 session；中央仍會查核原始執行證據。",
		ar_receipt: "對此版本的審閱紀錄（最多 2000 字）",
		ar_accept: "記錄此版本的審閱",
		ar_check_accept: "查回原審閱提交",
		ar_accept_help: "請先檢視這份成果，再記錄審閱依據。此回執只對應下列版本，不表示測試通過、任務完成、合併或部署。",
		ar_approve_scope: "記錄審閱需要 approve 權限；查看附件需要 observe 權限。",
		ar_revision: "固定附件版本",
		ar_lineage: "中央來源與執行證據",
		ar_check: "查回原操作",
		ar_new_review: "新增另一筆審閱",
		ar_recorded: "已記錄對此固定版本的審閱。任務與工作項目的完成狀態未改變。",
		ar_catalog: "已保存的管理中來源成果",
		ar_no_artifacts: "這一頁尚無可審閱的管理中來源成果。",
		ar_invalid_result: "回應與原操作、固定版本或中央來源證據不符。原請求與 key 已保留。",
		ar_storage: "無法保存原操作的復原資料。請先允許此應用程式使用本機儲存空間。",
		ar_original_credential: "擷取查回需要原始憑證及 manage、observe 權限。請恢復原憑證；原請求與 key 會繼續保留。",
		ar_original_preview: "原始擷取預覽與來源證據",
		capture_title: "擷取遠端檔案",
		capture_host: "來源主機",
		capture_session: "完整人工 Session ID",
		capture_path: "遠端相對檔案路徑",
		capture_help: "輸入一個相對於所選人工 session 資料夾的檔案路徑。讀取過程不會更動來源。",
		capture_preview: "預覽來源檔案",
		capture_review: "我已檢視此檔案與來源證據",
		capture_save: "保存已檢視的檔案",
		capture_check: "查回原擷取操作",
		capture_new: "擷取另一個檔案",
		capture_attach: "加入目前附件草稿",
		capture_attached: "已加入附件草稿。儲存工作項目或派工後才會套用。",
		capture_name: "檔名",
		capture_bytes: "位元組",
		capture_source: "來源",
		capture_root: "Session 資料夾",
		capture_repository: "儲存庫",
		capture_expiry: "預覽有效期限",
		capture_single_file: "只擷取這一個檔案；不包含其他尚未提交的變更。",
		capture_expired: "預覽已過期。請重新預覽與檢視；尚未提交擷取。",
		capture_fixed: "保留原預覽與操作識別；查回不會改取較新的內容。",
		capture_unknown: "提交結果尚未確認。請查回同一筆擷取；原草稿與操作 key 已保留。",
		capture_saved: "已保存固定附件版本，可在附件選擇中使用：",
		capture_scope_observe: "預覽需要 observe 權限。",
		capture_scope_manage: "保存需要 manage 與 observe 權限及中央擷取能力。",
		capture_manual_only: "來源必須是中央明確觀測為人工建立的完整 session。",
		capture_invalid_preview: "中央預覽與選定來源不符。",
		capture_invalid_result: "無法查證已保存附件的固定版本與擷取來源。",
		obs_unknown: "未知",
		obs_state_evidence: "分項狀態與證據",
		obs_lifecycle_note: "閒置、未載入或沒有分頁都不代表結束；沒有結束證據就保留未知。",
		obs_discovery: "Discovery 涵蓋範圍",
		obs_discovery_note: "這裡顯示中央已記錄的掃描範圍，不會另行掃描主機；沒有看見不代表不存在。",
		obs_scan_status: "最近掃描",
		obs_last_success: "最後成功觀測",
		obs_last_attempt: "最近查詢完成",
		obs_authority: "觀測授權",
		obs_verified: "已驗證",
		obs_unverified: "未驗證",
		obs_scan_coverage: "讀取方式、範圍與失敗",
		obs_outside_scan: "未涵蓋的範圍",
		obs_no_scan: "尚未記錄這台主機的掃描證據。",
		obs_new_facts: "Journal 有新紀錄。已載入的頁面仍保持原快照；可重新讀取此資源。",
		obs_event_kind: "事件 kind（選填）",
		obs_execution_filter: "Execution ID（選填）",
		obs_read_latest: "讀取最新紀錄",
		obs_evidence: "原始 ID 與證據",
		obs_occurred: "發生時間",
		obs_recorded: "記錄時間",
		obs_pending_binding: "尚未綁定 session",
		obs_half_open: "序號區間 [{start}, {end})",
		obs_follow_up: "接續執行",
		obs_empty: "這個範圍沒有已記錄的證據。",
		obs_snapshot: "固定 journal 快照：{seq}。",
		obs_historical_limits: "早期歷程可能不完整；未知時間不會推測。",
		obs_first_recorded: "最早記錄",
		obs_relations: "Execution 與 Session 關係",
		obs_history: "資源歷程",
		obs_include_closed: "包含已關閉關係",
		obs_execution: "Execution",
		obs_worktree: "Worktree",
		obs_known_identity: "顯示中央的已知資源 ID；關係與歷程不授予操作權限。",
		obs_inventory_note: "依穩定 ID 巡覽，保留已載入頁數。列表反映持續變化的觀測，不是隔離快照。",
		obs_axis_connection: "連線",
		obs_axis_loading: "載入",
		obs_axis_tab: "分頁",
		obs_axis_activity: "活動",
		obs_axis_lifecycle: "生命週期",
		obs_axis_enumeration: "列舉",
		obs_axis_freshness: "資料新鮮度",
		obs_value_unknown: "未知",
		obs_value_connected: "已連線",
		obs_value_not_connected: "未連線",
		obs_value_loaded: "已載入",
		obs_value_not_loaded: "未載入",
		obs_value_present: "存在",
		obs_value_no_tab: "沒有分頁",
		obs_value_starting: "啟動中",
		obs_value_streaming: "輸出中",
		obs_value_not_streaming: "未輸出",
		obs_value_active: "運作中",
		obs_value_ended: "已結束",
		obs_value_gone: "已離開列舉",
		obs_value_missing: "本次未列舉",
		obs_value_fresh: "新鮮",
		obs_value_stale: "過期",
		obs_scope_other_profiles_and_hosts: "其他 profile 與主機",
		obs_scope_manual_sessions_without_tabs_or_facts: "沒有分頁或事實的手動 session",
		obs_scope_arbitrary_transcripts: "未綁定的逐字稿",
		obs_scope_codex_rollouts: "Codex rollout 掃描",
		obs_scope_background_git_state: "背景 Git 狀態探測",
		obs_scope_earlier_history: "較早的歷程",
		parent_archived: "這個項目或所屬專案已封存；編輯草稿仍保留。",
		pending_changed: "待回覆的問題已改變；草稿仍保留。請查看目前的要求後重新作答。",
		files_unavailable: "目前連線無法取回原傳輸。從草稿移除不會取消上傳。",
		files_choose: "選擇檔案",
		files_help: "檔案內容會在選取時固定；完成驗證後即可加入附件。",
		files_drop: "啟用拖放",
		files_drop_help: "將檔案拖入視窗，再按「上傳」加入這份草稿。",
		files_upload: "上傳",
		files_progress: "本機傳輸進度",
		files_stop: "停止傳輸",
		files_retry: "重試原傳輸",
		files_check: "查回結果",
		files_cancel: "取消上傳",
		files_discard: "清除本機紀錄",
		files_save: "另存新檔",
		files_preview: "預覽",
		files_selected: "已選取",
		files_checking: "查核原操作",
		files_uploading: "傳送中",
		files_verifying: "驗證中",
		files_downloading: "下載中",
		files_saving: "儲存中",
		files_ready: "已驗證",
		files_saved: "已儲存",
		files_stopped: "已停止，結果保留",
		files_failed: "操作失敗",
		files_cancelled: "已取消",
		files_receipt_mismatch: "傳輸紀錄與原檔案不符，未加入附件。",
		attachment_file_changed: "請重新選擇相同檔案以查回原上傳；不同內容請先移除這一項。",
		attachment_pending: "上傳結果仍待確認。請以相同檔案重試原操作。",
		existing_artifact: "已上傳附件",
		add_attachment: "加入附件",
		attachments: "附件",
		choose_attachments: "選擇附件",
		upload_on_choose: "選擇檔案後立即上傳。成功上傳的版本會隨草稿保存。",
		choose_again: "請重新選擇這個檔案。瀏覽器無法在重新載入後開啟本機檔案。",
		uploading: "正在上傳…",
		retry: "重試",
		attachment_role: "附件用途",
		attachment_input: "輸入",
		attachment_result: "成果",
		attachments_not_ready: "請先完成附件上傳或移除未完成的檔案。",
		source_unavailable: "無法讀取來源 HEAD，保留草稿；恢復連線後再試。",
		confirm_source: "確認保留原版本與附件，繼續同一派工",
		materializations: "附件傳輸",
		material_pending: "待傳輸",
		material_transferring: "傳輸中",
		material_uncertain: "待確認",
		material_verified: "已驗證",
		material_blocked: "受阻",
		"nav_cleanup": "整理與復原",
		"cleanup_target": "選擇整理範圍",
		"cleanup_target_work_item": "工作項目",
		"cleanup_target_task": "執行任務",
		"cleanup_task_preview": "預覽此任務的資源整理",
		"cleanup_check": "查回原整理操作",
		"cleanup_new": "預覽另一筆整理",
		"cleanup_invalid_result": "操作回應與原整理請求不符。",
		"cleanup_task_help": "任務整理使用完整任務 ID，由中央檢查結束狀態、共用資源與未確認指令。未提交的任務內容與分支仍保留；不會刪除任務歷史。",
		"cleanup_target_checkpoint": "Checkpoint",
		"cleanup_target_integration": "整合操作",
		"cleanup_target_host": "主機",
		"cleanup_id": "主機名稱或原始 ID",
		"cleanup_children": "包含子工作項目",
		"cleanup_intro": "先查看實際資源與保留原因，再回收資源。工作脈絡、回執與原始 ID 永久可查。",
		"cleanup_repreview": "選擇或實際狀態已改變。執行前請重新預覽。",
		"cleanup_retry_same": "未收到明確回覆。請再次執行，使用原預覽與相同 key 查回原操作；不要另建清理。",
		"cleanup_preview": "預覽整理",
		"cleanup_apply": "執行已審閱的整理",
		"cleanup_reviewed": "我已查看這份預覽的資源、保留內容與丟棄選擇。",
		"cleanup_scope": "執行需要 cleanup 權限。",
		"cleanup_counts": "回收 {reclaim} 個資源 · 保留 {retain} 個",
		"cleanup_expires": "預覽到期時間：{time}（15 分鐘）。",
		"cleanup_blocked": "所有資源都保留。請查看每項的原因。",
		"cleanup_commit_kept": "保留 commit",
		"cleanup_not_delivered": "成果尚未送達。釋放後仍保留 commits 與本機 branch。",
		"cleanup_release": "釋放這個 worktree；保留尚未送達的 commits 與 branch",
		"cleanup_discard": "永久丟棄未提交的檔案（需要 cleanup_discard）",
		"cleanup_plan": "執行計畫",
		"cleanup_evidence": "ID、證據與送達涵蓋範圍",
		"cleanup_open_receipts": "查看逐項回執",
		"cleanup_history": "永久整理紀錄",
		"cleanup_retained": "實際保留的內容",
		"cleanup_retained_help": "從主機驗證 refs 與 commit objects。目前只提供保留內容列表；runtime 不會復活。",
		"cleanup_search": "搜尋原始 ID、舊位置或 PR",
		"cleanup_search_button": "搜尋",
		"cleanup_empty_history": "還沒有整理紀錄。",
		"cleanup_empty_retained": "還沒有已記錄的保留內容。",
		"cleanup_unavailable": "無法驗證主機或保留 objects。",
		"cleanup_reason_reviewed": "由審閱後的整理操作移除。",
		"cleanup_reason_automatic": "由任務服務自動整理，保留內容與操作回執。",
		"cleanup_reason_historical": "依過往任務整理事件保存的歷史紀錄；並非本次審閱操作。",
		"cleanup_reason_recorded": "已有整理紀錄，詳細來源請見回執。",
		"cleanup_choice_UNCOMMITTED_CHANGES": "已選擇永久丟棄未提交內容。",
		"cleanup_choice_RESULTS_NOT_DELIVERED": "已選擇釋放；保留尚未送達的 commits 與 branch。",
		"cleanup_kind_session": "Session",
		"cleanup_kind_worktree": "Worktree",
		"cleanup_kind_local_branch": "本機 branch",
		"cleanup_kind_clone": "Managed clone",
		"cleanup_kind_integration_area": "整合區",
		"cleanup_kind_git_pin": "Git pin",
		"cleanup_kind_source": "原始來源",
		"cleanup_kind_artifact": "附件參照",
		"cleanup_kind_temporary": "暫存",
		"cleanup_kind_retained_ref": "保留 ref",
		"cleanup_decision_retain": "保留",
		"cleanup_decision_reclaim": "回收",
		"cleanup_decision_already_absent": "已不存在",
		"cleanup_step_preserve": "Pin commit",
		"cleanup_step_stop": "停止 session",
		"cleanup_step_discard": "丟棄檔案",
		"cleanup_step_remove.worktree": "移除 worktree",
		"cleanup_step_remove.branch": "刪除已送達 branch",
		"cleanup_step_finalize": "保存回執",
		"cleanup_step_remove.temporary": "移除指定暫存",
		"cleanup_kind_remote": "遠端資源",
		"cleanup_reason_TIER_DISABLED": "主機的 write／orchestrate tier 未啟用。",
		"cleanup_reason_MANUAL_READ_ONLY": "人工建立，永遠唯讀。",
		"cleanup_reason_UNKNOWN_READ_ONLY": "無法證明建立來源。",
		"cleanup_reason_WORKDIR_NOT_MANAGED": "工作目錄不在 managed roots 內。",
		"cleanup_reason_BINDING_MISMATCH": "資源與建立時的綁定不符。",
		"cleanup_reason_CLONE_NOT_OURS": "沒有符合的 Connector 建立標記。",
		"cleanup_reason_CLONE_CONFIG_TAMPERED": "Repository 設定或 object 儲存不安全。",
		"cleanup_reason_OBSERVATION_UNAVAILABLE": "無法在主機讀取期限內觀測。",
		"cleanup_reason_ACTIVE_WRITER": "Session 正在串流或寫入。",
		"cleanup_reason_SESSION_WAITING": "Session 有待回答問題、權限或排隊指令。",
		"cleanup_reason_COMMAND_UNRESOLVED": "指令或外部步驟的結果尚未確認。",
		"cleanup_reason_ACTIVE_EXECUTION": "另一個執行仍需要資源。",
		"cleanup_reason_CONTENT_REQUIRED": "有效整合預覽或執行仍需要內容。",
		"cleanup_reason_TASK_OWNED": "此資源屬於執行任務，須在該任務範圍確認可整理；目前仍保留。",
		"cleanup_reason_RETAINED_COPY": "保留原分支作為內容副本。",
		"cleanup_reason_UNCOMMITTED_CHANGES": "有未提交、未追蹤或 ignored 內容。",
		"cleanup_reason_RESULTS_NOT_DELIVERED": "送達回執未涵蓋全部結果 commits。",
		"cleanup_reason_DELIVERY_UNCERTAIN": "送達結果尚未確認。",
		"cleanup_reason_RETENTION_RULE": "明確保留規則仍需要內容。",
		"cleanup_reason_SHARED_CONTAINER": "這個載體有共用資源。",
		"cleanup_reason_RETAINED_CONTENT_STORE": "載體或 pin 保留成果與證據。",
		"cleanup_reason_REMOTE_OUT_OF_SCOPE": "遠端 branch 刪除是另一個動作。",
		"cleanup_reason_RESOURCE_KIND_UNSUPPORTED": "這類資源或 Git 狀態沒有整理 adapter。",
		"cleanup_reason_RESOURCE_CLEANED": "這一代資源已有已確認的整理紀錄。",
		"cleanup_reason_CLEANUP_IN_PROGRESS": "整理操作已保留這個資源。",
		"cleanup_receipt_retained": "保留",
		"cleanup_receipt_pending": "等待",
		"cleanup_receipt_running": "執行中",
		"cleanup_receipt_succeeded": "完成",
		"cleanup_receipt_already_absent": "已不存在",
		"cleanup_receipt_failed": "失敗",
		"cleanup_receipt_uncertain": "待確認結果",
		"cleanup_receipt_blocked_stale": "狀態改變",
		"cleanup_receipt_cancelled": "已取消",
		dep_pull_request: "合併請求（PR）",
		dep_desired: "選定部署",
		dep_observed: "目前觀測版本",
		dep_last_verified: "最後驗證版本",
		dep_history: "部署歷史",
		dep_no_history: "尚無部署紀錄。",
		dep_no_version: "尚無版本紀錄。",
		dep_not_observed: "尚未觀測",
		dep_observed_at: "觀測時間：{time}",
		dep_verified_at: "驗證時間：{time}",
		dep_artifact: "產物 {id}",
		dep_not_undone: "回退不會撤銷",
		dep_no_limits: "此部署設定未宣告無法撤銷的副作用。",
		dep_rollback: "回退到此版本",
		dep_retry: "重試部署 · {sha}",
		dep_confirm_rollback: "開始回退",
		dep_confirm_retry: "重試此部署",
		dep_rollback_review: "檢視回退版本",
		dep_retry_review: "檢視重試部署",
		dep_retry_only: "重新部署此固定版本，不會再次合併 PR。",
		dep_retry_unavailable: "此舊紀錄缺少可重試的固定版本，請重新預覽部署。",
		dep_preview_generation: "{env} · 環境第 {generation} 代",
		dep_stale_preview: "環境或部署設定已變更。請檢視下方最新預覽，再決定是否重新送出。不會自動重送。",
		dep_refused: "部署請求未能繼續，請查看操作詳情。",
		dep_open_operation: "查看操作",
		dep_operation_details: "操作詳情",
		dep_run: "服務商執行紀錄",
		dep_attempt: "執行次數",
		dep_error_code: "錯誤代碼",
		dep_needs_scope: "需要 deploy 權限。",
		dep_missing_recipe: "此部署設定已移除。",
		dep_missing_verification: "部署已停用：缺少版本驗證設定。",
		dep_disabled: "目前未開放部署。",
		dep_provider_pending: "服務商的執行結果仍待確認，尚不能重試。",
		dep_attention: "需要處理",
		dep_attention_help: "請比較選定與觀測版本，並先查看操作詳情再決定下一步。",
		dep_drift: "觀測版本與選定部署不同，不會自動啟動部署。",
		dep_superseded: "已被新的選定部署取代。",
		dep_new_desired: "查看新的選定部署",
		dep_provider_run: "原始執行紀錄",
		dep_previous: "上一頁",
		dep_next: "下一頁",
		dep_page: "第 {page} 頁",
		dep_ROLLBACK_UNSUPPORTED: "此部署設定不支援回退。",
		dep_ROLLBACK_TARGET_INVALID: "此版本未經驗證，或屬於不同部署設定／環境。",
		dep_ROLLBACK_ARTIFACT_UNAVAILABLE: "保存的產物無法取得。",
		dep_ROLLBACK_ARTIFACT_EXPIRED: "保存的產物已過期。",
		dep_version_health: "已驗證執行環境版本與健康。",
		dep_version_only: "已驗證執行環境版本；此部署設定不檢查健康。",
		dep_health_only: "健康檢查通過；此部署設定不檢查執行環境版本。",
		dep_state_selected: "已選定",
		dep_state_waiting_order: "等待環境順序",
		dep_state_queued: "已排程",
		dep_state_building: "建置中",
		dep_state_waiting_environment: "等待環境核准",
		dep_state_deploying: "部署中",
		dep_state_verifying: "驗證中",
		dep_state_succeeded: "已驗證",
		dep_state_failed: "失敗",
		dep_state_cancelled: "已取消",
		dep_state_uncertain: "結果未明",
		dep_state_needs_attention: "需要處理",
		dep_state_unverified: "未驗證",
		dep_state_superseded: "已被取代",
		dep_operation: "操作",
		dep_status: "狀態",
		dep_generation: "環境第 {generation} 代",
		offline_actions_paused: "中央離線，暫停操作",
		sync_waiting: "等待更新，草稿已保留",
		desktop_add_credential: "新增憑證",
		desktop_replace_credential: "更換憑證",
		desktop_forget_credential: "移除此電腦儲存的憑證",
		desktop_reload_configuration: "重新載入設定",
		desktop_connecting: "正在處理連線…",
		desktop_setup_help: "先連接你已有的中央服務。輸入位址與預期帳號，再到原生視窗確認儲存。",
		desktop_setup_origin: "使用 HTTPS 位址；已建立的本機通道可用 http://127.0.0.1:連接埠。此處不需輸入權杖。",
		desktop_setup_review: "檢視連線設定",
		desktop_setup_saved: "設定已儲存。請新增憑證並驗證身分。",
		desktop_setup_cancelled: "已取消儲存；輸入內容仍保留。",
		desktop_endpoint: "中央位置",
		desktop_expected_actor: "預期身分",
		desktop_configuration_file: "設定檔",
		desktop_credential_source: "憑證來源",
		desktop_source_launch_environment: "本次啟動的記憶體憑證",
		desktop_source_windows_credential_manager: "Windows 認證管理員",
		desktop_source_macos_keychain: "macOS 鑰匙圈",
		desktop_enrollment_help: "在系統安全輸入框中輸入 Connector API 權杖。驗證身分後，才會儲存至此帳戶的保護儲存區，供下次使用。",
		desktop_enrollment_unsupported: "此平台尚未支援保護儲存與憑證輸入。可使用啟動時提供的記憶體憑證；不會儲存至磁碟。",
		desktop_forget_help: "只移除此電腦的已儲存憑證並中斷連線；不會撤銷中央 token。草稿與原操作識別仍保留。",
		desktop_forgotten: "已移除本機憑證並中斷連線。",
		desktop_reloaded: "已重新載入設定。請驗證連線；原草稿仍保留。",
		desktop_disconnected: "已中斷連線；中央工作仍繼續。",
		desktop_enrollment_cancelled: "已取消憑證輸入，保留原連線。",
		desktop_connection: "桌面中央連線",
		desktop_local: "本機功能",
		desktop_connect_needed: "請連到已配置的中央 Connector。",
		desktop_polling: "已連線 · 每秒更新",
		desktop_config_needed: "尚未配置中央連線。",
		desktop_credential_missing: "尚未提供可用的本機憑證。",
		desktop_credential_help: "中央位置與身份由本機設定指定；憑證保留在原生程式，不存入此畫面。",
		desktop_dashboard_only: "Dashboard 無需安裝 BAT。Windows 可在本機 Fleet 控制中檢視連線、視窗與登入啟動。關閉視窗會留在系統匣；退出程式會等待所屬 Fleet 連線停止。中央工作仍獨立執行。",
		fleet_login_waiting: "正在等待所選 BAT 工作區就緒，Dashboard 可繼續使用。",
		fleet_login_attention: "登入啟動需要檢查。請先讀取原始啟動結果，再重試。",
		fleet_login_complete: "已處理登入啟動選擇。這不代表 BAT 視窗或工作區已開啟。",
		fleet_retry_migration: "重試相同設定變更",
		fleet_desktop_title: "本機 Fleet 與視窗",
		fleet_independent: "分別選擇連線、BAT 視窗與 Dashboard。儲存選擇不會立即開啟視窗。",
		fleet_connections: "連線",
		fleet_windows_title: "要開啟的視窗",
		fleet_dashboard_choice: "開啟 Dashboard",
		fleet_local_bat: "本機 BAT 視窗",
		fleet_selection_help: "遠端 BAT 視窗需要各自已通過驗證的連線；其他主機連線時，Dashboard 仍可使用。",
		fleet_review_choices: "檢視選擇",
		fleet_save_choices: "儲存已檢視的選擇",
		fleet_prerequisites: "另外需要的連線：{names}。",
		fleet_none: "無",
		fleet_launch_title: "開啟已儲存的選擇",
		fleet_launch_help: "選定的連線就緒後才開啟 BAT 視窗。已開啟的 BAT 視窗會保持原狀。",
		fleet_review_launch: "檢視啟動內容",
		fleet_launch_apply: "開啟已儲存的選擇",
		fleet_retry_launch: "重試原啟動要求",
		fleet_launch_review: "請檢視已儲存的視窗選擇，再開啟。",
		fleet_local_anchor: "若只選遠端設定，BAT 可能也會開啟一個本機視窗。",
		fleet_launch_no_bat: "未要求開啟 BAT 視窗；連線選擇仍獨立生效。",
		fleet_launch_already_running: "BAT 已在執行，原有視窗與設定均已保留。",
		fleet_launch_started: "BAT 程序已啟動，請在其視窗確認連線狀態。",
		fleet_launch_uncertain: "啟動結果尚未確認。再次要求啟動前，請讀取原回執。",
		fleet_launch_not_started: "BAT 未啟動。若要提出新的啟動要求，請重新檢視。",
		fleet_new_launch: "檢視新的啟動要求",
		fleet_login_title: "登入 Windows 時",
		fleet_login_picker: "登入後先顯示選擇，再啟動",
		fleet_backend_title: "連線監控與自動啟動",
		fleet_backend_help: "變更前先檢視目前的監控與登入啟動項目。原設定會保留，供你明確選擇還原。",
		fleet_backend_rust: "原生監控",
		fleet_backend_powershell: "PowerShell 監控",
		fleet_autostart: "登入 Windows 時啟動 Fleet",
		fleet_review_migration: "檢視監控與啟動設定",
		fleet_apply_migration: "套用已檢視的轉換",
		fleet_continue_migration: "繼續原轉換",
		fleet_restore_migration: "還原原設定",
		fleet_new_migration: "檢視新的轉換",
		fleet_migration_review: "監控：{from} → {to}。登入啟動：{before} → {after}。",
		fleet_enabled: "啟用",
		fleet_disabled: "停用",
		fleet_migration_unknown: "轉換已受理或結果未明。請讀取原回執。",
		fleet_migration_prepared: "轉換已儲存；繼續以要求監控正常結束。",
		fleet_migration_quit_requested: "已要求正常結束；監控退出後可繼續。",
		fleet_migration_stopped: "原監控已停止，轉換進行中。",
		fleet_migration_startup_written: "登入啟動項目已儲存，請繼續原轉換。",
		fleet_migration_config_written: "監控設定已儲存，請繼續原轉換。",
		fleet_migration_launch_requested: "已要求啟動新監控；請讀取其結果，不會重複啟動。",
		fleet_migration_complete: "轉換完成。原設定已保留，可明確選擇還原。",
		fleet_title: "本機 Fleet 連線",
		fleet_help: "選擇這台電腦需要的連線；連線選擇與實際就緒狀態分開顯示。",
		fleet_apply: "儲存連線選擇",
		fleet_refresh: "重新讀取狀態",
		fleet_use_current: "使用目前選擇",
		fleet_start: "啟動連線監控",
		fleet_quit: "停止本機連線監控",
		fleet_monitor_running: "監控執行中",
		fleet_monitor_stopped: "監控已停止",
		fleet_ready: "就緒",
		fleet_degraded: "部分可用",
		fleet_down: "無法連線",
		fleet_off: "未啟用",
		fleet_fresh: "最新觀測",
		fleet_stale: "觀測已過期",
		fleet_unavailable: "尚無可用觀測",
		fleet_applied: "監控已讀取目前選擇。",
		fleet_waiting: "等待監控讀取目前選擇。",
		fleet_changed: "連線選擇或監控已變更。草稿已保留；請讀取並檢視目前選擇。",
		fleet_other_owner: "目前監控不屬於這個登入工作階段，僅供檢視。",
		fleet_invalid: "Fleet 設定需要處理（{n} 項）。",
		fleet_windows: "Fleet 連線管理需要 Windows。",
		fleet_setup: "尚未配置 Fleet Kit；請依桌面設定文件指定安裝位置。",
		fleet_working: "正在處理連線設定…",
		fleet_saved: "設定已儲存；就緒狀態由監控回報。",
		fleet_quit_requested: "已請求停止監控；正在等候狀態更新。",
		fleet_unknown: "結果尚未確定，草稿已保留。重新讀取狀態後再操作。",
		fleet_read_failed: "無法讀取 Fleet；操作已暫停。",
		merge_scope_reload: "PR 範圍已變更，已保留你選定的預覽。請重新讀取並檢視後再合併。",
		metadata_diff: "內容比較",
		metadata_before: "寫前",
		metadata_intended: "預期",
		metadata_observed: "讀回",
		scope_stack_rebase: "上層分支將重整",
		scope_dependency: "分支相依",
		metadata_edit: "編輯 PR 標題與說明",
		metadata_title: "PR 標題",
		metadata_disabled: "此 repository 尚未啟用 allow_pr_update。",
		metadata_race_limit: "儲存前比較標題與說明，寫後再次讀回。GitHub 沒有原子比對寫入，最後讀取與寫入間仍可能覆蓋同時發生的編輯。",
		metadata_result_help: "操作詳情保留寫前、預期與讀回內容。若有衝突，先重新讀取再編輯；不自動覆蓋或還原。",
		metadata_pending: "PR 已修改，讀回驗證仍待完成。",
		merge_scope: "合併範圍",
		merge_method: "合併方式",
		merge_commit_range: "查看完整 BASE..HEAD：{count} 個 commits",
		merge_preview_fixed: "此預覽固定 head、base 與範圍；更換方式需重新讀取。",
		scope_single_pr: "未發現其他 PR 會被合併。",
		scope_native_stack: "原生 stack",
		scope_branch_chain: "相依分支 chain",
		scope_indirect_merge: "間接合併候選",
		scope_would_merge: "影響其他 PR",
		scope_candidate: "已包含的 commits",
		merged_newer_base: "合併到較新的 base：另有 {count} 個 commits 會一起發布。",
		close: "關閉",
		nav_projects: "專案",
		projects_help: "專案與工作項目是 Connector 自己的紀錄：目標、需求原文、驗收、步驟，以及做這件事的 sessions、版本、操作與 PR。改名不會改 ID；排序與固定只影響顯示。",
		new_project_name: "新專案名稱",
		add_project: "新增",
		show_archived: "顯示已封存",
		no_projects: "還沒有專案。",
		project_repository_optional: "派工儲存庫（選填）",
		project_repository_later: "稍後選擇",
		new_sub_project: "子專案名稱",
		rename: "改名",
		archive: "封存",
		restore: "復原",
		more: "更多",
		move_up: "上移",
		move_down: "下移",
		pin: "固定在上方",
		unpin: "取消固定",
		wi_done_of: "完成 {done}/{total}",
		wi_state_todo: "未開始",
		wi_state_doing: "進行中",
		wi_state_waiting: "等待中",
		wi_state_done: "已完成",
		wi_state_awaiting_approval: "待確認完成",
		wi_err_VERSION_CONFLICT: "這筆資料剛被改過，已重新載入最新內容（你在表單裡的修改還在）；確認後再存一次。",
		linked_back: "已連回這個工作項目",
		wi_err_ORDER_CHANGED: "順序剛被改過，已重新載入；請再排一次。",
		wi_err_PIN_CHANGED: "固定狀態剛被改過，已重新載入。",
		wi_err_CONTENT_CHANGED: "內容在你確認時被改過；請看過新的內容再決定。",
		wi_err_NAME_TAKEN: "已有同名的專案。",
		wi_err_HAS_CHILDREN: "請先封存它的子專案。",
		wi_err_PARENT_ARCHIVED: "上層已封存，請先復原上層。",
		wi_err_PINNED_FIRST: "固定的項目一定在未固定的上面；要往下移請先取消固定。",
		wi_err_STEPS_OPEN: "還有沒勾的步驟；勾完（或刪掉不需要的步驟）再標完成。",
		wi_err_CYCLE: "不能移到自己底下。",
		wi_err_LINK_TARGET_NOT_FOUND: "找不到這個連結對象（Connector 沒看過它）。",
		wi_err_NOTHING_TO_DECIDE: "沒有人回報完成，不需要決定。",
		new_item_title: "新工作項目",
		add_item: "新增",
		work_items: "工作項目",
		name: "名稱",
		description: "說明",
		repositories: "Repositories",
		task_project: "Task Service 專案名稱",
		save: "儲存",
		archived: "已封存",
		sub_projects: "子專案",
		new_child_item: "子項目名稱",
		new_branch_item: "分支項目名稱（與它同一層）",
		archive_with_children: "封存（連同子項目）",
		needs_decision: "等你決定",
		no_items: "還沒有工作項目。",
		link_missing: "已找不到",
		needs_manage_scope: "你的 token 沒有 manage 權限，不能修改專案與工作項目；用 --scope manage 重新發 token。",
		needs_approve_scope: "你的 token 沒有 approve 權限，不能確認完成；用 --scope approve 重新發 token。",
		accept_done: "確認完成",
		mark_done: "標記完成",
		keep_working: "還沒完成，繼續",
		approved_by: "{who} 已確認完成（{time}）。內容再被修改時會重新等待確認。",
		claimed_done: "{who} 回報已完成，等你確認。確認的是你現在看到的內容。",
		steps_all_checked: "步驟都勾完了。要標記完成，還是繼續？",
		goal: "目標",
		request: "需求原文",
		acceptance: "驗收條件",
		steps_title: "步驟",
		parent_id: "上層",
		remove: "移除",
		new_step: "新步驟",
		link_session: "Session",
		link_checkpoint: "版本",
		link_operation: "操作",
		link_task: "任務",
		link_pull_request: "PR",
		link_ref_hint: "對象",
		link_ref_session: "host/session_id",
		link_ref_checkpoint: "cp_…",
		link_ref_operation: "op_…",
		link_ref_task: "task ID",
		link_ref_pull_request: "owner/name#123",
		link: "連結",
		links: "相關資源",
		no_links: "還沒有連結。",
		no_steps: "沒有步驟。",
		children: "子項目",
		derived: "從這裡分出的項目",
		history: "紀錄",
		derived_from: "分支自",
		start_from_checkpoint: "從這個版本派工",
		claimed_by: "{who} 回報完成",
		linked_items: "相關工作項目",
		ev_work_item_created: "建立",
		ev_work_item_updated: "修改",
		ev_work_item_state: "狀態",
		ev_work_item_approved: "確認完成",
		ev_work_item_continued: "退回繼續",
		ev_work_item_linked: "加上連結",
		ev_work_item_unlinked: "移除連結",
		ev_work_item_archived: "封存",
		ev_work_item_restored: "復原",
		ev_work_item_pinned: "固定",
		ev_work_item_unpinned: "取消固定",
		nav_home: "待處理",
		nav_sessions: "工作階段",
		nav_delivery: "成果與 GitHub",
		nav_operations: "操作紀錄",
		nav_settings: "連線",
		tab_needs_you: "需要你處理",
		tab_to_confirm: "待確認",
		attention_tab_needs: "需要你處理",
		attention_tab_active: "執行中操作",
		attention_tab_unread: "未讀工作更新",
		attention_replies: "待回覆與權限",
		attention_replies_note: "依中央實際問題與權限請求列出；閱讀不會解除請求。",
		attention_completion: "完成確認",
		attention_completion_note: "工作回報完成或步驟已勾完，仍需你確認或退回繼續。",
		attention_problems: "需處理的操作",
		attention_problems_note: "包含結果尚不確定的操作；先查看原操作與回執。",
		attention_hosts: "主機連線",
		attention_hosts_note: "連不上或觀測過期的主機；不據此判定工作已結束。",
		attention_active: "執行中操作",
		attention_active_note: "已受理、執行中或等待外部條件的操作；這不是工作完成確認。",
		attention_unread: "未讀工作更新",
		attention_unread_note: "尚未標記已讀的工作項目版本，包含先前已有的項目；不代表未讀訊息數。",
		attention_loaded: "已載入 {count} 筆（非總數）",
		attention_empty: "這一類目前沒有項目。",
		attention_not_updated: "本次未能更新；若下方有資料，仍是上次讀取的內容。",
		attention_invalid: "清單回應不完整，請重新讀取。",
		reading_unread: "未讀更新",
		reading_read: "此版本已讀",
		reading_mark: "標記此版本已讀",
		reading_note: "已讀只記錄你看過的工作項目版本，會同步至同一身分的其他入口；不會確認完成或解除待回覆。",
		ev_work_item_read: "標記已讀",
		reading_newer: "中央已有較新版本；目前顯示的內容與未提交編輯仍保留，關閉編輯後會更新。",
		empty_needs_you: "目前沒有需要你處理的項目。",
		empty_to_confirm: "沒有等待確認的操作。",
		stale: "資料過期",
		stale_reason_host_unreachable: "主機連不上",
		stale_reason_host_not_refreshed: "很久沒更新",
		stale_reason_not_enumerated: "上次列舉沒有出現",
		stale_reason_gone: "已不存在",
		stale_reason_never_observed: "尚未觀測",
		read_only: "API 唯讀",
		managed: "Connector 管理",
		provenance_manual: "人工建立（BAT）",
		provenance_connector_managed: "Connector 建立",
		provenance_unknown: "來源不明",
		state_streaming: "執行中",
		state_loaded: "已載入",
		state_unloaded: "未載入",
		pending_ask_user: "等你回答",
		pending_permission: "等待權限",
		host: "主機",
		workspace: "Workspace",
		title: "標題",
		agent: "Agent",
		state: "狀態",
		activity: "最後活動",
		observed: "觀測時間",
		all_hosts: "全部主機",
		all_access: "全部",
		only_managed: "只看 Connector 管理",
		only_read_only: "只看唯讀",
		load_more: "載入更多",
		messages: "對話",
		send: "送出",
		send_placeholder: "給這個 managed session 的訊息…",
		interrupt: "中斷這一輪",
		answer: "回答",
		allow: "允許",
		deny: "拒絕",
		read_only_note: "這個 session 由人在 BAT 建立，API 永久唯讀：不送字、不回答、不中斷。要讓 agent 接續，請從它的 commit 另開 managed 工作。",
		continue_from_checkpoint: "從此版本建立 agent 工作",
		checkpoints: "版本（checkpoint）",
		checkpoint_help: "記下這個 session 目前的 commit 與最近對話（只讀，不改動原 session 或資料夾）。從版本開始的 agent 工作會在 Connector 自己的 clone 裡用新的 branch 與 session 進行。",
		create_checkpoint: "記下這個版本",
		no_checkpoints: "還沒有記下的版本。",
		excerpt_count: "{n} 則對話",
		commit: "Commit",
		checkpoint_note_placeholder: "接下來要做什麼（原文，會一併記下，選填）…",
		dirty_unknown: "未提交的修改：未觀測（這台主機沒有 SSH alias）；不會帶入新工作。",
		source_advanced: "來源已有更新的 commit；這個版本仍固定在原 commit。要帶入新版本請再記一次。",
		started_from: "這個 session 從版本 {commit} 開出：",
		source_session: "來源 session",
		dirty_warning: "記錄時有 {n} 個未提交的修改，不會帶入新工作。",
		continue_placeholder: "要 agent 接著做什麼…",
		start_agent_work: "開始 agent 工作",
		open_new_session: "開啟新 session",
		checkpoint_unavailable: "這台主機尚未設定 managed_roots、SSH alias 或 write／orchestrate 權限，不能從版本開工。",
		needs_start_scope: "你的 token 沒有 start 權限，不能開新的 agent 工作；用 --scope start 重新發 token。",
		confined_note: "工作目錄本身不提供保護。限制取決於啟動選項及帳號證據；個別批准可能允許外部寫入。",
		confinement_none: "無已證實的執行限制",
		confinement_prompt_gated: "權限詢問控管",
		confinement_host_account: "帳號限制",
		confinement_os_sandbox: "OS sandbox",
		confinement_os_pending: "OS sandbox（尚未實機驗證）",
		confinement_evidence: "限制證據",
		confinement_creation: "建立時限制",
		confinement_current: "目前核對",
		confinement_options: "啟動選項",
		confinement_gap: "尚未涵蓋",
		confinement_status_verified: "已查核",
		confinement_status_options_confirmed: "選項已核對",
		confinement_current_unknown: "目前限制未知",
		confinement_current_mismatch: "目前限制與紀錄不符",
		confinement_status_unknown: "未知",
		confinement_status_mismatch: "與紀錄不符",
		confinement_status_pending: "等待核對",
		confinement_gap_sandbox_enforcement_unverified: "尚未由 W12 實機驗證阻擋效果",
		confinement_gap_prompt_rules_are_not_os_isolation: "既有批准規則及 shell 可能允許外部寫入",
		confinement_gap_task_recipe_compatibility: "保留 Task Service 測試行為；未新增執行限制",
		confinement_gap_execution_restriction_unverified: "尚無執行限制證據",
		confinement_gap_legacy_evidence_missing: "舊 session 缺建立時證據；不自動升級",
		confinement_claude_note: "Claude 使用 default：未預先授權的編輯及 Bash 會詢問。既有批准規則仍適用，沒有 OS 寫入隔離。建議使用 Codex；個別批准可能允許外部寫入。",
		confinement_codex_note: "Codex 使用 workspace-write／on-request。未完成實機阻擋驗證；網路及可寫 roots 無法由 BAT 設定，安裝與 localhost 測試可能受限。個別批准可能越過限制。",
		confinement_account_note: "已查核 BAT 帳號不能寫宣告的私人 roots。Claude 可使用 acceptEdits；限制只涵蓋已查核的 roots，啟動前會重新核對。",
		confinement_account_blocked: "已宣告帳號限制，但查核尚未通過；新 session 會被拒絕。請修正主機配置。原因：{reason}。",
		confinement_account_recheck: "啟動 session 時會重新查核帳號限制。通過後，Claude 可使用 acceptEdits；若僅缺少可降級處理的環境加固條件，Claude 仍可用 default 啟動。其他查核失敗會拒絕啟動。",
		confinement_account_fallback: "帳號查核回報 {reason}。Claude 會使用 default，不啟用 acceptEdits。",
		repository: "Repository",
		pull_number: "PR 編號",
		load_pr: "讀取 PR",
		head: "Head",
		base: "Base",
		checks: "Checks",
		checks_summary: "{total} 個，{pending} 個未完成，{failed} 個失敗",
		mergeable: "可合併狀態",
		merge: "合併 PR",
		deploy_to: "部署到 {env}",
		merge_and_deploy_to: "合併並部署到 {env}",
		retry_deploy: "重試部署這個版本",
		merged_sha: "實際合併版本",
		op_accepted: "已受理",
		op_running: "執行中",
		op_waiting_checks: "等待 checks",
		op_waiting_external: "等待 GitHub／部署",
		op_needs_attention: "需要處理",
		op_uncertain: "結果不明，回查中",
		op_succeeded: "完成",
		op_failed: "失敗",
		op_cancelled: "已取消",
		cancel: "取消",
		resume: "重新執行",
		resume_help: "處理完原因後再跑一次：已完成的步驟不重做，未確定的步驟先回查，不會重送。",
		steps: "步驟",
		action: "動作",
		actor: "操作者",
		created: "建立時間",
		error: "錯誤",
		reason: "原因",
		token: "API token",
		token_help: "以 batc api-token issue 發行；只存在這台瀏覽器。",
		connect: "連線",
		remember: "在這台電腦記住",
		disconnect: "中斷",
		connected_as: "已連線：{actor}（{scopes}）",
		need_token: "請先在「連線」輸入 API token。",
		unreachable_hosts: "主機異常",
		loading: "載入中…",
		forbidden_scope: "你的 token 沒有這個權限。",
		queue_behind: "排在目前這一輪之後",
		no_messages: "還沒有訊息。",
		update_pr_results: "更新 PR 成果",
		update_pr_help: "把選定的成果整合進這個 PR 的 head：一般 push，不會強制覆蓋；不會改動你本機的資料夾。",
		needs_integrate_scope: "需要 integrate 權限：用 --scope integrate 重新發 token。",
		integration_no_host: "這個 repository 的 integrate 主機目前都沒有 SSH alias、managed root 或 write／orchestrate 權限。",
		kind_checkpoint: "你的 checkpoint",
		kind_checkpoint_run: "agent 成果",
		kind_branch: "GitHub 分支",
		previewing: "預覽中…（第一次會建立 managed 整合區，可能需要幾分鐘）",
		start_integration_conflict: "開始整合（第 {n} 項預計衝突，會停下讓你處理）",
		normal_push: "一般 push",
		push_access_ok: "可推送",
		push_access_denied: "這台主機的 git 憑證無法推送（請設定 deploy key 或憑證）",
		push_access_unknown: "推送權限未確認",
		plan_fast_forward: "快轉",
		plan_merge: "合併",
		plan_pick: "挑選",
		plan_already_included: "已在 PR 中",
		plan_conflict: "預計衝突",
		plan_not_predicted: "未檢查",
		plan_unrelated: "沒有共同歷史",
		n_commits: "{n} 個 commit",
		n_files: "{n} 個檔案",
		foreign_commit: "不屬於所選來源",
		overlapping_files: "重疊檔案：",
		preview_expired: "預覽已過期（超過 1 小時或 PR head 已變更）。",
		previewed_at: "預覽於 {time} · 1 小時內有效",
		preview_again: "重新預覽",
		branch_on_github: "GitHub 上的分支名稱",
		add: "加入",
		add_branch: "加入分支",
		delivered_to: "已送進 #{n}",
		agent_results: "agent 成果",
		your_checkpoints: "你的 checkpoint",
		still_working: "執行中",
		done: "已完成",
		none: "沒有",
		selected_in_order: "已選（依序整合）",
		integration_done: "PR 已更新：{old} → {new}，加入 {n} 個 commit。你本機的資料夾不會自動更新；要同步請在 BAT 裡 pull。",
		integration_INTEGRATION_CONFLICT: "有一項衝突。前面的項目已在 Connector 的整合區完成，尚未推送。可以交給 agent 在整合區解衝突，或取消後不含它重新預覽。",
		integration_RESOLUTION_INCOMPLETE: "衝突還沒解完（還沒 commit）。等 agent 完成 `git commit --no-edit` 後按「重新執行」。",
		integration_RESOLUTION_INVALID: "解衝突的結果不符合要求（要剛好一個 merge commit、沒有未提交修改或衝突標記）；修好後按「重新執行」。",
		integration_waiting_resolver: "等 agent 解完衝突（它還在工作）",
		hand_to_agent: "交給 agent 解衝突",
		handoff_started: "已開始解衝突的 session；它 commit 之後按「重新執行」。",
		integration_REMOTE_MOVED: "PR 在整合時有新的推送，沒有覆蓋它，也沒有推送。請取消並以最新版本重新預覽。",
		integration_PUSH_REJECTED: "GitHub 拒絕這次推送（保護規則或簽章要求）。",
		integration_PUSH_AUTH_FAILED: "這台主機的 git 憑證無法推送；修好後按「重新執行」。",
		integration_REMOTE_REWOUND_BEFORE_PUSH: "已推送，但推送前分支被往回改過；請看一下 PR，再按「重新執行」完成。",
		integration_REMOTE_REF_RECREATED: "已推送，但推送前分支被刪除過；請看一下 PR，再按「重新執行」完成。",
		integration_UNCERTAIN_UNRESOLVED: "推送結果還無法確認（讀不到遠端）；Connector 不會重推。",
		integration_uncertain: "推送結果確認中（Connector 會先讀遠端，不會重推）",
		integration_waiting: "已推送，等待 GitHub 顯示新的 head",
		integration_running: "正在更新 PR…",
		cancel_and_preview: "取消並重新預覽",
		receipts: "各來源紀錄",
		receipt_pending: "待處理",
		receipt_composed: "已整合（未推送）",
		receipt_already_included: "已在 PR 中",
		receipt_conflict: "衝突",
		receipt_delivered: "已送達",
		receipt_not_delivered: "未送達",
		receipt_unknown: "不確定（推送結果未證實）",
		receipt_resolved: "已解衝突（未推送）",
		integration_PUSH_UNPROVEN: "PR 分支在舊的 head，但組合後的 commit 已在 GitHub 上：之前的推送可能落地後被改回。不會再推一次；請看一下 PR，再取消並重新預覽。"
	},
	en: {
		managed_browser_connected: "Connected to your local Connector",
		managed_browser_help: "This browser uses your desktop identity. After signing out, reopen Dashboard from the desktop menu.",
		workspace_navigation: "Projects and work",
		workspace_search: "Search loaded projects and work",
		workspace_manage: "Add / manage projects",
		workspace_all_sessions: "All sessions",
		workspace_tools: "Tools",
		workspace_connection: "Connection / Fleet",
		workspace_expand: "Expand {name}",
		workspace_collapse: "Collapse {name}",
		workspace_needs_you: "Needs you",
		workspace_expand_load: "Expand to load work",
		workspace_no_work: "No work yet",
		workspace_no_match: "No matching loaded work.",
		workspace_stale: "The tree could not refresh. Last observed work is retained.",
		workspace_work_details: "Work and results",
		workspace_result: "Results and delivery",
		workspace_result_empty: "No linked result yet. You can record a checkpoint below.",
		workspace_work_missing: "This work is no longer in the current project response. Refresh the work tree.",
		workspace_refresh: "Refresh work tree",
		connection_details: "Connection details and configuration file",
		delivery_repository_input: "Repository or GitHub PR URL",
		needs_manage_access: "This account can view projects but cannot edit them. Ask your administrator for project management access, then replace your credential under Connection.",
		empty_next_work: "To begin new work, choose a project to dispatch from or start a session.",
		start_dispatched: "Started",
		session_access_unknown: "The origin and management permissions of this session have not been confirmed. Actions remain unavailable until valid information is received.",
		session_origin: "Origin",
		delivery_pr_number: "PR number",
		delivery_choose_pr: "Enter a repository and PR number, or paste a GitHub PR URL.",
		delivery_pr_unavailable: "The full details of this PR are unavailable. Load it again to retry.",
		pub_branch_help: "Enter a branch name such as main, or a full ref such as refs/heads/main.",
		pub_branch_invalid: "Enter a valid branch such as main or feature/name. Tags, commits and other refs are not supported.",
		delivery_result_unverified: "Result unverified",
		delivery_observed_at: "Last observed: {time}",
		delivery_unobserved: "No activity observation",
		delivery_source_context: "The original work's source is selected. Choose a repository and PR, then add it to the preview.",
		delivery_source_unavailable: "An eligible result source could not be confirmed.",
		delivery_review_result: "Review result and add to PR",
		delivery_project_work: "Dispatched work",
		delivery_no_work: "No explicitly linked dispatch records yet.",
		delivery_dispatch_state: "Dispatch state:",
		kind_execution: "central execution",
		kind_task_command: "Task Service result",
		delivery_dispatch_accepted: "accepted",
		delivery_worktree_branch: "Branch",
		delivery_worktree_path: "Working directory",
		delivery_worktree_owner: "Creation evidence",
		delivery_worktree_sessions: "Related sessions",
		delivery_worktree_recorded: "Bindings currently recorded by central; activity comes from each session's observation.",
		delivery_worktree_cleanup: "Cleanup eligibility needs a fresh preview. It lists active work, undelivered results, reservations and other blockers.",
		delivery_merge_read_receipts: "Check saved receipts",
		delivery_merge_recovery: "Worktree merge recovery",
		delivery_merge_held: "This operation has no resource-release receipt. These two working directories remain reserved according to the original operation; keep its operation ID.",
		delivery_merge_source: "Source worktree",
		delivery_merge_destination: "Destination checkout",
		delivery_merge_ack: "Positive ACK saved",
		delivery_merge_no_ack: "No positive ACK evidence",
		delivery_merge_safe_reads: "Read the session, inspect Git and operation records, or use the existing stop/interrupt controls. Checking receipts does not resend an unknown merge.",
		delivery_merge_closeout: "Safe closeout requires the original step's positive ACK and reservation identity. Manual adjudication for a wholly lost ACK is not available; do not infer the outcome from HEAD or clear reservations.",
		delivery_setup_title: "First connection and usage",
		delivery_setup_central: "On first use, enter your existing central address and expected identity, then confirm in the native window. Existing configuration can be reloaded.",
		delivery_setup_identity: "After connecting, confirm the actual identity and scopes. Fleet shows each host's readiness and blocking reasons.",
		delivery_setup_mode: "Use Dashboard directly to manage remote work. For local Windows connections and BAT startup, select connections, profiles and login startup in Fleet. Mac supports Dashboard use.",
		delivery_fleet_current_backend: "Current Fleet backend: {backend}",
		delivery_fleet_legacy_default: "Older configuration without a backend still uses PowerShell. Use the migration preview below to switch to Rust; installing a new Dashboard does not migrate it automatically.",
		message_code: "Code",
		message_table: "Message table",
		message_copy_code: "Copy code",
		message_copy: "Copy original",
		message_copied: "Copied.",
		message_copy_source: "Original text to copy",
		message_copy_manual: "Automatic copy is unavailable. Select and copy the original text below.",
		message_latest: "Back to latest",
		message_window: "Latest 30 messages",
		message_anchor_missing: "Your previous reading position is outside the messages currently loaded.",
		tailscale_request: "Original opening request",
		tailscale_title: "Tailscale",
		tailscale_open: "Open Tailscale",
		tailscale_refresh: "Refresh Tailscale status",
		tailscale_browser: "Sign in using Tailscale on this computer. The Windows desktop app can open it directly.",
		tailscale_unsupported: "Opening Tailscale is not supported on this platform yet.",
		tailscale_missing: "Tailscale was not found in its standard installation folder. Install the Windows app first.",
		tailscale_incomplete: "The Tailscale installation is incomplete. Check the Windows installation.",
		tailscale_unknown: "Tailscale status could not be confirmed.",
		tailscale_needs_login: "Tailscale needs sign-in.",
		tailscale_needs_approval: "This device still needs administrator approval.",
		tailscale_stopped: "Tailscale is disconnected.",
		tailscale_starting: "Tailscale is connecting.",
		tailscale_running: "Tailscale is running. See Fleet for each host’s connection status.",
		tailscale_help: "After opening, choose Log in from the Tailscale icon in the Windows notification area. Status refreshes when you return here.",
		tailscale_uncertain: "Opening is unconfirmed. Check the notification area first; the original request is kept and will not be opened again automatically.",
		tailscale_started: "The Tailscale process started. Check the notification area; sign-in is not yet confirmed.",
		tailscale_not_started: "This request did not start Tailscale.",
		tailscale_retry: "Check or retry original request",
		tailscale_new: "Prepare another opening",
		tailscale_damaged: "The saved request could not be read. Check the Tailscale app first.",
		tailscale_read_failed: "The latest status or opening result could not be confirmed. Refresh to check; the original request is kept.",
		bat_review_again: "Review original choice again",
		bat_preview_expired: "This preview was never submitted. Explicitly review the original profile again after reopening before launching BAT.",
		bat_handoff: "View in BAT",
		bat_copy_title: "Copy full title",
		bat_copy_id: "Copy full ID",
		bat_copied: "Copied.",
		bat_copy_manually: "Select and copy the complete text below.",
		bat_open: "Open in BAT",
		bat_browser: "Search in BAT using the full title or ID above. The desktop app can open an explicitly chosen BAT profile.",
		bat_profile: "BAT profile",
		bat_choose: "Choose a profile explicitly",
		bat_search_help: "Choose a profile, then search in BAT with the full title or ID. This does not focus the session automatically.",
		bat_review: "Review selected profile",
		bat_launch: "Open selected profile",
		bat_retry: "Check and retry original launch",
		bat_read: "Read original launch",
		bat_new: "Choose another profile",
		bat_chosen: "Chosen profile: {profile}",
		bat_reviewed: "Review this profile; BAT starts only when you choose Open.",
		bat_preferences: "Saved Fleet window, login and connection choices stay unchanged. A remote profile requires its connection to be selected already.",
		bat_problem: "Cannot continue yet:",
		bat_missing: "Local BAT launch support or configuration is unavailable. Check desktop connection settings.",
		bat_wrong_receipt: "The response does not match the original profile launch; the original request is retained.",
		bat_unknown: "The outcome is unconfirmed. Read the original request; BAT will not reopen automatically.",
		bat_no_receipt: "No original launch receipt was found. The request is retained; restarting the app will not resend it automatically.",
		bat_saved_invalid: "The saved launch request is incomplete. Establish the original launch outcome before creating another.",
		labels_refresh: "Refresh labels",
		labels_title: "Labels",
		labels_edit: "Edit labels",
		labels_input: "Labels (one per line)",
		labels_help: "Labels organize the Dashboard. They do not change the BAT title or session.",
		labels_limits: "Up to 8 labels, 40 characters each. An empty list clears labels.",
		labels_empty: "No labels yet",
		labels_save: "Save labels",
		labels_saved: "This label change was saved.",
		labels_scope: "Editing labels requires manage permission.",
		labels_unreadable: "Confirmed label data is unavailable. Saving is disabled.",
		labels_changed: "Labels have a newer version. Your draft is preserved; review the current labels before preparing a change.",
		labels_review_current: "Review current version and prepare change",
		labels_refused: "The original request was refused because labels changed. It was not applied.",
		labels_fixed: "The original request uses label version {version}.",
		labels_wrong_receipt: "The receipt does not match the original label request.",
		labels_damaged: "The saved draft could not be read. Review the current version before explicitly preparing a change.",
		update_title: "Desktop updates",
		update_current: "Current version: {version}",
		update_candidate: "Available version",
		update_check: "Check for updates",
		update_download: "Download and verify",
		update_install: "Install and restart",
		update_read: "Read update status",
		update_unsigned: "Signed updates are not enabled for this test package.",
		update_platform: "Desktop updates are not available on this platform.",
		update_help: "Installation requires a verified download. Local connections pause during installation; remote work keeps running.",
		update_problem: "Update cannot continue:",
		update_read_failed: "Update status is unavailable. Read the status again.",
		update_unknown: "The installation outcome is unknown. Read status; installation will not be repeated automatically.",
		update_requested: "Installation of {version} was requested. Reopen the app to check its version; if it is unchanged, check the installer result.",
		update_phase_idle: "Updates have not been checked.",
		update_phase_checking: "Checking for updates…",
		update_phase_available: "A new version is available to download.",
		update_phase_up_to_date: "No newer version is currently available.",
		update_phase_check_failed: "The update check did not succeed.",
		update_phase_downloading: "Downloading and verifying the signature…",
		update_phase_download_failed: "Download or signature verification did not succeed.",
		update_phase_verified: "The signature and version are verified. This update is ready to install.",
		update_phase_stopping_fleet: "Preparing installation and stopping local connections…",
		update_phase_installation_unknown: "The original installation request is saved; its outcome is not confirmed.",
		bootstrap_title: "Central service startup",
		bootstrap_help: "Check and ensure only the configured existing Connector service. This never restarts it or creates a new database.",
		bootstrap_configured: "Fixed startup recipe configured",
		bootstrap_missing: "No startup recipe configured",
		bootstrap_auto_on: "Automatic check and ensure enabled",
		bootstrap_auto_off: "Automatic startup disabled",
		bootstrap_healthy: "The central service is available; no startup is needed.",
		bootstrap_blocked: "Requires the selected connection, a proven current owner and recent service-unavailable evidence. Login, scope and version failures do not trigger startup.",
		bootstrap_prepared: "Original request saved. No remote query has been sent.",
		bootstrap_querying: "Checking the original request; service state is not yet confirmed.",
		bootstrap_ensure_requested: "Startup intent recorded. The outcome is not fully confirmed; only reconcile the original result.",
		bootstrap_needs_attention: "Bounded checks did not confirm the result. Check the existing deployment. The original request stays saved and ensure will not be sent again.",
		bootstrap_service_running: "The existing service owner was confirmed. This service evidence does not prove central login or API compatibility.",
		bootstrap_unknown: "Outcome not confirmed. Read the original request; reopening this page never sends ensure again.",
		bootstrap_request: "Original request",
		bootstrap_queries: "{count}/4 queries used",
		bootstrap_changed: "This request belongs to an earlier fixed recipe and can only be read here.",
		bootstrap_prepare: "Prepare fixed service request",
		bootstrap_ensure: "Check and ensure existing service",
		bootstrap_reconcile: "Reconcile original result",
		bootstrap_read: "Read original request",
		bootstrap_refresh: "Refresh startup status",
		bootstrap_separate: "Normal central connection and identity checks continue independently. A local receipt is not a central operation acceptance.",
		bootstrap_working: "Reading local receipts…",
		bootstrap_unproven: "The response could not be bound to the original request.",
		task_title: "Execution",
		task_unknown: "Dispatch state unknown",
		task_state_queued: "Queued",
		task_state_dispatching: "Dispatching",
		task_state_accepted: "Accepted",
		task_state_running: "Running",
		task_state_waiting_permission: "Waiting for permission",
		task_state_quota_limited: "Quota limited",
		task_state_human_owned: "Human handling",
		task_state_needs_ted: "Needs a human decision",
		task_state_verifying: "Verifying",
		task_state_done: "Done",
		task_state_failed: "Failed",
		task_state_uncertain: "Uncertain",
		task_controls: "Execution controls",
		task_pause: "Pause dispatch",
		task_resume: "Resume dispatch",
		task_abort: "Also interrupt the current turn",
		task_control_help: "Pause stops future dispatch. The current turn continues unless you choose to interrupt it. Resume still follows the existing checks.",
		task_control_unavailable: "Requires a current task read, operate scope and this action capability. Finished executions cannot dispatch again.",
		task_control_new: "Prepare another control",
		task_control_fixed: "The original request uses control version {version}. An unknown outcome keeps this request and key.",
		task_control_invalid: "The response does not match the original task control request.",
		task_control_refused: "The task version changed before admission. Review its current state before preparing another control.",
		task_control_recorded: "The control operation completed. Current task state is shown in the latest read above; this does not mean the work is complete.",
		task_paused: "Dispatch paused",
		task_dispatch_enabled: "Dispatch not paused",
		task_open_session: "View current session",
		task_evidence: "Execution identity and full record",
		operations_more: "Load earlier operations",
		operations_loaded: "{count} operations loaded (not a total)",
		operations_all: "All operations",
		operations_empty: "No operations in this scope.",
		operations_invalid_page: "Invalid page response; loaded operations are retained.",
		operations_view_attention: "View operations needing attention",
		operations_view_active: "View active operations",
		orch_waiting_children: "Waiting for original child operations",
		orch_body_limit: "The complete request exceeds central's 200,000-byte limit. Shorten the item instructions; nothing has been submitted.",
		orch_title: "Orchestrate work",
		orch_relay: "Relay instructions",
		orch_planner: "Start a planner",
		orch_items: "Start reviewed items",
		orch_failover: "Continue with Codex",
		orch_help_relay: "Send your original words with central relay context to one exact managed session. If it cannot receive them, this form does not create a replacement.",
		orch_help_planner: "Start one read-only Codex planner in a new worktree. Read its response, then enter and review the individual work items separately.",
		orch_help_items: "Start an independent managed worktree for each literal item below. No planner response is automatically imported, and this form does not stop a planner.",
		orch_help_failover: "Continue one idle, quota-exhausted managed Claude session with Codex. Central checks all writers and task ownership. The source tab and worktree remain; no force or task failover is offered.",
		orch_preparation: "Review these selected inputs. Central prepares and records the exact relay context, plan or handoff after submission; this page is not a transcript or handoff preview.",
		orch_session: "Exact managed session",
		orch_choose_session: "Choose a managed session",
		orch_message: "Original instructions",
		orch_instructions: "Additional handoff instructions (optional)",
		orch_max_items: "Planner item limit (1–16)",
		orch_item_title: "Item {n} title",
		orch_item_prompt: "Item {n} instructions",
		orch_item: "Item {n}",
		orch_title_label: "Title",
		orch_prompt_label: "Literal instructions",
		orch_remove_item: "Remove item {n}",
		orch_add_item: "Add another item",
		orch_reload: "Reload available targets",
		orch_loading: "Reading central targets…",
		orch_selection_help: "Only fresh Connector-managed sessions or exact central workspace IDs are selectable. Central rechecks policy before any effect.",
		orch_truncated: "Showing the first 200 records only. This is not a complete inventory. Open an exact session from Sessions if it is not in this page.",
		orch_empty: "No eligible targets were returned for this host. Manual, stale, unknown and task-linked failover sources are excluded.",
		orch_discovery_failed: "Target identity is unconfirmed. Reload the targets before submitting.",
		orch_review_relay: "I reviewed this exact session and the original instructions.",
		orch_review_planner: "I reviewed the workspace, original instructions and planner limit.",
		orch_review_items: "I reviewed the workspace, agent and every literal item above.",
		orch_review_failover: "I reviewed this exact Claude source. Central may refuse if quota, idle or shared ownership checks fail.",
		orch_apply_relay: "Relay to this session",
		orch_apply_planner: "Start planner",
		orch_apply_items: "Start reviewed items",
		orch_apply_failover: "Request Codex continuation",
		orch_new: "Prepare another request",
		orch_invalid_result: "Operation response does not match the original request and identity.",
		orch_unavailable: "Requires {scopes} scopes and explicit central capability. New requests also require current target and host write evidence.",
		orch_fixed: "The original inputs and key stay fixed. Accepted recovery only reads this operation. An unknown result does not authorize a new request or another child.",
		orch_partial: "Completion is not proven for the whole request. Inspect the original operation and individual receipts before any further action.",
		orch_receipts: "Individual operation receipts",
		orch_child: "Relayed message operation",
		orch_steps: "Preparation and effect receipts",
		orch_item_progress: "Initial instructions confirmed for {count} of {total} reviewed items. This is not task completion.",
		orch_relay_accepted: "The target accepted the relayed instructions. This does not mean its work is complete.",
		orch_planner_started: "Planner instructions accepted. Read its response:",
		orch_handoff_accepted: "Codex handoff accepted:",
		orch_successor_unconfirmed: "Successor identity retained; handoff acceptance is not yet proven:",
		bulk_title: "Batch approvals",
		bulk_choose_host: "Choose a host",
		bulk_workspace: "Workspace name or ID (optional)",
		bulk_preview: "Preview pending requests",
		bulk_scope: "Choose one host and optionally a workspace. Only explicitly selected requests enter this batch.",
		bulk_effect: "Each selected request is allowed with BAT instructed not to ask again for the same kind of request. This is not a one-time allowance. Changing the permission mode is a separate choice.",
		bulk_select: "Approve {id}",
		bulk_mode: "Subsequent permission mode for {id}",
		bulk_no_mode: "Keep permission mode",
		bulk_apply: "Approve selected requests",
		bulk_selected: "{count} selected",
		bulk_check: "Check batch outcome",
		bulk_new: "Review another batch",
		bulk_empty: "No pending approval requests in this scope.",
		bulk_blocked: "Unavailable for this batch",
		bulk_truncated: "Only the first 50 sessions were checked. This is not the complete inventory. Narrow the workspace and preview again.",
		bulk_fixed: "The original requests, selection and operation identity are retained. Newly arriving prompts never join this batch.",
		bulk_expired: "This preview expired. Preview again and select requests.",
		bulk_refused: "This request was refused before admission. You can review another batch.",
		bulk_invalid_preview: "The preview does not match the selected scope.",
		bulk_invalid_result: "The operation response does not match the original batch request.",
		bulk_all_proven: "Each selected approval and mode change has an acceptance receipt. This does not mean the work is complete.",
		bulk_partial: "Not all items are proven successful. Check the individual receipts and original operations.",
		bulk_item_complete: "Selected actions accepted",
		bulk_item_incomplete: "Not fully confirmed",
		bulk_answer: "Approval",
		bulk_permissions: "Permissions",
		bulk_full_prompt: "Full request and identity",
		pub_title: "Start from a published version",
		pub_intro: "Choose a bound GitHub repository and target workspace, then start from an explicit published version.",
		pub_binding: "Repository · host · workspace ID",
		pub_choose: "Choose a bound workspace",
		pub_ref: "Published branch ref",
		pub_prompt: "Original instructions",
		pub_head_only: "Only the exact head of the selected branch is supported. If it changes after preview, central stops instead of replacing your selected version.",
		pub_preview: "Preview published version",
		pub_loading: "Reading version…",
		pub_invalid_preview: "The version preview does not match the selected repository, workspace or branch.",
		pub_invalid_result: "The operation response does not match the original version, workspace or request.",
		pub_apply: "Start from this version",
		pub_new: "Prepare another published version",
		pub_isolation: "Creates a new managed clone, worktree and session. Existing manual working folders stay unchanged.",
		pub_reviewed: "Review this source and its full commit SHA:",
		pub_sha: "Fixed commit SHA",
		pub_unavailable: "Requires observe and start scopes, and an explicit central capability for this action.",
		pub_no_bindings: "Central has no explicit repository and workspace bindings configured.",
		pub_fixed: "Keeps the original commit, target, instructions and operation key. Readback only checks that operation; it does not follow a newer branch head or start another session.",
		start_title_page: "Start a new session",
		start_intro: "Create a standalone managed session on the host and workspace you choose.",
		dispatch_title: "Quick project dispatch",
		dispatch_back: "Back to project",
		dispatch_advanced: "Advanced settings",
		dispatch_intro: "Choose a bound project destination, review its published version, then start with your original instructions and attachments.",
		dispatch_project_help: "Only this project's explicit repository, host and workspace bindings are shown. No work item or Task Service task is created automatically.",
		dispatch_no_bindings: "This project has no available destination. Add its repository to the project and configure the corresponding host/workspace binding in central.",
		dispatch_archived: "This project is archived. New dispatch is unavailable; existing operations can still be read back.",
		dispatch_project_unavailable: "The current project could not be verified. Your draft is preserved and dispatch stays paused.",
		dispatch_unsupported: "Central does not support project dispatch yet. Update central first.",
		dispatch_fixed_inputs: "This operation uses the exact input revisions below. Read-back does not transfer again or start another session.",
		start_choose_host: "Choose a host",
		start_workspace: "Workspace",
		start_choose_workspace: "Choose a workspace",
		start_agent: "Agent",
		start_model: "Model (optional)",
		start_model_default: "Use the host or agent default",
		start_title: "Title (optional)",
		start_prompt: "Original instructions (optional)",
		start_reload_workspaces: "Reload workspaces",
		start_loading_workspaces: "Reading central workspaces…",
		start_discovery_failed: "Workspace discovery is unconfirmed. Reload before selecting.",
		start_no_workspaces: "This host returned no workspaces.",
		start_truncated: "Only the first 200 workspaces are shown; this is not a complete listing.",
		start_workspace_help: "Uses the exact workspace ID returned by central. Host repository and policy checks still apply.",
		start_isolation: "Uses a new worktree. This action does not adopt an existing manual or task session.",
		start_prompt_help: "Your original text is preserved. Leave this empty to start without sending instructions.",
		start_apply: "Start session",
		start_new: "Prepare another session",
		start_unavailable: "Requires observe and start scopes, and a host central permits for starting sessions.",
		start_invalid_result: "The operation response does not match the original start request.",
		start_unknown: "Submission is unconfirmed; the original request and key are preserved.",
		start_fixed: "Host, workspace, options and original text are fixed. Read-back never starts again; an unknown submission can only retry the same request.",
		start_refused: "This request was refused before admission. You can explicitly prepare another request.",
		start_started: "Start confirmed:",
		start_without_prompt: "No initial instructions were requested.",
		start_prompt_accepted: "Initial instructions were accepted.",
		start_prompt_unknown: "Started, but acceptance of the initial instructions is unconfirmed. Check the step receipts; do not resend by starting another session.",
		ar_content_download: "Download this revision",
		ar_content_downloaded: "SHA-256 verified; download handed to the browser.",
		ar_content_help: "Read this fixed revision without recording a review. Preview: UTF-8 text up to 256 KiB; static PNG up to 2 MiB / one megapixel. Download: up to 16 MiB.",
		ar_content_changed: "The file response does not match the fixed revision. Check the original operation again.",
		ar_content_limit: "This file exceeds the client's 16 MiB read limit.",
		ar_content_reading: "Reading and verifying the fixed revision…",
		ar_content_verified: "This preview comes from the SHA-256 verified fixed revision.",
		ar_content_preview_limit: "Preview is unavailable for this file. Download or Save As to inspect it.",
		ar_content_native_unavailable: "This desktop version does not provide native file reading.",
		ar_nav: "Artifacts",
		ar_title: "Artifacts and review",
		ar_open: "Capture and review this execution's file",
		ar_help: "Save one fixed file revision from a managed source, then explicitly record a review of that revision. This does not change the source worktree or execution state.",
		ar_capture_title: "Save source file",
		ar_review_title: "Review fixed revision",
		ar_execution: "Central execution evidence",
		ar_choose_execution: "Choose an accepted execution or command",
		ar_evidence_kind: "Evidence type",
		ar_operation: "Execution operation",
		ar_command: "Task Service command",
		ar_task_id: "Full task ID",
		ar_evidence_id: "Full operation or command ID",
		ar_exact_evidence: "Enter an older exact evidence ID…",
		ar_more_executions: "More executions",
		ar_refresh_sources: "Reload execution evidence",
		ar_source_unavailable: "Choose a current Connector-managed session with its full ID. Central still verifies the original execution evidence.",
		ar_receipt: "Review receipt for this revision (up to 2000 characters)",
		ar_accept: "Record review of this revision",
		ar_check_accept: "Check original review submission",
		ar_accept_help: "Inspect the result before recording your review. This receipt covers only the fixed revision below; it does not prove passing tests, task completion, merge or deployment.",
		ar_approve_scope: "Recording review requires approve; reading artifacts requires observe.",
		ar_revision: "Fixed artifact revision",
		ar_lineage: "Central source and execution evidence",
		ar_check: "Check original operations",
		ar_new_review: "Record another review",
		ar_recorded: "Review of this exact revision was recorded. Task and work-item completion are unchanged.",
		ar_catalog: "Saved results from managed sources",
		ar_no_artifacts: "No reviewable managed-source results on this page.",
		ar_invalid_result: "The response does not match the original operation, fixed revision or central source proof. The original request and key are retained.",
		ar_storage: "The original operation recovery data could not be saved. Enable local storage for this application before submitting.",
		ar_original_credential: "Capture recovery requires the original credential and manage/observe scopes. Restore that credential; the original request and key stay saved.",
		ar_original_preview: "Original capture preview and source evidence",
		sessions_label: "Title",
		sessions_workspace: "Workspace",
		sessions_workspace_id: "Workspace ID",
		sessions_id: "Session ID",
		sessions_title: "Sessions",
		sessions_intro: "Browse sessions by host and workspace, with manual work and earlier records kept in view.",
		sessions_search: "Search loaded sessions",
		sessions_workspaces: "Loaded workspaces",
		sessions_scope_note: "Counts cover loaded pages only.",
		sessions_all_loaded: "All loaded sessions",
		sessions_loaded_count: "{count} loaded",
		sessions_projects: "Projects and work items",
		sessions_workspace_unknown: "Workspace not recorded",
		sessions_workspace_unverified: "No recorded workspace ID",
		sessions_scope_missing: "Selected workspace is not in this view",
		sessions_no_matches: "No matching sessions in this view.",
		sessions_more_hint: "More pages are available. Load more, or adjust your search and filters.",
		sessions_empty_hint: "Adjust your search, host or access filter. Absence from this view does not mean work has ended.",
		sessions_showing: "Showing {shown} · {loaded} loaded",
		sessions_page_note: "Search and workspace selection cover loaded pages only.",
		sessions_manual: "Manual",
		sessions_connector: "Connector created",
		sessions_origin_unknown: "Origin unknown",
		sessions_access_unknown: "Access unknown",
		sessions_details: "Status and records",
		sessions_runtime_stale: "Activity and pending requests have not been rechecked.",
		sessions_not_seen: "Not in latest scan",
		sessions_stale: "Observation needs updating",
		sessions_activity_unknown: "Activity unknown",
		permissions_title: "Session permissions",
		permissions_mode: "Requested mode",
		permissions_default: "Normal permissions",
		permissions_allow_all: "Allow all",
		permissions_apply: "Apply permissions",
		permissions_check: "Check original operation",
		permissions_new: "Start another change",
		permissions_retry: "Retry original request",
		permissions_details: "View operation and step receipts",
		permissions_help: "Choose the permissions to apply. This does not show the current mode; host policy and confinement limits still apply.",
		permissions_default_help: "Use the normal approval flow, keeping prompts for actions that need confirmation.",
		permissions_allow_help: "Bypass the agent's approval prompts, including file writes and command execution. The host may still refuse this change.",
		permissions_unavailable: "Requires current session data, operate scope, and explicit central permission for this action and host writes.",
		permissions_unknown: "The result is not yet confirmed. The original request is retained.",
		permissions_fixed: "The mode, session and operation stay fixed. Check the receipts for partial or unknown results.",
		permissions_invalid_result: "The operation reply does not match the original permission request.",
		permissions_damaged: "The saved request is incomplete. Check operation history before proceeding.",
		permissions_accepted: "BAT accepted the requested configuration; the running agent's settings have not been independently verified.",
		permissions_next_turn: "Codex uses this setting on its next turn.",
		permissions_refused: "This request was refused before admission. You can explicitly start another change; the original request will not retry automatically.",
		capture_title: "Capture a remote file",
		capture_host: "Source host",
		capture_session: "Full manual session ID",
		capture_path: "Remote relative file path",
		capture_help: "Enter one file path relative to the selected manual session folder. The source is read without being changed.",
		capture_preview: "Preview source file",
		capture_review: "I reviewed this file and its source evidence",
		capture_save: "Save reviewed file",
		capture_check: "Check original capture",
		capture_new: "Capture another file",
		capture_attach: "Add to attachment draft",
		capture_attached: "Added to the attachment draft. Save the work item or start the work to apply it.",
		capture_name: "Filename",
		capture_bytes: "Bytes",
		capture_source: "Source",
		capture_root: "Session folder",
		capture_repository: "Repository",
		capture_expiry: "Preview expires",
		capture_single_file: "Only this file is captured; other uncommitted changes are excluded.",
		capture_expired: "Preview expired. Preview and review again; capture has not been submitted.",
		capture_fixed: "The original preview and operation identity are retained. Read-back does not select newer content.",
		capture_unknown: "Submission outcome is unknown. Check the same capture; its draft and operation key are retained.",
		capture_saved: "Saved a fixed attachment revision, available in attachment selection:",
		capture_scope_observe: "Preview requires observe scope.",
		capture_scope_manage: "Saving requires manage and observe scopes and central capture capability.",
		capture_manual_only: "The source must be a full session explicitly observed as manually created.",
		capture_invalid_preview: "Central preview does not match the selected source.",
		capture_invalid_result: "Unable to verify the saved attachment revision and capture source.",
		obs_unknown: "unknown",
		obs_state_evidence: "State and evidence",
		obs_lifecycle_note: "Idle, unloaded and no tab do not mean ended. Lifecycle stays unknown without end evidence.",
		obs_discovery: "Discovery coverage",
		obs_discovery_note: "This shows central recorded discovery; it does not start another host scan. Not observed does not mean absent.",
		obs_scan_status: "Latest scan",
		obs_last_success: "Last successful observation",
		obs_last_attempt: "Latest read completed",
		obs_authority: "Read authority",
		obs_verified: "verified",
		obs_unverified: "unverified",
		obs_scan_coverage: "Read methods, coverage and failures",
		obs_outside_scan: "Outside this scan",
		obs_no_scan: "No discovery evidence has been recorded for this host.",
		obs_new_facts: "New journal facts are available. Loaded pages keep their snapshot; refresh to check this resource.",
		obs_event_kind: "Event kind (optional)",
		obs_execution_filter: "Execution ID (optional)",
		obs_read_latest: "Read latest records",
		obs_evidence: "Original IDs and evidence",
		obs_occurred: "Occurred",
		obs_recorded: "Recorded",
		obs_pending_binding: "session binding pending",
		obs_half_open: "Sequence interval [{start}, {end})",
		obs_follow_up: "Follow-up of",
		obs_empty: "No recorded evidence in this range.",
		obs_snapshot: "Fixed journal snapshot: {seq}.",
		obs_historical_limits: "Earlier history may be incomplete; unknown times are not inferred.",
		obs_first_recorded: "First recorded",
		obs_relations: "Execution and session relations",
		obs_history: "Resource history",
		obs_include_closed: "Include closed relations",
		obs_execution: "Execution",
		obs_worktree: "Worktree",
		obs_known_identity: "Central known resource ID. Relations and history do not grant write authority.",
		obs_inventory_note: "Browse by stable ID while retaining loaded pages. Inventory reflects changing observations, without snapshot isolation.",
		obs_axis_connection: "Connection",
		obs_axis_loading: "Loading",
		obs_axis_tab: "Tab",
		obs_axis_activity: "Activity",
		obs_axis_lifecycle: "Lifecycle",
		obs_axis_enumeration: "Enumeration",
		obs_axis_freshness: "Freshness",
		obs_value_unknown: "unknown",
		obs_value_connected: "connected",
		obs_value_not_connected: "not connected",
		obs_value_loaded: "loaded",
		obs_value_not_loaded: "not loaded",
		obs_value_present: "present",
		obs_value_no_tab: "no tab",
		obs_value_starting: "starting",
		obs_value_streaming: "streaming",
		obs_value_not_streaming: "not streaming",
		obs_value_active: "active",
		obs_value_ended: "ended",
		obs_value_gone: "gone",
		obs_value_missing: "missing",
		obs_value_fresh: "fresh",
		obs_value_stale: "stale",
		obs_scope_other_profiles_and_hosts: "Other profiles and hosts",
		obs_scope_manual_sessions_without_tabs_or_facts: "Manual sessions without tabs or facts",
		obs_scope_arbitrary_transcripts: "Unbound transcripts",
		obs_scope_codex_rollouts: "Codex rollout scans",
		obs_scope_background_git_state: "Background Git probes",
		obs_scope_earlier_history: "Earlier history",
		parent_archived: "This item or its project is archived. Your edit draft is retained.",
		pending_changed: "The pending request changed. Your draft is retained; review the current request before answering.",
		files_unavailable: "The original transfer is unavailable on this connection. Removing it from the draft does not cancel the upload.",
		files_choose: "Choose files",
		files_help: "Selection fixes the file contents. Verified uploads become attachments.",
		files_drop: "Enable file drop",
		files_drop_help: "Drop files into this window, then choose Upload to add them to this draft.",
		files_upload: "Upload",
		files_progress: "Local transfer progress",
		files_stop: "Stop transfer",
		files_retry: "Retry original transfer",
		files_check: "Check result",
		files_cancel: "Cancel upload",
		files_discard: "Clear local receipt",
		files_save: "Save As",
		files_preview: "Preview",
		files_selected: "Selected",
		files_checking: "Checking original operation",
		files_uploading: "Sending",
		files_verifying: "Verifying",
		files_downloading: "Downloading",
		files_saving: "Saving",
		files_ready: "Verified",
		files_saved: "Saved",
		files_stopped: "Stopped; original result retained",
		files_failed: "Operation failed",
		files_cancelled: "Cancelled",
		files_receipt_mismatch: "The transfer receipt does not match the original file. Attachment was not added.",
		attachment_file_changed: "Choose the same file to recover this upload; remove this entry before choosing different content.",
		attachment_pending: "Upload outcome is still pending. Retry the original operation with the same file.",
		existing_artifact: "Uploaded attachment",
		add_attachment: "Add attachment",
		attachments: "Attachments",
		choose_attachments: "Choose attachments",
		upload_on_choose: "Files upload when chosen. Uploaded revisions are saved with your draft.",
		choose_again: "Choose this file again. The browser cannot reopen local files after a reload.",
		uploading: "Uploading…",
		retry: "Retry",
		attachment_role: "Attachment role",
		attachment_input: "Input",
		attachment_result: "Result",
		attachments_not_ready: "Finish uploading or remove the unfinished files first.",
		source_unavailable: "Source HEAD is unavailable. Your draft is kept; retry after reconnecting.",
		confirm_source: "Keep the original commit and attachments; resume this run",
		materializations: "Attachment transfer",
		material_pending: "Pending",
		material_transferring: "Transferring",
		material_uncertain: "Checking",
		material_verified: "Verified",
		material_blocked: "Blocked",
		"nav_cleanup": "Cleanup and retained work",
		"cleanup_target": "Choose a scope",
		"cleanup_target_work_item": "Work item",
		"cleanup_target_task": "Execution task",
		"cleanup_task_preview": "Preview this task's resource cleanup",
		"cleanup_check": "Check original cleanup",
		"cleanup_new": "Preview another cleanup",
		"cleanup_invalid_result": "The operation response does not match the original cleanup request.",
		"cleanup_task_help": "Task cleanup uses the complete task ID. Central checks terminal state, shared resources and unresolved commands. Uncommitted task content, task branches and task history are retained.",
		"cleanup_target_checkpoint": "Checkpoint",
		"cleanup_target_integration": "Integration",
		"cleanup_target_host": "Host",
		"cleanup_id": "Host name or original ID",
		"cleanup_children": "Include child work items",
		"cleanup_intro": "Review the resources before reclaiming them. Work context, receipts and original IDs stay findable forever.",
		"cleanup_repreview": "Choices or live state changed. Preview again before applying.",
		"cleanup_retry_same": "The reply was not confirmed. Apply again with this preview and the same key to recover the original operation.",
		"cleanup_preview": "Preview cleanup",
		"cleanup_apply": "Apply reviewed cleanup",
		"cleanup_reviewed": "I reviewed the resources, retained content and discard choices in this preview.",
		"cleanup_scope": "Applying needs the cleanup scope.",
		"cleanup_counts": "{reclaim} resources to reclaim · {retain} retained",
		"cleanup_expires": "This preview expires at {time} (15 minutes).",
		"cleanup_blocked": "All resources are retained. Review the reasons for each item.",
		"cleanup_commit_kept": "Commit kept",
		"cleanup_not_delivered": "Results were not delivered. Releasing keeps the commits and local branch.",
		"cleanup_release": "Release this worktree; keep its undelivered commits and branch",
		"cleanup_discard": "Discard uncommitted files permanently (requires cleanup_discard)",
		"cleanup_plan": "Plan",
		"cleanup_evidence": "IDs, evidence and delivery coverage",
		"cleanup_open_receipts": "View item receipts",
		"cleanup_history": "Permanent cleanup history",
		"cleanup_retained": "Actual retained content",
		"cleanup_retained_help": "Refs and commit objects verified on their host. Worktree restore is not available yet; a runtime cannot be revived.",
		"cleanup_search": "Search original ID, old location or PR",
		"cleanup_search_button": "Search",
		"cleanup_empty_history": "No cleanup history yet.",
		"cleanup_empty_retained": "No retained content recorded yet.",
		"cleanup_unavailable": "Host or retained objects could not be verified.",
		"cleanup_reason_reviewed": "Removed by a reviewed cleanup operation.",
		"cleanup_reason_automatic": "Automatically cleaned by the task service, with retained content and operation receipts.",
		"cleanup_reason_historical": "Historical record from an earlier task cleanup event; no current reviewed operation is implied.",
		"cleanup_reason_recorded": "Cleanup was recorded; inspect its receipt for the original source.",
		"cleanup_choice_UNCOMMITTED_CHANGES": "You chose permanent discard of uncommitted content.",
		"cleanup_choice_RESULTS_NOT_DELIVERED": "You chose release; undelivered commits and branch are kept.",
		"cleanup_kind_session": "Session",
		"cleanup_kind_worktree": "Worktree",
		"cleanup_kind_local_branch": "Local branch",
		"cleanup_kind_clone": "Clone",
		"cleanup_kind_integration_area": "Integration area",
		"cleanup_kind_git_pin": "Git pin",
		"cleanup_kind_source": "Source",
		"cleanup_kind_artifact": "Artifact",
		"cleanup_kind_temporary": "Temporary",
		"cleanup_kind_retained_ref": "Retained ref",
		"cleanup_decision_retain": "Retain",
		"cleanup_decision_reclaim": "Reclaim",
		"cleanup_decision_already_absent": "Already absent",
		"cleanup_step_preserve": "Pin commit",
		"cleanup_step_stop": "Stop session",
		"cleanup_step_discard": "Discard files",
		"cleanup_step_remove.worktree": "Remove worktree",
		"cleanup_step_remove.branch": "Delete delivered branch",
		"cleanup_step_finalize": "Record receipt",
		"cleanup_step_remove.temporary": "Remove exact temporary",
		"cleanup_kind_remote": "Remote resource",
		"cleanup_reason_TIER_DISABLED": "The host write or orchestrate tier is disabled.",
		"cleanup_reason_MANUAL_READ_ONLY": "A person created this resource; it is read-only.",
		"cleanup_reason_UNKNOWN_READ_ONLY": "Creation ownership is not proven.",
		"cleanup_reason_WORKDIR_NOT_MANAGED": "The workdir is outside the managed roots.",
		"cleanup_reason_BINDING_MISMATCH": "The resource does not match its creation binding.",
		"cleanup_reason_CLONE_NOT_OURS": "The repository has no matching connector creation markers.",
		"cleanup_reason_CLONE_CONFIG_TAMPERED": "Repository config or object storage is unsafe.",
		"cleanup_reason_OBSERVATION_UNAVAILABLE": "Live observation was unavailable within the host deadline.",
		"cleanup_reason_ACTIVE_WRITER": "A session is streaming or writing.",
		"cleanup_reason_SESSION_WAITING": "A session has a pending question, permission or queued turn.",
		"cleanup_reason_COMMAND_UNRESOLVED": "A command or external step has an unresolved outcome.",
		"cleanup_reason_ACTIVE_EXECUTION": "Another execution still needs this resource.",
		"cleanup_reason_CONTENT_REQUIRED": "An active integration preview or execution needs the content.",
		"cleanup_reason_TASK_OWNED": "This resource needs cleanup authority from its owning task. It remains retained in this scope or state.",
		"cleanup_reason_RETAINED_COPY": "The original branch remains as a retained copy.",
		"cleanup_reason_UNCOMMITTED_CHANGES": "Uncommitted tracked, staged, untracked or ignored content exists.",
		"cleanup_reason_RESULTS_NOT_DELIVERED": "Delivery receipts do not cover all result commits.",
		"cleanup_reason_DELIVERY_UNCERTAIN": "Delivery has an unresolved outcome.",
		"cleanup_reason_RETENTION_RULE": "An explicit retention rule requires this content.",
		"cleanup_reason_SHARED_CONTAINER": "This container has shared resources.",
		"cleanup_reason_RETAINED_CONTENT_STORE": "The repository or pin carries retained content and evidence.",
		"cleanup_reason_REMOTE_OUT_OF_SCOPE": "Remote branch deletion is a separate action.",
		"cleanup_reason_RESOURCE_KIND_UNSUPPORTED": "This resource or Git state has no cleanup adapter.",
		"cleanup_reason_RESOURCE_CLEANED": "This resource generation has a confirmed cleanup tombstone.",
		"cleanup_reason_CLEANUP_IN_PROGRESS": "A cleanup operation has reserved this resource.",
		"cleanup_receipt_retained": "retained",
		"cleanup_receipt_pending": "pending",
		"cleanup_receipt_running": "running",
		"cleanup_receipt_succeeded": "succeeded",
		"cleanup_receipt_already_absent": "already absent",
		"cleanup_receipt_failed": "failed",
		"cleanup_receipt_uncertain": "uncertain",
		"cleanup_receipt_blocked_stale": "blocked stale",
		"cleanup_receipt_cancelled": "cancelled",
		dep_pull_request: "Pull request",
		dep_desired: "Selected deployment",
		dep_observed: "Current observed version",
		dep_last_verified: "Last verified version",
		dep_history: "Deployment history",
		dep_no_history: "No deployments yet.",
		dep_no_version: "No version recorded.",
		dep_not_observed: "not observed yet",
		dep_observed_at: "Observed: {time}",
		dep_verified_at: "Verified: {time}",
		dep_artifact: "Artifact {id}",
		dep_not_undone: "Rollback does not undo",
		dep_no_limits: "This recipe declares no excluded side effects.",
		dep_rollback: "Rollback to this version",
		dep_retry: "Retry deploy · {sha}",
		dep_confirm_rollback: "Start rollback",
		dep_confirm_retry: "Retry this deployment",
		dep_rollback_review: "Review rollback",
		dep_retry_review: "Review deploy retry",
		dep_retry_only: "Deploy this saved identity again. The PR is never merged again.",
		dep_retry_unavailable: "This old record has no retryable fixed identity; preview a new deployment.",
		dep_preview_generation: "{env} · environment generation {generation}",
		dep_stale_preview: "The environment or recipe changed. Review the fresh preview below, then submit again if intended. Nothing is re-submitted automatically.",
		dep_refused: "The deployment request could not proceed. See operation details.",
		dep_open_operation: "View operation",
		dep_operation_details: "Operation details",
		dep_run: "Provider run",
		dep_attempt: "Run attempt",
		dep_error_code: "Error code",
		dep_needs_scope: "Requires deploy scope.",
		dep_missing_recipe: "This recipe is no longer configured.",
		dep_missing_verification: "Deploy disabled: add recipe verification.",
		dep_disabled: "Deployment is unavailable under the current capabilities.",
		dep_provider_pending: "The provider outcome is still pending; retry is unavailable.",
		dep_attention: "Needs attention",
		dep_attention_help: "Compare the selected and observed versions. Check the operation details before taking action.",
		dep_drift: "The observed version differs from the selected deployment. No deployment is started automatically.",
		dep_superseded: "Superseded by a newer selection.",
		dep_new_desired: "View new selection",
		dep_provider_run: "Original provider run",
		dep_previous: "Previous",
		dep_next: "Next",
		dep_page: "Page {page}",
		dep_ROLLBACK_UNSUPPORTED: "This recipe does not support rollback.",
		dep_ROLLBACK_TARGET_INVALID: "This version is unverified or belongs to another recipe or environment.",
		dep_ROLLBACK_ARTIFACT_UNAVAILABLE: "The saved artifact is unavailable.",
		dep_ROLLBACK_ARTIFACT_EXPIRED: "The saved artifact has expired.",
		dep_version_health: "Runtime version and health verified.",
		dep_version_only: "Runtime version verified; health is not checked by this recipe.",
		dep_health_only: "Health passed; runtime version is not checked by this recipe.",
		dep_state_selected: "Selected",
		dep_state_waiting_order: "Waiting for environment",
		dep_state_queued: "Queued",
		dep_state_building: "Building",
		dep_state_waiting_environment: "Waiting for approval",
		dep_state_deploying: "Deploying",
		dep_state_verifying: "Verifying",
		dep_state_succeeded: "Verified",
		dep_state_failed: "Failed",
		dep_state_cancelled: "Cancelled",
		dep_state_uncertain: "Outcome unknown",
		dep_state_needs_attention: "Needs attention",
		dep_state_unverified: "Unverified",
		dep_state_superseded: "Superseded",
		dep_operation: "Operation",
		dep_status: "State",
		dep_generation: "Environment generation {generation}",
		offline_actions_paused: "Central offline · actions paused",
		sync_waiting: "Waiting to refresh · draft preserved",
		desktop_add_credential: "Add credential",
		desktop_replace_credential: "Replace credential",
		desktop_forget_credential: "Forget saved credential",
		desktop_reload_configuration: "Reload configuration",
		desktop_connecting: "Connection in progress…",
		desktop_setup_help: "Connect to your existing central service. Enter its address and expected account, then review and save in the native window.",
		desktop_setup_origin: "Use an HTTPS origin, or http://127.0.0.1:port for an existing local tunnel. No token is needed here.",
		desktop_setup_review: "Review connection settings",
		desktop_setup_saved: "Configuration saved. Add a credential and verify your identity next.",
		desktop_setup_cancelled: "Saving cancelled; your inputs are preserved.",
		desktop_endpoint: "Central address",
		desktop_expected_actor: "Expected identity",
		desktop_configuration_file: "Configuration file",
		desktop_credential_source: "Credential source",
		desktop_source_launch_environment: "Memory-only launch credential",
		desktop_source_windows_credential_manager: "Windows Credential Manager",
		desktop_source_macos_keychain: "macOS Keychain",
		desktop_enrollment_help: "Enter the Connector API token in the system’s secure dialog. After identity verification, it is saved to this account’s protected storage for the next login.",
		desktop_enrollment_unsupported: "Protected storage and credential entry are not available on this platform yet. A launch credential can be used in memory; it is never saved to disk.",
		desktop_forget_help: "Removes this computer’s saved credential and disconnects; it does not revoke the central token. Drafts and original operation IDs stay saved.",
		desktop_forgotten: "Saved credential removed and disconnected.",
		desktop_reloaded: "Configuration reloaded. Verify the connection to continue; existing drafts stay saved.",
		desktop_disconnected: "Disconnected. Central work continues.",
		desktop_enrollment_cancelled: "Credential entry cancelled. The existing connection is unchanged.",
		desktop_connection: "Desktop central connection",
		desktop_local: "Local capabilities",
		desktop_connect_needed: "Connect to the configured central Connector.",
		desktop_polling: "connected · updates every second",
		desktop_config_needed: "Central connection is not configured.",
		desktop_credential_missing: "No native credential is available yet.",
		desktop_credential_help: "The central address and expected identity come from local configuration. Credentials stay in the native app, outside this page.",
		desktop_dashboard_only: "Dashboard is available without BAT installed. On Windows, use the local Fleet controls to review connections, windows and login startup. Closing the window keeps the app in the tray; Quit waits for owned Fleet connections to stop. Central work continues independently.",
		fleet_login_waiting: "Waiting for selected BAT workspaces; Dashboard remains available.",
		fleet_login_attention: "Login startup needs attention. Read the original launch result before retrying.",
		fleet_login_complete: "Login choices were processed. This does not prove BAT windows or workspaces opened.",
		fleet_retry_migration: "Retry the same change",
		fleet_desktop_title: "Local Fleet and windows",
		fleet_independent: "Choose connections, BAT windows and Dashboard separately. Saving choices does not open windows.",
		fleet_connections: "Connections",
		fleet_windows_title: "Windows to open",
		fleet_dashboard_choice: "Open Dashboard",
		fleet_local_bat: "Local BAT window",
		fleet_selection_help: "Selected remote windows need their own authenticated connection. Dashboard remains usable while other hosts connect.",
		fleet_review_choices: "Review choices",
		fleet_save_choices: "Save reviewed choices",
		fleet_prerequisites: "Connections also needed: {names}.",
		fleet_none: "none",
		fleet_launch_title: "Open saved selection",
		fleet_launch_help: "BAT windows open only when their selected connections are ready. Existing BAT windows stay as they are.",
		fleet_review_launch: "Review launch",
		fleet_launch_apply: "Open saved selection",
		fleet_retry_launch: "Retry original launch",
		fleet_launch_review: "The saved window selection is ready for review.",
		fleet_local_anchor: "BAT may also open a local window when all selected profiles are remote.",
		fleet_launch_no_bat: "No BAT window requested. Selected connections remain independent.",
		fleet_launch_already_running: "BAT is already running; its windows and profile settings were preserved.",
		fleet_launch_started: "BAT process started. Check its windows for connection status.",
		fleet_launch_uncertain: "Launch outcome not yet confirmed. Read the original receipt before another request.",
		fleet_launch_not_started: "BAT did not start. A new review is required to try a different launch.",
		fleet_new_launch: "New launch review",
		fleet_login_title: "At Windows sign-in",
		fleet_login_picker: "Show these choices before launching at sign-in",
		fleet_backend_title: "Connection monitor and startup",
		fleet_backend_help: "Review the current monitor and startup entry before changing them. The original settings remain available for an explicit restore.",
		fleet_backend_rust: "Native monitor",
		fleet_backend_powershell: "PowerShell monitor",
		fleet_autostart: "Start Fleet at Windows sign-in",
		fleet_review_migration: "Review monitor and startup",
		fleet_apply_migration: "Apply reviewed transition",
		fleet_continue_migration: "Continue original transition",
		fleet_restore_migration: "Restore original settings",
		fleet_new_migration: "New transition review",
		fleet_migration_review: "Monitor: {from} → {to}. Login startup: {before} → {after}.",
		fleet_enabled: "enabled",
		fleet_disabled: "disabled",
		fleet_migration_unknown: "Transition accepted or unconfirmed. Read its original receipt.",
		fleet_migration_prepared: "Transition saved. Continue to request normal monitor shutdown.",
		fleet_migration_quit_requested: "Normal shutdown requested. Continue after the monitor exits.",
		fleet_migration_stopped: "Original monitor stopped. Transition is in progress.",
		fleet_migration_startup_written: "Startup entry saved. Continue the original transition.",
		fleet_migration_config_written: "Monitor setting saved. Continue the original transition.",
		fleet_migration_launch_requested: "Replacement requested. Read back its exact owner; it will not be launched twice.",
		fleet_migration_complete: "Transition complete. Original settings are retained for restore.",
		fleet_title: "Local Fleet connections",
		fleet_help: "Choose connections for this computer. Your selection and observed readiness are shown separately.",
		fleet_apply: "Save connections",
		fleet_refresh: "Read status",
		fleet_use_current: "Use current selection",
		fleet_start: "Start connection monitor",
		fleet_quit: "Stop local connection monitor",
		fleet_monitor_running: "Monitor running",
		fleet_monitor_stopped: "Monitor stopped",
		fleet_ready: "Ready",
		fleet_degraded: "Partly available",
		fleet_down: "Unavailable",
		fleet_off: "Off",
		fleet_fresh: "Recent observation",
		fleet_stale: "Observation stale",
		fleet_unavailable: "No current observation",
		fleet_applied: "The monitor has read the current selection.",
		fleet_waiting: "Waiting for the monitor to read the current selection.",
		fleet_changed: "The selection or monitor changed. Your draft is preserved; read and review the current selection.",
		fleet_other_owner: "This monitor is outside this login session's control; status is read-only.",
		fleet_invalid: "Fleet configuration needs attention ({n} issues).",
		fleet_windows: "Fleet connection management requires Windows.",
		fleet_setup: "Fleet Kit is not configured. Follow desktop setup to select its installation.",
		fleet_working: "Updating connections…",
		fleet_saved: "Selection saved; the monitor reports readiness separately.",
		fleet_quit_requested: "Monitor stop requested; waiting for status.",
		fleet_unknown: "The outcome is unknown; your draft is preserved. Read status before acting again.",
		fleet_read_failed: "Fleet status unavailable; actions are paused.",
		merge_scope_reload: "PR scope changed; your selected preview is retained. Load and review it again before merging.",
		metadata_diff: "Content comparison",
		metadata_before: "Before",
		metadata_intended: "Intended",
		metadata_observed: "Observed",
		scope_stack_rebase: "Upper branch rebase",
		scope_dependency: "Branch dependency",
		metadata_edit: "Edit PR title and description",
		metadata_title: "PR title",
		metadata_disabled: "This repository has not enabled allow_pr_update.",
		metadata_race_limit: "Compare title/body before saving and read back after writing. GitHub has no atomic compare-and-write; edits in the final read/write window can still be overwritten.",
		metadata_result_help: "Operation details retain before, intended and observed content. On conflict, reload and edit again; no automatic overwrite or undo.",
		metadata_pending: "PR was modified; readback verification is pending.",
		merge_scope: "Merge scope",
		merge_method: "Merge method",
		merge_commit_range: "Review complete BASE..HEAD: {count} commits",
		merge_preview_fixed: "This preview fixes head, base and scope; changing method reloads it.",
		scope_single_pr: "No other PR was found to be merged.",
		scope_native_stack: "Native stack",
		scope_branch_chain: "Dependent branch chain",
		scope_indirect_merge: "Indirect merge candidate",
		scope_would_merge: "Affects other PRs",
		scope_candidate: "Included commits",
		merged_newer_base: "Merged onto a newer base: {count} other commits will ship too.",
		close: "Close",
		nav_projects: "Projects",
		projects_help: "Projects and work items are the connector's own records: goals, the request verbatim, acceptance, steps, and the sessions, checkpoints, operations and PRs that carried them. A rename never changes an ID; order and pins only change the display.",
		new_project_name: "New project name",
		add_project: "Add",
		show_archived: "Show archived",
		project_repository_optional: "Repository for dispatch (optional)",
		project_repository_later: "Choose later",
		no_projects: "No projects yet.",
		new_sub_project: "Sub-project name",
		rename: "Rename",
		archive: "Archive",
		restore: "Restore",
		more: "More",
		move_up: "Move up",
		move_down: "Move down",
		pin: "Pin to top",
		unpin: "Unpin",
		wi_done_of: "{done}/{total} done",
		wi_state_todo: "to do",
		wi_state_doing: "in progress",
		wi_state_waiting: "waiting",
		wi_state_done: "done",
		wi_state_awaiting_approval: "done? (to confirm)",
		wi_err_VERSION_CONFLICT: "Someone changed this meanwhile; the latest version was loaded (your edits in the form are kept). Check it and save again.",
		linked_back: "linked to this work item",
		wi_err_ORDER_CHANGED: "The order changed meanwhile; it was reloaded. Reorder again.",
		wi_err_PIN_CHANGED: "The pin changed meanwhile; it was reloaded.",
		wi_err_CONTENT_CHANGED: "The content changed while you were reading it; read the new content, then decide.",
		wi_err_NAME_TAKEN: "Another project has this name.",
		wi_err_HAS_CHILDREN: "Archive its sub-projects first.",
		wi_err_PARENT_ARCHIVED: "Its parent is archived; restore the parent first.",
		wi_err_PINNED_FIRST: "Pinned entries stay above the others; unpin it to move it down.",
		wi_err_STEPS_OPEN: "Some steps are not checked; check them (or remove the ones not needed) before marking it done.",
		wi_err_CYCLE: "It cannot move under itself.",
		wi_err_LINK_TARGET_NOT_FOUND: "Nothing to link: the connector has never seen it.",
		wi_err_NOTHING_TO_DECIDE: "Nobody claimed it is done; there is nothing to decide.",
		new_item_title: "New work item",
		add_item: "Add",
		work_items: "Work items",
		name: "Name",
		description: "Description",
		repositories: "Repositories",
		task_project: "Task Service project name",
		save: "Save",
		archived: "archived",
		sub_projects: "Sub-projects",
		new_child_item: "Child item title",
		new_branch_item: "Branch title (same level)",
		archive_with_children: "Archive (with its children)",
		needs_decision: "your decision",
		no_items: "No work items yet.",
		link_missing: "no longer found",
		needs_manage_scope: "Your token lacks the manage scope, so it cannot change projects or work items; issue one with --scope manage.",
		needs_approve_scope: "Your token lacks the approve scope, so it cannot accept work as done; issue one with --scope approve.",
		accept_done: "Accept as done",
		mark_done: "Mark done",
		keep_working: "Not done: keep working",
		approved_by: "{who} accepted it as done ({time}). Editing the content asks again.",
		claimed_done: "{who} says this is done and waits for you. You accept the content shown here.",
		steps_all_checked: "Every step is checked. Mark it done, or keep working?",
		goal: "Goal",
		request: "Request (verbatim)",
		acceptance: "Acceptance",
		steps_title: "Steps",
		parent_id: "Parent",
		remove: "Remove",
		new_step: "New step",
		link_session: "Session",
		link_checkpoint: "Checkpoint",
		link_operation: "Operation",
		link_task: "Task",
		link_pull_request: "PR",
		link_ref_hint: "Target",
		link_ref_session: "host/session_id",
		link_ref_checkpoint: "cp_…",
		link_ref_operation: "op_…",
		link_ref_task: "task ID",
		link_ref_pull_request: "owner/name#123",
		link: "Link",
		links: "Related",
		no_links: "Nothing linked yet.",
		no_steps: "No steps.",
		children: "Children",
		derived: "Branched from here",
		history: "History",
		derived_from: "Branched from",
		start_from_checkpoint: "Start agent work from this checkpoint",
		claimed_by: "{who} says done",
		linked_items: "Work items",
		ev_work_item_created: "Created",
		ev_work_item_updated: "Edited",
		ev_work_item_state: "State",
		ev_work_item_approved: "Accepted as done",
		ev_work_item_continued: "Sent back",
		ev_work_item_linked: "Linked",
		ev_work_item_unlinked: "Unlinked",
		ev_work_item_archived: "Archived",
		ev_work_item_restored: "Restored",
		ev_work_item_pinned: "Pinned",
		ev_work_item_unpinned: "Unpinned",
		nav_home: "Pending",
		nav_sessions: "Sessions",
		nav_delivery: "Delivery",
		nav_operations: "Operations",
		nav_settings: "Connection",
		tab_needs_you: "Needs you",
		tab_to_confirm: "To confirm",
		attention_tab_needs: "Needs you",
		attention_tab_active: "Active operations",
		attention_tab_unread: "Unread work updates",
		attention_replies: "Replies and permissions",
		attention_replies_note: "Questions and permission requests reported by central. Reading does not resolve them.",
		attention_completion: "Completion review",
		attention_completion_note: "Work reported done or with every step checked still needs your decision.",
		attention_problems: "Operations needing attention",
		attention_problems_note: "Includes uncertain outcomes. Review the original operation and its receipts.",
		attention_hosts: "Host connections",
		attention_hosts_note: "Unreachable or stale hosts. This does not mean their work has ended.",
		attention_active: "Active operations",
		attention_active_note: "Accepted, running or waiting for external conditions. These are not work completion reviews.",
		attention_unread: "Unread work updates",
		attention_unread_note: "Work-item versions you have not marked read, including existing items. This is not an unread message count.",
		attention_loaded: "{count} loaded (not a total)",
		attention_empty: "No items in this category.",
		attention_not_updated: "Could not refresh. Any items below are from the previous read.",
		attention_invalid: "Incomplete list response; reload to try again.",
		reading_unread: "Unread update",
		reading_read: "This version is read",
		reading_mark: "Mark this version read",
		reading_note: "Reading tracks the work-item version you saw and syncs across clients using the same identity. It does not approve completion or resolve requests.",
		ev_work_item_read: "Marked read",
		reading_newer: "Central has a newer version. The displayed content and unsaved edits are preserved until you close the editor.",
		empty_needs_you: "Nothing needs you right now.",
		empty_to_confirm: "Nothing is waiting.",
		stale: "stale",
		stale_reason_host_unreachable: "host unreachable",
		stale_reason_host_not_refreshed: "not refreshed",
		stale_reason_not_enumerated: "missing from last listing",
		stale_reason_gone: "gone",
		stale_reason_never_observed: "not observed yet",
		read_only: "API read-only",
		managed: "Connector-managed",
		provenance_manual: "created in BAT",
		provenance_connector_managed: "created by the connector",
		provenance_unknown: "unknown origin",
		state_streaming: "working",
		state_loaded: "loaded",
		state_unloaded: "unloaded",
		pending_ask_user: "asking you",
		pending_permission: "waiting for permission",
		host: "Host",
		workspace: "Workspace",
		title: "Title",
		agent: "Agent",
		state: "State",
		activity: "Last activity",
		observed: "Observed",
		all_hosts: "All hosts",
		all_access: "All",
		only_managed: "Connector-managed only",
		only_read_only: "Read-only only",
		load_more: "Load more",
		messages: "Messages",
		send: "Send",
		send_placeholder: "Message for this managed session…",
		interrupt: "Interrupt turn",
		answer: "Answer",
		allow: "Allow",
		deny: "Deny",
		read_only_note: "A person created this session in BAT, so the API never writes to it. To have an agent continue, start a new managed session from its commit.",
		continue_from_checkpoint: "Start agent work from this version",
		checkpoints: "Checkpoints",
		checkpoint_help: "Records this session's current commit and recent conversation (read-only; the session and its folder are not changed). Agent work started from it runs in the connector's own clone on a new branch and session.",
		create_checkpoint: "Record this version",
		no_checkpoints: "No checkpoints yet.",
		excerpt_count: "{n} messages",
		commit: "Commit",
		checkpoint_note_placeholder: "What should happen next (kept verbatim; optional)…",
		dirty_unknown: "Uncommitted changes: not observed (no SSH alias for this host); none are carried over.",
		source_advanced: "The source has newer commits; this checkpoint stays at its commit. Record again to include them.",
		started_from: "This session was started from version {commit}:",
		source_session: "source session",
		dirty_warning: "{n} uncommitted change(s) at capture time are not carried over.",
		continue_placeholder: "What should the agent do next…",
		start_agent_work: "Start agent work",
		open_new_session: "Open the new session",
		checkpoint_unavailable: "This host lacks managed_roots, an SSH alias or the write/orchestrate tiers, so work cannot start from a checkpoint here.",
		needs_start_scope: "Your token lacks the start scope, so it cannot start agent work; issue one with --scope start.",
		confined_note: "The working directory alone offers no protection. Limits come from start options and account evidence; individual approvals may permit outside writes.",
		confinement_none: "No proven execution limit",
		confinement_prompt_gated: "Prompt gated",
		confinement_host_account: "Host account",
		confinement_os_sandbox: "OS sandbox",
		confinement_os_pending: "OS sandbox (live verification pending)",
		confinement_evidence: "Confinement evidence",
		confinement_creation: "Creation limits",
		confinement_current: "Current verification",
		confinement_options: "Start options",
		confinement_gap: "Coverage gap",
		confinement_status_verified: "Verified",
		confinement_status_options_confirmed: "Options confirmed",
		confinement_current_unknown: "Current confinement unknown",
		confinement_current_mismatch: "Confinement mismatch",
		confinement_status_unknown: "Unknown",
		confinement_status_mismatch: "Record mismatch",
		confinement_status_pending: "Pending",
		confinement_gap_sandbox_enforcement_unverified: "W12 live enforcement verification is pending",
		confinement_gap_prompt_rules_are_not_os_isolation: "Existing approvals and shell commands can permit outside writes",
		confinement_gap_task_recipe_compatibility: "Task Service test behavior is preserved; no additional execution restriction",
		confinement_gap_execution_restriction_unverified: "No execution restriction evidence",
		confinement_gap_legacy_evidence_missing: "Legacy creation evidence is missing; no automatic upgrade",
		confinement_claude_note: "Claude uses default: unapproved edits and Bash ask for approval. Existing approval rules still apply; there is no OS write isolation. Consider Codex. Individual approvals may permit outside writes.",
		confinement_codex_note: "Codex uses workspace-write / on-request. Live enforcement is unverified; BAT cannot configure network or writable roots, so installs and localhost tests may be restricted. Individual approvals may escape these limits.",
		confinement_account_note: "The BAT account was checked against declared personal roots. Claude may use acceptEdits; only those roots are covered and the account is checked again before starting.",
		confinement_account_blocked: "A host account boundary is declared but its check has not passed. New sessions will be refused; fix the host configuration. Reason: {reason}.",
		confinement_account_recheck: "The account boundary is checked again when the session starts. If it passes, Claude may use acceptEdits; a supported hardening gap uses plain default. Other check failures refuse the start.",
		confinement_account_fallback: "The account check reports {reason}. Claude uses plain default without acceptEdits.",
		repository: "Repository",
		pull_number: "PR number",
		load_pr: "Load PR",
		head: "Head",
		base: "Base",
		checks: "Checks",
		checks_summary: "{total} total, {pending} pending, {failed} failed",
		mergeable: "Mergeable",
		merge: "Merge PR",
		deploy_to: "Deploy to {env}",
		merge_and_deploy_to: "Merge and deploy to {env}",
		retry_deploy: "Retry deploying this version",
		merged_sha: "Merged commit",
		op_accepted: "accepted",
		op_running: "running",
		op_waiting_checks: "waiting for checks",
		op_waiting_external: "waiting for GitHub/deploy",
		op_needs_attention: "needs attention",
		op_uncertain: "outcome unknown, reading back",
		op_succeeded: "done",
		op_failed: "failed",
		op_cancelled: "cancelled",
		cancel: "Cancel",
		resume: "Resume",
		resume_help: "Run it again after fixing the cause: finished steps are not repeated and unproven ones are read back, never re-sent.",
		steps: "Steps",
		action: "Action",
		actor: "Actor",
		created: "Created",
		error: "Error",
		reason: "Reason",
		token: "API token",
		token_help: "Issue one with batc api-token issue; it stays in this browser.",
		connect: "Connect",
		remember: "Remember on this computer",
		disconnect: "Disconnect",
		connected_as: "Connected as {actor} ({scopes})",
		need_token: "Enter an API token under Connection first.",
		unreachable_hosts: "Host problems",
		loading: "Loading…",
		forbidden_scope: "Your token lacks this scope.",
		queue_behind: "Queue behind the running turn",
		no_messages: "No messages yet.",
		update_pr_results: "Update PR results",
		update_pr_help: "Put the chosen results into this PR's head branch: a normal push, never forced; your local folders are not changed.",
		needs_integrate_scope: "Needs the integrate scope: issue a token with --scope integrate.",
		integration_no_host: "No integrate host of this repository has an SSH alias, a managed root and the write/orchestrate tiers.",
		kind_checkpoint: "your checkpoint",
		kind_checkpoint_run: "agent result",
		kind_branch: "GitHub branch",
		previewing: "Previewing… (the first time builds the managed integration area and can take minutes)",
		start_integration_conflict: "Start integrating (item {n} is expected to conflict; it will stop there)",
		normal_push: "normal push",
		push_access_ok: "can push",
		push_access_denied: "this host's git credentials cannot push (set a deploy key or credential)",
		push_access_unknown: "push access not confirmed",
		plan_fast_forward: "fast-forward",
		plan_merge: "merge",
		plan_pick: "pick",
		plan_already_included: "already in PR",
		plan_conflict: "expected conflict",
		plan_not_predicted: "not checked",
		plan_unrelated: "no shared history",
		n_commits: "{n} commit(s)",
		n_files: "{n} file(s)",
		foreign_commit: "not from the chosen source",
		overlapping_files: "Files touched by more than one:",
		preview_expired: "This preview has expired (over an hour old, or the PR head changed).",
		previewed_at: "Previewed {time} · valid for an hour",
		preview_again: "Preview again",
		branch_on_github: "branch name on GitHub",
		add: "Add",
		add_branch: "Add branch",
		delivered_to: "sent to #{n}",
		agent_results: "Agent results",
		your_checkpoints: "Your checkpoints",
		still_working: "working",
		done: "done",
		none: "None",
		selected_in_order: "Selected (integrated in this order)",
		integration_done: "PR updated: {old} → {new}, {n} commit(s) added. Your local folders are not updated; pull in BAT to sync.",
		integration_INTEGRATION_CONFLICT: "One item conflicts. The items before it are composed in the connector's area and nothing was pushed. Hand it to an agent to resolve there, or cancel and preview again without it.",
		integration_RESOLUTION_INCOMPLETE: "The conflict is not resolved yet (nothing committed). Resume after the agent runs `git commit --no-edit`.",
		integration_RESOLUTION_INVALID: "The resolution does not qualify (exactly one merge commit, no uncommitted changes or conflict markers); fix it, then Resume.",
		integration_waiting_resolver: "Waiting for the agent to finish resolving (it is still working)",
		hand_to_agent: "Ask an agent to resolve",
		handoff_started: "A session is resolving it; Resume after it commits.",
		integration_REMOTE_MOVED: "Someone pushed to the PR meanwhile; nothing was overwritten or pushed. Cancel and preview again at the new head.",
		integration_PUSH_REJECTED: "GitHub refused the push (branch protection or signature rules).",
		integration_PUSH_AUTH_FAILED: "This host's git credentials cannot push; fix them, then Resume.",
		integration_REMOTE_REWOUND_BEFORE_PUSH: "Pushed, but the branch was moved back just before; check the PR, then Resume to finish.",
		integration_REMOTE_REF_RECREATED: "Pushed, but the branch had been deleted just before; check the PR, then Resume to finish.",
		integration_UNCERTAIN_UNRESOLVED: "The push outcome cannot be confirmed yet (the remote is unreadable); the connector never pushes again on a guess.",
		integration_uncertain: "Confirming the push (the remote is read first; nothing is pushed twice)",
		integration_waiting: "Pushed; waiting for GitHub to show the new head",
		integration_running: "Updating the PR…",
		cancel_and_preview: "Cancel and preview again",
		receipts: "Per-source records",
		receipt_pending: "pending",
		receipt_composed: "composed (not pushed)",
		receipt_already_included: "already in PR",
		receipt_conflict: "conflict",
		receipt_delivered: "delivered",
		receipt_not_delivered: "not delivered",
		receipt_unknown: "unknown (the push was never proven)",
		receipt_resolved: "resolved (not pushed)",
		integration_PUSH_UNPROVEN: "The PR branch is at its old head, but the composed commit exists on GitHub: an earlier push may have landed and been set back. Nothing is pushed again; check the PR, then cancel and preview again."
	}
};
var lang = (navigator.language || "zh-TW").toLowerCase().startsWith("zh") ? "zh-TW" : "en";
function t(key, vars = {}) {
	return (STRINGS[lang][key] ?? STRINGS["zh-TW"][key] ?? key).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}
//#endregion
//#region src/native-files.js
init_transport();
var pending$1 = new Set([
	"checking",
	"uploading",
	"verifying",
	"downloading",
	"saving"
]);
var fixedRef = (ref) => ({
	artifact_id: ref.artifact_id,
	revision: ref.revision,
	digest: ref.digest
});
var sameRef = (a, b) => a && b && a.artifact_id === b.artifact_id && a.revision === b.revision && a.digest === b.digest;
function nativeAttachments({ h, t, guard, canWrite, draftId, onReceipt, onDiscard, onVisibility, attached }) {
	const rows = h("div", { class: "native-transfers" }), notice = h("p", {
		class: "muted",
		role: "status"
	});
	const preview = h("div", {
		class: "file-preview",
		hidden: true
	});
	const box = h("div", { class: "native-files" }, rows, notice, preview);
	const known = new Map(), downloads = new Set();
	let armed = false, refreshing, picking = false, objectUrl = null, stopped = false;
	const live = () => {
		guard();
		if (!box.isConnected) throw new Error("Attachment form changed");
	};
	const failure = (error) => {
		try {
			live();
			notice.textContent = String(error?.message || error);
		} catch {}
	};
	const writable = () => {
		live();
		if (!canWrite()) throw new Error(t("offline_actions_paused"));
	};
	const act = async (receipt, action) => {
		try {
			live();
			if (["retry", "cancel_upload"].includes(action) && receipt.direction === "upload") writable();
			await nativeFilesControl(receipt.transfer_id, action);
			live();
			if (action === "discard_local") onDiscard(receipt.transfer_id);
			await refresh();
		} catch (error) {
			failure(error);
		}
	};
	const render = () => {
		rows.replaceChildren(...[...known.values()].filter((r) => r.direction === "download" || !attached(r.transfer_id)).map((r) => {
			const active = pending$1.has(r.stage), percent = r.size_bytes ? Math.min(100, Math.floor(r.transferred_bytes / r.size_bytes * 100)) : 0;
			return h("div", { class: "file-transfer" }, h("div", { class: "row" }, h("div", { class: "grow" }, r.display_name, h("div", { class: "muted" }, `${t(`files_${r.stage}`)} · ${r.transferred_bytes} / ${r.size_bytes} B`)), r.operation_id ? h("a", { href: `#/op/${r.operation_id}` }, t("dep_operation_details")) : null), active ? h("progress", {
				max: 100,
				value: percent,
				"aria-label": t("files_progress")
			}) : null, r.error ? h("p", { class: "muted" }, r.error) : null, h("div", { class: "actions" }, active ? h("button", {
				class: "secondary",
				onclick: () => act(r, "stop")
			}, t("files_stop")) : null, !active && ![
				"ready",
				"saved",
				"failed",
				"cancelled"
			].includes(r.stage) ? h("button", {
				class: "secondary",
				disabled: r.direction === "upload" && !canWrite(),
				onclick: () => act(r, "retry")
			}, t(r.stage === "selected" ? "files_upload" : "files_retry")) : null, !active && r.direction === "upload" && r.stage !== "selected" && ![
				"ready",
				"failed",
				"cancelled"
			].includes(r.stage) ? h("button", {
				class: "secondary",
				onclick: () => act(r, "check")
			}, t("files_check")) : null, !active && r.operation_id && ![
				"succeeded",
				"failed",
				"cancelled"
			].includes(r.operation_status) ? h("button", {
				class: "secondary",
				disabled: !canWrite(),
				onclick: () => act(r, "cancel_upload")
			}, t("files_cancel")) : null, !active && (r.direction === "download" || r.stage === "selected" || [
				"ready",
				"failed",
				"cancelled"
			].includes(r.stage)) ? h("button", {
				class: "secondary",
				onclick: async () => {
					await act(r, "discard_local");
				}
			}, t("files_discard")) : null));
		}));
	};
	const adopt = (r) => {
		if (!/^file_[0-9a-f]{32}$/.test(r?.transfer_id) || !/^[0-9a-f]{64}$/.test(r.digest) || !Number.isSafeInteger(r.size_bytes) || r.size_bytes < 0 || r.size_bytes > 16777216 || typeof r.display_name !== "string") throw new Error(t("files_receipt_mismatch"));
		const previous = known.get(r.transfer_id);
		if (previous && [
			"intent_key",
			"direction",
			"draft_id",
			"display_name",
			"size_bytes",
			"digest"
		].some((k) => previous[k] !== r[k])) throw new Error(t("files_receipt_mismatch"));
		if (r.direction === "upload" && r.draft_id !== draftId) return;
		if (r.stage === "ready" && (r.operation_status !== "succeeded" || !r.operation_id || r.artifact?.digest !== r.digest || !/^art_[0-9a-f]{32}$/.test(r.artifact?.artifact_id) || !Number.isSafeInteger(r.artifact?.revision))) throw new Error(t("files_receipt_mismatch"));
		known.set(r.transfer_id, r);
		if (r.direction === "upload" && JSON.stringify(previous) !== JSON.stringify(r)) onReceipt(r);
	};
	const refresh = async () => {
		if (refreshing) return refreshing;
		const task = (async () => {
			live();
			const status = await nativeFilesStatus();
			live();
			const previousKeys = [...known.keys()].join(","), current = new Set();
			for (const receipt of status.transfers) if (receipt.direction === "upload" && receipt.draft_id === draftId || receipt.direction === "download" && (receipt.stage !== "saved" || downloads.has(receipt.transfer_id))) {
				current.add(receipt.transfer_id);
				adopt(receipt);
			}
			for (const id of known.keys()) if (!current.has(id)) known.delete(id);
			if ([...known.keys()].join(",") !== previousKeys) onVisibility();
			if (status.drop_error) notice.textContent = status.drop_error;
			render();
		})();
		refreshing = task;
		try {
			await task;
		} finally {
			if (refreshing === task) refreshing = null;
		}
	};
	const pick = async () => {
		if (picking) return;
		try {
			writable();
			picking = true;
			const receipts = await nativeFilesPick(draftId);
			live();
			for (const receipt of receipts) {
				adopt(receipt);
				writable();
				await nativeFilesUpload(receipt.transfer_id);
				live();
			}
			await refresh();
		} catch (error) {
			failure(error);
			await refresh().catch(failure);
		} finally {
			picking = false;
		}
	};
	const drop = h("button", {
		class: "secondary",
		"aria-pressed": false,
		onclick: async () => {
			try {
				writable();
				armed = !armed;
				await nativeFilesDropTarget(draftId, armed);
				live();
				drop.setAttribute("aria-pressed", String(armed));
				notice.textContent = armed ? t("files_drop_help") : "";
			} catch (error) {
				armed = false;
				failure(error);
			}
		}
	}, t("files_drop"));
	const closePreview = () => {
		preview.replaceChildren();
		preview.hidden = true;
		if (objectUrl) URL.revokeObjectURL(objectUrl);
		objectUrl = null;
	};
	const actions = (ref) => h("span", { class: "actions file-actions" }, h("button", {
		class: "secondary",
		onclick: async () => {
			try {
				live();
				const expected = fixedRef(ref), receipt = await nativeFilesSave(expected);
				live();
				if (!receipt) return;
				if (receipt.direction !== "download" || !sameRef(receipt.artifact, expected)) throw new Error(t("files_receipt_mismatch"));
				downloads.add(receipt.transfer_id);
				adopt(receipt);
				render();
			} catch (error) {
				failure(error);
			}
		}
	}, t("files_save")), h("button", {
		class: "secondary",
		onclick: async () => {
			try {
				live();
				const content = await nativeFilesPreview(fixedRef(ref));
				live();
				closePreview();
				let view;
				if (content.media_type === "text/plain" && typeof content.text === "string" && content.text.length <= 262144) view = h("pre", {}, content.text);
				else if (content.media_type === "image/png" && typeof content.base64 === "string" && content.base64.length <= 28e5) {
					const bytes = Uint8Array.from(atob(content.base64), (c) => c.charCodeAt(0));
					objectUrl = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
					view = h("img", {
						src: objectUrl,
						alt: t("files_preview")
					});
				} else throw new Error(t("files_receipt_mismatch"));
				preview.hidden = false;
				preview.append(h("div", { class: "actions" }, h("strong", {}, t("files_preview")), h("button", {
					class: "secondary",
					onclick: closePreview
				}, t("close"))), view);
			} catch (error) {
				failure(error);
			}
		}
	}, t("files_preview")));
	const tick = async () => {
		try {
			live();
			await refresh();
			if (armed) {
				writable();
				await nativeFilesDropTarget(draftId, box.getClientRects().length > 0 && document.visibilityState === "visible");
			}
		} catch (error) {
			try {
				live();
				failure(error);
			} catch {
				stopped = true;
				closePreview();
				await nativeFilesDropTarget(draftId, false).catch(() => {});
			}
		}
		if (!stopped) setTimeout(tick, 1e3);
	};
	queueMicrotask(tick);
	return {
		box,
		pick,
		drop,
		actions,
		refresh,
		has: (id) => known.has(id)
	};
}
//#endregion
//#region \0vite/preload-helper.js
var scriptRel = (function detectScriptRel() {
	const relList = typeof document !== "undefined" && document.createElement("link").relList;
	return relList && relList.supports && relList.supports("modulepreload") ? "modulepreload" : "preload";
})();
var assetsURL = function(dep, importerUrl) {
	return new URL(dep, importerUrl).href;
};
var seen = {};
var isCssPreloadUrl = function isCssPreloadUrl(url) {
	return url.pathname.endsWith(".css");
};
var preloadOnce = function preloadOnce(seen, href, preload) {
	if (href in seen) return seen[href];
	const promise = preload();
	if (!promise) {
		seen[href] = void 0;
		return;
	}
	const preloadPromise = promise.then(() => {
		seen[href] = void 0;
	}, (err) => {
		seen[href] = void 0;
		throw err;
	});
	seen[href] = preloadPromise;
	return preloadPromise;
};
var __vitePreload = function preload(baseModule, deps, importerUrl) {
	let promise = Promise.resolve();
	if (deps && deps.length > 0) {
		let preloadedHrefs;
		const cspNonceMeta = document.querySelector("meta[property=csp-nonce]");
		const cspNonce = cspNonceMeta?.nonce || cspNonceMeta?.getAttribute("nonce");
		function allSettled(promises) {
			return Promise.all(promises.map((p) => Promise.resolve(p).then((value) => ({
				status: "fulfilled",
				value
			}), (reason) => ({
				status: "rejected",
				reason
			}))));
		}
		function importMetaResolve(specifier) {
			if (import.meta.resolve) return new URL(import.meta.resolve(specifier));
			return new URL(specifier, import.meta.url);
		}
		promise = allSettled(deps.map((depString) => {
			depString = assetsURL(depString, importerUrl);
			const dep = importMetaResolve(depString);
			const isCss = isCssPreloadUrl(dep);
			return preloadOnce(seen, dep.href, () => {
				if (preloadedHrefs === void 0) {
					preloadedHrefs = {
						all: new Set(),
						styles: new Set()
					};
					const links = document.getElementsByTagName("link");
					for (let i = links.length - 1; i >= 0; i--) {
						const link = links[i];
						preloadedHrefs.all.add(link.href);
						if (link.rel === "stylesheet") preloadedHrefs.styles.add(link.href);
					}
				}
				if ((isCss ? preloadedHrefs.styles : preloadedHrefs.all).has(dep.href)) return;
				const link = document.createElement("link");
				link.rel = isCss ? "stylesheet" : scriptRel;
				if (!isCss) link.as = "script";
				link.crossOrigin = "";
				link.href = dep.href;
				if (cspNonce) link.setAttribute("nonce", cspNonce);
				document.head.appendChild(link);
				if (isCss) return new Promise((res, rej) => {
					link.addEventListener("load", res);
					link.addEventListener("error", () => rej(new Error(`Unable to preload CSS for ${dep}`)));
				});
			});
		}).filter((p) => p !== void 0));
	}
	function handlePreloadError(err) {
		const e = new Event("vite:preloadError", { cancelable: true });
		e.payload = err;
		window.dispatchEvent(e);
		if (!e.defaultPrevented) throw err;
	}
	return promise.then((res) => {
		for (const item of res || []) {
			if (item.status !== "rejected") continue;
			handlePreloadError(item.reason);
		}
		return baseModule().catch(handlePreloadError);
	});
};
//#endregion
//#region src/fleet-desktop.js
var fleet_desktop_exports = __exportAll({ mountFleetDesktop: () => mountFleetDesktop });
async function mountFleetDesktop(main, { h, t }) {
	const panel = h("section", {
		class: "panel fleet-desktop",
		"aria-label": t("fleet_desktop_title")
	});
	const content = h("div"), message = h("p", {
		class: "muted",
		role: "status"
	});
	panel.append(h("h2", {}, t("fleet_desktop_title")), h("p", { class: "muted" }, t("fleet_independent")), content, message);
	if (!main.isConnected) return () => {};
	main.append(panel);
	let disposed = false, busy = false, readable = false, snapshot, draft, binding, choicePreview, launch, migration, timer;
	let backend = "rust", autostart = false;
	const alive = () => !disposed && panel.isConnected;
	const key = () => `batc.desktop.fleet.controls.${binding}`;
	const choices = (value) => ({
		connections: [...value.connections],
		profiles: [...value.profiles],
		dashboard: value.dashboard
	});
	const equivalent = (a, b) => a && b && a.dashboard === b.dashboard && ["connections", "profiles"].every((k) => Array.isArray(a[k]) && Array.isArray(b[k]) && [...a[k]].sort().join("\0") === [...b[k]].sort().join("\0"));
	const validId = (id) => typeof id === "string" && /^[0-9a-f]{32}$/.test(id);
	const validSummary = (s, id) => s?.launch_id === id && Array.isArray(s.profiles) && s.profiles.every((v) => typeof v === "string") && typeof s.dashboard === "boolean" && typeof s.opens_bat === "boolean";
	const knownLaunch = () => [
		"started",
		"not_started",
		"no_bat",
		"already_running"
	].includes(launch?.receipt?.state);
	const acceptLaunch = (value) => {
		if (!launch || !value) return;
		const receipt = value.summary || value;
		if (receipt.launch_id !== launch.preview_id || !Array.isArray(receipt.profiles) || typeof receipt.dashboard !== "boolean" || launch.summary && (JSON.stringify(receipt.profiles) !== JSON.stringify(launch.summary.profiles) || receipt.dashboard !== launch.summary.dashboard)) throw new Error(t("fleet_unknown"));
		if (![
			"prepared",
			"uncertain",
			"started",
			"not_started",
			"no_bat",
			"already_running"
		].includes(value.state)) throw new Error(t("fleet_unknown"));
		launch.receipt = value;
	};
	const acceptMigration = (value) => {
		if (!migration || value?.id !== migration.preview_id || typeof value.phase !== "string") throw new Error(t("fleet_unknown"));
		migration.receipt = value;
	};
	const save = () => {
		try {
			sessionStorage.setItem(key(), JSON.stringify({
				draft,
				launch,
				migration
			}));
		} catch {}
	};
	const enabled = () => readable && !busy && snapshot?.configuration.valid && !snapshot.pending_migration && (snapshot.monitor.state === "stopped" || snapshot.monitor.controllable);
	const stale = () => draft && (draft.revision !== snapshot.selection.revision || draft.epoch !== snapshot.monitor.epoch);
	const discardPreview = () => {
		if (choicePreview) fleetControl({
			action: "discard",
			preview_id: choicePreview.preview_id
		}).catch(() => {});
		choicePreview = null;
	};
	const edit = (field, value) => {
		if (!enabled() || stale()) return;
		discardPreview();
		draft ||= {
			...choices(snapshot.selection),
			revision: snapshot.selection.revision,
			epoch: snapshot.monitor.epoch
		};
		draft[field] = value;
		if (equivalent(draft, snapshot.selection)) draft = null;
		save();
		render();
	};
	const accept = (value) => {
		if (value?.control_version !== 1 || !value.configuration?.binding || !Array.isArray(value.profiles) || !Array.isArray(value.selection?.profiles) || typeof value.selection.dashboard !== "boolean" || !value.monitor || !value.login || !value.readiness) throw new Error(t("fleet_unavailable"));
		if (binding !== value.configuration.binding) {
			binding = value.configuration.binding;
			backend = value.backend;
			draft = choicePreview = launch = migration = null;
			try {
				const old = JSON.parse(sessionStorage.getItem(key()) || "null");
				if (old?.draft && Array.isArray(old.draft.connections) && Array.isArray(old.draft.profiles) && [...old.draft.connections, ...old.draft.profiles].every((v) => typeof v === "string") && typeof old.draft.dashboard === "boolean") draft = old.draft;
				if (validId(old?.launch?.preview_id)) launch = {
					preview_id: old.launch.preview_id,
					attempted: old.launch.attempted === true,
					summary: validSummary(old.launch.summary, old.launch.preview_id) ? old.launch.summary : null,
					receipt: null
				};
				if (launch?.summary && ["no_bat", "already_running"].includes(old?.launch?.receipt?.state)) acceptLaunch(old.launch.receipt);
				if (validId(old?.migration?.preview_id) && (old.migration.accepted === true || /^[0-9a-f]{64}$/.test(old.migration.fingerprint))) migration = {
					...old.migration,
					receipt: null
				};
			} catch {}
		}
		snapshot = value;
		readable = true;
		const automatic = value.login_launch;
		if (!launch && automatic?.configuration_binding === binding && validId(automatic.preview_id) && validSummary(automatic.summary, automatic.preview_id)) {
			launch = {
				preview_id: automatic.preview_id,
				summary: automatic.summary,
				attempted: true
			};
			if (automatic.receipt) acceptLaunch(automatic.receipt);
			save();
		}
		if (draft && equivalent(draft, value.selection)) {
			draft = null;
			discardPreview();
			save();
		}
		if (validId(value.pending_migration) && migration?.preview_id !== value.pending_migration) {
			migration = {
				preview_id: value.pending_migration,
				accepted: true
			};
			save();
		}
	};
	const run = async (fn) => {
		if (!alive() || busy) return;
		busy = true;
		message.textContent = t("fleet_working");
		render();
		try {
			await fn();
			if (alive()) message.textContent = "";
		} catch (error) {
			if (alive()) message.textContent = `${t("fleet_unknown")} ${String(error)}`;
		} finally {
			busy = false;
			if (alive()) {
				save();
				render();
			}
		}
	};
	const read = async () => {
		try {
			const value = await fleetControl({ action: "overview" });
			if (!alive()) return;
			accept(value);
			if (launch?.attempted) {
				const receipt = await fleetControl({
					action: "launch_status",
					launch_id: launch.preview_id
				});
				if (alive() && receipt) acceptLaunch(receipt);
			}
			if (migration?.accepted) {
				const receipt = await fleetControl({
					action: "migration_status",
					migration_id: migration.preview_id
				});
				if (alive()) acceptMigration(receipt);
			}
		} catch (error) {
			readable = false;
			throw error;
		}
	};
	const reviewChoices = () => run(async () => {
		const value = await fleetControl({
			action: "preview_choices",
			choices: choices(draft),
			configuration_binding: binding,
			selection_revision: draft.revision,
			monitor_epoch: draft.epoch
		});
		if (alive()) {
			if (!validId(value.preview_id) || !equivalent(value.summary?.choices, draft)) throw new Error(t("fleet_unknown"));
			choicePreview = value;
		}
	});
	const launchApply = () => run(async () => {
		launch.attempted = true;
		save();
		const value = await fleetControl({
			action: "launch",
			preview_id: launch.preview_id
		});
		if (alive()) acceptLaunch(value);
	});
	const label = (id) => id === "default" ? t("fleet_local_bat") : snapshot.profiles.find((row) => row.id === id)?.label || snapshot.configuration.connections.find((row) => row.name === id)?.label || id;
	const render = () => {
		if (!alive() || !snapshot) return;
		const focus = document.activeElement?.dataset?.fleetChoice;
		const selected = draft || snapshot.selection, ready = new Map([...snapshot.readiness.hosts, snapshot.readiness.connector].filter(Boolean).map((row) => [row.name, row]));
		const checkbox = (field, id, text) => h("label", { class: "fleet-choice" }, h("input", {
			type: "checkbox",
			checked: field === "dashboard" ? selected.dashboard : selected[field].includes(id),
			"data-fleet-choice": field + ":" + id,
			disabled: !enabled() || !!stale(),
			onchange: (e) => edit(field, field === "dashboard" ? e.target.checked : e.target.checked ? [...selected[field], id] : selected[field].filter((v) => v !== id))
		}), " ", text);
		const button = (text, fn, disabled = false, primary = false) => h("button", {
			class: primary ? "primary" : "secondary",
			disabled: busy || disabled,
			onclick: fn
		}, t(text));
		const fields = [
			h("p", { "data-fleet-current-backend": true }, t("delivery_fleet_current_backend", { backend: t(["rust", "powershell"].includes(snapshot.backend) ? "fleet_backend_" + snapshot.backend : "obs_unknown") })),
			snapshot.backend === "powershell" ? h("p", { class: "note" }, t("delivery_fleet_legacy_default")) : null,
			h("p", {}, t("fleet_monitor_" + snapshot.monitor.state), " · ", t("fleet_" + snapshot.readiness.state)),
			snapshot.monitor.state === "running" && !snapshot.monitor.controllable ? h("p", { class: "note" }, t("fleet_other_owner")) : null,
			snapshot.login_launch ? h("p", { class: "note" }, t("fleet_login_" + snapshot.login_launch.state), snapshot.login_launch.code ? ` (${snapshot.login_launch.code})` : null) : null,
			h("div", { class: "actions" }, button("fleet_start", () => run(async () => {
				await fleetRequest({
					action: "ensure_monitor",
					expected_configuration_binding: binding
				});
				await read();
			}), !enabled() || !!draft || snapshot.monitor.state !== "stopped"), button("fleet_quit", () => run(async () => {
				await fleetRequest({
					action: "quit_owned",
					expected_configuration_binding: binding,
					expected_monitor_epoch: snapshot.monitor.epoch
				});
				await read();
			}), !enabled() || !!draft || !snapshot.monitor.controllable)),
			h("h3", {}, t("fleet_connections")),
			h("div", { class: "fleet-options" }, ...snapshot.configuration.connections.map((row) => h("div", { class: "row" }, h("div", { class: "grow" }, checkbox("connections", row.name, row.label)), h("span", { class: "chip" }, t("fleet_" + (ready.get(row.name)?.level || "unavailable")))))),
			h("h3", {}, t("fleet_windows_title")),
			h("div", { class: "fleet-options" }, ...snapshot.profiles.map((row) => h("div", { class: "row" }, checkbox("profiles", row.id, label(row.id)))), h("div", { class: "row" }, checkbox("dashboard", "dashboard", t("fleet_dashboard_choice")))),
			h("p", { class: "muted" }, t("fleet_selection_help")),
			stale() ? h("p", { class: "error" }, t("fleet_changed")) : null,
			choicePreview ? h("p", { class: "note" }, t("fleet_prerequisites", { names: choicePreview.summary.added_connections.map(label).join(", ") || t("fleet_none") })) : null,
			h("div", { class: "actions" }, button(choicePreview ? "fleet_save_choices" : "fleet_review_choices", () => choicePreview ? run(async () => {
				await fleetControl({
					action: "apply_choices",
					preview_id: choicePreview.preview_id
				});
				await read();
			}) : reviewChoices(), !enabled() || !draft || !!stale(), true), button("fleet_use_current", () => {
				draft = null;
				discardPreview();
				save();
				render();
			}, !draft), button("fleet_refresh", () => run(read))),
			h("h3", {}, t("fleet_launch_title")),
			h("p", { class: "muted" }, t("fleet_launch_help")),
			launch ? h("p", { class: "note" }, launch.receipt ? t("fleet_launch_" + (launch.receipt.state === "prepared" ? "uncertain" : launch.receipt.state || "uncertain")) : t(launch.attempted ? "fleet_launch_uncertain" : "fleet_launch_review")) : null,
			launch?.summary?.bat_may_open_local_window ? h("p", { class: "muted" }, t("fleet_local_anchor")) : null,
			h("div", { class: "actions" }, button("fleet_review_launch", () => run(async () => {
				const value = await fleetControl({ action: "preview_launch" });
				if (alive()) {
					if (!validId(value.preview_id) || !validSummary(value.summary, value.preview_id)) throw new Error(t("fleet_unknown"));
					launch = value;
				}
			}), !enabled() || !!draft || !!launch?.attempted), launch && !launch.receipt && launch.summary ? button(launch.attempted ? "fleet_retry_launch" : "fleet_launch_apply", launchApply, !enabled() || !!draft || snapshot.login_launch?.state === "waiting") : null, launch ? button("fleet_refresh", () => run(read)) : null, knownLaunch() ? button("fleet_new_launch", () => {
				fleetControl({
					action: "discard",
					preview_id: launch.preview_id
				}).catch(() => {});
				launch = null;
				save();
				render();
			}) : null, launch && !launch.attempted ? button("cancel", () => {
				fleetControl({
					action: "discard",
					preview_id: launch.preview_id
				}).catch(() => {});
				launch = null;
				save();
				render();
			}) : null),
			h("h3", {}, t("fleet_login_title")),
			h("label", { class: "fleet-choice" }, h("input", {
				type: "checkbox",
				checked: snapshot.login.show_picker,
				disabled: !enabled(),
				"data-fleet-login": "picker",
				onchange: (e) => run(async () => {
					const value = await fleetControl({
						action: "save_login",
						expected_revision: snapshot.login.revision,
						show_picker: e.target.checked
					});
					if (alive()) snapshot.login = value;
				})
			}), " ", t("fleet_login_picker")),
			h("h3", {}, t("fleet_backend_title")),
			h("p", { class: "muted" }, t("fleet_backend_help")),
			h("div", { class: "actions" }, h("select", {
				value: backend,
				disabled: busy || !!migration,
				"aria-label": t("fleet_backend_title"),
				onchange: (e) => {
					backend = e.target.value;
				}
			}, h("option", {
				value: "rust",
				selected: backend === "rust"
			}, t("fleet_backend_rust")), h("option", {
				value: "powershell",
				selected: backend === "powershell"
			}, t("fleet_backend_powershell"))), h("label", { class: "fleet-choice" }, h("input", {
				type: "checkbox",
				checked: autostart,
				disabled: busy || !!migration,
				onchange: (e) => {
					autostart = e.target.checked;
				},
				"data-fleet-autostart": "enabled"
			}), " ", t("fleet_autostart"))),
			migration ? h("p", { class: "note" }, migration.receipt ? t("fleet_migration_" + migration.receipt.phase) : t(migration.accepted ? "fleet_migration_unknown" : "fleet_migration_review", {
				from: t("fleet_backend_" + migration.from),
				to: t("fleet_backend_" + migration.to),
				before: t(migration.autostart_before ? "fleet_enabled" : "fleet_disabled"),
				after: t(migration.autostart ? "fleet_enabled" : "fleet_disabled")
			})) : null,
			h("div", { class: "actions" }, button("fleet_review_migration", () => run(async () => {
				const value = await fleetControl({
					action: "preview_migration",
					backend,
					autostart
				});
				if (alive()) {
					if (!validId(value.preview_id) || typeof value.fingerprint !== "string") throw new Error(t("fleet_unknown"));
					migration = value;
				}
			}), !enabled() || !!migration), migration && !migration.accepted ? button("fleet_apply_migration", () => run(async () => {
				migration.accepted = true;
				save();
				const value = await fleetControl({
					action: "apply_migration",
					preview_id: migration.preview_id,
					fingerprint: migration.fingerprint
				});
				if (alive()) acceptMigration(value);
				await read();
			}), !readable) : null, migration?.accepted && migration.receipt && migration.receipt.phase !== "complete" ? button("fleet_continue_migration", () => run(async () => {
				const value = await fleetControl({
					action: "advance_migration",
					migration_id: migration.preview_id
				});
				if (alive()) acceptMigration(value);
				await read();
			}), !readable) : null, migration?.accepted ? button("fleet_refresh", () => run(read)) : null, migration?.accepted && !migration.receipt ? button("fleet_retry_migration", () => run(async () => {
				const value = await fleetControl(migration.restore_source ? {
					action: "restore_migration",
					source_id: migration.restore_source,
					restore_id: migration.preview_id
				} : {
					action: "apply_migration",
					preview_id: migration.preview_id,
					fingerprint: migration.fingerprint
				});
				if (alive()) acceptMigration(value);
				await read();
			}), !migration.restore_source && !migration.fingerprint) : null, migration?.receipt?.phase === "complete" ? button("fleet_new_migration", () => {
				fleetControl({
					action: "discard",
					preview_id: migration.preview_id
				}).catch(() => {});
				migration = null;
				save();
				render();
			}) : null, migration && !migration.accepted ? button("cancel", () => {
				fleetControl({
					action: "discard",
					preview_id: migration.preview_id
				}).catch(() => {});
				migration = null;
				save();
				render();
			}) : null, migration?.receipt?.phase === "complete" ? button("fleet_restore_migration", () => run(async () => {
				const source = migration.preview_id;
				const restoreId = crypto.randomUUID().replaceAll("-", "");
				migration = {
					preview_id: restoreId,
					accepted: true,
					restore_source: source
				};
				save();
				const value = await fleetControl({
					action: "restore_migration",
					source_id: source,
					restore_id: restoreId
				});
				if (alive()) acceptMigration(value);
				await read();
			}), !readable) : null)
		];
		content.replaceChildren(...fields.filter(Boolean));
		if (focus) [...content.querySelectorAll("input")].find((input) => input.dataset.fleetChoice === focus)?.focus();
	};
	await run(read);
	const poll = async () => {
		if (!alive()) return;
		if (!busy) await run(read);
		if (alive()) timer = setTimeout(poll, 5e3);
	};
	timer = setTimeout(poll, 5e3);
	return () => {
		disposed = true;
		clearTimeout(timer);
		panel.remove();
	};
}
var init_fleet_desktop = __esmMin((() => {
	init_transport();
}));
//#endregion
//#region src/fleet-bootstrap.js
var fleet_bootstrap_exports = __exportAll({ mountFleetBootstrap: () => mountFleetBootstrap });
async function mountFleetBootstrap(main, { h, t }) {
	const panel = h("section", {
		class: "panel fleet-bootstrap",
		"aria-label": t("bootstrap_title")
	});
	const content = h("div"), message = h("p", {
		class: "muted",
		role: "status"
	});
	panel.append(h("h2", {}, t("bootstrap_title")), h("p", { class: "muted" }, t("bootstrap_help")), content, message);
	if (!main.isConnected) return () => {};
	main.prepend(panel);
	let disposed = false, busy = false, readable = false, snapshot, original, timer;
	const alive = () => !disposed && panel.isConnected;
	const storage = "batc.desktop.fleet.bootstrap.original";
	const hex = (v, n) => typeof v === "string" && new RegExp(`^[0-9a-f]{${n}}$`).test(v);
	const valid = (value) => value && hex(value.recipe_binding, 64) && hex(value.status?.request_id, 32) && [
		"querying",
		"ensure_requested",
		"needs_attention",
		"service_running"
	].includes(value.status.phase) && Number.isInteger(value.status.queries) && value.status.queries >= 0 && value.status.queries <= 4 && typeof value.status.ensure_requested === "boolean" && typeof value.status.ensure_accepted === "boolean" && [
		null,
		"unknown",
		"stopped",
		"transitioning",
		"owner_present",
		"running"
	].includes(value.status.last_state) && (!value.status.ensure_accepted || value.status.ensure_requested);
	const save = () => {
		if (original) try {
			sessionStorage.setItem(storage, JSON.stringify({
				request_id: original.status.request_id,
				recipe_binding: original.recipe_binding
			}));
		} catch {}
	};
	try {
		const value = JSON.parse(sessionStorage.getItem(storage) || "null");
		if (hex(value?.request_id, 32) && hex(value.recipe_binding, 64)) original = {
			recipe_binding: value.recipe_binding,
			status: { request_id: value.request_id },
			unknown: true
		};
	} catch {}
	const accept = (value, expected) => {
		if (!valid(value) || expected && (value.status.request_id !== expected.status.request_id || value.recipe_binding !== expected.recipe_binding)) throw new Error(t("bootstrap_unproven"));
		original = value;
		save();
	};
	const current = () => readable && snapshot?.configured && snapshot.eligible && original?.recipe_binding === snapshot.recipe_binding && !original.unknown;
	const phase = () => original?.unknown ? "unknown" : original?.status.queries === 0 ? "prepared" : original?.status.phase;
	const readOriginal = async () => {
		if (!original) return;
		const expected = original;
		original = {
			...original,
			unknown: true
		};
		save();
		const value = await fleetBootstrap({
			action: "receipt",
			request_id: expected.status.request_id
		});
		if (alive()) {
			if (!value) throw new Error(t("bootstrap_unproven"));
			accept(value, expected);
		}
	};
	const read = async () => {
		readable = false;
		const value = await fleetBootstrap({ action: "overview" });
		if (!alive()) return;
		if (value?.version !== 1 || typeof value.configured !== "boolean" || typeof value.auto_ensure !== "boolean" || typeof value.eligible !== "boolean" || !(value.recipe_binding === null || hex(value.recipe_binding, 64)) || value.latest !== null && !valid(value.latest)) throw new Error(t("bootstrap_unproven"));
		snapshot = value;
		readable = true;
		if (!original && value.latest) accept(value.latest);
		await readOriginal();
	};
	const run = async (fn) => {
		if (!alive() || busy) return;
		busy = true;
		message.textContent = t("bootstrap_working");
		render();
		try {
			await fn();
			if (alive()) message.textContent = "";
		} catch {
			if (alive()) message.textContent = t("bootstrap_unknown");
		} finally {
			busy = false;
			if (alive()) render();
		}
	};
	const prepare = () => run(async () => {
		const binding = snapshot.recipe_binding;
		const value = await fleetBootstrap({
			action: "prepare",
			recipe_binding: binding
		});
		if (alive()) {
			if (!valid(value) || value.recipe_binding !== binding) throw new Error(t("bootstrap_unproven"));
			accept(value);
		}
	});
	const advance = () => run(async () => {
		if (!current()) return;
		const expected = original;
		original = {
			...original,
			unknown: true
		};
		save();
		const value = await fleetBootstrap({
			action: "advance",
			request_id: expected.status.request_id,
			recipe_binding: expected.recipe_binding
		});
		if (alive()) accept(value, expected);
	});
	function render() {
		if (!alive()) return;
		const button = (key, fn, disabled = false, primary = false) => h("button", {
			class: primary ? "primary" : "secondary",
			disabled: busy || disabled,
			onclick: fn
		}, t(key));
		content.replaceChildren(...[
			snapshot ? h("p", {}, t(snapshot.configured ? "bootstrap_configured" : "bootstrap_missing"), " · ", t(snapshot.auto_ensure ? "bootstrap_auto_on" : "bootstrap_auto_off")) : null,
			snapshot?.code ? h("p", { class: "muted" }, t(snapshot.code === "BOOTSTRAP_NOT_NEEDED" ? "bootstrap_healthy" : "bootstrap_blocked")) : null,
			original ? h("p", { class: "note" }, t("bootstrap_" + (phase() || "unknown"))) : null,
			original ? h("p", { class: "muted bootstrap-receipt" }, t("bootstrap_request"), " ", h("code", {}, original.status.request_id), Number.isInteger(original.status.queries) ? ` · ${t("bootstrap_queries", { count: original.status.queries })}` : null) : null,
			original && snapshot?.recipe_binding !== original.recipe_binding ? h("p", { class: "muted" }, t("bootstrap_changed")) : null,
			h("div", { class: "actions" }, button("bootstrap_prepare", prepare, !readable || !snapshot?.eligible || !!original && phase() !== "service_running", !original), original && !["service_running"].includes(phase()) ? button(original.status.ensure_requested ? "bootstrap_reconcile" : "bootstrap_ensure", advance, !current() || original.status.queries >= 4, true) : null, original ? button("bootstrap_read", () => run(readOriginal)) : null, button("bootstrap_refresh", () => run(read))),
			h("p", { class: "muted" }, t("bootstrap_separate"))
		].filter(Boolean));
	}
	render();
	await run(read);
	const poll = async () => {
		if (!alive()) return;
		if (!busy) await run(read);
		if (alive()) timer = setTimeout(poll, 5e3);
	};
	timer = setTimeout(poll, 5e3);
	return () => {
		disposed = true;
		clearTimeout(timer);
		panel.remove();
	};
}
var init_fleet_bootstrap = __esmMin((() => {
	init_transport();
}));
//#endregion
//#region src/fleet.js
init_transport();
async function mountFleet(main, { h, t }) {
	if (!main.isConnected) return () => {};
	const panel = h("section", {
		class: "panel",
		"aria-label": t("fleet_title")
	});
	const content = h("div"), message = h("p", {
		class: "muted",
		role: "status"
	});
	panel.append(h("h2", {}, t("fleet_title")), h("p", { class: "muted" }, t("fleet_help")), content, message);
	main.append(panel);
	let nativeCleanup, bootstrapCleanup;
	let disposed = false, busy = false, readable = false, timer, snapshot, draft, binding;
	const alive = () => !disposed && panel.isConnected;
	const key = () => `batc.desktop.fleet.selection.${binding}`;
	const save = () => {
		try {
			if (draft) sessionStorage.setItem(key(), JSON.stringify(draft));
			else sessionStorage.removeItem(key());
		} catch {}
	};
	const same = (a, b) => a.length === b.length && [...a].sort().every((x, i) => x === [...b].sort()[i]);
	const changed = () => draft && (draft.revision !== snapshot.selection.revision || draft.epoch !== snapshot.monitor.epoch);
	const editable = () => readable && !busy && snapshot?.configuration.valid && (snapshot.monitor.state === "stopped" || snapshot.monitor.controllable);
	const render = () => {
		if (!alive() || !snapshot) return;
		const names = draft?.connections || snapshot.selection.connections;
		const ready = new Map([...snapshot.readiness.hosts || [], snapshot.readiness.connector].filter(Boolean).map((row) => [row.name, row]));
		const focus = document.activeElement?.dataset?.fleetName;
		const rows = snapshot.configuration.connections.map((entry) => {
			const input = h("input", {
				type: "checkbox",
				checked: names.includes(entry.name),
				disabled: !editable() || !!changed(),
				"data-fleet-name": entry.name,
				onchange: () => {
					if (!draft) draft = {
						revision: snapshot.selection.revision,
						epoch: snapshot.monitor.epoch,
						connections: [...snapshot.selection.connections]
					};
					draft.connections = input.checked ? [...new Set([...draft.connections, entry.name])] : draft.connections.filter((x) => x !== entry.name);
					if (same(draft.connections, snapshot.selection.connections)) draft = null;
					save();
					render();
				}
			});
			const observed = ready.get(entry.name);
			return h("div", { class: "row" }, h("label", { class: "grow fleet-choice" }, input, " ", entry.label), h("span", { class: "chip" }, t("fleet_" + (observed?.level || "unavailable"))), observed?.blocking ? h("span", { class: "muted" }, observed.blocking) : null);
		});
		content.replaceChildren(...[
			h("p", {}, t("fleet_monitor_" + snapshot.monitor.state), " · ", t("fleet_" + snapshot.readiness.state)),
			!snapshot.configuration.valid ? h("p", { class: "error" }, t("fleet_invalid", { n: snapshot.configuration.issue_count })) : null,
			snapshot.monitor.state === "running" && !snapshot.monitor.controllable ? h("p", { class: "note" }, t("fleet_other_owner")) : null,
			...rows,
			h("p", { class: "muted" }, t(snapshot.selection.applied_revision === snapshot.selection.revision ? "fleet_applied" : "fleet_waiting")),
			changed() ? h("p", { class: "error" }, t("fleet_changed")) : h("span"),
			h("div", { class: "actions" }, h("button", {
				class: "primary",
				disabled: !editable() || !draft || !!changed(),
				onclick: () => mutate({
					action: "set_connections",
					connections: [...draft.connections],
					expected_selection_revision: draft.revision,
					expected_monitor_epoch: draft.epoch,
					expected_configuration_binding: binding
				})
			}, t("fleet_apply")), h("button", {
				class: "secondary",
				disabled: busy,
				onclick: () => read(true)
			}, t("fleet_refresh")), h("button", {
				class: "secondary",
				disabled: !readable || busy || !draft,
				onclick: () => {
					draft = null;
					save();
					message.textContent = "";
					render();
				}
			}, t("fleet_use_current"))),
			h("div", { class: "actions" }, h("button", {
				class: "secondary",
				disabled: !editable() || !!draft || snapshot.monitor.state !== "stopped",
				onclick: () => mutate({
					action: "ensure_monitor",
					expected_configuration_binding: binding
				})
			}, t("fleet_start")), h("button", {
				class: "danger",
				disabled: !editable() || !!draft || !snapshot.monitor.controllable,
				onclick: () => mutate({
					action: "quit_owned",
					expected_configuration_binding: binding,
					expected_monitor_epoch: snapshot.monitor.epoch
				})
			}, t("fleet_quit")))
		].filter(Boolean));
		if (focus) [...content.querySelectorAll("input")].find((input) => input.dataset.fleetName === focus)?.focus();
	};
	const accept = (value) => {
		if (!value?.configuration?.connections || !value?.monitor || !value?.selection || !value?.readiness) throw new Error(t("fleet_unavailable"));
		if (binding !== value.configuration.binding) {
			binding = value.configuration.binding;
			draft = null;
			try {
				const old = JSON.parse(sessionStorage.getItem(key()) || "null");
				if (old && Array.isArray(old.connections) && old.connections.every((x) => typeof x === "string") && typeof old.revision === "string") draft = old;
			} catch {}
		}
		snapshot = value;
		readable = true;
		if (draft && same(draft.connections, value.selection.connections)) {
			draft = null;
			save();
		}
	};
	const read = async (explicit = false) => {
		if (!alive() || busy) return;
		busy = true;
		render();
		try {
			const value = await fleetRequest({ action: "status" });
			if (!alive()) return;
			accept(value);
			if (explicit) message.textContent = "";
		} catch (error) {
			if (alive()) {
				readable = false;
				message.textContent = `${t("fleet_read_failed")} ${String(error)}`;
			}
		} finally {
			busy = false;
			render();
		}
	};
	const mutate = async (input) => {
		if (!editable() || !alive()) return;
		busy = true;
		readable = false;
		message.textContent = t("fleet_working");
		render();
		try {
			const result = await fleetRequest(input);
			if (!alive()) return;
			if (input.action !== "quit_owned") accept(result);
			message.textContent = t(input.action === "quit_owned" ? "fleet_quit_requested" : "fleet_saved");
		} catch (error) {
			if (alive()) message.textContent = `${t("fleet_unknown")} ${String(error)}`;
		} finally {
			busy = false;
			render();
		}
	};
	try {
		const availability = await fleetAvailability();
		if (!alive()) return () => {
			disposed = true;
		};
		if (!availability.configured || !availability.platform_supported) message.textContent = t(!availability.platform_supported ? "fleet_windows" : "fleet_setup");
		else if (availability.native_controls === true) {
			const { mountFleetDesktop } = await __vitePreload(async () => {
				const { mountFleetDesktop } = await Promise.resolve().then(() => (init_fleet_desktop(), fleet_desktop_exports));
				return { mountFleetDesktop };
			}, void 0, import.meta.url);
			if (alive()) {
				panel.remove();
				nativeCleanup = await mountFleetDesktop(main, {
					h,
					t
				});
				if (availability.bootstrap_controls === true && !disposed && main.isConnected) {
					const { mountFleetBootstrap } = await __vitePreload(async () => {
						const { mountFleetBootstrap } = await Promise.resolve().then(() => (init_fleet_bootstrap(), fleet_bootstrap_exports));
						return { mountFleetBootstrap };
					}, void 0, import.meta.url);
					bootstrapCleanup = await mountFleetBootstrap(main, {
						h,
						t
					});
				}
			}
		} else {
			await read();
			const poll = async () => {
				if (!alive()) return;
				await read();
				if (alive()) timer = setTimeout(poll, 5e3);
			};
			timer = setTimeout(poll, 5e3);
		}
	} catch {
		message.textContent = t("fleet_unavailable");
	}
	return () => {
		disposed = true;
		clearTimeout(timer);
		nativeCleanup?.();
		bootstrapCleanup?.();
		panel.remove();
	};
}
//#endregion
//#region src/tailscale.js
init_transport();
function mountTailscale(main, { h, t }) {
	const panel = h("section", {
		class: "panel",
		"aria-label": t("tailscale_title")
	});
	const content = h("div"), message = h("p", {
		class: "muted",
		role: "status"
	});
	panel.append(h("h2", {}, t("tailscale_title")), content, message);
	main.append(panel);
	let disposed = false, busy = false, pending = false, readable = false, snapshot, intent, receipt, damaged = false;
	const alive = () => !disposed && panel.isConnected;
	const hex = (value, size) => typeof value === "string" && new RegExp(`^[0-9a-f]{${size}}$`).test(value);
	const validReceipt = (value) => value && hex(value.request_id, 32) && [
		"uncertain",
		"started",
		"not_started"
	].includes(value.phase);
	const key = () => `batc.desktop.tailscale.${snapshot.scope}`;
	const accept = (value, scope, id) => {
		if (value?.version !== 1 || value.scope !== scope || value.receipt !== null && (!validReceipt(value.receipt) || value.receipt.request_id !== id)) throw Error("invalid");
		receipt = value.receipt;
	};
	const save = () => {
		if (intent) localStorage.setItem(key(), JSON.stringify({ request_id: intent }));
		else localStorage.removeItem(key());
	};
	const render = () => {
		if (!alive()) return;
		const native = nativeDesktop && snapshot?.supported === true;
		const state = !nativeDesktop ? "browser" : snapshot?.supported === false ? "unsupported" : !readable ? "unknown" : snapshot.installation !== "available" ? snapshot.installation : snapshot.login;
		const unknown = intent && (!receipt || receipt.phase === "uncertain");
		content.replaceChildren(...[
			h("p", {}, t("tailscale_" + state)),
			native ? h("p", { class: "muted" }, t("tailscale_help")) : null,
			intent ? h("p", { class: "muted" }, t("tailscale_" + (receipt?.phase || "uncertain"))) : null,
			intent ? h("details", {}, h("summary", {}, t("tailscale_request")), h("code", {}, intent)) : null,
			damaged ? h("p", { class: "error" }, t("tailscale_damaged")) : null,
			nativeDesktop ? h("div", { class: "actions" }, h("button", {
				class: "secondary",
				disabled: busy || !native || !readable || !snapshot.can_open || damaged || !!intent,
				onclick: () => run(async () => {
					intent = crypto.randomUUID().replaceAll("-", "");
					receipt = null;
					save();
					await open();
				})
			}, t("tailscale_open")), unknown && !receipt && !damaged ? h("button", {
				class: "secondary",
				disabled: busy || !readable || !snapshot?.can_open,
				onclick: () => run(open)
			}, t("tailscale_retry")) : null, receipt && receipt.phase !== "uncertain" ? h("button", {
				class: "secondary",
				disabled: busy,
				onclick: () => run(async () => {
					const previous = intent;
					intent = null;
					try {
						save();
					} catch (error) {
						intent = previous;
						throw error;
					}
					receipt = null;
				})
			}, t("tailscale_new")) : null, h("button", {
				class: "secondary",
				disabled: busy,
				onclick: refresh
			}, t("tailscale_refresh"))) : null
		].filter(Boolean));
	};
	const read = async () => {
		const value = await tailscaleControl({ action: "status" });
		if (!alive()) return;
		if (value?.version !== 1 || typeof value.supported !== "boolean" || typeof value.can_open !== "boolean" || ![
			"missing",
			"incomplete",
			"available",
			"unknown"
		].includes(value.installation) || ![
			"unknown",
			"needs_login",
			"needs_approval",
			"stopped",
			"starting",
			"running"
		].includes(value.login) || value.latest !== null && !validReceipt(value.latest) || value.supported && !hex(value.scope, 64)) throw Error("invalid");
		if (value.scope !== snapshot?.scope) {
			intent = receipt = null;
			damaged = false;
			snapshot = value;
			if (value.supported) try {
				const saved = JSON.parse(localStorage.getItem(key()) || "null");
				if (saved && hex(saved.request_id, 32)) intent = saved.request_id;
				else if (saved) damaged = true;
			} catch {
				damaged = true;
			}
		}
		snapshot = value;
		if (value.latest?.phase === "uncertain" && (!intent || intent !== value.latest.request_id)) {
			intent = value.latest.request_id;
			receipt = value.latest;
			save();
		}
		if (intent) {
			const result = await tailscaleControl({
				action: "receipt",
				request_id: intent
			});
			if (!alive()) return;
			accept(result, value.scope, intent);
		}
		readable = true;
	};
	const open = async () => {
		if (!intent || !snapshot?.supported || damaged) return;
		save();
		const scope = snapshot.scope, id = intent;
		const value = await tailscaleControl({
			action: "open",
			request_id: id
		});
		if (!alive()) return;
		accept(value, scope, id);
		pending = true;
	};
	const run = async (action) => {
		if (!alive() || busy) return;
		busy = true;
		message.textContent = "";
		render();
		try {
			await action();
		} catch {
			if (alive()) {
				readable = false;
				message.textContent = t("tailscale_read_failed");
			}
		} finally {
			busy = false;
			render();
			if (pending && alive()) {
				pending = false;
				refresh();
			}
		}
	};
	const refresh = () => {
		if (busy) {
			pending = true;
			return;
		}
		return run(read);
	};
	const returned = () => {
		if (document.visibilityState === "visible" && alive()) refresh();
	};
	render();
	if (nativeDesktop) {
		window.addEventListener("focus", returned);
		document.addEventListener("visibilitychange", returned);
		refresh();
	}
	return () => {
		disposed = true;
		window.removeEventListener("focus", returned);
		document.removeEventListener("visibilitychange", returned);
		panel.remove();
	};
}
//#endregion
//#region src/updates.js
init_transport();
async function mountUpdates(main, { h, t }) {
	const panel = h("section", {
		class: "panel",
		"aria-label": t("update_title")
	});
	const content = h("div"), message = h("p", {
		role: "status",
		class: "muted"
	});
	panel.append(h("h2", {}, t("update_title")), content, message);
	main.append(panel);
	let disposed = false, busy = false, readable = false, value;
	const active = () => !disposed && panel.isConnected;
	const phases = new Set([
		"idle",
		"checking",
		"available",
		"up_to_date",
		"check_failed",
		"downloading",
		"download_failed",
		"verified",
		"stopping_fleet",
		"installation_unknown"
	]);
	const render = () => {
		if (!active()) return;
		if (!value) {
			content.replaceChildren(h("button", {
				class: "secondary",
				disabled: busy,
				onclick: () => request({ action: "status" })
			}, t("update_read")));
			return;
		}
		const blocked = busy || !readable || !value.available || [
			"checking",
			"downloading",
			"stopping_fleet",
			"installation_unknown"
		].includes(value.phase);
		const candidate = value.candidate;
		content.replaceChildren(h("p", {}, t("update_current", { version: value.current_version })), h("p", { class: "muted" }, !value.available ? t(value.code === "UPDATE_PLATFORM_UNSUPPORTED" ? "update_platform" : "update_unsigned") : t("update_phase_" + value.phase)), ...candidate ? [h("dl", { class: "kv" }, h("dt", {}, t("update_candidate")), h("dd", {}, candidate.version), h("dt", {}, t("pub_sha")), h("dd", { class: "mono" }, candidate.source_sha))] : [], ...value.installation ? [h("p", {}, t("update_requested", { version: value.installation.to_version }))] : [], ...value.available ? [h("p", { class: "muted" }, t("update_help")), h("div", { class: "actions" }, h("button", {
			class: candidate ? "secondary" : "primary",
			disabled: blocked,
			onclick: () => request({ action: "check" })
		}, t("update_check")), ...candidate ? [h("button", {
			class: "primary",
			disabled: blocked || value.phase === "verified",
			onclick: () => request({
				action: "download",
				candidate_id: candidate.candidate_id
			})
		}, t("update_download")), h("button", {
			class: value.phase === "verified" ? "primary" : "secondary",
			disabled: blocked || value.phase !== "verified",
			onclick: () => request({
				action: "install",
				candidate_id: candidate.candidate_id
			})
		}, t("update_install"))] : [], h("button", {
			class: "secondary",
			disabled: busy,
			onclick: () => request({ action: "status" })
		}, t("update_read")))] : []);
	};
	const request = async (input) => {
		if (busy || !active()) return;
		busy = true;
		readable = false;
		message.textContent = "";
		render();
		try {
			const next = await updateRequest(input);
			if (!active()) return;
			if (!next || typeof next.current_version !== "string" || typeof next.available !== "boolean" || !phases.has(next.phase) || next.candidate && [
				"candidate_id",
				"version",
				"source_sha"
			].some((k) => typeof next.candidate[k] !== "string")) throw new Error("UPDATE_STATUS_INVALID");
			value = next;
			readable = true;
			if (next.code && next.available && !next.installation) message.textContent = `${t("update_problem")} ${next.code}`;
		} catch {
			if (active()) message.textContent = t(input.action === "install" ? "update_unknown" : "update_read_failed");
		} finally {
			busy = false;
			render();
		}
	};
	await request({ action: "status" });
	return () => {
		disposed = true;
		panel.remove();
	};
}
//#endregion
//#region src/capture.js
var record$2 = (value) => value && typeof value === "object" && !Array.isArray(value);
var digest$2 = (value) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
var operationId$2 = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var previewId = (value) => typeof value === "string" && /^acpv_[0-9a-f]{32}$/.test(value);
var previewToken = (value) => typeof value === "string" && value.length > 0 && value.length <= 24576;
var validPreview$3 = (doc) => record$2(doc) && record$2(doc.source) && record$2(doc.evidence) && [
	doc.relative_path,
	doc.source.host,
	doc.source.session_id,
	doc.source.root,
	doc.source.repository_root,
	doc.evidence.head_sha
].every((value) => typeof value === "string" && value.length > 0) && doc.source.provenance === "manual" && doc.snapshot === false && Number.isFinite(doc.expires_at) && previewId(doc.preview_id) && previewToken(doc.preview_token) && digest$2(doc.fingerprint) && digest$2(doc.evidence.digest) && Number.isSafeInteger(doc.evidence.size_bytes) && doc.evidence.size_bytes >= 0;
function restore$2(value, source) {
	const saved = { input: {
		...source,
		relative_path: ""
	} };
	if (!record$2(value)) return saved;
	if (record$2(value.input)) {
		for (const key of [
			"host",
			"session_id",
			"relative_path"
		]) if (typeof value.input[key] === "string") saved.input[key] = value.input[key];
	}
	if (validPreview$3(value.preview)) saved.preview = value.preview;
	const intent = value.intent, request = intent?.request;
	const usable = request?.action === "artifact.capture" && previewId(request.target?.preview_id) && previewToken(request.params?.preview_token) && digest$2(request.preconditions?.expected_fingerprint) && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200;
	if (usable || operationId$2(intent?.operation_id)) saved.intent = {
		key: usable ? intent.key : null,
		request: usable ? request : null,
		operation_id: operationId$2(intent.operation_id) ? intent.operation_id : null,
		reviewed_digest: digest$2(intent.reviewed_digest) ? intent.reviewed_digest : saved.preview?.evidence.digest
	};
	return saved;
}
function capturePanel({ h, t, api, caps, guard, onEvents, errorBox, storageKey, source = {}, onAttach }) {
	let saved;
	try {
		saved = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	saved = restore$2(saved, source);
	let busy = false, revision = 0, disposed = false, refreshing = null;
	const host = h("select", { "aria-label": t("capture_host") }, h("option", { value: "" }, t("capture_host")), ...(caps()?.hosts || []).map((item) => h("option", { value: item.host }, item.host)));
	const session = h("input", {
		"aria-label": t("capture_session"),
		placeholder: "sess-…",
		maxlength: 256
	});
	const path = h("input", {
		"aria-label": t("capture_path"),
		placeholder: "notes/input.txt"
	});
	host.value = saved.input.host || "";
	session.value = saved.input.session_id || "";
	path.value = saved.input.relative_path || "";
	const notice = h("div", { role: "status" }), evidence = h("div", { "data-capture-evidence": "" });
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => update()
	});
	const review = h("label", { class: "capture-choice" }, reviewed, " ", t("capture_review"));
	const persist = () => {
		guard();
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
		} catch {}
	};
	const current = () => ({
		host: host.value,
		session_id: session.value.trim(),
		relative_path: path.value
	});
	const scopes = () => caps()?.scopes || [];
	const supported = () => caps()?.artifacts?.capture?.manual_single_file === true;
	const mayPreview = () => supported() && scopes().includes("observe");
	const mayCapture = () => mayPreview() && scopes().includes("manage") && caps()?.actions?.some((item) => item.action === "artifact.capture" && item.allowed === true);
	const expired = () => !saved.preview || saved.preview.expires_at * 1e3 <= Date.now();
	const settled = () => [
		"succeeded",
		"failed",
		"cancelled"
	].includes(saved.operation?.status);
	const active = () => Boolean(saved.intent && (!settled() || saved.operation.status === "succeeded" && !saved.result) && !saved.refused);
	const currentView = () => {
		try {
			guard();
			return !disposed;
		} catch {
			return false;
		}
	};
	const validInput = (input) => input.host && input.session_id.length >= 6 && input.session_id.length <= 256 && !/[\x00-\x1f\x7f-\x9f/\\]/.test(input.session_id) && input.relative_path && new TextEncoder().encode(input.relative_path).length <= 4096 && !/[\\\x00-\x1f\x7f-\x9f]/.test(input.relative_path) && input.relative_path.split("/").every((part) => part && part !== "." && part !== ".." && part.toLowerCase() !== ".git");
	const showError = (error) => {
		if (currentView()) notice.replaceChildren(errorBox(error));
	};
	const preview = h("button", {
		class: "secondary",
		onclick: async () => {
			const input = current();
			guard();
			if (busy || saved.intent || !mayPreview() || !validInput(input)) return;
			const ticket = ++revision;
			busy = true;
			saved.preview = null;
			reviewed.checked = false;
			persist();
			render();
			try {
				const row = (await api("GET", `/sessions/${encodeURIComponent(input.host)}/${encodeURIComponent(input.session_id)}`)).session;
				guard();
				if (ticket !== revision) return;
				if (row?.provenance !== "manual" || row.host !== input.host || row.session_id !== input.session_id) throw new Error(t("capture_manual_only"));
				const response = await api("POST", "/artifact-capture-previews", input);
				guard();
				if (ticket !== revision) return;
				const doc = response.preview;
				if (!validPreview$3(doc) || doc.source.host !== input.host || doc.source.session_id !== input.session_id || doc.relative_path !== input.relative_path) throw new Error(t("capture_invalid_preview"));
				saved.preview = doc;
				persist();
				notice.replaceChildren();
			} catch (error) {
				if (ticket === revision) showError(error);
			} finally {
				busy = false;
				render();
			}
		}
	}, t("capture_preview"));
	const accept = async (operation) => {
		guard();
		const intent = saved.intent;
		if (!intent || !operationId$2(operation?.operation_id) || operation.action !== "artifact.capture" || intent.operation_id && intent.operation_id !== operation.operation_id || intent.request && operation.target?.preview_id !== intent.request.target.preview_id) throw new Error(t("capture_invalid_result"));
		saved.operation = operation;
		saved.intent.operation_id = operation.operation_id;
		persist();
		if (operation.status === "succeeded") {
			const ref = operation.result;
			if (!/^art_[0-9a-f]{32}$/.test(ref?.artifact_id) || !Number.isSafeInteger(ref.revision) || ref.revision < 1 || !digest$2(ref.digest) || ref.digest !== intent.reviewed_digest) throw new Error(t("capture_invalid_result"));
			const { artifact } = await api("GET", `/artifacts/${ref.artifact_id}/revisions/${ref.revision}`);
			guard();
			if (saved.intent !== intent) return;
			if (artifact.artifact_id !== ref.artifact_id || artifact.revision !== ref.revision || artifact.state !== "ready" || artifact.digest !== ref.digest || artifact.source?.kind !== "manual_capture" || artifact.source.operation_id !== operation.operation_id) throw new Error(t("capture_invalid_result"));
			saved.result = {
				artifact_id: ref.artifact_id,
				revision: ref.revision,
				digest: ref.digest
			};
			persist();
		}
		render();
	};
	const apply = h("button", {
		class: "secondary",
		onclick: async () => {
			guard();
			if (busy || !mayCapture() || settled() && (saved.operation.status !== "succeeded" || saved.result) || saved.refused) return;
			if (!saved.intent) {
				if (expired() || !reviewed.checked) return;
				const doc = saved.preview;
				saved.intent = {
					key: crypto.randomUUID(),
					reviewed_digest: doc.evidence.digest,
					request: {
						action: "artifact.capture",
						target: { preview_id: doc.preview_id },
						params: { preview_token: doc.preview_token },
						preconditions: { expected_fingerprint: doc.fingerprint }
					}
				};
				persist();
			}
			busy = true;
			update();
			try {
				const intent = saved.intent;
				const result = intent.operation_id ? await api("GET", `/operations/${intent.operation_id}`) : await api("POST", "/operations?wait=3", intent.request, intent.key);
				guard();
				await accept(result.operation);
				notice.replaceChildren();
			} catch (error) {
				if (!currentView()) return;
				if (!saved.intent.operation_id && [
					"PREVIEW_EXPIRED",
					"PREVIEW_TOKEN_INVALID",
					"PREVIEW_MISMATCH",
					"INVALID_PARAMS"
				].includes(error.code)) saved.refused = true;
				persist();
				showError(error);
			} finally {
				busy = false;
				render();
			}
		}
	}, t("capture_save"));
	const reset = h("button", {
		class: "secondary",
		onclick: () => {
			guard();
			if (busy || refreshing || active()) return;
			saved = { input: current() };
			reviewed.checked = false;
			revision++;
			persist();
			notice.replaceChildren();
			render();
		}
	}, t("capture_new"));
	const attach = onAttach ? h("button", {
		class: "secondary",
		onclick: () => {
			guard();
			if (saved.result) {
				onAttach({ ...saved.result }, (saved.preview?.relative_path || saved.input.relative_path).split("/").at(-1));
				notice.textContent = t("capture_attached");
			}
		}
	}, t("capture_attach")) : null;
	const box = h("details", {
		class: "capture",
		"data-capture": "",
		hidden: !supported()
	}, h("summary", {}, t("capture_title")), h("p", { class: "muted" }, t("capture_help")), h("div", { class: "capture-fields" }, h("label", {}, t("capture_host"), host), h("label", {}, t("capture_session"), session), h("label", {}, t("capture_path"), path)), h("div", { class: "actions" }, preview), evidence, review, h("div", { class: "actions" }, apply, attach, reset), notice);
	function update() {
		const frozen = busy || Boolean(saved.intent);
		for (const field of [
			host,
			session,
			path
		]) field.disabled = frozen;
		preview.disabled = busy || Boolean(saved.intent) || !mayPreview() || !validInput(current());
		review.hidden = !saved.preview || Boolean(saved.intent);
		reviewed.disabled = expired();
		apply.hidden = settled() && (saved.operation.status !== "succeeded" || saved.result);
		apply.textContent = saved.intent ? t("capture_check") : t("capture_save");
		apply.disabled = busy || !mayCapture() || Boolean(saved.refused) || !saved.intent && (expired() || !reviewed.checked);
		reset.hidden = !saved.intent;
		reset.disabled = busy || Boolean(refreshing) || active();
		if (attach) {
			attach.hidden = !saved.result;
			attach.disabled = busy;
		}
		const expiry = evidence.querySelector("[data-capture-expiry]");
		if (expiry) expiry.textContent = saved.intent ? t("capture_fixed") : expired() ? t("capture_expired") : t("capture_single_file");
	}
	function render() {
		if (disposed) return;
		evidence.replaceChildren();
		if (!mayPreview()) evidence.append(h("p", { class: "muted" }, t("capture_scope_observe")));
		else if (!mayCapture()) evidence.append(h("p", { class: "muted" }, t("capture_scope_manage")));
		const doc = saved.preview;
		if (doc) {
			const facts = [
				[t("capture_name"), doc.relative_path.split("/").at(-1)],
				[t("capture_bytes"), String(doc.evidence.size_bytes)],
				["SHA-256", doc.evidence.digest],
				[t("capture_source"), `${doc.source.host} / ${doc.source.session_id}`],
				[t("capture_path"), doc.relative_path],
				[t("capture_root"), doc.source.root],
				[t("capture_repository"), doc.source.repository_root],
				["HEAD", doc.evidence.head_sha],
				[t("capture_expiry"), new Date(doc.expires_at * 1e3).toLocaleString()]
			];
			evidence.append(h("dl", { class: "kv" }, ...facts.flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, h("code", {}, value))])), h("p", {
				class: "muted",
				"data-capture-expiry": ""
			}));
		}
		if (saved.intent) evidence.append(h("p", {}, saved.operation ? `${t("op_" + saved.operation.status)} ` : t("capture_unknown"), saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, saved.intent.operation_id) : null, saved.operation?.status_reason ? ` · ${saved.operation.status_reason}` : ""));
		if (saved.result) evidence.append(h("p", { class: "pre" }, t("capture_saved"), " ", `${saved.result.artifact_id} · r${saved.result.revision} · ${saved.result.digest}`));
		update();
	}
	for (const field of [
		host,
		session,
		path
	]) field.addEventListener("input", () => {
		guard();
		if (saved.intent) return;
		revision++;
		saved.input = current();
		saved.preview = null;
		reviewed.checked = false;
		persist();
		render();
	});
	const refresh = async (fresh = false) => {
		if (!saved.intent?.operation_id) return;
		if (refreshing) {
			await refreshing;
			if (!fresh) return;
			guard();
			return refresh(true);
		}
		const id = saved.intent.operation_id;
		refreshing = (async () => {
			while (busy) {
				await new Promise((resolve) => setTimeout(resolve, 25));
				guard();
			}
			const { operation } = await api("GET", `/operations/${id}`);
			guard();
			if (saved.intent?.operation_id === id) await accept(operation);
		})();
		try {
			await refreshing;
		} finally {
			refreshing = null;
		}
	};
	const off = onEvents((event) => {
		if (!box.isConnected) {
			off();
			return;
		}
		if (!currentView()) {
			off();
			return;
		}
		if (event.resource_id === saved.intent?.operation_id || event.resource_id === saved.result?.artifact_id) return refresh(true);
	});
	const timer = setInterval(() => {
		if (!box.isConnected) {
			disposed = true;
			clearInterval(timer);
			off();
			return;
		}
		try {
			guard();
		} catch {
			disposed = true;
			clearInterval(timer);
			off();
			return;
		}
		update();
		if (saved.intent?.operation_id && (active() || saved.operation?.status === "succeeded" && !saved.result)) refresh().catch(showError);
	}, 1e3);
	queueMicrotask(() => {
		if (box.isConnected && saved.intent?.operation_id) refresh().catch(showError);
	});
	render();
	return box;
}
//#endregion
//#region src/task-controls.js
var object$4 = (value) => value && typeof value === "object" && !Array.isArray(value);
var opId$2 = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var version = (value) => Number.isSafeInteger(value) && value >= 0;
var equal$5 = (a, b) => a === b || object$4(a) && object$4(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$5(a[k], b[k]));
var terminal$6 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
function valid(request, id) {
	return ["task.pause", "task.resume"].includes(request?.action) && equal$5(request.target, { task_id: id }) && object$4(request.params) && (request.action === "task.pause" ? typeof request.params.abort_current === "boolean" && Object.keys(request.params).length === 1 : Object.keys(request.params).length === 0) && object$4(request.preconditions) && Object.keys(request.preconditions).length === 1 && version(request.preconditions.control_version);
}
function taskControlsPanel({ h, t, api, caps, guard, ready, task, taskId, storageKey, errorBox, opStatus, onSettled }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = { abort: raw?.abort === true }, operation = null, submission = null, refreshing = null, busy = false, readFailed = false;
	if (raw?.intent) {
		const proven = valid(raw.intent.request, taskId) && typeof raw.intent.key === "string" && raw.intent.key.length > 0 && raw.intent.key.length <= 200;
		saved.intent = {
			request: proven ? raw.intent.request : null,
			key: proven ? raw.intent.key : null,
			operation_id: opId$2(raw.intent.operation_id) ? raw.intent.operation_id : null
		};
		if (proven && !saved.intent.operation_id && raw.intent.refused === "CONTROL_VERSION_CONFLICT") saved.intent.refused = raw.intent.refused;
		if (proven) saved.abort = raw.intent.request.params.abort_current === true;
	}
	const live = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = () => {
		guard();
		localStorage.setItem(storageKey, JSON.stringify(saved));
	};
	const observed = () => task()?.task_id === taskId && version(task()?.control_version) && [
		true,
		false,
		0,
		1
	].includes(task()?.paused);
	const action = () => saved.intent?.request?.action || (task()?.paused ? "task.resume" : "task.pause");
	const permitted = () => (caps()?.scopes || []).includes("operate") && caps()?.actions?.some((a) => a.action === action() && a.allowed === true);
	const writable = () => ready() && observed() && permitted() && (saved.intent || !["done", "failed"].includes(task()?.state));
	const abort = h("input", {
		type: "checkbox",
		checked: saved.abort
	});
	const message = h("div", { role: "status" }), result = h("div", { "data-task-result": "" }), restriction = h("p", { class: "muted" });
	const showError = (error) => {
		if (live()) {
			message.replaceChildren(errorBox(error));
			update();
		}
	};
	const accept = (candidate) => {
		guard();
		const intent = saved.intent;
		if (!intent || !opId$2(candidate?.operation_id) || !["task.pause", "task.resume"].includes(candidate.action) || candidate.target?.task_id !== taskId || candidate.actor !== caps()?.actor || intent.operation_id && candidate.operation_id !== intent.operation_id || intent.key && candidate.idempotency_key !== intent.key || intent.request && !equal$5({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request)) throw new Error(t("task_control_invalid"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		persist();
		readFailed = false;
		message.replaceChildren();
		update();
	};
	const apply = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!live() || busy || refreshing || readFailed || !writable() || saved.intent?.operation_id || saved.intent && (!saved.intent.request || saved.intent.refused)) return;
			const previous = saved;
			if (!saved.intent) saved = {
				...saved,
				intent: {
					request: {
						action: action(),
						target: { task_id: taskId },
						params: action() === "task.pause" ? { abort_current: saved.abort } : {},
						preconditions: { control_version: task().control_version }
					},
					key: crypto.randomUUID(),
					operation_id: null
				}
			};
			try {
				persist();
			} catch (e) {
				saved = previous;
				showError(e);
				return;
			}
			busy = true;
			update();
			const intent = saved.intent;
			submission = (async () => {
				try {
					const response = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(response.operation);
				} catch (e) {
					if (live()) {
						if (e.code === "CONTROL_VERSION_CONFLICT" && e.status === 409) {
							intent.refused = e.code;
							try {
								persist();
							} catch {}
						}
						showError(e);
					}
				} finally {
					busy = false;
					if (live()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
			if (live()) try {
				await onSettled?.();
			} catch (e) {
				showError(e);
			}
		}
	}, t("task_pause"));
	const check = h("button", {
		class: "secondary",
		onclick: () => (onSettled ? onSettled() : refresh(true)).catch(showError)
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: () => {
			if (!live() || busy || refreshing || readFailed || !writable() || !(terminal$6(operation) || saved.intent?.refused)) return;
			const previous = saved;
			saved = { abort: false };
			try {
				persist();
			} catch (e) {
				saved = previous;
				showError(e);
				return;
			}
			operation = null;
			abort.checked = false;
			message.replaceChildren();
			update();
		}
	}, t("task_control_new"));
	const abortLabel = h("label", { class: "muted" }, abort, " ", t("task_abort"));
	abort.onchange = () => {
		if (!live() || saved.intent || busy) {
			abort.checked = saved.abort;
			return;
		}
		saved.abort = abort.checked;
		try {
			persist();
		} catch (e) {
			showError(e);
		}
		update();
	};
	const box = h("section", {
		class: "panel",
		"data-task-controls": ""
	}, h("h2", {}, t("task_controls")), h("p", { class: "muted" }, t("task_control_help")), abortLabel, h("div", { class: "actions" }, apply, check, another), restriction, result, message);
	function update() {
		const fixed = Boolean(saved.intent);
		abortLabel.hidden = action() !== "task.pause";
		abort.disabled = fixed || busy;
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.disabled = busy || Boolean(refreshing) || readFailed || !writable() || Boolean(fixed && !saved.intent.request);
		apply.textContent = t(fixed ? "permissions_retry" : action() === "task.pause" ? "task_pause" : "task_resume");
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$6(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed || !writable();
		restriction.textContent = writable() ? "" : t("task_control_unavailable");
		result.replaceChildren();
		if (fixed) {
			result.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "task_control_refused" : "permissions_unknown"), " ", ...saved.intent.operation_id ? [h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details"))] : []), h("p", { class: "muted" }, t("task_control_fixed", { version: saved.intent.request?.preconditions.control_version ?? "?" })));
			if (operation?.status_reason) result.append(h("p", {}, operation.status_reason));
			if (operation?.status === "succeeded") result.append(h("p", { class: "muted" }, t("task_control_recorded")));
			if (!saved.intent.request && !saved.intent.operation_id) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		}
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) return;
		refreshing = (async () => {
			const data = await api("GET", `/operations/${saved.intent.operation_id}`);
			guard();
			accept(data.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			readFailed = true;
			showError(e);
			throw e;
		} finally {
			refreshing = null;
			if (live()) update();
		}
	}
	update();
	return {
		box,
		update,
		refresh
	};
}
//#endregion
//#region src/operation-list.js
function operationList({ h, t, api, guard, row, statuses }) {
	let rows = [], before = null, pages = 1, queue = Promise.resolve(), pending = 0, failed = false;
	const list = h("div", {
		class: "panel",
		"data-operation-list": ""
	}), count = h("p", {
		class: "muted",
		"data-operation-count": ""
	}), status = h("div", { role: "status" });
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const update = () => {
		more.hidden = before === null;
		more.disabled = pending > 0 || failed;
		refresh.disabled = pending > 0;
	};
	const more = h("button", {
		class: "secondary",
		onclick: () => load(true).catch(() => {})
	}, t("operations_more"));
	const refresh = h("button", {
		class: "secondary",
		onclick: () => load().catch(() => {})
	}, t("refresh"));
	const box = h("div", {}, count, list, status, h("div", { class: "actions" }, more, refresh));
	function load(append = false) {
		pending++;
		update();
		const job = queue.catch(() => {}).then(async () => {
			guard();
			if (append && before === null) return;
			const first = [...list.children].find((el) => el.getBoundingClientRect().bottom >= 0);
			const anchor = first?.dataset.operationId, top = first?.getBoundingClientRect().top;
			let next = append ? before : null, candidate = append ? [...rows] : [], read = 0;
			const targetPages = append ? 1 : pages;
			for (let i = 0; i < targetPages; i++) {
				const params = new URLSearchParams({ limit: "100" });
				if (statuses) params.set("status", statuses);
				if (next !== null) params.set("before", String(next));
				const result = await api("GET", "/operations?" + params);
				guard();
				if (!Array.isArray(result.operations) || result.operations.some((op) => !/^op_[0-9a-f]{32}$/.test(op?.operation_id)) || result.next_before !== null && result.next_before !== void 0 && (typeof result.next_before !== "number" || !Number.isFinite(result.next_before) || result.next_before <= 0 || next !== null && result.next_before >= next || result.operations.length === 0)) throw new Error(t("operations_invalid_page"));
				candidate.push(...result.operations);
				read++;
				next = result.next_before ?? null;
				if (next === null) break;
			}
			guard();
			rows = [...new Map(candidate.map((op) => [op.operation_id, op])).values()];
			pages = append ? pages + read : read;
			before = next;
			failed = false;
			list.replaceChildren(...rows.length ? rows.map((op) => {
				const el = row(op);
				el.dataset.operationId = op.operation_id;
				return el;
			}) : [h("p", { class: "muted" }, t("operations_empty"))]);
			count.textContent = t("operations_loaded", { count: rows.length });
			status.replaceChildren();
			const restored = [...list.children].find((el) => el.dataset.operationId === anchor);
			if (restored && top !== void 0) window.scrollBy(0, restored.getBoundingClientRect().top - top);
		}).catch((error) => {
			if (current()) {
				failed = true;
				status.replaceChildren(h("p", { class: "error" }, error.message));
			}
			throw error;
		}).finally(() => {
			pending--;
			if (current()) update();
		});
		queue = job;
		return job;
	}
	update();
	return {
		box,
		load
	};
}
//#endregion
//#region src/permissions.js
var record$1 = (value) => value && typeof value === "object" && !Array.isArray(value);
var modeValue = (value) => ["default", "allow_all"].includes(value);
var operationId$1 = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var terminal$5 = (operation) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(operation?.status);
var admissionRefusals$2 = new Set([
	"TASK_PAUSED",
	"CONTROL_VERSION_CONFLICT",
	"PERMISSIONS_HOST_POLICY",
	"CONFINEMENT_RAISE_REFUSED"
]);
function restore$1(value, target) {
	const saved = { mode: modeValue(value?.mode) ? value.mode : "default" };
	if (!record$1(value) || !value.intent) return saved;
	const intent = value.intent, request = intent.request;
	const valid = request?.action === "session.permissions" && request.target?.host === target.host && request.target?.session_id === target.session_id && modeValue(request.params?.mode) && record$1(request.preconditions) && Object.keys(request.preconditions).length === 0 && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200;
	saved.intent = {
		key: valid ? intent.key : null,
		request: valid ? {
			action: "session.permissions",
			target: { ...target },
			params: { mode: request.params.mode },
			preconditions: {}
		} : null,
		operation_id: operationId$1(intent.operation_id) ? intent.operation_id : null
	};
	if (valid && !saved.intent.operation_id && admissionRefusals$2.has(intent.refused)) saved.intent.refused = intent.refused;
	if (valid) saved.mode = request.params.mode;
	return saved;
}
function permissionsPanel({ h, t, api, caps, guard, errorBox, opStatus, storageKey, target, session, ready }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = restore$1(raw, target), operation = null, busy = false, refreshing = null, submission = null, readFailed = false;
	const mode = h("select", { "aria-label": t("permissions_mode") }, ...["default", "allow_all"].map((value) => h("option", { value }, t("permissions_" + value))));
	mode.value = saved.mode;
	const message = h("div", { role: "status" }), result = h("div", { "data-permission-result": "" });
	const explanation = h("p", { class: "muted" }), restriction = h("p", { class: "muted" });
	const persist = () => {
		guard();
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
		} catch {}
	};
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const writable = () => ready() && session()?.api_access === "managed" && session()?.provenance === "connector_managed" && (caps()?.scopes || []).includes("operate") && caps()?.hosts?.some((host) => host.host === target.host && host.writes === true) && caps()?.actions?.some((action) => action.action === "session.permissions" && action.allowed === true);
	const accept = (candidate) => {
		guard();
		if (!saved.intent || !operationId$1(candidate?.operation_id) || candidate.action !== "session.permissions" || candidate.target?.host !== target.host || candidate.target?.session_id !== target.session_id || !modeValue(candidate.params?.mode) || saved.intent.request && candidate.params.mode !== saved.intent.request.params.mode || saved.intent.key && candidate.idempotency_key !== saved.intent.key || saved.intent.operation_id && candidate.operation_id !== saved.intent.operation_id) throw new Error(t("permissions_invalid_result"));
		operation = candidate;
		saved.intent.operation_id = candidate.operation_id;
		saved.mode = candidate.params.mode;
		mode.value = saved.mode;
		readFailed = false;
		persist();
		message.replaceChildren();
		update();
	};
	const apply = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || readFailed || !writable() || saved.intent?.operation_id || saved.intent && (!saved.intent.request || saved.intent.refused)) return;
			busy = true;
			if (!saved.intent) {
				saved.intent = {
					key: crypto.randomUUID(),
					request: {
						action: "session.permissions",
						target: { ...target },
						params: { mode: saved.mode },
						preconditions: {}
					},
					operation_id: null
				};
				persist();
			}
			const intent = saved.intent;
			update();
			submission = (async () => {
				try {
					const response = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					if (saved.intent === intent) accept(response.operation);
				} catch (error) {
					if (current()) {
						if (error.status >= 400 && error.status < 500 && admissionRefusals$2.has(error.code)) {
							intent.refused = error.code;
							persist();
						}
						message.replaceChildren(errorBox(error));
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("permissions_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(showError)
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: () => {
			if (!current() || busy || refreshing || readFailed || !(terminal$5(operation) || saved.intent?.refused) || !writable()) return;
			saved = { mode: "default" };
			mode.value = saved.mode;
			operation = null;
			persist();
			message.replaceChildren();
			update();
		}
	}, t("permissions_new"));
	const box = h("details", {
		class: "permissions",
		"data-permissions": ""
	}, h("summary", {}, t("permissions_title")), h("p", { class: "muted" }, t("permissions_help")), h("label", { class: "permission-mode" }, t("permissions_mode"), mode), explanation, h("div", { class: "actions" }, apply, check, another), restriction, result, message);
	mode.addEventListener("change", () => {
		if (!current() || saved.intent) {
			mode.value = saved.mode;
			return;
		}
		saved.mode = modeValue(mode.value) ? mode.value : "default";
		persist();
		update();
	});
	function update() {
		const managed = session()?.api_access === "managed" && session()?.provenance === "connector_managed";
		box.hidden = !managed;
		mode.disabled = busy || Boolean(saved.intent);
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.disabled = busy || readFailed || !writable() || Boolean(saved.intent && !saved.intent.request);
		apply.textContent = t(saved.intent ? "permissions_retry" : "permissions_apply");
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$5(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed || !writable();
		explanation.textContent = t(saved.mode === "allow_all" ? "permissions_allow_help" : "permissions_default_help");
		restriction.textContent = writable() ? "" : t("permissions_unavailable");
		result.replaceChildren();
		if (saved.intent) {
			result.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "permissions_refused" : "permissions_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null, operation?.status_reason ? ` · ${operation.status_reason}` : ""));
			result.append(h("p", { class: "muted" }, t("permissions_fixed")));
			if (operation?.status === "succeeded") result.append(h("p", { class: "muted" }, t("permissions_accepted"), operation.result?.agent_kind === "codex" ? " " + t("permissions_next_turn") : ""));
			if (!saved.intent.request && !saved.intent.operation_id) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		}
	}
	function showError(error) {
		if (current()) {
			readFailed = true;
			message.replaceChildren(errorBox(error));
			update();
		}
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) return;
		const intent = saved.intent;
		refreshing = (async () => {
			const response = await api("GET", `/operations/${intent.operation_id}`);
			guard();
			if (saved.intent === intent) accept(response.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (error) {
			showError(error);
			throw error;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	update();
	return {
		box,
		update,
		refresh
	};
}
//#endregion
//#region src/approvals.js
var object$3 = (value) => value && typeof value === "object" && !Array.isArray(value);
var opId$1 = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var mode = (value) => value === null || value === "default" || value === "allow_all";
var terminal$4 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var equal$4 = (a, b) => {
	if (a === b) return true;
	if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => equal$4(v, b[i]));
	return object$3(a) && object$3(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$4(a[k], b[k]));
};
var refusedBeforeAdmission = new Set([
	"BULK_PREVIEW_INVALID",
	"BULK_PREVIEW_EXPIRED",
	"BULK_PREVIEW_MISMATCH",
	"BULK_MODE_REFUSED",
	"CONTROL_VERSION_CONFLICT",
	"BULK_BINDING_CHANGED"
]);
function validPreview$2(p) {
	return object$3(p) && typeof p.host === "string" && p.host.length > 0 && (p.workspace === null || typeof p.workspace === "string") && typeof p.preview_token === "string" && p.preview_token.startsWith("bap1.") && p.preview_token.length <= 262144 && /^[0-9a-f]{64}$/.test(p.fingerprint) && Number.isFinite(p.expires_at) && equal$4(p.answer, {
		permission: "allow",
		dont_ask_again: true
	}) && Array.isArray(p.items) && p.items.length <= 50 && new Set(p.items.map((i) => i?.item_id)).size === p.items.length && p.items.every((i) => object$3(i) && /^bapi_[0-9a-f]{24}$/.test(i.item_id) && i.host === p.host && typeof i.session_id === "string" && typeof i.eligible === "boolean" && (!i.eligible || object$3(i.prompt) && typeof i.prompt.toolUseId === "string" && Array.isArray(i.allowed_modes) && i.allowed_modes.includes(null) && i.allowed_modes.every(mode)));
}
function validRequest$3(r) {
	return r?.action === "session.approve_pending" && typeof r.target?.host === "string" && Object.keys(r.target).length === 1 && typeof r.params?.preview_token === "string" && Object.keys(r.params).length === 2 && Array.isArray(r.params.selection) && r.params.selection.length > 0 && r.params.selection.length <= 50 && r.params.selection.every((s) => object$3(s) && Object.keys(s).length === 2 && /^bapi_[0-9a-f]{24}$/.test(s.item_id) && mode(s.mode)) && new Set(r.params.selection.map((s) => s.item_id)).size === r.params.selection.length && object$3(r.preconditions) && Object.keys(r.preconditions).length === 1 && /^[0-9a-f]{64}$/.test(r.preconditions.expected_fingerprint);
}
function approvalsPanel({ h, t, api, caps, guard, ready, errorBox, opStatus, storageKey }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = {
		host: typeof raw?.host === "string" ? raw.host : "",
		workspace: typeof raw?.workspace === "string" ? raw.workspace : ""
	};
	if (validPreview$2(raw?.preview) && raw.preview.host === saved.host && (raw.preview.workspace || "") === saved.workspace) saved.preview = raw.preview;
	if (raw?.intent) saved.intent = {
		request: validRequest$3(raw.intent.request) ? raw.intent.request : null,
		key: typeof raw.intent.key === "string" && raw.intent.key.length > 0 && raw.intent.key.length <= 200 ? raw.intent.key : null,
		operation_id: opId$1(raw.intent.operation_id) ? raw.intent.operation_id : null,
		refused: refusedBeforeAdmission.has(raw.intent.refused) && !raw.intent.operation_id ? raw.intent.refused : null
	};
	let operation = null, busy = false, submission = null, refreshing = null, readFailed = false;
	const selected = new Map(), controls = [];
	if (saved.preview && !saved.intent && Array.isArray(raw?.selection)) {
		for (const s of raw.selection) if (object$3(s) && saved.preview.items.some((i) => i.eligible && i.item_id === s.item_id && i.allowed_modes.includes(s.mode))) selected.set(s.item_id, s.mode);
	}
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = (required = false) => {
		guard();
		saved.selection = [...selected].map(([item_id, mode]) => ({
			item_id,
			mode
		}));
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
		} catch (error) {
			if (required) throw error;
		}
	};
	const observable = () => ready() && caps()?.scopes?.includes("observe");
	const writable = () => observable() && caps()?.scopes?.includes("operate") && caps()?.actions?.some((a) => a.action === "session.approve_pending" && a.allowed === true) && caps()?.hosts?.some((host) => host.host === (saved.intent?.request?.target.host || saved.host) && host.writes === true);
	const host = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("bulk_choose_host")), ...(caps()?.hosts || []).map((x) => h("option", { value: x.host }, x.host)));
	host.value = saved.host;
	const workspace = h("input", {
		"aria-label": t("bulk_workspace"),
		placeholder: t("bulk_workspace"),
		value: saved.workspace
	});
	const rows = h("div", { "data-approval-items": "" }), result = h("div", { "data-approval-result": "" }), status = h("div", { role: "status" });
	const summary = h("p", { class: "muted" });
	const previewButton = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || saved.intent || !observable() || !host.value) return;
			saved.host = host.value;
			saved.workspace = workspace.value.trim();
			workspace.value = saved.workspace;
			delete saved.preview;
			selected.clear();
			busy = true;
			persist();
			renderPreview();
			update();
			try {
				const p = await api("POST", "/approval-previews", {
					host: saved.host,
					...saved.workspace ? { workspace: saved.workspace } : {}
				});
				guard();
				if (!validPreview$2(p) || p.host !== saved.host || (p.workspace || "") !== saved.workspace) throw new Error(t("bulk_invalid_preview"));
				saved.preview = p;
				persist();
				status.replaceChildren();
				renderPreview();
			} catch (e) {
				if (current()) status.replaceChildren(errorBox(e));
			} finally {
				busy = false;
				if (current()) update();
			}
		}
	}, t("bulk_preview"));
	const accept = (candidate) => {
		guard();
		const intent = saved.intent;
		if (!intent || !opId$1(candidate?.operation_id) || !intent.request || !intent.key || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key || !equal$4({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request) || intent.operation_id && candidate.operation_id !== intent.operation_id) throw new Error(t("bulk_invalid_result"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		readFailed = false;
		persist();
		status.replaceChildren();
		update();
	};
	const apply = h("button", {
		class: "primary",
		onclick: async () => {
			if (!current() || busy || readFailed || !writable() || saved.intent?.operation_id || saved.intent?.refused) return;
			if (!saved.intent) {
				if (!saved.preview || saved.preview.expires_at * 1e3 <= Date.now() || !selected.size) {
					update();
					return;
				}
				const selection = saved.preview.items.filter((i) => selected.has(i.item_id)).map((i) => ({
					item_id: i.item_id,
					mode: selected.get(i.item_id)
				}));
				saved.intent = {
					key: crypto.randomUUID(),
					operation_id: null,
					request: {
						action: "session.approve_pending",
						target: { host: saved.preview.host },
						params: {
							preview_token: saved.preview.preview_token,
							selection
						},
						preconditions: { expected_fingerprint: saved.preview.fingerprint }
					}
				};
			}
			if (!saved.intent.request || !saved.intent.key) return;
			try {
				persist(true);
			} catch (error) {
				status.replaceChildren(errorBox(error));
				update();
				return;
			}
			busy = true;
			const intent = saved.intent;
			update();
			submission = (async () => {
				try {
					const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(data.operation);
				} catch (e) {
					if (current()) {
						if (e.status >= 400 && e.status < 500 && refusedBeforeAdmission.has(e.code)) {
							intent.refused = e.code;
							persist();
						}
						status.replaceChildren(errorBox(e));
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("bulk_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(() => {})
	}, t("bulk_check"));
	const another = h("button", {
		class: "secondary",
		onclick: () => {
			if (!current() || busy || refreshing || readFailed || !(terminal$4(operation) || saved.intent?.refused)) return;
			delete saved.intent;
			delete saved.preview;
			selected.clear();
			operation = null;
			persist();
			status.replaceChildren();
			renderPreview();
			update();
		}
	}, t("bulk_new"));
	const box = h("section", { "data-approvals": "" }, h("div", { class: "panel" }, h("div", { class: "filters" }, host, workspace, previewButton), h("p", { class: "muted" }, t("bulk_scope"))), rows, h("div", { class: "panel" }, h("p", { class: "note" }, t("bulk_effect")), summary, h("div", { class: "actions" }, apply, check, another), result, status));
	host.onchange = workspace.oninput = () => {
		if (!current() || busy || saved.intent) return;
		saved.host = host.value;
		saved.workspace = workspace.value;
		delete saved.preview;
		selected.clear();
		persist();
		renderPreview();
		update();
	};
	function renderPreview() {
		controls.length = 0;
		rows.replaceChildren();
		if (!saved.preview) return;
		if (saved.preview.truncated) rows.append(h("p", { class: "note" }, t("bulk_truncated")));
		if (!saved.preview.items.length) rows.append(h("p", { class: "panel" }, t("bulk_empty")));
		for (const item of saved.preview.items) {
			const choice = h("input", {
				type: "checkbox",
				"aria-label": t("bulk_select", { id: item.session_id })
			});
			const requestMode = saved.intent?.request?.params.selection.find((s) => s.item_id === item.item_id);
			choice.checked = Boolean(requestMode) || selected.has(item.item_id);
			const select = h("select", { "aria-label": t("bulk_mode", { id: item.session_id }) }, ...(item.allowed_modes || [null]).map((value) => h("option", { value: value || "" }, t(value === null ? "bulk_no_mode" : "permissions_" + value))));
			select.value = requestMode?.mode || selected.get(item.item_id) || "";
			choice.onchange = () => {
				if (!current() || saved.intent || busy) return;
				if (choice.checked) selected.set(item.item_id, select.value || null);
				else selected.delete(item.item_id);
				persist();
				update();
			};
			select.onchange = () => {
				if (!current() || saved.intent || busy) return;
				if (selected.has(item.item_id)) selected.set(item.item_id, select.value || null);
				persist();
				update();
			};
			const warning = h("p", { class: "muted" });
			controls.push({
				item,
				choice,
				select,
				warning
			});
			rows.append(h("article", {
				class: "panel bulk-item",
				"data-approval-item": item.item_id
			}, h("div", { class: "row" }, choice, h("div", { class: "grow" }, h("a", {
				class: "title",
				href: `#/session/${encodeURIComponent(item.host)}/${encodeURIComponent(item.session_id)}`
			}, item.session_id), h("div", { class: "muted" }, [item.host, item.agent_kind].filter(Boolean).join(" · ")))), item.eligible ? [
				h("p", { class: "title" }, item.prompt.toolName || t("bulk_answer")),
				h("pre", { class: "pre bulk-prompt" }, typeof item.prompt.input === "string" ? item.prompt.input : Object.keys(item.prompt.input || {}).length === 1 && typeof item.prompt.input?.command === "string" ? item.prompt.input.command : JSON.stringify(item.prompt.input ?? item.prompt, null, 2)),
				h("details", { class: "bulk-evidence" }, h("summary", {}, t("bulk_full_prompt")), h("pre", { class: "pre bulk-prompt" }, JSON.stringify(item.prompt, null, 2))),
				select,
				warning
			] : h("p", { class: "muted" }, t("bulk_blocked"), " · ", item.code || t("obs_unknown"))));
		}
	}
	function update() {
		const fixed = Boolean(saved.intent), expired = saved.preview && saved.preview.expires_at * 1e3 <= Date.now();
		host.disabled = workspace.disabled = busy || fixed;
		previewButton.disabled = busy || fixed || !observable() || !host.value;
		for (const c of controls) {
			c.choice.disabled = busy || fixed || !c.item.eligible || !writable() || expired;
			c.select.disabled = c.choice.disabled || !c.choice.checked;
			c.warning.textContent = c.select.value === "allow_all" ? t("permissions_allow_help") : "";
		}
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.textContent = t(fixed ? "permissions_retry" : "bulk_apply");
		apply.disabled = busy || readFailed || !writable() || (fixed ? !saved.intent.request || !saved.intent.key : !selected.size || expired);
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$4(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed;
		summary.textContent = fixed ? t(saved.intent.refused ? "bulk_refused" : "bulk_fixed") : expired ? t("bulk_expired") : t("bulk_selected", { count: selected.size });
		result.replaceChildren();
		if (!fixed) return;
		result.append(h("p", {}, operation ? opStatus(operation) : t("permissions_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null));
		if (!saved.intent.request || !saved.intent.key) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		if (!operation) return;
		const items = operation.result?.items || operation.external_refs?.bulk_items || [];
		result.append(h("p", { class: "muted" }, t(operation.result?.all_succeeded === true ? "bulk_all_proven" : "bulk_partial")));
		for (const item of items) result.append(h("div", { class: "row bulk-receipt" }, h("div", { class: "grow" }, item.session_id, h("div", { class: "muted" }, t(item.complete === true ? "bulk_item_complete" : "bulk_item_incomplete"))), ...["answer", "permissions"].filter((phase) => item[phase]).map((phase) => h("span", {}, t("bulk_" + phase), ": ", opId$1(item[phase].operation_id) ? h("a", { href: `#/op/${item[phase].operation_id}` }, item[phase].status || t("obs_unknown")) : item[phase].status || t("obs_unknown"), item[phase].code ? ` · ${item[phase].code}` : ""))));
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) {
			update();
			return;
		}
		refreshing = (async () => {
			const data = await api("GET", `/operations/${saved.intent.operation_id}`);
			guard();
			accept(data.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			if (current()) {
				readFailed = true;
				status.replaceChildren(errorBox(e));
				update();
			}
			throw e;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	renderPreview();
	update();
	return {
		box,
		update,
		refresh
	};
}
//#endregion
//#region src/session-start.js
var object$2 = (v) => v && typeof v === "object" && !Array.isArray(v);
var operationId = (v) => typeof v === "string" && /^op_[0-9a-f]{32}$/.test(v);
var terminal$3 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var equal$3 = (a, b) => a === b || object$2(a) && object$2(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$3(a[k], b[k]));
var text$2 = (v, max) => typeof v === "string" && v.trim().length > 0 && v.length <= max;
var fields = [
	"host",
	"workspace",
	"agent",
	"model",
	"title",
	"prompt"
];
var admissionRefusals$1 = new Set(["TIER_DISABLED", "START_WORKTREE_REQUIRED"]);
function validRequest$2(r) {
	return r?.action === "session.start" && object$2(r.target) && Object.keys(r.target).length === 2 && text$2(r.target.host, 256) && text$2(r.target.workspace, 256) && object$2(r.params) && Object.keys(r.params).every((k) => [
		"agent",
		"model",
		"title",
		"prompt",
		"use_worktree"
	].includes(k)) && ["claude", "codex"].includes(r.params.agent) && r.params.use_worktree === true && [
		"model",
		"title",
		"prompt"
	].every((k) => !(k in r.params) || text$2(r.params[k], k === "prompt" ? 2e4 : 256)) && object$2(r.preconditions) && Object.keys(r.preconditions).length === 0;
}
function sessionStartPanel({ h, t, api, caps, guard, ready, errorBox, opStatus, storageKey }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = Object.fromEntries(fields.map((k) => [k, typeof raw?.[k] === "string" ? raw[k] : k === "agent" ? "claude" : ""]));
	if (!["claude", "codex"].includes(saved.agent)) saved.agent = "claude";
	if (raw?.intent) {
		const valid = validRequest$2(raw.intent.request) && text$2(raw.intent.key, 200);
		saved.intent = {
			request: valid ? raw.intent.request : null,
			key: valid ? raw.intent.key : null,
			operation_id: operationId(raw.intent.operation_id) ? raw.intent.operation_id : null,
			refused: !raw.intent.operation_id && admissionRefusals$1.has(raw.intent.refused) ? raw.intent.refused : null
		};
		if (valid) Object.assign(saved, raw.intent.request.target, {
			model: "",
			title: "",
			prompt: ""
		}, raw.intent.request.params);
	}
	let operation = null, busy = false, submission = null, refreshing = null, readFailed = false;
	let workspaces = [], discovery = 0, discovering = false, discoveredHost = "";
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = () => {
		guard();
		localStorage.setItem(storageKey, JSON.stringify(saved));
	};
	const observe = () => caps()?.scopes?.includes("observe");
	const allowed = () => observe() && caps()?.scopes?.includes("start") && caps()?.actions?.some((a) => a.action === "session.start" && a.allowed === true);
	const hostAllowed = () => caps()?.hosts?.some((x) => x.host === saved.host && x.writes === true && x.orchestrate === true);
	const status = h("div", { role: "status" }), result = h("div", { "data-start-result": "" }), discoveryStatus = h("p", {
		class: "muted",
		role: "status"
	});
	const host = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("start_choose_host")), ...(caps()?.hosts || []).map((x) => h("option", { value: x.host }, x.host)));
	if (saved.host && ![...host.options].some((o) => o.value === saved.host)) host.append(h("option", { value: saved.host }, saved.host));
	const workspace = h("select", { "aria-label": t("start_workspace") });
	const agent = h("select", { "aria-label": t("start_agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
	const model = h("input", {
		"aria-label": t("start_model"),
		maxlength: 256,
		placeholder: t("start_model_default")
	});
	const title = h("input", {
		"aria-label": t("start_title"),
		maxlength: 256
	});
	const prompt = h("textarea", {
		"aria-label": t("start_prompt"),
		maxlength: 2e4,
		rows: 6
	});
	const inputs = {
		host,
		workspace,
		agent,
		model,
		title,
		prompt
	};
	const fill = () => {
		for (const [k, el] of Object.entries(inputs)) el.value = saved[k];
	};
	const showError = (e) => {
		if (current()) status.replaceChildren(errorBox(e));
	};
	function renderWorkspaces() {
		workspace.replaceChildren(h("option", { value: "" }, t("start_choose_workspace")), ...workspaces.map((w) => h("option", { value: w.workspace_id }, `${w.name || w.workspace_id} · ${w.workspace_id}`)));
		if (saved.workspace && ![...workspace.options].some((o) => o.value === saved.workspace)) workspace.append(h("option", { value: saved.workspace }, saved.workspace));
		workspace.value = saved.workspace;
	}
	async function discover() {
		if (!current() || saved.intent || !observe() || !saved.host) return;
		const expected = ++discovery, selectedHost = saved.host;
		discovering = true;
		discoveredHost = "";
		workspaces = [];
		renderWorkspaces();
		update();
		discoveryStatus.textContent = t("start_loading_workspaces");
		try {
			const doc = await api("GET", `/workspaces?host=${encodeURIComponent(selectedHost)}&limit=200`);
			guard();
			if (expected !== discovery || saved.host !== selectedHost || saved.intent) return;
			if (!Array.isArray(doc.workspaces) || doc.workspaces.length > 200 || typeof doc.has_more !== "boolean" || !object$2(doc.errors) || Object.keys(doc.errors).length || doc.workspaces.some((w) => !object$2(w) || w.host !== selectedHost || !text$2(w.workspace_id, 256) || typeof w.folder !== "string") || new Set(doc.workspaces.map((w) => w.workspace_id)).size !== doc.workspaces.length) throw new Error(t("start_discovery_failed"));
			workspaces = doc.workspaces;
			discoveredHost = selectedHost;
			renderWorkspaces();
			discoveryStatus.textContent = t(doc.has_more ? "start_truncated" : !workspaces.length ? "start_no_workspaces" : "start_workspace_help");
		} catch (e) {
			if (current() && expected === discovery) {
				discoveryStatus.textContent = t("start_discovery_failed");
				showError(e);
			}
		} finally {
			if (expected === discovery && current()) {
				discovering = false;
				update();
			}
		}
	}
	const reload = h("button", {
		class: "secondary",
		onclick: discover
	}, t("start_reload_workspaces"));
	const accept = (candidate) => {
		guard();
		const intent = saved.intent;
		if (!intent || !intent.request || !intent.key || !operationId(candidate?.operation_id) || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key || !equal$3({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request) || intent.operation_id && intent.operation_id !== candidate.operation_id) throw new Error(t("start_invalid_result"));
		for (const proof of [candidate.result, candidate.external_refs?.start_result]) if (proof?.started === true && (proof.host !== intent.request.target.host || !text$2(proof.session_id, 256) || proof.session_id !== candidate.external_refs?.session_id)) throw new Error(t("start_invalid_result"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		readFailed = false;
		persist();
		status.replaceChildren();
		update();
	};
	function request() {
		const params = {
			agent: saved.agent,
			use_worktree: true
		};
		for (const key of [
			"model",
			"title",
			"prompt"
		]) if (saved[key] !== "") params[key] = saved[key];
		return {
			action: "session.start",
			target: {
				host: saved.host,
				workspace: saved.workspace
			},
			params,
			preconditions: {}
		};
	}
	const apply = h("button", {
		class: "primary",
		onclick: async () => {
			if (!current() || busy || readFailed || !ready() || !allowed() || saved.intent?.operation_id || saved.intent?.refused) return;
			if (!saved.intent) {
				if (!hostAllowed() || discoveredHost !== saved.host || !workspaces.some((w) => w.workspace_id === saved.workspace) || !validRequest$2(request())) return;
				saved.intent = {
					request: request(),
					key: crypto.randomUUID(),
					operation_id: null
				};
			}
			if (!saved.intent.request || !saved.intent.key) return;
			try {
				persist();
			} catch (e) {
				showError(e);
				update();
				return;
			}
			busy = true;
			update();
			const intent = saved.intent;
			submission = (async () => {
				try {
					const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(data.operation);
				} catch (e) {
					if (current()) {
						if (e.status >= 400 && e.status < 500 && admissionRefusals$1.has(e.code)) {
							intent.refused = e.code;
							try {
								persist();
							} catch {}
						}
						showError(e);
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("start_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(() => {})
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || refreshing || readFailed || !(terminal$3(operation) || saved.intent?.refused)) return;
			const previous = saved;
			saved = {
				host: saved.host,
				workspace: "",
				agent: "claude",
				model: "",
				title: "",
				prompt: ""
			};
			try {
				persist();
			} catch (e) {
				saved = previous;
				showError(e);
				return;
			}
			operation = null;
			status.replaceChildren();
			fill();
			renderWorkspaces();
			update();
			await discover();
		}
	}, t("start_new"));
	for (const [key, el] of Object.entries(inputs)) el.addEventListener(key === "host" || key === "workspace" || key === "agent" ? "change" : "input", () => {
		if (!current() || saved.intent || busy) {
			fill();
			return;
		}
		saved[key] = el.value;
		if (key === "host") {
			saved.workspace = "";
			discoveredHost = "";
			workspaces = [];
			discovery++;
			renderWorkspaces();
		}
		try {
			persist();
		} catch (e) {
			showError(e);
		}
		update();
		if (key === "host") discover();
	});
	const label = (name, control) => h("label", {}, t(name), control);
	const box = h("section", {
		class: "session-start",
		"data-session-start": ""
	}, h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("host", host), label("start_workspace", workspace)), h("div", { class: "actions" }, reload), discoveryStatus, h("p", { class: "muted" }, t("start_isolation"))), h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("start_agent", agent), label("start_model", model), label("start_title", title)), label("start_prompt", prompt), h("p", { class: "muted" }, t("start_prompt_help"))), h("div", { class: "actions" }, apply, check, another), result, status);
	function update() {
		const fixed = Boolean(saved.intent);
		for (const el of Object.values(inputs)) el.disabled = busy || fixed;
		workspace.disabled ||= discovering || !saved.host;
		reload.hidden = fixed;
		reload.disabled = discovering || !observe() || !saved.host;
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.textContent = t(fixed ? "permissions_retry" : "start_apply");
		apply.disabled = busy || readFailed || !ready() || !allowed() || (fixed ? !saved.intent.request || !saved.intent.key : !hostAllowed() || discoveredHost !== saved.host || !workspaces.some((w) => w.workspace_id === saved.workspace) || !validRequest$2(request()));
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$3(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed;
		result.replaceChildren();
		if (!allowed()) result.append(h("p", { class: "muted" }, t("start_unavailable")));
		if (!fixed) return;
		result.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "start_refused" : "start_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null, operation?.status_reason ? ` · ${operation.status_reason}` : ""));
		result.append(h("p", { class: "muted" }, t("start_fixed")));
		if (!saved.intent.request || !saved.intent.key) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		const proof = operation?.result?.started === true ? operation.result : operation?.external_refs?.start_result;
		if (proof?.started === true) {
			result.append(h("p", {}, t("start_started"), " ", h("a", { href: `#/session/${encodeURIComponent(proof.host)}/${encodeURIComponent(proof.session_id)}` }, proof.session_id)));
			const sent = operation?.result?.prompt_sent;
			result.append(h("p", { class: "muted" }, t(!saved.intent.request?.params.prompt ? "start_without_prompt" : sent === true ? "start_prompt_accepted" : "start_prompt_unknown")));
		}
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) {
			update();
			return;
		}
		refreshing = (async () => {
			const doc = await api("GET", `/operations/${saved.intent.operation_id}`);
			guard();
			accept(doc.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			if (current()) {
				readFailed = true;
				showError(e);
				update();
			}
			throw e;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	renderWorkspaces();
	fill();
	update();
	return {
		box,
		update,
		refresh,
		init: async () => {
			if (saved.intent) await refresh();
			else await discover();
		}
	};
}
//#endregion
//#region src/session-bat.js
init_transport();
function sessionBatPanel({ h, t, guard, storageKey, session }) {
	const box = h("section", {
		class: "session-bat",
		"aria-label": t("bat_handoff")
	});
	const actions = h("div", { class: "actions" }), content = h("div", { hidden: true });
	const message = h("p", {
		class: "muted",
		role: "status"
	}), copyFallback = h("div");
	let disposed = false, busy = false, expanded = false, readable = false, overview, chosen = "", intent, receipt, restoredPreview = false, damaged = false;
	const alive = () => {
		if (disposed) return false;
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const id = (v) => typeof v === "string" && /^[0-9a-f]{32}$/.test(v);
	const profile = (v) => typeof v === "string" && /^[A-Za-z0-9_.-]{1,64}$/.test(v);
	const binding = (v) => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
	const summaryMatches = (s, value) => s?.launch_id === value.preview_id && s.dashboard === false && s.opens_bat === true && typeof s.already_running === "boolean" && typeof s.bat_may_open_local_window === "boolean" && Array.isArray(s.profiles) && s.profiles.length === 1 && s.profiles[0] === value.profile_id;
	const persist = (value) => localStorage.setItem(storageKey, JSON.stringify(value));
	try {
		const raw = localStorage.getItem(storageKey);
		if (raw) {
			const saved = JSON.parse(raw);
			if (saved?.version !== 1 || !id(saved.preview_id) || !profile(saved.profile_id) || !binding(saved.configuration_binding) || typeof saved.attempted !== "boolean" || !summaryMatches(saved.summary, saved)) throw new Error("invalid saved launch");
			intent = saved;
			chosen = saved.profile_id;
			expanded = true;
			restoredPreview = !saved.attempted;
		}
	} catch {
		damaged = true;
		expanded = true;
	}
	const terminal = () => [
		"started",
		"not_started",
		"already_running"
	].includes(receipt?.state);
	const acceptReceipt = (value) => {
		if (!value || !intent) return;
		const r = value.summary || value;
		if (r.launch_id !== intent.preview_id || r.dashboard !== false || !Array.isArray(r.profiles) || r.profiles.length !== 1 || r.profiles[0] !== intent.profile_id || ![
			"prepared",
			"uncertain",
			"started",
			"not_started",
			"already_running"
		].includes(value.state) || value.summary && !summaryMatches(value.summary, intent)) throw new Error(t("bat_wrong_receipt"));
		receipt = value;
	};
	const run = async (fn) => {
		if (!alive() || busy) return;
		busy = true;
		message.textContent = "";
		render();
		try {
			await fn();
		} catch (error) {
			if (alive()) message.textContent = `${t("bat_problem")} ${String(error)}`;
		} finally {
			busy = false;
			if (alive()) render();
		}
	};
	const readReceipt = async () => {
		if (!intent?.attempted) return;
		const value = await fleetControl({
			action: "launch_status",
			launch_id: intent.preview_id
		});
		if (alive()) {
			acceptReceipt(value);
			if (!value) message.textContent = t("bat_no_receipt");
		}
	};
	const read = async () => {
		readable = false;
		const available = await fleetAvailability();
		if (!alive()) return;
		if (!available.configured || !available.platform_supported || !available.native_controls) throw new Error(t("bat_missing"));
		const value = await fleetControl({ action: "overview" });
		if (!alive()) return;
		if (value?.control_version !== 1 || !binding(value.configuration?.binding) || !Array.isArray(value.profiles) || value.profiles.length > 1001 || value.profiles.some((p) => !profile(p.id) || typeof p.label !== "string" || !(p.connection === null || typeof p.connection === "string")) || new Set(value.profiles.map((p) => p.id)).size !== value.profiles.length || !Array.isArray(value.selection?.connections)) throw new Error(t("bat_missing"));
		overview = value;
		readable = value.configuration.valid === true && !value.pending_migration;
		await readReceipt();
	};
	const copy = async (field) => {
		if (!alive()) return;
		const value = field === "title" ? session()?.title || "" : session()?.session_id || "";
		try {
			await navigator.clipboard.writeText(value);
			if (alive()) message.textContent = t("bat_copied");
		} catch {
			if (!alive()) return;
			const input = h("textarea", {
				readonly: true,
				"aria-label": t(field === "title" ? "bat_copy_title" : "bat_copy_id")
			}, value);
			copyFallback.replaceChildren(h("p", { class: "muted" }, t("bat_copy_manually")), input);
			input.focus();
			input.select();
		}
	};
	const review = () => run(async () => {
		if (!readable || intent && (!restoredPreview || intent.attempted) || damaged || !profile(chosen)) return;
		const previous = intent?.preview_id, selected = intent?.profile_id || chosen;
		const value = await fleetControl({
			action: "preview_profile",
			profile_id: selected
		});
		if (!alive()) return;
		const next = {
			version: 1,
			profile_id: selected,
			preview_id: value?.preview_id,
			configuration_binding: value?.configuration_binding,
			summary: value?.summary,
			attempted: false
		};
		if (!id(next.preview_id) || !binding(next.configuration_binding) || next.configuration_binding !== overview.configuration.binding || !summaryMatches(next.summary, next)) throw new Error(t("bat_wrong_receipt"));
		intent = next;
		receipt = null;
		persist(intent);
		restoredPreview = false;
		if (previous && previous !== next.preview_id && alive()) await fleetControl({
			action: "discard",
			preview_id: previous
		});
	});
	const launch = () => run(async () => {
		if (!intent || damaged || restoredPreview || intent.summary.already_running || receipt) return;
		const next = {
			...intent,
			attempted: true
		};
		persist(next);
		intent = next;
		guard();
		const value = await fleetControl({
			action: "launch",
			preview_id: intent.preview_id
		});
		if (alive()) acceptReceipt(value);
	});
	const reset = () => run(async () => {
		if (!intent || intent.attempted && !terminal()) return;
		localStorage.removeItem(storageKey);
		const old = intent.preview_id;
		intent = receipt = null;
		restoredPreview = false;
		chosen = "";
		await fleetControl({
			action: "discard",
			preview_id: old
		});
	});
	const render = () => {
		if (!alive()) return;
		const button = (key, fn, disabled = false) => h("button", {
			class: "secondary",
			disabled: busy || disabled,
			onclick: fn
		}, t(key));
		actions.replaceChildren(button("bat_copy_title", () => copy("title"), !session()?.title), button("bat_copy_id", () => copy("id"), !session()?.session_id), button("bat_open", () => {
			expanded = true;
			run(read);
		}, !nativeDesktop));
		content.hidden = !expanded;
		if (!expanded) return;
		const fixed = !!intent || damaged;
		const picker = h("select", {
			"aria-label": t("bat_profile"),
			disabled: busy || fixed || !readable,
			onchange: (e) => {
				chosen = e.target.value;
				render();
			}
		}, h("option", {
			value: "",
			selected: !chosen
		}, t("bat_choose")), ...(overview?.profiles || []).map((p) => h("option", {
			value: p.id,
			selected: chosen === p.id
		}, `${p.label} · ${p.id}`)));
		const lines = [h("p", { class: "muted" }, t("bat_search_help")), h("label", {}, t("bat_profile"), " ", picker)];
		if (intent) {
			lines.push(h("p", { class: "note" }, t("bat_chosen", { profile: intent.profile_id }), " · ", h("code", {}, intent.preview_id)), h("p", { class: "muted" }, receipt ? t("fleet_launch_" + (receipt.state === "prepared" ? "uncertain" : receipt.state)) : restoredPreview ? t("bat_preview_expired") : intent.summary.already_running ? t("fleet_launch_already_running") : t(intent.attempted ? "bat_unknown" : "bat_reviewed")));
			if (intent.summary.bat_may_open_local_window) lines.push(h("p", { class: "muted" }, t("fleet_local_anchor")));
		}
		if (damaged) lines.push(h("p", { class: "error" }, t("bat_saved_invalid")));
		const buttons = [button("bat_read", () => run(read))];
		if (!fixed) buttons.unshift(button("bat_review", review, !readable || !chosen));
		if (restoredPreview) buttons.unshift(button("bat_review_again", review, !readable));
		if (intent && !restoredPreview && !receipt && !intent.summary.already_running) buttons.unshift(button(intent.attempted ? "bat_retry" : "bat_launch", launch, !readable));
		if (intent && (!intent.attempted || terminal())) buttons.push(button(intent.attempted ? "bat_new" : "cancel", reset));
		lines.push(h("div", { class: "actions" }, ...buttons), h("p", { class: "muted" }, t("bat_preferences"), " ", h("a", { href: "#/settings" }, t("nav_settings"))));
		content.replaceChildren(...lines);
	};
	box.append(actions);
	if (!nativeDesktop) box.append(h("p", { class: "muted" }, t("bat_browser")));
	box.append(content, copyFallback, message);
	render();
	if (nativeDesktop && expanded) queueMicrotask(() => run(read));
	return {
		box,
		update: render,
		dispose: () => {
			disposed = true;
		}
	};
}
//#endregion
//#region src/orchestration.js
var object$1 = (v) => v && typeof v === "object" && !Array.isArray(v);
var text$1 = (v, max = 256) => typeof v === "string" && v.trim().length > 0 && v.length <= max;
var opId = (v) => typeof v === "string" && /^op_[0-9a-f]{32}$/.test(v);
var equal$2 = (a, b) => a === b || Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => equal$2(v, b[i])) || object$1(a) && object$1(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$2(a[k], b[k]));
var terminal$2 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var orchestrationActions = {
	relay: "session.relay",
	planner: "fanout.plan",
	items: "fanout.start",
	failover: "session.failover"
};
var scopes = (mode) => mode === "relay" ? ["observe", "operate"] : mode === "failover" ? [
	"observe",
	"start",
	"operate"
] : ["observe", "start"];
var sessionMode = (mode) => ["relay", "failover"].includes(mode);
var managed = (row) => row?.api_access === "managed" && row.provenance === "connector_managed" && row.stale === false && row.scope_status === "current" && ["claude", "codex"].includes(row.agent_kind);
var failoverSource = (row) => managed(row) && row.agent_kind === "claude" && row.streaming === false && !row.task_id && Array.isArray(row.relations) && row.relations.length === 0;
var admissionRefusals = new Set([
	"TIER_DISABLED",
	"START_WORKTREE_REQUIRED",
	"FANOUT_CAP"
]);
var withinBodyLimit = (r) => new TextEncoder().encode(JSON.stringify(r)).length <= 2e5;
function validRequest$1(r, mode) {
	if (!object$1(r) || r.action !== orchestrationActions[mode] || !object$1(r.target) || !object$1(r.params) || !object$1(r.preconditions) || Object.keys(r.preconditions).length || Object.keys(r.target).length !== 2 || !text$1(r.target.host) || !text$1(r.target[sessionMode(mode) ? "session_id" : "workspace"]) || !withinBodyLimit(r)) return false;
	const p = r.params, keys = Object.keys(p);
	if (mode === "relay") return keys.length === 3 && text$1(p.message, 12e3) && typeof p.queue === "boolean" && p.start_if_missing === false;
	if (mode === "planner") return keys.length === 2 && text$1(p.message, 12e3) && Number.isInteger(p.max_items) && p.max_items >= 1 && p.max_items <= 16;
	if (mode === "failover") return keys.every((k) => ["tail_messages", "instructions"].includes(k)) && p.tail_messages === 12 && (!("instructions" in p) || text$1(p.instructions, 4e3));
	return keys.length === 2 && ["claude", "codex"].includes(p.agent) && Array.isArray(p.plan) && p.plan.length >= 1 && p.plan.length <= 16 && p.plan.every((v, i) => object$1(v) && Object.keys(v).length === 3 && v.index === i + 1 && text$1(v.title, 200) && text$1(v.prompt, 19e3));
}
function orchestrationPanel({ h, t, api, caps, guard, ready, errorBox, opStatus, storageKey, mode, context = {} }) {
	if (!Object.hasOwn(orchestrationActions, mode)) throw new Error("Unknown orchestration form");
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = {
		host: typeof raw?.host === "string" ? raw.host : context.host || "",
		selection: typeof raw?.selection === "string" ? raw.selection : context.session_id || "",
		message: typeof raw?.message === "string" ? raw.message : "",
		queue: raw?.queue === true,
		agent: raw?.agent === "claude" ? "claude" : "codex",
		max_items: Number.isInteger(raw?.max_items) ? raw.max_items : 3,
		items: Array.isArray(raw?.items) && raw.items.length >= 1 && raw.items.length <= 16 ? raw.items.map((v) => ({
			title: typeof v?.title === "string" ? v.title : "",
			prompt: typeof v?.prompt === "string" ? v.prompt : ""
		})) : [{
			title: "",
			prompt: ""
		}]
	};
	if (raw?.intent) {
		const valid = validRequest$1(raw.intent.request, mode) && text$1(raw.intent.key, 200);
		saved.intent = {
			request: valid ? raw.intent.request : null,
			key: valid ? raw.intent.key : null,
			operation_id: opId(raw.intent.operation_id) ? raw.intent.operation_id : null,
			refused: !raw.intent.operation_id && admissionRefusals.has(raw.intent.refused) ? raw.intent.refused : null
		};
		if (valid) {
			const r = raw.intent.request;
			Object.assign(saved, {
				host: r.target.host,
				selection: r.target.session_id || r.target.workspace,
				message: r.params.message || r.params.instructions || "",
				queue: r.params.queue === true,
				max_items: r.params.max_items || 3,
				agent: r.params.agent || "codex",
				items: r.params.plan || saved.items
			});
		}
	}
	let operation = null, busy = false, submission = null, refreshing = null, readFailed = false, rows = [], selected = null;
	let discovering = false, discovery = 0, discoveredHost = "", reviewed = false;
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = () => {
		guard();
		localStorage.setItem(storageKey, JSON.stringify(saved));
	};
	const allowed = () => scopes(mode).every((s) => caps()?.scopes?.includes(s)) && caps()?.actions?.some((a) => a.action === orchestrationActions[mode] && a.allowed === true);
	const hostAllowed = () => caps()?.hosts?.some((row) => row.host === saved.host && row.writes === true && (mode === "relay" || row.orchestrate === true));
	const proofOf = (op) => op?.result || op?.external_refs?.[mode === "relay" ? "relay_result" : mode === "failover" ? "failover_result" : "fanout_result"] || {};
	const childrenOf = (op) => {
		const rows = op?.external_refs?.fanout_result?.started ?? proofOf(op).started;
		return Array.isArray(rows) ? rows : [];
	};
	const mayReplace = () => {
		if (!terminal$2(operation)) return false;
		const statuses = [proofOf(operation).child_operation_status, ...childrenOf(operation).map((row) => row.operation_status)].filter(Boolean);
		return !(operation.steps || []).some((step) => ["started", "uncertain"].includes(step.status)) && statuses.every((status) => [
			"succeeded",
			"failed",
			"cancelled"
		].includes(status));
	};
	const selectedAllowed = () => discoveredHost === saved.host && (sessionMode(mode) ? selected?.host === saved.host && selected.session_id === saved.selection && (mode === "failover" ? failoverSource(selected) : managed(selected)) : rows.some((row) => row.workspace_id === saved.selection));
	const status = h("div", { role: "status" }), result = h("div", { "data-orchestration-result": "" }), discoveryStatus = h("p", {
		class: "muted",
		role: "status"
	}), identity = h("p", { class: "muted" });
	const host = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("start_choose_host")), ...(caps()?.hosts || []).map((row) => h("option", { value: row.host }, row.host)));
	if (saved.host && ![...host.options].some((o) => o.value === saved.host)) host.append(h("option", { value: saved.host }, saved.host));
	const selection = h("select", { "aria-label": t(sessionMode(mode) ? "orch_session" : "start_workspace") });
	const message = h("textarea", {
		"aria-label": t(mode === "failover" ? "orch_instructions" : "orch_message"),
		rows: 5,
		maxlength: mode === "failover" ? 4e3 : 12e3
	});
	const queue = h("input", { type: "checkbox" }), agent = h("select", { "aria-label": t("start_agent") }, h("option", { value: "codex" }, "Codex"), h("option", { value: "claude" }, "Claude"));
	const maximum = h("input", {
		type: "number",
		min: 1,
		max: 16,
		"aria-label": t("orch_max_items")
	});
	const review = h("input", { type: "checkbox" }), items = h("div", { "data-orchestration-items": "" });
	const label = (key, input) => h("label", {}, t(key), input);
	const inputs = {
		host,
		selection,
		message,
		queue,
		agent,
		maximum
	};
	function fill() {
		host.value = saved.host;
		selection.value = saved.selection;
		message.value = saved.message;
		queue.checked = saved.queue;
		agent.value = saved.agent;
		maximum.value = saved.max_items;
	}
	const showError = (error) => {
		if (current()) status.replaceChildren(errorBox(error));
	};
	function renderSelection() {
		const id = (row) => sessionMode(mode) ? row.session_id : row.workspace_id;
		selection.replaceChildren(h("option", { value: "" }, t(sessionMode(mode) ? "orch_choose_session" : "start_choose_workspace")), ...rows.map((row) => h("option", { value: id(row) }, (row.title || row.name) && (row.title || row.name) !== id(row) ? `${row.title || row.name} · ${id(row)}` : id(row))));
		if (saved.selection && ![...selection.options].some((o) => o.value === saved.selection)) selection.append(h("option", { value: saved.selection }, saved.selection));
		selection.value = saved.selection;
	}
	async function readSelected(serial = discovery) {
		selected = null;
		if (!sessionMode(mode) || !saved.selection || saved.intent) return;
		const fixed = {
			host: saved.host,
			session_id: saved.selection
		};
		const doc = await api("GET", `/sessions/${encodeURIComponent(fixed.host)}/${encodeURIComponent(fixed.session_id)}`);
		guard();
		if (serial !== discovery || saved.intent || saved.host !== fixed.host || saved.selection !== fixed.session_id) return;
		if (doc?.session?.host !== fixed.host || doc.session.session_id !== fixed.session_id || !Array.isArray(doc.relations_summary)) throw new Error(t("orch_discovery_failed"));
		selected = {
			...doc.session,
			relations: doc.relations_summary
		};
	}
	async function discover() {
		if (!current() || saved.intent || !caps()?.scopes?.includes("observe") || !saved.host) return;
		const mine = ++discovery, expectedHost = saved.host;
		discovering = true;
		selected = null;
		discoveredHost = "";
		rows = [];
		renderSelection();
		update();
		discoveryStatus.textContent = t("orch_loading");
		try {
			const doc = await api("GET", sessionMode(mode) ? `/sessions?host=${encodeURIComponent(expectedHost)}&access=managed&provenance=connector_managed&limit=200` : `/workspaces?host=${encodeURIComponent(expectedHost)}&limit=200`);
			guard();
			if (mine !== discovery || expectedHost !== saved.host || saved.intent) return;
			const list = doc[sessionMode(mode) ? "sessions" : "workspaces"], id = sessionMode(mode) ? "session_id" : "workspace_id";
			if (!Array.isArray(list) || list.length > 200 || list.some((row) => row?.host !== expectedHost || !text$1(row?.[id])) || new Set(list.map((row) => row[id])).size !== list.length || !sessionMode(mode) && (!object$1(doc.errors) || Object.keys(doc.errors).length || typeof doc.has_more !== "boolean") || sessionMode(mode) && doc.next_cursor !== null && !text$1(doc.next_cursor, 8192)) throw new Error(t("orch_discovery_failed"));
			rows = sessionMode(mode) ? list.filter((row) => mode === "failover" ? failoverSource(row) : managed(row)) : list;
			discoveredHost = expectedHost;
			renderSelection();
			await readSelected(mine);
			guard();
			if (mine === discovery) readFailed = false;
			if (mine === discovery) discoveryStatus.textContent = t(doc.next_cursor || doc.has_more ? "orch_truncated" : rows.length ? "orch_selection_help" : "orch_empty");
		} catch (error) {
			if (current() && mine === discovery) {
				discoveredHost = "";
				selected = null;
				discoveryStatus.textContent = t("orch_discovery_failed");
				showError(error);
			}
			throw error;
		} finally {
			if (current() && mine === discovery) {
				discovering = false;
				update();
			}
		}
	}
	const reload = h("button", {
		class: "secondary",
		onclick: () => discover().catch(() => {})
	}, t("orch_reload"));
	const changed = () => {
		reviewed = false;
		review.checked = false;
		try {
			persist();
		} catch (e) {
			showError(e);
		}
		update();
	};
	for (const [key, input] of Object.entries(inputs)) input.addEventListener([
		"host",
		"selection",
		"queue",
		"agent"
	].includes(key) ? "change" : "input", () => {
		if (!current() || busy || saved.intent) {
			fill();
			return;
		}
		if (key === "maximum") saved.max_items = Number(input.value);
		else saved[key] = key === "queue" ? input.checked : input.value;
		if (key === "host") {
			saved.selection = "";
			selected = null;
			discovering = false;
			rows = [];
			discoveredHost = "";
			++discovery;
			renderSelection();
		}
		changed();
		if (key === "host") discover().catch(() => {});
		if (key === "selection") {
			const mine = ++discovery;
			discovering = true;
			selected = null;
			update();
			readSelected(mine).catch((error) => {
				if (current() && mine === discovery) showError(error);
			}).finally(() => {
				if (current() && mine === discovery) {
					discovering = false;
					update();
				}
			});
		}
	});
	function renderItems() {
		items.replaceChildren(...saved.items.map((item, index) => {
			const title = h("input", {
				"aria-label": t("orch_item_title", { n: index + 1 }),
				maxlength: 200
			}), prompt = h("textarea", {
				"aria-label": t("orch_item_prompt", { n: index + 1 }),
				rows: 4,
				maxlength: 19e3
			});
			title.value = item.title;
			prompt.value = item.prompt;
			for (const [key, el] of [["title", title], ["prompt", prompt]]) el.addEventListener("input", () => {
				if (!current() || saved.intent || busy) {
					el.value = item[key];
					return;
				}
				item[key] = el.value;
				changed();
			});
			const remove = h("button", {
				class: "secondary",
				onclick: () => {
					if (!current() || saved.intent || busy || saved.items.length < 2) return;
					saved.items.splice(index, 1);
					renderItems();
					changed();
				}
			}, t("orch_remove_item", { n: index + 1 }));
			return h("section", { class: "orch-item" }, h("h2", {}, t("orch_item", { n: index + 1 })), label("orch_title_label", title), label("orch_prompt_label", prompt), h("div", { class: "actions" }, remove));
		}));
	}
	const add = h("button", {
		class: "secondary",
		onclick: () => {
			if (!current() || saved.intent || busy || saved.items.length >= 16) return;
			saved.items.push({
				title: "",
				prompt: ""
			});
			renderItems();
			changed();
		}
	}, t("orch_add_item"));
	review.addEventListener("change", () => {
		reviewed = review.checked;
		update();
	});
	function request() {
		const target = {
			host: saved.host,
			[sessionMode(mode) ? "session_id" : "workspace"]: saved.selection
		};
		const params = mode === "relay" ? {
			message: saved.message,
			queue: saved.queue,
			start_if_missing: false
		} : mode === "planner" ? {
			message: saved.message,
			max_items: saved.max_items
		} : mode === "items" ? {
			agent: saved.agent,
			plan: saved.items.map((item, i) => ({
				index: i + 1,
				title: item.title,
				prompt: item.prompt
			}))
		} : {
			tail_messages: 12,
			...saved.message !== "" ? { instructions: saved.message } : {}
		};
		return {
			action: orchestrationActions[mode],
			target,
			params,
			preconditions: {}
		};
	}
	function accept(candidate) {
		guard();
		const intent = saved.intent;
		if (!intent?.request || !intent.key || !opId(candidate?.operation_id) || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key || !equal$2({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request) || intent.operation_id && intent.operation_id !== candidate.operation_id) throw new Error(t("orch_invalid_result"));
		const proof = proofOf(candidate);
		if (!object$1(proof) || proof.host !== void 0 && proof.host !== intent.request.target.host || mode === "relay" && proof.session_id !== void 0 && proof.session_id !== intent.request.target.session_id || mode === "failover" && proof.old_session_id !== void 0 && proof.old_session_id !== intent.request.target.session_id || proof.started !== void 0 && !(mode === "planner" && proof.started === true) && (!Array.isArray(proof.started) || proof.started.length > 16 || proof.started.some((row) => !object$1(row))) || !Array.isArray(candidate.steps)) throw new Error(t("orch_invalid_result"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		readFailed = false;
		persist();
		status.replaceChildren();
		update();
	}
	const apply = h("button", {
		class: "primary",
		onclick: async () => {
			if (!current() || busy || readFailed || !ready() || !allowed() || saved.intent?.operation_id || saved.intent?.refused) return;
			if (!saved.intent) {
				if (discovering || !hostAllowed() || !selectedAllowed() || !validRequest$1(request(), mode) || !reviewed) return;
				saved.intent = {
					request: request(),
					key: crypto.randomUUID(),
					operation_id: null
				};
			}
			if (!saved.intent.request || !saved.intent.key) return;
			try {
				persist();
			} catch (e) {
				showError(e);
				update();
				return;
			}
			busy = true;
			update();
			const intent = saved.intent;
			submission = (async () => {
				try {
					const doc = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(doc.operation);
				} catch (error) {
					if (current()) {
						if (error.status >= 400 && error.status < 500 && admissionRefusals.has(error.code)) {
							intent.refused = error.code;
							try {
								persist();
							} catch {}
						}
						showError(error);
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("orch_apply_" + mode));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(() => {})
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || busy || refreshing || readFailed || !(mayReplace() || saved.intent?.refused)) return;
			const previous = saved;
			saved = {
				...saved,
				message: "",
				queue: false,
				items: [{
					title: "",
					prompt: ""
				}]
			};
			delete saved.intent;
			try {
				persist();
			} catch (error) {
				saved = previous;
				showError(error);
				return;
			}
			operation = null;
			reviewed = false;
			review.checked = false;
			status.replaceChildren();
			fill();
			renderItems();
			update();
			await discover().catch(() => {});
		}
	}, t("orch_new"));
	const editor = mode === "items" ? h("div", { class: "panel" }, label("start_agent", agent), items, h("div", { class: "actions" }, add)) : h("div", { class: "panel" }, label(mode === "failover" ? "orch_instructions" : "orch_message", message), ...mode === "relay" ? [h("label", { class: "orch-check" }, queue, " ", t("queue_behind"))] : [], ...mode === "planner" ? [label("orch_max_items", maximum)] : []);
	const reviewLine = h("label", { class: "orch-check" }, review, " ", t("orch_review_" + mode));
	const box = h("section", {
		class: "orchestration",
		"data-orchestration": mode
	}, h("p", { class: "muted" }, t("orch_help_" + mode)), h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("host", host), label(sessionMode(mode) ? "orch_session" : "start_workspace", selection)), h("div", { class: "actions" }, reload), discoveryStatus, identity), editor, h("p", { class: "muted" }, t("orch_preparation")), reviewLine, h("div", { class: "actions" }, apply, check, another), result, status);
	function renderResult() {
		result.replaceChildren();
		if (!saved.intent && !withinBodyLimit(request())) result.append(h("p", { class: "error" }, t("orch_body_limit")));
		if (!allowed()) result.append(h("p", { class: "muted" }, t("orch_unavailable", { scopes: scopes(mode).join(" + ") })));
		if (!saved.intent) return;
		const intent = saved.intent;
		result.append(h("p", {}, operation ? operation.status === "waiting_external" ? t("orch_waiting_children") : opStatus(operation) : t(intent.refused ? "start_refused" : "start_unknown"), " ", ...intent.operation_id ? [h("a", { href: `#/op/${intent.operation_id}` }, t("permissions_details"))] : [], operation?.status_reason ? ` · ${operation.status_reason}` : ""));
		result.append(h("p", { class: "muted" }, t("orch_fixed")));
		if (!intent.request || !intent.key) result.append(h("p", { class: "error" }, t("permissions_damaged")));
		if (!operation) return;
		const proof = proofOf(operation);
		if (operation.status !== "succeeded") result.append(h("p", { class: "note" }, t("orch_partial")));
		const links = new Map();
		if (opId(proof.child_operation_id)) links.set(proof.child_operation_id, t("orch_child"));
		for (const row of childrenOf(operation)) if (opId(row.operation_id)) links.set(row.operation_id, `${row.task}. ${row.title} · ${row.operation_status}`);
		for (const step of operation.steps || []) if (opId(step.response?.operation_id)) links.set(step.response.operation_id, links.get(step.response.operation_id) || step.name);
		if (links.size) result.append(h("h2", {}, t("orch_receipts")), h("ul", {}, ...[...links].map(([id, label]) => h("li", {}, h("a", { href: `#/op/${id}` }, label)))));
		if (mode === "items") result.append(h("p", { class: "muted" }, t("orch_item_progress", {
			count: childrenOf(operation).filter((row) => row.prompt_sent === true).length,
			total: intent.request?.params.plan.length || 0
		})));
		if (mode === "relay" && proof.sent === true) result.append(h("p", {}, t("orch_relay_accepted")));
		if (mode === "planner" && proof.prompt_sent === true && text$1(proof.session_id)) result.append(h("p", {}, t("orch_planner_started"), " ", h("a", { href: `#/session/${encodeURIComponent(intent.request.target.host)}/${encodeURIComponent(proof.session_id)}` }, proof.session_id)));
		if (mode === "failover") {
			const sid = proof.new_session_id || proof.pending_successor;
			if (text$1(sid)) result.append(h("p", {}, t(proof.prompt_sent === true ? "orch_handoff_accepted" : "orch_successor_unconfirmed"), " ", h("a", { href: `#/session/${encodeURIComponent(intent.request.target.host)}/${encodeURIComponent(sid)}` }, sid)));
		}
		if (operation.steps?.length) result.append(h("details", {}, h("summary", {}, t("orch_steps")), h("ul", {}, ...operation.steps.map((step) => h("li", {}, `${step.name} · ${step.status}`)))));
	}
	function update() {
		const fixed = Boolean(saved.intent);
		for (const el of Object.values(inputs)) el.disabled = busy || fixed;
		selection.disabled ||= discovering || !saved.host;
		for (const el of items.querySelectorAll("input,textarea,button")) el.disabled = busy || fixed || el.tagName === "BUTTON" && saved.items.length === 1;
		add.disabled = busy || fixed || saved.items.length >= 16;
		add.hidden = fixed;
		reload.hidden = fixed;
		reload.disabled = discovering || !saved.host || !caps()?.scopes?.includes("observe");
		review.disabled = fixed || busy;
		reviewLine.hidden = fixed;
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.textContent = t(fixed ? "permissions_retry" : "orch_apply_" + mode);
		apply.disabled = busy || readFailed || !ready() || !allowed() || (fixed ? !saved.intent.request || !saved.intent.key : discovering || !reviewed || !hostAllowed() || !selectedAllowed() || !validRequest$1(request(), mode));
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(mayReplace() || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed;
		identity.replaceChildren();
		identity.hidden = !saved.selection;
		if (saved.selection) identity.append(t(sessionMode(mode) ? "sessions_id" : "sessions_workspace_id"), ": ", h("code", {}, saved.selection));
		renderResult();
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		refreshing = (async () => {
			if (saved.intent?.operation_id) {
				const doc = await api("GET", `/operations/${saved.intent.operation_id}`);
				guard();
				accept(doc.operation);
			} else if (!saved.intent) await discover();
			else update();
		})();
		update();
		try {
			await refreshing;
		} catch (error) {
			if (current()) {
				readFailed = true;
				showError(error);
				update();
			}
			throw error;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	renderSelection();
	renderItems();
	fill();
	update();
	return {
		box,
		update,
		refresh,
		init: refresh
	};
}
//#endregion
//#region src/repository-start.js
var object = (v) => v && typeof v === "object" && !Array.isArray(v);
var equal$1 = (a, b) => a === b || Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => equal$1(v, b[i])) || object(a) && object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => equal$1(a[k], b[k]));
var text = (v, max) => typeof v === "string" && v.trim().length > 0 && v.length <= max && !/[\x00-\x1f\x7f]/.test(v);
var oid$1 = (v) => typeof v === "string" && /^op_[0-9a-f]{32}$/.test(v);
var sha = (v) => typeof v === "string" && /^[0-9a-f]{40}$/.test(v);
var digest$1 = (v) => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
var terminal$1 = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var target = (v) => object(v) && Object.keys(v).length === 3 && [
	"repository",
	"host",
	"workspace_id"
].every((k) => text(v[k], 256));
var ref = (v) => typeof v === "string" && /^refs\/heads\/(?!-)(?!.*\.\.)(?!.*\/\/)(?!.*@\{)[A-Za-z0-9._/-]{1,200}$/.test(v) && !/[./]$/.test(v) && v.slice(11).split("/").every((p) => !p.startsWith(".") && !p.endsWith(".lock"));
var branchRef = (value) => value.startsWith("refs/") ? value : "refs/heads/" + value;
var preconditions = (v) => object(v) && Object.keys(v).length === 2 && Number.isSafeInteger(v.repository_id) && v.repository_id > 0 && digest$1(v.binding_digest);
var projectId = (v) => typeof v === "string" && /^prj_[0-9a-f]{20}$/.test(v);
var artifactRefs = (v) => Array.isArray(v) && v.every((r) => object(r) && Object.keys(r).length === 3 && /^art_[0-9a-f]{32}$/.test(r.artifact_id) && Number.isSafeInteger(r.revision) && r.revision > 0 && digest$1(r.digest));
var requestPreconditions = (r) => object(r.params) && "project_id" in r.params ? projectId(r.params.project_id) && object(r.preconditions) && Number.isSafeInteger(r.preconditions.expected_project_version) && r.preconditions.expected_project_version > 0 && preconditions(Object.fromEntries(Object.entries(r.preconditions).filter(([k]) => k !== "expected_project_version"))) : preconditions(r.preconditions);
var validRequest = (r) => r?.action === "repository.continue" && target(r.target) && requestPreconditions(r) && object(r.params) && Object.keys(r.params).every((k) => [
	"agent",
	"prompt",
	"title",
	"model",
	"artifacts",
	"project_id",
	"source_ref",
	"source_sha"
].includes(k)) && ref(r.params.source_ref) && sha(r.params.source_sha) && ["claude", "codex"].includes(r.params.agent) && typeof r.params.prompt === "string" && r.params.prompt.trim() && r.params.prompt.length <= 12e3 && ["title", "model"].every((k) => !(k in r.params) || text(r.params[k], 256)) && (!("artifacts" in r.params) || artifactRefs(r.params.artifacts));
var validPreview$1 = (p, input) => object(p) && equal$1(p.target, input.target) && p.source_ref === input.source_ref && sha(p.source_sha) && p.exact_ref_head_only === true && preconditions(p.preconditions) && p.repository_id === p.preconditions.repository_id && p.binding_digest === p.preconditions.binding_digest && object(p.workspace) && p.workspace.workspace_id === input.target.workspace_id && text(p.workspace.folder, 4096) && (p.workspace.name == null || typeof p.workspace.name === "string");
var noAdmission = new Set(["REPOSITORY_NOT_BOUND", "REPOSITORY_HOST_UNAVAILABLE"]);
function repositoryStartPanel({ h, t, api, caps, guard, ready, errorBox, opStatus, storageKey, project = null, attachmentFactory }) {
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = {
		target: target(raw?.target) ? raw.target : null,
		source_ref: typeof raw?.source_ref === "string" ? raw.source_ref : "",
		agent: ["claude", "codex"].includes(raw?.agent) ? raw.agent : "claude",
		prompt: typeof raw?.prompt === "string" ? raw.prompt : "",
		model: typeof raw?.model === "string" ? raw.model : "",
		title: typeof raw?.title === "string" ? raw.title : ""
	};
	if (raw?.intent) {
		const valid = validRequest(raw.intent.request) && text(raw.intent.key, 200) && (!project || raw.intent.request.params.project_id === project);
		saved.intent = {
			request: valid ? raw.intent.request : null,
			key: valid ? raw.intent.key : null,
			operation_id: oid$1(raw.intent.operation_id) ? raw.intent.operation_id : null,
			refused: !raw.intent.operation_id && noAdmission.has(raw.intent.refused) ? raw.intent.refused : null
		};
		if (valid) Object.assign(saved, {
			target: raw.intent.request.target,
			title: "",
			model: ""
		}, raw.intent.request.params);
	}
	let preview = null, operation = null, busy = false, reading = false, sequence = 0, readFailed = false, submission = null, refreshing = null;
	let projectDoc = null, projectFailed = Boolean(project), previewProjectVersion = null, autoSelect = !raw, projectQueue = Promise.resolve();
	const current = () => {
		try {
			guard();
			return true;
		} catch {
			return false;
		}
	};
	const persist = () => {
		guard();
		localStorage.setItem(storageKey, JSON.stringify(saved));
	};
	const observe = () => caps()?.scopes?.includes("observe");
	const allowed = () => observe() && caps()?.scopes?.includes("start") && caps()?.actions?.some((a) => a.action === "repository.continue" && a.allowed === true);
	const expanded = () => caps()?.features?.project_dispatch?.version === 1;
	const projectReady = () => !project || expanded() && projectDoc && !projectDoc.archived && !projectFailed;
	const bindings = () => (caps()?.features?.repository_sync || []).filter((b) => b.exact_ref_head_only === true && target({
		repository: b.repository,
		host: b.host,
		workspace_id: b.workspace_id
	}) && (!project || projectDoc?.repositories?.some((r) => r.toLowerCase() === b.repository.toLowerCase())));
	const bound = () => bindings().some((b) => equal$1({
		repository: b.repository,
		host: b.host,
		workspace_id: b.workspace_id
	}, saved.target));
	const hostAllowed = () => caps()?.hosts?.some((h) => h.host === saved.target?.host && h.writes === true && h.orchestrate === true);
	const status = h("div", { role: "status" }), facts = h("div", { "data-published-preview": "" }), outcome = h("div", { "data-published-result": "" });
	const projectStatus = h("div", {
		role: "status",
		"data-dispatch-project": ""
	});
	const binding = h("select", { "aria-label": t("pub_binding") }), sourceRef = h("input", {
		"aria-label": t("pub_ref"),
		maxlength: 211,
		placeholder: "main"
	});
	const branchHelp = h("p", {
		class: "muted",
		"aria-live": "polite"
	});
	const agent = h("select", { "aria-label": t("start_agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
	const prompt = h("textarea", {
		"aria-label": t("pub_prompt"),
		maxlength: 12e3,
		rows: 5
	}), title = h("input", {
		"aria-label": t("start_title"),
		maxlength: 256
	});
	const model = h("input", {
		"aria-label": t("start_model"),
		maxlength: 256,
		placeholder: t("start_model_default")
	});
	const inputs = {
		source_ref: sourceRef,
		agent,
		prompt,
		title,
		model
	};
	prompt.value = saved.prompt;
	const attachments = expanded() && attachmentFactory ? attachmentFactory(prompt, () => {
		if (current()) update();
	}) : null;
	if (attachments && !saved.intent) saved.prompt = prompt.value;
	const attachmentBox = attachments ? h("fieldset", { class: "dispatch-attachments" }, attachments.box) : null;
	const key = (b) => JSON.stringify(b);
	function fill() {
		binding.replaceChildren(h("option", { value: "" }, t("pub_choose")), ...bindings().map((b) => {
			const value = {
				repository: b.repository,
				host: b.host,
				workspace_id: b.workspace_id
			};
			return h("option", { value: key(value) }, `${b.repository} · ${b.host} · ${b.workspace_id}`);
		}));
		if (saved.target && ![...binding.options].some((o) => o.value === key(saved.target))) binding.append(h("option", { value: key(saved.target) }, Object.values(saved.target).join(" · ")));
		binding.value = saved.target ? key(saved.target) : "";
		for (const [k, el] of Object.entries(inputs)) el.value = saved[k];
	}
	const showError = (e) => {
		if (current()) status.replaceChildren(errorBox(e));
	};
	const selected = () => ({
		target: saved.target,
		source_ref: branchRef(saved.source_ref)
	});
	const request = () => ({
		action: "repository.continue",
		target: saved.target,
		params: {
			source_ref: preview?.source_ref,
			source_sha: preview?.source_sha,
			agent: saved.agent,
			prompt: saved.prompt,
			...saved.title ? { title: saved.title } : {},
			...saved.model && expanded() ? { model: saved.model } : {},
			...attachments?.refs().length ? { artifacts: attachments.refs() } : {},
			...project ? { project_id: project } : {}
		},
		preconditions: preview ? {
			...preview.preconditions,
			...project ? { expected_project_version: previewProjectVersion } : {}
		} : null
	});
	const inspect = h("button", {
		class: "secondary",
		onclick: async () => {
			if (!current() || saved.intent || reading || !observe() || !ready() || !projectReady() || !bound() || !ref(selected().source_ref)) return;
			const expected = ++sequence, input = selected(), projectVersion = projectDoc?.version;
			preview = null;
			reading = true;
			update();
			status.replaceChildren();
			try {
				const doc = await api("POST", "/repository-previews", {
					...input.target,
					source_ref: input.source_ref
				});
				guard();
				if (expected !== sequence || saved.intent || !equal$1(input, selected())) return;
				if (!validPreview$1(doc.preview, input)) throw new Error(t("pub_invalid_preview"));
				preview = doc.preview;
				previewProjectVersion = projectVersion;
			} catch (e) {
				if (expected === sequence) showError(e);
			} finally {
				if (expected === sequence && current()) {
					reading = false;
					update();
				}
			}
		}
	}, t("pub_preview"));
	function accept(candidate) {
		guard();
		const intent = saved.intent;
		if (!intent?.request || !intent.key || !oid$1(candidate?.operation_id) || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key || !equal$1({
			action: candidate.action,
			target: candidate.target,
			params: candidate.params,
			preconditions: candidate.preconditions
		}, intent.request) || intent.operation_id && candidate.operation_id !== intent.operation_id) throw new Error(t("pub_invalid_result"));
		const result = candidate.result, refs = candidate.external_refs || {};
		for (const [name, value] of Object.entries({
			host: intent.request.target.host,
			repository: intent.request.target.repository,
			repository_id: intent.request.preconditions.repository_id,
			source_ref: intent.request.params.source_ref,
			source_sha: intent.request.params.source_sha,
			repository_binding: intent.request.preconditions.binding_digest,
			...intent.request.params.project_id ? { project_id: intent.request.params.project_id } : {}
		})) if (name in refs && refs[name] !== value) throw new Error(t("pub_invalid_result"));
		if (result != null && (!object(result) || result.host !== intent.request.target.host || result.workspace_id !== intent.request.target.workspace_id || result.repository !== intent.request.target.repository || result.source_ref !== intent.request.params.source_ref || result.source_sha !== intent.request.params.source_sha || result.repository_id !== intent.request.preconditions.repository_id || result.binding_digest !== intent.request.preconditions.binding_digest || !text(result.session_id, 256) || result.session_id !== candidate.external_refs?.session_id)) throw new Error(t("pub_invalid_result"));
		if (candidate.status === "succeeded" && (!result || result.message_id !== `batc-${candidate.operation_id}`)) throw new Error(t("pub_invalid_result"));
		operation = candidate;
		intent.operation_id = candidate.operation_id;
		readFailed = false;
		persist();
		status.replaceChildren();
		update();
	}
	const apply = h("button", {
		class: "primary",
		onclick: async () => {
			if (!current() || busy || readFailed || !ready() || !allowed() || saved.intent?.operation_id || saved.intent?.refused) return;
			if (!saved.intent) {
				if (!projectReady() || !preview || !validPreview$1(preview, selected()) || !bound() || !hostAllowed() || attachments && !attachments.ready() || !validRequest(request())) return;
				saved.intent = {
					request: structuredClone(request()),
					key: crypto.randomUUID(),
					operation_id: null
				};
			}
			if (!saved.intent.request || !saved.intent.key) return;
			try {
				persist();
			} catch (e) {
				showError(e);
				update();
				return;
			}
			busy = true;
			update();
			const intent = saved.intent;
			submission = (async () => {
				try {
					const doc = await api("POST", "/operations?wait=3", intent.request, intent.key);
					guard();
					accept(doc.operation);
				} catch (e) {
					if (current()) {
						if (e.status >= 400 && e.status < 500 && noAdmission.has(e.code)) {
							intent.refused = e.code;
							try {
								persist();
							} catch {}
						}
						showError(e);
					}
				} finally {
					busy = false;
					if (current()) update();
				}
			})();
			try {
				await submission;
			} finally {
				submission = null;
			}
		}
	}, t("pub_apply"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(() => {})
	}, t("permissions_check"));
	const another = h("button", {
		class: "secondary",
		onclick: () => {
			if (!current() || busy || refreshing || readFailed || attachments && !attachments.ready() || !(terminal$1(operation) || saved.intent?.refused)) return;
			const previous = saved;
			saved = {
				target: saved.target,
				source_ref: saved.source_ref,
				agent: saved.agent,
				prompt: "",
				title: "",
				model: saved.model
			};
			try {
				persist();
			} catch (e) {
				saved = previous;
				showError(e);
				return;
			}
			operation = preview = null;
			status.replaceChildren();
			attachments?.reset();
			fill();
			update();
		}
	}, t("pub_new"));
	function change(field, value) {
		if (!current() || saved.intent || busy) {
			fill();
			return;
		}
		saved[field] = value;
		if (field === "target" || field === "source_ref") {
			preview = null;
			sequence++;
			reading = false;
		}
		try {
			persist();
		} catch (e) {
			showError(e);
		}
		update();
	}
	binding.addEventListener("change", () => change("target", binding.value ? JSON.parse(binding.value) : null));
	for (const [field, el] of Object.entries(inputs)) el.addEventListener(field === "agent" ? "change" : "input", () => change(field, el.value));
	const label = (name, el) => h("label", {}, t(name), el);
	const advanced = h("details", {
		class: "dispatch-advanced",
		open: Boolean(saved.model || saved.title)
	}, h("summary", {}, t("dispatch_advanced")), h("div", { class: "capture-fields" }, label("start_title", title), label("start_model", model)));
	const box = h("section", {
		class: "session-start published-start",
		"data-published-start": ""
	}, project ? projectStatus : null, h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("pub_binding", binding), label("pub_ref", sourceRef)), branchHelp, h("p", { class: "muted" }, t("pub_head_only")), h("div", { class: "actions" }, inspect), facts), h("div", { class: "panel" }, h("div", { class: "capture-fields" }, label("start_agent", agent), !project ? label("start_title", title) : null, !project && expanded() ? label("start_model", model) : null), label("pub_prompt", prompt), project ? advanced : null, attachmentBox, h("p", { class: "muted" }, t("pub_isolation"))), h("div", { class: "actions" }, apply, check, another), outcome, status);
	function update() {
		const fixed = Boolean(saved.intent);
		if (attachmentBox) {
			attachmentBox.disabled = fixed || busy;
			attachmentBox.hidden = fixed;
		}
		binding.disabled = fixed || busy;
		for (const el of Object.values(inputs)) el.disabled = fixed || busy;
		const validBranch = ref(selected().source_ref);
		branchHelp.hidden = fixed;
		branchHelp.textContent = t(saved.source_ref && !validBranch ? "pub_branch_invalid" : "pub_branch_help");
		sourceRef.setAttribute("aria-invalid", String(Boolean(saved.source_ref && !validBranch)));
		inspect.hidden = fixed;
		inspect.disabled = reading || !observe() || !ready() || !projectReady() || !bound() || !validBranch;
		inspect.textContent = t(reading ? "pub_loading" : "pub_preview");
		apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused);
		apply.textContent = t(fixed ? "permissions_retry" : "pub_apply");
		apply.disabled = busy || readFailed || !ready() || !allowed() || (fixed ? !saved.intent.request || !saved.intent.key : reading || !projectReady() || !preview || !validPreview$1(preview, selected()) || !bound() || !hostAllowed() || attachments && !attachments.ready() || !validRequest(request()));
		check.hidden = !saved.intent?.operation_id;
		check.disabled = busy || Boolean(refreshing);
		another.hidden = !(terminal$1(operation) || saved.intent?.refused);
		another.disabled = busy || Boolean(refreshing) || readFailed || Boolean(attachments && !attachments.ready());
		facts.replaceChildren();
		const original = saved.intent?.request;
		if (preview || original) {
			const r = original || request();
			const row = (label, value) => h("div", {}, h("strong", {}, t(label), ": "), h("span", { class: "pre" }, value));
			facts.append(h("p", { class: "muted" }, t("pub_reviewed")), row("capture_repository", r.target.repository), row("host", r.target.host), row("sessions_workspace_id", r.target.workspace_id), ...preview ? [row("start_workspace", `${preview.workspace.name || ""} · ${preview.workspace.folder}`)] : [], row("pub_ref", r.params.source_ref), row("pub_sha", r.params.source_sha));
		}
		outcome.replaceChildren();
		if (!allowed()) outcome.append(h("p", { class: "muted" }, t("pub_unavailable")));
		else if (!bindings().length && !fixed) outcome.append(h("p", { class: "muted" }, t(project ? "dispatch_no_bindings" : "pub_no_bindings")));
		if (!fixed) return;
		outcome.append(h("p", {}, operation ? opStatus(operation) : t(saved.intent.refused ? "start_refused" : "start_unknown"), " ", saved.intent.operation_id ? h("a", { href: `#/op/${saved.intent.operation_id}` }, t("permissions_details")) : null, operation?.status_reason ? ` · ${operation.status_reason}` : ""), h("p", { class: "muted" }, t("pub_fixed")));
		if (!original || !saved.intent.key) outcome.append(h("p", { class: "error" }, t("permissions_damaged")));
		if (original?.params.artifacts?.length) outcome.append(h("p", { class: "muted" }, t("dispatch_fixed_inputs")), h("ul", { class: "dispatch-fixed-inputs" }, ...original.params.artifacts.map((r) => h("li", {}, `${r.artifact_id} · r${r.revision} · ${r.digest}`))));
		const complete = operation?.status === "succeeded" && operation.result?.message_id === `batc-${operation.operation_id}`;
		const proof = complete ? operation.result : operation?.steps?.some((s) => s.name === "session.start" && s.status === "succeeded") && text(operation.external_refs?.session_id, 256) ? {
			host: saved.target.host,
			session_id: operation.external_refs.session_id
		} : null;
		if (proof) outcome.append(h("p", {}, t("start_started"), " ", h("a", { href: `#/session/${encodeURIComponent(proof.host)}/${encodeURIComponent(proof.session_id)}` }, proof.session_id)), h("p", { class: "muted" }, t(complete ? "start_prompt_accepted" : "start_prompt_unknown")));
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		if (!saved.intent?.operation_id) {
			update();
			return;
		}
		refreshing = (async () => {
			const doc = await api("GET", `/operations/${saved.intent.operation_id}`);
			guard();
			accept(doc.operation);
		})();
		update();
		try {
			await refreshing;
		} catch (e) {
			if (current()) {
				readFailed = true;
				showError(e);
				update();
			}
			throw e;
		} finally {
			refreshing = null;
			if (current()) update();
		}
	}
	async function readProject() {
		if (!project) return;
		try {
			const { project: p } = await api("GET", `/projects/${encodeURIComponent(project)}`);
			guard();
			if (p?.project_id !== project || !Number.isSafeInteger(p.version) || p.version < 1 || !Array.isArray(p.repositories) || p.repositories.some((r) => typeof r !== "string")) throw new Error(t("dispatch_project_unavailable"));
			if (projectDoc && (p.version !== projectDoc.version || !equal$1(p.repositories, projectDoc.repositories) || p.archived !== projectDoc.archived)) {
				preview = null;
				previewProjectVersion = null;
				sequence++;
				reading = false;
			}
			projectDoc = p;
			projectFailed = false;
			if (autoSelect && !saved.intent && !saved.target && bindings().length === 1) {
				const b = bindings()[0];
				saved.target = {
					repository: b.repository,
					host: b.host,
					workspace_id: b.workspace_id
				};
				persist();
			}
			autoSelect = false;
			const values = Object.fromEntries(Object.entries(inputs).map(([k, el]) => [k, el.value]));
			fill();
			for (const [k, value] of Object.entries(values)) inputs[k].value = value;
			projectStatus.replaceChildren(h("p", {}, h("a", { href: `#/project/${project}` }, p.name)), h("p", { class: "muted" }, t(p.archived ? "dispatch_archived" : expanded() ? "dispatch_project_help" : "dispatch_unsupported")));
			update();
		} catch (e) {
			if (current()) {
				projectFailed = true;
				projectStatus.replaceChildren(errorBox(e));
				update();
			}
			throw e;
		}
	}
	function loadProject() {
		projectQueue = projectQueue.catch(() => {}).then(() => {
			guard();
			return readProject();
		});
		return projectQueue;
	}
	fill();
	update();
	const refreshAll = async () => {
		const failed = (await Promise.allSettled([loadProject(), refresh(true)])).find((r) => r.status === "rejected");
		if (failed) throw failed.reason;
	};
	return {
		box,
		update,
		refresh: project ? refreshAll : refresh,
		init: project ? refreshAll : refresh
	};
}
//#endregion
//#region src/artifact-content.js
init_transport();
var reference = (row) => ({
	artifact_id: row.artifact_id,
	revision: row.revision,
	digest: row.digest
});
var same = (a, b) => a && b && a.artifact_id === b.artifact_id && a.revision === b.revision && a.digest === b.digest;
var pending = new Set(["downloading", "saving"]);
var textLimit = 262144;
var pngLimit = 2097152;
var contentLimit = 16777216;
async function browserPreview(bytes) {
	if (bytes.slice(0, 8).every((byte, i) => byte === [
		137,
		80,
		78,
		71,
		13,
		10,
		26,
		10
	][i]) && bytes.length >= 33) {
		if (bytes.length > pngLimit) throw new Error("PREVIEW_UNSUPPORTED");
		const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
		const width = view.getUint32(16), height = view.getUint32(20);
		if (view.getUint32(8) !== 13 || String.fromCharCode(...bytes.slice(12, 16)) !== "IHDR" || !width || !height || width * height > 1048576) throw new Error("PREVIEW_UNSUPPORTED");
		const chunks = [bytes.slice(0, 8)];
		let header = false, palette = false, transparency = false, data = false, dataEnded = false, ended = false;
		for (let offset = 8; offset < bytes.length;) {
			if (offset + 12 > bytes.length) throw new Error("PREVIEW_UNSUPPORTED");
			const length = view.getUint32(offset), end = offset + length + 12;
			const kind = String.fromCharCode(...bytes.slice(offset + 4, offset + 8));
			if (end > bytes.length || !/^[A-Za-z]{2}[A-Z][A-Za-z]$/.test(kind) || kind === "acTL") throw new Error("PREVIEW_UNSUPPORTED");
			if (kind === "IHDR") {
				if (header || offset !== 8 || length !== 13) throw new Error("PREVIEW_UNSUPPORTED");
				header = true;
			} else if (!header) throw new Error("PREVIEW_UNSUPPORTED");
			if (kind === "PLTE") {
				if (palette || transparency || data || !length || length > 768 || length % 3) throw new Error("PREVIEW_UNSUPPORTED");
				palette = true;
			}
			if (kind === "tRNS") {
				if (transparency || data || bytes[25] === 3 && !palette) throw new Error("PREVIEW_UNSUPPORTED");
				transparency = true;
			}
			if (kind === "IDAT") {
				if (dataEnded || bytes[25] === 3 && !palette) throw new Error("PREVIEW_UNSUPPORTED");
				data = true;
			} else if (data) dataEnded = true;
			if (kind === "IEND") {
				if (!data || ended || length !== 0 || end !== bytes.length) throw new Error("PREVIEW_UNSUPPORTED");
				ended = true;
			}
			if ([
				"IHDR",
				"PLTE",
				"IDAT",
				"IEND",
				"tRNS"
			].includes(kind)) chunks.push(bytes.slice(offset, end));
			else if (/^[A-Z]/.test(kind)) throw new Error("PREVIEW_UNSUPPORTED");
			offset = end;
		}
		if (!ended) throw new Error("PREVIEW_UNSUPPORTED");
		const bitmap = await createImageBitmap(new Blob(chunks, { type: "image/png" }));
		try {
			if (bitmap.width !== width || bitmap.height !== height) throw new Error("PREVIEW_UNSUPPORTED");
			const canvas = document.createElement("canvas");
			canvas.width = width;
			canvas.height = height;
			canvas.getContext("2d").drawImage(bitmap, 0, 0);
			return { canvas };
		} finally {
			bitmap.close();
		}
	}
	if (bytes.length > textLimit) throw new Error("PREVIEW_UNSUPPORTED");
	let text;
	try {
		text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
	} catch {
		throw new Error("PREVIEW_UNSUPPORTED");
	}
	if (text.includes("\0")) throw new Error("PREVIEW_UNSUPPORTED");
	return { text };
}
function artifactContent({ h, t, api, guard, getArtifact, canRead, validArtifact, readBrowser }) {
	const status = h("p", {
		class: "muted",
		role: "status"
	}), transfers = h("div"), preview = h("div", {
		class: "file-preview",
		hidden: true
	});
	const box = h("div", { class: "artifact-content" }), receipts = new Map(), controller = new AbortController();
	let current = null, busy = false, disposed = false, timer, readingStatus = null;
	const live = (expected) => {
		guard();
		if (disposed || !canRead() || expected && !same(expected, getArtifact())) throw new Error(t("ar_content_changed"));
	};
	const fail = (error) => {
		try {
			guard();
			if (!disposed) status.textContent = error.message === "PREVIEW_UNSUPPORTED" ? t("ar_content_preview_limit") : error.message;
		} catch {}
	};
	const close = () => {
		preview.replaceChildren();
		preview.hidden = true;
	};
	const receiptValid = (value) => /^file_[0-9a-f]{32}$/.test(value?.transfer_id) && value.direction === "download" && same(value.artifact, current) && value.digest === current.digest && value.size_bytes === current.size_bytes && [
		"downloading",
		"saving",
		"saved",
		"stopped",
		"failed",
		"cancelled"
	].includes(value.stage) && Number.isSafeInteger(value.transferred_bytes) && value.transferred_bytes >= 0 && value.transferred_bytes <= value.size_bytes;
	const adopt = (value) => {
		if (!receiptValid(value)) throw new Error(t("ar_content_changed"));
		const previous = receipts.get(value.transfer_id);
		if (previous && [
			"display_name",
			"digest",
			"size_bytes",
			"direction"
		].some((key) => previous[key] !== value[key])) throw new Error(t("ar_content_changed"));
		receipts.set(value.transfer_id, value);
	};
	async function control(receipt, action) {
		try {
			live(receipt.artifact);
			await nativeFilesControl(receipt.transfer_id, action);
			live(receipt.artifact);
			await refresh();
		} catch (error) {
			fail(error);
		}
	}
	function renderTransfers() {
		transfers.replaceChildren(...[...receipts.values()].map((row) => h("div", { class: "file-transfer" }, h("div", { class: "muted" }, `${t(`files_${row.stage}`)} · ${row.transferred_bytes} / ${row.size_bytes} B`), row.error ? h("p", { class: "muted" }, row.error) : null, h("div", { class: "actions" }, pending.has(row.stage) ? h("button", {
			class: "secondary",
			onclick: () => control(row, "stop")
		}, t("files_stop")) : [row.stage === "stopped" || row.stage === "failed" ? h("button", {
			class: "secondary",
			onclick: () => control(row, "retry")
		}, t("files_retry")) : null, h("button", {
			class: "secondary",
			onclick: () => control(row, "discard_local")
		}, t("files_discard"))]))));
	}
	async function refresh() {
		if (readingStatus) return readingStatus;
		const expected = current;
		readingStatus = (async () => {
			live(expected);
			const doc = await nativeFilesStatus();
			live(expected);
			const found = new Set();
			for (const row of doc.transfers || []) if (row.direction === "download" && same(row.artifact, expected)) {
				adopt(row);
				found.add(row.transfer_id);
			}
			for (const id of receipts.keys()) if (!found.has(id)) receipts.delete(id);
			renderTransfers();
			clearTimeout(timer);
			if ([...receipts.values()].some((row) => pending.has(row.stage))) timer = setTimeout(() => refresh().catch(fail), 1e3);
		})();
		try {
			await readingStatus;
		} finally {
			readingStatus = null;
		}
	}
	async function fresh() {
		live();
		const expected = getArtifact();
		if (!expected || !Number.isSafeInteger(expected.size_bytes) || expected.size_bytes < 0 || expected.size_bytes > contentLimit) throw new Error(t("ar_content_limit"));
		const { artifact: row } = await api("GET", `/artifacts/${expected.artifact_id}/revisions/${expected.revision}`);
		live(expected);
		if (!validArtifact(row, reference(expected)) || row.size_bytes !== expected.size_bytes || row.operation_id !== expected.operation_id || row.source?.fingerprint !== expected.source?.fingerprint) throw new Error(t("ar_content_changed"));
		return row;
	}
	async function perform(action) {
		if (busy) return;
		busy = true;
		update();
		status.textContent = t("ar_content_reading");
		try {
			const row = await fresh(), ref = reference(row);
			if (action === "preview") {
				if (row.size_bytes > pngLimit) throw new Error("PREVIEW_UNSUPPORTED");
				let content;
				if (nativeDesktop) {
					const result = await nativeFilesPreview(ref);
					live(ref);
					if (result.media_type === "text/plain" && typeof result.text === "string" && new TextEncoder().encode(result.text).length <= textLimit && !result.text.includes("\0")) content = { text: result.text };
					else if (result.media_type === "image/png" && typeof result.base64 === "string" && result.base64.length <= 28e5) content = await browserPreview(Uint8Array.from(atob(result.base64), (c) => c.charCodeAt(0)));
					else throw new Error(t("ar_content_changed"));
				} else content = await browserPreview(await readBrowser(ref, row.size_bytes, controller.signal));
				live(ref);
				close();
				let body;
				if (content.canvas) {
					body = content.canvas;
					body.setAttribute("role", "img");
					body.setAttribute("aria-label", t("files_preview"));
				} else body = h("pre", {}, content.text);
				preview.hidden = false;
				preview.append(h("div", { class: "actions" }, h("strong", {}, t("files_preview")), h("button", {
					class: "secondary",
					onclick: close
				}, t("close"))), body);
				status.textContent = t("ar_content_verified");
			} else if (nativeDesktop) {
				const receipt = await nativeFilesSave(ref);
				live(ref);
				status.textContent = "";
				if (receipt) {
					adopt(receipt);
					renderTransfers();
					await refresh();
				}
			} else {
				const bytes = await readBrowser(ref, row.size_bytes, controller.signal);
				live(ref);
				const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
				const link = document.createElement("a");
				link.href = url;
				link.download = String(row.display_name || row.artifact_id).replace(/[\\/\x00-\x1f\x7f]/g, "_").slice(0, 200) || row.artifact_id;
				link.click();
				setTimeout(() => URL.revokeObjectURL(url), 1e3);
				status.textContent = t("ar_content_downloaded");
			}
		} catch (error) {
			fail(error);
		} finally {
			busy = false;
			update();
		}
	}
	const peek = h("button", {
		class: "secondary",
		onclick: () => perform("preview")
	}, t("files_preview"));
	const save = h("button", {
		class: "secondary",
		onclick: () => perform("save")
	}, t(nativeDesktop ? "files_save" : "ar_content_download"));
	box.append(h("div", { class: "actions" }, peek, save), h("p", { class: "muted" }, t("ar_content_help")), status, preview, transfers);
	function update() {
		if (disposed) return;
		const next = getArtifact(), changed = !same(current, next);
		if (changed) {
			current = next;
			close();
			receipts.clear();
			renderTransfers();
			clearTimeout(timer);
			status.textContent = "";
		}
		box.hidden = !next;
		peek.disabled = save.disabled = busy || !next || !canRead() || nativeDesktop && !nativeFileSupport;
		if (next && nativeDesktop && !nativeFileSupport) status.textContent = t("ar_content_native_unavailable");
		if (changed && next && nativeDesktop && nativeFileSupport) queueMicrotask(() => refresh().catch(fail));
	}
	return {
		box,
		update,
		dispose() {
			disposed = true;
			controller.abort();
			clearTimeout(timer);
			close();
		}
	};
}
//#endregion
//#region src/artifact-review.js
var record = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
var ordered = (value) => record(value) ? Object.fromEntries(Object.keys(value).sort().map((k) => [k, ordered(value[k])])) : Array.isArray(value) ? value.map(ordered) : value;
var stable = (value) => JSON.stringify(ordered(value));
var equal = (a, b) => stable(a ?? null) === stable(b ?? null);
var digest = (value) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
var oid = (value) => typeof value === "string" && /^op_[0-9a-f]{32}$/.test(value);
var aid = (value) => typeof value === "string" && /^art_[0-9a-f]{32}$/.test(value);
var tid = (value) => typeof value === "string" && /^[0-9a-f-]{8,64}$/.test(value);
var commandId = (value) => typeof value === "string" && value.length > 0 && value.length <= 256 && !/[\x00-\x1f\x7f-\x9f]/.test(value);
var terminal = (op) => [
	"succeeded",
	"failed",
	"cancelled"
].includes(op?.status);
var sha40 = (value) => typeof value === "string" && /^[0-9a-f]{40}$/.test(value);
var executions = [
	"checkpoint.continue",
	"integration.handoff",
	"session.send",
	"session.start",
	"repository.continue"
];
var managedCaptureExecution = (op) => oid(op?.operation_id) && op.status === "succeeded" && executions.includes(op.action) && (op.action !== "session.start" || op.result?.started === true && op.result.prompt_sent === true && op.result.message_id === `batc-${op.operation_id}`) && (op.action !== "repository.continue" || op.result?.message_id === `batc-${op.operation_id}` && sha40(op.result.source_sha));
var safePath = (path) => typeof path === "string" && path && new TextEncoder().encode(path).length <= 4096 && !/[\\\x00-\x1f\x7f-\x9f]/.test(path) && path.split("/").every((p) => p && p !== "." && p !== ".." && p.toLowerCase() !== ".git");
var selectorValid = (s) => record(s) && (equal(Object.keys(s).sort(), ["execution_operation_id"]) && oid(s.execution_operation_id) || equal(Object.keys(s).sort(), ["command_id", "task_id"]) && tid(s.task_id) && commandId(s.command_id));
var validRef = (ref) => aid(ref?.artifact_id) && Number.isSafeInteger(ref.revision) && ref.revision > 0 && ref.revision <= 999999999 && digest(ref.digest);
var refOf = (value) => ({
	artifact_id: value.artifact_id,
	revision: value.revision,
	digest: value.digest
});
var sourceFromOperation = (op) => op.action === "session.send" ? op.external_refs?.resolved_target || op.target : op.result;
function validPreview(doc, input) {
	return record(doc) && /^acpv_[0-9a-f]{32}$/.test(doc.preview_id) && typeof doc.preview_token === "string" && doc.preview_token.length > 0 && doc.preview_token.length <= 24576 && digest(doc.fingerprint) && doc.snapshot === false && Number.isFinite(doc.expires_at) && doc.source?.provenance === "connector_managed" && doc.source.host === input.host && doc.source.session_id === input.session_id && equal(doc.source.selector, input.selector) && doc.relative_path === input.relative_path && typeof doc.source.root === "string" && typeof doc.source.repository_root === "string" && record(doc.source.lineage) && digest(doc.evidence?.digest) && /^[0-9a-f]{40}$/.test(doc.evidence.head_sha) && Number.isSafeInteger(doc.evidence.size_bytes) && doc.evidence.size_bytes >= 0;
}
function validArtifact(row, expected) {
	const proof = row?.source;
	return validRef(row) && row.state === "ready" && record(proof) && proof.kind === "managed_capture" && oid(proof.operation_id) && row.operation_id === proof.operation_id && digest(proof.fingerprint) && proof.source?.provenance === "connector_managed" && record(proof.source.lineage) && selectorValid(proof.source.selector) && safePath(proof.relative_path) && proof.evidence?.digest === row.digest && proof.evidence.size_bytes === row.size_bytes && /^[0-9a-f]{40}$/.test(proof.evidence.head_sha) && (!expected || equal(refOf(row), expected));
}
function restore(raw) {
	const saved = {
		relative_path: "",
		selector: null,
		reviewText: ""
	};
	if (!record(raw)) return saved;
	if (typeof raw.relative_path === "string") saved.relative_path = raw.relative_path;
	if (selectorValid(raw.selector)) saved.selector = raw.selector;
	if (typeof raw.reviewText === "string") saved.reviewText = raw.reviewText;
	if (record(raw.preview)) saved.preview = raw.preview;
	for (const kind of ["capture", "accept"]) if (raw[kind]) {
		const intent = raw[kind];
		const usable = record(intent.request) && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200 && typeof intent.actor === "string" && record(intent.request.target) && record(intent.request.params) && record(intent.request.preconditions) && intent.request.action === (kind === "capture" ? "artifact.capture.managed" : "artifact.accept");
		saved[kind] = {
			request: usable ? intent.request : null,
			key: usable ? intent.key : null,
			actor: intent.actor,
			operation_id: oid(intent.operation_id) ? intent.operation_id : null,
			expected: intent.expected,
			refused: usable && [
				"PREVIEW_EXPIRED",
				"PREVIEW_TOKEN_INVALID",
				"PREVIEW_MISMATCH",
				"INVALID_PARAMS",
				"ARTIFACT_REVISION_MISMATCH",
				"ARTIFACT_LINEAGE_UNPROVEN"
			].includes(intent.refused) ? intent.refused : null
		};
	}
	return saved;
}
async function mountArtifactReview({ main, h, t, api, caps, guard, onEvents, errorBox, opStatus, storageKey, context, readBrowser }) {
	const container = h("div", { class: "artifact-review" });
	main.append(container);
	let raw;
	try {
		raw = JSON.parse(localStorage.getItem(storageKey));
	} catch {}
	let saved = restore(raw), source = null, artifact = null, busy = false, readFailed = false, disposed = false;
	let refreshing = null, submission = null, revision = 0, catalogCursor = null, catalogReading = null, catalogPages = 0;
	let catalogRows = new Map();
	const operations = {
		capture: null,
		accept: null
	}, candidates = new Map(), pages = new Map();
	const notice = h("div", { role: "status" }), sourceBox = h("div"), evidence = h("div"), outcome = h("div");
	const catalog = h("div"), reviewFacts = h("div"), catalogNotice = h("div");
	const path = h("input", {
		"aria-label": t("capture_path"),
		value: saved.relative_path,
		placeholder: "results/report.md"
	});
	const choice = h("select", { "aria-label": t("ar_execution") }, h("option", { value: "" }, t("ar_choose_execution")));
	const customType = h("select", { "aria-label": t("ar_evidence_kind") }, h("option", { value: "operation" }, t("ar_operation")), h("option", { value: "command" }, t("ar_command")));
	const customTask = h("input", {
		"aria-label": t("ar_task_id"),
		maxlength: 64
	});
	const customId = h("input", {
		"aria-label": t("ar_evidence_id"),
		maxlength: 256
	});
	const custom = h("div", {
		class: "capture-fields",
		hidden: true
	}, h("label", {}, t("ar_evidence_kind"), customType), h("label", {}, t("ar_task_id"), customTask), h("label", {}, t("ar_evidence_id"), customId));
	const receipt = h("textarea", {
		"aria-label": t("ar_receipt"),
		maxlength: 2e3,
		value: saved.reviewText
	});
	receipt.value = saved.reviewText;
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => update()
	});
	const currentView = () => {
		try {
			guard();
			return !disposed;
		} catch {
			return false;
		}
	};
	const persist = (required = false) => {
		guard();
		try {
			localStorage.setItem(storageKey, JSON.stringify(saved));
			return true;
		} catch {
			if (required) throw new Error(t("ar_storage"));
			return false;
		}
	};
	const showError = (error) => {
		if (currentView()) notice.replaceChildren(errorBox(error));
	};
	const supported = () => caps()?.artifacts?.capture?.managed_single_file === true;
	const scope = (name) => caps()?.scopes?.includes(name);
	const allowed = (name) => caps()?.actions?.some((a) => a.action === name && a.allowed === true);
	const mayCapture = () => supported() && scope("observe") && scope("manage") && allowed("artifact.capture.managed");
	const mayAccept = () => scope("observe") && scope("approve") && allowed("artifact.accept");
	const active = (kind) => saved[kind] && !saved[kind].refused && (!terminal(operations[kind]) || kind === "capture" && operations.capture?.status === "succeeded" && !artifact);
	const frozen = () => Boolean(saved.capture || saved.accept);
	const input = () => ({
		host: source?.host,
		session_id: source?.session_id,
		relative_path: path.value,
		selector: saved.selector
	});
	const facts = (rows) => h("dl", { class: "kv" }, ...rows.flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, h("code", {}, value ?? ""))]));
	const proofFacts = (proof) => facts([
		[t("capture_source"), `${proof.source.host} / ${proof.source.session_id}`],
		[t("capture_path"), proof.relative_path],
		[t("capture_root"), proof.source.root],
		["HEAD", proof.evidence.head_sha],
		[t("capture_bytes"), String(proof.evidence.size_bytes)],
		["SHA-256", proof.evidence.digest]
	]);
	function renderChoice() {
		choice.replaceChildren(h("option", { value: "" }, t("ar_choose_execution")), ...[...candidates].map(([key, entry]) => h("option", { value: key }, entry.label)), h("option", { value: "custom" }, t("ar_exact_evidence")));
		if (saved.selector) {
			const key = stable(saved.selector);
			if (frozen() && !candidates.has(key)) choice.append(h("option", { value: key }, saved.selector.execution_operation_id ? `${t("ar_operation")} · ${saved.selector.execution_operation_id}` : `${t("ar_command")} · ${saved.selector.task_id} · ${saved.selector.command_id}`));
			if (candidates.has(key) || frozen()) choice.value = key;
			else {
				choice.value = "custom";
				customType.value = saved.selector.task_id ? "command" : "operation";
				customTask.value = saved.selector.task_id || context.task_id || "";
				customId.value = saved.selector.command_id || saved.selector.execution_operation_id;
			}
		}
		custom.hidden = choice.value !== "custom";
		customTask.disabled = customType.value !== "command" || frozen() || busy;
	}
	function changed() {
		if (!currentView() || frozen()) return;
		revision++;
		saved.relative_path = path.value;
		saved.preview = null;
		reviewed.checked = false;
		saved.selector = choice.value === "custom" ? customType.value === "command" ? {
			task_id: customTask.value.trim(),
			command_id: customId.value.trim()
		} : { execution_operation_id: customId.value.trim() } : candidates.get(choice.value)?.selector || null;
		custom.hidden = choice.value !== "custom";
		persist();
		render();
	}
	for (const field of [
		path,
		choice,
		customType,
		customTask,
		customId
	]) field.addEventListener("input", changed);
	receipt.addEventListener("input", () => {
		if (!currentView() || saved.accept) return;
		saved.reviewText = receipt.value;
		persist();
		update();
	});
	async function captureArtifact(op) {
		const intent = saved.capture, ref = op.result;
		if (!validRef(ref) || ref.digest !== intent.expected?.digest) throw new Error(t("ar_invalid_result"));
		const { artifact: row } = await api("GET", `/artifacts/${ref.artifact_id}/revisions/${ref.revision}`);
		guard();
		const proof = row?.source;
		if (!validArtifact(row, refOf(ref)) || proof.operation_id !== op.operation_id || proof.fingerprint !== intent.request.preconditions.expected_fingerprint || !equal(proof.source, intent.expected.source) || !equal(proof.evidence, intent.expected.evidence) || proof.relative_path !== intent.expected.relative_path) throw new Error(t("ar_invalid_result"));
		artifact = row;
		await loadCatalog();
	}
	async function adopt(kind, op) {
		guard();
		const intent = saved[kind];
		if (!intent?.request || !oid(op?.operation_id) || op.actor !== intent.actor || op.actor !== caps().actor || op.idempotency_key !== intent.key || op.action !== intent.request.action || !equal(op.target, intent.request.target) || !equal(op.params, intent.request.params) || !equal(op.preconditions, intent.request.preconditions) || intent.operation_id && intent.operation_id !== op.operation_id) throw new Error(t("ar_invalid_result"));
		intent.operation_id = op.operation_id;
		persist();
		if (kind === "capture" && op.status === "succeeded") await captureArtifact(op);
		if (kind === "accept" && op.status === "succeeded") {
			const result = op.result, request = intent.request;
			if (!result || result.operation_id !== op.operation_id || result.actor !== intent.actor || result.meaning !== "artifact_revision_review" || !equal(refOf(result), {
				...request.target,
				digest: request.params.digest
			}) || result.source_fingerprint !== request.params.source_fingerprint || result.receipt !== request.params.receipt || result.capture_operation_id !== intent.expected?.capture_operation_id || result.source_commit !== intent.expected?.source_commit || !equal(result.lineage, intent.expected?.lineage)) throw new Error(t("ar_invalid_result"));
		}
		operations[kind] = op;
		readFailed = false;
		render();
	}
	async function submit(kind) {
		if (busy || refreshing || readFailed || !saved[kind]?.request) return;
		guard();
		busy = true;
		update();
		let finish;
		submission = new Promise((resolve) => {
			finish = resolve;
		});
		try {
			persist(true);
			const intent = saved[kind];
			const result = intent.operation_id ? await api("GET", `/operations/${intent.operation_id}`) : await api("POST", "/operations?wait=3", intent.request, intent.key);
			guard();
			await adopt(kind, result.operation);
			notice.replaceChildren();
		} catch (error) {
			if (!currentView()) return;
			const safe = kind === "capture" ? [
				"PREVIEW_EXPIRED",
				"PREVIEW_TOKEN_INVALID",
				"PREVIEW_MISMATCH",
				"INVALID_PARAMS"
			] : [
				"INVALID_PARAMS",
				"ARTIFACT_REVISION_MISMATCH",
				"ARTIFACT_LINEAGE_UNPROVEN"
			];
			if (!saved[kind].operation_id && error.status >= 400 && error.status < 500 && safe.includes(error.code)) saved[kind].refused = error.code;
			persist();
			showError(error);
			if (kind === "capture" && error.status === 403) notice.append(h("p", { class: "muted" }, t("ar_original_credential")));
		} finally {
			busy = false;
			finish();
			submission = null;
			if (currentView()) render();
		}
	}
	const preview = h("button", {
		class: "secondary",
		onclick: async () => {
			if (busy || frozen() || !source || !scope("observe") || !supported() || !safePath(path.value) || !selectorValid(saved.selector)) return;
			guard();
			const ticket = ++revision, fixed = structuredClone(input());
			busy = true;
			saved.preview = null;
			reviewed.checked = false;
			update();
			try {
				const { selector, ...fields } = fixed;
				const { preview: doc } = await api("POST", "/artifact-managed-capture-previews", {
					...fields,
					...selector
				});
				guard();
				if (ticket !== revision) return;
				if (!validPreview(doc, fixed)) throw new Error(t("capture_invalid_preview"));
				saved.preview = doc;
				readFailed = false;
				persist();
				notice.replaceChildren();
			} catch (error) {
				if (ticket === revision) showError(error);
			} finally {
				busy = false;
				if (currentView()) render();
			}
		}
	}, t("capture_preview"));
	const capture = h("button", {
		class: "primary",
		onclick: () => {
			if (busy || refreshing || readFailed || !mayCapture() || saved.capture?.operation_id || saved.capture?.refused) return;
			guard();
			if (!saved.capture) {
				const doc = saved.preview;
				if (!doc || !reviewed.checked || doc.expires_at * 1e3 <= Date.now() || !validPreview(doc, input())) return;
				saved.capture = {
					key: crypto.randomUUID(),
					actor: caps().actor,
					request: {
						action: "artifact.capture.managed",
						target: { preview_id: doc.preview_id },
						params: { preview_token: doc.preview_token },
						preconditions: { expected_fingerprint: doc.fingerprint }
					},
					expected: {
						digest: doc.evidence.digest,
						evidence: doc.evidence,
						source: doc.source,
						relative_path: doc.relative_path
					}
				};
			}
			submit("capture");
		}
	}, t("capture_save"));
	const accept = h("button", {
		class: "primary",
		onclick: () => {
			if (busy || refreshing || readFailed || !artifact || !mayAccept() || saved.accept?.operation_id || saved.accept?.refused || !receipt.value.trim() || [...receipt.value].length > 2e3) return;
			guard();
			if (!saved.accept) saved.accept = {
				key: crypto.randomUUID(),
				actor: caps().actor,
				request: {
					action: "artifact.accept",
					target: {
						artifact_id: artifact.artifact_id,
						revision: artifact.revision
					},
					params: {
						digest: artifact.digest,
						source_fingerprint: artifact.source.fingerprint,
						receipt: receipt.value
					},
					preconditions: {}
				},
				expected: {
					capture_operation_id: artifact.source.operation_id,
					source_commit: artifact.source.evidence.head_sha,
					lineage: artifact.source.source.lineage
				}
			};
			submit("accept");
		}
	}, t("ar_accept"));
	const check = h("button", {
		class: "secondary",
		onclick: () => refresh(true).catch(showError)
	}, t("ar_check"));
	const reload = h("button", {
		class: "secondary",
		onclick: async () => {
			if (busy || refreshing || frozen()) return;
			busy = true;
			update();
			try {
				await loadSource();
				guard();
				readFailed = false;
				notice.replaceChildren();
			} catch (error) {
				showError(error);
			} finally {
				busy = false;
				if (currentView()) render();
			}
		}
	}, t("ar_refresh_sources"));
	const reset = h("button", {
		class: "secondary",
		onclick: async () => {
			guard();
			if (busy || refreshing || readFailed || active("capture") || active("accept")) return;
			saved = {
				relative_path: path.value,
				selector: null,
				reviewText: ""
			};
			artifact = source = null;
			candidates.clear();
			pages.clear();
			operations.capture = operations.accept = null;
			reviewed.checked = false;
			receipt.value = "";
			revision++;
			persist();
			notice.replaceChildren();
			renderChoice();
			busy = true;
			render();
			try {
				await loadSource();
			} catch (error) {
				showError(error);
			} finally {
				busy = false;
				if (currentView()) render();
			}
		}
	}, t("capture_new"));
	const newReview = h("button", {
		class: "secondary",
		onclick: () => {
			guard();
			if (busy || refreshing || readFailed || active("accept")) return;
			saved.accept = null;
			operations.accept = null;
			persist();
			render();
		}
	}, t("ar_new_review"));
	const moreExecutions = h("button", {
		class: "secondary",
		onclick: () => loadExecutions(true).catch(showError)
	}, t("ar_more_executions"));
	const content = artifactContent({
		h,
		t,
		api,
		guard,
		getArtifact: () => artifact,
		canRead: () => scope("observe") && !readFailed,
		validArtifact,
		readBrowser
	});
	const reviewPanel = h("section", {
		class: "panel",
		"data-artifact-accept": ""
	}, h("h2", {}, t("ar_review_title")), reviewFacts, content.box, h("p", { class: "muted" }, t("ar_accept_help")), h("label", {}, t("ar_receipt"), receipt), h("p", { class: "muted" }, t("ar_approve_scope")), h("div", { class: "actions" }, accept, newReview));
	const capturePanel = h("section", {
		class: "panel",
		"data-managed-capture": ""
	}, h("h2", {}, t("ar_capture_title")), sourceBox, h("div", { class: "capture-fields" }, h("label", {}, t("ar_execution"), choice), h("label", {}, t("capture_path"), path)), custom, h("div", { class: "actions" }, reload, moreExecutions, preview), evidence, h("label", { class: "capture-choice" }, reviewed, t("capture_review")), h("div", { class: "actions" }, capture, reset));
	const moreArtifacts = h("button", {
		class: "secondary",
		hidden: true,
		onclick: () => loadCatalog(true).catch((e) => catalogNotice.replaceChildren(errorBox(e)))
	}, t("more"));
	const catalogPanel = h("section", { class: "panel" }, h("h2", {}, t("ar_catalog")), catalog, catalogNotice, h("div", { class: "actions" }, moreArtifacts));
	container.append(h("h1", {}, t("ar_title")), h("p", { class: "muted" }, t("ar_help")), capturePanel, reviewPanel, h("div", { class: "actions" }, check), outcome, notice, catalogPanel);
	function update() {
		content.update();
		const fixed = busy || frozen();
		for (const field of [
			path,
			choice,
			customType,
			customId
		]) field.disabled = fixed;
		customTask.disabled = fixed || customType.value !== "command";
		preview.disabled = busy || frozen() || !source || !scope("observe") || !supported() || !safePath(path.value) || !selectorValid(saved.selector);
		reviewed.disabled = busy || Boolean(saved.capture) || !saved.preview || saved.preview.expires_at * 1e3 <= Date.now();
		reviewed.closest("label").hidden = Boolean(saved.capture) || !saved.preview;
		capture.hidden = Boolean(saved.capture?.operation_id || saved.capture?.refused);
		capture.textContent = saved.capture ? t("capture_check") : t("capture_save");
		capture.disabled = busy || Boolean(refreshing) || readFailed || !mayCapture() || !source || Boolean(saved.capture && !saved.capture.request) || !saved.capture && (!saved.preview || !reviewed.checked || saved.preview.expires_at * 1e3 <= Date.now());
		receipt.disabled = busy || Boolean(saved.accept) || !artifact;
		accept.hidden = Boolean(saved.accept?.operation_id || saved.accept?.refused);
		accept.textContent = saved.accept ? t("ar_check_accept") : t("ar_accept");
		accept.disabled = busy || Boolean(refreshing) || readFailed || !artifact || !mayAccept() || !receipt.value.trim() || [...receipt.value].length > 2e3 || Boolean(saved.accept && !saved.accept.request);
		check.hidden = !saved.capture?.operation_id && !saved.accept?.operation_id && context.kind !== "artifact";
		check.disabled = busy || Boolean(refreshing);
		reset.hidden = !saved.capture;
		reset.disabled = busy || Boolean(refreshing) || readFailed || Boolean(active("capture") || active("accept"));
		newReview.hidden = !saved.accept;
		newReview.disabled = busy || Boolean(refreshing) || readFailed || Boolean(active("accept"));
		moreExecutions.disabled = busy || frozen();
		reload.disabled = busy || frozen();
		moreExecutions.hidden = ![...pages.values()].some((value) => value !== null);
	}
	function render() {
		if (!currentView()) return;
		capturePanel.hidden = ![
			"session",
			"task",
			"operation"
		].includes(context.kind);
		evidence.replaceChildren();
		if (!mayCapture()) evidence.append(h("p", { class: "muted" }, t("capture_scope_manage")));
		if (saved.preview && validPreview(saved.preview, input())) {
			const description = [proofFacts(saved.preview), h("p", { class: "muted" }, saved.capture ? t("capture_fixed") : saved.preview.expires_at * 1e3 <= Date.now() ? t("capture_expired") : t("capture_single_file"))];
			evidence.append(...artifact ? [h("details", {}, h("summary", {}, t("ar_original_preview")), ...description)] : description);
		}
		reviewPanel.hidden = !artifact && context.kind !== "artifact" && !saved.accept;
		reviewFacts.replaceChildren();
		if (artifact) reviewFacts.append(facts([[t("ar_revision"), `${artifact.artifact_id} · r${artifact.revision}`]]), proofFacts(artifact.source), h("details", {}, h("summary", {}, t("ar_lineage")), h("pre", { class: "pre" }, JSON.stringify(artifact.source.source.lineage, null, 2))));
		outcome.replaceChildren();
		for (const kind of ["capture", "accept"]) if (saved[kind]) {
			const intent = saved[kind], op = operations[kind];
			outcome.append(h("p", {}, t(kind === "capture" ? "ar_capture_title" : "ar_review_title"), ": ", op ? opStatus(op) : t("capture_unknown"), " ", intent.operation_id ? h("a", { href: `#/op/${intent.operation_id}` }, intent.operation_id) : null));
			if (intent.refused) outcome.append(h("p", { class: "muted" }, intent.refused));
		}
		if (artifact) outcome.append(h("p", { "data-artifact-ready": "" }, t("capture_saved"), " ", `${artifact.artifact_id} · r${artifact.revision}`));
		if (operations.accept?.status === "succeeded") outcome.append(h("p", { "data-artifact-accepted": "" }, t("ar_recorded")));
		update();
	}
	async function loadExecutions(more = false) {
		if (!source || frozen()) return;
		const results = await Promise.all(executions.map(async (action) => {
			if (more && pages.get(action) === null) return;
			const before = more ? pages.get(action) : null;
			return {
				action,
				data: await api("GET", `/operations?status=succeeded&action=${action}&limit=50${before ? `&before=${before}` : ""}`)
			};
		}));
		guard();
		if (frozen()) return;
		for (const result of results.filter(Boolean)) {
			pages.set(result.action, result.data.next_before ?? null);
			for (const op of result.data.operations || []) {
				const bound = sourceFromOperation(op);
				if (managedCaptureExecution(op) && bound?.host === source.host && bound.session_id === source.session_id) {
					const selector = { execution_operation_id: op.operation_id };
					candidates.set(stable(selector), {
						selector,
						label: `${op.action} · ${op.operation_id}`
					});
				}
			}
		}
		renderChoice();
		update();
	}
	async function loadSource() {
		let task, data, bound;
		if (context.kind === "task") {
			task = (await api("GET", `/tasks/${encodeURIComponent(context.task_id)}`)).task;
			if (task?.task_id !== context.task_id) throw new Error(t("ar_source_unavailable"));
			bound = {
				host: task.host,
				session_id: task.session_id
			};
			customTask.value = task.task_id;
		} else if (context.kind === "operation") {
			const op = (await api("GET", `/operations/${context.operation_id}`)).operation;
			if (op?.operation_id !== context.operation_id || !managedCaptureExecution(op)) throw new Error(t("ar_source_unavailable"));
			bound = sourceFromOperation(op);
			if (!saved.selector) saved.selector = { execution_operation_id: context.operation_id };
		} else if (context.kind === "session") bound = context;
		else return;
		guard();
		if (!bound?.host || !bound?.session_id) throw new Error(t("ar_source_unavailable"));
		data = await api("GET", `/sessions/${encodeURIComponent(bound.host)}/${encodeURIComponent(bound.session_id)}`);
		guard();
		const row = data.session;
		if (row?.host !== bound.host || row.session_id !== bound.session_id || row.provenance !== "connector_managed" || row.api_access !== "managed") throw new Error(t("ar_source_unavailable"));
		source = {
			host: row.host,
			session_id: row.session_id
		};
		sourceBox.replaceChildren(facts([[t("capture_source"), `${row.host} / ${row.session_id}`]]));
		if (!saved.capture) {
			const taskIds = task ? [task.task_id] : [...new Set((data.relations_summary || []).filter((r) => r.status !== "closed").map((r) => r.execution_id))].filter(tid);
			const tasks = task ? [task] : await Promise.all(taskIds.slice(0, 20).map(async (id) => (await api("GET", `/tasks/${id}`)).task));
			guard();
			for (const current of tasks) if (current?.host === source.host && current.session_id === source.session_id) {
				for (const cmd of current.commands || []) if (cmd.task_id === current.task_id && cmd.session_id === source.session_id && cmd.kind === "send" && ["accepted", "settled"].includes(cmd.status) && commandId(cmd.command_id)) {
					const selector = {
						task_id: current.task_id,
						command_id: cmd.command_id
					};
					candidates.set(stable(selector), {
						selector,
						label: `${t("ar_command")} · ${current.task_id} · ${cmd.command_id}`
					});
				}
			}
			await loadExecutions();
		}
		renderChoice();
		render();
	}
	async function loadExactArtifact() {
		const expected = context.kind === "artifact" ? {
			artifact_id: context.artifact_id,
			revision: context.revision
		} : null;
		if (!expected) return;
		if (!aid(expected.artifact_id) || !Number.isSafeInteger(expected.revision) || expected.revision < 1 || expected.revision > 999999999) throw new Error(t("ar_invalid_result"));
		const { artifact: row } = await api("GET", `/artifacts/${expected.artifact_id}/revisions/${expected.revision}`);
		guard();
		if (!validArtifact(row) || row.artifact_id !== expected.artifact_id || row.revision !== expected.revision) throw new Error(t("ar_invalid_result"));
		artifact = row;
		render();
	}
	async function loadCatalog(more = false) {
		if (catalogReading) {
			await catalogReading;
			guard();
			return loadCatalog(more);
		}
		if (more && !catalogCursor) return;
		catalogReading = (async () => {
			let cursor = more ? catalogCursor : null, readPages = 0;
			const rows = more ? new Map(catalogRows) : new Map(), seen = new Set();
			for (let index = 0; index < (more ? 1 : Math.max(1, catalogPages)); index++) {
				if (seen.has(cursor)) throw new Error(t("ar_invalid_result"));
				seen.add(cursor);
				const data = await api("GET", `/artifacts?limit=30${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
				guard();
				if (!Array.isArray(data.artifacts) || data.next_cursor != null && (typeof data.next_cursor !== "string" || !data.next_cursor)) throw new Error(t("ar_invalid_result"));
				for (const row of data.artifacts.map((a) => a.revision).filter((row) => validArtifact(row))) rows.set(`${row.artifact_id}:${row.revision}`, row);
				cursor = data.next_cursor ?? null;
				readPages++;
				if (!cursor) break;
			}
			guard();
			catalogRows = rows;
			catalogCursor = cursor;
			catalogPages = (more ? catalogPages : 0) + readPages;
			catalog.replaceChildren(...[...rows.values()].map((row) => h("div", { class: "row" }, h("a", {
				class: "title",
				href: `#/artifact-review/artifact/${row.artifact_id}/${row.revision}`
			}, `${row.display_name || row.artifact_id} · r${row.revision}`), h("code", {}, row.digest))));
			moreArtifacts.hidden = !catalogCursor;
			catalogNotice.replaceChildren();
			if (!rows.size) catalog.append(h("p", { class: "muted" }, t("ar_no_artifacts")));
		})();
		moreArtifacts.disabled = true;
		try {
			await catalogReading;
		} catch (error) {
			if (currentView()) catalogNotice.replaceChildren(errorBox(error));
			throw error;
		} finally {
			catalogReading = null;
			moreArtifacts.disabled = false;
		}
	}
	async function refresh(fresh = false) {
		if (submission) {
			await submission;
			guard();
		}
		if (refreshing) {
			await refreshing;
			if (fresh) return refresh(true);
			return;
		}
		refreshing = (async () => {
			const reads = [];
			if (saved.capture?.operation_id) reads.push(api("GET", `/operations/${saved.capture.operation_id}`).then((data) => adopt("capture", data.operation)));
			else if (context.kind === "artifact") reads.push(loadExactArtifact());
			if (saved.accept?.operation_id) reads.push(api("GET", `/operations/${saved.accept.operation_id}`).then((data) => adopt("accept", data.operation)));
			const outcomes = await Promise.allSettled(reads);
			for (const result of outcomes) if (result.status === "rejected") throw result.reason;
			guard();
			readFailed = false;
			render();
		})();
		update();
		try {
			await refreshing;
		} catch (error) {
			if (currentView()) {
				readFailed = true;
				showError(error);
			}
			throw error;
		} finally {
			refreshing = null;
			if (currentView()) update();
		}
	}
	const off = onEvents(async (event) => {
		if (!currentView()) return;
		const reads = [];
		if (event.resource_id === saved.capture?.operation_id || event.resource_id === saved.accept?.operation_id || event.resource_id === artifact?.artifact_id || context.kind === "artifact" && event.resource_id === context.artifact_id) reads.push(refresh(true));
		if (event.resource_type === "artifact") reads.push(loadCatalog());
		const settled = await Promise.allSettled(reads);
		for (const result of settled) if (result.status === "rejected") throw result.reason;
	});
	if (saved.capture?.expected?.source) source = {
		host: saved.capture.expected.source.host,
		session_id: saved.capture.expected.source.session_id
	};
	renderChoice();
	render();
	const initial = [];
	if (!saved.capture) initial.push(loadSource());
	if (saved.capture?.operation_id || saved.accept?.operation_id || context.kind === "artifact") initial.push(refresh());
	initial.push(loadCatalog().catch((error) => {
		if (currentView()) catalogNotice.replaceChildren(errorBox(error));
	}));
	const results = await Promise.allSettled(initial);
	for (const result of results) if (result.status === "rejected") {
		readFailed = true;
		showError(result.reason);
	}
	if (!source && saved.capture?.expected?.source) {
		source = {
			host: saved.capture.expected.source.host,
			session_id: saved.capture.expected.source.session_id
		};
		renderChoice();
	}
	render();
	const timer = setInterval(() => {
		if (!currentView()) return;
		update();
		if (saved.capture?.operation_id && active("capture") || saved.accept?.operation_id && active("accept")) refresh().catch(showError);
	}, 1e3);
	return () => {
		disposed = true;
		clearInterval(timer);
		content.dispose();
		off();
	};
}
//#endregion
//#region src/state/events.ts
function consumePage(page, cursor, emit) {
	if (page.reset_required || page.reset || page.head_cursor < cursor) {
		emit({
			seq: 0,
			kind: "reset",
			resource_type: "reset"
		});
		cursor = 0;
	}
	for (const event of page.events) {
		if (event.seq <= cursor) continue;
		emit(event);
		cursor = event.seq;
	}
	if (Number.isSafeInteger(page.next_cursor) && page.next_cursor >= cursor && page.next_cursor <= page.head_cursor) cursor = page.next_cursor;
	return cursor;
}
async function consumePageAsync(page, cursor, emit) {
	if (page.reset_required || page.reset || page.head_cursor < cursor) {
		await emit({
			seq: 0,
			kind: "reset",
			resource_type: "reset"
		});
		cursor = 0;
	}
	const pending = [];
	const next = consumePage({
		...page,
		reset: false,
		reset_required: false
	}, cursor, (event) => {
		pending.push(Promise.resolve().then(() => emit(event)));
	});
	await settleRefreshes(pending);
	return next;
}
async function settleRefreshes(pending) {
	const results = await Promise.allSettled(pending);
	for (const result of results) if (result.status === "rejected") throw result.reason;
}
function storageScope(endpoint, actor, server = "legacy", principal = actor) {
	return [
		endpoint,
		server,
		principal,
		actor
	].map(encodeURIComponent).join(":");
}
//#endregion
//#region src/app.js
init_transport();
var TOKEN_KEY = "batc.dashboard.token";
var state = {
	token: null,
	caps: null,
	lastEvent: 0,
	listeners: new Set(),
	namespace: "",
	epoch: 0,
	online: false,
	viewReady: false,
	sync: null,
	endpoint: "",
	connectionError: null,
	nativeBusy: false,
	nativeAttempt: 0,
	connectionNotice: null,
	refreshCycle: null
};
async function activate(caps, endpoint = location.origin, reset = false) {
	state.epoch++;
	state.observations = new Map();
	state.connectionError = null;
	state.online = false;
	state.viewReady = false;
	state.caps = caps;
	state.endpoint = endpoint;
	state.sync = null;
	let bootstrap;
	try {
		bootstrap = await api("GET", "/bootstrap");
	} catch (e) {
		if (nativeDesktop || e.status !== 404) throw e;
	}
	if (bootstrap) {
		const sync = bootstrap.sync;
		if (sync?.version !== 1 || !sync.server_id || !sync.principal_id || !Number.isSafeInteger(sync.checkpoint?.cursor) || sync.checkpoint.cursor < 0 || !sync.checkpoint.token || bootstrap.capabilities?.actor !== caps.actor || caps.desktop_identity && (caps.desktop_identity.server_id !== sync.server_id || caps.desktop_identity.principal_id !== sync.principal_id)) throw new Error("Invalid central bootstrap identity");
		state.caps = bootstrap.capabilities;
		state.namespace = storageScope(endpoint, caps.actor, sync.server_id, sync.principal_id);
		state.sync = sync.checkpoint;
		if (!reset) try {
			const saved = JSON.parse(localStorage.getItem(`batc.sync.${state.namespace}`));
			if (Number.isSafeInteger(saved?.cursor) && saved.cursor >= 0 && typeof saved.token === "string" && saved.token) state.sync = saved;
		} catch {}
		state.lastEvent = state.sync.cursor;
	} else {
		state.namespace = storageScope(endpoint, caps.actor);
		state.lastEvent = 0;
	}
	state.online = true;
}
function saveCursor() {
	if (state.sync) try {
		localStorage.setItem(`batc.sync.${state.namespace}`, JSON.stringify(state.sync));
	} catch {}
}
function disconnect() {
	if (state.token === "managed-browser-session") forgetBrowserSession()?.catch(() => {});
	state.epoch++;
	clearToken();
	state.token = null;
	state.caps = null;
	state.lastEvent = 0;
	state.online = false;
	state.viewReady = false;
	state.sync = null;
}
function loadToken() {
	if (nativeDesktop) return null;
	try {
		return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
	} catch {
		return null;
	}
}
function saveToken(token, remember) {
	if (nativeDesktop) return;
	try {
		sessionStorage.setItem(TOKEN_KEY, token);
		if (remember) localStorage.setItem(TOKEN_KEY, token);
		else localStorage.removeItem(TOKEN_KEY);
	} catch {}
}
function clearToken() {
	try {
		sessionStorage.removeItem(TOKEN_KEY);
		localStorage.removeItem(TOKEN_KEY);
	} catch {}
}
function h(tag, attrs = {}, ...children) {
	const el = document.createElement(tag);
	for (const [k, v] of Object.entries(attrs || {})) {
		if (v === null || v === void 0 || v === false) continue;
		if (k === "class") el.className = v;
		else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
		else el.setAttribute(k, v === true ? "" : String(v));
	}
	for (const c of children.flat()) {
		if (c === null || c === void 0 || c === false) continue;
		el.append(c instanceof Node ? c : document.createTextNode(String(c)));
	}
	if (nativeDesktop && tag === "a" && attrs.href && !attrs.href.startsWith("#")) el.addEventListener("click", async (event) => {
		event.preventDefault();
		try {
			await openExternal(attrs.href);
		} catch (error) {
			document.getElementById("main").prepend(errorBox(error));
		}
	});
	return el;
}
var chip = (text, cls = "") => h("span", { class: `chip ${cls}` }, text);
function when(iso) {
	if (!iso) return "";
	const d = new Date(iso);
	return isNaN(d) ? iso : d.toLocaleString();
}
async function draftId(scope, request) {
	const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(request)));
	return `${scope}.${[...new Uint8Array(digest).slice(0, 12)].map((b) => b.toString(16).padStart(2, "0")).join("")}`;
}
var TERMINAL = [
	"succeeded",
	"failed",
	"cancelled"
];
function assertConnection(connection) {
	if (connection.epoch !== state.epoch || connection.namespace !== state.namespace) throw new ApiError(0, "CONNECTION_CHANGED", "Connection changed while preparing the operation");
}
async function keyFor(scope, connection) {
	assertConnection(connection);
	const k = `batc.key.${connection.namespace}.${scope}`;
	let saved = null;
	try {
		const raw = localStorage.getItem(k);
		try {
			saved = JSON.parse(raw);
		} catch {
			saved = raw ? { key: raw } : null;
		}
	} catch {
		saved = null;
	}
	if (saved?.key && saved.op) try {
		const op = (await api("GET", `/operations/${saved.op}`)).operation;
		assertConnection(connection);
		if (TERMINAL.includes(op.status)) saved = null;
	} catch (e) {
		if (e.code === "CONNECTION_CHANGED") throw e;
		if (e.status === 404) saved = null;
	}
	assertConnection(connection);
	if (saved?.key) return saved.key;
	const key = crypto.randomUUID();
	try {
		localStorage.setItem(k, JSON.stringify({ key }));
	} catch {}
	return key;
}
function rememberOp(scope, key, op, namespace) {
	try {
		localStorage.setItem(`batc.key.${namespace}.${scope}`, JSON.stringify({
			key,
			op
		}));
	} catch {}
}
function dropKey(scope, namespace) {
	try {
		localStorage.removeItem(`batc.key.${namespace}.${scope}`);
	} catch {}
}
var ApiError = class extends Error {
	constructor(status, code, message) {
		super(message || code);
		this.status = status;
		this.code = code;
	}
};
async function api(method, path, body, key) {
	if (!state.token) throw new ApiError(401, "UNAUTHORIZED", t("need_token"));
	if (method === "POST" && (state.nativeBusy || !state.online || !state.viewReady)) throw new ApiError(0, "CENTRAL_OFFLINE", t("offline_actions_paused"));
	const epoch = state.epoch;
	const { status, data } = await connectorRequest(method, path, body, key, state.token);
	if (epoch !== state.epoch) throw new ApiError(0, "CONNECTION_CHANGED", "Connection changed while the request was in flight");
	if (status < 200 || status >= 300) throw new ApiError(status, data.error?.code, data.error?.message);
	return data;
}
function errorBox(e) {
	if (state.refreshCycle) state.refreshCycle.error ||= e;
	return h("p", { class: "error" }, e.status === 403 && e.code === "FORBIDDEN" ? t("forbidden_scope") : `${e.code || ""} ${e.message || e}`);
}
async function submit(action, target, params, preconditions, scope) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace
	};
	const request = {
		action,
		target,
		params,
		preconditions
	};
	scope = await draftId(scope, request);
	assertConnection(connection);
	const key = await keyFor(scope, connection);
	assertConnection(connection);
	try {
		const out = await api("POST", "/operations?wait=3", request, key);
		assertConnection(connection);
		if (TERMINAL.includes(out.operation.status)) dropKey(scope, connection.namespace);
		else rememberOp(scope, key, out.operation.operation_id, connection.namespace);
		return out.operation;
	} catch (e) {
		if (e.status && e.status < 500 && e.status !== 409) dropKey(scope, connection.namespace);
		throw e;
	}
}
function manualCapture(scope, source = {}, onAttach) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	return capturePanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		onEvents,
		errorBox,
		storageKey: `batc.capture.${connection.namespace}.${scope}`,
		source,
		onAttach
	});
}
function attachmentDraft(scope, text, initial = [], roles = false, onChange = () => {}) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const key = `batc.draft.${connection.namespace}.${scope}`;
	let saved;
	try {
		saved = JSON.parse(localStorage.getItem(key));
	} catch {}
	saved = saved && typeof saved === "object" ? saved : {
		text: text.value,
		attachments: initial.map((ref) => ({
			name: ref.artifact_id,
			ref: { ...ref }
		}))
	};
	if (!Array.isArray(saved.attachments)) saved.attachments = [];
	saved.attachments = saved.attachments.filter((a) => a && typeof a === "object");
	for (const a of saved.attachments) delete a.busy;
	if (typeof saved.text === "string") text.value = saved.text;
	const files = new Map(), rows = h("div", { class: "attachment-list" });
	let pendingSelections = 0;
	const changed = () => queueMicrotask(() => {
		if (box.isConnected && connection.epoch === state.epoch && connection.generation === generation) onChange();
	});
	const status = h("p", {
		class: "muted",
		role: "status"
	});
	const supported = Boolean(state.caps?.artifacts), nativeFiles = nativeDesktop && nativeFileSupport;
	const nativeUploadAllowed = state.caps?.actions?.some((a) => a.action === "artifact.upload" && a.allowed === true);
	let native;
	const choose = nativeFiles ? h("button", {
		class: "secondary",
		disabled: !supported || !may("manage") || !nativeUploadAllowed,
		onclick: () => native.pick()
	}, t("files_choose")) : h("input", {
		type: "file",
		multiple: true,
		disabled: !supported || !may("manage"),
		"aria-label": t("choose_attachments")
	});
	const box = h("div", {
		class: "attachments",
		hidden: !supported
	}, nativeFiles ? h("div", { class: "actions" }, h("strong", {}, t("attachments")), choose) : h("label", {}, t("attachments"), choose), h("p", { class: "muted" }, t(nativeFiles ? "files_help" : "upload_on_choose")), rows, status);
	const guard = (mounted = false) => {
		assertView(connection);
		if (mounted && !box.isConnected) throw new ApiError(0, "VIEW_CHANGED", "Attachment form changed during the request");
	};
	const persist = () => {
		guard();
		saved.text = text.value;
		try {
			localStorage.setItem(key, JSON.stringify(saved));
		} catch {}
		changed();
	};
	const removeStored = () => {
		guard();
		try {
			localStorage.removeItem(key);
		} catch {}
	};
	text.addEventListener("input", persist);
	const refs = () => saved.attachments.filter((a) => a.ref).map((a) => roles ? {
		...a.ref,
		role: a.ref.role || "input"
	} : {
		artifact_id: a.ref.artifact_id,
		revision: a.ref.revision,
		digest: a.ref.digest
	});
	const snapshot = () => JSON.stringify({
		text: text.value,
		attachments: refs(),
		fields: saved.fields
	});
	const ready = () => pendingSelections === 0 && saved.attachments.every((a) => a.ref);
	const render = () => {
		changed();
		return fill(rows, ...saved.attachments.filter((a) => !nativeFiles || !a.native_handle || a.ref || !native?.has(a.native_handle)).map((a) => h("div", { class: "row" }, h("div", { class: "grow" }, a.name, a.ref ? h("div", { class: "muted" }, `${a.ref.artifact_id} · r${a.ref.revision} · ${a.ref.digest.slice(0, 12)}`) : h("div", { class: "muted" }, a.error || (a.native_handle ? t("files_unavailable") : files.has(a) ? t("uploading") : t("choose_again")))), a.ref && roles ? h("select", {
			"aria-label": t("attachment_role"),
			onchange: (e) => {
				guard();
				a.ref.role = e.target.value;
				persist();
			}
		}, ...["input", "result"].map((role) => h("option", {
			value: role,
			selected: (a.ref.role || "input") === role
		}, t(`attachment_${role}`)))) : null, a.ref && native ? native.actions(a.ref) : null, !a.ref && files.has(a) && !a.busy ? h("button", {
			class: "secondary",
			onclick: () => upload(a)
		}, t("retry")) : null, h("button", {
			class: "secondary",
			disabled: a.busy,
			onclick: () => {
				guard();
				if (a.native_handle) {
					saved.native_ignored ||= [];
					saved.native_ignored.push(a.native_handle);
				}
				saved.attachments = saved.attachments.filter((x) => x !== a);
				files.delete(a);
				persist();
				render();
			}
		}, t("remove")))));
	};
	if (nativeFiles) {
		if (!Array.isArray(saved.native_ignored)) saved.native_ignored = [];
		saved.native_ignored = saved.native_ignored.filter((id) => typeof id === "string" && /^file_[0-9a-f]{32}$/.test(id));
		if (typeof saved.native_draft !== "string" || !/^[0-9a-f-]{36}$/.test(saved.native_draft)) saved.native_draft = saved.attachments.find((a) => typeof a.native_receipt?.draft_id === "string" && /^[0-9a-f-]{36}$/.test(a.native_receipt.draft_id))?.native_receipt.draft_id || crypto.randomUUID();
		native = nativeAttachments({
			h,
			t,
			guard: () => guard(true),
			canWrite: () => state.online && state.viewReady && may("manage") && nativeUploadAllowed,
			draftId: saved.native_draft,
			onVisibility: render,
			onDiscard: (id) => {
				guard(true);
				saved.attachments = saved.attachments.filter((a) => a.native_handle !== id || a.ref);
				persist();
				render();
			},
			attached: (id) => saved.attachments.some((a) => a.native_handle === id && a.ref) || saved.native_ignored?.includes(id),
			onReceipt: (receipt) => {
				guard(true);
				if (saved.native_ignored?.includes(receipt.transfer_id)) return;
				let a = saved.attachments.find((a) => a.native_handle === receipt.transfer_id);
				if (a?.native_receipt && [
					"intent_key",
					"display_name",
					"size_bytes",
					"digest"
				].some((field) => a.native_receipt[field] !== receipt[field])) throw new Error(t("files_receipt_mismatch"));
				if (a && JSON.stringify(a.native_receipt) === JSON.stringify(receipt)) return;
				if (!a) {
					a = {
						name: receipt.display_name,
						native_handle: receipt.transfer_id
					};
					saved.attachments.push(a);
				}
				a.native_receipt = receipt;
				if (receipt.stage === "ready") a.ref = {
					...receipt.artifact,
					...roles ? { role: a.ref?.role || "input" } : {}
				};
				persist();
				render();
			}
		});
		choose.after(native.drop);
		box.insertBefore(native.box, rows);
		persist();
	}
	const acceptUpload = (a, op) => {
		if (op.status !== "succeeded") return;
		a.ref = {
			artifact_id: op.result.artifact_id,
			revision: op.result.revision,
			digest: op.result.digest,
			...roles ? { role: "input" } : {}
		};
		delete a.operation_id;
		delete a.key;
		delete a.error;
		delete a.request;
		files.delete(a);
		persist();
		render();
	};
	const upload = async (a) => {
		if (a.busy) return;
		guard();
		a.busy = true;
		delete a.error;
		render();
		try {
			const file = files.get(a), limit = Math.min(state.caps.artifacts.limits.max_file_bytes, nativeDesktop ? 16777216 : Number.MAX_SAFE_INTEGER);
			if (file.size > limit) throw new Error(`ARTIFACT_TOO_LARGE (${limit})`);
			const bytes = await file.arrayBuffer();
			guard(true);
			const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((x) => x.toString(16).padStart(2, "0")).join("");
			guard(true);
			const request = {
				action: "artifact.upload",
				target: {},
				params: {
					display_name: file.name,
					media_type: file.type || "application/octet-stream",
					size_bytes: file.size,
					expected_digest: digest
				},
				preconditions: {}
			};
			if (a.request && JSON.stringify(a.request) !== JSON.stringify(request)) throw new Error(t("attachment_file_changed"));
			a.request ||= request;
			a.key ||= crypto.randomUUID();
			persist();
			let op = a.operation_id ? (await api("GET", `/operations/${a.operation_id}`)).operation : null;
			guard(true);
			if (op && ["failed", "cancelled"].includes(op.status)) {
				op = null;
				a.key = crypto.randomUUID();
				delete a.operation_id;
				persist();
			}
			if (!op) op = (await api("POST", "/operations?wait=3", a.request, a.key)).operation;
			guard(true);
			a.operation_id = op.operation_id;
			persist();
			const deadline = Date.now() + 6e4;
			const readNext = async () => {
				if (Date.now() > deadline) throw new Error(t("attachment_pending"));
				await sleep(400);
				guard(true);
				const next = (await api("GET", `/operations/${op.operation_id}`)).operation;
				guard(true);
				return next;
			};
			while (["accepted", "running"].includes(op.status)) op = await readNext();
			if (op.status === "waiting_external") {
				if (!state.online || !state.viewReady) throw new ApiError(0, "CENTRAL_OFFLINE", t("offline_actions_paused"));
				const epoch = state.epoch;
				const response = await connectorUploadArtifact(op.operation_id, bytes, state.token);
				guard(true);
				if (epoch !== state.epoch) throw new ApiError(0, "CONNECTION_CHANGED", "Connection changed during upload");
				if (response.status < 200 || response.status >= 300) throw new ApiError(response.status, response.data.error?.code, response.data.error?.message);
				do
					op = await readNext();
				while ([
					"accepted",
					"running",
					"waiting_external"
				].includes(op.status));
			}
			if (op.status !== "succeeded") throw new Error(`${op.error_code || op.status}: ${op.status_reason || ""}`);
			acceptUpload(a, op);
		} catch (e) {
			if (connection.epoch !== state.epoch || connection.generation !== generation || !box.isConnected) return;
			a.error = e.message;
		} finally {
			delete a.busy;
			if (connection.epoch === state.epoch && connection.generation === generation && box.isConnected) {
				persist();
				render();
			}
		}
	};
	if (!nativeFiles) choose.onchange = () => {
		guard();
		for (const file of choose.files) {
			let a = saved.attachments.find((x) => !x.ref && !files.has(x) && x.name === file.name);
			if (!a) {
				a = { name: file.name };
				saved.attachments.push(a);
			}
			files.set(a, file);
			upload(a);
		}
		choose.value = "";
		persist();
		render();
	};
	const existing = h("select", { "aria-label": t("existing_artifact") }, h("option", { value: "" }, t("existing_artifact")));
	box.append(h("div", { class: "actions" }, existing, h("button", {
		class: "secondary",
		onclick: async () => {
			if (!existing.value) return;
			const [artifactId, revision] = existing.value.split(":");
			pendingSelections++;
			changed();
			try {
				guard();
				const { artifact } = await api("GET", `/artifacts/${artifactId}/revisions/${revision}`);
				guard(true);
				if (artifact.state !== "ready") throw new Error(t("attachments_not_ready"));
				if (!saved.attachments.some((a) => a.ref?.artifact_id === artifactId && a.ref?.revision === Number(revision))) saved.attachments.push({
					name: artifact.display_name,
					ref: {
						artifact_id: artifactId,
						revision: Number(revision),
						digest: artifact.digest,
						...roles ? { role: "input" } : {}
					}
				});
				persist();
				render();
			} catch (e) {
				if (connection.epoch === state.epoch) fill(status, errorBox(e));
			} finally {
				pendingSelections--;
				changed();
			}
		}
	}, t("add_attachment"))));
	let catalogCursor = null;
	const more = h("button", {
		class: "secondary",
		hidden: true,
		onclick: async () => {
			more.disabled = true;
			try {
				await loadCatalog(catalogCursor);
			} catch (e) {
				if (box.isConnected) fill(status, errorBox(e));
			} finally {
				more.disabled = false;
			}
		}
	}, t("more"));
	box.append(more);
	if (state.caps?.artifacts?.capture?.manual_single_file) box.append(manualCapture(scope, {}, (ref, name) => {
		guard(true);
		if (!saved.attachments.some((a) => a.ref?.artifact_id === ref.artifact_id && a.ref?.revision === ref.revision)) saved.attachments.push({
			name,
			ref: {
				...ref,
				...roles ? { role: "input" } : {}
			}
		});
		persist();
		render();
	}));
	const loadCatalog = async (cursor = "") => {
		const page = await api("GET", `/artifacts?limit=200${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
		guard(true);
		const selected = existing.value, selectedOption = existing.selectedOptions[0];
		if (!cursor) existing.replaceChildren(h("option", { value: "" }, t("existing_artifact")));
		for (const { revision: r } of page.artifacts) if (r?.state === "ready" && ![...existing.options].some((o) => o.value === `${r.artifact_id}:${r.revision}`)) existing.append(h("option", { value: `${r.artifact_id}:${r.revision}` }, `${r.display_name} · r${r.revision} · ${r.artifact_id.slice(-8)}`));
		if (selected && ![...existing.options].some((o) => o.value === selected)) existing.append(selectedOption);
		existing.value = selected;
		catalogCursor = page.next_cursor;
		more.hidden = !catalogCursor;
	};
	const settleSubmission = (op) => {
		guard(true);
		if (!saved.submission || !TERMINAL.includes(op.status)) return;
		const unchanged = saved.submission.snapshot === snapshot();
		delete saved.submission;
		if (op.status === "succeeded" && unchanged) {
			text.value = "";
			saved.attachments = [];
			saved.fields = void 0;
			removeStored();
			render();
		} else persist();
	};
	const perform = async (action, target, params, preconditions, requestScope) => {
		guard(true);
		const request = {
			action,
			target,
			params,
			preconditions
		};
		if (saved.submission?.refused && JSON.stringify(saved.submission.request) !== JSON.stringify(request)) delete saved.submission;
		if (!saved.submission) {
			saved.submission = {
				request: structuredClone({
					action,
					target,
					params,
					preconditions
				}),
				key: crypto.randomUUID(),
				snapshot: snapshot(),
				scope: requestScope
			};
			persist();
		}
		const intent = saved.submission;
		try {
			const op = intent.operation_id ? (await api("GET", `/operations/${intent.operation_id}`)).operation : (await api("POST", "/operations?wait=3", intent.request, intent.key)).operation;
			guard(true);
			intent.operation_id = op.operation_id;
			persist();
			settleSubmission(op);
			return op;
		} catch (error) {
			if (connection.epoch === state.epoch && connection.generation === generation && error.status >= 400 && error.status < 500 && error.code !== "IDEMPOTENCY_CONFLICT") {
				intent.refused = true;
				persist();
			}
			throw error;
		}
	};
	const refresh = async () => {
		guard(true);
		const pending = saved.attachments.filter((a) => !a.ref && a.operation_id);
		await settleRefreshes([
			...native ? [native.refresh()] : [],
			...pending.map(async (a) => {
				const { operation } = await api("GET", `/operations/${a.operation_id}`);
				guard(true);
				acceptUpload(a, operation);
			}),
			...saved.submission?.operation_id ? [(async () => {
				const { operation } = await api("GET", `/operations/${saved.submission.operation_id}`);
				guard(true);
				settleSubmission(operation);
			})()] : []
		]);
	};
	if (supported) {
		const unsub = onEvents((ev) => {
			if (!box.isConnected || connection.epoch !== state.epoch) {
				unsub();
				return;
			}
			if (ev.resource_type === "artifact") return settleRefreshes([refresh(), loadCatalog()]);
			if (ev.resource_id === saved.submission?.operation_id || saved.attachments.some((a) => a.operation_id === ev.resource_id)) return refresh();
		});
		queueMicrotask(() => settleRefreshes([loadCatalog(), refresh()]).catch((e) => {
			if (box.isConnected && connection.epoch === state.epoch) fill(status, errorBox(e));
		}));
	}
	const bindFields = (fields) => {
		for (const [name, field] of Object.entries(fields)) {
			if (typeof saved.fields?.[name] === "string") field.value = saved.fields[name];
			field.addEventListener("input", () => {
				guard();
				saved.fields = Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.value]));
				persist();
			});
		}
	};
	render();
	return {
		box,
		refs,
		ready,
		perform,
		bindFields,
		pending: () => Boolean(saved.submission),
		reset: () => {
			guard(true);
			if (!ready()) throw new Error(t("attachments_not_ready"));
			const ignored = [...saved.native_ignored || [], ...saved.attachments.map((a) => a.native_handle).filter(Boolean)];
			saved = {
				text: "",
				attachments: [],
				native_draft: saved.native_draft,
				native_ignored: ignored
			};
			text.value = "";
			files.clear();
			persist();
			render();
		}
	};
}
function onEvents(fn) {
	state.listeners.add(fn);
	return () => state.listeners.delete(fn);
}
var onlineListeners = new Set();
function onOnline(fn) {
	onlineListeners.add(fn);
	return () => onlineListeners.delete(fn);
}
function updateOnline(value) {
	state.online = value;
	for (const fn of onlineListeners) fn();
}
async function streamEvents() {
	const live = document.getElementById("live");
	for (;;) {
		if (state.nativeBusy || !state.token || !state.viewReady) {
			live.className = "live down";
			live.textContent = state.token ? t("sync_waiting") : "";
			await sleep(1e3);
			continue;
		}
		const epoch = state.epoch, view = generation;
		let cycle;
		try {
			const before = state.lastEvent;
			const page = await api("GET", `/events?after=${before}&limit=100${state.sync ? `&checkpoint=${encodeURIComponent(state.sync.token)}` : ""}`);
			if (epoch !== state.epoch || view !== generation || !state.viewReady) continue;
			cycle = { error: null };
			state.refreshCycle = cycle;
			live.className = "live down";
			live.textContent = t("sync_waiting");
			const cursor = await consumePageAsync(page, before, (ev) => {
				return settleRefreshes([...state.listeners].map((fn) => Promise.resolve().then(() => fn(ev))));
			});
			if (epoch !== state.epoch || view !== generation || !state.viewReady) continue;
			if (cycle.error) throw cycle.error;
			if (state.sync) {
				if (page.sync?.checkpoint?.cursor !== cursor || !page.sync?.checkpoint?.token) throw new Error("Invalid central event checkpoint");
				state.sync = page.sync.checkpoint;
			}
			state.lastEvent = cursor;
			saveCursor();
			state.refreshCycle = null;
			updateOnline(true);
			live.className = "live ok";
			live.textContent = t("desktop_polling");
			if (!page.has_more || cursor <= before) await sleep(1e3);
		} catch (error) {
			if (epoch !== state.epoch || view !== generation) continue;
			if (state.refreshCycle === cycle) state.refreshCycle = null;
			updateOnline(false);
			live.className = "live down";
			live.textContent = t("offline_actions_paused");
			if (error.code === "EVENT_CURSOR_RESET") {
				const previous = {
					namespace: state.namespace,
					sync: state.sync
				};
				try {
					await activate(state.caps, state.endpoint, true);
					if (state.namespace === previous.namespace && (editing || typing())) idleReload = route;
					else await route();
				} catch {
					state.sync = previous.sync;
					state.viewReady = true;
				}
			}
			await sleep(3e3);
		} finally {
			if (state.refreshCycle === cycle) state.refreshCycle = null;
		}
	}
}
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function debounce(fn, ms) {
	let id;
	return () => {
		clearTimeout(id);
		id = setTimeout(fn, ms);
	};
}
function assertView(connection) {
	assertConnection(connection);
	if (connection.generation !== generation) throw new ApiError(0, "VIEW_CHANGED", "View changed during refresh");
}
function debounceRefresh(fn, ms) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	let id, waiting = [];
	return () => new Promise((resolve, reject) => {
		waiting.push({
			resolve,
			reject
		});
		clearTimeout(id);
		id = setTimeout(async () => {
			const batch = waiting;
			waiting = [];
			try {
				assertView(connection);
				await fn();
				assertView(connection);
				batch.forEach((p) => p.resolve());
			} catch (error) {
				batch.forEach((p) => p.reject(error));
			}
		}, ms);
	});
}
function rememberObservation(type, id, value, dependencies = []) {
	state.observations ||= new Map();
	state.observations.set(`${type}:${id}`, {
		value,
		dependencies: new Set(dependencies)
	});
}
function observationAffected(type, id, event) {
	const key = `${event.resource_type}:${event.resource_id}`;
	return key === `${type}:${id}` || state.observations?.get(`${type}:${id}`)?.dependencies.has(key);
}
function itemDependencies(data) {
	return [
		`project:${data.project.project_id}`,
		...[
			...data.path || [],
			...data.children || [],
			...data.derived || []
		].map((item) => `work_item:${item.work_item_id}`),
		...(data.links || []).flatMap((link) => {
			const related = [`${link.kind}:${link.ref}`];
			if (link.kind === "task") related.push(`execution:${link.ref}`);
			if (link.target?.session) related.push(`session:${link.target.session.host}/${link.target.session.session_id}`);
			return related;
		})
	];
}
function confinementLabel(s) {
	const level = s.confinement?.level || "none";
	return t(level === "os_sandbox" && s.confinement?.verification?.status !== "verified" ? "confinement_os_pending" : "confinement_" + level);
}
function confinementNote(host, agent) {
	const note = h("p", {
		class: "muted",
		"data-confinement-note": ""
	});
	const update = () => {
		const account = state.caps?.hosts?.find((x) => x.host === host)?.confinement?.host_account;
		const effect = account?.start_effect;
		if (effect === "refused") {
			note.textContent = t("confinement_account_blocked", { reason: account.reason });
			if (agent.value === "codex") note.textContent += " " + t("confinement_codex_note");
		} else if (agent.value === "codex") note.textContent = t("confinement_codex_note");
		else if (effect === "verified") note.textContent = t("confinement_account_note");
		else if (effect === "recheck") note.textContent = t("confinement_account_recheck");
		else note.textContent = (effect === "fallback_default" && account?.declared ? t("confinement_account_fallback", { reason: account.reason }) + " " : "") + t("confinement_claude_note");
	};
	agent.addEventListener("change", update);
	note.setHost = (value) => {
		host = value;
		update();
	};
	update();
	return note;
}
function confinementDetails(s) {
	const record = s.confinement;
	const current = s.current_verification;
	return h("details", {}, h("summary", {}, t("confinement_evidence")), h("p", { class: "muted" }, t("confined_note")), h("dl", { class: "kv" }, h("dt", {}, t("confinement_creation")), h("dd", {}, confinementLabel(s)), h("dt", {}, t("confinement_current")), h("dd", {}, t("confinement_status_" + (current?.status || "unknown"))), h("dt", {}, t("confinement_options")), h("dd", {}, h("code", {}, JSON.stringify(record?.options || {}))), h("dt", {}, t("confinement_evidence")), h("dd", {}, h("code", {}, JSON.stringify(record?.evidence || {}))), h("dt", {}, t("confinement_gap")), h("dd", {}, record?.gap ? t("confinement_gap_" + record.gap) : t("none")), h("dt", {}, t("confinement_current")), h("dd", {}, h("code", {}, JSON.stringify(current || { status: "unknown" })))));
}
function sessionBadges(s) {
	return [
		chip(s.host),
		chip(confinementLabel(s), s.confinement?.level === "none" ? "readonly" : "info"),
		s.confinement?.level && s.confinement.level !== "none" && ["unknown", "mismatch"].includes(s.current_verification?.status) ? chip(t("confinement_current_" + s.current_verification.status), "stale") : null,
		s.api_access === "managed" ? chip(t("managed"), "managed") : chip(t("read_only"), "readonly"),
		s.stale ? chip(`${t("stale")} · ${t("stale_reason_" + s.stale_reason)}`, "stale") : null,
		s.pending ? chip(t("pending_" + s.pending.kind), "stale") : null
	];
}
function light(s) {
	return h("span", {
		class: `light ${s.pending ? "pending" : s.streaming ? "streaming" : s.loaded ? "ok" : ""}`,
		title: s.streaming ? t("state_streaming") : s.loaded ? t("state_loaded") : t("state_unloaded")
	});
}
function sessionRow(s) {
	return h("div", { class: "row" }, light(s), h("div", { class: "grow" }, h("a", {
		class: "title",
		href: `#/session/${encodeURIComponent(s.host)}/${encodeURIComponent(s.session_id)}`
	}, s.title || s.session_id), h("div", { class: "muted" }, [
		s.workspace,
		s.agent_kind,
		s.worktree_branch
	].filter(Boolean).join(" · "))), h("div", { class: "actions session-badges" }, ...sessionBadges(s)), h("span", { class: "muted" }, when(s.last_activity_at)));
}
var epoch = (x) => x ? new Date(x * 1e3).toISOString() : "";
function opStatus(op) {
	const started = op.status === "succeeded" && ["session.start", "repository.continue"].includes(op.action);
	return h("span", { class: `status-${op.status}` }, t(started ? "start_dispatched" : "op_" + op.status));
}
function opRow(op) {
	return h("div", { class: "row" }, h("div", { class: "grow" }, h("a", {
		class: "title",
		href: `#/op/${op.operation_id}`
	}, op.action), h("div", { class: "muted" }, [op.actor, when(epoch(op.created_at))].join(" · ")), op.status_reason ? h("div", { class: "muted" }, op.status_reason) : null), opStatus(op), op.error_code ? chip(op.error_code, "bad") : null);
}
async function viewHome(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	return attentionView({
		main,
		h,
		t,
		api,
		caps: state.caps,
		storageKey: `batc.attention.${connection.namespace}`,
		guard: () => assertView(connection),
		route,
		onEvents,
		debounceRefresh,
		errorBox,
		sessionRow,
		workItemRow,
		opRow
	});
}
async function viewSessions(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const storageKey = `batc.sessions.${connection.namespace}`;
	const q = new URLSearchParams(sessionStorage.getItem(storageKey) || "");
	const hostSel = h("select", { "aria-label": t("host") }, h("option", { value: "" }, t("all_hosts")));
	const accessSel = h("select", { "aria-label": t("all_access") }, h("option", { value: "" }, t("all_access")), h("option", { value: "managed" }, t("only_managed")), h("option", { value: "read_only" }, t("only_read_only")));
	const search = h("input", {
		type: "search",
		"aria-label": t("sessions_search"),
		placeholder: t("sessions_search")
	});
	search.value = q.get("search") || "";
	let selected = q.get("workspace") || "", cursor = null, pages = 1, serial = Promise.resolve(), revision = 0;
	const rows = new Map(), expanded = new Set();
	const list = h("div", { class: "session-inventory" }), status = h("div", {}), count = h("p", {
		class: "muted",
		"aria-live": "polite"
	});
	const more = h("button", {
		class: "secondary",
		hidden: true
	}, t("load_more"));
	const navigation = h("nav", {
		"aria-label": t("sessions_workspaces"),
		class: "session-workspaces"
	});
	const scope = h("details", {
		class: "panel session-scope",
		open: matchMedia("(min-width: 901px)").matches
	}, h("summary", {}, t("sessions_workspaces")), h("p", { class: "muted" }, t("sessions_scope_note")), navigation, h("a", {
		class: "session-project-link",
		href: "#/projects"
	}, t("sessions_projects")));
	main.append(h("div", { class: "session-heading" }, h("h1", {}, t("sessions_title")), state.caps?.actions?.some((a) => a.action === "session.start") ? h("a", { href: "#/start" }, t("start_title_page")) : null, state.caps?.features?.repository_sync?.length ? h("a", { href: "#/published" }, t("pub_title")) : null, state.caps?.actions?.some((a) => Object.values(orchestrationActions).includes(a.action)) ? h("a", { href: "#/orchestrate/relay" }, t("orch_title")) : null), h("p", { class: "muted" }, t("sessions_intro")), h("div", { class: "filters session-filters" }, search, hostSel, accessSel, state.caps?.actions?.some((a) => a.action === "session.approve_pending") ? h("a", { href: "#/approvals" }, t("bulk_title")) : null), status, h("div", { class: "session-layout" }, scope, h("section", {
		"aria-label": t("sessions_title"),
		class: "session-results"
	}, count, list, h("div", { class: "session-pagination" }, more, h("span", { class: "muted" }, t("sessions_page_note"))))));
	try {
		const hosts = (await api("GET", "/hosts")).hosts;
		assertView(connection);
		for (const x of hosts) hostSel.append(h("option", { value: x.host }, x.host));
	} catch (e) {
		status.replaceChildren(errorBox(e));
		return;
	}
	hostSel.value = q.get("host") || "";
	accessSel.value = q.get("access") || "";
	const save = () => {
		assertView(connection);
		const values = new URLSearchParams({
			host: hostSel.value,
			access: accessSel.value,
			search: search.value,
			workspace: selected
		});
		sessionStorage.setItem(storageKey, values.toString());
	};
	const row = (session) => {
		const id = `${session.host}/${session.session_id}`, activity = sessionActivity(session);
		const origin = session.provenance === "manual" ? "sessions_manual" : session.provenance === "connector_managed" ? "sessions_connector" : "sessions_origin_unknown";
		const access = session.api_access === "managed" ? "managed" : session.api_access === "read_only" ? "read_only" : "sessions_access_unknown";
		const evidence = () => [
			h("dl", { class: "kv" }, h("dt", {}, t("sessions_label")), h("dd", {}, session.title || session.session_id), h("dt", {}, t("sessions_workspace")), h("dd", {}, session.workspace || t("sessions_workspace_unknown")), h("dt", {}, t("sessions_workspace_id")), h("dd", {}, h("code", {}, session.workspace_id || t("obs_unknown"))), h("dt", {}, t("sessions_id")), h("dd", {}, h("code", {}, session.session_id)), h("dt", {}, t("activity")), h("dd", {}, observationTime(session.last_activity_at)), h("dt", {}, t("observed")), h("dd", {}, observationTime(session.observed_at))),
			h("p", { class: "muted" }, confinementLabel(session)),
			confinementDetails(session),
			observationState(session)
		];
		const details = h("details", {
			class: "session-row-details",
			open: expanded.has(id)
		}, h("summary", {}, t("sessions_details")));
		let mounted = false;
		const mountEvidence = () => {
			if (!mounted) {
				details.append(...evidence());
				mounted = true;
			}
		};
		if (expanded.has(id)) mountEvidence();
		details.addEventListener("toggle", () => {
			if (!details.isConnected) return;
			if (details.open) {
				expanded.add(id);
				mountEvidence();
			} else expanded.delete(id);
		});
		return h("article", {
			class: "session-entry",
			"data-resource-id": id
		}, h("div", { class: "session-entry-heading" }, h("a", {
			class: "title",
			title: session.title || session.session_id,
			href: `#/session/${encodeURIComponent(session.host)}/${encodeURIComponent(session.session_id)}`
		}, session.title || session.session_id), chip(t(activity.key), activity.tone)), h("div", { class: "session-entry-meta" }, h("span", { class: session.api_access === "managed" ? "" : "session-readonly" }, session.provenance === "connector_managed" && session.api_access === "managed" ? t(access) : `${t(origin)} · ${t(access)}`), h("span", {}, [session.agent_kind, session.worktree_branch].filter(Boolean).join(" · "))), runtimeStale(session) ? h("p", { class: "session-stale muted" }, t("sessions_stale"), " · ", session.stale_reason === "gone" ? t("sessions_not_seen") : session.stale_reason ? t("stale_reason_" + session.stale_reason) : t("sessions_runtime_stale")) : null, validLabels(session.connector_metadata?.labels) && session.connector_metadata.labels.length ? h("div", {
			class: "actions session-entry-meta",
			"aria-label": t("labels_title")
		}, ...session.connector_metadata.labels.slice(0, 2).map((v) => chip(v)), session.connector_metadata.labels.length > 2 ? h("span", {
			class: "muted",
			title: session.connector_metadata.labels.join(" · ")
		}, `+${session.connector_metadata.labels.length - 2}`) : null) : null, details);
	};
	const render = () => {
		assertView(connection);
		const groups = groupedSessions([...rows.values()]);
		const choose = (key) => {
			selected = key;
			save();
			render();
		};
		const workspaceName = (group) => group.name || group.id || t("sessions_workspace_unknown");
		const navButton = (label, key, n) => h("button", {
			class: "session-scope-button",
			"aria-pressed": String(selected === key),
			"data-workspace-key": key,
			title: label,
			onclick: () => choose(key)
		}, h("span", {}, label), h("span", { class: "muted" }, t("sessions_loaded_count", { count: n })));
		const links = [navButton(t("sessions_all_loaded"), "", rows.size)];
		const labels = new Map();
		const labelKey = (group) => JSON.stringify([group.host, workspaceName(group)]);
		for (const group of groups) labels.set(labelKey(group), (labels.get(labelKey(group)) || 0) + 1);
		let lastHost;
		for (const group of groups) {
			if (group.host !== lastHost) {
				links.push(h("a", {
					class: "session-host-link",
					href: `#/host/${encodeURIComponent(group.host)}`,
					title: t("obs_discovery")
				}, group.host));
				lastHost = group.host;
			}
			const sameName = labels.get(labelKey(group)) > 1;
			links.push(navButton(workspaceName(group) + (sameName && group.id ? ` · ${group.id}` : ""), group.key, group.sessions.length));
		}
		if (selected && !groups.some((group) => group.key === selected)) links.push(navButton(t("sessions_scope_missing"), selected, 0));
		const focusedKey = navigation.contains(document.activeElement) ? document.activeElement.dataset.workspaceKey : void 0;
		navigation.replaceChildren(...links);
		if (focusedKey !== void 0) [...navigation.querySelectorAll("button")].find((button) => button.dataset.workspaceKey === focusedKey)?.focus({ preventScroll: true });
		let visible = 0;
		const sections = groups.filter((group) => !selected || selected === group.key).flatMap((group) => {
			const sessions = group.sessions.filter((session) => matchesSession(session, search.value));
			if (!sessions.length) return [];
			visible += sessions.length;
			return [h("section", { class: "panel session-group" }, h("header", { class: "session-group-heading" }, h("h2", { title: workspaceName(group) }, workspaceName(group)), h("span", { class: "muted" }, group.host), group.name && group.id && labels.get(labelKey(group)) > 1 ? h("code", { class: "muted" }, group.id) : null, group.name && !group.id ? h("span", { class: "muted" }, t("sessions_workspace_unverified")) : null), ...sessions.map(row))];
		});
		list.replaceChildren(...sections.length ? sections : [h("div", { class: "panel" }, h("p", {}, t("sessions_no_matches")), h("p", { class: "muted" }, cursor ? t("sessions_more_hint") : t("sessions_empty_hint")))]);
		count.textContent = t("sessions_showing", {
			shown: visible,
			loaded: rows.size
		});
	};
	const read = async (mode, expectedRevision) => {
		if (expectedRevision !== revision) return;
		const p = new URLSearchParams({
			limit: "50",
			order: "id",
			include_gone: "true"
		});
		if (hostSel.value) p.set("host", hostSel.value);
		if (accessSel.value) p.set("access", accessSel.value);
		save();
		more.disabled = true;
		try {
			assertView(connection);
			const before = scrollY, anchor = [...list.querySelectorAll("[data-resource-id]")].find((node) => node.getBoundingClientRect().bottom > 110);
			const anchorID = anchor?.dataset.resourceId, offset = anchor?.getBoundingClientRect().top;
			const observed = new Map(mode === "more" ? rows : []);
			let next = mode === "more" ? cursor : null;
			const total = mode === "refresh" ? pages : 1;
			let readPages = 0;
			for (let page = 0; page < total; page++) {
				const query = new URLSearchParams(p);
				if (next) query.set("cursor", next);
				const result = await api("GET", `/sessions?${query}`);
				assertView(connection);
				if (expectedRevision !== revision) return;
				for (const session of result.sessions) observed.set(`${session.host}/${session.session_id}`, session);
				readPages++;
				if (result.next_cursor && result.next_cursor === next) throw new Error("Inventory cursor did not advance");
				next = result.next_cursor;
				if (!next) break;
			}
			rows.clear();
			for (const [id, session] of observed) {
				rows.set(id, session);
				rememberObservation("session", id, { session }, [`host:${session.host}`]);
			}
			cursor = next;
			more.hidden = !cursor;
			pages = mode === "more" ? pages + readPages : readPages;
			const focused = document.activeElement;
			const focusedID = list.contains(focused) ? focused.closest("[data-resource-id]")?.dataset.resourceId : null;
			const focusedPart = focused?.tagName === "SUMMARY" ? "summary" : focused?.classList.contains("title") ? "a.title" : null;
			render();
			status.replaceChildren();
			if (focusedID && focusedPart && document.activeElement === document.body) [...list.querySelectorAll("[data-resource-id]")].find((node) => node.dataset.resourceId === focusedID)?.querySelector(focusedPart)?.focus({ preventScroll: true });
			const current = [...list.querySelectorAll("[data-resource-id]")].find((node) => node.dataset.resourceId === anchorID);
			if (mode === "refresh" && current && Math.abs(scrollY - before) < 1) scrollBy(0, current.getBoundingClientRect().top - offset);
		} catch (e) {
			status.replaceChildren(errorBox(e));
		} finally {
			more.disabled = false;
		}
	};
	const load = async (mode) => {
		const expected = revision;
		serial = serial.then(() => read(mode, expected));
		let pending;
		do {
			pending = serial;
			await pending;
		} while (pending !== serial);
	};
	hostSel.onchange = accessSel.onchange = () => {
		revision++;
		selected = "";
		save();
		return load("reset");
	};
	search.oninput = () => {
		save();
		render();
	};
	more.onclick = () => load("more");
	await load("reset");
	const reload = debounceRefresh(() => load("refresh"), 500);
	return onEvents((ev) => {
		if ([
			"session",
			"host",
			"execution",
			"task"
		].includes(ev.resource_type)) return reload();
	});
}
var observationTime = (value) => value === null || value === void 0 || value === "" ? t("obs_unknown") : when(typeof value === "number" ? new Date(value * 1e3).toISOString() : value);
function observationLink(type, id) {
	if (!id) return null;
	let href;
	if (type === "session") {
		const [host, ...sid] = id.split("/");
		if (host && sid.length) href = `#/session/${encodeURIComponent(host)}/${encodeURIComponent(sid.join("/"))}`;
	} else if (type === "execution" || type === "task") href = `#/task/${encodeURIComponent(id)}`;
	else if (type === "worktree") href = `#/worktree/${encodeURIComponent(id)}`;
	else if (type === "operation") href = `#/op/${encodeURIComponent(id)}`;
	return href ? h("a", { href }, id) : h("code", {}, id);
}
function observationState(row) {
	return h("details", { class: "observation-evidence" }, h("summary", {}, t("obs_state_evidence")), h("p", { class: "muted" }, t("obs_lifecycle_note")), h("dl", { class: "kv" }, ...[
		"connection",
		"loading",
		"tab",
		"activity",
		"lifecycle",
		"enumeration",
		"freshness"
	].flatMap((axis) => {
		const evidence = row.state?.evidence?.[axis];
		return [h("dt", {}, t("obs_axis_" + axis)), h("dd", {}, t("obs_value_" + (row.state?.[axis] || "unknown")), evidence?.stale ? [" · ", chip(t("stale"), "stale")] : null, h("div", { class: "muted" }, observationTime(evidence?.observed_at), " · ", evidence?.source_ref || t("obs_unknown")))];
	})));
}
function discoveryEvidence(scopes) {
	return h("div", {}, ...scopes?.length ? scopes.map((scope) => h("section", { class: "observation-evidence" }, h("h3", {}, scope.profile_id || t("obs_unknown")), h("dl", { class: "kv" }, h("dt", {}, t("obs_scan_status")), h("dd", {}, scope.status || t("obs_unknown")), h("dt", {}, t("obs_last_success")), h("dd", {}, observationTime(scope.last_success_at)), h("dt", {}, t("obs_last_attempt")), h("dd", {}, observationTime(scope.finished_at)), h("dt", {}, t("obs_authority")), h("dd", {}, scope.authority?.kind || t("obs_unknown"), " · ", t(scope.authority?.verified ? "obs_verified" : "obs_unverified"))), scope.error_code ? h("p", { class: "error" }, scope.error_code) : null, h("details", {}, h("summary", {}, t("obs_scan_coverage")), h("pre", { class: "pre" }, JSON.stringify({
		coverage: scope.coverage || {},
		methods: scope.methods || {},
		errors: scope.errors || []
	}, null, 2))), h("h3", {}, t("obs_outside_scan")), h("ul", {}, ...(scope.outside_scan || []).map((x) => h("li", {}, t("obs_scope_" + x.scope), " · ", h("code", {}, x.reason)))))) : [h("p", { class: "muted" }, t("obs_no_scan"))]);
}
function observationPanels(type, id, path) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const section = (mode) => {
		const relations = mode === "relations";
		const list = h("div", {}), status = h("div", {}), evidence = h("p", { class: "muted" });
		const notice = h("p", {
			class: "note",
			hidden: true
		}, t("obs_new_facts"));
		const kind = h("input", {
			placeholder: t("obs_event_kind"),
			"aria-label": t("obs_event_kind")
		});
		const execution = h("input", {
			placeholder: t("obs_execution_filter"),
			"aria-label": t("obs_execution_filter")
		});
		const closed = h("input", {
			type: "checkbox",
			checked: true
		});
		let cursor = null, asOf = null, busy = false, parameters = "", loaded = false, latestSeen = state.lastEvent;
		const seen = new Set();
		const more = h("button", {
			class: "secondary",
			hidden: true,
			onclick: () => load(false)
		}, t("load_more"));
		const refresh = h("button", {
			class: "secondary",
			onclick: () => load(true)
		}, t("obs_read_latest"));
		const eventRow = (event) => {
			const context = event.context || {};
			const occurred = Object.hasOwn(context, "occurred_at") ? context.occurred_at : event.created_at;
			const details = h("details", {}, h("summary", {}, t("obs_evidence")), h("pre", { class: "pre" }, JSON.stringify({
				body: event.body || {},
				context
			}, null, 2)));
			const refs = [];
			for (const [field, resource] of [
				["execution_id", "execution"],
				["session_resource_id", "session"],
				["worktree_id", "worktree"],
				["operation_id", "operation"]
			]) {
				const value = event.body?.[field] || context[field];
				if (value) refs.push(observationLink(resource, value));
			}
			return h("article", {
				class: "observation-record",
				"data-history-seq": event.seq
			}, h("div", { class: "actions" }, h("strong", {}, event.kind), chip(`#${event.seq}`), observationLink(event.resource_type, event.resource_id)), h("p", { class: "muted" }, t("obs_occurred"), ": ", observationTime(occurred), " · ", t("obs_recorded"), ": ", observationTime(context.recorded_at ?? event.created_at), " · ", event.actor || t("obs_unknown")), refs.length ? h("div", { class: "actions" }, ...refs) : null, details);
		};
		const relationRow = (relation) => h("article", {
			class: "observation-record",
			"data-relation-id": relation.relation_id
		}, h("div", { class: "actions" }, observationLink("execution", relation.execution_id), relation.session_resource_id ? observationLink("session", relation.session_resource_id) : chip(t("obs_pending_binding"), "warn")), h("p", {}, relation.role || t("obs_unknown"), " · ", relation.status || t("obs_unknown"), " · ", relation.reason || t("obs_unknown")), h("p", { class: "muted" }, t("obs_half_open", {
			start: relation.start_seq ?? "?",
			end: relation.end_seq ?? "∞"
		}), " · ", observationTime(relation.started_at), " → ", observationTime(relation.ended_at)), relation.follow_up_of_execution_id ? h("p", {}, t("obs_follow_up"), " ", observationLink("execution", relation.follow_up_of_execution_id)) : null, h("details", {}, h("summary", {}, t("obs_evidence")), h("pre", { class: "pre" }, JSON.stringify({
			relation_id: relation.relation_id,
			branch_id: relation.branch_id,
			parent_relation_id: relation.parent_relation_id,
			command_ids: relation.command_ids || [],
			worktree_ranges: relation.worktree_ranges,
			evidence: relation.evidence
		}, null, 2))));
		async function load(reset) {
			if (busy) return;
			busy = true;
			refresh.disabled = more.disabled = true;
			try {
				assertView(connection);
				const params = reset ? new URLSearchParams({ limit: "20" }) : new URLSearchParams(parameters);
				if (reset && relations) {
					params.set("include_closed", String(closed.checked));
					if (execution.value.trim()) params.set("execution_id", execution.value.trim());
				} else if (reset) {
					params.set("order", "desc");
					if (kind.value.trim()) params.set("kind", kind.value.trim());
				}
				const filters = params.toString();
				if (!reset && cursor) params.set("cursor", cursor);
				const result = await api("GET", `${path}/${relations && type === "execution" ? "sessions" : mode}?${params}`);
				assertView(connection);
				if (!Number.isSafeInteger(result.as_of) || !reset && result.as_of !== asOf) throw new Error("Observation cursor changed its as_of");
				const items = result[relations ? "relations" : "events"];
				if (!Array.isArray(items)) throw new Error("Invalid observation page");
				if (reset) {
					seen.clear();
					list.replaceChildren();
					parameters = filters;
					asOf = result.as_of;
					notice.hidden = true;
				}
				for (const item of items) {
					const key = relations ? item.relation_id : item.seq;
					if (!seen.has(key)) {
						seen.add(key);
						list.append(relations ? relationRow(item) : eventRow(item));
					}
				}
				if (!seen.size) list.replaceChildren(h("p", { class: "muted" }, t("obs_empty")));
				cursor = result.next_cursor;
				more.hidden = !cursor;
				loaded = true;
				notice.hidden = latestSeen <= asOf;
				evidence.replaceChildren(...[
					t("obs_snapshot", { seq: asOf }),
					" ",
					t("obs_historical_limits"),
					!relations ? [
						" ",
						t("obs_first_recorded"),
						": ",
						observationTime(result.coverage?.first_recorded_at)
					] : ""
				].flat());
				status.replaceChildren();
			} catch (error) {
				status.replaceChildren(errorBox(error));
			} finally {
				busy = false;
				refresh.disabled = more.disabled = false;
			}
		}
		const box = h("details", {
			class: "panel observation-panel",
			"data-observation": mode,
			ontoggle: () => {
				if (box.open && !loaded) load(true);
			}
		}, h("summary", {}, t(relations ? "obs_relations" : "obs_history")), h("div", { class: "filters" }, relations ? execution : kind, relations ? h("label", {}, closed, " ", t("obs_include_closed")) : null, refresh), notice, evidence, status, list, more);
		return {
			box,
			changed: (event) => {
				latestSeen = Math.max(latestSeen, event.seq);
				if (loaded && latestSeen > asOf) notice.hidden = false;
			}
		};
	};
	const history = section("history"), relations = section("relations");
	return {
		box: h("div", {}, history.box, relations.box),
		changed: (event) => {
			history.changed(event);
			relations.changed(event);
		}
	};
}
async function viewTask(main, id) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const head = h("div", { class: "panel" }), status = h("div", { role: "status" });
	const observations = observationPanels("execution", id, `/tasks/${encodeURIComponent(id)}`);
	let task = null, readReady = false, active = null, retry;
	const panel = taskControlsPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		taskId: id,
		task: () => task,
		ready: () => readReady && state.online && !state.nativeBusy,
		storageKey: `batc.task-control.${connection.namespace}.${id}`,
		errorBox,
		opStatus,
		onSettled: () => load()
	});
	main.append(head, status, panel.box, observations.box);
	async function load() {
		assertView(connection);
		if (active) {
			await active.catch(() => {});
			assertView(connection);
			return load();
		}
		active = (async () => {
			const operation = panel.refresh(true);
			const observation = operation.catch(() => {}).then(() => api("GET", `/tasks/${encodeURIComponent(id)}`));
			await settleRefreshes([observation, operation]);
			const data = await observation;
			assertView(connection);
			if (data.task?.task_id !== id) throw new Error(t("task_control_invalid"));
			task = data.task;
			head.replaceChildren(h("h1", {}, t("task_title")), h("p", {}, task.project || id), h("p", { class: "actions" }, chip(t([
				true,
				false,
				0,
				1
			].includes(task.paused) ? task.paused ? "task_paused" : "task_dispatch_enabled" : "task_unknown")), chip([
				"queued",
				"dispatching",
				"accepted",
				"running",
				"waiting_permission",
				"quota_limited",
				"human_owned",
				"needs_ted",
				"verifying",
				"done",
				"failed",
				"uncertain"
			].includes(task.state) ? t("task_state_" + task.state) : task.state || "?")), h("p", { class: "muted" }, task.host || "", " · ", h("code", {}, id)), ...task.host && task.session_id ? [h("p", {}, h("a", { href: `#/session/${encodeURIComponent(task.host)}/${encodeURIComponent(task.session_id)}` }, t("task_open_session")))] : [], ...state.caps?.features?.cleanup_task === true ? [h("p", {}, h("a", { href: `#/cleanup/task/${encodeURIComponent(id)}` }, t("cleanup_task_preview")))] : [], ...state.caps?.artifacts?.capture?.managed_single_file === true ? [h("p", {}, h("a", { href: `#/artifact-review/task/${encodeURIComponent(id)}` }, t("ar_open")))] : [], h("details", {}, h("summary", {}, t("task_evidence")), h("pre", { class: "pre" }, JSON.stringify(task, null, 2))));
			status.replaceChildren();
			readReady = true;
			clearTimeout(retry);
		})();
		try {
			await active;
		} catch (error) {
			if (connection.generation === generation && connection.epoch === state.epoch) {
				readReady = false;
				status.replaceChildren(errorBox(error));
				clearTimeout(retry);
				retry = setTimeout(() => load().catch(() => {}), 3e3);
			}
			throw error;
		} finally {
			active = null;
			panel.update();
		}
	}
	await load().catch(() => {});
	const refresh = debounceRefresh(load, 500);
	const off = onEvents((event) => {
		observations.changed(event);
		if ([
			"execution",
			"task",
			"operation",
			"session"
		].includes(event.resource_type)) return refresh();
	});
	return () => {
		clearTimeout(retry);
		off();
	};
}
async function viewObservedResource(main, type, id) {
	const path = type === "execution" ? `/tasks/${encodeURIComponent(id)}` : `/worktrees/${encodeURIComponent(id)}`;
	const head = h("div", { class: "panel" });
	const panels = observationPanels(type, id, path);
	main.append(head, panels.box);
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const load = async () => {
		try {
			const data = await api("GET", path);
			assertView(connection);
			const resource = data[type === "execution" ? "task" : "worktree"];
			const sessions = resource.known_sessions || [];
			fill(head, h("h1", {}, t(type === "execution" ? "obs_execution" : "obs_worktree")), h("code", {}, id), h("p", { class: "muted" }, t("obs_known_identity")), type === "worktree" ? [
				h("dl", { class: "kv" }, h("dt", {}, t("host")), h("dd", {}, resource.host || t("obs_unknown")), h("dt", {}, t("delivery_worktree_branch")), h("dd", {}, h("code", {}, resource.branch || t("obs_unknown"))), h("dt", {}, t("delivery_worktree_path")), h("dd", {}, h("code", {}, resource.worktree_path || t("obs_unknown"))), h("dt", {}, t("delivery_worktree_owner")), h("dd", {}, resource.intent_type || t("obs_unknown"), " · ", resource.intent_type === "registry" ? h("code", {}, resource.intent_id || t("obs_unknown")) : observationLink(resource.intent_type === "task" ? "execution" : "operation", resource.intent_id))),
				h("h2", {}, t("delivery_worktree_sessions")),
				h("p", { class: "muted" }, t("delivery_worktree_recorded")),
				...sessions.map((s) => h("div", { class: "row" }, observationLink("session", `${s.host}/${s.session_id}`), chip(t(sessionActivity(s.observation || {}).key), sessionActivity(s.observation || {}).tone))),
				!sessions.length ? h("p", { class: "muted" }, t("none")) : null,
				...(resource.work || []).map((item) => deliveryWork(item)),
				h("p", { class: "note" }, t("delivery_worktree_cleanup")),
				h("p", {}, h("a", { href: `#/cleanup/${resource.intent_type === "task" ? "task" : "host"}/${encodeURIComponent(resource.intent_type === "task" ? resource.intent_id : resource.host || "")}` }, t("cleanup_preview")))
			] : null, type === "execution" && state.caps?.features?.cleanup_task === true ? h("p", {}, h("a", { href: `#/cleanup/task/${encodeURIComponent(id)}` }, t("cleanup_task_preview"))) : null, type === "execution" && state.caps?.artifacts?.capture?.managed_single_file === true ? h("p", {}, h("a", { href: `#/artifact-review/task/${encodeURIComponent(id)}` }, t("ar_open"))) : null, h("details", {}, h("summary", {}, t("sessions_details")), h("pre", { class: "pre" }, JSON.stringify(resource, null, 2))));
		} catch (error) {
			head.append(errorBox(error));
		}
	};
	await load();
	const reload = debounceRefresh(load, 500);
	return onEvents((event) => {
		panels.changed(event);
		if ([
			type,
			"task",
			"operation",
			"session"
		].includes(event.resource_type)) return reload();
	});
}
async function viewHostDiscovery(main, host) {
	const head = h("div", { class: "panel" });
	main.append(h("h1", {}, host, " · ", t("obs_discovery")), h("p", { class: "note" }, t("obs_discovery_note")), head);
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const load = async () => {
		try {
			const data = await api("GET", `/hosts/${encodeURIComponent(host)}/discovery`);
			assertView(connection);
			head.replaceChildren(discoveryEvidence(data.scopes));
		} catch (error) {
			head.append(errorBox(error));
		}
	};
	await load();
	const reload = debounceRefresh(load, 500);
	return onEvents((event) => {
		if (event.resource_type === "host" && event.resource_id === host) return reload();
	});
}
async function viewSession(main, host, sid, context = null) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const path = `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}`;
	const head = h("div", { class: "workspace-session-heading" });
	const metadata = h("div", { class: "workspace-metadata" });
	const result = h("section", {
		class: "workspace-result",
		"data-workspace-result": ""
	});
	const conversation = conversationPanel({
		h,
		t,
		when,
		guard: () => assertView(connection)
	});
	const pending = h("div", { "data-pending-controls": "" }), status = h("div", { class: "muted" });
	const scope = `send.${host}.${sid}`, draftKey = `batc.draft.${connection.namespace}.${scope}`;
	const box = h("textarea", { placeholder: t("send_placeholder") });
	try {
		box.value = localStorage.getItem(draftKey) || "";
	} catch {}
	box.oninput = () => {
		try {
			localStorage.setItem(draftKey, box.value);
		} catch {}
	};
	const queue = h("input", { type: "checkbox" });
	let row, pendingIdentity, sending = false, readReady = false, refreshInFlight = null, readError = null;
	const allowed = (action) => readReady && row?.api_access === "managed" && may("operate") && state.caps?.hosts?.find((item) => item.host === host)?.writes !== false && state.caps?.actions?.find((item) => item.action === action)?.allowed !== false;
	const identity = (pend) => pend ? JSON.stringify({
		kind: pend.kind,
		toolUseId: pend.toolUseId,
		toolName: pend.toolName,
		input_preview: pend.input_preview,
		questions: pend.questions
	}) : "";
	const send = h("button", {
		class: "primary",
		disabled: true,
		onclick: async () => {
			if (!box.value.trim()) return;
			const submitted = box.value;
			sending = true;
			send.disabled = true;
			try {
				assertView(connection);
				const op = await submit("session.send", {
					host,
					session_id: sid
				}, {
					text: submitted,
					queue: queue.checked
				}, {}, scope);
				assertView(connection);
				status.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
				if (op.status === "succeeded" && box.value === submitted) {
					box.value = "";
					try {
						localStorage.removeItem(draftKey);
					} catch {}
				}
			} catch (e) {
				status.replaceChildren(errorBox(e));
			} finally {
				sending = false;
				send.disabled = !allowed("session.send");
			}
		}
	}, t("send"));
	const stop = h("button", {
		class: "danger",
		disabled: true,
		onclick: async () => {
			try {
				assertView(connection);
				const op = await submit("session.interrupt", {
					host,
					session_id: sid
				}, { mode: "soft" }, {}, `interrupt.${host}.${sid}`);
				assertView(connection);
				status.replaceChildren(opStatus(op));
			} catch (e) {
				status.replaceChildren(errorBox(e));
			}
		}
	}, t("interrupt"));
	const composer = h("div", { hidden: true }, box, h("div", { class: "actions" }, send, stop, h("label", { class: "muted" }, queue, " ", t("queue_behind"))));
	const readonly = h("p", { class: "note" }, t("session_access_unknown"));
	let capture, permissions, batHandoff;
	const captureSlot = h("div"), permissionsSlot = h("div"), batSlot = h("div");
	const controls = h("div", { class: "panel workspace-composer" }, pending, readonly, composer, status);
	const labels = sessionLabelsPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		target: {
			host,
			session_id: sid
		},
		storageKey: `batc.labels.${connection.namespace}.${JSON.stringify([host, sid])}`,
		errorBox,
		opStatus
	});
	const cps = checkpointPanel(host, sid);
	const observations = observationPanels("session", `${host}/${sid}`, path);
	const inspector = h("details", {
		class: "workspace-inspector",
		open: true
	}, h("summary", {}, t("workspace_work_details")), context?.itemBox, result, batSlot, h("details", { class: "workspace-evidence" }, h("summary", {}, t("sessions_details")), metadata), labels.box, permissionsSlot, captureSlot, cps.box, observations.box);
	const lane = h("section", {
		class: "workspace-conversation",
		"aria-label": t("messages")
	}, conversation.box, controls);
	if (context?.picker) main.append(context.picker);
	main.append(head, h("div", { class: "workspace-session" }, lane, inspector));
	const renderPending = () => {
		const pend = row.api_access === "managed" ? row.pending : null;
		const current = identity(pend);
		if (current === pendingIdentity) return;
		pendingIdentity = current;
		pending.replaceChildren();
		if (!pend) return;
		const answerScope = `answer.${host}.${sid}.${pend.toolUseId || ""}`;
		const key = `batc.draft.${connection.namespace}.${answerScope}`;
		let saved;
		try {
			saved = JSON.parse(localStorage.getItem(key));
		} catch {}
		const answer = async (params) => {
			try {
				assertView(connection);
				const latest = await api("GET", path);
				assertView(connection);
				applyObservation(latest);
				if (latest.session.api_access !== "managed" || identity(latest.session.pending) !== current || !pend.toolUseId) throw new ApiError(409, "PENDING_CHANGED", t("pending_changed"));
				const op = await submit("session.answer", {
					host,
					session_id: sid
				}, {
					...params,
					tool_use_id: pend.toolUseId
				}, {}, answerScope);
				assertView(connection);
				status.replaceChildren(opStatus(op));
				if (op.status === "succeeded") await loadObservation();
			} catch (e) {
				status.replaceChildren(errorBox(e));
			}
		};
		const card = h("div", { class: "panel" }, h("div", { class: "title" }, t("pending_" + pend.kind)));
		if (pend.kind === "permission") card.append(h("p", {}, h("code", {}, pend.toolName || "")), h("p", { class: "msg" }, pend.input_preview || ""), h("div", { class: "actions" }, h("button", {
			class: "primary",
			"data-answer-action": "",
			disabled: !pend.toolUseId || !allowed("session.answer"),
			onclick: () => answer({ permission: "allow" })
		}, t("allow")), h("button", {
			class: "danger",
			"data-answer-action": "",
			disabled: !pend.toolUseId || !allowed("session.answer"),
			onclick: () => answer({ permission: "deny" })
		}, t("deny"))));
		else if (pend.kind === "ask_user") {
			const fields = [];
			const save = () => {
				try {
					localStorage.setItem(key, JSON.stringify({
						identity: current,
						answers: fields.map((f) => f.value)
					}));
				} catch {}
			};
			for (const [index, q] of (pend.questions || []).entries()) {
				const input = h("input", {
					placeholder: t("answer"),
					"aria-label": q.question || t("answer"),
					value: saved?.identity === current ? saved.answers?.[index] || "" : "",
					oninput: save
				});
				fields.push(input);
				const picks = (q.options || []).map((o) => h("button", {
					class: "secondary",
					onclick: () => {
						input.value = o;
						save();
					}
				}, o));
				card.append(h("p", {}, q.header ? h("strong", {}, `${q.header} · `) : null, q.question), picks.length ? h("div", { class: "actions" }, ...picks) : null, h("div", { class: "actions" }, input));
			}
			card.append(h("div", { class: "actions" }, h("button", {
				class: "primary",
				"data-answer-action": "",
				disabled: !pend.toolUseId || !allowed("session.answer"),
				onclick: () => answer({ answers: fields.map((f) => f.value) })
			}, t("answer"))));
		}
		pending.append(card);
	};
	const updateControls = () => {
		permissions?.update();
		send.disabled = !allowed("session.send") || sending;
		stop.disabled = !allowed("session.interrupt");
		for (const button of pending.querySelectorAll("[data-answer-action]")) button.disabled = !row?.pending?.toolUseId || !allowed("session.answer");
	};
	const applyObservation = (data) => {
		const first = !row;
		row = data.session || (data.cleanup?.length ? {
			host,
			session_id: sid,
			provenance: "unknown",
			api_access: "read_only"
		} : null);
		if (!row) throw new Error(t("obs_unknown"));
		rememberObservation("session", `${host}/${sid}`, data, [
			`host:${host}`,
			...(data.work_items || []).map((item) => `work_item:${item.work_item_id}`),
			...(data.relations_summary || []).flatMap((relation) => [`execution:${relation.execution_id}`, `task:${relation.execution_id}`]),
			...data.started_from?.operation_id ? [`operation:${data.started_from.operation_id}`] : []
		]);
		if (first) queue.checked = Boolean(row.streaming);
		const activity = sessionActivity(row);
		head.replaceChildren(h("div", {}, context?.project ? h("a", {
			class: "muted",
			href: `#/project/${encodeURIComponent(context.project.project_id)}`
		}, context.project.name) : null, h("h1", {}, row.title || sid)), h("div", { class: "workspace-session-meta" }, chip(t(activity.key), activity.tone), h("span", { class: "muted" }, [row.agent_kind, row.model].filter(Boolean).join(" · ")), h("a", {
			class: "muted",
			href: `#/host/${encodeURIComponent(host)}`
		}, row.host), chip(t(row.api_access === "managed" ? "managed" : "read_only"), row.api_access === "managed" ? "managed" : "readonly")));
		metadata.replaceChildren(h("div", { class: "actions" }, ...sessionBadges(row)), h("dl", { class: "kv" }, h("dt", {}, t("host")), h("dd", {}, h("a", { href: `#/host/${encodeURIComponent(host)}` }, row.host)), h("dt", {}, t("workspace")), h("dd", {}, row.workspace || ""), h("dt", {}, t("sessions_label")), h("dd", {}, h("code", {}, row.session_id)), h("dt", {}, t("agent")), h("dd", {}, [row.agent_kind, row.model].filter(Boolean).join(" · ")), h("dt", {}, t("session_origin")), h("dd", {}, t("provenance_" + ([
			"manual",
			"connector_managed",
			"unknown"
		].includes(row.provenance) ? row.provenance : "unknown"))), h("dt", {}, t("observed")), h("dd", {}, observationTime(row.observed_at))), observationState(row), confinementDetails(row));
		if (!batHandoff) batHandoff = sessionBatPanel({
			h,
			t,
			guard: () => assertView(connection),
			session: () => row,
			storageKey: `batc.session-bat.${connection.namespace}.${JSON.stringify([host, sid])}`
		});
		batSlot.append(batHandoff.box);
		batHandoff.update();
		if (data.started_from) {
			const from = data.started_from;
			metadata.append(h("p", { class: "note" }, t("started_from", { commit: from.commit_sha.slice(0, 12) }), " ", h("a", { href: `#/session/${encodeURIComponent(from.source_host)}/${encodeURIComponent(from.source_session_id)}` }, t("source_session")), " · ", h("a", { href: `#/op/${from.operation_id}` }, from.operation_id)));
		}
		if (data.work_items?.length) metadata.append(linkedItems(data.work_items));
		if (data.discovery?.length) metadata.append(h("details", {}, h("summary", {}, t("obs_discovery")), discoveryEvidence(data.discovery)));
		const managed = row.api_access === "managed";
		if (managed && row.provenance === "connector_managed" && state.caps?.artifacts?.capture?.managed_single_file) metadata.append(h("p", {}, h("a", { href: `#/artifact-review/session/${encodeURIComponent(host)}/${encodeURIComponent(sid)}` }, t("ar_open"))));
		if (managed && row.provenance === "connector_managed") {
			const links = [];
			if (state.caps?.actions?.some((a) => a.action === "session.relay")) links.push(h("a", { href: `#/orchestrate/relay/${encodeURIComponent(host)}/${encodeURIComponent(sid)}` }, t("orch_relay")));
			if (row.agent_kind === "claude" && !data.relations_summary?.length && state.caps?.actions?.some((a) => a.action === "session.failover")) links.push(h("a", { href: `#/orchestrate/failover/${encodeURIComponent(host)}/${encodeURIComponent(sid)}` }, t("orch_failover")));
			if (links.length) metadata.append(h("div", { class: "actions" }, ...links));
		}
		if (managed && row.provenance === "connector_managed" && !permissions) {
			permissions = permissionsPanel({
				h,
				t,
				api,
				caps: () => state.caps,
				guard: () => assertView(connection),
				errorBox,
				opStatus,
				storageKey: `batc.permissions.${connection.namespace}.${JSON.stringify([host, sid])}`,
				target: {
					host,
					session_id: sid
				},
				session: () => row,
				ready: () => readReady
			});
			permissionsSlot.append(permissions.box);
		}
		const manualSource = row.provenance === "manual" && state.caps?.artifacts?.capture?.manual_single_file;
		if (manualSource && !capture) {
			capture = manualCapture(`session.${JSON.stringify([host, sid])}`, {
				host,
				session_id: sid
			});
			captureSlot.append(capture);
		}
		if (capture) capture.hidden = !manualSource;
		composer.hidden = !managed;
		readonly.hidden = managed;
		readonly.textContent = t(row.provenance === "manual" ? "read_only_note" : "session_access_unknown");
		renderPending();
		updateControls();
	};
	const loadObservation = async () => {
		const data = await api("GET", path);
		assertView(connection);
		applyObservation(data);
		let work = [], repositories = [];
		if (context?.project) {
			const project = await api("GET", `/projects/${encodeURIComponent(context.project.project_id)}`);
			assertView(connection);
			work = (project.work || []).filter((item) => item.host === host && item.session_id === sid);
			repositories = project.project?.repositories || [];
		} else if (row.worktree_id && state.caps?.features?.execution_delivery?.version === 1) {
			const detail = await api("GET", `/worktrees/${encodeURIComponent(row.worktree_id)}`);
			assertView(connection);
			work = (detail.worktree?.work || []).filter((item) => item.host === host && item.session_id === sid);
		}
		fill(result, h("h2", {}, t("workspace_result")), ...work.map((item) => deliveryWork(item, repositories, true)), !work.length ? h("p", { class: "muted" }, t("workspace_result_empty")) : null, data.work_items?.length ? linkedItems(data.work_items) : null, !work.some((item) => item.worktree_id === row.worktree_id) && row.worktree_id ? h("p", {}, observationLink("worktree", row.worktree_id)) : null);
	};
	const loadMessages = async () => {
		const read = await api("GET", `${path}/messages?last_n=30`);
		assertView(connection);
		conversation.update(read.messages);
	};
	const refresh = async (fromEvent = false) => {
		if (refreshInFlight) {
			await refreshInFlight;
			if (fromEvent) return refresh(true);
			return;
		}
		refreshInFlight = (async () => {
			try {
				await settleRefreshes([loadObservation(), loadMessages()]);
				await permissions?.refresh(fromEvent);
				readReady = true;
				updateControls();
				readError?.remove();
				readError = null;
			} catch (error) {
				readReady = false;
				updateControls();
				readError = errorBox(error);
				status.replaceChildren(readError);
				throw error;
			}
		})();
		try {
			await refreshInFlight;
		} finally {
			refreshInFlight = null;
		}
	};
	try {
		await settleRefreshes([
			refresh(),
			cps.load(),
			labels.refresh()
		]);
	} catch {}
	const retry = setInterval(() => {
		if (!readReady && !refreshInFlight) refresh().catch(() => {});
	}, 1e3);
	const reload = debounceRefresh(() => refresh(true), 500), reloadCps = debounceRefresh(cps.load, 500);
	const off = onEvents((ev) => {
		observations.changed(ev);
		return settleRefreshes([
			observationAffected("session", `${host}/${sid}`, ev) || [
				"work_item",
				"integration",
				"worktree"
			].includes(ev.resource_type) || context?.project && [
				"project",
				"operation",
				"task",
				"execution"
			].includes(ev.resource_type) ? reload() : Promise.resolve(),
			ev.resource_type === "checkpoint" ? reloadCps() : Promise.resolve(),
			ev.resource_type === "operation" ? permissions?.refresh(true) : Promise.resolve(),
			observationAffected("session", `${host}/${sid}`, ev) || ev.resource_type === "operation" ? labels.refresh(true) : Promise.resolve()
		]);
	});
	return () => {
		clearInterval(retry);
		off();
		batHandoff?.dispose();
		conversation.dispose();
	};
}
function checkpointPanel(host, sid) {
	const can = (state.caps?.features?.checkpoints || []).includes(host);
	const mayStart = (state.caps?.scopes || []).includes("start");
	const list = h("div", {});
	const status = h("div", { class: "muted" });
	const rows = new Map();
	let preview = null;
	const row = (cp) => rows.get(cp.checkpoint_id) || rows.set(cp.checkpoint_id, buildRow(cp)).get(cp.checkpoint_id);
	const buildRow = (cp) => {
		const instr = h("textarea", { placeholder: t("continue_placeholder") });
		const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
		const out = h("div", { class: "muted" });
		const draft = attachmentDraft(`continue.${cp.checkpoint_id}`, instr, cp.artifacts || []);
		draft.bindFields({ agent });
		let expectedHead = null;
		const go = h("button", {
			class: "primary",
			onclick: async () => {
				if (!instr.value.trim()) return;
				go.disabled = true;
				try {
					if (!draft.ready() && !draft.pending()) throw new Error(t("attachments_not_ready"));
					if (state.caps?.artifacts && !expectedHead && !draft.pending()) throw new Error(t("source_unavailable"));
					const op = await draft.perform("checkpoint.continue", { checkpoint_id: cp.checkpoint_id }, {
						instructions: instr.value,
						agent: agent.value,
						...state.caps?.artifacts ? { artifacts: draft.refs() } : {}
					}, state.caps?.artifacts ? { expected_source_head_sha: expectedHead } : {}, `continue.${cp.checkpoint_id}`);
					out.replaceChildren(opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
				} catch (e) {
					out.replaceChildren(errorBox(e));
				}
				go.disabled = false;
			}
		}, t("start_agent_work"));
		const form = h("div", { hidden: true }, confinementNote(host, agent), instr, draft.box, h("div", { class: "actions" }, agent, go), out);
		return h("div", { class: "row" }, h("div", { class: "grow" }, h("div", { class: "title" }, h("code", {}, cp.commit_sha.slice(0, 12)), " ", cp.branch || ""), h("div", { class: "muted" }, [
			when(epoch(cp.captured_at)),
			cp.actor,
			t("excerpt_count", { n: cp.excerpt_messages })
		].join(" · ")), cp.dirty ? h("div", { class: "error" }, t("dirty_warning", { n: cp.dirty })) : cp.dirty === null ? h("div", { class: "muted" }, t("dirty_unknown")) : null, preview && preview.head !== cp.commit_sha ? h("div", { class: "muted" }, t("source_advanced")) : null, form), h("button", {
			class: "secondary",
			disabled: !can || !mayStart,
			title: !can ? t("checkpoint_unavailable") : mayStart ? null : t("needs_start_scope"),
			onclick: async () => {
				form.hidden = !form.hidden;
				if (state.caps?.artifacts && !form.hidden && !expectedHead) try {
					expectedHead = (await api("GET", `/checkpoints/${cp.checkpoint_id}?live=true`)).source.head;
					if (!expectedHead) fill(out, h("p", { class: "error" }, t("source_unavailable")));
				} catch (e) {
					fill(out, errorBox(e));
				}
			}
		}, t("continue_from_checkpoint")));
	};
	const load = async () => {
		try {
			const page = await api("GET", `/checkpoints?${new URLSearchParams({
				host,
				session_id: sid,
				limit: "10"
			})}`);
			list.replaceChildren(...page.checkpoints.length ? page.checkpoints.map(row) : [h("p", { class: "muted" }, t("no_checkpoints"))]);
		} catch (e) {
			list.replaceChildren(errorBox(e));
		}
	};
	const pick = h("select", {
		"aria-label": t("commit"),
		hidden: true
	});
	const note = h("textarea", {
		placeholder: t("checkpoint_note_placeholder"),
		hidden: true
	});
	let previewFailed = false;
	const loadPreview = async () => {
		if (!can) return;
		try {
			const selectedCommit = pick.value;
			const current = (await api("GET", `/sessions/${encodeURIComponent(host)}/${encodeURIComponent(sid)}/checkpoint-preview`)).preview;
			if (!Array.isArray(current?.commits)) throw new Error("Invalid checkpoint preview");
			preview = current;
			pick.replaceChildren(...preview.commits.map((c) => h("option", { value: c.hash }, `${c.hash.slice(0, 10)} · ${c.message}`)));
			if (preview.commits.some((c) => c.hash === selectedCommit)) pick.value = selectedCommit;
			pick.hidden = note.hidden = false;
			create.disabled = false;
			if (previewFailed) status.replaceChildren();
			previewFailed = false;
			if (preview.dirty) status.replaceChildren(h("span", { class: "error" }, t("dirty_warning", { n: preview.dirty })));
		} catch (error) {
			previewFailed = true;
			create.disabled = true;
			status.replaceChildren(errorBox(error));
		}
	};
	const create = h("button", {
		class: "secondary",
		disabled: !can,
		onclick: async () => {
			create.disabled = true;
			try {
				const params = {
					last_n: 20,
					...preview ? { commit: pick.value } : {},
					...note.value.trim() ? { note: note.value.trim() } : {}
				};
				const op = await submit("checkpoint.create", {
					host,
					session_id: sid
				}, params, {}, `checkpoint.${host}.${sid}`);
				if (op.status === "succeeded") note.value = "";
				status.replaceChildren(...[
					opStatus(op),
					op.error_code ? chip(op.error_code, "bad") : null,
					op.status_reason
				].filter(Boolean).flatMap((x) => [x, " "]));
				await load();
			} catch (e) {
				status.replaceChildren(errorBox(e));
			}
			create.disabled = !can || previewFailed;
		}
	}, t("create_checkpoint"));
	return {
		box: h("div", { class: "panel" }, h("h2", {}, t("checkpoints")), h("p", { class: "muted" }, t("checkpoint_help")), can ? null : h("p", { class: "muted" }, t("checkpoint_unavailable")), can && !mayStart ? h("p", { class: "muted" }, t("needs_start_scope")) : null, note, h("div", { class: "actions" }, pick, create), status, list),
		load: async () => {
			await loadPreview();
			await load();
		}
	};
}
async function viewDelivery(main, sourceHost, sourceKind, sourceId, sourceRepository) {
	freshPage();
	const source = sourceHost && ["execution", "task_command"].includes(sourceKind) && sourceId ? {
		host: sourceHost,
		kind: sourceKind,
		id: sourceId
	} : null;
	const repo = h("input", {
		"aria-label": t("delivery_repository_input"),
		placeholder: "owner/name",
		value: source ? sourceRepository || "" : sessionStorage.getItem("batc.repo") || ""
	});
	const num = h("input", {
		"aria-label": t("delivery_pr_number"),
		placeholder: "123",
		inputmode: "numeric",
		size: 6,
		value: source ? "" : sessionStorage.getItem("batc.pr") || ""
	});
	const card = h("div", { class: "panel delivery-card" });
	const inputStatus = h("p", {
		class: "muted",
		role: "status"
	});
	const acceptLink = () => {
		const pr = parsePullRequest(repo.value);
		if (pr) {
			repo.value = pr.repository;
			num.value = pr.number;
		}
	};
	repo.addEventListener("change", acceptLink);
	const groups = new Map();
	for (const r of state.caps?.deploy_recipes || []) {
		const key = JSON.stringify([r.repository.toLowerCase(), r.environment]);
		if (!groups.has(key)) groups.set(key, []);
		groups.get(key).push(r);
	}
	const environments = [...groups.values()].map(environmentCard);
	main.append(h("h1", {}, t("nav_delivery")), ...environments.map((e) => e.card));
	if (source) main.append(h("p", { class: "note" }, t("delivery_source_context"), " ", h("code", {}, source.id)));
	let selectedMethod = "";
	let reviewedPreview = null;
	main.append(h("h2", {}, t("dep_pull_request")), h("form", {
		class: "filters delivery-controls",
		onsubmit: (event) => {
			event.preventDefault();
			acceptLink();
			load();
		}
	}, h("label", {}, t("delivery_repository_input"), repo), h("label", {}, t("delivery_pr_number"), num), h("button", {
		type: "submit",
		class: "secondary"
	}, t("load_pr"))), inputStatus, card);
	if (!source && !repo.value && state.caps?.repositories?.length) repo.value = state.caps.repositories[0].repository;
	const load = async (flash = null, fromEvent = false) => {
		const opens = drawerOpens;
		const holdCard = () => card.querySelector(".drawer:not([hidden])") || fromEvent && holdRender(true, opens);
		sessionStorage.setItem("batc.repo", repo.value);
		sessionStorage.setItem("batc.pr", num.value);
		if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo.value) || !/^[1-9]\d{0,8}$/.test(num.value)) {
			inputStatus.textContent = repo.value || num.value ? t("delivery_choose_pr") : "";
			return;
		}
		inputStatus.textContent = "";
		try {
			const query = new URLSearchParams();
			if (selectedMethod) query.set("method", selectedMethod);
			if (fromEvent) query.set("from_event", "true");
			const pr = (await api("GET", `/repositories/${repo.value}/pulls/${num.value}?${query}`)).pull_request;
			if (!pr?.merge_preview || !pr?.merge) throw new Error(t("delivery_pr_unavailable"));
			if (holdCard()) {
				idleReload = () => load(null, true);
				return;
			}
			const status = h("div", { "aria-live": "polite" });
			const target = {
				repository: pr.repository,
				pull_number: Number(pr.pull_number)
			};
			if (!fromEvent || !reviewedPreview) reviewedPreview = pr.merge_preview;
			const pv = reviewedPreview;
			const scopeChanged = pr.merge_preview.digest !== pv.digest;
			const pre = {
				expected_head_sha: pv.target.head_sha,
				expected_base_sha: pv.target.base_sha,
				preview_digest: pv.digest
			};
			const params = {
				method: pv.method,
				preview_id: pv.preview_id
			};
			const run = async (action, extra, scope) => {
				try {
					const op = await submit(action, {
						...target,
						...extra.target
					}, extra.params || params, extra.pre ?? pre, scope);
					const receipt = op.result?.merge || op.result || op.external_refs?.merge_receipt;
					fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id), receipt?.base_moved ? h("p", { class: "note warn" }, t("merged_newer_base", { count: receipt.other_commits_count })) : null);
				} catch (e) {
					fill(status, errorBox(e));
				}
			};
			const blocked = pr.state !== "open" || pr.draft || pr.merged || pv.blocking.length > 0 || scopeChanged;
			const method = h("select", {
				"aria-label": t("merge_method"),
				onchange: () => {
					selectedMethod = method.value;
					load();
				}
			}, ...pr.merge.methods.map((m) => h("option", {
				value: m,
				selected: m === pv.method
			}, m)));
			const buttons = [h("button", {
				class: "primary",
				"data-testid": "merge-submit",
				disabled: blocked || !pr.merge.allowed || !may("merge"),
				onclick: () => run("github.pr.merge", {}, `merge.${pv.preview_id}`)
			}, t("merge"))];
			for (const r of pr.recipes) {
				buttons.push(h("button", {
					class: "secondary",
					disabled: blocked || !pr.merge.allowed || !may("merge") || !may("deploy") || !state.caps?.deploy_recipes?.find((c) => c.name === r.name)?.readiness?.ready,
					onclick: async () => {
						try {
							const deploymentPreview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(r.name)}`)).preview;
							await run("delivery.merge_and_deploy", {
								target: { recipe: r.name },
								pre: {
									...pre,
									...deploymentPreview.preconditions
								}
							}, `merge_deploy.${pv.preview_id}.${r.name}`);
						} catch (e) {
							fill(status, errorBox(e));
						}
					}
				}, t("merge_and_deploy_to", { env: r.environment })));
				if (pr.merged && pr.merge_commit_sha) buttons.push(h("button", {
					class: "secondary",
					disabled: !may("deploy") || !state.caps?.deploy_recipes?.find((c) => c.name === r.name)?.readiness?.ready,
					onclick: async () => {
						try {
							const deploymentPreview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(r.name)}`)).preview;
							const op = await submit("deployment.start", { recipe: r.name }, { source_sha: pr.merge_commit_sha }, deploymentPreview.preconditions, `deploy.${r.name}.${pr.merge_commit_sha}`);
							fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
						} catch (e) {
							fill(status, errorBox(e));
						}
					}
				}, t("deploy_to", { env: r.environment })));
			}
			const commitList = h("details", { class: "row-details" }, h("summary", {}, t("merge_commit_range", { count: pv.commits.length })), h("ul", {}, ...pv.commits.map((c) => h("li", {}, h("code", {}, c.sha), " ", c.message))));
			const affected = pv.affected_prs.map((p) => h("div", { class: "row" }, h("div", { class: "grow" }, h("a", {
				href: p.html_url,
				target: "_blank",
				rel: "noopener"
			}, `#${p.number} ${p.title || ""}`), " · ", t("scope_" + p.reason), h("div", {}, h("code", {}, p.head_sha || ""))), chip(t(p.effect === "branch_rebase" ? "scope_stack_rebase" : p.effect === "dependency" ? "scope_dependency" : p.would_merge ? "scope_would_merge" : "scope_candidate"), p.would_merge ? "warn" : "")));
			card.querySelector("[data-integration-review]")?.closeReview?.();
			fill(card, h("h2", {}, h("a", {
				href: pr.html_url,
				target: "_blank",
				rel: "noopener"
			}, `#${pr.pull_number} ${pr.title || ""}`)), h("dl", { class: "kv" }, h("dt", {}, t("head")), h("dd", {}, h("code", {}, `${pr.head_ref} @ ${pr.head_sha}`)), h("dt", {}, t("base")), h("dd", {}, h("code", {}, `${pr.base_ref} @ ${pr.base_sha}`)), h("dt", {}, t("mergeable")), h("dd", {}, `${pr.state}${pr.draft ? " · draft" : ""} · ${pr.mergeable_state || "?"}`), h("dt", {}, t("checks")), h("dd", {}, t("checks_summary", pr.checks)), pr.merged ? [h("dt", {}, t("merged_sha")), h("dd", {}, h("code", {}, pr.merge_commit_sha))] : null), metadataDrawer(pr, load), scopeChanged ? h("p", { class: "note warn" }, t("merge_scope_reload")) : null, h("h2", {}, t("merge_scope")), h("label", {}, t("merge_method"), " ", method), h("p", { class: "muted" }, t("merge_preview_fixed"), " ", h("code", {}, pv.preview_id)), commitList, affected.length ? h("div", {}, ...affected) : h("p", { class: "muted" }, t("scope_single_pr")), ...pv.blocking.map((b) => h("p", { class: "note warn" }, h("code", {}, b.code), " · ", b.message)), ...pv.warnings.map((w) => h("p", { class: "muted" }, w)), h("div", { class: "actions" }, ...buttons), status, flash instanceof Node ? flash : null, pr.integration?.allowed ? integrationPanel(pr, load, source) : null);
		} catch (e) {
			if (!holdCard()) fill(card, errorBox(e));
		}
	};
	const reload = async (fromEvent = true) => {
		await settleRefreshes([...environments.map((e) => e.load(fromEvent)), load(null, fromEvent)]);
	};
	await reload(false);
	return liveReload(reload, [
		"operation",
		"integration",
		"deployment",
		"deployment_environment"
	]);
}
function deliveryWork(item, repositories = [], compact = false) {
	const activity = sessionActivity(item.session || {});
	const repo = item.repository || (repositories.length === 1 ? repositories[0] : "");
	const links = [];
	if (item.operation_id) links.push(h("a", { href: `#/op/${encodeURIComponent(item.operation_id)}` }, t("permissions_details")));
	if (item.task_id) links.push(observationLink("execution", item.task_id));
	if (!compact && item.host && item.session_id) links.push(observationLink("session", `${item.host}/${item.session_id}`));
	if (item.worktree_id) links.push(observationLink("worktree", item.worktree_id));
	if (item.eligible && state.caps?.features?.execution_delivery?.version === 1) links.push(h("a", { href: `#/delivery/${[
		item.host,
		item.kind,
		item.id,
		repo
	].map(encodeURIComponent).join("/")}` }, t("delivery_review_result")));
	return h("div", {
		class: "row",
		"data-project-work": item.id
	}, h("div", { class: "grow" }, compact ? null : h("strong", {}, item.title || item.branch || item.action || item.id), compact ? null : [" ", chip(t(activity.key), activity.tone)], h("p", { class: "muted" }, item.host || "?", item.actor ? ` · ${item.actor}` : "", " · ", h("code", {}, item.branch || item.id)), h("p", { class: "muted" }, t("delivery_dispatch_state"), " ", t(item.operation_id && item.status === "succeeded" ? "delivery_dispatch_accepted" : (item.operation_id ? "op_" : "task_state_") + item.status), " · ", t("delivery_result_unverified")), item.unavailable ? h("p", { class: "muted" }, t("delivery_source_unavailable"), " ", h("code", {}, item.unavailable.code)) : null, h("div", { class: "actions" }, ...links, ...(item.delivered_to || []).map((receipt) => h("a", {
		href: `https://github.com/${receipt.repository}/pull/${receipt.pull_number}`,
		target: "_blank",
		rel: "noopener",
		title: `${receipt.pinned_sha} → ${receipt.delivered_sha}`
	}, t("delivered_to", { n: receipt.pull_number }))))));
}
function deploymentIdentity(identity, empty = "dep_no_version") {
	if (!identity?.source_sha && !identity?.artifact_id) return h("p", { class: "muted" }, t(empty));
	return h("div", { class: "deployment-identity" }, identity.source_sha ? h("code", {}, identity.source_sha) : null, identity.artifact_id ? h("p", {}, t("dep_artifact", { id: identity.artifact_id }), identity.artifact_digest ? [" · ", h("code", {}, identity.artifact_digest)] : null) : null);
}
function deploymentState(value) {
	return chip(t(`dep_state_${value || "unverified"}`), [
		"failed",
		"needs_attention",
		"uncertain"
	].includes(value) ? "bad" : value === "succeeded" ? "ok" : "warn");
}
function deploymentTime(value) {
	return value ? when(Number(value) * 1e3) : t("dep_not_observed");
}
function heldDetails(title, children, onOpen) {
	let counted = false;
	const details = h("details", {
		class: "row-details",
		ontoggle: () => {
			if (details.open !== counted) {
				counted = details.open;
				if (counted) {
					drawerOpens += 1;
					if (onOpen) onOpen();
				}
				setEditing(editing + (counted ? 1 : -1));
			}
		}
	}, h("summary", {}, title), ...children);
	details.closeHeld = () => {
		if (counted) {
			counted = false;
			setEditing(editing - 1);
		}
		details.open = false;
	};
	return details;
}
function deploymentReceipt(dep) {
	const body = h("div", {});
	let read = false;
	return heldDetails(t("dep_operation_details"), [body], async () => {
		if (read) return;
		read = true;
		try {
			const op = (await api("GET", `/operations/${dep.operation_id}`)).operation;
			const saved = op.external_refs?.deployment_id && op.external_refs.deployment_id !== dep.deployment_id ? (await api("GET", `/deployments/${op.external_refs.deployment_id}`)).deployment : dep;
			const values = [
				[t("dep_operation"), h("a", { href: `#/op/${op.operation_id}` }, op.operation_id)],
				[t("dep_status"), opStatus(op)],
				[t("dep_run"), saved.run_id],
				[t("dep_attempt"), saved.run_attempt],
				[t("dep_error_code"), op.error_code || saved.error_code || saved.reconciliation_error]
			];
			fill(body, h("dl", { class: "kv" }, ...values.filter(([, v]) => v !== null && v !== void 0 && v !== "").flatMap(([label, value]) => [h("dt", {}, label), h("dd", {}, value)])), op.status_reason ? h("p", {}, op.status_reason) : null, ...(op.steps || []).map((s) => h("div", { class: "row" }, h("code", {}, s.name), h("code", {}, s.status))));
		} catch (e) {
			fill(body, errorBox(e));
			read = false;
		}
	});
}
function deploymentLimits(limits) {
	return h("div", { class: "deployment-limits" }, h("span", { class: "muted" }, t("dep_not_undone")), limits?.length ? h("ul", {}, ...limits.map((value) => h("li", {}, value))) : h("p", { class: "muted" }, t("dep_no_limits")));
}
function deploymentPreviewSummary(preview) {
	return h("p", {
		class: "muted",
		"data-testid": "deployment-preview-generation"
	}, t("dep_preview_generation", {
		env: preview.environment,
		generation: preview.environment_generation
	}));
}
function deploymentIntent(dep, kind, reload) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace
	};
	const out = h("div", { "aria-live": "polite" });
	const d = drawer();
	let busy = false, accepted = false, preview = null;
	const scope = `deployment.${kind}.${dep.deployment_id}`;
	const confirm = h("button", {
		class: kind === "rollback" ? "danger" : "primary",
		disabled: true,
		"data-testid": `deployment-${kind}-confirm`,
		onclick: async () => {
			if (busy || accepted || !preview) return;
			busy = true;
			confirm.disabled = true;
			try {
				assertConnection(connection);
				const action = kind === "rollback" ? "deployment.rollback" : "deployment.start";
				const params = kind === "rollback" ? { deployment_id: dep.deployment_id } : {
					source_sha: dep.identity.source_sha,
					retry_of: dep.deployment_id
				};
				let op = await submit(action, { recipe: dep.recipe }, params, preview.preconditions, scope);
				while (["accepted", "running"].includes(op.status) && d.box.isConnected && !d.box.hidden) {
					await sleep(1e3);
					assertConnection(connection);
					if (!d.box.isConnected || d.box.hidden) break;
					op = (await api("GET", `/operations/${op.operation_id}`)).operation;
				}
				if ([
					"DEPLOY_PREVIEW_REQUIRED",
					"ENVIRONMENT_CHANGED",
					"RECIPE_CHANGED"
				].includes(op.error_code)) {
					fill(out, h("p", { class: "note warn" }, t("dep_stale_preview")), deploymentReceipt({ operation_id: op.operation_id }));
					await refreshPreview();
				} else {
					accepted = true;
					fill(out, h("p", {}, opStatus(op), " · ", h("a", { href: `#/op/${op.operation_id}` }, t("dep_open_operation"))), deploymentReceipt({ operation_id: op.operation_id }));
				}
			} catch (e) {
				fill(out, h("p", { class: "error" }, t("dep_refused")), heldDetails(t("dep_operation_details"), [errorBox(e)]));
				if ([
					"DEPLOY_PREVIEW_REQUIRED",
					"ENVIRONMENT_CHANGED",
					"RECIPE_CHANGED"
				].includes(e.code)) {
					out.prepend(h("p", { class: "note warn" }, t("dep_stale_preview")));
					await refreshPreview();
				}
			} finally {
				busy = false;
				confirm.disabled = accepted || !preview?.readiness?.ready;
			}
		}
	}, t(kind === "rollback" ? "dep_confirm_rollback" : "dep_confirm_retry"));
	const previewBox = h("div", {});
	async function refreshPreview() {
		preview = null;
		confirm.disabled = true;
		try {
			assertConnection(connection);
			preview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(dep.recipe)}`)).preview;
			fill(previewBox, deploymentPreviewSummary(preview), preview.readiness?.ready ? null : h("p", { class: "note warn" }, t("dep_missing_verification")));
			confirm.disabled = busy || accepted || !preview.readiness?.ready;
		} catch (e) {
			fill(previewBox, errorBox(e));
		}
	}
	fill(d.box, h("h3", {}, t(kind === "rollback" ? "dep_rollback_review" : "dep_retry_review")), deploymentIdentity(dep.identity), h("p", {}, `${dep.repository} · ${dep.environment}`), kind === "rollback" ? deploymentLimits(dep.rollback?.not_undone) : h("p", { class: "muted" }, t("dep_retry_only")), previewBox, out, h("div", { class: "actions" }, confirm, h("button", {
		class: "secondary",
		onclick: () => {
			d.box.querySelectorAll("details[open]").forEach((el) => el.closeHeld?.());
			d.close();
			reload();
		}
	}, t("close"))));
	return {
		button: h("button", {
			class: "secondary",
			"data-testid": `deployment-${kind}`,
			onclick: () => {
				if (!d.box.hidden) return;
				d.open();
				refreshPreview();
			}
		}, t(kind === "rollback" ? "dep_rollback" : "dep_retry", { sha: (dep.identity?.source_sha || "").slice(0, 8) })),
		box: d.box
	};
}
function deploymentRecord(dep, env, reload, compact = false) {
	if (!dep) return h("p", { class: "muted" }, t("dep_no_version"));
	const r = (state.caps?.deploy_recipes || []).find((r) => r.name === dep.recipe);
	dep = {
		...dep,
		repository: dep.repository || r?.repository || "",
		environment: dep.environment || r?.environment || env.environment || t("dep_no_version")
	};
	const canDeploy = Boolean(state.caps?.features?.deploy && r?.readiness?.ready && (state.caps?.actions || []).some((a) => a.action === "deployment.start" && a.allowed) && may("deploy"));
	const disabledReason = !may("deploy") ? "dep_needs_scope" : !r ? "dep_missing_recipe" : !r.readiness?.ready ? "dep_missing_verification" : "dep_disabled";
	const actions = [], drawers = [];
	if (!compact && dep.rollback_eligible && !dep.is_current) {
		const intent = deploymentIntent(dep, "rollback", reload);
		intent.button.disabled = !canDeploy || !(state.caps?.actions || []).some((a) => a.action === "deployment.rollback" && a.allowed);
		actions.push(intent.button);
		drawers.push(intent.box);
		if (intent.button.disabled) actions.push(h("span", { class: "muted" }, t(disabledReason)));
	}
	if (!compact && dep.state === "failed") {
		if (dep.provider_terminal && !dep.legacy && dep.identity?.source_sha) {
			const intent = deploymentIntent(dep, "retry", reload);
			intent.button.disabled = !canDeploy;
			actions.push(intent.button);
			drawers.push(intent.box);
			if (!canDeploy) actions.push(h("span", { class: "muted" }, t(disabledReason)));
		} else actions.push(h("span", { class: "muted" }, t(dep.provider_terminal ? "dep_retry_unavailable" : "dep_provider_pending")));
	}
	let rollbackReason = dep.rollback_reason;
	let providerUrl = null;
	try {
		const url = new URL(dep.provider_url);
		if (url.protocol === "https:") providerUrl = url.href;
	} catch {}
	if (rollbackReason === "ROLLBACK_ARTIFACT_UNAVAILABLE" && dep.identity?.artifact_expires_at && Date.parse(dep.identity.artifact_expires_at) <= Date.now()) rollbackReason = "ROLLBACK_ARTIFACT_EXPIRED";
	return h("div", {
		class: "deployment-record",
		"data-deployment": dep.deployment_id
	}, h("div", { class: "deployment-record-heading" }, deploymentState(dep.state), h("span", { class: "muted" }, dep.recipe)), deploymentIdentity(dep.identity), compact ? h("p", {}, h("a", { href: `#/op/${dep.operation_id}` }, t("dep_open_operation"))) : h("p", { class: "muted" }, `${dep.environment} · ${deploymentTime(dep.created_at)}`), dep.state === "superseded" ? h("p", {}, t("dep_superseded"), " ", env.desired ? h("a", { href: `#/op/${env.desired.operation_id}` }, t("dep_new_desired")) : null, " · ", providerUrl ? h("a", {
		href: providerUrl,
		target: "_blank",
		rel: "noopener"
	}, t("dep_provider_run")) : null) : null, dep.state === "needs_attention" || dep.reconciliation_error ? h("p", { class: "note warn" }, t("dep_attention")) : null, !compact && rollbackReason ? h("p", { class: "muted" }, t(`dep_${rollbackReason}`)) : null, !compact && dep.rollback_eligible && !dep.is_current ? deploymentLimits(dep.rollback?.not_undone) : null, actions.length ? h("div", { class: "actions" }, ...actions) : null, deploymentReceipt(dep), ...drawers);
}
function environmentCard(group) {
	const card = h("section", {
		class: "panel delivery-card environment-card",
		"data-environment": group[0].environment
	});
	const cursors = [null];
	let page = 0, next = null, loading = false, inFlight = null;
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	async function load(fromEvent = false) {
		if (inFlight) {
			await inFlight;
			if (fromEvent) return load(true);
			return;
		}
		const opens = drawerOpens;
		if (editing || fromEvent && typing()) {
			idleReload = () => load(true);
			return;
		}
		loading = true;
		inFlight = (async () => {
			try {
				assertView(connection);
				const query = new URLSearchParams({
					recipe: group[0].name,
					limit: "5"
				});
				if (cursors[page]) query.set("cursor", cursors[page]);
				const reads = await Promise.allSettled([api("GET", `/deployment-environments?recipe=${encodeURIComponent(group[0].name)}`), api("GET", `/deployment-environments/history?${query}`)]);
				assertView(connection);
				for (const read of reads) if (read.status === "rejected") throw read.reason;
				const [environment, history] = reads.map((read) => read.value);
				if (holdRender(fromEvent, opens) || editing) {
					idleReload = () => load(true);
					return;
				}
				const env = environment.environment;
				next = history.next_cursor;
				const observed = env.observed || env.current?.evidence?.runtime?.observed;
				const needs = env.attention || env.desired?.state === "needs_attention" || env.desired?.reconciliation_error || env.current?.state === "needs_attention" || env.current?.reconciliation_error;
				const previous = h("button", {
					class: "secondary",
					disabled: page === 0,
					"data-testid": "history-previous",
					onclick: () => {
						if (loading) return;
						previous.disabled = more.disabled = true;
						page -= 1;
						load();
					}
				}, t("dep_previous"));
				const more = h("button", {
					class: "secondary",
					disabled: !next,
					"data-testid": "history-next",
					onclick: () => {
						if (loading) return;
						previous.disabled = more.disabled = true;
						cursors[++page] = next;
						load();
					}
				}, t("dep_next"));
				const verified = env.last_verified;
				fill(card, h("div", { class: "deployment-card-heading" }, h("h2", {}, group[0].environment), needs ? chip(t("dep_attention"), "warn") : null), h("p", { class: "muted" }, group[0].repository, " · ", t("dep_generation", { generation: env.desired_generation })), needs ? h("p", { class: "note warn" }, t(env.attention === "ENVIRONMENT_VERSION_DRIFT" ? "dep_drift" : "dep_attention_help")) : null, h("div", { class: "deployment-versions" }, h("div", {}, h("h3", {}, t("dep_desired")), deploymentRecord(env.desired, env, load, true)), h("div", {}, h("h3", {}, t("dep_observed")), deploymentIdentity(observed), h("p", { class: "muted" }, t("dep_observed_at", { time: deploymentTime(observed?.observed_at || env.current?.evidence?.runtime?.checked_at) })), env.current?.evidence?.runtime?.summary ? h("p", { class: "muted" }, runtimeSummary(env.current.evidence.runtime)) : null)), h("div", { class: "deployment-last-verified" }, h("h3", {}, t("dep_last_verified")), deploymentIdentity(verified?.identity), h("p", { class: "muted" }, t("dep_verified_at", { time: deploymentTime(verified?.evidence?.runtime?.checked_at) })), verified?.evidence?.runtime?.summary ? h("p", { class: "muted" }, runtimeSummary(verified.evidence.runtime)) : null, verified ? deploymentReceipt(verified) : null), h("h3", {}, t("dep_history")), h("div", { "data-testid": "deployment-history" }, ...history.items.length ? history.items.map((dep) => deploymentRecord(dep, env, load)) : [h("p", { class: "muted" }, t("dep_no_history"))]), !history.items.length && group.every((r) => !r.rollback?.supported) ? h("p", { class: "muted" }, t("dep_ROLLBACK_UNSUPPORTED")) : null, h("div", { class: "actions deployment-pagination" }, previous, h("span", { class: "muted" }, t("dep_page", { page: page + 1 })), more));
			} catch (e) {
				if (["CONNECTION_CHANGED", "VIEW_CHANGED"].includes(e.code)) return;
				const failure = errorBox(e);
				if (!holdRender(fromEvent, opens) && !editing) fill(card, failure);
			}
		})();
		try {
			await inFlight;
		} finally {
			loading = false;
			inFlight = null;
		}
	}
	return {
		card,
		load
	};
}
function runtimeSummary(evidence) {
	return t(evidence.version_checked ? evidence.health_checked ? "dep_version_health" : "dep_version_only" : "dep_health_only");
}
function metadataDrawer(pr, reload) {
	const title = h("input", {
		value: pr.title || "",
		"data-testid": "metadata-title"
	});
	const body = h("textarea", { "data-testid": "metadata-body" }, pr.body || "");
	const initialBody = body.value;
	const out = h("div", { "aria-live": "polite" });
	let d;
	const save = h("button", {
		class: "primary",
		"data-testid": "metadata-save",
		onclick: async () => {
			const params = {};
			if (title.value !== (pr.title || "")) params.title = title.value;
			if (body.value !== initialBody) params.body = body.value;
			if (!Object.keys(params).length) return;
			save.disabled = true;
			try {
				const op = await submit("github.pr.update", {
					repository: pr.repository,
					pull_number: pr.pull_number
				}, params, { expected_metadata_digest: pr.metadata_digest }, `pr_metadata.${pr.repository}.${pr.pull_number}.${pr.metadata_digest}`);
				const diff = op.external_refs?.metadata_difference;
				const contents = diff ? h("details", {
					class: "row-details",
					open: true
				}, h("summary", {}, t("metadata_diff")), ...[
					["metadata_before", diff.observed ? diff.before : {
						title: pr.title,
						body: pr.body
					}],
					["metadata_intended", diff.after || diff.intended],
					["metadata_observed", diff.observed || diff.before]
				].map(([label, value]) => h("div", {}, h("strong", {}, t(label)), h("pre", { class: "pre" }, JSON.stringify(value, null, 2))))) : null;
				fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id), op.error_code ? chip(op.error_code, "bad") : null, contents, h("p", { class: "muted" }, t("metadata_result_help")));
				idleReload = () => reload();
			} catch (e) {
				fill(out, errorBox(e));
				save.disabled = false;
			}
		}
	}, t("save"));
	const close = h("button", {
		class: "secondary",
		"data-testid": "metadata-close",
		onclick: () => d.close()
	}, t("close"));
	d = drawer(h("label", {}, t("metadata_title"), title), h("label", {}, t("description"), body), h("p", { class: "muted" }, t("metadata_race_limit")), h("div", { class: "actions" }, save, close), out);
	return h("div", {}, h("button", {
		class: "secondary",
		"data-testid": "metadata-edit",
		disabled: !pr.metadata_update.allowed || !may("integrate"),
		title: !may("integrate") ? t("needs_integrate_scope") : !pr.metadata_update.allowed ? t("metadata_disabled") : null,
		onclick: () => d.open()
	}, t("metadata_edit")), d.box);
}
function integrationPanel(pr, reloadCard, source = null) {
	const box = h("div", {
		class: "panel",
		"data-integration-review": true
	});
	const may = (state.caps?.scopes || []).includes("integrate");
	const hosts = pr.integration.hosts;
	box.append(h("h2", {}, t("update_pr_results")), h("p", { class: "muted" }, t("update_pr_help")));
	if (!may) {
		box.append(h("p", { class: "note" }, t("needs_integrate_scope")));
		return box;
	}
	if (!hosts.length) {
		box.append(h("p", { class: "note" }, t("integration_no_host")));
		return box;
	}
	if (source && (!hosts.includes(source.host) || state.caps?.features?.execution_delivery?.version !== 1)) {
		box.append(h("p", { class: "note" }, t("delivery_source_unavailable")));
		return box;
	}
	const target = {
		host: source?.host || hosts[0],
		repository: pr.repository,
		pull_number: Number(pr.pull_number)
	};
	const selected = [];
	let holdingReview = false;
	box.closeReview = () => {
		if (holdingReview) {
			holdingReview = false;
			setEditing(editing - 1);
		}
	};
	const holdReview = () => {
		if (selected.length && !holdingReview) {
			holdingReview = true;
			drawerOpens++;
			setEditing(editing + 1);
		} else if (!selected.length) box.closeReview();
	};
	const pickList = h("div", {});
	const order = h("div", {});
	const previewBox = h("div", {});
	const status = h("div", {});
	let doc = null;
	let generation = 0;
	const rerender = () => {
		holdReview();
		order.replaceChildren(...selected.map((s, i) => h("div", { class: "row" }, h("div", { class: "grow" }, `${i + 1}. `, chip(t("kind_" + s.kind)), " ", h("code", {}, s.label)), h("button", {
			class: "secondary",
			disabled: i === 0,
			onclick: () => {
				selected.splice(i - 1, 0, selected.splice(i, 1)[0]);
				changed();
			}
		}, "↑"), h("button", {
			class: "secondary",
			disabled: i === selected.length - 1,
			onclick: () => {
				selected.splice(i + 1, 0, selected.splice(i, 1)[0]);
				changed();
			}
		}, "↓"), h("button", {
			class: "secondary",
			onclick: () => {
				selected.splice(i, 1);
				changed();
			}
		}, "×"))));
	};
	const freshHead = async () => {
		try {
			pr.head_sha = (await api("GET", `/repositories/${pr.repository}/pulls/${pr.pull_number}`)).pull_request.head_sha;
		} catch {}
	};
	const runPreview = async () => {
		const mine = ++generation;
		doc = null;
		if (!selected.length) {
			previewBox.replaceChildren();
			return;
		}
		previewBox.replaceChildren(h("p", { class: "muted" }, t("previewing")));
		try {
			let op = await submit("integration.preview", target, { sources: selected.map(({ kind, id }) => ({
				kind,
				id
			})) }, { expected_head_sha: pr.head_sha }, `preview.${pr.repository}.${pr.pull_number}`);
			while (!TERMINAL.includes(op.status) && op.status !== "needs_attention" && box.isConnected && mine === generation) {
				await sleep(1e3);
				op = (await api("GET", `/operations/${op.operation_id}`)).operation;
			}
			if (mine !== generation || !box.isConnected) return;
			if (op.status !== "succeeded") {
				previewBox.replaceChildren(h("p", { class: "error" }, `${op.error_code || op.status} ${op.status_reason || ""}`));
				return;
			}
			doc = op.result;
			renderPreview();
		} catch (e) {
			if (mine === generation) previewBox.replaceChildren(errorBox(e));
		}
	};
	const changed = debounce(() => {
		rerender();
		runPreview();
	}, 600);
	const add = (kind, id, label) => {
		if (!selected.some((s) => s.kind === kind && s.id === id)) selected.push({
			kind,
			id,
			label
		});
		holdReview();
		changed();
	};
	const plain = (w) => h("li", {}, w.text);
	const renderPreview = () => {
		const expired = Date.now() / 1e3 > doc.expires_at || doc.target.head_sha !== pr.head_sha;
		const conflictAt = doc.sources.find((s) => s.predicted === "conflict");
		const go = h("button", {
			class: "primary",
			disabled: !doc.ready || expired,
			onclick: async () => {
				go.disabled = true;
				try {
					const req = {
						action: "integration.apply",
						target,
						params: { preview_id: doc.preview_id },
						preconditions: {
							expected_head_sha: doc.target.head_sha,
							preview_digest: doc.digest
						}
					};
					follow((await api("POST", "/operations?wait=3", req, "integrate." + doc.preview_id)).operation);
				} catch (e) {
					status.replaceChildren(errorBox(e));
					go.disabled = false;
				}
			}
		}, conflictAt ? t("start_integration_conflict", { n: conflictAt.seq }) : t("update_pr_results"));
		previewBox.replaceChildren(...[
			h("p", {}, h("code", {}, `${doc.repository} #${doc.pull_number} · ${doc.target.head_ref} @ ${doc.target.head_sha.slice(0, 12)}`), " → ", t("normal_push"), " · ", t("push_access_" + doc.target.push_access)),
			...doc.sources.map((s) => h("details", { class: "row-details" }, h("summary", {}, `${s.seq}. `, chip(t("plan_" + (s.predicted || "not_predicted")), s.predicted === "conflict" ? "bad" : ""), " ", h("code", {}, s.label), " · ", t("n_commits", { n: s.commits_total }), " · ", t("n_files", { n: s.files_total }), s.conflict_files.length ? h("span", { class: "error" }, " · ", s.conflict_files.join(", ")) : null), h("ul", {}, ...s.commits.map((c) => h("li", {}, h("code", {}, c.sha.slice(0, 10)), ` ${c.subject} — ${c.author}`, c.origin === "foreign" ? h("span", { class: "error" }, " · ", t("foreign_commit")) : null))), s.warnings.length ? h("ul", { class: "muted" }, ...s.warnings.map(plain)) : null)),
			doc.overlaps.length ? h("p", { class: "muted" }, t("overlapping_files"), " ", doc.overlaps.map((o) => `${o.path} (${o.seqs.join(", ")}${o.also_changed_on_pr ? ", PR" : ""})`).join("; ")) : null,
			doc.blocking.length ? h("ul", { class: "error" }, ...doc.blocking.map(plain)) : null,
			doc.warnings.length ? h("ul", { class: "muted" }, ...doc.warnings.map(plain)) : null,
			h("p", { class: "muted" }, expired ? t("preview_expired") : t("previewed_at", { time: when(epoch(doc.observed_at)) }), " ", h("a", {
				href: "#",
				onclick: (ev) => {
					ev.preventDefault();
					runPreview();
				}
			}, t("preview_again"))),
			h("div", { class: "actions" }, go)
		].filter(Boolean));
	};
	const follow = async (op) => {
		for (;;) {
			if (!box.isConnected) return;
			status.replaceChildren(integrationStatus(op, {
				resume: async () => {
					try {
						follow((await api("POST", `/operations/${op.operation_id}/resume`, {})).operation);
					} catch (e) {
						status.append(errorBox(e));
					}
				},
				cancel: async () => {
					await api("POST", `/operations/${op.operation_id}/cancel`, {});
					await freshHead();
					runPreview();
				}
			}));
			if (TERMINAL.includes(op.status) || op.status === "needs_attention") break;
			await sleep(1500);
			op = (await api("GET", `/operations/${op.operation_id}`)).operation;
		}
		if (op.status === "succeeded") {
			box.closeReview();
			reloadCard(integrationStatus(op, {}));
		} else if (["TARGET_HEAD_CHANGED", "SOURCE_CHANGED"].includes(op.error_code)) {
			await freshHead();
			runPreview();
		}
	};
	const branch = h("input", { placeholder: t("branch_on_github") });
	(async () => {
		try {
			const query = new URLSearchParams({ host: target.host });
			if (source) {
				query.set("source_kind", source.kind);
				query.set("source_id", source.id);
			}
			const c = await api("GET", `/integrations/candidates?${query}`);
			const row = (kind, id, label, chips, eligible = true) => h("div", {
				class: "row",
				"data-delivery-source": id
			}, h("div", { class: "grow" }, h("code", {}, label), " ", ...chips), h("button", {
				class: "secondary",
				disabled: !eligible,
				onclick: () => add(kind, id, label)
			}, t("add")));
			const delivered = (x) => (x.delivered_to || []).map((receipt) => receipt.repository ? h("a", {
				href: `https://github.com/${receipt.repository}/pull/${receipt.pull_number}`,
				target: "_blank",
				rel: "noopener",
				title: `${receipt.repository} · ${receipt.pinned_sha || ""} → ${receipt.delivered_sha || ""}`
			}, t("delivered_to", { n: receipt.pull_number })) : chip(t("delivered_to", { n: receipt.pull_number })));
			const evidence = (r) => {
				const session = r.session || { streaming: r.streaming }, activity = sessionActivity(session);
				return [
					chip(t(activity.key), activity.tone),
					session.pending && runtimeStale(session) ? chip(t("sessions_stale"), "stale") : null,
					h("p", { class: "muted" }, t("delivery_result_unverified")),
					h("p", { class: "muted" }, session.observed_at ? t("delivery_observed_at", { time: when(typeof session.observed_at === "number" ? epoch(session.observed_at) : session.observed_at) }) : t("delivery_unobserved")),
					r.unavailable ? h("p", { class: "note" }, t("delivery_source_unavailable"), " ", h("code", {}, r.unavailable.code)) : null,
					...delivered(r)
				];
			};
			const results = source ? c.selected && c.selected.kind === source.kind && c.selected.id === source.id && c.selected.host === source.host ? [c.selected] : [] : c.agent_results;
			pickList.replaceChildren(h("h3", {}, t("agent_results")), ...results.length ? results.map((r) => row(r.kind || "checkpoint_run", r.id, r.branch || r.id, evidence(r), r.eligible !== false)) : [h("p", { class: "muted" }, t("none"))], h("h3", {}, t("your_checkpoints")), ...c.checkpoints.length ? c.checkpoints.map((r) => row("checkpoint", r.id, `${r.branch || "?"} @ ${r.commit_sha.slice(0, 10)}`, [r.note ? h("span", { class: "muted" }, r.note.slice(0, 60)) : null, ...delivered(r)])) : [h("p", { class: "muted" }, t("none"))], h("div", { class: "actions" }, branch, h("button", {
				class: "secondary",
				onclick: () => {
					if (branch.value.trim()) add("branch", branch.value.trim(), branch.value.trim());
					branch.value = "";
				}
			}, t("add_branch"))));
		} catch (e) {
			pickList.replaceChildren(errorBox(e));
		}
	})();
	box.append(pickList, h("h3", {}, t("selected_in_order")), order, previewBox, status);
	return box;
}
function repairControl(op) {
	const conflict = [
		"INTEGRATION_CONFLICT",
		"RESOLUTION_INCOMPLETE",
		"RESOLUTION_INVALID"
	].includes(op.error_code);
	const out = h("div", {});
	let handoff = null;
	let repair = null;
	if (conflict && (state.caps?.scopes || []).includes("start")) {
		const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
		const go = h("button", {
			class: "secondary",
			onclick: async () => {
				go.disabled = true;
				try {
					const o = await submit("integration.handoff", { operation_id: op.operation_id }, { agent: agent.value }, {}, `handoff.${op.operation_id}`);
					out.append(h("p", {}, opStatus(o), " ", t("handoff_started"), " ", h("a", { href: `#/op/${o.operation_id}` }, o.operation_id)));
				} catch (e) {
					out.append(errorBox(e));
				}
				go.disabled = false;
			}
		}, t("start_agent_work"));
		const d = drawer(confinementNote(op.target?.host || op.external_refs?.host, agent), h("div", { class: "actions" }, agent, go));
		repair = d.box;
		handoff = h("button", {
			class: "secondary",
			onclick: () => d.toggle.click()
		}, t("hand_to_agent"));
	}
	if (handoff) out.append(handoff, repair);
	return out;
}
function integrationStatus(op, act) {
	const code = op.error_code;
	const text = op.status === "succeeded" ? t("integration_done", {
		old: op.result.old_head.slice(0, 7),
		new: op.result.new_head.slice(0, 7),
		n: op.result.added_commits ?? "?"
	}) : op.status === "needs_attention" ? t("integration_" + code) !== "integration_" + code ? t("integration_" + code) : op.status_reason : op.status === "uncertain" ? t("integration_uncertain") : op.status === "waiting_external" ? (op.external_refs || {}).conflict ? t("integration_waiting_resolver") : (op.external_refs || {}).pushed_sha ? t("integration_waiting") : op.status_reason || t("integration_running") : op.status === "failed" ? `${code}: ${op.status_reason || ""}` : t("integration_running");
	const out = h("div", {});
	const handoff = repairControl(op);
	const buttons = op.status === "needs_attention" ? [
		h("button", {
			class: "primary",
			onclick: act.resume
		}, t("resume")),
		handoff,
		h("button", {
			class: "danger",
			onclick: act.cancel
		}, t("cancel_and_preview"))
	].filter(Boolean) : [];
	out.append(h("p", {}, opStatus(op), " ", text, " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id)), h("div", { class: "actions" }, ...buttons));
	return out;
}
async function viewOperations(main, filter = "all") {
	const statuses = {
		attention: "needs_attention,uncertain",
		active: "accepted,running,waiting_checks,waiting_external"
	}[filter];
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const list = operationList({
		h,
		t,
		api,
		guard: () => assertView(connection),
		row: opRow,
		statuses
	});
	main.append(h("h1", {}, t("nav_operations")), h("div", { class: "actions" }, ...[
		["all", "operations_all"],
		["attention", "tab_needs_you"],
		["active", "tab_to_confirm"]
	].map(([id, label]) => h("a", {
		href: `#/operations/${id}`,
		class: filter === id ? "on" : ""
	}, t(label)))), list.box);
	await list.load().catch(() => {});
	const reload = debounceRefresh(() => list.load(), 500);
	return onEvents((ev) => {
		if (ev.resource_type === "operation") return reload();
	});
}
async function viewOperation(main, id) {
	freshPage();
	const panel = h("div", { class: "panel" });
	main.append(panel);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		try {
			const { operation: op, work_items: linked, cleanup_receipts: cleanupReceipts } = await api("GET", `/operations/${id}`);
			const refs = op.external_refs || {};
			const retry = refs.merged_sha && op.action === "delivery.merge_and_deploy" && op.status === "failed" ? h("button", {
				class: "primary",
				onclick: async () => {
					try {
						const preview = (await api("GET", `/deployments/preview?recipe=${encodeURIComponent(op.target.recipe)}`)).preview;
						const o = await submit("deployment.start", { recipe: op.target.recipe }, { source_sha: refs.merged_sha }, preview.preconditions, `deploy.${op.target.recipe}.${refs.merged_sha}`);
						location.hash = `#/op/${o.operation_id}`;
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("retry_deploy")) : null;
			const needsConfirm = op.action === "checkpoint.continue" && ["SOURCE_MOVED", "SOURCE_UNAVAILABLE"].includes(op.error_code);
			const resume = op.status === "needs_attention" && !needsConfirm ? h("button", {
				class: "primary",
				title: t("resume_help"),
				onclick: async () => {
					try {
						await api("POST", `/operations/${id}/resume`, {});
						render();
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t(op.action === "worktree.merge" ? "delivery_merge_read_receipts" : "resume")) : null;
			const confirmSource = op.status === "needs_attention" && needsConfirm ? h("button", {
				class: "primary",
				onclick: async () => {
					const connection = {
						epoch: state.epoch,
						namespace: state.namespace,
						generation
					};
					try {
						const seen = (await api("GET", `/checkpoints/${op.target.checkpoint_id}?live=true`)).source.head;
						assertView(connection);
						if (!seen) throw new Error(t("source_unavailable"));
						await submit("checkpoint.continue.revalidate", { operation_id: id }, { observed_source_head_sha: seen }, { expected_input_manifest_digest: refs.input_manifest_digest }, `revalidate.${id}.${seen}`);
						render();
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("confirm_source")) : null;
			const materialized = refs.materializations || op.result?.materializations || [];
			const opened = op.result?.session_id && op.result?.host ? h("a", {
				class: "secondary",
				href: `#/session/${encodeURIComponent(op.result.host)}/${encodeURIComponent(op.result.session_id)}`
			}, t("open_new_session")) : null;
			let receipts = null;
			if (op.action === "integration.apply") {
				const rows = (await api("GET", `/integrations/${id}`)).receipts;
				receipts = [h("h2", {}, t("receipts")), ...rows.map((r) => h("div", { class: "row" }, h("div", { class: "grow" }, `${r.seq}. ${t("kind_" + r.source_kind)} `, h("code", {}, r.source_id.slice(0, 15)), " ", h("code", {}, `${r.pinned_sha.slice(0, 10)} → ${(r.integrated_sha || "").slice(0, 10)}`), r.conflict_files ? h("span", { class: "error" }, " ", r.conflict_files.join(", ")) : null), chip(r.method || "-"), chip(t("receipt_" + r.effective_status), r.effective_status === "delivered" ? "ok" : "")))];
			}
			const cancel = !TERMINAL.includes(op.status) ? h("button", {
				class: "danger",
				onclick: async () => {
					try {
						await api("POST", `/operations/${id}/cancel`, {});
						render();
					} catch (e) {
						panel.append(errorBox(e));
					}
				}
			}, t("cancel")) : null;
			if (!panel.isConnected) return;
			if (holdRender(fromEvent, opens)) {
				idleReload = () => render(true);
				return;
			}
			freshPage();
			fill(panel, h("h1", {}, op.action), h("p", { class: "op-status" }, opStatus(op), " ", op.error_code ? chip(op.error_code, "bad") : null), ...linked?.length ? [linkedItems(linked)] : [], h("dl", { class: "kv" }, h("dt", {}, t("actor")), h("dd", {}, `${op.actor} (${op.entry})`), h("dt", {}, t("created")), h("dd", {}, when(epoch(op.created_at))), op.status_reason ? [h("dt", {}, t("reason")), h("dd", {}, op.status_reason)] : null, h("dt", {}, "Target"), h("dd", {}, h("code", {}, JSON.stringify(op.target))), Object.keys(refs).length && op.action !== "worktree.merge" ? [h("dt", {}, "Refs"), h("dd", {}, h("code", {}, JSON.stringify(refs)))] : null, op.result && op.action !== "worktree.merge" ? [h("dt", {}, "Result"), h("dd", {}, h("code", {}, JSON.stringify(op.result)))] : null), ...receipts || [], mergeRecovery(op), op.action === "worktree.merge" ? h("details", {}, h("summary", {}, t("sessions_details")), h("pre", { class: "pre" }, JSON.stringify({
				refs,
				result: op.result
			}, null, 2))) : null, ...materialized.length ? [h("h2", {}, t("materializations")), ...materialized.map((m) => h("div", { class: "row" }, h("div", { class: "grow" }, `${m.artifact_id} · r${m.revision}`, h("div", { class: "muted" }, m.managed_path)), chip(t(`material_${m.state}`), m.state === "verified" ? "ok" : "")))] : [], ...cleanupReceipts?.length ? [h("h2", {}, t("cleanup_open_receipts")), ...cleanupReceipts.map((r) => h("details", { class: "row-details" }, h("summary", {}, r.resource_id, " · ", t("cleanup_receipt_" + r.status)), h("pre", { class: "pre" }, JSON.stringify(r, null, 2))))] : [], ...op.action === "integration.apply" ? [repairControl(op)] : [], (op.result?.merge || op.result || refs.merge_receipt)?.base_moved ? h("p", { class: "note warn" }, t("merged_newer_base", { count: (op.result?.merge || op.result || refs.merge_receipt).other_commits_count })) : null, refs.write_acknowledged && refs.verification_pending ? h("p", { class: "note warn" }, t("metadata_pending")) : null, h("h2", {}, t("steps")), ...op.steps.map((s) => h("div", { class: "row" }, h("div", { class: "grow" }, s.name), h("span", { class: `status-${s.status}` }, s.status), s.error ? chip(s.error.code || t("error"), "bad") : null)), h("div", { class: "actions" }, opened, ["artifact.capture.managed", "artifact.accept"].includes(op.action) && op.status === "succeeded" && /^art_[0-9a-f]{32}$/.test(op.result?.artifact_id) && Number.isSafeInteger(op.result?.revision) && op.result.revision > 0 ? h("a", { href: `#/artifact-review/artifact/${op.result.artifact_id}/${op.result.revision}` }, t("ar_review_title")) : null, state.caps?.artifacts?.capture?.managed_single_file && managedCaptureExecution(op) ? h("a", { href: `#/artifact-review/operation/${op.operation_id}` }, t("ar_open")) : null, confirmSource, resume, retry, cancel));
		} catch (e) {
			fill(panel, errorBox(e));
		}
	};
	await render();
	return liveReload(render, [
		"operation",
		"integration",
		"cleanup"
	]);
}
function mergeRecovery(op) {
	if (op.action !== "worktree.merge") return null;
	const steps = op.steps || [], refs = op.external_refs || {};
	const reserved = steps.some((s) => s.name === "merge.reserve" && s.status === "succeeded");
	const released = steps.some((s) => s.name === "merge.release" && s.status === "succeeded");
	if (!reserved || released) return null;
	const frames = steps.filter((s) => ["rehydrate.frame", "merge.frame"].includes(s.name));
	return h("section", {
		class: "panel",
		"data-merge-recovery": true
	}, h("h2", {}, t("delivery_merge_recovery")), h("p", { class: "note" }, t("delivery_merge_held")), h("dl", { class: "kv" }, ...["source", "destination"].flatMap((label, i) => [h("dt", {}, t("delivery_merge_" + label)), h("dd", {}, h("code", {}, refs.carrier_paths?.[i] || t("obs_unknown")))])), ...frames.map((step) => h("p", {}, h("code", {}, step.name), " · ", t(step.status === "succeeded" ? "delivery_merge_ack" : "delivery_merge_no_ack"), " · ", observationTime(step.finished_at || step.started_at))), h("p", {}, t("delivery_merge_safe_reads")), h("p", { class: "muted" }, t("delivery_merge_closeout")), refs.host && refs.session_id ? observationLink("session", `${refs.host}/${refs.session_id}`) : null);
}
function viewSettings(main) {
	if (nativeDesktop) return viewNativeSettings(main);
	if (state.token === "managed-browser-session") {
		main.append(h("h1", {}, t("nav_settings")), h("section", { class: "panel" }, h("h2", {}, t("managed_browser_connected")), h("p", {}, t("connected_as", {
			actor: state.caps.actor,
			scopes: state.caps.scopes.join(", ")
		})), h("p", { class: "muted" }, t("managed_browser_help")), h("button", {
			class: "secondary",
			onclick: () => {
				disconnect();
				route();
			}
		}, t("disconnect"))));
		return mountTailscale(main, {
			h,
			t
		});
	}
	const input = h("input", {
		type: "password",
		autocomplete: "off",
		placeholder: "batc_…"
	});
	const remember = h("input", { type: "checkbox" });
	const info = h("p", { class: "muted" });
	if (state.caps) info.textContent = t("connected_as", {
		actor: state.caps.actor,
		scopes: state.caps.scopes.join(", ")
	});
	else if (state.connectionError) info.replaceChildren(errorBox(state.connectionError));
	main.append(h("h1", {}, t("nav_settings")), h("div", { class: "panel" }, h("div", { class: "filters connection-controls" }, h("label", { class: "connection-token" }, t("token"), input), h("button", {
		class: "primary",
		onclick: async () => {
			disconnect();
			state.token = input.value.trim();
			try {
				await activate(await api("GET", "/capabilities"));
				saveToken(state.token, remember.checked);
				location.hash = "#/home";
				await route();
			} catch (e) {
				state.token = null;
				info.replaceChildren(errorBox(e));
			}
		}
	}, t("connect")), h("button", {
		class: "secondary",
		onclick: () => {
			disconnect();
			route();
		}
	}, t("disconnect"))), h("label", {}, remember, " ", t("remember")), h("p", { class: "muted" }, t("token_help")), info));
	return mountTailscale(main, {
		h,
		t
	});
}
async function nativeTransition(kind, config = null) {
	if (state.nativeBusy && kind !== "disconnect") return;
	const attempt = ++state.nativeAttempt;
	const previousOnline = state.online;
	const previousToken = state.token;
	state.nativeBusy = true;
	state.epoch++;
	state.online = false;
	state.connectionError = null;
	state.connectionNotice = null;
	try {
		if (kind === "configure") {
			const saved = await nativeSetupConfiguration(config);
			if (attempt !== state.nativeAttempt) return;
			if (saved) {
				state.nativeSetupDraft = null;
				state.connectionNotice = t("desktop_setup_saved");
			} else {
				state.online = previousOnline;
				state.connectionNotice = t("desktop_setup_cancelled");
			}
		} else if (kind === "disconnect" || kind === "reload" || kind === "forget") {
			disconnect();
			if (kind === "disconnect") await nativeDisconnect();
			else if (kind === "reload") await nativeReloadConfiguration();
			else await nativeForgetCredential();
			if (attempt === state.nativeAttempt) state.connectionNotice = t(kind === "forget" ? "desktop_forgotten" : kind === "reload" ? "desktop_reloaded" : "desktop_disconnected");
		} else {
			const status = await nativeStatus();
			if (attempt !== state.nativeAttempt) return;
			const caps = kind === "enroll" ? await nativeEnroll() : await nativeConnect();
			if (attempt !== state.nativeAttempt) return;
			if (!caps) {
				state.online = previousOnline;
				state.connectionNotice = t("desktop_enrollment_cancelled");
			} else {
				state.token = "native-credential";
				try {
					await activate(caps, status.endpoint);
				} catch (error) {
					if (attempt === state.nativeAttempt) {
						await nativeDisconnect();
						disconnect();
					}
					throw error;
				}
				if (kind === "connect" && attempt === state.nativeAttempt) location.hash = "#/home";
			}
		}
	} catch (error) {
		if (attempt !== state.nativeAttempt) return;
		state.connectionError = error;
		if (state.token === previousToken) state.online = previousOnline;
	} finally {
		if (attempt === state.nativeAttempt) {
			state.nativeBusy = false;
			await route();
		}
	}
}
async function viewNativeSettings(main) {
	const mine = generation;
	const info = h("div", { "aria-live": "polite" });
	const details = h("dl", { class: "kv" });
	const technicalDetails = h("dl", { class: "kv" });
	const setup = h("div", {
		"data-native-setup": "",
		hidden: true
	});
	const help = h("p", { class: "muted" }, t("desktop_credential_help"));
	const platform = h("p", { class: "muted" });
	const fleetRoot = h("div");
	const updateRoot = h("div");
	let disposeUpdates;
	let firstConnection = false;
	const controls = [];
	const action = (kind, label, cls = "secondary") => {
		const button = h("button", {
			class: cls,
			disabled: true,
			onclick: () => {
				for (const control of controls) control.disabled = true;
				if (kind === "connect" || kind === "enroll") leave.disabled = false;
				info.textContent = t("desktop_connecting");
				return nativeTransition(kind);
			}
		}, t(label));
		controls.push(button);
		return button;
	};
	const connect = action("connect", "connect", "primary");
	const enroll = action("enroll", "desktop_add_credential");
	const reload = action("reload", "desktop_reload_configuration");
	const forget = action("forget", "desktop_forget_credential");
	const leave = action("disconnect", "disconnect");
	const actions = h("div", { class: "actions" }, connect, enroll, reload, leave);
	const saved = h("div", {}, h("p", { class: "muted" }, t("desktop_forget_help")), forget);
	const connectionDetails = h("details", {}, h("summary", {}, t("connection_details")), technicalDetails, help);
	const introduction = h("details", {}, h("summary", {}, t("delivery_setup_title")), h("ol", {}, h("li", {}, t("delivery_setup_central")), h("li", {}, t("delivery_setup_identity")), h("li", {}, t("delivery_setup_mode"))));
	const localDetails = h("details", { class: "panel" }, h("summary", {}, t("desktop_local")), h("p", { class: "muted" }, t("desktop_dashboard_only")));
	main.append(h("h1", {}, t("nav_settings")), h("section", {
		class: "panel native-connection",
		"aria-label": t("desktop_connection")
	}, h("h2", {}, t("desktop_connection")), setup, details, platform, actions, info, connectionDetails, introduction, saved), localDetails, fleetRoot, updateRoot);
	const showInfo = () => {
		info.replaceChildren();
		if (state.caps) info.append(h("p", {}, t("connected_as", {
			actor: state.caps.actor,
			scopes: state.caps.scopes.join(", ")
		})));
		if (state.connectionNotice) info.append(h("p", {}, state.connectionNotice));
		if (state.connectionError) info.append(errorBox(state.connectionError));
		if (state.nativeBusy) info.append(h("p", {}, t("desktop_connecting")));
	};
	showInfo();
	try {
		const status = await nativeStatus();
		if (mine !== generation || !main.contains(details)) return;
		if (status.updates === true) disposeUpdates = await mountUpdates(updateRoot, {
			h,
			t
		});
		if (mine !== generation || !main.contains(details)) {
			disposeUpdates?.();
			return;
		}
		const row = (label, value) => {
			if (value) details.append(h("dt", {}, t(label)), h("dd", {}, value));
		};
		if (status.configuration_setup === true) {
			firstConnection = true;
			setup.hidden = false;
			details.hidden = true;
			actions.hidden = true;
			platform.hidden = true;
			localDetails.hidden = true;
			const draft = state.nativeSetupDraft ||= {
				endpoint: "",
				expected_actor: ""
			};
			const endpoint = h("input", {
				type: "url",
				value: draft.endpoint,
				placeholder: "https://connector.example",
				required: true,
				maxlength: 512,
				disabled: state.nativeBusy,
				autocomplete: "off",
				oninput: (event) => {
					draft.endpoint = event.target.value;
				}
			});
			const actor = h("input", {
				value: draft.expected_actor,
				required: true,
				maxlength: 200,
				disabled: state.nativeBusy,
				autocomplete: "off",
				oninput: (event) => {
					draft.expected_actor = event.target.value;
				}
			});
			const review = h("button", {
				type: "submit",
				class: "primary",
				disabled: state.nativeBusy
			}, t("desktop_setup_review"));
			const form = h("form", { onsubmit: (event) => {
				event.preventDefault();
				if (state.nativeBusy || !form.reportValidity()) return;
				review.disabled = true;
				return nativeTransition("configure", {
					endpoint: endpoint.value.trim(),
					expected_actor: actor.value.trim(),
					contract_version: "2026-10-08"
				});
			} }, h("p", {}, t("desktop_setup_help")), h("div", { class: "capture-fields" }, h("label", {}, t("desktop_endpoint"), endpoint), h("label", {}, t("desktop_expected_actor"), actor)), h("p", { class: "muted" }, t("desktop_setup_origin")), h("div", { class: "actions" }, review));
			setup.append(form);
			connectionDetails.append(h("div", { class: "actions" }, reload));
		}
		row("desktop_endpoint", status.endpoint || t("desktop_config_needed"));
		row("desktop_expected_actor", status.expected_actor);
		if (status.configuration_file) technicalDetails.append(h("dt", {}, t("desktop_configuration_file")), h("dd", {}, status.configuration_file));
		if (status.credential_source) row("desktop_credential_source", t("desktop_source_" + status.credential_source));
		if (status.error && !status.configuration_setup) info.append(errorBox(new Error(status.error)));
		else if (!status.credential_available && !status.configuration_setup) info.append(h("p", {}, t("desktop_credential_missing")));
		platform.textContent = status.enrollment_supported === true ? t("desktop_enrollment_help") : status.enrollment_supported === false ? t("desktop_enrollment_unsupported") : "";
		connect.disabled = state.nativeBusy || !!status.error || !status.credential_available;
		enroll.hidden = status.enrollment_supported !== true;
		enroll.textContent = t(status.credential_saved ? "desktop_replace_credential" : "desktop_add_credential");
		enroll.disabled = state.nativeBusy || !status.endpoint || !status.expected_actor;
		enroll.className = status.credential_available ? "secondary" : "primary";
		if (!status.credential_available) connect.className = "secondary";
		reload.hidden = !status.configuration_reload;
		reload.disabled = state.nativeBusy || !status.configuration_reload;
		leave.disabled = !state.token && !state.nativeBusy;
		saved.hidden = !status.credential_saved;
		forget.disabled = state.nativeBusy || !status.credential_saved;
	} catch (error) {
		if (mine === generation) info.append(errorBox(error));
	}
	if (mine !== generation) return;
	if (firstConnection) return () => disposeUpdates?.();
	const disposeFleet = await mountFleet(fleetRoot, {
		h,
		t
	});
	if (mine !== generation || !main.isConnected) {
		disposeFleet?.();
		disposeUpdates?.();
		return;
	}
	const disposeTailscale = mountTailscale(fleetRoot, {
		h,
		t
	});
	return () => {
		disposeFleet?.();
		disposeUpdates?.();
		disposeTailscale();
	};
}
var may = (scope) => (state.caps?.scopes || []).includes(scope);
function fill(el, ...kids) {
	el.replaceChildren(...kids.flat(2).filter((x) => x !== null && x !== void 0 && x !== false));
}
var PROJECT_ERRORS = [
	"VERSION_CONFLICT",
	"ORDER_CHANGED",
	"PIN_CHANGED",
	"CONTENT_CHANGED",
	"NAME_TAKEN",
	"HAS_CHILDREN",
	"PARENT_ARCHIVED",
	"PINNED_FIRST",
	"STEPS_OPEN",
	"CYCLE",
	"LINK_TARGET_NOT_FOUND",
	"NOTHING_TO_DECIDE"
];
function problem(code, message) {
	return h("p", { class: "error" }, PROJECT_ERRORS.includes(code) ? t("wi_err_" + code) : `${code || ""} ${message || ""}`);
}
var STALE = [
	"VERSION_CONFLICT",
	"ORDER_CHANGED",
	"PIN_CHANGED",
	"CONTENT_CHANGED"
];
var lastFailure = null;
async function change(out, action, target, params, pre, scope) {
	lastFailure = null;
	try {
		const op = await submit(action, target, params, pre, scope);
		if (op.status === "succeeded") {
			fill(out);
			return op;
		}
		lastFailure = op.error_code || op.status;
		if (TERMINAL.includes(op.status)) fill(out, problem(op.error_code, op.status_reason));
		else fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
	} catch (e) {
		lastFailure = e.code || "ERROR";
		fill(out, e.status === 403 ? errorBox(e) : problem(e.code, e.message));
	}
	return null;
}
function manageNote() {
	return may("manage") ? null : h("p", { class: "note" }, t("needs_manage_access"));
}
function indent(el, depth) {
	el.style.setProperty("--depth", String(depth));
	return el;
}
function stateChip(c) {
	const cls = {
		done: "ok",
		awaiting_approval: "warn",
		doing: "info",
		waiting: "warn"
	}[c.display_state] || "";
	return chip(t("wi_state_" + c.display_state), cls);
}
function counts(c) {
	return [
		c.doing ? chip(`${t("wi_state_doing")} ${c.doing}`, "info") : null,
		c.awaiting_approval ? chip(`${t("wi_state_awaiting_approval")} ${c.awaiting_approval}`, "warn") : null,
		chip(t("wi_done_of", {
			done: c.done,
			total: c.total
		}), c.total && c.done === c.total ? "ok" : "")
	];
}
function orderButtons(sibs, i, key, run) {
	const me = sibs[i];
	const swap = (j) => () => {
		const before = sibs.map((x) => x[key]);
		const order = before.slice();
		[order[i], order[j]] = [order[j], order[i]];
		run("order", before, order);
	};
	const can = (j) => j >= 0 && j < sibs.length && sibs[j].pinned === me.pinned;
	return [
		h("button", {
			class: "mini",
			title: t("move_up"),
			"aria-label": t("move_up"),
			disabled: !can(i - 1),
			onclick: swap(i - 1)
		}, "↑"),
		h("button", {
			class: "mini",
			title: t("move_down"),
			"aria-label": t("move_down"),
			disabled: !can(i + 1),
			onclick: swap(i + 1)
		}, "↓"),
		h("button", {
			class: `mini ${me.pinned ? "on" : ""}`,
			title: me.pinned ? t("unpin") : t("pin"),
			"aria-label": me.pinned ? t("unpin") : t("pin"),
			onclick: () => run("pin", me.pinned)
		}, me.pinned ? "★" : "☆")
	];
}
var editing = 0;
var idleReload = null;
var drawerOpens = 0;
function setEditing(n) {
	editing = Math.max(0, n);
	if (!editing && idleReload) {
		const fn = idleReload;
		idleReload = null;
		fn();
	}
}
function drawer(...children) {
	const box = h("div", {
		class: "drawer",
		hidden: true
	}, ...children);
	const toggle = h("button", {
		class: "mini",
		title: t("more"),
		"aria-label": t("more"),
		onclick: () => {
			box.hidden = !box.hidden;
			if (!box.hidden) drawerOpens += 1;
			setEditing(editing + (box.hidden ? -1 : 1));
		}
	}, "…");
	const open = () => {
		if (box.hidden) toggle.click();
	};
	return {
		box,
		toggle,
		open,
		close: () => {
			if (!box.hidden) toggle.click();
		}
	};
}
function freshPage() {
	editing = 0;
	idleReload = null;
}
function typing() {
	const a = document.activeElement;
	return Boolean(a?.closest?.("#main")) && (a.tagName === "TEXTAREA" || a.tagName === "SELECT" || a.tagName === "INPUT" && ![
		"checkbox",
		"radio",
		"button",
		"submit"
	].includes(a.type));
}
function holdRender(fromEvent, opensAtStart) {
	return editing > 0 && (fromEvent || drawerOpens !== opensAtStart) || fromEvent && typing();
}
document.addEventListener("focusout", () => setTimeout(() => {
	if (!editing && !typing() && idleReload) {
		const fn = idleReload;
		idleReload = null;
		fn();
	}
}, 0));
function liveReload(fn, kinds, prepare = null) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const later = debounceRefresh(async () => {
		let preparedAt = 0;
		const prepareNow = async () => {
			if (prepare) {
				await prepare();
				preparedAt = Date.now();
			}
		};
		await prepareNow();
		for (;;) {
			while (editing || typing()) {
				assertView(connection);
				await sleep(100);
				if (prepare && Date.now() - preparedAt >= 1e3) await prepareNow();
			}
			assertView(connection);
			const opened = drawerOpens;
			await fn(true);
			assertView(connection);
			if (!editing && !typing() && drawerOpens === opened) return;
		}
	}, 500);
	return onEvents((ev) => {
		if (typeof kinds === "function" ? kinds(ev) : kinds.includes(ev.resource_type)) return later();
	});
}
async function viewProjects(main) {
	freshPage();
	const out = h("div", {});
	const tree = h("div", { class: "panel" });
	const archived = h("div", {});
	const name = h("input", {
		placeholder: t("new_project_name"),
		"aria-label": t("new_project_name"),
		maxlength: 80,
		required: true
	});
	const repositories = [...new Set((state.caps?.features?.repository_sync || []).map((binding) => binding.repository))].sort();
	const repository = h("select", { "aria-label": t("project_repository_optional") }, h("option", { value: "" }, t("project_repository_later")), ...repositories.map((value) => h("option", { value }, value)));
	const add = h("button", {
		class: "primary",
		type: "submit",
		disabled: !may("manage")
	}, t("add_project"));
	const create = async (event) => {
		event.preventDefault();
		if (add.disabled || !name.value.trim()) return;
		add.disabled = true;
		const params = {
			name: name.value.trim(),
			...repository.value ? { repositories: [repository.value] } : {}
		};
		const op = await change(out, "project.create", {}, params, {}, "project.create");
		add.disabled = false;
		if (op) {
			name.value = "";
			location.hash = `#/project/${op.result.project_id}`;
		}
	};
	const fields = h("div", { class: "capture-fields" }, h("label", {}, t("new_project_name"), name), ...repositories.length ? [h("label", {}, t("project_repository_optional"), repository)] : []);
	const showArchived = h("input", { type: "checkbox" });
	main.append(h("h1", {}, t("nav_projects")), h("p", { class: "muted" }, t("projects_help")), manageNote() || "", h("form", {
		class: "panel",
		onsubmit: create
	}, fields, h("div", { class: "actions" }, add)), out, tree, h("label", { class: "muted" }, showArchived, " ", t("show_archived")), archived);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		try {
			const data = await api("GET", `/projects${showArchived.checked ? "?include_archived=true" : ""}`);
			if (!tree.isConnected) return;
			if (holdRender(fromEvent, opens)) {
				idleReload = () => render(true);
				return;
			}
			freshPage();
			const rows = [];
			const walk = (sibs, depth, parent) => sibs.forEach((p, i) => {
				const msg = out;
				const run = async (what, before, order) => {
					if (what === "order") await change(msg, "project.order", {}, {
						parent_id: parent,
						order
					}, { before }, `project.order.${parent}`);
					else await change(msg, "project.pin", { project_id: p.project_id }, { pinned: !before }, { before }, `project.pin.${p.project_id}`);
					render();
				};
				const rename = h("input", {
					value: p.name,
					maxlength: 80
				});
				const sub = h("input", {
					placeholder: t("new_sub_project"),
					maxlength: 80
				});
				const d = drawer(h("div", { class: "filters" }, rename, h("button", {
					class: "secondary",
					onclick: async () => {
						if (await change(msg, "project.update", { project_id: p.project_id }, { name: rename.value.trim() }, { expected_version: p.version }, `project.rename.${p.project_id}`) || STALE.includes(lastFailure)) render();
					}
				}, t("rename"))), h("div", { class: "filters" }, sub, h("button", {
					class: "secondary",
					onclick: async () => {
						if (!sub.value.trim()) return;
						if (await change(msg, "project.create", {}, {
							name: sub.value.trim(),
							parent_id: p.project_id
						}, {}, `project.create.${p.project_id}`)) {
							d.close();
							render();
						}
					}
				}, t("add_project"))), h("div", { class: "actions" }, h("button", {
					class: "danger",
					onclick: async () => {
						if (await change(msg, "project.update", { project_id: p.project_id }, { archived: true }, { expected_version: p.version }, `project.archive.${p.project_id}`) || STALE.includes(lastFailure)) render();
					}
				}, t("archive"))));
				rows.push(indent(h("div", { class: "row tree" }, h("div", { class: "grow" }, h("a", {
					class: "title",
					href: `#/project/${p.project_id}`
				}, p.name), p.description ? h("div", { class: "muted clamp" }, p.description) : null), ...counts(p.counts), may("manage") ? h("span", { class: "tree-actions" }, ...orderButtons(sibs, i, "project_id", run), d.toggle) : null), depth), d.box);
				walk(p.children, depth + 1, p.project_id);
			});
			walk(data.projects, 0, "");
			fill(tree, ...rows.length ? rows : [h("p", { class: "muted" }, t("no_projects"))]);
			fill(archived, ...(data.archived || []).map((p) => h("div", { class: "row" }, h("div", { class: "grow" }, h("span", { class: "muted" }, p.name)), h("button", {
				class: "secondary",
				disabled: !may("manage"),
				onclick: async () => {
					await change(out, "project.update", { project_id: p.project_id }, { archived: false }, { expected_version: p.version }, `project.restore.${p.project_id}`);
					render();
				}
			}, t("restore")))));
		} catch (e) {
			fill(tree, errorBox(e));
		}
	};
	showArchived.onchange = () => render();
	await render();
	return liveReload(render, ["project", "work_item"]);
}
async function viewProject(main, pid) {
	freshPage();
	let draft = null;
	const head = h("div", { class: "panel" });
	const items = h("div", { class: "panel" });
	const work = h("section", {
		class: "panel",
		hidden: true,
		"data-project-work-list": true
	});
	const out = h("div", {});
	const archived = h("div", {});
	const showArchived = h("input", { type: "checkbox" });
	const title = h("input", {
		placeholder: t("new_item_title"),
		maxlength: 120
	});
	const add = h("button", {
		class: "primary",
		disabled: !may("manage"),
		onclick: async () => {
			if (!title.value.trim()) return;
			add.disabled = true;
			const op = await change(out, "work_item.create", { project_id: pid }, { title: title.value.trim() }, {}, `wi.create.${pid}`);
			add.disabled = false;
			if (op) {
				title.value = "";
				render();
			}
		}
	}, t("add_item"));
	main.append(manageNote() || "", out, head, work, h("h2", {}, t("work_items")), h("div", { class: "filters" }, title, add), items, h("label", { class: "muted" }, showArchived, " ", t("show_archived")), archived);
	const render = async (fromEvent = false) => {
		const opens = drawerOpens;
		let data;
		try {
			data = await api("GET", `/projects/${pid}${showArchived.checked ? "?include_archived=true" : ""}`);
		} catch (e) {
			fill(head, errorBox(e));
			return;
		}
		if (!head.isConnected) return;
		if (holdRender(fromEvent, opens)) {
			idleReload = () => render(true);
			return;
		}
		freshPage();
		const p = data.project;
		work.hidden = !Array.isArray(data.work);
		fill(work, h("h2", {}, t("delivery_project_work")), ...data.work?.length ? data.work.map((item) => deliveryWork(item, p.repositories)) : [h("p", { class: "muted" }, t("delivery_no_work"))]);
		const msg = out;
		const v = draft || {
			name: p.name,
			description: p.description,
			repositories: p.repositories,
			task_project: p.task_project || ""
		};
		const f = {
			name: h("input", {
				value: v.name,
				maxlength: 80
			}),
			description: h("textarea", {}, v.description),
			repositories: h("input", {
				value: v.repositories.join(", "),
				placeholder: "owner/name, owner/name"
			}),
			task_project: h("input", {
				value: v.task_project,
				placeholder: t("task_project")
			})
		};
		const d = drawer(h("label", {}, t("name")), f.name, h("label", {}, t("description")), f.description, h("label", {}, t("repositories")), f.repositories, h("label", {}, t("task_project")), f.task_project, h("div", { class: "actions" }, h("button", {
			class: "primary",
			onclick: async () => {
				const params = {
					name: f.name.value.trim(),
					description: f.description.value,
					repositories: f.repositories.value.split(/[\s,]+/).filter(Boolean),
					task_project: f.task_project.value.trim()
				};
				const ok = await change(msg, "project.update", { project_id: pid }, params, { expected_version: p.version }, `project.edit.${pid}`);
				if (!ok && STALE.includes(lastFailure)) draft = params;
				if (ok || draft) render();
			}
		}, t("save"))));
		fill(head, h("div", { class: "muted" }, h("a", { href: "#/projects" }, t("nav_projects")), ...data.path.flatMap((x) => [" / ", h("a", { href: `#/project/${x.project_id}` }, x.name)])), h("h1", {}, p.name, " ", p.archived ? chip(t("archived"), "warn") : null), p.description ? h("p", { class: "pre" }, p.description) : null, h("div", { class: "actions" }, ...counts(p.counts), ...p.repositories.map((r) => chip(r)), !p.archived && state.caps?.features?.project_dispatch?.version === 1 ? h("a", {
			class: "session-project-link",
			href: `#/dispatch/${pid}`
		}, t("dispatch_title")) : null, p.task_project ? chip(`Task Service: ${p.task_project}`) : null, may("manage") && !p.archived ? d.toggle : null), d.box, data.sub_projects.length ? h("p", {}, t("sub_projects"), ": ", ...data.sub_projects.flatMap((x, i) => [i ? " · " : "", h("a", { href: `#/project/${x.project_id}` }, x.name)])) : null);
		if (draft) {
			draft = null;
			d.open();
		}
		const rows = [];
		const walk = (sibs, depth, parent) => sibs.forEach((w, i) => {
			const rowMsg = out;
			const run = async (what, before, order) => {
				if (what === "order") await change(rowMsg, "work_item.order", { project_id: pid }, {
					parent_id: parent,
					order
				}, { before }, `wi.order.${pid}.${parent}`);
				else await change(rowMsg, "work_item.pin", { work_item_id: w.work_item_id }, { pinned: !before }, { before }, `wi.pin.${w.work_item_id}`);
				render();
			};
			const child = h("input", {
				placeholder: t("new_child_item"),
				maxlength: 120
			});
			const branch = h("input", {
				placeholder: t("new_branch_item"),
				maxlength: 120
			});
			const create = (input, params, scope) => h("button", {
				class: "secondary",
				onclick: async () => {
					if (!input.value.trim()) return;
					if (await change(rowMsg, "work_item.create", { project_id: pid }, {
						title: input.value.trim(),
						...params
					}, {}, scope)) render();
				}
			}, t("add_item"));
			const dr = drawer(h("div", { class: "filters" }, child, create(child, { parent_id: w.work_item_id }, `wi.child.${w.work_item_id}`)), h("div", { class: "filters" }, branch, create(branch, {
				parent_id: parent || null,
				derived_from: w.work_item_id
			}, `wi.branch.${w.work_item_id}`)), h("div", { class: "actions" }, h("button", {
				class: "danger",
				onclick: async () => {
					if (await change(rowMsg, "work_item.update", { work_item_id: w.work_item_id }, { archived: true }, { expected_version: w.version }, `wi.archive.${w.work_item_id}`) || STALE.includes(lastFailure)) render();
				}
			}, t("archive_with_children"))));
			const done = w.steps.filter((s) => s.done).length;
			rows.push(indent(h("div", { class: "row tree" }, stateChip(w.completion), h("div", { class: "grow" }, h("a", {
				class: "title",
				href: `#/item/${w.work_item_id}`
			}, w.title), w.derived_from ? h("span", { class: "muted" }, " ⑂") : null), w.steps.length ? chip(`${done}/${w.steps.length}`) : null, w.completion.pending ? chip(t("needs_decision"), "warn") : null, may("manage") && !p.archived ? h("span", { class: "tree-actions" }, ...orderButtons(sibs, i, "work_item_id", run), dr.toggle) : null), depth), dr.box);
			walk(w.children, depth + 1, w.work_item_id);
		});
		walk(data.work_items, 0, "");
		fill(items, ...rows.length ? rows : [h("p", { class: "muted" }, t("no_items"))]);
		fill(archived, ...(data.archived || []).map((w) => h("div", { class: "row" }, h("div", { class: "grow" }, h("a", {
			class: "muted",
			href: `#/item/${w.work_item_id}`
		}, w.title)), h("button", {
			class: "secondary",
			disabled: !may("manage") || p.archived,
			onclick: async () => {
				await change(out, "work_item.update", { work_item_id: w.work_item_id }, { archived: false }, { expected_version: w.version }, `wi.restore.${w.work_item_id}`);
				render();
			}
		}, t("restore")))));
		add.disabled = !may("manage") || p.archived;
	};
	showArchived.onchange = () => render();
	await render();
	return liveReload(render, [
		"project",
		"work_item",
		"operation",
		"task",
		"execution",
		"session",
		"integration"
	]);
}
function linkTarget(l) {
	const x = l.target || {};
	if (!x.found) return h("span", { class: "muted" }, l.ref, " · ", t("link_missing"));
	if (l.kind === "session") {
		const [host, ...rest] = l.ref.split("/");
		return h("span", {}, h("a", { href: `#/session/${encodeURIComponent(host)}/${encodeURIComponent(rest.join("/"))}` }, x.title || l.ref), " ", chip(x.api_access === "managed" ? t("managed") : t("read_only"), x.api_access === "managed" ? "managed" : "readonly"), x.gone ? chip(t("stale_reason_gone"), "stale") : null);
	}
	if (l.kind === "operation") return h("span", {}, h("a", { href: `#/op/${l.ref}` }, x.action), " ", h("span", { class: `status-${x.status}` }, t("op_" + x.status)), x.session ? [" · ", h("a", { href: `#/session/${encodeURIComponent(x.session.host)}/${encodeURIComponent(x.session.session_id)}` }, t("open_new_session"))] : null);
	if (l.kind === "checkpoint") return h("span", {}, h("a", { href: `#/session/${encodeURIComponent(x.host)}/${encodeURIComponent(x.source_session_id)}` }, h("code", {}, x.commit_sha.slice(0, 12))), " ", x.branch || "", " · ", x.host);
	if (l.kind === "task") return h("span", {}, observationLink("execution", l.ref), " ", x.project, " · ", x.state);
	return h("a", {
		href: `https://github.com/${x.repository}/pull/${x.number}`,
		target: "_blank",
		rel: "noopener"
	}, `${x.repository}#${x.number}`);
}
async function viewWorkItem(main, wid) {
	freshPage();
	const notice = h("div", {});
	const panel = h("div", {});
	const reading = h("div", {});
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	let mutable = true;
	const archiveLocks = new Map();
	const blocked = h("p", {
		class: "note warn",
		hidden: true
	}, t("parent_archived"));
	main.append(blocked);
	const requireMutable = () => {
		assertView(connection);
		if (!mutable) throw new ApiError(409, "ITEM_ARCHIVED", t("parent_archived"));
	};
	const refreshSafety = async () => {
		try {
			const data = await api("GET", `/work-items/${wid}`);
			assertView(connection);
			rememberObservation("work_item", wid, data, itemDependencies(data));
			mutable = !data.work_item.archived && !data.project.archived;
			blocked.hidden = mutable;
			if (!mutable) {
				for (const button of panel.querySelectorAll("button")) if (button.getAttribute("aria-label") !== t("more")) {
					if (!archiveLocks.has(button)) archiveLocks.set(button, button.disabled);
					button.disabled = true;
				}
				for (const control of panel.querySelectorAll("select,input[type=checkbox]")) {
					if (!archiveLocks.has(control)) archiveLocks.set(control, control.disabled);
					control.disabled = true;
				}
			} else {
				for (const [control, disabled] of archiveLocks) control.disabled = disabled;
				archiveLocks.clear();
			}
		} catch (error) {
			fill(notice, errorBox(error));
			throw error;
		}
	};
	let draft = null;
	const newStep = h("input", {
		placeholder: t("new_step"),
		maxlength: 300
	});
	const kind = h("select", {}, ...[
		"session",
		"checkpoint",
		"operation",
		"task",
		"pull_request"
	].map((k) => h("option", { value: k }, t("link_" + k))));
	const ref = h("input", { placeholder: t("link_ref_hint") });
	kind.onchange = () => {
		ref.placeholder = t("link_ref_" + kind.value);
	};
	kind.onchange();
	main.append(manageNote() || "", notice, reading, panel);
	let displayedItem = null, renderQueue = Promise.resolve();
	const showReading = (w, progress) => {
		const readingSupported = state.caps?.features?.work_item_reads?.version === 1 && progress;
		reading.replaceChildren();
		if (readingSupported) {
			const canRead = state.caps.actions?.some((a) => a.action === "work_item.read" && a.allowed);
			const mark = h("button", {
				class: "secondary",
				disabled: !canRead || progress.read_version >= w.version,
				onclick: async () => {
					try {
						assertView(connection);
						mark.disabled = true;
						await change(notice, "work_item.read", { work_item_id: wid }, {}, { expected_version: w.version }, `wi.read.${wid}.${w.version}`);
						assertView(connection);
						await render(true);
					} catch (error) {
						if (!["VIEW_CHANGED", "CONNECTION_CHANGED"].includes(error.code)) fill(notice, errorBox(error));
					} finally {
						if (mark.isConnected) mark.disabled = !canRead || progress.read_version >= w.version;
					}
				}
			}, t("reading_mark"));
			reading.append(h("div", { class: "panel reading-state" }, h("div", { class: "actions" }, chip(t(progress.unread ? "reading_unread" : "reading_read")), mark), h("p", { class: "muted" }, t("reading_note")), progress.current_version > w.version ? h("p", { class: "muted" }, t("reading_newer")) : null));
		}
	};
	const render = (fromEvent = false) => {
		const work = renderQueue.catch(() => {}).then(() => renderNow(fromEvent));
		renderQueue = work;
		return work;
	};
	const renderNow = async (fromEvent = false) => {
		if (!panel.isConnected) return;
		const opens = drawerOpens;
		let data;
		try {
			data = await api("GET", `/work-items/${wid}`);
		} catch (e) {
			fill(panel, errorBox(e));
			return;
		}
		if (!panel.isConnected) return;
		assertView(connection);
		rememberObservation("work_item", wid, data, itemDependencies(data));
		if (holdRender(fromEvent, opens)) {
			if (displayedItem) showReading(displayedItem, data.work_item.reading);
			idleReload = () => render(true);
			return;
		}
		freshPage();
		const w = data.work_item, c = w.completion;
		displayedItem = w;
		showReading(w, w.reading);
		const live = mutable = !w.archived && !data.project.archived;
		blocked.hidden = live;
		const pre = { expected_version: w.version };
		const update = (params, scope) => {
			requireMutable();
			return change(notice, "work_item.update", { work_item_id: wid }, params, pre, scope);
		};
		const decide = async (action, scope) => {
			requireMutable();
			await change(notice, action, { work_item_id: wid }, {}, { expected_fingerprint: c.fingerprint }, scope);
			render();
		};
		const approve = h("button", {
			class: "primary",
			disabled: !live || !may("approve"),
			title: may("approve") ? null : t("needs_approve_scope"),
			onclick: () => decide("work_item.approve", `wi.approve.${wid}.${c.fingerprint}`)
		}, c.pending ? t("accept_done") : t("mark_done"));
		const keepGoing = h("button", {
			class: "secondary",
			disabled: !live || !may("manage"),
			onclick: () => decide("work_item.continue", `wi.continue.${wid}.${c.fingerprint}`)
		}, t("keep_working"));
		let banner = null;
		if (c.approved) banner = h("p", { class: "note ok" }, t("approved_by", {
			who: c.approved_by,
			time: when(epoch(c.approved_at))
		}));
		else if (c.pending && w.state === "done") banner = h("div", { class: "note warn" }, h("p", {}, t("claimed_done", { who: c.claimed_by || "?" })), h("div", { class: "actions" }, approve, keepGoing), may("approve") ? null : h("p", { class: "muted" }, t("needs_approve_scope")));
		else if (c.pending) banner = h("div", { class: "note warn" }, h("p", {}, t("steps_all_checked")), h("div", { class: "actions" }, approve, keepGoing));
		const stateSel = h("select", { disabled: !live || !may("manage") }, ...[
			"todo",
			"doing",
			"waiting"
		].map((s) => h("option", {
			value: s,
			selected: w.state === s
		}, t("wi_state_" + s))));
		if (w.state === "done") stateSel.prepend(h("option", {
			value: "done",
			selected: true
		}, t("wi_state_" + c.display_state)));
		stateSel.onchange = async () => {
			await update({ state: stateSel.value }, `wi.state.${wid}`);
			render();
		};
		const v = {
			...w,
			...draft || {}
		};
		const f = {
			title: h("input", {
				value: v.title,
				maxlength: 120
			}),
			goal: h("textarea", {}, v.goal),
			request: h("textarea", {}, v.request),
			acceptance: h("textarea", {}, v.acceptance)
		};
		const attachment = attachmentDraft(`wi.edit.${wid}`, f.request, v.attachments || [], true);
		attachment.bindFields(f);
		const d = drawer(h("label", {}, t("title")), f.title, h("label", {}, t("goal")), f.goal, h("label", {}, t("request")), f.request, h("label", {}, t("acceptance")), f.acceptance, attachment.box, h("div", { class: "actions" }, h("button", {
			class: "primary",
			onclick: async () => {
				const params = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, k === "title" ? el.value.trim() : el.value]).filter(([k, v]) => v !== w[k]));
				if (!attachment.ready()) {
					fill(notice, h("p", { class: "error" }, t("attachments_not_ready")));
					return;
				}
				if (JSON.stringify(attachment.refs()) !== JSON.stringify(w.attachments || [])) params.attachments = attachment.refs();
				if (!Object.keys(params).length && !attachment.pending()) {
					d.close();
					return;
				}
				let op;
				try {
					requireMutable();
					op = await attachment.perform("work_item.update", { work_item_id: wid }, params, pre, `wi.edit.${wid}`);
				} catch (e) {
					fill(notice, errorBox(e));
					if (STALE.includes(e.code)) {
						draft = params;
						render();
					}
					return;
				}
				const ok = op.status === "succeeded";
				if (!ok) fill(notice, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
				if (!ok && STALE.includes(lastFailure)) draft = params;
				if (ok || draft) render();
			}
		}, t("save"))));
		const section = (label, text) => text ? [h("h2", {}, label), h("div", { class: "panel pre" }, text)] : [];
		const setSteps = async (steps, added) => {
			if (await update({ steps }, `wi.steps.${wid}`) && added) newStep.value = "";
			render();
		};
		const stepRows = w.steps.map((s, i) => h("div", { class: "step" }, h("label", {}, h("input", {
			type: "checkbox",
			checked: s.done,
			disabled: !live || !may("manage"),
			onchange: () => setSteps(w.steps.map((x, j) => j === i ? {
				...x,
				done: !x.done
			} : x))
		}), " ", s.text), live && may("manage") ? h("button", {
			class: "mini",
			title: t("remove"),
			"aria-label": t("remove"),
			onclick: () => setSteps(w.steps.filter((_, j) => j !== i))
		}, "×") : null));
		const addStep = h("button", {
			class: "secondary",
			disabled: !live || !may("manage"),
			onclick: () => {
				if (newStep.value.trim()) setSteps([...w.steps, {
					text: newStep.value.trim(),
					done: false
				}], true);
			}
		}, t("add"));
		const link = async (params, scope, typed) => {
			requireMutable();
			if (await change(notice, "work_item.link", { work_item_id: wid }, params, {}, scope)) {
				if (typed) ref.value = "";
				render();
			}
		};
		const linkRows = data.links.map((l) => h("div", { class: "row" }, chip(t("link_" + l.kind)), h("div", { class: "grow" }, linkTarget(l), l.note ? h("div", { class: "muted" }, l.note) : null, h("div", { class: "muted" }, `${l.linked_by} · ${when(epoch(l.linked_at))}`)), l.kind === "checkpoint" && l.target?.found && live ? continueFrom(w, l.ref, notice) : null, live && may("manage") ? h("button", {
			class: "mini",
			title: t("remove"),
			"aria-label": t("remove"),
			onclick: () => link({
				kind: l.kind,
				ref: l.ref,
				remove: true
			}, `wi.unlink.${wid}.${l.kind}.${l.ref}`)
		}, "×") : null));
		const brief = (x) => h("div", { class: "row" }, chip(t("wi_state_" + x.display_state)), h("a", {
			class: "grow",
			href: `#/item/${x.work_item_id}`
		}, x.title));
		fill(panel, h("div", { class: "muted" }, h("a", { href: "#/projects" }, t("nav_projects")), " / ", h("a", { href: `#/project/${data.project.project_id}` }, data.project.name), ...data.path.flatMap((x) => [" / ", h("a", { href: `#/item/${x.work_item_id}` }, x.title)])), h("h1", {}, w.title, " ", stateChip(c), w.archived ? [" ", chip(t("archived"), "warn")] : null), data.derived_from ? h("p", { class: "muted" }, t("derived_from"), " ", h("a", { href: `#/item/${data.derived_from.work_item_id}` }, data.derived_from.title)) : null, banner, h("div", { class: "actions" }, h("label", {}, t("state"), " ", stateSel), !c.pending && !c.approved && live ? approve : null, live && may("manage") ? d.toggle : null), d.box, ...section(t("goal"), w.goal), ...section(t("request"), w.request), ...section(t("acceptance"), w.acceptance), h("h2", {}, t("steps_title")), h("div", { class: "panel" }, ...stepRows.length ? stepRows : [h("p", { class: "muted" }, t("no_steps"))], live && may("manage") ? h("div", { class: "filters" }, newStep, addStep) : null), h("div", { class: "actions" }, h("a", { href: `#/cleanup/item/${wid}` }, t("nav_cleanup"))), h("h2", {}, t("links")), h("div", { class: "panel" }, ...linkRows.length ? linkRows : [h("p", { class: "muted" }, t("no_links"))], live && may("manage") ? h("div", { class: "filters" }, kind, ref, h("button", {
			class: "secondary",
			onclick: () => {
				if (ref.value.trim()) link({
					kind: kind.value,
					ref: ref.value.trim()
				}, `wi.link.${wid}`, true);
			}
		}, t("link"))) : null), data.children.length ? [h("h2", {}, t("children")), h("div", { class: "panel" }, ...data.children.map(brief))] : null, data.derived.length ? [h("h2", {}, t("derived")), h("div", { class: "panel" }, ...data.derived.map(brief))] : null, h("h2", {}, t("history")), h("div", { class: "panel" }, ...data.events.map((ev) => h("div", { class: "row" }, h("div", { class: "grow" }, t("ev_" + ev.kind.replace(".", "_")), h("div", { class: "muted" }, eventDetail(ev.body))), h("span", { class: "muted" }, `${ev.actor || ""} · ${when(epoch(ev.created_at))}`)))));
		if (draft) {
			draft = null;
			d.open();
		}
	};
	await render();
	return liveReload(render, (event) => observationAffected("work_item", wid, event), refreshSafety);
}
function continueFrom(w, checkpointId, notice) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const instr = h("textarea", {}, [
		w.title,
		w.goal,
		w.request && `${t("request")}:\n${w.request}`,
		w.acceptance && `${t("acceptance")}:\n${w.acceptance}`,
		w.steps.length ? `${t("steps_title")}:\n${w.steps.map((s) => `- [${s.done ? "x" : " "}] ${s.text}`).join("\n")}` : ""
	].filter(Boolean).join("\n\n"));
	const agent = h("select", { "aria-label": t("agent") }, h("option", { value: "claude" }, "Claude"), h("option", { value: "codex" }, "Codex"));
	const out = h("div", {});
	const draft = attachmentDraft(`continue.${checkpointId}.${w.work_item_id}`, instr, (w.attachments || []).filter((x) => x.role === "input"));
	draft.bindFields({ agent });
	let expectedHead = null;
	const go = h("button", {
		class: "primary",
		onclick: async () => {
			go.disabled = true;
			let op;
			try {
				if (!draft.ready() && !draft.pending()) throw new Error(t("attachments_not_ready"));
				if (state.caps?.artifacts && !expectedHead && !draft.pending()) throw new Error(t("source_unavailable"));
				op = await draft.perform("checkpoint.continue", { checkpoint_id: checkpointId }, {
					instructions: instr.value,
					agent: agent.value,
					...state.caps?.artifacts ? {
						artifacts: draft.refs(),
						work_item_id: w.work_item_id
					} : {}
				}, state.caps?.artifacts ? {
					expected_source_head_sha: expectedHead,
					expected_work_item_fingerprint: w.completion.fingerprint
				} : {}, `continue.${checkpointId}`);
			} catch (e) {
				fill(out, errorBox(e));
				go.disabled = false;
				return;
			}
			assertView(connection);
			fill(out, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, op.operation_id));
			if (TERMINAL.includes(op.status) && op.status !== "succeeded") return;
			if (!state.caps?.artifacts) {
				if (await change(notice, "work_item.link", { work_item_id: w.work_item_id }, {
					kind: "operation",
					ref: op.operation_id
				}, {}, `wi.link.${w.work_item_id}.${op.operation_id}`)) out.append(" · ", t("linked_back"));
			} else out.append(" · ", t("linked_back"));
		}
	}, t("start_agent_work"));
	const note = confinementNote(w.links?.find((l) => l.ref === checkpointId)?.target?.host, agent);
	api("GET", `/checkpoints/${encodeURIComponent(checkpointId)}`).then((x) => note.setHost(x.checkpoint.host)).catch(() => {});
	const d = drawer(note, instr, draft.box, h("div", { class: "actions" }, agent, go), out);
	const why = !may("start") ? t("needs_start_scope") : !may("manage") ? t("needs_manage_scope") : null;
	return h("div", { class: "grow" }, h("button", {
		class: "secondary",
		disabled: Boolean(why),
		title: why,
		onclick: async () => {
			d.toggle.click();
			if (state.caps?.artifacts && !expectedHead) try {
				expectedHead = (await api("GET", `/checkpoints/${checkpointId}?live=true`)).source.head;
			} catch (e) {
				fill(out, errorBox(e));
			}
		}
	}, t("start_from_checkpoint")), d.box);
}
function eventDetail(b) {
	if (b.fields) return b.fields.map((f) => t(f === "steps" ? "steps_title" : f)).join(", ");
	if (b.from && b.to) return `${t("wi_state_" + b.from)} → ${t("wi_state_" + b.to)}${b.note ? ` · ${b.note}` : ""}`;
	if (b.kind && b.ref) return `${t("link_" + b.kind)} ${b.ref}`;
	return b.note || "";
}
function linkedItems(items) {
	return h("p", { class: "muted" }, t("linked_items"), ": ", ...items.flatMap((x, i) => [i ? " · " : "", h("a", { href: `#/item/${x.work_item_id}` }, x.title)]));
}
function workItemRow(w) {
	return h("div", { class: "row" }, stateChip(w.completion), h("div", { class: "grow" }, h("a", {
		class: "title",
		href: `#/item/${w.work_item_id}`
	}, w.title), h("div", { class: "muted" }, [w.project_name, w.completion.claimed_by && t("claimed_by", { who: w.completion.claimed_by })].filter(Boolean).join(" · "))), w.reading?.unread ? chip(t("reading_unread")) : null, w.completion.pending ? chip(t("needs_decision"), "warn") : null);
}
async function viewCleanup(main, section, ident) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const draftKey = `batc.cleanup.draft.${connection.namespace}`;
	const pendingKey = `batc.cleanup.pending.${connection.namespace}`;
	const intentKey = `batc.cleanup.intent.${connection.namespace}`;
	const readStored = (key) => {
		try {
			return JSON.parse(localStorage.getItem(key) || sessionStorage.getItem(key) || "null");
		} catch {
			return null;
		}
	};
	const persist = (key, value) => {
		assertView(connection);
		try {
			for (const storage of [localStorage, sessionStorage]) if (value === null) storage.removeItem(key);
			else storage.setItem(key, JSON.stringify(value));
		} catch (error) {
			if (error.code) throw error;
		}
	};
	const stored = readStored(draftKey) || {};
	const choices = [
		"item",
		"task",
		"host"
	].includes(section) && stored.id !== ident ? {
		discard_uncommitted: [],
		release_undelivered: []
	} : stored.choices || {
		discard_uncommitted: [],
		release_undelivered: []
	};
	const pending = readStored(pendingKey);
	let intent = readStored(intentKey);
	if (intent) {
		const request = intent.request;
		const valid = request?.action === "cleanup.apply" && request.target?.preview_id === pending?.preview_id && request.params?.preview_token === pending?.preview_token && request.preconditions?.preview_fingerprint === pending?.fingerprint && typeof intent.key === "string" && intent.key.length > 0 && intent.key.length <= 200 && pending;
		intent = {
			key: valid ? intent.key : null,
			request: valid ? {
				action: "cleanup.apply",
				target: { preview_id: pending.preview_id },
				params: { preview_token: pending.preview_token },
				preconditions: { preview_fingerprint: pending.fingerprint }
			} : null,
			operation_id: typeof intent.operation_id === "string" && /^op_[0-9a-f]{32}$/.test(intent.operation_id) ? intent.operation_id : null,
			refused: valid && [
				"PREVIEW_TOKEN_INVALID",
				"PREVIEW_EXPIRED",
				"PREVIEW_MISMATCH",
				"PREVIEW_BLOCKED"
			].includes(intent.refused) ? intent.refused : null
		};
	}
	let operation = null, operationRead = null, submission = null, readFailed = false;
	const supportsTask = state.caps?.features?.cleanup_task === true;
	const kind = h("select", { "aria-label": t("cleanup_target") }, ...[
		"work_item",
		"checkpoint",
		"integration",
		"host",
		...supportsTask || pending?.target?.kind === "task" ? ["task"] : []
	].map((k) => h("option", { value: k }, t("cleanup_target_" + k))));
	kind.value = section === "host" ? "host" : section === "item" ? "work_item" : section === "task" && supportsTask ? "task" : stored.kind || "host";
	const targetId = h("input", {
		value: [
			"item",
			"task",
			"host"
		].includes(section) ? ident : stored.id || "",
		"aria-label": t("cleanup_id"),
		placeholder: t("cleanup_id"),
		class: "cleanup-id"
	});
	const children = h("input", {
		type: "checkbox",
		checked: stored.children || false
	});
	const childrenLabel = h("label", { class: "cleanup-choice" }, children, t("cleanup_children"));
	const previewOut = h("div", { "aria-live": "polite" });
	const status = h("div", { "aria-live": "polite" });
	const historyOut = h("div", { "aria-live": "polite" });
	const retainedOut = h("div", { "aria-live": "polite" });
	let doc = pending, busy = false, loading = true, pendingRequest = !!pending, previewRevision = 0;
	function changed() {
		assertView(connection);
		previewRevision++;
		doc = null;
		apply.disabled = true;
		reviewed.checked = false;
		persist(draftKey, {
			kind: kind.value,
			id: targetId.value,
			children: children.checked,
			choices
		});
		childrenLabel.hidden = kind.value !== "work_item";
		fill(status, h("p", { class: "muted" }, t("cleanup_repreview")));
	}
	function targetChanged() {
		choices.discard_uncommitted = [];
		choices.release_undelivered = [];
		changed();
	}
	kind.addEventListener("change", targetChanged);
	targetId.addEventListener("input", targetChanged);
	children.addEventListener("change", targetChanged);
	childrenLabel.hidden = kind.value !== "work_item";
	function choice(item, key, label) {
		const input = h("input", {
			type: "checkbox",
			checked: choices[key].includes(item.resource_id),
			disabled: pendingRequest || key === "discard_uncommitted" && !may("cleanup_discard"),
			onchange: () => {
				choices[key] = choices[key].filter((id) => id !== item.resource_id);
				if (input.checked) choices[key].push(item.resource_id);
				changed();
			}
		});
		return h("label", { class: "cleanup-choice" }, input, label);
	}
	function resourceRow(item) {
		const codes = (item.reasons || []).map((r) => r.code);
		const eligible = item.proven && item.kind === "worktree" && (!item.task_owned || item.task_cleanup?.eligible === true);
		return h("article", { class: "cleanup-resource" }, h("div", { class: "row" }, h("strong", { class: "grow" }, t("cleanup_kind_" + item.kind)), chip(t("cleanup_decision_" + item.decision), item.decision === "reclaim" ? "ok" : "")), h("div", { class: "cleanup-binding" }, item.host || "", " ", item.path || item.ref || item.resource_id), item.observation?.head ? h("p", { class: "muted" }, t("cleanup_commit_kept"), " ", h("code", {}, item.observation.head)) : null, item.delivery && !item.delivery.delivered ? h("p", { class: "note warn" }, t("cleanup_not_delivered")) : null, ...(item.reasons || []).map((r) => h("div", { class: "cleanup-reason" }, h("code", {}, r.code), " · ", t("cleanup_reason_" + r.code))), ...(item.overridden_reasons || []).map((r) => h("p", { class: "muted" }, t("cleanup_choice_" + r.code))), item.steps?.length ? h("p", {}, t("cleanup_plan"), ": ", item.steps.map((x) => t("cleanup_step_" + x)).join(" → ")) : null, eligible && codes.includes("RESULTS_NOT_DELIVERED") ? choice(item, "release_undelivered", t("cleanup_release")) : null, eligible && !item.task_owned && codes.includes("UNCOMMITTED_CHANGES") ? choice(item, "discard_uncommitted", t("cleanup_discard")) : null, h("details", {}, h("summary", {}, t("cleanup_evidence")), h("pre", { class: "pre" }, JSON.stringify({
			resource_id: item.resource_id,
			original_ids: item.original_ids,
			reasons: item.reasons,
			consumers: item.consumers,
			task_cleanup: item.task_cleanup,
			delivery: item.delivery,
			manifest: item.observation?.manifest
		}, null, 2))));
	}
	const reviewed = h("input", {
		type: "checkbox",
		onchange: () => {
			apply.disabled = loading || busy || readFailed || Boolean(intent?.operation_id) || !doc?.ready || !may("cleanup") || !reviewed.checked;
		}
	});
	function acceptCleanup(op) {
		assertView(connection);
		if (!intent || !/^op_[0-9a-f]{32}$/.test(op?.operation_id) || op.action !== "cleanup.apply" || op.actor !== state.caps.actor || op.idempotency_key !== intent.key || !intent.request || op.target?.preview_id !== intent.request.target.preview_id || op.params?.preview_token !== intent.request.params.preview_token || op.preconditions?.preview_fingerprint !== intent.request.preconditions.preview_fingerprint || intent.operation_id && intent.operation_id !== op.operation_id) throw new Error(t("cleanup_invalid_result"));
		operation = op;
		intent.operation_id = op.operation_id;
		persist(intentKey, intent);
		readFailed = false;
		fill(status, opStatus(op), " ", h("a", { href: `#/op/${op.operation_id}` }, t("cleanup_open_receipts")), ...(op.result?.items || []).map((r) => h("p", {}, h("code", {}, r.resource_id), " · ", t("cleanup_receipt_" + r.status))));
		cleanupControls();
	}
	function cleanupControls() {
		const fixed = Boolean(intent || pendingRequest);
		kind.disabled = targetId.disabled = children.disabled = loading || busy || fixed;
		previewButton.disabled = loading || busy || fixed || section === "task" && !supportsTask;
		apply.hidden = Boolean(intent?.operation_id || intent?.refused);
		apply.disabled = loading || busy || readFailed || Boolean(intent && !intent.request) || !doc?.ready || !reviewed.checked || !may("cleanup");
		check.hidden = !intent?.operation_id;
		check.disabled = loading || busy || Boolean(operationRead);
		another.hidden = !(TERMINAL.includes(operation?.status) || intent?.refused);
		another.disabled = loading || busy || readFailed || Boolean(operationRead);
	}
	async function refreshCleanup(fresh = false) {
		if (submission) {
			await submission;
			assertView(connection);
		}
		if (operationRead) {
			await operationRead;
			if (fresh) return refreshCleanup(true);
			return;
		}
		if (!intent?.operation_id) return;
		operationRead = (async () => {
			acceptCleanup((await api("GET", `/operations/${intent.operation_id}`)).operation);
		})();
		cleanupControls();
		try {
			await operationRead;
		} catch (e) {
			assertView(connection);
			readFailed = true;
			fill(status, errorBox(e), h("a", { href: `#/op/${intent.operation_id}` }, t("cleanup_open_receipts")));
			throw e;
		} finally {
			operationRead = null;
			cleanupControls();
		}
	}
	const check = h("button", {
		class: "secondary",
		hidden: true,
		onclick: () => refreshCleanup(true).catch(() => {})
	}, t("cleanup_check"));
	const another = h("button", {
		class: "secondary",
		hidden: true,
		onclick: () => {
			assertView(connection);
			if (loading || busy || readFailed || operationRead || !(TERMINAL.includes(operation?.status) || intent?.refused)) return;
			intent = operation = doc = null;
			pendingRequest = false;
			persist(intentKey, null);
			persist(pendingKey, null);
			reviewed.checked = false;
			previewOut.replaceChildren();
			status.replaceChildren();
			cleanupControls();
		}
	}, t("cleanup_new"));
	const apply = h("button", {
		class: "primary",
		disabled: true,
		onclick: async () => {
			if (loading || busy || readFailed || !doc || !reviewed.checked || intent?.operation_id || intent?.refused || intent && !intent.request) return;
			assertView(connection);
			const reviewedDoc = doc;
			busy = true;
			pendingRequest = true;
			apply.disabled = true;
			previewButton.disabled = true;
			kind.disabled = true;
			targetId.disabled = true;
			children.disabled = true;
			previewOut.querySelectorAll("input").forEach((input) => {
				input.disabled = true;
			});
			persist(pendingKey, reviewedDoc);
			let finish;
			submission = new Promise((resolve) => {
				finish = resolve;
			});
			try {
				if (!intent) {
					const request = {
						action: "cleanup.apply",
						target: { preview_id: reviewedDoc.preview_id },
						params: { preview_token: reviewedDoc.preview_token },
						preconditions: { preview_fingerprint: reviewedDoc.fingerprint }
					};
					intent = {
						request,
						key: await keyFor(await draftId("cleanup.apply", request), connection),
						operation_id: null
					};
					persist(intentKey, intent);
				}
				const data = await api("POST", "/operations?wait=3", intent.request, intent.key);
				assertView(connection);
				acceptCleanup(data.operation);
				await loadHistory();
				await loadRetained();
			} catch (e) {
				if (connection.epoch !== state.epoch || connection.namespace !== state.namespace || connection.generation !== generation) return;
				if (intent && !intent.operation_id && e.status >= 400 && e.status < 500 && [
					"PREVIEW_TOKEN_INVALID",
					"PREVIEW_EXPIRED",
					"PREVIEW_MISMATCH",
					"PREVIEW_BLOCKED"
				].includes(e.code)) {
					intent.refused = e.code;
					persist(intentKey, intent);
				}
				fill(status, errorBox(e), h("p", {}, t(intent?.refused ? "cleanup_repreview" : "cleanup_retry_same")));
			} finally {
				busy = false;
				finish();
				submission = null;
				if (connection.epoch === state.epoch && connection.generation === generation) cleanupControls();
			}
		}
	}, t("cleanup_apply"));
	function renderPreview() {
		fill(previewOut, h("h2", {}, t("cleanup_preview")), h("p", {}, t("cleanup_counts", {
			reclaim: doc.impact.reclaim,
			retain: doc.impact.retain
		})), h("p", { class: "muted" }, t("cleanup_expires", { time: when(doc.expires_at * 1e3) })), ...(doc.items || []).map(resourceRow), !doc.ready ? h("p", { class: "note" }, t("cleanup_blocked")) : null);
	}
	const previewButton = h("button", {
		class: "secondary",
		onclick: async () => {
			if (loading) return;
			assertView(connection);
			const revision = ++previewRevision;
			previewButton.disabled = true;
			doc = null;
			apply.disabled = true;
			reviewed.checked = false;
			const key = {
				work_item: "work_item_id",
				checkpoint: "checkpoint_id",
				integration: "operation_id",
				host: "host",
				task: "task_id"
			}[kind.value];
			const target = {
				kind: kind.value,
				[key]: targetId.value.trim(),
				...kind.value === "work_item" ? { include_children: children.checked } : {}
			};
			try {
				const result = await api("POST", "/cleanup-previews", {
					target,
					choices: structuredClone(choices)
				});
				assertView(connection);
				if (revision !== previewRevision) return;
				doc = result.preview;
				renderPreview();
				fill(status);
			} catch (e) {
				if (revision === previewRevision && connection.epoch === state.epoch) fill(status, errorBox(e));
			} finally {
				previewButton.disabled = false;
			}
		}
	}, t("cleanup_preview"));
	if (pending && section !== "resource") {
		kind.value = pending.target.kind;
		targetId.value = pending.target[{
			work_item: "work_item_id",
			checkpoint: "checkpoint_id",
			integration: "operation_id",
			host: "host",
			task: "task_id"
		}[kind.value]];
		children.checked = !!pending.target.include_children;
		childrenLabel.hidden = kind.value !== "work_item";
		renderPreview();
		reviewed.checked = true;
		apply.disabled = !may("cleanup");
		previewButton.disabled = true;
		kind.disabled = true;
		targetId.disabled = true;
		children.disabled = true;
		fill(status, h("p", { class: "note" }, t("cleanup_retry_same")));
	}
	const search = h("input", {
		class: "cleanup-id",
		"aria-label": t("cleanup_search"),
		placeholder: t("cleanup_search")
	});
	async function loadHistory(cursor = "") {
		try {
			const result = await api("GET", `/cleanup-tombstones?query=${encodeURIComponent(search.value)}&cursor=${encodeURIComponent(cursor)}`);
			assertView(connection);
			const rows = (result.tombstones || []).map((x) => h("article", { class: "cleanup-resource" }, h("a", { href: `#/cleanup/resource/${x.resource_id}` }, t("cleanup_kind_" + x.kind)), h("div", { class: "cleanup-binding" }, x.host, " ", x.path || x.ref || ""), h("p", { class: "muted" }, x.actor, " · ", when(x.cleaned_at * 1e3)), h("p", {}, t({
				reviewed_cleanup: "cleanup_reason_reviewed",
				task_lifecycle: "cleanup_reason_automatic",
				historical_task_cleanup: "cleanup_reason_historical"
			}[x.reason] || "cleanup_reason_recorded")), ...(x.pull_requests || []).map((pr) => h("p", {}, `${pr.repository} #${pr.pull_number}`))));
			if (cursor) historyOut.append(...rows);
			else fill(historyOut, ...rows, rows.length ? null : h("p", { class: "muted" }, t("cleanup_empty_history")));
			if (result.next_cursor) historyOut.append(h("button", {
				class: "secondary",
				onclick: (e) => {
					e.currentTarget.remove();
					loadHistory(result.next_cursor);
				}
			}, t("more")));
		} catch (e) {
			fill(historyOut, errorBox(e));
		}
	}
	async function loadRetained(cursor = "") {
		try {
			const result = await api("GET", `/cleanup-retained?cursor=${encodeURIComponent(cursor)}`);
			assertView(connection);
			const rows = (result.retained || []).map((x) => h("article", { class: "cleanup-resource" }, h("code", {}, x.commit_sha), h("div", { class: "cleanup-binding" }, x.host, " ", x.repository), h("p", { class: "muted" }, x.ref)));
			const unavailable = (result.unavailable || []).map((x) => h("p", { class: "note warn" }, x.host, " ", x.ref, " · ", t("cleanup_unavailable")));
			if (cursor) retainedOut.append(...rows, ...unavailable);
			else fill(retainedOut, ...rows, ...unavailable, rows.length || unavailable.length ? null : h("p", { class: "muted" }, t("cleanup_empty_retained")));
			if (result.next_cursor) retainedOut.append(h("button", {
				class: "secondary",
				onclick: (e) => {
					e.currentTarget.remove();
					loadRetained(result.next_cursor);
				}
			}, t("more")));
		} catch (e) {
			fill(retainedOut, errorBox(e));
		}
	}
	main.append(h("h1", {}, t("nav_cleanup")), h("p", { class: "muted" }, t("cleanup_intro")), section === "task" || supportsTask ? h("p", { class: "muted" }, t("cleanup_task_help")) : "");
	if (section === "resource") {
		try {
			const data = await api("GET", `/cleanup-tombstones/${encodeURIComponent(ident)}`);
			main.append(h("a", { href: "#/cleanup" }, t("nav_cleanup")), resourceRow(data.tombstone), h("h2", {}, t("cleanup_open_receipts")), h("pre", { class: "panel pre" }, JSON.stringify(data.receipts, null, 2)));
		} catch (e) {
			main.append(errorBox(e));
		}
		return;
	}
	main.append(h("div", { class: "panel" }, h("h2", {}, t("cleanup_target")), h("div", { class: "filters" }, kind, targetId), childrenLabel, h("div", { class: "actions" }, previewButton)), previewOut, h("div", { class: "panel" }, h("label", { class: "cleanup-choice" }, reviewed, t("cleanup_reviewed")), !may("cleanup") ? h("p", { class: "muted" }, t("cleanup_scope")) : null, h("div", { class: "actions" }, apply, check, another), status), h("h2", {}, t("cleanup_history")), h("div", { class: "panel" }, h("form", {
		class: "filters",
		onsubmit: (e) => {
			e.preventDefault();
			loadHistory();
		}
	}, search, h("button", {
		class: "secondary",
		type: "submit"
	}, t("cleanup_search_button"))), historyOut), h("h2", {}, t("cleanup_retained")), h("p", { class: "muted" }, t("cleanup_retained_help")), h("div", { class: "panel" }, retainedOut));
	cleanupControls();
	await loadHistory();
	await loadRetained();
	try {
		await refreshCleanup();
	} catch {}
	loading = false;
	cleanupControls();
	const refresh = debounceRefresh(() => settleRefreshes([
		loadHistory(),
		loadRetained(),
		refreshCleanup(true)
	]), 500);
	return onEvents((ev) => {
		if (["cleanup", "operation"].includes(ev.resource_type)) return refresh();
	});
}
async function viewApprovals(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const panel = approvalsPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		storageKey: `batc.approvals.${connection.namespace}`
	});
	main.append(h("a", { href: "#/sessions" }, t("sessions_title")), h("h1", {}, t("bulk_title")), panel.box);
	try {
		await panel.refresh();
	} catch {}
	return onEvents((event) => event.resource_type === "operation" ? panel.refresh(true) : panel.update());
}
async function viewStart(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const panel = sessionStartPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		storageKey: `batc.start.${connection.namespace}`
	});
	main.append(h("a", { href: "#/sessions" }, t("nav_sessions")), h("h1", {}, t("start_title_page")), h("p", { class: "muted" }, t("start_intro")), ...state.caps?.features?.repository_sync?.length ? [h("p", {}, h("a", { href: "#/published" }, t("pub_title")))] : [], panel.box);
	try {
		await panel.init();
	} catch {}
	assertView(connection);
	return onEvents((ev) => {
		if ([
			"operation",
			"host",
			"session"
		].includes(ev.resource_type)) return panel.refresh(true);
	});
}
async function viewOrchestration(main, selectedMode = "relay", host, sid) {
	const mode = Object.hasOwn(orchestrationActions, selectedMode) ? selectedMode : "relay";
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const context = host && sid ? {
		host,
		session_id: sid
	} : {};
	const panel = orchestrationPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		mode,
		context,
		storageKey: `batc.orchestrate.${connection.namespace}.${mode}.${JSON.stringify(context)}`
	});
	main.append(h("a", { href: "#/sessions" }, t("nav_sessions")), h("h1", {}, t("orch_title")), h("nav", {
		class: "orch-modes",
		"aria-label": t("orch_title")
	}, ...Object.keys(orchestrationActions).map((key) => h("a", {
		href: `#/orchestrate/${key}`,
		"aria-current": key === mode ? "page" : null
	}, t("orch_" + key)))), h("h2", {}, t("orch_" + mode)), panel.box);
	try {
		await panel.init();
	} catch {}
	assertView(connection);
	return onEvents((event) => {
		if ([
			"operation",
			"session",
			"host"
		].includes(event.resource_type)) return panel.refresh(true);
	});
}
async function viewPublished(main) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const panel = repositoryStartPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		storageKey: `batc.published.${connection.namespace}`,
		attachmentFactory: (prompt, changed) => attachmentDraft("published", prompt, [], false, changed)
	});
	main.append(h("a", { href: "#/sessions" }, t("nav_sessions")), h("h1", {}, t("pub_title")), h("p", { class: "muted" }, t("pub_intro")), panel.box);
	try {
		await panel.init();
	} catch {}
	assertView(connection);
	const offOnline = onOnline(() => {
		try {
			assertView(connection);
			panel.update();
		} catch {}
	});
	const offEvents = onEvents((ev) => {
		if ([
			"operation",
			"host",
			"session"
		].includes(ev.resource_type)) return panel.refresh(true);
	});
	return () => {
		offOnline();
		offEvents();
	};
}
async function viewProjectDispatch(main, pid) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const panel = repositoryStartPanel({
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		ready: () => state.online && !state.nativeBusy,
		errorBox,
		opStatus,
		project: pid,
		storageKey: `batc.dispatch.${connection.namespace}.${pid}`,
		attachmentFactory: (prompt, changed) => attachmentDraft(`dispatch.${pid}`, prompt, [], false, changed)
	});
	main.append(h("a", { href: `#/project/${pid}` }, t("dispatch_back")), h("h1", {}, t("dispatch_title")), h("p", { class: "muted" }, t("dispatch_intro")), panel.box);
	try {
		await panel.init();
	} catch {}
	try {
		assertView(connection);
	} catch {
		return;
	}
	const offOnline = onOnline(() => {
		try {
			assertView(connection);
			panel.update();
		} catch {}
	});
	const offEvents = onEvents((ev) => {
		if (["operation", "host"].includes(ev.resource_type) || ev.resource_type === "project" && ev.resource_id === pid) return panel.refresh(true);
	});
	return () => {
		offOnline();
		offEvents();
	};
}
async function viewArtifactReview(main, kind, first, second) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	const context = kind === "session" ? {
		kind,
		host: first,
		session_id: second
	} : kind === "task" ? {
		kind,
		task_id: first
	} : kind === "operation" ? {
		kind,
		operation_id: first
	} : kind === "artifact" ? {
		kind,
		artifact_id: first,
		revision: Number(second)
	} : { kind: "catalog" };
	return mountArtifactReview({
		main,
		h,
		t,
		api,
		caps: () => state.caps,
		guard: () => assertView(connection),
		onEvents,
		errorBox,
		opStatus,
		context,
		readBrowser: (ref, size, signal) => {
			assertView(connection);
			return readArtifactContent(ref, size, state.token, signal);
		},
		storageKey: `batc.artifact-review.${connection.namespace}.${JSON.stringify(context)}`
	});
}
async function viewLinkedWorkItem(main, wid, host, sid) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	let data;
	try {
		data = await api("GET", `/work-items/${encodeURIComponent(wid)}`);
		assertView(connection);
	} catch (error) {
		if (!["VIEW_CHANGED", "CONNECTION_CHANGED"].includes(error.code)) main.append(errorBox(error));
		return;
	}
	const sessions = new Map();
	for (const link of data.links || []) {
		const target = link.target;
		if (!target?.found) continue;
		const session = link.kind === "session" ? target : link.kind === "operation" ? target.session : null;
		if (session?.host && session?.session_id) sessions.set(JSON.stringify([session.host, session.session_id]), session);
	}
	if (!sessions.size) return viewWorkItem(main, wid);
	const selected = host && sid ? sessions.get(JSON.stringify([host, sid])) : sessions.values().next().value;
	if (!selected) {
		main.append(errorBox(new Error(t("workspace_work_missing"))));
		return;
	}
	main.classList.add("session-view");
	const itemBox = h("section", { class: "workspace-work-item" });
	const picker = sessions.size > 1 ? h("label", { class: "workspace-session-picker" }, t("nav_sessions"), " ", h("select", {
		"aria-label": t("nav_sessions"),
		onchange: (event) => {
			const [nextHost, nextSid] = JSON.parse(event.target.value);
			location.hash = `#/item/${[
				wid,
				nextHost,
				nextSid
			].map(encodeURIComponent).join("/")}`;
		}
	}, ...[...sessions].map(([key, session]) => h("option", {
		value: key,
		selected: session === selected
	}, `${session.title || session.session_id} · ${session.host}`)))) : null;
	const offSession = await viewSession(main, selected.host, selected.session_id, {
		project: data.project,
		itemBox,
		picker
	});
	try {
		assertView(connection);
		const offItem = await viewWorkItem(itemBox, wid);
		return () => {
			offSession?.();
			offItem?.();
		};
	} catch (error) {
		offSession?.();
		if (!["VIEW_CHANGED", "CONNECTION_CHANGED"].includes(error.code)) throw error;
	}
}
async function viewProjectWork(main, pid, kind, id) {
	const connection = {
		epoch: state.epoch,
		namespace: state.namespace,
		generation
	};
	try {
		const data = await api("GET", `/projects/${encodeURIComponent(pid)}`);
		assertView(connection);
		const item = data.work?.find((item) => item.kind === kind && item.id === id);
		if (!item) throw new Error(t("workspace_work_missing"));
		if (item.host && item.session_id) return viewSession(main, item.host, item.session_id, { project: data.project });
		main.append(h("h1", {}, item.title || item.action || item.id), deliveryWork(item, data.project.repositories));
	} catch (error) {
		if (!["VIEW_CHANGED", "CONNECTION_CHANGED"].includes(error.code)) main.append(errorBox(error));
	}
}
var NAV = [
	["home", "nav_home"],
	["projects", "nav_projects"],
	["sessions", "nav_sessions"],
	["artifact-review", "ar_nav"],
	["delivery", "nav_delivery"],
	["operations", "nav_operations"],
	["cleanup", "nav_cleanup"],
	["settings", "nav_settings"]
];
var workspaceNav = null;
var workspaceIdentity = "";
function mountWorkspace(name) {
	const identity = state.token ? `${state.epoch}:${state.namespace}` : "";
	if (workspaceIdentity !== identity) {
		workspaceNav?.dispose();
		workspaceNav = null;
		workspaceIdentity = identity;
		if (identity) {
			const connection = {
				epoch: state.epoch,
				namespace: state.namespace
			};
			workspaceNav = workspaceNavigation({
				h,
				t,
				api,
				guard: () => assertConnection(connection),
				onEvents,
				namespace: state.namespace,
				errorBox
			});
			document.getElementById("workspace").prepend(workspaceNav.box);
		}
	}
	document.body.classList.toggle("has-workspace", Boolean(state.token));
	document.getElementById("main").className = ["session", "work"].includes(name) ? "session-view" : "";
	const menu = document.getElementById("workspace-menu");
	menu.hidden = !state.token;
	menu.textContent = t("workspace_navigation");
	menu.onclick = () => {
		const open = document.body.classList.toggle("workspace-nav-open");
		menu.setAttribute("aria-expanded", String(open));
	};
	document.body.classList.remove("workspace-nav-open");
	menu.setAttribute("aria-expanded", "false");
	workspaceNav?.select(location.hash || "#/home");
	const tools = h("details", { class: "workspace-tools" }, h("summary", {}, t("workspace_tools")), h("div", {}, ...NAV.filter(([key]) => ![
		"home",
		"settings",
		"projects"
	].includes(key)).map(([key, label]) => h("a", {
		href: `#/${key}`,
		"aria-current": name === key ? "page" : null
	}, t(label)))));
	document.getElementById("nav").replaceChildren(...state.token ? [h("a", {
		href: "#/home",
		class: name === "home" ? "on" : ""
	}, t("nav_home")), tools] : [], h("a", {
		href: "#/settings",
		class: !state.token || name === "settings" ? "on" : ""
	}, t("nav_settings")));
}
var teardown = null;
var generation = 0;
async function route() {
	const mine = ++generation;
	state.viewReady = false;
	if (teardown) {
		teardown();
		teardown = null;
	}
	freshPage();
	const [name, ...rest] = (location.hash.replace(/^#\//, "") || "home").split("/").map(decodeURIComponent);
	mountWorkspace(name);
	const main = document.getElementById("main");
	main.replaceChildren();
	if (!state.token && name !== "settings") {
		const off = await viewSettings(main);
		if (mine !== generation) {
			off?.();
			return;
		}
		teardown = off || null;
		return;
	}
	const off = await ({
		home: viewHome,
		projects: viewProjects,
		project: viewProject,
		item: viewLinkedWorkItem,
		sessions: viewSessions,
		cleanup: viewCleanup,
		approvals: viewApprovals,
		delivery: viewDelivery,
		operations: viewOperations,
		session: viewSession,
		start: viewStart,
		published: viewPublished,
		orchestrate: viewOrchestration,
		op: viewOperation,
		settings: viewSettings,
		"artifact-review": viewArtifactReview,
		work: viewProjectWork,
		dispatch: viewProjectDispatch,
		host: viewHostDiscovery,
		task: viewTask,
		worktree: (main, id) => viewObservedResource(main, "worktree", id)
	}[name] || viewHome)(main, ...rest);
	if (mine !== generation) {
		if (off) off();
		return;
	}
	teardown = off || null;
	state.viewReady = true;
}
async function start() {
	window.addEventListener("hashchange", route);
	if (nativeDesktop) {
		clearToken();
		const attempt = ++state.nativeAttempt;
		try {
			const status = await nativeStatus();
			if (!status.error && status.credential_available) {
				state.nativeBusy = true;
				route().catch(() => {});
				const caps = await nativeConnect();
				if (attempt === state.nativeAttempt) {
					state.token = "native-credential";
					await activate(caps, status.endpoint);
				}
			}
		} catch (error) {
			if (attempt === state.nativeAttempt) {
				disconnect();
				state.connectionError = error;
				await nativeDisconnect().catch(() => {});
			}
		} finally {
			if (attempt === state.nativeAttempt) state.nativeBusy = false;
		}
	} else {
		const browserSession = await restoreBrowserSession().catch(() => false);
		if (browserSession) clearToken();
		state.token = browserSession ? browserSessionToken : loadToken();
		if (state.token) try {
			await activate(await api("GET", "/capabilities"));
		} catch {
			state.token = null;
		}
	}
	await route();
	streamEvents();
}
start();
//#endregion
