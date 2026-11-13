# bdh-sdk

The Black Diamond Hub SDK: the small contract package that hub apps import to
describe themselves to [Black Diamond Hub](https://github.com/blackdiamondlodge/BlackDiamondHub).

Hub apps are Django apps that live in their own repos (e.g. `bdh-app-wifi`)
and register a `blackdiamondhub.plugins` entry point that resolves to a
`PluginSpec`. `bdh-sdk` has no runtime dependencies and never imports or
configures Django on import, so app `plugin.py` modules can use it while the
hub's settings are still being built.

See [docs/app-template.md](docs/app-template.md) for the layout of an app repo.

## Install

`bdh-sdk` is not published to PyPI. Install a tagged release from GitHub:

```
pip install "bdh-sdk @ git+https://github.com/blackdiamondlodge/bdh-sdk@v0.1.0"
```

or download the wheel attached to the GitHub release (its sha256 is in the
release notes). Apps depend on `bdh-sdk>=0.1,<1`.

## Plugin contract

```python
from bdh_sdk import PluginSpec, Tile, OWNER_ONLY

spec = PluginSpec(
    id="wifi",
    app="wifi",
    urls="wifi.urls",              # mounted at "wifi/" (spec.prefix)
    tiles=(Tile(title="Wi-Fi", url_name="wifi:index",
                icon="wifi/hub/icon.svg", section="lodge"),),
    status="wifi.homepage.status",
    websocket_routes="wifi.routing.websocket_urlpatterns",
)
```

`bdh_sdk` exports `API_VERSION`, `ENTRY_POINT_GROUP`
(`"blackdiamondhub.plugins"`), the homepage modes `GUEST`, `DASHBOARD`,
`OWNER`, `ALL_MODES`, `OWNER_ONLY`, `SECTIONS`, the status levels `INFO`,
`ON`, `WARN`, `STATUS_LEVELS`, and the frozen dataclasses `PluginSpec`,
`Tile`, `Status`, `StatusRow`, `Action`, `Shortcut`, `Stay`, `Card`, `Reading` and
`Setting`. Hooks (`status`, `shortcuts`, `run_shortcut`, `run_action`,
`websocket_routes`, `stay`, `card`) are dotted
`module.attribute` paths that the hub resolves lazily.

A `status` hook can return live `rows` (`StatusRow`: title, detail,
image URL, `dimmed`, and `Action` buttons) instead of just a line of text,
e.g. the speaker groups that are playing. The tile shows as many as fit its
size; tile-wide `actions` are used when it is too small for rows. Taps call
`run_action(row_id, action_id)` (`row_id` is `""` for tile-wide actions).
Set `Status.refresh` (seconds) for things that change quickly: the
homepage checks that often while the status is showing.

A `stay` hook returns the `Stay` in progress (guest name, arrival, checkout)
or None. While an app reports a stay the homepage is in guest mode and
welcomes the guest by name. Never put door codes in it: the homepage is a
kiosk. A stay with `owner=True` is an owner visit: the homepage acts as
signed in until it ends.

A `card` hook returns the lodge `Card` shown at the top of the homepage in
every mode (title, detail line, `Reading`s such as temperatures, and
alerts). Tapping it opens `url_name`; guests see neither alerts nor the
link.

## Provided data

Apps can offer data to other parts of the hub (today: the screensaver) with
`provides`, a map from capability to a zero-argument callable. An app with
no tiles or URLs that only provides data and settings is fine.

```python
from bdh_sdk import PluginSpec, STATS, Stat

spec = PluginSpec(
    id="weather",
    app="weather",
    provides={STATS: "weather.provide.stats"},
    stat_keys=(("temp", "Temperature"), ("sunrise", "Sunrise")),
)

# weather/provide.py
def stats():
    now = cached_conditions()            # return quickly, from your own cache
    yield Stat("temp", "Temperature", value=f"{now.temp:.0f}°C")
    yield Stat("sunrise", "Sunrise", time=now.sunrise)   # timezone-aware
```

| capability | returns | used for |
|---|---|---|
| `STATS` (`"stats"`) | iterable of `Stat` | screensaver info strip |
| `BACKGROUNDS` (`"backgrounds"`) | iterable of `Background` | screensaver live cam |
| `SEASON` (`"season"`) | `SeasonHint` or None | bringing winter forward (e.g. lifts open) |

- `Stat` has exactly one of `value` (formatted, with units) or `time`
  (timezone-aware). Declare every key in `stat_keys`: the settings page
  lists them without calling the app, and undeclared keys are dropped.
  Other code refers to a stat as `"<plugin id>.<key>"`, e.g.
  `weather.sunrise`.
- `Background(id, label, image_url, refresh_seconds=60)`: the screen
  reloads the URL every `refresh_seconds`, so a stable URL is fine.
- `SeasonHint("winter", reason)` can only bring winter forward.

The hub calls providers in worker threads with a short deadline and keeps
the last good result, so a slow upstream never stalls a screen.

## App settings

```python
from bdh_sdk.settings import app_setting, as_bool

ssid = app_setting("wifi", "ssid", legacy=["WIFI_SSID"])
show_qr = app_setting("wifi", "show_qr", True, cast=as_bool)
```

`app_setting(app_id, key, default=..., *, legacy=(), cast=None)` looks the
setting up in this order and returns the first hit:

0. The value saved on the hub's Settings page. The hub installs a store
   with `bdh_sdk.settings.set_store(lookup)`; `lookup(app_id, key)` returns
   the saved value or raises `KeyError`.
1. Environment variable `BDH_<APPID>_<KEY>`: upper-cased, every
   non-alphanumeric character replaced by `_` (`("ski-cams", "base.url")` ->
   `BDH_SKI_CAMS_BASE_URL`).
2. The first environment variable in `legacy` that is set (old
   un-namespaced names such as `WIFI_SSID`).
3. Django settings, only if Django is installed **and** configured:
   `settings.BDH_<APPID>_<KEY>`, then each `legacy` name.
4. `default`.

An environment variable counts as set when it is present, even if empty.
With no value and no default, `bdh_sdk.settings.MissingSetting` (a
`KeyError`) is raised. `cast` is applied only to string values; `as_bool`
accepts `1/true/yes/on` and `0/false/no/off` (case-insensitive).

### Settings page

Declare the settings admins may change from the hub, and the hub gives the
app a section on its staff-only Settings page:

```python
from bdh_sdk import PluginSpec, Setting
from bdh_sdk.plugins import BOOL, INT

spec = PluginSpec(
    id="wifi", app="wifi",
    settings=(
        Setting("show_qr", "Show QR code", type=BOOL, default=True),
        Setting("refresh", "Refresh every", type=INT, default=5,
                minimum=1, maximum=60, unit="min"),
    ),
)
```

Types are `BOOL`, `INT` (optional `minimum`/`maximum`), `STR`, `CHOICE`
(`choices` of values or `(value, label)` pairs), `MULTI` (a list of values
picked from `choices`, drawn as checkboxes) and `TIME` (`"HH:MM"`). For
options only known at run time, pass `choices_from="myapp.module.func"`
instead of `choices`: a zero-argument callable returning the same pairs,
called whenever the Settings page is drawn. A `MULTI` setting with
`choices_from` keeps picked values the callable no longer returns (e.g. a
speaker that is offline). In the environment a `MULTI` value is a JSON list
or comma-separated text; read it with `app_setting(..., cast=as_list)`
(`from bdh_sdk.plugins import as_list`).
`Setting.parse(raw)` validates input and raises `ValueError` with a message
for the form. Saved values win over the environment, so keep reading them
with `app_setting`. Never declare secrets as settings.

For anything a flat list can't hold (say, a list of calendar feeds), the
app can draw its own pages and list them in `settings_pages`; the hub links
them from the app's section:

```python
from bdh_sdk import SettingsPage

settings_pages=(SettingsPage("Feeds", "calendar:feeds", subtitle="iCal links"),)
```

`url_name` is reversed by the hub. The view must check `is_admin(request)`
itself. Its template can `{% extends "hub_settings/_layout.html" %}` and fill
`{% block section %}` to sit inside the hub's Settings navigation.

## App state and media

Apps that need to remember something between runs (not a setting a person
edits) use a per-app key/value store. Values must be JSON-serializable:

```python
from bdh_sdk.storage import app_state

state = app_state("display")
opened = state.get("lifts_opened")          # None when unset
state.set("lifts_opened", "2026-11-21")
state.delete("lifts_opened"); state.keys(); "lifts_opened" in state
```

The hub installs a database backend with
`bdh_sdk.storage.set_state_backend(backend)` (`get` raising `KeyError`,
`set`, `delete`, `keys`). Without one, state lives in memory, which is what
unit tests get.

Files an app stores go in its own folder via a Django storage rooted at
`MEDIA_ROOT/apps/<app_id>/` (served at `MEDIA_URL + "apps/<app_id>/"`):

```python
from bdh_sdk.storage import app_media

storage = app_media("display")
name = storage.save("photos/lake.jpg", uploaded_file)
url = storage.url(name)
```

App ids must be lower-case letters, digits and `_`.

## Units

The hub has one units setting, metric or imperial, for every app: the °C/°F
switch in its title bar (a site sets the starting value with
`[apps.hub] units` in its `site.toml`). Apps read it and show their numbers
in it; they can't change it. An app may offer its own view-only switch by
passing the choice to `units()`.

```python
from bdh_sdk.units import system, units

system()              # "metric" or "imperial"
u = units()           # or units(request.GET.get("units")) for a view-only switch
u.temp_text(15.6)     # "16°C" / "60°F"
u.speed_text(10)      # "10 km/h" / "6 mph"
u.length_text(1000)   # "1,000 m" / "3,281 ft"
u.t(15.6), u.temp_unit  # 16, "°C"
```
## Location

The hub has one location, set by an admin under Settings > Location: a city
picked from a search, and its time zone (taken from the city unless the admin
picks another). Apps read it; they can't change it.

```python
from bdh_sdk.location import location, tzinfo

where = location()        # None until the hub's location is set
where.label               # "Sun Peaks, British Columbia, Canada"
where.name                # "Sun Peaks"
where.latitude, where.longitude  # 50.88, -119.91 (None if unknown)
where.timezone            # "America/Vancouver"
tzinfo()                  # ZoneInfo("America/Vancouver"); UTC when unset
```
## Branding

`bdh_sdk.branding.brand()` returns the site's `name`, `subtitle` and
`monogram` / `monogram_light` SVG paths; `monogram_svg(light=False)` returns
the SVG text (100x100 viewBox; `light` is the version for dark backgrounds).
The hub sets them per site through `settings.HUB_BRAND`. Anything a site
leaves out falls back to "Black Diamond Hub" and the BDH monogram shipped
with the SDK.

## QR codes

`bdh_sdk.qr.qr_svg(text)` returns an SVG QR code in the hub style: round
dots, square finder patterns and the site's monogram in the centre (error
correction H keeps it scannable). Text over 200 characters drops to error
correction L with a smaller monogram so the code isn't too dense to scan.
Pass `logo=<svg text>` to use a different centre image. Install the
`bdh-sdk[qr]` extra; the hub already ships `qrcode`.

