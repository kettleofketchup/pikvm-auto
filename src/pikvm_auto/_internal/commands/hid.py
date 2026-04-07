"""HID input library for PiKVM.

Provides a high-level interface for sending keyboard input via the kvmd HTTP
API (key taps, chorded shortcuts, text typing, and timed sequences).

HTTP wiring
-----------
pikvm-lib 0.5.0's ``BuildPiKVM`` does NOT use a ``requests.Session``. Upstream
calls the module-level ``requests.get`` / ``requests.post`` functions directly
with ``headers=self.headers`` and ``verify=self.certificate_trusted`` on every
call. ``HIDClient`` follows the same pattern: it reads ``headers``,
``hostname``, ``schema``, and ``certificate_trusted`` from the passed PiKVM
instance and calls the module-level ``requests.post`` directly. There is no
``_session`` attribute on the PiKVM object. Tests must monkeypatch
``pikvm_auto._internal.commands.hid.requests.post`` rather than any session.

Modifier key aliases
--------------------
Short modifier aliases (``ctrl``, ``alt``, ``shift``, ``meta``/``win``) default
to the LEFT variant of the corresponding kvmd key code (``ControlLeft``,
``AltLeft``, ``ShiftLeft``, ``MetaLeft``). To target the right-hand modifier,
pass the canonical name directly (``ControlRight``, ``AltRight``,
``ShiftRight``, ``MetaRight``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class HIDAction:
    """A single HID action in a scripted input sequence.

    Fields:
      kind:    one of "key", "shortcut", "text", "wait".
      key:     single key name (used when ``kind == "key"``).
      keys:    list of key names for a chord (used when ``kind == "shortcut"``).
      text:    text to type (used when ``kind == "text"``).
      seconds: delay in seconds (used when ``kind == "wait"``).
    """

    kind: Literal["key", "shortcut", "text", "wait"]
    key: Optional[str] = None
    keys: Optional[list[str]] = None
    text: Optional[str] = None
    seconds: Optional[float] = None


# Friendly alias → kvmd canonical key code.
# Modifier aliases default to the LEFT variant; use the canonical name to
# target the right-hand modifier.
_KEY_ALIASES: dict[str, str] = {
    # Function keys F1..F12
    **{f"f{i}": f"KeyF{i}" for i in range(1, 13)},
    # Arrow keys
    "up": "ArrowUp",
    "down": "ArrowDown",
    "left": "ArrowLeft",
    "right": "ArrowRight",
    # Common singles
    "enter": "Enter",
    "return": "Enter",
    "esc": "Escape",
    "escape": "Escape",
    "tab": "Tab",
    "del": "Delete",
    "delete": "Delete",
    "backspace": "Backspace",
    "space": "Space",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    # Modifiers default to LEFT variant
    "ctrl": "ControlLeft",
    "alt": "AltLeft",
    "shift": "ShiftLeft",
    "meta": "MetaLeft",
    "win": "MetaLeft",
}

# Canonical key codes that do not share a common prefix (Key*, Arrow*, Digit*,
# Numpad*) but are still valid passthroughs.
_CANONICAL_SINGLES: frozenset[str] = frozenset(
    {
        "Enter",
        "Escape",
        "Tab",
        "Delete",
        "Backspace",
        "Space",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "Insert",
        "CapsLock",
        "ControlLeft",
        "ControlRight",
        "AltLeft",
        "AltRight",
        "ShiftLeft",
        "ShiftRight",
        "MetaLeft",
        "MetaRight",
        "Minus",
        "Equal",
        "BracketLeft",
        "BracketRight",
        "Backslash",
        "Semicolon",
        "Quote",
        "Backquote",
        "Comma",
        "Period",
        "Slash",
    }
)

_CANONICAL_PREFIXES: tuple[str, ...] = ("Key", "Arrow", "Digit", "Numpad")


def canonical_key(key: str) -> str:
    """Return the kvmd canonical code for ``key``.

    Lookup order:
      1. Friendly alias (case-insensitive) — e.g. ``f11`` → ``KeyF11``.
      2. Canonical passthrough — names with a known prefix (``Key*``,
         ``Arrow*``, ``Digit*``, ``Numpad*``) or known singles (``Enter``,
         ``ControlRight``, …) are returned unchanged.

    Raises ``ValueError`` if the key cannot be resolved.
    """
    if not isinstance(key, str) or not key:
        raise ValueError(f"unknown key: {key!r}")

    lower = key.lower()
    if lower in _KEY_ALIASES:
        return _KEY_ALIASES[lower]

    if key in _CANONICAL_SINGLES:
        return key
    if key.startswith(_CANONICAL_PREFIXES):
        return key

    raise ValueError(f"unknown key: {key!r}")
