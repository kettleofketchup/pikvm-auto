#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: pikvm_msd
short_description: Manage PiKVM mass storage drive images
version_added: "1.0.0"
description:
    - Upload, remove, and manage ISO images on PiKVM MSD.
    - Connect/disconnect virtual drives with media type control.
    - Supports local file upload and remote URL download.
    - Validates MSD health before operations (preflight).
    - Optional size validation to detect stale same-name images.
    - Reports upload timing and throughput.
    - Supports check mode and diff mode.
options:
    state:
        description:
            - Desired state of the MSD resource.
            - C(present) uploads image if missing or size mismatched.
            - C(absent) removes image from storage.
            - C(connected) mounts virtual drive.
            - C(disconnected) unmounts virtual drive.
            - C(verify) checks that the expected image is connected, complete, and optionally size-matched.
        type: str
        required: true
        choices: ["present", "absent", "connected", "disconnected", "verify"]
    image:
        description: Image filename on PiKVM storage.
        type: str
    image_url:
        description:
            - URL for PiKVM to download ISO from remotely.
            - Mutually exclusive with I(image_path).
        type: str
    image_path:
        description:
            - Local path to ISO file for upload.
            - Mutually exclusive with I(image_url).
        type: path
    expected_size:
        description:
            - Expected image size in bytes.
            - When set, C(state=present) will re-upload if the existing image size differs.
            - When set, C(state=verify) will fail if the connected image size differs.
            - Set to 0 or omit to skip size validation.
        type: int
        default: 0
    cdrom:
        description: Mount as CD-ROM (true) or Flash drive (false).
        type: bool
        default: true
    wait:
        description: Wait for upload to complete.
        type: bool
        default: true
    timeout:
        description: Seconds to wait for upload completion.
        type: int
        default: 600
extends_documentation_fragment:
    - kettleofketchup.pikvm.pikvm_auth
author:
    - "KettleOfKetchup (@kettleofketchup)"
"""

EXAMPLES = r"""
- name: Upload ISO from URL
  kettleofketchup.pikvm.pikvm_msd:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: present
    image_url: "http://fileserver/ubuntu.iso"
    cdrom: true

- name: Upload with size validation (re-upload if stale)
  kettleofketchup.pikvm.pikvm_msd:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: present
    image_url: "http://fileserver/ubuntu.iso"
    expected_size: 3877109760

- name: Verify ISO is loaded correctly
  kettleofketchup.pikvm.pikvm_msd:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: verify
    image: ubuntu.iso
    expected_size: 3877109760

- name: Connect boot drive
  kettleofketchup.pikvm.pikvm_msd:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: connected
    image: ubuntu.iso
    cdrom: true

- name: Remove old ISO
  kettleofketchup.pikvm.pikvm_msd:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: absent
    image: old-image.iso

- name: Disconnect drive
  kettleofketchup.pikvm.pikvm_msd:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: disconnected
"""

RETURN = r"""
changed:
    description: Whether the MSD state was changed.
    returned: always
    type: bool
image:
    description: Image information.
    returned: when available
    type: dict
drive:
    description: Current drive state after operation.
    returned: always
    type: dict
storage:
    description: Storage information after operation.
    returned: always
    type: dict
preflight:
    description: MSD subsystem health at operation start.
    returned: always
    type: dict
    contains:
        enabled:
            description: MSD subsystem is enabled.
            type: bool
        online:
            description: USB-OTG device is visible.
            type: bool
        busy:
            description: Another operation is in progress.
            type: bool
upload:
    description: Upload timing and throughput (only when an upload occurred).
    returned: when upload performed
    type: dict
    contains:
        elapsed_seconds:
            description: Total upload duration.
            type: float
        throughput_mbps:
            description: Upload throughput in Mbps.
            type: float
        throughput_mibs:
            description: Upload throughput in MiB/s.
            type: float
        size_bytes:
            description: Uploaded image size in bytes.
            type: int
msg:
    description: Human-readable status message.
    returned: always
    type: str
