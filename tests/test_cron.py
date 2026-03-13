import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from soleclaw.cron.types import CronJob
from soleclaw.cron.store import CronStore
from soleclaw.cron.service import compute_next_run, is_due, _backoff_delay, BACKOFF_SCHEDULE


@pytest.fixture
def store(tmp_path):
    return CronStore(tmp_path / "cron" / "jobs.json")


def _make_job(**overrides):
    defaults = dict(
        id="test123",
        name="test job",
        message="do something",
        schedule_kind="every",
        schedule_value="3600",
        channel="telegram",
        chat_id="999",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(overrides)
    return CronJob(**defaults)


# --- Store tests ---

def test_store_add_load(store):
    job = _make_job()
    store.add(job)
    jobs = store.load()
    assert len(jobs) == 1
    assert jobs[0].id == "test123"
    assert jobs[0].name == "test job"


def test_store_remove(store):
    store.add(_make_job(id="a"))
    store.add(_make_job(id="b"))
    assert store.remove("a")
    assert len(store.load()) == 1
    assert not store.remove("nonexistent")


def test_store_update(store):
    store.add(_make_job())
    assert store.update("test123", enabled=False)
    job = store.get("test123")
    assert job.enabled is False


def test_store_cache(store):
    store.add(_make_job())
    jobs1 = store.load()
    jobs2 = store.load()
    assert len(jobs1) == 1
    assert len(jobs2) == 1


def test_store_log_run(store):
    store.log_run("test123", "ok", 1500)
    store.log_run("test123", "error", 200, "timeout")
    runs = store.get_runs("test123")
    assert len(runs) == 2
    assert runs[0]["status"] == "error"  # reversed (newest first)
    assert runs[1]["status"] == "ok"


def test_store_get_runs_empty(store):
    assert store.get_runs("nonexistent") == []


def test_store_get_runs_limit(store):
    for i in range(30):
        store.log_run("x", "ok", i * 10)
    runs = store.get_runs("x", limit=5)
    assert len(runs) == 5


# --- compute_next_run tests ---

def test_compute_next_run_every():
    job = _make_job(schedule_kind="every", schedule_value="60")
    nr = compute_next_run(job)
    assert nr

    now = datetime.now(timezone.utc)
    job.last_run_at = now.isoformat()
    nr = compute_next_run(job, after=now)
    expected = now + timedelta(seconds=60)
    assert abs(datetime.fromisoformat(nr).timestamp() - expected.timestamp()) < 1


def test_compute_next_run_cron():
    job = _make_job(schedule_kind="cron", schedule_value="0 9 * * *")
    nr = compute_next_run(job)
    assert nr
    dt = datetime.fromisoformat(nr)
    assert dt.minute == 0


def test_compute_next_run_cron_with_tz():
    job = _make_job(schedule_kind="cron", schedule_value="0 9 * * *", schedule_tz="Asia/Shanghai")
    nr = compute_next_run(job)
    assert nr
    dt = datetime.fromisoformat(nr)
    assert dt.tzinfo is not None


def test_compute_next_run_at_future():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    job = _make_job(schedule_kind="at", schedule_value=future)
    nr = compute_next_run(job)
    assert nr == future


def test_compute_next_run_at_past():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    job = _make_job(schedule_kind="at", schedule_value=past)
    nr = compute_next_run(job)
    assert nr == ""


# --- is_due tests ---

def test_is_due():
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    job = _make_job(next_run_at=past)
    assert is_due(job)


def test_is_not_due_future():
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    job = _make_job(next_run_at=future)
    assert not is_due(job)


def test_is_not_due_disabled():
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    job = _make_job(next_run_at=past, enabled=False)
    assert not is_due(job)


def test_is_not_due_running():
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    job = _make_job(next_run_at=past, running_at=datetime.now(timezone.utc).isoformat())
    assert not is_due(job)


# --- backoff tests ---

def test_backoff_delay():
    assert _backoff_delay(1) == 30
    assert _backoff_delay(2) == 60
    assert _backoff_delay(3) == 300
    assert _backoff_delay(4) == 900
    assert _backoff_delay(5) == 3600
    assert _backoff_delay(100) == 3600  # capped


# --- types tests ---

def test_cronjob_new_fields():
    job = _make_job()
    assert job.running_at == ""
    assert job.last_run_status == ""
    assert job.last_error == ""
    assert job.last_duration_ms == 0
    assert job.consecutive_errors == 0
    assert job.delete_after_run is False
    assert job.schedule_error_count == 0


def test_cronjob_summary_with_errors():
    job = _make_job(last_run_status="error", consecutive_errors=3)
    s = job.summary()
    assert s["last_run_status"] == "error"
    assert s["consecutive_errors"] == 3


def test_cronjob_to_dict_roundtrip():
    job = _make_job(delete_after_run=True, last_run_status="ok", consecutive_errors=0)
    d = job.to_dict()
    assert "delete_after_run" in d
    job2 = CronJob.from_dict(d)
    assert job2.delete_after_run is True
    assert job2.last_run_status == "ok"


# --- sdk_tools cron tests ---

def _parse(result):
    return json.loads(result["content"][0]["text"])


@pytest.mark.asyncio
async def test_cron_schedule_add(tmp_path):
    from soleclaw.tools.sdk_tools import cron_schedule, cron_list, init_tools

    store = CronStore(tmp_path / "jobs.json")
    init_tools(workspace=tmp_path, cron_store=store)

    result = _parse(await cron_schedule.handler({
        "name": "test_reminder", "message": "remind user",
        "schedule_kind": "every", "schedule_value": "3600",
    }))
    assert result["success"]
    assert result["job_id"]

    listing = _parse(await cron_list.handler({}))
    assert len(listing["jobs"]) == 1
    assert listing["jobs"][0]["name"] == "test_reminder"


@pytest.mark.asyncio
async def test_cron_schedule_with_tz(tmp_path):
    from soleclaw.tools.sdk_tools import cron_schedule, init_tools

    store = CronStore(tmp_path / "jobs.json")
    init_tools(workspace=tmp_path, cron_store=store)

    result = _parse(await cron_schedule.handler({
        "name": "morning", "message": "good morning",
        "schedule_kind": "cron", "schedule_value": "0 9 * * *",
        "schedule_tz": "Asia/Shanghai",
    }))
    assert result["success"]
    job = store.get(result["job_id"])
    assert job.schedule_tz == "Asia/Shanghai"


@pytest.mark.asyncio
async def test_cron_delete(tmp_path):
    from soleclaw.tools.sdk_tools import cron_schedule, cron_delete, cron_list, init_tools

    store = CronStore(tmp_path / "jobs.json")
    init_tools(workspace=tmp_path, cron_store=store)

    add_result = _parse(await cron_schedule.handler({
        "name": "tmp", "message": "x",
        "schedule_kind": "every", "schedule_value": "60",
    }))
    job_id = add_result["job_id"]

    del_result = _parse(await cron_delete.handler({"job_id": job_id}))
    assert del_result["success"]

    listing = _parse(await cron_list.handler({}))
    assert len(listing["jobs"]) == 0
