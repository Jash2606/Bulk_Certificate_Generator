"""Every error, whatever its source, comes back in the same shape: {"error": {"code", "message", "details"}}."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services import job_service
from tests.helpers import error_of


def test_application_errors_use_the_error_shape(client):
    job_id = uuid.uuid4()

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found", "details": None}
    }


def test_request_validation_errors_list_every_problem(client):
    response = client.post("/jobs", json={"recipients": []})

    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "The request is invalid"
    problems = {detail["field"]: detail["type"] for detail in error["details"]}
    assert problems == {"body.course_name": "missing", "body.recipients": "too_short"}


def test_malformed_path_parameter_is_a_validation_error(client):
    response = client.get("/jobs/not-a-uuid")

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    assert error_of(response)["details"][0]["field"] == "path.job_id"


def test_unknown_url_uses_the_error_shape(client):
    response = client.get("/no-such-page")

    assert response.status_code == 404
    assert error_of(response) == {"code": "NOT_FOUND", "message": "Not Found", "details": None}


def test_wrong_http_method_uses_the_error_shape(client):
    response = client.delete("/jobs")

    assert response.status_code == 405
    assert error_of(response)["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_errors_return_a_generic_500_without_internals(monkeypatch):
    def broken_get_job(db, job_id):
        raise RuntimeError("connection string with a password in it")

    monkeypatch.setattr(job_service, "get_job", broken_get_job)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"/jobs/{uuid.uuid4()}")

    assert response.status_code == 500
    assert error_of(response) == {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred", "details": None}
    assert "password" not in response.text
