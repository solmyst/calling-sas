import tempfile, unittest
from fastapi.testclient import TestClient
from app.main import create_app


class VoiceSafetyTests(unittest.TestCase):
    def test_recording_is_not_treated_as_a_customer(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            TestClient(create_app(temp + "/db.sqlite")) as c,
        ):
            call = c.post(
                "/api/calls",
                json={"agent_id": "agent-sales", "contact_id": "contact-1"},
            ).json()
            r = c.post(
                "/api/calls/" + call["id"] + "/turn",
                json={
                    "text": "The person you are calling is unavailable. Leave a message after the beep."
                },
            )
            self.assertEqual(r.json()["outcome"], "no_answer")

    def test_person_saying_busy_still_gets_callback(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            TestClient(create_app(temp + "/db.sqlite")) as c,
        ):
            call = c.post(
                "/api/calls",
                json={"agent_id": "agent-sales", "contact_id": "contact-1"},
            ).json()
            r = c.post(
                "/api/calls/" + call["id"] + "/turn",
                json={"text": "I am busy, please call me later"},
            )
            self.assertEqual(r.json()["outcome"], "follow_up")
