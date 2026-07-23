# 订单数据对接 ERP 集成方案（v1.4 设计稿）

> 调研/设计时间：2026-07-18
> 决策基线：
> - **ERP 厂商**：金蝶（云星空/星辰）或 用友（U8/T+），走 OpenAPI / WebService
> - **对接范围**：全主数据打通（客户 / 产品 / 价格 / 订单 / 合同 / 发票 / 回款 / 发货 / 库存）
> - **部署形态**：SaaS 多租户**共享一个 ERP 实例**，每个 tenant 映射到不同核算主体（账套/公司码）
> - **实时性**：准实时事件驱动（Outbox + Worker），状态类定时拉取或 ERP 回调 WebHook
> 关联：订单模型见 `apps/api/app/models/crm.py`（Order/OrderLine/Contract/Invoice/Payment/DeliveryNote）；对接位预留见 `docs/v0.7-crm-deal执行计划.md` §6

---

## 0. 总体原则

1. **反腐蚀层（Anti-Corruption Layer）**：ERP 永远是外部系统。定义 `ERPAdapter` 抽象接口，金蝶/用友各一个实现，可热切换、可 Mock。沿用本项目 `MockWeChatPublisher`/`RealWeChatPublisher` 同接口模式。
2. **系统 of record 划分**
   - CRM 负责：商机、报价、合同、**订单草稿与审批**、销售过程
   - ERP 负责：**销售订单执行、客户/物料主数据、价格基准、发票、收款清账、发货出库、库存、总账**
3. **多租户共享 ERP**：`tenant_id` → ERP 核算主体（金蝶＝账套/组织，用友＝账套）。所有同步按 tenant 路由到对应主体 + 凭证。
4. **至少一次投递 + 幂等**：订单 `confirmed` 后入 Outbox，后台 Worker 异步推；以业务主键（tenant+业务单号）去重，Adapter 侧做 upsert。
5. **主数据以 ERP 为准**：客户/产品/价格优先引用 ERP 编码；CRM 自建的实时推 ERP 生成并回写 ERP 编码。

---

## 1. 数据模型扩展（Alembic 迁移，不动业务表）

| 表 | 用途 | 关键字段 |
|---|---|---|
| `erp_tenant_bindings` | 租户↔ERP 核算主体 + 凭证 | tenant_id, erp_org_code, erp_sets_of_books, endpoint, app_id, app_secret(加密), enabled |
| `erp_sync_outbox` | 可靠事件队列 | id, tenant_id, entity_type, entity_id, event_type(created/updated/confirmed), payload(JSON), status(pending/done/failed), attempts, last_error, next_retry_at |
| `erp_entity_maps` | CRM id ↔ ERP id 映射 | tenant_id, entity_type, crm_id, erp_id, erp_code, synced_at |
| `erp_sync_config` | WebHook 订阅状态/拉取游标 | tenant_id, entity_type, webhook_subscribed, last_pull_at, cron_expr |

> 业务表 `extra_data`(JSON) 仍可作为轻量兜底存 `erp_id`/`sync_status`，但统一映射建议走 `erp_entity_maps`，便于对账与排查。

---

## 2. 字段级映射（全主数据）

| CRM 实体 / 字段 | ERP 对应（典型） | 同步方向 | 备注 |
|---|---|---|---|
| `tenant_id` → `erp_tenant_bindings.erp_org_code` | 账套/公司码 | — | 路由键 |
| `customers.customer_number` / `company_name` | 客户主数据（BD_Customer / 客户档案） | 双向 | CRM 自建→推 ERP 生成并回写 `erp_code`；ERP 已有→直接引用 `customer_number`=ERP 编码 |
| `products.code` / `name` / `list_price` / `cost_price` | 物料（BD_Material / 存货档案） | 双向 | 基准价以 ERP 物料为准，`cost_price` 来自 ERP |
| `price_books` / `price_book_entries` | 价格策略（可选映射） | ERP→CRM | 基准价取 ERP，促销价 CRM 侧 |
| `orders.order_number`(status=confirmed) + `order_lines` | 销售订单（SAL_SaleOrder / 销售订单） | CRM→ERP | **必须 confirmed 后推**；行：product_id→物料、quantity、unit_price、discount_rate、tax_rate |
| `contracts.contract_number` | 框架协议/合同（可选） | 双向 | |
| `invoices.invoice_number` / `amount` / `tax_amount` | 销售发票（SAL_SaleInvoice / 销售发票） | ERP→CRM 为主 | CRM 可开票则双向 |
| `payments.payment_number` / `amount` / `paid_at` | 收款单（AR_RECEIVEBILL / 收款单） | ERP→CRM | 回写 CRM 回款状态、支撑应收台账 |
| `delivery_notes.delivery_number` | 发货通知/出库（SAL_DELIVERYNOTICE / 发货单） | ERP→CRM | 回写 `shipped_at`/`delivered_at`/物流 |
| 库存（新增视图） | 库存（STK_Inventory / 现存量） | ERP→CRM | 订单行可用性校验、交付承诺 |

