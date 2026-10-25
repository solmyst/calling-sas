import os, tempfile, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app


class BoundaryTests(unittest.TestCase):
    def test_hosted_configuration_fails_closed(self):
        with patch.dict(
            os.environ,
            {"APP_ENV": "production", "DEMO_PASSWORD": "", "SESSION_SECRET": ""},
        ):
            with self.assertRaises(RuntimeError):
                create_app()

    def test_authentication_cookie_and_logout(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.dict(
                os.environ,
                {
                    "APP_ENV": "local",
                    "DEMO_PASSWORD": "fictional-test-password-only",
                    "SESSION_SECRET": "test-secret-value-with-at-least-32-characters",
                },
            ),
        ):
            with TestClient(create_app(temp + "/db.sqlite")) as c:
                self.assertEqual(c.get("/api/state").status_code, 401)
                self.assertEqual(
                    c.post("/api/login", json={"password": "wrong"}).status_code, 401
                )
                response = c.post(
                    "/api/login", json={"password": "fictional-test-password-only"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("HttpOnly", response.headers["set-cookie"])
                self.assertEqual(c.get("/api/state").status_code, 200)
                c.post("/api/logout")
                self.assertEqual(c.get("/api/state").status_code, 401)

    def test_restart_preserves_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            path = temp + "/db.sqlite"
            with TestClient(create_app(path)) as c:
                a = c.get("/api/state").json()["agents"][0]
                a["name"] = "Persistent Agent"
                c.put("/api/agents/" + a["id"], json=a)
            with TestClient(create_app(path)) as c:
                state = c.get("/api/state").json()
                self.assertIn("Persistent Agent", [a["name"] for a in state["agents"]])
                self.assertEqual(state["metrics"]["seeded"], 18)

    def test_negative_confirmation_is_not_success(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            TestClient(create_app(temp + "/db.sqlite")) as c,
        ):
            call = c.post(
                "/api/calls",
                json={"agent_id": "agent-sales", "contact_id": "contact-1"},
            ).json()
            for text in ["Yes", "We need help", "No"]:
                response = c.post(
                    "/api/calls/" + call["id"] + "/turn", json={"text": text}
                )
            self.assertEqual(response.json()["outcome"], "not_interested")

    def test_repeated_turn_does_not_duplicate(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            TestClient(create_app(temp + "/db.sqlite")) as c,
        ):
            call = c.post(
                "/api/calls",
                json={"agent_id": "agent-sales", "contact_id": "contact-1"},
            ).json()
            payload = {"text": "Yes", "request_id": "turn-once"}
            a = c.post("/api/calls/" + call["id"] + "/turn", json=payload).json()
            b = c.post("/api/calls/" + call["id"] + "/turn", json=payload).json()
            self.assertEqual(a, b)
            self.assertEqual(len(b["transcript"]), 3)
