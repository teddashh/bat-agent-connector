"""Configuration: host list (TOML), token references, client identity, paths.

Config file (default ``~/.config/bat-agent-connector/hosts.toml``)::

    [client]
    label = "BAT Agent Connector"      # shown on the host's remote-client list

    [safety]
    audit_preview_chars = 0            # 0 = log only sha256 prefix + length of prompts
    write_min_interval_s = 60          # per (host, session)
    max_writes_per_hour = 30           # across all hosts

    [bat]
    profiles_dir = "~/.local/share/org.tonyq.better-agent-terminal/profiles"

    [hosts.myhost]
    url = "wss://127.0.0.1:9876/"
    fingerprint = "AA:BB:...:FF"       # SHA-256 of the server cert (DER)
    token_ref = "env:BAT_TOKEN_MYHOST" # or "file:/path/to/token" or "bat-profile:<profile id>"
    writes = false                     # write tools stay unavailable unless true
    orchestrate = false                # 3rd tier: start worktree sessions, merge, remove (needs writes)
    orchestrate_max_sessions = 4       # cap on concurrently orchestrated sessions on this host
    orchestrate_register_tabs = false  # append a tab to the host workspace (workspace:save, append-only)
    default_permission_mode = "default" # "default" (agent asks) or "allow_all" (like BAT's bypass setting)
    auto_cleanup = false               # allow session_cleanup to merge/remove/stop on this host
    codex_model = ""                   # default model for Codex sessions started/failed over here ("" = BAT default)
    profile_id = "default"             # workspace profile on the host
    managed_roots = []                 # host folders the connector owns (its own clones); see resource_policy.py
    shared_clone_worktrees = true      # legacy: new worktrees may live in a human checkout's .bat-worktrees

    [jev]                              # optional judgment layer (TypeSafe Jev); off without an API key
    enabled = "auto"                   # on when TYPESAFE_API_KEY or OPENROUTER_API_KEY is set
    timeout_s = 3.0

Token values never live in this file.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError, TokenUnavailable
from .redact import register_secret

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

APP = "bat-agent-connector"
DEFAULT_BAT_PROFILES_DIR = "~/.local/share/org.tonyq.better-agent-terminal/profiles"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_FP_RE = re.compile(r"^[0-9A-F]{64}$")


def config_dir() -> Path:
    if os.environ.get("BATC_CONFIG_DIR"):
        return Path(os.environ["BATC_CONFIG_DIR"]).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / APP


def state_dir() -> Path:
    if os.environ.get("BATC_STATE_DIR"):
        return Path(os.environ["BATC_STATE_DIR"]).expanduser()
    base = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(base).expanduser() / APP


def default_config_path() -> Path:
    if os.environ.get("BATC_CONFIG"):
        return Path(os.environ["BATC_CONFIG"]).expanduser()
    return config_dir() / "hosts.toml"


def normalize_fingerprint(fp: str) -> str:
    s = fp.strip().upper()
    if s.startswith("SHA256:"):
        s = s[7:]
    s = s.replace(":", "").replace(" ", "")
    if not _FP_RE.match(s):
        raise ConfigError("fingerprint must be a SHA-256 hex digest (64 hex chars, colons optional)")
    return s


def format_fingerprint(hex64: str) -> str:
    return ":".join(hex64[i : i + 2] for i in range(0, len(hex64), 2))


@dataclass
class HostConfig:
    name: str
    url: str
    fingerprint: str  # normalized 64-hex
    token_ref: str
    writes: bool = False
    orchestrate: bool = False
    orchestrate_max_sessions: int = 4
    orchestrate_register_tabs: bool = False
    default_permission_mode: str = "default"
    auto_cleanup: bool = False
    codex_model: str | None = None
    profile_id: str = "default"
    bat_profiles_dir: str = DEFAULT_BAT_PROFILES_DIR
    labels: list[str] = field(default_factory=list)
    managed_roots: tuple[str, ...] = ()
    shared_clone_worktrees: bool = True

    def __repr__(self) -> str:  # never include token material
        return f"HostConfig(name={self.name!r}, url={self.url!r}, writes={self.writes}, orchestrate={self.orchestrate})"

    @property
    def token_kind(self) -> str:
        return self.token_ref.split(":", 1)[0] if ":" in self.token_ref else "invalid"

    def token_available(self) -> bool:
        try:
            self.resolve_token()
            return True
        except TokenUnavailable:
            return False

    def resolve_token(self) -> str:
        tok = _resolve_token_ref(self.token_ref, self.bat_profiles_dir)
        register_secret(tok)
        return tok


def _resolve_token_ref(ref: str, profiles_dir: str) -> str:
    kind, _, arg = ref.partition(":")
    arg = arg.strip()
    if not arg:
        raise TokenUnavailable("token_ref must look like env:NAME, file:PATH or bat-profile:ID")
    if kind == "env":
        val = os.environ.get(arg, "").strip()
        if not val:
            raise TokenUnavailable(f"environment variable {arg} is not set")
        return val
    if kind == "file":
        p = Path(arg).expanduser()
        try:
            val = p.read_text().strip()
        except OSError as e:
            raise TokenUnavailable(f"cannot read token file {p}: {e.strerror}") from None
        if not val:
            raise TokenUnavailable(f"token file {p} is empty")
        return val
    if kind == "bat-profile":
        return _token_from_bat_profiles(Path(profiles_dir).expanduser(), arg)
    raise TokenUnavailable(f"unknown token_ref kind {kind!r}")


def _token_from_bat_profiles(pdir: Path, profile_id: str) -> str:
    path = pdir / "remote-tokens.enc.json"
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise TokenUnavailable(f"cannot read BAT token store {path}: {type(e).__name__}") from None
    if raw.get("enc") not in (False, None):
        raise TokenUnavailable(
            "BAT token store is encrypted (OS keychain); use token_ref env: or file: instead"
        )
    data = raw.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            raise TokenUnavailable("BAT token store has an unexpected format") from None
    tokens = (data or {}).get("tokens") or {}
    tok = tokens.get(profile_id)
    if not isinstance(tok, str) or not tok:
        raise TokenUnavailable(f"no token for BAT profile {profile_id!r} in {path}")
    return tok


@dataclass
class SafetyConfig:
    audit_preview_chars: int = 0
    write_min_interval_s: float = 60.0
    max_writes_per_hour: int = 30
    max_start_per_call: int = 4


PERMISSION_MODES = ("default", "allow_all")


def normalize_host_path(raw: str) -> str:
    """A host-side absolute POSIX path in canonical text form (no symlink resolution; that needs the host)."""
    path = str(raw or "").strip()
    if not path.startswith("/") or "\0" in path or ".." in path.split("/"):
        raise ConfigError(f"host path {raw!r} must be absolute and must not contain '..'")
    path = posixpath.normpath(path)
    return "/" + path.lstrip("/") if path != "/" else "/"


def _managed_roots(name: str, raw) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ConfigError(f"host {name!r}: managed_roots must be a list of absolute paths")
    roots = tuple(dict.fromkeys(normalize_host_path(x) for x in raw))
    if "/" in roots:
        raise ConfigError(f"host {name!r}: managed_roots must not contain '/'")
    return roots


@dataclass
class JevConfig:
    enabled: str = "auto"  # auto | true | false
    timeout_s: float = 3.0
    model: str = "jev-latest"
    base_url: str = "https://api.typesafe.ai"
    api_key_env: str = "TYPESAFE_API_KEY"


@dataclass
class ApiConfig:
    """[api]: the task daemon's /api/v1 (inventory refresh and browser origins)."""

    inventory_interval_s: float = 60.0
    stale_after_s: float = 180.0
    activity_every: int = 5
    allowed_origins: tuple[str, ...] = ()


