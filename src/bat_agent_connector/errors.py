"""Exception types. Messages must never contain token values (see redact.py)."""


class BatError(Exception):
    """Base class for connector errors."""


class ConfigError(BatError):
    pass


class TokenUnavailable(ConfigError):
    pass


class FingerprintMismatch(BatError):
    """The server's TLS certificate does not match the pinned SHA-256 fingerprint."""


class AuthError(BatError):
    pass


class ChannelNotAllowed(BatError):
    """The channel is not on the connector allowlist (or is a write channel with writes disabled)."""


class InvokeError(BatError):
    """The host returned invoke-error."""


class InvokeTimeout(BatError):
    pass


class ConnectionLost(BatError):
    pass


class WriteRefused(BatError):
    """A write tool refused to run (missing confirm, rate limit, writes disabled, streaming...)."""


class TaskDispatchCancelled(WriteRefused):
    """A journaled task send was cancelled before its BAT frame was submitted."""


class TaskIdentityMismatch(WriteRefused):
    """A durable task reservation conflicts with registry or BAT host identity."""


class ResourceReadOnly(WriteRefused):
    """The resource policy refused a mutation before any BAT frame was sent (see resource_policy.py)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")
