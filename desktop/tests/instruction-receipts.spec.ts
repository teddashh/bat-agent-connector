import {test, expect} from '@playwright/test';
import {conversationFixture, mountConversation} from './conversation-fixture';
const row = (i: number) => ({operation_id:'op_'+String(i).padStart(32,'0'),host:'demo',session_id:'session-1',
  phase:'accepted',text_excerpt:'Instruction '+i,queue_position:null,per_message_cancel:false,was_queued:true,created_at:1790000000+i});
const response = (rows: any[]) => ({version:1,host:'demo',session_id:'session-1',live_queue_available:false,
  per_message_cancel:false,instructions:rows,next_cursor:null,read_at:1790000000});
async function fixture(page: any, native: boolean) {
  const base=conversationFixture();
  const state={errors:[] as string[],rows:[row(1)],reads:0,after:0,eventDelivered:false,hold:false,release:null as any,
    fail:false,badIdentity:false};
  page.on('pageerror',(error: any)=>state.errors.push(error.message));
  await mountConversation(page,native,async input=>{
    if(input.path.startsWith('/sessions/demo/session-1/instructions')) {
      state.reads++;
      const snapshot=response(structuredClone(state.rows));
      if(state.hold) await new Promise(resolve=>{state.release=resolve;});
      if(state.fail) return {status:503,data:{error:{code:'UNAVAILABLE',message:'Instruction read failed'}}};
      if(state.badIdentity) snapshot.session_id='other-session';
      return {status:200,data:snapshot};
    }
    const result=await base.dispatch(input);
    if(['/bootstrap','/capabilities'].includes(input.path)) {
      const caps=input.path==='/bootstrap'?result.data.capabilities:result.data;
      caps.features={...caps.features,session_instructions:{version:1}};
    }
    if(input.path.startsWith('/events?')) {
      state.after=Number(new URL(input.path,'http://fixture').searchParams.get('after'));
      if(result.data.events?.length) state.eventDelivered=true;
    }
    return result;
  });
  return {state,base};
}
for(const native of [false,true]) {
  const mode=native?'IPC':'HTTP';
  test(`${mode}: instruction event waits for a fresh receipt read after an in-flight snapshot`,async({page})=>{
    const {state,base}=await fixture(page,native);await page.goto('/dashboard/#/session/demo/session-1');
    const panel=page.locator('[data-instruction-receipts]');
    state.hold=true;
    await panel.getByText('Sent instructions',{exact:true}).click();await expect.poll(()=>state.reads).toBe(1);
    state.rows=[row(2),row(1)];base.data.cursor=1;
    await expect.poll(()=>state.eventDelivered).toBe(true);expect(state.after).toBe(0);
    const first=state.release;state.release=null;first();
    await expect.poll(()=>state.reads).toBe(2);expect(state.after).toBe(0);
    await expect(panel).toContainText('Instruction 1');await expect(panel).not.toContainText('Instruction 2');
    state.hold=false;state.release();
    await expect(panel).toContainText('Instruction 2');await expect.poll(()=>state.after).toBe(1);
    await expect(panel).toContainText('Was queued at submission');
    expect(base.data.writes).toEqual([]);expect(state.errors).toEqual([]);
  });
  test(`${mode}: instruction failures retain history and event checkpoint; disposed reads never update the next route`,async({page})=>{
    const {state,base}=await fixture(page,native);await page.goto('/dashboard/#/session/demo/session-1');
    const panel=page.locator('[data-instruction-receipts]');await panel.getByText('Sent instructions',{exact:true}).click();
    await expect(panel).toContainText('Instruction 1');state.fail=true;state.rows=[row(2),row(1)];base.data.cursor=1;
    await expect(panel).toContainText('Instruction read failed');await expect(panel).toContainText('Instruction 1');expect(state.after).toBe(0);
    state.fail=false;await expect(panel).toContainText('Instruction 2');await expect.poll(()=>state.after).toBe(1);
    state.badIdentity=true;await panel.getByRole('button',{name:'Refresh receipts',exact:true}).click();
    await expect(panel).toContainText('Invalid instruction receipts');await expect(panel).toContainText('Instruction 2');
    state.badIdentity=false;state.hold=true;state.release=null;await panel.getByRole('button',{name:'Refresh receipts',exact:true}).click();
    await expect.poll(()=>Boolean(state.release)).toBe(true);
    await page.evaluate(()=>{location.hash='#/sessions';});await expect(page.locator('[data-instruction-receipts]')).toHaveCount(0);
    state.hold=false;state.release();await expect(page.locator('main')).not.toContainText('Instruction 2');
    expect(base.data.writes).toEqual([]);expect(state.errors).toEqual([]);
  });
}
