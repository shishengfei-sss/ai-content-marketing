#!/usr/bin/env python3
"""P09 商品审核。对照 PRD 06#p09-pending-queue · #p09-review-panel · #p09a · #p09b · #p09c。"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_m4 import _ensure_cms_refs, _ensure_merchant_token  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "ProductReviews.vue"


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


def _submit_product(merchant: str, refs: dict, name: str) -> str | None:
    code, data = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "digital",
            "name": name,
            "price_cents": 9900,
            "cover_url": refs["cover_url"],
            "ref_type": "digital_package",
            "ref_id": refs["package_id"],
        },
    )
    if code != 200:
        return None
    code_s, sub = req("POST", f"/shop/products/{data['id']}/submit-review", token=merchant, body={})
    if code_s != 200:
        return None
    return sub.get("review_id")


def main() -> int:
    results: list[bool] = []
    stamp = time.strftime("%H%M%S")

    results.append(
        check(
            "VP09-UI 待审/已审/面板完备 TC-P09-L01",
            _page_has(
                WEB,
                "#p09-pending-queue",
                "#p09-review-panel",
                "#p09a",
                "#p09b",
                "待审队列",
                "已审出队",
                "搜索商品 / 商家",
                "列设置",
                "导出",
                "商品快照",
                "机审明细",
                "关联内容",
                "审核日志",
                "内部备注（选填）",
                "原因码",
                "确认驳回",
                "影响说明（只读）",
                "确认强制下架",
                "审核状态（只读）",
                "是否首单公域",
                "预览买家页",
                'data-testid="shop-product-reviews"',
            )
            and "买家页预览未接通" not in WEB.read_text(encoding="utf-8"),
            str(WEB),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    code, listed = req("GET", "/admin/shop/product-reviews?status=pending&page_size=20", token=admin)
    results.append(
        check(
            "VP09-L01 待审队列 TC-P09-L01",
            code == 200
            and isinstance(listed, dict)
            and "items" in listed
            and "pending_count" in listed,
            f"{code} {_err(listed)}",
        )
    )
    code_q, qdata = req(
        "GET",
        "/admin/shop/product-reviews?status=pending&q=___no_hit_xyz___",
        token=admin,
    )
    results.append(
        check(
            "VP09-L01b 搜索空态",
            code_q == 200 and (qdata or {}).get("total", 0) == 0,
            f"{code_q} {(qdata or {}).get('total')}",
        )
    )
    code_fp, fp_yes = req(
        "GET",
        "/admin/shop/product-reviews?status=pending&first_public=yes",
        token=admin,
    )
    code_fn, fp_no = req(
        "GET",
        "/admin/shop/product-reviews?status=pending&first_public=no",
        token=admin,
    )
    results.append(
        check(
            "VP09-L02 是否首单公域筛选",
            code_fp == 200
            and code_fn == 200
            and isinstance(fp_yes, dict)
            and "items" in fp_yes
            and isinstance(fp_no, dict)
            and "items" in fp_no,
            f"{code_fp}/{code_fn} {_err(fp_yes)} {_err(fp_no)}",
        )
    )

    merchant = _ensure_merchant_token()
    refs = _ensure_cms_refs(merchant)
    rid = _submit_product(merchant, refs, f"QA待审资料_{stamp}")
    results.append(check("VP09-F00 提审入队", bool(rid), str(rid)))

    if rid:
        code_d, detail = req("GET", f"/admin/shop/product-reviews/{rid}", token=admin)
        results.append(
            check(
                "VP09-D01 审核面板字段",
                code_d == 200
                and (detail or {}).get("product_name")
                and "snapshot_json" in (detail or {})
                and "auto_result" in (detail or {}),
                f"{code_d} {_err(detail)}",
            )
        )
        code_pv, preview = req(
            "GET",
            f"/admin/shop/product-reviews/{rid}/buyer-preview",
            token=admin,
        )
        results.append(
            check(
                "VP09-PV01 买家页预览未上架水印",
                code_pv == 200
                and (preview or {}).get("watermark") == "未上架"
                and (preview or {}).get("product_name"),
                f"{code_pv} {_err(preview)}",
            )
        )
        code_a, approved = req("POST", f"/admin/shop/product-reviews/{rid}/approve", token=admin, body={})
        results.append(
            check(
                "VP09-F01 人审通过 TC-P09-F01",
                code_a == 200 and (approved or {}).get("manual_result") == "approved",
                f"{code_a} {_err(approved)}",
            )
        )
        pid = (approved or detail or {}).get("product_id")
        if pid:
            code_p, pub = req("POST", f"/shop/products/{pid}/publish", token=merchant)
            results.append(
                check(
                    "VP09-F01b 通过后可上架",
                    code_p == 200 and (pub or {}).get("status") == "on_sale",
                    f"{code_p} {_err(pub)}",
                )
            )
            code_off, off = req(
                "POST",
                f"/admin/shop/product-reviews/{rid}/force-off-sale",
                token=admin,
                body={"reason": "QA强制下架验收"},
            )
            results.append(
                check(
                    "VP09-B01 强制下架",
                    code_off == 200 and (off or {}).get("product_status") == "off_sale",
                    f"{code_off} {_err(off)}",
                )
            )
        else:
            results.append(check("VP09-F01b 通过后可上架", False, "no pid"))
            results.append(check("VP09-B01 强制下架", False, "skip"))
    else:
        results.append(check("VP09-D01 审核面板字段", False, "no review"))
        results.append(check("VP09-PV01 买家页预览未上架水印", False, "no review"))
        results.append(check("VP09-F01 人审通过 TC-P09-F01", False, "no review"))
        results.append(check("VP09-F01b 通过后可上架", False, "skip"))
        results.append(check("VP09-B01 强制下架", False, "skip"))

    rid2 = _submit_product(merchant, refs, f"QA待驳回_{stamp}")
    if rid2:
        code_e, empty = req(
            "POST",
            f"/admin/shop/product-reviews/{rid2}/reject",
            token=admin,
            body={"reject_reason": ""},
        )
        results.append(
            check(
                "VP09-E01 驳回无原因 422 TC-P09-E01",
                code_e == 422 and "驳回原因" in _err(empty),
                f"{code_e} {_err(empty)}",
            )
        )
        code_r, rej = req(
            "POST",
            f"/admin/shop/product-reviews/{rid2}/reject",
            token=admin,
            body={"reject_code": "sensitive", "reject_reason": "材料含违禁承诺请改"},
        )
        results.append(
            check(
                "VP09-A01 确认驳回",
                code_r == 200 and (rej or {}).get("manual_result") == "rejected",
                f"{code_r} {_err(rej)}",
            )
        )
    else:
        results.append(check("VP09-E01 驳回无原因 422 TC-P09-E01", False, "no review"))
        results.append(check("VP09-A01 确认驳回", False, "skip"))

    cs = _ensure_cs_user()
    code_cs, data_cs = req("GET", "/admin/shop/product-reviews", token=cs)
    results.append(
        check(
            "VP09-P01 无 review 权 403 TC-P09-P01",
            code_cs == 403,
            f"{code_cs} {_err(data_cs)}",
        )
    )

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'} {sum(1 for r in results if r)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
