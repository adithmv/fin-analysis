import sys
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from scheduler import runner


def test_command_rejects_unconfigured_input_and_path_escape(tmp_path):
    job = {"module": "test", "kind": "ok"}
    with pytest.raises(ValueError):
        runner.command_for(job, {})
    spec = {"test": {"directory": "../outside", "args_by_kind": {"ok": []}, "timeout_seconds": 2}}
    with pytest.raises(ValueError, match="inside"):
        runner.command_for(job, spec, tmp_path)
    job["params"] = {"command": "arbitrary"}
    with pytest.raises(ValueError, match="parameters"):
        runner.command_for(job, spec, tmp_path)


def run_child(monkeypatch, code, timeout=10, heartbeat=True):
    job = {"id": 1, "module": "fixture", "kind": "test", "run_id": str(uuid4())}
    queue = MagicMock()
    queue.heartbeat.return_value = heartbeat
    monkeypatch.setattr(runner, "command_for", lambda *a: ([sys.executable, "-c", code], timeout))
    monkeypatch.setattr(runner, "log_event", lambda *a, **kw: True)
    runner.execute(job, "test-worker", queue, {}, heartbeat_seconds=0.05)
    return queue, job


def test_child_receives_run_id_and_redacts_output(monkeypatch):
    monkeypatch.setenv("TEST_SECRET", "never-persist-me")
    queue, job = run_child(monkeypatch, "import os; print(os.environ['RUN_ID']); print(os.environ['TEST_SECRET'])")
    args = queue.finish.call_args.args
    assert args[2] == 0 and job["run_id"] in args[3]
    assert "never-persist-me" not in args[3]


def test_nonzero_exit_is_preserved(monkeypatch):
    queue, _ = run_child(monkeypatch, "raise SystemExit(7)")
    assert queue.finish.call_args.args[2] == 7


def test_timeout_kills_child(monkeypatch):
    queue, _ = run_child(monkeypatch, "import time; time.sleep(30)", timeout=0)
    assert queue.finish.call_args.args[2] == 1
    assert "TimeoutError" in queue.finish.call_args.args[3]


def test_cancelled_job_does_not_launch(monkeypatch):
    queue, _ = run_child(monkeypatch, "raise RuntimeError('must not execute')", heartbeat=False)
    queue.finish.assert_not_called()
