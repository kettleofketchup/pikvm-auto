# PiKVM recipes

# Show system info from PiKVM device
[no-cd]
info *ARGS:
    uv run pikvm-auto info {{ ARGS }}