> **金额口径坑**：CRM `order_lines.line_total` 是「折后未税合计」，含税另算（`line_total_incl_tax`）。推 ERP 时务必对齐「含税/未税」与税码，避免财务对账差一分钱。

---

## 3. 准实时事件流

```
订单 confirm（事务内）
   └─ 写 erp_sync_outbox(event=order.confirmed, payload=订单快照)
Worker（定时/队列）消费 outbox：
   1. 据 tenant_id 取 erp_tenant_bindings（endpoint+凭证+主体）
   2. ERPAdapter.create_sales_order(order) → 幂等 upsert
   3. 成功 → 写 erp_entity_maps(erp_so_id) + outbox=done
   4. 失败 → attempts++，退避重试；超阈值告警
ERP 回传（订阅 WebHook 或定时拉取）：
   发票/回款/发货/库存 状态变更 → 更新 CRM 对应表 + erp_entity_maps
```

- 复用现有基建：WebHook 公开接口（FR-CRM-CAMP-08 线索）、cron（合同到期通知）机制直接作为集成样板。
- 失败隔离：单 tenant / 单单据失败不影响其他；提供「手动重推」入口。

---

## 4. Adapter 接口（抽象，先 Mock 后真接）

```python
class ERPAdapter(ABC):
    def bind(self, binding: ErpTenantBinding) -> None: ...
    def upsert_customer(self, customer) -> str: ...      # 返回 ERP code
    def upsert_product(self, product) -> str: ...
    def create_sales_order(self, order) -> str: ...      # 幂等 upsert
    def issue_invoice(self, invoice) -> str: ...
    def post_payment(self, payment) -> str: ...
    def create_delivery(self, note) -> str: ...
    def pull_status(self, entity_type, cursor) -> list: ...  # 回传
    def pull_inventory(self, product_codes) -> dict: ...

class MockERPAdapter(ERPAdapter): ...   # 先跑通链路，返回假 ERP id
class KingdeeAdapter(ERPAdapter): ...   # 金蝶 OpenAPI + access_token
class U8Adapter(ERPAdapter): ...        # 用友 OpenAPI / EAI
```

金蝶云星空：OpenAPI(REST) + AppId/AppSecret 换 access_token，表单如 SAL_SaleOrder / BD_Customer / BD_Material；支持 WebHook 订阅。
用友：T+ 走 OpenAPI(token 认证)，U8 走 EAI/XML WebService。
> 具体表单 ID、字段名需对照目标版本确认；Adapter 内做映射，不影响上层。

---

## 5. 落地路线

**P0 — 基础设施 + 订单单向 MVP（约 8~10 人天）**
- 迁移：`erp_tenant_bindings` / `erp_sync_outbox` / `erp_entity_maps` / `erp_sync_config`
- 抽象：`ERPAdapter` + `MockERPAdapter`；Outbox Worker（可单进程定时或接入队列）
- MVP：订单 `confirmed` → 推销售订单（Mock），幂等 + 重试 + 手动重推
- 验收：Mock 全绿、重复 confirm 不重复生成、失败可重推

**P1 — 主数据双向 + 回传（约 10~12 人天）**
- 客户/产品/价格 upsert（双向），回写 `erp_code`
- 回传发票/回款/发货状态到 CRM（`invoices`/`payments`/`delivery_notes` 状态字段）
- 验收：CRM 建客户→ERP 生成→回写；ERP 收款→CRM 回款状态更新

**P2 — 库存/全主数据 + 真实厂商 + 对账（约 10~14 人天）**
- 接真实金蝶/用友 Adapter（按所选厂商）
- ERP WebHook 订阅 / 定时拉取库存
- 对账：CRM 应收台账 = ERP 未清项，定时校验告警
- 验收：端到端真环境跑通一单；对账差异 < 阈值

---

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 金额/税率口径不一致 | 统一「未税/含税/税码」约定；加对账校验 |
| 租户错账（推到错误账套） | `erp_tenant_bindings` 强校验；发送前断言 tenant↔主体映射存在 |
| ERP 侧字段不全/版本差异 | 映射全部收敛在 Adapter，上层不变 |
| 网络/ERP 抖动 | Outbox 至少一次 + 退避重试 + 告警 + 手动重推 |
| 主数据循环同步 | 用 `source`/`synced_at` 标记来源，避免 A→B→A 死循环 |

---

## 7. 下一步

1. 确认具体厂商与版本（金蝶云星空 / 星辰 / 用友 U8 / T+）→ 锁定表单与认证。
2. 确认多租户下「账套」分配规则（每租户固定一个账套？还是按业务线）。
3. 从 P0 起步，先 Mock 跑通 Outbox+Worker，再接真实厂商。
