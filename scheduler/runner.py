"""Fixed argv, isolated environments, bounded output and fenced completion."""

from collections import deque
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import psutil
from shared.logbook import log_event, sanitize

ROOT = Path(__file__).resolve().parents[1]


def command_for(job, modules, root=ROOT):
    spec = modules.get(job["module"])
    if not spec or job["kind"] not in spec["args_by_kind"]:
        raise ValueError("Module or job kind is not configured")
    if job.get("params"):
        raise ValueError("This job kind accepts no extra parameters")
    folder = (root / spec["directory"]).resolve()
    if not folder.is_relative_to(root.resolve()):
        raise ValueError("Module must be inside the repository")
    python = folder / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    script = folder / "main.py"
    if not python.is_file() or not script.is_file():
        raise ValueError(f"Environment or entry point missing for {job['module']}")
    return [str(python), str(script), *spec["args_by_kind"][job["kind"]]], int(spec["timeout_seconds"])


def stop_tree(process):
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=5)
    except psutil.NoSuchProcess:
        pass
    process.wait(timeout=10)


def execute(job, worker, queue, modules, root=ROOT, heartbeat_seconds=20):
    process = None
    try:
        argv, timeout = command_for(job, modules, root)
        if not queue.heartbeat(job, worker):
            return False
        env = dict(os.environ, RUN_ID=job["run_id"], JOB_ID=str(job["id"]), PYTHONUNBUFFERED="1")
        process = subprocess.Popen(argv, cwd=root, env=env, shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        tail = deque(maxlen=20)

        def drain():
            # Fixed-size reads also bound a child that writes one endless line.
            while chunk := process.stdout.read(1024):
                tail.append(chunk)

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        log_event(job["run_id"], "scheduler", "claim_job", "started", output_summary=f"Job {job['id']}: {job['module']}/{job['kind']}")
        start = last_beat = time.monotonic()
        while process.poll() is None:
            if time.monotonic() - start > timeout:
                stop_tree(process)
                raise TimeoutError("Module exceeded configured runtime")
            if time.monotonic() - last_beat >= heartbeat_seconds:
                # Fail closed on DB outage: stop this process tree before lease expiry.
                if not queue.heartbeat(job, worker):
                    stop_tree(process)
                    return False
                last_beat = time.monotonic()
            time.sleep(0.2)
        reader.join(timeout=3)
        summary = str(sanitize("".join(tail)))[-2000:]
        summary = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REDACTED]", summary)
        saved = queue.finish(job, worker, process.returncode, summary or f"Exit code {process.returncode}")
        log_event(job["run_id"], "scheduler", "finish_job", "success" if process.returncode == 0 else "failed",
                  output_summary=f"Job {job['id']}: exit {process.returncode}; result saved={saved}")
        return saved
    except BaseException as exc:
        if process is not None and process.poll() is None:
            stop_tree(process)
        # No raw child exception/command/environment is persisted.
        try:
            queue.finish(job, worker, 1, f"Runner stopped: {type(exc).__name__}; check environment, database and module logbook")
        except Exception:
            pass  # Recovery handles the expired lease after connectivity returns.
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return False
    finally:
        if process is not None and process.stdout:
            process.stdout.close()
