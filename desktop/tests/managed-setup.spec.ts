import {test, expect, type Page} from '@playwright/test';
import {attentionFixture} from './attention-fixture.ts';

async function fixture(page: Page, native: boolean, locale = 'en') {
  const base = attentionFixture();
  const state = {posts: [] as any[], staged: [] as any[], lost: false, refused: false,
    saved: false, reads: 0, revision: 'a'.repeat(64), scopes: ['observe', 'manage'], allowed: true, badActor: false, operation: null as any, hold: false, release: null as any, verification: {commands: {other: ['uv', 'run', 'pytest', '-q']}, timeout_s: 300}};
  const caps = () => ({...base.caps(), scopes: state.scopes, hosts: state.saved ? [{host:'demo'}] : [],
    managed_installation: {runtime_version:'0.2.4', background:true},
    actions: [{action:'setup.host', allowed:state.allowed}, {action:'setup.repository', allowed:state.allowed}, {action:'setup.verification', allowed:state.allowed}]});
  const dispatch = async (input: any) => {
    const url = new URL(input.path, 'http://fixture'), path = url.pathname;
    if (path === '/capabilities') return {status:200, data:caps()};
    if (path === '/bootstrap') return {status:200, data:{capabilities:caps(), sync:{version:1,
      server_id:'setup-central', principal_id:'setup-person', checkpoint:{cursor:0,token:'setup-0'}}}};
    if (path === '/managed/setup') {state.reads++; if (state.hold) await new Promise(resolve => {state.release = resolve;}); return {status:200,data:{revision:state.revision, verification: state.verification,
      hosts:state.saved ? [{name:'demo',url:'wss://demo.example:9876/',connected:true}] : [],
      repositories:[], profiles:[{id:'profile-demo',name:'Demo profile',url:'wss://demo.example:9876/',
        fingerprint:'a'.repeat(64),profile_id:'default',token_available:true}],busy:false}};}
    if (path === '/managed/setup/secrets') {state.staged.push(input); return {status:200,data:{secret_ref:'setup_'+'b'.repeat(32),kind:input.body.kind}};}
    if (path.startsWith('/operations/') && state.operation) return {status:200,data:{operation:state.operation}};
    if (path === '/operations' && input.method === 'POST') {
      state.posts.push(input);
      if (state.refused) return {status:409,data:{error:{code:'CONFIGURATION_CHANGED',message:'Read the new configuration.'}}};
      if (state.lost && state.posts.length === 1) return {status:503,data:{error:{code:'LOST_REPLY',message:'The reply was lost.'}}};
      state.saved = true;
      if (input.body.action === 'setup.verification') state.verification = input.body.params;
      state.operation = {...input.body,actor:state.badActor ? 'other' : caps().actor,operation_id:'op_'+'c'.repeat(32),
        idempotency_key:input.idempotency_key,status:'succeeded'};
      return {status:200,data:{operation:state.operation}};
    }
    return base.dispatch(input);
  };
  await page.addInitScript(locale => localStorage.setItem('batc.lang',locale), locale);
  if (native) {
    await page.exposeFunction('setupConnector', dispatch);
    await page.addInitScript(c => Object.assign(window,{isTauri:true,__TAURI_INTERNALS__:{
      invoke:async (command:string,args:any) => {
        if(command==='native_status') return {endpoint:'http://127.0.0.1:9870',credential_available:true};
        if(command==='connector_connect') return c;
        if(command==='connector_request') return (window as any).setupConnector(args.input);
        if(command==='managed_control') return {mode:'managed',ready:true,background:true,login_enabled:false};
        if(command==='connector_disconnect') return null;
        throw new Error('Fixture native feature unavailable');
      }}}),caps());
  } else await page.addInitScript(() => sessionStorage.setItem('batc.dashboard.token','fixture-token'));
  await page.route('**/api/v1/**',async route=>{
    if(native) throw Error('Native must use IPC');
    const req=route.request(),url=new URL(req.url());
    const result=await dispatch({method:req.method(),path:url.pathname.slice(7)+url.search,
      body:req.postData()?req.postDataJSON():null,idempotency_key:req.headers()['idempotency-key']});
    await route.fulfill({status:result.status,json:result.data});
  });
  return state;
}

