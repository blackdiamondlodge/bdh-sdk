"""Data an app provides to other parts of the hub.

An app lists capabilities in ``PluginSpec.provides``, mapping a capability
name to a dotted path of a zero-argument callable. The hub calls providers
in worker threads with a short deadline and keeps the last good result, so
a provider should return quickly from its own cache.

- ``stats``: iterable of :class:`Stat` (screensaver info strip)
- ``backgrounds``: iterable of :class:`Background` (screensaver live cam)
- ``season``: :class:`SeasonHint` or None (screensaver season)

Stats are listed on the settings page from ``PluginSpec.stat_keys`` without
calling the provider; a provider only returns stats whose key it declared.
Consumers refer to them as ``"<plugin id>.<key>"``.
"""
from dataclasses import dataclass
from datetime import datetime

STATS = "stats"
BACKGROUNDS = "backgrounds"
SEASON = "season"
CAPABILITIES = frozenset({STATS, BACKGROUNDS, SEASON})

WINTER = "winter"


@dataclass(frozen=True)
class Stat:
    """One labelled number or time, e.g. ``Stat("snow_24h", "New snow", "12 cm")``.

    Set exactly one of ``value`` (already formatted with units, in the app's
    own unit setting) or ``time`` (timezone-aware; the screen formats it in
    local time).
    """

    key: str
    label: str
    value: str | None = None
    time: datetime | None = None
    order: int = 100

    def __post_init__(self):
        if (self.value is None) == (self.time is None):
            raise ValueError(f"stat {self.key!r} needs exactly one of value or time")
        if self.time is not None and self.time.utcoffset() is None:
            raise ValueError(f"stat {self.key!r} time must be timezone-aware")


@dataclass(frozen=True)
class Background:
    """A live image a screen can show full-screen, e.g. a webcam.

    The screen reloads ``image_url`` every ``refresh_seconds`` (adding a
    cache-busting parameter), so a stable URL is fine.
    """

    id: str
    label: str
    image_url: str
    refresh_seconds: int = 60
    live: bool = True

    def __post_init__(self):
        if self.refresh_seconds < 1:
            raise ValueError(f"background {self.id!r} refresh_seconds must be at least 1")


@dataclass(frozen=True)
class SeasonHint:
    """Evidence that a season has started early, e.g. the lifts are open.

    Only ``"winter"`` is supported for now, and a hint can only bring the
    season forward (within the screen's early window), never delay it.
    ``reason`` is shown on the settings page.
    """

    season: str
    reason: str

    def __post_init__(self):
        if self.season != WINTER:
            raise ValueError(f"unsupported season {self.season!r}")
