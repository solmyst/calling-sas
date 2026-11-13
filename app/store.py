"""SQLite storage. Every record belongs to one workspace; transactions serialize call transitions and request deduplication.

The active workspace comes from a context variable set per request by the auth
middleware, so every read and write below is scoped without callers passing it.
"""

import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

MAIN = "main"  # the main account's workspace; holds all pre-account data
SYSTEM = "_system"  # account records, never a user's workspace
workspace = ContextVar("workspace", default=MAIN)


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction() as db:
            columns = [r[1] for r in db.execute("PRAGMA table_info(records)")]
            if columns and "ws" not in columns:
                db.execute("ALTER TABLE records RENAME TO records_v1")
            db.execute(
                "CREATE TABLE IF NOT EXISTS records (ws TEXT NOT NULL, kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(ws,kind,id))"
            )
            if columns and "ws" not in columns:
                # Single-workspace data from before accounts belongs to the main account.
                db.execute(
                    "INSERT INTO records SELECT ?, kind, id, body FROM records_v1 ORDER BY rowid",
                    (MAIN,),
                )
                db.execute("DROP TABLE records_v1")
            db.execute(
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
        Path(self.path).chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def all(db, kind, ws=None):
        return [
            json.loads(r[0])
            for r in db.execute(
                "SELECT body FROM records WHERE ws=? AND kind=? ORDER BY rowid DESC",
                (ws or workspace.get(), kind),
            )
        ]

    @staticmethod
    def get(db, kind, id, ws=None):
        r = db.execute(
            "SELECT body FROM records WHERE ws=? AND kind=? AND id=?",
            (ws or workspace.get(), kind, id),
        ).fetchone()
        return json.loads(r[0]) if r else None

    @staticmethod
    def put(db, kind, value, ws=None):
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(ws,kind,id) DO UPDATE SET body=excluded.body",
            (ws or workspace.get(), kind, value["id"], json.dumps(value)),
        )

    @staticmethod
    def workspaces(db):
        """Every user workspace that holds records, always including MAIN."""
        rows = db.execute("SELECT DISTINCT ws FROM records WHERE ws != ?", (SYSTEM,))
        return sorted({MAIN} | {r[0] for r in rows})

    @staticmethod
    def cached(db, id):
        r = db.execute(
            "SELECT body FROM requests WHERE id=?", (workspace.get() + "|" + id,)
        ).fetchone()
        return json.loads(r[0]) if r else None

    @staticmethod
    def cache(db, id, value):
        db.execute(
            "INSERT INTO requests VALUES (?,?)",
            (workspace.get() + "|" + id, json.dumps(value)),
        )
