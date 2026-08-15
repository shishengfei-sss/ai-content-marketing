#!/usr/bin/env python3
"""P02-E 分配管家 · P02-B-T 编辑标签。对照 PRD 06#p02e · #p02b-tags。"""

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

LIST = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "MerchantsList.vue"
DETAIL = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "MerchantDetail.vue"
ASSIGN = REPO_ROOT / "apps" / "web" / "src" / "components" / "shop" / "ShopAssignManagerDialog.vue"
TAGS = REPO_ROOT / "apps" / "web" / "src" / "components" / "shop" / "ShopMerchantTagsDialog.vue"


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


def _ensure_cs(phone: str, password: str, name: str) -> str:
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
    from app.services.auth_service import hash_password

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name=name,
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            )
            db.add(u)
        else:
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
            u.hashed_password = hash_password(password)
            u.display_name = name
            u.is_active = True
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def _create_and_approve(admin: str) -> str | None:
    code, opts = req("GET", "/admin/shop/onboarding/tenant-options", token=admin)
    items = (opts or {}).get("items") or []
    if code != 200 or not items:
        return None
    tid = items[0]["tenant_id"]
    code, created = req(
        "POST",
        "/admin/shop/onboarding/applications",
        token=admin,
        body={
            "tenant_id": tid,
            "entity_type": "enterprise",
            "legal_name": f"验收改派主体-{uuid.uuid4().hex[:6]}",
            "display_name": f"验收改派商家-{uuid.uuid4().hex[:6]}",
            "contact_name": "测试联系人",
            "contact_mobile": "13900004444",
            "unified_social_credit_code": "91110000MA01234568",
            "legal_rep_name": "李四",
        },
    )
    if code != 201:
        return None
    app_id = created.get("id")
    code_a, approved = req(
        "POST",
        f"/admin/shop/onboarding/applications/{app_id}/approve",
        token=admin,
        body={"plan_label": "7天试用基础版", "trial_days": 7, "store_quota": 1},
    )
    if code_a != 200:
        return None
    return approved.get("tenant_id") or tid


