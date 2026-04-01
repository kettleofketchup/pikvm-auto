# Why does this file exist, and why not put this in `__main__`?
#
# You might be tempted to import things from `__main__` later,
# but that will cause problems: the code will get executed twice:
#
# - When you run `python -m pikvm_auto` python will execute
#   `__main__.py` as a script. That means there won't be any
#   `pikvm_auto.__main__` in `sys.modules`.
# - When you import `__main__` it will get executed again (as a module) because
#   there's no `pikvm_auto.__main__` in `sys.modules`.

from __future__ import annotations

import argparse
import sys
from typing import Any

from pikvm_auto._internal import debug
from pikvm_auto._internal.commands.info import run_info
from pikvm_auto._internal.config import PiKVMSettings


class _DebugInfo(argparse.Action):
    def __init__(self, nargs: int | str | None = 0, **kwargs: Any) -> None:
        super().__init__(nargs=nargs, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        debug._print_debug_info()
        sys.exit(0)


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("connection")
    group.add_argument("--host", help="PiKVM hostname or IP.")
    group.add_argument("--user", help="PiKVM username (default: admin).")
    group.add_argument("--password", help="PiKVM password.")
    group.add_argument("--schema", help="Protocol: http or https (default: https).")
    group.add_argument("--cert-trusted", action="store_true", help="Trust SSL certificate.")


def get_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser.

    Returns:
        An argparse parser.
    """
    parser = argparse.ArgumentParser(prog="pikvm-auto")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {debug._get_version()}")
    parser.add_argument("--debug-info", action=_DebugInfo, help="Print debug information.")

    subparsers = parser.add_subparsers(dest="command")

    info_parser = subparsers.add_parser("info", help="Show PiKVM system info and health status.")
    _add_connection_args(info_parser)

    return parser


def _build_settings(opts: argparse.Namespace) -> PiKVMSettings:
    overrides: dict[str, Any] = {}
    if opts.host:
        overrides["host"] = opts.host
    if opts.user:
        overrides["user"] = opts.user
    if opts.password:
        overrides["password"] = opts.password
    if opts.schema:
        overrides["schema_"] = opts.schema
    if opts.cert_trusted:
        overrides["cert_trusted"] = opts.cert_trusted
    return PiKVMSettings(**overrides)


def main(args: list[str] | None = None) -> int:
    """Run the main program.

    This function is executed when you type `pikvm-auto` or `python -m pikvm_auto`.

    Parameters:
        args: Arguments passed from the command line.

    Returns:
        An exit code.
    """
    parser = get_parser()
    opts = parser.parse_args(args=args)

    if opts.command is None:
        parser.print_help()
        return 0

    if opts.command == "info":
        settings = _build_settings(opts)
        client = settings.create_client()
        return run_info(client)

    return 0
