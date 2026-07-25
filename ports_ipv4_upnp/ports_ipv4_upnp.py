#!/usr/bin/env python3
'''Synchronize IPv4 UPnP port mappings (TCP|UDP).

Usage:
  ports-ipv4-upnp.py TCP|UDP [port ...]

Exit codes:
  0  success (no ports, or all ports in desired state)
  1  invalid CLI / protocol / port
  2  could not determine internal IPv4
  3  async-upnp-client missing or IGD unavailable
  4  one or more ports failed to map/refresh
'''

from __future__ import annotations

import asyncio
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
IGD_SEARCH_TARGETS = (
    'urn:schemas-upnp-org:device:InternetGatewayDevice:2',
    'urn:schemas-upnp-org:device:InternetGatewayDevice:1',
)

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
    '''Abstract async IPv4 IGD backend.'''

    async def discover(self) -> str:
        raise NotImplementedError

    async def list_mappings(self) -> list[PortMapping]:
        raise NotImplementedError

    async def add_mapping(
        self,
        internal_ip: str,
        port: int,
        protocol: str,
        description: str,
        lease_seconds: int,
    ) -> None:
        raise NotImplementedError

    async def delete_mapping(self, port: int, protocol: str, remote_host: str = '') -> None:
        raise NotImplementedError


