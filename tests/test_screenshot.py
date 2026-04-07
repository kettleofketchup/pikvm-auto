"""Tests for the screenshot command module."""

from __future__ import annotations

from unittest.mock import MagicMock

from pikvm_auto._internal.commands.screenshot import ScreenMatch


def _mock_pikvm() -> MagicMock:
    """Mock PiKVM matching ScreenshotClient's expected attribute surface."""
    pk = MagicMock()
    pk.hostname = "pikvm.local"
    pk.schema = "https"
    pk.headers = {"X-KVMD-User": "admin", "X-KVMD-Passwd": "admin"}
    pk.certificate_trusted = False
    return pk


def test_screen_match_dataclass() -> None:
    """ScreenMatch dataclass shape."""
    m = ScreenMatch(
        matched=True,
        score=0.92,
        expected="Boot Menu",
        ocr_text="Press F11 for Boot Menu",
        elapsed=2.3,
        captures=[],
    )
    assert m.matched is True
    assert m.score == 0.92
