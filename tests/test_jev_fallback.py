"""Both Jev transports keep the same typed judgment and fail-open boundary."""

from __future__ import annotations

import json
from io import BytesIO

import pytest

from bat_agent_connector.config import JevConfig
from bat_agent_connector.jev import OPENROUTER_JEV_MODEL, OPENROUTER_URL, Jev
from bat_agent_connector.model_router import ModelRouter
from bat_agent_connector.task_journal import Journal
from bat_agent_connector.triage import refine_with_jev


def answers_for(questions: dict, choice: str) -> dict:
    answers = {}
    for name, spec in questions.items():
        if spec["type"] == "noul":
            answers[name] = {"type": "noul", "noul": 0.9}
        else:
            criteria = spec["criteria"]
            selected = choice if choice in criteria else next(iter(criteria))
            answers[name] = {"type": "choice", "choice": selected, "confidence": 0.93,
                             "probabilities": {key: float(key == selected) for key in criteria}}
    return answers


def openrouter_reply(body: bytes, choice: str) -> dict:
    request = json.loads(body)
    questions = json.loads(request["messages"][1]["content"])["questions"]
    return {"choices": [{"message": {"content": json.dumps({"answers": answers_for(questions, choice)})}}]}


def test_openrouter_transport_uses_fixed_endpoint_and_env_key(monkeypatch):
    jev = Jev(JevConfig())
    payload = json.dumps({"model": OPENROUTER_JEV_MODEL, "messages": []}).encode()

    def urlopen(request, timeout):
        assert request.full_url == OPENROUTER_URL
        assert request.get_header("Authorization") == "Bearer fake-test-key"
        assert json.loads(request.data)["model"] == OPENROUTER_JEV_MODEL
        assert timeout == jev.cfg.timeout_s
        return BytesIO(b'{"choices":[]}')

    monkeypatch.setattr("bat_agent_connector.jev.urllib.request.urlopen", urlopen)
    assert jev._post_openrouter(payload, "fake-test-key") == {"choices": []}


@pytest.mark.asyncio
async def test_jev_primary_success_does_not_call_openrouter(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-primary-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    jev = Jev(JevConfig())
    calls = []

    def primary(body, key):
        calls.append("typesafe")
        assert key == "fake-primary-key"
        return {"answers": answers_for(json.loads(body)["questions"], "quota_exhausted")}

    monkeypatch.setattr(jev, "_post", primary)
    monkeypatch.setattr(jev, "_post_openrouter", lambda *_: pytest.fail("unexpected fallback"))
    result = await jev.classify_state("synthetic quota message")
    assert result["state"] == "quota_exhausted" and result["jev_backend"] == "typesafe"
    assert jev.backend == "typesafe" and calls == ["typesafe"]


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_result", ["timeout", "invalid"])
async def test_jev_primary_failure_uses_openrouter_judgment(monkeypatch, primary_result, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-primary-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    jev = Jev(JevConfig())
    models = []

    def primary(_body, _key):
        if primary_result == "timeout":
            raise TimeoutError("synthetic timeout")
        return {"answers": {"step_type": {"type": "choice", "choice": "forged"}}}

    def fallback(body, key):
        assert key == "fake-fallback-key"
        model = json.loads(body)["model"]
        models.append(model)
        return openrouter_reply(body, "planning")

    monkeypatch.setattr(jev, "_post", primary)
    monkeypatch.setattr(jev, "_post_openrouter", fallback)
    journal = Journal(tmp_path / "tasks.db")
    task = journal.submit(project="p", host="h1", workspace="w", original_words="synthetic task",
                          idempotency_key=primary_result)
    try:
        route = await ModelRouter(journal, jev).choose(task["task_id"], "plan", "plan code",
                                                      expected_type="planning", high_stakes=True)
        assert route["provider"] == "claude" and route["jev_backend"] == "openrouter_jev"
        assert json.loads(journal.events(task["task_id"])[-1]["body"])["jev_backend"] == "openrouter_jev"
        reopened = Journal(tmp_path / "tasks.db")
        assert reopened.routes(task["task_id"])[0]["jev_backend"] == "openrouter_jev"
        reopened.close()
        assert models == [OPENROUTER_JEV_MODEL]
        gate = await jev.merge_gate("task", "done", "diff --git", "passed")
        assert gate and gate["jev_backend"] == "openrouter_jev"
        await ModelRouter(journal, jev).prescreen(task["task_id"], commit="a" * 40, tree="b" * 40,
                                                   request="task", final_output="done",
                                                   diff_excerpt="diff --git", tests="passed")
        prescreen = next(e for e in journal.events(task["task_id"]) if e["kind"] == "jev_prescreen")
        assert json.loads(prescreen["body"])["jev_backend"] == "openrouter_jev"
        triage = await refine_with_jev(jev, {"state": "error_other", "ambiguous": True,
                                            "source": "pattern"}, [], "always")
        assert triage["source"] == "jev" and triage["jev_backend"] == "openrouter_jev"
    finally:
        journal.close()


@pytest.mark.asyncio
async def test_jev_both_endpoints_fail_open_without_cheap_model(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-primary-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    jev = Jev(JevConfig())
    called = []
    monkeypatch.setattr(jev, "_post", lambda *_: (_ for _ in ()).throw(TimeoutError()))

    def invalid_reply(body, _key):
        called.append(json.loads(body)["model"])
        return {"choices": [{"message": {"content": "{}"}}]}

    monkeypatch.setattr(jev, "_post_openrouter", invalid_reply)
    journal = Journal(tmp_path / "tasks.db")
    task = journal.submit(project="p", host="h1", workspace="w", original_words="synthetic task",
                          idempotency_key="both-fail")
    try:
        route = await ModelRouter(journal, jev).choose(task["task_id"], "review", "review code",
                                                      expected_type="review", high_stakes=True)
        assert route["provider"] == "codex" and route["reason"] == "jev_unavailable"
        assert route["jev_backend"] is None and jev.backend is None
        assert await jev.merge_gate("task", "done", "diff", "passed") is None
        assert called == [OPENROUTER_JEV_MODEL, OPENROUTER_JEV_MODEL]
    finally:
        journal.close()


@pytest.mark.asyncio
async def test_jev_missing_openrouter_key_skips_fallback(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-primary-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    jev = Jev(JevConfig())
    monkeypatch.setattr(jev, "_post", lambda *_: {"answers": {}})
    monkeypatch.setattr(jev, "_post_openrouter", lambda *_: pytest.fail("missing key must skip"))
    assert await jev.classify_state("synthetic") is None
    assert jev.backend is None


@pytest.mark.asyncio
async def test_jev_cheap_model_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    used = []

    def reply(body, _key):
        model = json.loads(body)["model"]
        used.append(model)
        return openrouter_reply(body, "quota_exhausted") if model == "test/cheap-small" else {}

    ordinary = Jev(JevConfig(cheap_model="test/cheap-small"))
    monkeypatch.setattr(ordinary, "_post_openrouter", reply)
    assert ordinary.enabled and await ordinary.classify_state("synthetic") is None
    assert used == [OPENROUTER_JEV_MODEL]
    opted_in = Jev(JevConfig(allow_cheap_model=True, cheap_model="test/cheap-small"))
    monkeypatch.setattr(opted_in, "_post_openrouter", reply)
    result = await opted_in.classify_state("synthetic")
    assert result["state"] == "quota_exhausted" and result["jev_backend"] == "openrouter_cheap"
    assert used[-2:] == [OPENROUTER_JEV_MODEL, "test/cheap-small"]
