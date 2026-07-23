# -*- coding: utf-8 -*-
"""回归：深圳二高办公设备采购公告结构化抽取。"""
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.services.tender_parse_service import _heuristic_extract

SAMPLE = (API_ROOT / "tests" / "_sample_tender.txt").read_text(encoding="utf-8")


def main() -> int:
    r = _heuristic_extract(SAMPLE, "paste-sz.txt")
    checks = [
        ("buyer", "第二高级中学" in (r.get("buyer_name") or "") and r.get("buyer_name") != "信息"),
        ("product", "便携式计算机" in (r.get("product_name") or "") and "用户需求书" not in (r.get("product_name") or "")),
        ("region", "深圳" in (r.get("region") or "") and "必须选择" not in (r.get("region") or "")),
        ("qty", "91" in (r.get("quantity") or "")),
        ("budget", r.get("budget_max") == 3227000.0),
        ("deadline", r.get("deadline") == "2026-07-27"),
        ("contact", r.get("contact_name") == "郑洪生"),
        ("phone", r.get("contact_phone") == "0755-86500014"),
        ("url", (r.get("source_url") or "").startswith("http") and "）" not in (r.get("source_url") or "")),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'} {name}: {r.get('buyer_name') if name=='buyer' else r.get({'product':'product_name','region':'region','qty':'quantity','budget':'budget_max','deadline':'deadline','contact':'contact_name','phone':'contact_phone','url':'source_url'}[name])!r}")
    if failed:
        print("FAILED", failed)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
