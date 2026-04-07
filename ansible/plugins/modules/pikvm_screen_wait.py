#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = r"""
---
module: pikvm_screen_wait
short_description: Wait for fuzzy-matched text to appear on PiKVM screen
version_added: "1.1.0"
description:
    - Polls the PiKVM streamer OCR endpoint until the expected text appears
      on screen with a similarity score >= threshold.
    - Useful for synchronising HID input with BIOS/OS state during automation.
notes:
    - "This module FAILS the task on timeout. Use C(failed_when: false) or
      C(ignore_errors: yes) on the task if you want to inspect the match
      result without failing the play."
    - "In Ansible C(--check) mode the module returns C(matched=false) without
      polling — check mode reports a result skeleton, not a real screen state."
options:
    expected:
        description: The text to wait for. Literal string, no regex.
        type: str
        required: true
    threshold:
        description: Minimum fuzzy similarity 0.0-1.0 for a match.
        type: float
        default: 0.9
    timeout:
        description: Total wait time in seconds.
        type: float
        default: 60.0
    interval:
        description: Poll interval in seconds.
        type: float
        default: 1.0
    capture_dir:
        description: Optional directory to save each poll's screenshot for debugging.
        type: path
        required: false
    case_sensitive:
        description: Whether matching is case-sensitive.
        type: bool
        default: false
extends_documentation_fragment:
    - kettleofketchup.pikvm.pikvm_auth
author:
    - "KettleOfKetchup (@kettleofketchup)"
"""

EXAMPLES = r"""
- name: Wait for BIOS POST prompt
  kettleofketchup.pikvm.pikvm_screen_wait:
    pikvm_host: edge-dev-pi.graynet.lan
    pikvm_user: admin
    pikvm_passwd: "{{ pikvm_passwd }}"
    expected: "Press F11 for Boot Menu"
    threshold: 0.85
    timeout: 60
    capture_dir: /tmp/edge-auto-screens/
  register: post_screen
"""

RETURN = r"""
changed:
    description: Always false (read-only).
    returned: always
    type: bool
matched:
    description:
        - Whether the expected text was found within the timeout.
        - When C(false), the module fails the task; use C(failed_when: false)
          or C(ignore_errors: yes) to inspect the result without failing.
    returned: always
    type: bool
score:
    description: Best similarity score observed (0.0-1.0).
    returned: always
    type: float
expected:
    description: Echo of input expected text.
    returned: always
    type: str
ocr_text:
    description: Last OCR output from the screen.
    returned: always
    type: str
elapsed_seconds:
    description: How long waiting took.
    returned: always
    type: float
captures:
    description: Paths to saved screenshots (if capture_dir was set).
    returned: always
    type: list
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.kettleofketchup.pikvm.plugins.module_utils.pikvm_client import (
    PIKVM_COMMON_ARGS,
    PiKVMModuleClient,
)


def main():
    module_args = {
        **PIKVM_COMMON_ARGS,
        "expected": dict(type="str", required=True),
        "threshold": dict(type="float", default=0.9),
        "timeout": dict(type="float", default=60.0),
        "interval": dict(type="float", default=1.0),
        "capture_dir": dict(type="path", required=False),
        "case_sensitive": dict(type="bool", default=False),
    }

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if not module.params["expected"]:
        module.fail_json(msg="pikvm_screen_wait requires a non-empty 'expected' text")

    if module.check_mode:
        module.exit_json(
            changed=False,
            matched=False,
            score=0.0,
            expected=module.params["expected"],
            ocr_text="",
            elapsed_seconds=0.0,
            captures=[],
        )
        return

    try:
        client = PiKVMModuleClient(module)
        match = client.screenshot().wait_for_text(
            module.params["expected"],
            threshold=module.params["threshold"],
            timeout=module.params["timeout"],
            interval=module.params["interval"],
            capture_dir=module.params["capture_dir"],
            case_sensitive=module.params["case_sensitive"],
        )
    except Exception as e:
        module.fail_json(msg=f"pikvm_screen_wait failed: {e}")

    result = {
        "changed": False,
        "matched": match.matched,
        "score": match.score,
        "expected": match.expected,
        "ocr_text": match.ocr_text,
        "elapsed_seconds": match.elapsed,
        "captures": [str(p) for p in match.captures],
    }
    if not match.matched:
        module.fail_json(
            msg=f"timeout waiting for {match.expected!r} (best score {match.score:.2f})",
            **result,
        )
    module.exit_json(**result)


if __name__ == "__main__":
    main()
