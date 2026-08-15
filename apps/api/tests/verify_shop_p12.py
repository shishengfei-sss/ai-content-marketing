#!/usr/bin/env python3
"""P12 短信管理。对照 PRD 06#p12 · #p12-signatures · #p12-assign · #p12-logs。"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "SmsManagement.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AdminLayout.vue"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"
A15S = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "SmsClaimSettings.vue"


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


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP12-UI 短信管理页",
            _page_has(
                WEB,
                "#p12",
                "通道配置",
                "签名管理",
                "模板管理",
                "商家分配",
                "发送记录",
                "+ 新建签名申请",
                "+ 登记新模板",
                "+ 分配短信资源",
                "搜索签名 / 商家",
                "同步供应商审核状态",
                "列设置",
                "导出 CSV",
                "连通性测试",
                "确认保存",
            )
            and _page_has(LAYOUT, "短信管理", "/admin/shop/sms")
            and _page_has(ROUTER, "shop/sms", "SmsManagement"),
            f"{WEB}",
        )
    )
    results.append(
        check(
            "VP12-UI 导出任务弹窗 #p12-logs",
            _page_has(
                WEB,
                "导出 CSV",
                "导出任务",
                "createShopSmsLogExport",
                "getShopSmsLogExportFile",
                "当前筛选",
                "列配置",
                "createShopSmsSignatureExport",
                "createShopSmsTemplateExport",
                "createShopSmsAssignmentExport",
                "getShopSmsSignatureExportFile",
                "getShopSmsTemplateExportFile",
                "getShopSmsAssignmentExportFile",
            ),
            "P12 export dialogs",
        )
    )
    results.append(
        check(
            "VP12-UI A15-S 只读签名",
            _page_has(A15S, "短信签名（只读）", "领权短信模板（只读）"),
            str(A15S),
        )
    )

    merchant, tenant_id = _ensure_merchant()
    admin = login("13800000000", "admin123456", "platform")

    code, listing = req(
        "GET", "/admin/shop/sms/signatures?status=pending&page=1&page_size=100", token=admin
    )
    for it in (listing or {}).get("items") or []:
        if str(it.get("tenant_id")) == str(tenant_id):
            req("POST", f"/admin/shop/sms/signatures/{it['id']}/withdraw", token=admin, body={})

    code, cfg = req("GET", "/admin/shop/sms/channel-config", token=admin)
    results.append(
        check(
            "VP12-0 通道凭据可落库 TC-P12-F01",
            code == 200 and cfg.get("credentials_persist") is True,
            f"{code} {cfg}",
        )
    )
    code, empty_ak = req(
        "PUT",
        "/admin/shop/sms/channel-config",
        token=admin,
        body={"access_key_id": "", "access_key_secret": "secret123456"},
    )
    results.append(
        check(
            "VP12-0b AccessKey 空 422 TC-P12-E01",
            code == 422 and "AccessKey ID" in _err(empty_ak),
            f"{code} {_err(empty_ak)}",
        )
    )
    code, saved_cfg = req(
        "PUT",
        "/admin/shop/sms/channel-config",
        token=admin,
        body={
            "access_key_id": "LTAItestkey12",
            "access_key_secret": "sms-secret-value",
            "default_notify_signature": "【智营获客】",
        },
    )
    results.append(
        check(
            "VP12-0c 保存通道凭据 #p12c",
            code == 200
            and (saved_cfg or {}).get("configured") is True
            and str((saved_cfg or {}).get("access_key_id_masked") or "").startswith("LTAI")
            and "sms-secret-value" not in str(saved_cfg),
            f"{code} {saved_cfg}",
        )
    )
    code, tested = req("POST", "/admin/shop/sms/channel-config/test", token=admin, body={})
    results.append(
        check(
            "VP12-0d 连通性测试",
            code == 200 and (tested or {}).get("last_test_ok") is True,
            f"{code} {tested}",
        )
    )

    bad = {"tenant_id": tenant_id, "content": "!!"}
    code, err = req("POST", "/admin/shop/sms/signatures", token=admin, body=bad)
    results.append(
        check(
            "VP12-1 非法签名 422",
            code == 422 and "非法" in _err(err),
            f"{code} {_err(err)}",
        )
    )

    sig_content = f"【测{uuid.uuid4().hex[:6]}】"
    payload = {
        "tenant_id": tenant_id,
        "content": sig_content,
        "remark": "抖店公域领权短信",
    }
    code, sig = req("POST", "/admin/shop/sms/signatures", token=admin, body=payload)
    results.append(
        check(
            "VP12-2 新建签名申请",
            code == 200 and sig.get("status") == "pending" and sig.get("content") == sig_content,
            f"{code} {sig}",
        )
    )
    sig_id = sig.get("id") if isinstance(sig, dict) else None

    code, dup = req("POST", "/admin/shop/sms/signatures", token=admin, body=payload)
    results.append(
        check(
            "VP12-3 同商家不可第二 pending",
            code == 422 and "审核中" in _err(dup),
            f"{code} {_err(dup)}",
        )
    )

    code, synced = req("POST", f"/admin/shop/sms/signatures/{sig_id}/sync", token=admin, body={})
    results.append(
        check(
            "VP12-4 同步仍审核中",
            code == 200 and synced.get("status") == "pending",
            f"{code} {synced.get('status') if isinstance(synced, dict) else synced}",
        )
    )

    code, approved = req(
        "POST", f"/admin/shop/sms/signatures/{sig_id}/approve", token=admin, body={}
    )
    results.append(
        check(
            "VP12-5 签名通过",
            code == 200 and approved.get("status") == "approved",
            f"{code} {approved.get('status') if isinstance(approved, dict) else approved}",
        )
    )

    tpl_code = f"SMS_{uuid.uuid4().hex[:8].upper()}"
    code, tpl = req(
        "POST",
        "/admin/shop/sms/templates",
        token=admin,
        body={
            "name": "抖店领权默认",
            "template_code": tpl_code,
            "purpose": "claim_link",
            "content_preview": "您已购买${product}，点击 ${url} 领取",
            "is_default_claim": True,
        },
    )
    results.append(
        check(
            "VP12-6 登记领权模板",
            code == 200 and tpl.get("is_default_claim") is True and tpl.get("status") == "approved",
            f"{code} {tpl}",
        )
    )
    tpl_id = tpl.get("id") if isinstance(tpl, dict) else None

    code, dup_tpl = req(
        "POST",
        "/admin/shop/sms/templates",
        token=admin,
        body={"name": "重复", "template_code": tpl_code, "purpose": "claim_link"},
    )
    results.append(
        check(
            "VP12-7 Code 已存在",
            code == 422 and "已存在" in _err(dup_tpl),
            f"{code} {_err(dup_tpl)}",
        )
    )

    pending_sig = req(
        "POST",
        "/admin/shop/sms/signatures",
        token=admin,
        body={"tenant_id": tenant_id, "content": f"【待{uuid.uuid4().hex[:6]}】"},
    )
    code, asg_fail = req(
        "POST",
        "/admin/shop/sms/assignments",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "sms_signature_id": (pending_sig[1] or {}).get("id") or sig_id,
            "claim_template_id": tpl_id,
        },
    )
    if pending_sig[0] == 200:
        results.append(
            check(
                "VP12-8 未审签名不可分配 TC-P12-E02",
                code == 422 and "未通过" in _err(asg_fail),
                f"{code} {_err(asg_fail)}",
            )
        )
        pending_id = pending_sig[1]["id"]
        code, short_rej = req(
            "POST",
            f"/admin/shop/sms/signatures/{pending_id}/reject",
            token=admin,
            body={"reason": "abc"},
        )
        results.append(
            check(
                "VP12-8b 驳回原因过短",
                code == 422 and "4" in _err(short_rej),
                f"{code} {_err(short_rej)}",
            )
        )
        code, rejected = req(
            "POST",
            f"/admin/shop/sms/signatures/{pending_id}/reject",
            token=admin,
            body={"reason": "资质材料不齐"},
        )
        results.append(
            check(
                "VP12-8c 签名驳回",
                code == 200 and rejected.get("status") == "rejected",
                f"{code} {rejected}",
            )
        )
    else:
        results.append(
            check(
                "VP12-8 未审签名不可分配 TC-P12-E02",
                False,
                f"create pending {pending_sig}",
            )
        )
        results.append(check("VP12-8b 驳回原因过短", False, "no pending"))
        results.append(check("VP12-8c 签名驳回", False, "no pending"))

    code, assigned = req(
        "POST",
        "/admin/shop/sms/assignments",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "sms_signature_id": sig_id,
            "claim_template_id": tpl_id,
        },
    )
    results.append(
        check(
            "VP12-9 分配给商家 TC-P12-F02",
            code == 200 and assigned.get("assign_status") == "assigned",
            f"{code} {assigned}",
        )
    )

    code, sms = req("GET", "/shop/settings/sms", token=merchant)
    results.append(
        check(
            "VP12-10 A15-S 只读可见签名",
            code == 200
            and sms.get("config_status") == "assigned"
            and sig_content in str(sms.get("sms_signature") or ""),
            f"{code} {sms}",
        )
    )

    code, listing = req("GET", "/admin/shop/sms/signatures?page=1&page_size=20", token=admin)
    results.append(
        check(
            "VP12-11 签名列表",
            code == 200 and isinstance((listing or {}).get("items"), list),
            f"{code}",
        )
    )
    code, sig_csv = req("GET", "/admin/shop/sms/signatures/export", token=admin)
    results.append(
        check(
            "VP12-S0 GET 签名导出含默认列",
            code == 200 and "签名" in str(sig_csv) and "关联商家" in str(sig_csv),
            f"{code} {str(sig_csv)[:80]}",
        )
    )
    code, sig_task = req("POST", "/admin/shop/sms/signatures/export", token=admin, body={})
    results.append(
        check(
            "VP12-S1 POST 签名导出任务",
            code == 200
            and isinstance(sig_task, dict)
            and sig_task.get("status") == "done"
            and sig_task.get("resource") == "sms_signatures"
            and sig_task.get("id"),
            f"{code} {sig_task}",
        )
    )
    sig_tid = (sig_task or {}).get("id") if isinstance(sig_task, dict) else None
    if sig_tid:
        code, sig_file = req(
            "GET", f"/admin/shop/sms/signatures/export-tasks/{sig_tid}/file", token=admin
        )
        results.append(
            check(
                "VP12-S2 签名任务文件可下载",
                code == 200 and "签名" in str(sig_file) and "供应商审核" in str(sig_file),
                f"{code} head={str(sig_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VP12-S2 签名任务文件可下载", False, "no task id"))
    code, sig_cols = req(
        "POST",
        "/admin/shop/sms/signatures/export",
        token=admin,
        body={"columns": ["content", "status"]},
    )
    if code == 200 and isinstance(sig_cols, dict) and sig_cols.get("id"):
        code2, sig_col_csv = req(
            "GET",
            f"/admin/shop/sms/signatures/export-tasks/{sig_cols['id']}/file",
            token=admin,
        )
        head = str(sig_col_csv).splitlines()[0] if sig_col_csv else ""
        results.append(
            check(
                "VP12-S3 签名列配置表头",
                code2 == 200 and "签名" in head and "供应商审核" in head and "关联商家" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VP12-S3 签名列配置表头", False, f"{code} {sig_cols}"))
    code, tpl_task = req("POST", "/admin/shop/sms/templates/export", token=admin, body={})
    results.append(
        check(
            "VP12-T1 POST 模板导出任务",
            code == 200
            and isinstance(tpl_task, dict)
            and tpl_task.get("resource") == "sms_templates"
            and tpl_task.get("status") == "done",
            f"{code} {tpl_task}",
        )
    )
    if code == 200 and isinstance(tpl_task, dict) and tpl_task.get("id"):
        code2, tpl_file = req(
            "GET", f"/admin/shop/sms/templates/export-tasks/{tpl_task['id']}/file", token=admin
        )
        results.append(
            check(
                "VP12-T2 模板任务文件可下载",
                code2 == 200 and "模板名称" in str(tpl_file) and "供应商 Code" in str(tpl_file),
                f"{code2} head={str(tpl_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VP12-T2 模板任务文件可下载", False, "no task id"))
    code, asg_task = req("POST", "/admin/shop/sms/assignments/export", token=admin, body={})
    results.append(
        check(
            "VP12-A1 POST 分配导出任务",
            code == 200
            and isinstance(asg_task, dict)
            and asg_task.get("resource") == "sms_assignments"
            and asg_task.get("status") == "done",
            f"{code} {asg_task}",
        )
    )
    if code == 200 and isinstance(asg_task, dict) and asg_task.get("id"):
        code2, asg_file = req(
            "GET", f"/admin/shop/sms/assignments/export-tasks/{asg_task['id']}/file", token=admin
        )
        results.append(
            check(
                "VP12-A2 分配任务文件可下载",
                code2 == 200 and "商家" in str(asg_file) and "领权签名" in str(asg_file),
                f"{code2} head={str(asg_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VP12-A2 分配任务文件可下载", False, "no task id"))

    from uuid import UUID as UUIDType

    from app.database import SessionLocal
    from app.models.shop import ShopSmsLog

    db = SessionLocal()
    try:
        db.add(
            ShopSmsLog(
                id=uuid.uuid4(),
                tenant_id=UUIDType(str(tenant_id)),
                buyer_mobile="13912341234",
                type="claim_link",
                content="领权测试短信（无明文手机）",
                status="sent",
                provider_msg_id="biz_mask_check",
            )
        )
        db.commit()
    finally:
        db.close()

    code, logs = req("GET", "/admin/shop/sms/logs?page=1&page_size=50", token=admin)
    items = (logs or {}).get("items") if isinstance(logs, dict) else []
    hit = next((it for it in (items or []) if it.get("mobile_masked") == "139****1234"), None)
    results.append(
        check(
            "VP12-12 发送记录脱敏 TC-P12-L01",
            code == 200
            and hit is not None
            and not hit.get("mobile")
            and "13912341234" not in str(hit),
            f"{code} hit={hit}",
        )
    )

    code, csv_body = req("GET", "/admin/shop/sms/logs/export?range_key=30d", token=admin)
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VP12-13 导出发送记录",
            code == 200 and "发送时间" in csv_text,
            f"{code} {csv_text[:60]}",
        )
    )
    code, task = req("POST", "/admin/shop/sms/logs/export", token=admin, body={"range_key": "30d"})
    results.append(
        check(
            "VP12-13b POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "sms_logs"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req(
            "GET", f"/admin/shop/sms/logs/export-tasks/{task_id}/file", token=admin
        )
        results.append(
            check(
                "VP12-13c 任务文件可下载",
                code == 200 and "发送时间" in str(file_csv) and "关联单号" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VP12-13c 任务文件可下载", False, "no task id"))
    code, too_wide = req(
        "POST",
        "/admin/shop/sms/logs/export",
        token=admin,
        body={"range_key": "custom", "date_from": "2026-01-01", "date_until": "2026-03-15"},
    )
    results.append(
        check(
            "VP12-13d 超31天 导出范围过大",
            code == 422 and "导出范围过大" in _err(too_wide),
            f"{code} {_err(too_wide)}",
        )
    )

    code, forbidden = req("GET", "/admin/shop/sms/signatures", token=merchant)
    results.append(
        check(
            "VP12-14 商家无平台权 TC-P12-P01",
            code in (401, 403),
            f"{code}",
        )
    )
    code, exp_forbidden = req("POST", "/admin/shop/sms/logs/export", token=merchant, body={})
    results.append(
        check(
            "VP12-14b 商家 POST 导出 403",
            code in (401, 403),
            f"{code} {exp_forbidden}",
        )
    )
    code, sig_forbidden = req("POST", "/admin/shop/sms/signatures/export", token=merchant, body={})
    results.append(
        check(
            "VP12-14c 商家 POST 签名导出 403",
            code in (401, 403),
            f"{code} {sig_forbidden}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP12 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