```python
from bdh_sdk.qr import qr_svg

svg = qr_svg("http://192.168.10.216/settings/display/upload/abc/")
```

## Alerts

`bdh_sdk.alerts.push(Alert(...))` pops a modal up on every hub screen, in
every mode and on every page, waking the screensaver. It shows `title`, an optional
`body` and an `<iframe>` of `embed_url`, which must be a path on the hub. The modal closes
after `ttl` seconds (1-600, default 60), or when someone taps X or the
backdrop. Pushing again with the same `key` while it's showing restarts the timer;
a different alert replaces it. Nothing goes to phones.

```python
from bdh_sdk.alerts import Alert, push

push(Alert(app="cameras", key="doorbell:front", title="Someone's at the door",
           embed_url="/cameras/popup/front/", ttl=60))
```

`push` never blocks and is safe from any thread, including one running its own
event loop. Async code can `await apush(alert)`. The hub installs the delivery
function with `set_sender`. Without one (unit tests, scripts), pushing only
logs at debug level. Import `bdh_sdk.alerts` inside your worker, not in `plugin.py`.

## Events

`bdh_sdk.events` lets apps react to things happening elsewhere without talking
to Home Assistant (or anything else) directly. The hub runs event sources,
declared per site in `site.toml`, and publishes what they see; apps subscribe.

