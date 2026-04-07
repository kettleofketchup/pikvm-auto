#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: pikvm_hid
short_description: Send keyboard input via PiKVM HID
version_added: "1.1.0"
description:
    - Sends HID keyboard events to the connected machine via PiKVM kvmd HID API.
    - Supports single key tap, chords (shortcut), text typing, and mixed
      sequences via the actions list.
options:
    actions:
        description: Ordered list of HID actions to play.
        type: list
        elements: dict
        required: false
    key:
        description: Sugar for a single key tap (alternative to actions).
        type: str
        required: false
    shortcut:
        description: Sugar for a single chord (alternative to actions).
        type: list
        elements: str
        required: false
    text:
        description: Sugar for typing a string (alternative to actions).
        type: str
        required: false
extends_documentation_fragment:
    - kettleofketchup.pikvm.pikvm_auth
author:
    - "KettleOfKetchup (@kettleofketchup)"
"""

EXAMPLES = r"""
- name: Boot menu navigation
  kettleofketchup.pikvm.pikvm_hid:
    pikvm_host: edge-dev-pi.graynet.lan
    pikvm_user: admin
    pikvm_passwd: "{{ pikvm_passwd }}"
    actions:
      - { kind: wait, seconds: 8 }
      - { kind: key, key: F11 }
      - { kind: wait, seconds: 1 }
      - { kind: key, key: down }
      - { kind: key, key: enter }

- name: Single key tap (sugar)
  kettleofketchup.pikvm.pikvm_hid:
    pikvm_host: edge-dev-pi.graynet.lan
    pikvm_user: admin
    pikvm_passwd: "{{ pikvm_passwd }}"
    key: F11
"""

RETURN = r"""
changed:
    description: Always false (HID input is fire-and-forget).
    returned: always
    type: bool
actions_sent:
    description: Count of actions played.
    returned: always
    type: int
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PIKVM_COMMON_ARGS,
    PiKVMModuleClient,
)


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "actions": dict(type="list", elements="dict", required=False),
        "key": dict(type="str", required=False),
        "shortcut": dict(type="list", elements="str", required=False),
        "text": dict(type="str", required=False),
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        mutually_exclusive=[["actions", "key", "shortcut", "text"]],
        required_one_of=[["actions", "key", "shortcut", "text"]],
    )

    # Build the action list — sugar fields synthesise a single-action list
    raw_actions = module.params["actions"]
    if raw_actions is None:
        if module.params["key"]:
            raw_actions = [{"kind": "key", "key": module.params["key"]}]
        elif module.params["shortcut"]:
            raw_actions = [{"kind": "shortcut", "keys": module.params["shortcut"]}]
        elif module.params["text"] is not None:
            raw_actions = [{"kind": "text", "text": module.params["text"]}]

    if module.check_mode:
        module.exit_json(changed=False, actions_sent=len(raw_actions))
        return

    try:
        from pikvm_auto._internal.commands.hid import actions_from_yaml
        actions = actions_from_yaml(raw_actions)
        client = PiKVMModuleClient(module)
        client.hid().play(actions)
    except Exception as e:
        module.fail_json(msg=f"pikvm_hid failed: {e}")

    module.exit_json(changed=False, actions_sent=len(actions))


if __name__ == "__main__":
    main()
