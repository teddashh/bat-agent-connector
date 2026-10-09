// Presentation identities only: workspace labels never imply a repository or project.
const text = value => typeof value === "string" ? value : "";
export function workspaceGroup(session) {
  const host = text(session.host), id = text(session.workspace_id), name = text(session.workspace);
  return {key: JSON.stringify([host, id ? "id" : name ? "label" : "unknown", id || name]), host, id, name};
}
export function groupedSessions(sessions) {
  const groups = new Map();
  for (const session of sessions) {
    const group = workspaceGroup(session);
    if (!groups.has(group.key)) groups.set(group.key, {...group, sessions: []});
    groups.get(group.key).sessions.push(session);
  }
  return [...groups.values()].sort((a, b) => a.host.localeCompare(b.host) ||
    (a.name || a.id).localeCompare(b.name || b.id) || a.key.localeCompare(b.key));
}
export function matchesSession(session, query) {
  const haystack = [session.title, session.session_id, session.host, session.workspace,
    session.workspace_id, session.agent_kind, session.model, session.worktree_branch,
    ...(Array.isArray(session.connector_metadata?.labels) ? session.connector_metadata.labels : [])]
    .map(text).join("\n").toLocaleLowerCase();
  return query.trim().toLocaleLowerCase().split(/\s+/).every(word => haystack.includes(word));
}
export function runtimeStale(session) {
  return Boolean(session.stale || session.fields_stale || session.state?.evidence?.activity?.stale);
}
export function sessionActivity(session) {
  if (session.pending) return {key: "pending_" + session.pending.kind, tone: "stale"};
  if (session.state?.lifecycle === "ended") return {key: "obs_value_ended", tone: ""};
  if (session.gone_at || ["gone", "missing"].includes(session.state?.enumeration))
    return {key: "sessions_not_seen", tone: "stale"};
  // Stale observations must not claim that output is still arriving.
  if (runtimeStale(session)) return {key: "sessions_stale", tone: "stale"};
  if (session.streaming === true) return {key: "obs_value_streaming", tone: "info"};
  if (session.streaming === false) return {key: "obs_value_not_streaming", tone: ""};
  return {key: "sessions_activity_unknown", tone: ""};
}