"""

import json
import os
import time

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PiKVMModuleClient,
    PIKVM_COMMON_ARGS,
)


def _get_image_name(params):
    """Derive image name from params."""
    if params.get("image"):
        return params["image"]
    if params.get("image_url"):
        return os.path.basename(params["image_url"].split("?")[0])
    if params.get("image_path"):
        return os.path.basename(params["image_path"])
    return None


def _preflight(msd):
    """Extract MSD health info."""
    return {
        "enabled": msd.get("enabled", False),
        "online": msd.get("online", False),
        "busy": msd.get("busy", False),
    }


def _check_preflight(module, preflight):
    """Fail early if MSD subsystem is unhealthy."""
    if not preflight["enabled"]:
        module.fail_json(
            msg="MSD subsystem is disabled. Enable it in PiKVM web UI or kvmd config.",
            preflight=preflight,
        )
    if not preflight["online"]:
        module.fail_json(
            msg="MSD is enabled but offline — USB-OTG device not detected. Check USB cable and BIOS settings.",
            preflight=preflight,
        )
    if preflight["busy"]:
        module.fail_json(
            msg="MSD is busy with another operation. Wait for it to complete or reset MSD via PiKVM web UI.",
            preflight=preflight,
        )


def _size_matches(existing, expected_size):
    """Check if existing image size matches expected."""
    if not expected_size:
        return True
    return existing.get("size", 0) == expected_size


def _upload_throughput(elapsed, size_bytes):
    """Compute upload throughput stats."""
    elapsed = max(elapsed, 0.001)
    return {
        "elapsed_seconds": round(elapsed, 1),
        "size_bytes": size_bytes,
        "throughput_mibs": round(size_bytes / 1048576 / elapsed, 1),
        "throughput_mbps": round(size_bytes * 8 / 1000000 / elapsed, 0),
    }


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "state": dict(type="str", required=True, choices=["present", "absent", "connected", "disconnected", "verify"]),
        "image": dict(type="str", required=False),
        "image_url": dict(type="str", required=False),
        "image_path": dict(type="path", required=False),
        "expected_size": dict(type="int", default=0),
        "cdrom": dict(type="bool", default=True),
        "wait": dict(type="bool", default=True),
        "timeout": dict(type="int", default=600),
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        mutually_exclusive=[["image_url", "image_path"]],
        required_if=[
            ("state", "absent", ("image",)),
            ("state", "connected", ("image",)),
            ("state", "verify", ("image",)),
        ],
    )

    client = PiKVMModuleClient(module)
    state = module.params["state"]
    expected_size = module.params.get("expected_size", 0) or 0

    try:
        msd = client.get_msd_state()
    except Exception as e:
        module.fail_json(msg=f"Failed to get MSD state: {e}")

    preflight = _preflight(msd)
    result = {
        "changed": False,
        "drive": msd.get("drive", {}),
        "storage": msd.get("storage", {}),
        "preflight": preflight,
        "msg": "",
    }

    drive = msd.get("drive", {})
    is_connected = drive.get("connected", False)
    current_drive_image = drive.get("image") or None
    storage_images = msd.get("storage", {}).get("images", {})

    # Preflight check for all mutating operations
    if state in ("present", "absent", "connected", "disconnected"):
        _check_preflight(module, preflight)

    if state == "present":
        image_name = _get_image_name(module.params)
        if not image_name:
            module.fail_json(msg="Cannot determine image name. Provide image, image_url, or image_path.")

        existing = storage_images.get(image_name)

        # Skip upload if image exists, is complete, and size matches
        if existing and existing.get("complete", False) and _size_matches(existing, expected_size):
            result["msg"] = f"Image {image_name} already present and complete"
            if expected_size:
                result["msg"] += f" (size {existing.get('size', 'unknown')} matches expected {expected_size})"
            result["image"] = {"name": image_name, **existing}
            module.exit_json(**result)
            return

        # Need to upload — determine reason
        if existing and existing.get("complete", False) and not _size_matches(existing, expected_size):
            reason = f"size mismatch (have {existing.get('size', 0)}, expected {expected_size})"
        elif existing and not existing.get("complete", False):
            reason = "incomplete upload"
        else:
            reason = "not present"

        result["changed"] = True
        result["msg"] = f"Uploading {image_name} ({reason})"

        if module.check_mode:
            module.exit_json(**result)
            return

        # Remove existing image (incomplete or size mismatch)
        if existing:
            if is_connected and current_drive_image == image_name:
                client.msd_disconnect()
            client.msd_remove(image_name)

        # Disconnect before upload if drive is connected
        if is_connected:
            client.msd_disconnect()

        t_start = time.monotonic()
        try:
            if module.params.get("image_url"):
                client.msd_upload_remote(module.params["image_url"], image_name=image_name)
            elif module.params.get("image_path"):
                client.msd_upload_file(module.params["image_path"], image_name=image_name)
        except Exception as e:
            module.fail_json(msg=f"Upload failed: {e}")
        t_elapsed = time.monotonic() - t_start

        try:
            client.msd_set_params(image_name, cdrom=module.params["cdrom"])
        except Exception as e:
            module.fail_json(msg=f"Failed to set MSD params: {e}")

        # Determine uploaded size from refreshed state
        try:
            msd_after = client.get_msd_state()
            uploaded_image = msd_after.get("storage", {}).get("images", {}).get(image_name, {})
            upload_size = uploaded_image.get("size", expected_size or 0)
        except Exception:
            upload_size = expected_size or 0

        result["image"] = {"name": image_name}
        result["upload"] = _upload_throughput(t_elapsed, upload_size)
        result["msg"] = f"Uploaded {image_name} in {result['upload']['elapsed_seconds']}s ({result['upload']['throughput_mibs']} MiB/s)"

    elif state == "absent":
        image_name = module.params["image"]

        if image_name not in storage_images:
            result["msg"] = f"Image {image_name} not found"
            module.exit_json(**result)
            return

        result["changed"] = True
        result["msg"] = f"Removing {image_name}"

        if module.check_mode:
            module.exit_json(**result)
            return

        if is_connected and current_drive_image == image_name:
            client.msd_disconnect()

        try:
            client.msd_remove(image_name)
        except Exception as e:
            module.fail_json(msg=f"Failed to remove image: {e}")

        result["msg"] = f"Removed {image_name}"

    elif state == "connected":
        image_name = module.params["image"]

        if is_connected and current_drive_image == image_name and drive.get("cdrom") == module.params["cdrom"]:
            result["msg"] = f"Already connected with {image_name}"
            module.exit_json(**result)
            return

        result["changed"] = True
        result["msg"] = f"Connecting {image_name}"

        if module.check_mode:
            module.exit_json(**result)
            return

        if is_connected:
            client.msd_disconnect()

        try:
            client.msd_set_params(image_name, cdrom=module.params["cdrom"])
            client.msd_connect()
        except Exception as e:
            module.fail_json(msg=f"Failed to connect drive: {e}")

        result["msg"] = f"Connected {image_name} as {'CD-ROM' if module.params['cdrom'] else 'flash'}"

    elif state == "disconnected":
        if not is_connected:
            result["msg"] = "Already disconnected"
            module.exit_json(**result)
            return

        result["changed"] = True
        result["msg"] = "Disconnecting drive"

        if module.check_mode:
            module.exit_json(**result)
            return

        try:
            client.msd_disconnect()
        except Exception as e:
            module.fail_json(msg=f"Failed to disconnect: {e}")

        result["msg"] = "Disconnected"

    elif state == "verify":
        image_name = module.params["image"]
        existing = storage_images.get(image_name)
        checks = []
        failed = []

        # Check 1: image exists in storage
        if not existing:
            failed.append(f"Image '{image_name}' not found in MSD storage")
        else:
            checks.append("image present")

            # Check 2: image is complete
            if not existing.get("complete", False):
                failed.append(f"Image '{image_name}' exists but is not complete (interrupted upload?)")
            else:
                checks.append("complete")

            # Check 3: size matches (if expected_size provided)
            if expected_size and not _size_matches(existing, expected_size):
                failed.append(
                    f"Image size mismatch: have {existing.get('size', 0)}, "
                    f"expected {expected_size}"
                )
            elif expected_size:
                checks.append(f"size verified ({expected_size})")

        # Check 4: drive connected with correct image
        if not is_connected:
            failed.append("Drive is not connected")
        elif current_drive_image != image_name:
            failed.append(f"Drive connected but wrong image: '{current_drive_image}' (expected '{image_name}')")
        else:
            checks.append("drive connected")

        result["image"] = {"name": image_name, **(existing or {})}
        result["verify"] = {
            "passed": len(failed) == 0,
            "checks_ok": checks,
            "checks_failed": failed,
        }

        if failed:
            result["msg"] = f"MSD verify failed: {'; '.join(failed)}"
            module.fail_json(**result)
        else:
            result["msg"] = f"MSD verify passed: {', '.join(checks)}"

    # Refresh state after changes
    if result["changed"] and not module.check_mode:
        try:
            msd = client.get_msd_state()
            result["drive"] = msd.get("drive", {})
            result["storage"] = msd.get("storage", {})
        except Exception:
            pass

    if module._diff and result["changed"]:
        result["diff"] = {
            "before": json.dumps(drive, indent=2, sort_keys=True, default=str) + "\n",
            "after": json.dumps(result["drive"], indent=2, sort_keys=True, default=str) + "\n",
        }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
