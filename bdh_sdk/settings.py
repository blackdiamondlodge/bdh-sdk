"""Per-app settings lookup for hub apps.

Apps read their configuration with :func:`app_setting` instead of reaching
into ``os.environ`` or ``django.conf.settings`` directly, so every app's
settings live under one predictable namespace (``BDH_<APPID>_<KEY>``) while
old un-namespaced names keep working during migration.

This module does not import Django at import time.
"""
import os
import re

__all__ = ["MissingSetting", "app_setting", "as_bool", "setting_name"]

_MISSING = object()
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


class MissingSetting(KeyError):
    """A required app setting is not set anywhere and has no default."""

    def __str__(self):
        return str(self.args[0]) if self.args else "missing setting"


def setting_name(app_id, key):
    """Namespaced name for ``key`` of ``app_id``, e.g. ``BDH_WIFI_SSID``."""
    return _NON_ALNUM.sub("_", f"BDH_{app_id}_{key}".upper())


def as_bool(value):
    """Parse a boolean setting. Accepts 1/true/yes/on and 0/false/no/off."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def _django_settings():
    try:
        from django.conf import settings
    except ImportError:
        return None
    try:
        return settings if settings.configured else None
    except Exception:
        return None


def app_setting(app_id, key, default=_MISSING, *, legacy=(), cast=None):
    """Return the value of setting ``key`` for app ``app_id``.

    Lookup order (first hit wins):

    1. Environment variable ``BDH_<APPID>_<KEY>`` (upper-cased, every
       non-alphanumeric character replaced by ``_``).
    2. The first environment variable in ``legacy`` that is set (old
       un-namespaced names such as ``WIFI_SSID``).
    3. Django settings, only when Django is installed *and* configured:
       ``settings.BDH_<APPID>_<KEY>``, then each ``legacy`` name in order.
    4. ``default``.

    An environment variable counts as set when it is present, even if empty.
    If nothing is found and no ``default`` was given, :class:`MissingSetting`
    is raised. ``cast`` (e.g. ``int`` or :func:`as_bool`) is applied to the
    result only when it is a string, so non-string Django settings and
    defaults are returned unchanged.
    """
    if isinstance(legacy, str):
        legacy = (legacy,)
    name = setting_name(app_id, key)
    value = _MISSING

    for env_name in (name, *legacy):
        if env_name in os.environ:
            value = os.environ[env_name]
            break

    if value is _MISSING:
        settings = _django_settings()
        if settings is not None:
            for attr in (name, *legacy):
                if hasattr(settings, attr):
                    value = getattr(settings, attr)
                    break

    if value is _MISSING:
        if default is _MISSING:
            tried = ", ".join((name, *legacy))
            raise MissingSetting(
                f"setting {key!r} for app {app_id!r} is not set (tried {tried})"
            )
        value = default

    if cast is not None and isinstance(value, str):
        value = cast(value)
    return value
