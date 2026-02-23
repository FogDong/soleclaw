from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import CronJob

log = logging.getLogger(__name__)


class CronStore:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._runs_dir = self._path.parent / "runs"
        self._cache: list[CronJob] | None = None
        self._mtime: float = 0.0

    def _file_mtime(self) -> float:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def load(self) -> list[CronJob]:
        mt = self._file_mtime()
        if self._cache is not None and mt == self._mtime:
            return list(self._cache)
        if not self._path.exists():
            self._cache = []
            self._mtime = 0.0
            return []
        try:
            data = json.loads(self._path.read_text())
            self._cache = [CronJob.from_dict(j) for j in data.get("jobs", [])]
            self._mtime = mt
            return list(self._cache)
        except Exception:
            log.exception("Failed to load cron store from %s", self._path)
            return []

    def save(self, jobs: list[CronJob]) -> None:
        data = {"version": 1, "jobs": [j.to_dict() for j in jobs]}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp.rename(self._path)
        self._cache = list(jobs)
        self._mtime = self._file_mtime()

    def add(self, job: CronJob) -> None:
        jobs = self.load()
        jobs.append(job)
        self.save(jobs)

    def remove(self, job_id: str) -> bool:
        jobs = self.load()
        before = len(jobs)
        jobs = [j for j in jobs if j.id != job_id]
        if len(jobs) == before:
            return False
        self.save(jobs)
        return True

    def update(self, job_id: str, **kwargs: Any) -> bool:
        jobs = self.load()
        for j in jobs:
            if j.id == job_id:
                for k, v in kwargs.items():
                    if hasattr(j, k):
                        setattr(j, k, v)
                self.save(jobs)
                return True
        return False

    def get(self, job_id: str) -> CronJob | None:
        for j in self.load():
            if j.id == job_id:
                return j
        return None

    def log_run(self, job_id: str, status: str, duration_ms: int, error: str = "") -> None:
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        }
        path = self._runs_dir / f"{job_id}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_runs(self, job_id: str, limit: int = 20) -> list[dict[str, Any]]:
        path = self._runs_dir / f"{job_id}.jsonl"
        if not path.exists():
            return []
        lines = path.read_text().strip().splitlines()
        entries = []
        for line in reversed(lines):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(entries) >= limit:
                break
        return entries