for (const native of [false,true]) test.describe(native?'Native setup':'Browser setup',()=>{
  test('first run guides setup, preserves non-secret draft, recovers the original key',async({page})=>{
    const state=await fixture(page,native); state.lost=true;
    await page.goto('/dashboard/');
    const panel=page.locator('[data-managed-setup]'),form=panel.locator('[data-setup-host]');
    await expect(panel).toBeVisible();
    await form.getByLabel('BAT connection profile',{exact:true}).selectOption('profile-demo');
    await form.getByLabel('Host name',{exact:true}).fill('demo');
    await form.getByLabel('BAT connection token', {exact:false}).fill('private-bat-secret');
    await panel.getByRole('button',{name:'Recheck configuration'}).click();
    await expect(form.getByLabel('Host name',{exact:true})).toHaveValue('demo');
    await form.getByRole('button',{name:'Verify and save host'}).click();
    await expect(panel).toContainText('The reply was lost.');
    expect(state.posts).toHaveLength(1);expect(state.staged).toHaveLength(1);
    expect(state.posts[0].body.params).toMatchObject({secret_ref:'setup_'+'b'.repeat(32),writes:false,orchestrate:false});
    expect(JSON.stringify(state.posts)).not.toContain('private-bat-secret');
    expect(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))).not.toContain('private-bat-secret');
    await page.reload();
    await expect(form.getByLabel('Host name',{exact:true})).toHaveValue('demo');
    await expect(form.getByRole('button',{name:'Verify and save host'})).toBeDisabled();
    await panel.getByRole('button',{name:'Recover original setup request'}).click();
    await expect(panel.getByRole('link',{name:'View setup operation'})).toBeVisible();
    expect(state.posts).toHaveLength(2);
    expect(state.posts[1].idempotency_key).toBe(state.posts[0].idempotency_key);
    expect(state.posts[1].body).toEqual(state.posts[0].body);expect(state.staged).toHaveLength(1);
    await expect(form.locator('input[type=password]')).toHaveValue('');
  });
  test('known revision refusal allows a reviewed new intent without pretending success',async({page})=>{
    const state=await fixture(page,native);state.refused=true;
    await page.goto('/dashboard/#/settings');
    const panel=page.locator('[data-managed-setup]'),form=panel.locator('[data-setup-host]');
    await form.getByLabel('BAT connection profile',{exact:true}).selectOption('profile-demo');
    await form.getByLabel('Host name',{exact:true}).fill('demo');
    await form.getByRole('button',{name:'Verify and save host'}).click();
    await expect(panel).toContainText('Read the new configuration.');
    await expect(panel.getByRole('link',{name:'View setup operation'})).toHaveCount(0);
    state.revision='d'.repeat(64);state.refused=false;
    await panel.getByRole('button',{name:'Review another configuration change'}).click();
    await form.getByRole('button',{name:'Verify and save host'}).click();
    await expect(panel.getByRole('link',{name:'View setup operation'})).toBeVisible();
    expect(state.posts[1].idempotency_key).not.toBe(state.posts[0].idempotency_key);
    expect(state.posts[1].body.preconditions.config_revision).toBe(state.revision);
  });
});

