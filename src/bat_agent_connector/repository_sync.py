"""Start at an explicitly published GitHub head in new managed resources."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import uuid
from dataclasses import asdict
from importlib import resources

from . import checkpoints, registry, resource_policy, service, task_control
from .operations import RERUN, ActionDef, AmbiguousOutcome, NeedsAttention, OperationError, StepFailed

SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
FIELDS = {"source_ref", "source_sha", "agent", "prompt", "title"}


def install(ops):
    if "repository.continue" not in ops.actions:
        ops.register(ActionDef("repository.continue", "start", "Start from a published version", run, admit,
                               ("repository", "host", "workspace_id")))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def configured(ops, target):
    if (set(target) != {"repository", "host", "workspace_id"} or any(not isinstance(v, str) or
            not 1 <= len(v) <= 256 for v in target.values())):
        raise OperationError("INVALID_TARGET", "exact repository, host and workspace_id are required", 422)
    fleet = ops.context["fleet"]
    repo = fleet.config.github.repos.get(target["repository"].lower())
    pair = target["host"], target["workspace_id"]
    if not repo or not repo.sync or pair not in repo.sync.bindings:
        raise OperationError("REPOSITORY_NOT_BOUND", "no explicit repository/host/workspace binding", 403)
    hc = fleet.config.hosts.get(pair[0])
    runner = ops.context.get("git_runner")
    if not hc or not fleet.orchestrate_enabled(pair[0]) or not hc.managed_roots:
        raise OperationError("REPOSITORY_HOST_UNAVAILABLE", "target needs write/orchestrate and a managed root", 403)
    if not runner or not runner.available(pair[0]) or ops.context.get("github") is None:
        raise OperationError("REPOSITORY_HOST_UNAVAILABLE", "GitHub read client and SSH Git runner are required", 409)
    return repo, hc


def config_snapshot(ops, target):
    repo, hc = configured(ops, target)
    return {"provider_origin": ops.context["github_config"].api_url, "repository": repo.repository,
            "host": hc.name, "workspace_id": target["workspace_id"], "profile_id": hc.profile_id,
            "managed_root": resource_policy.norm(hc.managed_roots[0]), "remote_url": repo.sync.remote_url,
            "sync": asdict(repo.sync), "permission_policy": hc.default_permission_mode,
            "register_tabs": hc.orchestrate_register_tabs, "confinement_policy": hc.confinement}


def check_ref(ref):
    branch = ref[len("refs/heads/"):] if isinstance(ref, str) and ref.startswith("refs/heads/") else ""
    if not resource_policy.HEAD_REF.fullmatch(branch) or any(p.endswith(".lock") or p.startswith(".") for p in branch.split("/")):
        raise OperationError("INVALID_REF", "source_ref must be an explicit refs/heads/ branch", 422)
    return branch


def admit(ops, principal, target, params, pre):
    configured(ops, target)
    if set(params) - FIELDS or set(pre) != {"repository_id", "binding_digest"}:
        raise OperationError("INVALID_PARAMS", "published start requires exact preview preconditions", 422)
    check_ref(params.get("source_ref"))
    if (not isinstance(params.get("source_sha"), str) or not SHA.fullmatch(params["source_sha"])
            or type(pre["repository_id"]) is not int or pre["repository_id"] <= 0
            or not isinstance(pre["binding_digest"], str) or not DIGEST.fullmatch(pre["binding_digest"])):
        raise OperationError("INVALID_PARAMS", "full source SHA, repository ID and binding digest required", 422)
    if not isinstance(params.get("agent", "claude"), str) or params.get("agent", "claude") not in {"claude", "codex"}:
        raise OperationError("INVALID_PARAMS", "agent must be claude or codex", 422)
    for key, limit in (("prompt", 12000), ("title", 256)):
        if key == "prompt" or key in params:
            if not isinstance(params.get(key), str) or not params[key].strip() or len(params[key]) > limit:
                raise OperationError("INVALID_PARAMS", f"{key} must contain 1-{limit} characters", 422)


async def gh_read(call):
    status, value = await call
    if status != 200 or not isinstance(value, dict):
        raise OperationError("REPOSITORY_SOURCE_UNAVAILABLE", "published GitHub identity/ref unavailable", 409)
    return value


async def published(ops, repository, ref, *, expected_id=None, expected_sha=None):
    gh = ops.context["github"]
    repo = await gh_read(gh.repository(repository))
    if (type(repo.get("id")) is not int or repo["id"] <= 0 or
            str(repo.get("full_name", "")).lower() != repository.lower() or
            expected_id is not None and repo["id"] != expected_id):
        raise OperationError("REPOSITORY_ID_CHANGED", "configured repository has a different identity", 409)
    observed = await gh_read(gh.branch_ref(repository, check_ref(ref)))
    obj = observed.get("object") or {}
    sha = obj.get("sha")
    if (observed.get("ref") != ref or obj.get("type") != "commit" or not isinstance(sha, str) or not SHA.fullmatch(sha)):
        raise OperationError("REPOSITORY_SOURCE_UNAVAILABLE", "GitHub did not prove the exact published branch head", 409)
    if expected_sha is not None and sha != expected_sha:
        raise OperationError("REPOSITORY_REF_CHANGED", "published branch head changed; keep original selection and review again", 409)
    return repo["id"], sha


async def workspace(ops, target, read=None):
    _, hc = configured(ops, target)
    if read:
        value = await read("workspace:load", {"profileId": hc.profile_id})
        doc = json.loads(value) if isinstance(value, str) else value
    else:
        doc = await service._workspace(checkpoints._read_fleet(ops).client(target["host"]))
    rows = [r for r in (doc or {}).get("workspaces", []) if isinstance(r, dict) and r.get("id") == target["workspace_id"]]
    if len(rows) != 1 or not resource_policy.norm(rows[0].get("folderPath")):
        raise OperationError("REPOSITORY_WORKSPACE_CHANGED", "exact bound workspace is unavailable", 409)
    return {"workspace_id": rows[0]["id"], "folder": rows[0]["folderPath"], "name": rows[0].get("name")}


async def preview(ops, principal, request):
    if not principal.allows("observe"):
        raise OperationError("FORBIDDEN", "published version preview requires observe", 403)
    return await source_preview(ops, request)


async def source_preview(ops, request):
    if not isinstance(request, dict) or set(request) != {"repository", "host", "workspace_id", "source_ref"}:
        raise OperationError("INVALID_PARAMS", "preview requires repository/host/workspace_id/source_ref", 422)
    target = {k: request[k] for k in ("repository", "host", "workspace_id")}
    config = config_snapshot(ops, target)
    ws = await workspace(ops, target)
    rid, sha = await published(ops, config["repository"], request["source_ref"])
    binding = digest({"config": config, "workspace": {k: ws[k] for k in ("workspace_id", "folder")}, "repository_id": rid})
    return {"target": target, "workspace": ws, "source_ref": request["source_ref"], "source_sha": sha,
            "repository_id": rid, "binding_digest": binding, "exact_ref_head_only": True,
            "preconditions": {"repository_id": rid, "binding_digest": binding}}


def capabilities(ops):
    return [{"repository": r.repository, "host": h, "workspace_id": w, "exact_ref_head_only": True}
            for r in ops.context["fleet"].config.github.repos.values() if r.sync for h, w in r.sync.bindings]


def receipt(ctx, name):
    row = ctx.service.db.execute("SELECT response FROM operation_steps WHERE operation_id=? AND name=? AND status='succeeded'",
                                 (ctx.operation_id, name)).fetchone()
    return json.loads(row[0]) if row else None


async def resolve(ctx):
    selected = await source_preview(ctx.service, {**ctx.target, "source_ref": ctx.params["source_ref"]})
    if selected["source_sha"] != ctx.params["source_sha"]:
        raise StepFailed("REPOSITORY_REF_CHANGED", "selected published head changed")
    if selected["preconditions"] != ctx.preconditions:
        raise StepFailed("REPOSITORY_BINDING_CHANGED", "reviewed repository/workspace configuration changed")
    config = config_snapshot(ctx.service, ctx.target)
    suffix = ctx.operation_id[3:15]
    clone = config["managed_root"] + "/batc-published-" + ctx.operation_id[3:]
    return {**selected, "config": config, "config_digest": digest(config), "operation_id": ctx.operation_id,
            "session_id": str(uuid.uuid5(checkpoints._SESSION_NS, ctx.operation_id)), "clone_path": clone,
            "worktree_path": clone + "/.bat-worktrees/batc-published-" + suffix, "branch": "batc/published-" + suffix,
            "markers": {"managed-clone": "true", "role": "published", "repository": config["repository"],
                "repository-id": str(selected["repository_id"]), "host": ctx.target["host"], "remote-url": config["remote_url"],
                "operation": ctx.operation_id, "binding": selected["binding_digest"]}}


def guard(ctx, plan):
    ctx.check_cancel()
    if digest(config_snapshot(ctx.service, ctx.target)) != plan["config_digest"]:
        raise StepFailed("REPOSITORY_BINDING_CHANGED", "fixed repository target configuration changed")
    from .cleanup import guard as cleanup_guard
    cleanup_guard(ctx.target["host"], session_id=plan["session_id"], path=plan["worktree_path"], branch=plan["branch"])
    task_control.refuse_owned(ctx.service.context["fleet"], ctx.target["host"], plan["session_id"])
    row = registry.get(ctx.target["host"], plan["session_id"])
    if row and (row.get("start_operation_id") != ctx.operation_id or row.get("status") in registry.RETIRED
                or row.get("repository_binding") != plan["binding_digest"]):
        raise StepFailed("REPOSITORY_BINDING_CHANGED", "published start reservation changed")
    reserved = (ctx.service.get(ctx.operation_id).get("external_refs") or {}).get("repository_reservation")
    if reserved and (not row or row.get("created_at") != reserved.get("created_at")):
        raise StepFailed("REPOSITORY_BINDING_CHANGED", "published start incarnation changed")


async def frame(ctx, plan, *, at_frame=False):
    guard(ctx, plan)
    c = ctx.service.context["fleet"].client(ctx.target["host"])
    current = await workspace(ctx.service, ctx.target, c.guard_read if at_frame else None)
    if current["folder"] != plan["workspace"]["folder"]:
        raise StepFailed("REPOSITORY_WORKSPACE_CHANGED", "fixed workspace folder changed")
    if at_frame:
        root = await c.guard_read("git:getRoot", {"cwd": plan["worktree_path"]})
        log = await c.guard_read("git:log", {"cwd": plan["worktree_path"], "count": 1})
        branch = await c.guard_read("git:branch", {"cwd": plan["worktree_path"]})
        if root != plan["worktree_path"] or not log or log[0].get("hash") != plan["source_sha"] or branch != plan["branch"]:
            raise StepFailed("REPOSITORY_CARRIER_CHANGED", "fixed managed carrier HEAD/root changed")
    guard(ctx, plan)


async def host_call(ctx, plan, phase):
    runner = ctx.service.context["git_runner"]
    req = {**plan, **{k: plan["config"][k] for k in ("managed_root", "remote_url")}, "phase": phase}
    source = (resources.files(__package__) / "repository_sync_host.py").read_text()
    arg = base64.b64encode(json.dumps(req).encode()).decode()
    async def check():
        await frame(ctx, plan)
        if phase == "fetch":
            await published(ctx.service, plan["config"]["repository"], plan["source_ref"],
                            expected_id=plan["repository_id"], expected_sha=plan["source_sha"])
    token = checkpoints._LOCKED_CHECK.set(None if phase.startswith("read.") else check)
    try:
        result = json.loads(await runner.run(ctx.target["host"], "python3 -c " + shlex.quote(source) + " " + shlex.quote(arg),
                                            timeout_s=plan["config"]["sync"]["fetch_timeout_s"]))
    finally:
        checkpoints._LOCKED_CHECK.reset(token)
    if "error" in result:
        if result["error"] == "REPOSITORY_HOST_UNCERTAIN":
            raise AmbiguousOutcome("published repository host effect is unproven")
        raise NeedsAttention(result["error"], "published repository carrier requires review")
    return result["result"]


async def run(ctx):
    async def reread(_):
        return RERUN
    plan = await ctx.step("source.resolve", lambda: resolve(ctx), reconcile=reread)
    ctx.set_refs(host=ctx.target["host"], session_id=plan["session_id"], repository=plan["config"]["repository"],
                 repository_id=plan["repository_id"], clone_path=plan["clone_path"], worktree_path=plan["worktree_path"],
                 branch=plan["branch"], source_sha=plan["source_sha"], source_ref=plan["source_ref"],
                 repository_binding=plan["binding_digest"])
    async def reconcile_fetch(_):
        observed = await host_call(ctx, plan, "read.fetch")
        if observed.get("pinned") is True:
            return {"clone_path": plan["clone_path"], "source_sha": plan["source_sha"], "pinned": True}
        return RERUN  # fixed object fetch/CAS only; carrier/start is a separate effect
    await ctx.step("repository.fetch", lambda: host_call(ctx, plan, "fetch"),
                   request={"source_sha": plan["source_sha"], "repository_id": plan["repository_id"]}, reconcile=reconcile_fetch)
    async def reconcile_carrier(_):
        observed = await host_call(ctx, plan, "read.carrier")
        return observed.get("carrier") or RERUN  # prepare refuses a leftover branch or different carrier
    await ctx.step("worktree.prepare", lambda: host_call(ctx, plan, "prepare"),
                   request={"clone_path": plan["clone_path"], "worktree_path": plan["worktree_path"], "branch": plan["branch"]},
                   reconcile=reconcile_carrier)
    marker = "[batc:" + ctx.operation_id + "]"
    fields = {"start_operation_id": ctx.operation_id, "repository_binding": plan["binding_digest"],
              "repository": plan["config"]["repository"], "repository_id": plan["repository_id"],
              "published_sha": plan["source_sha"], "origin_root": plan["clone_path"], "worktree_made_by": "connector"}
    result = await checkpoints.start_in_worktree(ctx, host=ctx.target["host"], workspace=ctx.target["workspace_id"],
        agent=ctx.params.get("agent", "claude"), worktree=plan["worktree_path"], branch=plan["branch"], head=plan["source_sha"],
        title=ctx.params.get("title") or "Published " + plan["source_sha"][:12], text=marker + "\n" + ctx.params["prompt"],
        marker=marker, registry_fields={}, creation_fields=fields,
        frame_check=lambda: frame(ctx, plan, at_frame=True), final_check=lambda: guard(ctx, plan))
    return {**result, "host": ctx.target["host"], "workspace_id": ctx.target["workspace_id"],
            "repository": plan["config"]["repository"], "repository_id": plan["repository_id"],
            "source_ref": plan["source_ref"], "source_sha": plan["source_sha"], "worktree_path": plan["worktree_path"],
            "branch": plan["branch"], "binding_digest": plan["binding_digest"]}


def carriers(ops, operations):
    for op in operations:
        if op["action"] != "repository.continue":
            continue
        rows = {r["name"]: json.loads(r["response"]) for r in ops.db.execute("SELECT name,response FROM operation_steps "
                "WHERE operation_id=? AND status='succeeded' AND name IN ('source.resolve','repository.fetch','worktree.prepare')",
                (op["operation_id"],))}
        plan = rows.get("source.resolve")
        fetched, carrier = rows.get("repository.fetch"), rows.get("worktree.prepare")
        if not plan:
            continue
        if (plan.get("operation_id") != op["operation_id"] or plan.get("target") != op["target"] or
                fetched is not None and fetched != {"clone_path": plan["clone_path"], "source_sha": plan["source_sha"], "pinned": True}):
            continue
        if fetched is None and not ops.db.execute("SELECT 1 FROM operation_steps WHERE operation_id=? AND name='repository.fetch'",
                                                  (op["operation_id"],)).fetchone():
            continue
        if carrier and carrier != {"clone_path": plan["clone_path"], "worktree_path": plan["worktree_path"],
                                   "branch": plan["branch"], "head": plan["source_sha"]}:
            continue
        yield {**plan, "carrier_proven": bool(fetched and carrier)}
