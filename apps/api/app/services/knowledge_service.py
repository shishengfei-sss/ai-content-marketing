"""知识库、场景模板与 Prompt 辅助查询。

文档分块入库后供 RAG 检索；检索优先级：租户私有库 → 平台行业库（FR-KB-04）。
C4 起默认 hybrid：关键词 + 本地 embedding 余弦；PostgreSQL 可用 pgvector 列加速。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ContentTemplate, KnowledgeChunk, KnowledgeDocument, TenantBrandProfile, UserPromptProfile
from app.services.embedding_service import (
    EMBED_DIM,
    cosine_similarity,
    embed_text,
    embedding_from_json,
    embedding_to_json,
    vector_to_pg_literal,
)


@dataclass
class KnowledgeSearchHit:
    chunk: KnowledgeChunk
    score: float
    keyword_score: float
    vector_score: float


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


def _pgvector_available(db: Session) -> bool:
    if not settings.DATABASE_URL.startswith("postgresql"):
        return False
    try:
        cols = {c["name"] for c in inspect(db.bind).get_columns("knowledge_chunks")}
        return "embedding" in cols
    except Exception:
        return False


def _store_chunk_embedding(db: Session, chunk: KnowledgeChunk, vec: list[float]) -> None:
    chunk.embedding_json = embedding_to_json(vec)
    if _pgvector_available(db):
        db.execute(
            text("UPDATE knowledge_chunks SET embedding = :vec::vector WHERE id = :id"),
            {"vec": vector_to_pg_literal(vec), "id": str(chunk.id)},
        )


def ensure_chunk_embedding(db: Session, chunk: KnowledgeChunk) -> list[float]:
    parsed = embedding_from_json(chunk.embedding_json)
    if parsed:
        return parsed
    vec = embed_text(chunk.content)
    _store_chunk_embedding(db, chunk, vec)
    return vec


def backfill_knowledge_embeddings(db: Session, *, limit: int = 500) -> int:
    rows = db.execute(
        text("SELECT id, content FROM knowledge_chunks WHERE embedding_json IS NULL LIMIT :lim"),
        {"lim": limit},
    ).fetchall()
    count = 0
    for row_id, content in rows:
        emb = embedding_to_json(embed_text(content))
        rid = str(row_id)
        db.execute(
            text(
                "UPDATE knowledge_chunks SET embedding_json = :emb "
                "WHERE CAST(id AS TEXT) = :rid OR CAST(id AS TEXT) = :hex"
            ),
            {"emb": emb, "rid": rid, "hex": rid.replace("-", "")},
        )
        count += 1
    if count:
        db.commit()
    return count


def index_document(db: Session, document: KnowledgeDocument) -> None:
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
    pieces = chunk_text(document.raw_text)
    for idx, piece in enumerate(pieces):
        vec = embed_text(piece)
        chunk = KnowledgeChunk(
            document_id=document.id,
            tenant_id=document.tenant_id,
            industry_code=document.industry_code,
            scope=document.scope,
            chunk_index=idx,
            content=piece,
            embedding_json=embedding_to_json(vec),
        )
        db.add(chunk)
        db.flush()
        if _pgvector_available(db):
            db.execute(
                text("UPDATE knowledge_chunks SET embedding = :vec::vector WHERE id = :id"),
                {"vec": vector_to_pg_literal(vec), "id": str(chunk.id)},
            )
    document.chunk_count = len(pieces)
    document.status = "parsed"
    db.commit()
    db.refresh(document)


def _extract_keywords(query: str) -> list[str]:
    keywords = [w for w in re.split(r"\s+", query.strip()) if len(w) >= 2][:5]
    if not keywords:
        keywords = [query[:20]] if query else ["财税"]
    return keywords


def _keyword_score(content: str, keywords: list[str]) -> float:
    if not content.strip():
        return 0.0
    lower = content.lower()
    score = 0.0
    for kw in keywords:
        if kw.lower() in lower:
            score += 2.0
        for token in re.split(r"[\s，。、；：]+", kw):
            if len(token) >= 2 and token.lower() in lower:
                score += 0.75
    return score


def _vector_score(chunk: KnowledgeChunk, query_vec: list[float], db: Session) -> float:
    parsed = embedding_from_json(chunk.embedding_json)
    if not parsed:
        parsed = ensure_chunk_embedding(db, chunk)
    return cosine_similarity(query_vec, parsed)


def _score_chunk(
    chunk: KnowledgeChunk,
    *,
    keywords: list[str],
    query_vec: list[float],
    db: Session,
    mode: str,
) -> KnowledgeSearchHit:
    kw = _keyword_score(chunk.content, keywords)
    vec = _vector_score(chunk, query_vec, db) if mode in ("hybrid", "vector") else 0.0
    if mode == "keyword":
        total = kw
    elif mode == "vector":
        total = vec
    else:
        total = kw * 0.4 + vec * 0.6
    return KnowledgeSearchHit(chunk=chunk, score=total, keyword_score=kw, vector_score=vec)


def _pgvector_search_scope(
    db: Session,
    *,
    scope: str,
    tenant_id: UUID,
    industry_code: str,
    query_vec: list[float],
    limit: int,
) -> list[KnowledgeChunk]:
    vec_lit = vector_to_pg_literal(query_vec)
    if scope == "tenant":
        sql = text(
            """
            SELECT id FROM knowledge_chunks
            WHERE industry_code = :industry
              AND scope = 'tenant'
              AND tenant_id = :tenant_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :qvec::vector
            LIMIT :lim
            """
        )
        params = {
            "industry": industry_code,
            "tenant_id": str(tenant_id),
            "qvec": vec_lit,
            "lim": limit,
        }
    else:
        sql = text(
            """
            SELECT id FROM knowledge_chunks
            WHERE industry_code = :industry
              AND scope = 'platform'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :qvec::vector
            LIMIT :lim
            """
        )
        params = {"industry": industry_code, "qvec": vec_lit, "lim": limit}
    ids = [row[0] for row in db.execute(sql, params).fetchall()]
    if not ids:
        return []
    rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.id.in_(ids)).all()
    order = {str(i): idx for idx, i in enumerate(ids)}
    rows.sort(key=lambda c: order.get(str(c.id), 999))
    return rows


def _python_rank_scope(
    db: Session,
    *,
    scope: str,
    tenant_id: UUID,
    industry_code: str,
    query: str,
    keywords: list[str],
    query_vec: list[float],
    mode: str,
    limit: int,
    exclude: set[UUID],
) -> list[KnowledgeSearchHit]:
    q = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.industry_code == industry_code,
        KnowledgeChunk.scope == scope,
    )
    if scope == "tenant":
        q = q.filter(KnowledgeChunk.tenant_id == tenant_id)
    candidates = q.order_by(KnowledgeChunk.created_at.desc()).limit(max(limit * 20, 50)).all()
    hits: list[KnowledgeSearchHit] = []
    for chunk in candidates:
        if chunk.id in exclude:
            continue
        hit = _score_chunk(chunk, keywords=keywords, query_vec=query_vec, db=db, mode=mode)
        if mode == "keyword" and hit.keyword_score <= 0:
            continue
        if mode in ("hybrid", "vector") and hit.score <= 0:
            continue
        hits.append(hit)
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def search_knowledge(
    db: Session,
    *,
    tenant_id: UUID,
    industry_code: str,
    query: str,
    limit: int = 5,
    mode: str = "hybrid",
) -> list[KnowledgeChunk]:
    """检索知识块；默认 hybrid（关键词 + embedding）。"""
    if mode not in ("keyword", "hybrid", "vector"):
        mode = "hybrid"
    limit = max(1, min(limit, 20))
    keywords = _extract_keywords(query)
    query_vec = embed_text(query)
    seen: set[UUID] = set()
    ordered: list[KnowledgeChunk] = []

    use_pg = mode in ("hybrid", "vector") and _pgvector_available(db)

    for scope in ("tenant", "platform"):
        remaining = limit - len(ordered)
        if remaining <= 0:
            break
        if use_pg:
            chunks = _pgvector_search_scope(
                db,
                scope=scope,
                tenant_id=tenant_id,
                industry_code=industry_code,
                query_vec=query_vec,
                limit=remaining,
            )
            for chunk in chunks:
                if chunk.id in seen:
                    continue
                seen.add(chunk.id)
                ordered.append(chunk)
                if len(ordered) >= limit:
                    break
        else:
            hits = _python_rank_scope(
                db,
                scope=scope,
                tenant_id=tenant_id,
                industry_code=industry_code,
                query=query,
                keywords=keywords,
                query_vec=query_vec,
                mode=mode,
                limit=remaining,
                exclude=seen,
            )
            for hit in hits:
                seen.add(hit.chunk.id)
                ordered.append(hit.chunk)
                if len(ordered) >= limit:
                    break
    return ordered[:limit]


def search_knowledge_scored(
    db: Session,
    *,
    tenant_id: UUID,
    industry_code: str,
    query: str,
    limit: int = 5,
    mode: str = "hybrid",
) -> list[KnowledgeSearchHit]:
    """带分数的检索，供 API / 工具验收。"""
    if mode not in ("keyword", "hybrid", "vector"):
        mode = "hybrid"
    limit = max(1, min(limit, 20))
    keywords = _extract_keywords(query)
    query_vec = embed_text(query)
    seen: set[UUID] = set()
    hits: list[KnowledgeSearchHit] = []

    for scope in ("tenant", "platform"):
        remaining = limit - len(hits)
        if remaining <= 0:
            break
        scope_hits = _python_rank_scope(
            db,
            scope=scope,
            tenant_id=tenant_id,
            industry_code=industry_code,
            query=query,
            keywords=keywords,
            query_vec=query_vec,
            mode=mode,
            limit=remaining,
            exclude=seen,
        )
        for hit in scope_hits:
            seen.add(hit.chunk.id)
            hits.append(hit)
            if len(hits) >= limit:
                break
    return hits[:limit]


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
