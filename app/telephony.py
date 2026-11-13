"""VoiceLink phone bridge: live call audio <-> Gnani STT, conversation model, Gnani TTS.

VoiceLink opens a WebSocket to us per call and sends JSON events
(connected, start, media, mark, stop). Real calls carry G.711 A-law at 8 kHz in
160-byte frames even when a bot is configured for 16 kHz PCM, so the format is
read from the `start` event. Docs: https://app.voicelink.co.in/documentation/websocket-events/
"""

import asyncio
import base64
import json
import logging
import time
import uuid

import numpy as np

from .engine import now, private

GNANI_RATE = 16000  # Gnani STT input and Silero VAD frame rate
TTS_RATE = 24000  # Gnani streaming TTS output
VAD_FRAME_BYTES = 1024  # 512 PCM16 samples at 16 kHz


def _alaw_table():
    values = []
    for code in range(256):
        a = code ^ 0x55
        t = (a & 0x0F) << 4
        seg = (a & 0x70) >> 4
        if seg == 0:
            t += 8
        else:
            t = (t + 0x108) << (seg - 1)
        values.append(t if a & 0x80 else -t)
    return np.array(values, dtype=np.int16)


ALAW_TO_PCM = _alaw_table()
_SORTED = np.argsort(ALAW_TO_PCM)
_LEVELS = ALAW_TO_PCM[_SORTED].astype(np.int32)


def alaw_decode(data):
    return ALAW_TO_PCM[np.frombuffer(data, dtype=np.uint8)]


def alaw_encode(pcm):
    """Nearest A-law code for each PCM16 sample."""
    x = np.asarray(pcm, dtype=np.int32)
    i = np.clip(np.searchsorted(_LEVELS, x), 1, len(_LEVELS) - 1)
    nearer_low = (x - _LEVELS[i - 1]) <= (_LEVELS[i] - x)
    return _SORTED[np.where(nearer_low, i - 1, i)].astype(np.uint8).tobytes()


def resample(pcm, src, dst):
    """Linear-interpolation resampling of PCM16; averages first when downsampling by an integer factor."""
    pcm = np.asarray(pcm, dtype=np.int16)
    if src == dst or not len(pcm):
        return pcm
    if src % dst == 0:
        k = src // dst
        n = len(pcm) // k * k
        return pcm[:n].reshape(-1, k).mean(axis=1).round().astype(np.int16)
    out = np.arange(round(len(pcm) * dst / src)) * (src / dst)
    return np.interp(out, np.arange(len(pcm)), pcm).round().astype(np.int16)


class PhoneFormat:
    """Wire format of one call, from the `start` event's media_format."""

    def __init__(self, media_format):
        encoding = str((media_format or {}).get("encoding", "audio/alaw")).lower()
        self.alaw = "alaw" in encoding or "pcma" in encoding
        self.rate = int((media_format or {}).get("sample_rate") or (8000 if self.alaw else 16000))

    def to_gnani(self, payload):
        raw = base64.b64decode(payload)
        pcm = alaw_decode(raw) if self.alaw else np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<i2")
        return resample(pcm, self.rate, GNANI_RATE).astype("<i2").tobytes()

    def from_tts(self, chunk):
        pcm = resample(np.frombuffer(chunk, dtype="<i2"), TTS_RATE, self.rate)
        return base64.b64encode(alaw_encode(pcm) if self.alaw else pcm.astype("<i2").tobytes()).decode()


def custom_parameters(start):
    params = (start.get("start") or {}).get("custom_parameters") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {}
    return params if isinstance(params, dict) else {}


