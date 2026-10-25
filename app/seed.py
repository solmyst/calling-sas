"""Create minimum product configuration without fabricated activity data."""

from .engine import now
from .store import Store

PRODUCT_AGENT = {
    "id": "agent-sales", "name": "Relay AI",
    "role": "AI calling consultant for Relay Voice.", "use_case": "sales",
    "industry": "Business services", "language": "English", "status": "active",
    "opening": "Hello {name}, this is {agent} from Relay Voice. You booked a demo with us, and this browser conversation is the demo itself. Is this still a good time to talk for about five minutes?",
    "question": "What kind of business do you run?",
    "prompt": "Disclose that you are an AI voice assistant. Follow the discovery flow, ask one question at a time, acknowledge answers naturally, and keep every reply brief enough for a phone conversation. Qualify business type, weekly enquiry volume, and missed follow-ups. Then propose one small measurable pilot. Never invent pricing, integrations, bookings, or completed actions.",
    "context": "Relay Voice provides configurable AI voice agents for lead qualification, appointment reminders, customer support, follow-ups, and sales calls. This is a browser voice demonstration using the computer microphone and speakers; it does not dial a telephone number. A pilot starts with one workflow and measures results before expansion.",
    "color": "mint",
}

BOOKING_AGENT = {
    "id": "agent-booking", "name": "Nisha",
    "role": "Hindi and Hinglish customer-help and booking assistant.",
    "use_case": "appointment_reminder", "industry": "Services and clinics",
    "language": "Hinglish", "status": "active",
    "opening": "नमस्ते {name}, मैं {agent}, एक AI voice assistant बोल रही हूँ। मैं आपकी booking में मदद करने के लिए यहाँ हूँ। क्या अभी बात करने का सही समय है?",
    "question": "आप किस service या appointment के लिए booking करना चाहते हैं?",
    "prompt": "Clearly disclose that you are an AI assistant. Speak in natural Hindi or simple Hinglish matching the customer. Help identify the requested service, preferred date and preferred time, one question at a time. Summarize the booking request, but never claim that a booking is confirmed or that a calendar was updated. Escalate complaints, emergencies, payment disputes, and requests for a human.",
    "context": "This agent demonstrates customer help and appointment booking intake. It can collect a requested service, date and time and create a follow-up record. It cannot see live availability, confirm an appointment, take payment, or modify an external calendar until those integrations are explicitly configured.",
    "color": "peach",
}

DEMO_PARTICIPANT = {
    "id": "contact-1", "name": "Demo participant", "company": "",
    "phone": "+910000000000", "email": "", "segment": "Browser demo",
    "consent": True, "do_not_call": False,
    "notes": "Local browser-session placeholder. Replace with an actual consenting prospect before a customer demo.",
    "created_at": now(),
}

def seed(store):
    with store.transaction() as db:
        marker = Store.get(db, "meta", "seed")
        version = marker.get("version", 0) if marker else 0
        if version >= 3:
            return
        if version < 2:
            # Remove only records shipped by the former fictional showcase.
            db.execute("DELETE FROM records WHERE kind='calls' AND id LIKE 'seed-call-%'")
            db.execute("DELETE FROM records WHERE kind='tasks' AND id LIKE 'task-seed-call-%'")
            db.execute("DELETE FROM records WHERE kind='workflows' AND id IN ('workflow-1','workflow-2')")
            db.execute("DELETE FROM records WHERE kind='agents' AND id IN ('agent-reminders','agent-support')")
            db.execute("DELETE FROM records WHERE kind='contacts' AND id IN ('contact-2','contact-3','contact-4','contact-5','contact-6')")
            Store.put(db, "agents", PRODUCT_AGENT)
            Store.put(db, "contacts", DEMO_PARTICIPANT)
        Store.put(db, "agents", BOOKING_AGENT)
        Store.put(db, "meta", {"id": "seed", "version": 3})
