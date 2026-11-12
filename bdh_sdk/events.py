"""Events: apps subscribe to topics and get called when something happens.

Topics are ``/``-separated paths. The first segment names who published:
an event source the hub runs (``ha/state/binary_sensor.front_door`` from the
Home Assistant source named ``ha``, ``hook/...`` from a webhook) or an app
(``cameras/doorbell/front``). Apps publish under their own app id.

Subscription patterns use MQTT wildcards: ``+`` matches one segment and a
trailing ``#`` matches the rest (``ha/state/+``, ``ha/#``).

Handlers run on one shared dispatcher thread, so they must not block; hand
long work to your own thread. A plain function is called directly, an
``async def`` handler runs as a task on the dispatcher's event loop. A
handler that raises is logged and does not affect the others.

Delivery is in-process and best effort: events published while nobody is
subscribed, or while a source is disconnected, are gone.

The hub reads :func:`patterns` and :func:`add_listener` to decide what to
fetch from its sources. This module does not import Django and starts its
thread only on the first :func:`publish`.
"""
import asyncio
import inspect
import logging
import threading
import time as _time
from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = [
    "Event",
    "Subscription",
    "add_listener",
    "apublish",
    "flush",
    "matches",
    "patterns",
    "publish",
    "reset",
    "subscribe",
]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    topic: str
    data: Any = None
    time: float = field(default_factory=_time.time)

    @property
    def source(self) -> str:
        """The first topic segment: the source or app that published it."""
        return self.topic.split("/", 1)[0]


def _segments(topic, *, wildcards):
    if not isinstance(topic, str) or not topic:
        raise ValueError(f"topic must be a non-empty string, got {topic!r}")
    parts = topic.split("/")
    for i, part in enumerate(parts):
        if not part:
            raise ValueError(f"empty segment in topic {topic!r}")
        if "+" in part or "#" in part:
            if not wildcards:
                raise ValueError(f"wildcards are not allowed in a published topic: {topic!r}")
            if part not in ("+", "#") or (part == "#" and i != len(parts) - 1):
                raise ValueError(f"bad wildcard in pattern {topic!r}")
    return parts


def matches(pattern: str, topic: str) -> bool:
    """Whether ``topic`` matches subscription ``pattern``."""
    want = _segments(pattern, wildcards=True)
    have = _segments(topic, wildcards=False)
    for i, part in enumerate(want):
        if part == "#":
            return True
        if i >= len(have) or (part != "+" and part != have[i]):
            return False
    return len(want) == len(have)


class Subscription:
    def __init__(self, pattern, handler):
        self.pattern = pattern
        self.handler = handler

    def cancel(self):
        """Stop delivering to this handler."""
        with _lock:
            if self in _subs:
                _subs.remove(self)
                _notify()

    def __repr__(self):
        return f"Subscription({self.pattern!r}, {getattr(self.handler, '__qualname__', self.handler)!r})"


_lock = threading.RLock()
_subs: list[Subscription] = []
_listeners: list[Callable[[list[str]], None]] = []
_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None
_tasks: set = set()


def subscribe(pattern: str, handler: Callable[[Event], Any]) -> Subscription:
    """Call ``handler(event)`` for every published event matching ``pattern``."""
    _segments(pattern, wildcards=True)
    if not callable(handler):
        raise TypeError("handler must be callable")
    sub = Subscription(pattern, handler)
    with _lock:
        _subs.append(sub)
        _notify()
    return sub


def patterns() -> list[str]:
    """The distinct patterns currently subscribed to, sorted."""
    with _lock:
        return sorted({s.pattern for s in _subs})


def add_listener(listener: Callable[[list[str]], None]) -> Callable[[], None]:
    """Call ``listener(patterns())`` now and whenever the patterns change.

    For the hub's event sources. Returns a function that removes the listener.
    The listener runs in whichever thread changed the subscriptions and must
    not block.
    """
    with _lock:
        _listeners.append(listener)
        current = patterns()
    _safe_call(listener, current)

    def remove():
        with _lock:
            if listener in _listeners:
                _listeners.remove(listener)
    return remove


def _notify():
    current = patterns()
    for listener in list(_listeners):
        _safe_call(listener, current)


def _safe_call(fn, *args):
    try:
        fn(*args)
    except Exception:
        log.exception("event listener %r failed", fn)


def publish(topic: str, data: Any = None) -> None:
    """Deliver ``data`` to everything subscribed to ``topic``.

    Thread-safe and never blocks; handlers run later on the dispatcher thread.
    """
    _segments(topic, wildcards=False)
    event = Event(topic, data)
    _ensure_loop().call_soon_threadsafe(_dispatch, event)


async def apublish(topic: str, data: Any = None) -> None:
    """:func:`publish` for async code; it doesn't block either."""
    publish(topic, data)


def flush(timeout: float = 5.0) -> bool:
    """Wait until every event published so far has been handled.

    Includes ``async`` handlers. Returns False on timeout. Meant for tests.
    """
    loop = _loop
    if loop is None:
        return True
    future = asyncio.run_coroutine_threadsafe(_drain(), loop)
    try:
        future.result(timeout)
        return True
    except TimeoutError:
        return False


def reset() -> None:
    """Drop every subscription and listener. Meant for tests."""
    flush()
    with _lock:
        _subs.clear()
        _listeners.clear()


async def _drain():
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


def _ensure_loop():
    global _loop, _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _loop = asyncio.new_event_loop()
            _thread = threading.Thread(target=_loop.run_forever, name="bdh-events", daemon=True)
            _thread.start()
        return _loop


def _dispatch(event):
    with _lock:
        targets = [s for s in _subs if matches(s.pattern, event.topic)]
    for sub in targets:
        try:
            result = sub.handler(event)
            if inspect.isawaitable(result):
                task = asyncio.ensure_future(_guard(sub, event, result))
                _tasks.add(task)
                task.add_done_callback(_tasks.discard)
        except Exception:
            log.exception("event handler %r failed on %s", sub, event.topic)


async def _guard(sub, event, awaitable):
    try:
        await awaitable
    except Exception:
        log.exception("event handler %r failed on %s", sub, event.topic)