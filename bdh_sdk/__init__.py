"""Black Diamond Hub SDK: the contract hub apps use to describe themselves.

Importing this package never imports or configures Django, so app
``plugin.py`` modules can use it while the hub's settings are being built.
"""
from .plugins import (
    ALL_MODES,
    API_VERSION,
    DASHBOARD,
    ENTRY_POINT_GROUP,
    GUEST,
    INFO,
    ON,
    OWNER,
    OWNER_ONLY,
    SECTIONS,
    STATUS_LEVELS,
    WARN,
    PluginSpec,
    Shortcut,
    Status,
    Tile,
)

__version__ = "0.1.1"

__all__ = [
    "__version__",
    "API_VERSION",
    "ENTRY_POINT_GROUP",
    "GUEST",
    "DASHBOARD",
    "OWNER",
    "ALL_MODES",
    "OWNER_ONLY",
    "SECTIONS",
    "Tile",
    "INFO",
    "ON",
    "WARN",
    "STATUS_LEVELS",
    "Status",
    "Shortcut",
    "PluginSpec",
]
