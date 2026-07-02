from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import Content, ContentReview, User

REVIEWER_ROLES = frozenset({"admin", "reviewer"})

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_review"},
    "pending_review": {"approved", "draft"},
}


def get_content_for_tenant(db: Session, content_id: UUID, tenant_id: UUID) -> Content:
    content = (
        db.query(Content)
        .options(joinedload(Content.author))
        .filter(Content.id == content_id, Content.tenant_id == tenant_id)
        .first()
    )
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    return content


def assert_reviewer(user: User) -> None:
    if user.role not in REVIEWER_ROLES:
        raise HTTPException(status_code=403, detail="无审核权限")


def _transition(content: Content, to_status: str) -> None:
    allowed = VALID_TRANSITIONS.get(content.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态「{content.status}」不能变更为「{to_status}」",
        )
    content.status = to_status


def submit_for_review(
    db: Session, content: Content, user: User, comment: str = ""
) -> Content:
    _transition(content, "pending_review")
    db.add(
        ContentReview(
            content_id=content.id,
            reviewer_id=user.id,
            action="submit",
            comment=comment,
        )
    )
    db.commit()
    db.refresh(content)
    return content


def approve_content(
    db: Session, content: Content, reviewer: User, comment: str = ""
) -> Content:
    assert_reviewer(reviewer)
    _transition(content, "approved")
    db.add(
        ContentReview(
            content_id=content.id,
            reviewer_id=reviewer.id,
            action="approve",
            comment=comment,
        )
    )
    db.commit()
    db.refresh(content)
    return content


def reject_content(
    db: Session, content: Content, reviewer: User, comment: str = ""
) -> Content:
    assert_reviewer(reviewer)
    _transition(content, "draft")
    db.add(
        ContentReview(
            content_id=content.id,
            reviewer_id=reviewer.id,
            action="reject",
            comment=comment,
        )
    )
    db.commit()
    db.refresh(content)
    return content
