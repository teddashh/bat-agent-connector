export interface ConnectorEvent { seq: number; kind: string; resource_type?: string; resource_id?: string }
export interface EventPage { events: ConnectorEvent[]; head_cursor: number; next_cursor?: number;
  has_more: boolean; reset_required?: boolean; reset?: boolean }

// Commit only handled events, never head_cursor: a bounded page may have more events after it.
export function consumePage(page: EventPage, cursor: number, emit: (event: ConnectorEvent) => void): number {
  if (page.reset_required || page.reset || page.head_cursor < cursor) {
    emit({ seq: 0, kind: "reset", resource_type: "reset" });
    cursor = 0;
  }
  for (const event of page.events) {
    if (event.seq <= cursor) continue;
    emit(event);
    cursor = event.seq;
  }
  if (Number.isSafeInteger(page.next_cursor) && page.next_cursor! >= cursor && page.next_cursor! <= page.head_cursor)
    cursor = page.next_cursor!;
  return cursor;
}

export function storageScope(endpoint: string, actor: string, server = "legacy", principal = actor): string {
  return [endpoint, server, principal, actor].map(encodeURIComponent).join(":");
}
