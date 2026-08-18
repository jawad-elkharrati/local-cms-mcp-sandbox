import asyncio
import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from apps.fake_blog.db.models import (
    ApiToken,
    Article,
    ArticleRevision,
    AuditLog,
    Category,
    MediaAsset,
    Tag,
    User,
    article_categories,
    article_tags,
)
from apps.fake_blog.db.session import session_scope
from apps.fake_blog.domain.storage import ObjectStorage

TOKENS = {
    "dev-reader-token": ("reader", ["article:read", "taxonomy:read", "media:read", "audit:self"]),
    "dev-editor-token": (
        "editor",
        [
            "article:read",
            "taxonomy:read",
            "media:read",
            "audit:self",
            "article:create",
            "article:update",
            "media:upload",
            "taxonomy:assign",
        ],
    ),
    "dev-publisher-token": (
        "publisher",
        [
            "article:read",
            "taxonomy:read",
            "media:read",
            "audit:self",
            "article:create",
            "article:update",
            "media:upload",
            "taxonomy:assign",
            "article:publish",
            "article:unpublish",
        ],
    ),
    "dev-admin-token": ("admin", ["*"]),
}

TOPICS = [
    ("Python Data Pipelines", "python-data-pipelines", "published", "Python", "Data Engineering"),
    ("Reliable Docker Workflows", "reliable-docker-workflows", "published", "Docker", "DevOps"),
    (
        "Deploying ML Models with Docker",
        "deploy-ml-models-docker",
        "published",
        "Machine Learning",
        "DevOps",
    ),
    (
        "Containerized Machine Learning Deployment",
        "containerized-ml-deployment",
        "published",
        "Machine Learning",
        "DevOps",
    ),
    (
        "Practical SQL Window Functions",
        "sql-window-functions",
        "published",
        "SQL",
        "Data Engineering",
    ),
    (
        "Local AI Agent Patterns",
        "local-ai-agent-patterns",
        "draft",
        "AI Agents",
        "Artificial Intelligence",
    ),
    (
        "Redis for Data Applications",
        "redis-data-applications",
        "draft",
        "Redis",
        "Data Engineering",
    ),
    (
        "PostgreSQL Indexing Basics",
        "postgresql-indexing-basics",
        "draft",
        "PostgreSQL",
        "Data Engineering",
    ),
    (
        "Feature Engineering Checklist",
        "feature-engineering-checklist",
        "draft",
        "Machine Learning",
        "Artificial Intelligence",
    ),
    ("Cloud Concepts without Cloud Spend", "local-cloud-concepts", "review", "Cloud", "DevOps"),
    ("Testing Async Python APIs", "testing-async-python-apis", "review", "Python", "Development"),
    (
        "Archived Data Lake Notes",
        "archived-data-lake-notes",
        "archived",
        "Cloud",
        "Data Engineering",
    ),
    ("Safe CMS Automation", "safe-cms-automation", "draft", "AI Agents", "Development"),
]


def stable_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"local-cms-lab:{name}"))


def content(title: str, primary: str, secondary: str) -> str:
    paragraph = (
        f"This fictional tutorial explains {primary.lower()} using a completely local lab. "
        f"It connects practical {secondary.lower()} decisions with repeatable examples, tests, "
        "failure handling, observability, and safe iteration. Every command targets disposable "
        "local "
        "services and every identity is invented for learning."
    )
    return f"# {title}\n\n## Why it matters\n\n{paragraph}\n\n## Implementation\n\n" + "\n\n".join(
        [paragraph] * 4
    )


