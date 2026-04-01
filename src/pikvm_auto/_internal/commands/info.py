from __future__ import annotations

import json

from pikvm_lib.pikvm import PiKVM


def run_info(client: PiKVM) -> int:
    system_info = client.get_system_info()
    atx_state = client.get_atx_state()
    streamer_state = client.get_streamer_state()

    _print_section("System Info", system_info.get("result", {}))
    _print_section("ATX / Power Status", atx_state.get("result", {}))
    _print_section("Streamer Status", streamer_state.get("result", {}))

    return 0


def _print_section(title: str, data: dict) -> None:
    print(f"\n{'=' * 40}")
    print(f"  {title}")
    print(f"{'=' * 40}")
    print(json.dumps(data, indent=2))
