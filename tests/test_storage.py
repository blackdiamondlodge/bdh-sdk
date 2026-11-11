import os
import tempfile
import unittest
from importlib.util import find_spec

from bdh_sdk.storage import MemoryStateBackend, app_media, app_state, set_state_backend


class AppStateTests(unittest.TestCase):
    def setUp(self):
        set_state_backend(None)
        self.addCleanup(set_state_backend, None)

    def test_round_trip_and_default(self):
        state = app_state("display")
        self.assertIsNone(state.get("opened"))
        self.assertEqual(state.get("opened", "never"), "never")
        state.set("opened", {"date": "2026-11-21"})
        self.assertEqual(state.get("opened"), {"date": "2026-11-21"})
        self.assertIn("opened", state)
        state.delete("opened")
        self.assertNotIn("opened", state)

    def test_apps_are_isolated(self):
        app_state("a").set("k", 1)
        self.assertIsNone(app_state("b").get("k"))
        self.assertEqual(app_state("a").keys(), ["k"])
        self.assertEqual(app_state("b").keys(), [])

    def test_returned_values_are_copies(self):
        state = app_state("a")
        state.set("k", [1])
        state.get("k").append(2)
        self.assertEqual(state.get("k"), [1])

    def test_rejects_unserializable_value_and_bad_app_id(self):
        with self.assertRaises(TypeError):
            app_state("a").set("k", object())
        for bad in ("", "../x", "Display", None):
            with self.assertRaises(ValueError):
                app_state(bad)

    def test_installed_backend_is_used(self):
        backend = MemoryStateBackend()
        set_state_backend(backend)
        app_state("a").set("k", 2)
        self.assertEqual(backend.get("a", "k"), 2)


@unittest.skipUnless(find_spec("django"), "Django not installed")
class AppMediaTests(unittest.TestCase):
    def test_storage_is_scoped_to_app(self):
        from django.conf import settings

        with tempfile.TemporaryDirectory() as root:
            if not settings.configured:
                settings.configure()
            with self.settings_override(MEDIA_ROOT=root, MEDIA_URL="/media/"):
                storage = app_media("display")
                self.assertEqual(storage.location, os.path.join(root, "apps", "display"))
                self.assertEqual(storage.url("a.jpg"), "/media/apps/display/a.jpg")
        with self.assertRaises(ValueError):
            app_media("../etc")

    def settings_override(self, **kw):
        from django.test.utils import override_settings
        return override_settings(**kw)


if __name__ == "__main__":
    unittest.main()
