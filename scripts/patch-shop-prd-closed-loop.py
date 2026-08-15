#!/usr/bin/env python3
"""Apply business/data closed-loop fixes from 21-PRD-Phase1-业务与数据闭环分析.md."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/01-PRD/21-内容获客商城-phase1"
PRD = BASE / "PRD-内容获客商城-phase1.md"
FLOWS = BASE / "03-数据流.html"
MODEL = BASE / "04-数据模型.html"
INDEX = BASE / "index.html"


def patch_prd() -> None:
    text = PRD.read_text(encoding="utf-8")

    boundary = """
### 1.2 Phase 1 闭环边界声明（已知开放边）

> 对照 [业务与数据闭环分析](./21-PRD-Phase1-业务与数据闭环分析.md)。下列项**不阻塞 Mx 交易验收**，但实现与验收须对齐边界，避免误判为缺陷。

| 类别 | 边界 | Phase 1 做法 | 后续 |
|------|------|--------------|------|
| 套餐资金流 | 商家→平台 B2B 购套餐 | 线下对公 + P11 人工开通；系统外收款，靠备注勾稽 | Phase 2 自助购 |
| 平台→商家结算 | P05 清结算 | UI/API/权限 + **F10 数据模型**；批次 T+1 生成，打款人工确认 | 自动分账对接 |
| 公域退款 | 抖店/课程库 refund 事件 | Webhook `event=order.refund` → 同 **F2** 关权（§8.11） | — |
| 发票冲红 | 已开票后退款 | F2 仅标 `needs_red_flush=true`；**红冲人工线下** | Phase 2 全流程 |
| 买家身份 | 私域 openid / 公域 mobile / 课程库 openid | **mobile 归一** + openid 绑定（§3.2 · 04 `#b`） | 跨 tenant 合并 Phase 2 |
| 机审 | F6 上架闸 | 敏感词库可配置；**Phase 1 可降级为全人审**（机审 stub 全 flag） | 规则引擎增强 |
| 公域链路 | Mx 验收 | **先通链路 ① 或 ② 一条**；路径 A/B 其余组合 Phase 2 | §3.5 |

**真·数据断点（本版已补文档）**：① 公域 refund→F2（§8.11）；② 结算表 + F10（04 / 03）；③ 买家身份归一策略（04 `#b`）。
"""

    if "### 1.2 Phase 1 闭环边界声明" not in text:
        text = text.replace(
            "| 🚫 公域四链路全组合 | Mx 先通 ① **或** ② 一条；路径 A/B 与链路独立但验收期择一 |\n\n## 二、商家主体",
            "| 🚫 公域四链路全组合 | Mx 先通 ① **或** ② 一条；路径 A/B 与链路独立但验收期择一 |"
            + boundary
            + "\n## 二、商家主体",
        )

    webhook_old = """**Webhook 处理（链路 ① 摘要）**：

1. 验签 + 解析 `external_order_no`
2. 查 `shop_channel_listings`；未 mapped / 未过闸 → **拒单** + 审计日志
3. 幂等：已存在 `(channel, external_order_no)` → 200 空操作
4. INSERT `shop_orders`（`channel=doudian`，`status=claim_pending` 或 `paid`）
5. INSERT `payments`（若已付）
6. INSERT `entitlements` + `claim_tokens`（待领权）
7. 触发领权短信（A15 配置 · F9 短信额度）

**商家 `closed`/`suspended`**"""

    webhook_new = """**Webhook 处理（链路 ① · 按 `event` 分支）**：

| `event` | 处理 | 落点 |
|---------|------|------|
| `order.pay_success` | 见下 1–7 步 | F3 正向 |
| `order.refund` / `order.refund_success` | 见下 **R1–R6** | **F2 关权**（与微信 refund-notify 同效） |

**`order.pay_success`（正向 1–7）**：

1. 验签 + 解析 `external_order_no`
2. 查 `shop_channel_listings`；未 mapped / 未过闸 → **拒单** + 审计日志
3. 幂等：已存在 `(channel, external_order_no)` 且已付 → 200 空操作
4. INSERT `shop_orders`（`channel=doudian`，`status=claim_pending` 或 `paid`）
5. INSERT `payments`（若已付）
6. INSERT `entitlements` + `claim_tokens`（待领权）
7. 触发领权短信（A15 配置 · F9 短信额度）

