"""Gnani Prisma/Timbre adapter. Credentials never leave the backend.

Protocol: https://docs.gnani.ai/api/STT/stt-websocket
          https://docs.gnani.ai/api/TTS/tts-websocket
"""

import asyncio
import base64
import json
import os
import re
import io
import wave
from dataclasses import dataclass

from websockets.asyncio.client import connect

from .voice import VoiceConfigurationError, VoiceEngine, VoiceProviderError


def browser_wav(audio):
    """Finalize streaming WAV length fields without changing its PCM samples."""
    try:
        with wave.open(io.BytesIO(audio), 'rb') as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            pcm = source.readframes(len(audio))
        if not pcm:
            raise ValueError('Empty audio')
        output = io.BytesIO()
        with wave.open(output, 'wb') as target:
            target.setnchannels(channels)
            target.setsampwidth(width)
            target.setframerate(rate)
            target.writeframes(pcm)
        return output.getvalue()
    except (wave.Error, EOFError, ValueError):
        raise VoiceProviderError('Gnani returned invalid WAV audio.') from None


# Timbre v3.0 catalogue: https://docs.gnani.ai/api/TTS/available-voices.md
# Every v3.0 voice speaks all supported Indian languages, including English and Hindi.
VOICES = {
    "Avinash": "Male · professional", "Devansh": "Male · conversational", "Harshad": "Male · professional",
    "Prakash": "Male · professional", "Shubham": "Male · energetic", "Yashraj": "Male · warm",
    "Chetana": "Female · warm", "Kalpana": "Female · warm", "Lakshmi": "Female · energetic",
    "Riyaa": "Female · confident", "Shivani": "Female · warm", "Tarika": "Female · warm",
    "Vasudha": "Female · energetic",
}


@dataclass(frozen=True)
class GnaniConfig:
    api_key: str
    stt_model: str = "prisma-v3.0"
    tts_model: str = "timbre-v3.0"
    voice: str = "Shivani"
    silence_ms: int = 500
    speed: float = 1.0
    audio_tags: bool = False

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("GNANI_API_KEY", "").strip(),
            stt_model=os.getenv("GNANI_STT_MODEL", "prisma-v3.0").strip(),
            tts_model=os.getenv("GNANI_TTS_MODEL", "timbre-v3.0").strip(),
            voice=os.getenv("GNANI_VOICE", "Shivani").strip(),
            silence_ms=max(300, min(2000, int(os.getenv("GNANI_SILENCE_MS", "500")))),
            speed=max(0.85, min(1.15, float(os.getenv("GNANI_SPEED", "1.0")))),
            audio_tags=os.getenv("GNANI_AUDIO_TAGS", "false").lower() == "true",
        )


