import dataclasses
import json
import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

import bdh_sdk
from bdh_sdk import (
    ALL_MODES,
    API_VERSION,
    Card,
    ENTRY_POINT_GROUP,
    INFO,
    OWNER,
    OWNER_ONLY,
    PluginSpec,
    Reading,
    Shortcut,
    Stay,
    Status,
    Tile,
)


class ContractTests(unittest.TestCase):
    def test_spec_defaults(self):
        spec = PluginSpec(id="wifi", app="wifi")
        self.assertEqual(spec.api_version, API_VERSION)
        self.assertEqual(spec.tiles, ())
        for name in ("urls", "url_prefix", "status", "shortcuts",
                     "run_shortcut", "websocket_routes", "stay", "card"):
            self.assertIsNone(getattr(spec, name), name)

    def test_prefix_defaults_to_id_and_honours_override(self):
        self.assertEqual(PluginSpec(id="wifi", app="wifi").prefix, "wifi/")
        self.assertEqual(
            PluginSpec(id="wifi", app="wifi", url_prefix="net/").prefix, "net/"
        )
        self.assertEqual(PluginSpec(id="home", app="home", url_prefix="").prefix, "")

    def test_tile_status_shortcut_defaults(self):
        tile = Tile(title="Wi-Fi", url_name="wifi:index",
                    icon="wifi/hub/icon.svg", section="lodge")
        self.assertEqual((tile.subtitle, tile.order, tile.modes), ("", 100, ALL_MODES))
        self.assertEqual(Status("ok").level, INFO)
        shortcut = Shortcut(id="movie", title="Movie", icon="fa-solid fa-film")
        self.assertEqual(shortcut.modes, OWNER_ONLY)
        self.assertEqual(OWNER_ONLY, frozenset({OWNER}))

    def test_dataclasses_are_frozen(self):
        objs = [
            PluginSpec(id="wifi", app="wifi"),
            Tile(title="t", url_name="u", icon="i", section="more"),
            Status("x"),
            Shortcut(id="s", title="t", icon="i"),
            Stay("Smith"),
            Card("Vacation mode"),
            Reading("Hot tub", 39, "C"),
        ]
        for obj in objs:
            field = dataclasses.fields(obj)[0].name
            with self.subTest(type(obj).__name__), \
                    self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(obj, field, "changed")

    def test_package_metadata(self):
        self.assertEqual(ENTRY_POINT_GROUP, "blackdiamondhub.plugins")
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with pyproject.open("rb") as f:
            self.assertEqual(bdh_sdk.__version__, tomllib.load(f)["project"]["version"])
        for name in bdh_sdk.__all__:
            self.assertTrue(hasattr(bdh_sdk, name), name)

    def test_import_does_not_load_django(self):
        code = (
            "import sys, json, bdh_sdk, bdh_sdk.settings, bdh_sdk.testing;"
            "print(json.dumps(sorted(m for m in sys.modules if m.split('.')[0] == 'django')))"
        )
        env = dict(os.environ)
        env.pop("DJANGO_SETTINGS_MODULE", None)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout), [])


if __name__ == "__main__":
    unittest.main()
