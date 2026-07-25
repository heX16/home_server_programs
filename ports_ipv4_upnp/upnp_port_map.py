'''UPnP IGD port mapping backends (IPv4 TCP|UDP).'''

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

SSDP_SEARCH_TIMEOUT = int(os.environ.get('SSDP_SEARCH_TIMEOUT', '5'))

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortMapping:
    protocol: str
    external_port: int
    internal_ip: str
    internal_port: int
    description: str
    remote_host: str
    lease_time: int


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
