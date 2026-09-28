"""Both Jev transports keep the same typed judgment and fail-open boundary."""

from __future__ import annotations

import json
from io import BytesIO

import pytest

from bat_agent_connector.config import JevConfig
from bat_agent_connector.jev import OPENROUTER_JEV_MODEL, OPENROUTER_URL, Jev
from bat_agent_connector.model_router import MinimalReviewGate, ModelRouter, RouterConfig
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


def decisions_reply(body: bytes, choice: str) -> dict:
    request = json.loads(body)
    return {"model": "typesafe/jev-1.13-20260917",
            "answers": answers_for(request["questions"], choice)}


def test_openrouter_transport_uses_decisions_endpoint_and_system_one_shape(monkeypatch):
    jev = Jev(JevConfig())
    payload = json.dumps({"model": OPENROUTER_JEV_MODEL, "state": {"synthetic": True},
                          "questions": {"test": {"type": "noul", "instructions": "Test?"}}}).encode()

    def urlopen(request, timeout):
        assert request.full_url == OPENROUTER_URL
        assert request.get_header("Authorization") == "Bearer fake-test-key"
        assert json.loads(request.data) == json.loads(payload)
        assert set(json.loads(request.data)) == {"model", "state", "questions"}
        assert request.get_method() == "POST"
        assert timeout == jev.cfg.timeout_s
        return BytesIO(b'{"answers":{}}')

    monkeypatch.setattr("bat_agent_connector.jev.urllib.request.urlopen", urlopen)
    assert jev._post_openrouter(payload, "fake-test-key") == {"answers": {}}


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
    primary_payloads = []

    def primary(body, _key):
        primary_payloads.append(json.loads(body))
        if primary_result == "timeout":
            raise TimeoutError("synthetic timeout")
        return {"answers": {"step_type": {"type": "choice", "choice": "forged"}}}

    def fallback(body, key):
        assert key == "fake-fallback-key"
        model = json.loads(body)["model"]
        models.append(model)
        assert set(json.loads(body)) == {"model", "state", "questions"}
        assert {key: value for key, value in json.loads(body).items() if key != "model"} == {
            key: value for key, value in primary_payloads[-1].items() if key != "model"
        }
        return decisions_reply(body, "planning")

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
async def test_jev_both_endpoints_fail_open(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-primary-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    jev = Jev(JevConfig())
    called = []
    monkeypatch.setattr(jev, "_post", lambda *_: (_ for _ in ()).throw(TimeoutError()))

    def invalid_reply(body, _key):
        called.append(json.loads(body)["model"])
        return {"answers": {}}

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
async def test_jev_decisions_invalid_output_never_sets_backend(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    jev = Jev(JevConfig())
    used = []

    def invalid_reply(body, _key):
        used.append(json.loads(body)["model"])
        return {"answers": {"state": {"type": "choice", "choice": "quota_exhausted",
                                      "confidence": 0.9, "probabilities": {"quota_exhausted": 1}}}}

    monkeypatch.setattr(jev, "_post_openrouter", invalid_reply)
    assert jev.enabled and await jev.classify_state("synthetic") is None
    assert jev.backend is None
    assert used == [OPENROUTER_JEV_MODEL]


@pytest.mark.asyncio
async def test_minimal_review_uses_one_typed_question_and_decisions_fallback(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-primary-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fallback-key")
    jev = Jev(JevConfig())
    calls = []

    def primary(body, _key):
        calls.append(("typesafe", json.loads(body)))
        raise TimeoutError("synthetic primary outage")

    def fallback(body, _key):
        request = json.loads(body)
        calls.append(("openrouter_jev", request))
        return {"answers": answers_for(request["questions"], "pass")}

    monkeypatch.setattr(jev, "_post", primary)
    monkeypatch.setattr(jev, "_post_openrouter", fallback)
    result = await MinimalReviewGate(jev, RouterConfig()).judge(
        original_words="Ted's exact request", diff="diff --git a/README.md b/README.md\n+line",
        paths=["README.md"])
    assert result["verdict"] == "pass" and result["jev_backend"] == "openrouter_jev"
    assert [name for name, _ in calls] == ["typesafe", "openrouter_jev"]
    assert len(calls[0][1]["questions"]) == 1
    assert calls[0][1]["state"] == calls[1][1]["state"]
    assert calls[0][1]["questions"] == calls[1][1]["questions"]
    assert calls[1][1]["model"] == "typesafe/jev-1.13"
