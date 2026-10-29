import asyncio, base64, hashlib, hmac, json, logging, os, re, secrets, time, uuid
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as websocket_connect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .store import Store
from .engine import DemoProvider, LiveCallingDisabled, now, private
from .seed import seed
from .voice import VoiceConfigurationError, VoiceEngine, VoiceProviderError
from .memory import update_memory

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Agent(Model):
    name: str = Field(min_length=1, max_length=60)
    role: str = Field(default="Ready for the next conversation.", max_length=140)
    use_case: Literal[
        "lead_qualification",
        "appointment_reminder",
        "customer_support",
        "follow_up",
        "sales",
    ] = "lead_qualification"
    industry: str = Field(default="General business", max_length=80)
    language: Literal["English", "Hindi", "Hinglish"] = "English"
    delivery: Literal["neutral", "warm", "calm", "upbeat"] = "warm"
    status: Literal["active", "paused"] = "active"
    opening: str = Field(min_length=1, max_length=1200)
    question: str = Field(min_length=1, max_length=1200)
    prompt: str = Field(min_length=1, max_length=6000)
    context: str = Field(min_length=1, max_length=6000)
    color: Literal["mint", "peach", "lavender"] = "mint"


class Contact(Model):
    name: str = Field(min_length=1, max_length=100)
    company: str = Field(default="", max_length=100)
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    email: str = Field(default="", max_length=200)
    segment: str = Field(default="New leads", min_length=1, max_length=80)
    consent: bool = False
    do_not_call: bool = False
    notes: str = Field(default="", max_length=2000)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v):
        if v and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
            raise ValueError("Invalid email")
        return v


class Workflow(Model):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=300)
    agent_id: str = Field(min_length=1, max_length=100)
    segment: str = Field(min_length=1, max_length=80)
    action: Literal[
        "Create follow-up task", "Record confirmation", "Review support outcome"
    ] = "Create follow-up task"
    status: Literal["active", "paused"] = "active"


class Start(Model):
    agent_id: str
    contact_id: str
    mode: str = "demo"
    request_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex, max_length=100, min_length=1
    )


class Turn(Model):
    text: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex, max_length=100, min_length=1
    )


class VoiceText(Model):
    text: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=100)


class Interrupt(Model):
    request_id: str = Field(min_length=1, max_length=100)
    played_ms: int = Field(default=0, ge=0, le=900000)
    customer_text: str = Field(default="", max_length=2000)


class Run(Model):
    request_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex, max_length=100, min_length=1
    )


class Login(Model):
    password: str = Field(max_length=300)


def require(db, kind, id):
    value = Store.get(db, kind, id)
    if not value:
        raise HTTPException(404, f"{kind.rstrip('s').title()} not found")
    return value


def metrics(calls):
    done = [c for c in calls if c["status"] == "completed"]
    success = [
        c for c in done if c["outcome"] in ("qualified", "confirmed", "resolved")
    ]
    durations = [
        max(
            0,
            (
                datetime.fromisoformat(c["ended_at"])
                - datetime.fromisoformat(c["started_at"])
            ).total_seconds(),
        )
        for c in done
    ]
    outcomes = Counter(c["outcome"] for c in done)
    days = []
    for i in range(6, -1, -1):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        group = [c for c in calls if c["started_at"][:10] == d]
        days.append(
            {
                "date": d,
                "label": datetime.fromisoformat(d).strftime("%a"),
                "calls": len(group),
                "successful": sum(
                    c.get("outcome") in ("qualified", "confirmed", "resolved")
                    for c in group
                ),
            }
        )
    return dict(
        total=len(calls),
        completed=len(done),
        successful=len(success),
        success_rate=round(100 * len(success) / len(done)) if done else 0,
        avg_duration=round(sum(durations) / len(durations)) if durations else 0,
        handoffs=outcomes["handoff"],
        outcomes=dict(outcomes),
        days=days,
        seeded=sum(c.get("source") == "seed" for c in calls),
    )


