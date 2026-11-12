"""Plugin contract for Black Diamond Hub apps.

Every app (built-in or installed from its own repo) describes itself with a
single ``PluginSpec``. The hub reads these specs to add the app to
INSTALLED_APPS, mount its URLs and put its tiles on the homepage.

This module is the public surface that plugin repos import, so it must stay
free of Django model/settings imports: specs are loaded while settings are
still being built.
"""
from dataclasses import dataclass, field
from datetime import datetime

API_VERSION = 1

# Entry point group that separately installed apps register their spec under.
ENTRY_POINT_GROUP = "blackdiamondhub.plugins"

# Homepage modes. "guest" is used while a stay is active, "dashboard" when the
# lodge is between stays, "owner" when someone is signed in.
GUEST = "guest"
DASHBOARD = "dashboard"
OWNER = "owner"
ALL_MODES = frozenset({GUEST, DASHBOARD, OWNER})
OWNER_ONLY = frozenset({OWNER})

# Homepage sections, in display order.
SECTIONS = {
    "mountain": "On the mountain",
    "lodge": "In the lodge",
    "more": "More",
}


@dataclass(frozen=True)
class Tile:
    """A homepage tile that links to one of the app's pages.

    ``modes`` only controls where the tile is shown. Views behind an
    owner-only tile must still enforce sign-in themselves.
    """

    title: str
    url_name: str
    icon: str  # static path, e.g. "wifi/hub/icon.svg"
    section: str
    subtitle: str = ""
    order: int = 100
    modes: frozenset = ALL_MODES


# Status levels. "on" highlights something that is running (lights on, lifts
# open), "warn" flags a problem the user may want to look at.
INFO = "info"
ON = "on"
WARN = "warn"
STATUS_LEVELS = frozenset({INFO, ON, WARN})


@dataclass(frozen=True)
class Action:
    """A button on a status row or tile, handled by the ``run_action`` hook."""

    id: str
    icon: str  # Font Awesome classes, e.g. "fa-solid fa-pause"
    label: str = ""  # accessible name; the button shows only the icon
    primary: bool = False  # drawn in the accent colour


@dataclass(frozen=True)
class StatusRow:
    """One live item on a tile, e.g. a speaker group that is playing.

    ``image`` is a URL the screen's browser can load. ``dimmed`` greys the
    row out (paused, idle).
    """

    id: str
    title: str
    detail: str = ""
    image: str = ""
    dimmed: bool = False
    actions: tuple[Action, ...] = ()


@dataclass(frozen=True)
class Status:
    """A one-line summary shown on the app's homepage tile.

    With ``rows`` the tile shows them, sized to fit the tile, each with its
    own buttons; ``actions`` are tile-wide buttons, shown when the tile is
    too small for rows. ``refresh`` (seconds) asks the homepage to check
    again that often while this status is showing, for things that change
    quickly; leave it None for the normal once a minute.
    """

    text: str
    level: str = INFO
    rows: tuple[StatusRow, ...] = ()
    actions: tuple[Action, ...] = ()
    refresh: int | None = None


@dataclass(frozen=True)
class Shortcut:
    """A one-tap action shown in the homepage quick actions row.

    Shortcuts are owner-only unless the app lists other modes explicitly,
    because guest and dashboard modes don't require sign-in.
    """

    id: str
    title: str
    icon: str  # Font Awesome classes, e.g. "fa-solid fa-film"
    order: int = 100
    modes: frozenset = OWNER_ONLY


@dataclass(frozen=True)
class Stay:
    """The guests currently staying at the lodge.

    Use timezone-aware datetimes. Don't put door codes or other secrets here:
    the homepage shows these fields on a kiosk anyone can walk up to.
    """

    guest: str
    arrival: datetime | None = None
    checkout: datetime | None = None
    # The owners themselves are staying: the homepage acts as signed in.
    owner: bool = False


@dataclass(frozen=True)
class Reading:
    """A labelled value on the lodge card, e.g. ``Reading("Hot tub", 39, "C")``.

    Temperatures use unit ``"C"`` so the hub can show them in the visitor's
    chosen units.
    """

    label: str
    value: float | str
    unit: str = ""


@dataclass(frozen=True)
class Card:
    """The lodge card at the top of the homepage.

    ``alerts`` are problems worth acting on; tapping the card opens
    ``url_name``. The hub hides both from guests.
    """

    title: str
    detail: str = ""
    readings: tuple[Reading, ...] = ()
    alerts: tuple[str, ...] = ()
    url_name: str | None = None
    level: str = INFO


# Setting types an app can declare. The hub draws the matching control.
BOOL = "bool"
INT = "int"
STR = "str"
CHOICE = "choice"
TIME = "time"  # "HH:MM", 24-hour
SETTING_TYPES = frozenset({BOOL, INT, STR, CHOICE, TIME})


