"""Bedrock caller — unit test dengan transport boto3 di-stub.

Kontrak:
- converse(modelId, messages, inferenceConfig) → teks gabungan content text
- error AWS dibungkus BedrockInvocationError dengan status_code bila ada
  (429/5xx nanti diklasifikasi chain; AccessDenied = auth, bukan retry)
- boto3 tidak terpasang → RuntimeError eksplisit (jujur), bukan crash import
"""

import sys
import types

import pytest

from app.ai_providers.bedrock_caller import (
    BedrockInvocationError,
    run_text,
)


class _FakeClientError(Exception):
    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}


def _install_fake_boto3(monkeypatch, *, respond=None, raise_exc=None):
    """Pasang modul boto3/botocore palsu di sys.modules + client pencatat."""
    assert monkeypatch is not None
    calls = {}

    class _FakeConverse:
        def __init__(self):
            self.received = None

        def __call__(self, **kwargs):
            calls.update(kwargs)
            if raise_exc is not None:
                raise raise_exc
            return respond

    converse = _FakeConverse()

    class _FakeClient:
        def __init__(self, service, region_name=None, config=None):
            calls["service"] = service
            calls["region"] = region_name
            self.converse = converse

    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = _FakeClient
    fake_botocore = types.ModuleType("botocore")
    fake_botocore_config = types.ModuleType("botocore.config")
    fake_botocore_config.Config = lambda **kw: {"kw": kw}
    fake_botocore.exceptions = types.ModuleType("botocore.exceptions")
    fake_botocore.exceptions.ClientError = _FakeClientError
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", fake_botocore_config)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore.exceptions)
    return calls, converse


def _converse_response(text: str) -> dict:
    return {"output": {"message": {"content": [{"text": text}]}}}


def test_converse_returns_text_and_sends_json_prompt(monkeypatch):
    calls, _ = _install_fake_boto3(
        monkeypatch, respond=_converse_response('{"verdict":"CONSISTENT"}')
    )
    out = run_text("us.anthropic.", 'Konteks: {"a":1}')
    assert out == '{"verdict":"CONSISTENT"}'
    assert calls["service"] == "bedrock-runtime"
    assert calls["modelId"] == "us.anthropic."
    msgs = calls["messages"]
    assert msgs[0]["role"] == "user"
    # prompt dikirim sebagai JSON: {"prompt": <teks>} — tanpa secret
    import json

    sent = json.loads(msgs[0]["content"][0]["text"])
    assert sent["prompt"].startswith("Konteks:")


def test_throttled_error_carries_status_429(monkeypatch):
    err = _FakeClientError("ThrottlingException", 429)
    _install_fake_boto3(monkeypatch, raise_exc=err)
    with pytest.raises(BedrockInvocationError) as excinfo:
        run_text("us.anthropic.", "x")
    assert excinfo.value.status_code == 429


def test_access_denied_carries_status_403(monkeypatch):
    err = _FakeClientError("AccessDeniedException", 403)
    _install_fake_boto3(monkeypatch, raise_exc=err)
    with pytest.raises(BedrockInvocationError) as excinfo:
        run_text("us.anthropic.", "x")
    assert excinfo.value.status_code == 403


def test_plain_error_without_status(monkeypatch):
    _install_fake_boto3(monkeypatch, raise_exc=ValueError("bukan error AWS"))
    with pytest.raises(BedrockInvocationError) as excinfo:
        run_text("us.anthropic.", "x")
    assert excinfo.value.status_code is None


def test_boto3_missing_raises_runtime_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "boto3", None)  # import boto3 → ImportError
    with pytest.raises(RuntimeError):
        run_text("us.anthropic.", "x")
