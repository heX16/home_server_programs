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
