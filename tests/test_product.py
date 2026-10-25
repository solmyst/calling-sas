import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.main import create_app


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(self.tmp.name + "/test.sqlite"))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def data(self):
        return self.client.get("/api/state").json()

    def start(self, **extra):
        return self.client.post(
            "/api/calls",
            json={
                "agent_id": "agent-sales",
                "contact_id": "contact-1",
                "mode": "demo",
                **extra,
            },
        )

    def test_end_to_end_persistence_and_metrics(self):
        before = self.data()["metrics"]["total"]
        c = self.start().json()
        for text in [
            "Yes, happy to talk",
            "We have a team of 12 and need help with follow-ups",
            "Yes, please arrange a demo",
        ]:
            r = self.client.post(f"/api/calls/{c['id']}/turn", json={"text": text})
            self.assertEqual(r.status_code, 200, r.text)
        call = r.json()
        self.assertEqual(call["outcome"], "qualified")
        self.assertEqual(call["status"], "completed")
        self.assertEqual(len(call["transcript"]), 7)
        self.assertEqual(self.data()["metrics"]["total"], before + 1)
        self.assertEqual(
            self.client.get("/api/calls/" + c["id"]).json()["outcome"], "qualified"
        )
        self.assertEqual(
            self.client.post(
                f"/api/calls/{c['id']}/turn", json={"text": "again"}
            ).status_code,
            409,
        )

    def test_live_calls_always_rejected(self):
        self.assertEqual(self.start(mode="live").status_code, 403)

    def test_opt_out_suppresses_future_calls(self):
        c = self.start().json()
        r = self.client.post(
            f"/api/calls/{c['id']}/turn", json={"text": "Do not call me again"}
        )
        self.assertEqual(r.json()["outcome"], "opted_out")
        self.assertEqual(self.start().status_code, 409)

    def test_redacts_before_persisting(self):
        c = self.start().json()
        r = self.client.post(
            f"/api/calls/{c['id']}/turn",
            json={"text": "My OTP is 123456 and PAN ABCDE1234F"},
        )
        self.assertNotIn("123456", r.text)
        self.assertNotIn("ABCDE1234F", self.client.get("/api/calls/" + c["id"]).text)

    def test_idempotent_creation(self):
        a = self.start(request_id="same-request").json()
        b = self.start(request_id="same-request").json()
        self.assertEqual(a["id"], b["id"])

    def test_consent_and_validation(self):
        self.assertEqual(self.start(contact_id="contact-6").status_code, 409)
        self.assertEqual(self.start(agent_id="missing").status_code, 404)
        self.assertEqual(
            self.client.post("/api/contacts", json={"name": ""}).status_code, 422
        )

    def test_origin_and_host_protection(self):
        self.assertEqual(
            self.client.post(
                "/api/calls", json={}, headers={"Origin": "https://evil.example"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/state", headers={"Host": "evil.example"}).status_code,
            400,
        )

    def test_workflow_idempotency(self):
        body = {"request_id": "workflow-test"}
        a = self.client.post("/api/workflows/workflow-1/run", json=body)
        b = self.client.post("/api/workflows/workflow-1/run", json=body)
        self.assertEqual(a.status_code, 200, a.text)
        self.assertEqual(a.json(), b.json())
        self.assertGreater(a.json()["created"], 0)

    def test_configuration_snapshot(self):
        agent = next(x for x in self.data()["agents"] if x["id"] == "agent-sales")
        agent["opening"] = "Hello {name}, welcome to the new demo."
        self.assertEqual(
            self.client.put("/api/agents/agent-sales", json=agent).status_code, 200
        )
        c = self.start().json()
        self.assertIn("welcome to the new demo", c["transcript"][0]["text"])
        agent["opening"] = "Changed later"
        self.client.put("/api/agents/agent-sales", json=agent)
        self.assertIn(
            "welcome to the new demo", self.client.get("/api/calls/" + c["id"]).text
        )

    def test_export_and_cancel(self):
        c = self.start().json()
        self.assertEqual(
            self.client.post("/api/calls/" + c["id"] + "/end").json()["status"],
            "cancelled",
        )
        r = self.client.get("/api/calls/" + c["id"] + "/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("SIMULATED", r.text)


if __name__ == "__main__":
    unittest.main()
