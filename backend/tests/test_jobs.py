"""Jobs and the analysis pipeline.

A job must show what it is doing, must not pretend a step ran, and must keep
its state per company.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import Database
from app.services.job_runner import JobRunner
from tests.conftest import register_and_verify


def make_runner(database: Database) -> JobRunner:
    return JobRunner(database)


def test_a_job_runs_its_steps_and_records_the_state(database: Database) -> None:
    runner = make_runner(database)
    job = runner.enqueue(
        "tender_analysis",
        "company-1",
        tender_id="tender-1",
        steps=[
            {"key": "first", "label": "First step"},
            {"key": "second", "label": "Second step"},
        ],
    )
    assert job["status"] == "queued"
    assert len(job["steps"]) == 2

    done = runner.run(job["id"])
    assert done["status"] == "done"
    assert done["steps"][0]["status"] == "skipped"
    assert "not available yet" in done["steps"][0]["error"]
    assert done["steps"][1]["status"] == "skipped"


def test_a_handled_step_records_its_summary(database: Database) -> None:
    runner = make_runner(database)
    runner.register("work", lambda context: {"read": 3})
    job = runner.enqueue(
        "tender_analysis", "company-1", tender_id="tender-1", steps=[{"key": "work"}]
    )
    done = runner.run(job["id"])
    assert done["status"] == "done"
    assert done["steps"][0]["status"] == "done"
    assert done["steps"][0]["summary"] == {"read": 3}


def test_a_failing_step_fails_the_job_honestly(database: Database) -> None:
    def boom(context):
        raise RuntimeError("the source could not be read")

    runner = make_runner(database)
    runner.register("work", boom)
    job = runner.enqueue(
        "tender_analysis", "company-1", tender_id="tender-1", steps=[{"key": "work"}]
    )
    failed = runner.run(job["id"])
    assert failed["status"] == "failed"
    assert failed["steps"][0]["status"] == "failed"
    assert "could not be read" in failed["steps"][0]["error"]
    assert "could not be read" in (failed["error"] or "")


def test_a_job_is_scoped_to_its_company(database: Database) -> None:
    runner = make_runner(database)
    job = runner.enqueue("tender_analysis", "company-1", tender_id="tender-1")
    assert runner.jobs.find_for_company(job["id"], "company-1") is not None
    assert runner.jobs.find_for_company(job["id"], "company-2") is None


def test_the_analysis_endpoint_queues_a_job(
    client: TestClient, auth_headers: dict[str, str], tender: dict
) -> None:
    response = client.post(f"/api/analysis/tenders/{tender['id']}", headers=auth_headers)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "queued"
    assert job["tender_id"] == tender["id"]
    keys = [step["key"] for step in job["steps"]]
    assert keys == ["requirements", "recommendations", "verification", "legal_research"]

    latest = client.get(f"/api/analysis/tenders/{tender['id']}", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["id"] == job["id"]


def test_the_analysis_job_is_not_readable_by_another_company(
    client: TestClient, auth_headers: dict[str, str], tender: dict, fake_email
) -> None:
    job = client.post(f"/api/analysis/tenders/{tender['id']}", headers=auth_headers).json()

    other = register_and_verify(
        client,
        fake_email,
        email="job-owner@example.com",
        full_name="Other Owner",
        company_name="Other Infra Pvt Ltd",
    )
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    response = client.get(f"/api/analysis/jobs/{job['id']}", headers=other_headers)
    assert response.status_code == 404
