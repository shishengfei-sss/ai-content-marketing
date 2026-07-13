from uuid import UUID

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_active_tenant_id
from app.models import KnowledgeDocument, User
from app.schemas import KnowledgeDocumentOut, KnowledgeUploadTextRequest
from app.services.assistant_service import MARKETING_ADVISOR_CODE, normalize_advisor_code
from app.services.knowledge_service import index_document, search_knowledge_scored

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

logger = logging.getLogger(__name__)


def _doc_out(doc: KnowledgeDocument) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut(
        id=doc.id,
        title=doc.title,
        file_name=doc.file_name,
        scope=doc.scope,
        industry_code=doc.industry_code or "",
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
    )


def _resolve_industry_code(raw: str | None) -> str:
    code = normalize_advisor_code(raw or MARKETING_ADVISOR_CODE)
    return code if code else MARKETING_ADVISOR_CODE


def _safe_index(db: Session, doc: KnowledgeDocument) -> None:
    try:
        index_document(db, doc)
    except Exception as exc:
        logger.exception("knowledge index failed doc=%s", doc.id)
        doc.status = "failed"
        db.commit()
        msg = str(exc).lower()
        if "does not exist" in msg or "undefinedtable" in msg or "no such table" in msg:
            detail = "知识库表未初始化，请在服务器执行 alembic upgrade head"
        else:
            detail = f"文档解析失败: {exc}"
        raise HTTPException(status_code=500, detail=detail) from exc


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.scope == "tenant",
            KnowledgeDocument.tenant_id == tenant_id,
        )
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )
    return [_doc_out(d) for d in docs]


@router.post("/documents/text", response_model=KnowledgeDocumentOut)
def upload_text(
    body: KnowledgeUploadTextRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        industry_code=_resolve_industry_code(body.industry_code),
        scope="tenant",
        title=body.title,
        file_name=f"{body.title}.txt",
        raw_text=body.text,
        status="parsing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    _safe_index(db, doc)
    return _doc_out(doc)


@router.post("/documents/upload", response_model=KnowledgeDocumentOut)
async def upload_file(
    title: str = Form(...),
    industry_code: str = Form(default=MARKETING_ADVISOR_CODE),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    raw = (await file.read()).decode("utf-8", errors="ignore")
    if len(raw.strip()) < 10:
        raise HTTPException(status_code=400, detail="文件内容过短或无法解析为文本")
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        industry_code=_resolve_industry_code(industry_code),
        scope="tenant",
        title=title,
        file_name=file.filename or f"{title}.txt",
        raw_text=raw,
        status="parsing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    _safe_index(db, doc)
    return _doc_out(doc)


@router.get("/search")
def search_documents(
    q: str,
    mode: str = "hybrid",
    limit: int = 5,
    industry_code: str = "finance",
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    if mode not in ("keyword", "hybrid", "vector"):
        raise HTTPException(status_code=400, detail="mode 必须为 keyword、hybrid 或 vector")
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="q 至少 2 个字符")
    hits = search_knowledge_scored(
        db,
        tenant_id=tenant_id,
        industry_code=industry_code,
        query=q.strip(),
        limit=min(limit, 10),
        mode=mode,
    )
    return {
        "query": q.strip(),
        "mode": mode,
        "results": [
            {
                "content": h.chunk.content[:500],
                "scope": h.chunk.scope,
                "score": round(h.score, 4),
                "keyword_score": round(h.keyword_score, 4),
                "vector_score": round(h.vector_score, 4),
                "has_embedding": bool(h.chunk.embedding_json),
            }
            for h in hits
        ],
    }


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.scope == "tenant",
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    db.delete(doc)
    db.commit()
    return {"ok": True}
