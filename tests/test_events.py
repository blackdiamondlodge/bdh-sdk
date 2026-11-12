import asyncio
import threading
import unittest

from bdh_sdk import events


class MatchTests(unittest.TestCase):
    def test_wildcards(self):
        cases = [
            ("ha/state/binary_sensor.front_door", "ha/state/binary_sensor.front_door", True),
            ("ha/state/+", "ha/state/binary_sensor.front_door", True),
            ("ha/#", "ha/state/binary_sensor.front_door", True),
            ("#", "cameras/doorbell/front", True),
            ("ha/state/+", "ha/state", False),
            ("ha/state/+", "ha/state/a/b", False),
            ("ha/state/light.x", "ha/state/binary_sensor.front_door", False),
            ("sunpeaks/#", "ha/state/light.x", False),
        ]
        for pattern, topic, expected in cases:
            with self.subTest(pattern=pattern, topic=topic):
                self.assertEqual(events.matches(pattern, topic), expected)

    def test_rejects_bad_topics(self):
        for pattern in ("", "ha//x", "ha/#/x", "ha/st+", "ha/#x"):
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                events.subscribe(pattern, print)
        for topic in ("ha/+", "ha/#", "", "/ha"):
            with self.subTest(topic=topic), self.assertRaises(ValueError):
                events.publish(topic)


class BusTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(events.reset)

    def test_sync_and_async_handlers_get_matching_events(self):
        got = []

        async def slow(event):
            await asyncio.sleep(0.05)
            got.append(("async", event.topic, event.data))

        events.subscribe("ha/state/+", lambda e: got.append(("sync", e.topic, e.data)))
        events.subscribe("ha/#", slow)
        events.publish("ha/state/binary_sensor.front_door", {"new": "on"})
        events.publish("cameras/doorbell/front")
        self.assertTrue(events.flush())
        self.assertEqual(sorted(got), [
            ("async", "ha/state/binary_sensor.front_door", {"new": "on"}),
            ("sync", "ha/state/binary_sensor.front_door", {"new": "on"}),
        ])

    def test_failing_handler_does_not_stop_the_others(self):
        got = []

        def boom(event):
            raise RuntimeError("boom")

        events.subscribe("x/#", boom)
        events.subscribe("x/#", lambda e: got.append(e.source))
        with self.assertLogs("bdh_sdk.events", "ERROR"):
            events.publish("x/y")
            events.flush()
        self.assertEqual(got, ["x"])

    def test_cancel_and_listeners(self):
        seen = []
        remove = events.add_listener(seen.append)
        sub = events.subscribe("ha/state/light.x", print)
        events.subscribe("ha/state/+", print)
        sub.cancel()
        remove()
        events.subscribe("other/x", print)
        self.assertEqual(seen, [[], ["ha/state/light.x"],
                                ["ha/state/+", "ha/state/light.x"], ["ha/state/+"]])
        self.assertEqual(events.patterns(), ["ha/state/+", "other/x"])

    def test_publish_from_any_thread_and_async_code(self):
        got = []
        events.subscribe("t/+", lambda e: got.append(e.topic))
        thread = threading.Thread(target=events.publish, args=("t/thread",))
        thread.start()
        thread.join()
        asyncio.run(events.apublish("t/async"))
        events.flush()
        self.assertEqual(sorted(got), ["t/async", "t/thread"])


if __name__ == "__main__":
    unittest.main()
