"""Accounts: one unlimited main account plus self-service trial users.

The main account is configured by environment (ADMIN_EMAIL + DEMO_PASSWORD) and
owns the MAIN workspace. Each trial user owns a private workspace named by
their user ID. Trial voice time is metered as live microphone stream seconds.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from .engine import now
from .store import MAIN, SYSTEM, Store

TRIAL_DAYS = 7
TRIAL_VOICE_SECONDS = 15 * 60
TRIAL_SIGNUPS_PER_DAY = 20


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt.hex() + "$" + digest.hex()


def check_password(password, stored):
    salt, digest = stored.split("$")
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), stored)


def main_account(email):
    return {"id": MAIN, "email": email, "role": "main"}


def find(db, email):
    email = email.strip().lower()
    return next((u for u in Store.all(db, "users", ws=SYSTEM) if u["email"] == email), None)


def get(db, user_id):
    return Store.get(db, "users", user_id, ws=SYSTEM)


def signups_today(db):
    today = now()[:10]
    return sum(u["created_at"][:10] == today for u in Store.all(db, "users", ws=SYSTEM))


def create_trial(db, email, password):
    user = {
        "id": uuid.uuid4().hex,
        "email": email.strip().lower(),
        "password": hash_password(password),
        "role": "trial",
        "created_at": now(),
        "trial_ends": (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)).isoformat(),
        "voice_seconds": 0,
        "disabled": False,
    }
    Store.put(db, "users", user, ws=SYSTEM)
    return user


def voice_left(user):
    """Seconds of live voice left; None means unlimited."""
    if user["role"] == "main":
        return None
    if datetime.fromisoformat(user["trial_ends"]) <= datetime.now(timezone.utc):
        return 0
    return max(0, TRIAL_VOICE_SECONDS - user.get("voice_seconds", 0))


def add_voice_seconds(db, user_id, seconds):
    user = get(db, user_id)
    if user:
        user["voice_seconds"] = user.get("voice_seconds", 0) + seconds
        Store.put(db, "users", user, ws=SYSTEM)


def view(user):
    """Account details safe to send to the browser."""
    left = voice_left(user)
    return {
        "email": user["email"],
        "role": user["role"],
        "trial_ends": user.get("trial_ends"),
        "voice_seconds_left": None if left is None else round(left),
    }