async def seed() -> None:
    pixel_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    async with session_scope() as session:
        await session.execute(delete(article_tags))
        await session.execute(delete(article_categories))
        for model in [
            AuditLog,
            ArticleRevision,
            Article,
            MediaAsset,
            ApiToken,
            Tag,
            Category,
            User,
        ]:
            await session.execute(delete(model))

        users: dict[str, User] = {}
        for role in ["reader", "editor", "publisher", "admin"]:
            user = User(
                id=stable_id(f"user:{role}"),
                email=f"{role}@local.invalid",
                display_name=f"Local {role.title()}",
                role=role,
            )
            session.add(user)
            users[role] = user
        await session.flush()
        for raw, (role, scopes) in TOKENS.items():
            session.add(
                ApiToken(
                    id=stable_id(f"token:{role}"),
                    token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                    user_id=users[role].id,
                    label=f"Local {role}",
                    scopes=scopes,
                    expires_at=None,
                    revoked_at=None,
                    last_used_at=None,
                )
            )
        session.add(
            ApiToken(
                id=stable_id("token:expired"),
                token_hash=hashlib.sha256(b"expired-demo-token").hexdigest(),
                user_id=users["reader"].id,
                label="Expired demo",
                scopes=["article:read"],
                expires_at=datetime.now(UTC) - timedelta(days=1),
                revoked_at=None,
                last_used_at=None,
            )
        )

        tag_names = [
            "Python",
            "Docker",
            "Machine Learning",
            "SQL",
            "PostgreSQL",
            "Redis",
            "Cloud",
            "AI Agents",
            "Testing",
            "MCP",
            "FastAPI",
        ]
        tags = {
            name: Tag(
                name=name,
                slug=name.lower().replace(" ", "-"),
                description=f"Fictional {name} learning content",
            )
            for name in tag_names
        }
        session.add_all(tags.values())
        categories = {
            name: Category(
                name=name, slug=name.lower().replace(" ", "-"), description=f"Local {name} category"
            )
            for name in [
                "Development",
                "Data Engineering",
                "Artificial Intelligence",
                "DevOps",
                "Databases",
            ]
        }
        session.add_all(categories.values())
        await session.flush()

        for i in range(4):
            object_key = f"seed/{i}.png"
            await ObjectStorage().put(object_key, pixel_png, "image/png")
            session.add(
                MediaAsset(
                    id=stable_id(f"media:{i}"),
                    object_key=object_key,
                    filename=f"fictional-{i}.png",
                    mime_type="image/png",
                    size_bytes=68,
                    width=1,
                    height=1,
                    alt_text=f"Fictional local sample {i}",
                    caption="Generated seed placeholder",
                    sha256=hashlib.sha256(pixel_png).hexdigest(),
                    uploaded_by=users["admin"].id,
                )
            )

        for index, (title, slug, status, primary, category) in enumerate(TOPICS):
            body = content(title, primary, category)
            article = Article(
                id=stable_id(f"article:{slug}"),
                title=title,
                slug=slug,
                excerpt=f"A fictional guide to {primary.lower()}.",
                content_markdown=body,
                content_html="",
                status=status,
                version=2 if index == 0 else 1,
                author_id=users["editor"].id,
                seo_title=title[:60],
                seo_description=(
                    f"Learn {primary.lower()} safely in a fictional local lab with repeatable "
                    "examples and practical checks."
                ),
                canonical_path=f"/articles/{slug}",
                published_at=datetime.now(UTC) - timedelta(days=index + 1)
                if status == "published"
                else None,
            )
            article.tags = [tags[primary] if primary in tags else tags["Testing"]]
            article.categories = [categories[category]]
            session.add(article)
            await session.flush()
            session.add(
                ArticleRevision(
                    id=stable_id(f"revision:{slug}:1"),
                    article_id=article.id,
                    version=1,
                    snapshot_json={**article.snapshot(), "version": 1},
                    change_summary="Seeded fictional article",
                    actor_id=users["admin"].id,
                )
            )
            if article.version == 2:
                session.add(
                    ArticleRevision(
                        id=stable_id(f"revision:{slug}:2"),
                        article_id=article.id,
                        version=2,
                        snapshot_json=article.snapshot(),
                        change_summary="Expanded deterministic seed article",
                        actor_id=users["admin"].id,
                    )
                )
            session.add(
                AuditLog(
                    id=stable_id(f"audit:{slug}"),
                    request_id=f"seed-{index:02d}",
                    actor_id=users["admin"].id,
                    action="article.seed",
                    entity_type="article",
                    entity_id=article.id,
                    before_json=None,
                    after_json=article.snapshot(),
                    metadata_json={"seed": True},
                )
            )

        deleted = Article(
            id=stable_id("article:deleted"),
            title="Deleted Fictional Draft",
            slug="deleted-fictional-draft",
            excerpt="Soft-deleted seed",
            content_markdown=content("Deleted Fictional Draft", "MCP", "Development"),
            content_html="",
            status="draft",
            previous_status="draft",
            version=2,
            author_id=users["editor"].id,
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted)
        await session.flush()
        session.add(
            ArticleRevision(
                id=stable_id("revision:deleted:2"),
                article_id=deleted.id,
                version=2,
                snapshot_json=deleted.snapshot(),
                change_summary="Soft-deleted seed",
                actor_id=users["admin"].id,
            )
        )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
