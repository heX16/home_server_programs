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
  --ip=IP                  Explicit internal IPv4
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
from typing import Optional

from docopt import docopt

from net_iface import (
    build_internal_ip_candidates,
    candidates_from_iface,
    iproute2_available,
    list_all_iface_ipv4,
    list_local_ipv4,
)
from upnp_port_map import MiniupnpcBackend, PortMapping, UpnpBackend, UpnpError

__version__ = '0.2.0'

# --- Configuration (edit / template-substitute as needed) ---
LEASE_SECONDS = int(os.environ.get('LEASE_SECONDS', '3600'))
DESCRIPTION = os.environ.get('DESCRIPTION', 'ports-ipv4-upnp')
INTERNAL_IP = os.environ.get('INTERNAL_IP', '')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

IGD_RETRY_CODES = {606}  # Action not authorized — often wrong internal IP

logger = logging.getLogger('ports_ipv4_upnp')


def setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logger.setLevel(level)


def cli_error(message: str) -> None:
    print(f'ports-ipv4-upnp: {message}', file=sys.stderr)
    sys.exit(1)


def parse_ports_csv(raw: str) -> list[int]:
    ports: list[int] = []
    for part in str(raw).split(','):
        part = part.strip()
        if not part:
            continue
        try:
            port = int(part)
        except ValueError:
            cli_error(f"Invalid port '{part}'.")
        if port < 1 or port > 65535:
            cli_error(f'Port {port} out of range (1-65535).')
        ports.append(port)
    if not ports:
        cli_error('Empty --ports= (need at least one port).')
    return ports


def parse_protocols(raw: str) -> list[str]:
    text = str(raw).strip().upper()
    if not text:
        cli_error('Empty --proto= (expected TCP, UDP, BOTH, or TCP,UDP).')
    if text == 'BOTH':
        return ['TCP', 'UDP']
    protocols: list[str] = []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if part not in ('TCP', 'UDP'):
            cli_error(
                f"Invalid protocol '{part}' "
                '(expected TCP, UDP, BOTH, or TCP,UDP).'
            )
        if part not in protocols:
            protocols.append(part)
    if not protocols:
        cli_error('Empty --proto= (expected TCP, UDP, BOTH, or TCP,UDP).')
    return protocols


def resolve_candidates(
    iface: Optional[str],
    ip: Optional[str],
) -> list[str]:
    '''CLI --ip / --iface beat env INTERNAL_IP; else auto-detect.'''
    if ip:
        logger.info('Using explicit --ip=%s', ip)
        return [ip]
    if iface:
        logger.info('Using --iface=%s', iface)
        return candidates_from_iface(iface)
    return build_internal_ip_candidates(INTERNAL_IP.strip())


def create_backend() -> MiniupnpcBackend:
    backend = MiniupnpcBackend()
    igd = backend.discover()
    logger.info('Using miniupnpc; IGD=%s', igd)
    return backend


def find_mapping(
    mappings: list[PortMapping],
    port: int,
    protocol: str,
) -> Optional[PortMapping]:
    for m in mappings:
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
    try:
        mappings = backend.list_mappings()
    except UpnpError as exc:
        logger.error(
            'Failed to list mappings before %s/%s: %s',
            protocol,
            port,
            exc,
        )
        return False

    try_ips = list(ip_candidates)
    existing = find_mapping(mappings, port, protocol)
    if existing is not None:
        if existing.description == description:
            # Owned by this script — refresh lease; keep working IP first if known.
            if existing.internal_ip in try_ips:
                try_ips = [existing.internal_ip] + [
                    ip for ip in try_ips if ip != existing.internal_ip
                ]
            logger.info(
                '%s/%s owned mapping %s:%s desc=%r — refreshing (try IPs: %s)',
                protocol,
                port,
                existing.internal_ip,
                existing.internal_port,
                existing.description,
                ', '.join(try_ips),
            )
            backend.delete_mapping(
                port,
                protocol,
                remote_host=existing.remote_host,
            )
        elif force:
            logger.warning(
                '%s/%s foreign mapping %s:%s desc=%r — overwriting (--force)',
                protocol,
                port,
                existing.internal_ip,
                existing.internal_port,
                existing.description,
            )
            backend.delete_mapping(
                port,
                protocol,
                remote_host=existing.remote_host,
            )
        elif existing.internal_ip in ip_candidates:
            logger.warning(
                '%s/%s occupied by foreign desc=%r on our IP %s — not overwriting',
                protocol,
                port,
                existing.description,
                existing.internal_ip,
            )
            return False
        else:
            logger.warning(
                '%s/%s occupied by other host %s:%s desc=%r — not deleting',
                protocol,
                port,
                existing.internal_ip,
                existing.internal_port,
                existing.description,
            )
            return False

    last_err: Optional[UpnpError] = None
    for ip in try_ips:
        try:
            backend.add_mapping(ip, port, protocol, description, lease_seconds)
            logger.info(
                '%s/%s mapped to %s (lease=%ss, desc=%r)',
                protocol,
                port,
                ip,
                lease_seconds,
                description,
            )
            return True
        except UpnpError as exc:
            last_err = exc
            code_s = f' code={exc.code}' if exc.code is not None else ''
            logger.error(
                'Failed to map %s/%s via %s:%s — %s',
                protocol,
                port,
                ip,
                code_s,
                exc,
            )
            if exc.code in IGD_RETRY_CODES and ip != try_ips[-1]:
                logger.warning(
                    'IGD code %s for %s — trying next internal IP',
                    exc.code,
                    ip,
                )
                continue
            # Non-retryable or last candidate
            if exc.code not in IGD_RETRY_CODES:
                break

    if last_err is not None:
        logger.error('Port %s/%s failed after trying IPs: %s', protocol, port, try_ips)
    return False


