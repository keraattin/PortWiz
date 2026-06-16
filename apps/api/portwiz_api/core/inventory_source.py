"""External inventory sources (IPAM/DCIM).

A provider-agnostic interface, like the issue tracker and notifier, so other
sources (phpIPAM, a CSV-on-a-URL, Device42) can be added later. NetBox is the
first concrete source. ``get_inventory_source`` is a FastAPI dependency, which
also makes it trivial to inject a fake in tests. Config and httpx are imported
lazily so importing this module stays cheap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("portwiz.inventory_source")


@dataclass
class SourceAsset:
    """A host pulled from an external source, normalized to PortWiz fields."""

    ip: str
    hostname: str | None = None
    description: str | None = None
    vlan_name: str | None = None


class InventorySource(Protocol):
    name: str

    async def fetch_assets(self) -> list[SourceAsset]: ...
    async def verify(self) -> tuple[bool, str]: ...


class NullSource:
    """Used when no inventory source is configured."""

    name = "none"

    async def fetch_assets(self) -> list[SourceAsset]:
        return []

    async def verify(self) -> tuple[bool, str]:
        return False, "No inventory source is configured."


class NetBoxSource:
    """Pulls IP addresses from a NetBox instance via its REST API."""

    name = "netbox"

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Token {token}", "Accept": "application/json"}

    async def fetch_assets(self) -> list[SourceAsset]:
        import httpx

        assets: list[SourceAsset] = []
        url: str | None = f"{self._base}/api/ipam/ip-addresses/?limit=500"
        async with httpx.AsyncClient(timeout=30) as client:
            while url:
                resp = await client.get(url, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
                for record in data.get("results", []):
                    # NetBox addresses are CIDR ("10.0.0.5/24"); keep the host part.
                    ip = (record.get("address") or "").split("/")[0].strip()
                    if not ip:
                        continue
                    assets.append(
                        SourceAsset(
                            ip=ip,
                            hostname=(record.get("dns_name") or None),
                            description=(record.get("description") or None),
                        )
                    )
                url = data.get("next")
        return assets

    async def verify(self) -> tuple[bool, str]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self._base}/api/status/", headers=self._headers)
                resp.raise_for_status()
                version = resp.json().get("netbox-version", "unknown")
                return True, f"Connected to NetBox {version}"
        except Exception as exc:  # surface connectivity/auth failures to the UI
            return False, str(exc)


def get_inventory_source() -> InventorySource:
    from .config import get_settings

    settings = get_settings()
    if settings.netbox_enabled and settings.netbox_url and settings.netbox_token:
        return NetBoxSource(settings.netbox_url, settings.netbox_token)
    return NullSource()
