'''Network and interface helpers (IPv4 routing / iface addresses).'''

from __future__ import annotations

import logging
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional

ROUTE_PROBE_DST = '1.1.1.1'

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IfaceAddr:
    ip: str
    dynamic: bool
    secondary: bool


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


def _addrs_from_ip_json(data: list) -> list[tuple[str, IfaceAddr]]:
    '''Parse ip -j addr JSON into (iface_name, IfaceAddr) pairs.'''
    out: list[tuple[str, IfaceAddr]] = []
    for link in data:
        name = str(link.get('ifname') or '')
        if not name:
            continue
        for info in link.get('addr_info', []):
            if info.get('family') != 'inet':
                continue
            local = info.get('local')
            if not local or local.startswith('127.'):
                continue
            out.append(
                (
                    name,
                    IfaceAddr(
                        ip=local,
                        dynamic=bool(info.get('dynamic', False)),
                        secondary=bool(info.get('secondary', False)),
                    ),
                )
            )
    return out


def _addrs_from_ip_text(text: str, iface_filter: Optional[str] = None) -> list[tuple[str, IfaceAddr]]:
    '''Parse `ip -4 addr show` text into (iface_name, IfaceAddr) pairs.'''
    out: list[tuple[str, IfaceAddr]] = []
    current: Optional[str] = None
    for line in text.splitlines():
        if line and line[0].isdigit():
            # e.g. "2: eth0: <BROADCAST,...>"
            parts = line.split(':', 2)
            if len(parts) >= 2:
                current = parts[1].strip().split('@')[0]
            continue
        if iface_filter is not None and current != iface_filter:
            continue
        stripped = line.strip()
        if not stripped.startswith('inet '):
            continue
        if current is None:
            continue
        parts = stripped.split()
        ip = parts[1].split('/')[0]
        if ip.startswith('127.'):
            continue
        out.append(
            (
                current,
                IfaceAddr(
                    ip=ip,
                    dynamic='dynamic' in parts,
                    secondary='secondary' in parts,
                ),
            )
        )
    return out


def list_iface_ipv4(iface: str) -> list[IfaceAddr]:
    # Prefer JSON (iproute2); fall back to text parse.
    out = _run_ip('-4', '-j', 'addr', 'show', 'dev', iface)
    if out:
        try:
            import json

            return [addr for _, addr in _addrs_from_ip_json(json.loads(out))]
        except (ValueError, TypeError, KeyError):
            pass

    text = _run_ip('-4', 'addr', 'show', 'dev', iface)
    return [addr for _, addr in _addrs_from_ip_text(text, iface_filter=iface)]


def list_all_iface_ipv4() -> list[tuple[str, IfaceAddr]]:
    '''Return (iface_name, addr) for all non-loopback IPv4 addresses.'''
    out = _run_ip('-4', '-j', 'addr', 'show')
    if out:
        try:
            import json

            return _addrs_from_ip_json(json.loads(out))
        except (ValueError, TypeError, KeyError):
            pass

    text = _run_ip('-4', 'addr', 'show')
    if text:
        return _addrs_from_ip_text(text)
    return []


def iproute2_available() -> bool:
    return bool(_run_ip('-4', 'addr', 'show'))


def _is_usable_ipv4(ip: str) -> bool:
    if not ip or ip.startswith('127.'):
        return False
    # Link-local / APIPA — usually not useful for UPnP internal client.
    if ip.startswith('169.254.'):
        return False
    return True


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _list_ipv4_via_powershell() -> list[str]:
    '''Windows: Get-NetIPAddress (locale-independent).'''
    try:
        out = subprocess.check_output(
            [
                'powershell',
                '-NoProfile',
                '-Command',
                'Get-NetIPAddress -AddressFamily IPv4 '
                '| Select-Object -ExpandProperty IPAddress',
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    ips: list[str] = []
    for line in out.splitlines():
        ip = line.strip()
        if _is_usable_ipv4(ip):
            ips.append(ip)
    return ips


def _list_ipv4_via_socket() -> list[str]:
    '''Cross-platform hostname / getaddrinfo fallback.'''
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = ''
    if hostname:
        try:
            _, _, addrs = socket.gethostbyname_ex(hostname)
            for ip in addrs:
                if _is_usable_ipv4(ip):
                    ips.append(ip)
        except OSError:
            pass
        try:
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if _is_usable_ipv4(ip):
                    ips.append(ip)
        except OSError:
            pass
    probed = route_src_via_socket()
    if probed and _is_usable_ipv4(probed):
        ips.append(probed)
    return ips


def list_local_ipv4() -> list[str]:
    '''Local non-loopback IPv4 addresses (Linux iproute2 or Windows fallbacks).'''
    entries = list_all_iface_ipv4()
    if entries:
        return _dedupe_keep_order(
            [addr.ip for _, addr in entries if _is_usable_ipv4(addr.ip)]
        )

    ips = _list_ipv4_via_powershell()
    if not ips:
        ips = _list_ipv4_via_socket()
    return _dedupe_keep_order(ips)


def candidates_from_iface(iface: str) -> list[str]:
    '''IPv4 candidates on iface: DHCP first, then static (no route probe).'''
    iface_addrs = list_iface_ipv4(iface)
    if not iface_addrs:
        logger.warning('No IPv4 addresses on iface %s', iface)
        return []
    logger.info(
        'Iface %s addresses: %s',
        iface,
        ', '.join(
            f"{a.ip}({'dhcp' if a.dynamic else 'static'}"
            f"{',secondary' if a.secondary else ''})"
            for a in iface_addrs
        ),
    )
    if len(iface_addrs) == 1:
        return [iface_addrs[0].ip]
    dhcp = [a.ip for a in iface_addrs if a.dynamic]
    static = [a.ip for a in iface_addrs if not a.dynamic]
    candidates = dhcp + static
    logger.info(
        'Multiple IPv4 on %s — trying DHCP first, then others: %s',
        iface,
        ', '.join(candidates),
    )
    return candidates


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
