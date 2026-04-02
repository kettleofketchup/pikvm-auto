# kettleofketchup.pikvm

Ansible collection for managing PiKVM KVM-over-IP devices.

## Requirements

- ansible-core >= 2.15
- pikvm-lib >= 0.5.0 (`pip install pikvm-lib`)

## Modules

- `pikvm_info` — Gather device facts
- `pikvm_msd` — Manage ISO images and virtual drives
- `pikvm_atx` — Control power state
- `pikvm_snapshot` — Capture screen snapshots
