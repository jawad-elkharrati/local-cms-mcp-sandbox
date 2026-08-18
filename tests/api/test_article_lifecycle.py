from fastapi.testclient import TestClient

from tests.api.test_auth_system import headers

LONG_BODY = "# Local test\n\n" + " ".join(["fictional"] * 170)


def create(client: TestClient, key: str = "create-demo") -> dict[str, object]:
    response = client.post(
        "/api/v1/articles",
        headers={**headers("dev-editor-token"), "Idempotency-Key": key},
        json={
            "title": "A Complete Local Testing Article",
            "slug": f"complete-local-testing-{key}",
            "content_markdown": LONG_BODY,
            "seo_description": "A fictional local article used to verify safe lifecycle behavior with deterministic acceptance tests.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_idempotency_concurrency_permissions_and_publish(client: TestClient) -> None:
    article = create(client)
    again = client.post(
        "/api/v1/articles",
        headers={**headers("dev-editor-token"), "Idempotency-Key": "create-demo"},
        json={
            "title": "A Complete Local Testing Article",
            "slug": "complete-local-testing-create-demo",
            "content_markdown": LONG_BODY,
            "seo_description": "A fictional local article used to verify safe lifecycle behavior with deterministic acceptance tests.",
        },
    )
    assert again.status_code == 201
    assert again.json()["id"] == article["id"]

    updated = client.patch(
        f"/api/v1/articles/{article['id']}",
        headers=headers("dev-editor-token"),
        json={"expected_version": 1, "excerpt": "Updated safely", "change_summary": "Test update"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    stale = client.patch(
        f"/api/v1/articles/{article['id']}",
        headers=headers("dev-editor-token"),
        json={"expected_version": 1, "excerpt": "Would overwrite"},
    )
    assert stale.status_code == 409
    assert stale.json()["details"]["current_version"] == 2

    denied = client.post(
        f"/api/v1/articles/{article['id']}/publish",
        headers=headers("dev-editor-token"),
        json={"expected_version": 2},
    )
    assert denied.status_code == 403
    published = client.post(
        f"/api/v1/articles/{article['id']}/publish",
        headers=headers("dev-publisher-token"),
        json={"expected_version": 2},
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert client.get(f"/articles/{published.json()['slug']}").status_code == 200

    revisions = client.get(
        f"/api/v1/articles/{article['id']}/revisions",
        headers=headers("dev-reader-token"),
    )
    assert [item["version"] for item in revisions.json()["items"]] == [3, 2, 1]
    audit = client.get(
        f"/api/v1/articles/{article['id']}/audit", headers=headers("dev-admin-token")
    )
    assert len(audit.json()["items"]) == 3
    assert all(item["request_id"] for item in audit.json()["items"])


def test_soft_delete_hides_and_restore_preserves_history(client: TestClient) -> None:
    article = create(client, "delete-demo")
    deleted = client.request(
        "DELETE",
        f"/api/v1/articles/{article['id']}",
        headers=headers("dev-admin-token"),
        json={"expected_version": 1},
    )
    assert deleted.status_code == 200
    assert (
        client.get(
            f"/api/v1/articles/{article['id']}", headers=headers("dev-reader-token")
        ).status_code
        == 404
    )
    restored = client.post(
        f"/api/v1/articles/{article['id']}/restore",
        headers=headers("dev-admin-token"),
        json={"expected_version": 2},
    )
    assert restored.status_code == 200
    assert restored.json()["version"] == 3


def test_public_ui_excludes_drafts(client: TestClient) -> None:
    article = create(client, "ui-draft")
    page = client.get("/")
    assert article["slug"] not in page.text
    assert client.get("/admin").status_code == 200


def test_editor_can_move_draft_to_review(client: TestClient) -> None:
    article = create(client, "review-demo")
    response = client.post(
        f"/api/v1/articles/{article['id']}/status",
        headers=headers("dev-editor-token"),
        json={"expected_version": 1, "status": "review"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "review"
    assert response.json()["version"] == 2
