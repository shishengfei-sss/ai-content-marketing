#!/usr/bin/env python3
"""P02-B 商家详情。对照 PRD 06#p02b-overview · #p02b-entitlements · #p02b-stores · #p02b-materials · #p02b-service · #p02b-note · #p02b-renewal · #p02b-audit。"""

from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "MerchantDetail.vue"


def login(phone: str, password: str, workspace_mode: str | None = None) -> str:
    body: dict = {"phone": phone, "password": password}
    if workspace_mode:
        body["workspace_mode"] = workspace_mode
    code, data = req("POST", "/auth/login", body=body)
    assert code == 200, data
    return data["access_token"]


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _err(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    d = data.get("detail", data)
    if isinstance(d, list):
        return " ".join(str(x) for x in d)
    return str(d)


def _pick_active_tenant(admin: str) -> str:
    code, data = req("GET", "/admin/shop/merchants", token=admin)
    assert code == 200, data
    preferred = None
    for item in data.get("items") or []:
        if not item.get("merchant_id") or item.get("onboarding_status") != "active":
            continue
        if item.get("entity_type") in ("enterprise", "individual_business"):
            return item["tenant_id"]
        preferred = preferred or item["tenant_id"]
    if preferred:
        return preferred
    raise RuntimeError("no active merchant for P02-B tests")


def _ensure_cs_user() -> str:
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
    from app.services.auth_service import hash_password

    phone = "13800000088"
    password = "cs12345678"
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="商城管家测试",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            )
            db.add(u)
        else:
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
            u.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def _ensure_finance_user() -> str:
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_FINANCE
    from app.services.auth_service import hash_password

    phone = "13800000077"
    password = "fin12345678"
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="商城财务测试",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_FINANCE,
            )
            db.add(u)
        else:
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_FINANCE
            u.hashed_password = hash_password(password)
            u.is_active = True
        db.commit()
    finally:
        db.close()
    return login(phone, password, "platform")


def _raw_contact_and_seed_ocr(tenant_id: str) -> str | None:
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantAccount, ShopOnboardingApplication

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, UUID(str(tenant_id))))
            .first()
        )
        if not m:
            return None
        app = None
        if m.onboarding_application_id:
            app = (
                db.query(ShopOnboardingApplication)
                .filter(uuid_eq(ShopOnboardingApplication.id, m.onboarding_application_id))
                .first()
            )
        if app is None:
            app = (
                db.query(ShopOnboardingApplication)
                .filter(uuid_eq(ShopOnboardingApplication.tenant_id, m.tenant_id))
                .order_by(ShopOnboardingApplication.submitted_at.desc())
                .first()
            )
        if app is not None:
            app.ocr_results = [
                {
                    "doc_type": "business_license",
                    "file_id": "verify-p02b-ocr",
                    "fields": {
                        "legal_name": app.legal_name or m.legal_name or "示例教育科技有限公司",
                        "unified_social_credit_code": app.unified_social_credit_code
                        or m.unified_social_credit_code
                        or "91110000MA01234567",
                        "legal_rep_name": app.legal_rep_name or m.legal_rep_name or "张三",
                    },
                    "confidence": 0.92,
                    "stub": True,
                }
            ]
            files = dict(app.qualification_files or {})
            files.setdefault("business_license", "verify-p02b-file")
            app.qualification_files = files
            info = dict(app.bank_account_info or {})
            info.setdefault("account_no", "6222020000008821")
            info.setdefault("bank_name", "验收银行")
            info.setdefault("account_name", "演示对公户")
            app.bank_account_info = info
            db.commit()
        return m.contact_mobile
    finally:
        db.close()


