// Used only by disposable installed-app fixtures. Never writes or logs credentials.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFile, readdir, lstat } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

export async function probeManaged(dataRoot, { wait = false } = {}) {
  const root = join(dataRoot, 'managed-central');
  const deadline = Date.now() + (wait ? 70_000 : 5_000);
  do {
    try {
      const path = join(root, 'installation.json');
      assert(!(await lstat(path)).isSymbolicLink());
      const installation = JSON.parse(await readFile(path, 'utf8'));
      assert.equal(installation.state, 'ready');
      const pointer = JSON.parse(await readFile(join(root, 'state/task-service.json'), 'utf8'));
      const endpoint = new URL(pointer.endpoint);
      assert.equal(endpoint.hostname, '127.0.0.1');
      assert.equal(endpoint.protocol, 'http:');
      assert.equal(endpoint.pathname, '/rpc');
      const token = (await readFile(join(root, 'identity.token'), 'utf8')).trim();
      const response = await fetch(`${endpoint.origin}/api/v1/bootstrap`, {
        headers: { Authorization: `Bearer ${token}` }, redirect: 'error', signal: AbortSignal.timeout(3000),
      });
      assert.equal(response.status, 200);
      const bootstrap = await response.json();
      assert.equal(bootstrap.sync.server_id, installation.server_id);
      assert.equal(bootstrap.sync.principal_id, installation.principal_id);
      return { installation_id: installation.installation_id, server_id: installation.server_id,
        principal_id: installation.principal_id, runtime_version: installation.runtime_version,
        authenticated_bootstrap: true };
    } catch {
      if (Date.now() >= deadline) throw new Error('Installed managed service did not authenticate');
      await delay(200);
    }
  } while (true);
}

export async function stopManaged(dataRoot) {
  const data = join(dataRoot, 'managed-central');
  try { await lstat(join(data, 'installation.json')); } catch (error) {
    if (error.code === 'ENOENT') return;
    throw error;
  }
  const cache = join(dataRoot, 'managed-runtimes');
  const entries = (await readdir(cache)).filter(name => /^[a-f0-9]{64}$/.test(name));
  assert.equal(entries.length, 1, 'Fixture owns exactly one extracted runtime');
  const executable = join(cache, entries[0], process.platform === 'win32' ? 'batc-managed-runtime.exe' : 'batc-managed-runtime');
  const reply = execFileSync(executable, ['stop', '--data-dir', data], {
    env: { ...process.env, PATH: '', PYINSTALLER_RESET_ENVIRONMENT: '1' },
    windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], timeout: 30_000, maxBuffer: 16384,
  });
  assert.equal(JSON.parse(reply).stopped, true);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const [action, root] = process.argv.slice(2);
  assert(root && ['wait', 'probe', 'stop'].includes(action));
  if (action === 'stop') await stopManaged(root);
  else console.log(JSON.stringify(await probeManaged(root, { wait: action === 'wait' })));
}
