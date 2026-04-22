from unittest.mock import patch
from claude_hub.cli.main import build_parser, main


def test_parser_has_expected_subcommands():
    parser = build_parser()
    subparsers = [a for a in parser._actions if a.dest == "command"][0]
    choices = set(subparsers.choices.keys())
    assert choices == {"install", "uninstall", "status", "logs", "doctor"}


def test_main_returns_zero_on_help():
    import pytest
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_main_dispatches_to_install_handler():
    with patch("claude_hub.cli.install.run") as mock_run:
        mock_run.return_value = 0
        rc = main(["install", "--no-interactive", "--hub-only"])
    mock_run.assert_called_once()
    assert rc == 0