def create_app(db_path=None, voice_engine=None, vad_factory=None, request_extractor=None):
    environment = os.getenv("APP_ENV", "local")
    password = os.getenv("DEMO_PASSWORD", "")
    secret = os.getenv("SESSION_SECRET", "") or secrets.token_hex(32)
    origin = os.getenv("PUBLIC_ORIGIN", "http://127.0.0.1:8787").rstrip("/")
    if environment != "local" and (
        len(password) < 16
        or len(secret) < 32
        or not os.getenv("SESSION_SECRET")
        or not origin.startswith("https://")
    ):
        raise RuntimeError(
            "Hosted mode requires a 16+ character password, 32+ character SESSION_SECRET and HTTPS PUBLIC_ORIGIN."
        )
    hosts = (
        {"127.0.0.1", "localhost", "testserver"}
        if environment == "local"
        else {urlsplit(origin).hostname}
    )
    origins = {origin} | (
        {"http://127.0.0.1:8787", "http://localhost:8787", "http://testserver"}
        if environment == "local"
        else set()
    )
    store = Store(
        db_path or os.getenv("DATABASE_PATH", str(ROOT / "runtime/relay.sqlite"))
    )
    seed(store)
    provider = DemoProvider()
    if voice_engine is not None:
        voice = voice_engine
    elif os.getenv("SPEECH_PROVIDER", "legacy").strip().lower() == "gnani":
        from .gnani import GnaniVoiceEngine
        voice = GnaniVoiceEngine()
    else:
        voice = VoiceEngine()
    app = FastAPI(
        title="Relay Voice",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    attempts = defaultdict(deque)
    responding = set()
    active_responses = {}

    async def speak_for_call(text, call):
        if hasattr(voice, "speech_chunks"):
            agent = call["agent_snapshot"]
            return await voice.speak(text, agent.get("language", "English"), agent.get("delivery", "warm"))
        return await voice.speak(text)

    def valid(token):
        try:
            expiry, nonce, sig = token.split(".")
            expected = hmac.new(
                secret.encode(), f"{expiry}.{nonce}".encode(), hashlib.sha256
            ).hexdigest()
            return int(expiry) > time.time() and hmac.compare_digest(sig, expected)
        except (ValueError, AttributeError):
            return False

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.hostname not in hosts and not (
            request.method in ("GET", "HEAD") and request.url.path == "/health"
        ):
            return JSONResponse({"detail": "Unrecognized host"}, status_code=400)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if (
                request.headers.get("origin")
                and request.headers["origin"] not in origins
            ) or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse(
                    {"detail": "Cross-origin writes are blocked"}, status_code=403
                )
            try:
                size = int(request.headers.get("content-length", "0") or 0)
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid content length"}, status_code=400
                )
            limit = 8_000_000 if "/voice/turn" in request.url.path else 64000
            if size > limit:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        if (
            request.url.path.startswith("/api/")
            and request.url.path not in ("/api/session", "/api/login")
            and password
            and not valid(request.cookies.get("relay_session", ""))
        ):
            return JSONResponse(
                {"detail": "Sign in to this demo workspace"}, status_code=401
            )
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            }
        )
        if environment != "local":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.get("/health")
    def health():
        with store.transaction() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "mode": "demo", "voice_ready": voice.ready, "version": "0.2.0"}

    @app.get("/api/session")
    def session(request: Request):
        return {
            "authenticated": not password
            or valid(request.cookies.get("relay_session", "")),
            "password_required": bool(password),
        }

    @app.post("/api/login")
    def login(body: Login, request: Request):
        key = request.client.host if request.client else "unknown"
        q = attempts[key]
        while q and q[0] < time.time() - 300:
            q.popleft()
        if len(q) >= 10:
            raise HTTPException(429, "Too many attempts. Try again in five minutes.")
        q.append(time.time())
        if not password or not hmac.compare_digest(
            body.password.encode(), password.encode()
        ):
            raise HTTPException(401, "Incorrect workspace password")
        payload = f"{int(time.time() + 28800)}.{secrets.token_hex(16)}"
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        r = JSONResponse({"authenticated": True})
        r.set_cookie(
            "relay_session",
            payload + "." + sig,
            httponly=True,
            secure=environment != "local",
            samesite="strict",
            max_age=28800,
        )
        return r

    @app.post("/api/logout")
    def logout():
        r = JSONResponse({"ok": True})
        r.delete_cookie("relay_session")
        return r

    @app.get("/api/state")
    def state():
        with store.transaction() as db:
            data = {
                k: Store.all(db, k)
                for k in ("agents", "contacts", "workflows", "calls", "tasks")
            }
        data["calls"].sort(key=lambda c: c["started_at"], reverse=True)
        data["metrics"] = metrics(data["calls"])
        data["settings"] = {
            "mode": "browser_voice" if voice.ready else "demo",
            "telephony": "disabled",
            "conversation_engine": " + ".join(voice.providers.values()) if voice.ready else "Offline simulator",
            "ai_connected": voice.ready,
            "voice_providers": voice.providers,
            "streaming_audio": hasattr(voice, "speech_chunks"),
            "automatic_barge_in": True,
            "vad": "Silero v5",
            "memory_scope": "conversation",
            "workspace": "Relay Voice workspace",
            "authentication": bool(password),
            "version": "0.2.0",
        }
        return data

    def save(kind, model, id=None):
        with store.transaction() as db:
            previous = require(db, kind, id) if id else {}
            value = model.model_dump() | {
                "id": id or uuid.uuid4().hex,
                "created_at": previous.get("created_at", now()),
            }
            if kind == "workflows":
                require(db, "agents", value["agent_id"])
            Store.put(db, kind, value)
        return value

    @app.post("/api/agents")
    def new_agent(body: Agent):
        return save("agents", body)

    @app.put("/api/agents/{id}")
    def edit_agent(id: str, body: Agent):
        return save("agents", body, id)

    @app.post("/api/contacts")
    def new_contact(body: Contact):
        return save("contacts", body)

    @app.put("/api/contacts/{id}")
    def edit_contact(id: str, body: Contact):
        return save("contacts", body, id)

    @app.post("/api/workflows")
    def new_workflow(body: Workflow):
        return save("workflows", body)

    @app.put("/api/workflows/{id}")
    def edit_workflow(id: str, body: Workflow):
        return save("workflows", body, id)

    def make_call(db, aid, cid, wid=None, mode="demo"):
        a = require(db, "agents", aid)
        c = require(db, "contacts", cid)
        if a["status"] != "active":
            raise HTTPException(409, "This agent is paused.")
        if c["do_not_call"] or not c["consent"]:
            raise HTTPException(409, "Contact is opted out or has no recorded consent.")
        call = dict(
            id=uuid.uuid4().hex,
            mode=mode,
            source="workflow" if wid else "interactive",
            status="in_progress",
            outcome=None,
            agent_id=aid,
            contact_id=cid,
            agent_snapshot=a.copy(),
            contact_snapshot=c.copy(),
            started_at=now(),
            ended_at=None,
            step=0,
            transcript=provider.start(a, c),
            summary="",
            next_action="",
            workflow_id=wid,
        )
        if mode == "browser":
            call["transcript"][0]["response_id"] = "opening:" + call["id"]
        update_memory(call)
        Store.put(db, "calls", call)
        return call

    def finish(db, c, action=None):
        if c["outcome"] == "opted_out":
            contact = require(db, "contacts", c["contact_id"])
            contact["do_not_call"] = True
            Store.put(db, "contacts", contact)
        if c["status"] == "completed":
            Store.put(
                db,
                "tasks",
                {
                    "id": "task-" + c["id"],
                    "call_id": c["id"],
                    "contact_name": c["contact_snapshot"]["name"],
                    "title": action or c["next_action"],
                    "status": "open",
                    "created_at": now(),
                    "mode": c["mode"],
                },
            )
        Store.put(db, "calls", c)

    @app.post("/api/calls")
    def start(body: Start):
        if body.mode == "browser":
            try:
                voice.require_ready()
            except VoiceConfigurationError as e:
                raise HTTPException(503, str(e))
        elif body.mode != "demo":
            try:
                LiveCallingDisabled().start()
            except PermissionError as e:
                raise HTTPException(403, str(e))
        with store.transaction() as db:
            key = "call:" + body.request_id
            cached = Store.cached(db, key)
            if cached:
                if (cached["agent_id"], cached["contact_id"]) != (
                    body.agent_id,
                    body.contact_id,
                ):
                    raise HTTPException(
                        409, "Request ID already used with different inputs"
                    )
                return require(db, "calls", cached["id"])
            c = make_call(db, body.agent_id, body.contact_id, mode=body.mode)
            Store.cache(db, key, c)
        logging.getLogger("uvicorn.error").info("call_created id=%s mode=%s", c["id"], c["mode"])
        return c

    @app.post("/api/calls/{id}/voice/opening")
    async def voice_opening(id: str):
        with store.transaction() as db:
            c = require(db, "calls", id)
        if c["mode"] != "browser":
            raise HTTPException(409, "This is not a browser voice session.")
        try:
            audio = await speak_for_call(c["transcript"][0]["text"], c)
        except (VoiceConfigurationError, VoiceProviderError) as e:
            raise HTTPException(503, str(e))
        return {"audio": base64.b64encode(audio).decode(), "content_type": getattr(voice, "audio_content_type", "audio/mpeg")}

    @app.post("/api/calls/{id}/voice/turn")
    async def voice_turn(id: str, request: Request):
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in ("audio/webm", "audio/mp4", "audio/ogg"):
            raise HTTPException(415, "Unsupported browser audio format.")
        audio = await request.body()
        if not audio or len(audio) > 8_000_000:
            raise HTTPException(413 if audio else 400, "Microphone audio is empty or too large.")
        with store.transaction() as db:
            c = require(db, "calls", id)
            if c["mode"] != "browser" or c["status"] != "in_progress":
                raise HTTPException(409, "This browser voice session has ended.")
        try:
            customer_text = private(await voice.transcribe(audio, content_type))
            c["transcript"].append({"role": "customer", "text": customer_text, "at": now()})
            update_memory(c)
            assistant_text = private(await voice.reply(c))
            generated_audio = await speak_for_call(assistant_text, c)
        except (VoiceConfigurationError, VoiceProviderError, ValueError) as e:
            raise HTTPException(503, str(e))
        c["transcript"].append({"role": "agent", "text": assistant_text, "at": now()})
        with store.transaction() as db:
            latest = require(db, "calls", id)
            if latest["status"] != "in_progress":
                raise HTTPException(409, "This browser voice session has ended.")
            latest["transcript"] = c["transcript"]
            update_memory(latest)
            Store.put(db, "calls", latest)
        return {
            "call": latest,
            "transcript": customer_text,
            "reply": assistant_text,
            "audio": base64.b64encode(generated_audio).decode(),
            "content_type": getattr(voice, "audio_content_type", "audio/mpeg"),
        }

    @app.websocket("/api/calls/{id}/voice/stream")
    async def voice_stream(websocket: WebSocket, id: str):
        request_origin = websocket.headers.get("origin")
        if request_origin and request_origin not in origins:
            await websocket.close(code=1008)
            return
        if password and not valid(websocket.cookies.get("relay_session", "")):
            await websocket.close(code=1008)
            return
        with store.transaction() as db:
            c = Store.get(db, "calls", id)
        if not c or c.get("mode") != "browser" or c.get("status") != "in_progress":
            await websocket.close(code=1008)
            return
        try:
            voice.require_ready()
            from .vad import SileroVad
            vad = await asyncio.to_thread(vad_factory or SileroVad)
            await websocket.accept()
            async with websocket_connect(
                voice.streaming_stt_url_for(c["agent_snapshot"].get("language", "English")),
                additional_headers=voice.streaming_headers(c["agent_snapshot"].get("language", "English")),
                compression=None,
                open_timeout=10,
            ) as upstream:
                playback = False
                send_lock = asyncio.Lock()

                async def send_event(event):
                    async with send_lock:
                        await websocket.send_json(event)

                async def send_audio():
                    nonlocal playback
                    try:
                        while True:
                            incoming = await websocket.receive()
                            if incoming["type"] == "websocket.disconnect":
                                break
                            if incoming.get("text"):
                                control = json.loads(incoming["text"])
                                if control.get("type") == "playback":
                                    playback = bool(control.get("active"))
                                continue
                            chunk = incoming.get("bytes")
                            if chunk:
                                if len(chunk) != 1024:
                                    raise VoiceProviderError("Invalid microphone frame size.")
                                event = await asyncio.to_thread(vad.process, chunk, playback)
                                if event:
                                    await send_event(event)
                                await upstream.send(chunk)
                    except WebSocketDisconnect:
                        try:
                            if not hasattr(voice, "speech_chunks"):
                                await upstream.send('{"type":"Terminate"}')
                        except Exception:
                            pass

                async def send_transcripts():
                    async for message in upstream:
                        event = voice.stream_event(message)
                        if event:
                            await send_event(event)

                tasks = [asyncio.create_task(send_audio()), asyncio.create_task(send_transcripts())]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    task.result()
        except Exception:
            logging.getLogger("uvicorn.error").warning("streaming_stt_failed call_id=%s", id)
            try:
                await websocket.close(code=1011)
            except Exception:
                pass

    @app.post("/api/calls/{id}/voice/interrupt")
    async def interrupt_voice(id: str, body: Interrupt):
        with store.transaction() as db:
            c = require(db, "calls", id)
            if c["mode"] != "browser":
                raise HTTPException(409, "This is not a browser voice session.")
            cancelled = c.get("cancelled_response_ids", [])
            if body.request_id not in cancelled:
                c["cancelled_response_ids"] = (cancelled + [body.request_id])[-32:]
            if body.customer_text and not body.request_id.startswith("opening:") and not any(
                t.get("response_id") == body.request_id and t["role"] == "customer" for t in c["transcript"]
            ):
                c["transcript"].append({"role": "customer", "text": private(body.customer_text), "at": now(), "response_id": body.request_id})
                update_memory(c)
            for turn in c["transcript"]:
                if turn.get("response_id") == body.request_id and turn["role"] == "agent":
                    turn.update(delivery_status="interrupted", played_ms=body.played_ms)
            c["interruptions"] = len(c.get("cancelled_response_ids", []))
            Store.put(db, "calls", c)
        active = active_responses.get(id)
        if active and active["request_id"] == body.request_id:
            active["interrupted"] = True
            active_responses.pop(id, None)
            responding.discard(id)
            if active["task"]:
                active["task"].cancel()
        return {"interrupted": True, "request_id": body.request_id}

    @app.post("/api/calls/{id}/voice/respond/stream")
    async def voice_respond_stream(id: str, body: VoiceText):
        if not hasattr(voice, "speech_chunks"):
            raise HTTPException(409, "Streaming audio requires Gnani speech configuration.")
        with store.transaction() as db:
            c = require(db, "calls", id)
            if c["mode"] != "browser" or c["status"] != "in_progress":
                raise HTTPException(409, "This browser voice session has ended.")
        try:
            voice.require_ready()
        except VoiceConfigurationError as exc:
            raise HTTPException(503, str(exc))
        if id in responding:
            raise HTTPException(409, "This session is already preparing a response.")
        if len(c["transcript"]) >= 61:
            raise HTTPException(409, "Session turn limit reached. Please start a new conversation.")
        if body.request_id in c.get("cancelled_response_ids", []) or any(
            t.get("response_id") == body.request_id for t in c["transcript"]
        ):
            raise HTTPException(409, "This response was already processed or interrupted.")
        responding.add(id)
        active = {"request_id": body.request_id, "task": None, "interrupted": False}
        active_responses[id] = active

        async def events():
            started = time.perf_counter()
            def event(value):
                return json.dumps(value, ensure_ascii=False) + "\n"
            try:
                active["task"] = asyncio.current_task()
                if active["interrupted"]:
                    return
                with store.transaction() as db:
                    latest = require(db, "calls", id)
                    if latest["status"] != "in_progress":
                        raise VoiceProviderError("This browser voice session has ended.")
                    if body.request_id in latest.get("cancelled_response_ids", []):
                        return
                    c.update(latest)
                    c["transcript"] = latest["transcript"] + [{"role": "customer", "text": private(body.text), "at": now(), "response_id": body.request_id}]
                    update_memory(c)
                    Store.put(db, "calls", c)
                answer = private(await voice.reply(c))
                model_ms = round((time.perf_counter() - started) * 1000)
                c["transcript"].append({"role": "agent", "text": answer, "at": now(), "delivery_status": "generated", "response_id": body.request_id})
                # Persist generated text before audio delivery. Provider/playback
                # failure must not erase the customer's input or the answer.
                with store.transaction() as db:
                    latest = require(db, "calls", id)
                    if latest["status"] != "in_progress":
                        raise VoiceProviderError("This browser voice session has ended.")
                    latest["transcript"] = c["transcript"]
                    update_memory(latest)
                    Store.put(db, "calls", latest)
                yield event({"type": "reply", "call": latest, "llm_ms": model_ms, "response_id": body.request_id})
                first_audio_ms = None
                async for chunk in voice.speech_chunks(answer, c["agent_snapshot"].get("language", "English"), c["agent_snapshot"].get("delivery", "warm")):
                    if first_audio_ms is None:
                        first_audio_ms = round((time.perf_counter() - started) * 1000)
                    yield event({"type": "audio", "audio": base64.b64encode(chunk).decode(), "sample_rate": 24000})
                if first_audio_ms is None:
                    raise VoiceProviderError("No generated audio was received.")
                timing = {"first_audio_ms": first_audio_ms, "llm_ms": model_ms,
                          "total_ms": round((time.perf_counter() - started) * 1000)}
                with store.transaction() as db:
                    latest = require(db, "calls", id)
                    latest["voice_timing"] = timing
                    Store.put(db, "calls", latest)
                yield event({"type": "complete", **timing})
            except asyncio.CancelledError:
                raise
            except Exception:
                yield event({"type": "error", "message": "Voice response failed. Your saved transcript is available; retry or restart the session."})
            finally:
                if active_responses.get(id) is active:
                    active_responses.pop(id, None)
                    responding.discard(id)
        return StreamingResponse(events(), media_type="application/x-ndjson",
                                 headers={"X-Accel-Buffering": "no"})

    @app.post("/api/calls/{id}/voice/respond")
    async def voice_respond(id: str, body: VoiceText):
        with store.transaction() as db:
            c = require(db, "calls", id)
            if c["mode"] != "browser" or c["status"] != "in_progress":
                raise HTTPException(409, "This browser voice session has ended.")
        try:
            customer_text = private(body.text)
            c["transcript"].append({"role": "customer", "text": customer_text, "at": now()})
            update_memory(c)
            assistant_text = private(await voice.reply(c))
            generated_audio = await speak_for_call(assistant_text, c)
        except (VoiceConfigurationError, VoiceProviderError, ValueError) as e:
            raise HTTPException(503, str(e))
        c["transcript"].append({"role": "agent", "text": assistant_text, "at": now()})
        with store.transaction() as db:
            latest = require(db, "calls", id)
            if latest["status"] != "in_progress":
                raise HTTPException(409, "This browser voice session has ended.")
            latest["transcript"] = c["transcript"]
            update_memory(latest)
            Store.put(db, "calls", latest)
        return {"call": latest, "transcript": customer_text, "reply": assistant_text,
                "audio": base64.b64encode(generated_audio).decode(), "content_type": getattr(voice, "audio_content_type", "audio/mpeg")}

    @app.get("/api/calls/{id}")
    def get_call(id: str):
        with store.transaction() as db:
            return require(db, "calls", id)

    @app.post("/api/calls/{id}/turn")
    def turn(id: str, body: Turn):
        with store.transaction() as db:
            key = "turn:" + id + ":" + body.request_id
            cached = Store.cached(db, key)
            if cached:
                return cached
            c = require(db, "calls", id)
            if c["status"] != "in_progress":
                raise HTTPException(409, "This conversation has ended")
            if len(c["transcript"]) >= 61:
                raise HTTPException(
                    409, "Demo turn limit reached. End this call and start another."
                )
            provider.turn(c, body.text)
            update_memory(c)
            finish(db, c)
            Store.cache(db, key, c)
            return c

    @app.post("/api/calls/{id}/end")
    def end(id: str):
        with store.transaction() as db:
            c = require(db, "calls", id)
            if c["status"] == "in_progress":
                browser = c["mode"] == "browser"
                c.update(
                    status="cancelled",
                    outcome="cancelled",
                    ended_at=now(),
                    summary=(
                        "Browser voice session ended by the operator."
                        if browser
                        else "Simulation ended by the operator."
                    ),
                    next_action="No action",
                )
                Store.put(db, "calls", c)
                if browser and any(t["role"] == "customer" for t in c["transcript"]):
                    customer = " ".join(t["text"] for t in c["transcript"] if t["role"] == "customer").lower()
                    opted_out = bool(re.search(r"do not call|don't call|stop calling|unsubscribe|कॉल मत|फोन मत", customer))
                    handoff = bool(re.search(r"\bhuman\b|\bmanager\b|इंसान|किसी व्यक्ति", customer))
                    outcome = "opted_out" if opted_out else "handoff" if handoff else "follow_up"
                    c.update(status="completed", outcome=outcome,
                             summary=f"Browser {c['agent_snapshot']['use_case']} session saved for review. No external action was executed.",
                             next_action="Respect opt-out" if opted_out else "Review human handoff request" if handoff else "Review transcript and agree next step")
                    finish(db, c)
            return c

    @app.get("/api/calls/{id}/export")
    def export(id: str):
        with store.transaction() as db:
            c = require(db, "calls", id)
        label = "BROWSER VOICE SESSION" if c["mode"] == "browser" else "SIMULATED CALL"
        txt = f"RELAY VOICE — {label}\nCall: {c['id']}\nAgent: {c['agent_snapshot']['name']}\nOutcome: {c['outcome'] or 'In progress'}\n{c['summary']}\n\n"
        txt += "\n\n".join(f"{t['role'].upper()}: {t['text']}" for t in c["transcript"])
        return PlainTextResponse(
            private(txt),
            headers={"Content-Disposition": f'attachment; filename="relay-{id}.txt"'},
        )

    @app.post("/api/workflows/{id}/run")
    def run(id: str, body: Run):
        with store.transaction() as db:
            key = "workflow:" + id + ":" + body.request_id
            cached = Store.cached(db, key)
            if cached:
                return cached
            w = require(db, "workflows", id)
            a = require(db, "agents", w["agent_id"])
            if w["status"] != "active" or a["status"] != "active":
                raise HTTPException(409, "Workflow or agent is paused")
            contacts = [
                c for c in Store.all(db, "contacts") if c["segment"] == w["segment"]
            ]
            ids = []
            skipped = 0
            for contact in contacts:
                if contact["do_not_call"] or not contact["consent"]:
                    skipped += 1
                    continue
                c = make_call(db, a["id"], contact["id"], id)
                for text in [
                    "Yes, I can talk",
                    "We need help with our next steps",
                    "Yes, please proceed",
                ]:
                    provider.turn(c, text)
                finish(db, c, w["action"])
                ids.append(c["id"])
            result = {
                "created": len(ids),
                "skipped": skipped,
                "call_ids": ids,
                "mode": "demo",
            }
            Store.cache(db, key, result)
            return result

    @app.post("/api/tasks/{id}/complete")
    def complete(id: str):
        with store.transaction() as db:
            task = require(db, "tasks", id)
            task["status"] = "done"
            Store.put(db, "tasks", task)
            return task

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static/index.html")

    from .requests import router as request_router
    app.include_router(request_router(store, request_extractor or getattr(voice, "extract_request", None)))
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