**`order.refund` / `order.refund_success`（退款 R1–R6 · 触达 F2）**：

1. 验签 + 解析 `external_order_no` + `refund_no`（或平台退款单号）
2. 查 `shop_orders` WHERE `(channel, external_order_no)`；不存在 → 404 + 审计
3. 幂等：`refunds` 已存在同 `refund_no` 且 `status=succeeded` → 200 空操作
4. INSERT/UPDATE `refunds`（`channel=doudian`，`status=succeeded`，`raw_notify` 留痕）
5. UPDATE `shop_orders.status=refunded`（或 `partial_refunded` 若部分退）
6. **F2**：`entitlements.status=revoked` + `entitlement_revoked_at` + `enrollments.revoked`；已开票 → `invoice_requests.needs_red_flush=true`
7. 写审计日志；返回 `{ "ok": true, "order_id", "entitlements_revoked": N }`

> 链路 ② `POST /integrations/dy-knowledge/webhook` 的 `event=trade.refund` 处理**同 R1–R6**，仅 `channel=dy_knowledge`。Mx 验收第 7 步（退款关权益）对 ①② 均适用。

**商家 `closed`/`suspended`**"""

    if "**`order.refund` / `order.refund_success`（退款 R1–R6" not in text:
        text = text.replace(webhook_old, webhook_new)

    refund_sample = """**拒单响应**（未过挂载闸 / 商家 blocked）：

```json
{
  "ok": false,
  "reason": "mount_gate_blocked | merchant_status_blocked | unmapped_product",
  "audit_log_id": "uuid"
}
```