def _prepare_renewal(tenant_id: str) -> None:
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantAccount, ShopMerchantServiceLog

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, UUID(str(tenant_id))))
            .first()
        )
        if m:
            m.status = "active"
            m.plan_status = "expiring_soon"
            m.has_pending_renewal = False
            db.query(ShopMerchantServiceLog).filter(
                uuid_eq(ShopMerchantServiceLog.merchant_id, m.id),
                ShopMerchantServiceLog.type == "renewal_request",
                ShopMerchantServiceLog.status == "pending",
            ).update({"status": "cancelled"}, synchronize_session=False)
            db.commit()
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    src = WEB.read_text(encoding="utf-8") if WEB.is_file() else ""

    results.append(
        check(
            "VP02B-UI 六 Tab 与写操作栏位 TC-P02B-F01",
            _page_has(
                WEB,
                "#p02b-overview",
                "#p02b-entitlements",
                "#p02b-service",
                "#p02b-note",
                "#p02b-renewal",
                'label="概览"',
                'label="当前权益"',
                'label="旗下店铺"',
                'label="入驻材料"',
                'label="支付进件"',
                'label="服务记录"',
                'label="操作日志"',
                "生效中订阅",
                "合并后有效权益",
                "领权短信 / 月",
                "分组 · 无合并值",
                "toggleGroup",
                "写跟进",
                "申请续费",
                "跟进类型",
                "跟进时间",
                "下次跟进",
                "提交申请",
                "续费同档",
                "叠加加购",
                "主套餐升级",
                "套餐标价",
                "客户确认",
                "查看全部订阅",
                "换档升级",
                "本月 GMV",
                "店铺短码",
                "录入 / 更新",
                "搜索内容 / 操作人",
                "请填写跟进内容",
                "maskMobile",
                "OCR 识别快照",
                "revealField",
                'data-testid="btn-reveal-contact-mobile"',
                'data-testid="shop-merchant-detail"',
                'data-testid="shop-merchant-audit"',
                "全部动作",
                "搜索操作人 / 摘要",
            ),
            str(WEB),
        )
    )
    results.append(
        check(
            "VP02B-UI 详情头不设暂停入口",
            "doSuspend" not in src and "doResume" not in src and "doClose" not in src,
            "pause only on list",
        )
    )
    results.append(
        check(
            "VP02B-UI 操作日志独立表",
            "无独立审计表" not in src and 'data-testid="shop-merchant-audit"' in src,
            "audit tab",
        )
    )
    results.append(
        check(
            "VP02B-UI 经营联系人原文与掩码",
            "经营联系人" in src and "主体类型" in src and "统一社会信用代码" in src and "资质证照" in src,
            "labels",
        )
    )
    results.append(
        check(
            "VP02B-UI 商家编码非 UUID 派生",
            "detail.value?.merchant_code" in src and "slice(0, 12)" not in src,
            str(WEB),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    tenant_id = _pick_active_tenant(admin)
    raw_mobile = _raw_contact_and_seed_ocr(tenant_id)

    code, detail = req("GET", f"/admin/shop/merchants/{tenant_id}", token=admin)
    mats = (detail or {}).get("onboarding_materials") if isinstance(detail, dict) else None
    stores = (detail or {}).get("stores") if isinstance(detail, dict) else None
    results.append(
        check(
            "VP02B-F01 GET 详情聚合 TC-P02B-F01",
            code == 200
            and isinstance(detail, dict)
            and "stores" in detail
            and "service_logs" in detail
            and "operation_logs" in detail
            and "onboarding_status" in detail
            and isinstance(detail.get("month_gmv_cents"), int),
            f"{code} keys={list(detail)[:12] if isinstance(detail, dict) else detail}",
        )
    )
    mcode = str((detail or {}).get("merchant_code") or "") if isinstance(detail, dict) else ""
    results.append(
        check(
            "VP02B-N01 商家编码规则",
            bool(re.fullmatch(r"SH\d{12}", mcode)),
            f"{code} merchant_code={mcode}",
        )
    )
    code_q, listed = req("GET", f"/admin/shop/merchants?q={mcode}&page_size=20", token=admin)
    q_codes = {str(i.get("merchant_code") or "") for i in ((listed or {}).get("items") or [])}
    results.append(
        check(
            "VP02B-N02 按商家编码搜索",
            code_q == 200 and mcode in q_codes,
            f"{code_q} hit={mcode in q_codes}",
        )
    )
    results.append(
        check(
            "VP02B-GMV 店铺本月GMV与商品数",
            isinstance(stores, list)
            and all(isinstance(s.get("month_gmv_cents"), int) and isinstance(s.get("product_count"), int) for s in stores),
            f"stores={len(stores) if isinstance(stores, list) else stores}",
        )
    )
    masked_ok = True
    if raw_mobile and len(raw_mobile) == 11:
        expected = f"{raw_mobile[:3]}****{raw_mobile[-4:]}"
        got = (detail or {}).get("contact_mobile")
        masked_ok = got == expected and raw_mobile not in str(got)
    results.append(
        check(
            "VP02B-MASK GET 联系人手机脱敏",
            code == 200 and masked_ok,
            f"got={(detail or {}).get('contact_mobile') if isinstance(detail, dict) else detail}",
        )
    )
    results.append(
        check(
            "VP02B-OCR 材料含识别快照",
            isinstance(mats, dict)
            and isinstance(mats.get("ocr_results"), list)
            and any((x or {}).get("fields") for x in (mats.get("ocr_results") or [])),
            f"ocr={None if not isinstance(mats, dict) else len(mats.get('ocr_results') or [])}",
        )
    )

    code, empty_note = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/notes",
        token=admin,
        body={"type": "call", "content": "   "},
    )
    results.append(
        check(
            "VP02B-E01 空跟进 422 TC-P02B-E01",
            code == 422 and "跟进内容" in _err(empty_note),
            f"{code} {_err(empty_note)}",
        )
    )
    code, short_note = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/notes",
        token=admin,
        body={"type": "call", "content": "已电话沟通续费意向"},
    )
    results.append(
        check(
            "VP02B-E01b 短于10字 422 TC-P02B-E01",
            code == 422,
            f"{code} {_err(short_note)}",
        )
    )

    note_text = "已电话沟通续费意向，客户同意本周对公"
    code, note = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/notes",
        token=admin,
        body={
            "type": "call",
            "content": note_text,
            "payload_json": {"occurred_at": "2026-08-13 10:00:00"},
        },
    )
    results.append(
        check(
            "VP02B-F02 写跟进 201 TC-P02B-F02",
            code == 201 and (note or {}).get("type") == "call" and note_text in str((note or {}).get("content")),
            f"{code} {_err(note)}",
        )
    )

    code, logs = req(
        "GET",
        f"/admin/shop/merchants/{tenant_id}/service-logs?page=1&page_size=20&q={note_text[:8]}",
        token=admin,
    )
    items = (logs or {}).get("items") if isinstance(logs, dict) else []
    results.append(
        check(
            "VP02B-F02b 列表可见跟进 TC-P02B-F02",
            code == 200
            and isinstance(items, list)
            and any(note_text in str(x.get("content")) for x in items),
            f"{code} total={(logs or {}).get('total') if isinstance(logs, dict) else logs}",
        )
    )

    code, page10 = req(
        "GET",
        f"/admin/shop/merchants/{tenant_id}/service-logs?page=1&page_size=10",
        token=admin,
    )
    results.append(
        check(
            "VP02B-0c 服务记录分页",
            code == 200
            and isinstance(page10, dict)
            and page10.get("page_size") == 10
            and isinstance(page10.get("items"), list)
            and "total" in page10,
            f"{code} {page10 if not isinstance(page10, dict) else {k: page10.get(k) for k in ('total', 'page', 'page_size')}}",
        )
    )

    _prepare_renewal(tenant_id)
    code, ren = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests",
        token=admin,
        body={
            "purchase_mode": "renew_same",
            "target_plan": "basic",
            "quoted_amount_cents": 9900,
            "catalog_price_cents": 980000,
            "customer_confirmed": True,
            "content": "客户已确认对公续费请本周开通",
        },
    )
    results.append(
        check(
            "VP02B-R 申请续费 pending",
            code == 201 and (ren or {}).get("type") == "renewal_request" and (ren or {}).get("status") == "pending",
            f"{code} {_err(ren)}",
        )
    )

    cs_tok = _ensure_cs_user()
    code_cs, data_cs = req("GET", f"/admin/shop/merchants/{tenant_id}", token=cs_tok)
    results.append(
        check(
            "VP02B-CS 管家可读详情或超范围",
            code_cs in (200, 403),
            f"{code_cs} {_err(data_cs)}",
        )
    )

    code_rev, rev = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/reveal-sensitive",
        token=admin,
        body={"field": "contact_mobile"},
    )
    rev_ok = code_rev == 200 and isinstance(rev, dict) and rev.get("field") == "contact_mobile"
    if raw_mobile:
        rev_ok = rev_ok and rev.get("value") == raw_mobile
    results.append(
        check(
            "VP02B-REVEAL 运营揭露明文",
            rev_ok,
            f"{code_rev} {_err(rev) if not isinstance(rev, dict) else rev.get('value')}",
        )
    )
    code_logs, logs_after = req(
        "GET",
        f"/admin/shop/merchants/{tenant_id}",
        token=admin,
    )
    op_logs = (logs_after or {}).get("operation_logs") if isinstance(logs_after, dict) else []
    results.append(
        check(
            "VP02B-AUDIT 操作日志含查看经营联系人手机",
            code_logs == 200
            and any("查看经营联系人手机" in str((x or {}).get("summary") or "") for x in (op_logs or []))
            and any(
                "查看经营联系人手机" in str((x or {}).get("summary") or "")
                and (x or {}).get("action") == "查看敏感信息"
                and (x or {}).get("source") == "商家详情"
                for x in (op_logs or [])
            ),
            f"ops={len(op_logs) if isinstance(op_logs, list) else op_logs}",
        )
    )

    fin_tok = _ensure_finance_user()
    code_fin, data_fin = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/reveal-sensitive",
        token=fin_tok,
        body={"field": "contact_mobile"},
    )
    results.append(
        check(
            "VP02B-E02 无权 reveal 403 TC-P02B-E02",
            code_fin == 403 and "无查看权限" in _err(data_fin),
            f"{code_fin} {_err(data_fin)}",
        )
    )
    results.append(
        check(
            "VP02B-UI 管家走申请续费、运营走换档",
            'v-if="canWriteFollow && !canManage"' in src and "换档升级" in src and "申请续费" in src,
            "permission gates",
        )
    )
    results.append(
        check(
            "VP02B-UI 已用用量与分组折叠已接通",
            "已用用量暂无计量接口" not in src and "用量分组折叠本批未做" not in src and "ent-group" in src,
            "usage groups",
        )
    )

    code_sub, pack = req("GET", f"/admin/shop/merchants/{tenant_id}/subscriptions", token=admin)
    ent = (pack or {}).get("entitlements") if isinstance(pack, dict) else {}
    groups = (ent or {}).get("usage_groups") if isinstance(ent, dict) else None
    leaves = []
    if isinstance(groups, list):
        for g in groups:
            leaves.extend((g or {}).get("items") or [])
    shops = next((x for x in leaves if (x or {}).get("code") == "quota.max_shops"), None)
    sms = next((x for x in leaves if (x or {}).get("code") == "usage.sms_claim_send"), None)
    doudian = next((x for x in leaves if (x or {}).get("code") == "channel.doudian"), None)
    group_names = [(g or {}).get("group") for g in (groups or [])]
    results.append(
        check(
            "VP02B-USAGE 合并权益含已用与分组 TC-P02B-F01",
            code_sub == 200
            and isinstance(groups, list)
            and len(groups) >= 1
            and "店铺与商品" in group_names
            and isinstance(shops, dict)
            and shops.get("name") == "店铺数"
            and isinstance(shops.get("used"), int)
            and shops.get("used") >= 0
            and isinstance(sms, dict)
            and sms.get("name") == "领权短信 / 月"
            and isinstance(sms.get("used"), int)
            and isinstance(doudian, dict)
            and doudian.get("used_display") == "—"
            and shops.get("aggregate_mode_label") in ("取最大", "累加", "任一满足"),
            f"{code_sub} groups={group_names} shops={None if not shops else shops.get('used')}",
        )
    )

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'} {sum(1 for r in results if r)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
