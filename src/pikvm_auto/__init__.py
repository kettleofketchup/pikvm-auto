"""pikvm-auto package.

pikvmautomation, library, and ansible modules
"""

from __future__ import annotations

from pikvm_auto._internal.cli import get_parser, main
from pikvm_auto._internal.commands.hid import (
    HIDAction,
    HIDClient,
    actions_from_yaml,
    canonical_key,
)
from pikvm_auto._internal.commands.info import run_info
from pikvm_auto._internal.config import PiKVMSettings

__all__: list[str] = [
    "HIDAction",
    "HIDClient",
    "PiKVMSettings",
    "actions_from_yaml",
    "canonical_key",
    "get_parser",
    "main",
    "run_info",
]
