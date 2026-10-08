"""A small fake of the GitHub REST endpoints delivery.py uses (API version 2026-03-10 shapes)."""

from __future__ import annotations

import json
import re
import subprocess
import threading
import uuid as uuidlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "ghp_fake_" + "x" * 30  # gitleaks:allow (fake test token)


class FakeGitHub:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []
        self.pulls: dict[int, dict] = {}
        self.merge_requests: dict[str, dict] = {}
        self.check_runs: dict[str, list[dict]] = {}
        self.runs: dict[int, dict] = {}
        self.jobs: dict[int, list[dict]] = {}
        self.next_run_id = 9000
        # number -> path of a bare repository: the PR head follows that branch, as on GitHub after a push
        self.pr_remotes: dict[int, str] = {}
        # behaviour switches
        self.merge_mode = "async"  # async | enqueue | fail_500 | fail_500_but_merged | conflict_409_same | conflict_409_other
        self.dispatch_mode = "run_id"  # run_id | no_content | fail_500_but_started
        self.result_status = "merged"  # what GET merge-async/{uuid} reports first
        self.token = TOKEN  # the token GitHub currently accepts (rotate it to expire the connector's copy)
        # one-off answers, each used once by the first matching request: (method, path regex, status, headers, body)
        self.script: list[tuple[str, str, int, dict, dict]] = []
        # (method, path regex): handle the request normally, then cut the reply body short, once
        self.truncate: list[tuple[str, str]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def add_pr(self, number: int, head: str, *, head_ref: str | None = None, fork: bool = False, repo_id: int = 4242,
               **fields) -> dict:
        repo = {"id": repo_id, "full_name": "o/r", "default_branch": "main"}
        head_repo = {"id": repo_id + 1, "full_name": "someone/r"} if fork else {"id": repo_id, "full_name": "o/r"}
        pr = {"number": number, "state": "open", "draft": False, "merged": False, "merge_commit_sha": None,
              "mergeable": True, "mergeable_state": "clean", "title": f"PR {number}",
              "head": {"sha": head, "ref": head_ref or f"feature-{number}", "repo": head_repo},
              "base": {"sha": "b" * 40, "ref": "main", "repo": repo},
              "html_url": f"https://github.example/o/r/pull/{number}", **fields}
        self.pulls[number] = pr
        return pr

    def track_remote(self, number: int, bare_repo: str) -> None:
        """Make PR ``number``'s head follow its head ref in a local bare repository (a stand-in for the remote)."""
        self.pr_remotes[number] = bare_repo

    def _live_head(self, pr: dict) -> None:
        bare = self.pr_remotes.get(pr["number"])
        if bare:
            out = subprocess.run(["git", "-C", bare, "rev-parse", "--verify", "-q", "refs/heads/" + pr["head"]["ref"]],
                                 capture_output=True, text=True).stdout.strip()
            if out:
                pr["head"]["sha"] = out

    def merge(self, number: int, sha: str = "9" * 40) -> None:
        self.pulls[number].update(merged=True, state="closed", merge_commit_sha=sha)

    def add_run(self, *, head_sha: str = "c" * 40, title: str = "deploy", status: str = "in_progress",
                conclusion: str | None = None, event: str = "workflow_dispatch", job_conclusion: str | None = None):
        rid = self.next_run_id
        self.next_run_id += 1
        self.runs[rid] = {"id": rid, "head_sha": head_sha, "display_title": title, "name": "Deploy",
                          "status": status, "conclusion": conclusion, "event": event, "run_attempt": 1,
                          "html_url": f"https://github.example/o/r/actions/runs/{rid}"}
        self.jobs[rid] = [{"name": "build", "conclusion": "success"},
                          {"name": "deploy", "conclusion": job_conclusion}]
        return self.runs[rid]

    def count(self, method: str, pattern: str) -> int:
        return sum(1 for m, p, _ in self.requests if m == method and re.search(pattern, p))

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, status: int, body: dict | None = None, headers: dict | None = None) -> None:
                raw = json.dumps(body).encode() if body is not None else b""
                length = len(raw)
                for i, (m, pattern) in enumerate(fake.truncate):
                    if m == self.command and re.search(pattern, self.path):
                        del fake.truncate[i]
                        length += 50  # promise more than is sent: the client sees IncompleteRead
                        break
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(length))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

            def _route(self, method: str) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                path = self.path.split("?", 1)[0]
                query = dict(p.split("=", 1) for p in self.path.split("?", 1)[1].split("&")) if "?" in self.path else {}
                fake.requests.append((method, self.path, body))
                for i, (m, pattern, status, headers, answer) in enumerate(fake.script):
                    if m == method and re.search(pattern, path):
                        del fake.script[i]
                        return self._send(status, answer, headers)
                if self.headers.get("Authorization") != "Bearer " + fake.token:
                    return self._send(401, {"message": "Bad credentials"})
                if self.headers.get("X-GitHub-Api-Version") != "2026-03-10":
                    return self._send(400, {"message": "unsupported API version"})
                m = re.fullmatch(r"/repos/o/r/pulls/(\d+)", path)
                if m and method == "GET":
                    pr = fake.pulls.get(int(m.group(1)))
                    if pr:
                        fake._live_head(pr)
                    return self._send(200, pr) if pr else self._send(404, {"message": "Not Found"})
                m = re.fullmatch(r"/repos/o/r/commits/([0-9a-f]{40})", path)
                if m and method == "GET":  # a commit exists when any tracked bare remote has the object
                    for bare in fake.pr_remotes.values():
                        if subprocess.run(["git", "-C", bare, "cat-file", "-e", m.group(1) + "^{commit}"],
                                          capture_output=True).returncode == 0:
                            return self._send(200, {"sha": m.group(1)})
                    return self._send(422, {"message": "No commit found for SHA: " + m.group(1)})
                m = re.fullmatch(r"/repos/o/r/pulls/(\d+)/merge-async", path)
                if m and method == "PUT":
                    return self._merge_async(int(m.group(1)), body or {})
                m = re.fullmatch(r"/repos/o/r/pulls/(\d+)/merge-async/([0-9a-f-]+)", path)
                if m and method == "GET":
                    req = fake.merge_requests.get(m.group(2))
                    if not req:
                        return self._send(404, {"message": "Not Found"})
                    if fake.result_status == "merged":
                        fake.merge(int(m.group(1)))
                        return self._send(200, {"status": "merged", "details": {"message": "ok", "sha": "9" * 40}})
                    if fake.result_status == "failed":
                        return self._send(200, {"status": "failed", "details": {"message": "required review missing"}})
                    return self._send(200, {"status": "pending", "details": req})
                m = re.fullmatch(r"/repos/o/r/commits/([0-9a-f]+)/check-runs", path)
                if m and method == "GET":
                    return self._send(200, {"check_runs": fake.check_runs.get(m.group(1), [])})
                m = re.fullmatch(r"/repos/o/r/actions/workflows/([^/]+)/dispatches", path)
                if m and method == "POST":
                    return self._dispatch(body or {})
                m = re.fullmatch(r"/repos/o/r/actions/workflows/([^/]+)/runs", path)
                if m and method == "GET":
                    runs = [r for r in fake.runs.values()
                            if (not query.get("head_sha") or r["head_sha"] == query["head_sha"])
                            and (not query.get("event") or r["event"] == query["event"])]
                    return self._send(200, {"total_count": len(runs), "workflow_runs": runs})
                m = re.fullmatch(r"/repos/o/r/actions/runs/(\d+)", path)
                if m and method == "GET":
                    run = fake.runs.get(int(m.group(1)))
                    return self._send(200, run) if run else self._send(404, {"message": "Not Found"})
                m = re.fullmatch(r"/repos/o/r/actions/runs/(\d+)/jobs", path)
                if m and method == "GET":
                    return self._send(200, {"jobs": fake.jobs.get(int(m.group(1)), [])})
                return self._send(404, {"message": "no route " + path})

            def _merge_async(self, number: int, body: dict) -> None:
                pr = fake.pulls[number]
                if pr["merged"]:
                    return self._send(200, {"status": "merged", "details": {"message": "ok",
                                                                            "sha": pr["merge_commit_sha"]}})
                mode = fake.merge_mode
                if mode == "fail_500":
                    fake.merge_mode = "async"
                    return self._send(502, {"message": "Bad Gateway"})
                if mode == "fail_500_but_merged":
                    fake.merge_mode = "async"
                    fake.merge(number)
                    return self._send(502, {"message": "Bad Gateway"})
                if mode == "enqueue":
                    return self._send(200, {"status": "enqueued", "details": {"message": "added to queue"}})
                if mode.startswith("conflict_409"):
                    sha = body.get("sha") if mode == "conflict_409_same" else "f" * 40
                    req = {"message": "pending", "uuid": "11111111-2222-3333-4444-555555555555",
                           "merge_method": body.get("merge_method"), "merge_action": "default",
                           "expected_head_sha": sha}
                    fake.merge_requests[req["uuid"]] = req
                    return self._send(409, {"status": "pending", "details": req})
                if pr["state"] != "open" or pr["draft"]:
                    return self._send(400, {"status": "failed", "details": {"message": "not mergeable"}})
                uid = str(uuidlib.uuid4())
                req = {"message": "accepted", "uuid": uid, "merge_method": body.get("merge_method"),
                       "merge_action": body.get("merge_action"), "expected_head_sha": body.get("sha")}
                fake.merge_requests[uid] = req
                return self._send(202, {"status": "pending", "details": req})

            def _dispatch(self, body: dict) -> None:
                inputs = body.get("inputs") or {}
                title = "deploy " + str(inputs.get("operation_id", ""))
                run = fake.add_run(head_sha="d" * 40, title=title)
                if fake.dispatch_mode == "fail_500_but_started":
                    fake.dispatch_mode = "run_id"
                    return self._send(502, {"message": "Bad Gateway"})
                if fake.dispatch_mode == "no_content":
                    return self._send(204)
                return self._send(200, {"workflow_run_id": run["id"], "run_url": "x", "html_url": run["html_url"]})

            def do_GET(self):
                self._route("GET")

            def do_PUT(self):
                self._route("PUT")

            def do_POST(self):
                self._route("POST")

        return Handler