```python
from bdh_sdk import events

def door(event):  # event.topic, event.data, event.time, event.source
    if event.data["new"] == "on" and event.data["old"] == "off":
        ...

events.subscribe("ha/state/binary_sensor.front_door", door)
events.publish("cameras/doorbell/front", {"camera": "front"})  # your own events
```

- Topics are `/`-separated. The first segment is the source name from
  `site.toml` (e.g. `ha`, `sunpeaks`, `hook`) or the publishing app's id; apps
  publish under their own id.
- Home Assistant sources publish `<source>/state/<entity_id>` with data
  `{"entity_id", "old", "new", "attributes"}`. They only fetch entities
  someone subscribed to, so subscribe to exact entities where you can.
- Patterns take MQTT wildcards: `+` is one segment, a trailing `#` is the rest.
- Handlers run on one shared dispatcher thread and must not block. Plain
  functions are called directly; `async def` handlers run as tasks there. An
  exception is logged and doesn't affect other handlers.
- Delivery is best effort: nothing is replayed after a source reconnects.
- `subscribe` returns a `Subscription` with `cancel()`. Subscribe from your
  `AppConfig.ready()` (or your worker), never at `plugin.py` import time.
- `publish` is thread-safe and never blocks; async code can
  `await events.apublish(...)`.
