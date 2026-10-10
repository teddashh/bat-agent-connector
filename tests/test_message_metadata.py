"""Preserve message-local facts without inventing them from session state."""
from bat_agent_connector.summarize import summarize_message


def test_message_metadata_is_local_optional_and_validated():
    assert summarize_message({"id": "old", "role": "assistant", "content": "Original"},
                             include_tools=True, max_chars=1000) == {
        "id": "old", "role": "assistant", "ts": None, "text": "Original"}
    raw = {"id": "m", "role": "assistant", "content": "Original", "model": "exact:old", "agent": "codex", "durationMs": 1234, "status": "failed"}
    result = summarize_message(raw, include_tools=True, max_chars=1000)
    assert result["status"] == "failed"
    assert result["model"] == "exact:old" and result["agent"] == "codex" and result["duration_ms"] == 1234
    for value in [float("inf"), float("nan"), -1, True, "100"]:
        assert "duration_ms" not in summarize_message({**raw, "durationMs": value}, include_tools=True, max_chars=1000)
    assert "model" not in summarize_message({**raw, "model": {"value": "not a model"}}, include_tools=True, max_chars=1000)


def test_tool_error_result_and_denial_survive_bounded_input_with_real_elapsed_time():
    raw = {"id": "tool", "toolName": "Bash", "input": {"command": "x" * 5000}, "result": "ERROR: original failure",
           "status": "error", "denied": True, "denyReason": "Permission denied", "isDeferred": False,
           "timestamp": 1791580000000, "completedAt": 1791580001200}
    result = summarize_message(raw, include_tools=True, max_chars=1000)
    assert "ERROR: original failure" in result["text"] and "Permission denied" in result["text"]
    assert result["duration_ms"] == 1200 and result["denied"] is True and result["deferred"] is False
    assert result["completed_at"] and len(result["text"]) <= 1000
    assert summarize_message(raw, include_tools=False, max_chars=1000) is None
    result = summarize_message({**raw, "completedAt": 1791579999999}, include_tools=True, max_chars=1000)
    assert "duration_ms" not in result
