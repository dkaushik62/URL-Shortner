from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from orchestrator.domain import utcnow


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    """Persistent run snapshots, append-only events and operation receipts.

    SQLite is an explicit test backend. The application uses PostgreSQL.
    A single-process lock provides atomic snapshot updates for this local prototype.
    """

    def __init__(self, url: str):
        self.lock = threading.RLock()
        self.sqlite = url.startswith("sqlite:")
        if self.sqlite:
            path = url.removeprefix("sqlite:")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.row_factory = sqlite3.Row
        else:
            from psycopg_pool import ConnectionPool
            self.pool = ConnectionPool(url, min_size=1, max_size=4, open=True)
        with self.connection() as db:
            for sql in [
                "CREATE TABLE IF NOT EXISTS engineering_runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS engineering_events (run_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY(run_id,seq))",
                "CREATE TABLE IF NOT EXISTS engineering_receipts (run_id TEXT NOT NULL, operation TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(run_id,operation))",
            ]:
                db.execute(sql)

    @contextmanager
    def connection(self):
        if self.sqlite:
            with self.db:
                yield self.db
        else:
            with self.pool.connection() as db:
                yield db

    def sql(self, statement: str) -> str:
        return statement if self.sqlite else statement.replace("?", "%s")

    def get(self, run_id: str) -> dict:
        with self.lock, self.connection() as db:
            row = db.execute(self.sql("SELECT body FROM engineering_runs WHERE id=?"), (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            return json.loads(row[0])

    def save(self, run: dict):
        with self.lock, self.connection() as db:
            db.execute(self.sql("INSERT INTO engineering_runs(id,body) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body"), (run["id"], canonical(run)))

    def update(self, run_id: str, mutate):
        with self.lock:
            run = self.get(run_id)
            result = mutate(run)
            self.save(run)
            return result if result is not None else run

    def list(self) -> list[dict]:
        with self.lock, self.connection() as db:
            rows = db.execute("SELECT body FROM engineering_runs").fetchall()
            return sorted([json.loads(row[0]) for row in rows], key=lambda r: r["created_at"], reverse=True)

    def event(self, run_id: str, kind: str, **data) -> dict:
        with self.lock, self.connection() as db:
            row = db.execute(self.sql("SELECT seq,hash FROM engineering_events WHERE run_id=? ORDER BY seq DESC LIMIT 1"), (run_id,)).fetchone()
            seq, previous = (row[0] + 1, row[1]) if row else (1, "0" * 64)
            event = {"run_id": run_id, "seq": seq, "at": utcnow(), "kind": kind,
                     "previous_hash": previous, "data": data}
            digest = hashlib.sha256(canonical(event).encode()).hexdigest()
            db.execute(self.sql("INSERT INTO engineering_events(run_id,seq,body,hash) VALUES(?,?,?,?)"), (run_id, seq, canonical(event), digest))
            return {**event, "hash": digest}

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        with self.lock, self.connection() as db:
            rows = db.execute(self.sql("SELECT body,hash FROM engineering_events WHERE run_id=? AND seq>? ORDER BY seq"), (run_id, after)).fetchall()
            return [{**json.loads(row[0]), "hash": row[1]} for row in rows]

    def receipt(self, run_id: str, operation: str):
        with self.lock, self.connection() as db:
            row = db.execute(self.sql("SELECT body FROM engineering_receipts WHERE run_id=? AND operation=?"), (run_id, operation)).fetchone()
            return json.loads(row[0]) if row else None

    def record_receipt(self, run_id: str, operation: str, body: dict):
        with self.lock, self.connection() as db:
            db.execute(self.sql("INSERT INTO engineering_receipts(run_id,operation,body) VALUES(?,?,?) ON CONFLICT(run_id,operation) DO NOTHING"), (run_id, operation, canonical(body)))

    def verify_chain(self, run_id: str) -> bool:
        previous = "0" * 64
        try:
            for expected_seq, event in enumerate(self.events(run_id), 1):
                digest = event.pop("hash")
                if event.get("seq") != expected_seq or event.get("previous_hash") != previous or hashlib.sha256(canonical(event).encode()).hexdigest() != digest:
                    return False
                previous = digest
        except (KeyError, ValueError, TypeError):
            return False
        return True

    def close(self):
        self.db.close() if self.sqlite else self.pool.close()
