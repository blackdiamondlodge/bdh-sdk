"""Black Diamond Hub SDK: the contract hub apps use to describe themselves.

Importing this package never imports or configures Django, so app
``plugin.py`` modules can use it while the hub's settings are being built.
"""
from .plugins import (
    ALL_MODES,
    API_VERSION,
    Action,
    Card,
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
    Reading,
    Setting,
    SettingsPage,
    Shortcut,
    Stay,
    Status,
    StatusRow,
    Tile,
)
from .auth import is_admin
from .provides import BACKGROUNDS, SEASON, STATS, Background, SeasonHint, Stat

__version__ = "0.18.0"

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
    "StatusRow",
    "Action",
    "Shortcut",
    "Stay",
    "Reading",
    "Card",
    "Setting",
    "SettingsPage",
    "PluginSpec",
    "is_admin",
    "STATS",
    "BACKGROUNDS",
    "SEASON",
    "Stat",
    "Background",
    "SeasonHint",
]
