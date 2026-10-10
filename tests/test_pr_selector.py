import pytest
from bat_agent_connector.config import GitHubConfig, GitHubRepo
from bat_agent_connector.github import GitHubClient
from bat_agent_connector.task_daemon import TaskDaemon
from bat_agent_connector.api_v1 import ApiV1
from tests.conftest import make_config

@pytest.fixture
def fake_github(monkeypatch):
    class FakeGitHubClient(GitHubClient):
        def __init__(self):
            super().__init__(GitHubConfig(api_url="http://fake", token_ref="env:FAKE",
                                        repos={"owner/repo": GitHubRepo(repository="owner/repo", integrate=True)}), token="fixed")
        async def call(self, method, path, body=None, query=None):
            if path == "/repos/owner/repo/pulls" and method == "GET":
                if query.get("state") == "open":
                    return 200, {"items": [{"number": 1, "title": "First PR", "state": "open", "draft": False}]}
                elif query.get("state") == "closed":
                    return 200, {"items": [{"number": 2, "title": "Closed PR", "state": "closed", "draft": False}]}
                return 200, {"items": []}
            return 404, {"message": "Not Found"}
    return FakeGitHubClient()

@pytest.fixture
def daemon(mock, tmp_path):
    d = TaskDaemon(make_config(mock, writes=True, orchestrate=True, managed_roots=["/srv"],
                               safety={"write_min_interval_s": 0}), tmp_path / "tasks.db")
    yield d
    d.journal.close()

@pytest.mark.asyncio
async def test_pr_selector_api(daemon, fake_github):
    api = ApiV1(daemon)
    daemon.ops.context["github"] = fake_github
    daemon.ops.context["github_config"] = fake_github.cfg
    
    # Test open PRs
    status, res = await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["1"]})
    assert status == 200
    assert len(res["pulls"]) == 1
    assert res["pulls"][0]["number"] == 1
    
    # Test closed PRs
    status, res = await api.pulls_list("owner", "repo", {"state": ["closed"], "page": ["1"]})
    assert status == 200
    assert len(res["pulls"]) == 1
    assert res["pulls"][0]["number"] == 2

    # Test unknown repo
    from bat_agent_connector.operations import OperationError
    try:
        await api.pulls_list("other", "repo", {"state": ["open"], "page": ["1"]})
        assert False, "Should have raised OperationError"
    except OperationError as e:
        assert e.code == "INVALID_PARAMS"
