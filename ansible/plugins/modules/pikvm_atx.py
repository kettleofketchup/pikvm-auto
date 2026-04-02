#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: pikvm_atx
short_description: Control PiKVM ATX power state
version_added: "1.0.0"
description:
    - Control the power state of the computer connected to a PiKVM device.
    - Uses the state-aware C(/api/atx/power) endpoint for idempotent power management.
    - Supports check mode and diff mode.
options:
    state:
        description: Desired power state.
        type: str
        required: true
        choices: ["on", "off", "reboot"]
    force:
        description: Use hard actions (long press power off) instead of graceful. Has no effect on reboot.
        type: bool
        default: false
    wait:
        description: Wait for power LED to confirm state change.
        type: bool
        default: true
    timeout:
        description: Seconds to wait for power LED confirmation.
        type: int
        default: 30
extends_documentation_fragment:
    - kettleofketchup.pikvm.pikvm_auth
author:
    - "KettleOfKetchup (@kettleofketchup)"
"""

EXAMPLES = r"""
- name: Power on the machine
  kettleofketchup.pikvm.pikvm_atx:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: "on"

- name: Hard power off
  kettleofketchup.pikvm.pikvm_atx:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    state: "off"
    force: true
"""

RETURN = r"""
changed:
    description: Whether the power state was changed.
    returned: always
    type: bool
power_led:
    description: Current power LED state after action.
    returned: always
    type: bool
hdd_led:
    description: Current HDD LED state after action.
    returned: always
    type: bool
action_taken:
    description: The API action that was performed.
    returned: always
    type: str
    sample: "on"
msg:
    description: Human-readable status message.
    returned: always
    type: str
"""

import json
import time

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PiKVMModuleClient,
    PIKVM_COMMON_ARGS,
)


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "state": dict(type="str", required=True, choices=["on", "off", "reboot"]),
        "force": dict(type="bool", default=False),
        "wait": dict(type="bool", default=True),
        "timeout": dict(type="int", default=30),
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    client = PiKVMModuleClient(module)
    state = module.params["state"]
    force = module.params["force"]

    try:
        atx = client.get_atx_state()
    except Exception as e:
        module.fail_json(msg=f"Failed to get ATX state: {e}")

    power_on = atx.get("leds", {}).get("power", False)
    before_state = {"power": power_on}
    result = {
        "changed": False,
        "power_led": power_on,
        "hdd_led": atx.get("leds", {}).get("hdd", False),
        "action_taken": "none",
        "msg": "",
    }

    if state == "on":
        if power_on:
            result["msg"] = "Already powered on"
        else:
            result["changed"] = True
            result["action_taken"] = "on"
            result["msg"] = "Powering on"

    elif state == "off":
        if not power_on:
            result["msg"] = "Already powered off"
        else:
            action = "off_hard" if force else "off"
            result["changed"] = True
            result["action_taken"] = action
            result["msg"] = f"Powering off ({'hard' if force else 'graceful'})"

    elif state == "reboot":
        result["changed"] = True
        if not power_on:
            result["action_taken"] = "on"
            result["msg"] = "Machine is off, powering on"
        else:
            # No graceful vs hard distinction for reset at the API level
            result["action_taken"] = "reset_hard"
            result["msg"] = "Resetting machine"

    if module._diff:
        if state == "reboot":
            after_power = True  # reboot results in power on
        elif result["changed"]:
            after_power = not power_on
        else:
            after_power = power_on
        result["diff"] = {
            "before": json.dumps(before_state, sort_keys=True) + "\n",
            "after": json.dumps({"power": after_power}, sort_keys=True) + "\n",
        }

    if module.check_mode:
        module.exit_json(**result)
        return

    if result["changed"] and result["action_taken"] != "none":
        try:
            action = result["action_taken"]
            client.set_atx_power(action=action)
        except Exception as e:
            module.fail_json(msg=f"ATX action failed: {e}", **result)

        if module.params["wait"] and state != "reboot":
            expected = state == "on"
            current = power_on  # Initialize before loop to avoid UnboundLocalError
            deadline = time.time() + module.params["timeout"]
            while time.time() < deadline:
                try:
                    atx = client.get_atx_state()
                    current = atx.get("leds", {}).get("power", False)
                    if current == expected:
                        result["power_led"] = current
                        result["hdd_led"] = atx.get("leds", {}).get("hdd", False)
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                result["msg"] = (
                    f"Timeout waiting for power state change. Current power LED: {current}. "
                    "Consider retrying with force=true."
                )
                module.fail_json(**result)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
