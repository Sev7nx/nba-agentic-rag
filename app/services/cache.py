import hashlib
import json
import sqlite3
import time
from pathlib import Path


class Cache:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache ("
                "key TEXT PRIMARY KEY, "
                "value TEXT NOT NULL, "
                "expires_at REAL NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def make_key(self, question: str, profile: dict | None = None) -> str:
        raw = (
            f"{question.strip().lower()}|"
            f"{json.dumps(profile or {}, sort_keys=True, ensure_ascii=False)}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at <= time.time():
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int = 86400) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, time.time() + ttl_seconds),
            )