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
    - Supports check mode and diff mode.
options:
    state:
        description:
            - Desired state of the MSD resource.
            - C(present) uploads image if missing.
            - C(absent) removes image from storage.
            - C(connected) mounts virtual drive.
            - C(disconnected) unmounts virtual drive.
        type: str
        required: true
        choices: ["present", "absent", "connected", "disconnected"]
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
msg:
    description: Human-readable status message.
    returned: always
    type: str
"""

import json
import os

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


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "state": dict(type="str", required=True, choices=["present", "absent", "connected", "disconnected"]),
        "image": dict(type="str", required=False),
        "image_url": dict(type="str", required=False),
        "image_path": dict(type="path", required=False),
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
        ],
    )

    client = PiKVMModuleClient(module)
    state = module.params["state"]

    try:
        msd = client.get_msd_state()
    except Exception as e:
        module.fail_json(msg=f"Failed to get MSD state: {e}")

    result = {
        "changed": False,
        "drive": msd.get("drive", {}),
        "storage": msd.get("storage", {}),
        "msg": "",
    }

    drive = msd.get("drive", {})
    is_connected = drive.get("connected", False)
    # IMPORTANT: drive.image is a string (image filename), not a dict
    current_drive_image = drive.get("image") or None
    storage_images = msd.get("storage", {}).get("images", {})

    if state == "present":
        image_name = _get_image_name(module.params)
        if not image_name:
            module.fail_json(msg="Cannot determine image name. Provide image, image_url, or image_path.")

        existing = storage_images.get(image_name)
        if existing and existing.get("complete", False):
            result["msg"] = f"Image {image_name} already present and complete"
            result["image"] = {"name": image_name, **existing}
            module.exit_json(**result)
            return

        result["changed"] = True
        result["msg"] = f"Uploading {image_name}"

        if module.check_mode:
            module.exit_json(**result)
            return

        # Remove incomplete image if exists
        if existing and not existing.get("complete", False):
            if is_connected and current_drive_image == image_name:
                client.msd_disconnect()
            client.msd_remove(image_name)

        # Disconnect before upload if drive is connected
        if is_connected:
            client.msd_disconnect()

        try:
            if module.params.get("image_url"):
                client.msd_upload_remote(module.params["image_url"], image_name=image_name)
            elif module.params.get("image_path"):
                client.msd_upload_file(module.params["image_path"], image_name=image_name)
        except Exception as e:
            module.fail_json(msg=f"Upload failed: {e}")

        try:
            client.msd_set_params(image_name, cdrom=module.params["cdrom"])
        except Exception as e:
            module.fail_json(msg=f"Failed to set MSD params: {e}")

        result["image"] = {"name": image_name}
        result["msg"] = f"Uploaded {image_name}"

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