_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
MERGE_METHODS = ("merge", "squash", "rebase")
_INPUT_FIELDS = ("source_sha", "operation_id", "environment", "repository")


# Never a PR head that integration pushes to; the PR's base and the default branch are refused as well.
PROTECTED_REFS = ("main", "master", "release/*", "releases/*", "production", "staging")


@dataclass(frozen=True)
class IntegrateConfig:
    """``integrate = {...}`` on a [[github.repos]] entry: which hosts may push composed results to its PR heads,
    and the exact URL they push to (with that host's own git credentials). Design: docs/design/integration.md."""

    hosts: tuple[str, ...]
    remote_url: str
    protected_refs: tuple[str, ...] = PROTECTED_REFS
    fetch_timeout_s: float = 1800.0
    workspace: str | None = None  # BAT workspace for a conflict-resolving session when its source has none


@dataclass(frozen=True)
class GitHubRepo:
    repository: str  # owner/name
    allow_merge: bool = True
    merge_methods: tuple[str, ...] = MERGE_METHODS
    default_merge_method: str = "squash"
    integrate: IntegrateConfig | None = None


@dataclass(frozen=True)
class DeployRecipe:
    """One environment's deploy route. The Dashboard names a recipe; it never passes workflows or inputs."""

    name: str
    repository: str
    environment: str
    mode: str  # "workflow_dispatch" (connector starts it) or "on_merge" (the push already started it)
    workflow: str  # workflow file name, e.g. deploy.yml
    deploy_job: str  # this job must conclude success; skipped is not deployed
    ref: str = "main"  # branch whose workflow file runs (workflow_dispatch)
    inputs: tuple[tuple[str, str], ...] = ()  # workflow input -> one of _INPUT_FIELDS
    run_name_contains: str | None = None  # "operation_id": the workflow's run-name carries it


