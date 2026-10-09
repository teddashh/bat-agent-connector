// One explicitly published head and one new managed session. Central owns every effect.
const object = v => v && typeof v === 'object' && !Array.isArray(v);
const equal = (a, b) => a === b || (object(a) && object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => equal(a[k], b[k])));
const text = (v, max) => typeof v === 'string' && v.trim().length > 0 && v.length <= max && !/[\x00-\x1f\x7f]/.test(v);
const oid = v => typeof v === 'string' && /^op_[0-9a-f]{32}$/.test(v);
const sha = v => typeof v === 'string' && /^[0-9a-f]{40}$/.test(v);
const digest = v => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);
const terminal = op => ['succeeded', 'failed', 'cancelled'].includes(op?.status);
const target = v => object(v) && Object.keys(v).length === 3 && ['repository', 'host', 'workspace_id'].every(k => text(v[k], 256));
const ref = v => typeof v === 'string' && /^refs\/heads\/(?!-)(?!.*\.\.)(?!.*\/\/)(?!.*@\{)[A-Za-z0-9._/-]{1,200}$/.test(v) &&
  !/[./]$/.test(v) && v.slice(11).split('/').every(p => !p.startsWith('.') && !p.endsWith('.lock'));
const preconditions = v => object(v) && Object.keys(v).length === 2 && Number.isSafeInteger(v.repository_id) && v.repository_id > 0 && digest(v.binding_digest);
const validRequest = r => r?.action === 'repository.continue' && target(r.target) && preconditions(r.preconditions) && object(r.params) &&
  Object.keys(r.params).every(k => ['agent', 'prompt', 'title', 'source_ref', 'source_sha'].includes(k)) &&
  ref(r.params.source_ref) && sha(r.params.source_sha) && ['claude', 'codex'].includes(r.params.agent) &&
  typeof r.params.prompt === 'string' && r.params.prompt.trim() && r.params.prompt.length <= 12000 &&
  (!('title' in r.params) || text(r.params.title, 256));
const validPreview = (p, input) => object(p) && equal(p.target, input.target) && p.source_ref === input.source_ref &&
  sha(p.source_sha) && p.exact_ref_head_only === true && preconditions(p.preconditions) &&
  p.repository_id === p.preconditions.repository_id && p.binding_digest === p.preconditions.binding_digest &&
  object(p.workspace) && p.workspace.workspace_id === input.target.workspace_id && text(p.workspace.folder, 4096) &&
  (p.workspace.name == null || typeof p.workspace.name === 'string');
// Both are checked after existing-key replay, before the operation is inserted.
const noAdmission = new Set(['REPOSITORY_NOT_BOUND', 'REPOSITORY_HOST_UNAVAILABLE']);
export function repositoryStartPanel({h, t, api, caps, guard, ready, errorBox, opStatus, storageKey}) {
  let raw; try {raw = JSON.parse(localStorage.getItem(storageKey));} catch { /* new draft */ }
  let saved = {target: target(raw?.target) ? raw.target : null, source_ref: typeof raw?.source_ref === 'string' ? raw.source_ref : '',
    agent: ['claude', 'codex'].includes(raw?.agent) ? raw.agent : 'claude', prompt: typeof raw?.prompt === 'string' ? raw.prompt : '', title: typeof raw?.title === 'string' ? raw.title : ''};
  if (raw?.intent) {
    const valid = validRequest(raw.intent.request) && text(raw.intent.key, 200);
    saved.intent = {request: valid ? raw.intent.request : null, key: valid ? raw.intent.key : null,
      operation_id: oid(raw.intent.operation_id) ? raw.intent.operation_id : null,
      refused: !raw.intent.operation_id && noAdmission.has(raw.intent.refused) ? raw.intent.refused : null};
    if (valid) Object.assign(saved, {target: raw.intent.request.target, title: ''}, raw.intent.request.params);
  }
  let preview = null, operation = null, busy = false, reading = false, sequence = 0, readFailed = false, submission = null, refreshing = null;
  const current = () => {try {guard(); return true;} catch {return false;}};
  const persist = () => {guard(); localStorage.setItem(storageKey, JSON.stringify(saved));};
  const observe = () => caps()?.scopes?.includes('observe');
  const allowed = () => observe() && caps()?.scopes?.includes('start') && caps()?.actions?.some(a => a.action === 'repository.continue' && a.allowed === true);
  const bindings = () => (caps()?.features?.repository_sync || []).filter(b => b.exact_ref_head_only === true && target({repository: b.repository, host: b.host, workspace_id: b.workspace_id}));
  const bound = () => bindings().some(b => equal({repository: b.repository, host: b.host, workspace_id: b.workspace_id}, saved.target));
  const hostAllowed = () => caps()?.hosts?.some(h => h.host === saved.target?.host && h.writes === true && h.orchestrate === true);
  const status = h('div', {role: 'status'}), facts = h('div', {'data-published-preview': ''}), outcome = h('div', {'data-published-result': ''});
  const binding = h('select', {'aria-label': t('pub_binding')}), sourceRef = h('input', {'aria-label': t('pub_ref'), maxlength: 211, placeholder: 'refs/heads/main'});
  const agent = h('select', {'aria-label': t('start_agent')}, h('option', {value: 'claude'}, 'Claude'), h('option', {value: 'codex'}, 'Codex'));
  const prompt = h('textarea', {'aria-label': t('pub_prompt'), maxlength: 12000, rows: 5}), title = h('input', {'aria-label': t('start_title'), maxlength: 256});
  const inputs = {source_ref: sourceRef, agent, prompt, title};
  const key = b => JSON.stringify(b);
  function fill() {
    binding.replaceChildren(h('option', {value: ''}, t('pub_choose')), ...bindings().map(b => {
      const value = {repository: b.repository, host: b.host, workspace_id: b.workspace_id};
      return h('option', {value: key(value)}, `${b.repository} · ${b.host} · ${b.workspace_id}`);
    }));
    if (saved.target && ![...binding.options].some(o => o.value === key(saved.target))) binding.append(h('option', {value: key(saved.target)}, Object.values(saved.target).join(' · ')));
    binding.value = saved.target ? key(saved.target) : '';
    for (const [k, el] of Object.entries(inputs)) el.value = saved[k];
  }
  const showError = e => {if (current()) status.replaceChildren(errorBox(e));};
  const selected = () => ({target: saved.target, source_ref: saved.source_ref});
  const request = () => ({action: 'repository.continue', target: saved.target,
    params: {source_ref: preview?.source_ref, source_sha: preview?.source_sha, agent: saved.agent, prompt: saved.prompt, ...(saved.title ? {title: saved.title} : {})},
    preconditions: preview?.preconditions});
  const inspect = h('button', {class: 'secondary', onclick: async () => {
    if (!current() || saved.intent || reading || !observe() || !ready() || !bound() || !ref(saved.source_ref)) return;
    const expected = ++sequence, input = selected(); preview = null; reading = true; update(); status.replaceChildren();
    try {
      const doc = await api('POST', '/repository-previews', {...input.target, source_ref: input.source_ref}); guard();
      if (expected !== sequence || saved.intent || !equal(input, selected())) return;
      if (!validPreview(doc.preview, input)) throw new Error(t('pub_invalid_preview'));
      preview = doc.preview;
    } catch (e) {if (expected === sequence) showError(e);}
    finally {if (expected === sequence && current()) {reading = false; update();}}
  }}, t('pub_preview'));
  function accept(candidate) {
    guard(); const intent = saved.intent;
    if (!intent?.request || !intent.key || !oid(candidate?.operation_id) || candidate.actor !== caps()?.actor || candidate.idempotency_key !== intent.key ||
        !equal({action: candidate.action, target: candidate.target, params: candidate.params, preconditions: candidate.preconditions}, intent.request) ||
        intent.operation_id && candidate.operation_id !== intent.operation_id) throw new Error(t('pub_invalid_result'));
    const result = candidate.result, refs = candidate.external_refs || {};
    for (const [name, value] of Object.entries({host: intent.request.target.host, repository: intent.request.target.repository,
      repository_id: intent.request.preconditions.repository_id, source_ref: intent.request.params.source_ref,
      source_sha: intent.request.params.source_sha, repository_binding: intent.request.preconditions.binding_digest})) {
      if (name in refs && refs[name] !== value) throw new Error(t('pub_invalid_result'));
    }
    if (result != null && (!object(result) || result.host !== intent.request.target.host || result.workspace_id !== intent.request.target.workspace_id ||
        result.repository !== intent.request.target.repository || result.source_ref !== intent.request.params.source_ref || result.source_sha !== intent.request.params.source_sha ||
        result.repository_id !== intent.request.preconditions.repository_id || result.binding_digest !== intent.request.preconditions.binding_digest ||
        !text(result.session_id, 256) || result.session_id !== candidate.external_refs?.session_id)) throw new Error(t('pub_invalid_result'));
    if (candidate.status === 'succeeded' && (!result || result.message_id !== `batc-${candidate.operation_id}`)) throw new Error(t('pub_invalid_result'));
    operation = candidate; intent.operation_id = candidate.operation_id; readFailed = false; persist(); status.replaceChildren(); update();
  }
  const apply = h('button', {class: 'primary', onclick: async () => {
    if (!current() || busy || readFailed || !ready() || !allowed() || saved.intent?.operation_id || saved.intent?.refused) return;
    if (!saved.intent) {
      if (!preview || !validPreview(preview, selected()) || !bound() || !hostAllowed() || !validRequest(request())) return;
      saved.intent = {request: request(), key: crypto.randomUUID(), operation_id: null};
    }
    if (!saved.intent.request || !saved.intent.key) return;
    try {persist();} catch (e) {showError(e); update(); return;}
    busy = true; update(); const intent = saved.intent;
    submission = (async () => {
      try {const doc = await api('POST', '/operations?wait=3', intent.request, intent.key); guard(); accept(doc.operation);}
      catch (e) {if (current()) {if (e.status >= 400 && e.status < 500 && noAdmission.has(e.code)) {intent.refused = e.code; try {persist();} catch { /* fixed request remains */ }} showError(e);}}
      finally {busy = false; if (current()) update();}
    })();
    try {await submission;} finally {submission = null;}
  }}, t('pub_apply'));
  const check = h('button', {class: 'secondary', onclick: () => refresh(true).catch(() => {})}, t('permissions_check'));
  const another = h('button', {class: 'secondary', onclick: () => {
    if (!current() || busy || refreshing || readFailed || !(terminal(operation) || saved.intent?.refused)) return;
    const previous = saved; saved = {target: saved.target, source_ref: saved.source_ref, agent: saved.agent, prompt: '', title: ''};
    try {persist();} catch (e) {saved = previous; showError(e); return;}
    operation = preview = null; status.replaceChildren(); fill(); update();
  }}, t('pub_new'));
  function change(field, value) {
    if (!current() || saved.intent || busy) {fill(); return;}
    saved[field] = value;
    if (field === 'target' || field === 'source_ref') {preview = null; sequence++; reading = false;}
    try {persist();} catch (e) {showError(e);} update();
  }
  binding.addEventListener('change', () => change('target', binding.value ? JSON.parse(binding.value) : null));
  for (const [field, el] of Object.entries(inputs)) el.addEventListener(field === 'agent' ? 'change' : 'input', () => change(field, el.value));
  const label = (name, el) => h('label', {}, t(name), el);
  const box = h('section', {class: 'session-start published-start', 'data-published-start': ''},
    h('div', {class: 'panel'}, h('div', {class: 'capture-fields'}, label('pub_binding', binding), label('pub_ref', sourceRef)), h('p', {class: 'muted'}, t('pub_head_only')),
      h('div', {class: 'actions'}, inspect), facts),
    h('div', {class: 'panel'}, h('div', {class: 'capture-fields'}, label('start_agent', agent), label('start_title', title)), label('pub_prompt', prompt),
      h('p', {class: 'muted'}, t('pub_isolation'))), h('div', {class: 'actions'}, apply, check, another), outcome, status);
  function update() {
    const fixed = Boolean(saved.intent);
    binding.disabled = fixed || busy;
    for (const el of Object.values(inputs)) el.disabled = fixed || busy;
    inspect.hidden = fixed; inspect.disabled = reading || !observe() || !ready() || !bound() || !ref(saved.source_ref);
    inspect.textContent = t(reading ? 'pub_loading' : 'pub_preview');
    apply.hidden = Boolean(saved.intent?.operation_id || saved.intent?.refused); apply.textContent = t(fixed ? 'permissions_retry' : 'pub_apply');
    apply.disabled = busy || readFailed || !ready() || !allowed() || (fixed ? !saved.intent.request || !saved.intent.key :
      reading || !preview || !validPreview(preview, selected()) || !bound() || !hostAllowed() || !validRequest(request()));
    check.hidden = !saved.intent?.operation_id; check.disabled = busy || Boolean(refreshing);
    another.hidden = !(terminal(operation) || saved.intent?.refused); another.disabled = busy || Boolean(refreshing) || readFailed;
    facts.replaceChildren(); const original = saved.intent?.request;
    if (preview || original) {
      const r = original || request();
      const row = (label, value) => h('div', {}, h('strong', {}, t(label), ': '), h('span', {class: 'pre'}, value));
      facts.append(h('p', {class: 'muted'}, t('pub_reviewed')), row('capture_repository', r.target.repository), row('host', r.target.host),
        row('sessions_workspace_id', r.target.workspace_id), ...(preview ? [row('start_workspace', `${preview.workspace.name || ''} · ${preview.workspace.folder}`)] : []),
        row('pub_ref', r.params.source_ref), row('pub_sha', r.params.source_sha));
    }
    outcome.replaceChildren();
    if (!allowed()) outcome.append(h('p', {class: 'muted'}, t('pub_unavailable')));
    else if (!bindings().length && !fixed) outcome.append(h('p', {class: 'muted'}, t('pub_no_bindings')));
    if (!fixed) return;
    outcome.append(h('p', {}, operation ? opStatus(operation) : t(saved.intent.refused ? 'start_refused' : 'start_unknown'), ' ',
      saved.intent.operation_id ? h('a', {href: `#/op/${saved.intent.operation_id}`}, t('permissions_details')) : null,
      operation?.status_reason ? ` · ${operation.status_reason}` : ''), h('p', {class: 'muted'}, t('pub_fixed')));
    if (!original || !saved.intent.key) outcome.append(h('p', {class: 'error'}, t('permissions_damaged')));
    const complete = operation?.status === 'succeeded' && operation.result?.message_id === `batc-${operation.operation_id}`;
    const proof = complete ? operation.result : operation?.steps?.some(s => s.name === 'session.start' && s.status === 'succeeded') &&
      text(operation.external_refs?.session_id, 256) ? {host: saved.target.host, session_id: operation.external_refs.session_id} : null;
    if (proof) outcome.append(h('p', {}, t('start_started'), ' ', h('a', {href: `#/session/${encodeURIComponent(proof.host)}/${encodeURIComponent(proof.session_id)}`}, proof.session_id)),
      h('p', {class: 'muted'}, t(complete ? 'start_prompt_accepted' : 'start_prompt_unknown')));
  }
  async function refresh(fresh = false) {
    if (submission) {await submission; guard();}
    if (refreshing) {await refreshing; if (fresh) return refresh(true); return;}
    if (!saved.intent?.operation_id) {update(); return;}
    refreshing = (async () => {const doc = await api('GET', `/operations/${saved.intent.operation_id}`); guard(); accept(doc.operation);})(); update();
    try {await refreshing;} catch (e) {if (current()) {readFailed = true; showError(e); update();} throw e;}
    finally {refreshing = null; if (current()) update();}
  }
  fill(); update();
  return {box, update, refresh, init: refresh};
}