- Tests: `events.flush()` waits for pending handlers and `events.reset()`
  drops all subscriptions.

## Admin check

`is_admin(request)` is true when a signed-in, active hub admin (Django staff
user) made the request. Use it instead of reading `request.user` fields, so
every app follows the hub's rule and never touches the user table.

```python
from bdh_sdk import is_admin

if not is_admin(request):
    return HttpResponseForbidden()
```

## Home Assistant client

`bdh_sdk.ha` talks to Home Assistant for apps that need it (install the
`bdh-sdk[ha]` extra; the hub already ships `requests` and `websocket-client`).
The connection comes from `HOMEASSISTANT_URL` and
`HOMEASSISTANT_ACCESS_TOKEN`, read from Django settings and then the
environment.

```python
from bdh_sdk import ha

state = ha.get_entity_state("light.kitchen")       # dict or None
ok, err = ha.call_service("light", "turn_on", "light.kitchen")
```

Read helpers (`get_entity_state`, `get_entity_states`, `get_history`) return
`None`/`{}` when HA is unreachable, so pages can still render.
`get_all_states`, `get_static` and `ws_commands` raise `ha.HAError` instead.

## Testing helpers

```python
from bdh_sdk.testing import assert_plugin_importable

assert_plugin_importable("wifi.plugin")
```

Imports the module in a fresh interpreter and fails if it doesn't expose a
`PluginSpec` named `spec`, sets up Django or configures settings, starts
threads, or imports `requests`, any `*.models` module, or the app's `views`
or `homepage` modules. Pass `forbidden=("name", ...)` to ban more modules.

## Reusable CI for app repos

`.github/workflows/app-ci.yml` is a reusable workflow. In an app repo:

```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  hub:
    uses: blackdiamondlodge/bdh-sdk/.github/workflows/app-ci.yml@v0
    with:
      app_id: wifi
```

It checks out the app (into `app/`) and `blackdiamondlodge/BlackDiamondHub`
(into `hub/`), installs the hub requirements and `bdh-sdk`, builds and
installs the app wheel, then:

- runs `assert_plugin_importable("<app_id>.plugin")` against the installed wheel;
- runs `manage.py check` and `manage.py collectstatic --noinput` with
  `DJANGO_SETTINGS_MODULE=BlackDiamondHub.settings_test`;
- runs `manage.py hub_smoke --app <app_id>` (plugin loaded via entry point,
  tile URLs reverse and return < 500 for a superuser, icon resolves);
- runs `manage.py test <test_module> --exclude-tag=selenium`;
- in a second job (input `selenium`, default true), runs the app's tests
  tagged `selenium` in the runner's headless Chrome (with a go2rtc server
  on `localhost:1984` when `go2rtc: true`).

Inputs: `app_id` (required), `hub_ref` (default `main`), `python-version`
(default `3.12`), `test_module` (default `app_id`), `sdk_ref` (default
`v0`), `selenium` (default true), `go2rtc` (default false). Optional secret `hub_token` if the hub repo is private.

`.github/workflows/app-release.yml` is the matching reusable release
workflow. Call it on pushes to `main` (with `permissions: contents: write`).
The first time a `pyproject.toml` version lands on main it tags
`v<version>`, builds the wheel and publishes a GitHub release. The release
notes include the hashed line to paste into the hub's
`sites/<site>/apps.txt`, which is also available as the `requirement`
output.

## Development

```
python -m unittest discover -s tests -v
python -m build
```

## Releasing

Bump `version` in `pyproject.toml` and `bdh_sdk/__init__.py` and merge to
`main`. `release.yml` tags `v<version>`, moves the major tag (e.g. `v0`),
and creates a GitHub release with the wheel and sdist attached. If the tag
already exists the workflow does nothing.

## License

MIT
