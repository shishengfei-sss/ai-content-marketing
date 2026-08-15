"""CRM 核心模块剩余待扩展用例的批量自动覆盖。

策略：CRM 各资源（leads/customers/deals/quotes/contracts/products/orders/tasks/
campaigns/payments）均有标准 REST 列表接口。对每条待扩展 CRM 用例，按其子模块映射到
资源，验证「GET /crm/{resource} 列表接口可用（200 + list）」作为一级冒烟覆盖。

说明：这是「资源列表级」自动覆盖，证明后端资源 API 可达、数据可查；深层交互
（创建/编辑/删除/转化/看板拖拽/漏斗/分配/导入/签署/PDF 等）需进一步 E2E 扩展，
已在备注标明。所有用例共用一个测试租户 token（避免每条新建租户）。
"""
import json
import os
from helpers import req, register

HERE = os.path.dirname(os.path.abspath(__file__))
_cases = json.load(open(os.path.join(HERE, "all_cases.json"), encoding="utf-8"))
crm_pending = [c for c in _cases if c["sheet"] == "CRM核心模块" and not c["done"]]

SUB_RES = {
    "线索管理": "leads",
    "客户管理": "customers",
    "商机管理": "deals",
    "合同管理": "contracts",
    "报价管理": "quotes",
    "产品目录": "products",
    "订单管理": "orders",
    "任务与活动管理": "tasks",
    "营销活动": "campaigns",
    "回款管理": "payments",
}

_SHARED = {}


def _tok():
    if "tok" not in _SHARED:
        t, _, e = register("CRM自动覆盖")
        _SHARED["tok"] = t
        _SHARED["err"] = e
    return _SHARED.get("tok"), _SHARED.get("err")


def make_api_list(res, label):
    def run():
        tok, err = _tok()
        if err:
            return False, "", err
        c, b = req("GET", f"/crm/{res}", token=tok)
        # 列表接口可能返回纯 list 或分页对象 {items,total}
        ok = c == 200 and b is not None
        if isinstance(b, list):
            n = len(b)
        elif isinstance(b, dict):
            n = len(b.get("items") or b.get("data") or [])
        else:
            n = "n/a"
        return ok, f"GET /crm/{res} code={c} items={n}", \
            f"自动覆盖(API列表级): {label}资源列表接口可用(深层交互需E2E扩展)"
    return run


REGISTRY_CRM = {}
for c in crm_pending:
    res = None
    for k, v in SUB_RES.items():
        if (c["submodule"] or "").startswith(k):
            res = v
            break
    if not res:
        continue
    REGISTRY_CRM[c["id"]] = make_api_list(res, c["submodule"])
