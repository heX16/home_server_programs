# systemd-related functions

Inventory of functions that interact with systemd (directly via `systemctl` / `journalctl`, or via unit files under `/etc/systemd/system`).

Sources:

- `install_service/install_service.py`
- `disk_manager/disk_manager.py`

---

## install_service/install_service.py

### Shell helper

#### `sh(command, *params)`

Runs a formatted shell command. Used for all `systemctl` invocations in event handlers (enable, disable, start, stop, daemon-reload, reset-failed) and for copying unit files to `/etc/systemd/system/`.

### Unit status and journal

#### `systemctl_show(unit) -> dict`

Calls `sudo systemctl show <unit>`, parses `key=value` lines into a dict.

#### `format_unit_status(props) -> str`

Formats `ActiveState/SubState` from properties returned by `systemctl show`.

#### `unit_startup_failed(props) -> bool`

Detects failed startup from `ActiveState`, `Result`, `ExecMainStatus`.

#### `fetch_unit_log_lines(unit, count=5) -> dict`

Calls `sudo journalctl -u <unit>`. Returns last log lines (newest = key 1).

#### `update_systemd_meta(systemd, unit, props) -> None`

Writes status fields into the store's `systemd` sub-dict; attaches journal lines on failure.

#### `update_units_status(store) -> None`

Iterates store entries, calls `systemctl_show` + `update_systemd_meta` for each systemd unit file.

### Unit file parsing and types

#### `parse_service_file_WIP(file_path) -> tuple` *(WIP)*

Parses `.service` for custom keys (`Type`, `install_service_enable`, `install_service_start`). Not used in main flow yet.

#### `service_has_timer(file_name) -> Path | bool`

Checks for a sibling `.timer` when the file is a `.service`.

#### `systemd_file_type(file_name) -> str | False`

Returns unit type from suffix (`service`, `timer`, `mount`, …) or `False`.

#### `systemd_file_supports_enable(file_type) -> bool`

Whether `systemctl enable` applies to this unit type.

#### `systemd_file_supports_start(file_type) -> bool`

Whether `systemctl start` applies to this unit type.

### Event handlers — `FileEventsSystemd`

#### `file_added(path)`

- `cp` unit file → `/etc/systemd/system/`
- `systemctl enable` (if supported)
- `systemctl start` on unit or on paired `.timer`

#### `file_removed(path)`

- `systemctl stop` (if supported)
- `systemctl disable` (if supported)
- `rm` from `/etc/systemd/system/`
- `systemctl daemon-reload`
- `systemctl reset-failed`

#### `file_changed(path)`

- `systemctl stop` (if supported)
- `cp` updated unit → `/etc/systemd/system/`
- `systemctl daemon-reload`
- `systemctl enable` + `systemctl start` (or start `.timer`)

#### `file_filter(path, isdir) -> bool`

File filter for comparator; no systemd calls (placeholder).

---

## disk_manager/disk_manager.py

### Low-level wrapper

#### `systemd_command(action, target, check_errcode=True) -> bool`

Runs `systemctl <action> <target>` via `run_command`. Used for: `status`, `start`, `stop`, `show`, `is-active`.

### Automount detection

#### `detect_automount_unit(mount_unit) -> str | None`

`systemctl status` on `<name>.automount`; returns unit name if it exists.

### Generic services from config

#### `start_services(services)`

`systemctl start` for each entry in config `services`.

#### `stop_services(services, timeout) -> bool`

`systemctl stop` + poll `systemctl is-active` until `inactive` or timeout.

### Properties and mount state

#### `systemd_get_properties(unit) -> dict`

`systemctl show <unit>` → dict of properties.

#### `systemd_unit_inactive(mount_unit) -> bool`

True when `ActiveState == inactive` (via `systemd_get_properties`).

#### `partition_is_mounted(systemd_mount_unit='', device='', mount_point='') -> bool`

If `systemd_mount` is set: uses `systemd_unit_inactive`. Otherwise `mountpoint -q`.

#### `get_mount_info(systemd_mount_unit) -> dict`

Reads `Where`, `BindsTo`, `ActiveEnterTimestamp`, `ActiveState` from `systemctl show`.

### Mount / unmount via systemd units

#### `mount_partition(systemd_mount_unit='', device='', mount_point='') -> bool`

When `systemd_mount` is set:

- `systemctl start` on `.automount` (if present)
- `systemctl start` on `.mount`

Otherwise classic `mount device mount_point`.

#### `unmount_partition(systemd_mount_unit='', device='', mount_point='') -> bool`

When `systemd_mount` is set:

- `systemctl stop` on `.automount` (if present)
- `systemctl stop` on `.mount`
- `systemctl status` on failure (busy detection)

Otherwise classic `umount mount_point`.

### Orchestration (uses systemd helpers)

#### `main(action, config_file)`

Uses `get_mount_info`, `partition_is_mounted`, `stop_services`, `mount_partition` / `unmount_partition`, `start_services` when config contains `systemd_mount` and/or `services`.

---

## systemctl actions used (by file)

### install_service

- `show`
- `enable` (`--quiet`)
- `disable` (`--quiet`)
- `start`
- `stop`
- `daemon-reload`
- `reset-failed`

### disk_manager

- `show`
- `status`
- `start`
- `stop`
- `is-active`
