# ports_ipv4_upnp

Sync IPv4 UPnP port mappings on the local IGD (same external and internal port).

```bash
# Debian / Raspberry Pi OS (preferred)
sudo apt install python3-miniupnpc

# Or via pip
pip install miniupnpc

python3 ports_ipv4_upnp.py TCP|UDP [port ...]
```

Owned mappings (matching `DESCRIPTION`) are refreshed; foreign mappings are left alone.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `LEASE_SECONDS` | `3600` | Mapping lease |
| `DESCRIPTION` | `ports-ipv4-upnp` | Ownership tag |
| `INTERNAL_IP` | *(auto)* | Force internal client IP |
| `LOG_LEVEL` | `INFO` | Logging |
| `SSDP_SEARCH_TIMEOUT` | `5` | SSDP discovery timeout (s); sets miniupnpc `discoverdelay` |

Without `INTERNAL_IP`, the script picks candidates from the default route (DHCP first if several addresses). On Windows / hosts without iproute2, a UDP socket probe is used.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK (also if no ports given) |
| 1 | Bad CLI |
| 2 | No internal IPv4 |
| 3 | Missing `miniupnpc` or no IGD |
| 4 | One or more ports failed |

## Ansible / systemd (production)

Role `external_ports_upnp_fw` should:

1. Install `python3-miniupnpc` (keep CLI `miniupnpc` / `upnpc` optional for debugging).
2. Deploy this script to `/srv/config/utils_scripts/ports-ipv4-upnp.py` (or Syncthing sync path).
3. Point `ports-ipv4-upnp.service` `ExecStart` at the Python script, e.g.:

   ```ini
   ExecStart=/usr/bin/python3 /srv/config/utils_scripts/ports-ipv4-upnp.py TCP 16022
   ```

4. Pass env (`LEASE_SECONDS`, `DESCRIPTION`, …) via `Environment=` / `EnvironmentFile=` as before.
5. Deprecate `/usr/local/sbin/ports-ipv4-upnp.sh` after the Python unit is verified.

The Ansible role tree is not in this repository; apply the above where `external_ports_upnp_fw` lives.
