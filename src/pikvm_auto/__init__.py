"""pikvm-auto package.

pikvmautomation, library, and ansible modules
"""

from __future__ import annotations

from pikvm_auto._internal.cli import get_parser, main

__all__: list[str] = ["get_parser", "main"]
