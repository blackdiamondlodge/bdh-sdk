import unittest
from unittest import mock

from bdh_sdk import alerts, ha, speakers

REGISTRY = [
    {"entity_id": "media_player.kitchen", "platform": "sonos"},
    {"entity_id": "media_player.kids_echo_2", "platform": "alexa_media"},
    {"entity_id": "media_player.kids_echo", "platform": "alexa_devices"},
    {"entity_id": "media_player.old", "platform": "sonos", "disabled_by": "user"},
    {"entity_id": "sensor.kitchen_battery", "platform": "sonos"},
]
STATES = [
    {"entity_id": "media_player.kitchen", "state": "playing", "attributes": {"friendly_name": "Kitchen"}},
    {"entity_id": "media_player.kids_echo_2", "state": "unavailable", "attributes": {"friendly_name": "Kids"}},
    {"entity_id": "media_player.kids_echo", "state": "idle", "attributes": {}},
]


@mock.patch("bdh_sdk.speakers.time.sleep")
@mock.patch("bdh_sdk.ha.ws_commands", return_value=[REGISTRY])
class SpeakerTests(unittest.TestCase):
    def setUp(self):
        speakers._uploaded.clear()

    @mock.patch("bdh_sdk.ha.get_all_states", return_value=STATES)
    def test_list_speakers_filters_platforms(self, _states, _ws, _sleep):
        self.assertEqual(speakers.list_speakers(), [
            ("media_player.kids_echo_2", "Kids (Alexa) - offline"),
            ("media_player.kitchen", "Kitchen (Sonos)"),
        ])

    def test_every_chime_is_bundled(self, _ws, _sleep):
        for chime in alerts.CHIMES:
            self.assertGreater(speakers.chime_seconds(chime), 0.3, chime)

    @mock.patch("bdh_sdk.ha.upload_media", return_value="media-source://media_source/local/bdh-chimes/notify.wav")
    @mock.patch("bdh_sdk.ha.call_service", return_value=(True, None))
    def test_announce_chime_then_tts(self, call, upload, _ws, sleep):
        failed = speakers.announce(
            "Dinner & dessert", ["media_player.kitchen", "media_player.kids_echo_2"],
            volume=40, chime="notify", voice="AvaNeural",
        )
        self.assertEqual(failed, [])
        notify, chime, tts = call.call_args_list
        self.assertEqual(notify.args[:3], ("notify", "alexa_media", None))
        self.assertEqual(notify.args[3]["target"], ["media_player.kids_echo_2"])
        self.assertEqual(notify.args[3]["data"], {"type": "announce"})
        self.assertEqual(chime.args[2], ["media_player.kitchen"])
        self.assertTrue(chime.args[3]["media_content_id"].endswith("notify.wav"))
        self.assertEqual(chime.args[3]["extra"], {"volume": 40})
        self.assertTrue(chime.args[3]["announce"])
        self.assertEqual(
            tts.args[3]["media_content_id"],
            "media-source://tts/tts.home_assistant_cloud?message=Dinner%20%26%20dessert&voice=AvaNeural",
        )
        sleep.assert_called_once()
        self.assertGreater(sleep.call_args.args[0], speakers.chime_seconds("notify"))
        # Uploaded once, reused next time.
        speakers.announce("again", ["media_player.kitchen"], chime="notify")
        upload.assert_called_once()

    @mock.patch("bdh_sdk.ha.upload_media", side_effect=ha.HAError("403"))
    @mock.patch("bdh_sdk.ha.call_service", return_value=(True, None))
    def test_chime_failure_still_speaks(self, call, _upload, _ws, sleep):
        self.assertEqual(speakers.announce("hi", ["media_player.kitchen"], chime="notify"), [])
        self.assertEqual(call.call_count, 1)
        sleep.assert_not_called()

    @mock.patch("bdh_sdk.ha.call_service", return_value=(True, None))
    def test_unknown_speaker_reported(self, call, _ws, _sleep):
        failed = speakers.announce("hi", ["media_player.kitchen", "media_player.gone"], chime=alerts.SILENT)
        self.assertEqual(failed, ["media_player.gone"])
        self.assertNotIn("extra", call.call_args.args[3])

    @mock.patch("bdh_sdk.ha.call_service", return_value=(False, "500"))
    def test_all_failed_raises(self, _call, _ws, _sleep):
        with self.assertRaises(speakers.AnnounceError):
            speakers.announce("hi", ["media_player.kitchen"])

    def test_validation(self, _ws, _sleep):
        with self.assertRaises(ValueError):
            speakers.announce(" ", ["media_player.kitchen"])
        with self.assertRaises(ValueError):
            speakers.announce("hi", ["media_player.kitchen"], chime="bogus")
        with self.assertRaises(ValueError):
            speakers.announce("hi", ["media_player.kitchen"], volume=101)
        with self.assertRaises(speakers.AnnounceError):
            speakers.announce("hi", [])


if __name__ == "__main__":
    unittest.main()
