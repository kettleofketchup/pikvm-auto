"""Tests for pikvm_client module utils."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PiKVMModuleClient,
    PIKVM_COMMON_ARGS,
)


def _make_module(**overrides):
    params = {
        "pikvm_host": "10.0.0.1",
        "pikvm_user": "admin",
        "pikvm_passwd": "secret",
        "pikvm_totp_secret": None,
        "pikvm_verify_ssl": False,
    }
    params.update(overrides)
    module = MagicMock()
    module.params = params
    return module


def test_common_args_has_required_keys():
    """PIKVM_COMMON_ARGS contains all required auth params."""
    assert "pikvm_host" in PIKVM_COMMON_ARGS
    assert "pikvm_user" in PIKVM_COMMON_ARGS
    assert "pikvm_passwd" in PIKVM_COMMON_ARGS
    assert "pikvm_totp_secret" in PIKVM_COMMON_ARGS
    assert "pikvm_verify_ssl" in PIKVM_COMMON_ARGS


def test_passwd_is_no_log():
    """Password and TOTP secret are marked no_log."""
    assert PIKVM_COMMON_ARGS["pikvm_passwd"]["no_log"] is True
    assert PIKVM_COMMON_ARGS["pikvm_totp_secret"]["no_log"] is True


@patch("ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client.PiKVM")
def test_client_creates_pikvm_instance(mock_pikvm):
    """Client creates a PiKVM instance with correct params."""
    module = _make_module()
    client = PiKVMModuleClient(module)
    mock_pikvm.assert_called_once_with(
        hostname="10.0.0.1",
        username="admin",
        password="secret",
        secret=None,
        schema="https",
        cert_trusted=False,
        ws_client=None,
    )


@patch("ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client.HAS_PIKVM_LIB", False)
def test_client_fails_without_pikvm_lib():
    """Client calls fail_json if pikvm-lib not installed."""
    module = _make_module()
    PiKVMModuleClient(module)
    module.fail_json.assert_called_once()
    assert "pikvm-lib" in module.fail_json.call_args[1]["msg"]
