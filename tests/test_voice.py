import base64
import json
import os
import tempfile
import unittest

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.voice import VoiceConfig, VoiceConfigurationError, VoiceEngine
from unittest.mock import patch


class FakeVoiceEngine:
    ready = True
    providers = {
        "stt": "AssemblyAI",
        "llm": "Bifrost",
        "tts": "ElevenLabs",
    }

    def require_ready(self):
        return None

    async def transcribe(self, audio, content_type):
        if content_type != "audio/webm":
            raise ValueError("Unsupported browser audio format")
        return "We run an automobile dealership and receive fifty leads a week."

    async def reply(self, call):
        assert call["mode"] == "browser"
        return "Thanks. What usually happens when your sales team gets busy?"

    async def speak(self, text):
        return b"ID3fake-mp3"


class MissingVoiceEngine:
    ready = False
    providers = {"stt": "Missing", "llm": "Missing", "tts": "Missing"}

    def require_ready(self):
        raise VoiceConfigurationError(
            "Browser voice needs AssemblyAI, Bifrost and ElevenLabs configuration."
        )


class VoiceTests(unittest.TestCase):
    def test_streaming_url_uses_low_latency_pcm_configuration(self):
        config = VoiceConfig(
            assemblyai_key="stt-secret", bifrost_key="bifrost-secret",
            bifrost_url="https://gateway.example/v1", bifrost_model="gemini/test",
            elevenlabs_key="voice-secret", elevenlabs_voice="voice-id",
            elevenlabs_model="eleven_flash_v2_5",
        )
        engine = VoiceEngine(config=config)
        self.assertEqual(
            engine.streaming_stt_url,
            "wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&speech_model=u3-rt-pro&format_turns=true",
        )
        self.assertIn("language_code=hi", engine.streaming_stt_url_for("Hindi"))
        self.assertIn("language_code=hi", engine.streaming_stt_url_for("Hinglish"))
        self.assertNotIn("language_code", engine.streaming_stt_url_for("English"))

    def test_blank_optional_values_use_safe_provider_defaults(self):
        with patch.dict(
            os.environ,
            {
                "BIFROST_URL": "",
                "BIFROST_MODELS": "",
                "ELEVENLABS_MODEL": "",
                "ELEVENLABS_VOICE_ID": "",
            },
            clear=False,
        ):
            config = VoiceConfig.from_env()
        self.assertEqual(config.bifrost_url, "https://bifrost.parkplus.io/v1")
        self.assertEqual(config.elevenlabs_model, "eleven_flash_v2_5")

    def test_provider_requests_use_bifrost_and_elevenlabs_server_side(self):
        seen = []

        def handler(request):
            seen.append(request)
            if request.url.host == "gateway.example":
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "A short AI reply."}}]},
                )
            if request.url.host == "api.elevenlabs.io":
                return httpx.Response(200, content=b"ID3audio")
            return httpx.Response(404)

        config = VoiceConfig(
            assemblyai_key="stt-secret",
            bifrost_key="bifrost-secret",
            bifrost_url="https://gateway.example/v1",
            bifrost_model="gemini/test-model",
            elevenlabs_key="voice-secret",
            elevenlabs_voice="voice-id",
            elevenlabs_model="eleven_flash_v2_5",
        )
        engine = VoiceEngine(
            config=config,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        call = {
            "agent_snapshot": {"name": "Aria", "prompt": "Be concise.", "context": "Approved facts."},
            "transcript": [{"role": "customer", "text": "Tell me more."}],
        }
        import asyncio

        reply = asyncio.run(engine.reply(call))
        audio = asyncio.run(engine.speak(reply))
        asyncio.run(engine._client.aclose())
        self.assertEqual(reply, "A short AI reply.")
        self.assertEqual(audio, b"ID3audio")
        bifrost = seen[0]
        self.assertEqual(bifrost.headers["x-bf-vk"], "bifrost-secret")
        self.assertEqual(json.loads(bifrost.content)["model"], "gemini/test-model")
        eleven = seen[1]
        self.assertEqual(eleven.headers["xi-api-key"], "voice-secret")
        self.assertIn("voice-id", str(eleven.url))

    def test_browser_voice_turn_persists_transcript_and_returns_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(
                create_app(temp + "/test.sqlite", voice_engine=FakeVoiceEngine())
            ) as client:
                call = client.post(
                    "/api/calls",
                    json={
                        "agent_id": "agent-sales",
                        "contact_id": "contact-1",
                        "mode": "browser",
                    },
                ).json()
                self.assertEqual(call["mode"], "browser")

                opening = client.post(f"/api/calls/{call['id']}/voice/opening")
                self.assertEqual(opening.status_code, 200, opening.text)
                self.assertEqual(base64.b64decode(opening.json()["audio"]), b"ID3fake-mp3")

                response = client.post(
                    f"/api/calls/{call['id']}/voice/turn",
                    content=b"browser-audio",
                    headers={"content-type": "audio/webm"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body["transcript"], "We run an automobile dealership and receive fifty leads a week.")
                self.assertEqual(body["reply"], "Thanks. What usually happens when your sales team gets busy?")
                self.assertEqual(base64.b64decode(body["audio"]), b"ID3fake-mp3")
                saved = client.get(f"/api/calls/{call['id']}").json()
                self.assertEqual([t["role"] for t in saved["transcript"]], ["agent", "customer", "agent"])

    def test_streaming_transcript_skips_slow_batch_transcription(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(temp + "/test.sqlite", voice_engine=FakeVoiceEngine())) as client:
                call = client.post("/api/calls", json={"agent_id": "agent-sales", "contact_id": "contact-1", "mode": "browser"}).json()
                response = client.post(f"/api/calls/{call['id']}/voice/respond", json={"text": "We run a clinic."})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["transcript"], "We run a clinic.")
                self.assertEqual([t["role"] for t in response.json()["call"]["transcript"]], ["agent", "customer", "agent"])

    def test_browser_mode_fails_closed_without_provider_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(
                create_app(temp + "/test.sqlite", voice_engine=MissingVoiceEngine())
            ) as client:
                response = client.post(
                    "/api/calls",
                    json={
                        "agent_id": "agent-sales",
                        "contact_id": "contact-1",
                        "mode": "browser",
                    },
                )
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("API_KEY", response.text)

    def test_phone_mode_remains_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(
                create_app(temp + "/test.sqlite", voice_engine=FakeVoiceEngine())
            ) as client:
                response = client.post(
                    "/api/calls",
                    json={
                        "agent_id": "agent-sales",
                        "contact_id": "contact-1",
                        "mode": "live",
                    },
                )
                self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
