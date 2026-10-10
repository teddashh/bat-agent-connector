import {test, expect, type Page} from '@playwright/test';
import {attentionFixture} from './attention-fixture.ts';

async function fixture(page: Page, native: boolean, locale = 'en') {
  const base = attentionFixture();
  const state = {posts: [] as any[], staged: [] as any[], lost: false, refused: false,
    saved: false, reads: 0, revision: 'a'.repeat(64)};
  const caps = () => ({...base.caps(), scopes: ['observe', 'manage'], hosts: state.saved ? [{host:'demo'}] : [],
    managed_installation: {runtime_version:'0.2.4', background:true},
    actions: [{action:'setup.host', allowed:true}, {action:'setup.repository', allowed:true}]});
  const dispatch = async (input: any) => {
    const url = new URL(input.path, 'http://fixture'), path = url.pathname;
    if (path === '/capabilities') return {status:200, data:caps()};
    if (path === '/bootstrap') return {status:200, data:{capabilities:caps(), sync:{version:1,
      server_id:'setup-central', principal_id:'setup-person', checkpoint:{cursor:0,token:'setup-0'}}}};
    if (path === '/managed/setup') {state.reads++; return {status:200,data:{revision:state.revision,
      hosts:state.saved ? [{name:'demo',url:'wss://demo.example:9876/',connected:true}] : [],
      repositories:[], profiles:[{id:'profile-demo',name:'Demo profile',url:'wss://demo.example:9876/',
        fingerprint:'a'.repeat(64),profile_id:'default',token_available:true}],busy:false}};}
    if (path === '/managed/setup/secrets') {state.staged.push(input); return {status:200,data:{secret_ref:'setup_'+'b'.repeat(32),kind:input.body.kind}};}
    if (path === '/operations' && input.method === 'POST') {
      state.posts.push(input);
      if (state.refused) return {status:409,data:{error:{code:'CONFIGURATION_CHANGED',message:'Read the new configuration.'}}};
      if (state.lost && state.posts.length === 1) return {status:503,data:{error:{code:'LOST_REPLY',message:'The reply was lost.'}}};
      state.saved = true;
      return {status:200,data:{operation:{...input.body,operation_id:'op_'+'c'.repeat(32),
        idempotency_key:input.idempotency_key,status:'succeeded'}}};
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
