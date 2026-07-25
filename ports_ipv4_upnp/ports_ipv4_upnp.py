#!/usr/bin/env python3
'''Synchronize IPv4 UPnP port mappings (TCP|UDP).

Usage:
  ports_ipv4_upnp.py [--add] --ports=PORTS [--force] [--proto=PROTO]
                     [--iface=IFACE | --ip=IP]
                     [--lease=SECONDS] [--description=DESC] [--log-level=LEVEL]
  ports_ipv4_upnp.py --remove --ports=PORTS [--force] [--proto=PROTO]
                     [--lease=SECONDS] [--description=DESC] [--log-level=LEVEL]
  ports_ipv4_upnp.py --list [--proto=PROTO] [--log-level=LEVEL]
  ports_ipv4_upnp.py --iface-list [--log-level=LEVEL]
  ports_ipv4_upnp.py --ip-list [--log-level=LEVEL]
  ports_ipv4_upnp.py (-h | --help | --version)

Options:
  --ports=PORTS            Comma-separated ports (trailing commas OK)
  --add                    Same as bare --ports (ensure/sync)
  --remove                 Delete mappings for --ports
  --list                   List IGD mappings
  --iface-list             List local IPv4 interfaces/addresses (needs iproute2)
  --ip-list                List local IPv4 addresses (cross-platform)
  --force                  Overwrite/delete foreign mappings
  --proto=PROTO            TCP, UDP, BOTH, or TCP,UDP [default: TCP]
  --iface=IFACE            Internal IP from this interface
                           (if no --iface/--ip: auto-detect iface via default route)
  --ip=IP                  Explicit internal IPv4 (beats --iface / auto-detect)
  --lease=SECONDS          Mapping lease (overrides LEASE_SECONDS)
  --description=DESC       Ownership tag (overrides DESCRIPTION)
  --log-level=LEVEL        Logging level (overrides LOG_LEVEL)
  -h, --help               Show this help
  --version                Show version

Exit codes:
  0  success
  1  invalid CLI / protocol / port
  2  could not determine internal IPv4 / list ifaces
  3  miniupnpc missing or IGD unavailable
  4  one or more ports failed to map/refresh/remove
'''

from __future__ import annotations

import logging
import os
import sys
from typing import Callable, Optional

from docopt import docopt

from utils_net_iface import (
    build_internal_ip_candidates,
    candidates_from_iface,
    iproute2_available,
    list_all_iface_ipv4,
    list_local_ipv4,
)
from utils_upnp_port_map import MiniupnpcBackend, PortMapping, UpnpBackend, UpnpError

__version__ = '0.2.0'

# --- Configuration (edit / template-substitute as needed) ---
LEASE_SECONDS = int(os.environ.get('LEASE_SECONDS', '3600'))
DESCRIPTION = os.environ.get('DESCRIPTION', 'ports-ipv4-upnp')
INTERNAL_IP = os.environ.get('INTERNAL_IP', '')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

IGD_RETRY_CODES = {606}  # Action not authorized — often wrong internal IP

logger = logging.getLogger('ports_ipv4_upnp')


def setup_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format='%(levelname)s %(name)s: %(message)s',
        stream=sys.stderr,
        force=True,
    )


def cli_error(message: str) -> None:
    print(f'ports-ipv4-upnp: {message}', file=sys.stderr)
    sys.exit(1)


# --- CLI parsing helpers ---

def parse_ports_csv(raw: str) -> list[int]:
    parts = [part.strip() for part in str(raw).split(',') if part.strip()]
    if not parts:
        cli_error('Empty --ports= (need at least one port).')
    try:
        ports = [int(part) for part in parts]
    except ValueError:
        cli_error(f"Invalid --ports value: {raw!r}.")
    for port in ports:
        if not 1 <= port <= 65535:
            cli_error(f'Port {port} out of range (1-65535).')
    return ports


def parse_protocols(raw: str) -> list[str]:
    hint = 'expected one of: TCP, UDP, BOTH, TCP,UDP'
    text = str(raw).strip().upper()
    if text == 'TCP':
        return ['TCP']
    if text == 'UDP':
        return ['UDP']
    if text in ('BOTH', 'TCP,UDP', 'UDP,TCP'):
        return ['TCP', 'UDP']
    cli_error(f"Invalid --proto= {raw!r} ({hint}).")


