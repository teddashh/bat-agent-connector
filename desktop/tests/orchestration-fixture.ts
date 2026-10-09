import {expect, type Page} from '@playwright/test';
export const operationId = 'op_'+'a'.repeat(32), childId = 'op_'+'b'.repeat(32);
export async function orchestrationFixture(page: Page, native: boolean, options: any = {}) {
  const state = {actor: 'orchestration-person', principal: 'orchestration-principal', server: 'orchestration-server',
    scopes: ['observe', 'start', 'operate'], allowed: true, writes: true, orchestrate: true, status: 'succeeded',
    posts: [] as any[], reads: [] as string[], errors: [] as string[], operation: null as any, events: [] as any[], after: 0, ...options};
  const caps = () => ({actor: state.actor, scopes: state.scopes, api_version: 1, contract_version: '2026-10-08',
    hosts: ['demo', 'other'].map(host => ({host, writes: state.writes, orchestrate: state.orchestrate})),
    actions: state.absent ? [] : ['session.relay', 'session.failover', 'fanout.plan', 'fanout.start'].map(action => ({action, allowed: state.allowed})), features: {checkpoints: []}});
  const row = (host: string, session_id: string, extra = {}) => ({host, session_id, title: session_id, workspace: 'Dashboard', workspace_id: host+'-ws',
    api_access: 'managed', provenance: 'connector_managed', stale: false, scope_status: 'current', agent_kind: 'claude', streaming: false, relations: [], ...extra});
  const dispatch = async (input: any) => {
    const url = new URL(input.path, 'http://fixture'), path = url.pathname;
    if (input.method === 'POST') {
      state.posts.push(structuredClone(input));
      if (state.refuse) return {status: state.refuse === 'TIER_DISABLED' ? 403 : 409, data: {error: {code: state.refuse, message: 'Fixture refusal'}}};
      if (!state.operation) {
        const action = input.body.action, partial = state.status !== 'succeeded';
        const result = action === 'session.relay' ? {child_operation_id: childId, sent: !partial} : action === 'session.failover' ?
          {new_session_id: 'successor-exact', prompt_sent: !partial} : {started: [{task: 1, title: 'First item', operation_id: childId,
            operation_status: partial ? 'uncertain' : 'succeeded', prompt_sent: !partial}], ...(action === 'fanout.plan' ? {prompt_sent: !partial, session_id: 'planner-exact'} : {})};
        state.operation = {operation_id: operationId, actor: state.actor, idempotency_key: input.idempotency_key, ...structuredClone(input.body), status: state.status,
          steps: [{name: action+'.prepare', status: 'succeeded'}, {name: 'child', status: 'succeeded', response: {operation_id: childId}}],
          external_refs: {[action === 'session.relay' ? 'relay_result' : action === 'session.failover' ? 'failover_result' : 'fanout_result']: result},
          result: partial ? null : action === 'fanout.plan' ? {...result, started: true} : result};
      }
      const op = structuredClone(state.operation);
      if (state.bad === 'key') op.idempotency_key = 'wrong';
      if (state.bad === 'actor') op.actor = 'wrong';
      if (state.bad === 'target') op.target.host = 'wrong';
      if (state.bad === 'items') op.params.plan.reverse();
      if (state.bad === 'preconditions') op.preconditions = {control_version: 4};
      if (state.delayPost) await new Promise(resolve => {state.holdPost = resolve;});
      if (state.lost) {state.lost = false; return {status: 503, data: {error: {code: 'LOST', message: 'Lost orchestration reply'}}};}
      return {status: 200, data: {operation: op}};
    }
    state.reads.push(input.path);
    if (path === '/workspaces') {
      const host = url.searchParams.get('host');
      if (state.delayHost === host) await new Promise(resolve => {state.holdDiscovery = resolve;});
      return {status: 200, data: {workspaces: [{host, workspace_id: host+'-ws', name: 'Dashboard', folder: '/srv/demo'}], has_more: Boolean(state.truncated), errors: {}}};
    }
    if (path === '/sessions') {
      const host = url.searchParams.get('host') || 'demo';
      return {status: 200, data: {sessions: [row(host, 'managed-exact'), row(host, 'managed-second'), row(host, 'manual', {provenance: 'manual'}),
        row(host, 'unknown', {provenance: 'unknown'}), row(host, 'stale', {stale: true}), row(host, 'task-owned', {relations: [{execution_id: 'task-1'}]}),
        row(host, 'codex', {agent_kind: 'codex'}), row(host, 'streaming', {streaming: true})], next_cursor: state.truncated ? 'more-cursor' : null}};
    }
    if (/^\/sessions\/[^/]+\/[^/]+$/.test(path)) {
      if (state.failSelection) return {status: 503, data: {error: {code: 'READ_FAILED', message: 'Selection read failed'}}};
      const [, , host, sid] = path.split('/');
      if (state.delaySession === sid) await new Promise(resolve => {state.holdSelection = resolve;});
      return {status: 200, data: {session: row(host, state.wrongSession ? 'replacement' : sid, state.manual ? {provenance: 'manual'} : {}),
        relations_summary: state.taskOwned ? [{execution_id: 'task-1'}] : []}};
    }
    if (path === '/operations/'+operationId) {
      if (state.failRead) return {status: 503, data: {error: {code: 'READ_FAILED', message: 'Receipt read failed'}}};
      return {status: 200, data: {operation: {...state.operation, status: state.status}}};
    }
    if (path === '/events') state.after = Number(url.searchParams.get('after'));
    const events = state.events.filter((e: any) => e.seq > state.after), cursor = events.at(-1)?.seq || state.after;
    return {status: 200, data: path === '/capabilities' ? caps() : path === '/bootstrap' ? {capabilities: caps(), sync: {version: 1, server_id: state.server,
      principal_id: state.principal, checkpoint: {cursor: 0, token: 'proof-0'}}} : path === '/events' ? {events, head_cursor: cursor, next_cursor: cursor,
      sync: {checkpoint: {cursor, token: 'proof-'+cursor}}} : {hosts: caps().hosts, operations: [], work_items: [], checkpoints: []}};
  };
  page.on('pageerror', e => state.errors.push(e.message));
  if (native) {
    await page.exposeFunction('orchestrationFixture', dispatch);
    await page.addInitScript(() => Object.assign(window, {isTauri: true, __TAURI_INTERNALS__: {invoke: async (command: string, args: any) => {
      if (command === 'native_status') return {endpoint: 'https://fixture.example', credential_available: true};
      if (command === 'connector_connect') return (await (window as any).orchestrationFixture({method: 'GET', path: '/capabilities'})).data;
      if (command === 'connector_disconnect') return;
      if (command === 'connector_request') return (window as any).orchestrationFixture(args.input);
      if (command === 'fleet_availability') return {configured: false, platform_supported: false};
      throw new Error(command);
    }}}));
  } else await page.addInitScript(() => sessionStorage.setItem('batc.dashboard.token', 'fixture-token'));
  await page.route('**/api/v1/**', async route => {
    if (native) throw new Error('Native orchestration must use IPC');
    const request = route.request(), url = new URL(request.url());
    const response = await dispatch({method: request.method(), path: url.pathname.slice('/api/v1'.length)+url.search,
      body: request.postDataJSON(), idempotency_key: request.headers()['idempotency-key']});
    await route.fulfill({status: response.status, contentType: 'application/json', body: JSON.stringify(response.data)});
  });
  return state;
}
export async function openOrchestration(page: Page, mode: string) {
  await page.goto('/dashboard/#/orchestrate/'+mode); const form = page.locator('[data-orchestration]'); await expect(form).toBeVisible(); return form;
}
export async function chooseTarget(form: any, mode: string) {
  await form.getByRole('combobox', {name: 'Host', exact: true}).selectOption('demo');
  const session = ['relay', 'failover'].includes(mode), select = form.getByRole('combobox', {name: session ? 'Exact managed session' : 'Workspace', exact: true});
  await expect(select).toBeEnabled(); await select.selectOption(session ? 'managed-exact' : 'demo-ws');
}
export async function fillOrchestration(form: any, mode: string) {
  if (mode === 'items') {
    await form.getByRole('textbox', {name: 'Item 1 title', exact: true}).fill('Review login');
    await form.getByRole('textbox', {name: 'Item 1 instructions', exact: true}).fill('  Literal first item.  ');
    await form.getByRole('button', {name: 'Add another item'}).click();
    await form.getByRole('textbox', {name: 'Item 2 title', exact: true}).fill('Add tests');
    await form.getByRole('textbox', {name: 'Item 2 instructions', exact: true}).fill('Second literal item.');
  } else await form.getByRole('textbox').fill(mode === 'failover' ? '  Retain original evidence.  ' : '  Keep my original words.\nDo not replace them.  ');
  await form.locator('.orch-check input').last().check();
}