@dataclass
class GitHubConfig:
    token_ref: str | None = None
    api_url: str = "https://api.github.com"
    api_version: str = "2026-03-10"
    timeout_s: float = 20.0
    wait_max_s: float = 3600.0
    repos: dict[str, GitHubRepo] = field(default_factory=dict)
    recipes: dict[str, DeployRecipe] = field(default_factory=dict)

    def token(self) -> str:
        if not self.token_ref:
            raise TokenUnavailable("[github] token_ref is not configured")
        tok = _resolve_token_ref(self.token_ref, DEFAULT_BAT_PROFILES_DIR)
        register_secret(tok)
        return tok


def _integrate_url(url, repository: str, api_url: str) -> str:
    """The push URL must name this repository on this GitHub, with no credentials or tricks in it."""
    if not isinstance(url, str) or not url or url != url.strip() or url.startswith("-") or any(
            c.isspace() or c in "?#" for c in url):
        raise ConfigError(f"[[github.repos]] {repository}: integrate.remote_url is not a plain URL")
    api_host = re.sub(r"^https?://", "", api_url).split("/", 1)[0].split(":", 1)[0]
    if api_host in {"127.0.0.1", "localhost"} and (url.startswith("/") or url.startswith("file:///")):
        return url  # a local bare repository stands in for GitHub in tests
    gh = "github.com" if api_host == "api.github.com" else api_host
    owner, name = (re.escape(p) for p in repository.split("/", 1))
    tail = rf"{owner}/{name}(\.git)?"
    forms = (rf"git@{re.escape(gh)}:{tail}", rf"ssh://git@{re.escape(gh)}/{tail}", rf"https://{re.escape(gh)}/{tail}")
    if not any(re.fullmatch(f, url, re.IGNORECASE) for f in forms):
        raise ConfigError(f"[[github.repos]] {repository}: integrate.remote_url must be git@{gh}:{repository}.git, "
                          f"ssh://git@{gh}/{repository}.git or https://{gh}/{repository}.git (no token in it)")
    return url