def parse_lease(raw: Optional[str]) -> int:
    if not raw:
        return LEASE_SECONDS
    try:
        lease = int(raw)
    except ValueError:
        cli_error(f"Invalid --lease '{raw}'.")
    if lease < 0:
        cli_error('--lease must be >= 0.')
    return lease


def resolve_candidates(iface: Optional[str], ip: Optional[str]) -> list[str]:
    '''CLI --ip / --iface beat env INTERNAL_IP; else auto-detect.'''
    if ip:
        logger.info(f'Using explicit --ip={ip}')
        return [ip]
    if iface:
        logger.info(f'Using --iface={iface}')
        return candidates_from_iface(iface)
    return build_internal_ip_candidates(INTERNAL_IP.strip())


# --- UPnP operations ---

def create_backend() -> MiniupnpcBackend:
    backend = MiniupnpcBackend()
    igd = backend.discover()
    logger.info(f'Using miniupnpc; IGD={igd}')
    return backend


def describe(m: PortMapping) -> str:
    return f'{m.internal_ip}:{m.internal_port} desc={m.description!r}'


def find_mapping(backend: UpnpBackend, port: int, protocol: str) -> Optional[PortMapping]:
    '''Return the current mapping for port/protocol, or None. Raises UpnpError.'''
    for m in backend.list_mappings():
        if m.external_port == port and m.protocol == protocol:
            return m
    return None


def ensure_port(
    backend: UpnpBackend,
    protocol: str,
    port: int,
    ip_candidates: list[str],
    description: str,
    lease_seconds: int,
    force: bool = False,
) -> bool:
    '''Return True on success for this port.'''

    target = f'{protocol}/{port}'
    try:
        existing = find_mapping(backend, port, protocol)
    except UpnpError as exc:
        logger.error(f'Failed to list mappings before {target}: {exc}')
        return False

    try_ips = list(ip_candidates)
    if existing is not None:
        if existing.description == description:
            # Owned by this script — refresh lease; keep working IP first if known.
            if existing.internal_ip in try_ips:
                try_ips.remove(existing.internal_ip)
                try_ips.insert(0, existing.internal_ip)
            logger.info(
                f'{target} owned mapping {describe(existing)} — '
                f"refreshing (try IPs: {', '.join(try_ips)})"
            )
        elif force:
            logger.warning(
                f'{target} foreign mapping {describe(existing)} — overwriting (--force)'
            )
        elif existing.internal_ip in ip_candidates:
            logger.warning(
                f'{target} occupied by foreign desc={existing.description!r} '
                f'on our IP {existing.internal_ip} — not overwriting'
            )
            return False
        else:
            logger.warning(
                f'{target} occupied by other host {describe(existing)} — not deleting'
            )
            return False
        backend.delete_mapping(port, protocol, remote_host=existing.remote_host)

    for i, ip in enumerate(try_ips):
        try:
            backend.add_mapping(ip, port, protocol, description, lease_seconds)
            logger.info(
                f'{target} mapped to {ip} (lease={lease_seconds}s, desc={description!r})'
            )
            return True
        except UpnpError as exc:
            code_s = f' code={exc.code}' if exc.code is not None else ''
            logger.error(f'Failed to map {target} via {ip}:{code_s} — {exc}')
            if exc.code not in IGD_RETRY_CODES:
                break
            if i + 1 < len(try_ips):
                logger.warning(f'IGD code {exc.code} for {ip} — trying next internal IP')

    logger.error(f'Port {target} failed after trying IPs: {try_ips}')
    return False


