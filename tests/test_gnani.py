import asyncio
import base64
import json
import io
import wave
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.gnani import GnaniConfig, GnaniVoiceEngine, browser_wav
from app.main import create_app
from app.seed import seed
from app.store import Store
from app.voice import VoiceConfig, VoiceConfigurationError, VoiceProviderError


def engine(client=None, key="test-only", tags=False):
    return GnaniVoiceEngine(
        VoiceConfig("test-bifrost", "https://gateway.example/v1", "test-model"),
        client, GnaniConfig(api_key=key, audio_tags=tags),
    )


class FakeStreamingVoice:
    ready = True
    providers = {"stt": "Gnani Prisma", "llm": "Bifrost", "tts": "Gnani Timbre"}
    fail_audio = False
    fail_model = False

    def require_ready(self):
        pass

    async def reply(self, call):
        if self.fail_model:
            raise VoiceProviderError("model unavailable")
        return "I can record your appointment preference for the team to review."

    async def speech_chunks(self, text, language, delivery, voice=None):
        if self.fail_audio:
            raise VoiceProviderError("tts unavailable")
        yield b"\x01\x00" * 240


class FakePrewarmedVoice(FakeStreamingVoice):
    def __init__(self):
        self.preparing = False
        self.connection = object()
        self.closed_connection = None

    async def prepare_speech(self):
        self.preparing = True
        await asyncio.sleep(0)
        return self.connection

    async def reply(self, call):
        if not self.preparing:
            raise AssertionError("TTS was not prepared while the model was running")
        await asyncio.sleep(0)
        return await super().reply(call)

    async def speech_chunks(self, text, language, delivery, connection=None, voice=None):
        if connection is not self.connection:
            raise AssertionError("Prepared TTS connection was not reused")
        yield b"\x01\x00" * 240

    async def close_speech(self, connection):
        self.closed_connection = connection


