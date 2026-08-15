#!/usr/bin/env python3
"""A04 专栏 / A05 课时 / A06 资料包 CMS 验收。

对照 PRD 01-管理端UI.html #a04 · #a05 · #a06
履约：商品 ref_type=column|digital_package → MP outline/materials。
"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop"


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _ensure_merchant() -> tuple[str, str]:
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000097"
    password = "test123456"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            db.close()
            code, data = req(
                "POST",
                "/auth/register",
                body={
                    "phone": phone,
                    "password": password,
                    "tenant_name": f"A04验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A04验",
                },
            )
            assert code in (200, 201), data
            db = SessionLocal()
            user = db.query(User).filter(User.phone == phone).first()
        merchant = (
            db.query(ShopMerchantAccount)
            .filter(ShopMerchantAccount.status == "active")
            .order_by(ShopMerchantAccount.created_at.desc())
            .first()
        )
        if not merchant:
            raise RuntimeError("no active merchant")
        mem = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.user_id, user.id),
                uuid_eq(TenantMembership.tenant_id, merchant.tenant_id),
            )
            .first()
        )
        role = (
            db.query(TenantRole)
            .filter(
                uuid_eq(TenantRole.tenant_id, merchant.tenant_id),
                TenantRole.code == "shop_admin",
            )
            .first()
        )
        if role is None:
            role = (
                db.query(TenantRole)
                .filter(uuid_eq(TenantRole.tenant_id, merchant.tenant_id))
                .order_by(TenantRole.created_at.asc())
                .first()
            )
        if mem is None and role is not None:
            db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    tenant_id=merchant.tenant_id,
                    role_id=role.id,
                    is_active=True,
                )
            )
        elif mem is not None and role is not None:
            mem.role_id = role.id
            mem.is_active = True
        user.tenant_id = merchant.tenant_id
        user.hashed_password = hash_password(password)
        db.commit()
        tenant_id = str(merchant.tenant_id)
    finally:
        db.close()
    return login(phone, password), tenant_id


def _ensure_payment(merchant: str) -> str:
    api_key = "mock_api_key_a04"
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_a04",
            "wx_app_id": "wx_mock_appid_a04",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, data
    return api_key


def _pay(order_no: str, amount: int, api_key: str):
    from app.services.shop.wechat_pay_service import stub_sign

    tx = f"TX{uuid.uuid4().hex[:16]}"
    sign = stub_sign(order_no, tx, amount, api_key)
    code, paid = req(
        "POST",
        "/mp/shop/payments/notify",
        body={
            "order_no": order_no,
            "transaction_id": tx,
            "paid_amount_cents": amount,
            "sign": sign,
        },
    )
    assert code == 200 and paid.get("status") == "paid", paid


def _buyer(tenant_id: str) -> str:
    openid = f"a04_{uuid.uuid4().hex[:10]}"
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def _upload(token: str, name: str, content: bytes, mime: str) -> dict:
    from tests.http_client import USE_LIVE, _get_test_client

    if USE_LIVE:
        raise RuntimeError("A04 verify upload requires TestClient (VERIFY_LIVE_API=0)")
    client = _get_test_client()
    r = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, content, mime)},
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    assert r.status_code == 200, data
    return data


def _force_on_sale(product_id: str) -> bool:
    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct, ShopProductReview

    db = SessionLocal()
    try:
        pid_uuid = UUIDType(str(product_id))
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, pid_uuid)).first()
        if not p:
            return False
        if p.status != "on_sale":
            p.status = "on_sale"
            rev = (
                db.query(ShopProductReview)
                .filter(uuid_eq(ShopProductReview.product_id, pid_uuid))
                .order_by(ShopProductReview.created_at.desc())
                .first()
            )
            if rev:
                rev.manual_result = "approved"
            db.commit()
        return p.status == "on_sale"
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "UI A04 列表 §0b",
            _page_has(
                WEB / "ColumnsList.vue",
                "标题",
                "课时数",
                "引用商品",
                "列设置",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                "/shop/columns/export",
                "/shop/columns/export-tasks/",
                "page_size",
                "新建专栏",
            ),
        )
    )
    results.append(
        check(
            "UI A04 Tab/高级筛选/弹窗",
            _page_has(
                WEB / "ColumnsList.vue",
                "全部专栏",
                "高级筛选",
                "引用商品 ≥",
                "更新起",
                "创建并编辑",
                'data-testid="shop-columns"',
                "shop_id: currentId",
                "请输入专栏标题",
                "确认发布",
                "确认下架",
                "发布说明",
                "el-drawer",
                "el-dialog",
            ),
        )
    )
    results.append(
        check(
            "UI A05 课时编辑",
            _page_has(
                WEB / "ColumnEdit.vue",
                "课时列表",
                "新增课时",
                "选择文件上传",
                "试看",
                "发布专栏",
            ),
        )
    )
    results.append(
        check(
            "UI A06 列表 §0b",
            _page_has(
                WEB / "DigitalPackagesList.vue",
                "标题",
                "交付方式",
                "文件数",
                "引用商品",
                "列设置",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                "/shop/digital-packages/export",
                "/shop/digital-packages/export-tasks/",
                "新建资料包",
            ),
        )
    )
    results.append(
        check(
            "UI A06 Tab/弹窗",
            _page_has(
                WEB / "DigitalPackagesList.vue",
                "全部资料包",
                "创建并编辑",
                'data-testid="shop-packages"',
                "shop_id: currentId",
                "请输入资料包标题",
                "确认发布",
                "确认下架",
                "发布说明",
                "在线查看",
                "el-drawer",
                "el-dialog",
            ),
        )
    )
    results.append(
        check(
            "UI A06 真实上传",
            _page_has(
                WEB / "DigitalPackageEdit.vue",
                "上传文件",
                "/api/v1/shop/content/files",
                "预览",
                "+ 添加文件",
                "开始上传",
                "确认发布",
                "发布说明",
                "只读",
                "列设置",
                "搜索文件名",
                'data-testid="shop-package-edit"',
                "点击或拖拽上传",
                "zip 请下载后本地解压",
            ),
            "a06-edit",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = _ensure_payment(merchant)

    # ── A04/A05 专栏课时 ──
    code, col = req(
        "POST",
        "/shop/columns",
        token=merchant,
        body={"title": f"专栏-{uuid.uuid4().hex[:6]}", "intro": "验收简介"},
    )
    results.append(check("VA04-1 创建专栏草稿", code == 201 and col.get("status") == "draft", f"{code} {col}"))
    col_id = col.get("id")
    results.append(
        check(
            "VA04-1b 空壳 published_lesson_count=0",
            col.get("published_lesson_count") == 0,
            col,
        )
    )

    code, far = req("GET", "/shop/columns?updated_from=2099-01-01", token=merchant)
    results.append(
        check(
            "VA04-list 未来日期无结果",
            code == 200 and far.get("total") == 0,
            f"{code} {far}",
        )
    )
    code, counts_body = req("GET", "/shop/columns", token=merchant)
    sc = counts_body.get("status_counts") or {}
    results.append(
        check(
            "VA04-list status_counts",
            code == 200 and isinstance(sc, dict) and "draft" in sc and "published" in sc and "off_sale" in sc,
            f"{code} {sc}",
        )
    )

    code, no_pub = req("POST", f"/shop/columns/{col_id}/publish", token=merchant)
    results.append(
        check(
            "VA04-2 无课时不可发布",
            code == 422 and "须至少 1 个已发布课时" in str(no_pub),
            f"{code} {no_pub}",
        )
    )

    up = _upload(merchant, "lesson1.mp4", b"fake-video-bytes", "video/mp4")
    results.append(check("VA05-1 上传媒体", bool(up.get("file_id")), up))

    code, lesson = req(
        "POST",
        f"/shop/columns/{col_id}/lessons",
        token=merchant,
        body={
            "title": "第1课",
            "media_type": "video",
            "media_id": up["file_id"],
            "media_url": up["file_url"],
            "duration_sec": 600,
            "is_trial": True,
            "trial_seconds": 60,
        },
    )
    results.append(
        check(
            "VA05-2 创建课时",
            code == 201 and lesson.get("status") == "draft" and lesson.get("media_id") == up["file_id"],
            f"{code} {lesson}",
        )
    )
    lesson_id = lesson.get("id")

    code, still = req("POST", f"/shop/columns/{col_id}/publish", token=merchant)
    results.append(check("VA04-3 未发布课时不可发专栏", code == 422, f"{code} {still}"))

    code, les_pub = req(
        "POST",
        f"/shop/columns/{col_id}/lessons/{lesson_id}/publish",
        token=merchant,
    )
    results.append(check("VA05-3 发布课时", code == 200 and les_pub.get("status") == "published", f"{code} {les_pub}"))

    code, col_pub = req("POST", f"/shop/columns/{col_id}/publish", token=merchant)
    results.append(
        check("VA04-4 发布专栏", code == 200 and col_pub.get("status") == "published", f"{code} {col_pub}")
    )

    code, course = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": f"课-{uuid.uuid4().hex[:6]}",
            "price_cents": 9900,
            "ref_type": "column",
            "ref_id": col_id,
        },
    )
    results.append(
        check(
            "VA04-5 商品关联专栏",
            code in (200, 201) and course.get("ref_type") == "column" and course.get("ref_id") == col_id,
            f"{code} {course}",
        )
    )
    course_id = course.get("id")
    for path in (f"/shop/products/{course_id}/submit-review", f"/shop/products/{course_id}/publish"):
        req("POST", path, token=merchant, body={})
    results.append(check("VA04-6 课程 on_sale", _force_on_sale(course_id), course_id))

    # ── A06 资料包 ──
    code, pkg = req(
        "POST",
        "/shop/digital-packages",
        token=merchant,
        body={"title": f"资料-{uuid.uuid4().hex[:6]}", "deliver_mode": "download", "max_downloads": 3},
    )
    results.append(check("VA06-1 创建资料包", code == 201 and pkg.get("status") == "draft", f"{code} {pkg}"))
    pkg_id = pkg.get("id")
    results.append(
        check(
            "VA06-1b 空包 file_count=0",
            pkg.get("file_count") == 0,
            pkg,
        )
    )
    code, pkg_list = req("GET", "/shop/digital-packages", token=merchant)
    psc = pkg_list.get("status_counts") or {}
    results.append(
        check(
            "VA06-list status_counts",
            code == 200 and isinstance(psc, dict) and "draft" in psc and "published" in psc,
            f"{code} {psc}",
        )
    )

    code, no_file = req("POST", f"/shop/digital-packages/{pkg_id}/publish", token=merchant)
    results.append(
        check(
            "VA06-2 无文件不可发布",
            code == 422 and "请添加至少 1 个文件" in str(no_file),
            f"{code} {no_file}",
        )
    )

    pdf = _upload(merchant, "话术库.pdf", b"%PDF-1.4 fake", "application/pdf")
    code, asset = req(
        "POST",
        f"/shop/digital-packages/{pkg_id}/assets",
        token=merchant,
        body={
            "file_id": pdf["file_id"],
            "file_name": pdf["file_name"],
            "file_url": pdf["file_url"],
            "mime": pdf["mime"],
            "size_bytes": pdf["size_bytes"],
        },
    )
    results.append(
        check(
            "VA06-3 添加文件",
            code == 201 and asset.get("file_id") == pdf["file_id"] and asset.get("previewable") is True,
            f"{code} {asset}",
        )
    )
    results.append(
        check(
            "VA06-3b 含上传时间",
            bool(asset.get("created_at")),
            asset,
        )
    )
    txt = _upload(merchant, "备注.txt", b"hello", "text/plain")
    code, bad_ext = req(
        "POST",
        f"/shop/digital-packages/{pkg_id}/assets",
        token=merchant,
        body={
            "file_id": txt["file_id"],
            "file_name": txt["file_name"],
            "file_url": txt["file_url"],
            "mime": txt["mime"],
            "size_bytes": txt["size_bytes"],
        },
    )
    results.append(
        check(
            "VA06-3c 非白名单不可加",
            code == 422 and "仅支持" in str(bad_ext),
            f"{code} {bad_ext}",
        )
    )

    code, pkg_pub = req("POST", f"/shop/digital-packages/{pkg_id}/publish", token=merchant)
    results.append(
        check("VA06-4 发布资料包", code == 200 and pkg_pub.get("status") == "published", f"{code} {pkg_pub}")
    )

    code, digital = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "digital",
            "name": f"资料商品-{uuid.uuid4().hex[:6]}",
            "price_cents": 4900,
            "ref_type": "digital_package",
            "ref_id": pkg_id,
        },
    )
    results.append(
        check(
            "VA06-5 商品关联资料包",
            code in (200, 201) and digital.get("ref_id") == pkg_id,
            f"{code} {digital}",
        )
    )
    dig_id = digital.get("id")
    for path in (f"/shop/products/{dig_id}/submit-review", f"/shop/products/{dig_id}/publish"):
        req("POST", path, token=merchant, body={})
    results.append(check("VA06-6 资料商品 on_sale", _force_on_sale(dig_id), dig_id))
    qpkg = (pkg.get("title") or "")[:8]
    code, csv_pkg = req("GET", f"/shop/digital-packages/export?q={qpkg}", token=merchant)
    results.append(
        check(
            "VA06-export 含标题",
            code == 200 and "标题" in str(csv_pkg) and "下载" in str(csv_pkg),
            f"{code} {str(csv_pkg)[:120]}",
        )
    )
    code, pkg_task = req("POST", "/shop/digital-packages/export", token=merchant, body={"q": qpkg})
    results.append(
        check(
            "VA06-X1 POST 导出任务已完成",
            code == 200
            and isinstance(pkg_task, dict)
            and pkg_task.get("status") == "done"
            and pkg_task.get("resource") == "digital_packages"
            and pkg_task.get("id"),
            f"{code} {pkg_task}",
        )
    )
    pkg_task_id = (pkg_task or {}).get("id") if isinstance(pkg_task, dict) else None
    if pkg_task_id:
        code, pkg_file = req(
            "GET", f"/shop/digital-packages/export-tasks/{pkg_task_id}/file", token=merchant
        )
        results.append(
            check(
                "VA06-X2 任务文件可下载",
                code == 200 and "标题" in str(pkg_file) and "交付方式" in str(pkg_file),
                f"{code} head={str(pkg_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VA06-X2 任务文件可下载", False, "no task id"))
    code, pkg_cols = req(
        "POST",
        "/shop/digital-packages/export",
        token=merchant,
        body={"q": qpkg, "columns": ["title", "status"]},
    )
    if code == 200 and isinstance(pkg_cols, dict) and pkg_cols.get("id"):
        code2, pkg_col_csv = req(
            "GET",
            f"/shop/digital-packages/export-tasks/{pkg_cols['id']}/file",
            token=merchant,
        )
        head = str(pkg_col_csv).splitlines()[0] if pkg_col_csv else ""
        results.append(
            check(
                "VA06-X3 列配置导出表头",
                code2 == 200 and "标题" in head and "状态" in head and "文件数" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA06-X3 列配置导出表头", False, f"{code} {pkg_cols}"))
    code, plat_pkg = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_pkg_token = (
        plat_pkg.get("access_token") if code == 200 and isinstance(plat_pkg, dict) else None
    )
    code, pkg_forbidden = req(
        "POST", "/shop/digital-packages/export", token=plat_pkg_token, body={}
    )
    results.append(
        check(
            "VA06-P01 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {pkg_forbidden}",
        )
    )

    # ── 买家履约接 CMS ──
    buyer = _buyer(tenant_id)
    mobile = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    code, bind = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("VA04-7a 绑定手机", code == 200, f"{code} {bind}"))

    code, created_c = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": course_id})
    order_c = (created_c or {}).get("order") or created_c
    results.append(check("VA04-7 课程下单", code == 200, f"{code} {created_c}"))
    if code == 200:
        _pay(order_c["order_no"], int(order_c["amount_cents"]), api_key)

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent_c = next((e for e in (ents.get("items") or []) if e.get("product_id") == course_id), None)
    results.append(check("VA04-8 课程权益", ent_c is not None and ent_c.get("status") == "active", f"{code} {ent_c}"))

    code, outline = req("GET", f"/mp/shop/entitlements/{ent_c['id']}/outline", token=buyer) if ent_c else (0, {})
    titles = [x.get("title") for x in (outline.get("lessons") or [])]
    results.append(
        check(
            "VA04-9 outline 来自 CMS",
            code == 200 and "第1课" in titles and len(titles) == 1,
            f"{code} {outline}",
        )
    )

    code, created_d = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": dig_id})
    order_d = (created_d or {}).get("order") or created_d
    results.append(check("VA06-7 资料下单", code == 200, f"{code} {created_d}"))
    if code == 200:
        _pay(order_d["order_no"], int(order_d["amount_cents"]), api_key)

    code, ents2 = req("GET", "/mp/shop/entitlements", token=buyer)
    ent_d = next((e for e in (ents2.get("items") or []) if e.get("product_id") == dig_id), None)
    results.append(check("VA06-8 资料权益", ent_d is not None and ent_d.get("status") == "active", f"{code} {ent_d}"))

    code, mats = req("GET", f"/mp/shop/entitlements/{ent_d['id']}/materials", token=buyer) if ent_d else (0, {})
    names = [f.get("name") for f in (mats.get("files") or [])]
    results.append(
        check(
            "VA06-9 materials 来自 CMS",
            code == 200 and any("话术库" in (n or "") or "pdf" in (n or "").lower() for n in names),
            f"{code} {mats}",
        )
    )

    # 列表计数
    code, cols = req("GET", f"/shop/columns?q={col.get('title', '')[:8]}", token=merchant)
    hit = next((x for x in (cols.get("items") or []) if x.get("id") == col_id), None)
    results.append(
        check(
            "VA04-10 列表课时/引用计数",
            code == 200 and hit and hit.get("lesson_count") >= 1 and hit.get("ref_product_count") >= 1,
            f"{code} {hit}",
        )
    )
    q8 = (col.get("title") or "")[:8]
    code, refed = req("GET", f"/shop/columns?ref_min=1&q={q8}", token=merchant)
    hit_ref = next((x for x in (refed.get("items") or []) if x.get("id") == col_id), None)
    results.append(
        check(
            "VA04-list 引用商品≥1",
            code == 200 and hit_ref and hit_ref.get("ref_product_count") >= 1,
            f"{code} {hit_ref}",
        )
    )
    code, csv = req("GET", f"/shop/columns/export?q={q8}", token=merchant)
    results.append(
        check(
            "VA04-export 含标题",
            code == 200 and "标题" in str(csv),
            f"{code} {str(csv)[:80]}",
        )
    )
    code, task = req("POST", "/shop/columns/export", token=merchant, body={"q": q8})
    results.append(
        check(
            "VA04-X1 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "columns"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req("GET", f"/shop/columns/export-tasks/{task_id}/file", token=merchant)
        results.append(
            check(
                "VA04-X2 任务文件可下载",
                code == 200 and "标题" in str(file_csv) and "课时数" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VA04-X2 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/shop/columns/export",
        token=merchant,
        body={"q": q8, "columns": ["title", "status"]},
    )
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/shop/columns/export-tasks/{cols_task['id']}/file",
            token=merchant,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        results.append(
            check(
                "VA04-X3 列配置导出表头",
                code2 == 200 and "标题" in head and "状态" in head and "课时数" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA04-X3 列配置导出表头", False, f"{code} {cols_task}"))
    code, plat = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_token = plat.get("access_token") if code == 200 and isinstance(plat, dict) else None
    code, forbidden = req("POST", "/shop/columns/export", token=plat_token, body={})
    results.append(
        check(
            "VA04-P01 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {forbidden}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA04–A06 CMS: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
