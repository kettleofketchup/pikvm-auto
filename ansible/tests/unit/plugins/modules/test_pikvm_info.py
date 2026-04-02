"""Tests for pikvm_info module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_info import main


def _run_module(params, check_mode=False):
    """Run module with mocked AnsibleModule and PiKVM client."""
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_info.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_info.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1",
            "pikvm_user": "admin",
            "pikvm_passwd": "secret",
            "pikvm_totp_secret": None,
            "pikvm_verify_ssl": False,
            "gather": ["system", "atx", "msd", "streamer"],
            **params,
        }
        mock_module.check_mode = check_mode
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_system_info.return_value = {"system": {"kvmd": {"version": "4.161"}}}
        mock_client.get_atx_state.return_value = {"enabled": True, "leds": {"power": False}}
        mock_client.get_msd_state.return_value = {"enabled": True, "storage": {"images": {}}}
        mock_client.get_streamer_state.return_value = {"streamer": {"source": {"online": False}}}
        mock_client_cls.return_value = mock_client

        main()
        return mock_module, mock_client


def test_info_returns_facts():
    """pikvm_info sets ansible_facts with pikvm data."""
    module, client = _run_module({})
    module.exit_json.assert_called_once()
    call_kwargs = module.exit_json.call_args[1]
    assert call_kwargs["changed"] is False
    assert "ansible_facts" in call_kwargs
    assert "pikvm" in call_kwargs["ansible_facts"]


def test_info_calls_all_subsystems():
    """pikvm_info calls all four subsystem APIs by default."""
    module, client = _run_module({})
    client.get_system_info.assert_called_once()
    client.get_atx_state.assert_called_once()
    client.get_msd_state.assert_called_once()
    client.get_streamer_state.assert_called_once()


def test_info_respects_gather_filter():
    """pikvm_info only queries requested subsystems."""
    module, client = _run_module({"gather": ["system"]})
    client.get_system_info.assert_called_once()
    client.get_atx_state.assert_not_called()
    client.get_msd_state.assert_not_called()
    client.get_streamer_state.assert_not_called()


def test_info_works_in_check_mode():
    """pikvm_info works identically in check mode (read-only)."""
    module, client = _run_module({}, check_mode=True)
    module.exit_json.assert_called_once()
    assert module.exit_json.call_args[1]["changed"] is False
