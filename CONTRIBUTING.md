# Contributing

Thanks for helping! This is an unofficial companion to Better Agent Terminal; please keep it small and safe.

* Open an issue before large changes, especially anything that adds a protocol channel.
* New channels must be classified (read / write / orchestrate / never) in `channels.py`, with a test proving they are
  blocked when their tier is off. Destructive channels (stop/reset/kill, file ops, settings, installs, account changes)
  are not accepted.
* Every write-capable tool needs `confirm=true`, rate limiting, and an audit record without message bodies.
* Tests: `uv run ruff check . && uv run pytest`. Unit tests must run against the mock server in `tests/mockbat.py`.
  Never write tests that send write channels to real hosts.
* Never commit real hostnames, IPs, fingerprints, tokens, session ids, workspace names or emails. CI runs a secret
  scan; please also run `gitleaks detect` locally.
* Protocol behaviour should cite the BAT source file/version it was read from.
