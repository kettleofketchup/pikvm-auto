#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: pikvm_info
short_description: Gather PiKVM device facts
version_added: "1.0.0"
description:
    - Gathers system information, ATX power state, MSD storage state, and streamer status from a PiKVM device.
    - Sets C(ansible_facts.pikvm) with the gathered data.
    - This module never makes changes (always C(changed=false)).
options:
    gather:
        description:
            - List of subsystems to query.
            - Supported values are C(system), C(atx), C(msd), C(streamer).
        type: list
        elements: str
        default: ["system", "atx", "msd", "streamer"]
extends_documentation_fragment:
    - kettleofketchup.pikvm.pikvm_auth
author:
    - "KettleOfKetchup (@kettleofketchup)"
"""

EXAMPLES = r"""
- name: Gather all PiKVM facts
  kettleofketchup.pikvm.pikvm_info:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
  register: pikvm_facts

- name: Gather only system and ATX info
  kettleofketchup.pikvm.pikvm_info:
    pikvm_host: pikvm.local
    pikvm_user: admin
    pikvm_passwd: "{{ vault_pikvm_passwd }}"
    gather:
      - system
      - atx
"""

RETURN = r"""
ansible_facts:
    description: Facts about the PiKVM device.
    returned: always
    type: dict
    contains:
        pikvm:
            description: PiKVM device information.
            returned: always
            type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PiKVMModuleClient,
    PIKVM_COMMON_ARGS,
)


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "gather": dict(
            type="list",
            elements="str",
            default=["system", "atx", "msd", "streamer"],
        ),
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    client = PiKVMModuleClient(module)
    gather = module.params["gather"]
    facts = {}

    gather_map = {
        "system": client.get_system_info,
        "atx": client.get_atx_state,
        "msd": client.get_msd_state,
        "streamer": client.get_streamer_state,
    }

    for subsystem in gather:
        if subsystem in gather_map:
            try:
                facts[subsystem] = gather_map[subsystem]()
            except Exception as e:
                module.fail_json(msg=f"Failed to gather {subsystem} info: {e}")

    module.exit_json(changed=False, ansible_facts={"pikvm": facts})


if __name__ == "__main__":
    main()