def _integrate(r: dict, repository: str, api_url: str, host_names: set[str]) -> IntegrateConfig | None:
    raw = r.get("integrate")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"[[github.repos]] {repository}: integrate must be a table")
    hosts = raw.get("hosts")
    if not isinstance(hosts, list) or not hosts or any(h not in host_names for h in hosts):
        raise ConfigError(f"[[github.repos]] {repository}: integrate.hosts must list configured hosts")
    protected = raw.get("protected_refs", list(PROTECTED_REFS))
    if not isinstance(protected, list) or any(not isinstance(p, str) or not p for p in protected):
        raise ConfigError(f"[[github.repos]] {repository}: integrate.protected_refs must be a list of globs")
    try:
        timeout = float(raw.get("fetch_timeout_s", 1800))
    except (TypeError, ValueError):
        timeout = -1.0
    if not 60 <= timeout <= 7200:
        raise ConfigError(f"[[github.repos]] {repository}: integrate.fetch_timeout_s must be 60-7200")
    workspace = raw.get("workspace")
    if workspace is not None and (not isinstance(workspace, str) or not workspace.strip()):
        raise ConfigError(f"[[github.repos]] {repository}: integrate.workspace must be a BAT workspace name or id")
    return IntegrateConfig(tuple(dict.fromkeys(str(h) for h in hosts)),
                           _integrate_url(raw.get("remote_url"), repository, api_url), tuple(protected), timeout,
                           workspace)


def parse_github(data: dict) -> GitHubConfig:
    g = data.get("github") or {}
    api_url = str(g.get("api_url") or "https://api.github.com").rstrip("/")
    host = re.sub(r"^https?://", "", api_url).split("/", 1)[0].split(":", 1)[0]
    if not (api_url.startswith("https://") or (api_url.startswith("http://")
                                               and host in {"127.0.0.1", "localhost"})):
        raise ConfigError("[github] api_url must be https:// (http only for a loopback test server)")
    token_ref = g.get("token_ref")
    if token_ref is not None and (not isinstance(token_ref, str) or token_ref.split(":", 1)[0] not in {"env", "file"}):
        raise ConfigError("[github] token_ref must look like env:NAME or file:PATH")
    repos: dict[str, GitHubRepo] = {}
    for r in g.get("repos") or []:
        name = str(r.get("repository") or "")
        if not _REPO_RE.match(name):
            raise ConfigError(f"[[github.repos]] repository {name!r} must be owner/name")
        methods = tuple(r.get("merge_methods") or MERGE_METHODS)
        if not methods or any(m not in MERGE_METHODS for m in methods):
            raise ConfigError(f"[[github.repos]] {name}: merge_methods must be a subset of {MERGE_METHODS}")
        default = str(r.get("default_merge_method") or methods[0])
        if default not in methods:
            raise ConfigError(f"[[github.repos]] {name}: default_merge_method must be one of merge_methods")
        repos[name.lower()] = GitHubRepo(name, bool(r.get("allow_merge", True)), methods, default,
                                         _integrate(r, name, api_url, set((data.get("hosts") or {}).keys())))
    recipes: dict[str, DeployRecipe] = {}
    for r in (data.get("deploy") or {}).get("recipes") or []:
        name = str(r.get("name") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name) or name in recipes:
            raise ConfigError(f"[[deploy.recipes]] name {name!r} is invalid or repeated")
        repo = str(r.get("repository") or "")
        if repo.lower() not in repos:
            raise ConfigError(f"[[deploy.recipes]] {name}: repository {repo!r} needs a [[github.repos]] entry")
        mode = str(r.get("mode") or "")
        if mode not in {"workflow_dispatch", "on_merge"}:
            raise ConfigError(f"[[deploy.recipes]] {name}: mode must be workflow_dispatch or on_merge")
        workflow, job = str(r.get("workflow") or ""), str(r.get("deploy_job") or "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml", workflow) or not job:
            raise ConfigError(f"[[deploy.recipes]] {name}: workflow must be a file name and deploy_job is required")
        inputs = r.get("inputs") or {}
        if not isinstance(inputs, dict) or len(inputs) > 10 or any(
                not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(k)) or v not in _INPUT_FIELDS for k, v in inputs.items()):
            raise ConfigError(f"[[deploy.recipes]] {name}: inputs map workflow inputs to one of {_INPUT_FIELDS}")
        run_name = r.get("run_name_contains")
        if run_name not in (None, "operation_id"):
            raise ConfigError(f"[[deploy.recipes]] {name}: run_name_contains may only be \"operation_id\"")
        if mode == "workflow_dispatch" and "operation_id" not in inputs.values():
            raise ConfigError(f"[[deploy.recipes]] {name}: pass operation_id as a workflow input so a lost "
                              "dispatch reply can be matched to its run")
        recipes[name] = DeployRecipe(name, repos[repo.lower()].repository, str(r.get("environment") or name),
                                     mode, workflow, job, str(r.get("ref") or "main"),
                                     tuple(sorted((str(k), str(v)) for k, v in inputs.items())), run_name)
    return GitHubConfig(
        token_ref=token_ref, api_url=api_url, api_version=str(g.get("api_version") or "2026-03-10"),
        timeout_s=max(2.0, min(120.0, float(g.get("timeout_s", 20)))),
        wait_max_s=max(60.0, min(7 * 86400.0, float(g.get("wait_max_s", 3600)))),
        repos=repos, recipes=recipes)


