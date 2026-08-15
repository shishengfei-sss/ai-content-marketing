#!/usr/bin/env python3
"""商品映射暂停/恢复/日志 + 列表完备性。对照 PRD 01-管理端UI.html #a14 #a14-list #a14c。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ChannelMappings.vue"


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
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


def _ensure_merchant() -> tuple[str, str]:
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000099"
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
                    "tenant_name": f"A14验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A14验",
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
                TenantRole.code == "admin",
            )
            .first()
        )
        if role is None:
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
        tid = str(merchant.tenant_id)
    finally:
        db.close()
    return login(phone, password), tid


def _on_sale_product(merchant: str) -> str:
    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct
    from tests.http_client import _get_test_client

    client = _get_test_client()
    code, col = req(
        "POST",
        "/shop/columns",
        token=merchant,
        body={"title": f"A14col-{uuid.uuid4().hex[:6]}", "intro": "d"},
    )
    assert code in (200, 201), col
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "L1",
            "duration_sec": 60,
            "media_type": "video",
            "media_url": "https://example.com/a14.mp4",
        },
    )
    assert code in (200, 201), les
    req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
    req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)
    cover = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("c.png", b"\x89PNG", "image/png")},
    ).json()["file_url"]
    code, product = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": f"A14课-{uuid.uuid4().hex[:6]}",
            "price_cents": 19900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    assert code in (200, 201), product
    db = SessionLocal()
    try:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUIDType(product["id"]))).first()
        p.status = "on_sale"
        # F7：映射闸要求曾过人审（last_review_id）
        if not p.last_review_id:
            p.last_review_id = uuid.uuid4()
        db.commit()
    finally:
        db.close()
    return product["id"]


def main() -> int:
    from app.services.shop.channel_service import stub_douyin_sign

    results: list[bool] = []
    results.append(
        check(
            "VA14-UI-1 暂停/恢复/日志抽屉",
            _page_has(
                WEB,
                "暂停",
                "恢复",
                "公域日志",
                "重新同步",
                "listing_paused",
                "openLogs",
                "#a14c",
                "useCurrentShop",
                "shop_id: currentId",
            ),
            str(WEB),
        )
    )
    results.append(
        check(
            "VA14-UI-2 列表高级筛选/导出/列设置",
            _page_has(
                WEB,
                "高级筛选",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                'placeholder="外部审核"',
                'placeholder="挂载状态"',
                'placeholder="对接路径"',
                'placeholder="映射起"',
                "最近同步时间",
                "channel-mappings/export",
                "channel-mappings/export-tasks/",
                "快捷 Tab 已覆盖已挂载/未挂载/已阻断",
            ),
            str(WEB),
        )
    )

    merchant, tenant_id = _ensure_merchant()
    secret = f"a14sec_{uuid.uuid4().hex[:12]}"
    dy_shop = f"dy_{uuid.uuid4().hex[:8]}"
    code, cfg = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={
            "enabled_combos": ["1A"],
            "douyin_shop_id": dy_shop,
            "douyin_webhook_secret": secret,
        },
    )
    assert code == 200 and cfg.get("douyin_configured"), cfg

    pid = _on_sale_product(merchant)
    ch_pid = f"Dou{uuid.uuid4().hex[:8]}"
    code, mapping = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel": "douyin",
            "channel_product_id": ch_pid,
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VA14-1 新建映射",
            code == 200 and mapping.get("status") == "mapped",
            f"{code} {mapping.get('status')}",
        )
    )
    mid = mapping["id"]
    sid = mapping.get("shop_id")
    code, scoped = req(
        "GET", f"/shop/channel-mappings?shop_id={sid}", token=merchant
    )
    scoped_ids = [str(i.get("id")) for i in (scoped.get("items") or [])] if isinstance(scoped, dict) else []
    results.append(
        check(
            "VA14-1b 当前店可见映射",
            code == 200 and str(mid) in scoped_ids and bool(sid),
            f"{code} sid={sid} ids={scoped_ids[:5]}",
        )
    )
    fake = str(uuid.uuid4())
    code, empty = req(
        "GET", f"/shop/channel-mappings?shop_id={fake}", token=merchant
    )
    results.append(
        check(
            "VA14-1c 他店 UUID 映射为空",
            code == 200 and isinstance(empty, dict) and empty.get("total") == 0,
            f"{code} {empty.get('total') if isinstance(empty, dict) else empty}",
        )
    )

    code, by_audit = req(
        "GET",
        f"/shop/channel-mappings?external_audit_status=approved&q={ch_pid}",
        token=merchant,
    )
    audit_ids = [str(i.get("id")) for i in (by_audit.get("items") or [])] if isinstance(by_audit, dict) else []
    results.append(
        check(
            "VA14-1d 外部审核=已通过",
            code == 200 and str(mid) in audit_ids and mapping.get("path_label") == "A",
            f"{code} path={mapping.get('path_label')} ids={audit_ids[:5]}",
        )
    )
    code, path_b = req(
        "GET", f"/shop/channel-mappings?path=B&q={ch_pid}", token=merchant
    )
    results.append(
        check(
            "VA14-1e 对接路径 B 不含本条",
            code == 200 and isinstance(path_b, dict) and path_b.get("total") == 0,
            f"{code} {path_b.get('total') if isinstance(path_b, dict) else path_b}",
        )
    )
    code, path_a = req(
        "GET", f"/shop/channel-mappings?path=A&q={ch_pid}", token=merchant
    )
    path_a_ids = [str(i.get("id")) for i in (path_a.get("items") or [])] if isinstance(path_a, dict) else []
    results.append(
        check(
            "VA14-1f 对接路径 A 含本条",
            code == 200 and str(mid) in path_a_ids,
            f"{code} ids={path_a_ids[:5]}",
        )
    )
    code, future = req(
        "GET",
        f"/shop/channel-mappings?mapped_from=2099-01-01&q={ch_pid}",
        token=merchant,
    )
    results.append(
        check(
            "VA14-1g 映射起未来为空",
            code == 200 and isinstance(future, dict) and future.get("total") == 0,
            f"{code} {future.get('total') if isinstance(future, dict) else future}",
        )
    )
    code, past = req(
        "GET",
        f"/shop/channel-mappings?mapped_from=2020-01-01&mapped_to=2099-12-31&q={ch_pid}",
        token=merchant,
    )
    past_ids = [str(i.get("id")) for i in (past.get("items") or [])] if isinstance(past, dict) else []
    results.append(
        check(
            "VA14-1h 映射时间区间含本条",
            code == 200 and str(mid) in past_ids,
            f"{code} ids={past_ids[:5]}",
        )
    )
    code, csv_body = req(
        "GET", f"/shop/channel-mappings/export?q={ch_pid}", token=merchant
    )
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VA14-1i 导出含默认列与本条",
            code == 200
            and "本地商品" in csv_text
            and "最近同步时间" in csv_text
            and ch_pid in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )
    code, map_task = req(
        "POST", "/shop/channel-mappings/export", token=merchant, body={"q": ch_pid}
    )
    results.append(
        check(
            "VA14-X1 POST 导出任务已完成",
            code == 200
            and isinstance(map_task, dict)
            and map_task.get("status") == "done"
            and map_task.get("resource") == "channel_mappings"
            and map_task.get("id"),
            f"{code} {map_task}",
        )
    )
    map_task_id = (map_task or {}).get("id") if isinstance(map_task, dict) else None
    if map_task_id:
        code, map_file = req(
            "GET", f"/shop/channel-mappings/export-tasks/{map_task_id}/file", token=merchant
        )
        results.append(
            check(
                "VA14-X2 任务文件可下载",
                code == 200 and "本地商品" in str(map_file) and ch_pid in str(map_file),
                f"{code} head={str(map_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VA14-X2 任务文件可下载", False, "no task id"))
    code, map_cols = req(
        "POST",
        "/shop/channel-mappings/export",
        token=merchant,
        body={"q": ch_pid, "columns": ["product_name", "status_label"]},
    )
    if code == 200 and isinstance(map_cols, dict) and map_cols.get("id"):
        code2, map_col_csv = req(
            "GET",
            f"/shop/channel-mappings/export-tasks/{map_cols['id']}/file",
            token=merchant,
        )
        head = str(map_col_csv).splitlines()[0] if map_col_csv else ""
        results.append(
            check(
                "VA14-X3 列配置导出表头",
                code2 == 200
                and "本地商品" in head
                and "挂载状态" in head
                and "外部商品 ID" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA14-X3 列配置导出表头", False, f"{code} {map_cols}"))
    code, plat_map = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_map_token = (
        plat_map.get("access_token") if code == 200 and isinstance(plat_map, dict) else None
    )
    code, map_forbidden = req(
        "POST", "/shop/channel-mappings/export", token=plat_map_token, body={}
    )
    results.append(
        check(
            "VA14-P01 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {map_forbidden}",
        )
    )

    code, paused = req("POST", f"/shop/channel-mappings/{mid}/pause", token=merchant)
    results.append(
        check(
            "VA14-2 暂停同步",
            code == 200
            and paused.get("status") == "paused"
            and paused.get("status_label") == "暂停同步"
            and paused.get("external_audit_status") == "approved",
            f"{code} {paused}",
        )
    )

    code, bad = req("POST", f"/shop/channel-mappings/{mid}/pause", token=merchant)
    results.append(
        check(
            "VA14-3 非已挂载不可再暂停",
            code == 422 and "已挂载" in _err_text(bad),
            f"{code} {_err_text(bad)}",
        )
    )

    # 暂停后 Webhook 拒单
    ext = f"DD{uuid.uuid4().hex[:10]}"
    payload = {
        "event_id": f"ev_{uuid.uuid4().hex[:12]}",
        "event_type": "order.paid",
        "tenant_id": tenant_id,
        "douyin_shop_id": dy_shop,
        "channel_product_id": ch_pid,
        "external_order_no": ext,
        "buyer_mobile": "13900001111",
        "paid_amount_cents": 19900,
    }
    payload["sign"] = stub_douyin_sign(payload, secret)
    code, wh = req("POST", "/webhooks/douyin/order", body=payload)
    results.append(
        check(
            "VA14-4 暂停态拒单 mapping_paused",
            code == 409 and "mapping_paused" in _err_text(wh),
            f"{code} {_err_text(wh)}",
        )
    )

    code, logs = req(
        "GET", f"/shop/channel-mappings/{mid}/logs?category=status", token=merchant
    )
    results.append(
        check(
            "VA14-5 日志含暂停事件",
            code == 200
            and any(i.get("event") == "listing_paused" for i in (logs.get("items") or [])),
            f"{code} {[i.get('event') for i in (logs.get('items') or [])]}",
        )
    )

    code, logs_wh = req(
        "GET", f"/shop/channel-mappings/{mid}/logs?category=webhook", token=merchant
    )
    results.append(
        check(
            "VA14-6 日志含回调拒单",
            code == 200
            and any(i.get("event") == "auto_reject" for i in (logs_wh.get("items") or [])),
            f"{code} {logs_wh.get('total')}",
        )
    )

    code, resumed = req("POST", f"/shop/channel-mappings/{mid}/resume", token=merchant)
    results.append(
        check(
            "VA14-7 恢复同步",
            code == 200 and resumed.get("status") == "mapped",
            f"{code} {resumed.get('status')}",
        )
    )

    code, synced = req("POST", f"/shop/channel-mappings/{mid}/sync", token=merchant)
    results.append(
        check(
            "VA14-8 重新同步",
            code == 200 and synced.get("status") == "mapped",
            f"{code} {synced.get('status')}",
        )
    )

    code, logs_all = req("GET", f"/shop/channel-mappings/{mid}/logs", token=merchant)
    results.append(
        check(
            "VA14-9 日志含恢复与同步",
            code == 200
            and any(i.get("event") == "listing_resumed" for i in (logs_all.get("items") or []))
            and any(i.get("event") == "sync_succeeded" for i in (logs_all.get("items") or [])),
            f"{code} {[i.get('event') for i in (logs_all.get('items') or [])]}",
        )
    )

    passed = sum(1 for x in results if x)
    print(f"\nA14: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
