"""Persistent, single-conversation memory of redacted customer statements.

No cross-contact matching, external store or extra model request. Corrections stay
in chronological order so the model can prefer the latest statement.
"""
import json

from .engine import private


def update_memory(call):
    notes = [
        {"text": private(turn["text"])[:2000], "at": turn.get("at", "")}
        for turn in call["transcript"] if turn["role"] == "customer"
    ][-32:]
    call["memory"] = {"scope": "conversation", "customer_notes": notes,
                      "corrections": "Latest customer statement takes precedence."}
    return call["memory"]


def memory_context(call):
    memory = call.get("memory") or update_memory(call)
    notes = []
    for note in memory.get("customer_notes", [])[-32:]:
        text = note["text"]
        if len(text) > 350:
            text = text[:170] + " … " + text[-170:]
        notes.append(text)
    return json.dumps(notes, ensure_ascii=False)


def history_context(call):
    for turn in call["transcript"][-20:]:
        text = turn["text"]
        if turn["role"] == "agent" and turn.get("delivery_status") == "interrupted":
            text = "[This AI reply was interrupted. Do not assume the customer heard the generated answer.]"
        yield {"role": "assistant" if turn["role"] == "agent" else "user", "content": text}
