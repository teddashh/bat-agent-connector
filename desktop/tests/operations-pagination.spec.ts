import {test, expect} from '@playwright/test';
import {taskFixture} from './task-controls-fixture';
const operations = () => Array.from({length:7},(_,i)=>({operation_id:'op_'+String(i+1).padStart(32,'0'),
  action:'task.pause', actor:'history-person', status:i%2 ? 'running':'needs_attention',
  created_at:100-i, status_reason:`Historical receipt ${i+1}`}));
for(const native of [false,true]) {
  const mode=native?'native':'browser';
  test(`${mode}: history loads older pages and refreshes all loaded pages without duplicates`,async({page})=>{
    const state=await taskFixture(page,native,{list:operations()});
    await page.goto('/dashboard/#/operations');
    await expect(page.locator('[data-operation-count]')).toHaveText('2 operations loaded (not a total)');
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect(page.locator('[data-operation-count]')).toHaveText('4 operations loaded (not a total)');
    expect(state.reads.some((p:string)=>p.includes('before=99'))).toBe(true);
    state.list[3].status_reason='Older receipt changed';
    state.events.push({seq:1,resource_type:'operation',resource_id:state.list[3].operation_id,kind:'operation.updated'});
    await expect(page.getByText('Older receipt changed',{exact:true})).toBeVisible();
    await expect.poll(()=>state.after).toBe(1);
    expect(await page.locator('[data-operation-list] > .row').count()).toBe(4);
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect(page.locator('[data-operation-count]')).toContainText('7 operations loaded');
    await expect(page.getByRole('button',{name:'Load earlier operations'})).toBeHidden();
    expect(state.errors).toEqual([]);
  });
  test(`${mode}: event during pagination joins it and reads again before acknowledging`,async({page})=>{
    const state=await taskFixture(page,native,{list:operations()});
    await page.goto('/dashboard/#/operations');
    await expect(page.locator('[data-operation-count]')).toContainText('2 operations loaded');
    state.delayList=true;
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect.poll(()=>Boolean(state.holdList)).toBe(true);
    state.events.push({seq:1,resource_type:'operation',resource_id:state.list[3].operation_id,kind:'operation.updated'});
    state.failList=true; state.holdList();
    await expect(page.getByText('List read failed',{exact:true})).toBeVisible();
    expect(state.after).toBe(0);
    await expect(page.locator('[data-operation-count]')).toContainText('2 operations loaded');
    state.failList=false;
    await expect.poll(()=>state.after).toBe(1);
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect(page.locator('[data-operation-count]')).toContainText('4 operations loaded');
  });
  test(`${mode}: newly inserted rows use fresh cursors and retain the loaded window`,async({page})=>{
    const state=await taskFixture(page,native,{list:operations()});
    await page.goto('/dashboard/#/operations');
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect(page.locator('[data-operation-count]')).toContainText('4 operations loaded');
    state.list.unshift({...state.list[0],operation_id:'op_'+'e'.repeat(32),created_at:101,status_reason:'New operation'});
    state.events.push({seq:1,resource_type:'operation',resource_id:state.list[0].operation_id,kind:'operation.accepted'});
    await expect(page.getByText('New operation',{exact:true})).toBeVisible();
    await expect.poll(()=>state.after).toBe(1);
    await expect(page.locator('[data-operation-count]')).toContainText('4 operations loaded');
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect(page.getByText('Historical receipt 4',{exact:true})).toBeVisible();
    await expect(page.locator('[data-operation-count]')).toContainText('6 operations loaded');
  });
  test(`${mode}: Home continuation preserves attention or active filter`,async({page})=>{
    await taskFixture(page,native,{list:operations()});
    await page.goto('/dashboard/#/home');
    await page.getByRole('link',{name:'View operations needing attention'}).click();
    await expect(page.locator('[data-operation-count]')).toContainText('2 operations loaded');
    await expect(page.getByText('Historical receipt 2',{exact:true})).toHaveCount(0);
    await page.getByRole('button',{name:'Load earlier operations'}).click();
    await expect(page.getByText('Historical receipt 7',{exact:true})).toBeVisible();
    await page.goto('/dashboard/#/home');
    await page.getByRole('button',{name:'Active operations',exact:true}).click();
    await page.getByRole('link',{name:'View active operations'}).click();
    await expect(page.getByText('Historical receipt 2',{exact:true})).toBeVisible();
    await expect(page.getByText('Historical receipt 1',{exact:true})).toHaveCount(0);
  });
}
