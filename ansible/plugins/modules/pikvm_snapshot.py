#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: pikvm_snapshot
short_description: Capture PiKVM screen snapshot
version_added: "1.0.0"
description:
    - Captures a screenshot of the connected computer's display via PiKVM streamer.
    - Optionally uses OCR to extract text from the screen.
    - Useful for verifying boot screens, installer prompts, or OS state during automation.
options:
    dest:
        description: Local directory to save the snapshot file.
        type: path
        required: true
    filename:
        description: Filename for the snapshot.
        type: str
        default: snapshot.jpeg
    ocr:
        description: Enable OCR mode. Saves extracted text instead of image.
        type: bool
        default: false
extends_documentation_fragment:
    - kettleofketchup.pikvm.pikvm_auth
author:
    - "KettleOfKetchup (@kettleofketchup)"
"""

EXAMPLES = r"""
- name: Capture current screen
  kettleofketchup.pikvm.pikvm_snapshot:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    dest: /tmp/screenshots/
    filename: boot-screen.jpeg

- name: OCR the screen contents
  kettleofketchup.pikvm.pikvm_snapshot:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    dest: /tmp/
    filename: screen-text.txt
    ocr: true
"""

RETURN = r"""
changed:
    description: Always true (new snapshot taken).
    returned: always
    type: bool
path:
    description: Full path to the saved snapshot file.
    returned: success
    type: str
    sample: "/tmp/screenshots/boot-screen.jpeg"
msg:
    description: Human-readable status message.
    returned: always
    type: str
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PiKVMModuleClient,
    PIKVM_COMMON_ARGS,
)


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "dest": dict(type="path", required=True),
        "filename": dict(type="str", default="snapshot.jpeg"),
        "ocr": dict(type="bool", default=False),
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    result = {
        "changed": True,
        "path": "",
        "msg": "",
    }

    if module.check_mode:
        result["msg"] = "Would capture snapshot"
        module.exit_json(**result)
        return

    client = PiKVMModuleClient(module)

    try:
        path = client.get_snapshot(
            module.params["dest"],
            filename=module.params["filename"],
            ocr=module.params["ocr"],
        )
        result["path"] = str(path)
        result["msg"] = f"Snapshot saved to {path}"
    except Exception as e:
        module.fail_json(msg=f"Failed to capture snapshot: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
