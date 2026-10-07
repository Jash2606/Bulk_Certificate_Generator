"""Retrieving generated certificates."""
import uuid

from app.services import certificate_renderer
from tests.helpers import error_of, job_payload, pdf_path, recipients


def submit(client, rows) -> dict:
    return client.post("/jobs", json=job_payload(rows)).json()


def certificates_of(client, job: dict) -> list[dict]:
    return client.get(job["status_url"]).json()["certificates"]


def test_download_generated_certificate(client, run_worker):
    job = submit(client, recipients("Asha Rao"))
    run_worker()
    certificate = certificates_of(client, job)[0]

    response = client.get(certificate["download_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert f"certificate-{certificate['id']}.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_download_unknown_certificate_returns_404(client):
    response = client.get(f"/certificates/{uuid.uuid4()}/download")

    assert response.status_code == 404
    assert error_of(response)["code"] == "CERTIFICATE_NOT_FOUND"


def test_certificates_that_are_not_generated_cannot_be_downloaded(client):
    job = submit(client, recipients("Asha Rao") + [{"name": "No Email"}])
    pending, invalid = certificates_of(client, job)  # the worker hasn't run yet

    for certificate in (pending, invalid):
        response = client.get(f"/certificates/{certificate['id']}/download")
        assert response.status_code == 409
        assert error_of(response)["code"] == "CERTIFICATE_NOT_READY"
        assert certificate["status"] in error_of(response)["message"]


def test_failed_certificate_cannot_be_downloaded(client, run_worker, monkeypatch):
    def always_fail(**kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(certificate_renderer, "render_certificate", always_fail)
    job = submit(client, recipients("Asha Rao"))
    run_worker()
    certificate = certificates_of(client, job)[0]

    assert certificate["status"] == "FAILED"
    response = client.get(f"/certificates/{certificate['id']}/download")
    assert response.status_code == 409
    assert error_of(response)["code"] == "CERTIFICATE_NOT_READY"


def test_missing_pdf_file_returns_404_instead_of_crashing(client, run_worker):
    job = submit(client, recipients("Asha Rao"))
    run_worker()
    certificate = certificates_of(client, job)[0]
    pdf_path(job["job_id"], certificate["id"]).unlink()

    response = client.get(certificate["download_url"])

    assert response.status_code == 404
    assert error_of(response)["code"] == "CERTIFICATE_FILE_MISSING"
