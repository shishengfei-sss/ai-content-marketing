#!/usr/bin/env python3
"""A02 商品列表 §0b 验收。对照 PRD 01-管理端UI.html #a02。"""

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
from tests.verify_shop_a14 import _ensure_merchant, _on_sale_product  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ProductsList.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA02-UI §0b 列/筛选/导出/列设置",
            _page_has(
                WEB,
                "#a02",
                "#a02a",
                "#a02b",
                "#a02c",
                'label="封面"',
                'label="名称"',
                'label="销量"',
                'label="公域"',
                "高级筛选",
                "公域挂载",
                "列设置",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                "/shop/products/export",
                "/shop/products/export-tasks/",
                "page-sizes",
                "公域映射",
                "未关联",
                "批量提交审核",
                "批量下架",
                "delete-precheck",
                "确认删除",
            ),
            str(WEB),
        )
    )

    merchant, _tid = _ensure_merchant()
    pid = _on_sale_product(merchant)

    code, listing = req("GET", "/shop/products?page_size=20", token=merchant)
    results.append(
        check(
            "VA02-1 列表含封面/销量/公域字段",
            code == 200
            and isinstance(listing.get("items"), list)
            and listing.get("status_counts") is not None
            and any(
                i.get("id") == pid
                and "sales_count" in i
                and "cover_url" in i
                and "channel_mount_label" in i
                for i in listing["items"]
            ),
            f"{code} total={listing.get('total')} sample={ (listing.get('items') or [{}])[0] }",
        )
    )

    # 绑定抖店并挂载 → 公域=已挂载
    secret = f"a02_{uuid.uuid4().hex[:10]}"
    code, cfg = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={
            "enabled_combos": ["1A"],
            "douyin_shop_id": f"dy_{uuid.uuid4().hex[:8]}",
            "douyin_webhook_secret": secret,
        },
    )
    assert code == 200, cfg

    # 若该品已有映射则直接筛；否则创建
    code, mapped_list = req(
        "GET", f"/shop/channel-mappings?page_size=50&status=mapped", token=merchant
    )
    has_mapped = any(
        str(i.get("product_id")) == str(pid) for i in (mapped_list.get("items") or [])
    )
    if not has_mapped:
        code, m = req(
            "POST",
            "/shop/channel-mappings",
            token=merchant,
            body={
                "product_id": pid,
                "channel": "douyin",
                "channel_product_id": f"DouA02{uuid.uuid4().hex[:8]}",
                "combo": "1A",
            },
        )
        # 可能已占用 → 忽略，改用筛选结果
        if code != 200 and "already_mapped" not in str(m):
            results.append(check("VA02-2 准备已挂载映射", False, f"{code} {m}"))
        else:
            results.append(check("VA02-2 准备已挂载映射", True, f"{code}"))
    else:
        results.append(check("VA02-2 准备已挂载映射", True, "reuse"))

    code, by_mount = req(
        "GET", "/shop/products?channel_mount=mapped&page_size=50", token=merchant
    )
    results.append(
        check(
            "VA02-3 高级筛：公域已挂载",
            code == 200
            and any(i.get("channel_mount") == "mapped" for i in (by_mount.get("items") or []))
            and all(
                i.get("channel_mount") == "mapped" for i in (by_mount.get("items") or [])
            ),
            f"{code} n={len(by_mount.get('items') or [])}",
        )
    )

    code, priced = req(
        "GET", "/shop/products?price_min_cents=1&price_max_cents=99999999&page_size=5", token=merchant
    )
    results.append(
        check(
            "VA02-4 售价区间筛选",
            code == 200 and isinstance(priced.get("items"), list),
            f"{code} {priced.get('total')}",
        )
    )

    code, csv_body = req(
        "GET",
        "/shop/products/export?status=on_sale",
        token=merchant,
    )
    text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VA02-5 导出 CSV 含默认列头",
            code == 200
            and "名称" in text
            and "销量" in text
            and "公域" in text
            and "售价" in text,
            f"{code} head={text[:80]!r}",
        )
    )
    code, task = req("POST", "/shop/products/export", token=merchant, body={"status": "on_sale"})
    results.append(
        check(
            "VA02-X1 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "products"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req("GET", f"/shop/products/export-tasks/{task_id}/file", token=merchant)
        results.append(
            check(
                "VA02-X2 任务文件可下载",
                code == 200 and "名称" in str(file_csv) and "销量" in str(file_csv),
                f"{code} head={str(file_csv)[:80]!r}",
            )
        )
    else:
        results.append(check("VA02-X2 任务文件可下载", False, "no task id"))
    code, cols_task = req(
        "POST",
        "/shop/products/export",
        token=merchant,
        body={"columns": ["name", "status"]},
    )
    if code == 200 and isinstance(cols_task, dict) and cols_task.get("id"):
        code2, col_csv = req(
            "GET",
            f"/shop/products/export-tasks/{cols_task['id']}/file",
            token=merchant,
        )
        head = str(col_csv).splitlines()[0] if col_csv else ""
        results.append(
            check(
                "VA02-X3 列配置导出表头",
                code2 == 200 and "名称" in head and "状态" in head and "销量" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA02-X3 列配置导出表头", False, f"{code} {cols_task}"))
    code, plat = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_token = plat.get("access_token") if code == 200 and isinstance(plat, dict) else None
    code, forbidden = req("POST", "/shop/products/export", token=plat_token, body={})
    results.append(
        check(
            "VA02-P01 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {forbidden}",
        )
    )

    # Tab 计数
    code, all_list = req("GET", "/shop/products?page_size=1", token=merchant)
    sc = all_list.get("status_counts") or {}
    results.append(
        check(
            "VA02-6 status_counts 含 all/草稿等",
            code == 200 and "all" in sc and isinstance(sc.get("all"), int),
            f"{code} {sc}",
        )
    )

    # 下架自动暂停映射
    code, off = req("POST", f"/shop/products/{pid}/off-sale", token=merchant)
    code2, maps = req("GET", f"/shop/channel-mappings?page_size=50", token=merchant)
    paused = [
        i
        for i in (maps.get("items") or [])
        if str(i.get("product_id")) == str(pid) and i.get("status") == "paused"
    ]
    results.append(
        check(
            "VA02-7 下架自动暂停映射",
            code == 200 and off.get("status") == "off_sale" and len(paused) >= 1,
            f"off={code} paused={len(paused)}",
        )
    )

    # 有映射不可删
    code, pre = req("GET", f"/shop/products/{pid}/delete-precheck", token=merchant)
    results.append(
        check(
            "VA02-8 有映射 delete-precheck 不可删",
            code == 200
            and pre.get("can_delete") is False
            and "channel_mappings" in (pre.get("blockers") or []),
            f"{code} {pre}",
        )
    )
    code, del_fail = req("DELETE", f"/shop/products/{pid}", token=merchant)
    results.append(
        check(
            "VA02-9 有映射删除 422",
            code == 422,
            f"{code} {del_fail}",
        )
    )

    # 解除映射后可删（先 unmap）
    mid = paused[0]["id"] if paused else None
    if mid:
        req("DELETE", f"/shop/channel-mappings/{mid}", token=merchant)
    # 可能还有其他映射
    code, maps2 = req("GET", "/shop/channel-mappings?page_size=50", token=merchant)
    for i in maps2.get("items") or []:
        if str(i.get("product_id")) == str(pid) and i.get("status") != "unmapped":
            req("DELETE", f"/shop/channel-mappings/{i['id']}", token=merchant)

    code, pre2 = req("GET", f"/shop/products/{pid}/delete-precheck", token=merchant)
    results.append(
        check(
            "VA02-10 解除映射后可删",
            code == 200 and pre2.get("can_delete") is True,
            f"{code} {pre2}",
        )
    )
    code, deleted = req("DELETE", f"/shop/products/{pid}", token=merchant)
    results.append(
        check("VA02-11 软删 204", code == 204, f"{code} {deleted}"),
    )

    # 批量下架：再建一个在售品
    pid2 = _on_sale_product(merchant)
    code, batch = req(
        "POST",
        "/shop/products/batch-off-sale",
        token=merchant,
        body={"product_ids": [pid2]},
    )
    results.append(
        check(
            "VA02-12 批量下架",
            code == 200 and batch.get("ok_count") == 1,
            f"{code} {batch}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA02: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
