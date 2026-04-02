"""Tests for pikvm_msd module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_msd import main


MSD_EMPTY = {
    "enabled": True,
    "online": True,
    "busy": False,
    "drive": {"connected": False, "image": None, "cdrom": False, "rw": False},
    "storage": {"images": {}, "parts": {"": {"free": 20000000000, "size": 24000000000, "writable": True}}},
}

MSD_WITH_IMAGE = {
    "enabled": True,
    "online": True,
    "busy": False,
    "drive": {
        "connected": True,
        "image": "test.iso",
        "cdrom": True,
        "rw": False,
    },
    "storage": {
        "images": {"test.iso": {"size": 1000000, "complete": True}},
        "parts": {"": {"free": 19000000000, "size": 24000000000, "writable": True}},
    },
}


def _run_module(params, msd_state=None, check_mode=False):
    if msd_state is None:
        msd_state = MSD_EMPTY

    with patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_msd.AnsibleModule") as mock_am, \
         patch("ansible_collections.kettleofketchup.pikvm.plugins.modules.pikvm_msd.PiKVMModuleClient") as mock_client_cls:

        mock_module = MagicMock()
        mock_module.params = {
            "pikvm_host": "10.0.0.1",
            "pikvm_user": "admin",
            "pikvm_passwd": "secret",
            "pikvm_totp_secret": None,
            "pikvm_verify_ssl": False,
            "state": "present",
            "image": None,
            "image_url": None,
            "image_path": None,
            "cdrom": True,
            "wait": True,
            "timeout": 600,
            **params,
        }
        mock_module.check_mode = check_mode
        mock_module._diff = False
        mock_am.return_value = mock_module

        mock_client = MagicMock()
        mock_client.get_msd_state.return_value = msd_state
        mock_client_cls.return_value = mock_client

        main()
        return mock_module, mock_client


def test_present_uploads_remote():
    """MSD present with image_url triggers remote upload."""
    module, client = _run_module({"state": "present", "image_url": "http://example.com/test.iso"})
    client.msd_upload_remote.assert_called_once()
    assert module.exit_json.call_args[1]["changed"] is True


def test_present_uploads_local_file():
    """MSD present with image_path triggers local file upload."""
    module, client = _run_module({"state": "present", "image_path": "/tmp/test.iso"})
    client.msd_upload_file.assert_called_once()
    assert module.exit_json.call_args[1]["changed"] is True


def test_present_skips_if_exists():
    """MSD present skips upload if image already exists and complete."""
    module, client = _run_module(
        {"state": "present", "image_url": "http://example.com/test.iso"},
        msd_state=MSD_WITH_IMAGE,
    )
    client.msd_upload_remote.assert_not_called()
    assert module.exit_json.call_args[1]["changed"] is False


def test_absent_removes_image():
    """MSD absent removes an existing image."""
    module, client = _run_module({"state": "absent", "image": "test.iso"}, msd_state=MSD_WITH_IMAGE)
    client.msd_disconnect.assert_called_once()
    client.msd_remove.assert_called_once_with("test.iso")
    assert module.exit_json.call_args[1]["changed"] is True


def test_absent_idempotent():
    """MSD absent is no-op if image doesn't exist."""
    module, client = _run_module({"state": "absent", "image": "nonexistent.iso"})
    client.msd_remove.assert_not_called()
    assert module.exit_json.call_args[1]["changed"] is False


def test_connected_connects_drive():
    """MSD connected connects the drive."""
    state = {**MSD_WITH_IMAGE, "drive": {**MSD_WITH_IMAGE["drive"], "connected": False}}
    module, client = _run_module({"state": "connected", "image": "test.iso"}, msd_state=state)
    client.msd_connect.assert_called_once()
    assert module.exit_json.call_args[1]["changed"] is True


def test_disconnected_disconnects():
    """MSD disconnected disconnects the drive."""
    module, client = _run_module({"state": "disconnected"}, msd_state=MSD_WITH_IMAGE)
    client.msd_disconnect.assert_called_once()
    assert module.exit_json.call_args[1]["changed"] is True


def test_disconnected_idempotent():
    """MSD disconnected is no-op if already disconnected."""
    module, client = _run_module({"state": "disconnected"})
    client.msd_disconnect.assert_not_called()
    assert module.exit_json.call_args[1]["changed"] is False


def test_check_mode_no_action():
    """MSD check mode reports change but takes no action."""
    module, client = _run_module(
        {"state": "present", "image_url": "http://example.com/test.iso"},
        check_mode=True,
    )
    client.msd_upload_remote.assert_not_called()
    assert module.exit_json.call_args[1]["changed"] is True
