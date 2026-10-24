"""Small client for the service-only, atomic queue RPCs.

Named job_queue, not queue, to avoid shadowing Python's standard library queue.
"""


class Queue:
    def __init__(self, client):
        self.client = client

    def rpc(self, name, **params):
        return self.client.rpc(name, params).execute().data

    def enqueue(self, key, at, stages):
        return self.rpc("enqueue_pipeline", p_key=key, p_at=at.isoformat(), p_stages=stages)

    def claim(self, worker):
        rows = self.rpc("claim_job", p_worker=worker)
        return rows[0] if rows else None

    def heartbeat(self, job, worker):
        return self.rpc("heartbeat_job", p_id=job["id"], p_run=job["run_id"], p_worker=worker)

    def finish(self, job, worker, code, summary):
        return self.rpc("finish_job", p_id=job["id"], p_run=job["run_id"], p_worker=worker,
                        p_exit=code, p_summary=summary)

    def recover(self):
        return self.rpc("recover_jobs")

    def control(self, job_id, action):
        return self.rpc("control_job", p_id=job_id, p_action=action)