def remove_port(
    backend: UpnpBackend,
    protocol: str,
    port: int,
    description: str,
    force: bool = False,
) -> bool:
    '''Return True on success (including missing mapping).'''
    try:
        mappings = backend.list_mappings()
    except UpnpError as exc:
        logger.error(
            'Failed to list mappings before remove %s/%s: %s',
            protocol,
            port,
            exc,
        )
        return False

    existing = find_mapping(mappings, port, protocol)
    if existing is None:
        logger.info('%s/%s — no mapping to remove', protocol, port)
        return True

    if existing.description == description:
        logger.info(
            '%s/%s owned mapping %s:%s desc=%r — deleting',
            protocol,
            port,
            existing.internal_ip,
            existing.internal_port,
            existing.description,
        )
    elif force:
        logger.warning(
            '%s/%s foreign mapping %s:%s desc=%r — deleting (--force)',
            protocol,
            port,
            existing.internal_ip,
            existing.internal_port,
            existing.description,
        )
    else:
        logger.warning(
            '%s/%s foreign mapping %s:%s desc=%r — not deleting (use --force)',
            protocol,
            port,
            existing.internal_ip,
            existing.internal_port,
            existing.description,
        )
        return False

    try:
        backend.delete_mapping(
            port,
            protocol,
            remote_host=existing.remote_host,
        )
    except UpnpError as exc:
        logger.error('Failed to delete %s/%s: %s', protocol, port, exc)
        return False
    logger.info('%s/%s deleted', protocol, port)
    return True


def process_ports(
    backend: UpnpBackend,
    protocols: list[str],
    ports: list[int],
    candidates: list[str],
    description: str,
    lease_seconds: int,
    force: bool,
) -> int:
    '''Ensure all ports for all protocols; return number of failures.'''
    failed = 0
    for protocol in protocols:
        for port in ports:
            ok = ensure_port(
                backend,
                protocol,
                port,
                candidates,
                description,
                lease_seconds,
                force=force,
            )
            if not ok:
                failed += 1
    return failed


def process_removes(
    backend: UpnpBackend,
    protocols: list[str],
    ports: list[int],
    description: str,
    force: bool,
) -> int:
    '''Remove all ports for all protocols; return number of failures.'''
    failed = 0
    for protocol in protocols:
        for port in ports:
            ok = remove_port(
                backend,
                protocol,
                port,
                description,
                force=force,
            )
            if not ok:
                failed += 1
    return failed


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
    except UpnpError as exc:
        logger.error('%s', exc)
        return 3

    try:
        mappings = backend.list_mappings()
    except UpnpError as exc:
        logger.error('Failed to list mappings: %s', exc)
        return 3

    allowed = set(protocols)
    printed = 0
    for m in mappings:
        if m.protocol not in allowed:
            continue
        print(
            f'{m.protocol}/{m.external_port} -> '
            f'{m.internal_ip}:{m.internal_port} '
            f'desc={m.description!r} lease={m.lease_time}'
        )
        printed += 1
    logger.info('Listed %s mapping(s)', printed)
    return 0


def run_ensure(
    protocols: list[str],
    ports: list[int],
    candidates: list[str],
    description: str,
    lease_seconds: int,
    force: bool,
) -> int:
    logger.info(
        'Start ensure: protocols=%s ports=%s force=%s',
        protocols,
        ports,
        force,
    )
    if not candidates:
        logger.error('Could not determine internal IPv4 address')
        return 2
    logger.info('Selected internal IPv4 candidate order: %s', ', '.join(candidates))

    try:
        backend = create_backend()
    except UpnpError as exc:
        logger.error('%s', exc)
        return 3

    total = len(protocols) * len(ports)
    failed = process_ports(
        backend,
        protocols,
        ports,
        candidates,
        description,
        lease_seconds,
        force,
    )
    if failed:
        logger.error('Finished with %s/%s port(s) failed', failed, total)
        return 4

    logger.info('Finished successfully: %s port(s) ok', total)
    return 0


def run_remove(
    protocols: list[str],
    ports: list[int],
    description: str,
    force: bool,
) -> int:
    logger.info(
        'Start remove: protocols=%s ports=%s force=%s',
        protocols,
        ports,
        force,
    )
    try:
        backend = create_backend()
    except UpnpError as exc:
        logger.error('%s', exc)
        return 3

    total = len(protocols) * len(ports)
    failed = process_removes(
        backend,
        protocols,
        ports,
        description,
        force,
    )
    if failed:
        logger.error('Finished with %s/%s remove(s) failed', failed, total)
        return 4

    logger.info('Finished successfully: %s remove(s) ok', total)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = docopt(
        __doc__,
        argv=argv,
        version=f'ports-ipv4-upnp {__version__}',
    )

    log_level = args['--log-level'] or LOG_LEVEL
    setup_logging(log_level)

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
        return run_remove(protocols, ports, description, force)

    lease_raw = args['--lease']
    if lease_raw:
        try:
            lease_seconds = int(lease_raw)
        except ValueError:
            cli_error(f"Invalid --lease '{lease_raw}'.")
        if lease_seconds < 0:
            cli_error('--lease must be >= 0.')
    else:
        lease_seconds = LEASE_SECONDS

    candidates = resolve_candidates(args['--iface'], args['--ip'])
    return run_ensure(
        protocols,
        ports,
        candidates,
        description,
        lease_seconds,
        force,
    )


if __name__ == '__main__':
    sys.exit(main())