#### 8.11.1 Webhook 请求体样例（链路 ① · 抖店）"""

    refund_sample_with = """**拒单响应**（未过挂载闸 / 商家 blocked）：

```json
{
  "ok": false,
  "reason": "mount_gate_blocked | merchant_status_blocked | unmapped_product",
  "audit_log_id": "uuid"
}
```

**退款事件样例**（`order.refund_success`）：

```json
{
  "event": "order.refund_success",
  "external_order_no": "DD202608070001",
  "refund_no": "RF_DD_20260808001",
  "refund_amount_cent": 9900,
  "refunded_at": "2026-08-08T10:00:00+08:00",
  "sign": "…"
}
```

> 处理走 §8.11 **R1–R6** → F2；与私域 `POST /integrations/wechat-pay/refund-notify` 写入字段一致。

#### 8.11.1 Webhook 请求体样例（链路 ① · 抖店）"""

    if '"event": "order.refund_success"' not in text:
        text = text.replace(refund_sample, refund_sample_with)

    dy_refund = """**拒单**：与 §8.11.1 相同 `reason` 枚举；`external_audit_status≠approved` → `mount_gate_blocked`。

### 8.12 买家小程序 API"""

    dy_refund_with = """**拒单**：与 §8.11.1 相同 `reason` 枚举；`external_audit_status≠approved` → `mount_gate_blocked`。

**退款事件**（`event=trade.refund` / `trade.refund_success`）：请求体含 `external_order_no` + `refund_no`；处理同 §8.11 **R1–R6**（`channel=dy_knowledge`）→ **F2**。

### 8.12 买家小程序 API"""

    if "**退款事件**（`event=trade.refund`" not in text:
        text = text.replace(dy_refund, dy_refund_with)

    shop_ctx = """> 前缀 `/mp/shop/*` · 鉴权：买家微信登录 JWT（`shop_buyers`）或领权 token（M14）。  
> 店铺上下文：`shop_id` 来自小程序启动参数 / 扫码 / 领权落地页。"""

    shop_ctx_new = """> 前缀 `/mp/shop/*` · 鉴权：买家微信登录 JWT（`shop_buyers`）或领权 token（M14）。  
> 店铺上下文：`shop_id` 来自小程序启动参数 / 扫码 / 领权落地页。

**`shop_id` 缺失/非法兜底**（I4）：

| 场景 | 行为 |
|------|------|
| 启动参数无 `shop_id` | 返回 `400` + 统一错误页 **M00-E**「请从店铺入口进入」；不展示商品列表 |
| `shop_id` 不存在或 `shop_stores.status=deleted` | `404`「店铺不存在」 |
| `merchant.status≠active` 或 `shop_stores.status=paused` | M02–M04 返回「暂停营业」；M06–M10 已购履约不受影响（校验 entitlement） |
| 领权落地页 | `claim_tokens` 内嵌 `shop_id`，绑定后写入 session 上下文 |"""

    if "**`shop_id` 缺失/非法兜底**" not in text:
        text = text.replace(shop_ctx, shop_ctx_new)

  # buyer identity section - add after buyer section in PRD if there's §3.2
    buyer_section = """### 3.2 买家身份解析（跨端归一 · I1）

买家在**商家 tenant** 维度唯一，禁止 FK 到 CRM `contacts`。Phase 1 归一策略：

| 入口 | 标识 | 落库 |
|------|------|------|
| 私域小程序登录 | 微信 `openid` | `shop_buyers.wx_openid` |
| 公域链路①领权 | 短信 `mobile` | `shop_buyers.mobile`；领权时绑定 openid |
| 公域链路②内付 | `buyer_open_id` | 同 openid 查或建 buyer |

**合并规则**（`UK(tenant_id, mobile)` 为主）：

1. 领权（M14）：按 token 内 `mobile` 查 buyer；存在则绑定 `wx_openid`；不存在则 INSERT buyer + 写 `orders.buyer_id`
2. 小程序登录：按 `openid` 查；若仅有 openid 无 mobile，允许下单但 M04 须补绑手机
3. **禁止**同一 tenant 下 `(mobile, openid)` 指向两条 buyer；冲突时以**先付费/先领权**记录为主，另一条标记 `merged_into_id`（Phase 1 可日志告警 + 人工合并）

数据表见 [04-数据模型.html#b](./04-数据模型.html#b)。

"""

    if "### 3.2 买家身份解析" not in text:
        # insert before ### 3.5 or ### 3.6
        anchor = "### 3.5 抖音公域"
        if anchor in text:
            text = text.replace(anchor, buyer_section + anchor)

    f10_row = "| **F9** | **套餐用量校验与计数** | [F9](./03-数据流.html#f9) |\n"
    f10_new = f10_row + "| **F10** | **清结算批次生成与打款** | [F10](./03-数据流.html#f10) |\n"
    if "**F10**" not in text:
        text = text.replace(f10_row, f10_new)

    settle_api = """| GET | `/admin/shop/settlement-batches/{id}/export` | 同上 | 已打款导出凭证 |

#### 8.14.4 P07 违规稽查"""

    settle_api_new = """| GET | `/admin/shop/settlement-batches/{id}/export` | 同上 | 已打款导出凭证 |

**数据模型**：[04-数据模型.html#settle](./04-数据模型.html#settle) · `shop_settlement_batches` / `shop_settlement_items`。

**批次生成（F10）**：T+1 定时任务聚合前日 `shop_orders`（`status=paid` 且 `settled_at IS NULL`）与同期 `refunds.succeeded`，按 `tenant_id` + `shop_id` 生成 `pending` 批次；退款冲正写入明细负行。运营 P05-B 确认打款后写 `paid_at` + 凭证 URL。

#### 8.14.4 P07 违规稽查"""

    if "**批次生成（F10）**" not in text:
        text = text.replace(settle_api, settle_api_new)

    f6_note = "| 机审 | 敏感词/类目规则 | auto_result=pass|flag|reject；写 compliance_flags |"
    f6_note_new = "| 机审 | 平台敏感词库（可配置 JSON）+ 类目禁售表；**Phase 1 可 stub 为全 flag→人审** | auto_result=pass|flag|reject；写 compliance_flags |"
    if "Phase 1 可 stub 为全 flag" not in text:
        text = text.replace(f6_note, f6_note_new)

    PRD.write_text(text, encoding="utf-8")
    print("patched PRD")


