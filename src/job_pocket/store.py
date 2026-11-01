from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .model import now


class Store:
    """Every card and detail is a committed transaction; SQLite is the source of truth."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.commit()

    def close(self):
        self.db.close()

    def rows(self) -> list[dict]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM jobs ORDER BY rowid")]

    def count(self) -> int:
        return self.db.execute("SELECT count(*) FROM jobs").fetchone()[0]

    def add(self, record: dict, limit: int) -> bool:
        if self.count() >= min(limit, 200):
            return False
        with self.db:
            result = self.db.execute("INSERT OR IGNORE INTO jobs VALUES (?, ?)",
                                     (record["job_id"], json.dumps(record, ensure_ascii=False)))
        return result.rowcount == 1

    def update(self, job_id: str, **values):
        row = self.db.execute("SELECT payload FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        record = json.loads(row[0])
        record.update(values, updated_at=now())
        with self.db:
            self.db.execute("UPDATE jobs SET payload=? WHERE job_id=?",
                            (json.dumps(record, ensure_ascii=False), job_id))

    def pending(self) -> list[dict]:
        return [r for r in self.rows() if r["jd_status"] == "pending"]

    def set_meta(self, key: str, value: str):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
