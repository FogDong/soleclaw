---
name: cron
description: Schedule recurring or one-shot tasks that run automatically
always: true
---

# Cron

You have these tools for scheduling tasks:

- `cron_schedule` — Create a new scheduled task
- `cron_list` — List all scheduled tasks
- `cron_update` — Update an existing task
- `cron_delete` — Delete a task
- `cron_trigger` — Manually trigger a task to run immediately (does not affect its schedule)

**Schedule types:**
- `at` — One-shot at a specific time (ISO 8601, e.g. `2026-02-23T09:00:00+08:00`)
- `every` — Repeat at fixed interval in seconds (e.g. `3600` = every hour)
- `cron` — Cron expression (e.g. `0 9 * * *` = daily at 9 AM)

**Message kinds:**
- `agent` (default) — An isolated agent session runs your message and generates a response
- `static` — The message text is sent directly to the user without LLM processing

**Timezone:** Use `schedule_tz` for cron expressions (IANA format, e.g. `Asia/Shanghai`). Defaults to UTC.

**Delivery:** Results are delivered to the channel/chat where the job was created. For Telegram group topics, `thread_id` is auto-detected. Channel, chat_id, and thread_id can also be set explicitly.

**Reliability:** Failed jobs get exponential backoff (30s → 1m → 5m → 15m → 60m). Jobs stuck for >2h are auto-cleared.

**When to use:** User asks for reminders, daily summaries, periodic checks, scheduled reports, or any recurring task.

**Common operations:**
- Create a job: `cron_schedule(name=..., schedule_kind=..., schedule_value=..., message=...)`
- Pause a job: `cron_update(job_id=..., enabled=false)`
- Resume a job: `cron_update(job_id=..., enabled=true)`
- Change schedule: `cron_update(job_id=..., schedule_kind=..., schedule_value=...)`
- Change message: `cron_update(job_id=..., message=...)`
- Run now: `cron_trigger(job_id=...)`
- Delete: `cron_delete(job_id=...)`

**Example:** User says "remind me to exercise every day at 7pm" →
```
cron_schedule(name="exercise_reminder", message="Remind the user to exercise. Be encouraging.", schedule_kind="cron", schedule_value="0 19 * * *", schedule_tz="Asia/Shanghai")
```

**One-shot cleanup:** Use `delete_after_run=true` in `cron_schedule` for jobs that should be removed after execution.