def patch_flows() -> None:
    text = FLOWS.read_text(encoding="utf-8")

    nav_old = '<a href="#f9">F9 用量计数</a>\n</div>'
    nav_new = '<a href="#f9">F9 用量计数</a><a href="#f10">F10 清结算</a>\n</div>'
    if "#f10" not in text:
        text = text.replace(nav_old, nav_new)

    f2_old = '<rect x="180" y="40" width="120" height="40" rx="8" fill="#fbbf24"/><text x="240" y="64" text-anchor="middle" fill="#0f172a" font-weight="700">微信退款</text>'
    f2_new = '<rect x="160" y="20" width="100" height="32" rx="8" fill="#fbbf24"/><text x="210" y="40" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="700">微信退款</text>\n<rect x="160" y="58" width="100" height="32" rx="8" fill="#fbbf24"/><text x="210" y="78" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="700">抖店/课程库</text>'
    if "抖店/课程库" not in text:
        text = text.replace(f2_old, f2_new)
        text = text.replace(
            '<text x="440" y="130" text-anchor="middle" fill="#94a3b8">写：refunds.succeeded + entitlement_revoked_at + entitlements.revoked + enrollments.revoked</text>',
            '<text x="440" y="125" text-anchor="middle" fill="#94a3b8">触发源：微信 refund-notify · 抖店 order.refund · 课程库 trade.refund · 商家 A09/A10 审核</text>\n<text x="440" y="145" text-anchor="middle" fill="#94a3b8">写：refunds.succeeded + entitlement_revoked_at + entitlements.revoked + enrollments.revoked</text>',
        )
        text = text.replace(
            '<text x="440" y="155" text-anchor="middle" fill="#fbbf24">若已开票 → invoice.needs_red_flush=true（人工红冲）</text>',
            '<text x="440" y="168" text-anchor="middle" fill="#fbbf24">若已开票 → invoice.needs_red_flush=true（Phase 1 人工红冲线下）</text>',
        )

    f3_note = '<text x="450" y="160" text-anchor="middle" fill="#94a3b8">链路②：抖音小程序内付+学，可跳过短信</text>'
    f3_note_new = '<text x="450" y="145" text-anchor="middle" fill="#f87171">退款：抖店 order.refund → §8.11 R1–R6 → F2 关权（Mx 第 7 步）</text>\n<text x="450" y="168" text-anchor="middle" fill="#94a3b8">链路②：抖音小程序内付+学，可跳过短信</text>'
    if "抖店 order.refund" not in text:
        text = text.replace(f3_note, f3_note_new)

    f6_sub = '<p class="sub">draft 不可直接 on_sale；rejected 须修改后重新提交审核。</p>'
    f6_sub_new = '<p class="sub">draft 不可直接 on_sale；rejected 须修改后重新提交审核。<b>机审边界</b>：敏感词库来源 = 平台配置 JSON（P09 维护）；Phase 1 可实现为 stub（全 flag）→ 一律走人审，不阻塞验收。</p>'
    if "机审边界" not in text:
        text = text.replace(f6_sub, f6_sub_new)

    f10_block = """
<div class="block" id="f10">
<h2>F10 清结算批次生成与打款（P05）</h2>
<p class="sub">平台向商家结算已成交订单款（扣除平台服务费/类目费率）。与微信/抖店分账可并行；P05 为<strong>平台侧对账打款</strong>台账。表见 <a href="04-数据模型.html#settle">04 §settlement</a> · API §8.14.3。</p>
<table>
<tr><th>步骤</th><th>读</th><th>写</th></tr>
<tr><td>1. T+1 聚合</td><td>前日 <code>shop_orders.status=paid</code> 且 <code>settled_at IS NULL</code>；同期 <code>refunds.succeeded</code></td><td>INSERT <code>shop_settlement_batches</code>（status=pending）+ <code>shop_settlement_items</code> 明细行</td></tr>
<tr><td>2. 计费</td><td>类目费率 <code>category_fee_rules</code>；订单 <code>amount</code></td><td>明细：gross_amount · platform_fee · net_amount（商家应结）</td></tr>
<tr><td>3. 退款冲正</td><td>批次周期内退款成功的订单</td><td>明细负行 <code>item_type=refund_reversal</code>；冲减 net_amount</td></tr>
<tr><td>4. 运营确认</td><td>batch.status=pending；净额 &gt; 0</td><td>P05-B confirm → status=paid；写 paid_at · transfer_voucher_url</td></tr>
<tr><td>5. 打款失败</td><td>银行/对公退回</td><td>status=failed；P05-C 重试</td></tr>
<tr><td>6. 关账</td><td>批次 paid</td><td>回写订单 <code>settled_at</code>；明细 order_id 标记已结算</td></tr>
</table>
<p class="sub">Phase 1：<strong>批次自动生成 + 人工确认打款</strong>；不对接银行自动划付。与套餐 B2B 续费资金流（§2.4.3 线下对公）无关。</p>
</div>
"""

    if 'id="f10"' not in text:
        text = text.replace("</div></body></html>", f10_block + "\n</div></body></html>")

    FLOWS.write_text(text, encoding="utf-8")
    print("patched 03-数据流.html")


