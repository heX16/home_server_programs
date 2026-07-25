# ports_ipv4_upnp

CLI that ensures TCP/UDP IPv4 UPnP mappings on the LAN IGD via `miniupnpc`.

`ports_ipv4_upnp.py [--add] --ports=PORTS [--proto=PROTO] [--force] [--ip-iface|--ip] …` — docopt CLI: ensure/sync (`--ports`/`--add`), `--remove` (owned only unless `--force`), `--list`, `--list-iface` (iproute2), `--list-ip` (cross-platform IPv4 list). Discovers IGD (SSDP), resolves internal IPv4 (`--ip` > `--ip-iface` > `INTERNAL_IP` > auto; `--ip-iface` collects all non-loopback IPv4 on that iface, DHCP then static, first successful `AddPortMapping` wins), then for each port×proto: refresh if owned (`DESCRIPTION`/`--description`), skip foreign unless `--force`, else map (external = internal). Retry next candidate on IGD code 606. `--proto` accepts TCP, UDP, BOTH, or TCP,UDP.

Config via env or CLI: `LEASE_SECONDS`/`--lease`, `DESCRIPTION`/`--description`, `INTERNAL_IP`, `LOG_LEVEL`/`--log-level`, `SSDP_SEARCH_TIMEOUT`. Exit 0–4 as in the module docstring. Helpers: `utils_net_iface.py`, `utils_upnp_port_map.py`.
