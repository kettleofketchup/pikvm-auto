"""Tests for the HID input library."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pikvm_auto._internal.commands.hid import (
    HIDAction,
    HIDClient,
    actions_from_yaml,
    canonical_key,
)


def _mock_pikvm() -> MagicMock:
    """Mock PiKVM with the attribute surface HIDClient reads.

    Mirrors pikvm_lib.pikvm_aux.pikvm_aux.BuildPiKVM:
      - hostname, schema, headers, certificate_trusted set in __init__
      - HTTP done via module-level requests.{get,post}, NOT a session
    """
    pk = MagicMock()
    pk.hostname = "pikvm.local"
    pk.schema = "https"
    pk.headers = {"X-KVMD-User": "admin", "X-KVMD-Passwd": "admin"}
    pk.certificate_trusted = False
    return pk


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


def test_tap_sends_key_event_to_kvmd(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.tap posts press + release to /api/hid/events/send_key."""
    pk = _mock_pikvm()
    posts: list[tuple[str, dict]] = []

    def fake_post(url: str, **kwargs: object) -> MagicMock:
        posts.append((url, kwargs))
        return MagicMock(status_code=200)

    monkeypatch.setattr("pikvm_auto._internal.commands.hid.requests.post", fake_post)

    HIDClient(pk).tap("F11")

    assert len(posts) == 2
    url1, kw1 = posts[0]
    url2, kw2 = posts[1]
    assert url1 == "https://pikvm.local/api/hid/events/send_key"
    assert url2 == "https://pikvm.local/api/hid/events/send_key"
    assert kw1["params"] == {"key": "KeyF11", "state": "true"}
    assert kw2["params"] == {"key": "KeyF11", "state": "false"}
    assert kw1["headers"] == {"X-KVMD-User": "admin", "X-KVMD-Passwd": "admin"}
    assert kw1["verify"] is False
    assert kw1["timeout"] == 10


def test_tap_friendly_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.tap canonicalizes friendly aliases before posting."""
    pk = _mock_pikvm()
    posts: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: posts.append((url, kw)) or MagicMock(status_code=200),
    )
    HIDClient(pk).tap("down")
    assert posts[0][1]["params"]["key"] == "ArrowDown"


def test_press_holds_for_configured_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.press sends press, sleeps hold_ms, then sends release."""
    pk = _mock_pikvm()
    posts: list[tuple[str, dict]] = []
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: posts.append((url, kw)) or MagicMock(status_code=200),
    )
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    HIDClient(pk).press("F11", hold_ms=200)

    assert sleep_calls == [0.2]
    assert len(posts) == 2
    assert posts[0][1]["params"] == {"key": "KeyF11", "state": "true"}
    assert posts[1][1]["params"] == {"key": "KeyF11", "state": "false"}


def test_shortcut_calls_send_shortcut_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.shortcut posts atomically to /api/hid/events/send_shortcut."""
    pk = _mock_pikvm()
    posts: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: posts.append((url, kw)) or MagicMock(status_code=200),
    )
    HIDClient(pk).shortcut(["Ctrl", "Alt", "Delete"])
    assert len(posts) == 1
    url, kw = posts[0]
    assert url == "https://pikvm.local/api/hid/events/send_shortcut"
    assert kw["params"] == {"keys": "ControlLeft,AltLeft,Delete"}
    assert kw["headers"] == pk.headers
    assert kw["verify"] is False


def test_shortcut_canonicalizes_each_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.shortcut canonicalizes every key in the chord."""
    pk = _mock_pikvm()
    captured: dict = {}
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: captured.update(kw) or MagicMock(status_code=200),
    )
    HIDClient(pk).shortcut(["meta", "F11"])
    assert captured["params"]["keys"] == "MetaLeft,KeyF11"


def test_type_text_calls_print_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.type_text posts string body to /api/hid/print."""
    pk = _mock_pikvm()
    captured: dict = {}

    def fake_post(url: str, **kw: object) -> MagicMock:
        captured["url"] = url
        captured.update(kw)
        return MagicMock(status_code=200)

    monkeypatch.setattr("pikvm_auto._internal.commands.hid.requests.post", fake_post)

    HIDClient(pk).type_text("Hello")
    assert captured["url"] == "https://pikvm.local/api/hid/print"
    assert captured["params"] == {"limit": 0}
    assert captured["data"] == "Hello"
    assert captured["headers"] == pk.headers
    assert captured["verify"] is False
    assert captured["timeout"] == 30


def test_type_text_slow_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.type_text passes slow=true when requested."""
    pk = _mock_pikvm()
    captured: dict = {}
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: captured.update(kw) or MagicMock(status_code=200),
    )
    HIDClient(pk).type_text("Hi", slow=True)
    assert captured["params"]["slow"] == "true"


