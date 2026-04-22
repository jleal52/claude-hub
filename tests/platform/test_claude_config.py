import json

from claude_hub.platform.claude_config import ensure_remote_control_consent


def test_creates_file_when_missing(monkeypatch, tmp_path):
    """Regression: fresh Linux installs start with no ~/.claude.json at all.
    The helper must create it rather than raise FileNotFoundError."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows Path.home()

    assert ensure_remote_control_consent("/root") is True

    cfg = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert cfg["remoteDialogSeen"] is True
    assert cfg["projects"]["/root"]["hasTrustDialogAccepted"] is True


def test_preserves_existing_fields(monkeypatch, tmp_path):
    """Must not clobber unrelated fields (credentials, feature flags, etc.)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    existing = {
        "oauthAccount": {"email": "x@y"},
        "projects": {"/other": {"hasTrustDialogAccepted": True, "extra": 1}},
        "unrelated": 42,
    }
    (tmp_path / ".claude.json").write_text(json.dumps(existing), encoding="utf-8")

    ensure_remote_control_consent("/root")

    cfg = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert cfg["oauthAccount"] == {"email": "x@y"}
    assert cfg["unrelated"] == 42
    assert cfg["projects"]["/other"] == {"hasTrustDialogAccepted": True, "extra": 1}
    assert cfg["projects"]["/root"]["hasTrustDialogAccepted"] is True
    assert cfg["remoteDialogSeen"] is True


def test_writes_both_windows_path_variants(monkeypatch, tmp_path):
    """Claude normalizes Windows paths inconsistently between code paths (we
    saw both `C:\\Users\\x` and `C:/Users/x` as keys). Write both so whichever
    form Claude looks up matches."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    ensure_remote_control_consent(r"C:\Users\Usuario")

    cfg = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert cfg["projects"][r"C:\Users\Usuario"]["hasTrustDialogAccepted"] is True
    assert cfg["projects"]["C:/Users/Usuario"]["hasTrustDialogAccepted"] is True


def test_returns_false_on_corrupt_json(monkeypatch, tmp_path):
    """If ~/.claude.json exists but is unparseable (user edit gone wrong),
    do NOT overwrite it — return False so the caller warns, preserving the
    user's file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    corrupt = "{not valid json"
    (tmp_path / ".claude.json").write_text(corrupt, encoding="utf-8")

    assert ensure_remote_control_consent("/root") is False
    # File is untouched.
    assert (tmp_path / ".claude.json").read_text(encoding="utf-8") == corrupt


def test_idempotent(monkeypatch, tmp_path):
    """Reinstall scenario: calling twice produces the same result and doesn't
    accumulate duplicate keys or toggle any state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    ensure_remote_control_consent("/root")
    first = (tmp_path / ".claude.json").read_text(encoding="utf-8")
    ensure_remote_control_consent("/root")
    second = (tmp_path / ".claude.json").read_text(encoding="utf-8")

    assert first == second
