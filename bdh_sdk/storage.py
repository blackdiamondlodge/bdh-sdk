"""Per-app state and media storage for hub apps.

:func:`app_state` is a small key/value store for an app's own bookkeeping
(things the app remembers, not settings a person edits). Values must be
JSON-serializable. The hub installs a database-backed backend with
:func:`set_state_backend`; without one, state lives in memory, which is what
unit tests get.

:func:`app_media` is a Django file storage rooted at ``MEDIA_ROOT/apps/<id>/``
so each app's uploaded files stay in their own folder.

This module does not import Django at import time.
"""
import copy
import json
import re

__all__ = ["AppState", "MemoryStateBackend", "app_media", "app_state", "set_state_backend"]

_APP_ID = re.compile(r"^[a-z0-9_]+$")


def _check_app_id(app_id):
    if not isinstance(app_id, str) or not _APP_ID.match(app_id):
        raise ValueError(f"invalid app id: {app_id!r}")
    return app_id


class MemoryStateBackend:
    """In-process state backend: the default, and the one tests use."""

    def __init__(self):
        self._data = {}

    def get(self, app_id, key):
        return copy.deepcopy(self._data[(app_id, key)])

    def set(self, app_id, key, value):
        self._data[(app_id, key)] = copy.deepcopy(value)

    def delete(self, app_id, key):
        self._data.pop((app_id, key), None)

    def keys(self, app_id):
        return sorted(k for a, k in self._data if a == app_id)


_backend = MemoryStateBackend()


def set_state_backend(backend):
    """Install the backend behind :func:`app_state`; ``None`` restores memory.

    A backend has ``get(app_id, key)`` (raises ``KeyError`` when unset),
    ``set(app_id, key, value)``, ``delete(app_id, key)`` and ``keys(app_id)``.
    """
    global _backend
    _backend = backend if backend is not None else MemoryStateBackend()


class AppState:
    """One app's state. Get one with :func:`app_state`."""

    def __init__(self, app_id):
        self.app_id = _check_app_id(app_id)

    def get(self, key, default=None):
        try:
            return _backend.get(self.app_id, key)
        except KeyError:
            return default

    def set(self, key, value):
        json.dumps(value)  # fail here, not in the backend, on unserializable values
        _backend.set(self.app_id, key, value)

    def delete(self, key):
        _backend.delete(self.app_id, key)

    def keys(self):
        return list(_backend.keys(self.app_id))

    def __contains__(self, key):
        try:
            _backend.get(self.app_id, key)
        except KeyError:
            return False
        return True


def app_state(app_id):
    """Key/value state for ``app_id`` (e.g. ``app_state("display").get("lifts_opened")``)."""
    return AppState(app_id)


def app_media(app_id):
    """Django storage for ``app_id``'s files, under ``MEDIA_ROOT/apps/<app_id>/``.

    Use it like any Django storage, or pass it as an ``ImageField``'s
    ``storage``. Needs Django configured.
    """
    import os

    from django.conf import settings
    from django.core.files.storage import FileSystemStorage

    _check_app_id(app_id)
    return FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "apps", app_id),
        base_url=f"{settings.MEDIA_URL.rstrip('/')}/apps/{app_id}/",
    )
