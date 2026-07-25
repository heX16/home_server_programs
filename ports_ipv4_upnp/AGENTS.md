# ports_ipv4_upnp

CLI that ensures TCP/UDP IPv4 UPnP mappings on the LAN IGD via `miniupnpc`.

`ports_ipv4_upnp.py TCP|UDP [port ...]` — discovers IGD (SSDP), resolves internal IPv4 candidates, then for each port: refresh if owned (`DESCRIPTION`), skip if foreign, else `AddPortMapping` (external port = internal port). Retry internal IPs on IGD code 606 (`Action not authorized`).

Config via env: `LEASE_SECONDS`, `DESCRIPTION`, `INTERNAL_IP`, `LOG_LEVEL`, `SSDP_SEARCH_TIMEOUT` (mapped to miniupnpc `discoverdelay` in ms). Exit 0–4 as in the module docstring.
