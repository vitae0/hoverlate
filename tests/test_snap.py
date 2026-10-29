from pathlib import Path

import pytest

from hoverlate.snap import request_path, screenshot_file


def test_portal_request_path():
    assert request_path(":1.23", "hoverlate_ab12") == (
        "/org/freedesktop/portal/desktop/request/1_23/hoverlate_ab12"
    )


def test_reject_invalid_request_token():
    with pytest.raises(ValueError):
        request_path(":1.23", "not-allowed!")


def test_reject_nonfile_uri():
    with pytest.raises(ValueError):
        screenshot_file("https://example.org/screen.png")


def test_reject_remote_file_uri():
    with pytest.raises(ValueError):
        screenshot_file("file://example.org/screen.png")


def test_local_file_uri(tmp_path: Path):
    file = tmp_path / "a b.png"
    file.write_bytes(b"png")
    assert screenshot_file(file.as_uri()) == file


def test_missing_file_uri(tmp_path: Path):
    with pytest.raises(ValueError):
        screenshot_file((tmp_path / "no.png").as_uri())
