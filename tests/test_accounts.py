import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import accounts
from app.main import create_app
from app.store import MAIN, SYSTEM, Store

ENV = {"APP_ENV": "local", "DEMO_PASSWORD": "main-account-password", "ADMIN_EMAIL": "owner@relay.test"}


class ReadyVoice:
    ready = True
    providers = {"stt": "Gnani Prisma", "llm": "Bifrost", "tts": "Gnani Timbre"}
    streaming_stt_url = "wss://stt.example/stream"

    def require_ready(self):
        pass

    def streaming_headers(self, language):
        return {}

    def stream_event(self, message):
        return None


class SilentUpstream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, chunk):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        import asyncio
        await asyncio.Event().wait()


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/db.sqlite"
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.app = create_app(self.path, voice_engine=ReadyVoice(), vad_factory=lambda: None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def client(self):
        return TestClient(self.app)

    def signup(self, client, email):
        return client.post("/api/signup", json={"email": email, "password": "trial-password-1"})

    def browser_call(self, client):
        return client.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"})

    def set_used(self, email, seconds):
        store = Store(self.path)
        with store.transaction() as db:
            user = accounts.find(db, email)
            user["voice_seconds"] = seconds
            Store.put(db, "users", user, ws=SYSTEM)

    def test_trial_signup_gets_private_seeded_workspace(self):
        with self.client() as a, self.client() as b, self.client() as main:
            self.assertEqual(self.signup(a, "a@example.com").status_code, 200)
            self.assertEqual(self.signup(b, "b@example.com").status_code, 200)
            self.assertEqual(main.post("/api/login", json={"email": "owner@relay.test", "password": ENV["DEMO_PASSWORD"]}).status_code, 200)

            state = a.get("/api/state").json()
            self.assertEqual(state["account"]["role"], "trial")
            self.assertEqual(state["account"]["voice_seconds_left"], accounts.TRIAL_VOICE_SECONDS)
            self.assertTrue(any(x["id"] == "demo-booking" for x in state["agents"]))

            call = a.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": "contact-1"}).json()
            self.assertEqual(a.get(f"/api/calls/{call['id']}").status_code, 200)
            self.assertEqual(b.get(f"/api/calls/{call['id']}").status_code, 404)
            self.assertEqual(main.get(f"/api/calls/{call['id']}").status_code, 404)
            self.assertEqual(b.get("/api/state").json()["calls"], [])
            self.assertEqual(main.get("/api/state").json()["account"]["role"], "main")

    def test_login_rules(self):
        with self.client() as c:
            self.assertEqual(c.get("/api/state").status_code, 401)
            self.assertEqual(self.signup(c, "a@example.com").status_code, 200)
            self.assertEqual(self.signup(c, "A@example.com").status_code, 409)
            self.assertEqual(self.signup(c, "owner@relay.test").status_code, 409)
        with self.client() as c:
            self.assertEqual(c.post("/api/login", json={"email": "a@example.com", "password": "wrong-password"}).status_code, 401)
            self.assertEqual(c.post("/api/login", json={"email": "a@example.com", "password": "trial-password-1"}).status_code, 200)
        with self.client() as c:
            # Older clients send only the workspace password: that is the main account.
            self.assertEqual(c.post("/api/login", json={"password": ENV["DEMO_PASSWORD"]}).status_code, 200)
            self.assertEqual(c.get("/api/session").json()["account"]["role"], "main")

    def test_daily_signup_cap(self):
        with patch.object(accounts, "TRIAL_SIGNUPS_PER_DAY", 1), self.client() as c:
            self.assertEqual(self.signup(c, "a@example.com").status_code, 200)
            self.assertEqual(self.signup(c, "b@example.com").status_code, 429)

    def test_used_trial_blocks_voice_but_not_typed_simulation(self):
        with self.client() as c:
            self.signup(c, "a@example.com")
            self.assertEqual(self.browser_call(c).status_code, 200)
            self.set_used("a@example.com", accounts.TRIAL_VOICE_SECONDS)
            self.assertEqual(self.browser_call(c).status_code, 402)
            self.assertEqual(c.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": "contact-1"}).status_code, 200)

    def test_voice_stream_stops_at_trial_limit_and_meters_usage(self):
        with patch("app.main.websocket_connect", lambda *a, **k: SilentUpstream()), self.client() as c:
            self.signup(c, "a@example.com")
            call = self.browser_call(c).json()
            self.set_used("a@example.com", accounts.TRIAL_VOICE_SECONDS - 0.2)
            with c.websocket_connect(f"/api/calls/{call['id']}/voice/stream") as ws:
                with self.assertRaises(WebSocketDisconnect) as closed:
                    ws.receive_json()
            self.assertEqual(closed.exception.code, 4402)
            self.assertEqual(c.get("/api/session").json()["account"]["voice_seconds_left"], 0)
            with c.websocket_connect(f"/api/calls/{call['id']}/voice/stream") as ws:
                with self.assertRaises(WebSocketDisconnect) as closed:
                    ws.receive_json()
            self.assertEqual(closed.exception.code, 4402)

    def test_existing_single_workspace_data_moves_to_main_account(self):
        path = self.tmp.name + "/old.sqlite"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE records (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))")
        db.execute("INSERT INTO records VALUES ('calls','old-call','{\"id\": \"old-call\"}')")
        db.commit()
        db.close()
        store = Store(path)
        with store.transaction() as db:
            self.assertEqual(Store.get(db, "calls", "old-call", ws=MAIN), {"id": "old-call"})
            self.assertIsNone(Store.get(db, "calls", "old-call", ws="someone-else"))


if __name__ == "__main__":
    unittest.main()