@dataclass
class Config:
    hosts: dict[str, HostConfig]
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    jev: JevConfig = field(default_factory=JevConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    client_label: str = "BAT Agent Connector"
    path: Path | None = None
    human_name: str | None = None  # [client] human_name: who relayed messages come from (NEED-<NAME> marker)
    relay_name: str | None = None  # [client] relay_name: the relaying bot, named in relay headers

    def host(self, name: str) -> HostConfig:
        if name not in self.hosts:
            raise ConfigError(
                f"unknown host {name!r}; configured: {', '.join(sorted(self.hosts)) or '(none)'}"
            )
        return self.hosts[name]

    @property
    def any_writes(self) -> bool:
        return any(h.writes for h in self.hosts.values())

    @property
    def any_orchestrate(self) -> bool:
        return any(h.writes and h.orchestrate for h in self.hosts.values())


def parse_config(data: dict, path: Path | None = None) -> Config:
    bat = data.get("bat") or {}
    pdir = str(bat.get("profiles_dir") or DEFAULT_BAT_PROFILES_DIR)
    hosts: dict[str, HostConfig] = {}
    for name, h in (data.get("hosts") or {}).items():
        if not _NAME_RE.match(name):
            raise ConfigError(f"invalid host name {name!r}")
        if not isinstance(h, dict):
            raise ConfigError(f"host {name!r} must be a table")
        for key in ("url", "fingerprint", "token_ref"):
            if not h.get(key):
                raise ConfigError(f"host {name!r} is missing {key!r}")
        if "token" in h:
            raise ConfigError(f"host {name!r}: inline 'token' is not supported; use token_ref")
        url = str(h["url"])
        if not url.startswith("wss://"):
            raise ConfigError(f"host {name!r}: url must start with wss://")
        writes = h.get("writes", False)
        if not isinstance(writes, bool):
            raise ConfigError(f"host {name!r}: writes must be true or false")
        orch = h.get("orchestrate", False)
        tabs = h.get("orchestrate_register_tabs", False)
        if not isinstance(orch, bool) or not isinstance(tabs, bool):
            raise ConfigError(f"host {name!r}: orchestrate/orchestrate_register_tabs must be true or false")
        if orch and not writes:
            raise ConfigError(f"host {name!r}: orchestrate = true requires writes = true")
        pmode = str(h.get("default_permission_mode", "default"))
        if pmode not in PERMISSION_MODES:
            raise ConfigError(f"host {name!r}: default_permission_mode must be one of {', '.join(PERMISSION_MODES)}")
        if pmode != "default" and not writes:
            raise ConfigError(f"host {name!r}: default_permission_mode = {pmode!r} requires writes = true")
        cleanup = h.get("auto_cleanup", False)
        if not isinstance(cleanup, bool):
            raise ConfigError(f"host {name!r}: auto_cleanup must be true or false")
        if cleanup and not orch:
            raise ConfigError(f"host {name!r}: auto_cleanup = true requires orchestrate = true")
        shared = h.get("shared_clone_worktrees", True)
        if not isinstance(shared, bool):
            raise ConfigError(f"host {name!r}: shared_clone_worktrees must be true or false")
        cmodel = str(h.get("codex_model") or "").strip() or None
        if cmodel and not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", cmodel):
            raise ConfigError(f"host {name!r}: codex_model {cmodel!r} is not a valid model id")
        hosts[name] = HostConfig(
            name=name,
            url=url,
            fingerprint=normalize_fingerprint(str(h["fingerprint"])),
            token_ref=str(h["token_ref"]),
            writes=writes,
            orchestrate=orch,
            orchestrate_max_sessions=max(1, min(32, int(h.get("orchestrate_max_sessions", 4)))),
            orchestrate_register_tabs=tabs,
            default_permission_mode=pmode,
            auto_cleanup=cleanup,
            codex_model=cmodel,
            profile_id=str(h.get("profile_id") or "default"),
            bat_profiles_dir=str(h.get("bat_profiles_dir") or pdir),
            labels=list(h.get("labels") or []),
            managed_roots=_managed_roots(name, h.get("managed_roots")),
            shared_clone_worktrees=shared,
        )
    s = data.get("safety") or {}
    safety = SafetyConfig(
        audit_preview_chars=max(0, min(200, int(s.get("audit_preview_chars", 0)))),
        write_min_interval_s=float(s.get("write_min_interval_s", 60)),
        max_writes_per_hour=int(s.get("max_writes_per_hour", 30)),
        max_start_per_call=max(1, min(16, int(s.get("max_start_per_call", 4)))),
    )
    j = data.get("jev") or {}
    en = j.get("enabled", "auto")
    en = "true" if en is True else "false" if en is False else str(en).lower()
    if en not in ("auto", "true", "false"):
        raise ConfigError('[jev] enabled must be "auto", true or false')
    base = str(j.get("base_url") or "https://api.typesafe.ai").rstrip("/")
    if not base.startswith("https://"):
        raise ConfigError("[jev] base_url must be https://")
    jev = JevConfig(
        enabled=en,
        timeout_s=max(0.5, min(30.0, float(j.get("timeout_s", 3.0)))),
        model=str(j.get("model") or "jev-latest"),
        base_url=base,
        api_key_env=str(j.get("api_key_env") or "TYPESAFE_API_KEY"),
    )
    a = data.get("api") or {}
    origins = a.get("allowed_origins") or []
    if not isinstance(origins, list) or not all(
            isinstance(o, str) and re.fullmatch(r"https?://[A-Za-z0-9.\-\[\]:]+", o) for o in origins):
        raise ConfigError("[api] allowed_origins must be a list of scheme://host[:port] origins")
    api = ApiConfig(
        inventory_interval_s=max(10.0, min(3600.0, float(a.get("inventory_interval_s", 60)))),
        stale_after_s=max(30.0, min(86400.0, float(a.get("stale_after_s", 180)))),
        activity_every=max(1, min(100, int(a.get("activity_every", 5)))),
        allowed_origins=tuple(origins),
    )
    cl = data.get("client") or {}
    label = str(cl.get("label") or "BAT Agent Connector")
    human = str(cl.get("human_name") or "").strip() or None
    if human and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,40}", human):
        raise ConfigError("[client] human_name must be 1-40 letters/digits/spaces")
    relay_name = str(cl.get("relay_name") or "").strip() or None
    if relay_name and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,40}", relay_name):
        raise ConfigError("[client] relay_name must be 1-40 letters/digits/spaces")
    return Config(hosts=hosts, safety=safety, jev=jev, api=api, github=parse_github(data), client_label=label,
                  path=path, human_name=human, relay_name=relay_name)


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path).expanduser() if path else default_config_path()
    if not p.exists():
        raise ConfigError(
            f"config not found: {p} (run `batc import-bat` or copy examples/hosts.example.toml)"
        )
    try:
        data = tomllib.loads(p.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"cannot parse {p}: {e}") from None
    return parse_config(data, p)


def device_id() -> str:
    """Stable per-client deviceId (avoids 'remote client connected' spam on hosts)."""
    if os.environ.get("BATC_DEVICE_ID"):
        return os.environ["BATC_DEVICE_ID"].strip()
    d = config_dir()
    f = d / "device-id"
    try:
        v = f.read_text().strip()
        if v:
            return v
    except OSError:
        pass
    d.mkdir(parents=True, exist_ok=True)
    v = f"batc-{uuid.uuid4()}"
    try:
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return f.read_text().strip()
    with os.fdopen(fd, "w") as fh:
        fh.write(v + "\n")
    return v
