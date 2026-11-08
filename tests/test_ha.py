import os
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from bdh_sdk import ha

ENV = {"HOMEASSISTANT_URL": "http://ha.test:8123", "HOMEASSISTANT_ACCESS_TOKEN": "tok"}


def _resp(status=200, body=None, text=""):
    r = mock.Mock(status_code=status, text=text, content=b"js")
    r.json.return_value = body
    return r


@mock.patch.dict(os.environ, ENV)
class HAClientTests(unittest.TestCase):
    @mock.patch("bdh_sdk.ha.requests.get")
    def test_get_entity_state_uses_env_connection(self, get):
        get.return_value = _resp(body={"entity_id": "light.a", "state": "on"})
        self.assertEqual(ha.get_entity_state("light.a")["state"], "on")
        url = get.call_args.args[0]
        self.assertEqual(url, "http://ha.test:8123/api/states/light.a")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer tok")

    @mock.patch("bdh_sdk.ha.requests.get", side_effect=requests.ConnectionError("down"))
    def test_unreachable_ha_degrades(self, get):
        self.assertIsNone(ha.get_entity_state("light.a"))
        self.assertEqual(ha.get_entity_states(["light.a"]), {})
        self.assertEqual(ha.get_history(["light.a"], datetime.now(timezone.utc)), {})
        with self.assertRaises(ha.HAError):
            ha.get_all_states()

    @mock.patch("bdh_sdk.ha.requests.get")
    def test_get_entity_states_filters(self, get):
        get.return_value = _resp(body=[{"entity_id": "a"}, {"entity_id": "b"}])
        self.assertEqual(list(ha.get_entity_states(["b"])), ["b"])

    @mock.patch("bdh_sdk.ha.requests.get")
    def test_history_minimal_response(self, get):
        get.return_value = _resp(body=[[
            {"entity_id": "sensor.t", "state": "1", "last_changed": "t1"},
            {"state": "2", "last_updated": "t2"},
        ], []])
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(ha.get_history(["sensor.t"], start), {"sensor.t": [("t1", "1"), ("t2", "2")]})

    @mock.patch("bdh_sdk.ha.requests.post")
    def test_call_service(self, post):
        post.return_value = _resp()
        self.assertEqual(ha.call_service("light", "turn_on", "light.a", {"brightness": 5}), (True, None))
        self.assertEqual(post.call_args.kwargs["json"], {"entity_id": "light.a", "brightness": 5})
        post.return_value = _resp(status=401, text="nope")
        ok, err = ha.call_service("light", "turn_on", "light.a")
        self.assertFalse(ok)
        self.assertIn("401", err)


if __name__ == "__main__":
    unittest.main()
