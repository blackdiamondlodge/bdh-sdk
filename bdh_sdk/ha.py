"""Home Assistant client for hub apps.

Fetches entity states and history and calls services over the REST API, and
runs registry commands over the WebSocket API. The connection comes from
``HOMEASSISTANT_URL`` and ``HOMEASSISTANT_ACCESS_TOKEN``, read from Django
settings when configured, otherwise from the environment.

Needs ``requests`` (and ``websocket-client`` for :func:`ws_commands`):
install ``bdh-sdk[ha]``. The hub already ships both.
"""
import json
import logging
import os
from urllib.parse import urljoin

import requests

from .settings import _django_settings

__all__ = [
    "HAError",
    "TIMEOUT",
    "call_service",
    "get_all_states",
    "get_entity_state",
    "get_entity_states",
    "get_history",
    "get_static",
    "ws_commands",
]

logger = logging.getLogger(__name__)

TIMEOUT = 10  # seconds


class HAError(Exception):
    """Raised when a Home Assistant call that must succeed fails."""


def _setting(name, default=None):
    settings = _django_settings()
    value = getattr(settings, name, None) if settings is not None else None
    if value in (None, ""):
        value = os.environ.get(name, default)
    return value


def _base_url():
    return _setting("HOMEASSISTANT_URL", "http://homeassistant.local:8123")


def _token():
    return _setting("HOMEASSISTANT_ACCESS_TOKEN", "")


def _headers():
    return {
        "Authorization": "Bearer " + (_token() or ""),
        "Content-Type": "application/json",
    }


def get_entity_state(entity_id):
    """State dict (``entity_id``, ``state``, ``attributes``) or None on failure."""
    url = urljoin(_base_url(), f"/api/states/{entity_id}")
    try:
        resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("HA returned %s for %s", resp.status_code, entity_id)
    except requests.RequestException as exc:
        logger.error("Failed to get state for %s: %s", entity_id, exc)
    return None


def get_entity_states(entity_ids):
    """Dict of entity_id -> state dict for the wanted entities ({} on failure)."""
    url = urljoin(_base_url(), "/api/states")
    try:
        resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
        if resp.status_code == 200:
            wanted = set(entity_ids)
            return {s["entity_id"]: s for s in resp.json() if s["entity_id"] in wanted}
        logger.warning("HA returned %s fetching all states", resp.status_code)
    except requests.RequestException as exc:
        logger.error("Failed to fetch states: %s", exc)
    return {}


def get_history(entity_ids, start, end=None):
    """State history between ``start`` and ``end`` (timezone-aware datetimes).

    Returns entity_id -> list of (iso_timestamp, state), oldest first, or {}
    on failure.
    """
    url = urljoin(_base_url(), f"/api/history/period/{start.isoformat()}")
    params = {
        "filter_entity_id": ",".join(entity_ids),
        "minimal_response": "",
        "no_attributes": "",
    }
    if end is not None:
        params["end_time"] = end.isoformat()
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.warning("HA returned %s fetching history", resp.status_code)
            return {}
        result = {}
        for series in resp.json():
            if not series:
                continue
            # With minimal_response only the first item carries entity_id.
            eid = series[0].get("entity_id")
            result[eid] = [
                (item.get("last_changed") or item.get("last_updated"), item.get("state"))
                for item in series
            ]
        return result
    except (requests.RequestException, ValueError) as exc:
        logger.error("Failed to fetch history: %s", exc)
    return {}


def call_service(domain, service, entity_id, extra_data=None):
    """Call ``domain.service`` on ``entity_id``. Returns (success, error or None)."""
    url = urljoin(_base_url(), f"/api/services/{domain}/{service}")
    payload = {"entity_id": entity_id}
    if extra_data:
        payload.update(extra_data)
    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=TIMEOUT)
        if resp.status_code == 200:
            return True, None
        msg = f"HA returned {resp.status_code}: {resp.text[:200]}"
        logger.warning(msg)
        return False, msg
    except requests.RequestException as exc:
        msg = f"Request failed: {exc}"
        logger.error(msg)
        return False, msg


def get_all_states():
    """Every entity state as a list. Raises HAError on failure."""
    url = urljoin(_base_url(), "/api/states")
    try:
        resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise HAError(f"states fetch failed: {exc}") from exc
    if resp.status_code != 200:
        raise HAError(f"HA returned {resp.status_code} fetching states")
    return resp.json()


def get_static(path):
    """Bytes of a static file served by HA (e.g. an integration's card JS)."""
    url = urljoin(_base_url(), path)
    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise HAError(f"fetch {path} failed: {exc}") from exc
    if resp.status_code != 200:
        raise HAError(f"HA returned {resp.status_code} for {path}")
    return resp.content


def ws_commands(*messages):
    """Run WebSocket commands (dicts like ``{"type": "config/device_registry/list"}``)
    over one connection and return their results in order.

    Used for data REST doesn't expose (entity / device registries). Raises
    HAError on any failure.
    """
    import websocket

    base = _base_url().rstrip("/")
    url = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/api/websocket"
    try:
        ws = websocket.create_connection(url, timeout=TIMEOUT)
    except (OSError, websocket.WebSocketException) as exc:
        raise HAError(f"connect failed: {exc}") from exc
    try:
        ws.recv()  # auth_required
        ws.send(json.dumps({"type": "auth", "access_token": _token()}))
        if json.loads(ws.recv()).get("type") != "auth_ok":
            raise HAError("auth failed")
        results = []
        for i, message in enumerate(messages, start=1):
            ws.send(json.dumps({**message, "id": i}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == i:
                    break
            if not msg.get("success"):
                raise HAError(f"{message.get('type')} failed: {msg.get('error')}")
            results.append(msg.get("result"))
        return results
    except (OSError, ValueError, websocket.WebSocketException) as exc:
        raise HAError(f"websocket command failed: {exc}") from exc
    finally:
        ws.close()
