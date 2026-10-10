// A pasted PR URL selects a resource on the configured central. It is never fetched directly.
export function parsePullRequest(value) {
  try {
    const url = new URL(value.trim());
    if (url.protocol !== 'https:' || url.hostname !== 'github.com' || url.port || url.username || url.password) return null;
    const match = /^\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)\/pull\/([1-9][0-9]{0,8})\/?$/.exec(url.pathname);
    return match ? {repository: match[1], number: match[2]} : null;
  } catch { return null; }
}
