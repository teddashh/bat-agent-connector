// Central creates work; this controller only preserves the reviewed request/key.
const object = v => v && typeof v === 'object' && !Array.isArray(v);
const pid = v => typeof v === 'string' && /^prj_[0-9a-f]{20}$/.test(v);
const wid = v => typeof v === 'string' && /^wi_[0-9a-f]{20}$/.test(v);
const oid = v => typeof v === 'string' && /^op_[0-9a-f]{32}$/.test(v);
const digest = v => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);
const canonical = v => JSON.stringify(v, (_, value) => object(value) ?
  Object.fromEntries(Object.keys(value).sort().map(key => [key, value[key]])) : value);
const source = v => object(v) && ((v.kind === 'operation' && Object.keys(v).length === 2 && oid(v.operation_id)) ||
  (v.kind === 'discovery' && Object.keys(v).length === 3 && ['host', 'profile_id'].every(k => typeof v[k] === 'string' && v[k].length > 0 && v[k].length <= 256)));

export function repairRequest(doc) {
  if (doc?.version !== 1 || !pid(doc.project_id) || !source(doc.source) || !digest(doc.evidence_digest) ||
      !Number.isSafeInteger(doc.expected_project_version) || doc.expected_project_version < 1) throw new Error('Invalid fixed repair evidence');
  return {action: 'repair.create', target: {project_id: doc.project_id}, params: {source: structuredClone(doc.source)},
    preconditions: {expected_project_version: doc.expected_project_version, expected_evidence_digest: doc.evidence_digest}};
}

function validRequest(request) {
  if (!object(request) || canonical(Object.keys(request).sort()) !== canonical(['action', 'params', 'preconditions', 'target'])) return false;
  if (request.action !== 'repair.create' || !object(request.target) || !object(request.params) || !object(request.preconditions)) return false;
  try {
    return canonical(request) === canonical(repairRequest({version: 1, project_id: request.target.project_id,
      source: request.params.source, expected_project_version: request.preconditions.expected_project_version,
      evidence_digest: request.preconditions.expected_evidence_digest}));
  } catch {return false;}
}

export function validateRepairRecord(record, projectId, workItemId) {
  if (record?.version !== 1 || !pid(record.project_id) || !wid(record.work_item_id) || !digest(record.evidence_digest) ||
      !digest(record.expected_work_item_fingerprint) || typeof record.request !== 'string' || !record.request.trim() ||
      record.request.length > 12000 || typeof record.dispatchable !== 'boolean' ||
      record.dispatch_operation_id !== null && !oid(record.dispatch_operation_id) ||
      projectId && record.project_id !== projectId || workItemId && record.work_item_id !== workItemId) {
    throw new Error('Invalid repair work identity');
  }
  return record;
}

export function repairDispatchSeed(record) {
  if (record?.version !== 1 || !pid(record.project_id) || !wid(record.work_item_id) || !digest(record.evidence_digest) ||
      !digest(record.expected_work_item_fingerprint) || typeof record.request !== 'string' || !record.request.trim() ||
      record.request.length > 12000 || record.dispatchable !== true || record.dispatch_operation_id) throw new Error('Repair dispatch requires current server evidence');
  return {project_id: record.project_id, work_item_id: record.work_item_id, prompt: record.request,
    expected_work_item_fingerprint: record.expected_work_item_fingerprint};
}

export function repairIntent({api, guard, actor, allowed, storage, storageKey, newKey = () => crypto.randomUUID()}) {
  guard();
  let intent = null, operation = null, pending = null;
  const raw = storage.getItem(storageKey);
  if (raw) {
    intent = JSON.parse(raw);
    if (!validRequest(intent?.request) || typeof intent.key !== 'string' || !intent.key || intent.key.length > 200 ||
        intent.actor !== actor() || intent.operation_id !== null && !oid(intent.operation_id)) throw new Error('Stored repair intent is unavailable');
  }
  function accept(doc) {
    guard();
    const op = doc?.operation;
    if (!oid(op?.operation_id) || op.actor !== intent.actor || op.idempotency_key !== intent.key ||
        intent.operation_id && op.operation_id !== intent.operation_id ||
        ['action', 'target', 'params', 'preconditions'].some(key => canonical(op[key]) !== canonical(intent.request[key]))) {
      throw new Error('Repair operation identity changed');
    }
    intent.operation_id = op.operation_id;
    storage.setItem(storageKey, JSON.stringify(intent));
    operation = structuredClone(op);
    return structuredClone(operation);
  }
  async function check() {
    guard();
    if (!intent) return null;
    if (pending) return pending;
    if (intent.actor !== actor() || !allowed()) throw new Error('Repair authority unavailable');
    const fixed = structuredClone(intent);
    pending = (async () => accept(await (fixed.operation_id
      ? api('GET', `/operations/${fixed.operation_id}`)
      : api('POST', '/operations?wait=3', fixed.request, fixed.key))))();
    try {return await pending;} finally {pending = null;}
  }
  async function create(doc) {
    guard();
    if (!allowed()) throw new Error('Repair authority unavailable');
    const request = repairRequest(doc);
    if (intent && canonical(request) !== canonical(intent.request)) throw new Error('Resume the original repair intent first');
    if (!intent) {
      const next = {request, key: newKey(), actor: actor(), operation_id: null};
      storage.setItem(storageKey, JSON.stringify(next)); // no send if durable client intent failed
      intent = next;
    }
    return check();
  }
  return {create, check, snapshot: () => {guard(); return structuredClone({intent, operation});}};
}
