# ports_ipv4_upnp

Sync IPv4 UPnP port mappings on the local IGD (same external and internal port).

```bash
# Debian / Raspberry Pi OS (preferred)
sudo apt install python3-miniupnpc

# Or via pip
pip install -r requirements.txt

# Ensure / refresh mappings (default mode; --add is the same)
python3 ports_ipv4_upnp.py --ports=1234,2345,5466
python3 ports_ipv4_upnp.py --add --ports=16022 --proto=TCP

# Both protocols
python3 ports_ipv4_upnp.py --ports=16022 --proto=BOTH

# Remove owned mappings (foreign only with --force)
python3 ports_ipv4_upnp.py --remove --ports=16022

# List IGD mappings / local interfaces / IPs
python3 ports_ipv4_upnp.py --list
python3 ports_ipv4_upnp.py --iface-list
python3 ports_ipv4_upnp.py --ip-list

# Pin internal address
python3 ports_ipv4_upnp.py --ports=16022 --iface=eth0
python3 ports_ipv4_upnp.py --ports=16022 --ip=192.168.1.10
```

Owned mappings (matching `DESCRIPTION` / `--description`) are refreshed; foreign mappings are left alone unless `--force`.

## CLI

| Flag | Meaning |
|---|---|
| `--ports=PORTS` | Comma-separated ports (required for add/remove); trailing commas OK |
| `--add` | Same as bare `--ports` (ensure/sync) |
| `--remove` | Delete mappings for `--ports` |
| `--list` | List IGD port mappings |
| `--iface-list` | List local IPv4 interfaces/addresses (needs iproute2) |
| `--ip-list` | List local IPv4 addresses (cross-platform; Windows OK) |
| `--force` | Overwrite/delete foreign mappings |
| `--proto=PROTO` | `TCP`, `UDP`, `BOTH`, or `TCP,UDP` (default `TCP`) |
| `--iface=IFACE` | Internal IP from this interface (beats `INTERNAL_IP`) |
| `--ip=IP` | Explicit internal IPv4 (beats `INTERNAL_IP`) |
| `--lease=SECONDS` | Mapping lease (overrides `LEASE_SECONDS`) |
| `--description=DESC` | Ownership tag (overrides `DESCRIPTION`) |
| `--log-level=LEVEL` | Logging level (overrides `LOG_LEVEL`) |
| `--version` | Print version |

Empty `--ports=` is a CLI error (exit 1). Positional `TCP 16022` is no longer supported.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `LEASE_SECONDS` | `3600` | Mapping lease |
| `DESCRIPTION` | `ports-ipv4-upnp` | Ownership tag |
| `INTERNAL_IP` | *(auto)* | Force internal client IP (if `--ip`/`--iface` not set) |
| `LOG_LEVEL` | `INFO` | Logging |
| `SSDP_SEARCH_TIMEOUT` | `5` | SSDP discovery timeout (s); sets miniupnpc `discoverdelay` |

Without `--ip` / `--iface` / `INTERNAL_IP`, the script picks candidates from the default route (DHCP first if several addresses). On Windows / hosts without iproute2, a UDP socket probe is used. `--iface-list` needs iproute2; use `--ip-list` on Windows.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | Bad CLI |
| 2 | No internal IPv4 / cannot list ifaces |
| 3 | Missing `miniupnpc` or no IGD |
| 4 | One or more ports failed |

## Ansible / systemd (production)

Role `external_ports_upnp_fw` should:

1. Install `python3-miniupnpc` and `python3-docopt` (or pip `docopt`).
2. Deploy this script to `/srv/config/utils_scripts/ports-ipv4-upnp.py` (or Syncthing sync path).
3. Point `ports-ipv4-upnp.service` `ExecStart` at the Python script, e.g.:

   ```ini
   ExecStart=/usr/bin/python3 /srv/config/utils_scripts/ports-ipv4-upnp.py --ports=16022 --proto=TCP
   ```

4. Pass env (`LEASE_SECONDS`, `DESCRIPTION`, …) via `Environment=` / `EnvironmentFile=` as before.
5. Deprecate `/usr/local/sbin/ports-ipv4-upnp.sh` after the Python unit is verified.

The Ansible role tree is not in this repository; apply the above where `external_ports_upnp_fw` lives.