def test_play_executes_mixed_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.play executes waits and keys in order."""
    pk = _mock_pikvm()
    posts: list[tuple[str, dict]] = []
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: posts.append((url, kw)) or MagicMock(status_code=200),
    )
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    actions = [
        HIDAction(kind="wait", seconds=1.0),
        HIDAction(kind="key", key="F11"),
        HIDAction(kind="wait", seconds=2.0),
        HIDAction(kind="key", key="Enter"),
        HIDAction(kind="key", key="down"),
    ]
    HIDClient(pk).play(actions)

    assert sleep_calls == [1.0, 2.0]
    # 3 keys × 2 POSTs each (press + release) = 6 posts
    assert len(posts) == 6
    assert posts[0][1]["params"] == {"key": "KeyF11", "state": "true"}
    assert posts[1][1]["params"] == {"key": "KeyF11", "state": "false"}
    assert posts[2][1]["params"] == {"key": "Enter", "state": "true"}
    assert posts[3][1]["params"] == {"key": "Enter", "state": "false"}
    assert posts[4][1]["params"] == {"key": "ArrowDown", "state": "true"}
    assert posts[5][1]["params"] == {"key": "ArrowDown", "state": "false"}


def test_play_rejects_unknown_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """HIDClient.play raises ValueError on unknown action kinds."""
    pk = _mock_pikvm()
    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post",
        lambda url, **kw: MagicMock(status_code=200),
    )
    # Bypass dataclass Literal typing at runtime.
    bogus = HIDAction(kind="key")  # type: ignore[arg-type]
    bogus.kind = "wiggle"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="unknown HIDAction kind"):
        HIDClient(pk).play([bogus])


def test_actions_from_yaml_deserializes_list() -> None:
    """actions_from_yaml builds HIDAction objects from plain dicts."""
    raw = [
        {"kind": "wait", "seconds": 2},
        {"kind": "key", "key": "F11"},
        {"kind": "shortcut", "keys": ["Ctrl", "Alt", "Delete"]},
        {"kind": "text", "text": "hello"},
    ]
    actions = actions_from_yaml(raw)
    assert len(actions) == 4
    assert actions[0].kind == "wait" and actions[0].seconds == 2
    assert actions[1].kind == "key" and actions[1].key == "F11"
    assert actions[2].kind == "shortcut" and actions[2].keys == ["Ctrl", "Alt", "Delete"]
    assert actions[3].kind == "text" and actions[3].text == "hello"


def test_actions_from_yaml_rejects_unknown_kind() -> None:
    """actions_from_yaml raises ValueError on unknown kinds."""
    with pytest.raises(ValueError, match="unknown HIDAction kind"):
        actions_from_yaml([{"kind": "wiggle"}])


def test_actions_from_yaml_rejects_missing_key_for_key_kind():
    with pytest.raises(ValueError, match="kind=key requires"):
        actions_from_yaml([{"kind": "key"}])


def test_actions_from_yaml_rejects_missing_keys_for_shortcut_kind():
    with pytest.raises(ValueError, match="kind=shortcut requires"):
        actions_from_yaml([{"kind": "shortcut"}])


def test_actions_from_yaml_rejects_missing_text_for_text_kind():
    with pytest.raises(ValueError, match="kind=text requires"):
        actions_from_yaml([{"kind": "text"}])


def test_actions_from_yaml_rejects_missing_seconds_for_wait_kind():
    with pytest.raises(ValueError, match="kind=wait requires"):
        actions_from_yaml([{"kind": "wait"}])


def test_shortcut_rejects_empty_keys():
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match="shortcut.*at least one"):
        HIDClient(pk).shortcut([])


def test_type_text_rejects_empty_string():
    pk = _mock_pikvm()
    with pytest.raises(ValueError, match="type_text.*non-empty"):
        HIDClient(pk).type_text("")


def test_tap_raises_on_http_error(monkeypatch):
    import requests as _requests
    pk = _mock_pikvm()

    def fake_post(url, **kwargs):
        resp = MagicMock(status_code=401)
        resp.raise_for_status.side_effect = _requests.HTTPError("401 Unauthorized")
        return resp

    monkeypatch.setattr(
        "pikvm_auto._internal.commands.hid.requests.post", fake_post,
    )

    with pytest.raises(_requests.HTTPError, match="401"):
        HIDClient(pk).tap("F11")