class GnaniVoiceEngine(VoiceEngine):
    streaming_stt_url = "wss://api.vachana.ai/stt/v3/stream"

    def __init__(self, config=None, client=None, gnani_config=None):
        super().__init__(config, client)
        self.gnani = gnani_config or GnaniConfig.from_env()
        self.providers = {"stt": "Gnani Prisma", "llm": self.providers["llm"], "tts": "Gnani Timbre"}

    @property
    def ready(self):
        return all((self.gnani.api_key, self.gnani.voice, self.gnani.tts_model,
                    self.llm_ready))

    def require_ready(self):
        if not self.ready:
            raise VoiceConfigurationError(
                "Browser voice needs GNANI_API_KEY and a configured conversation model."
            )

    def streaming_headers(self, language):
        return {
            "x-api-key-id": self.gnani.api_key,
            "x-model": self.gnani.stt_model,
            # The live service currently rejects comma-separated locales despite
            # its v3 documentation. A Hindi locale with codemix is accepted.
            "lang_code": "hi-IN" if language in ("Hinglish", "Hindi") else "en-IN",
            "x-format": "codemix" if language == "Hinglish" else "transcribe",
            "x-sample-rate": "16000",
            "x-min-silence-ms": str(self.gnani.silence_ms),
            "x-min-speech-ms": "150",
            "x-idle-timeout-sec": "300",
        }

    def stream_event(self, message):
        event = json.loads(message)
        kind = event.get("type")
        if kind == "error":
            raise VoiceProviderError("Gnani speech recognition is unavailable. Check account access and credits.")
        if kind == "connected":
            return {"type": "ready"}
        if kind == "speech_start":
            return {"type": "speech_start"}
        if kind == "processing":
            return {"type": "processing"}
        if kind == "transcript":
            return {"type": "Turn", "transcript": event.get("text", ""),
                    "end_of_turn": True, "turn_order": event.get("segment_id") or event.get("segment_index"),
                    "stt_ms": event.get("latency")}
        return None

    def synthesis_payload(self, text, language="English", container="wav", delivery="neutral", voice=None):
        # Expression belongs to speech rendering, not the saved customer transcript.
        # Only use documented business-appropriate tags, never arbitrary LLM tags.
        text = re.sub(r"<[^>]*>", "", text).strip()
        if self.gnani.audio_tags and self.gnani.tts_model == "timbre-v3.0":
            text = re.sub(r"([.!?।])\s+", r"\1 <pauses> ", text, count=1)
            if delivery == "upbeat":
                text = "<excited> " + text
        return {
            "text": text, "model": self.gnani.tts_model, "voice": voice or self.gnani.voice,
            "language": {"English": "en-IN", "Hindi": "hi-IN", "Hinglish": "hi-en"}.get(language, "auto"),
            "speed": self.gnani.speed,
            "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                             "encoding": "linear_pcm", "container": container},
        }

    async def speak(self, text, language="English", delivery="neutral", voice=None):
        self.require_ready()
        client = self._http()
        try:
            response = await client.post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers={"X-API-Key-ID": self.gnani.api_key},
                json=self.synthesis_payload(text, language, delivery=delivery, voice=voice),
            )
            if response.status_code >= 400 or not response.content.startswith(b"RIFF"):
                raise VoiceProviderError("Gnani voice generation is unavailable. Check voice access and credits.")
            return browser_wav(response.content)
        except VoiceProviderError:
            raise
        except Exception:
            raise VoiceProviderError("Gnani voice generation is unavailable.") from None

    async def prepare_speech(self):
        """Open the TTS socket while the language model is generating text."""
        try:
            return await connect(
                "wss://api.vachana.ai/api/v1/tts",
                additional_headers={"X-API-Key-ID": self.gnani.api_key},
                compression=None, open_timeout=10, max_size=4_000_000,
            )
        except Exception:
            raise VoiceProviderError("Gnani realtime voice connection failed.") from None

    async def close_speech(self, connection):
        await connection.close()

    async def speech_chunks(self, text, language="English", delivery="neutral", connection=None, voice=None):
        """Yield raw 24 kHz PCM as generated, rather than awaiting a full file."""
        self.require_ready()
        try:
            if connection is None:
                async with connect(
                    "wss://api.vachana.ai/api/v1/tts",
                    additional_headers={"X-API-Key-ID": self.gnani.api_key},
                    compression=None, open_timeout=10, max_size=4_000_000,
                ) as upstream:
                    async for chunk in self._speech_chunks(upstream, text, language, delivery, voice):
                        yield chunk
            else:
                async for chunk in self._speech_chunks(connection, text, language, delivery, voice):
                    yield chunk
        except VoiceProviderError:
            raise
        except Exception:
            raise VoiceProviderError("Gnani realtime voice connection failed.") from None

    async def _speech_chunks(self, upstream, text, language, delivery, voice=None):
        await upstream.send(json.dumps(self.synthesis_payload(text, language, "raw", delivery, voice)))
        while True:
            message = await asyncio.wait_for(upstream.recv(), 25)
            event = json.loads(message)
            if event.get("type") == "error":
                raise VoiceProviderError("Gnani voice generation is unavailable.")
            data = event.get("data") or {}
            if data.get("audio"):
                chunk = base64.b64decode(data["audio"], validate=True)
                if len(chunk) % 2:
                    raise VoiceProviderError("Gnani returned invalid PCM audio.")
                yield chunk
            if event.get("type") == "complete" or data.get("is_final"):
                return
