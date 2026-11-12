"""The hub's units: metric or imperial, one choice for every app.

The hub owns the setting (the °C/°F switch in its title bar, saved as
``hub``/``units``; a site's default is ``[apps.hub] units`` in its
``site.toml``). Apps read it here and show their numbers in it. They can offer
their own view-only switch, but there is no way to change the hub's choice
from an app.

This module does not import Django at import time.
"""
from .settings import app_setting

__all__ = ["IMPERIAL", "METRIC", "Units", "system", "units"]

METRIC = "metric"
IMPERIAL = "imperial"


def system():
    """The hub's units, ``"metric"`` or ``"imperial"`` (anything else is metric)."""
    value = app_setting("hub", "units", METRIC)
    return IMPERIAL if str(value).strip().lower() == IMPERIAL else METRIC


class Units:
    """Converts metric values to a unit system and labels them.

    The ``t``/``speed``/``length`` methods return rounded numbers (None for
    None); ``temp_text`` etc. add the unit, e.g. ``"21°C"`` or ``"70°F"``.
    """

    def __init__(self, system=METRIC):
        self.imperial = system == IMPERIAL
        self.system = IMPERIAL if self.imperial else METRIC
        self.temp_unit = "°F" if self.imperial else "°C"
        self.speed_unit = "mph" if self.imperial else "km/h"
        self.length_unit = "ft" if self.imperial else "m"

    def t(self, celsius):
        if celsius is None:
            return None
        return round(celsius * 9 / 5 + 32) if self.imperial else round(celsius)

    def speed(self, kph):
        if kph is None:
            return None
        return round(kph * 0.621371) if self.imperial else round(kph)

    def length(self, metres):
        if metres is None:
            return None
        return round(metres * 3.28084) if self.imperial else round(metres)

    def temp_text(self, celsius):
        value = self.t(celsius)
        return None if value is None else f"{value}{self.temp_unit}"

    def speed_text(self, kph):
        value = self.speed(kph)
        return None if value is None else f"{value} {self.speed_unit}"

    def length_text(self, metres):
        value = self.length(metres)
        return None if value is None else f"{value:,} {self.length_unit}"


def units(override=None):
    """:class:`Units` for ``override`` (an app's own view-only choice) or the hub's."""
    if override in (METRIC, IMPERIAL):
        return Units(override)
    return Units(system())
