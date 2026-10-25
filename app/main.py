import hashlib, hmac, logging, os, re, secrets, time, uuid
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .store import Store
from .engine import DemoProvider, LiveCallingDisabled, now, private
from .seed import seed

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
    language: Literal["English"] = "English"
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


def create_app(db_path=None):
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
    app = FastAPI(
        title="Relay Voice",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    attempts = defaultdict(deque)

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
        if request.url.hostname not in hosts:
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
            if size > 64000:
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
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            }
        )
        if environment != "local":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.get("/health")
    def health():
        with store.transaction() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "mode": "demo", "version": "0.1.0"}

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
            "mode": "demo",
            "telephony": "disabled",
            "conversation_engine": "Offline simulator",
            "ai_connected": False,
            "workspace": "Northstar workspace",
            "authentication": bool(password),
            "version": "0.1.0",
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

    def make_call(db, aid, cid, wid=None):
        a = require(db, "agents", aid)
        c = require(db, "contacts", cid)
        if a["status"] != "active":
            raise HTTPException(409, "This agent is paused.")
        if c["do_not_call"] or not c["consent"]:
            raise HTTPException(409, "Contact is opted out or has no recorded consent.")
        call = dict(
            id=uuid.uuid4().hex,
            mode="demo",
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
                    "mode": "demo",
                },
            )
        Store.put(db, "calls", c)

    @app.post("/api/calls")
    def start(body: Start):
        if body.mode != "demo":
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
            c = make_call(db, body.agent_id, body.contact_id)
            Store.cache(db, key, c)
        logging.getLogger("uvicorn.error").info("call_created id=%s mode=demo", c["id"])
        return c

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
            finish(db, c)
            Store.cache(db, key, c)
            return c

    @app.post("/api/calls/{id}/end")
    def end(id: str):
        with store.transaction() as db:
            c = require(db, "calls", id)
            if c["status"] == "in_progress":
                c.update(
                    status="cancelled",
                    outcome="cancelled",
                    ended_at=now(),
                    summary="Simulation ended by the operator.",
                    next_action="No action",
                )
                Store.put(db, "calls", c)
            return c

    @app.get("/api/calls/{id}/export")
    def export(id: str):
        with store.transaction() as db:
            c = require(db, "calls", id)
        txt = f"RELAY VOICE — SIMULATED CALL\nCall: {c['id']}\nAgent: {c['agent_snapshot']['name']}\nOutcome: {c['outcome'] or 'In progress'}\n{c['summary']}\n\n"
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

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
