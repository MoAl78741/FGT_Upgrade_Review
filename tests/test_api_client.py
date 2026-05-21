"""
FastAPI TestClient tests — no live server or network required.

Uses the `client` fixture from conftest.py which injects an in-memory
SQLite database, so these tests run in isolation from the real DB.

Run:
    python -m pytest tests/test_api_client.py -v
"""

import pytest


# ── GET /api/jobs ─────────────────────────────────────────────────────────────

class TestListJobsClient:
    def test_empty_db_returns_empty_list(self, client):
        r = client.get("/api/jobs")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_list_type(self, client):
        r = client.get("/api/jobs")
        assert isinstance(r.json(), list)


# ── POST /api/jobs ────────────────────────────────────────────────────────────

class TestCreateJobClient:
    def test_valid_job_returns_201(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        assert r.status_code == 201

    def test_response_contains_id(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        assert "id" in r.json()

    def test_response_versions_match(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.4.11"})
        data = r.json()
        assert data["from_version"] == "7.2.0"
        assert data["to_version"] == "7.4.11"

    def test_initial_status_is_pending_or_running(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        assert r.json()["status"] in ("pending", "running")

    def test_default_source_is_scrape(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        assert r.json().get("source") == "scrape"

    def test_invalid_from_version(self, client):
        r = client.post("/api/jobs", json={"from_version": "bad", "to_version": "7.2.1"})
        assert r.status_code == 422

    def test_invalid_to_version(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "notver"})
        assert r.status_code == 422

    def test_from_version_equal_to_to_version(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.1", "to_version": "7.2.1"})
        assert r.status_code == 422

    def test_from_version_greater_than_to_version(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.4.11", "to_version": "7.2.8"})
        assert r.status_code == 422

    def test_missing_from_version(self, client):
        r = client.post("/api/jobs", json={"to_version": "7.2.1"})
        assert r.status_code == 422

    def test_missing_to_version(self, client):
        r = client.post("/api/jobs", json={"from_version": "7.2.0"})
        assert r.status_code == 422

    def test_job_appears_in_list(self, client):
        client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        jobs = client.get("/api/jobs").json()
        assert len(jobs) == 1

    def test_multiple_jobs_all_listed(self, client):
        client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"})
        client.post("/api/jobs", json={"from_version": "7.4.0", "to_version": "7.4.11"})
        jobs = client.get("/api/jobs").json()
        assert len(jobs) == 2


# ── GET /api/jobs/{id} ────────────────────────────────────────────────────────

class TestGetJobClient:
    def test_get_existing_job(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        r = client.get(f"/api/jobs/{created['id']}")
        assert r.status_code == 200

    def test_get_returns_correct_id(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        r = client.get(f"/api/jobs/{created['id']}")
        assert r.json()["id"] == created["id"]

    def test_get_returns_versions_field(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        r = client.get(f"/api/jobs/{created['id']}")
        assert "versions" in r.json()

    def test_get_returns_all_data_field(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        r = client.get(f"/api/jobs/{created['id']}")
        assert "all_data" in r.json()

    def test_get_returns_special_notices_field(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        r = client.get(f"/api/jobs/{created['id']}")
        assert "special_notices" in r.json()

    def test_get_nonexistent_job_returns_404(self, client):
        r = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_get_version_fields_match(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.4.0", "to_version": "7.4.11"}).json()
        r = client.get(f"/api/jobs/{created['id']}")
        data = r.json()
        assert data["from_version"] == "7.4.0"
        assert data["to_version"] == "7.4.11"


# ── DELETE /api/jobs/{id} ─────────────────────────────────────────────────────

class TestDeleteJobClient:
    def test_delete_existing_job_returns_204(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        r = client.delete(f"/api/jobs/{created['id']}")
        assert r.status_code == 204

    def test_deleted_job_not_found_afterwards(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        client.delete(f"/api/jobs/{created['id']}")
        r = client.get(f"/api/jobs/{created['id']}")
        assert r.status_code == 404

    def test_deleted_job_removed_from_list(self, client):
        created = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        client.delete(f"/api/jobs/{created['id']}")
        ids = [j["id"] for j in client.get("/api/jobs").json()]
        assert created["id"] not in ids

    def test_delete_nonexistent_returns_404(self, client):
        r = client.delete("/api/jobs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_delete_only_removes_target_job(self, client):
        j1 = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        j2 = client.post("/api/jobs", json={"from_version": "7.4.0", "to_version": "7.4.11"}).json()
        client.delete(f"/api/jobs/{j1['id']}")
        ids = [j["id"] for j in client.get("/api/jobs").json()]
        assert j1["id"] not in ids
        assert j2["id"] in ids


# ── list ordering ─────────────────────────────────────────────────────────────

class TestListOrdering:
    def test_both_jobs_in_list(self, client):
        j1 = client.post("/api/jobs", json={"from_version": "7.2.0", "to_version": "7.2.1"}).json()
        j2 = client.post("/api/jobs", json={"from_version": "7.4.0", "to_version": "7.4.11"}).json()
        ids = {j["id"] for j in client.get("/api/jobs").json()}
        assert j1["id"] in ids
        assert j2["id"] in ids
