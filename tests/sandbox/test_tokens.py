from __future__ import annotations

import pytest
from brz_runner.tokens import TokenError, TokenRegistry, key_fingerprint, new_key, sign_token, verify_token

KEY = new_key()
T0 = 1_800_000_000.0


def test_sign_and_verify_roundtrip():
    tok = sign_token(KEY, task_id="t1", scope=["exec"], step_id="s1", ttl_s=60, now=T0)
    payload = verify_token(KEY, tok, task_id="t1", action="exec", step_id="s1", now=T0 + 10)
    assert payload["tid"] == "t1" and payload["sid"] == "s1" and payload["scope"] == ["exec"]
    assert payload["exp"] == int(T0) + 60 and len(payload["jti"]) == 32
    assert len(key_fingerprint(KEY)) == 16


def test_expired_and_future_tokens_rejected():
    tok = sign_token(KEY, task_id="t1", scope=["exec"], ttl_s=60, now=T0)
    with pytest.raises(TokenError, match="expired"):
        verify_token(KEY, tok, task_id="t1", action="exec", now=T0 + 60)
    future = sign_token(KEY, task_id="t1", scope=["exec"], ttl_s=60, now=T0 + 3600)
    with pytest.raises(TokenError, match="future"):
        verify_token(KEY, future, task_id="t1", action="exec", now=T0)


def test_scope_task_and_step_binding():
    tok = sign_token(KEY, task_id="t1", scope=["exec"], step_id="s1", now=T0)
    with pytest.raises(TokenError, match="scope"):
        verify_token(KEY, tok, task_id="t1", action="revoke", now=T0)
    with pytest.raises(TokenError, match="different task"):
        verify_token(KEY, tok, task_id="t2", action="exec", now=T0)
    with pytest.raises(TokenError, match="bound to step"):
        verify_token(KEY, tok, task_id="t1", action="exec", step_id="s2", now=T0)
    wildcard = sign_token(KEY, task_id="t1", scope=["exec", "scan"], step_id="*", now=T0)
    assert verify_token(KEY, wildcard, task_id="t1", action="exec", step_id="s9", now=T0)["sid"] == "*"


def test_tampering_and_wrong_key():
    tok = sign_token(KEY, task_id="t1", scope=["exec"], now=T0)
    with pytest.raises(TokenError, match="bad signature"):
        verify_token(new_key(), tok, task_id="t1", action="exec", now=T0)
    head, sig = tok.split(".")
    flipped = ("A" if head[0] != "A" else "B") + head[1:]
    with pytest.raises(TokenError, match="bad signature"):
        verify_token(KEY, f"{flipped}.{sig}", task_id="t1", action="exec", now=T0)
    with pytest.raises(TokenError, match="malformed"):
        verify_token(KEY, "garbage", task_id="t1", action="exec", now=T0)
    with pytest.raises(TokenError, match="malformed"):
        verify_token(KEY, "not-base64!!.sig", task_id="t1", action="exec", now=T0)


def test_registry_single_use_and_revocation():
    reg = TokenRegistry(KEY, "t1")
    tok = sign_token(KEY, task_id="t1", scope=["exec"], step_id="s1", now=T0)
    assert reg.consume(tok, action="exec", step_id="s1", now=T0)["sid"] == "s1"
    with pytest.raises(TokenError, match="already used"):
        reg.consume(tok, action="exec", step_id="s1", now=T0 + 1)
    fresh = sign_token(KEY, task_id="t1", scope=["exec"], step_id="s1", now=T0)
    reg.revoke_all(now=T0 + 2)
    assert reg.revoked and reg.revoked_at == T0 + 2
    with pytest.raises(TokenError, match="revoked"):
        reg.consume(fresh, action="exec", step_id="s1", now=T0 + 3)


def test_registry_garbage_collects_old_jtis():
    reg = TokenRegistry(KEY, "t1")
    old = sign_token(KEY, task_id="t1", scope=["exec"], ttl_s=10, now=T0)
    reg.consume(old, action="exec", now=T0)
    assert len(reg._seen) == 1
    later = sign_token(KEY, task_id="t1", scope=["exec"], ttl_s=10, now=T0 + 7200)
    reg.consume(later, action="exec", now=T0 + 7200)
    assert len(reg._seen) == 1  # the old jti (expired > 1h ago) was dropped
