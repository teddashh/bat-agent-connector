import {test, expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';

async function setup(page: any, options: any = {}) {
  await page.addInitScript((options: any) => {
    const caps = (principal: string) => ({actor: 'fixture-operator', scopes: ['observe', 'operate'], api_version: 1,
      contract_version: '2026-10-08', hosts: [], features: {}, actions: [], desktop_identity: {server_id: 'fixture-server', principal_id: principal}});
    const fixture = {available: false, saved: false, supported: true, calls: [] as any[], principal: 'original-principal',
      connected: false, cancel: false, fail: false, delay: false, release: null as any, wrongBootstrap: false, ...options};
    Object.assign(window, {__credentialFixture: fixture, isTauri: true, __TAURI_INTERNALS__: {invoke: async (command: string, args: any) => {
      fixture.calls.push({command, args: args ?? null});
      if (command === 'native_status') return {endpoint: fixture.endpoint ?? 'https://central.example/', expected_actor: 'fixture-operator',
        credential_available: fixture.available, credential_saved: fixture.saved, enrollment_supported: fixture.supported,
        configuration_reload: true, configuration_file: fixture.configPath ?? 'C:\\Users\\fixture\\AppData\\Roaming\\io.betteragent.dashboard\\central.json',
        credential_source: fixture.available ? fixture.saved ? fixture.store ?? 'windows_credential_manager' : 'launch_environment' : null,
        connected: fixture.connected};
      if (command === 'connector_connect') {if (fixture.delayConnect) await new Promise(resolve => {fixture.releaseConnect = resolve;}); if (!fixture.available) throw new Error('Fixture credential unavailable'); fixture.connected = true; return caps(fixture.principal);}
      if (command === 'connector_enroll') {
        if (fixture.delay) await new Promise(resolve => {fixture.release = resolve;});
        if (fixture.cancel) return null;
        if (fixture.fail) throw new Error('Fixture identity mismatch; previous credential retained');
        fixture.principal = fixture.nextPrincipal ?? 'replacement-principal'; fixture.available = true; fixture.saved = true; fixture.connected = true;
        return caps(fixture.principal);
      }
      if (command === 'connector_disconnect') {fixture.connected = false; return;}
      if (command === 'connector_reload_configuration') {fixture.available = false; fixture.connected = false; fixture.endpoint = 'https://replacement.example/'; return {};}
      if (command === 'connector_forget_credential') {fixture.available = false; fixture.saved = false; fixture.connected = false; return;}
      if (command === 'fleet_availability') return {configured: false, platform_supported: false};
      if (command === 'connector_request') {
        const path = args.input.path;
        if (args.input.method === 'POST') {
          if (fixture.loseReply) {fixture.loseReply = false; throw new Error('Fixture lost operation reply');}
          return {status: 202, data: {operation: {operation_id: 'op_' + 'a'.repeat(32), status: 'accepted'}}};
        }
        if (path === '/sessions/h1/fixture-session') return {status: 200, data: {session: {host: 'h1', session_id: 'fixture-session',
          title: 'Fixture session', api_access: 'managed', provenance: 'connector', streaming: false}}};
        if (path.includes('/messages')) return {status: 200, data: {messages: []}};
        if (path.includes('/history')) return {status: 200, data: {events: [], next_cursor: null}};
        if (path.includes('/relations')) return {status: 200, data: {relations: [], next_cursor: null}};
        if (path.startsWith('/checkpoints')) return {status: 200, data: {checkpoints: []}};
        const checkpoint = {cursor: 0, token: 'synthetic-checkpoint'};
        if (path === '/bootstrap' && fixture.missingBootstrap) return {status: 404, data: {error: {code: 'NOT_FOUND', message: 'Fixture bootstrap unavailable'}}};
        if (path === '/bootstrap') return {status: 200, data: {capabilities: caps(fixture.principal), sync: {version: 1,
          server_id: 'fixture-server', principal_id: fixture.wrongBootstrap ? 'wrong-principal' : fixture.principal, checkpoint}}};
        if (path.startsWith('/events')) return {status: 200, data: {events: [], next_cursor: 0, head_cursor: 0, sync: {checkpoint}}};
        return {status: 200, data: {sessions: [], hosts: [], projects: [], work_items: [], operations: []}};
      }
      throw new Error('Unexpected native command ' + command);
    }}});
  }, options);
  await page.goto('/dashboard/#/settings');
  await expect(page.getByRole('region', {name: /Desktop central connection|桌面中央連線/})).toBeVisible();
}

for (const locale of ['en-US', 'zh-TW']) for (const width of [390, 768, 1440]) {
  test(`native credential recovery fits ${locale} ${width}`, async ({browser}) => {
    const context = await browser.newContext({locale, viewport: {width, height: 900}});
    const page = await context.newPage(); const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
    await setup(page);
    const add = page.getByRole('button', {name: locale === 'en-US' ? 'Add credential' : '新增憑證', exact: true});
    await expect(add).toBeEnabled();
    await expect(page.locator('input[type=password]')).toHaveCount(0);
    await expect(page.getByRole('button', {name: locale === 'en-US' ? 'Connect' : '連線', exact: true})).toBeDisabled();
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_connect'))).toEqual([]);
    await mkdir('/tmp/bac-credentials-after', {recursive: true});
    await page.screenshot({path: `/tmp/bac-credentials-after/settings-${locale}-${width}.png`, fullPage: true});
    await add.click();
    await expect(page.getByText(/Connected as fixture-operator|已連線：fixture-operator/)).toBeVisible();
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_enroll')))
      .toEqual([{command: 'connector_enroll', args: {locale}}]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.evaluate(() => [...Object.keys(localStorage), ...Object.keys(sessionStorage)].some(k => k === 'batc.dashboard.token'))).toBe(false);
    expect(errors).toEqual([]); await context.close();
  });
}

test('cancelled or refused replacement preserves the current account and saved drafts', async ({page}) => {
  await setup(page, {available: true, saved: true, cancel: true});
  await page.evaluate(() => localStorage.setItem('batc.draft.synthetic-original', JSON.stringify({key: 'original-key', operation_id: 'op_original', text: 'keep this'})));
  await page.getByRole('button', {name: 'Replace credential', exact: true}).click();
  await expect(page.getByText('Credential entry cancelled. The existing connection is unchanged.')).toBeVisible();
  await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
  await page.evaluate(() => {const f = (window as any).__credentialFixture; f.cancel = false; f.fail = true;});
  await page.getByRole('button', {name: 'Replace credential', exact: true}).click();
  await expect(page.getByText('Fixture identity mismatch; previous credential retained', {exact: false})).toBeVisible();
  await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('batc.draft.synthetic-original')!)))
    .toEqual({key: 'original-key', operation_id: 'op_original', text: 'keep this'});
  expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_disconnect'))).toEqual([]);
});

