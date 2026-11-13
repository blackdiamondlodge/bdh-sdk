import asyncio
import unittest

from bdh_sdk.alerts import CHIMES, SILENT, Alert, apush, push, set_sender


def make(**kw):
    return Alert(**{"app": "cameras", "key": "doorbell:front", "title": "Someone's at the door",
                    "embed_url": "/cameras/popup/front/", **kw})


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        set_sender(self.sent.append)
        self.addCleanup(set_sender, None)

    def test_push_and_apush_reach_the_sender(self):
        alert = make()
        push(alert)
        asyncio.run(apush(alert))
        self.assertEqual(self.sent, [alert, alert])
        self.assertEqual(alert.as_dict()["ttl"], 60)

    def test_without_a_sender_push_is_a_no_op(self):
        set_sender(None)
        push(make())
        self.assertEqual(self.sent, [])

    def test_rejects_bad_alerts(self):
        for kw in ({"app": "Cameras"}, {"key": ""}, {"title": ""}, {"ttl": 0}, {"ttl": 601},
                   {"ttl": True}, {"embed_url": "https://evil.example/"}, {"embed_url": "//evil.example/"},
                   {"embed_url": "/\\evil.example"}, {"embed_url": "cameras/popup/"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                make(**kw)
        with self.assertRaises(TypeError):
            push({"app": "cameras"})

    def test_sound_is_a_chime_silent_or_a_hub_path(self):
        for snd in (None, SILENT, *CHIMES, "/static/cameras/ring.mp3"):
            with self.subTest(sound=snd):
                self.assertEqual(make(sound=snd).as_dict()["sound"], snd)
        for snd in ("", "foghorn", "https://evil.example/a.mp3", "//evil.example/a.mp3", "/\\evil", 3):
            with self.subTest(sound=snd), self.assertRaises(ValueError):
                make(sound=snd)


if __name__ == "__main__":
    unittest.main()