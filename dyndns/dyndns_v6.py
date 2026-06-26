#!/usr/bin/env python3
"""
Update dynamic DNS with the current public IPv6 address.

Usage:
  dyndns_v6.py TOKEN [INTERFACE]
  dyndns_v6.py --provider=PROVIDER [--domains=DOMAINS] [--token=TOKEN] [--interface=INTERFACE] [--verbose] [--ipv6=IPV6] [--dry-run]
  dyndns_v6.py --url=URL [--token=TOKEN] [--var=KV]... [--interface=INTERFACE] [--ipv6=IPV6] [--dry-run]

Options:
  --provider=PROVIDER    DNS provider shortcut (freedns or duckdns); maps to a built-in URL template [default: freedns]
  --token=TOKEN          Provider token (substituted as {token} in --url templates)
  --domains=DOMAINS      DuckDNS subname(s), comma-separated (without .duckdns.org)
  --interface=INTERFACE  Network interface for IPv6 source lookup
  --verbose              Request verbose response from DuckDNS
  --url=URL              URL template with {placeholder} variables (provider-agnostic mode)
  --var=KV               Template variable as key=value (repeatable)
  --ipv6=IPV6            Use this IPv6 instead of auto-detected address
  --dry-run              Print rendered URL and exit without HTTP request

Examples:
  dyndns_v6.py YOUR_TOKEN
  dyndns_v6.py YOUR_TOKEN eth0
  dyndns_v6.py --provider=freedns --token=YOUR_TOKEN --interface=eth0
  dyndns_v6.py --provider=freedns --token=YOUR_TOKEN --ipv6=2001:db8::1 --dry-run
  dyndns_v6.py --provider=duckdns --domains=thai-server1616 --token=YOUR_TOKEN
  dyndns_v6.py --provider=duckdns --domains=foo,bar --token=YOUR_TOKEN --verbose --dry-run
  dyndns_v6.py --url='https://dynupdate.alviy.com/token/update?hostname={hostname}&token={token}&myip={ipv6}' --var=hostname=example.dynnamn.ru --token=YOUR_TOKEN
  dyndns_v6.py --url='https://example.com/update?ip={ipv6}' --ipv6=2001:db8::1 --dry-run
"""

import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from docopt import docopt


HTTP_TIMEOUT_S = 15
ROUTE_PROBE_DST = '2001:4860:4860::8888'
PLACEHOLDER_RE = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')

PROVIDER_TEMPLATES: dict[str, str] = {
    'freedns': 'http://freedns.afraid.org/dynamic/update.php?{token}&address={ipv6}',
    'duckdns': 'https://www.duckdns.org/update?domains={domains}&token={token}&ipv6={ipv6}',
}


@dataclass(frozen=True)
class UrlRequest:
    template: str
    vars: dict[str, str]
    provider: str | None = None
    env_fallback: bool = False


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


def normalize_var_list(raw: list[str] | str | bool | None) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    return [raw]


def parse_vars(kvs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for kv in kvs:
        if '=' not in kv:
            raise ValueError(f'invalid --var (expected key=value): {kv!r}')
        key, _, value = kv.partition('=')
        key = key.strip()
        if not key:
            raise ValueError(f'invalid --var (empty key): {kv!r}')
        result[key] = value
    return result


def render_url_template(template: str, vars: dict[str, str], *, env_fallback: bool = True) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in vars:
            value = vars[name]
        elif env_fallback and name in os.environ:
            value = os.environ[name]
        else:
            raise ValueError(f'missing template variable: {{{name}}}')
        return urllib.parse.quote(value, safe='')

    return PLACEHOLDER_RE.sub(replace, template)


def http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
        return resp.read().decode('utf-8', errors='replace').strip()


def is_request_success(
    response: str,
    *,
    options: dict,
    address: str,
    provider: str | None = None,
) -> bool:
    """Return whether the HTTP response indicates a successful DDNS update."""
    if provider == 'duckdns':
        return response.splitlines()[0].strip() == 'OK' if response else False
    return True


def validate_provider_options(options: dict) -> int | None:
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
    return None


def build_url_request(
    options: dict,
    address: str,
    interface: str | None,
    provider: str | None,
) -> UrlRequest:
    if provider is None:
        return UrlRequest(
            template=options['--url'],
            vars=build_template_vars(address, interface, options),
            env_fallback=True,
        )

    if provider not in PROVIDER_TEMPLATES:
        raise ValueError(f'unsupported provider: {provider!r}')

    template = PROVIDER_TEMPLATES[provider]
    if provider == 'duckdns':
        if options['--verbose']:
            template += '&verbose=true'
        template_vars = {
            'domains': (options['--domains'] or os.environ.get('DUCKDNS_DOMAINS') or '').strip(),
            'token': (options['--token'] or os.environ.get('DUCKDNS_TOKEN') or '').strip(),
            'ipv6': address,
        }
    else:
        template_vars = {
            'token': (options['TOKEN'] or options['--token'] or '').strip(),
            'ipv6': address,
        }

    return UrlRequest(
        template=template,
        vars=template_vars,
        provider=provider,
    )


def build_template_vars(address: str, interface: str | None, options: dict) -> dict[str, str]:
    # TODO: add {ipv4} placeholder — detect public IPv4 via external what-is-my-ip service.
    user_vars = parse_vars(normalize_var_list(options['--var']))
    template_vars: dict[str, str] = {
        'ipv6': address,
    }
    if interface:
        template_vars['interface'] = interface
    if options['--token']:
        template_vars['token'] = options['--token'].strip()
    template_vars.update(user_vars)
    return template_vars


def execute_url_update(
    template: str,
    template_vars: dict[str, str],
    *,
    options: dict,
    address: str,
    provider: str | None,
    env_fallback: bool,
    dry_run: bool,
) -> int:
    try:
        url = render_url_template(template, template_vars, env_fallback=env_fallback)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if dry_run:
        print(url)
        return 0

    try:
        response = http_get(url)
    except urllib.error.URLError as e:
        print(f'update failed: {e}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'update failed: {e}', file=sys.stderr)
        return 1

    if not is_request_success(response, options=options, address=address, provider=provider):
        print(f'update failed: {response}', file=sys.stderr)
        return 1

    print(response)
    return 0


def run_update(
    options: dict,
    address: str,
    interface: str | None,
    provider: str | None,
) -> int:
    try:
        request = build_url_request(options, address, interface, provider)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    return execute_url_update(
        request.template,
        request.vars,
        options=options,
        address=address,
        provider=request.provider,
        env_fallback=request.env_fallback,
        dry_run=options['--dry-run'],
    )


def main() -> int:
    options = docopt(__doc__)
    url_mode = bool(options['--url'])
    interface = (options['INTERFACE'] or options['--interface'] or '').strip() or None

    if not url_mode:
        validation_error = validate_provider_options(options)
        if validation_error is not None:
            return validation_error

    if options['--ipv6']:
        address = options['--ipv6'].strip()
    else:
        try:
            address = get_ipv6_src(interface)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 1

    if not address:
        print('no IPv6 address found', file=sys.stderr)
        return 1

    print(f'IPv6: {address}')

    provider = None if url_mode else options['--provider']
    return run_update(options, address, interface, provider)


if __name__ == '__main__':
    raise SystemExit(main())
