# HID input library for PiKVM.
#
# Provides a high-level interface for sending keyboard input via the kvmd HTTP
# API (key taps, chorded shortcuts, text typing, and timed sequences).
#
# HTTP wiring
# -----------
# pikvm-lib 0.5.0's BuildPiKVM does NOT use a requests.Session. Upstream calls
# the module-level requests.get / requests.post functions directly with
# headers=self.headers and verify=self.certificate_trusted on every call.
# HIDClient follows the same pattern: it reads headers, hostname, schema, and
# certificate_trusted from the passed PiKVM instance and calls the
# module-level requests.post directly. The PiKVM object exposes no persistent
# HTTP session attribute. Tests must monkeypatch
# pikvm_auto._internal.commands.hid.requests.post rather than any session.
#
# Modifier key aliases
# --------------------
# Short modifier aliases (ctrl, alt, shift, meta/win) default to the LEFT
# variant of the corresponding kvmd key code (ControlLeft, AltLeft, ShiftLeft,
# MetaLeft). To target the right-hand modifier, pass the canonical name
# directly (ControlRight, AltRight, ShiftRight, MetaRight).

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import requests

if TYPE_CHECKING:
    from pikvm_lib.pikvm import PiKVM


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
    key: str | None = None
    keys: list[str] | None = None
    text: str | None = None
    seconds: float | None = None


# Friendly alias → kvmd canonical key code.
# Modifier aliases default to the LEFT variant; use the canonical name to
# target the right-hand modifier.
_KEY_ALIASES: dict[str, str] = {
    # Function keys F1..F12
    **{f"f{i}": f"F{i}" for i in range(1, 13)},
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
    },
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


class HIDClient:
    """High-level HID input client for PiKVM.

    Reads ``headers``, ``hostname``, ``schema``, and ``certificate_trusted``
    from the passed ``PiKVM`` instance and calls the module-level
    ``requests.post`` directly (matching pikvm-lib's own pattern — see module
    docstring).
    """

    def __init__(self, pikvm: PiKVM) -> None:
        self._headers = pikvm.headers
        self._base = f"{pikvm.schema}://{pikvm.hostname}"
        self._verify = pikvm.certificate_trusted

    def _send_key(self, code: str, state: str) -> None:
        """POST a single key press or release event to kvmd.

        ``state`` is the string ``"true"`` (press) or ``"false"`` (release) —
        kvmd's API spec documents the ``state`` query parameter as a boolean,
        serialised as a lowercase string.
        """
        resp = requests.post(
            f"{self._base}/api/hid/events/send_key",
            params={"key": code, "state": state},
            headers=self._headers,
            verify=self._verify,
            timeout=10,
        )
        resp.raise_for_status()

    def tap(self, key: str) -> None:
        """Press and release a single key."""
        code = canonical_key(key)
        self._send_key(code, "true")
        self._send_key(code, "false")

    def press(self, key: str, *, hold_ms: int = 50) -> None:
        """Press a key, hold it for ``hold_ms`` milliseconds, then release."""
        code = canonical_key(key)
        self._send_key(code, "true")
        time.sleep(hold_ms / 1000)
        self._send_key(code, "false")

    def shortcut(self, keys: list[str]) -> None:
        """Send a chord atomically via kvmd's ``/api/hid/events/send_shortcut``.

        Server-side timing is more reliable than a synthesised press/release
        sequence, so this delegates the entire chord to kvmd.
        """
        if not keys:
            raise ValueError("shortcut() requires at least one key")
        codes = ",".join(canonical_key(k) for k in keys)
        resp = requests.post(
            f"{self._base}/api/hid/events/send_shortcut",
            params={"keys": codes},
            headers=self._headers,
            verify=self._verify,
            timeout=10,
        )
        resp.raise_for_status()

    def type_text(self, text: str, *, slow: bool = False) -> None:
        """Type a string via ``/api/hid/print``.

        ``limit=0`` means unlimited length. ``slow=True`` adds inter-character
        delays server-side for flaky guest input handling.
        """
        if not text:
            raise ValueError("type_text() requires non-empty text")
        params: dict[str, str | int] = {"limit": 0}
        if slow:
            params["slow"] = "true"
        resp = requests.post(
            f"{self._base}/api/hid/print",
            params=params,
            data=text,
            headers=self._headers,
            verify=self._verify,
            timeout=30,
        )
        resp.raise_for_status()

    def play(self, actions: list[HIDAction]) -> None:
        """Execute a sequence of HID actions in order.

        Each action is dispatched by ``kind``:
          - ``"wait"`` → ``time.sleep(a.seconds or 0)``
          - ``"key"`` → ``self.tap(a.key)`` (requires ``a.key``)
          - ``"shortcut"`` → ``self.shortcut(a.keys)`` (requires ``a.keys``)
          - ``"text"`` → ``self.type_text(a.text)`` (requires ``a.text``)
        """
        for a in actions:
            if a.kind == "wait":
                time.sleep(a.seconds or 0)
            elif a.kind == "key":
                if a.key is None:
                    raise ValueError("HIDAction(kind='key') requires 'key'")
                self.tap(a.key)
            elif a.kind == "shortcut":
                if a.keys is None:
                    raise ValueError("HIDAction(kind='shortcut') requires 'keys'")
                self.shortcut(a.keys)
            elif a.kind == "text":
                if a.text is None:
                    raise ValueError("HIDAction(kind='text') requires 'text'")
                self.type_text(a.text)
            else:
                raise ValueError(f"unknown HIDAction kind: {a.kind!r}")


_VALID_KINDS: frozenset[str] = frozenset({"key", "shortcut", "text", "wait"})


def actions_from_yaml(raw: list[dict]) -> list[HIDAction]:
    """Build a list of ``HIDAction`` from raw dicts (e.g. parsed YAML).

    Each dict must have a valid ``kind`` plus the relevant payload fields
    (``key``, ``keys``, ``text``, ``seconds``). Unknown kinds raise
    ``ValueError`` with the offending item index.
    """
    out: list[HIDAction] = []
    for i, item in enumerate(raw):
        kind = item.get("kind")
        if kind not in _VALID_KINDS:
            raise ValueError(f"unknown HIDAction kind: {kind!r} (item {i})")
        if kind == "key" and not item.get("key"):
            raise ValueError(f"HIDAction kind=key requires 'key' (item {i})")
        if kind == "shortcut" and not item.get("keys"):
            raise ValueError(f"HIDAction kind=shortcut requires 'keys' (item {i})")
        if kind == "text" and item.get("text") is None:
            raise ValueError(f"HIDAction kind=text requires 'text' (item {i})")
        if kind == "wait" and item.get("seconds") is None:
            raise ValueError(f"HIDAction kind=wait requires 'seconds' (item {i})")
        out.append(
            HIDAction(
                kind=kind,
                key=item.get("key"),
                keys=item.get("keys"),
                text=item.get("text"),
                seconds=item.get("seconds"),
            ),
        )
    return out
