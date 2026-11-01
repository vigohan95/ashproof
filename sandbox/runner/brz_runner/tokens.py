"""Capability tokens: HMAC-SHA256, single-use, scoped, expiring. Standard library only.

Token = base64url(payload JSON) + "." + base64url(HMAC-SHA256(key, payload bytes)).
Payload: {"v": 1, "tid": task id, "sid": step id or "*", "scope": ["exec"], "iat", "exp", "jti"}.

The control plane signs one token per request with a short TTL; the runner verifies the
signature, the task id, the scope, the expiry, the step id and that the ``jti`` has never
been seen before. Replaying a captured token therefore fails; so does using an "exec"
token to call "/revoke" or a token minted for step s1 to run step s2.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time

TOKEN_VERSION = 1
DEFAULT_TTL_S = 60


class TokenError(Exception):
    pass


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def new_key() -> bytes:
    return secrets.token_bytes(32)


def key_fingerprint(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:16]


def sign_token(
    key: bytes,
    *,
    task_id: str,
    scope: list[str] | tuple[str, ...],
    step_id: str = "*",
    ttl_s: int = DEFAULT_TTL_S,
    now: float | None = None,
) -> str:
    now = time.time() if now is None else now
    payload = {
        "v": TOKEN_VERSION,
        "tid": task_id,
        "sid": step_id,
        "scope": sorted(set(scope)),
        "iat": int(now),
        "exp": int(now) + int(ttl_s),
        "jti": secrets.token_hex(16),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(key, raw, hashlib.sha256).digest()
    return f"{_b64e(raw)}.{_b64e(sig)}"


def verify_token(
    key: bytes,
    token: str,
    *,
    task_id: str,
    action: str,
    step_id: str | None = None,
    now: float | None = None,
) -> dict:
    """Return the payload if the token is valid for ``action`` (and ``step_id``); raise TokenError otherwise.

    Does NOT check single-use; see :class:`TokenRegistry`.
    """
    now = time.time() if now is None else now
    try:
        raw_b64, sig_b64 = token.strip().split(".", 1)
        raw = _b64d(raw_b64)
        sig = _b64d(sig_b64)
    except (ValueError, TypeError) as exc:
        raise TokenError("malformed token") from exc
    expected = hmac.new(key, raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise TokenError("bad signature")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise TokenError("malformed payload") from exc
    if payload.get("v") != TOKEN_VERSION:
        raise TokenError("unsupported token version")
    if payload.get("tid") != task_id:
        raise TokenError("token is for a different task")
    if now >= float(payload.get("exp", 0)):
        raise TokenError("token expired")
    if float(payload.get("iat", 0)) > now + 30:  # clock skew guard
        raise TokenError("token issued in the future")
    if action not in (payload.get("scope") or []):
        raise TokenError(f"token scope {payload.get('scope')} does not allow {action!r}")
    sid = payload.get("sid", "*")
    if step_id is not None and sid != "*" and sid != step_id:
        raise TokenError(f"token is bound to step {sid!r}, not {step_id!r}")
    if not isinstance(payload.get("jti"), str) or len(payload["jti"]) < 16:
        raise TokenError("missing jti")
    return payload


class TokenRegistry:
    """Single-use enforcement + global revocation. Thread-safe (the runner server is threaded)."""

    def __init__(self, key: bytes, task_id: str):
        self.key = key
        self.task_id = task_id
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self.revoked = False
        self.revoked_at: float | None = None

    def consume(self, token: str, *, action: str, step_id: str | None = None, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        with self._lock:
            if self.revoked:
                raise TokenError("all tokens revoked (kill switch)")
            payload = verify_token(self.key, token, task_id=self.task_id, action=action, step_id=step_id, now=now)
            jti = payload["jti"]
            if jti in self._seen:
                raise TokenError("token already used (replay)")
            self._seen[jti] = float(payload["exp"])
            # garbage-collect expired jtis
            for old, exp in list(self._seen.items()):
                if exp < now - 3600:
                    del self._seen[old]
            return payload

    def revoke_all(self, now: float | None = None) -> None:
        with self._lock:
            self.revoked = True
            self.revoked_at = time.time() if now is None else now