class GnaniTests(unittest.TestCase):
    def test_requires_dedicated_key_without_fallback(self):
        with self.assertRaises(VoiceConfigurationError):
            engine(key="").require_ready()
        self.assertTrue(engine().ready)

    def test_stt_headers_and_normalized_events(self):
        e = engine()
        headers = e.streaming_headers("Hinglish")
        self.assertEqual(headers["lang_code"], "hi-IN")
        self.assertEqual(headers["x-format"], "codemix")
        self.assertEqual(headers["x-sample-rate"], "16000")
        self.assertEqual(headers["x-model"], "prisma-v3.0")
        self.assertEqual(headers["x-min-silence-ms"], "500")
        self.assertEqual(e.stream_event('{"type":"connected"}'), {"type": "ready"})
        event = e.stream_event(json.dumps({"type": "transcript", "text": "कल की booking", "segment_id": "s-1", "latency": 310}))
        self.assertEqual(event["transcript"], "कल की booking")
        self.assertTrue(event["end_of_turn"])
        self.assertEqual(event["turn_order"], "s-1")
        with self.assertRaises(VoiceProviderError):
            e.stream_event('{"type":"error","message":"sensitive-upstream-message"}')

    def test_speech_expression_is_rendered_separately_and_optional(self):
        text = "नमस्ते। आपकी कैसे मदद करूँ?"
        payload = engine(tags=True).synthesis_payload(text, "Hinglish", delivery="warm")
        self.assertIn("<pauses>", payload["text"])
        self.assertNotIn("<excited>", payload["text"])
        self.assertEqual(payload["language"], "hi-en")
        self.assertEqual(payload["audio_config"]["sample_rate"], 24000)
        self.assertEqual(engine().synthesis_payload("<yawns> Hello.")["text"], "Hello.")
        self.assertEqual(text, "नमस्ते। आपकी कैसे मदद करूँ?")

    def test_rest_tts_auth_and_actual_audio_format(self):
        seen = []
        sample = io.BytesIO()
        with wave.open(sample, 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x01\x00' * 240)
        def handler(request):
            seen.append(request)
            return httpx.Response(200, content=sample.getvalue(), headers={"content-type": "audio/wav"})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        audio = asyncio.run(engine(client).speak("Hello", "English"))
        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertEqual(seen[0].headers["X-API-Key-ID"], "test-only")
        self.assertEqual(json.loads(seen[0].content)["language"], "en-IN")
        asyncio.run(client.aclose())

    def test_streaming_wav_header_is_finalized_without_altering_audio(self):
        sample = io.BytesIO()
        pcm = b'\x01\x00' * 2400
        with wave.open(sample, 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm)
        streaming = bytearray(sample.getvalue())
        streaming[4:8] = streaming[40:44] = b'\xff' * 4
        with wave.open(io.BytesIO(browser_wav(bytes(streaming))), 'rb') as wav:
            self.assertEqual(wav.getnframes(), 2400)
            self.assertEqual(wav.readframes(2400), pcm)

    def test_provider_error_does_not_leak_response_or_key(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403, text="secret-upstream-body")))
        with self.assertRaises(VoiceProviderError) as caught:
            asyncio.run(engine(client).speak("hello"))
        self.assertNotIn("secret-upstream-body", str(caught.exception))
        asyncio.run(client.aclose())

    def test_seed_upgrade_preserves_customization_and_adds_four_flows(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp + "/db.sqlite")
            seed(store)
            with store.transaction() as db:
                agent = Store.get(db, "agents", "demo-cx")
                agent["name"] = "My customized agent"
                Store.put(db, "agents", agent)
                Store.put(db, "meta", {"id": "seed", "version": 3})
            seed(store)
            with store.transaction() as db:
                self.assertEqual(Store.get(db, "agents", "demo-cx")["name"], "My customized agent")
                self.assertEqual(len([a for a in Store.all(db, "agents") if a["id"].startswith("demo-")]), 4)
                self.assertEqual(Store.all(db, "calls"), [])

    def test_streaming_transcript_audio_timing_and_followup(self):
        self._stream_flow()

    def test_backchannel_audio_is_available_before_a_slow_reply(self):
        voice = FakeStreamingVoice()
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
            with TestClient(create_app(temp + "/db.sqlite", voice_engine=voice)) as client:
                call = client.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"}).json()
                response = client.post(f"/api/calls/{call['id']}/voice/backchannel")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sample_rate"], 24000)
        self.assertEqual(len(base64.b64decode(response.json()["audio"])), 480)

    def test_tts_connection_is_prepared_in_parallel_with_model_reply(self):
        voice = FakePrewarmedVoice()
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
            with TestClient(create_app(temp + "/db.sqlite", voice_engine=voice)) as client:
                call = client.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"}).json()
                response = client.post(
                    f"/api/calls/{call['id']}/voice/respond/stream",
                    json={"text": "Tomorrow morning please"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.text.splitlines()[-1])["type"], "complete")
        self.assertIs(voice.closed_connection, voice.connection)

    def test_prepared_tts_connection_closes_when_model_reply_fails(self):
        voice = FakePrewarmedVoice()
        voice.fail_model = True
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
            with TestClient(create_app(temp + "/db.sqlite", voice_engine=voice)) as client:
                call = client.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"}).json()
                response = client.post(
                    f"/api/calls/{call['id']}/voice/respond/stream",
                    json={"text": "Tomorrow morning please"},
                )

        self.assertEqual(json.loads(response.text.splitlines()[-1])["type"], "error")
        self.assertIs(voice.closed_connection, voice.connection)

    def test_browser_opt_out_marks_contact_do_not_call(self):
        for phrase in ("Please remove me from your list", "मुझे कॉल मत करो"):
            with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
                with TestClient(create_app(temp + "/db.sqlite", voice_engine=FakeStreamingVoice())) as c:
                    call = c.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"}).json()
                    path = f"/api/calls/{call['id']}"
                    c.post(path + "/voice/respond/stream", json={"text": phrase})
                    self.assertEqual(c.post(path + "/end").json()["outcome"], "opted_out", phrase)
                    contact = next(x for x in c.get("/api/state").json()["contacts"] if x["id"] == "contact-1")
                    self.assertTrue(contact["do_not_call"], phrase)

    def test_tts_failure_keeps_generated_transcript_and_releases_session(self):
        self._stream_flow(fail_audio=True)

    def test_model_failure_keeps_customer_input(self):
        self._stream_flow(fail_model=True)

    def _stream_flow(self, fail_audio=False, fail_model=False):
        voice = FakeStreamingVoice()
        voice.fail_audio, voice.fail_model = fail_audio, fail_model
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
            with TestClient(create_app(temp + "/db.sqlite", voice_engine=voice)) as c:
                call = c.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"}).json()
                path = f"/api/calls/{call['id']}"
                response = c.post(path + "/voice/respond/stream", json={
                    "text": "Tomorrow morning please", "asr_ms": 412, "stt_provider_ms": 267,
                })
                self.assertEqual(response.status_code, 200)
                events = [json.loads(x) for x in response.text.splitlines()]
                saved = c.get(path).json()
                self.assertEqual(saved["transcript"][1]["role"], "customer")
                self.assertEqual(events[-1]["type"], "error" if fail_audio or fail_model else "complete")
                if not fail_model:
                    self.assertEqual(saved["transcript"][-1]["role"], "agent")
                if not (fail_audio or fail_model):
                    self.assertEqual(len(base64.b64decode(events[1]["audio"])), 480)
                    self.assertIsNotNone(saved["voice_timing"]["first_audio_ms"])
                    self.assertEqual(saved["voice_timing"]["asr_ms"], 412)
                    self.assertEqual(saved["voice_timing"]["stt_provider_ms"], 267)
                    self.assertIsNotNone(saved["voice_timing"]["tts_first_audio_ms"])
                ended = c.post(path + "/end").json()
                self.assertEqual(ended["outcome"], "follow_up")
                self.assertIn("No external action", ended["summary"])
                self.assertEqual(c.post(path + "/voice/respond/stream", json={"text": "again"}).status_code, 409)

    def test_idle_speech_stream_closes_with_resume_code(self):
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
                await asyncio.Event().wait()

        class StreamingVoice(FakeStreamingVoice):
            streaming_stt_url = "wss://stt.example/stream"

            def streaming_headers(self, language):
                return {}

            def stream_event(self, message):
                return None

        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}), \
                patch("app.main.websocket_connect", lambda *a, **k: SilentUpstream()), \
                patch("app.main.STREAM_IDLE_SECONDS", 0.05):
            with TestClient(create_app(temp + "/db.sqlite", voice_engine=StreamingVoice(), vad_factory=lambda: None)) as c:
                call = c.post("/api/calls", json={"agent_id": "demo-booking", "contact_id": "contact-1", "mode": "browser"}).json()
                with c.websocket_connect(f"/api/calls/{call['id']}/voice/stream") as ws:
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        ws.receive_json()
        self.assertEqual(closed.exception.code, 4408)


