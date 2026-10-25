"""Offline conversation provider. No sockets, provider credentials or telephone operations."""

import re
from datetime import datetime, timezone
from typing import Protocol
from .reused.redaction import redact
from .reused.voicemail import is_voicemail_announcement

USE_CASES = (
    "lead_qualification",
    "appointment_reminder",
    "customer_support",
    "follow_up",
    "sales",
)
ENDINGS = {
    "lead_qualification": "qualified",
    "appointment_reminder": "confirmed",
    "customer_support": "resolved",
    "follow_up": "follow_up",
    "sales": "qualified",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def private(text):
    text = redact(text)
    text = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[EMAIL REDACTED]",
        text,
        flags=re.I,
    )
    return text


def line(role, text):
    return {"role": role, "text": private(text), "at": now()}


def render(text, agent, contact):
    for k, v in {
        "name": contact["name"].split()[0],
        "company": contact["company"],
        "agent": agent["name"],
    }.items():
        text = text.replace("{" + k + "}", v)
    return text


class CallingProvider(Protocol):
    def start(self, agent: dict, contact: dict) -> list[dict]: ...
    def turn(self, call: dict, text: str) -> dict: ...


class LiveCallingDisabled:
    def start(self, *args, **kwargs):
        raise PermissionError(
            "Real calling is unavailable in this release. No telephony adapter is installed."
        )


class DemoProvider:
    def start(self, agent, contact):
        return [line("agent", render(agent["opening"], agent, contact))]

    def turn(self, call, text):
        agent = call["agent_snapshot"]
        call["transcript"].append(line("customer", text))
        t = text.lower().strip()
        outcome = None
        if re.search(
            r"do not call|don't call|stop calling|unsubscribe|remove me|opt out", t
        ):
            reply = "Understood. I have marked this demo contact as do not call. Thank you for your time."
            outcome = "opted_out"
        elif is_voicemail_announcement(text):
            reply = "An automated greeting was detected in this simulation. The conversation is closed without qualifying this contact."
            outcome = "no_answer"
        elif re.search(r"\bhuman\b|\bperson\b|\bmanager\b|\bescalate\b", t):
            reply = "Of course. I have recorded a handoff request for your team in this demo. A real transfer is not connected."
            outcome = "handoff"
        elif re.search(r"\bbusy\b|call (me )?later|\btomorrow\b|another time", t):
            reply = "Absolutely. I have recorded a follow-up request. Your team can confirm a convenient time."
            outcome = "follow_up"
        elif re.search(
            r"not interested|\bno thanks\b|\bnot now\b|^no[.! ]*$|^nope[.! ]*$", t
        ):
            reply = "Thank you for letting me know. I will close this conversation."
            outcome = "not_interested"
        elif re.search(r"\botp\b|password|credit card|verification code", t):
            reply = "Please do not share passwords, payment details or verification codes. We do not need those for this conversation."
        elif "?" in text:
            reply = f"Here is the business information available for this demo: {agent['context']} {agent['question']}"
        elif call["step"] >= 2 and not re.search(
            r"\byes\b|\bsure\b|\bagree\b|\bconfirm\b|\bplease\b|\bokay\b|\bok\b", t
        ):
            reply = "Would you like me to record that next step? Please confirm yes, decline, or ask for a human."
        else:
            call["step"] += 1
            if call["step"] == 1:
                reply = render(agent["question"], agent, call["contact_snapshot"])
            elif call["step"] == 2:
                reply = {
                    "appointment_reminder": "Thank you. Should I record this appointment as confirmed?",
                    "customer_support": "I have noted your request. Does this resolve your question, or would you prefer a human?",
                    "follow_up": "Thanks for the update. May I record a follow-up request for your team?",
                }.get(
                    agent["use_case"],
                    "That sounds like a good fit. May I record a request for your team to arrange a demo?",
                )
            else:
                outcome = ENDINGS[agent["use_case"]]
                reply = "Thank you. I have recorded the outcome in this demo workspace. No booking, message or real call has been made."
        call["transcript"].append(line("agent", reply))
        if outcome:
            call.update(status="completed", outcome=outcome, ended_at=now())
            call["summary"] = (
                f"Simulated {agent['use_case'].replace('_', ' ')} conversation. Outcome: {outcome.replace('_', ' ')}."
            )
            call["next_action"] = {
                "no_answer": "Review unanswered contact",
                "qualified": "Arrange a discovery meeting",
                "confirmed": "Review appointment confirmation",
                "handoff": "Assign a human owner",
                "follow_up": "Confirm callback time",
                "opted_out": "Suppress future outreach",
                "not_interested": "Close lead",
                "resolved": "Review resolution",
            }[outcome]
        return call
