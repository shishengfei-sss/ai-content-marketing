#!/usr/bin/env python3
"""P05 清结算。对照 PRD 06#p05 · #p05a · #p05b · #p05c · §8.14.3。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import _get_test_client, check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "Settlements.vue"
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


def _prepare_merchant(tenant_id: str):
    from app.database import SessionLocal
    from app.models.shop import ShopOnboardingApplication, ShopStore
    from app.services.shop import p05_settlement_service as p05svc

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
        app = apps_by_tid.get(_tid_key(tid))
        if app is not None:
            info = dict(app.bank_account_info or {})
            info.update(
                {
                    "account_no": "6222020000008821",
                    "bank_name": "验收银行",
                    "account_name": "演示对公户",
                }
            )
            app.bank_account_info = info
            db.commit()
        pending = p05svc.seed_pending_batch(db, tid, shop_id, net_cents=40837)
        carried = p05svc.seed_batch(
            db, tid, shop_id, net_cents=-5250, batch_status="carried_forward"
        )
        pending_carry = p05svc.seed_batch(
            db,
            tid,
            shop_id,
            net_cents=14150,
            batch_status="pending",
            opening_cents=-5250,
            source_batch_id=carried.id,
        )
        failed = p05svc.seed_batch(
            db,
            tid,
            shop_id,
            net_cents=18228,
            batch_status="payment_failed",
            fail_reason="收款户名与进件不一致",
        )
        return (
            str(pending.id),
            str(carried.id),
            str(failed.id),
            pending.batch_no,
            str(pending_carry.id),
        )
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP05-UI 清结算页 TC-P05-L01",
            _page_has(
                WEB,
                "#p05",
                "结算批次",
                "商家",
                "周期",
                "成交额",
                "平台抽成",
                "退款冲正",
                "应结",
                "生成时间",
                "确认打款",
                "导出凭证",
                "列设置",
                "本月平台收入",
                "待结算给商家",
                "周结",
                "结转来源（只读）",
                "打款凭证（选填）",
                "周期起",
                "退回待结算（商家改账户）",
            )
            and "opening_balance 抵扣" not in WEB.read_text(encoding="utf-8")
            and _page_has(LAYOUT, "清结算", "/admin/shop/settlements")
            and _page_has(ROUTER, "shop/settlements", "Settlements")
            and _page_has(DASH, "/admin/shop/settlements"),
            str(WEB),
        )
    )
    results.append(
        check(
            "VP05-UI 导出任务弹窗 #p05",
            _page_has(
                WEB,
                "当前筛选",
                "列配置",
                "导出任务",
                "createShopSettlementExport",
                "getShopSettlementExportFile",
            )
            and "ElMessageBox" not in WEB.read_text(encoding="utf-8"),
            "P05 export dropdown + dialog",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    admin = login("13800000000", "admin123456", "platform")
    pending_id, carried_id, failed_id, batch_no, carry_pending_id = _prepare_merchant(tenant_id)

    code, listing = req("GET", "/admin/shop/settlement-batches?page=1&page_size=20", token=admin)
    items = (listing or {}).get("items") or []
    sample = next((x for x in items if x.get("id") == pending_id), items[0] if items else {})
    results.append(
        check(
            "VP05-0 列表默认列 TC-P05-L01",
            code == 200
            and "batch_no" in sample
            and "merchant_name" in sample
            and "gross_amount_cents" in sample
            and "platform_fee_cents" in sample
            and "refund_reversal_cents" in sample
            and "net_amount_cents" in sample
            and "status" in sample
            and listing.get("stats", {}).get("settlement_period") == "weekly",
            f"{code} n={len(items)}",
        )
    )
    code, task = req("POST", "/admin/shop/settlement-batches/export", token=admin, body={})
    results.append(
        check(
            "VP05-X1 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "settlements"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req(
            "GET", f"/admin/shop/settlement-batches/export-tasks/{task_id}/file", token=admin
        )
        results.append(
            check(
                "VP05-X2 任务文件可下载",
                code == 200 and "结算批次" in str(file_csv) and "应结" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VP05-X2 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/admin/shop/settlement-batches/export",
        token=admin,
        body={"columns": ["batch_no", "merchant_name"]},
    )
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/admin/shop/settlement-batches/export-tasks/{cols_task['id']}/file",
            token=admin,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        results.append(
            check(
                "VP05-X3 列配置导出表头",
                code2 == 200 and "结算批次" in head and "商家" in head and "应结" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VP05-X3 列配置导出表头", False, f"{code} {cols_task}"))
    results.append(
        check(
            "VP05-0b 空搜不 500 TC-P05-L01-S2",
            req("GET", "/admin/shop/settlement-batches?q=ZZZNONE", token=admin)[0] == 200,
            "",
        )
    )
    code, far = req(
        "GET",
        "/admin/shop/settlement-batches?period_start=2099-01-01&period_end=2099-12-31",
        token=admin,
    )
    results.append(
        check(
            "VP05-0c 周期筛选 TC-P05-L01",
            code == 200 and (far or {}).get("total") == 0,
            f"{code} {(far or {}).get('total')}",
        )
    )
    code, bad_period = req(
        "GET",
        "/admin/shop/settlement-batches?period_start=not-a-date",
        token=admin,
    )
    results.append(
        check(
            "VP05-0d 非法周期 422",
            code == 422 and "周期" in _err(bad_period),
            f"{code} {_err(bad_period)}",
        )
    )
    code, cdetail = req(
        "GET",
        f"/admin/shop/settlement-batches/{carry_pending_id}",
        token=admin,
    )
    srcs = (cdetail or {}).get("carry_sources") or []
    results.append(
        check(
            "VP05-A 详情结转来源 #p05a-pending-carry",
            code == 200
            and (cdetail or {}).get("opening_balance_cents") == -5250
            and srcs
            and srcs[0].get("batch_no")
            and srcs[0].get("id") == carried_id,
            f"{code} srcs={srcs[:1]}",
        )
    )

    code, zero = req(
        "POST",
        f"/admin/shop/settlement-batches/{carried_id}/confirm",
        token=admin,
        body={},
    )
    results.append(
        check(
            "VP05-E01 net≤0 不可打款 TC-P05-E01",
            code == 422 and "待结算" in _err(zero),
            f"{code} {_err(zero)}",
        )
    )

    client = _get_test_client()
    up = client.post(
        f"/api/v1/admin/shop/settlement-batches/{pending_id}/voucher",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("voucher.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    voucher = up.json() if up.headers.get("content-type", "").startswith("application/json") else {}
    file_id = voucher.get("file_id") if isinstance(voucher, dict) else None
    results.append(
        check(
            "VP05-F01b 真实上传凭证",
            up.status_code == 200 and bool(file_id),
            f"{up.status_code} {voucher}",
        )
    )

    code, paid = req(
        "POST",
        f"/admin/shop/settlement-batches/{pending_id}/confirm",
        token=admin,
        body={"transfer_voucher_url": file_id, "remark": "验收"},
    )
    results.append(
        check(
            "VP05-F01 确认打款 TC-P05-F01",
            code == 200 and paid.get("status") == "paid" and paid.get("paid_at"),
            f"{code} {paid.get('status') if isinstance(paid, dict) else paid}",
        )
    )
    dl = client.get(
        f"/api/v1/admin/shop/settlement-batches/{pending_id}/voucher/{file_id}",
        headers={"Authorization": f"Bearer {admin}"},
    )
    results.append(
        check(
            "VP05-F01c 凭证可预览",
            dl.status_code == 200 and len(dl.content) > 4,
            str(dl.status_code),
        )
    )

    code, csv_body = req("GET", f"/admin/shop/settlement-batches/{pending_id}/export", token=admin)
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VP05-1 已打款导出凭证",
            code == 200 and "结算凭证" in csv_text and batch_no in csv_text,
            f"{code} {csv_text[:60]}",
        )
    )

    code, retried = req(
        "POST",
        f"/admin/shop/settlement-batches/{failed_id}/retry",
        token=admin,
        body={"action": "return_pending"},
    )
    results.append(
        check(
            "VP05-2 失败退回待结算",
            code == 200 and retried.get("status") == "pending",
            f"{code} {retried.get('status') if isinstance(retried, dict) else retried}",
        )
    )

    code, closed = req("POST", "/admin/shop/settlement-batches/close-period", token=admin, body={})
    results.append(
        check(
            "VP05-F10 周关账可调用",
            code == 200 and "created" in (closed or {}),
            f"{code} {closed}",
        )
    )

    code, forbidden = req("GET", "/admin/shop/settlement-batches", token=merchant)
    results.append(
        check(
            "VP05-E02 商家无结算权 TC-P05-E02",
            code in (401, 403),
            f"{code}",
        )
    )
    code, exp_forbidden = req("POST", "/admin/shop/settlement-batches/export", token=merchant, body={})
    results.append(
        check(
            "VP05-E02b 商家 POST 导出 403",
            code in (401, 403),
            f"{code} {exp_forbidden}",
        )
    )
    fin = login("13800000077", "fin12345678", "platform")
    code, flist = req("GET", "/admin/shop/settlement-batches?page=1&page_size=5", token=fin)
    results.append(
        check(
            "VP05-P01 财务可读列表",
            code == 200 and isinstance((flist or {}).get("items"), list),
            f"{code}",
        )
    )
    code, patched = req(
        "PATCH",
        f"/admin/shop/settlement-batches/{carried_id}",
        token=admin,
        body={"net_amount_cents": 1},
    )
    results.append(
        check(
            "VP05-E03 禁止改应结金额 TC-P05-E03",
            code in (404, 405, 422),
            f"{code}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP05 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
