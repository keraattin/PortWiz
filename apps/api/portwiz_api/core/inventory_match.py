"""Match an asset to the VLAN whose IP range contains its address.

Assets are mostly hosts living inside a VLAN's subnets, so a freshly added or
discovered asset can be placed in its VLAN automatically by checking its IP
against the configured IP ranges (the most specific range wins).
"""

from __future__ import annotations

import ipaddress
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.asset import IPRange

# A parsed range plus the VLAN it belongs to.
Ranges = list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, uuid.UUID]]


async def load_vlan_ranges(session: AsyncSession) -> Ranges:
    """Every VLAN-assigned IP range, parsed once so many IPs can be matched
    without re-querying (used by the ingest auto-discovery loop and backfill)."""
    rows = (
        await session.execute(
            select(IPRange.cidr, IPRange.vlan_id).where(IPRange.vlan_id.is_not(None))
        )
    ).all()
    out: Ranges = []
    for cidr, vlan_id in rows:
        try:
            out.append((ipaddress.ip_network(cidr, strict=False), vlan_id))
        except ValueError:
            continue
    return out


def match_ip(ranges: Ranges, ip: str) -> uuid.UUID | None:
    """The VLAN whose range contains ``ip``, preferring the most specific
    (longest-prefix) match. None if the IP is invalid or unmatched."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    best_prefix = -1
    best: uuid.UUID | None = None
    for net, vlan_id in ranges:
        if addr.version == net.version and addr in net and net.prefixlen > best_prefix:
            best_prefix = net.prefixlen
            best = vlan_id
    return best


async def match_vlan_for_ip(session: AsyncSession, ip: str) -> uuid.UUID | None:
    """Convenience for a single lookup: load the ranges and match one IP."""
    return match_ip(await load_vlan_ranges(session), ip)
