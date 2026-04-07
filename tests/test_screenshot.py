"""Tests for the screenshot command module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pikvm_auto._internal.commands.screenshot import (
    ScreenMatch,
    ScreenshotClient,
    fuzzy_score,
)

if TYPE_CHECKING:
    from pathlib import Path


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


def test_fuzzy_score_exact_match() -> None:
    """Exact-substring expected text scores 1.0."""
    assert fuzzy_score("Boot Menu", "Press F11 for Boot Menu") == 1.0


def test_fuzzy_score_one_character_off() -> None:
    """OCR-style single-char drop should still score >= 0.85."""
    score = fuzzy_score("Boot Menu", "Press F11 for Bot Menu")
    assert 0.85 <= score < 1.0


def test_fuzzy_score_no_match() -> None:
    """Unrelated strings score below 0.7."""
    score = fuzzy_score("Loading kernel", "Welcome to BIOS Setup")
    assert score < 0.7


def test_fuzzy_score_case_insensitive_default() -> None:
    """Case is ignored by default."""
    assert fuzzy_score("BOOT MENU", "boot menu") == 1.0


def test_fuzzy_score_case_sensitive() -> None:
    """case_sensitive=True makes case mismatches score below 1.0."""
    assert fuzzy_score("BOOT", "boot", case_sensitive=True) < 1.0


def test_capture_returns_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """capture() returns raw jpeg bytes from /api/streamer/snapshot."""
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> MagicMock:
        captured["url"] = url
        captured.update(kwargs)
        m = MagicMock(status_code=200)
        m.content = b"\xff\xd8\xff\xe0fakejpeg"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    pk = _mock_pikvm()
    data = ScreenshotClient(pk).capture()

    assert data == b"\xff\xd8\xff\xe0fakejpeg"
    assert captured["url"] == "https://pikvm.local/api/streamer/snapshot"
    assert captured["params"] == {}
    assert captured["headers"] == pk.headers
    assert captured["verify"] is False
    assert captured["timeout"] == 30


def test_capture_with_ocr_flag_passes_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """capture(ocr=True) sends ocr=true query param."""
    captured: dict[str, object] = {}

    def fake_get(_url: str, **kwargs: object) -> MagicMock:
        captured.update(kwargs)
        m = MagicMock(status_code=200)
        m.content = b"text bytes"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    ScreenshotClient(_mock_pikvm()).capture(ocr=True)
    assert captured["params"]["ocr"] == "true"


def test_capture_to_writes_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """capture_to() writes the response body to the target path."""

    def fake_get(_url: str, **_kwargs: object) -> MagicMock:
        m = MagicMock(status_code=200)
        m.content = b"jpeg data"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    out = ScreenshotClient(_mock_pikvm()).capture_to(tmp_path / "snap.jpeg")
    assert out == tmp_path / "snap.jpeg"
    assert (tmp_path / "snap.jpeg").read_bytes() == b"jpeg data"


def test_capture_to_creates_parent_dirs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """capture_to() creates missing parent directories."""

    def fake_get(_url: str, **_kwargs: object) -> MagicMock:
        m = MagicMock(status_code=200)
        m.content = b"jpeg data"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    out = ScreenshotClient(_mock_pikvm()).capture_to(
        tmp_path / "nested/dir/snap.jpeg",
    )
    assert out.exists()


def test_capture_text_uses_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """capture_text() requests ocr=true and decodes to str."""
    captured: dict[str, object] = {}

    def fake_get(_url: str, **kwargs: object) -> MagicMock:
        captured.update(kwargs)
        m = MagicMock(status_code=200)
        m.content = b"Press F11 for Boot Menu"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    text = ScreenshotClient(_mock_pikvm()).capture_text()
    assert text == "Press F11 for Boot Menu"
    assert captured["params"]["ocr"] == "true"


def test_wait_for_text_matches_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """wait_for_text() returns matched=True when OCR contains expected."""

    def fake_get(_url: str, **_kwargs: object) -> MagicMock:
        m = MagicMock(status_code=200)
        m.content = b"Press F11 for Boot Menu"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    m = ScreenshotClient(_mock_pikvm()).wait_for_text(
        "Boot Menu",
        timeout=1.0,
        interval=0.1,
    )
    assert m.matched is True
    assert m.score >= 0.9
    assert m.expected == "Boot Menu"
    assert "Boot Menu" in m.ocr_text


def test_wait_for_text_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """wait_for_text() returns matched=False when the threshold never met."""

    def fake_get(_url: str, **_kwargs: object) -> MagicMock:
        m = MagicMock(status_code=200)
        m.content = b"Press F11 for Bot Menu"  # OCR-style typo
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.time.sleep",
        lambda _s: None,
    )

    m = ScreenshotClient(_mock_pikvm()).wait_for_text(
        "Boot Menu",
        threshold=0.99,
        timeout=0.3,
        interval=0.1,
    )
    assert m.matched is False


def test_capture_to_rejects_empty_path() -> None:
    """capture_to() rejects empty path at the boundary."""
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match=r"capture_to.*non-empty path"):
        ScreenshotClient(pk).capture_to("")


def test_wait_for_text_rejects_empty_expected() -> None:
    """wait_for_text() rejects empty expected text at the boundary."""
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match=r"wait_for_text.*non-empty"):
        ScreenshotClient(pk).wait_for_text("")


def test_wait_for_text_rejects_out_of_range_threshold() -> None:
    """wait_for_text() rejects threshold outside [0.0, 1.0]."""
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match=r"threshold must be in"):
        ScreenshotClient(pk).wait_for_text("Boot", threshold=1.5)
    with pytest.raises(ValueError, match=r"threshold must be in"):
        ScreenshotClient(pk).wait_for_text("Boot", threshold=-0.1)


def test_wait_for_text_rejects_negative_timeout() -> None:
    """wait_for_text() rejects negative timeout."""
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match=r"timeout.*non-negative"):
        ScreenshotClient(pk).wait_for_text("Boot", timeout=-1.0)


def test_wait_for_text_rejects_non_positive_interval() -> None:
    """wait_for_text() rejects zero or negative interval."""
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match=r"interval must be positive"):
        ScreenshotClient(pk).wait_for_text("Boot", interval=0)
    with pytest.raises(ValueError, match=r"interval must be positive"):
        ScreenshotClient(pk).wait_for_text("Boot", interval=-0.5)


def test_wait_for_text_saves_captures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """wait_for_text(capture_dir=...) persists at least one screenshot."""

    def fake_get(_url: str, **_kwargs: object) -> MagicMock:
        m = MagicMock(status_code=200)
        m.content = b"Boot Menu"
        return m

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.screenshot.requests.get",
        fake_get,
    )

    m = ScreenshotClient(_mock_pikvm()).wait_for_text(
        "Boot Menu",
        capture_dir=tmp_path,
        timeout=1.0,
        interval=0.1,
    )
    assert m.matched is True
    assert len(m.captures) >= 1
    for p in m.captures:
        assert p.exists()
