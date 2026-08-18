from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.fake_blog.auth import Actor, require_scope
from apps.fake_blog.db.models import AuditLog
from apps.fake_blog.db.session import get_session
from apps.fake_blog.errors import ApiError

router = APIRouter(prefix="/audit", tags=["audit"])
Session = Annotated[AsyncSession, Depends(get_session)]


def audit_data(row: AuditLog) -> dict[str, object]:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "actor_id": row.actor_id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "before": row.before_json,
        "after": row.after_json,
        "metadata": row.metadata_json,
        "created_at": row.created_at,
    }


@router.get("")
async def list_audit(
    session: Session,
    _: Actor = require_scope("audit:read"),
    action: str | None = None,
    entity_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    statement = select(AuditLog)
    if action:
        statement = statement.where(AuditLog.action == action)
    if entity_id:
        statement = statement.where(AuditLog.entity_id == entity_id)
    if request_id:
        statement = statement.where(AuditLog.request_id == request_id)
    rows = (await session.scalars(statement.order_by(AuditLog.created_at.desc()).limit(100))).all()
    return {"items": [audit_data(row) for row in rows]}


@router.get("/{audit_id}")
async def get_audit(
    audit_id: str, session: Session, _: Actor = require_scope("audit:read")
) -> dict[str, object]:
    row = await session.get(AuditLog, audit_id)
    if not row:
        raise ApiError(404, "not_found", "Audit event not found")
    return audit_data(row)
