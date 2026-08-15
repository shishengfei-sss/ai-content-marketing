#!/usr/bin/env python3
"""P03 入驻审核。对照 PRD 06#p03-list · #p03-detail · #p03-approve · #p03-reject。"""

from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "OnboardingApplications.vue"


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


def _create_pending(admin: str, *, entity_type: str = "enterprise", **extra) -> str | None:
    code, opts = req("GET", "/admin/shop/onboarding/tenant-options", token=admin)
    items = (opts or {}).get("items") or []
    if code != 200 or not items:
        return None
    tid = items[0]["tenant_id"]
    body: dict = {
        "tenant_id": tid,
        "entity_type": entity_type,
        "legal_name": f"入驻验收主体-{uuid.uuid4().hex[:6]}",
        "display_name": f"入驻验收商家-{uuid.uuid4().hex[:6]}",
        "contact_name": "测试联系人",
        "contact_mobile": "13900002222",
        "qualification_files": {},
        "ocr_results": [],
        "remark": "P03 验收脚本发起",
    }
    if entity_type == "personal":
        body["id_no"] = "110101199001011234"
    else:
        body["unified_social_credit_code"] = "91110000MA01234567"
        body["legal_rep_name"] = "张三"
        body["bank_account_info"] = {
            "account_no": "123456789012345678",
            "bank_name": "招商银行",
            "account_name": "P03验收主体",
        }
    body.update(extra)
    code, created = req(
        "POST",
        "/admin/shop/onboarding/applications",
        token=admin,
        body=body,
    )
    if code != 201:
        return None
    return created.get("id")


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


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "VP03-UI 列表/审核栏位完备 TC-P03-L01",
            _page_has(
                WEB,
                "#p03-list",
                "#p03-detail",
                "#p03-approve",
                "#p03-reject",
                "全部申请",
                "待审",
                "已通过",
                "已驳回",
                "搜索商家名",
                "列设置",
                "导出",
                "高级筛选",
                "申请单号",
                "主体类型",
                "申请时间",
                "发起方式",
                "首开套餐",
                "分配商家管家",
                "驳回原因码",
                "确认通过并开通",
                "确认驳回",
                "审核日志",
                "对公账户",
                "将创建（只读）",
                "商家（正常）+ 订阅快照",
                'data-testid="shop-onboarding"',
                'data-testid="btn-reveal-contact-mobile"',
            ),
            str(WEB),
        )
    )
    results.append(
        check(
            "VP03-UI 申请单号非 UUID 派生",
            _page_has(WEB, "row.application_no", "current.value?.application_no")
            and "UUID 派生" not in WEB.read_text(encoding="utf-8")
            and "applicationNoOf" not in WEB.read_text(encoding="utf-8"),
            str(WEB),
        )
    )
    results.append(
        check(
            "VP03-UI2 无明文揭露缺口文案",
            _page_has(WEB, "审核日志")
            and "明文揭露本批未接" not in WEB.read_text(encoding="utf-8")
            and "本批未接" not in WEB.read_text(encoding="utf-8"),
            str(WEB),
        )
    )

    admin = login("13800000000", "admin123456", "platform")

    code, reasons = req("GET", "/admin/shop/onboarding/reject-reasons", token=admin)
    items = (reasons or {}).get("items") or []
    codes = {i.get("code") for i in items}
    results.append(
        check(
            "VP03-R01 驳回原因码 15 项",
            code == 200
            and len(items) == 15
            and "illegible_docs" in codes
            and "need_supplement" in codes
            and "other" in codes
            and len((reasons or {}).get("groups") or []) == 5,
            f"{code} n={len(items)} groups={len((reasons or {}).get('groups') or [])}",
        )
    )

    code, opts = req(
        "GET",
        "/admin/shop/onboarding/approve-options?entity_type=enterprise",
        token=admin,
    )
    results.append(
        check(
            "VP03-O01 通过并开通下拉",
            code == 200
            and isinstance((opts or {}).get("plans"), list)
            and isinstance((opts or {}).get("managers"), list)
            and (opts or {}).get("default_manager_user_id"),
            f"{code} plans={len((opts or {}).get('plans') or [])} mgr={len((opts or {}).get('managers') or [])}",
        )
    )

    code, listing = req("GET", "/admin/shop/onboarding/applications?status=pending", token=admin)
    results.append(
        check(
            "VP03-L01 待审列表 TC-P03-L01",
            code == 200 and isinstance((listing or {}).get("items"), list),
            f"{code} total={(listing or {}).get('total')}",
        )
    )
    code_miss, miss = req(
        "GET",
        "/admin/shop/onboarding/applications?q=__no_such_merchant_zzz__",
        token=admin,
    )
    results.append(
        check(
            "VP03-L01b 搜索空态 TC-P03-L01-S2",
            code_miss == 200 and (miss or {}).get("total", 1) == 0,
            f"{code_miss} total={(miss or {}).get('total')}",
        )
    )

    app_id = _create_pending(admin)
    if app_id:
        import json as _json

        raw_mobile = "13900002222"
        raw_bank = "123456789012345678"
        code_d, detail = req(
            "GET",
            f"/admin/shop/onboarding/applications/{app_id}",
            token=admin,
        )
        dumped = _json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else str(detail)
        logs = (detail or {}).get("review_logs") or []
        actions = {x.get("action") for x in logs if isinstance(x, dict)}
        app_no = str((detail or {}).get("application_no") or "")
        results.append(
            check(
                "VP03-N01 申请单号编码规则",
                code_d == 200
                and bool(re.fullmatch(r"OB\d{12}", app_no)),
                f"{code_d} application_no={app_no}",
            )
        )
        code_q, by_no = req(
            "GET",
            f"/admin/shop/onboarding/applications?q={app_no}&page_size=20",
            token=admin,
        )
        ids = {str(i.get("id")) for i in ((by_no or {}).get("items") or [])}
        nos = {str(i.get("application_no") or "") for i in ((by_no or {}).get("items") or [])}
        results.append(
            check(
                "VP03-N02 按申请单号搜索",
                code_q == 200 and str(app_id) in ids and app_no in nos,
                f"{code_q} n={len(ids)} nos={list(nos)[:3]}",
            )
        )
        results.append(
            check(
                "VP03-S01 GET 详情脱敏且含提交日志 TC-P03-S01",
                code_d == 200
                and (detail or {}).get("contact_mobile") == "139****2222"
                and raw_mobile not in dumped
                and raw_bank not in dumped
                and "submitted" in actions,
                f"{code_d} mobile={(detail or {}).get('contact_mobile')} actions={sorted(actions)}",
            )
        )
        results.append(
            check(
                "VP03-S01b 企业详情对公尾号 TC-P03-S01",
                code_d == 200
                and "尾号" in str((detail or {}).get("bank_account_display") or "")
                and "5678" in str((detail or {}).get("bank_account_display") or ""),
                f"display={(detail or {}).get('bank_account_display')}",
            )
        )
        code_list, listing_s = req(
            "GET",
            "/admin/shop/onboarding/applications?status=pending&page_size=100",
            token=admin,
        )
        hit = next(
            (i for i in ((listing_s or {}).get("items") or []) if str(i.get("id")) == str(app_id)),
            None,
        )
        results.append(
            check(
                "VP03-S01c 列表手机脱敏",
                code_list == 200 and hit is not None and hit.get("contact_mobile") == "139****2222",
                f"{code_list} hit={hit.get('contact_mobile') if hit else None}",
            )
        )
        code_rev, rev = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/reveal-sensitive",
            token=admin,
            body={"field": "contact_mobile"},
        )
        results.append(
            check(
                "VP03-S02 运营揭露经营联系人手机 TC-P03-S02",
                code_rev == 200 and (rev or {}).get("value") == raw_mobile,
                f"{code_rev} {_err(rev)}",
            )
        )
        code_bank, bank = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/reveal-sensitive",
            token=admin,
            body={"field": "bank_account_no"},
        )
        results.append(
            check(
                "VP03-S02b 运营揭露对公账号",
                code_bank == 200 and (bank or {}).get("value") == raw_bank,
                f"{code_bank} {_err(bank)}",
            )
        )
        code_d2, detail2 = req(
            "GET",
            f"/admin/shop/onboarding/applications/{app_id}",
            token=admin,
        )
        summaries = [x.get("summary") for x in ((detail2 or {}).get("review_logs") or [])]
        results.append(
            check(
                "VP03-S03 审核日志含查看经营联系人手机",
                code_d2 == 200 and "查看经营联系人手机" in summaries,
                f"{code_d2} summaries={summaries[:8]}",
            )
        )
        fin_tok = _ensure_finance_user()
        code_fin, data_fin = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/reveal-sensitive",
            token=fin_tok,
            body={"field": "contact_mobile"},
        )
        results.append(
            check(
                "VP03-S04 财务揭露 403 无查看权限 TC-P03-P02",
                code_fin == 403 and "无查看权限" in _err(data_fin),
                f"{code_fin} {_err(data_fin)}",
            )
        )
        app_personal = _create_pending(admin, entity_type="personal")
        if app_personal:
            raw_id = "110101199001011234"
            code_pd, pdetail = req(
                "GET",
                f"/admin/shop/onboarding/applications/{app_personal}",
                token=admin,
            )
            pdump = _json.dumps(pdetail, ensure_ascii=False) if isinstance(pdetail, dict) else str(pdetail)
            code_pid, pid = req(
                "POST",
                f"/admin/shop/onboarding/applications/{app_personal}/reveal-sensitive",
                token=admin,
                body={"field": "id_no"},
            )
            results.append(
                check(
                    "VP03-S05 个人身份证脱敏与揭露",
                    code_pd == 200
                    and raw_id not in pdump
                    and code_pid == 200
                    and (pid or {}).get("value") == raw_id,
                    f"get={code_pd} id_no={(pdetail or {}).get('id_no')} reveal={code_pid} {_err(pid)}",
                )
            )
        else:
            results.append(check("VP03-S05 个人身份证脱敏与揭露", False, "无可用租户"))

        code_e, empty = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/reject",
            token=admin,
            body={"reject_code": "illegible_docs", "reject_reason": ""},
        )
        results.append(
            check(
                "VP03-E01 驳回原因为空 422 TC-P03-E01",
                code_e == 422 and "驳回原因" in _err(empty),
                f"{code_e} {_err(empty)}",
            )
        )
        code_bad, bad = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/reject",
            token=admin,
            body={"reject_code": "duplicate", "reject_reason": "材料模糊请重传营业执照清晰照片"},
        )
        results.append(
            check(
                "VP03-E01b 原因码无效 422",
                code_bad == 422 and "原因码" in _err(bad),
                f"{code_bad} {_err(bad)}",
            )
        )
        code_r, rej = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/reject",
            token=admin,
            body={
                "reject_code": "illegible_docs",
                "reject_reason": "材料模糊请重传营业执照清晰照片",
            },
        )
        results.append(
            check(
                "VP03-F02 驳回 TC-P03-F02",
                code_r == 200 and (rej or {}).get("status") == "rejected",
                f"{code_r} {_err(rej)}",
            )
        )
        rej_logs = (rej or {}).get("review_logs") or []
        rej_actions = {x.get("action") for x in rej_logs if isinstance(x, dict)}
        results.append(
            check(
                "VP03-S06 驳回后审核日志含驳回",
                code_r == 200 and "rejected" in rej_actions,
                f"actions={sorted(rej_actions)}",
            )
        )
    else:
        results.append(check("VP03-E01 驳回原因为空 422 TC-P03-E01", False, "无可用租户"))
        results.append(check("VP03-E01b 原因码无效 422", False, "跳过"))
        results.append(check("VP03-F02 驳回 TC-P03-F02", False, "跳过"))

    app_ok = _create_pending(admin)
    if app_ok:
        plan_id = ((opts or {}).get("plans") or [{}])[0].get("id")
        body: dict = {"trial_days": 7, "store_quota": 1}
        if plan_id:
            body["plan_id"] = plan_id
        else:
            body["plan_label"] = "7天试用基础版"
        mgr = (opts or {}).get("default_manager_user_id")
        if mgr:
            body["account_manager_user_id"] = mgr
        code_a, approved = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_ok}/approve",
            token=admin,
            body=body,
        )
        results.append(
            check(
                "VP03-F01 审核通过 TC-P03-F01",
                code_a == 200 and approved.get("merchant_id") is not None,
                f"{code_a} {_err(approved)}",
            )
        )
        code_ad, adetail = req(
            "GET",
            f"/admin/shop/onboarding/applications/{app_ok}",
            token=admin,
        )
        a_actions = {x.get("action") for x in ((adetail or {}).get("review_logs") or []) if isinstance(x, dict)}
        results.append(
            check(
                "VP03-S07 通过后审核日志含通过",
                code_ad == 200 and "approved" in a_actions,
                f"{code_ad} actions={sorted(a_actions)}",
            )
        )
        mcode = str((adetail or {}).get("merchant_code") or "")
        results.append(
            check(
                "VP03-N03 通过后商家编码",
                bool(re.fullmatch(r"SH\d{12}", mcode)),
                f"{code_ad} merchant_code={mcode}",
            )
        )
        tid = (adetail or {}).get("tenant_id")
        code_md, mdetail = req("GET", f"/admin/shop/merchants/{tid}", token=admin) if tid else (0, {})
        results.append(
            check(
                "VP03-N04 详情商家编码同源",
                code_md == 200 and (mdetail or {}).get("merchant_code") == mcode,
                f"{code_md} {(mdetail or {}).get('merchant_code')}",
            )
        )
        sub_no = str((approved or {}).get("subscription_no") or "")
        sub_id = (approved or {}).get("subscription_id")
        results.append(
            check(
                "VP03-N05 通过后写出订阅行",
                bool(re.fullmatch(r"DY\d{12}", sub_no)) and sub_id,
                f"{code_a} subscription_no={sub_no}",
            )
        )
        code_subs, subs = (
            req("GET", f"/admin/shop/merchants/{tid}/subscriptions", token=admin) if tid else (0, {})
        )
        sub_items = (subs or {}).get("items") or []
        hit_sub = any(str(i.get("id")) == str(sub_id) and i.get("subscription_no") == sub_no for i in sub_items)
        results.append(
            check(
                "VP03-N06 商家订阅列表可见首开",
                code_subs == 200 and hit_sub,
                f"{code_subs} n={len(sub_items)} hit={hit_sub}",
            )
        )
        code_again, again = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_ok}/approve",
            token=admin,
            body=body,
        )
        results.append(
            check(
                "VP03-E02 已通过单再通过 409 TC-P03-E02",
                code_again == 409,
                f"{code_again} {_err(again)}",
            )
        )
    else:
        results.append(check("VP03-F01 审核通过 TC-P03-F01", False, "无可用租户"))
        results.append(check("VP03-S07 通过后审核日志含通过", False, "跳过"))
        results.append(check("VP03-N03 通过后商家编码", False, "跳过"))
        results.append(check("VP03-N04 详情商家编码同源", False, "跳过"))
        results.append(check("VP03-N05 通过后写出订阅行", False, "跳过"))
        results.append(check("VP03-N06 商家订阅列表可见首开", False, "跳过"))
        results.append(check("VP03-E02 已通过单再通过 409 TC-P03-E02", False, "跳过"))

    cs = _ensure_cs_user()
    code_cs, data_cs = req(
        "POST",
        f"/admin/shop/onboarding/applications/{app_ok or app_id or uuid.uuid4()}/approve",
        token=cs,
        body={"plan_label": "7天试用基础版", "trial_days": 7},
    )
    results.append(
        check(
            "VP03-P01 无审核权 403 TC-P03-P01",
            code_cs == 403,
            f"{code_cs} {_err(data_cs)}",
        )
    )
    code_cs_opt, opt_cs = req("GET", "/admin/shop/onboarding/approve-options", token=cs)
    results.append(
        check(
            "VP03-P01b 管家无通过选项 403",
            code_cs_opt == 403,
            f"{code_cs_opt} {_err(opt_cs)}",
        )
    )

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'} {sum(1 for r in results if r)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