def remove_port(
    backend: UpnpBackend,
    protocol: str,
    port: int,
    description: str,
    force: bool = False,
) -> bool:
    '''Return True on success (including missing mapping).'''
    target = f'{protocol}/{port}'
    try:
        existing = find_mapping(backend, port, protocol)
    except UpnpError as exc:
        logger.error(f'Failed to list mappings before remove {target}: {exc}')
        return False

    if existing is None:
        logger.info(f'{target} — no mapping to remove')
        return True

    if existing.description == description:
        logger.info(f'{target} owned mapping {describe(existing)} — deleting')
    elif force:
        logger.warning(f'{target} foreign mapping {describe(existing)} — deleting (--force)')
    else:
        logger.warning(
            f'{target} foreign mapping {describe(existing)} — not deleting (use --force)'
        )
        return False

    try:
        backend.delete_mapping(port, protocol, remote_host=existing.remote_host)
    except UpnpError as exc:
        logger.error(f'Failed to delete {target}: {exc}')
        return False
    logger.info(f'{target} deleted')
    return True


# --- Commands ---

def cmd_iface_list() -> int:
    entries = list_all_iface_ipv4()
    if not entries:
        if not iproute2_available():
            logger.error(
                'Could not list interfaces (iproute2 unavailable; '
                'use --ip-list on Windows, or pass --ip=)'
            )
            return 2
        logger.info('No non-loopback IPv4 addresses found')
        return 0

    for name, addr in entries:
        flags = 'dhcp' if addr.dynamic else 'static'
        if addr.secondary:
            flags += ',secondary'
        print(f'{name}\t{addr.ip}\t{flags}')
    return 0


def cmd_ip_list() -> int:
    ips = list_local_ipv4()
    if not ips:
        logger.error('Could not determine any local IPv4 address')
        return 2
    for ip in ips:
        print(ip)
    return 0


def cmd_list(protocols: list[str]) -> int:
    try:
        backend = create_backend()
        mappings = backend.list_mappings()
    except UpnpError as exc:
        logger.error(f'{exc}')
        return 3

    selected = [m for m in mappings if m.protocol in protocols]
    for m in selected:
        print(
            f'{m.protocol}/{m.external_port} -> '
            f'{m.internal_ip}:{m.internal_port} '
            f'desc={m.description!r} lease={m.lease_time}'
        )
    logger.info(f'Listed {len(selected)} mapping(s)')
    return 0


def run_batch(
    protocols: list[str],
    ports: list[int],
    action: Callable[[UpnpBackend, str, int], bool],
    noun: str,
) -> int:
    '''Apply action to every protocol x port pair; return exit code.'''
    try:
        backend = create_backend()
    except UpnpError as exc:
        logger.error(f'{exc}')
        return 3

    total = len(protocols) * len(ports)
    failed = sum(
        not action(backend, protocol, port)
        for protocol in protocols
        for port in ports
    )
    if failed:
        logger.error(f'Finished with {failed}/{total} {noun}(s) failed')
        return 4
    logger.info(f'Finished successfully: {total} {noun}(s) ok')
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = docopt(__doc__, argv=argv, version=f'ports-ipv4-upnp {__version__}')
    setup_logging(args['--log-level'] or LOG_LEVEL)

    if args['--iface-list']:
        return cmd_iface_list()
    if args['--ip-list']:
        return cmd_ip_list()

    protocols = parse_protocols(args['--proto'])
    if args['--list']:
        return cmd_list(protocols)

    ports = parse_ports_csv(args['--ports'])
    description = args['--description'] or DESCRIPTION
    force = bool(args['--force'])

    if args['--remove']:
        logger.info(f'Start remove: protocols={protocols} ports={ports} force={force}')
        return run_batch(
            protocols,
            ports,
            lambda backend, protocol, port: remove_port(
                backend, protocol, port, description, force=force
            ),
            noun='remove',
        )

    lease_seconds = parse_lease(args['--lease'])
    logger.info(f'Start ensure: protocols={protocols} ports={ports} force={force}')
    candidates = resolve_candidates(args['--iface'], args['--ip'])
    if not candidates:
        logger.error('Could not determine internal IPv4 address')
        return 2
    logger.info(f"Selected internal IPv4 candidate order: {', '.join(candidates)}")

    return run_batch(
        protocols,
        ports,
        lambda backend, protocol, port: ensure_port(
            backend, protocol, port, candidates, description, lease_seconds, force=force
        ),
        noun='port',
    )


if __name__ == '__main__':
    sys.exit(main())
