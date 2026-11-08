import json
import os
import tempfile
import unittest

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.voice import VoiceConfig, VoiceConfigurationError, VoiceEngine, VoiceProviderError
from unittest.mock import patch


class FakeVoiceEngine:
    ready = True
    providers = {"stt": "Gnani Prisma", "llm": "Bifrost", "tts": "Gnani Timbre"}

    def require_ready(self):
        return None

    async def reply(self, call):
        assert call["mode"] == "browser"
        return "Thanks. What usually happens when your sales team gets busy?"

    async def speak(self, text, language="English", delivery="warm"):
        return b"RIFFfake-wav"


class MissingVoiceEngine:
    ready = False
    providers = {"stt": "Missing", "llm": "Missing", "tts": "Missing"}

    def require_ready(self):
        raise VoiceConfigurationError(
            "Browser voice needs speech and conversation model configuration."
        )


class VoiceTests(unittest.TestCase):
    def test_default_http_client_is_reused_until_engine_shutdown(self):
        engine = VoiceEngine(
            config=VoiceConfig(bifrost_key="bifrost-secret",
                bifrost_url="https://gateway.example/v1", bifrost_model="gemini/test",
            )
        )

        first = engine._http()
        second = engine._http()

        self.assertIs(first, second)
        import asyncio
        asyncio.run(engine.aclose())
        self.assertTrue(first.is_closed)

    def test_blank_optional_values_use_safe_provider_defaults(self):
        with patch.dict(
            os.environ,
            {
                "BIFROST_URL": "",
                "BIFROST_MODELS": "",
                "BIFROST_REASONING_EFFORT": "",
            },
            clear=False,
        ):
            config = VoiceConfig.from_env()
        self.assertEqual(config.bifrost_url, "https://bifrost.parkplus.io/v1")
        self.assertEqual(config.reasoning_effort, "minimal")

    def test_provider_requests_use_bifrost_server_side(self):
        seen = []

        def handler(request):
            seen.append(request)
            if request.url.host == "gateway.example":
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "A short AI reply."}}]},
                )
            return httpx.Response(404)

        config = VoiceConfig(
            bifrost_key="bifrost-secret",
            bifrost_url="https://gateway.example/v1",
            bifrost_model="gemini/test-model",
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
        asyncio.run(engine._client.aclose())
        self.assertEqual(reply, "A short AI reply.")
        bifrost = seen[0]
        self.assertEqual(bifrost.headers["x-bf-vk"], "bifrost-secret")
        model_request = json.loads(bifrost.content)
        self.assertEqual(model_request["model"], "gemini/test-model")
        self.assertEqual(model_request["reasoning_effort"], "minimal")
        self.assertIn(
            "If the customer opts out, reply exactly",
            " ".join(model_request["messages"][0]["content"].split()),
        )
        self.assertIn("Never request card digits", model_request["messages"][0]["content"])
        self.assertIn("without claiming it was recorded", model_request["messages"][0]["content"])
        serialized_messages = json.dumps(model_request["messages"])
        self.assertEqual(serialized_messages.count("Tell me more."), 1)

    def test_groq_provider_uses_backend_bearer_auth_and_disables_reasoning(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "A short safe reply."}}]}
            )

        config = VoiceConfig(bifrost_key="", bifrost_url="https://gateway.example/v1",
            bifrost_model="", llm_provider="groq",
            groq_key="groq-secret", groq_model="qwen/qwen3.8-27b",
        )
        engine = VoiceEngine(
            config=config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        call = {
            "agent_snapshot": {"name": "Mira", "prompt": "Be concise.", "context": "Approved facts."},
            "transcript": [{"role": "customer", "text": "Help me."}],
        }

        import asyncio
        reply = asyncio.run(engine.reply(call))
        asyncio.run(engine._client.aclose())

        self.assertEqual(reply, "A short safe reply.")
        request = seen[0]
        self.assertEqual(request.url.host, "api.groq.com")
        self.assertEqual(request.headers["authorization"], "Bearer groq-secret")
        self.assertNotIn("x-bf-vk", request.headers)
        payload = json.loads(request.content)
        self.assertEqual(payload["model"], "qwen/qwen3.8-27b")
        self.assertEqual(payload["reasoning_effort"], "none")

    def test_groq_rate_limit_falls_back_to_gemini_and_opens_circuit(self):
        seen = []

        def handler(request):
            seen.append(request)
            if request.url.host == "api.groq.com":
                return httpx.Response(429, headers={"retry-after": "60"})
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "Gemini fallback reply."}}]}
            )

        config = VoiceConfig(bifrost_key="bifrost-secret",
            bifrost_url="https://gateway.example/v1", bifrost_model="gemini/test-model", llm_provider="groq",
            groq_key="groq-secret", groq_model="qwen/qwen3.8-27b",
        )
        engine = VoiceEngine(
            config=config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        call = {
            "agent_snapshot": {"name": "Mira", "prompt": "Be concise.", "context": "Approved facts."},
            "transcript": [{"role": "customer", "text": "Help me."}],
        }

        import asyncio
        first = asyncio.run(engine.reply(call))
        second = asyncio.run(engine.reply(call))
        asyncio.run(engine._client.aclose())

        self.assertEqual(first, "Gemini fallback reply.")
        self.assertEqual(second, "Gemini fallback reply.")
        self.assertEqual([request.url.host for request in seen], [
            "api.groq.com", "gateway.example", "gateway.example",
        ])
        groq_payload = json.loads(seen[0].content)
        fallback_payload = json.loads(seen[1].content)
        self.assertEqual(groq_payload["messages"], fallback_payload["messages"])
        self.assertEqual(fallback_payload["model"], "gemini/test-model")
        self.assertEqual(fallback_payload["reasoning_effort"], "minimal")
        self.assertEqual(seen[1].headers["x-bf-vk"], "bifrost-secret")

    def test_groq_auth_error_does_not_hide_bad_configuration_with_fallback(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(401)

        config = VoiceConfig(bifrost_key="bifrost-secret",
            bifrost_url="https://gateway.example/v1", bifrost_model="gemini/test-model", llm_provider="groq",
            groq_key="invalid", groq_model="qwen/qwen3.8-27b",
        )
        engine = VoiceEngine(
            config=config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        call = {
            "agent_snapshot": {"name": "Mira", "prompt": "Be concise.", "context": "Approved facts."},
            "transcript": [{"role": "customer", "text": "Help me."}],
        }

        import asyncio
        with self.assertRaises(VoiceProviderError):
            asyncio.run(engine.reply(call))
        asyncio.run(engine._client.aclose())

        self.assertEqual([request.url.host for request in seen], ["api.groq.com"])

    def test_groq_exhausted_success_routes_next_turn_directly_to_gemini(self):
        seen = []

        def handler(request):
            seen.append(request)
            if request.url.host == "api.groq.com":
                return httpx.Response(
                    200,
                    headers={"x-ratelimit-remaining-tokens": "0"},
                    json={"choices": [{"message": {"content": "Last Groq reply."}}]},
                )
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "Gemini reply."}}]}
            )

        config = VoiceConfig(bifrost_key="bifrost-secret",
            bifrost_url="https://gateway.example/v1", bifrost_model="gemini/test-model", llm_provider="groq",
            groq_key="groq-secret", groq_model="qwen/qwen3.8-27b",
        )
        engine = VoiceEngine(
            config=config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        call = {
            "agent_snapshot": {"name": "Mira", "prompt": "Be concise.", "context": "Facts."},
            "transcript": [{"role": "customer", "text": "Help me."}],
        }

        import asyncio
        self.assertEqual(asyncio.run(engine.reply(call)), "Last Groq reply.")
        self.assertEqual(asyncio.run(engine.reply(call)), "Gemini reply.")
        asyncio.run(engine._client.aclose())

        self.assertEqual(
            [request.url.host for request in seen], ["api.groq.com", "gateway.example"]
        )

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
