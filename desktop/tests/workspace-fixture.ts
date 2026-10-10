import {attentionFixture, mountAttention} from './attention-fixture.ts';
import type {Page} from '@playwright/test';
export const workspaceProject = 'prj_' + 'a'.repeat(20);
export const workspaceOperation = 'op_' + 'a'.repeat(32);
export const workspaceRoute = `#/work/${workspaceProject}/execution/${workspaceOperation}`;
export function workspaceFixture(locale = 'en') {
  const zh = locale.startsWith('zh');
  const fixture = attentionFixture();
  const project = {project_id: workspaceProject, name: zh ? '文件搜尋' : 'Documentation search', description: '', repositories: ['example/docs'],
    version: 1, archived: false, counts: {total: 2, pending: 1}, children: []};
  const session = {host: 'demo', session_id: 'search-results', title: zh ? '改善搜尋的空結果提示' : 'Improve empty search results',
    agent_kind: 'codex', model: 'selected-model', streaming: true, workspace: 'docs', workspace_id: 'docs', worktree_id: 'wt_search',
    provenance: 'connector_managed', api_access: 'managed', observed_at: '2026-10-10T12:00:00Z',
    connector_metadata: {version: 1, labels: [], updated_by: null, updated_at: null}};
  const work = {kind: 'execution', id: workspaceOperation, operation_id: workspaceOperation, status: 'succeeded', action: 'repository.continue',
    title: session.title, host: session.host, session_id: session.session_id, session, branch: 'refs/heads/agent/search-empty-state',
    actor: 'agent', eligible: true, repository: 'example/docs', worktree_id: 'wt_search', delivered_to: [] as any[]};
  const detail = {project, path: [], sub_projects: [], work_items: [] as any[], work: [work], archived: []};
  const waitingSession = {...session, session_id:'review-search', streaming:false, pending:{kind:'ask_user'}, title:zh?'確認搜尋的驗收條件':'Confirm search acceptance'};
  detail.work.push({...work, id:'op_'+'b'.repeat(32), operation_id:'op_'+'b'.repeat(32), session_id:waitingSession.session_id,
    title:waitingSession.title, session:waitingSession});
  const roots = [project, { ...project, project_id: 'prj_'+'b'.repeat(20), name: zh ? '桌面安裝與啟動' : 'Desktop installation', counts: {total: 0, pending: 0}},
    {...project, project_id: 'prj_'+'c'.repeat(20), name: zh ? 'Connector 日常運行' : 'Connector operations', counts: {total: 0, pending: 0}}];
  const data = {session, work, detail, roots, failTree: false, linkedItem: false, posts: [] as any[], events: [] as any[], after: 0,
    messages: [
      {id: 'request', role: 'user', ts: '2026-10-10T12:00:00Z', text: zh
        ? '改善文件搜尋沒有結果時的提示。保留查詢內容，讓讀者可以修改關鍵字再搜尋，並補上測試。'
        : 'Improve the empty state in documentation search. Keep the query so readers can edit it and try again. Add tests.'},
      {id: 'response', role: 'assistant', ts: '2026-10-10T12:02:00Z', text: zh
        ? '正在調整空結果提示，保留搜尋字詞與輸入焦點，並補上再次搜尋的測試。\n\n```tsx\n<SearchEmptyState query={query} onRetry={focusSearch} />\n```\n測試仍在執行，完成後會提供固定 commit 供你審閱。'
        : 'I am updating the empty state, preserving the query and input focus, and adding retry tests.\n\n```tsx\n<SearchEmptyState query={query} onRetry={focusSearch} />\n```\nTests are still running. I will provide a fixed commit for review when they finish.'}
    ]};
  const caps = () => ({...fixture.caps(), scopes: ['observe','operate','manage'], features: {execution_delivery: {version: 1}},
    hosts: [{host: 'demo', writes: true}], actions: [{action: 'session.labels.set', allowed: true},{action: 'session.send', allowed: true},{action: 'session.interrupt',allowed:true}]});
  const dispatch = async (input: any) => {
    const url = new URL(input.path, 'http://fixture'), path = url.pathname;
    if (input.method !== 'GET') {data.posts.push(input); return {status: 200, data: {operation: {operation_id: 'op_'+'d'.repeat(32),status:'succeeded'}}};}
    if (path === '/capabilities') return {status: 200, data: caps()};
    if (path === '/bootstrap') return {status: 200, data: {capabilities: caps(), sync: {version:1,server_id:'workspace-fixture',principal_id:fixture.data.principal,checkpoint:{cursor:0,token:'w-0'}}}};
    if (path === '/events') {data.after = Number(url.searchParams.get('after'));const cursor = data.events.at(-1)?.seq || 0;
      return {status:200,data:{events:data.events.filter(e=>e.seq>data.after),next_cursor:cursor,head_cursor:cursor,has_more:false,sync:{checkpoint:{cursor,token:'w-'+cursor}}}};}
    if (path === '/projects' && data.failTree) return {status:503,data:{error:{code:'TREE_UNAVAILABLE',message:'Tree read failed'}}};
    if (path === '/projects') return {status:200,data:{projects:data.roots}};
    if (path.startsWith('/projects/')) return {status:200,data: path.endsWith(workspaceProject) ? data.detail : {...detail,project:roots.find(p=>path.endsWith(p.project_id)),work:[]}};
    if (path.startsWith('/work-items/') && data.linkedItem) return {status:200,data:{work_item:fixture.data.items[0], project, path:[],
      links:[{kind:'session',ref:'demo/search-results',target:{found:true,...data.session},linked_by:'fixture',linked_at:1}],children:[],derived:[],events:[]}};
    if (path === '/sessions/demo/search-results') return {status:200,data:{session:data.session, connector_metadata:data.session.connector_metadata}};
    if (path === '/sessions/demo/search-results/messages') return {status:200,data:{messages:data.messages}};
    if (path === '/sessions') return {status:200,data:{sessions:[data.session],next_cursor:null}};
    if (path === '/sessions/demo/search-results/checkpoints') return {status:200,data:{checkpoints:[]}};
    if (path === '/checkpoints') return {status:200,data:{checkpoints:[]}};
    if (path.endsWith('/permissions')) return {status:200,data:{}};
    if (path.startsWith('/worktrees/')) return {status:200,data:{worktree:{work:[data.work]}}};
    return fixture.dispatch(input);
  };
  return {data, fixture, caps, dispatch};
}
export async function mountWorkspace(page: Page, native: boolean, f: ReturnType<typeof workspaceFixture>) {
  await mountAttention(page,native,{...f.fixture,caps:f.caps},f.dispatch);
}
