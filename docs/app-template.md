# Hub app repo template

Each hub app lives in its own repo under `blackdiamondlodge` (e.g.
`bdh-app-wifi`) and is installed into the hub as an ordinary Python package.
The hub finds it through the `blackdiamondhub.plugins` entry point.

Below, `<id>` is the app's permanent plugin id, which is also its Python
package name (e.g. `wifi`).

## Layout

```
bdh-app-<id>/
├── pyproject.toml
├── README.md
├── <id>/
│   ├── __init__.py
│   ├── apps.py
│   ├── plugin.py              # spec = PluginSpec(...)  (no Django imports!)
│   ├── urls.py
│   ├── views.py
│   ├── models.py
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/<id>/...     # namespaced: templates/<id>/index.html
│   ├── static/<id>/...        # namespaced: static/<id>/hub/icon.svg
│   └── tests/
│       └── __init__.py
└── .github/workflows/ci.yml
```

Templates and static files are namespaced under the app id so they never
collide with the hub's or another app's files.

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "bdh-app-wifi"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "bdh-sdk>=0.1,<1",
]

[project.entry-points."blackdiamondhub.plugins"]
wifi = "wifi.plugin:spec"

[tool.setuptools.packages.find]
include = ["wifi", "wifi.*"]

[tool.setuptools.package-data]
# "**" matches nested directories, so templates/wifi/partials/x.html and
# static/wifi/hub/icon.svg are both included.
wifi = [
    "templates/**/*",
    "static/**/*",
    "migrations/*.py",
]
```

`packages.find` picks up `wifi.migrations` and `wifi.tests` as packages
(they have `__init__.py`); the `package-data` globs pull in the
non-Python files. Check a build with:

```
python -m build --wheel
python -m zipfile -l dist/bdh_app_wifi-0.1.0-py3-none-any.whl
```

`bdh-sdk` is not on PyPI. Install it from GitHub before installing the app,
e.g. `pip install "bdh-sdk @ git+https://github.com/blackdiamondlodge/bdh-sdk@v0"`.

## `<id>/plugin.py`

```python
from bdh_sdk import ALL_MODES, PluginSpec, Tile

spec = PluginSpec(
    id="wifi",
    app="wifi",
    urls="wifi.urls",
    tiles=(
        Tile(
            title="Wi-Fi",
            url_name="wifi:index",
            icon="wifi/hub/icon.svg",
            section="lodge",
            modes=ALL_MODES,
        ),
    ),
    status="wifi.homepage.status",
)
```

This module is imported while the hub's settings are being built, so it
must not import Django models or views, `requests`, or the app's
`homepage` module, and must not start threads. Put hook code in other
modules and reference it by dotted path. CI checks this with
`bdh_sdk.testing.assert_plugin_importable("wifi.plugin")`.

Read configuration with `bdh_sdk.settings.app_setting`:

```python
from bdh_sdk.settings import app_setting

SSID = app_setting("wifi", "ssid", legacy=["WIFI_SSID"])
```

## `.github/workflows/ci.yml`

```yaml
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
