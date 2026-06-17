"""SQLModel ORM models.

Importing this package ensures every table is registered on SQLModel.metadata
(used by Alembic autogenerate and metadata.create_all in tests).
"""

from .agent import Agent
from .app_setting import AppSetting
from .asset import Asset, Criticality, DataSensitivity, IPRange, VLAN
from .audit import AuditEvent
from .change import ChangeEvent, PortState
from .scan import (
    Observation,
    ScanProfile,
    ScanRun,
    ScanRunStatus,
    ScanSource,
    ScanType,
)
from .task import Task, TaskStatus
from .user import User, UserRole

__all__ = [
    "Agent",
    "AppSetting",
    "Asset",
    "AuditEvent",
    "ChangeEvent",
    "PortState",
    "Criticality",
    "DataSensitivity",
    "IPRange",
    "Observation",
    "ScanProfile",
    "ScanRun",
    "ScanRunStatus",
    "ScanSource",
    "ScanType",
    "Task",
    "TaskStatus",
    "User",
    "UserRole",
    "VLAN",
]
