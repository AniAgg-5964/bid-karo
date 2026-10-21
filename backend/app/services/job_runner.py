"""Running jobs, and the agent pipeline that will run on them.

A job is a list of steps. Each step is handled by a registered handler; a step
with no handler is reported as "not available yet" rather than quietly passing.
The runner is deliberately simple: one job at a time, in this process, with the
state written to MongoDB so the user can see where it is.

The agent pipeline is registered here as steps, so the shape of the work is
visible before the agents exist:

``requirements``    read the tender document and propose cited requirements
``recommendations`` propose what the company should do, grounded in the
                    requirements that passed the gate
``verification``    check the proposals against the company's own records
``legal_research``  read official legal sources for the clauses that matter
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from app.core.database import Database, utcnow
from app.repositories.jobs import JobRepository

logger = logging.getLogger(__name__)

StepHandler = Callable[["JobContext"], dict]


class JobContext:
    """What a step handler is given."""

    def __init__(self, job: dict, step: dict) -> None:
        self.job = job
        self.step = step
        self.db: Database = job["_db"]  # type: ignore[assignment]
        self.company_id = job.get("company_id")
        self.tender_id = job.get("tender_id")
        self.document_id = job.get("document_id")
        self.payload = job.get("payload") or {}


class JobRunner:
    """Runs queued jobs, one at a time, in this process."""

    def __init__(self, db: Database, *, handlers: dict[str, StepHandler] | None = None) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self.handlers: dict[str, StepHandler] = dict(handlers or {})
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------ setup
    def register(self, key: str, handler: StepHandler) -> None:
        self.handlers[key] = handler

    def enqueue(
        self,
        kind: str,
        company_id: str,
        *,
        tender_id: str | None = None,
        document_id: str | None = None,
        payload: dict | None = None,
        steps: list[dict] | None = None,
    ) -> dict:
        """Create a queued job with its steps."""
        job = self.jobs.create(
            {
                "company_id": company_id,
                "kind": kind,
                "tender_id": tender_id,
                "document_id": document_id,
                "payload": payload or {},
                "steps": [
                    {
                        "key": step["key"],
                        "label": step.get("label") or step["key"],
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "error": None,
                        "summary": {},
                    }
                    for step in (steps or [])
                ],
            }
        )
        return job

    # ------------------------------------------------------------------- run
    def run(self, job_id: str) -> dict:
        """Run one job's steps in order."""
        job = self.jobs.collection.find_one({"_id": job_id})
        if not job:
            raise ValueError("Job not found.")
        job = {**job, "_db": self.db}
        self.jobs.set_status(job_id, "running")
        current = self.jobs.find_for_company(job_id, job.get("company_id"))
        steps = list((current or {}).get("steps") or [])

        for step in steps:
            key = step.get("key")
            handler = self.handlers.get(key)
            self.jobs.update_step(
                job_id, key, {"status": "running", "started_at": utcnow()}
            )
            if handler is None:
                self.jobs.update_step(
                    job_id,
                    key,
                    {
                        "status": "skipped",
                        "finished_at": utcnow(),
                        "error": "This step is not available yet.",
                        "summary": {},
                    },
                )
                continue
            try:
                summary = handler(JobContext(job, step)) or {}
            except Exception as exc:  # noqa: BLE001 - a failed step is reported
                logger.exception("Job step %s failed for job %s", key, job_id)
                self.jobs.update_step(
                    job_id,
                    key,
                    {
                        "status": "failed",
                        "finished_at": utcnow(),
                        "error": str(exc),
                        "summary": {},
                    },
                )
                self.jobs.set_status(job_id, "failed", error=str(exc))
                return self.jobs.find_for_company(job_id, job.get("company_id"))
            self.jobs.update_step(
                job_id,
                key,
                {
                    "status": "done",
                    "finished_at": utcnow(),
                    "error": None,
                    "summary": summary,
                },
            )

        self.jobs.set_status(job_id, "done")
        return self.jobs.find_for_company(job_id, job.get("company_id"))

    def run_next(self) -> dict | None:
        """Run the oldest queued job, if there is one."""
        queued = self.jobs.next_queued()
        if not queued:
            return None
        return self.run(queued["id"])

    # ---------------------------------------------------------------- worker
    def start_worker(self, *, interval_seconds: float = 2.0) -> None:
        """Run queued jobs in the background of this process."""
        if self._thread and self._thread.is_alive():
            return

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.run_next()
                except Exception:  # noqa: BLE001 - the worker must survive
                    logger.exception("The job worker hit an error")
                self._stop.wait(interval_seconds)

        self._thread = threading.Thread(target=loop, name="bidkaro-job-worker", daemon=True)
        self._thread.start()

    def stop_worker(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
