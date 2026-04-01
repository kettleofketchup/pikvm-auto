"""Tests for the info command."""

from __future__ import annotations

from unittest.mock import MagicMock

from pikvm_auto._internal.commands.info import run_info


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.get_system_info.return_value = {
        "result": {
            "system": {
                "kvmd": {"version": "3.291"},
                "streamer": {"app": "ustreamer", "version": "6.12"},
            },
            "hw": {
                "platform": {"type": "rpi4", "base": "Raspberry Pi 4 Model B Rev 1.5"},
            },
            "meta": {"server": {"host": "pikvm.local"}},
        }
    }
    client.get_atx_state.return_value = {
        "result": {
            "enabled": True,
            "busy": False,
            "leds": {"power": True, "hdd": False},
        }
    }
    client.get_streamer_state.return_value = {
        "result": {
            "ok": True,
            "features": {"resolution": {"width": 1920, "height": 1080}},
        }
    }
    return client


def test_run_info_returns_zero() -> None:
    """info command returns 0 on success."""
    client = _make_mock_client()
    result = run_info(client)
    assert result == 0


def test_run_info_calls_apis() -> None:
    """info command calls all three API endpoints."""
    client = _make_mock_client()
    run_info(client)
    client.get_system_info.assert_called_once()
    client.get_atx_state.assert_called_once()
    client.get_streamer_state.assert_called_once()


def test_run_info_output(capsys) -> None:
    """info command prints formatted output."""
    client = _make_mock_client()
    run_info(client)
    output = capsys.readouterr().out
    assert "System Info" in output or "system" in output.lower()
    assert "ATX" in output or "Power" in output
