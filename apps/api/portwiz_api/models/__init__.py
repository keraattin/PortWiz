"""SQLModel ORM models.

Importing this package ensures every table is registered on SQLModel.metadata
(used by Alembic autogenerate and metadata.create_all in tests).
"""

from .asset import Asset, Criticality, DataSensitivity, IPRange, VLAN
from .audit import AuditEvent
from .user import User, UserRole

__all__ = [
    "Asset",
    "AuditEvent",
    "Criticality",
    "DataSensitivity",
    "IPRange",
    "User",
    "UserRole",
    "VLAN",
]
