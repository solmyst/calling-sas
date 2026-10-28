"""Paid live LLM + TTS smoke tests with synthetic conversations and temporary DB."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from app.gnani import GnaniVoiceEngine
from app.main import create_app

SCENARIOS = {
    "demo-sales": "Yes. I run a car dealership. We get fifty enquiries weekly and miss follow-ups when busy.",
    "demo-helper": "आप कौन कौन सी services देते हैं? क्या मैं हिंदी में बात कर सकता हूँ?",
    "demo-cx": "My website microphone isn't working. I've already refreshed the page. Please help.",
    "demo-booking": "मुझे अगले सोमवार सुबह दस बजे service appointment चाहिए। क्या booking confirm है?",
}

with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"APP_ENV": "local", "DEMO_PASSWORD": ""}):
    results = []
    with TestClient(create_app(temp + "/smoke.sqlite", voice_engine=GnaniVoiceEngine())) as client:
        for agent, text in SCENARIOS.items():
            call = client.post("/api/calls", json={"agent_id": agent, "contact_id": "contact-1", "mode": "browser"})
            assert call.status_code == 200, f"{agent}: call creation failed"
            path = "/api/calls/" + call.json()["id"]
            opening = client.post(path + "/voice/opening")
            assert opening.status_code == 200 and opening.json()["content_type"] == "audio/wav", f"{agent}: opening failed"
            response = client.post(path + "/voice/respond/stream", json={"text": text})
            events = [json.loads(line) for line in response.text.splitlines()]
            assert events[-1]["type"] == "complete", f"{agent}: streaming reply failed"
            assert any(e["type"] == "audio" for e in events), f"{agent}: no audio"
            saved = client.get(path).json()
            assert len(saved["transcript"]) == 3
            assert client.post(path + "/end").json()["status"] == "completed"
            result = {"agent": agent, "reply": saved["transcript"][-1]["text"], **saved["voice_timing"], "synthetic_test": True}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    Path("runtime/gnani-demo-flow-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
