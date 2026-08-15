#!/usr/bin/env python3
"""P11 订阅台账。对照 PRD 06#p11 · #p11-todo · #p11a · #p11b · #p11c · #p11d · #p11e。"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "Subscriptions.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AdminLayout.vue"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"
P01_SVC = API_ROOT / "app" / "services" / "shop" / "p01_analytics_service.py"


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
    raise RuntimeError("no active merchant for P11 tests")


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
                ShopMerchantServiceLog.status.in_(("pending", "processing")),
            ).update({"status": "cancelled"}, synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _set_merchant_status(tenant_id: str, status: str) -> None:
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantAccount

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, UUID(str(tenant_id))))
            .first()
        )
        if m:
            m.status = status
            db.commit()
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP11-UI 订阅台账页 TC-P11-L01",
            _page_has(
                WEB,
                "#p11",
                "#p11-todo",
                "待处理续费申请",
                "开通单号",
                "商家",
                "套餐",
                "订阅类型",
                "生效起",
                "生效止",
                "开通时间",
                "开通人",
                "人工开通（主套餐/叠加）",
                "列设置",
                "导出",
                "订阅单号 / 商家名",
                "确认开通",
                "确认开通并结案",
                "暂存处理中",
                "合并预览（只读）",
                "确认换档",
                "套餐标价（只读）",
                "应付金额",
                "换档金额",
                "管家备注（只读）",
                "运营备注（选填）",
            )
            and _page_has(LAYOUT, "订阅台账", "/admin/shop/subscriptions")
            and _page_has(ROUTER, "shop/subscriptions", "Subscriptions")
            and _page_has(P01_SVC, "/admin/shop/subscriptions?todo=renewal"),
            str(WEB),
        )
    )
    results.append(
        check(
            "VP11-UI 导出任务弹窗 #p11",
            _page_has(
                WEB,
                "当前筛选",
                "列配置",
                "导出任务",
                "createShopSubscriptionExport",
                "getShopSubscriptionExportFile",
            )
            and "ElMessageBox" not in WEB.read_text(encoding="utf-8"),
            "P11 export dropdown + dialog",
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    tenant_id = _pick_active_tenant(admin)
    today = date.today()
    expires = today + timedelta(days=365) - timedelta(days=1)

    code, empty = req(
        "GET",
        "/admin/shop/subscriptions?q=zzzznotexist-p11-xyz&page=1&page_size=20",
        token=admin,
    )
    results.append(
        check(
            "VP11-0c 空搜不 500 TC-P11-L01-S2",
            code == 200 and isinstance((empty or {}).get("items"), list),
            f"{code} {empty}",
        )
    )

    code, csv_body = req("GET", "/admin/shop/subscriptions/export", token=admin)
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VP11-0d 导出 CSV",
            code == 200 and "开通单号" in csv_text and "开通人" in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )
    code, task = req("POST", "/admin/shop/subscriptions/export", token=admin, body={})
    results.append(
        check(
            "VP11-X1 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "subscriptions"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req(
            "GET", f"/admin/shop/subscriptions/export-tasks/{task_id}/file", token=admin
        )
        results.append(
            check(
                "VP11-X2 任务文件可下载",
                code == 200 and "开通单号" in str(file_csv) and "开通人" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VP11-X2 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/admin/shop/subscriptions/export",
        token=admin,
        body={"columns": ["subscription_no", "merchant_name"]},
    )
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/admin/shop/subscriptions/export-tasks/{cols_task['id']}/file",
            token=admin,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        results.append(
            check(
                "VP11-X3 列配置导出表头",
                code2 == 200 and "开通单号" in head and "商家" in head and "开通人" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VP11-X3 列配置导出表头", False, f"{code} {cols_task}"))

    code, sub = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "catalog_price_cents": 980000,
            "paid_amount_cents": 9900,
            "source": "manual",
            "remark": "对公已到账",
        },
    )
    code_e, ent = req("GET", f"/admin/shop/merchants/{tenant_id}/entitlements", token=admin)
    results.append(
        check(
            "VP11-F01 人工开通 basic TC-P11-F01",
            code == 200
            and (sub or {}).get("status") == "active"
            and (sub or {}).get("plan_code") == "basic"
            and (sub or {}).get("paid_amount_cents") == 9900
            and code_e == 200
            and bool((ent or {}).get("quotas") or (ent or {}).get("features")),
            f"{code} {_err(sub)} ent={code_e}",
        )
    )

    sample = sub if isinstance(sub, dict) else {}
    results.append(
        check(
            "VP11-0b 开通默认列 TC-P11-L01",
            bool(sample.get("subscription_no"))
            and "merchant_display_name" in sample
            and "plan_name" in sample
            and sample.get("plan_type_label") == "主套餐"
            and "operator_name" in sample
            and sample.get("status_label") == "生效中"
            and "has_pending_renewal" in sample
            and "created_at" in sample,
            f"keys={list(sample)[:16]}",
        )
    )

    code_ps, stack_prev = req(
        "GET",
        f"/admin/shop/merchants/{tenant_id}/entitlements?preview_plan=addon_sms_500&preview_mode=stack",
        token=admin,
    )
    stack_text = str((stack_prev or {}).get("preview_text") or "")
    stack_lines = (stack_prev or {}).get("preview_lines") or []
    results.append(
        check(
            "VP11-M1 叠加合并预览 TC-P11-F01",
            code_ps == 200
            and (stack_prev or {}).get("preview_mode") == "stack"
            and (stack_prev or {}).get("preview_plan") == "addon_sms_500"
            and ("累加" in stack_text or bool(stack_lines)),
            f"{code_ps} {stack_text[:80]} {_err(stack_prev)}",
        )
    )
    code_prp, rep_prev = req(
        "GET",
        f"/admin/shop/merchants/{tenant_id}/entitlements?preview_plan=flagship&preview_mode=replace",
        token=admin,
    )
    rep_text = str((rep_prev or {}).get("preview_text") or "")
    results.append(
        check(
            "VP11-M2 换档合并预览 TC-P11-F01",
            code_prp == 200
            and (rep_prev or {}).get("preview_mode") == "replace"
            and ("∞" in rep_text or "取最大值" in rep_text),
            f"{code_prp} {rep_text[:80]} {_err(rep_prev)}",
        )
    )

    cs_tok = _ensure_cs_user()
    code_cs, data_cs = req(
        "POST",
        "/admin/shop/subscriptions",
        token=cs_tok,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "paid_amount_cents": 0,
            "remark": "管家不应开通",
        },
    )
    results.append(
        check(
            "VP11-E01 管家开通 403 TC-P11-E01",
            code_cs == 403,
            f"{code_cs} {_err(data_cs)}",
        )
    )
    results.append(
        check(
            "VP11-E01b UI 无开通按钮（管家无 manage）",
            'v-if="canManage"' in WEB.read_text(encoding="utf-8")
            and "人工开通（主套餐/叠加）" in WEB.read_text(encoding="utf-8"),
            "canManage gate",
        )
    )

    _set_merchant_status(tenant_id, "closed")
    code_c, data_c = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "paid_amount_cents": 0,
            "remark": "closed should fail",
        },
    )
    results.append(
        check(
            "VP11-E02 closed 商家 422 TC-P11-E02",
            code_c == 422 and "清退" in str(data_c),
            f"{code_c} {_err(data_c)}",
        )
    )
    _set_merchant_status(tenant_id, "active")

    _prepare_renewal(tenant_id)
    code_r, ren_req = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests",
        token=admin,
        body={
            "purchase_mode": "replace",
            "target_plan": "basic",
            "quoted_amount_cents": 9900,
            "catalog_price_cents": 980000,
            "customer_confirmed": True,
            "content": "客户已确认对公续费请本周开通",
        },
    )
    log_id = (ren_req or {}).get("id")
    results.append(
        check(
            "VP11-R0 提交续费申请",
            code_r in (200, 201) and bool(log_id),
            f"{code_r} {_err(ren_req)}",
        )
    )

    code_empty, empty_cancel = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{log_id}/cancel",
        token=admin,
    )
    results.append(
        check(
            "VP11-C01 取消原因空 422",
            code_empty == 422 and "取消原因" in str(empty_cancel),
            f"{code_empty} {_err(empty_cancel)}",
        )
    )
    code_short, short_cancel = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{log_id}/cancel?note=abc",
        token=admin,
    )
    results.append(
        check(
            "VP11-C02 取消原因过短 422",
            code_short == 422 and "取消原因" in str(short_cancel),
            f"{code_short} {_err(short_cancel)}",
        )
    )

    code_pr, pending = req("GET", "/admin/shop/merchants/pending-renewals", token=admin)
    pending_items = (pending or {}).get("items") or []
    hit = next((x for x in pending_items if str(x.get("service_log_id")) == str(log_id)), None)
    results.append(
        check(
            "VP11-TODO 待办含金额快照",
            code_pr == 200
            and hit is not None
            and hit.get("quoted_amount_cents") == 9900
            and hit.get("catalog_price_cents") == 980000,
            f"{code_pr} hit={hit}",
        )
    )

    code_park, parked = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{log_id}/mark-processing",
        token=admin,
    )
    results.append(
        check(
            "VP11-P1 暂存处理中 pending→processing",
            code_park == 200 and (parked or {}).get("status") == "processing",
            f"{code_park} {_err(parked)}",
        )
    )
    code_pr2, pending2 = req("GET", "/admin/shop/merchants/pending-renewals", token=admin)
    hit2 = next(
        (x for x in ((pending2 or {}).get("items") or []) if str(x.get("service_log_id")) == str(log_id)),
        None,
    )
    results.append(
        check(
            "VP11-P2 处理中仍在待办",
            code_pr2 == 200 and hit2 is not None and hit2.get("status") == "processing",
            f"{code_pr2} hit={hit2}",
        )
    )
    code_cx, cx_body = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{log_id}/cancel?note=客户改期下周再开",
        token=admin,
    )
    results.append(
        check(
            "VP11-P3 处理中取消须先退回 422",
            code_cx == 422 and "退回" in str(cx_body),
            f"{code_cx} {_err(cx_body)}",
        )
    )
    code_rv, reverted = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{log_id}/revert-pending",
        token=admin,
    )
    results.append(
        check(
            "VP11-P4 退回待处理",
            code_rv == 200 and (reverted or {}).get("status") == "pending",
            f"{code_rv} {_err(reverted)}",
        )
    )
    code_park2, parked2 = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{log_id}/mark-processing",
        token=admin,
    )
    results.append(
        check(
            "VP11-P5 再暂存后可从处理中结案",
            code_park2 == 200 and (parked2 or {}).get("status") == "processing",
            f"{code_park2} {_err(parked2)}",
        )
    )

    code_done, opened = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "catalog_price_cents": 980000,
            "paid_amount_cents": 9900,
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "remark": "对公已到账",
            "source": "renew",
            "renewal_request_id": log_id,
        },
    )
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantServiceLog

    db = SessionLocal()
    try:
        log = (
            db.query(ShopMerchantServiceLog)
            .filter(uuid_eq(ShopMerchantServiceLog.id, UUID(str(log_id))))
            .first()
            if log_id
            else None
        )
        log_status = log.status if log else None
        related = str(log.related_subscription_id) if log and log.related_subscription_id else None
    finally:
        db.close()
    results.append(
        check(
            "VP11-R1 处理续费结案 processing→completed",
            code_done == 200
            and (opened or {}).get("status") == "active"
            and log_status == "completed"
            and related == str((opened or {}).get("id")),
            f"{code_done} status={log_status} related={related} {_err(opened)}",
        )
    )

    merchant = login("13900000099", "test123456", "merchant")
    code, exp_forbidden = req("POST", "/admin/shop/subscriptions/export", token=merchant, body={})
    results.append(
        check(
            "VP11-P01b 商家 POST 导出 403",
            code in (401, 403),
            f"{code} {exp_forbidden}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP11 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
