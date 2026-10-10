from .operations import OperationError


async def list_pulls(ops, repository: str, state: str, page: int):
    if state not in ("open", "closed", "all"):
        raise OperationError("INVALID_PARAMS", f"Invalid state: {state}", 422)

    try:
        page = int(page)
    except ValueError:
        raise OperationError("INVALID_PARAMS", f"Invalid page: {page}", 422) from None
    if not (1 <= page <= 1000):
        raise OperationError("INVALID_PARAMS", f"Page out of bounds: {page}", 422)

    github = ops.context.get("github")
    if not github:
        raise OperationError("NOT_CONFIGURED", "GitHub is not configured", 422)
    gh_cfg = ops.context["github_config"]

    # Normalize repository case
    repo_lower = repository.lower()
    matched_repo = None
    for r in gh_cfg.repos:
        if r.lower() == repo_lower:
            matched_repo = r
            break

    if not matched_repo:
        raise OperationError("INVALID_PARAMS", f"Repository {repository} is not explicitly configured", 422)

    from .github import GitHubAmbiguous
    try:
        status, data = await github.pulls(matched_repo, page=page, state=state, sort="updated", direction="desc")
        if status != 200:
            raise OperationError("GITHUB_ERROR", f"GitHub answered {status}", 502)

        has_more = False
        if "_link" in data:
            has_more = 'rel="next"' in data["_link"]

        return {
            "pulls": data.get("items", []),
            "has_more": has_more,
            "next_page": page + 1 if has_more else None,
            "loaded_scope": matched_repo
        }
    except GitHubAmbiguous as e:
        raise OperationError("GITHUB_ERROR", str(e), 502) from e
