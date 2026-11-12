"""Simulated VoiceLink calls: the bridge is exercised with VoiceLink's documented events and audio format."""

import asyncio
import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from app.telephony import PhoneFormat, alaw_decode, alaw_encode

ENV = {
    "APP_ENV": "local", "DEMO_PASSWORD": "main-account-password", "ADMIN_EMAIL": "owner@relay.test",
    "VOICELINK_API_TOKEN": "vl-test-token", "VOICELINK_DID": "07912345678",
    "VOICELINK_WEBSOCKET_URL": "wss://relay.test/api/telephony/voicelink",
}
SAID = "I would like a demo next week"


class STT:
    """Fake Gnani STT socket: returns one final transcript once it has heard some audio."""

    def __init__(self):
        self.frames = []
        self.heard = asyncio.Event()
        self.done = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, frame):
        self.frames.append(frame)
        if len(self.frames) >= 3:
            self.heard.set()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self.heard.wait()
        if self.done:
            await asyncio.Event().wait()
        self.done = True
        return json.dumps({"type": "transcript", "text": SAID})


class PhoneVoice:
    ready = True
    providers = {"stt": "Gnani Prisma", "llm": "Bifrost", "tts": "Gnani Timbre"}
    streaming_stt_url = "wss://stt.example/stream"
    replies = []

    def require_ready(self):
        pass

    def streaming_headers(self, language):
        return {}

    def stream_event(self, message):
        event = json.loads(message)
        return {"type": "Turn", "transcript": event["text"], "end_of_turn": True}

    async def reply(self, call):
        self.replies.append(call["transcript"][-1]["text"])
        return "Happy to help. Which day suits you?"

    async def speech_chunks(self, text, language, delivery):
        yield (np.full(480, 1000, dtype="<i2")).tobytes()  # 20 ms at 24 kHz


class Answer:
    status_code = 200


class TelephonyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.stt = STT()
        self.app = create_app(self.tmp.name + "/db.sqlite", voice_engine=PhoneVoice(), vad_factory=lambda: None)
        self.posts = []

        def post(url, **kwargs):
            self.posts.append((url, kwargs))
            return Answer()

        self.patches = [patch("app.main.httpx.post", post), patch("app.main.PHONE_HOURS", (0, 24)),
                        patch("app.main.websocket_connect", lambda *a, **k: self.stt)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()
        self.tmp.cleanup()

    def main_client(self):
        c = TestClient(self.app)
        c.__enter__()
        c.post("/api/login", json={"email": "owner@relay.test", "password": ENV["DEMO_PASSWORD"]})
        return c

    def phone_contact(self, c, phone="+919876543210"):
        return c.post("/api/contacts", json={"name": "Test Caller", "phone": phone, "consent": True}).json()["id"]

    def test_alaw_roundtrip_and_frame_sizes(self):
        codes = bytes(range(256))
        self.assertEqual(alaw_encode(alaw_decode(codes)), codes)
        fmt = PhoneFormat({"encoding": "audio/alaw", "sample_rate": "8000"})
        self.assertEqual(len(fmt.to_gnani(base64.b64encode(bytes(160)).decode())), 640)  # 20 ms -> 16 kHz PCM16
        self.assertEqual(len(base64.b64decode(fmt.from_tts(bytes(960)))), 160)  # 20 ms of 24 kHz -> A-law

    def test_simulated_phone_call_end_to_end(self):
        c = self.main_client()
        self.assertEqual(c.get("/api/state").json()["settings"]["telephony"], "voicelink")
        call = c.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": self.phone_contact(c), "mode": "phone"})
        self.assertEqual(call.status_code, 200, call.text)
        call = call.json()
        url, sent = self.posts[0]
        self.assertTrue(url.endswith("/add_lead"))
        self.assertEqual(sent["headers"]["Authorization"], "Bearer vl-test-token")
        self.assertEqual((sent["json"]["customer_number"], sent["json"]["country_code"]), ("9876543210", "91"))
        params = sent["json"]["custom_parameters"]

        with c.websocket_connect("/api/telephony/voicelink") as ws:
            ws.send_json({"event": "connected"})
            ws.send_json({"event": "start", "sequence_number": 0, "stream_sid": "stream-1", "start": {
                "stream_sid": "stream-1", "call_sid": "vl-call", "custom_parameters": params,
                "media_format": {"encoding": "audio/alaw", "sample_rate": "8000"}}})
            opening = self.until_mark(ws)
            self.assertEqual(opening[-1]["mark"]["name"], "opening:" + call["id"])
            self.assertEqual(len(base64.b64decode(opening[0]["media"]["payload"])), 160)
            self.assertEqual(opening[0]["stream_sid"], "stream-1")
            ws.send_json({"event": "mark", "mark": opening[-1]["mark"]})  # VoiceLink echoes marks once played
            frame = base64.b64encode(alaw_encode(np.full(160, 2000))).decode()
            for _ in range(8):
                ws.send_json({"event": "media", "media": {"track": "inbound", "payload": frame}})
            reply = self.until_mark(ws)
            self.assertEqual(reply[0]["event"], "media")
            ws.send_json({"event": "stop", "stop": {"callSid": "vl-call"}})

        saved = c.get(f"/api/calls/{call['id']}").json()
        self.assertEqual([t["role"] for t in saved["transcript"]], ["agent", "customer", "agent"])
        self.assertEqual(saved["transcript"][1]["text"], SAID)
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(len(self.stt.frames[0]), 1024)
        c.__exit__(None, None, None)

    def until_mark(self, ws):
        events = []
        while not events or events[-1]["event"] != "mark":
            events.append(ws.receive_json())
        return events

    def test_forged_token_is_rejected(self):
        c = self.main_client()
        call = c.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": self.phone_contact(c), "mode": "phone"}).json()
        with c.websocket_connect("/api/telephony/voicelink") as ws:
            ws.send_json({"event": "start", "start": {"custom_parameters": {"call_id": call["id"], "token": "forged"}}})
            with self.assertRaises(WebSocketDisconnect) as closed:
                ws.receive_json()
        self.assertEqual(closed.exception.code, 1008)
        c.__exit__(None, None, None)

    def test_dial_rules(self):
        c = self.main_client()
        bad_number = c.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": "contact-1", "mode": "phone"})
        self.assertEqual(bad_number.status_code, 422)
        self.assertEqual(self.posts, [])
        with patch("app.main.PHONE_HOURS", (0, 0)):
            late = c.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": self.phone_contact(c), "mode": "phone"})
            self.assertEqual(late.status_code, 409)
        c.__exit__(None, None, None)
        with TestClient(self.app) as trial:
            trial.post("/api/signup", json={"email": "t@example.com", "password": "trial-password-1"})
            r = trial.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": "contact-1", "mode": "phone"})
            self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
