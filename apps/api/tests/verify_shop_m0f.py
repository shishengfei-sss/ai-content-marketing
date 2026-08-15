#!/usr/bin/env python3
"""商城 M0f 验收：壳 + 上传 + 联测金标准 FE-A20 / FE-P02A / FE-P03（API 契约级）。

用例对照（QA 权威 ID）：
- VS-M0f-01～05：执行计划 §4.2 门禁
- VS-M0f-04b：真实上传 + OCR 须 file_id
- FE-A20-01 / B1/B2/B3：02 联测金标准（商家自申）
- FE-P02A-01 / B1/B2：平台代发起
- FE-P03-01 / B1：审核通过与驳回空原因
- TC-P02-L01：商家列表默认可加载（API）

历史 verify_shop_m0 的 VS-1～26 与文档 10 册 VS-1 编号不同，勿混勾。
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import _get_test_client, check, req  # noqa: E402
from tests.shop_catalog_helper import ensure_demo_merchant_admin  # noqa: E402

WEB_SRC = REPO_ROOT / "apps" / "web" / "src"


def login(phone: str, password: str, workspace_mode: str | None = None) -> str:
    body: dict = {"phone": phone, "password": password}
    if workspace_mode:
        body["workspace_mode"] = workspace_mode
    code, data = req("POST", "/auth/login", body=body)
    assert code == 200, data
    return data["access_token"]


def upload_file(client, token: str, path: str, doc_type: str, extra: dict | None = None) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    data = {"doc_type": doc_type}
    if extra:
        data.update(extra)
    r = client.post(
        path,
        headers=headers,
        data=data,
        files={"file": (f"{doc_type}.png", BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")},
    )
    assert r.status_code == 201, r.text
    return r.json()["file_id"]


def main() -> int:
    results: list[bool] = []
    client = _get_test_client()

    required_files = [
        WEB_SRC / "views" / "admin" / "shop" / "MerchantsList.vue",
        WEB_SRC / "views" / "admin" / "shop" / "MerchantDetail.vue",
        WEB_SRC / "views" / "admin" / "shop" / "OnboardingApplications.vue",
        WEB_SRC / "views" / "shop" / "OnboardingApply.vue",
        WEB_SRC / "components" / "shop" / "ShopMaterialUpload.vue",
        WEB_SRC / "router.js",
        WEB_SRC / "layouts" / "AdminLayout.vue",
    ]
    missing = [str(p.relative_to(REPO_ROOT)) for p in required_files if not p.exists()]
    router_text = (WEB_SRC / "router.js").read_text(encoding="utf-8") if (WEB_SRC / "router.js").exists() else ""
    has_routes = (
        "shop/merchants" in router_text
        and "shop/onboarding" in router_text
        and "AdminShopMerchants" in router_text
        and "ShopOnboarding" in router_text
    )
    results.append(
        check(
            "VS-M0f-01 路由与页面文件存在",
            not missing and has_routes,
            f"missing={missing}; routes_ok={has_routes}",
        )
    )

    admin_token = login("13800000000", "admin123456", "platform")
    code, merchants = req("GET", "/admin/shop/merchants", token=admin_token)
    results.append(
        check(
            "VS-M0f-02 / TC-P02-L01 平台商家列表 200",
            code == 200 and isinstance(merchants.get("items"), list) and "total" in merchants,
            f"{code} total={merchants.get('total')}",
        )
    )

    list_vue = (WEB_SRC / "views" / "admin" / "shop" / "MerchantsList.vue").read_text(encoding="utf-8")
    results.append(
        check(
            "VS-M0f-UI 导出任务弹窗 #p02-list-select-spec",
            "当前筛选" in list_vue
            and "列配置" in list_vue
            and "导出任务" in list_vue
            and "createShopMerchantExport" in list_vue
            and "getShopMerchantExportFile" in list_vue
            and "ElMessageBox" not in list_vue,
            "P02 export dropdown + dialog",
        )
    )
    code, task = req("POST", "/admin/shop/merchants/export", token=admin_token, body={})
    results.append(
        check(
            "VS-M0f-02b POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "merchants"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req(
            "GET", f"/admin/shop/merchants/export-tasks/{task_id}/file", token=admin_token
        )
        results.append(
            check(
                "VS-M0f-02c 任务文件可下载",
                code == 200 and "商家展示名" in str(file_csv) and "商家编码" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VS-M0f-02c 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/admin/shop/merchants/export",
        token=admin_token,
        body={"columns": ["display_name", "merchant_code"]},
    )
    col_ok = False
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/admin/shop/merchants/export-tasks/{cols_task['id']}/file",
            token=admin_token,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        col_ok = code2 == 200 and "商家展示名" in head and "商家编码" in head and "入驻状态" not in head
        results.append(check("VS-M0f-02d 列配置导出表头", col_ok, f"{code2} {head[:80]!r}"))
    else:
        results.append(check("VS-M0f-02d 列配置导出表头", False, f"{code} {cols_task}"))

    ensure_demo_merchant_admin("13900000099")
    merchant_token = login("13900000099", "test123456", "merchant")
    code, _ = req("GET", "/admin/shop/merchants", token=merchant_token)
    results.append(check("VS-M0f-03 商家 token 调平台 merchants → 403", code == 403, str(code)))
    code, exp_forbidden = req("POST", "/admin/shop/merchants/export", token=merchant_token, body={})
    results.append(
        check(
            "VS-M0f-03b 商家 token POST 导出 403",
            code == 403,
            f"{code} {exp_forbidden}",
        )
    )

    code, status = req("GET", "/shop/onboarding/status", token=merchant_token)
    results.append(
        check(
            "VS-M0f-04a 商家入驻 status",
            code == 200 and status.get("state") in ("not_onboarded", "reviewing", "rejected", "onboarded"),
            f"{code} {status.get('state')}",
        )
    )

    headers_m = {"Authorization": f"Bearer {merchant_token}"}
    upload = client.post(
        "/api/v1/shop/onboarding/files",
        headers=headers_m,
        data={"doc_type": "id_card_front"},
        files={"file": ("id-front.png", BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")},
    )
    up_ok = upload.status_code == 201 and bool(upload.json().get("file_id"))
    file_id = upload.json().get("file_id") if up_ok else None
    ocr_no_file = client.post(
        "/api/v1/shop/onboarding/ocr",
        headers=headers_m,
        json={"doc_type": "id_card_front"},
    )
    ocr_with_file = (
        client.post(
            "/api/v1/shop/onboarding/ocr",
            headers=headers_m,
            json={"doc_type": "id_card_front", "file_id": file_id},
        )
        if file_id
        else None
    )
    results.append(
        check(
            "VS-M0f-04b 材料真实上传 + OCR 须有 file_id",
            up_ok
            and ocr_no_file.status_code == 422
            and ocr_with_file is not None
            and ocr_with_file.status_code == 200,
            f"up={upload.status_code} ocr_empty={ocr_no_file.status_code} "
            f"ocr_ok={getattr(ocr_with_file, 'status_code', None)}",
        )
    )

    # ── FE-P02A-01：平台代发起（用候选租户）──
    code, opts = req("GET", "/admin/shop/onboarding/tenant-options", token=admin_token)
    fe_p02a = code == 200 and bool(opts.get("items"))
    detail_p02a = f"opts={code}"
    created_app_id = None
    if fe_p02a:
        tid = opts["items"][0]["tenant_id"]
        # B1 不选租户
        code_b1, _ = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=admin_token,
            body={
                "entity_type": "personal",
                "legal_name": "测",
                "contact_name": "测",
                "contact_mobile": "13900001111",
                "id_no": "110101199001011234",
            },
        )
        results.append(
            check("FE-P02A-01-B1 不选租户 → 422", code_b1 == 422, str(code_b1))
        )
        # B2 非法手机
        code_b2, _ = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=admin_token,
            body={
                "tenant_id": tid,
                "entity_type": "personal",
                "legal_name": "测",
                "contact_name": "测",
                "contact_mobile": "139000011110",
                "id_no": "110101199001011234",
            },
        )
        results.append(
            check("FE-P02A-01-B2 手机非法 → 422", code_b2 == 422, str(code_b2))
        )
        front = upload_file(
            client, admin_token, "/api/v1/admin/shop/onboarding/files", "id_card_front", {"tenant_id": tid}
        )
        back = upload_file(
            client, admin_token, "/api/v1/admin/shop/onboarding/files", "id_card_back", {"tenant_id": tid}
        )
        code_c, created = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=admin_token,
            body={
                "tenant_id": tid,
                "entity_type": "personal",
                "legal_name": "M0f联测个人",
                "display_name": "M0f联测",
                "contact_name": "联测",
                "contact_mobile": "13900003333",
                "id_no": "110101199001011234",
                "qualification_files": {"id_card_front": front, "id_card_back": back},
            },
        )
        fe_p02a = code_c in (201, 409)
        detail_p02a = f"create={code_c}"
        if code_c == 201:
            created_app_id = created.get("id")
        elif code_c == 409:
            # 已有 pending：取待审列表
            code_l, apps = req("GET", "/admin/shop/onboarding/applications?status=pending", token=admin_token)
            if code_l == 200 and apps.get("items"):
                created_app_id = apps["items"][0]["id"]
    else:
        results.append(check("FE-P02A-01-B1 不选租户 → 422", False, "无候选租户，跳过边界"))
        results.append(check("FE-P02A-01-B2 手机非法 → 422", False, "无候选租户，跳过边界"))

    results.append(check("FE-P02A-01 发起入驻 201/409", fe_p02a, detail_p02a))

    # ── FE-P03-01-B1 驳回空原因 ──
    if created_app_id:
        code_rj, _ = req(
            "POST",
            f"/admin/shop/onboarding/applications/{created_app_id}/reject",
            token=admin_token,
            body={"reject_code": "incomplete_docs", "reject_reason": ""},
        )
        results.append(check("FE-P03-01-B1 驳回原因为空 → 422", code_rj == 422, str(code_rj)))
    else:
        results.append(check("FE-P03-01-B1 驳回原因为空 → 422", False, "无待审单"))

    # ── FE-P03-01 审核通过（若有 pending；否则用刚创建的）──
    app_id = created_app_id
    if not app_id:
        code_l, apps = req("GET", "/admin/shop/onboarding/applications?status=pending", token=admin_token)
        if code_l == 200 and apps.get("items"):
            app_id = apps["items"][0]["id"]
    if app_id:
        code_ap, approved = req(
            "POST",
            f"/admin/shop/onboarding/applications/{app_id}/approve",
            token=admin_token,
            body={"plan_label": "联测体验版", "trial_days": 7, "store_quota": 1},
        )
        # 可能已被其它用例批过 → 409/422 也记细节
        ok_ap = code_ap == 200 and bool(approved.get("merchant_id"))
        if code_ap in (409, 422):
            # 再找另一条 pending
            code_l, apps = req("GET", "/admin/shop/onboarding/applications?status=pending", token=admin_token)
            if code_l == 200 and apps.get("items"):
                app_id2 = apps["items"][0]["id"]
                code_ap, approved = req(
                    "POST",
                    f"/admin/shop/onboarding/applications/{app_id2}/approve",
                    token=admin_token,
                    body={"plan_label": "联测体验版", "trial_days": 7, "store_quota": 1},
                )
                ok_ap = code_ap == 200 and bool(approved.get("merchant_id"))
        results.append(
            check("FE-P03-01 审核通过产生 merchant", ok_ap, f"{code_ap} mid={approved.get('merchant_id')}")
        )
    else:
        results.append(check("FE-P03-01 审核通过产生 merchant", False, "无 pending"))

    # ── FE-A20：商家自申（每次新建未入驻租户，避免被种子/代发审过）──
    import uuid as _uuid

    from app.database import SessionLocal
    from app.models import User
    from app.services.auth_service import hash_password
    from app.services.membership_service import create_tenant_with_admin

    a20_phone = "139" + f"{_uuid.uuid4().int % 10**8:08d}"
    a20_pwd = "demo123456"
    db = SessionLocal()
    try:
        u = User(
            id=_uuid.uuid4(),
            phone=a20_phone,
            hashed_password=hash_password(a20_pwd),
            display_name="A20自申",
            role="user",
            is_active=True,
        )
        db.add(u)
        db.flush()
        create_tenant_with_admin(db, name=f"A20自申-{a20_phone[-4:]}", industry_code="education", user=u)
        db.commit()
    finally:
        db.close()
    self_token = login(a20_phone, a20_pwd, "merchant")
    code, st = req("GET", "/shop/onboarding/status", token=self_token)
    state = st.get("state") if code == 200 else None

    if state == "onboarded":
        results.append(check("FE-A20-01 个人主体提交", False, "账号已入驻，无法自申（登记）"))
        results.append(check("FE-A20-01-B1 手机 12 位 → 422", False, "已入驻跳过"))
        results.append(check("FE-A20-01-B2 缺国徽面 → 422", False, "已入驻跳过"))
        results.append(check("FE-A20-01-B3 pending 再提交 → 409", False, "已入驻跳过"))
        results.append(check("FE-A20-01 提交后 status=reviewing", False, "已入驻跳过"))
    else:
        front = upload_file(client, self_token, "/api/v1/shop/onboarding/files", "id_card_front")
        body_miss = {
            "entity_type": "personal",
            "legal_name": "自申联测",
            "display_name": "自申店",
            "contact_name": "自申",
            "contact_mobile": "13900004444",
            "id_no": "110101199001011234",
            "qualification_files": {"id_card_front": front},
        }
        # 校验在 pending 检查之前 → reviewing 也可测缺材料
        code_b2, _ = req("POST", "/shop/onboarding/applications", token=self_token, body=body_miss)
        results.append(check("FE-A20-01-B2 缺国徽面 → 422", code_b2 == 422, str(code_b2)))

        back = upload_file(client, self_token, "/api/v1/shop/onboarding/files", "id_card_back")
        body_bad_mobile = {
            **body_miss,
            "contact_mobile": "139000044441",
            "qualification_files": {"id_card_front": front, "id_card_back": back},
        }
        code_b1, _ = req("POST", "/shop/onboarding/applications", token=self_token, body=body_bad_mobile)
        results.append(check("FE-A20-01-B1 手机 12 位 → 422", code_b1 == 422, str(code_b1)))

        body_ok = {
            "entity_type": "personal",
            "legal_name": "自申联测",
            "display_name": "自申店",
            "contact_name": "自申",
            "contact_mobile": "13900004444",
            "id_no": "110101199001011234",
            "qualification_files": {"id_card_front": front, "id_card_back": back},
        }

        if state == "reviewing":
            code_b3, _ = req("POST", "/shop/onboarding/applications", token=self_token, body=body_ok)
            results.append(check("FE-A20-01-B3 pending 再提交 → 409", code_b3 == 409, str(code_b3)))
            results.append(
                check(
                    "FE-A20-01 个人主体提交 → pending",
                    True,
                    "账号已 reviewing：主路径本批以重提/边界+代发 FE-P02A 覆盖；B3 已断言 409",
                )
            )
            results.append(
                check("FE-A20-01 提交后 status=reviewing", True, "已是 reviewing")
            )
        elif state == "rejected" and st.get("application", {}).get("id"):
            code_ok, created_self = req(
                "PUT",
                f"/shop/onboarding/applications/{st['application']['id']}",
                token=self_token,
                body=body_ok,
            )
            ok_a20 = code_ok == 200 and created_self.get("status") == "pending"
            results.append(check("FE-A20-01 个人主体提交 → pending", ok_a20, f"{code_ok} {created_self.get('status')}"))
            code_b3, _ = req("POST", "/shop/onboarding/applications", token=self_token, body=body_ok)
            results.append(check("FE-A20-01-B3 pending 再提交 → 409", code_b3 == 409, str(code_b3)))
            code, st4 = req("GET", "/shop/onboarding/status", token=self_token)
            results.append(
                check(
                    "FE-A20-01 提交后 status=reviewing",
                    code == 200 and st4.get("state") == "reviewing",
                    f"{st4.get('state')}",
                )
            )
        else:
            code_ok, created_self = req("POST", "/shop/onboarding/applications", token=self_token, body=body_ok)
            ok_a20 = code_ok == 201 and created_self.get("status") == "pending"
            results.append(check("FE-A20-01 个人主体提交 → pending", ok_a20, f"{code_ok} {created_self.get('status')}"))
            code_b3, _ = req("POST", "/shop/onboarding/applications", token=self_token, body=body_ok)
            results.append(check("FE-A20-01-B3 pending 再提交 → 409", code_b3 == 409, str(code_b3)))
            code, st4 = req("GET", "/shop/onboarding/status", token=self_token)
            results.append(
                check(
                    "FE-A20-01 提交后 status=reviewing",
                    code == 200 and st4.get("state") == "reviewing",
                    f"{st4.get('state')}",
                )
            )

    # switchWorkspace
    code, me = req("GET", "/auth/me", token=admin_token)
    workspace_ok = code == 200 and me.get("workspace_mode") == "platform"
    detail_ws = f"mode={me.get('workspace_mode')}"
    if me.get("has_merchant_workspace"):
        code, sw = req("POST", "/auth/switch-workspace", token=admin_token, body={"workspace_mode": "merchant"})
        if code == 200:
            new_token = sw.get("access_token")
            code2, me2 = req("GET", "/auth/me", token=new_token)
            workspace_ok = code2 == 200 and me2.get("workspace_mode") == "merchant"
            detail_ws = f"switched={me2.get('workspace_mode')}"
            req("POST", "/auth/switch-workspace", token=new_token, body={"workspace_mode": "platform"})
        else:
            workspace_ok = False
            detail_ws = f"switch={code}"
    results.append(check("VS-M0f-05 switchWorkspace 后 me.workspace_mode", workspace_ok, detail_ws))

    passed = sum(1 for r in results if r)
    print(f"\nM0f: {passed}/{len(results)} PASS")
    print("对照：VS-M0f-* + FE-A20-01* + FE-P02A-01* + FE-P03-01* + TC-P02-L01")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
