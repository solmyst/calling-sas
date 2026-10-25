from datetime import datetime, timedelta, timezone
from .engine import DemoProvider, now
from .store import Store

AGENTS = [
    {
        "id": "agent-sales",
        "name": "Aria",
        "role": "Your first conversation, covered.",
        "use_case": "lead_qualification",
        "industry": "B2B services",
        "language": "English",
        "status": "active",
        "opening": "Hi {name}, I’m {agent}, an AI assistant for Northstar Studio. You asked about our services. Is now a good time for a quick conversation?",
        "question": "What does your team need help with, and how soon are you looking to get started?",
        "prompt": "Be warm, concise and transparent that you are an AI assistant. Ask one question at a time. Qualify need, team size and timeline. Never promise pricing or availability. Respect opt-outs immediately.",
        "context": "Northstar Studio is a fictional business offering customer engagement services. Discovery sessions are free; pricing is confirmed by a human.",
        "color": "mint",
    },
    {
        "id": "agent-reminders",
        "name": "Maya",
        "role": "A thoughtful reminder, right on time.",
        "use_case": "appointment_reminder",
        "industry": "Professional services",
        "language": "English",
        "status": "active",
        "opening": "Hi {name}, I’m {agent}, an AI assistant calling in this simulation to remind you about your consultation. May I confirm a few details?",
        "question": "Your fictional consultation is tomorrow at 10 AM. Does that time still work for you?",
        "prompt": "Confirm the appointment or record a rescheduling request. Do not claim to update any external calendar. Offer a person if needed.",
        "context": "This is a fictional consultation at Northstar Studio. Appointment changes require staff confirmation.",
        "color": "peach",
    },
    {
        "id": "agent-support",
        "name": "Leo",
        "role": "Helpful answers. Human when it matters.",
        "use_case": "customer_support",
        "industry": "Customer service",
        "language": "English",
        "status": "active",
        "opening": "Hi {name}, I’m {agent}, your AI support assistant in this demo. How can I help today?",
        "question": "Could you describe the issue and what you have tried so far?",
        "prompt": "Triage the issue, use only the supplied context, and offer human assistance. Never ask for passwords or verification codes.",
        "context": "Demo support is available Monday–Friday. Complex requests are handed to a human. No real ticketing system is connected.",
        "color": "lavender",
    },
]


def seed(store):
    with store.transaction() as db:
        if Store.get(db, "meta", "seed"):
            return
        for a in AGENTS:
            Store.put(db, "agents", a)
        contacts = []
        for i, (name, company, segment) in enumerate(
            [
                ("Jamie Morgan", "Northstar Studio", "New leads"),
                ("Alex Rivera", "Fieldwork Co.", "New leads"),
                ("Taylor Chen", "Juniper Health", "Appointments"),
                ("Sam Patel", "Atlas Works", "Support"),
                ("Casey Brooks", "Common Ground", "New leads"),
                ("Jordan Lee", "Harbor House", "New leads"),
            ],
            1,
        ):
            c = {
                "id": f"contact-{i}",
                "name": name,
                "company": company,
                "phone": f"+1202555010{i}",
                "email": f"demo{i}@example.com",
                "segment": segment,
                "consent": i != 6,
                "do_not_call": False,
                "notes": "Synthetic demo contact. Not a real customer.",
                "created_at": now(),
            }
            Store.put(db, "contacts", c)
            contacts.append(c)
        for w in [
            dict(
                id="workflow-1",
                name="New lead discovery",
                description="Turn interest into a useful first conversation.",
                agent_id="agent-sales",
                segment="New leads",
                action="Create follow-up task",
                status="active",
            ),
            dict(
                id="workflow-2",
                name="Tomorrow’s appointments",
                description="Confirm attendance and capture rescheduling requests.",
                agent_id="agent-reminders",
                segment="Appointments",
                action="Record confirmation",
                status="active",
            ),
        ]:
            Store.put(db, "workflows", w)
        provider = DemoProvider()
        for i in range(18):
            a = AGENTS[i % 3]
            c = contacts[i % 5]
            start = (
                datetime.now(timezone.utc)
                - timedelta(days=i % 7, hours=i % 5, minutes=3)
            ).isoformat()
            call = dict(
                id=f"seed-call-{i + 1}",
                mode="demo",
                source="seed",
                status="in_progress",
                outcome=None,
                agent_id=a["id"],
                contact_id=c["id"],
                agent_snapshot=a.copy(),
                contact_snapshot=c.copy(),
                started_at=start,
                ended_at=None,
                step=0,
                transcript=provider.start(a, c),
                summary="",
                next_action="",
                workflow_id=None,
            )
            texts = [
                "Yes, happy to talk",
                "We need help with customer follow-ups",
                "Yes, please",
            ]
            if i % 6 == 1:
                texts = ["Please call me later"]
            if i % 6 == 2:
                texts = ["Could I speak to a human?"]
            if i % 6 == 3:
                texts = ["No thanks, not interested"]
            for t in texts:
                provider.turn(call, t)
            call["ended_at"] = (
                datetime.fromisoformat(start) + timedelta(seconds=65 + i * 7)
            ).isoformat()
            for j, turn in enumerate(call["transcript"]):
                turn["at"] = (
                    datetime.fromisoformat(start) + timedelta(seconds=j * 12)
                ).isoformat()
            Store.put(db, "calls", call)
        Store.put(db, "meta", {"id": "seed", "version": 1})