async def run_call(websocket, start, call, *, voice, vad, connect, save, is_live, max_seconds, idle_seconds):
    """Hold one live phone conversation until the caller hangs up or a limit is reached.

    `save(update)` applies update(call) to the stored call and returns the stored call.
    `is_live()` is False once the operator closes the call record; the bridge then hangs up.
    """
    fmt = PhoneFormat((start.get("start") or {}).get("media_format"))
    stream_sid = start.get("stream_sid") or (start.get("start") or {}).get("stream_sid")
    language = call["agent_snapshot"].get("language", "English")
    delivery = call["agent_snapshot"].get("delivery", "warm")
    agent_voice = call["agent_snapshot"].get("voice") or None
    state = {"reply": None, "speaking_id": None, "playing": False}
    started = last_speech = time.monotonic()
    send_lock = asyncio.Lock()

    async def send(event):
        if stream_sid:
            event["stream_sid"] = stream_sid
        async with send_lock:
            await websocket.send_json(event)

    async def speak(text, response_id):
        state["speaking_id"] = response_id
        async for chunk in voice.speech_chunks(text, language, delivery, voice=agent_voice):
            state["playing"] = True
            await send({"event": "media", "media": {"payload": fmt.from_tts(chunk)}})
        await send({"event": "mark", "mark": {"name": response_id}})

    async def answer(text, response_id):
        try:
            await _answer(text, response_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep the call open; the caller can repeat themselves.
            logging.getLogger("uvicorn.error").warning("phone_reply_failed call_id=%s", call["id"])

    async def _answer(text, response_id):
        def add_customer(c):
            c["transcript"].append({"role": "customer", "text": private(text), "at": now(), "response_id": response_id})
        current = save(add_customer)
        reply = private(await voice.reply(current))
        save(lambda c: c["transcript"].append(
            {"role": "agent", "text": reply, "at": now(), "delivery_status": "generated", "response_id": response_id}))
        await speak(reply, response_id)

    async def barge_in():
        """Caller started talking: stop the reply in flight and flush queued audio."""
        task, response_id = state["reply"], state["speaking_id"]
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if state["playing"] or (task and not task.done()):
            await send({"event": "clear"})
        if response_id and state["playing"]:
            def mark(c):
                for turn in c["transcript"]:
                    if turn.get("response_id") == response_id and turn["role"] == "agent":
                        turn["delivery_status"] = "interrupted"
            save(mark)
        state["playing"] = False
        state["speaking_id"] = None

    async def listen(upstream):
        nonlocal last_speech
        buffer = b""
        while True:
            event = await websocket.receive_json()
            kind = event.get("event")
            if kind == "stop":
                return
            if kind == "mark" and (event.get("mark") or {}).get("name") == state["speaking_id"]:
                state["playing"] = False
            if kind != "media":
                continue
            buffer += fmt.to_gnani((event.get("media") or {}).get("payload", ""))
            while len(buffer) >= VAD_FRAME_BYTES:
                frame, buffer = buffer[:VAD_FRAME_BYTES], buffer[VAD_FRAME_BYTES:]
                if vad is not None:
                    detected = await asyncio.to_thread(vad.process, frame, state["playing"])
                    if detected and detected.get("type") == "vad_speech_start":
                        last_speech = time.monotonic()
                        if state["playing"]:
                            await barge_in()
                await upstream.send(frame)

    async def transcripts(upstream):
        nonlocal last_speech
        async for message in upstream:
            event = voice.stream_event(message)
            text = (event or {}).get("transcript", "").strip()
            if event and event.get("type") == "Turn" and event.get("end_of_turn") and text:
                last_speech = time.monotonic()
                await barge_in()
                state["reply"] = asyncio.create_task(answer(text, uuid.uuid4().hex))

    async def limits():
        while True:
            now = time.monotonic()
            left = min(idle_seconds - (now - last_speech), max_seconds - (now - started))
            if left <= 0 or not await asyncio.to_thread(is_live):
                return
            await asyncio.sleep(min(15, left))

    async with connect(
        voice.streaming_stt_url,
        additional_headers=voice.streaming_headers(language),
        compression=None,
        open_timeout=10,
    ) as upstream:
        state["reply"] = asyncio.create_task(speak(call["transcript"][0]["text"], "opening:" + call["id"]))
        tasks = [asyncio.create_task(listen(upstream)), asyncio.create_task(transcripts(upstream)), asyncio.create_task(limits())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks + [state["reply"]]:
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, state["reply"], return_exceptions=True)
