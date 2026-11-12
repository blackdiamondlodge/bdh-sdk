import unittest
from datetime import datetime, timezone

from bdh_sdk import STATS, Background, PluginSpec, SeasonHint, Stat


class ProvidesTests(unittest.TestCase):
    def test_stat_needs_exactly_one_of_value_or_time(self):
        Stat("temp", "Temperature", value="3°C")
        Stat("sunrise", "Sunrise", time=datetime(2026, 1, 1, 8, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            Stat("temp", "Temperature")
        with self.assertRaises(ValueError):
            Stat("temp", "Temperature", value="3°C",
                 time=datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_stat_time_must_be_aware(self):
        with self.assertRaises(ValueError):
            Stat("sunrise", "Sunrise", time=datetime(2026, 1, 1, 8))

    def test_background_refresh_and_season(self):
        with self.assertRaises(ValueError):
            Background("cam", "Cam", "/cam.jpg", refresh_seconds=0)
        SeasonHint("winter", "Lifts are open")
        with self.assertRaises(ValueError):
            SeasonHint("summer", "Warm")

    def test_spec_provides_and_stat_keys(self):
        spec = PluginSpec(id="weather", app="weather",
                          provides={STATS: "weather.provide.stats"},
                          stat_keys=(("temp", "Temperature"),))
        self.assertEqual(spec.provides, {"stats": "weather.provide.stats"})
        hash(spec)  # still usable as a dict key / in sets
        self.assertEqual(PluginSpec(id="x", app="x").provides, {})
        with self.assertRaises(ValueError):
            PluginSpec(id="x", app="x", stat_keys=(("a", "A"), ("a", "B")))
        with self.assertRaises(ValueError):
            PluginSpec(id="x", app="x", stat_keys=(("a", ""),))


if __name__ == "__main__":
    unittest.main()
