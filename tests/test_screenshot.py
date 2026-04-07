"""Tests for the screenshot command module."""

from __future__ import annotations

from unittest.mock import MagicMock

from pikvm_auto._internal.commands.screenshot import ScreenMatch, fuzzy_score


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
