"""CLI maintenance smoke tests, independent of desktop services."""
import pytest

from hoverlate import __version__
from hoverlate.app import main as app_main
from hoverlate.live import main as live_main


def test_live_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        live_main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"Hoverlate {__version__}"


@pytest.mark.parametrize("session", ["x11", "wayland"])
def test_version_flag_does_not_open_a_screen_share(monkeypatch, capsys, session):
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    with pytest.raises(SystemExit) as exc:
        app_main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"Hoverlate {__version__}"
