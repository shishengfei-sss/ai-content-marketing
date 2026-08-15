#!/usr/bin/env python3
"""P07 违规稽查。对照 PRD 06#p07 · #p07a · #p07b · #p07c · §8.14.4。"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import _get_test_client, check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "ModerationCases.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AdminLayout.vue"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"
DASH = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "PlatformDashboard.vue"


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


def _prepare(tenant_id: str):
    from app.database import SessionLocal
    from app.models.shop import ShopChannelMapping, ShopOnboardingApplication, ShopProduct, ShopStore
    from app.services.shop import p07_moderation_service as p07svc

    db = SessionLocal()
    try:
        tid = UUID(tenant_id)
        shops = list(db.query(ShopStore).filter(ShopStore.tenant_id.isnot(None)).all())
        apps = list(db.query(ShopOnboardingApplication).all())

        def _tid_key(val) -> str:
            return str(getattr(val, "hex", val) or "").replace("-", "")

        apps_by_tid = {_tid_key(a.tenant_id): a for a in apps}
        shop = next((s for s in shops if _tid_key(s.tenant_id) == tid.hex), None)
        if shop is None:
            shop = next((s for s in shops if _tid_key(s.tenant_id) in apps_by_tid), None)
        if shop is None:
            shop = shops[0] if shops else None
        assert shop is not None, "no shop for merchant"
        shop_id = shop.id if isinstance(shop.id, UUID) else UUID(str(shop.id))
        tid = shop.tenant_id if isinstance(shop.tenant_id, UUID) else UUID(str(shop.tenant_id))
        product = ShopProduct(
            id=uuid.uuid4(),
            tenant_id=tid,
            shop_id=shop_id,
            name=f"P07抽检课-{uuid.uuid4().hex[:6]}",
            type="course",
            status="on_sale",
            price_cents=9900,
            extra={},
        )
        db.add(product)
        db.flush()
        mapping = ShopChannelMapping(
            id=uuid.uuid4(),
            tenant_id=tid,
            shop_id=shop_id,
            product_id=product.id,
            channel="douyin",
            channel_product_id=f"dy_p07_{uuid.uuid4().hex[:8]}",
            status="mapped",
        )
        db.add(mapping)
        db.commit()
        product_case = p07svc.seed_case(
            db,
            tenant_id=tid,
            shop_id=shop_id,
            case_type="product_violation",
            object_type="product",
            object_ref=product.name,
            source="ops_manual",
            product_id=product.id,
        )
        complaint = p07svc.seed_case(
            db,
            tenant_id=tid,
            shop_id=shop_id,
            case_type="buyer_complaint",
            object_type="order",
            object_ref=f"订单 #{uuid.uuid4().hex[:4].upper()}",
            source="buyer_report",
        )
        atts = p07svc.seed_sample_attachments(db, complaint.id)
        flag_product = ShopProduct(
            id=uuid.uuid4(),
            tenant_id=tid,
            shop_id=shop_id,
            name=f"保证成交旗标课-{uuid.uuid4().hex[:4]}",
            type="course",
            status="pending_review",
            price_cents=19900,
            extra={},
        )
        db.add(flag_product)
        db.flush()
        f6 = p07svc.ingest_from_auto_review(
            db,
            product=flag_product,
            review_id=None,
            auto_result="flag",
            auto_flags=[{"rule": "exaggerated_claim", "level": "flag", "message": "夸大承诺"}],
        )
        db.commit()
        return {
            "product_id": str(product.id),
            "mapping_id": str(mapping.id),
            "product_case_id": str(product_case.id),
            "complaint_id": str(complaint.id),
            "chat_file_id": atts[0]["file_id"],
            "snap_file_id": atts[1]["file_id"],
            "f6_case_id": str(f6.id) if f6 else None,
            "product_name": product.name,
        }
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP07-UI 违规稽查页 TC-P07-L01",
            _page_has(
                WEB,
                "#p07",
                "待处理",
                "处理中",
                "本月已结案",
                "本月强制下架",
                "全部工单",
                "搜索对象 / 商家",
                "下架原因类型",
                "确认下架并更新工单",
                "结案说明",
                "是否通知商家",
                "列设置",
                "类型",
                "对象",
                "商家",
                "上报时间",
                "附件（只读）",
                "previewAttachment",
            )
            and "本批无文件预览" not in WEB.read_text(encoding="utf-8")
            and _page_has(LAYOUT, "违规稽查", "/admin/shop/moderation")
            and _page_has(ROUTER, "shop/moderation", "ModerationCases")
            and _page_has(DASH, "/admin/shop/moderation")
            and "违规稽查页尚未交付" not in DASH.read_text(encoding="utf-8"),
            str(WEB),
        )
    )
    results.append(
        check(
            "VP07-UI 导出任务弹窗 #p07",
            _page_has(
                WEB,
                "当前筛选",
                "列配置",
                "导出任务",
                "createShopModerationExport",
                "getShopModerationExportFile",
            )
            and "ElMessageBox" not in WEB.read_text(encoding="utf-8"),
            "P07 export dropdown + dialog",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    admin = login("13800000000", "admin123456", "platform")
    seeded = _prepare(tenant_id)
    pid = seeded["product_id"]
    product_case_id = seeded["product_case_id"]
    complaint_id = seeded["complaint_id"]
    mapping_id = seeded["mapping_id"]
    chat_file_id = seeded["chat_file_id"]
    snap_file_id = seeded["snap_file_id"]

    code, summary = req("GET", "/admin/shop/moderation-cases/summary", token=admin)
    code2, p01 = req("GET", "/admin/shop/analytics/summary", token=admin)
    p01_open = (p01 or {}).get("widgets", {}).get("open_moderation_cases")
    results.append(
        check(
            "VP07-0 summary 与 P01 同源 TC-P07-L01",
            code == 200
            and code2 == 200
            and summary.get("open_count") == p01_open
            and summary.get("open_count") == (summary.get("pending_count") or 0)
            + (summary.get("processing_count") or 0),
            f"sum={summary} p01={p01_open}",
        )
    )

    code, listing = req("GET", "/admin/shop/moderation-cases?page=1&page_size=20", token=admin)
    items = (listing or {}).get("items") or []
    sample = next((x for x in items if x.get("id") == product_case_id), items[0] if items else {})
    results.append(
        check(
            "VP07-0b 列表默认列 TC-P07-L01",
            code == 200
            and "case_type_label" in sample
            and "object_ref" in sample
            and "merchant_name" in sample
            and "reported_at" in sample
            and "status_label" in sample
            and "assignee_name" in sample,
            f"{code} n={len(items)}",
        )
    )
    results.append(
        check(
            "VP07-0c 空搜不 500 TC-P07-L01-S2",
            req("GET", "/admin/shop/moderation-cases?q=ZZZNONE", token=admin)[0] == 200,
            "",
        )
    )

    code, detail = req("GET", f"/admin/shop/moderation-cases/{complaint_id}", token=admin)
    atts = (detail or {}).get("attachments") or []
    kinds = {a.get("kind") for a in atts if isinstance(a, dict)}
    labels = {a.get("kind_label") for a in atts if isinstance(a, dict)}
    results.append(
        check(
            "VP07-C 详情栏位与附件 TC-P07-L01",
            code == 200
            and (detail.get("case_no") or "").startswith("WG")
            and detail.get("case_type_label") == "买家投诉"
            and detail.get("merchant_name")
            and isinstance(detail.get("timeline"), list)
            and len(atts) >= 2
            and "chat_screenshot" in kinds
            and "order_snapshot" in kinds
            and "聊天截图" in labels
            and "订单快照" in labels,
            f"{code} no={detail.get('case_no') if isinstance(detail, dict) else detail} n_att={len(atts)}",
        )
    )

    client = _get_test_client()
    dl = client.get(
        f"/api/v1/admin/shop/moderation-cases/{complaint_id}/attachments/{chat_file_id}",
        headers={"Authorization": f"Bearer {admin}"},
    )
    dl2 = client.get(
        f"/api/v1/admin/shop/moderation-cases/{complaint_id}/attachments/{snap_file_id}",
        headers={"Authorization": f"Bearer {admin}"},
    )
    results.append(
        check(
            "VP07-C1 附件可预览",
            dl.status_code == 200
            and len(dl.content) > 4
            and dl.content.startswith(b"\x89PNG")
            and dl2.status_code == 200
            and b"order_no" in dl2.content,
            f"{dl.status_code}/{dl2.status_code}",
        )
    )
    empty_up = client.post(
        f"/api/v1/admin/shop/moderation-cases/{complaint_id}/attachments",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("empty.png", b"", "image/png")},
        params={"kind": "chat_screenshot"},
    )
    results.append(
        check(
            "VP07-C2 空文件不可上传",
            empty_up.status_code == 422,
            str(empty_up.status_code),
        )
    )
    up = client.post(
        f"/api/v1/admin/shop/moderation-cases/{complaint_id}/attachments",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("聊天截图2.png", b"\x89PNG\r\n\x1a\nfake2", "image/png")},
        params={"kind": "chat_screenshot"},
    )
    extra = up.json() if up.headers.get("content-type", "").startswith("application/json") else {}
    extra_id = extra.get("file_id") if isinstance(extra, dict) else None
    extra_dl = (
        client.get(
            f"/api/v1/admin/shop/moderation-cases/{complaint_id}/attachments/{extra_id}",
            headers={"Authorization": f"Bearer {admin}"},
        )
        if extra_id
        else None
    )
    results.append(
        check(
            "VP07-C3 真实上传并可预览",
            up.status_code == 200 and bool(extra_id) and extra_dl is not None and extra_dl.status_code == 200,
            f"{up.status_code} {extra}",
        )
    )

    code, empty = req(
        "POST",
        f"/admin/shop/moderation-cases/{product_case_id}/force-off-sale",
        token=admin,
        body={"reason_type": "false_ad", "reason": ""},
    )
    results.append(
        check(
            "VP07-E01 原因空 422 TC-P07-E01",
            code == 422 and ("说明" in _err(empty) or "原因" in _err(empty)),
            f"{code} {_err(empty)}",
        )
    )

    code, off = req(
        "POST",
        f"/admin/shop/moderation-cases/{product_case_id}/force-off-sale",
        token=admin,
        body={"reason_type": "false_ad", "reason": "抽检违规宣传用语"},
    )
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopChannelAuditLog, ShopChannelMapping, ShopProduct

    db = SessionLocal()
    try:
        product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUID(pid))).first()
        mapping = (
            db.query(ShopChannelMapping).filter(uuid_eq(ShopChannelMapping.id, UUID(mapping_id))).first()
        )
        audits = (
            db.query(ShopChannelAuditLog)
            .filter(uuid_eq(ShopChannelAuditLog.product_id, UUID(pid)))
            .all()
        )
        blocked_audit = any((a.event == "listing_blocked") for a in audits)
        product_status = product.status if product else None
        mapping_status = mapping.status if mapping else None
    finally:
        db.close()
    results.append(
        check(
            "VP07-F01 强制下架 TC-P07-F01",
            code == 200
            and off.get("status") == "processing"
            and off.get("force_off_at")
            and product_status == "off_sale"
            and mapping_status == "blocked"
            and blocked_audit,
            f"{code} case={off.get('status')} product={product_status} map={mapping_status} audit={blocked_audit}",
        )
    )

    code, taken = req(
        "POST",
        f"/admin/shop/moderation-cases/{complaint_id}/take",
        token=admin,
        body={},
    )
    results.append(
        check(
            "VP07-F02a 投诉接单 TC-P07-F02",
            code == 200 and taken.get("status") == "processing" and not taken.get("is_product_case"),
            f"{code} {taken.get('status') if isinstance(taken, dict) else taken}",
        )
    )
    code, closed = req(
        "POST",
        f"/admin/shop/moderation-cases/{complaint_id}/close",
        token=admin,
        body={"resolution": "warned", "conclusion": "已沟通整改话术"},
    )
    results.append(
        check(
            "VP07-F02b 投诉结案 TC-P07-F02",
            code == 200 and closed.get("status") == "closed" and closed.get("closed_at"),
            f"{code} {closed.get('status') if isinstance(closed, dict) else closed}",
        )
    )
    code, reopen = req(
        "POST",
        f"/admin/shop/moderation-cases/{complaint_id}/close",
        token=admin,
        body={"resolution": "warned", "conclusion": "再次结案应拒绝"},
    )
    results.append(
        check(
            "VP07-F02c 已结案不可再结",
            code == 422,
            f"{code} {_err(reopen)}",
        )
    )

    code, typed = req(
        "GET",
        "/admin/shop/moderation-cases?case_type=product_violation&page_size=50",
        token=admin,
    )
    typed_items = (typed or {}).get("items") or []
    results.append(
        check(
            "VP07-L01 类型筛选",
            code == 200 and all(x.get("case_type") == "product_violation" for x in typed_items),
            f"{code} n={len(typed_items)}",
        )
    )
    code, task = req("POST", "/admin/shop/moderation-cases/export", token=admin, body={})
    results.append(
        check(
            "VP07-X1 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "moderation_cases"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req(
            "GET", f"/admin/shop/moderation-cases/export-tasks/{task_id}/file", token=admin
        )
        results.append(
            check(
                "VP07-X2 任务文件可下载",
                code == 200 and "工单号" in str(file_csv) and "类型" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VP07-X2 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/admin/shop/moderation-cases/export",
        token=admin,
        body={"columns": ["case_type", "merchant_name"]},
    )
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/admin/shop/moderation-cases/export-tasks/{cols_task['id']}/file",
            token=admin,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        results.append(
            check(
                "VP07-X3 列配置导出表头",
                code2 == 200 and "类型" in head and "商家" in head and "结案时间" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VP07-X3 列配置导出表头", False, f"{code} {cols_task}"))

    if seeded.get("f6_case_id"):
        code, f6 = req("GET", f"/admin/shop/moderation-cases/{seeded['f6_case_id']}", token=admin)
        results.append(
            check(
                "VP07-F6 机审入库",
                code == 200 and f6.get("source") == "f6_auto" and f6.get("status") == "pending",
                f"{code} {f6.get('source') if isinstance(f6, dict) else f6}",
            )
        )

    code, forbidden = req("GET", "/admin/shop/moderation-cases", token=merchant)
    att_forbidden = client.get(
        f"/api/v1/admin/shop/moderation-cases/{complaint_id}/attachments/{chat_file_id}",
        headers={"Authorization": f"Bearer {merchant}"},
    )
    results.append(
        check(
            "VP07-P01 商家无稽查权 TC-P07-P01",
            code in (401, 403) and att_forbidden.status_code in (401, 403),
            f"{code}/{att_forbidden.status_code}",
        )
    )
    code, exp_forbidden = req("POST", "/admin/shop/moderation-cases/export", token=merchant, body={})
    results.append(
        check(
            "VP07-P01b 商家 POST 导出 403",
            code in (401, 403),
            f"{code} {exp_forbidden}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP07 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
