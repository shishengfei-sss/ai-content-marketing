"""营销活动投放渠道字典服务。"""
from __future__ import annotations

import re
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import DEFAULT_CAMPAIGN_CHANNELS, CampaignChannel, MarketingCampaign
from app.schemas.crm import CampaignChannelCreate, CampaignChannelUpdate

_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


def list_channels(
    db: Session, tenant_id: UUID, *, active_only: bool = False
) -> list[CampaignChannel]:
    ensure_default_channels(db, tenant_id)
    q = db.query(CampaignChannel).filter(CampaignChannel.tenant_id == tenant_id)
    if active_only:
        q = q.filter(CampaignChannel.is_active.is_(True))
    return q.order_by(CampaignChannel.sort_order.asc(), CampaignChannel.name.asc()).all()


def get_channel(db: Session, tenant_id: UUID, channel_id: UUID) -> CampaignChannel | None:
    return (
        db.query(CampaignChannel)
        .filter(uuid_eq(CampaignChannel.id, channel_id), CampaignChannel.tenant_id == tenant_id)
        .first()
    )


def _slug_code(name: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if raw and _CODE_RE.match(raw):
        return raw[:50]
    return f"ch_{uuid.uuid4().hex[:10]}"


def _normalize_code(code: str | None, name: str) -> str:
    if code and code.strip():
        value = code.strip().lower()
        if not _CODE_RE.match(value):
            raise HTTPException(
                status_code=400,
                detail="渠道编码须为小写字母开头，仅含 a-z / 0-9 / _，最长 50",
            )
        return value
    return _slug_code(name)


def _check_unique(
    db: Session,
    tenant_id: UUID,
    *,
    code: str | None = None,
    name: str | None = None,
    exclude_id: UUID | None = None,
) -> None:
    if code is not None:
        q = db.query(CampaignChannel).filter(
            CampaignChannel.tenant_id == tenant_id, CampaignChannel.code == code
        )
        if exclude_id is not None:
            q = q.filter(CampaignChannel.id != exclude_id)
        if q.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="渠道编码已存在")
    if name is not None:
        q = db.query(CampaignChannel).filter(
            CampaignChannel.tenant_id == tenant_id, CampaignChannel.name == name
        )
        if exclude_id is not None:
            q = q.filter(CampaignChannel.id != exclude_id)
        if q.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="渠道名称已存在")


def create_channel(db: Session, ctx: TenantContext, data: CampaignChannelCreate) -> CampaignChannel:
    name = data.name.strip()
    code = _normalize_code(data.code, name)
    _check_unique(db, ctx.tenant_id, code=code, name=name)
    row = CampaignChannel(
        tenant_id=ctx.tenant_id,
        code=code,
        name=name,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _rewrite_campaign_channel_codes(
    db: Session, tenant_id: UUID, old_code: str, new_code: str | None
) -> None:
    """将活动 channels JSON 中的 old_code 替换为 new_code；new_code=None 表示移除。"""
    rows = (
        db.query(MarketingCampaign)
        .filter(
            MarketingCampaign.tenant_id == tenant_id,
            MarketingCampaign.deleted_at.is_(None),
        )
        .all()
    )
    for camp in rows:
        channels = list(camp.channels or [])
        if old_code not in channels:
            continue
        if new_code is None:
            camp.channels = [c for c in channels if c != old_code]
        else:
            camp.channels = [new_code if c == old_code else c for c in channels]


def update_channel(
    db: Session, ctx: TenantContext, row: CampaignChannel, data: CampaignChannelUpdate
) -> CampaignChannel:
    if data.name is not None:
        name = data.name.strip()
        if name != row.name:
            _check_unique(db, ctx.tenant_id, name=name, exclude_id=row.id)
            row.name = name
    if data.code is not None:
        code = _normalize_code(data.code, row.name)
        if code != row.code:
            _check_unique(db, ctx.tenant_id, code=code, exclude_id=row.id)
            old_code = row.code
            row.code = code
            _rewrite_campaign_channel_codes(db, ctx.tenant_id, old_code, code)
    if data.sort_order is not None:
        row.sort_order = data.sort_order
    if data.is_active is not None:
        row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return row


def delete_channel(db: Session, row: CampaignChannel) -> None:
    _rewrite_campaign_channel_codes(db, row.tenant_id, row.code, None)
    db.delete(row)
    db.commit()


def ensure_default_channels(db: Session, tenant_id: UUID) -> list[CampaignChannel]:
    existing = {
        c.code
        for c in db.query(CampaignChannel).filter(CampaignChannel.tenant_id == tenant_id).all()
    }
    if existing:
        return []
    created: list[CampaignChannel] = []
    for idx, (code, name) in enumerate(DEFAULT_CAMPAIGN_CHANNELS):
        row = CampaignChannel(
            tenant_id=tenant_id,
            code=code,
            name=name,
            sort_order=idx,
            is_active=True,
        )
        db.add(row)
        created.append(row)
    if created:
        db.commit()
        for row in created:
            db.refresh(row)
    return created


def seed_default_channels(db: Session, ctx: TenantContext) -> list[CampaignChannel]:
    existing = {c.code for c in list_channels(db, ctx.tenant_id)}
    created: list[CampaignChannel] = []
    for idx, (code, name) in enumerate(DEFAULT_CAMPAIGN_CHANNELS):
        if code in existing:
            continue
        created.append(
            create_channel(
                db,
                ctx,
                CampaignChannelCreate(code=code, name=name, sort_order=idx, is_active=True),
            )
        )
    return created
