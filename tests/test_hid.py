"""Tests for the HID input library."""

from __future__ import annotations

import pytest

from pikvm_auto._internal.commands.hid import HIDAction, canonical_key


def test_hid_action_key_kind() -> None:
    """HIDAction supports the 'key' kind with a key field."""
    action = HIDAction(kind="key", key="F11")
    assert action.kind == "key"
    assert action.key == "F11"
    assert action.keys is None
    assert action.text is None
    assert action.seconds is None


def test_hid_action_wait_kind() -> None:
    """HIDAction supports the 'wait' kind with a seconds field."""
    action = HIDAction(kind="wait", seconds=2.5)
    assert action.kind == "wait"
    assert action.seconds == 2.5
    assert action.key is None
    assert action.keys is None
    assert action.text is None


def test_canonical_key_friendly_aliases() -> None:
    """Friendly aliases map to kvmd canonical names (case-insensitive)."""
    assert canonical_key("F11") == "KeyF11"
    assert canonical_key("f11") == "KeyF11"
    assert canonical_key("down") == "ArrowDown"
    assert canonical_key("UP") == "ArrowUp"
    assert canonical_key("enter") == "Enter"
    assert canonical_key("return") == "Enter"
    assert canonical_key("esc") == "Escape"
    assert canonical_key("escape") == "Escape"
    assert canonical_key("del") == "Delete"
    assert canonical_key("delete") == "Delete"
    assert canonical_key("tab") == "Tab"
    assert canonical_key("ctrl") == "ControlLeft"
    assert canonical_key("alt") == "AltLeft"
    assert canonical_key("shift") == "ShiftLeft"
    assert canonical_key("meta") == "MetaLeft"
    assert canonical_key("win") == "MetaLeft"


def test_canonical_key_passthrough_canonical() -> None:
    """Already-canonical names pass through unchanged."""
    assert canonical_key("KeyF11") == "KeyF11"
    assert canonical_key("ArrowDown") == "ArrowDown"
    assert canonical_key("Enter") == "Enter"
    assert canonical_key("ControlRight") == "ControlRight"
    assert canonical_key("Digit1") == "Digit1"
    assert canonical_key("Numpad5") == "Numpad5"


def test_canonical_key_unknown_raises() -> None:
    """Unknown keys raise ValueError."""
    with pytest.raises(ValueError, match="unknown key"):
        canonical_key("BogusKey")