def patch_model() -> None:
    text = MODEL.read_text(encoding="utf-8")

    nav_old = '<a href="#i">invoice</a><a href="#ch">channel</a>'
    nav_new = '<a href="#i">invoice</a><a href="#settle">settlement</a><a href="#ch">channel</a>'
    if "#settle" not in text:
        text = text.replace(nav_old, nav_new)

    buyer_old = """<div class="block" id="b"><h2><code>shop_buyers</code></h2>
<table>
<tr><th>字段</th><th>约束</th></tr>
<tr><td>mobile</td><td><span class="uk">UK(tenant_id, mobile)</span></td></tr>
<tr><td>wx_openid</td><td>部分唯一</td></tr>
<tr><td>status</td><td>active|blocked</td></tr>
</table>
<p class="sub">买家在<strong>商家（tenant）</strong>维度统一：<span class="uk">UK(tenant_id, mobile)</span>；跨店购买时 <code>shop_orders.shop_id</code> 区分来源店铺。禁止 FK 到 contacts</p></div>"""

    buyer_new = """<div class="block" id="b"><h2><code>shop_buyers</code>（买家身份 · 跨端归一）</h2>
<table>
<tr><th>字段</th><th>类型</th><th>约束</th><th>说明</th></tr>
<tr><td><span class="pk">id</span></td><td>UUID</td><td>PK</td><td></td></tr>
<tr><td><span class="fk">tenant_id</span></td><td>UUID</td><td>FK IDX</td><td>商家维度隔离</td></tr>
<tr><td>mobile</td><td>VARCHAR(11)</td><td><span class="uk">UK(tenant_id, mobile)</span> 可空</td><td>公域领权 / 绑手机；<strong>归一主键</strong></td></tr>
<tr><td>wx_openid</td><td>VARCHAR(64)</td><td><span class="uk">UK(tenant_id, wx_openid)</span> 可空</td><td>私域小程序登录</td></tr>
<tr><td>dy_open_id</td><td>VARCHAR(64)</td><td>可空</td><td>链路②课程库 open_id；登录后合并到 wx_openid 或 mobile</td></tr>
<tr><td>merged_into_id</td><td>UUID</td><td>FK 可空</td><td>重复 buyer 人工合并指向；Phase 1 仅日志告警</td></tr>
<tr><td>status</td><td>VARCHAR(20)</td><td></td><td>active|blocked</td></tr>
<tr><td>first_purchase_at</td><td>TIMESTAMPTZ</td><td>可空</td><td>首单时间（CRM 事件用，不建 Contact）</td></tr>
<tr><td>created_at / updated_at</td><td>TIMESTAMPTZ</td><td></td><td></td></tr>
</table>
<p class="sub">买家在<strong>商家（tenant）</strong>维度统一；跨店购买用 <code>shop_orders.shop_id</code> 区分来源。<strong>归一策略</strong>：领权按 mobile 查/建 → 绑定 openid；小程序登录按 openid 查/建 → M04 补 mobile。禁止 FK 到 <code>contacts</code>。详见 PRD <a href="PRD-内容获客商城-phase1.md#32-买家身份解析跨端归一--i1">§3.2</a>。</p></div>"""

    if "merged_into_id" not in text:
        text = text.replace(buyer_old, buyer_new)

    settle_block = """
<div class="block" id="settle"><h2><code>shop_settlement_batches</code> / <code>shop_settlement_items</code>（清结算 · P05）</h2>
<p class="sub">平台→商家结算台账。生成逻辑见 <a href="03-数据流.html#f10">F10</a> · API §8.14.3 · UI <a href="06-平台端UI.html#p05">P05</a>。</p>
<h3 style="font-size:14px;margin:14px 0 6px"><code>shop_settlement_batches</code></h3>
<table>
<tr><th>字段</th><th>类型</th><th>说明</th></tr>
<tr><td><span class="pk">id</span></td><td>UUID</td><td>批次主键</td></tr>
<tr><td><span class="fk">tenant_id</span></td><td>UUID</td><td>商家</td></tr>
<tr><td><span class="fk">shop_id</span></td><td>UUID</td><td>店铺（单店批次；多店商家可拆批）</td></tr>
<tr><td>batch_no</td><td>VARCHAR(32)</td><td><span class="uk">UK</span> 业务批次号</td></tr>
<tr><td>period_start / period_end</td><td>DATE</td><td>结算周期（通常 T+1 聚合前一日）</td></tr>
<tr><td>gross_amount_cents</td><td>BIGINT</td><td>订单毛收入合计</td></tr>
<tr><td>platform_fee_cents</td><td>BIGINT</td><td>平台服务费/类目抽成</td></tr>
<tr><td>refund_reversal_cents</td><td>BIGINT</td><td>退款冲正（负向合计的绝对值）</td></tr>
<tr><td>net_amount_cents</td><td>BIGINT</td><td>应结净额 = gross - fee - reversal</td></tr>
<tr><td>status</td><td>VARCHAR(20)</td><td>pending|paid|failed</td></tr>
<tr><td>paid_at</td><td>TIMESTAMPTZ</td><td>确认打款时间</td></tr>
<tr><td>transfer_voucher_url</td><td>TEXT</td><td>打款凭证（P05-B 上传）</td></tr>
<tr><td>operator_id</td><td>UUID</td><td>确认打款运营</td></tr>
<tr><td>fail_reason</td><td>TEXT</td><td>打款失败原因</td></tr>
<tr><td>created_at / updated_at</td><td>TIMESTAMPTZ</td><td></td></tr>
</table>
<h3 style="font-size:14px;margin:14px 0 6px"><code>shop_settlement_items</code></h3>
<table>
<tr><th>字段</th><th>类型</th><th>说明</th></tr>
<tr><td><span class="pk">id</span></td><td>UUID</td><td></td></tr>
<tr><td><span class="fk">batch_id</span></td><td>UUID</td><td>→ batches</td></tr>
<tr><td>item_type</td><td>VARCHAR(20)</td><td>order_income|refund_reversal|adjustment</td></tr>
<tr><td><span class="fk">order_id</span></td><td>UUID</td><td>可空（调整行）</td></tr>
<tr><td><span class="fk">refund_id</span></td><td>UUID</td><td>冲正行关联退款</td></tr>
<tr><td>amount_cents</td><td>BIGINT</td><td>正=收入；负=冲正</td></tr>
<tr><td>fee_cents</td><td>BIGINT</td><td>该行分摊服务费</td></tr>
<tr><td>note</td><td>TEXT</td><td>备注</td></tr>
</table>
<p class="sub"><code>shop_orders.settled_at</code>：批次确认 paid 后回写，防重复入批。退款在批次生成后发生 → 进入<strong>下一周期</strong>冲正明细。</p></div>
"""

    if 'id="settle"' not in text:
        text = text.replace('<div class="block" id="ch">', settle_block + '\n<div class="block" id="ch">')

    orders_note = '<tr><td>client_token</td><td>防重复下单</td></tr>'
    orders_note_new = orders_note + '\n<tr><td>settled_at</td><td>TIMESTAMPTZ 可空；F10 批次 paid 后回写</td></tr>'
    if "settled_at" not in text:
        text = text.replace(orders_note, orders_note_new)

    MODEL.write_text(text, encoding="utf-8")
    print("patched 04-数据模型.html")


def patch_index() -> None:
    text = INDEX.read_text(encoding="utf-8")
    text = text.replace(
        "支付开权、退款关权等 <strong>11 条</strong>数据流",
        "支付开权、退款关权等 <strong>12 条</strong>数据流",
    )
    text = text.replace(
        '<div class="stat-card"><div class="stat-card__value">11</div><div class="stat-card__label">核心数据流</div></div>',
        '<div class="stat-card"><div class="stat-card__value">12</div><div class="stat-card__label">核心数据流</div></div>',
    )
  # also add F10 to flow list if present
    if "F9 用量" in text and "F10" not in text:
        text = text.replace("F8 套餐、<strong>F9 用量</strong>", "F8 套餐、<strong>F9 用量</strong>、<strong>F10 清结算</strong>")
    INDEX.write_text(text, encoding="utf-8")
    print("patched index.html")


if __name__ == "__main__":
    patch_prd()
    patch_flows()
    patch_model()
    patch_index()
