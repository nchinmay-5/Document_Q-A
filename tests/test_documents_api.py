import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from documents import services
from documents.models import Document

pytestmark = pytest.mark.django_db

UPLOAD_URL = "/api/documents/"


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    """Uploads must not need Redis in tests; record the queue call instead."""
    queued: list[int] = []
    monkeypatch.setattr(services, "queue_ingestion", lambda document: queued.append(document.id))
    return queued


def _upload(client: APIClient, name: str = "policy.txt", content: bytes = b"Leave policy text."):
    return client.post(
        UPLOAD_URL,
        {"file": SimpleUploadedFile(name, content, content_type="text/plain")},
        format="multipart",
    )


def test_upload_creates_document_and_queues_ingestion(api_client, user, no_broker):
    response = _upload(api_client)

    assert response.status_code == 201
    document = Document.objects.get(id=response.data["id"])
    assert document.user == user
    assert document.status == Document.Status.UPLOADED
    assert document.content_type == "txt"
    assert len(document.content_hash) == 64
    assert no_broker == [document.id]


def test_unsupported_extension_is_rejected(api_client):
    response = _upload(api_client, name="notes.md", content=b"# hello")

    assert response.status_code == 400
    assert Document.objects.count() == 0


def test_oversized_upload_is_rejected(api_client, settings):
    settings.MAX_UPLOAD_SIZE_MB = 0

    response = _upload(api_client, content=b"x" * 2048)

    assert response.status_code == 400


def test_listing_returns_only_the_callers_documents(api_client, user, other_user):
    _upload(api_client)
    Document.objects.create(
        user=other_user,
        filename="other.txt",
        file="documents/2/other.txt",
        content_type="txt",
        content_hash="0" * 64,
    )

    response = api_client.get(UPLOAD_URL)

    assert response.status_code == 200
    assert [item["filename"] for item in response.data] == ["policy.txt"]


def test_another_user_cannot_read_or_delete_a_document(api_client, other_user):
    document_id = _upload(api_client).data["id"]
    intruder = APIClient()
    intruder.force_authenticate(user=other_user)

    assert intruder.get(f"{UPLOAD_URL}{document_id}/").status_code == 404
    assert intruder.delete(f"{UPLOAD_URL}{document_id}/").status_code == 404
    assert Document.objects.filter(id=document_id).exists()


def test_anonymous_access_is_denied():
    assert APIClient().get(UPLOAD_URL).status_code == 401
