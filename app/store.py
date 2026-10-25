"""Single-workspace storage. Transactions serialize call transitions and request deduplication."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))"
            )
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
    def all(db, kind):
        return [
            json.loads(r[0])
            for r in db.execute(
                "SELECT body FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)
            )
        ]

    @staticmethod
    def get(db, kind, id):
        r = db.execute(
            "SELECT body FROM records WHERE kind=? AND id=?", (kind, id)
        ).fetchone()
        return json.loads(r[0]) if r else None

    @staticmethod
    def put(db, kind, value):
        db.execute(
            "INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body",
            (kind, value["id"], json.dumps(value)),
        )

    @staticmethod
    def cached(db, id):
        r = db.execute("SELECT body FROM requests WHERE id=?", (id,)).fetchone()
        return json.loads(r[0]) if r else None

    @staticmethod
    def cache(db, id, value):
        db.execute("INSERT INTO requests VALUES (?,?)", (id, json.dumps(value)))
