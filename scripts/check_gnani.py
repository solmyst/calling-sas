"""Live paid-provider smoke test using synthetic speech only.

Run from the project root: .venv/bin/python scripts/check_gnani.py
No keys, account response bodies or customer data are printed or saved.
"""
import asyncio
import json
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
from websockets.asyncio.client import connect
from app.gnani import GnaniVoiceEngine


async def main():
    load_dotenv()
    engine = GnaniVoiceEngine()
    engine.require_ready()
    reports = []
    for language, text in [("English", "Hello, I am your AI assistant. How can I help you today?"),
                           ("Hindi", "नमस्ते। मैं आपकी ए आई असिस्टेंट हूँ। आपको किस सेवा में मदद चाहिए?")]:
        started = time.perf_counter()
        chunks, first_ms = [], None
        async for chunk in engine.speech_chunks(text, language):
            if first_ms is None:
                first_ms = round((time.perf_counter() - started) * 1000)
            chunks.append(chunk)
        pcm = b"".join(chunks)
        if not pcm:
            raise RuntimeError("Gnani returned no audio")
        audio_path = Path("runtime") / f"gnani-{language.lower()}-sample.wav"
        audio_path.parent.mkdir(exist_ok=True, mode=0o700)
        with wave.open(str(audio_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(pcm)
        audio_path.chmod(0o600)
        # Test the same 16 kHz frames that the browser sends. Simple integer
        # resampling is sufficient for this synthetic connectivity check.
        samples = memoryview(pcm).cast('h')
        import struct
        pcm16 = b"".join(struct.pack('<h', samples[int(i * 1.5)]) for i in range(int(len(samples) / 1.5)))
        frames = [pcm16[i:i+1024].ljust(1024, b'\x00') for i in range(0, len(pcm16), 1024)]
        async with connect(engine.streaming_stt_url_for(language), additional_headers=engine.streaming_headers(language), compression=None, open_timeout=15) as socket:
            ready = json.loads(await asyncio.wait_for(socket.recv(), 15))
            if ready.get("type") != "connected":
                raise RuntimeError("STT did not acknowledge readiness")
            async def send():
                for frame in frames + [bytes(1024)] * 60:
                    await socket.send(frame)
                    await asyncio.sleep(0.032)
            sender = asyncio.create_task(send())
            texts = []
            try:
                await sender
                async with asyncio.timeout(30):
                    while True:
                        event = engine.stream_event(await socket.recv())
                        if event and event.get("type") == "Turn" and event.get("transcript"):
                            texts.append(event["transcript"])
                            break
            finally:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
            if not texts:
                raise RuntimeError("No transcript returned for synthetic speech")
        report = {"language": language, "tts_first_audio_ms": first_ms,
                  "pcm_bytes": len(pcm), "transcript": " ".join(texts),
                  "audio": str(audio_path), "synthetic_test": True}
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False))
    Path("runtime/gnani-smoke-results.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("Gnani smoke test failed:", type(exc).__name__, "Check provider access, model, voice and credits.")
        sys.exit(1)
