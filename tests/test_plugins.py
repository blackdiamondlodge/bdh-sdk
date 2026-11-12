import dataclasses
import json
import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

import bdh_sdk
from bdh_sdk.plugins import BOOL, CHOICE, INT, MULTI, TIME
from bdh_sdk import (
    ALL_MODES,
    API_VERSION,
    Card,
    ENTRY_POINT_GROUP,
    INFO,
    OWNER,
    OWNER_ONLY,
    PluginSpec,
    SettingsPage,
    Reading,
    Setting,
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
                     "run_shortcut", "run_action", "websocket_routes", "stay", "card"):
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

def _rooms():
    return [("u1", "Kitchen"), "u2"]


def _broken():
    raise OSError("no network")


class SettingTests(unittest.TestCase):
    def test_parse_by_type(self):
        self.assertIs(Setting("a", "A", type=BOOL).parse("on"), True)
        self.assertIs(Setting("a", "A", type=BOOL).parse(""), False)
        self.assertEqual(Setting("a", "A", type=INT, minimum=1, maximum=60).parse(" 15 "), 15)
        self.assertEqual(Setting("a", "A", type=TIME).parse("6:00"), "06:00")
        self.assertEqual(Setting("a", "A").parse("  hi "), "hi")
        pick = Setting("a", "A", type=CHOICE, choices=(("fall", "Fall"), "winter"))
        self.assertEqual(pick.options, (("fall", "Fall"), ("winter", "winter")))
        self.assertEqual(pick.parse("winter"), "winter")
        multi = Setting("a", "A", type=MULTI, choices=("x", "y", "z"))
        self.assertEqual(multi.parse(["y", "x", "y"]), ["y", "x"])
        self.assertEqual(multi.parse(" x, z "), ["x", "z"])
        self.assertEqual(multi.parse('["z"]'), ["z"])
        self.assertEqual(multi.parse(""), [])

    def test_choices_from_callable(self):
        dyn = Setting("a", "A", type=MULTI, choices_from="tests.test_plugins._rooms")
        self.assertEqual(dyn.options, (("u1", "Kitchen"), ("u2", "u2")))
        # Values the callable no longer offers (an offline device) are kept.
        self.assertEqual(dyn.parse(["u1", "gone"]), ["u1", "gone"])
        broken = Setting("a", "A", type=CHOICE, choices_from="tests.test_plugins._broken")
        self.assertEqual(broken.options, ())

    def test_parse_rejects_bad_input(self):
        cases = [
            (Setting("a", "A", type=BOOL), "maybe"),
            (Setting("a", "A", type=INT), "1.5"),
            (Setting("a", "A", type=INT, minimum=1), "0"),
            (Setting("a", "A", type=INT, maximum=60), "61"),
            (Setting("a", "A", type=TIME), "24:00"),
            (Setting("a", "A", type=TIME), "7:5"),
            (Setting("a", "A", type=CHOICE, choices=("x",)), "y"),
            (Setting("a", "A", type=MULTI, choices=("x",)), "x,y"),
            (Setting("a", "A", type=MULTI, choices=("x",)), '{"x": 1}'),
        ]
        for setting, raw in cases:
            with self.subTest(setting=setting.type, raw=raw), self.assertRaises(ValueError):
                setting.parse(raw)

    def test_declaration_is_checked(self):
        with self.assertRaises(ValueError):
            Setting("a", "A", type="colour")
        with self.assertRaises(ValueError):
            Setting("a", "A", type=CHOICE)
        with self.assertRaises(ValueError):
            Setting("a", "A", type=MULTI)

    def test_spec_settings_default_empty(self):
        self.assertEqual(PluginSpec(id="wifi", app="wifi").settings, ())

    def test_settings_pages(self):
        page = SettingsPage("Feeds", "calendar:feeds", subtitle="iCal links")
        spec = PluginSpec(id="calendar", app="calendar", settings_pages=(page,))
        self.assertEqual(spec.settings_pages[0].url_name, "calendar:feeds")
        self.assertEqual(PluginSpec(id="wifi", app="wifi").settings_pages, ())
        with self.assertRaises(ValueError):
            SettingsPage("", "calendar:feeds")