def _close(admin: str, tid: str) -> bool:
    code, _ = req(
        "POST",
        f"/admin/shop/merchants/{tid}/close",
        token=admin,
        body={
            "reason_code": "other",
            "reason_text": "验收打标只读清退",
            "ack_irreversible": True,
        },
    )
    return code == 200


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "VP02E-UI 分配管家栏位 #p02e",
            _page_has(ASSIGN, "新管家", "确认分配", "影响说明（只读）", "当前管家（只读）", "shop-assign-manager", "已选")
            and _page_has(LIST, "分配管家", "#p02e", "shop-batch-assign", "单次最多分配 50 家")
            and _page_has(DETAIL, "分配管家")
            and "本批未开放" not in DETAIL.read_text(encoding="utf-8"),
            f"{ASSIGN.name} / {LIST.name}",
        )
    )
    results.append(
        check(
            "VP02T-UI 编辑标签栏位 #p02b-tags",
            _page_has(
                TAGS,
                "已选标签",
                "添加标签",
                "常用（点击添加）",
                "续费意向",
                "高价值",
                "需回访",
                "华东区",
                "对公客户",
                "保存",
                "shop-merchant-tags",
            )
            and _page_has(LIST, "编辑标签", "placeholder=\"标签\"")
            and "字典未接" not in LIST.read_text(encoding="utf-8"),
            f"{TAGS.name}",
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    cs = _ensure_cs("13800000088", "cs12345678", "商城管家测试")
    _ensure_cs("13800000089", "cs12345678", "商城管家乙")

    code_cs_list, cs_list = req("GET", "/admin/shop/cs-users", token=cs)
    results.append(
        check(
            "VP02E-F01-B2 管家无分配权 403",
            code_cs_list == 403,
            f"{code_cs_list} {_err(cs_list)}",
        )
    )

    code_users, users = req("GET", "/admin/shop/cs-users", token=admin)
    cs_items = (users or {}).get("items") or []
    results.append(
        check(
            "VP02E-CS 管家下拉含启用商家管家",
            code_users == 200 and len(cs_items) >= 2,
            f"{code_users} n={len(cs_items)} {_err(users)}",
        )
    )

    tid = _create_and_approve(admin)
    if not tid:
        for name in (
            "TC-P02E-E01 目标空 422",
            "TC-P02E-F01 改派管家",
            "VP02T-F01 打已有标签",
            "VP02T-E01 管家新建标签 403",
            "VP02T-F02 运营新建标签",
            "VP02T-E02 清退只读",
            "VP02E-P 未入驻预分配",
        ):
            results.append(check(name, False, "无可用租户入驻"))
    else:
        code_empty, empty = req(
            "POST",
            f"/admin/shop/merchants/{tid}/assign",
            token=admin,
            body={},
        )
        results.append(
            check(
                "TC-P02E-E01 目标空 422",
                code_empty == 422 and "请选择新管家" in _err(empty),
                f"{code_empty} {_err(empty)}",
            )
        )

        code_tags, tag_dict = req("GET", "/admin/shop/merchant-tags", token=admin)
        items = (tag_dict or {}).get("items") or []
        names = {t.get("name") for t in items}
        seed_ok = names.issuperset({"续费意向", "高价值", "需回访", "华东区", "对公客户"})
        results.append(
            check(
                "VP02T-DICT 常用五标签已种子",
                code_tags == 200 and seed_ok,
                f"{code_tags} {sorted(names)}",
            )
        )
        intent = next((t for t in items if t.get("name") == "续费意向"), None)
        if intent:
            code_put, put = req(
                "PUT",
                f"/admin/shop/merchants/{tid}/tags",
                token=admin,
                body={"tag_ids": [intent["id"]]},
            )
            results.append(
                check(
                    "VP02T-F01 打已有标签",
                    code_put == 200 and "续费意向" in (put.get("tags") or []),
                    f"{code_put} {put.get('tags')} {_err(put)}",
                )
            )
            code_f, filtered = req(
                "GET",
                f"/admin/shop/merchants?tag_ids={intent['id']}",
                token=admin,
            )
            hit = any(i.get("tenant_id") == tid for i in (filtered or {}).get("items") or [])
            results.append(
                check(
                    "VP02T-L01 列表按标签筛选",
                    code_f == 200 and hit,
                    f"{code_f} hit={hit} total={(filtered or {}).get('total')}",
                )
            )
        else:
            results.append(check("VP02T-F01 打已有标签", False, "无续费意向"))
            results.append(check("VP02T-L01 列表按标签筛选", False, "跳过"))

        cs88 = next((u for u in cs_items if u.get("display_name") == "商城管家测试"), None) or (
            cs_items[0] if cs_items else None
        )
        if cs88:
            req(
                "POST",
                f"/admin/shop/merchants/{tid}/assign",
                token=admin,
                body={"account_manager_user_id": cs88["id"], "remark": "先派给管家以便测打标权限"},
            )
        new_name = f"验{uuid.uuid4().hex[:5]}"
        code_cs_new, cs_new = req(
            "PUT",
            f"/admin/shop/merchants/{tid}/tags",
            token=cs,
            body={"tag_ids": [intent["id"]] if intent else [], "create_names": [new_name]},
        )
        results.append(
            check(
                "VP02T-E01 管家新建标签 403",
                code_cs_new == 403 and "无权限创建新标签" in _err(cs_new),
                f"{code_cs_new} {_err(cs_new)}",
            )
        )
        code_ops, ops = req(
            "PUT",
            f"/admin/shop/merchants/{tid}/tags",
            token=admin,
            body={
                "tag_ids": [intent["id"]] if intent else [],
                "create_names": [new_name],
            },
        )
        results.append(
            check(
                "VP02T-F02 运营新建标签",
                code_ops == 200 and new_name in (ops.get("tags") or []),
                f"{code_ops} {ops.get('tags')} {_err(ops)}",
            )
        )

        target = next((u for u in cs_items if u.get("display_name") == "商城管家乙"), None) or (
            cs_items[1] if len(cs_items) > 1 else None
        )
        if not target:
            results.append(check("TC-P02E-F01 改派管家", False, "无目标管家"))
            results.append(check("VP02E-E02 新管家与当前相同 422", False, "跳过"))
        else:
            code_a, assigned = req(
                "POST",
                f"/admin/shop/merchants/{tid}/assign",
                token=admin,
                body={"account_manager_user_id": target["id"], "remark": "验收改派"},
            )
            results.append(
                check(
                    "TC-P02E-F01 改派管家",
                    code_a == 200 and str(assigned.get("account_manager_user_id")) == str(target["id"]),
                    f"{code_a} {assigned.get('account_manager_user_id')} {_err(assigned)}",
                )
            )
            same, same_body = req(
                "POST",
                f"/admin/shop/merchants/{tid}/assign",
                token=admin,
                body={"account_manager_user_id": target["id"]},
            )
            results.append(
                check(
                    "VP02E-E02 新管家与当前相同 422",
                    same == 422,
                    f"{same} {_err(same_body)}",
                )
            )

        close_tid = _create_and_approve(admin)
        if close_tid and _close(admin, close_tid):
            code_ro, ro = req(
                "PUT",
                f"/admin/shop/merchants/{close_tid}/tags",
                token=admin,
                body={"tag_ids": [intent["id"]] if intent else []},
            )
            results.append(
                check(
                    "VP02T-E02 清退只读",
                    code_ro == 422 and "只读" in _err(ro),
                    f"{code_ro} {_err(ro)}",
                )
            )
            code_as, asg = req(
                "POST",
                f"/admin/shop/merchants/{close_tid}/assign",
                token=admin,
                body={"account_manager_user_id": cs_items[0]["id"]} if cs_items else {},
            )
            results.append(
                check(
                    "VP02E-E03 清退不可分配",
                    code_as == 422 and "不可分配" in _err(asg),
                    f"{code_as} {_err(asg)}",
                )
            )
        else:
            results.append(check("VP02T-E02 清退只读", False, "未能清退"))
            results.append(check("VP02E-E03 清退不可分配", False, "跳过"))

    code_opts, opts = req("GET", "/admin/shop/onboarding/tenant-options", token=admin)
    prospect = ((opts or {}).get("items") or [None])[0]
    if prospect and cs_items:
        code_p, pbody = req(
            "POST",
            f"/admin/shop/merchants/{prospect['tenant_id']}/assign",
            token=admin,
            body={"account_manager_user_id": cs_items[0]["id"], "remark": "预分配验收"},
        )
        results.append(
            check(
                "VP02E-P 未入驻预分配",
                code_p == 200
                and pbody.get("onboarding_status") == "not_onboarded"
                and str(pbody.get("account_manager_user_id")) == str(cs_items[0]["id"]),
                f"{code_p} {pbody.get('onboarding_status')} {pbody.get('account_manager_user_id')} {_err(pbody)}",
            )
        )
    else:
        results.append(check("VP02E-P 未入驻预分配", False, f"{code_opts} n={len((opts or {}).get('items') or [])}"))

    code_cs_batch, cs_batch = req(
        "POST",
        "/admin/shop/merchants/batch-assign",
        token=cs,
        body={
            "tenant_ids": [str(uuid.uuid4())],
            "account_manager_user_id": cs_items[0]["id"] if cs_items else str(uuid.uuid4()),
        },
    )
    results.append(
        check(
            "VP02E-B0 管家批量 403",
            code_cs_batch == 403,
            f"{code_cs_batch} {_err(cs_batch)}",
        )
    )
    code_51, body_51 = req(
        "POST",
        "/admin/shop/merchants/batch-assign",
        token=admin,
        body={
            "tenant_ids": [str(uuid.uuid4()) for _ in range(51)],
            "account_manager_user_id": cs_items[0]["id"] if cs_items else str(uuid.uuid4()),
        },
    )
    results.append(
        check(
            "VP02E-B1 超过 50 家",
            code_51 == 422 and "50" in _err(body_51),
            f"{code_51} {_err(body_51)}",
        )
    )

    batch_ids: list[str] = []
    for _ in range(2):
        extra = _create_and_approve(admin)
        if extra and extra not in batch_ids:
            batch_ids.append(extra)
    if len(batch_ids) < 2:
        code_list, listing = req(
            "GET", "/admin/shop/merchants?page_size=50&onboarding_status=active", token=admin
        )
        for row in (listing or {}).get("items") or []:
            rid = row.get("tenant_id")
            if rid and rid not in batch_ids:
                batch_ids.append(rid)
            if len(batch_ids) >= 2:
                break
        if code_list != 200 and len(batch_ids) < 2:
            pass

    target_cs = None
    if cs_items:
        target_cs = next((u for u in cs_items if u.get("display_name") == "商城管家乙"), None) or cs_items[-1]
    if len(batch_ids) >= 2 and target_cs:
        closed = _create_and_approve(admin)
        if closed and _close(admin, closed):
            code_mix, mix = req(
                "POST",
                "/admin/shop/merchants/batch-assign",
                token=admin,
                body={
                    "tenant_ids": [batch_ids[0], closed],
                    "account_manager_user_id": target_cs["id"],
                },
            )
            results.append(
                check(
                    "VP02E-B2 含不可分配整批失败",
                    code_mix == 422 and "所选含不可分配商家" in _err(mix),
                    f"{code_mix} {_err(mix)}",
                )
            )
        else:
            results.append(check("VP02E-B2 含不可分配整批失败", False, "未能造清退商家"))
        code_ok, okb = req(
            "POST",
            "/admin/shop/merchants/batch-assign",
            token=admin,
            body={
                "tenant_ids": batch_ids[:2],
                "account_manager_user_id": target_cs["id"],
                "remark": "批量验收",
            },
        )
        results.append(
            check(
                "VP02E-B3 批量分配两家",
                code_ok == 200 and okb.get("assigned") == 2,
                f"{code_ok} {okb} {_err(okb)}",
            )
        )
        if code_ok == 200:
            code_d, det = req("GET", f"/admin/shop/merchants/{batch_ids[0]}", token=admin)
            results.append(
                check(
                    "VP02E-B4 批量后详情管家一致",
                    code_d == 200 and str(det.get("account_manager_user_id")) == str(target_cs["id"]),
                    f"{code_d} {det.get('account_manager_user_id') if isinstance(det, dict) else det}",
                )
            )
        else:
            results.append(check("VP02E-B4 批量后详情管家一致", False, "批量未成功"))
    else:
        results.append(check("VP02E-B2 含不可分配整批失败", False, f"n={len(batch_ids)}"))
        results.append(check("VP02E-B3 批量分配两家", False, f"n={len(batch_ids)}"))
        results.append(check("VP02E-B4 批量后详情管家一致", False, "跳过"))

    failed = sum(1 for x in results if not x)
    print(f"\nP02-E/T {len(results) - failed}/{len(results)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
