"""工商数据查询（MVP：stub，可配置真实 Provider）。"""

from __future__ import annotations

import hashlib
import os
from datetime import date


def lookup_company(company_name: str) -> dict:
    """按公司名返回工商摘要。

    环境变量 BUSINESS_LOOKUP_PROVIDER:
      - stub（默认）：确定性 mock，便于联调/验收
      - disabled：返回 available=False
    """
    name = (company_name or "").strip()
    if not name:
        return {"available": False, "provider": "none", "detail": "公司名为空"}
    provider = (os.environ.get("BUSINESS_LOOKUP_PROVIDER") or "stub").lower()
    if provider == "disabled":
        return {"available": False, "provider": "disabled", "detail": "工商查询未启用"}

    # stub：用哈希生成稳定字段，后续可换成天眼查/企查查
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    capital = (int(digest[:4], 16) % 9000 + 1000) * 10000
    year = 2000 + (int(digest[4:6], 16) % 24)
    month = 1 + (int(digest[6:8], 16) % 12)
    day = 1 + (int(digest[8:10], 16) % 28)
    credit_code = f"91{digest[:16].upper()}"
    return {
        "available": True,
        "provider": "stub",
        "company_name": name,
        "credit_code": credit_code,
        "legal_representative": f"法人{digest[10:14].upper()}",
        "registered_capital": float(capital),
        "established_date": str(date(year, month, day)),
        "business_scope": "软件开发；信息技术咨询；企业管理咨询（依法须经批准的项目，经相关部门批准后方可开展经营活动）",
        "raw": {"mode": "stub"},
    }
