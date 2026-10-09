import {test,expect,type Page} from '@playwright/test';
const captureId='op_'+'a'.repeat(32),acceptId='op_'+'b'.repeat(32),executionId='op_'+'c'.repeat(32),artifactId='art_'+'d'.repeat(32);
const taskId='11111111-2222-4333-8444-555555555555',ref={artifact_id:artifactId,revision:1,digest:'e'.repeat(64)},selector={execution_operation_id:executionId};
const source={host:'demo',session_id:'managed-session',root:'/managed/work',repository_root:'/managed/work',provenance:'connector_managed',selector,lineage:{kind:'execution_operation',execution_operation_id:executionId}};
const evidence={size_bytes:20,digest:ref.digest,head_sha:'1'.repeat(40)};
const proof={kind:'managed_capture',operation_id:captureId,fingerprint:'f'.repeat(64),source,evidence,relative_path:'result.txt'};
const row={...ref,size_bytes:20,state:'ready',display_name:'result.txt',operation_id:captureId,source:proof,acceptances:[]};
async function fixture(page:Page,native:boolean,options:any={}) {
 const state={actor:'reviewer',principal:'principal-one',server:'review-server',scopes:['observe','manage','approve'],writes:[] as any[],previews:[] as any[],reads:[] as string[],errors:[] as string[],events:[] as any[],after:0,captureStatus:'succeeded',acceptStatus:'succeeded',sourceGone:false,lostCapture:false,lostAccept:false,captureError:null as any,failRead:false,badResult:null as any,badPreview:false,captured:null as any,accepted:null as any,...options};
 const operation=(kind:string)=>{
  const intent=kind==='capture'?state.captured:state.accepted;if(!intent)return null;
  const op={operation_id:kind==='capture'?captureId:acceptId,actor:state.actor,idempotency_key:intent.idempotency_key,...intent.body,status:kind==='capture'?state.captureStatus:state.acceptStatus,result:kind==='capture'?ref:{...ref,operation_id:acceptId,actor:state.actor,meaning:'artifact_revision_review',source_fingerprint:proof.fingerprint,receipt:intent.body.params.receipt,capture_operation_id:captureId,source_commit:evidence.head_sha,lineage:source.lineage},steps:[]};
  if(state.badResult==='key')op.idempotency_key='wrong-key';if(state.badResult==='actor')op.actor='other';if(state.badResult==='params')op.params={...op.params,unexpected:true};if(state.badResult==='ref')op.result={...op.result,digest:'0'.repeat(64)};if(state.badResult==='accept-receipt'&&kind==='accept')op.result={...op.result,receipt:'not your review'};return op;
 };
 const execution=()=>({operation_id:executionId,action:state.executionAction||'checkpoint.continue',status:state.executionStatus||'succeeded',result:state.executionAction==='session.start'?{...source,started:true,prompt_sent:state.promptSent!==false,message_id:state.promptSent===false?null:'batc-'+executionId}:source,steps:[],target:{},params:{},preconditions:{},external_refs:{}});
 const dispatch=async(input:any)=>{
  const url=new URL(input.path,'http://fixture'),path=url.pathname;
  const caps={actor:state.actor,scopes:state.scopes,api_version:1,contract_version:'2026-10-08',hosts:[{host:'demo',writes:true}],features:{checkpoints:[]},artifacts:{capture:{managed_single_file:true},limits:{max_file_bytes:1024}},actions:[{action:'artifact.capture.managed',allowed:state.scopes.includes('manage')},{action:'artifact.accept',allowed:state.scopes.includes('approve')}]};
  if(input.method==='POST'){
   if(path==='/artifact-managed-capture-previews'){
    state.previews.push(input);if(state.holdPreview)await new Promise(resolve=>{state.releasePreview=resolve;});
    return {status:200,data:{preview:{preview_id:'acpv_'+'2'.repeat(32),preview_token:'fixture-managed-preview',fingerprint:proof.fingerprint,source:{...source,selector:input.body.task_id?{task_id:input.body.task_id,command_id:input.body.command_id}:selector,session_id:state.badPreview?'other-source':source.session_id},evidence,relative_path:input.body.relative_path,snapshot:false,expires_at:state.expired?1:Date.now()/1000+600}}};
   }
   state.writes.push(structuredClone(input));const kind=input.body.action==='artifact.capture.managed'?'capture':'accept';
   if(kind==='capture'&&state.captureError)return {status:403,data:{error:{code:state.captureError,message:'Original credential required'}}};
   if(kind==='capture')state.captured||=structuredClone(input);else state.accepted||=structuredClone(input);
   if(kind==='capture'&&state.lostCapture||kind==='accept'&&state.lostAccept){state.lostCapture=state.lostAccept=false;return {status:503,data:{error:{code:'LOST',message:'Reply lost'}}};}
   return {status:200,data:{operation:operation(kind)}};
  }
  state.reads.push(input.path);
  if(path==='/sessions/demo/managed-session')return state.sourceGone?{status:404,data:{error:{code:'NOT_FOUND',message:'Source removed'}}}:{status:200,data:{session:{host:'demo',session_id:'managed-session',provenance:state.manual?'manual':'connector_managed',api_access:state.manual?'read_only':'managed'},relations_summary:[]}};
  if(path==='/operations/'+captureId||path==='/operations/'+acceptId){if(state.failRead)return {status:503,data:{error:{code:'READ_FAILED',message:'Read unavailable'}}};if(state.holdRead){state.holdRead=false;await new Promise(resolve=>{state.releaseRead=resolve;});}return {status:200,data:{operation:operation(path.endsWith(captureId)?'capture':'accept')}};}
  if(path==='/operations/'+executionId)return {status:200,data:{operation:execution()}};
  if(path==='/operations')return {status:200,data:{operations:url.searchParams.get('action')===execution().action?[execution()]:[],next_before:null}};
  if(path==='/tasks/'+taskId)return {status:200,data:{task:{task_id:taskId,host:'demo',session_id:'managed-session',commands:[{task_id:taskId,session_id:'managed-session',command_id:'cmd-accepted',kind:'send',status:'accepted'},{task_id:taskId,session_id:'managed-session',command_id:'cmd-unknown',kind:'send',status:'uncertain'}]}}};
  if(path.startsWith('/artifacts/'))return state.artifactMissing?{status:404,data:{error:{code:'ARTIFACT_NOT_FOUND',message:'Artifact unavailable'}}}:{status:200,data:{artifact:state.changedArtifactRevision?{...row,revision:2}:state.badArtifact?{...row,source:{...proof,fingerprint:'0'.repeat(64)}}:row}};
  if(path==='/artifacts')return {status:200,data:{artifacts:[{revision:row}],next_cursor:null}};
  if(path==='/events')state.after=Number(url.searchParams.get('after'));const events=state.events.filter((e:any)=>e.seq>state.after),cursor=events.at(-1)?.seq||state.after;
  return {status:200,data:path==='/capabilities'?caps:path==='/bootstrap'?{capabilities:caps,sync:{version:1,server_id:state.server,principal_id:state.principal,checkpoint:{cursor:0,token:'proof-0'}}}:path==='/events'?{events,next_cursor:cursor,head_cursor:cursor,sync:{checkpoint:{cursor,token:'proof-'+cursor}}}:{sessions:[],operations:[],messages:[],hosts:[],work_items:[],checkpoints:[]}};
 };
 page.on('pageerror',error=>state.errors.push(error.message));
 if(native){await page.exposeFunction('artifactReviewFixture',dispatch);await page.addInitScript(()=>Object.assign(window,{isTauri:true,__TAURI_INTERNALS__:{invoke:async(command:string,args:any)=>{if(command==='native_status')return {endpoint:'https://fixture.example',credential_available:true};if(command==='connector_connect')return (await (window as any).artifactReviewFixture({method:'GET',path:'/capabilities'})).data;if(command==='connector_disconnect')return;if(command==='connector_request')return (window as any).artifactReviewFixture(args.input);if(command==='fleet_availability')return {configured:false,platform_supported:false};throw new Error(command);}}}));}
 else await page.addInitScript(()=>sessionStorage.setItem('batc.dashboard.token','fixture-token'));
 await page.route('**/api/v1/**',async route=>{if(native)throw new Error('Native managed artifact UI used browser HTTP');const r=route.request(),url=new URL(r.url()),reply=await dispatch({method:r.method(),path:url.pathname.slice('/api/v1'.length)+url.search,body:r.postDataJSON(),idempotency_key:r.headers()['idempotency-key']});await route.fulfill({status:reply.status,json:reply.data});});return state;
}
async function captureForm(page:Page){await page.goto('/dashboard/#/artifact-review/session/demo/managed-session');const box=page.locator('[data-managed-capture]');await box.getByRole('combobox',{name:'Central execution evidence'}).selectOption(JSON.stringify(selector));await box.getByRole('textbox',{name:'Relative file path'}).fill('result.txt');await box.getByRole('button',{name:'Preview source file',exact:true}).click();await expect(box).toContainText(ref.digest);await box.getByRole('checkbox').check();return box;}
for(const native of [false,true]){
 const mode=native?'native':'browser';
 test(`successful prompted start is a capture candidate and operation entrypoint (${mode})`,async({page})=>{
  const state=await fixture(page,native,{executionAction:'session.start'});await page.goto('/dashboard/#/op/'+executionId);await page.getByRole('link',{name:"Capture and review this execution's file",exact:true}).click();
  await expect(page.getByRole('combobox',{name:'Central execution evidence'})).toHaveValue(JSON.stringify(selector));await expect(page.getByRole('combobox',{name:'Central execution evidence'}).locator('option').filter({hasText:'session.start'})).toHaveCount(1);expect(state.writes).toHaveLength(0);
 });
 for(const excluded of [{promptSent:false},{executionStatus:'uncertain'}])test(`prompt-free or unknown start stays ineligible ${JSON.stringify(excluded)} (${mode})`,async({page})=>{
  const state=await fixture(page,native,{executionAction:'session.start',...excluded});await page.goto('/dashboard/#/artifact-review/session/demo/managed-session');await expect(page.getByRole('combobox',{name:'Central execution evidence'}).locator('option').filter({hasText:executionId})).toHaveCount(0);
  await page.goto('/dashboard/#/op/'+executionId);await expect(page.getByRole('link',{name:"Capture and review this execution's file",exact:true})).toHaveCount(0);await page.goto('/dashboard/#/artifact-review/operation/'+executionId);await expect(page.locator('.error')).toContainText('Connector-managed');await expect(page.getByRole('button',{name:'Preview source file',exact:true})).toBeDisabled();expect(state.previews).toHaveLength(0);expect(state.writes).toHaveLength(0);
 });
 test(`managed capture and acceptance keep separate exact intents (${mode})`,async({page})=>{
  const state=await fixture(page,native),box=await captureForm(page);await box.getByRole('button',{name:'Save reviewed file',exact:true}).click();await expect(page.locator('[data-artifact-ready]')).toContainText(artifactId);
  const review=page.locator('[data-artifact-accept]');await review.getByRole('textbox').fill('Reviewed the exact report.');await review.getByRole('button',{name:'Record review of this revision',exact:true}).click();await expect(page.locator('[data-artifact-accepted]')).toBeVisible();
  expect(state.writes.map((x:any)=>x.body.action)).toEqual(['artifact.capture.managed','artifact.accept']);expect(state.writes[1].body).toEqual({action:'artifact.accept',target:{artifact_id:artifactId,revision:1},params:{digest:ref.digest,source_fingerprint:proof.fingerprint,receipt:'Reviewed the exact report.'},preconditions:{}});
  await page.reload();await expect(page.locator('[data-artifact-accepted]')).toBeVisible();expect(state.writes).toHaveLength(2);expect(state.errors).toEqual([]);await expect(page.getByRole('combobox',{name:'Central execution evidence'})).toHaveValue(JSON.stringify(selector));
 });
 test(`lost capture keeps original credential key after source cleanup (${mode})`,async({page})=>{
  const state=await fixture(page,native,{lostCapture:true}),box=await captureForm(page);await box.getByRole('button',{name:'Save reviewed file',exact:true}).click();await expect(page.locator('.error')).toContainText('Reply lost');
  state.sourceGone=true;state.captureError='FORBIDDEN';await page.reload();await page.getByRole('button',{name:'Check original capture',exact:true}).click();await expect(page.getByText('Capture recovery requires the original credential', {exact:false})).toBeVisible();expect(state.writes[1]).toEqual(state.writes[0]);await expect(page.getByRole('button',{name:'Capture another file'})).toBeDisabled();
  state.captureError=null;await page.reload();await page.getByRole('button',{name:'Check original capture',exact:true}).click();await expect(page.locator('[data-artifact-ready]')).toBeVisible();expect(state.writes[2]).toEqual(state.writes[0]);await page.reload();await expect(page.locator('[data-artifact-ready]')).toBeVisible();expect(state.writes).toHaveLength(3);expect(state.errors).toEqual([]);
 });
 test(`approve-only reviewer opens an exact saved revision (${mode})`,async({page})=>{
  const state=await fixture(page,native,{scopes:['observe','approve']});await page.goto('/dashboard/#/artifact-review/artifact/'+artifactId+'/1');
  const review=page.locator('[data-artifact-accept]');await expect(review).toContainText(ref.digest);await expect(page.locator('[data-managed-capture]')).toBeHidden();
  await review.getByRole('textbox').fill('Read and reviewed this exact revision.');await review.getByRole('button',{name:'Record review of this revision',exact:true}).click();
  await expect(page.locator('[data-artifact-accepted]')).toBeVisible();expect(state.writes.map((w:any)=>w.body.action)).toEqual(['artifact.accept']);expect(state.errors).toEqual([]);
 });
 test(`lost acceptance keeps text, key and fixed ref on reload (${mode})`,async({page})=>{
  const state=await fixture(page,native,{lostAccept:true});await page.goto('/dashboard/#/artifact-review/artifact/'+artifactId+'/1');const review=page.locator('[data-artifact-accept]');
  await review.getByRole('textbox').fill('Original review receipt');await review.getByRole('button',{name:'Record review of this revision',exact:true}).click();await expect(page.locator('.error')).toContainText('Reply lost');
  await page.reload();await expect(review.getByRole('textbox')).toHaveValue('Original review receipt');await expect(review.getByRole('textbox')).toBeDisabled();
  await review.getByRole('button',{name:'Check original review submission',exact:true}).click();await expect(page.locator('[data-artifact-accepted]')).toBeVisible();expect(state.writes[1]).toEqual(state.writes[0]);
  state.artifactMissing=true;await page.reload();await expect(page.locator('[data-artifact-accepted]')).toBeVisible();await expect(page.getByRole('button',{name:'Record another review',exact:true})).toBeDisabled();expect(state.writes).toHaveLength(2);
 });
 test(`new capture rereads task/session context before choosing a later intent (${mode})`,async({page})=>{
  const state=await fixture(page,native),box=await captureForm(page);await box.getByRole('button',{name:'Save reviewed file',exact:true}).click();await expect(page.locator('[data-artifact-ready]')).toBeVisible();state.sourceGone=true;await page.reload();await expect(page.locator('[data-artifact-ready]')).toBeVisible();await page.getByRole('button',{name:'Capture another file',exact:true}).click();await expect(page.locator('.error')).toContainText('Source removed');await expect(page.getByRole('button',{name:'Preview source file',exact:true})).toBeDisabled();expect(state.writes).toHaveLength(1);
 });

 for(const mismatch of ['key','actor','params','ref']) test(`mismatched capture ${mismatch} cannot enable review (${mode})`,async({page})=>{
  const state=await fixture(page,native,{badResult:mismatch}),box=await captureForm(page);await box.getByRole('button',{name:'Save reviewed file',exact:true}).click();
  await expect(page.locator('.error')).toContainText('does not match');await expect(page.locator('[data-artifact-ready]')).toHaveCount(0);await expect(page.getByRole('button',{name:'Capture another file'})).toBeDisabled();
  expect(state.writes).toHaveLength(1);expect(state.errors).toEqual([]);
 });
 test(`mismatched acceptance receipt never reports reviewed (${mode})`,async({page})=>{
  const state=await fixture(page,native,{badResult:'accept-receipt'});await page.goto('/dashboard/#/artifact-review/artifact/'+artifactId+'/1');const box=page.locator('[data-artifact-accept]');
  await box.getByRole('textbox').fill('My exact review');await box.getByRole('button',{name:'Record review of this revision',exact:true}).click();await expect(page.locator('.error')).toContainText('does not match');
  await expect(page.locator('[data-artifact-accepted]')).toHaveCount(0);await expect(page.getByRole('button',{name:'Record another review',exact:true})).toBeDisabled();expect(state.writes).toHaveLength(1);
 });
 test(`task selector offers accepted commands and rejects unsafe file paths (${mode})`,async({page})=>{
  const state=await fixture(page,native);await page.goto('/dashboard/#/artifact-review/task/'+taskId);const box=page.locator('[data-managed-capture]'),select=box.getByRole('combobox',{name:'Central execution evidence'});
  await expect(select.locator('option')).toContainText(['Choose an accepted execution or command','Task Service command']);await expect(select.locator('option').filter({hasText:'cmd-unknown'})).toHaveCount(0);
  await select.selectOption(JSON.stringify({command_id:'cmd-accepted',task_id:taskId}));await box.getByRole('textbox',{name:'Relative file path'}).fill('../unsafe');await expect(box.getByRole('button',{name:'Preview source file',exact:true})).toBeDisabled();
  await box.getByRole('textbox',{name:'Relative file path'}).fill('result.txt');await box.getByRole('button',{name:'Preview source file',exact:true}).click();await expect(box).toContainText(ref.digest);expect(state.previews[0].body).toEqual({host:'demo',session_id:'managed-session',relative_path:'result.txt',task_id:taskId,command_id:'cmd-accepted'});expect(state.writes).toHaveLength(0);
 });
 test(`failed operation event read blocks acknowledgment and preserves fixed draft (${mode})`,async({page})=>{
  const state=await fixture(page,native,{captureStatus:'running'}),box=await captureForm(page);await box.getByRole('button',{name:'Save reviewed file',exact:true}).click();await expect(page.getByRole('link',{name:captureId,exact:true})).toBeVisible();
  state.failRead=true;state.events=[{seq:1,kind:'operation.updated',resource_type:'operation',resource_id:captureId}];await expect(page.locator('.live')).toContainText('paused');expect(state.after).toBe(0);
  state.failRead=false;state.captureStatus='succeeded';await expect(page.locator('[data-artifact-ready]')).toBeVisible();await expect.poll(()=>state.after).toBe(1);expect(state.writes).toHaveLength(1);expect(state.errors).toEqual([]);
 });
 test(`read-only manual context cannot capture or claim managed lineage (${mode})`,async({page})=>{
  const state=await fixture(page,native,{manual:true});await page.goto('/dashboard/#/artifact-review/session/demo/managed-session');await expect(page.locator('.error')).toContainText('Connector-managed');await expect(page.getByRole('button',{name:'Preview source file',exact:true})).toBeDisabled();expect(state.previews).toHaveLength(0);expect(state.writes).toHaveLength(0);
 });

 test(`preview mismatch and expiry cannot submit managed capture (${mode})`,async({page})=>{
  const state=await fixture(page,native,{badPreview:true});await page.goto('/dashboard/#/artifact-review/session/demo/managed-session');const box=page.locator('[data-managed-capture]');
  await box.getByRole('combobox',{name:'Central execution evidence'}).selectOption(JSON.stringify(selector));await box.getByRole('textbox',{name:'Relative file path'}).fill('result.txt');await box.getByRole('button',{name:'Preview source file',exact:true}).click();await expect(page.locator('.error')).toContainText('does not match');
  state.badPreview=false;state.expired=true;await box.getByRole('button',{name:'Preview source file',exact:true}).click();await expect(box).toContainText('Preview expired');await expect(box.getByRole('button',{name:'Save reviewed file',exact:true})).toBeDisabled();expect(state.writes).toHaveLength(0);
 });
 test(`late preview cannot follow navigation into another principal (${mode})`,async({page})=>{
  const state=await fixture(page,native,{holdPreview:true});await page.goto('/dashboard/#/artifact-review/session/demo/managed-session');const box=page.locator('[data-managed-capture]');await box.getByRole('combobox',{name:'Central execution evidence'}).selectOption(JSON.stringify(selector));await box.getByRole('textbox',{name:'Relative file path'}).fill('result.txt');await box.getByRole('button',{name:'Preview source file',exact:true}).click();await expect.poll(()=>typeof state.releasePreview).toBe('function');
  state.actor='other-reviewer';state.principal='other-principal';await page.goto('/dashboard/#/settings');await page.getByRole('button',{name:'Disconnect',exact:true}).click();if(!native)await page.getByPlaceholder('batc_…').fill('different-fixture-token');await page.getByRole('button',{name:'Connect',exact:true}).click();await expect(page).toHaveURL(/#\/home$/);state.releasePreview();await page.goto('/dashboard/#/artifact-review/session/demo/managed-session');
  await expect(page.getByRole('textbox',{name:'Relative file path'})).toHaveValue('');expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);expect(await page.evaluate(()=>Object.entries(localStorage).filter(([k])=>k.startsWith('batc.artifact-review.')).some(([,v])=>v.includes('result.txt')))).toBe(true);
 });
 test(`exact artifact event keeps focused review text and refuses changed revision (${mode})`,async({page})=>{
  const state=await fixture(page,native);await page.goto('/dashboard/#/artifact-review/artifact/'+artifactId+'/1');const text=page.locator('[data-artifact-accept] textarea');await text.fill('Review text remains focused');state.events=[{seq:1,kind:'artifact.accepted',resource_type:'artifact',resource_id:artifactId}];await expect.poll(()=>state.after).toBe(1);await expect(text).toHaveValue('Review text remains focused');await expect(text).toBeFocused();expect(state.writes).toHaveLength(0);state.changedArtifactRevision=true;state.events.push({seq:2,kind:'artifact.updated',resource_type:'artifact',resource_id:artifactId});await expect(page.locator('.live')).toContainText('paused');expect(state.after).toBe(1);await expect(page.getByRole('button',{name:'Record review of this revision',exact:true})).toBeDisabled();await expect(text).toHaveValue('Review text remains focused');state.changedArtifactRevision=false;await expect.poll(()=>state.after).toBe(2);
 });

}
for(const locale of ['en-US','zh-TW']) test.describe(`managed artifact review ${locale}`,()=>{
 test.use({locale});
 for(const width of [390,768,1440]) test(`fits ${width} with exact source evidence`,async({page})=>{
  const state=await fixture(page,false,{scopes:['observe','manage']});await page.setViewportSize({width,height:900});await page.goto('/dashboard/#/artifact-review/artifact/'+artifactId+'/1');
  const review=page.locator('[data-artifact-accept]');await expect(review).toContainText(ref.digest);
  await review.getByRole('textbox').fill(locale==='zh-TW'?'保留這份成果的審閱草稿。':'Keep the review draft.');
  await expect(review.getByRole('button',{name:locale==='zh-TW'?'記錄此版本的審閱':'Record review of this revision',exact:true})).toBeDisabled();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);
  await page.screenshot({path:`test-results/artifact-review-${locale}-${width}.png`,fullPage:true});
 });
});
