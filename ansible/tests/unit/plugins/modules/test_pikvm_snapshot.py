"""Tests for pikvm_snapshot module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_snapshot import main


def _run_module(params, check_mode=False):
    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_snapshot.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_snapshot.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1",
            "pikvm_user": "admin",
            "pikvm_passwd": "secret",
            "pikvm_totp_secret": None,
            "pikvm_verify_ssl": False,
            "dest": "/tmp/screenshots",
            "filename": "snapshot.jpeg",
            "ocr": False,
            **params,
        }
        mock_module.check_mode = check_mode
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_snapshot.return_value = "/tmp/screenshots/snapshot.jpeg"
        mock_client_cls.return_value = mock_client

        main()
        return mock_module, mock_client


def test_snapshot_captures():
    """Snapshot module captures and saves image."""
    module, client = _run_module({})
    client.get_snapshot.assert_called_once_with("/tmp/screenshots", filename="snapshot.jpeg", ocr=False)
    call_kwargs = module.exit_json.call_args[1]
    assert call_kwargs["changed"] is True
    assert call_kwargs["path"] == "/tmp/screenshots/snapshot.jpeg"


def test_snapshot_with_ocr():
    """Snapshot module supports OCR mode."""
    module, client = _run_module({"ocr": True, "filename": "screen.txt"})
    client.get_snapshot.assert_called_once_with("/tmp/screenshots", filename="screen.txt", ocr=True)


def test_snapshot_check_mode():
    """Snapshot check mode reports change but doesn't capture."""
    module, client = _run_module({}, check_mode=True)
    client.get_snapshot.assert_not_called()
    assert module.exit_json.call_args[1]["changed"] is True