@dataclass(frozen=True)
class Setting:
    """A setting the hub lets admins change on its Settings page.

    The saved value wins over the environment, so the environment (or
    ``default``) becomes the fallback. Read it with
    ``bdh_sdk.settings.app_setting(app_id, key, default)`` as usual.
    Never declare secrets here: they belong in the environment only.

    ``choices`` (for ``choice``) is a tuple of values or ``(value, label)``
    pairs. ``minimum``/``maximum`` bound ``int`` settings; ``unit`` is shown
    after the input (e.g. "min").
    """

    key: str
    label: str
    type: str = STR
    default: object = None
    help: str = ""
    choices: tuple = ()
    minimum: int | None = None
    maximum: int | None = None
    unit: str = ""

    def __post_init__(self):
        if self.type not in SETTING_TYPES:
            raise ValueError(f"setting {self.key!r} has unknown type {self.type!r}")
        if self.type == CHOICE and not self.choices:
            raise ValueError(f"choice setting {self.key!r} needs choices")

    @property
    def options(self) -> tuple:
        """``choices`` as ``(value, label)`` pairs."""
        return tuple(c if isinstance(c, tuple) else (c, str(c)) for c in self.choices)

    def parse(self, raw):
        """Turn form or environment input into a value of this setting's type.

        Raises ``ValueError`` with a message fit to show next to the field.
        """
        if self.type == BOOL:
            if isinstance(raw, bool):
                return raw
            text = str(raw).strip().lower()
            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off", ""}:
                return False
            raise ValueError("Must be on or off.")
        if self.type == INT:
            try:
                value = int(str(raw).strip())
            except ValueError:
                raise ValueError("Must be a whole number.") from None
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"Must be at least {self.minimum}.")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"Must be at most {self.maximum}.")
            return value
        text = str(raw).strip()
        if self.type == CHOICE:
            for value, _label in self.options:
                if text == str(value):
                    return value
            raise ValueError("Pick one of the options.")
        if self.type == TIME:
            hours, sep, minutes = text.partition(":")
            if (sep and hours.isdigit() and minutes.isdigit() and len(minutes) == 2
                    and int(hours) < 24 and int(minutes) < 60):
                return f"{int(hours):02d}:{minutes}"
            raise ValueError("Must be a time like 23:00.")
        return text


@dataclass(frozen=True)
class PluginSpec:
    """Describes one hub app.

    ``id`` is permanent: it names the URL prefix by default and will
    namespace the app's settings and data in future.

    The hooks are dotted paths so this module stays importable before
    Django is set up. They are resolved on first use:

    - ``status``: ``() -> Status | None``. Called in a worker thread with a
      timeout; return None when there is nothing worth showing.
    - ``shortcuts``: ``() -> iterable of Shortcut``.
    - ``run_shortcut``: ``(shortcut_id) -> str | None``. Runs a shortcut the
      hub has already checked is offered in the caller's mode. Raise to
      report failure; the optional return value is shown to the user.
    - ``run_action``: ``(row_id, action_id) -> str | None``. Runs a button
      from the app's current ``Status``; ``row_id`` is ``""`` for a
      tile-wide action. The hub has already checked the status offers it.
      Accepts an optional ``mode`` argument like ``status``.
    - ``websocket_routes``: a list of Channels URL patterns (e.g.
      ``"myapp.routing.websocket_urlpatterns"``). Imported by the ASGI
      application after Django is set up and mounted under the shared
      websocket router.
    - ``stay``: ``() -> Stay | None``. Reports the stay in progress, if any;
      the homepage is in guest mode while one is reported. Called like
      ``status`` (worker thread, timeout, cached briefly).
    - ``card``: ``() -> Card | None``. The lodge card shown at the top of
      the homepage in every mode; the first app that provides one is used.
      Called like ``status``.

    ``settings`` lists the :class:`Setting` objects admins can change on the
    hub's Settings page; the app gets its own section there when non-empty.
    """

    id: str
    app: str  # Django app module or AppConfig path for INSTALLED_APPS
    urls: str | None = None  # URLconf module, mounted at url_prefix
    url_prefix: str | None = None  # defaults to "<id>/"
    tiles: tuple[Tile, ...] = field(default_factory=tuple)
    status: str | None = None
    shortcuts: str | None = None
    run_shortcut: str | None = None
    run_action: str | None = None
    websocket_routes: str | None = None
    stay: str | None = None
    card: str | None = None
    settings: tuple[Setting, ...] = field(default_factory=tuple)
    api_version: int = API_VERSION

    @property
    def prefix(self) -> str:
        return self.url_prefix if self.url_prefix is not None else f"{self.id}/"