async function verificationForm(page: Page) {
  const panel = page.locator('[data-managed-setup]');
  await panel.locator('summary').filter({hasText: '3. Configure verification commands'}).click();
  return panel.locator('[data-setup-verification]');
}
async function fillVerification(form: any) {
  await form.getByLabel('Task Service project name', {exact: true}).fill('docs-project');
  await form.getByLabel('Executable', {exact: true}).fill('python');
  await form.getByLabel('Arguments (one per line)', {exact: true}).fill('-m\ncheck project\n--output=one two\n');
  await form.getByLabel('Timeout in seconds (1–3600)', {exact: true}).fill('120');
}
for (const native of [false, true]) test.describe(native ? 'Native verification setup' : 'Browser verification setup', () => {
  test('keeps other commands and exact argv; unknown response replays the same intent after reload', async ({page}) => {
    const state = await fixture(page, native); state.lost = true; await page.goto('/dashboard/#/settings');
    const panel = page.locator('[data-managed-setup]'), form = await verificationForm(page);
    await expect(form.getByLabel('Timeout in seconds (1–3600)', {exact: true})).toHaveValue('300');
    await expect(form).toContainText('it never runs the command'); await fillVerification(form);
    await form.getByRole('button', {name: 'Save verification command', exact: true}).click();
    await expect(panel).toContainText('The reply was lost.');
    const original = structuredClone(state.posts[0]);
    expect(original.body).toEqual({action: 'setup.verification', target: {}, params: {
      commands: {other: ['uv', 'run', 'pytest', '-q'], 'docs-project': ['python', '-m', 'check project', '--output=one two']}, timeout_s: 120},
      preconditions: {config_revision: 'a'.repeat(64)}});
    expect(state.staged).toEqual([]);
    state.revision = 'b'.repeat(64); await page.reload(); await verificationForm(page);
    await expect(form.getByLabel('Arguments (one per line)', {exact: true})).toHaveValue('-m\ncheck project\n--output=one two\n');
    await expect(form.getByRole('button', {name: 'Save verification command', exact: true})).toBeDisabled();
    await panel.getByRole('button', {name: 'Recover original setup request', exact: true}).click();
    await expect(panel.getByRole('link', {name: 'View setup operation'})).toBeVisible();
    expect(state.posts[1]).toEqual(original); expect(state.posts.map(post => post.body.action)).toEqual(['setup.verification', 'setup.verification']);
  });
  test('known verification receipts recover by operation ID without another write', async ({page}) => {
    const state = await fixture(page, native); await page.goto('/dashboard/#/settings');
    const form = await verificationForm(page); await fillVerification(form);
    await form.getByRole('button', {name: 'Save verification command', exact: true}).click();
    await expect(page.getByRole('link', {name: 'View setup operation'})).toBeVisible();
    await page.reload(); await expect(page.getByRole('link', {name: 'View setup operation'})).toBeVisible();
    expect(state.posts).toHaveLength(1);
  });
  test('a receipt from another actor is not accepted as verification success', async ({page}) => {
    const state = await fixture(page, native); state.badActor = true; await page.goto('/dashboard/#/settings');
    const form = await verificationForm(page); await fillVerification(form);
    await form.getByRole('button', {name: 'Save verification command', exact: true}).click();
    await expect(page.locator('[data-managed-setup]')).toContainText('The receipt does not match');
    await expect(page.getByRole('link', {name: 'View setup operation'})).toHaveCount(0);
    await expect(form.getByRole('button', {name: 'Save verification command', exact: true})).toBeDisabled();
  });
  test('refresh preserves the reviewed base until an explicit reload adopts newer configuration', async ({page}) => {
    const state = await fixture(page, native); await page.goto('/dashboard/#/settings');
    const panel = page.locator('[data-managed-setup]'), form = await verificationForm(page); await fillVerification(form);
    state.revision = 'b'.repeat(64); state.verification.commands.other = ['newer-command'];
    await panel.getByRole('button', {name: 'Recheck configuration', exact: true}).click();
    await expect(form).toContainText('Central configuration changed'); await expect(form.getByLabel('Executable', {exact: true})).toHaveValue('python');
    state.refused = true; await form.getByRole('button', {name: 'Save verification command', exact: true}).click();
    await expect(panel).toContainText('Read the new configuration.');
    expect(state.posts[0].body.params.commands.other).toEqual(['uv', 'run', 'pytest', '-q']);
    expect(state.posts[0].body.preconditions.config_revision).toBe('a'.repeat(64));
    state.refused = false; await panel.getByRole('button', {name: 'Review another configuration change', exact: true}).click();
    await form.getByRole('button', {name: 'Reload saved verification settings', exact: true}).click(); await fillVerification(form);
    await form.getByRole('button', {name: 'Save verification command', exact: true}).click();
    await expect(panel.getByRole('link', {name: 'View setup operation'})).toBeVisible();
    expect(state.posts[1].body.params.commands.other).toEqual(['newer-command']);
    expect(state.posts[1].body.preconditions.config_revision).toBe('b'.repeat(64));
    expect(state.posts[1].idempotency_key).not.toBe(state.posts[0].idempotency_key);
  });
  test('verification setup requires both manage scope and an allowed central action', async ({page}) => {
    const state = await fixture(page, native); state.scopes = ['observe']; await page.goto('/dashboard/#/settings');
    let form = await verificationForm(page);
    await expect(form).toContainText('Your central identity is not permitted');
    await expect(form.getByRole('button', {name: 'Save verification command', exact: true})).toBeDisabled();
    await form.evaluate(node => node.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})));
    state.scopes = ['observe', 'manage']; state.allowed = false; await page.reload(); form = await verificationForm(page);
    await expect(form.getByRole('button', {name: 'Save verification command', exact: true})).toBeDisabled();
    expect(state.posts).toEqual([]); expect(state.staged).toEqual([]);
  });
  test('shared clone is an explicit host choice and preserves manual read-only status', async ({page}) => {
    const state = await fixture(page, native); await page.goto('/dashboard/#/settings');
    const form = page.locator('[data-setup-host]');
    await form.locator('summary').filter({hasText: 'Allow managed work'}).click();
    const shared = form.getByRole('checkbox', {name: 'Allow Git worktrees sharing a clone', exact: true});
    await expect(shared).not.toBeChecked(); await shared.check(); await expect(form).toContainText('manual sessions and working directories remain read-only');
    await form.getByLabel('BAT connection profile', {exact: true}).selectOption('profile-demo');
    await form.getByLabel('Host name', {exact: true}).fill('demo'); await form.getByRole('button', {name: 'Verify and save host', exact: true}).click();
    await expect(page.getByRole('link', {name: 'View setup operation'})).toBeVisible();
    expect(state.posts[0].body.params).toMatchObject({shared_clone_worktrees: true, writes: false, orchestrate: false});
  });
  test('navigating away during setup initialization quietly retires the old view', async ({page}) => {
    const state = await fixture(page, native), errors: string[] = []; state.hold = true;
    page.on('pageerror', error => errors.push(error.message)); await page.goto('/dashboard/#/settings');
    await expect.poll(() => Boolean(state.release)).toBe(true);
    await page.evaluate(() => {location.hash = '#/sessions';});
    await expect(page.locator('[data-managed-setup]')).toHaveCount(0);
    state.hold = false; state.release();
    await expect(page.locator('#main h1')).toContainText('Sessions');
    await page.waitForTimeout(100); expect(errors).toEqual([]); expect(state.posts).toEqual([]);
  });
});