test('replacement isolates checkpoint namespace and never replays prior-account writes', async ({page}) => {
  await setup(page, {available: true, saved: true});
  await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
  await expect.poll(() => page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('batc.sync.')).length)).toBe(1);
  const original = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage)));
  await page.getByRole('button', {name: 'Replace credential', exact: true}).click();
  await expect.poll(() => page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('batc.sync.')).length)).toBe(2);
  for (const [key, value] of Object.entries(original)) expect(await page.evaluate(k => localStorage.getItem(k), key)).toBe(value);
  expect(await page.evaluate(() => (window as any).__credentialFixture.calls.some((c: any) => c.command === 'connector_request' && c.args.input.method === 'POST'))).toBe(false);
});

test('identity changes between native verification and mounted bootstrap leave the client disconnected', async ({page}) => {
  await setup(page, {wrongBootstrap: true});
  await page.getByRole('button', {name: 'Add credential', exact: true}).click();
  await expect(page.getByText('Invalid central bootstrap identity', {exact: false})).toBeVisible();
  await expect(page.getByText(/Connected as/)).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__credentialFixture.connected)).toBe(false);
  expect(await page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('batc.sync.')))).toEqual([]);
});

test('configuration reload disconnects and waits for explicit verification without clearing drafts', async ({page}) => {
  await setup(page, {available: true});
  await page.evaluate(() => localStorage.setItem('batc.draft.original', 'fixed-intent'));
  await page.getByRole('button', {name: 'Reload configuration', exact: true}).click();
  await expect(page.getByText('https://replacement.example/', {exact: true})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Connect', exact: true})).toBeDisabled();
  await expect(page.getByText(/Connected as/)).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem('batc.draft.original'))).toBe('fixed-intent');
  expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_reload_configuration')))
    .toEqual([{command: 'connector_reload_configuration', args: {}}]);
});

