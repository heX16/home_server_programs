#!/usr/bin/env python3
import re
import subprocess
import sys
import urllib.error
import urllib.request


HTTP_TIMEOUT_S = 15
ROUTE_PROBE_DST = '2001:4860:4860::8888'


def run_ip(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError('ip command not found (install iproute2).')


def get_ipv6_src(interface: str | None) -> str:
    """
    Get the IPv6 source address (`src`) the kernel would use for ROUTE_PROBE_DST.
    Uses `ip -6 route get ...` so routing selects the active uplink.
    If `interface` is set, constrain lookup to that interface (strict: return '' if not possible).
    """
    base_cmd = ['ip', '-6', 'route', 'get', ROUTE_PROBE_DST]

    if interface:
        # Prefer `oif <iface>` (output interface) when supported by iproute2.
        proc = run_ip([*base_cmd, 'oif', interface])
        if proc.returncode != 0:
            # Fallback for iproute2 variants that accept `dev <iface>` instead.
            proc = run_ip([*base_cmd, 'dev', interface])
    else:
        proc = run_ip(base_cmd)

    if proc.returncode != 0:
        return ''

    # Typical output includes: "... dev eth0 ... src 2001:db8::1234 ..."
    m = re.search(r'\bsrc\s+(\S+)\b', proc.stdout)
    if not m:
        return ''

    addr = m.group(1).lower()
    # Skip ULA addresses (fd00::/8). For DDNS we want a public/global address.
    if addr.startswith('fd'):
        return ''
    return addr


def dyndns_update(token: str, address: str) -> str:
    url = f'http://freedns.afraid.org/dynamic/update.php?{token}&address={address}'
    req = urllib.request.Request(
        url,
        method='GET',
        headers={'User-Agent': 'dyndns_v6.py (freedns.afraid.org)'},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return resp.read().decode('utf-8', errors='replace').strip()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print('Usage: dyndns_v6.py TOKEN [INTERFACE]', file=sys.stderr)
        return 2

    token = sys.argv[1].strip()
    if not token:
        print('TOKEN is empty', file=sys.stderr)
        return 2

    interface = None
    if len(sys.argv) == 3:
        interface = sys.argv[2].strip() or None

    try:
        address = get_ipv6_src(interface)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    if not address:
        print('no IPv6 address found', file=sys.stderr)
        return 1

    print(f'IPv6: {address}')

    try:
        response = dyndns_update(token, address)
    except urllib.error.URLError as e:
        print(f'update failed: {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'update failed: {e}', file=sys.stderr)
        return 1

    print(response)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

