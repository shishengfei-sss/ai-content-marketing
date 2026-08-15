#!/usr/bin/env python3
"""P10 套餐配置。对照 PRD 06#p10-dict · #p10a · #p10f · #p10h · #p10-plans · #p10d。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "PlanConfig.vue"


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


def _leaf_value(item: dict):
    vt = item.get("value_type")
    if vt == "bool":
        return True
    if vt == "unlimited":
        return "unlimited"
    return 3


def _pick_leaf(admin: str) -> tuple[str, object] | None:
    code, data = req("GET", "/admin/shop/feature-dictionary?node_type=leaf&is_active=true", token=admin)
    if code != 200 or not isinstance(data, list):
        return None
    preferred = next((x for x in data if x.get("code") == "quota.max_shops"), None)
    item = preferred or next((x for x in data if x.get("code")), None)
    if not item:
        return None
    return item["code"], _leaf_value(item)


def main() -> int:
    results: list[bool] = []
    stamp = time.strftime("%H%M%S")

    results.append(
        check(
            "VP10-UI 字典与模板完备 TC-P10-F01",
            _page_has(
                WEB,
                "#p10-dict",
                "#p10-plans",
                "#p10h",
                'label="功能字典"',
                'label="套餐模板"',
                "搜索 code / 名称",
                "名称 / 编码",
                "叠加模式",
                "埋点标识",
                "+ 新增分组",
                "+ 新增子功能",
                "+ 新建主套餐",
                "+ 新建加购包",
                "列设置",
                "导出",
                "搜索套餐名",
                "互斥组",
                "每日提审",
                "适用主体",
                "套餐能力配置",
                "保存后上架",
                "分组名称",
                "所属分组",
                "业务分类",
                "叠加合并方式",
                "确认停用",
                "高级筛选",
                "刷新预览",
                "创建人",
                "生效订阅数（只读）",
                "父分组路径",
                "最后修改人",
                'data-testid="shop-plan-config"',
            ),
            str(WEB),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    gname = f"QA分组_{stamp}"
    code, group = req(
        "POST",
        "/admin/shop/feature-dictionary",
        token=admin,
        body={"node_type": "group", "name": gname, "sort_order": 90},
    )
    results.append(
        check(
            "VP10-F01 新建功能分组 TC-P10-F01",
            code in (200, 201) and (group or {}).get("node_type") == "group" and (group or {}).get("name") == gname,
            f"{code} {_err(group)}",
        )
    )
    gid = (group or {}).get("id")
    results.append(
        check(
            "VP10-N01 分组含创建人姓名",
            bool((group or {}).get("created_by_name")),
            str((group or {}).get("created_by_name")),
        )
    )
    code_pv, preview = req("POST", "/admin/shop/feature-dictionary/preview-code", token=admin, body={})
    results.append(
        check(
            "VP10-PV01 功能编码预览",
            code_pv == 200 and bool((preview or {}).get("code")),
            f"{code_pv} {_err(preview)}",
        )
    )
    code_pp, pprev = req("POST", "/admin/shop/plan-templates/preview-code", token=admin, body={})
    results.append(
        check(
            "VP10-PV02 套餐编码预览",
            code_pp == 200 and bool((pprev or {}).get("code")),
            f"{code_pp} {_err(pprev)}",
        )
    )
    code_tree, tree = req("GET", "/admin/shop/feature-dictionary?tree=true", token=admin)
    names = []
    if isinstance(tree, list):
        names = [x.get("name") for x in tree]
    results.append(
        check(
            "VP10-F01b 树可见分组",
            code_tree == 200 and gname in names,
            f"{code_tree} {names[:8]}",
        )
    )

    code_dup, dup = req(
        "POST",
        "/admin/shop/feature-dictionary",
        token=admin,
        body={"node_type": "group", "name": gname, "sort_order": 91},
    )
    results.append(
        check(
            "VP10-E01 分组重名 422 TC-P10-E01",
            code_dup == 422 and "已存在" in _err(dup),
            f"{code_dup} {_err(dup)}",
        )
    )

    picked = _pick_leaf(admin)
    plan_name = f"QA主套餐_{stamp}"
    plan_code = f"qa_main_{stamp}"
    if picked:
        leaf_code, val = picked
        code_p, plan = req(
            "POST",
            "/admin/shop/plan-templates",
            token=admin,
            body={
                "plan_type": "main",
                "name": plan_name,
                "code": plan_code,
                "replace_group": "main",
                "price_cents": 9900,
                "billing_period": "yearly",
                "allowed_entity_types": ["personal", "individual_business", "enterprise"],
                "feature_values": {leaf_code: val},
                "publish_after_save": True,
            },
        )
        results.append(
            check(
                "VP10-F02 上架主套餐 TC-P10-F02",
                code_p in (200, 201) and (plan or {}).get("is_public") is True and (plan or {}).get("code") == plan_code,
                f"{code_p} {_err(plan)}",
            )
        )
        results.append(
            check(
                "VP10-N02 模板生效订阅数与创建人",
                isinstance((plan or {}).get("active_subscription_count"), int)
                and "created_by_name" in (plan or {}),
                str({k: (plan or {}).get(k) for k in ("active_subscription_count", "created_by_name")}),
            )
        )
        code_list, listed = req("GET", "/admin/shop/plan-templates?published=true&q=" + plan_name, token=admin)
        items = (listed or {}).get("items") if isinstance(listed, dict) else []
        results.append(
            check(
                "VP10-F02b P11 可选",
                code_list == 200 and any(x.get("code") == plan_code for x in items),
                f"{code_list} total={(listed or {}).get('total')}",
            )
        )
    else:
        results.append(check("VP10-F02 上架主套餐 TC-P10-F02", False, "无叶子功能"))
        results.append(check("VP10-N02 模板生效订阅数与创建人", False, "skip"))
        results.append(check("VP10-F02b P11 可选", False, "skip"))

    code_empty, empty = req(
        "POST",
        "/admin/shop/plan-templates",
        token=admin,
        body={
            "plan_type": "main",
            "name": f"QA空套餐_{stamp}",
            "price_cents": 0,
            "feature_values": {},
            "publish_after_save": True,
        },
    )
    results.append(
        check(
            "VP10-E02 0 功能上架 422 TC-P10-E02",
            code_empty == 422 and ("能力" in _err(empty) or "功能" in _err(empty)),
            f"{code_empty} {_err(empty)}",
        )
    )

    cs = _ensure_cs_user()
    code_cs, data_cs = req(
        "POST",
        "/admin/shop/feature-dictionary",
        token=cs,
        body={"node_type": "group", "name": f"CS不可_{stamp}"},
    )
    results.append(
        check(
            "VP10-P01 管家新建分组 403 TC-P10-P01",
            code_cs == 403,
            f"{code_cs} {_err(data_cs)}",
        )
    )
    results.append(
        check(
            "VP10-UI 写按钮受 plan.manage 控制",
            'v-if="canManage"' in WEB.read_text(encoding="utf-8") and "+ 新建主套餐" in WEB.read_text(encoding="utf-8"),
            "canManage",
        )
    )
    if gid:
        pass  # group left in DB as QA data; ok for local

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'} {sum(1 for r in results if r)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
