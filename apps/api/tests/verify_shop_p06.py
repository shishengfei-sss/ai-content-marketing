#!/usr/bin/env python3
"""P06 商户支付进件。对照 PRD 06#p06-onboarding-list · #p06e · #p02b-payment。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal, uuid_eq  # noqa: E402
from app.models.shop import PlatformChannelCredential, ShopPaymentOnboarding  # noqa: E402
from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "ChannelPayConfig.vue"
DETAIL = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "MerchantDetail.vue"
PANEL = REPO_ROOT / "apps" / "web" / "src" / "components" / "shop" / "ShopPaymentOnboardingPanel.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AdminLayout.vue"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"


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


def _err_text(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    d = data.get("detail", data)
    if isinstance(d, list):
        return " ".join(
            str(x.get("msg") or x.get("message") or x) if isinstance(x, dict) else str(x)
            for x in d
        )
    return str(d)


def _clear_wechat_cert() -> None:
    """VP06-18 需「未上传证书」；库里若已有证书则先清掉，避免脏数据把 422 变成 200。"""
    db = SessionLocal()
    try:
        row = (
            db.query(PlatformChannelCredential)
            .filter(PlatformChannelCredential.channel == "wechat_pay_sp")
            .first()
        )
        if not row:
            return
        pub = dict(row.public_json or {})
        pub.pop("cert_serial", None)
        pub.pop("cert_expires", None)
        row.public_json = pub
        db.commit()
    finally:
        db.close()


def _test_cert_pair() -> tuple[str, str]:
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "p06-test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(0x5F3A9B2C)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return pem, key_pem


def _reset_row(tenant_id: str, status: str = "not_submitted") -> None:
    with SessionLocal() as db:
        row = (
            db.query(ShopPaymentOnboarding)
            .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, UUID(str(tenant_id))))
            .first()
        )
        if not row:
            return
        row.onboarding_status = status
        row.wx_sub_mch_id = None
        row.approved_at = None
        if status == "not_submitted":
            row.settlement_account = None
            row.settlement_bank = None
            row.reject_reason = None
        db.commit()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP06-UI 渠道与支付页",
            _page_has(
                WEB,
                "#p06",
                "#p06-onboarding-list",
                "抖店公域",
                "微信支付服务商",
                "商户支付进件",
                "微信开放平台",
                "搜索商家名 / 子商户号",
                "商家管家",
                "主体类型",
                "列设置",
                "导出",
                "查看材料",
                "保存配置",
                "密钥轮换",
                "连通性测试",
                "证书轮换",
                "确认保存",
                "影响说明（只读）",
            )
            and _page_has(LAYOUT, "渠道与支付", "/admin/shop/channels")
            and _page_has(ROUTER, "shop/channels", "ChannelPayConfig"),
            f"{WEB} {LAYOUT} {ROUTER}",
        )
    )
    results.append(
        check(
            "VP06-UI 进件抽屉与 P02-B",
            _page_has(
                PANEL,
                "#p06e",
                "#p02b-payment",
                "主体名称（只读）",
                "统一社会信用代码（只读）",
                "结算开户行（只读）",
                "开户名（只读）",
                "结算账号（脱敏）",
                "资质证照（只读）",
                "刷新微信状态",
                "代提微信进件",
            )
            and _page_has(DETAIL, 'label="支付进件"', "ShopPaymentOnboardingPanel", 'variant="p02b"'),
            f"{PANEL} {DETAIL}",
        )
    )

    results.append(
        check(
            "VP06-UI 导出任务弹窗 #p06-onboarding-list",
            _page_has(
                WEB,
                "当前筛选",
                "列配置",
                "导出任务",
                "createShopPaymentOnboardingExport",
                "getShopPaymentOnboardingExportFile",
            ),
            "P06 export dropdown + dialog",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    _reset_row(tenant_id, "not_submitted")
    payload = {
        "settlement_bank": "招商银行",
        "settlement_account": "6222021234567890123",
        "settlement_account_name": "联测进件开户名",
        "remark": "verify_shop_p06",
    }
    code, submitted = req(
        "POST", "/shop/settings/payment/onboarding", token=merchant, body=payload
    )
    results.append(
        check(
            "VP06-0 商家提交进件",
            code == 200 and submitted.get("onboarding_status") == "submitted",
            f"{code} {submitted}",
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    code, listing = req("GET", "/admin/shop/payment-onboarding?page=1&page_size=20", token=admin)
    items = (listing or {}).get("items") if isinstance(listing, dict) else None
    counts = (listing or {}).get("status_counts") if isinstance(listing, dict) else None
    hit = next((x for x in (items or []) if str(x.get("tenant_id")) == str(tenant_id)), None)
    results.append(
        check(
            "VP06-1 进件列表 TC-P06-F02",
            code == 200
            and isinstance(items, list)
            and isinstance(counts, dict)
            and "submitted" in (counts or {})
            and hit is not None
            and hit.get("onboarding_status") == "submitted"
            and "结算账户" not in str(hit.get("settlement_account") or "")
            and hit.get("settlement_account") is None,
            f"{code} hit={hit} counts={counts}",
        )
    )

    code, filtered = req(
        "GET",
        "/admin/shop/payment-onboarding?status=submitted&page=1&page_size=20",
        token=admin,
    )
    f_items = (filtered or {}).get("items") if isinstance(filtered, dict) else []
    results.append(
        check(
            "VP06-2 状态筛选审核中",
            code == 200
            and all(x.get("onboarding_status") == "submitted" for x in (f_items or [])),
            f"{code} n={len(f_items or [])}",
        )
    )

    code, detail = req("GET", f"/admin/shop/payment-onboarding/{tenant_id}", token=admin)
    results.append(
        check(
            "VP06-3 进件详情",
            code == 200
            and detail.get("onboarding_status") == "submitted"
            and (detail.get("entity") or {}).get("legal_name") is not None
            and detail.get("settlement_account") is None
            and detail.get("settlement_account_masked")
            and isinstance(detail.get("timeline"), list),
            f"{code} {detail}",
        )
    )

    code, refreshed = req(
        "POST", f"/admin/shop/payment-onboarding/{tenant_id}/refresh", token=admin, body={}
    )
    events = " ".join(str(x.get("event")) for x in (refreshed or {}).get("timeline") or [])
    results.append(
        check(
            "VP06-4 刷新微信状态 TC-P06-F02",
            code == 200
            and refreshed.get("onboarding_status") == "submitted"
            and "刷新微信状态" in events,
            f"{code} {events}",
        )
    )

    code, wx = req(
        "POST",
        f"/admin/shop/payment-onboarding/{tenant_id}/submit-wechat",
        token=admin,
        body={},
    )
    results.append(
        check(
            "VP06-5 代提微信",
            code == 200
            and wx.get("wx_apply_no")
            and str(wx.get("wx_apply_no")).startswith("WX"),
            f"{code} {wx.get('wx_apply_no') if isinstance(wx, dict) else wx}",
        )
    )

    code, bad_rej = req(
        "POST",
        f"/admin/shop/payment-onboarding/{tenant_id}/reject",
        token=admin,
        body={"reason": "短"},
    )
    results.append(
        check(
            "VP06-6 驳回原因过短 422",
            code == 422 and "4" in _err_text(bad_rej),
            f"{code} {_err_text(bad_rej)}",
        )
    )

    code, revealed = req(
        "POST",
        f"/admin/shop/payment-onboarding/{tenant_id}/reveal-sensitive",
        token=admin,
        body={},
    )
    results.append(
        check(
            "VP06-7 揭露结算账号",
            code == 200 and revealed.get("settlement_account") == "6222021234567890123",
            f"{code} {revealed.get('settlement_account') if isinstance(revealed, dict) else revealed}",
        )
    )

    code, approved = req(
        "POST",
        f"/admin/shop/payment-onboarding/{tenant_id}/approve",
        token=admin,
        body={"wx_sub_mch_id": "1600123456"},
    )
    results.append(
        check(
            "VP06-8 开通子商户号",
            code == 200
            and approved.get("onboarding_status") == "approved"
            and approved.get("wx_sub_mch_id_masked")
            and "1600123456" not in str(approved.get("wx_sub_mch_id_masked")),
            f"{code} {approved.get('wx_sub_mch_id_masked') if isinstance(approved, dict) else approved}",
        )
    )

    _reset_row(tenant_id, "submitted")
    with SessionLocal() as db:
        row = (
            db.query(ShopPaymentOnboarding)
            .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, UUID(str(tenant_id))))
            .first()
        )
        if row:
            row.settlement_bank = "招商银行"
            row.settlement_account = "6222021234567890123"
            row.settlement_account_name = "联测进件开户名"
            db.commit()
    code, rejected = req(
        "POST",
        f"/admin/shop/payment-onboarding/{tenant_id}/reject",
        token=admin,
        body={"reason": "账户名与执照主体不一致"},
    )
    results.append(
        check(
            "VP06-9 驳回",
            code == 200
            and rejected.get("onboarding_status") == "rejected"
            and "执照" in (rejected.get("reject_reason") or ""),
            f"{code} {rejected.get('onboarding_status') if isinstance(rejected, dict) else rejected}",
        )
    )

    code, notified = req(
        "POST", f"/admin/shop/payment-onboarding/{tenant_id}/notify", token=admin, body={}
    )
    results.append(
        check(
            "VP06-10 通知商家",
            code == 200 and notified.get("ok") is True,
            f"{code} {notified}",
        )
    )

    code, csv_body = req("GET", "/admin/shop/payment-onboarding/export", token=admin)
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VP06-11 导出 CSV",
            code == 200 and "商家" in csv_text and "进件状态" in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )
    code, task = req("POST", "/admin/shop/payment-onboarding/export", token=admin, body={})
    results.append(
        check(
            "VP06-X1 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "payment_onboarding"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req(
            "GET", f"/admin/shop/payment-onboarding/export-tasks/{task_id}/file", token=admin
        )
        results.append(
            check(
                "VP06-X2 任务文件可下载",
                code == 200 and "商家" in str(file_csv) and "进件状态" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VP06-X2 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/admin/shop/payment-onboarding/export",
        token=admin,
        body={"columns": ["merchant_name", "onboarding_status"]},
    )
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/admin/shop/payment-onboarding/export-tasks/{cols_task['id']}/file",
            token=admin,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        results.append(
            check(
                "VP06-X3 列配置导出表头",
                code2 == 200 and "商家" in head and "进件状态" in head and "商家管家" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VP06-X3 列配置导出表头", False, f"{code} {cols_task}"))

    code, cfg = req("GET", "/admin/shop/payment-onboarding/channel-config", token=admin)
    results.append(
        check(
            "VP06-12 渠道回调只读",
            code == 200
            and cfg.get("credentials_persist") is True
            and "/api/v1/webhooks/douyin/order" in str(cfg.get("doudian_webhook_url") or "")
            and "/api/v1/mp/shop/payments/notify" in str(cfg.get("wechat_pay_notify_url") or ""),
            f"{code} {cfg}",
        )
    )

    code, short_key = req(
        "PUT",
        "/admin/shop/payment-onboarding/channel-config/doudian",
        token=admin,
        body={"app_key": "ab", "app_secret": "secret-123456"},
    )
    results.append(
        check(
            "VP06-14 AppKey 过短 422",
            code == 422 and "AppKey" in _err_text(short_key),
            f"{code} {_err_text(short_key)}",
        )
    )
    code, saved = req(
        "PUT",
        "/admin/shop/payment-onboarding/channel-config/doudian",
        token=admin,
        body={"app_key": "dy_ak_prod_7821", "app_secret": "old-secret-value"},
    )
    doudian = (saved or {}).get("doudian") or {}
    blob = json.dumps(saved, ensure_ascii=False)
    results.append(
        check(
            "VP06-15 保存抖店配置脱敏 #p06a",
            code == 200
            and saved.get("doudian_configured") is True
            and doudian.get("app_key_masked")
            and "old-secret-value" not in blob
            and "dy_ak_prod_7821" not in str(doudian.get("app_key_masked")),
            f"{code} {doudian}",
        )
    )
    code, rotated = req(
        "POST",
        "/admin/shop/payment-onboarding/channel-config/doudian/rotate",
        token=admin,
        body={"app_secret": "new-secret-value"},
    )
    results.append(
        check(
            "VP06-16 抖店密钥轮换 #p06b",
            code == 200 and (rotated or {}).get("doudian", {}).get("grace_until"),
            f"{code} {(rotated or {}).get('doudian')}",
        )
    )
    code, tested = req(
        "POST",
        "/admin/shop/payment-onboarding/channel-config/doudian/test",
        token=admin,
        body={},
    )
    results.append(
        check(
            "VP06-17 抖店连通性测试",
            code == 200 and (tested or {}).get("doudian", {}).get("last_test_ok") is True,
            f"{code} {(tested or {}).get('doudian')}",
        )
    )

    pem, key_pem = _test_cert_pair()
    _clear_wechat_cert()
    code, no_cert = req(
        "PUT",
        "/admin/shop/payment-onboarding/channel-config/wechat-pay",
        token=admin,
        body={
            "mch_id": "1600000001",
            "app_id": "wx_appid_a12f",
            "api_v3_key": "a" * 32,
        },
    )
    results.append(
        check(
            "VP06-18 未上传证书 422",
            code == 422 and "证书" in _err_text(no_cert),
            f"{code} {_err_text(no_cert)}",
        )
    )
    code, wx_saved = req(
        "PUT",
        "/admin/shop/payment-onboarding/channel-config/wechat-pay",
        token=admin,
        body={
            "mch_id": "1600000001",
            "app_id": "wx_appid_a12f",
            "api_v3_key": "b" * 32,
            "cert_pem": pem,
            "cert_key": key_pem,
        },
    )
    wp = (wx_saved or {}).get("wechat_pay") or {}
    wx_blob = json.dumps(wx_saved, ensure_ascii=False)
    results.append(
        check(
            "VP06-19 保存微信服务商 #p06c",
            code == 200
            and wx_saved.get("wechat_pay_configured") is True
            and wp.get("cert_serial")
            and "bbbbbbbb" not in wx_blob
            and "BEGIN CERTIFICATE" not in wx_blob,
            f"{code} {wp}",
        )
    )
    code, bad_v3 = req(
        "POST",
        "/admin/shop/payment-onboarding/channel-config/wechat-pay/rotate-v3",
        token=admin,
        body={"api_v3_key": "short"},
    )
    results.append(
        check(
            "VP06-20 v3 长度 422",
            code == 422 and "32" in _err_text(bad_v3),
            f"{code} {_err_text(bad_v3)}",
        )
    )

    code, forbidden = req("GET", "/admin/shop/payment-onboarding", token=merchant)
    results.append(
        check(
            "VP06-13 商家无平台权 TC-P06-P01",
            code in (401, 403),
            f"{code} {forbidden}",
        )
    )
    code, exp_forbidden = req("POST", "/admin/shop/payment-onboarding/export", token=merchant, body={})
    results.append(
        check(
            "VP06-P01b 商家 POST 导出 403",
            code in (401, 403),
            f"{code} {exp_forbidden}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP06 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