class AsyncUpnpClientBackend(UpnpBackend):
    '''IGD backend based on async-upnp-client.'''

    def __init__(self):
        try:
            from async_upnp_client.aiohttp import AiohttpRequester
            from async_upnp_client.client_factory import UpnpFactory
            from async_upnp_client.exceptions import UpnpActionError
            from async_upnp_client.profiles.igd import IgdDevice
            from async_upnp_client.search import async_search
        except ImportError as exc:
            raise UpnpError(
                'async-upnp-client is not installed '
                '(pip install async-upnp-client)'
            ) from exc

        self._AiohttpRequester = AiohttpRequester
        self._UpnpFactory = UpnpFactory
        self._UpnpActionError = UpnpActionError
        self._IgdDevice = IgdDevice
        self._async_search = async_search
        self._igd: Optional[object] = None
        self._location = ''

    async def discover(self) -> str:
        locations = await self._discover_locations()
        if not locations:
            raise UpnpError('No UPnP IGD devices discovered')

        last_err: Optional[Exception] = None
        requester = self._AiohttpRequester(timeout=10)
        factory = self._UpnpFactory(requester, non_strict=True)

        for location in locations:
            try:
                device = await factory.async_create_device(location)
                igd = self._IgdDevice(device, event_handler=None)
                # Prefer devices that actually expose port-mapping actions.
                action = igd._any_action(['WANIPC', 'WANPPPC'], 'AddPortMapping')
                if action is None:
                    logger.debug(
                        'Skipping %s: no AddPortMapping action',
                        location,
                    )
                    continue
                self._igd = igd
                self._location = location
                name = getattr(device, 'friendly_name', None) or device.device_type
                return f'{name} @ {location}'
            except Exception as exc:  # noqa: BLE001 — try next location
                last_err = exc
                logger.debug('Failed to init IGD at %s: %s', location, exc)

        detail = f': {last_err}' if last_err else ''
        raise UpnpError(f'IGD not available{detail}')

    async def _discover_locations(self) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        async def _on_response(headers) -> None:
            loc = headers.get('location')
            if not loc:
                return
            loc = str(loc).strip()
            if not loc or loc in seen:
                return
            # Prefer IPv4 description URLs.
            if loc.startswith('http://[') or loc.startswith('https://['):
                return
            seen.add(loc)
            found.append(loc)

        for st in IGD_SEARCH_TARGETS:
            logger.debug('SSDP search ST=%s timeout=%ss', st, SSDP_SEARCH_TIMEOUT)
            try:
                await self._async_search(
                    async_callback=_on_response,
                    timeout=SSDP_SEARCH_TIMEOUT,
                    search_target=st,
                )
            except OSError as exc:
                logger.debug('SSDP search failed for %s: %s', st, exc)
            if found:
                break

        logger.debug('Discovered IGD locations: %s', found)
        return found

    def _require_igd(self):
        if self._igd is None:
            raise UpnpError('IGD not discovered yet')
        return self._igd

    async def list_mappings(self) -> list[PortMapping]:
        igd = self._require_igd()
        out: list[PortMapping] = []
        idx = 0
        while idx < 1024:
            try:
                entry = await igd.async_get_generic_port_mapping_entry(idx)
            except self._UpnpActionError as exc:
                logger.debug(
                    'GetGenericPortMappingEntry(%s) ended: code=%s desc=%s',
                    idx,
                    getattr(exc, 'error_code', None),
                    getattr(exc, 'error_desc', None),
                )
                break
            except Exception as exc:
                code = _extract_igd_code_from_exc(exc)
                raise UpnpError(
                    f'Failed to list mappings at index {idx}: {exc}',
                    code=code,
                ) from exc

            if entry is None:
                break

            remote = ''
            if entry.remote_host is not None:
                remote = str(entry.remote_host)
            lease = 0
            if entry.lease_duration is not None:
                lease = int(entry.lease_duration.total_seconds())

            out.append(
                PortMapping(
                    protocol=str(entry.protocol).upper(),
                    external_port=int(entry.external_port),
                    internal_ip=str(entry.internal_client),
                    internal_port=int(entry.internal_port),
                    description=str(entry.description or ''),
                    remote_host=remote,
                    lease_time=lease,
                )
            )
            idx += 1
        return out

    async def add_mapping(
        self,
        internal_ip: str,
        port: int,
        protocol: str,
        description: str,
        lease_seconds: int,
    ) -> None:
        igd = self._require_igd()
        action = igd._any_action(['WANIPC', 'WANPPPC'], 'AddPortMapping')
        if action is None:
            raise UpnpError('AddPortMapping action not available on IGD')
        try:
            # Empty NewRemoteHost = mapping applies to all remote hosts (UPnP spec).
            await action.async_call(
                NewRemoteHost='',
                NewExternalPort=port,
                NewProtocol=protocol,
                NewInternalPort=port,
                NewInternalClient=internal_ip,
                NewEnabled=True,
                NewPortMappingDescription=description,
                NewLeaseDuration=int(lease_seconds),
            )
        except Exception as exc:
            code = _extract_igd_code_from_exc(exc)
            raise UpnpError(f'AddPortMapping failed: {exc}', code=code) from exc

    async def delete_mapping(
        self,
        port: int,
        protocol: str,
        remote_host: str = '',
    ) -> None:
        igd = self._require_igd()
        action = igd._any_action(['WANIPC', 'WANPPPC'], 'DeletePortMapping')
        if action is None:
            logger.debug('DeletePortMapping action not available')
            return

        candidates = [remote_host or '']
        if '0.0.0.0' not in candidates:
            candidates.append('0.0.0.0')
        if '' not in candidates:
            candidates.append('')

        for rh in candidates:
            try:
                await action.async_call(
                    NewRemoteHost=rh,
                    NewExternalPort=port,
                    NewProtocol=protocol,
                )
                return
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
    if not m:
        return None
    code = int(m.group(1))
    if 600 <= code <= 799:
        return code
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


async def create_async_backend() -> AsyncUpnpClientBackend:
    backend = AsyncUpnpClientBackend()
    igd = await backend.discover()
    logger.info('Using async-upnp-client; IGD=%s', igd)
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


async def ensure_port_async(
    backend: UpnpBackend,
    protocol: str,
    port: int,
    ip_candidates: list[str],
    description: str,
    lease_seconds: int,
) -> bool:
    '''Return True on success for this port.'''
    try:
        mappings = await backend.list_mappings()
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
            await backend.delete_mapping(
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
            await backend.add_mapping(ip, port, protocol, description, lease_seconds)
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


async def process_ports(
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
        ok = await ensure_port_async(
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


async def async_main(protocol: str, ports: list[int]) -> int:
    logger.info('Start: protocol=%s ports=%s', protocol, ports)

    candidates = build_internal_ip_candidates(INTERNAL_IP.strip())
    if not candidates:
        logger.error('Could not determine internal IPv4 address')
        return 2
    logger.info('Selected internal IPv4 candidate order: %s', ', '.join(candidates))

    try:
        backend = await create_async_backend()
    except UpnpError as exc:
        logger.error('%s', exc)
        return 3

    failed = await process_ports(
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

    return asyncio.run(async_main(protocol, ports))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
