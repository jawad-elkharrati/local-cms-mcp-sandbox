from fastapi.testclient import TestClient


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.json()["status"] == "ok"


def test_missing_unknown_and_expired_tokens_are_401(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers=headers("unknown-demo-token")).status_code == 401
    assert client.get("/api/v1/me", headers=headers("expired-demo-token")).status_code == 401


def test_role_scope_matrix(client: TestClient) -> None:
    reader = client.get("/api/v1/me", headers=headers("dev-reader-token"))
    assert reader.status_code == 200
    assert reader.json()["role"] == "reader"
    denied = client.post(
        "/api/v1/articles",
        headers=headers("dev-reader-token"),
        json={"title": "A reader cannot create this article"},
    )
    assert denied.status_code == 403
    assert denied.json()["details"]["required_scope"] == "article:create"
