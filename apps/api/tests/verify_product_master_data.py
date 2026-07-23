#!/usr/bin/env python3
"""产品基础数据验收：分类 + 计量单位；Alembic head=078。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "web"
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import check, req
from tests.verify_crm_helpers import finish_phase


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    if code != 200:
        raise RuntimeError(f"login failed {phone}: {code} {data}")
    return data["access_token"]


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    out = alembic_head()
    results.append(check(f"VPM-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))

    admin_tok = login("13900000099", "test123456")

    code, cats = req("GET", "/crm/product-categories", token=admin_tok)
    results.append(check("VPM-1-1 list categories 200", code == 200, str(code)))

    cat_name = f"验收分类-{uuid.uuid4().hex[:4]}"
    code, cat = req(
        "POST",
        "/crm/product-categories",
        token=admin_tok,
        body={"name": cat_name, "sort_order": 1, "is_active": True},
    )
    results.append(check("VPM-1-2 create category 201", code == 201, f"{code} {cat}"))
    cat_id = (cat or {}).get("id")

    code, units = req("GET", "/crm/product-units", token=admin_tok)
    results.append(check("VPM-2-1 list units 200", code == 200, str(code)))

    code, seeded = req("POST", "/crm/product-units/seed-defaults", token=admin_tok)
    results.append(check("VPM-2-2 seed defaults 200", code == 200, str(code)))
    results.append(check("VPM-2-3 seed has 套", any((u or {}).get("name") == "套" for u in (seeded or [])), str(seeded)))

    unit_name = f"箱-{uuid.uuid4().hex[:4]}"
    code, unit = req(
        "POST",
        "/crm/product-units",
        token=admin_tok,
        body={"name": unit_name, "sort_order": 9, "is_active": True},
    )
    results.append(check("VPM-2-4 create unit 201", code == 201, f"{code} {unit}"))

    code, prod = req(
        "POST",
        "/crm/products",
        token=admin_tok,
        body={
            "name": f"验收产品-{uuid.uuid4().hex[:4]}",
            "list_price": 100,
            "category_id": cat_id,
            "unit": unit_name,
            "is_active": True,
        },
    )
    results.append(check("VPM-3-1 product with category+unit 201", code == 201, f"{code} {prod}"))
    results.append(
        check(
            "VPM-3-2 unit persisted",
            (prod or {}).get("unit") == unit_name,
            str((prod or {}).get("unit")),
        )
    )

    code, bad = req(
        "POST",
        "/crm/products",
        token=admin_tok,
        body={
            "name": f"坏单位产品-{uuid.uuid4().hex[:4]}",
            "list_price": 1,
            "unit": "不存在单位",
            "is_active": True,
        },
    )
    results.append(check("VPM-3-3 invalid unit rejected", code == 400, f"{code} {bad}"))

    settings_vue = (WEB_ROOT / "src" / "views" / "SettingsProductMasterData.vue").read_text(encoding="utf-8")
    products_vue = (WEB_ROOT / "src" / "views" / "crm" / "Products.vue").read_text(encoding="utf-8")
    router_js = (WEB_ROOT / "src" / "router.js").read_text(encoding="utf-8")
    results.append(check("VPM-4-1 settings page", "产品基础数据" in settings_vue, "SettingsProductMasterData.vue"))
    results.append(check("VPM-4-2 products unit select", "listProductUnits" in products_vue, "Products.vue"))
    results.append(check("VPM-4-3 route", "product-master-data" in router_js, "router.js"))

    return finish_phase("产品基础数据", results)


if __name__ == "__main__":
    raise SystemExit(main())
