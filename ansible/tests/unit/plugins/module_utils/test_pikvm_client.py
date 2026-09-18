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


# ---------------------------------------------------------------------------
# _checked_post: kvmd's MSD write endpoints answer 4xx with the reason in the
# JSON body, and pikvm-lib's own MSD methods discard that response. These pin
# that the wrapper surfaces the failure instead of letting the module proceed.
# ---------------------------------------------------------------------------

def _client_with_post(status_code, body=None, text=""):
    """A PiKVMModuleClient whose underlying lib client answers every POST the same way."""
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client.PiKVM"):
        client = PiKVMModuleClient(_make_module())
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if body is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = body
    client.client._post = MagicMock(return_value=resp)
    return client, resp


def test_checked_post_returns_response_on_2xx():
    client, resp = _client_with_post(200, {"ok": True, "result": {}})
    assert client._checked_post("/api/msd/set_params", options="image=a.iso&cdrom=1") is resp


def test_checked_post_raises_with_kvmd_error_msg():
    """The message kvmd gives is the one the operator needs — surface it verbatim."""
    client, _ = _client_with_post(
        400, {"ok": False, "result": {"error": "MsdUnknownImageError", "error_msg": "The image is not found in the storage"}}
    )
    with pytest.raises(RuntimeError) as exc:
        client.msd_set_params("missing.iso", cdrom=True)
    assert "HTTP 400" in str(exc.value)
    assert "The image is not found in the storage" in str(exc.value)


def test_checked_post_raises_without_json_body():
    client, _ = _client_with_post(500, None, text="upstream gone")
    with pytest.raises(RuntimeError) as exc:
        client.msd_connect()
    assert "HTTP 500" in str(exc.value)
    assert "upstream gone" in str(exc.value)


def test_msd_upload_remote_encodes_url_and_names_image():
    """Query params in the download URL must reach kvmd as part of the url value, not as kvmd params."""
    client, _ = _client_with_post(200, {"ok": True, "result": {}})
    client.msd_upload_remote("http://files.example.test/a.iso?token=x", image_name="a.iso")
    path, kwargs = client.client._post.call_args[0][0], client.client._post.call_args[1]
    assert path == "/api/msd/write_remote"
    assert kwargs["options"] == "url=http%3A%2F%2Ffiles.example.test%2Fa.iso%3Ftoken%3Dx&image=a.iso"


def test_msd_upload_remote_raises_when_kvmd_cannot_fetch():
    """An unresolvable remote host is a failed upload, not a 0.4s success."""
    client, _ = _client_with_post(
        400, {"ok": False, "result": {"error": "ClientConnectorDNSError", "error_msg": "Cannot connect to host files.example.test:80"}}
    )
    with pytest.raises(RuntimeError) as exc:
        client.msd_upload_remote("http://files.example.test/a.iso")
    assert "Cannot connect to host" in str(exc.value)


def test_msd_connect_and_disconnect_use_set_connected():
    client, _ = _client_with_post(200, {"ok": True, "result": {}})
    client.msd_connect()
    client.msd_disconnect()
    calls = [(c[0][0], c[1]["options"]) for c in client.client._post.call_args_list]
    assert calls == [("/api/msd/set_connected", "connected=1"), ("/api/msd/set_connected", "connected=0")]
