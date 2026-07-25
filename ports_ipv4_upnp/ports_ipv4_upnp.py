#!/usr/bin/env python3
'''Synchronize IPv4 UPnP port mappings (TCP|UDP).

Usage:
  ports-ipv4-upnp.py TCP|UDP [port ...]

Exit codes:
  0  success (no ports, or all ports in desired state)
  1  invalid CLI / protocol / port
  2  could not determine internal IPv4
  3  miniupnpc missing or IGD unavailable
  4  one or more ports failed to map/refresh
'''

from __future__ import annotations

import logging
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

# --- Configuration (edit / template-substitute as needed) ---
LEASE_SECONDS = int(os.environ.get('LEASE_SECONDS', '3600'))
DESCRIPTION = os.environ.get('DESCRIPTION', 'ports-ipv4-upnp')
INTERNAL_IP = os.environ.get('INTERNAL_IP', '')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

ROUTE_PROBE_DST = '1.1.1.1'
IGD_RETRY_CODES = {606}  # Action not authorized — often wrong internal IP
SSDP_SEARCH_TIMEOUT = int(os.environ.get('SSDP_SEARCH_TIMEOUT', '5'))

logger = logging.getLogger('ports_ipv4_upnp')


@dataclass(frozen=True)
class PortMapping:
    protocol: str
    external_port: int
    internal_ip: str
    internal_port: int
    description: str
    remote_host: str
    lease_time: int


@dataclass(frozen=True)
class IfaceAddr:
    ip: str
    dynamic: bool
    secondary: bool


class UpnpError(Exception):
    '''UPnP operation failed.'''

    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code


class UpnpBackend:
    '''Abstract sync IPv4 IGD backend.'''

    def discover(self) -> str:
        raise NotImplementedError

    def list_mappings(self) -> list[PortMapping]:
        raise NotImplementedError

    def add_mapping(
        self,
        internal_ip: str,
        port: int,
        protocol: str,
        description: str,
        lease_seconds: int,
    ) -> None:
        raise NotImplementedError

    def delete_mapping(self, port: int, protocol: str, remote_host: str = '') -> None:
        raise NotImplementedError


class MiniupnpcBackend(UpnpBackend):
    '''IGD backend based on miniupnpc (synchronous).'''

    def __init__(self):
        try:
            import miniupnpc
        except ImportError as exc:
            raise UpnpError(
                'miniupnpc is not installed '
                '(apt install python3-miniupnpc / pip install miniupnpc)'
            ) from exc

        self._miniupnpc = miniupnpc
        self._upnp: Optional[object] = None

    def discover(self) -> str:
        upnp = self._miniupnpc.UPnP()
        # miniupnpc discoverdelay is milliseconds; env timeout is seconds.
        upnp.discoverdelay = max(1, SSDP_SEARCH_TIMEOUT) * 1000
        try:
            found = upnp.discover()
        except Exception as exc:
            raise UpnpError(f'UPnP discovery failed: {exc}') from exc

        if not found:
            raise UpnpError('No UPnP IGD devices discovered')

        try:
            location = upnp.selectigd()
        except Exception as exc:
            raise UpnpError(f'IGD not available: {exc}') from exc

        if not location:
            raise UpnpError('IGD not available (selectigd returned empty)')

        self._upnp = upnp
        lan = getattr(upnp, 'lanaddr', '') or ''
        try:
            wan = upnp.externalipaddress() or ''
        except Exception:
            wan = ''
        detail = f'{location}'
        if lan or wan:
            detail = f'{location} (lan={lan or "?"}, wan={wan or "?"})'
        return detail

    def _require_upnp(self):
        if self._upnp is None:
            raise UpnpError('IGD not discovered yet')
        return self._upnp

    def list_mappings(self) -> list[PortMapping]:
        upnp = self._require_upnp()
        out: list[PortMapping] = []
        idx = 0
        while idx < 1024:
            try:
                entry = upnp.getgenericportmapping(idx)
            except Exception as exc:
                # Some IGDs raise at end-of-list instead of returning None.
                logger.debug(
                    'GetGenericPortMappingEntry(%s) ended: %s',
                    idx,
                    exc,
                )
                break

            if entry is None:
                break

            try:
                # (ext_port, proto, (int_ip, int_port), desc, enabled, remote, lease)
                ext_port = int(entry[0])
                protocol = str(entry[1]).upper()
                internal = entry[2]
                if isinstance(internal, (tuple, list)) and len(internal) >= 2:
                    internal_ip = str(internal[0])
                    internal_port = int(internal[1])
                else:
                    internal_ip = str(internal)
                    internal_port = ext_port
                # NAT-PMP/PCP may report NewInternalPort=0; treat as external port.
                if internal_port == 0:
                    internal_port = ext_port
                description = str(entry[3] or '')
                remote_host = str(entry[5] or '') if len(entry) > 5 else ''
                lease_time = int(entry[6]) if len(entry) > 6 and entry[6] not in (None, '') else 0
            except (TypeError, ValueError, IndexError) as exc:
                raise UpnpError(
                    f'Failed to parse mapping at index {idx}: {entry!r} ({exc})',
                    code=_extract_igd_code_from_exc(exc),
                ) from exc

            out.append(
                PortMapping(
                    protocol=protocol,
                    external_port=ext_port,
                    internal_ip=internal_ip,
                    internal_port=internal_port,
                    description=description,
                    remote_host=remote_host,
                    lease_time=lease_time,
                )
            )
            idx += 1
        return out

    def add_mapping(
        self,
        internal_ip: str,
        port: int,
        protocol: str,
        description: str,
        lease_seconds: int,
    ) -> None:
        upnp = self._require_upnp()
        try:
            # Signature: (ext_port, proto, int_ip, int_port, desc, remote_host[, lease])
            ok = upnp.addportmapping(
                port,
                protocol,
                internal_ip,
                port,
                description,
                '',
                int(lease_seconds),
            )
        except Exception as exc:
            code = _extract_igd_code_from_exc(exc)
            raise UpnpError(f'AddPortMapping failed: {exc}', code=code) from exc

        if not ok:
            raise UpnpError('AddPortMapping returned false')

    def delete_mapping(
        self,
        port: int,
        protocol: str,
        remote_host: str = '',
    ) -> None:
        upnp = self._require_upnp()
        candidates = [remote_host or '']
        if '0.0.0.0' not in candidates:
            candidates.append('0.0.0.0')
        if '' not in candidates:
            candidates.append('')

        for rh in candidates:
            try:
                if rh:
                    ok = upnp.deleteportmapping(port, protocol, rh)
                else:
                    ok = upnp.deleteportmapping(port, protocol)
                if ok:
                    return
                logger.debug(
                    'DeletePortMapping %s/%s remote=%r returned false',
                    protocol,
                    port,
                    rh,
                )
            except Exception as exc:
                logger.debug(
                    'DeletePortMapping %s/%s remote=%r: %s',
                    protocol,
                    port,
                    rh,
                    exc,
                )


