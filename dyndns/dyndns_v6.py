#!/usr/bin/env python3
"""
Update dynamic DNS with the current public IPv6 address.

Usage:
  dyndns_v6.py TOKEN [INTERFACE]
  dyndns_v6.py --provider=PROVIDER [--domains=DOMAINS] [--token=TOKEN] [--interface=INTERFACE] [--verbose]

Options:
  --provider=PROVIDER    DNS provider (freedns or duckdns) [default: freedns]
  --token=TOKEN          Provider token
  --domains=DOMAINS      DuckDNS subname(s), comma-separated (without .duckdns.org)
  --interface=INTERFACE  Network interface for IPv6 source lookup
  --verbose              Request verbose response from DuckDNS

Examples:
  dyndns_v6.py YOUR_TOKEN
  dyndns_v6.py YOUR_TOKEN eth0
  dyndns_v6.py --provider=freedns --token=YOUR_TOKEN --interface=eth0
  dyndns_v6.py --provider=duckdns --domains=thai-server1616 --token=YOUR_TOKEN
  dyndns_v6.py --provider=duckdns --domains=foo,bar --token=YOUR_TOKEN --verbose
"""

import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from docopt import docopt


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


def freedns_update(token: str, address: str) -> str:
    url = f'http://freedns.afraid.org/dynamic/update.php?{token}&address={address}'
    req = urllib.request.Request(
        url,
        method='GET',
        headers={'User-Agent': 'dyndns_v6.py (freedns.afraid.org)'},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return resp.read().decode('utf-8', errors='replace').strip()


def duckdns_update(domains: str, token: str, ipv6: str, verbose: bool = False) -> str:
    q = urllib.parse.urlencode({
        'domains': domains,
        'token': token,
        'ipv6': ipv6,
        **({'verbose': 'true'} if verbose else {}),
    })
    req = urllib.request.Request(
        f'https://www.duckdns.org/update?{q}',
        headers={'User-Agent': 'dyndns_v6.py (duckdns.org)'},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return resp.read().decode('utf-8', errors='replace').strip()


def is_duckdns_success(response: str) -> bool:
    return response.splitlines()[0].strip() == 'OK' if response else False


def main() -> int:
    options = docopt(__doc__)

    if options['--provider'] == 'duckdns':
        if not (options['--domains'] or os.environ.get('DUCKDNS_DOMAINS')):
            print('--domains is required for duckdns (or set DUCKDNS_DOMAINS)', file=sys.stderr)
            return 2
        if not (options['--token'] or os.environ.get('DUCKDNS_TOKEN')):
            print('--token is required for duckdns (or set DUCKDNS_TOKEN)', file=sys.stderr)
            return 2
    elif not (options['TOKEN'] or options['--token']):
        print('--token is required for freedns provider', file=sys.stderr)
        return 2

    try:
        address = get_ipv6_src((options['INTERFACE'] or options['--interface'] or '').strip() or None)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    if not address:
        print('no IPv6 address found', file=sys.stderr)
        return 1

    print(f'IPv6: {address}')

    try:
        if options['--provider'] == 'duckdns':
            response = duckdns_update(
                (options['--domains'] or os.environ.get('DUCKDNS_DOMAINS') or '').strip(),
                (options['--token'] or os.environ.get('DUCKDNS_TOKEN') or '').strip(),
                address,
                verbose=options['--verbose'],
            )
            if not is_duckdns_success(response):
                print(f'update failed: {response}', file=sys.stderr)
                return 1
        else:
            response = freedns_update((options['TOKEN'] or options['--token'] or '').strip(), address)
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
