import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ContentTemplate, KnowledgeChunk, KnowledgeDocument, TenantBrandProfile, UserPromptProfile


def chunk_text(text: str, max_len: int = 450) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) + 2 <= max_len:
            buffer = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        else:
            if buffer:
                chunks.append(buffer)
            if len(paragraph) <= max_len:
                buffer = paragraph
            else:
                for i in range(0, len(paragraph), max_len):
                    chunks.append(paragraph[i : i + max_len])
                buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks or ([text[:max_len]] if text else [])


def index_document(db: Session, document: KnowledgeDocument) -> None:
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
    pieces = chunk_text(document.raw_text)
    for idx, piece in enumerate(pieces):
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                tenant_id=document.tenant_id,
                industry_code=document.industry_code,
                scope=document.scope,
                chunk_index=idx,
                content=piece,
            )
        )
    document.chunk_count = len(pieces)
    document.status = "parsed"
    db.commit()
    db.refresh(document)


def search_knowledge(
    db: Session,
    *,
    tenant_id: UUID,
    industry_code: str,
    query: str,
    limit: int = 5,
) -> list[KnowledgeChunk]:
    keywords = [w for w in re.split(r"\s+", query.strip()) if len(w) >= 2][:5]
    if not keywords:
        keywords = [query[:20]] if query else ["财税"]

    tenant_hits: list[KnowledgeChunk] = []
    seen: set[UUID] = set()
    for kw in keywords:
        rows = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.industry_code == industry_code,
                KnowledgeChunk.scope == "tenant",
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeChunk.content.ilike(f"%{kw}%"),
            )
            .limit(limit)
            .all()
        )
        for row in rows:
            if row.id not in seen:
                seen.add(row.id)
                tenant_hits.append(row)
        if len(tenant_hits) >= limit:
            return tenant_hits[:limit]

    platform_hits: list[KnowledgeChunk] = []
    for kw in keywords:
        rows = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.industry_code == industry_code,
                KnowledgeChunk.scope == "platform",
                KnowledgeChunk.content.ilike(f"%{kw}%"),
            )
            .limit(limit)
            .all()
        )
        for row in rows:
            if row.id not in seen:
                seen.add(row.id)
                platform_hits.append(row)
        if len(tenant_hits) + len(platform_hits) >= limit:
            break
    return (tenant_hits + platform_hits)[:limit]


def get_template(
    db: Session, industry_code: str, platform: str, scene: str
) -> ContentTemplate | None:
    return (
        db.query(ContentTemplate)
        .filter(
            ContentTemplate.industry_code == industry_code,
            ContentTemplate.platform == platform,
            ContentTemplate.scene == scene,
            ContentTemplate.is_active.is_(True),
        )
        .first()
    )


def list_templates(db: Session, industry_code: str, platform: str | None = None) -> list[ContentTemplate]:
    query = db.query(ContentTemplate).filter(
        ContentTemplate.industry_code == industry_code,
        ContentTemplate.is_active.is_(True),
    )
    if platform:
        query = query.filter(ContentTemplate.platform == platform)
    return query.order_by(ContentTemplate.platform, ContentTemplate.scene).all()


def get_brand_profile(db: Session, tenant_id: UUID) -> TenantBrandProfile | None:
    return db.query(TenantBrandProfile).filter(TenantBrandProfile.tenant_id == tenant_id).first()


def get_user_prompt(db: Session, user_id: UUID) -> UserPromptProfile | None:
    return db.query(UserPromptProfile).filter(UserPromptProfile.user_id == user_id).first()