for (const kind of ['connect', 'enroll']) {
  test(`disconnect stays available during manual ${kind} and ignores a late successful response`, async ({page}) => {
    await setup(page, {available: true, saved: true});
    await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
    await page.evaluate(kind => {
      const fixture = (window as any).__credentialFixture;
      if (kind === 'connect') fixture.delayConnect = true; else fixture.delay = true;
    }, kind);
    await page.getByRole('button', {name: kind === 'connect' ? 'Connect' : 'Replace credential', exact: true}).click();
    await expect.poll(() => page.evaluate(kind => typeof (window as any).__credentialFixture[kind === 'connect' ? 'releaseConnect' : 'release'], kind)).toBe('function');
    const disconnect = page.getByRole('button', {name: 'Disconnect', exact: true});
    await expect(disconnect).toBeEnabled(); // no navigation or rerender is needed to cancel
    await disconnect.click();
    await expect(page.getByText('Disconnected. Central work continues.')).toBeVisible();
    await expect(page.getByText(/Connected as/)).toHaveCount(0);
    await page.evaluate(kind => (window as any).__credentialFixture[kind === 'connect' ? 'releaseConnect' : 'release'](), kind);
    await expect(page.getByText('Disconnected. Central work continues.')).toBeVisible();
    await expect(page.getByText(/Connected as/)).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_request' && c.args.input.path === '/bootstrap').length)).toBe(1);
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_disconnect').length)).toBe(1);
  });
}

for (const entry of ['startup', 'connect', 'enroll']) {
  test(`native ${entry} refuses missing mounted bootstrap and recovers without a legacy namespace`, async ({page}) => {
    await setup(page, {available: entry !== 'enroll', saved: entry !== 'enroll', missingBootstrap: entry === 'startup'});
    let original: Record<string, string> = {};
    if (entry === 'connect') {
      await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
      await expect.poll(() => page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('batc.sync.')).length)).toBe(1);
      original = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage)));
    }
    if (entry !== 'startup') {
      await page.evaluate(() => {(window as any).__credentialFixture.missingBootstrap = true;});
      await page.getByRole('button', {name: entry === 'connect' ? 'Connect' : 'Add credential', exact: true}).click();
    }
    await expect(page.getByText('Fixture bootstrap unavailable', {exact: false})).toBeVisible();
    await expect(page.getByText(/Connected as/)).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).__credentialFixture.connected)).toBe(false);
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_disconnect').length)).toBe(1);
    expect(await page.evaluate(() => Object.keys(localStorage).some(k => k.includes(':legacy:')))).toBe(false);
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.some((c: any) => c.command === 'connector_request' && c.args.input.method === 'POST'))).toBe(false);
    for (const [key, value] of Object.entries(original)) expect(await page.evaluate(k => localStorage.getItem(k), key)).toBe(value);
    await page.evaluate(() => {(window as any).__credentialFixture.missingBootstrap = false;});
    await page.getByRole('button', {name: 'Connect', exact: true}).click();
    await expect(page).toHaveURL(/#\/home$/);
    await page.getByRole('link', {name: 'Connection', exact: true}).click();
    await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
    await expect.poll(() => page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('batc.sync.')).length)).toBe(1);
    expect(await page.evaluate(() => Object.keys(localStorage).some(k => k.includes(':legacy:')))).toBe(false);
  });
}

test('forget removes only the local credential and never calls a central mutation', async ({page}) => {
  await setup(page, {available: true, saved: true});
  await page.getByRole('button', {name: 'Forget saved credential', exact: true}).click();
  await expect(page.getByText('Saved credential removed and disconnected.')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Connect', exact: true})).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Add credential', exact: true})).toBeEnabled();
  expect(await page.evaluate(() => (window as any).__credentialFixture.calls.some((c: any) => c.command === 'connector_request' && c.args.input.method === 'POST'))).toBe(false);
});