def _extract_igd_code(text: str) -> Optional[int]:
    m = re.search(r'\b(?:code\s+)?(\d{3})\b', text)
    if m:
        code = int(m.group(1))
        if 600 <= code <= 799:
            return code
    # miniupnpc often returns the UPnP description without the numeric code.
    lowered = text.lower()
    if 'action not authorized' in lowered:
        return 606
    return None


def _extract_igd_code_from_exc(exc: BaseException) -> Optional[int]:
    code = getattr(exc, 'error_code', None)
    if isinstance(code, int) and 600 <= code <= 799:
        return code
    return _extract_igd_code(str(exc))


def setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logger.setLevel(level)


def parse_args(argv: list[str]) -> tuple[str, list[int]]:
    if len(argv) < 1:
        print(
            'ports-ipv4-upnp: Usage: ports-ipv4-upnp.py TCP|UDP [port ...]',
            file=sys.stderr,
        )
        sys.exit(1)

    proto = argv[0].upper()
    if proto not in ('TCP', 'UDP'):
        print(
            f"ports-ipv4-upnp: Invalid protocol '{argv[0]}' (expected TCP or UDP).",
            file=sys.stderr,
        )
        sys.exit(1)

    ports: list[int] = []
    for raw in argv[1:]:
        try:
            port = int(raw)
        except ValueError:
            print(f"ports-ipv4-upnp: Invalid port '{raw}'.", file=sys.stderr)
            sys.exit(1)
        if port < 1 or port > 65535:
            print(
                f'ports-ipv4-upnp: Port {port} out of range (1-65535).',
                file=sys.stderr,
            )
            sys.exit(1)
        ports.append(port)
    return proto, ports


