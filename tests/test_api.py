"""
API integration tests for the FortiGate Upgrade Review backend.

Requires the backend to be running:
    uvicorn backend.main:app --reload --port 8000

Run with:
    python -m pytest tests/test_api.py -v
    python -m pytest tests/test_api.py -v --tb=short   # less noise on failure
"""

import time
import pytest
import requests

BASE = "http://localhost:8000/api"


# ── helpers ───────────────────────────────────────────────────────────────────

def _wait_for_job(job_id: str, timeout: int = 60) -> dict:
    """Poll GET /api/jobs/{id} until the job leaves the running/pending state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{BASE}/jobs/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] not in ("pending", "running"):
            return data
        time.sleep(1)
    pytest.fail(f"Job {job_id} did not complete within {timeout}s")


# ── connectivity ──────────────────────────────────────────────────────────────

class TestConnectivity:
    def test_docs_reachable(self):
        """FastAPI /docs page should return 200."""
        r = requests.get("http://localhost:8000/docs")
        assert r.status_code == 200

    def test_openapi_json(self):
        """OpenAPI schema should be valid JSON with expected title."""
        r = requests.get("http://localhost:8000/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "paths" in data
        assert "/api/jobs" in data["paths"]


# ── GET /api/jobs ─────────────────────────────────────────────────────────────

class TestListJobs:
    def test_returns_list(self):
        r = requests.get(f"{BASE}/jobs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_response_shape(self):
        """Each job object must have the required fields."""
        r = requests.get(f"{BASE}/jobs")
        jobs = r.json()
        if not jobs:
            pytest.skip("No jobs in DB — run a job first or seed data")
        job = jobs[0]
        for field in ("id", "from_version", "to_version", "status", "created_at"):
            assert field in job, f"Missing field: {field}"


# ── POST /api/jobs ────────────────────────────────────────────────────────────

class TestCreateJob:
    created_id: str | None = None

    def test_create_valid_job(self):
        payload = {"from_version": "7.2.0", "to_version": "7.2.1"}
        r = requests.post(f"{BASE}/jobs", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["from_version"] == "7.2.0"
        assert data["to_version"] == "7.2.1"
        assert data["status"] in ("pending", "running")
        assert "id" in data
        TestCreateJob.created_id = data["id"]

    def test_invalid_from_version(self):
        r = requests.post(f"{BASE}/jobs", json={"from_version": "bad", "to_version": "7.2.1"})
        assert r.status_code == 422

    def test_invalid_to_version(self):
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.0", "to_version": "notaversion"})
        assert r.status_code == 422

    def test_from_version_not_less_than_to_version(self):
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.1", "to_version": "7.2.0"})
        assert r.status_code == 422

    def test_equal_versions_rejected(self):
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.1", "to_version": "7.2.1"})
        assert r.status_code == 422

    def test_missing_body_rejected(self):
        r = requests.post(f"{BASE}/jobs", json={})
        assert r.status_code == 422


# ── GET /api/jobs/{id} ────────────────────────────────────────────────────────

class TestGetJob:
    def test_get_existing_job(self):
        # Create one to fetch
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        assert r.status_code == 201
        job_id = r.json()["id"]

        r = requests.get(f"{BASE}/jobs/{job_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == job_id
        assert data["from_version"] == "7.2.0"
        assert data["to_version"] == "7.2.1"

    def test_get_nonexistent_job(self):
        r = requests.get(f"{BASE}/jobs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_detail_response_has_extra_fields(self):
        """GET /jobs/{id} returns detail-level fields not present in list."""
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        job_id = r.json()["id"]
        r = requests.get(f"{BASE}/jobs/{job_id}")
        data = r.json()
        # These keys exist on detail (may be null until completed)
        assert "versions" in data
        assert "all_data" in data
        assert "special_notices" in data


# ── DELETE /api/jobs/{id} ─────────────────────────────────────────────────────

class TestDeleteJob:
    def test_delete_existing_job(self):
        # Create a job to delete
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        assert r.status_code == 201
        job_id = r.json()["id"]

        r = requests.delete(f"{BASE}/jobs/{job_id}")
        assert r.status_code == 204

        # Confirm it's gone
        r = requests.get(f"{BASE}/jobs/{job_id}")
        assert r.status_code == 404

    def test_delete_nonexistent_job(self):
        r = requests.delete(f"{BASE}/jobs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_delete_removes_from_list(self):
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        job_id = r.json()["id"]
        requests.delete(f"{BASE}/jobs/{job_id}")

        ids = [j["id"] for j in requests.get(f"{BASE}/jobs").json()]
        assert job_id not in ids


# ── POST /api/jobs/upload ─────────────────────────────────────────────────────

class TestUploadPdfs:
    def test_upload_no_files_rejected(self):
        r = requests.post(f"{BASE}/jobs/upload")
        assert r.status_code in (400, 422)

    def test_upload_non_pdf_rejected(self):
        files = [("files", ("notes.txt", b"hello", "text/plain"))]
        r = requests.post(f"{BASE}/jobs/upload", files=files)
        assert r.status_code == 422

    def test_upload_pdf_without_version_in_name_rejected(self):
        """PDF whose filename has no version string should be rejected."""
        fake_pdf = b"%PDF-1.4 1 0 obj<</Type/Catalog>>endobj"
        files = [("files", ("release-notes.pdf", fake_pdf, "application/pdf"))]
        r = requests.post(f"{BASE}/jobs/upload", files=files)
        assert r.status_code == 422

    def test_upload_valid_pdf_filename_accepted(self):
        """
        A PDF with a parseable version in its name should create a job.
        The content is a minimal valid-looking PDF — parsing will fail, but
        the upload/job creation itself should succeed (status 201).
        Cleanup: delete the created job afterwards.
        """
        fake_pdf = b"%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n%%EOF"
        files = [("files", ("fortios-v7.4.11-release-notes.pdf", fake_pdf, "application/pdf"))]
        r = requests.post(f"{BASE}/jobs/upload", files=files)
        assert r.status_code == 201
        data = r.json()
        assert data["source"] == "pdf"
        assert data["to_version"] == "7.4.11"

        # Cleanup
        requests.delete(f"{BASE}/jobs/{data['id']}")


# ── job lifecycle (slow, optional) ───────────────────────────────────────────

class TestJobLifecycle:
    """
    These tests wait for a job to finish and inspect the result.
    Mark with -m slow or skip in CI if scraping is unavailable.
    """

    @pytest.mark.slow
    def test_completed_job_has_data(self):
        """
        Creates a real scrape job, waits for completion, and asserts
        the result contains parseable data.
        """
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.10", "to_version": "7.2.11"})
        assert r.status_code == 201
        job_id = r.json()["id"]

        data = _wait_for_job(job_id, timeout=120)

        assert data["status"] == "completed", f"Job failed: {data.get('error_message')}"
        assert isinstance(data.get("versions"), list)
        assert len(data["versions"]) > 0
        assert isinstance(data.get("all_data"), dict)

        # Cleanup
        requests.delete(f"{BASE}/jobs/{job_id}")

    @pytest.mark.slow
    def test_completed_job_log_is_populated(self):
        r = requests.post(f"{BASE}/jobs", json={"from_version": "7.2.10", "to_version": "7.2.11"})
        job_id = r.json()["id"]
        data = _wait_for_job(job_id, timeout=120)
        assert data.get("log"), "Log should not be empty after completion"
        requests.delete(f"{BASE}/jobs/{job_id}")