test('unsupported platforms retain honest memory-only connection recovery', async ({page}) => {
  await setup(page, {supported: false, available: true});
  await expect(page.getByText('Memory-only launch credential', {exact: true})).toBeVisible();
  await expect(page.getByText('Protected storage and credential entry are not available on this platform yet.', {exact: false})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Add credential', exact: true})).toHaveCount(0);
  await page.getByRole('button', {name: 'Disconnect', exact: true}).click();
  await page.getByRole('button', {name: 'Connect', exact: true}).click();
  await expect(page).toHaveURL(/#\/home$/);
  await page.getByRole('link', {name: 'Connection', exact: true}).click();
  await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
});


test('native account replacement preserves the actual lost-reply session key without reapplying it', async ({page}) => {
  await setup(page, {available: true, saved: true, loseReply: true});
  const session = async () => {
    await page.evaluate(() => {location.hash = '#/session/h1/fixture-session';});
    await expect(page.getByRole('heading', {name: 'Fixture session', exact: true})).toBeVisible();
  };
  await session();
  const draft = page.locator('textarea').first();
  await draft.fill('Keep the original instructions');
  await page.getByRole('button', {name: 'Send', exact: true}).click();
  await expect(page.getByText('Fixture lost operation reply', {exact: false})).toBeVisible();
  const original = await page.evaluate(() => (window as any).__credentialFixture.calls.find((c: any) => c.command === 'connector_request' && c.args.input.method === 'POST').args.input);
  await page.getByRole('link', {name: 'Connection', exact: true}).click();
  await page.getByRole('button', {name: 'Replace credential', exact: true}).click();
  await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
  await session(); await expect(draft).toHaveValue('');
  expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_request' && c.args.input.method === 'POST').length)).toBe(1);
  await page.getByRole('link', {name: 'Connection', exact: true}).click();
  await page.evaluate(() => {(window as any).__credentialFixture.nextPrincipal = 'original-principal';});
  await page.getByRole('button', {name: 'Replace credential', exact: true}).click();
  await expect(page.getByText(/Connected as fixture-operator/)).toBeVisible();
  await session(); await expect(draft).toHaveValue('Keep the original instructions');
  await page.getByRole('button', {name: 'Send', exact: true}).click();
  await expect(page.getByText('op_' + 'a'.repeat(32), {exact: true})).toBeVisible();
  const posts = await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_request' && c.args.input.method === 'POST'));
  expect(posts).toHaveLength(2); expect(posts[1].args.input).toEqual(original);
});


test('slow startup renders recovery controls and discards verification completed after disconnect', async ({page}) => {
  await setup(page, {available: true, saved: true, delayConnect: true});
  await expect(page.getByText('Connection in progress…', {exact: true})).toBeVisible();
  await expect.poll(() => page.evaluate(() => typeof (window as any).__credentialFixture.releaseConnect)).toBe('function');
  await page.getByRole('button', {name: 'Disconnect', exact: true}).click();
  await expect(page.getByText('Disconnected. Central work continues.')).toBeVisible();
  await page.evaluate(() => (window as any).__credentialFixture.releaseConnect());
  await expect(page.getByText(/Connected as fixture-operator/)).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_request' && c.args.input.path === '/bootstrap'))).toEqual([]);
});

for (const locale of ['en-US', 'zh-TW']) for (const width of [390, 768, 1440]) {
  test(`macOS Keychain enrollment uses native input ${locale} ${width}`, async ({browser}) => {
    const context = await browser.newContext({locale, viewport: {width, height: 900}});
    const page = await context.newPage();
    await setup(page, {store: 'macos_keychain',
      configPath: '/Users/fixture/Library/Application Support/io.betteragent.dashboard/central.json'});
    await page.getByRole('button', {name: locale === 'en-US' ? 'Add credential' : '新增憑證', exact: true}).click();
    await expect(page.getByText(locale === 'en-US' ? 'macOS Keychain' : 'macOS 鑰匙圈', {exact: true})).toBeVisible();
    await expect(page.locator('input[type=password]')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.evaluate(() => (window as any).__credentialFixture.calls.filter((c: any) => c.command === 'connector_enroll')))
      .toEqual([{command: 'connector_enroll', args: {locale}}]);
    await mkdir('test-results/macos-credentials', {recursive: true});
    await page.screenshot({path: `test-results/macos-credentials/settings-${locale}-${width}.png`, fullPage: true});
    await context.close();
  });
}