class AgentVoiceTests(unittest.TestCase):
    def test_payload_uses_agent_voice_and_falls_back_to_server_voice(self):
        self.assertEqual(engine().synthesis_payload("Hello", voice="Yashraj")["voice"], "Yashraj")
        self.assertEqual(engine().synthesis_payload("Hello")["voice"], "Shivani")

    def test_seeded_agents_get_distinct_voices_and_upgrade_keeps_user_choice(self):
        from app.gnani import VOICES
        from app.store import workspace
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp + "/db.sqlite")
            seed(store)
            with store.transaction() as db:
                voices = [a["voice"] for a in Store.all(db, "agents")]
                agent = Store.get(db, "agents", "demo-cx")
                del agent["voice"]
                Store.put(db, "agents", agent)
                chosen = Store.get(db, "agents", "demo-sales")
                chosen["voice"] = "Lakshmi"
                Store.put(db, "agents", chosen)
                Store.put(db, "meta", {"id": "seed", "version": 4})
                Store.put(db, "agents", dict(agent, voice=None), ws="trial-user")  # a pre-voice trial workspace
            self.assertEqual(len(set(voices)), len(voices))
            self.assertTrue(set(voices) <= set(VOICES))
            with patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
                create_app(temp + "/db.sqlite", voice_engine=FakeStreamingVoice())
            with store.transaction() as db:
                self.assertEqual(Store.get(db, "agents", "demo-cx")["voice"], "Yashraj")
                self.assertEqual(Store.get(db, "agents", "demo-sales")["voice"], "Lakshmi")
                self.assertEqual(Store.get(db, "agents", "demo-cx", ws="trial-user")["voice"], "Yashraj")
            self.assertEqual(workspace.get(), "main")

    def test_agent_voice_is_validated_and_reaches_speech(self):
        spoken = []

        class Voice(FakeStreamingVoice):
            async def speak(self, text, language="English", delivery="warm", voice=None):
                spoken.append(voice)
                return b"RIFF"

        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
            with TestClient(create_app(temp + "/db.sqlite", voice_engine=Voice())) as c:
                agent = c.get("/api/state").json()["agents"]
                cx = next(a for a in agent if a["id"] == "demo-cx")
                self.assertEqual(c.put("/api/agents/demo-cx", json=dict(cx, voice="Nobody")).status_code, 422)
                self.assertEqual(c.put("/api/agents/demo-cx", json=dict(cx, voice="Avinash")).status_code, 200)
                call = c.post("/api/calls", json={"agent_id": "demo-cx", "contact_id": "contact-1", "mode": "browser"}).json()
                self.assertEqual(c.post(f"/api/calls/{call['id']}/voice/opening").status_code, 200)
        self.assertEqual(spoken, ["Avinash"])
