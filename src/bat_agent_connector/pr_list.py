from .errors import ResourceReadOnly
from .operations import OperationError

async def list_pulls(ops, repository: str, state: str, page: int):
    github = ops.context.get("github")
    if not github:
        raise OperationError("NOT_CONFIGURED", "GitHub is not configured", 422)
    gh_cfg = ops.context["github_config"]
    if repository not in gh_cfg.repos:
        raise OperationError("INVALID_PARAMS", f"Repository {repository} is not explicitly configured", 422)
    
    from .github import GitHubAmbiguous
    try:
        status, data = await github.pulls(repository, page=page, state=state, sort="updated", direction="desc")
        if status != 200:
            raise OperationError("GITHUB_ERROR", f"GitHub answered {status}", 502)
        return {"pulls": data.get("items", [])}
    except GitHubAmbiguous as e:
        raise OperationError("GITHUB_ERROR", str(e), 502)
