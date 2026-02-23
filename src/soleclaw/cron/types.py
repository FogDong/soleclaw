from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class CronJob:
    id: str
    name: str
    message: str
    schedule_kind: str  # "at" | "every" | "cron"
    schedule_value: str  # ISO datetime | seconds | cron expr
    channel: str
    chat_id: str
    thread_id: str = ""
    message_kind: str = ""  # "agent" | "static"; empty defaults to agent
    enabled: bool = True
    schedule_tz: str = "UTC"
    delete_after_run: bool = False
    created_at: str = ""
    last_run_at: str = ""
    next_run_at: str = ""
    running_at: str = ""
    last_run_status: str = ""  # "ok" | "error"
    last_error: str = ""
    last_duration_ms: int = 0
    consecutive_errors: int = 0
    schedule_error_count: int = 0

    MAX_SCHEDULE_ERRORS = 3

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("MAX_SCHEDULE_ERRORS", None)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CronJob:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]

    def summary(self) -> dict[str, str]:
        s: dict[str, str] = {
            "id": self.id,
            "name": self.name,
            "schedule": f"{self.schedule_kind}:{self.schedule_value}",
            "tz": self.schedule_tz,
            "message_kind": self.message_kind or "agent",
            "enabled": str(self.enabled),
            "next_run_at": self.next_run_at,
            "last_run_at": self.last_run_at,
        }
        if self.last_run_status:
            s["last_status"] = self.last_run_status
        if self.consecutive_errors > 0:
            s["consecutive_errors"] = str(self.consecutive_errors)
        return s
