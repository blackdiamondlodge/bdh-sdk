import os
import sys
import unittest
from unittest import mock

from bdh_sdk import units
from bdh_sdk.settings import set_store

NO_DJANGO = {"django": None, "django.conf": None}


class UnitsTests(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("BDH_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        modules = mock.patch.dict(sys.modules, NO_DJANGO)
        modules.start()
        self.addCleanup(modules.stop)
        self.addCleanup(set_store, None)

    def test_system_defaults_to_metric(self):
        self.assertEqual(units.system(), "metric")

    def test_system_follows_hub_setting(self):
        os.environ["BDH_HUB_UNITS"] = " Imperial "
        self.assertEqual(units.system(), "imperial")
        os.environ["BDH_HUB_UNITS"] = "bogus"
        self.assertEqual(units.system(), "metric")

    def test_saved_setting_wins_over_site_default(self):
        os.environ["BDH_HUB_UNITS"] = "imperial"
        set_store(lambda app_id, key: {("hub", "units"): "metric"}[(app_id, key)])
        self.assertEqual(units.system(), "metric")

    def test_conversions(self):
        f = units.Units("imperial")
        self.assertEqual((f.t(15.6), f.speed(10), f.length(1000)), (60, 6, 3281))
        self.assertEqual((f.temp_text(-40), f.speed_text(100), f.length_text(1000)),
                         ("-40°F", "62 mph", "3,281 ft"))
        c = units.Units("metric")
        self.assertEqual((c.temp_text(15.6), c.speed_text(10.4), c.length_text(1000)),
                         ("16°C", "10 km/h", "1,000 m"))
        self.assertIsNone(c.t(None))
        self.assertIsNone(f.temp_text(None))

    def test_units_override_is_view_only(self):
        os.environ["BDH_HUB_UNITS"] = "imperial"
        self.assertTrue(units.units().imperial)
        self.assertFalse(units.units("metric").imperial)
        self.assertTrue(units.units("nonsense").imperial)
        self.assertEqual(units.system(), "imperial")
