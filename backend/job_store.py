"""Bounded, transactional single-host queue alongside existing file checkpoints.

SQLite is stdlib: no duplicate Redis/database service is introduced. The worker
also holds an OS lock for its lifetime; restart recovery runs only under that lock.
"""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager


class QueueFull(Exception): pass
class IdempotencyConflict(Exception): pass


class JobStore:
    def __init__(self, directory, capacity=4):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "jobs.sqlite3"
        self.capacity = capacity
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, request_key TEXT UNIQUE, payload TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL, updated REAL NOT NULL, result TEXT, error TEXT)""")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def submit(self, payload, request_key=None):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        # Without an explicit key, each requested lesson is a distinct job.
        request_key = request_key or uuid.uuid4().hex
        if len(request_key) > 128:
            raise ValueError("Idempotency key exceeds 128 characters")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT * FROM jobs WHERE request_key=?", (request_key,)).fetchone()
            if old:
                if old["payload"] != body:
                    raise IdempotencyConflict()
                return dict(old)
            active = conn.execute("SELECT count(*) FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]
            if active >= self.capacity:
                raise QueueFull()
            job_id, now = "run_" + uuid.uuid4().hex[:24], time.time()
            conn.execute("INSERT INTO jobs (id,request_key,payload,status,created,updated) VALUES (?,?,?,'QUEUED',?,?)",
                         (job_id, request_key, body, now, now))
            return dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def get(self, job_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def claim(self):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM jobs WHERE status='RUNNING'").fetchone():
                return None
            row = conn.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            conn.execute("UPDATE jobs SET status='RUNNING',attempts=attempts+1,updated=? WHERE id=?", (time.time(), row["id"]))
            return dict(conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def finish(self, job_id, result=None, error=None):
        with self.connect() as conn:
            conn.execute("UPDATE jobs SET status=?,result=?,error=?,updated=? WHERE id=? AND status='RUNNING'",
                         ("FAILED" if error else "COMPLETED", json.dumps(result) if result else None, error, time.time(), job_id))

    def recover(self, max_attempts):
        """Call only after obtaining the exclusive worker OS lock."""
        with self.connect() as conn:
            conn.execute("UPDATE jobs SET status=CASE WHEN attempts<? THEN 'QUEUED' ELSE 'FAILED' END, "
                         "error='worker_interrupted',updated=? WHERE status='RUNNING'", (max_attempts, time.time()))

    def retry(self, job_id, max_attempts):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row["status"] != "FAILED" or row["attempts"] >= max_attempts:
                return False
            active = conn.execute("SELECT count(*) FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]
            if active >= self.capacity:
                raise QueueFull()
            conn.execute("UPDATE jobs SET status='QUEUED',error=NULL,updated=? WHERE id=?", (time.time(), job_id))
            return True

    def backup(self, destination):
        with self.connect() as conn, sqlite3.connect(destination) as target:
            conn.backup(target)
