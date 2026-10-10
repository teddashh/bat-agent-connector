import pytest

from bat_agent_connector.api_v1 import ApiV1
from bat_agent_connector.config import GitHubConfig, GitHubRepo
from bat_agent_connector.github import GitHubAmbiguous, GitHubClient
from bat_agent_connector.operations import OperationError
from bat_agent_connector.task_daemon import TaskDaemon
from tests.conftest import make_config


class FakeGitHubClient(GitHubClient):
    def __init__(self):
        super().__init__(GitHubConfig(api_url="http://fake", token_ref="env:FAKE",
                                    repos={"owner/repo": GitHubRepo(repository="owner/repo", integrate=True)}), token="fixed")
        self.call_count = 0

    async def pulls(self, repository: str, *, page: int = 1, state: str = "open", sort: str | None = None, direction: str | None = None):
        if repository != "owner/repo":
            return 404, {"message": "Not Found"}
        self.call_count += 1

        if self.call_count == 999: # For providererror test
            raise GitHubAmbiguous("Simulated error")

        if self.call_count == 998: # For providererror test 2
            return 500, {"message": "Server Error"}

        if page == 1:
            return 200, {"items": [{"number": 1, "title": "First PR", "state": "open", "draft": False}], "_link": '<http://fake/repos/owner/repo/pulls?page=2>; rel="next"'}
        elif page == 2:
            return 200, {"items": [{"number": 2, "title": "Second PR", "state": "open", "draft": False}], "_link": '<http://fake/repos/owner/repo/pulls?page=1>; rel="prev"'}
        return 200, {"items": []}

@pytest.fixture
def fake_github():
    return FakeGitHubClient()

@pytest.fixture
def daemon(mock, tmp_path):
    d = TaskDaemon(make_config(mock, writes=True, orchestrate=True, managed_roots=["/srv"],
                               safety={"write_min_interval_s": 0}), tmp_path / "tasks.db")
    yield d
    d.journal.close()

@pytest.mark.asyncio
async def test_pr_selector_api_valid(daemon, fake_github):
    api = ApiV1(daemon)
    daemon.ops.context["github"] = fake_github
    daemon.ops.context["github_config"] = fake_github.cfg

    status, res = await api.pulls_list("OwNeR", "rEpO", {"state": ["open"], "page": ["1"]})
    assert status == 200
    assert len(res["pulls"]) == 1
    assert res["pulls"][0]["number"] == 1
    assert res["has_more"] is True
    assert res["next_page"] == 2
    assert res["loaded_scope"] == "owner/repo" # Normalized repo case

    status, res = await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["2"]})
    assert status == 200
    assert len(res["pulls"]) == 1
    assert res["pulls"][0]["number"] == 2
    assert res["has_more"] is False
    assert res["next_page"] is None

@pytest.mark.asyncio
async def test_pr_selector_api_invalid_input(daemon, fake_github):
    api = ApiV1(daemon)
    daemon.ops.context["github"] = fake_github
    daemon.ops.context["github_config"] = fake_github.cfg

    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["invalid"], "page": ["1"]})
    assert exc_info.value.code == "INVALID_PARAMS"

    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["0"]})
    assert exc_info.value.code == "INVALID_PARAMS"

    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["1001"]})
    assert exc_info.value.code == "INVALID_PARAMS"

    from bat_agent_connector.api_v1 import ApiError
    with pytest.raises(ApiError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["abc"]})
    assert exc_info.value.code == "INVALID_REQUEST"

@pytest.mark.asyncio
async def test_pr_selector_api_scope_unconfigured(daemon, fake_github):
    api = ApiV1(daemon)
    daemon.ops.context["github"] = fake_github
    daemon.ops.context["github_config"] = fake_github.cfg

    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("other", "repo", {"state": ["open"], "page": ["1"]})
    assert exc_info.value.code == "INVALID_PARAMS"

@pytest.mark.asyncio
async def test_pr_selector_api_provider_error(daemon, fake_github):
    api = ApiV1(daemon)
    daemon.ops.context["github"] = fake_github
    daemon.ops.context["github_config"] = fake_github.cfg

    fake_github.call_count = 998
    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["1"]})
    assert exc_info.value.code == "GITHUB_ERROR"

    fake_github.call_count = 997
    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["1"]})
    assert exc_info.value.code == "GITHUB_ERROR"

@pytest.mark.asyncio
async def test_pr_selector_api_github_unconfigured(daemon):
    api = ApiV1(daemon)
    # No github in context
    with pytest.raises(OperationError) as exc_info:
        await api.pulls_list("owner", "repo", {"state": ["open"], "page": ["1"]})
    assert exc_info.value.code == "NOT_CONFIGURED"

