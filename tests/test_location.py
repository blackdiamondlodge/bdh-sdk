import os
import sys
import types
import unittest
from datetime import timezone
from unittest import mock
from zoneinfo import ZoneInfo

from bdh_sdk import location as loc
from bdh_sdk.settings import set_store

NO_DJANGO = {"django": None, "django.conf": None}
SAVED = {"name": "Sun Peaks", "region": "British Columbia", "country": "Canada",
         "latitude": 50.88, "longitude": -119.91, "timezone": "America/Vancouver", "tz_auto": True}


class LocationTests(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("BDH_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        modules = mock.patch.dict(sys.modules, NO_DJANGO)
        modules.start()
        self.addCleanup(modules.stop)
        self.addCleanup(set_store, None)

    def save(self, value):
        set_store(lambda app_id, key: {("hub", "location"): value}[(app_id, key)])

    def test_unset(self):
        self.assertIsNone(loc.location())
        self.assertIs(loc.tzinfo(), timezone.utc)

    def test_saved_location(self):
        self.save(SAVED)
        where = loc.location()
        self.assertEqual((where.latitude, where.longitude, where.timezone), (50.88, -119.91, "America/Vancouver"))
        self.assertEqual(where.label, "Sun Peaks, British Columbia, Canada")
        self.assertEqual(loc.tzinfo(), ZoneInfo("America/Vancouver"))

    def test_bad_coordinates_keep_the_time_zone(self):
        self.save({"latitude": 91, "longitude": "x", "timezone": "Europe/Paris"})
        where = loc.location()
        self.assertFalse(where.has_coordinates)
        self.assertEqual(loc.tzinfo(), ZoneInfo("Europe/Paris"))

    def test_unknown_time_zone_is_utc(self):
        self.save({"latitude": 1, "longitude": 2, "timezone": "Mars/Olympus"})
        self.assertTrue(loc.location().has_coordinates)
        self.assertIs(loc.tzinfo(), timezone.utc)

    def test_empty_value_is_unset(self):
        self.save({"name": "Nowhere"})
        self.assertIsNone(loc.location())


class LegacyLocationTests(unittest.TestCase):
    """Hubs older than the Location setting have settings.HUB_LOCATION instead."""

    def setUp(self):
        self.addCleanup(set_store, None)

    def django(self, hub_location):
        conf = types.ModuleType("django.conf")
        conf.settings = types.SimpleNamespace(configured=True, HUB_LOCATION=hub_location)
        django = types.ModuleType("django")
        django.conf = conf
        return mock.patch.dict(sys.modules, {"django": django, "django.conf": conf})

    def test_falls_back_to_hub_location_setting(self):
        with self.django({"latitude": 47.57, "longitude": -122.22, "timezone": "America/Los_Angeles"}):
            where = loc.location()
        self.assertEqual((where.latitude, where.timezone), (47.57, "America/Los_Angeles"))

    def test_saved_wins_over_legacy(self):
        set_store(lambda app_id, key: {("hub", "location"): SAVED}[(app_id, key)])
        with self.django({"timezone": "UTC"}):
            self.assertEqual(loc.location().timezone, "America/Vancouver")