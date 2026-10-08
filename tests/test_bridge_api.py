"""
Unit tests for CV Servant Chrome Extension Bridge REST API.
"""
import json
import time
import urllib.request
import pytest
from cv_servant.bridge.api_server import CVBridgeServer, get_candidate_autofill_data
from cv_servant.coordinator import ApplicationCoordinator


@pytest.fixture
def test_bridge_server():
    coord = ApplicationCoordinator()
    # Use a test port to avoid conflict
    server = CVBridgeServer(coordinator=coord, port=5829)
    success = server.start()
    assert success is True
    time.sleep(0.1)
    yield server
    server.stop()


def test_autofill_data_structure():
    data = get_candidate_autofill_data()
    assert "candidate" in data
    cand = data["candidate"]
    assert cand["first_name"] == "Mustafa"
    assert cand["last_name"] == "Shawky"
    assert "arch.mustafa" in cand["email"]
    assert cand["total_experience_years"] == 19
    assert cand["pmp_certified"] == "Yes"
    assert "common_answers" in cand


def test_bridge_server_endpoints(test_bridge_server):
    base_url = "http://127.0.0.1:5829"

    # Test /api/status
    with urllib.request.urlopen(f"{base_url}/api/status") as res:
        assert res.status == 200
        body = json.loads(res.read().decode("utf-8"))
        assert body["status"] == "online"
        assert "Mustafa" in body["candidate"]

    # Test /api/profile
    with urllib.request.urlopen(f"{base_url}/api/profile") as res:
        assert res.status == 200
        body = json.loads(res.read().decode("utf-8"))
        assert "candidate" in body
        assert body["candidate"]["first_name"] == "Mustafa"

    # Test /api/track_application
    payload = {
        "job_title": "Senior BIM Specialist Test",
        "company_name": "Test Engineering Firm",
        "job_url": "https://www.linkedin.com/jobs/view/999999999",
        "country": "Australia",
        "city": "Brisbane",
        "source": "LinkedIn Easy Apply",
        "status": "Applied (External / تم التقديم)",
        "notes": "Testing Chrome Extension tracking bridge"
    }
    req = urllib.request.Request(
        f"{base_url}/api/track_application",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        body = json.loads(res.read().decode("utf-8"))
        assert body["success"] is True
        assert body["job_id"].startswith("JOB-")

    # Clean up test row from tracker
    test_bridge_server.coordinator.tracker.delete_job(body["job_id"])
