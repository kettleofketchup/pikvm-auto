"""Tests for pikvm_atx module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx import main


def _run_module(params, check_mode=False):
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1",
            "pikvm_user": "admin",
            "pikvm_passwd": "secret",
            "pikvm_totp_secret": None,
            "pikvm_verify_ssl": False,
            "state": "on",
            "force": False,
            "wait": False,
            "timeout": 30,
            **params,
        }
        mock_module.check_mode = check_mode
        mock_module._diff = False
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_atx_state.return_value = {
            "enabled": True,
            "busy": False,
            "leds": {"power": False, "hdd": False},
        }
        mock_client_cls.return_value = mock_client

        main()
        return mock_module, mock_client


def test_power_on_when_off():
    """ATX power on calls set_atx_power when machine is off."""
    module, client = _run_module({"state": "on"})
    client.set_atx_power.assert_called_with(action="on")
    call_kwargs = module.exit_json.call_args[1]
    assert call_kwargs["changed"] is True


def test_power_on_when_already_on():
    """ATX power on is idempotent when already on."""
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1", "pikvm_user": "admin", "pikvm_passwd": "secret",
            "pikvm_totp_secret": None, "pikvm_verify_ssl": False,
            "state": "on", "force": False, "wait": False, "timeout": 30,
        }
        mock_module.check_mode = False
        mock_module._diff = False
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_atx_state.return_value = {
            "enabled": True, "busy": False, "leds": {"power": True, "hdd": False},
        }
        mock_client_cls.return_value = mock_client

        main()
        mock_client.set_atx_power.assert_not_called()
        assert mock_module.exit_json.call_args[1]["changed"] is False


def test_power_off_uses_force():
    """ATX power off with force uses off_hard action."""
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1", "pikvm_user": "admin", "pikvm_passwd": "secret",
            "pikvm_totp_secret": None, "pikvm_verify_ssl": False,
            "state": "off", "force": True, "wait": False, "timeout": 30,
        }
        mock_module.check_mode = False
        mock_module._diff = False
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_atx_state.return_value = {
            "enabled": True, "busy": False, "leds": {"power": True, "hdd": False},
        }
        mock_client_cls.return_value = mock_client

        main()
        mock_client.set_atx_power.assert_called_with(action="off_hard")
        assert mock_module.exit_json.call_args[1]["changed"] is True


def test_reboot_when_off_powers_on():
    """ATX reboot when powered off sends power on instead."""
    module, client = _run_module({"state": "reboot"})
    client.set_atx_power.assert_called_with(action="on")


def test_reboot_when_on_uses_reset_hard():
    """ATX reboot always uses reset_hard (no graceful/hard distinction for reset)."""
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1", "pikvm_user": "admin", "pikvm_passwd": "secret",
            "pikvm_totp_secret": None, "pikvm_verify_ssl": False,
            "state": "reboot", "force": False, "wait": False, "timeout": 30,
        }
        mock_module.check_mode = False
        mock_module._diff = False
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_atx_state.return_value = {
            "enabled": True, "busy": False, "leds": {"power": True, "hdd": False},
        }
        mock_client_cls.return_value = mock_client

        main()
        mock_client.set_atx_power.assert_called_with(action="reset_hard")


def test_check_mode_no_action():
    """ATX check mode reports change but takes no action."""
    module, client = _run_module({"state": "on"}, check_mode=True)
    client.set_atx_power.assert_not_called()
    call_kwargs = module.exit_json.call_args[1]
    assert call_kwargs["changed"] is True


def test_timeout_fails_with_message():
    """ATX timeout calls fail_json with clear message."""
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.PiKVMModuleClient") as mock_client_cls, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_atx.time") as mock_time:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1", "pikvm_user": "admin", "pikvm_passwd": "secret",
            "pikvm_totp_secret": None, "pikvm_verify_ssl": False,
            "state": "on", "force": False, "wait": True, "timeout": 2,
        }
        mock_module.check_mode = False
        mock_module._diff = False
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        # Power stays off (never transitions)
        mock_client.get_atx_state.return_value = {
            "enabled": True, "busy": False, "leds": {"power": False, "hdd": False},
        }
        mock_client_cls.return_value = mock_client

        # Simulate time passing beyond timeout
        mock_time.time.side_effect = [0, 0, 3]  # start, first check, past deadline
        mock_time.sleep = MagicMock()

        main()
        mock_module.fail_json.assert_called_once()
        assert "Timeout" in mock_module.fail_json.call_args[1]["msg"]
