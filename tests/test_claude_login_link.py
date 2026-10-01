from bat_agent_connector.goose_acp import _link_claude_login


def test_links_only_login_files(tmp_path, monkeypatch):
    home = tmp_path / "op"
    (home / ".claude").mkdir(parents=True)
    creds = home / ".claude" / ".credentials.json"
    creds.write_text("secret")
    account = home / ".claude.json"
    account.write_text("{}")
    (home / "notes.txt").write_text("nope")
    monkeypatch.setenv("HOME", str(home))
    iso = tmp_path / "iso"
    iso.mkdir()
    _link_claude_login(str(iso))
    assert (iso / ".claude" / ".credentials.json").is_symlink()
    assert (iso / ".claude" / ".credentials.json").resolve() == creds.resolve()
    assert (iso / ".claude.json").resolve() == account.resolve()
    assert not (iso / "notes.txt").exists()


def test_missing_login_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "empty"))
    iso = tmp_path / "iso"
    iso.mkdir()
    _link_claude_login(str(iso))
    assert list(iso.iterdir()) == []
