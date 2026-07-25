# ports_ipv4_upnp

CLI that ensures TCP/UDP IPv4 UPnP mappings on the LAN IGD via `miniupnpc`.

`ports_ipv4_upnp.py [--add] --ports=PORTS [--proto=PROTO] [--force] [--iface|--ip] …` — docopt CLI: ensure/sync (`--ports`/`--add`), `--remove` (owned only unless `--force`), `--list`, `--iface-list` (iproute2), `--ip-list` (cross-platform IPv4 list). Discovers IGD (SSDP), resolves internal IPv4 (`--ip` > `--iface` > `INTERNAL_IP` > auto), then for each port×proto: refresh if owned (`DESCRIPTION`/`--description`), skip foreign unless `--force`, else `AddPortMapping` (external = internal). Retry internal IPs on IGD code 606. `--proto` accepts TCP, UDP, BOTH, or TCP,UDP.

Config via env or CLI: `LEASE_SECONDS`/`--lease`, `DESCRIPTION`/`--description`, `INTERNAL_IP`, `LOG_LEVEL`/`--log-level`, `SSDP_SEARCH_TIMEOUT`. Exit 0–4 as in the module docstring. Helpers: `net_iface.py`, `upnp_port_map.py`.
