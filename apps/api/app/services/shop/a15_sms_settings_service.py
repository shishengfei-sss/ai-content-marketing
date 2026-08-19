"""A15-S 短信与领权。对照 PRD 01#a15-sms · §8.7.3 GET/PUT /shop/settings/sms。"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    PlatformSmsSignature,
    PlatformSmsTemplate,
    ShopMerchantAccount,
    ShopSmsLog,
    ShopTenantSettings,
)
from app.services.shop import a18_service
from app.services.shop.entitlement_service import UNLIMITED, get_merged_entitlements

HTTPS_RE = re.compile(r"^https://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
MOBILE_RE = re.compile(r"^1\d{10}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount | None:
    return (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )


def _ensure_settings(db: Session, tenant_id: UUID) -> ShopTenantSettings:
    row = (
        db.query(ShopTenantSettings)
        .filter(uuid_eq(ShopTenantSettings.tenant_id, tenant_id))
        .first()
    )
    if row:
        return row
    row = ShopTenantSettings(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        claim_expire_days=7,
    )
    db.add(row)
    db.flush()
    return row


def _mask_template_code(code: str | None) -> str | None:
    if not code:
        return None
    if len(code) <= 8:
        return code[:4] + "****"
    return code[:8] + "****"


def _assignment_ready(sig: PlatformSmsSignature | None, tpl: PlatformSmsTemplate | None) -> bool:
    return (
        sig is not None
        and tpl is not None
        and sig.status == "approved"
        and tpl.status == "approved"
    )


def _usage_block(db: Session, tenant_id: UUID) -> dict[str, Any]:
    used = a18_service.count_month_sms(db, tenant_id)
    ents = get_merged_entitlements(db, tenant_id)
    usage_limits = ents.get("usage_limits") or {}
    limit = usage_limits.get("usage.sms_claim_send")
    if limit is None and "usage.sms_claim_send" not in usage_limits:
        limit = UNLIMITED
    return {
        "claim_sms_month": {
            "used": used,
            "limit": "unlimited" if limit == UNLIMITED else limit,
        }
    }


def _quota_remaining(db: Session, tenant_id: UUID) -> int | None:
    """剩余条数；None=不限；0=不足。"""
    block = _usage_block(db, tenant_id)["claim_sms_month"]
    lim = block["limit"]
    used = int(block["used"] or 0)
    if lim == "unlimited" or lim is None:
        return None
    try:
        return max(0, int(lim) - used)
    except (TypeError, ValueError):
        return None


def get_sms_settings(db: Session, ctx: TenantContext) -> dict[str, Any]:
    merchant = _merchant(db, ctx.tenant_id)
    if not merchant:
        return {
            "state": "not_onboarded",
            "config_status": "unassigned",
            "config_status_label": "待平台分配",
            "can_save": False,
            "sms_signature": None,
            "sms_signature_status": "unassigned",
            "claim_template_name": None,
            "claim_template_id": None,
            "claim_template_code_masked": None,
            "claim_template_status": "unassigned",
            "claim_landing_base": None,
            "claim_expire_days": 7,
            "domain_verified": False,
            "usage": {"claim_sms_month": {"used": 0, "limit": None}},
            "hint": "请先完成入驻",
        }

    row = _ensure_settings(db, ctx.tenant_id)
    sig = None
    tpl = None
    if row.sms_signature_id:
        sig = (
            db.query(PlatformSmsSignature)
            .filter(uuid_eq(PlatformSmsSignature.id, row.sms_signature_id))
            .first()
        )
    if row.claim_template_id:
        tpl = (
            db.query(PlatformSmsTemplate)
            .filter(uuid_eq(PlatformSmsTemplate.id, row.claim_template_id))
            .first()
        )

    ready = _assignment_ready(sig, tpl)
    config_status = "assigned" if ready else "unassigned"
    domain_ok = bool(
        row.claim_landing_base
        and row.domain_verified_base
        and row.domain_verified_base.rstrip("/") == row.claim_landing_base.rstrip("/")
        and row.domain_verified_at
    )
    return {
        "state": "onboarded",
        "config_status": config_status,
        "config_status_label": "签名已分配" if ready else "待平台分配",
        "can_save": ready,
        "sms_signature": sig.content if sig else None,
        "sms_signature_status": sig.status if sig else "unassigned",
        "claim_template_name": tpl.name if tpl else None,
        "claim_template_id": str(tpl.id) if tpl else None,
        "claim_template_code_masked": _mask_template_code(tpl.template_code) if tpl else None,
        "claim_template_status": tpl.status if tpl else "unassigned",
        "claim_landing_base": row.claim_landing_base,
        "claim_expire_days": row.claim_expire_days or 7,
        "domain_verified": domain_ok,
        "usage": _usage_block(db, ctx.tenant_id),
        "hint": (
            "签名/模板由平台分配，本页只配领权域名与过期天数。"
            if ready
            else "待平台配置签名与模板；可联系管家。保存已禁用。"
        ),
    }


def _normalize_base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        raise HTTPException(status_code=422, detail="请填写领权链接域名")
    if not u.lower().startswith("https://"):
        raise HTTPException(status_code=422, detail="领权域名须为 HTTPS")
    if not HTTPS_RE.match(u):
        raise HTTPException(status_code=422, detail="领权域名格式无效")
    return u


def check_domain(db: Session, ctx: TenantContext, *, url: str) -> dict[str, Any]:
    base = _normalize_base(url)
    fake = os.getenv("FORCE_FAKE_PLATFORM_LLM", "").strip() in ("1", "true", "True")
    host = base.split("://", 1)[-1].split("/", 1)[0].lower()
    reachable = False
    detail = ""
    if fake or host.endswith(".local") or host in ("localhost", "127.0.0.1"):
        reachable = True
        detail = "沙箱/本地域名视为可达"
    else:
        try:
            req = Request(base + "/", method="HEAD")
            req.add_header("User-Agent", "ai-content-marketing-claim-check/1.0")
            with urlopen(req, timeout=5) as resp:  # noqa: S310 — merchant-provided HTTPS URL check
                reachable = 200 <= getattr(resp, "status", 200) < 500
                detail = f"HTTP {getattr(resp, 'status', '?')}"
        except URLError as e:
            # 部分站点拒 HEAD，再试 GET
            try:
                req = Request(base + "/", method="GET")
                req.add_header("User-Agent", "ai-content-marketing-claim-check/1.0")
                with urlopen(req, timeout=5) as resp:  # noqa: S310
                    reachable = 200 <= getattr(resp, "status", 200) < 500
                    detail = f"GET HTTP {getattr(resp, 'status', '?')}"
            except Exception as e2:  # noqa: BLE001
                reachable = False
                detail = str(e2) or str(e)
        except Exception as e:  # noqa: BLE001
            reachable = False
            detail = str(e)

    if not reachable:
        raise HTTPException(status_code=422, detail="域名不可达")

    row = _ensure_settings(db, ctx.tenant_id)
    row.domain_verified_at = _now()
    row.domain_verified_base = base
    db.commit()
    return {"ok": True, "claim_landing_base": base, "detail": detail}


def update_sms_settings(
    db: Session,
    ctx: TenantContext,
    *,
    claim_landing_base: str,
    claim_expire_days: int,
) -> dict[str, Any]:
    merchant = _merchant(db, ctx.tenant_id)
    if not merchant:
        raise HTTPException(status_code=422, detail="请先完成入驻")
    row = _ensure_settings(db, ctx.tenant_id)
    sig = (
        db.query(PlatformSmsSignature)
        .filter(uuid_eq(PlatformSmsSignature.id, row.sms_signature_id))
        .first()
        if row.sms_signature_id
        else None
    )
    tpl = (
        db.query(PlatformSmsTemplate)
        .filter(uuid_eq(PlatformSmsTemplate.id, row.claim_template_id))
        .first()
        if row.claim_template_id
        else None
    )
    if not _assignment_ready(sig, tpl):
        raise HTTPException(status_code=422, detail="待平台配置")

    if not isinstance(claim_expire_days, int) or claim_expire_days < 1 or claim_expire_days > 30:
        raise HTTPException(status_code=422, detail="领权过期天数须为 1–30")

    base = _normalize_base(claim_landing_base)
    if (
        not row.domain_verified_at
        or not row.domain_verified_base
        or row.domain_verified_base.rstrip("/") != base
    ):
        raise HTTPException(status_code=422, detail="域名不可达")

    row.claim_landing_base = base
    row.claim_expire_days = claim_expire_days
    db.commit()
    return get_sms_settings(db, ctx)


def send_test_sms(db: Session, ctx: TenantContext, *, mobile: str) -> dict[str, Any]:
    merchant = _merchant(db, ctx.tenant_id)
    if not merchant:
        raise HTTPException(status_code=422, detail="请先完成入驻")
    row = _ensure_settings(db, ctx.tenant_id)
    sig = (
        db.query(PlatformSmsSignature)
        .filter(uuid_eq(PlatformSmsSignature.id, row.sms_signature_id))
        .first()
        if row.sms_signature_id
        else None
    )
    tpl = (
        db.query(PlatformSmsTemplate)
        .filter(uuid_eq(PlatformSmsTemplate.id, row.claim_template_id))
        .first()
        if row.claim_template_id
        else None
    )
    if not _assignment_ready(sig, tpl):
        raise HTTPException(status_code=422, detail="模板未就绪")

    m = (mobile or "").strip()
    if not MOBILE_RE.match(m):
        raise HTTPException(status_code=422, detail="请填写正确的手机号")

    rem = _quota_remaining(db, ctx.tenant_id)
    if rem is not None and rem <= 0:
        raise HTTPException(status_code=422, detail="额度不足")

    base = (row.claim_landing_base or "").rstrip("/") or "https://shop.example.local"
    link = f"{base}/mp/claim/test-token"
    content = f"{sig.content}【测试】领权链接：{link}（模板 {tpl.template_code}）"
    sms = ShopSmsLog(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=None,
        buyer_mobile=m,
        type="claim_link_test",
        content=content,
        status="sent",
        provider_msg_id=f"test_{uuid.uuid4().hex[:12]}",
        sent_at=_now(),
    )
    db.add(sms)
    db.commit()
    return {
        "ok": True,
        "mobile_masked": m[:3] + "****" + m[-4:],
        "message": "测试短信已发送（占用本月额度）",
        "usage": _usage_block(db, ctx.tenant_id),
    }


def get_claim_expire_days(db: Session, tenant_id: UUID) -> int:
    row = (
        db.query(ShopTenantSettings)
        .filter(uuid_eq(ShopTenantSettings.tenant_id, tenant_id))
        .first()
    )
    days = int(row.claim_expire_days) if row and row.claim_expire_days else 7
    return max(1, min(30, days))


def get_claim_landing_base(db: Session, tenant_id: UUID) -> str | None:
    row = (
        db.query(ShopTenantSettings)
        .filter(uuid_eq(ShopTenantSettings.tenant_id, tenant_id))
        .first()
    )
    return row.claim_landing_base if row else None


def build_claim_h5_link(db: Session, tenant_id: UUID, token: str) -> str:
    """M14 领权页。对照 H5 `#/pages/shop/claim`；无落地域名时回退本地 H5。"""
    from app.config import settings

    path = f"/pages/shop/claim?token={token}&tenant_id={tenant_id}"
    landing = (get_claim_landing_base(db, tenant_id) or "").rstrip("/")
    base = landing or (settings.SHOP_H5_DEMO_BASE or "http://localhost:5174").rstrip("/")
    return f"{base}/#{path}"


def force_assign_sms_for_tests(
    db: Session,
    tenant_id: UUID,
    *,
    signature_content: str = "【智学课堂】",
    template_name: str = "抖店领权默认",
    template_code: str = "SMS_28470001",
) -> ShopTenantSettings:
    """联测：模拟 P12 分配签名+模板。"""
    sig = PlatformSmsSignature(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="联测签名",
        content=signature_content,
        status="approved",
        provider_sig_id=f"stub_sig_{uuid.uuid4().hex[:8]}",
    )
    db.add(sig)
    db.flush()
    tpl = PlatformSmsTemplate(
        id=uuid.uuid4(),
        name=template_name,
        template_code=template_code,
        purpose="claim_link",
        status="approved",
        signature_id=sig.id,
    )
    db.add(tpl)
    db.flush()
    row = _ensure_settings(db, tenant_id)
    row.sms_signature_id = sig.id
    row.claim_template_id = tpl.id
    db.commit()
    db.refresh(row)
    return row
