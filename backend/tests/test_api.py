import io
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./storage/test_app.db")

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # triggers startup event -> init_db()
        yield c


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_documents_empty_or_list(client):
    res = client.get("/api/v1/documents")
    assert res.status_code == 200
    assert "documents" in res.json()


def test_process_unsupported_file_type(client):
    res = client.post(
        "/api/v1/documents/process",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        data={"document_type": "invoice"},
    )
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_process_image_invoice_end_to_end(client):
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), color="white").save(buf, format="PNG")
    buf.seek(0)
    res = client.post(
        "/api/v1/documents/process",
        files={"file": ("blank.png", buf, "image/png")},
        data={"document_type": "invoice"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["document_type"] == "invoice"
    assert "extracted_data" in body

    res2 = client.get("/api/v1/documents/blank.png")
    assert res2.status_code == 200
