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

    [jev]                              # optional judgment layer (TypeSafe Jev); off without an API key
    enabled = "auto"                   # on when TYPESAFE_API_KEY or OPENROUTER_API_KEY is set
    timeout_s = 3.0

Token values never live in this file.
"""

from __future__ import annotations

import json
import os
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


@dataclass
class JevConfig:
    enabled: str = "auto"  # auto | true | false
    timeout_s: float = 3.0
    model: str = "jev-latest"
    base_url: str = "https://api.typesafe.ai"
    api_key_env: str = "TYPESAFE_API_KEY"


@dataclass
class Config:
    hosts: dict[str, HostConfig]
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    jev: JevConfig = field(default_factory=JevConfig)
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
    cl = data.get("client") or {}
    label = str(cl.get("label") or "BAT Agent Connector")
    human = str(cl.get("human_name") or "").strip() or None
    if human and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,40}", human):
        raise ConfigError("[client] human_name must be 1-40 letters/digits/spaces")
    relay_name = str(cl.get("relay_name") or "").strip() or None
    if relay_name and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,40}", relay_name):
        raise ConfigError("[client] relay_name must be 1-40 letters/digits/spaces")
    return Config(hosts=hosts, safety=safety, jev=jev, client_label=label, path=path, human_name=human,
                  relay_name=relay_name)


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
