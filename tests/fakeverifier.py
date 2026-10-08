"""Runtime evidence independent of the workflow head SHA."""
class FakeVerifier:
    def __init__(self, github):
        self.github = github
        self.response = None
        self.calls = 0

    async def __call__(self, settings):
        self.calls += 1
        return dict(self.response) if self.response is not None else {
            "repository_id": self.github.repository_id, "environment": "production",
            "source_sha": self.github.deployed_source, "healthy": True}
