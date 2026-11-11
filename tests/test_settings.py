import os
import subprocess
import sys
import types
import unittest
from importlib.util import find_spec
from unittest import mock

from bdh_sdk.settings import MissingSetting, app_setting, as_bool, set_store, setting_name


def fake_django(**attrs):
    """sys.modules entries that make ``from django.conf import settings`` work."""
    django = types.ModuleType("django")
    conf = types.ModuleType("django.conf")
    conf.settings = types.SimpleNamespace(**attrs)
    django.conf = conf
    return {"django": django, "django.conf": conf}


NO_DJANGO = {"django": None, "django.conf": None}


class AppSettingTests(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("BDH_") and not k.startswith("WIFI_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_setting_name(self):
        self.assertEqual(setting_name("wifi", "ssid"), "BDH_WIFI_SSID")
        self.assertEqual(setting_name("ski-cams", "base.url"), "BDH_SKI_CAMS_BASE_URL")

    def test_precedence(self):
        django = fake_django(configured=True, BDH_WIFI_SSID="dj-ns", WIFI_SSID="dj-legacy")
        with mock.patch.dict(sys.modules, django):
            os.environ["BDH_WIFI_SSID"] = "env-ns"
            os.environ["WIFI_SSID"] = "env-legacy"
            self.assertEqual(app_setting("wifi", "ssid", "d", legacy=["WIFI_SSID"]), "env-ns")
            del os.environ["BDH_WIFI_SSID"]
            self.assertEqual(app_setting("wifi", "ssid", "d", legacy=["WIFI_SSID"]), "env-legacy")
            del os.environ["WIFI_SSID"]
            self.assertEqual(app_setting("wifi", "ssid", "d", legacy=["WIFI_SSID"]), "dj-ns")
            del django["django.conf"].settings.BDH_WIFI_SSID
            self.assertEqual(app_setting("wifi", "ssid", "d", legacy=["WIFI_SSID"]), "dj-legacy")
            del django["django.conf"].settings.WIFI_SSID
            self.assertEqual(app_setting("wifi", "ssid", "d", legacy=["WIFI_SSID"]), "d")

    def test_first_set_legacy_env_wins(self):
        os.environ["WIFI_OLD"] = "old"
        os.environ["WIFI_OLDER"] = "older"
        with mock.patch.dict(sys.modules, NO_DJANGO):
            self.assertEqual(
                app_setting("wifi", "ssid", legacy=("WIFI_MISSING", "WIFI_OLD", "WIFI_OLDER")),
                "old",
            )
            self.assertEqual(app_setting("wifi", "ssid", legacy="WIFI_OLDER"), "older")

    def test_unconfigured_django_settings_ignored(self):
        with mock.patch.dict(sys.modules, fake_django(configured=False, BDH_WIFI_SSID="dj")):
            self.assertEqual(app_setting("wifi", "ssid", "d"), "d")

    def test_without_django(self):
        with mock.patch.dict(sys.modules, NO_DJANGO):
            self.assertEqual(app_setting("wifi", "ssid", None), None)
            os.environ["BDH_WIFI_SSID"] = "lodge"
            self.assertEqual(app_setting("wifi", "ssid"), "lodge")

    def test_missing_raises(self):
        with mock.patch.dict(sys.modules, NO_DJANGO):
            with self.assertRaises(MissingSetting) as cm:
                app_setting("wifi", "ssid", legacy=["WIFI_SSID"])
        self.assertIsInstance(cm.exception, KeyError)
        self.assertIn("BDH_WIFI_SSID", str(cm.exception))
        self.assertIn("WIFI_SSID", str(cm.exception))

    def test_cast(self):
        os.environ["BDH_WIFI_PORT"] = "8080"
        os.environ["BDH_WIFI_ENABLED"] = "Yes"
        with mock.patch.dict(sys.modules, fake_django(configured=True, BDH_WIFI_LIMIT=5)):
            self.assertEqual(app_setting("wifi", "port", cast=int), 8080)
            self.assertIs(app_setting("wifi", "enabled", cast=as_bool), True)
            # Non-string values are returned unchanged.
            self.assertIs(app_setting("wifi", "debug", False, cast=as_bool), False)
            self.assertEqual(app_setting("wifi", "limit", cast=str.upper), 5)
            self.assertEqual(app_setting("wifi", "retries", "3", cast=int), 3)

    def test_as_bool(self):
        for value in ("1", "true", "TRUE", "yes", "on", " On ", True):
            self.assertIs(as_bool(value), True, value)
        for value in ("0", "false", "no", "off", "", False):
            self.assertIs(as_bool(value), False, value)
        with self.assertRaises(ValueError):
            as_bool("maybe")


@unittest.skipIf(find_spec("django") is None, "Django not installed")
class RealDjangoTests(unittest.TestCase):
    def test_reads_configured_django_settings(self):
        code = (
            "from django.conf import settings\n"
            "from bdh_sdk.settings import app_setting\n"
            "assert app_setting('wifi', 'ssid', 'd', legacy=['WIFI_SSID']) == 'd'\n"
            "settings.configure(WIFI_SSID='from-django')\n"
            "print(app_setting('wifi', 'ssid', 'd', legacy=['WIFI_SSID']))\n"
        )
        env = {k: v for k, v in os.environ.items()
               if k not in ("DJANGO_SETTINGS_MODULE", "BDH_WIFI_SSID", "WIFI_SSID")}
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "from-django")


if __name__ == "__main__":
    unittest.main()

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_store, None)
        patcher = mock.patch.dict(os.environ, {"BDH_WIFI_SSID": "env"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saved_value_beats_environment(self):
        set_store(lambda app_id, key: {("wifi", "ssid"): "saved"}[(app_id, key)])
        with mock.patch.dict(sys.modules, NO_DJANGO):
            self.assertEqual(app_setting("wifi", "ssid"), "saved")
            # Nothing saved for this key: falls through to the default.
            self.assertEqual(app_setting("wifi", "other", "d"), "d")

    def test_nothing_saved_falls_back_to_environment(self):
        def lookup(app_id, key):
            raise KeyError(key)
        set_store(lookup)
        with mock.patch.dict(sys.modules, NO_DJANGO):
            self.assertEqual(app_setting("wifi", "ssid"), "env")

    def test_cast_applies_to_saved_strings_only(self):
        set_store(lambda app_id, key: {"n": "5", "b": True}[key])
        with mock.patch.dict(sys.modules, NO_DJANGO):
            self.assertEqual(app_setting("wifi", "n", cast=int), 5)
            self.assertIs(app_setting("wifi", "b", cast=as_bool), True)
