from fastapi.testclient import TestClient

from tests.api.test_auth_system import headers


def test_taxonomy_permissions_and_safe_delete(client: TestClient) -> None:
    assert client.get("/api/v1/tags", headers=headers("dev-reader-token")).status_code == 200
    assert (
        client.post(
            "/api/v1/tags", headers=headers("dev-editor-token"), json={"name": "Local Only"}
        ).status_code
        == 403
    )
    created = client.post(
        "/api/v1/tags", headers=headers("dev-admin-token"), json={"name": "Local Only"}
    )
    assert created.status_code == 201
    assert (
        client.delete(
            f"/api/v1/tags/{created.json()['id']}", headers=headers("dev-admin-token")
        ).status_code
        == 204
    )


def test_media_rejects_executable_and_accepts_png_signature(client: TestClient) -> None:
    rejected = client.post(
        "/api/v1/media",
        headers=headers("dev-editor-token"),
        files={"file": ("evil.exe", b"MZfake", "application/octet-stream")},
    )
    assert rejected.status_code == 415
    png = b"\x89PNG\r\n\x1a\n" + b"local" * 20
    accepted = client.post(
        "/api/v1/media",
        headers=headers("dev-editor-token"),
        files={"file": ("../safe.png", png, "image/png")},
        data={"alt_text": "Fictional safe upload"},
    )
    assert accepted.status_code == 201, accepted.text
    assert ".." not in accepted.json()["filename"]
    assert len(accepted.json()["sha256"]) == 64
    content = client.get(
        f"/api/v1/media/{accepted.json()['id']}/content",
        headers=headers("dev-reader-token"),
    )
    assert content.content == png
