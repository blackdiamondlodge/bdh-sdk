"""The hub's location: one place, and its time zone, for every app.

The hub owns it (Settings > General, saved as ``hub``/``location``). Apps
read it here, e.g. for a forecast or to show times in the hub's local time;
there is no way to change it from an app.

This module does not import Django at import time.
"""
from dataclasses import dataclass
from datetime import timezone as _utc_tz
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .settings import app_setting

__all__ = ["Location", "location", "tzinfo"]


@dataclass(frozen=True)
class Location:
    """Where the hub is. Coordinates are None when only a time zone is known."""

    name: str = ""
    region: str = ""
    country: str = ""
    latitude: float = None
    longitude: float = None
    timezone: str = ""

    @property
    def label(self):
        """``"Sun Peaks, British Columbia, Canada"``; blank parts are left out."""
        return ", ".join(part for part in (self.name, self.region, self.country) if part)

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None


def _number(value, limit):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if -limit <= number <= limit else None


def _legacy():
    # Hubs older than the Location setting kept it in settings.HUB_LOCATION.
    try:
        from django.conf import settings
        return getattr(settings, "HUB_LOCATION", None) if settings.configured else None
    except Exception:
        return None


def location():
    """The hub's :class:`Location`, or None when it hasn't been set."""
    value = app_setting("hub", "location", None)
    if not isinstance(value, dict):
        value = _legacy()
    if not isinstance(value, dict):
        return None
    lat, lon = _number(value.get("latitude"), 90), _number(value.get("longitude"), 180)
    if lat is None or lon is None:
        lat = lon = None
    found = Location(
        name=str(value.get("name") or "").strip(),
        region=str(value.get("region") or "").strip(),
        country=str(value.get("country") or "").strip(),
        latitude=lat,
        longitude=lon,
        timezone=str(value.get("timezone") or "").strip(),
    )
    return found if found.has_coordinates or found.timezone else None


def tzinfo():
    """The hub's time zone as a ``tzinfo``; UTC when it isn't set or isn't known."""
    where = location()
    if where and where.timezone:
        try:
            return ZoneInfo(where.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return _utc_tz.utc