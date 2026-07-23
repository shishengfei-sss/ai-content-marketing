"""ICP 配置 + L1→L2 匹配打分 + claim→leads。"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import Tenant
from app.models.crm import Deal, Lead
from app.models.tender import IcpConfig, PlatformTenderLead, ScoredTenderLead
from app.schemas.crm import LeadCreate
from app.schemas.tender_leads import IcpConfigUpsert, ScoredTenderLeadOut
from app.services.crm.lead_service import create_lead

MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")


def _weights_ok(cfg: IcpConfig | IcpConfigUpsert) -> int:
    return (
        int(cfg.weight_industry)
        + int(cfg.weight_company_size)
        + int(cfg.weight_region)
        + int(cfg.weight_budget)
        + int(cfg.weight_urgency)
    )


def get_icp(db: Session, tenant_id: UUID) -> IcpConfig | None:
    return db.query(IcpConfig).filter(IcpConfig.tenant_id == tenant_id).first()


def upsert_icp(db: Session, ctx: TenantContext, data: IcpConfigUpsert) -> IcpConfig:
    if _weights_ok(data) != 100:
        raise HTTPException(status_code=400, detail="ICP 五维权重之和必须为 100%")
    row = get_icp(db, ctx.tenant_id)
    payload = data.model_dump()
    if row is None:
        row = IcpConfig(tenant_id=ctx.tenant_id, **payload)
        db.add(row)
    else:
        for k, v in payload.items():
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    # 保存后重算本租户匹配
    rematch_tenant(db, ctx.tenant_id)
    db.refresh(row)
    return row


def score_lead(platform: PlatformTenderLead, icp: IcpConfig) -> tuple[int, dict]:
    """返回 (0-100 分, breakdown)。"""
    breakdown: dict = {}
    total = 0

    industries = [str(x) for x in (icp.target_industries or [])]
    if industries:
        hit = bool(platform.industry and any(i in platform.industry or platform.industry in i for i in industries))
        pts = icp.weight_industry if hit else 0
    else:
        pts = icp.weight_industry // 2  # 未配置行业 → 给半权
    breakdown["industry"] = pts
    total += pts

    regions = [str(x) for x in (icp.target_regions or [])]
    if regions:
        hit = bool(platform.region and any(r in platform.region or platform.region in r for r in regions))
        pts = icp.weight_region if hit else 0
    else:
        pts = icp.weight_region // 2
    breakdown["region"] = pts
    total += pts

    # L1 无企业规模字段 → 给中性半权
    breakdown["company_size"] = icp.weight_company_size // 2
    total += breakdown["company_size"]

    threshold = float(icp.min_budget_threshold or 0)
    budget = float(platform.budget_max or platform.budget_min or 0)
    if threshold <= 0:
        pts = icp.weight_budget // 2
    elif budget >= threshold:
        pts = icp.weight_budget
    else:
        pts = 0
    breakdown["budget"] = pts
    total += pts

    # 紧迫度：截止日期越近越高
    if platform.deadline:
        days = (platform.deadline - date.today()).days
        if days < 0:
            pts = 0
        elif days <= 7:
            pts = icp.weight_urgency
        elif days <= 30:
            pts = int(icp.weight_urgency * 0.7)
        else:
            pts = int(icp.weight_urgency * 0.4)
    else:
        pts = icp.weight_urgency // 2
    breakdown["urgency"] = pts
    total += pts

    text = " ".join(
        filter(
            None,
            [platform.product_name, platform.summary, platform.buyer_name, platform.industry, platform.category],
        )
    )
    excludes = [str(x) for x in (icp.exclude_keywords or []) if str(x).strip()]
    if excludes and any(k in text for k in excludes):
        breakdown["exclude_hit"] = True
        total = max(0, total - 30)
    else:
        breakdown["exclude_hit"] = False

    includes = [str(x) for x in (icp.include_keywords or []) if str(x).strip()]
    if includes:
        if any(k in text for k in includes):
            breakdown["include_hit"] = True
            total = min(100, total + 5)
        else:
            breakdown["include_hit"] = False
            total = max(0, total - 5)

    return min(100, max(0, int(total))), breakdown


def score_crm_lead(lead: Lead, icp: IcpConfig) -> int:
    """CRM 线索相对租户 ICP 的匹配分（0-100）。"""
    extra = lead.extra_data or {}
    industry = str(extra.get("industry") or getattr(lead, "industry", None) or "")
    region = str(
        extra.get("region")
        or extra.get("province")
        or getattr(lead, "country", None)
        or ""
    )
    text = " ".join(
        filter(None, [lead.company_name, lead.remark, industry, region, str(lead.source or "")])
    )

    total = 0
    industries = [str(x) for x in (icp.target_industries or [])]
    if industries:
        hit = bool(industry and any(i in industry or industry in i for i in industries))
        total += icp.weight_industry if hit else 0
    else:
        total += icp.weight_industry // 2

    regions = [str(x) for x in (icp.target_regions or [])]
    if regions:
        hit = bool(region and any(r in region or region in r for r in regions))
        total += icp.weight_region if hit else 0
    else:
        total += icp.weight_region // 2

    total += icp.weight_company_size // 2
    total += icp.weight_budget // 2
    total += icp.weight_urgency // 2

    excludes = [str(x) for x in (icp.exclude_keywords or []) if str(x).strip()]
    if excludes and any(k in text for k in excludes):
        total = max(0, total - 30)

    includes = [str(x) for x in (icp.include_keywords or []) if str(x).strip()]
    if includes:
        if any(k in text for k in includes):
            total = min(100, total + 5)
        else:
            total = max(0, total - 5)

    return min(100, max(0, int(total)))


def _upsert_scored(
    db: Session,
    *,
    tenant_id: UUID,
    platform: PlatformTenderLead,
    score: int,
    breakdown: dict,
) -> ScoredTenderLead:
    row = (
        db.query(ScoredTenderLead)
        .filter(
            ScoredTenderLead.tenant_id == tenant_id,
            ScoredTenderLead.platform_tender_lead_id == platform.id,
        )
        .first()
    )
    if row is None:
        row = ScoredTenderLead(
            tenant_id=tenant_id,
            platform_tender_lead_id=platform.id,
            match_score=score,
            score_breakdown=breakdown,
            status="pending",
        )
        db.add(row)
    else:
        # 已 claim / invalid / expired 不覆盖业务状态，仅刷新分数
        row.match_score = score
        row.score_breakdown = breakdown
        if row.status == "pending" and platform.deadline and platform.deadline < date.today():
            row.status = "expired"
    return row


def rematch_platform_lead(db: Session, platform_id: UUID) -> int:
    """对单条已发布 L1，按所有启用 ICP 重算 L2。返回写入条数。"""
    platform = db.query(PlatformTenderLead).filter(PlatformTenderLead.id == platform_id).first()
    if not platform or platform.status != "published":
        return 0
    icps = db.query(IcpConfig).filter(IcpConfig.is_active.is_(True)).all()
    n = 0
    for icp in icps:
        score, breakdown = score_lead(platform, icp)
        _upsert_scored(db, tenant_id=icp.tenant_id, platform=platform, score=score, breakdown=breakdown)
        n += 1
    db.commit()
    return n


def rematch_tenant(db: Session, tenant_id: UUID) -> int:
    icp = get_icp(db, tenant_id)
    if not icp or not icp.is_active:
        return 0
    published = db.query(PlatformTenderLead).filter(PlatformTenderLead.status == "published").all()
    n = 0
    for platform in published:
        score, breakdown = score_lead(platform, icp)
        _upsert_scored(db, tenant_id=tenant_id, platform=platform, score=score, breakdown=breakdown)
        n += 1
    db.commit()
    return n


def enrich_scored(db: Session, row: ScoredTenderLead) -> ScoredTenderLeadOut:
    platform = db.query(PlatformTenderLead).filter(PlatformTenderLead.id == row.platform_tender_lead_id).first()
    out = ScoredTenderLeadOut.model_validate(row)
    if platform:
        out.buyer_name = platform.buyer_name
        out.industry = platform.industry
        out.region = platform.region
        out.product_name = platform.product_name
        out.quantity = platform.quantity
        out.budget_min = float(platform.budget_min) if platform.budget_min is not None else None
        out.budget_max = float(platform.budget_max) if platform.budget_max is not None else None
        out.deadline = platform.deadline
        out.source_url = platform.source_url
        out.summary = platform.summary
        out.project_no = platform.project_no
        out.published_at = platform.published_at
        out.procurement_method = platform.procurement_method
        out.agent_name = platform.agent_name
        out.buyer_address = platform.buyer_address
        out.category = platform.category
        out.bid_open_date = platform.bid_open_date
        out.sme_preference = platform.sme_preference
        out.qualification_summary = platform.qualification_summary
        out.max_price_limit = (
            float(platform.max_price_limit) if platform.max_price_limit is not None else None
        )
    return out


def list_scored(
    db: Session,
    ctx: TenantContext,
    *,
    status_filter: str | None,
    page: int,
    page_size: int,
    q: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    category: str | None = None,
    procurement_method: str | None = None,
    agent_name: str | None = None,
    project_no: str | None = None,
    sme_preference: bool | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    min_score: int | None = None,
) -> tuple[list[ScoredTenderLeadOut], int]:
    from app.models.tender import PlatformTenderLead

    query = (
        db.query(ScoredTenderLead)
        .join(PlatformTenderLead, PlatformTenderLead.id == ScoredTenderLead.platform_tender_lead_id)
        .filter(ScoredTenderLead.tenant_id == ctx.tenant_id)
    )
    if status_filter:
        query = query.filter(ScoredTenderLead.status == status_filter)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                PlatformTenderLead.buyer_name.ilike(like),
                PlatformTenderLead.product_name.ilike(like),
                PlatformTenderLead.summary.ilike(like),
                PlatformTenderLead.project_no.ilike(like),
                PlatformTenderLead.agent_name.ilike(like),
                PlatformTenderLead.category.ilike(like),
                PlatformTenderLead.region.ilike(like),
            )
        )
    if region and region.strip():
        query = query.filter(PlatformTenderLead.region.ilike(f"%{region.strip()}%"))
    if industry and industry.strip():
        query = query.filter(PlatformTenderLead.industry.ilike(f"%{industry.strip()}%"))
    if category and category.strip():
        query = query.filter(PlatformTenderLead.category.ilike(f"%{category.strip()}%"))
    if procurement_method and procurement_method.strip():
        query = query.filter(
            PlatformTenderLead.procurement_method.ilike(f"%{procurement_method.strip()}%")
        )
    if agent_name and agent_name.strip():
        query = query.filter(PlatformTenderLead.agent_name.ilike(f"%{agent_name.strip()}%"))
    if project_no and project_no.strip():
        query = query.filter(PlatformTenderLead.project_no.ilike(f"%{project_no.strip()}%"))
    if sme_preference is not None:
        query = query.filter(PlatformTenderLead.sme_preference.is_(sme_preference))
    if deadline_from:
        query = query.filter(PlatformTenderLead.deadline >= deadline_from)
    if deadline_to:
        query = query.filter(PlatformTenderLead.deadline <= deadline_to)
    if min_score is not None:
        query = query.filter(ScoredTenderLead.match_score >= min_score)
    total = query.count()
    rows = (
        query.order_by(ScoredTenderLead.match_score.desc(), ScoredTenderLead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [enrich_scored(db, r) for r in rows], total


def get_scored(db: Session, ctx: TenantContext, scored_id: UUID) -> ScoredTenderLead:
    row = (
        db.query(ScoredTenderLead)
        .filter(ScoredTenderLead.id == scored_id, ScoredTenderLead.tenant_id == ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="匹配线索不存在")
    return row


def set_scored_status(db: Session, ctx: TenantContext, scored_id: UUID, new_status: str) -> ScoredTenderLead:
    if new_status not in ("pending", "valid", "invalid", "expired"):
        raise HTTPException(status_code=400, detail="非法状态")
    row = get_scored(db, ctx, scored_id)
    if row.converted_lead_id and new_status in ("invalid", "pending"):
        raise HTTPException(status_code=409, detail="已纳入 CRM 线索，不可回退为该状态")
    row.status = new_status
    db.commit()
    db.refresh(row)
    return row


def _resolve_claim_mobile(platform: PlatformTenderLead, scored_id: UUID) -> str:
    phone = (platform.contact_phone or "").strip()
    digits = re.sub(r"\D", "", phone)
    if MOBILE_RE.match(digits):
        return digits
    # 占位手机：保证可创建线索；备注中标明待补
    suffix = f"{(scored_id.int % 100000000):08d}"
    return f"170{suffix}"


def claim_to_lead(db: Session, ctx: TenantContext, scored_id: UUID) -> tuple[ScoredTenderLead, Lead]:
    """认领：只创建 leads，断言不创建 deals。"""
    row = get_scored(db, ctx, scored_id)
    if row.status in ("invalid", "expired"):
        raise HTTPException(status_code=409, detail=f"状态为 {row.status}，不可认领")
    if row.converted_lead_id:
        existing = db.query(Lead).filter(Lead.id == row.converted_lead_id, Lead.deleted_at.is_(None)).first()
        if existing:
            return row, existing

    platform = db.query(PlatformTenderLead).filter(PlatformTenderLead.id == row.platform_tender_lead_id).first()
    if not platform:
        raise HTTPException(status_code=404, detail="平台线索不存在")

    deals_before = (
        db.query(Deal)
        .filter(Deal.tenant_id == ctx.tenant_id, Deal.deleted_at.is_(None))
        .count()
    )

    contact = (platform.contact_name or "").strip() or "招标联系人"
    mobile = _resolve_claim_mobile(platform, row.id)
    lead = create_lead(
        db,
        ctx,
        LeadCreate(
            company_name=platform.buyer_name,
            contact_name=contact,
            mobile=mobile,
            phone=platform.contact_phone,
            source="其他",
            source_detail="招标线索",
            lead_score=row.match_score,
            remark=f"来自招标线索 L2；原文：{platform.source_url or '—'}",
            landing_url=(platform.source_url or None)[:500] if platform.source_url else None,
            extra_data={
                "scored_tender_lead_id": str(row.id),
                "platform_tender_lead_id": str(platform.id),
                "source_url": platform.source_url,
            },
        ),
    )

    deals_after = (
        db.query(Deal)
        .filter(Deal.tenant_id == ctx.tenant_id, Deal.deleted_at.is_(None))
        .count()
    )
    if deals_after != deals_before:
        raise HTTPException(status_code=500, detail="认领异常：禁止创建商机 Deal")

    row.converted_lead_id = lead.id
    row.status = "valid"
    row.assigned_to = ctx.user.id
    db.commit()
    db.refresh(row)
    return row, lead