def _run_ip(*args: str) -> str:
    try:
        return subprocess.check_output(
            ['ip', *args],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return ''


def route_src_and_dev(dst: str = ROUTE_PROBE_DST) -> tuple[Optional[str], Optional[str]]:
    out = _run_ip('-4', 'route', 'get', dst)
    if not out:
        return None, None
    tokens = out.split()
    src = None
    dev = None
    for i, tok in enumerate(tokens):
        if tok == 'src' and i + 1 < len(tokens):
            src = tokens[i + 1]
        elif tok == 'dev' and i + 1 < len(tokens):
            dev = tokens[i + 1]
    return src, dev


def route_src_via_socket(dst: str = ROUTE_PROBE_DST) -> Optional[str]:
    '''Fallback when iproute2 is unavailable (e.g. Windows).'''
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((dst, 80))
            ip = sock.getsockname()[0]
    except OSError:
        return None
    if not ip or ip.startswith('127.'):
        return None
    return ip


def list_iface_ipv4(iface: str) -> list[IfaceAddr]:
    # Prefer JSON (iproute2); fall back to text parse.
    out = _run_ip('-4', '-j', 'addr', 'show', 'dev', iface)
    addrs: list[IfaceAddr] = []
    if out:
        try:
            import json

            data = json.loads(out)
            for link in data:
                for info in link.get('addr_info', []):
                    if info.get('family') != 'inet':
                        continue
                    local = info.get('local')
                    if not local or local.startswith('127.'):
                        continue
                    addrs.append(
                        IfaceAddr(
                            ip=local,
                            dynamic=bool(info.get('dynamic', False)),
                            secondary=bool(info.get('secondary', False)),
                        )
                    )
            return addrs
        except (ValueError, TypeError, KeyError):
            pass

    text = _run_ip('-4', 'addr', 'show', 'dev', iface)
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('inet '):
            continue
        parts = line.split()
        ip = parts[1].split('/')[0]
        if ip.startswith('127.'):
            continue
        addrs.append(
            IfaceAddr(
                ip=ip,
                dynamic='dynamic' in parts,
                secondary='secondary' in parts,
            )
        )
    return addrs


def build_internal_ip_candidates(explicit_ip: str) -> list[str]:
    if explicit_ip:
        logger.info('Using explicit INTERNAL_IP=%s', explicit_ip)
        return [explicit_ip]

    src, dev = route_src_and_dev()
    if not src:
        src = route_src_via_socket()
        if not src:
            return []
        logger.info('Using socket-probed internal IPv4=%s (no iproute2)', src)
        return [src]

    candidates: list[str] = []
    if dev:
        iface_addrs = list_iface_ipv4(dev)
        logger.info(
            'Route to %s via %s src=%s; iface addresses: %s',
            ROUTE_PROBE_DST,
            dev,
            src,
            ', '.join(
                f"{a.ip}({'dhcp' if a.dynamic else 'static'}"
                f"{',secondary' if a.secondary else ''})"
                for a in iface_addrs
            )
            or '(none)',
        )
        if len(iface_addrs) > 1:
            # Prefer DHCP/dynamic first; within each group keep route src first.
            def prefer_src(ips: list[str]) -> list[str]:
                if src in ips:
                    return [src] + [ip for ip in ips if ip != src]
                return list(ips)

            dhcp = [a.ip for a in iface_addrs if a.dynamic]
            static = [a.ip for a in iface_addrs if not a.dynamic]
            candidates = prefer_src(dhcp) + prefer_src(static)
            logger.info(
                'Multiple IPv4 on %s — trying DHCP first, then others: %s',
                dev,
                ', '.join(candidates),
            )
        elif iface_addrs:
            candidates = [iface_addrs[0].ip]
        else:
            candidates = [src]
    else:
        candidates = [src]

    # Ensure route src is present somewhere as fallback.
    if src and src not in candidates:
        candidates.append(src)
    return candidates


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


def process_ports(
    backend: UpnpBackend,
    protocol: str,
    ports: list[int],
    candidates: list[str],
    description: str,
    lease_seconds: int,
) -> int:
    '''Process all ports sequentially; return number of failures.'''
    failed = 0
    for port in ports:
        ok = ensure_port(
            backend,
            protocol,
            port,
            candidates,
            description,
            lease_seconds,
        )
        if not ok:
            failed += 1
    return failed


def run(protocol: str, ports: list[int]) -> int:
    logger.info('Start: protocol=%s ports=%s', protocol, ports)

    candidates = build_internal_ip_candidates(INTERNAL_IP.strip())
    if not candidates:
        logger.error('Could not determine internal IPv4 address')
        return 2
    logger.info('Selected internal IPv4 candidate order: %s', ', '.join(candidates))

    try:
        backend = create_backend()
    except UpnpError as exc:
        logger.error('%s', exc)
        return 3

    failed = process_ports(
        backend,
        protocol,
        ports,
        candidates,
        DESCRIPTION,
        LEASE_SECONDS,
    )

    if failed:
        logger.error('Finished with %s/%s port(s) failed', failed, len(ports))
        return 4

    logger.info('Finished successfully: %s port(s) ok', len(ports))
    return 0


def main(argv: list[str]) -> int:
    setup_logging(LOG_LEVEL)
    protocol, ports = parse_args(argv)

    if not ports:
        return 0

    return run(protocol, ports)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
