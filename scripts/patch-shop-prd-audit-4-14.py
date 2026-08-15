#!/usr/bin/env python3
"""Patch PRD/docs for audit items 4-14 (remaining gaps)."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/01-PRD/21-内容获客商城-phase1"
PRD = BASE / "PRD-内容获客商城-phase1.md"
FLOWS = BASE / "03-数据流.html"
MODEL = BASE / "04-数据模型.html"
BUYER = BASE / "02-买家端UI.html"


def patch_prd() -> None:
    text = PRD.read_text(encoding="utf-8")

    # --- #5 + #4: refund business rules + partial refund (after §四 or in §8.9) ---
    refund_section = """
### 4.1 退款业务规则与状态机（Phase 1）

> 技术关权见 [F2](./03-数据流.html#f2) · API §8.9 · 公域 §8.11 R1–R6。

#### 4.1.1 退款政策配置（#5）

Phase 1 **商家可配置 + 平台默认兜底**（非仅技术流程）：

| 配置项 | 配置位置 | Phase 1 规则 |
|--------|----------|--------------|
| 默认退款策略 | **A19** `default_refund_policy` | 新商品继承；枚举见下 |
| 单品覆盖 | **A03** `refund_policy` | 可逐商品覆盖 A19 默认 |
| 退款窗口 | **Phase 1 固定** | 下单后至履约完成前（由策略枚举隐含）；**无「N 天内可退」天数配置**（Phase 2） |
| 发起方 | 业务规则 | 见下表「谁可发起」 |
| 审核 | 业务规则 | `manual_only` 须商家 A09/A10 审核；其余按策略自动或买家自助 |
| 已学课时影响 | **Phase 1 固定** | `before_fulfill`：任一课时 `progress>0` 或资料已下载 → **禁止自助退**，须商家人工审核 |

**`refund_policy` 枚举（A03 / A19 / 04 §通用）**：

| 值 | 买家自助（M12-A） | 商家发起（A09/A10） | 说明 |
|----|-------------------|---------------------|------|
| `always_allow` | ✓ 付款后至 revoked 前 | ✓ | 课程类常用；仍校验未开票或已标 `needs_red_flush` |
| `before_fulfill` | ✓ 仅**零履约**（无进度/未下载/未核销） | ✓ | 有学习/下载/核销记录 → 买家端禁用，商家可人工退 |
| `manual_only` | ✗ | ✓ | 买家端不展示「申请退款」 |

**谁可发起**：

| 发起方 | 入口 | 权限/条件 |
|--------|------|-----------|
| 买家 | M12-A · M12 详情 | 策略允许 + 订单 `paid` + 无进行中退款 |
| 商家 | A09-B · A10-A | `shop.order.refund` + 策略允许 |
| 平台 | — | Phase 1 无平台代退入口 |
| 公域平台 | Webhook `order.refund` | 验签通过；走 §8.11 R1–R6 |

**退款理由**：`reason_code` 枚举 `buyer_request` / `quality_issue` / `duplicate` / `other`；商家发起 `remark` ≥4 字。Phase 1 **不强制平台审核工单**，商家 `manual_only` 即视为人工审核。

#### 4.1.2 部分退款（#4）

**Phase 1 默认：单笔订单单 `order_item` → 仅支持全额退款关权。** `partial_refunded` 为公域/多明细预留态。

| 订单态 | 触发条件 | 金额校验 | 权益处理 |
|--------|----------|----------|----------|
| `refunded` | `refund_amount_cents = order.paid_amount_cents` | 必须相等（私域 M12/A09） | **F2 全额**：`entitlements.status=revoked` · `enrollments.revoked` |
| `partial_refunded` | 外部 Webhook 推送 `refund_amount < paid` | 0 < amount ≤ 已付未退余额 | 见下 |
| `refunding` | 已调微信/抖店退款 API，待回调 | — | 权益仍 `active`，回调成功后转上 |

**`partial_refunded` 权益规则（Phase 1 边界）**：

1. **单 item 订单**（Phase 1 常态）：外部部分退金额仍 **整单关权**（`revoked`），差额记 `refunds` 留痕；避免「半权益」履约歧义。
2. **多 item 订单**（Phase 2）：按 `order_item_id` 粒度部分 `revoked`；未退 item 保持 `active`。
3. 私域小程序 **M12-A / 商家 A09**：`422`「Phase 1 仅支持全额退款」若 `amount_cents < paid`。

**状态机**：

```
paid → refunding → refunded | partial_refunded
paid → refunded（同步成功场景少见）
refunding + 回调失败 → paid（可重试）
```

已开票：任一退款成功前检查 `invoice_requests.status=issued` → 允许退但写 `needs_red_flush=true`（Phase 1 人工红冲）。

"""

    if "### 4.1 退款业务规则" not in text:
        # insert before ## 五、核心数据流
        text = text.replace(
            "\n## 五、核心数据流\n",
            refund_section + "\n## 五、核心数据流\n",
        )

    # Fix §8.11 R5 to align with 4.1.2
    text = text.replace(
        "5. UPDATE `shop_orders.status=refunded`（或 `partial_refunded` 若部分退）",
        "5. UPDATE `shop_orders.status=refunded`（全额）或 `partial_refunded`（外部部分退且 §4.1.2 规则；单 item 仍关权）",
    )

    # --- #11: content off-sale / entitlement ---
    content_section = """
### 3.3 商品下架与已购权益（#11）

**硬规则（Phase 1）**：

| 事件 | 新买家 | 已购买家（entitlement `active`） |
|------|--------|----------------------------------|
| 商品 `off_sale` / 下架 | M02 不展示或灰显不可购 | **不受影响**：M06–M10 照常履约 |
| 商品 `rejected` / 未上架 | 不可购 | 已购保留（购买时快照已开权） |
| 商家 `suspended` / 店铺 `paused` | M02–M04 拦截 | 已购不阻断（§2.4.4） |
| 商家 `closed` 清退 | 不可新购 | 已购不阻断 |
| 平台 P07/P09 强制下架 | 不可新购 + listing blocked | **已购保留**；新 Webhook 拒单 |

**内容版本策略**：

| 内容类型 | 已购买家看到 | 商家改内容后 |
|----------|--------------|--------------|
| 课程课时 | 购买时 `column_id` 下**当前已发布课时列表** | **跟最新发布**：新课时自动可见；删除/下架课时已学进度保留只读 |
| 数字资料 | `digital_package` 当前 assets 列表 | 跟最新（新增文件可见）；删除文件已下载记录保留 |
| 服务 | `service_offer` 当前配置 | 跟最新时段/次数规则；已预约不受影响 |

**快照**：`order_items.title_snapshot` / `product_snapshot` 仅用于订单展示与审计，**不锁定**履约内容版本（与知识付费行业惯例一致）。Phase 2 可选「购买时内容快照」加购包。

"""
    if "### 3.3 商品下架与已购权益" not in text:
        text = text.replace(
            "### 3.5 抖音公域 Mx 验收",
            content_section + "### 3.5 抖音公域 Mx 验收",
        )

    # --- #14: multi-store buyer ---
    multistore = """
#### 3.2.1 多店场景买家体验（#14）

买家主体 **tenant 级唯一**（`UK(tenant_id, mobile)`），订单/权益带 `shop_id` 区分来源店：

| 能力 | Phase 1 行为 |
|------|--------------|
| 购物车 | **无跨店购物车**；每次下单绑定当前 `shop_id` 上下文 |
| M06 已购 | **tenant 级汇总**：展示该商家下所有店的已购，卡片标注来源店名 |
| M11 订单 | **tenant 级汇总**；筛选 Chip 可按 `shop_id` 过滤 |
| 重复购买同一商品 | 不同店若上架相同 `product_id`（不同 shop）视为不同 SKU；同店重复购买走 entitlement 去重 |
| 切换店铺 | 小程序须从**目标店入口**（二维码/链接）进入；session 内 `shop_id` 切换 → 重新 `GET /mp/shop/store` |

商家 A11 买家列表为 **tenant 跨店汇总**；详情 Tab 订单可按 `shop_id` 筛选。

"""
    if "#### 3.2.1 多店场景" not in text:
        text = text.replace(
            "数据表见 [04-数据模型.html#b](./04-数据模型.html#b)。\n\n### 3.3 商品下架",
            "数据表见 [04-数据模型.html#b](./04-数据模型.html#b)。\n" + multistore + "\n### 3.3 商品下架",
        )

    # --- #6: PII appendix ---
    pii_appendix = """
## 十二、数据安全与 PII 治理附录（#6）

> Phase 1 最小可行；生产须与运维 `.env` / KMS 策略一致。

### 12.1 PII 字段清单

| 数据类 | 表/字段 | 敏感级 |
|--------|---------|--------|
| 买家手机 | `shop_buyers.mobile` | 高 |
| 买家微信 | `shop_buyers.wx_openid` | 中 |
| 入驻身份证 | `shop_onboarding_applications.id_no` | 高 |
| 经营联系人 | `contact_mobile` | 高 |
| 支付密钥 | `shop_tenant_settings.wx_*` 密文 | 极高 |

### 12.2 存储与加密

| 项 | Phase 1 方案 |
|----|--------------|
| 库内敏感字段 | **应用层 AES-256-GCM** 加密列（`encrypted_*` 或 JSONB 信封）；密钥来自环境变量 `SHOP_PII_KEY`（运维注入，不入库） |
| 支付/API 密钥 | 同 A15；`wx_api_v3_key` 等 **加密存储**，界面脱敏展示 |
| 日志 | 禁止打印明文手机/证号；结构化日志用 `masked` |
| 备份 | 跟随库备份；恢复须同密钥 |

### 12.3 展示脱敏

| 场景 | 规则 |
|------|------|
| 买家手机（商家 A11） | 中间四位 `138****8000` |
| 入驻 `contact_mobile` / `id_no`（P02/P03） | 默认脱敏；👁 `reveal-sensitive` + 审计 |
| API 列表/详情 | **永不**返回明文（除非揭露接口） |

### 12.4 保留与删除

| 数据 | 保留期 | 删除/anonymize |
|------|--------|----------------|
| 订单/支付 | ≥5 年（财务） | 不可物理删；可 anonymize 买家 PII 列 |
| 入驻申请 | 审出后 ≥3 年 | 清退商家可申请 anonymize 联系人（运营审批） |
| `shop_buyers` | 最后活跃 + 2 年无订单 | Phase 2 自动 anonymize 任务 |
| 审计日志 | ≥1 年 | 只追加，不删 |

**买家「注销」**：Phase 1 无 C 端注销入口；商家可 `blocked` 买家。Phase 2 补 `DELETE /mp/shop/me` 软删 + anonymize。

"""
    if "## 十二、数据安全与 PII" not in text:
        text = text.replace(
            "## 十一、关联文档\n",
            pii_appendix + "\n## 十一、关联文档\n",
        )
        text = text.replace(
            "- [README](./README.md)",
            "- [§十二 数据安全与 PII](./PRD-内容获客商城-phase1.md#十二数据安全与-pii-治理附录6)\n- [README](./README.md)",
        )

    # --- #7: webhook signature ---
    webhook_sig = """
#### 8.11.3 Webhook 验签规范（#7 · Mx 前必固定）

所有 `/integrations/*` 回调 **无 JWT**，统一中间件验签 + 防重放：

| 来源 | 算法 | 密钥 | 时间窗 |
|------|------|------|--------|
| 微信支付 | 平台证书 + `Wechatpay-Signature`（RSA-SHA256） | 微信商户平台证书 | 无 timestamp 窗（以 notify_id 幂等为准） |
| 微信退款 | 同上 `refund-notify` | 同上 | 同上 |
| 抖店 `doudian` | **HMAC-SHA256**（按抖店开放平台文档：`app_secret` + 排序参数拼接） | P06 `channel_config.doudian.app_secret` | `timestamp` 与服务器差 ≤ **300s** |
| 课程库 `dy-knowledge` | HMAC-SHA256 或平台指定（配置项 `sign_algo`） | P06 `dy_knowledge.app_secret` | ≤ **300s** |

**通用防重放**：

1. 验签失败 → `401` + 审计，**不**写业务表
2. `timestamp` 超窗 → `401` `replay_rejected`
3. 业务幂等：`notify_id` / `(channel, external_order_no)` / `refund_no` UK
4. 密钥轮换：P06 支持双 `app_secret` 并行 24h；旧密钥验签通过后告警升级

**实现落点**：`apps/api/app/integrations/` 独立验签模块；Mx 验收须附验签单测（正签/篡改/过期 timestamp）。

"""
    if "#### 8.11.3 Webhook 验签规范" not in text:
        text = text.replace(
            "**退款事件**（`event=trade.refund`",
            webhook_sig + "\n**退款事件**（`event=trade.refund`",
        )

    # Cross-ref in A15 for encryption
    a15_note = "**证书/API 密钥**：加密存储见 [§十二 PII 治理](./PRD-内容获客商城-phase1.md#十二数据安全与-pii-治理附录6)。"
    if "加密存储见 [§十二" not in text and "wx_mch_id" in text:
        # find A15 section mention - skip if complex
        pass

    PRD.write_text(text, encoding="utf-8")
    print("PRD patched (#4-7, #11, #14)")


def patch_flows() -> None:
    text = FLOWS.read_text(encoding="utf-8")

    f2_note = """</div>
</div>

<p class="sub"><b>部分退款</b>（§4.1.2）：Phase 1 私域仅全额；公域 <code>partial_refunded</code> 单 item 订单仍整单 <code>revoked</code>。多 item 部分退 Phase 2。</p>"""

    if "部分退款</b>（§4.1.2）" not in text:
        text = text.replace(
            '<text x="440" y="168" text-anchor="middle" fill="#fbbf24">若已开票 → invoice.needs_red_flush=true（Phase 1 人工红冲线下）</text>\n</svg>\n</div>\n</div>\n\n<div class="block" id="f3">',
            '<text x="440" y="168" text-anchor="middle" fill="#fbbf24">若已开票 → invoice.needs_red_flush=true（Phase 1 人工红冲线下）</text>\n</svg>\n</div>\n'
            + '<p class="sub"><b>部分退款</b>（§4.1.2）：Phase 1 私域仅全额；公域 <code>partial_refunded</code> 单 item 订单仍整单 <code>revoked</code>。多 item 部分退 Phase 2。</p>\n</div>\n\n<div class="block" id="f3">',
        )

    f9_note = '<p class="sub">加购包到期仅 merged_limit 下降，已用次数不回溯。换档 replace 立即按新合并结果生效。</p>'
    f9_new = f9_note + '\n<p class="sub"><b>并发控制</b>（#12）：<code>UPDATE shop_merchant_feature_usage SET used_count = used_count + 1 WHERE … AND used_count &lt; merged_limit</code>（单行原子递增）；失败重试 1 次；仍失败 403。高并发配额（<code>max_products</code>）用 <code>SELECT COUNT(*) … FOR UPDATE</code> 或乐观锁 <code>version</code> 列。详见 04 <a href="04-数据模型.html#usage-concurrency">§用量并发</a>。</p>'
    if "并发控制" not in text:
        text = text.replace(f9_note, f9_new)

    FLOWS.write_text(text, encoding="utf-8")
    print("flows patched")


def patch_model() -> None:
    text = MODEL.read_text(encoding="utf-8")

    usage_block = """<p class="sub">用量上限取自<strong>合并后</strong>的 <code>usage_limits</code>，不是单条订阅。计数仍按 tenant 维度一条 <code>used_count</code>（多套餐共享同一计数池）。</p>

<h3 id="usage-concurrency" style="font-size:14px;margin:12px 0 6px">用量并发控制（#12）</h3>
<table>
<tr><th>场景</th><th>策略</th></tr>
<tr><td><code>shop_merchant_feature_usage</code> 周期次数 +1</td><td>单 SQL 原子 <code>UPDATE … SET used_count=used_count+1 WHERE used_count &lt; limit</code>；uk 冲突则 INSERT</td></tr>
<tr><td>提审/短信等 F9 预检</td><td>先 merge 算 limit，再原子占用；业务失败补偿 -1</td></tr>
<tr><td><code>max_products</code> / <code>max_stores</code> 存量配额</td><td>事务内 <code>COUNT(*)</code> + 插入；或 <code>shop_stores.version</code> 乐观锁</td></tr>
<tr><td>预约 <code>booked_count</code></td><td>条件更新 <code>WHERE booked_count &lt; capacity</code>（F4 已有）</td></tr>
</table>"""

    old = '<p class="sub">用量上限取自<strong>合并后</strong>的 <code>usage_limits</code>，不是单条订阅。计数仍按 tenant 维度一条 <code>used_count</code>（多套餐共享同一计数池）。</p>\n\n<h3 style="font-size:14px;margin:12px 0 6px"><code>shop_subscription_plans</code>'
    if "usage-concurrency" not in text:
        text = text.replace(old, usage_block + '\n\n<h3 style="font-size:14px;margin:12px 0 6px"><code>shop_subscription_plans</code>')

    buyer_pii = """<tr><td>mobile</td><td>VARCHAR(11)</td><td><span class="uk">UK(tenant_id, mobile)</span> 可空</td><td>公域领权 / 绑手机；<strong>归一主键</strong>；库内可加密列 <code>mobile_enc</code></td></tr>"""
    if "mobile_enc" not in text:
        text = text.replace(
            "<tr><td>mobile</td><td>VARCHAR(11)</td><td><span class=\"uk\">UK(tenant_id, mobile)</span> 可空</td><td>公域领权 / 绑手机；<strong>归一主键</strong></td></tr>",
            buyer_pii,
        )

    refunds_row = "<tr><td>refunds</td><td>refund_no UK；status；entitlement_revoked_at（验收字段）</td></tr>"
    refunds_new = "<tr><td>refunds</td><td>refund_no UK；<code>amount_cents</code>；<code>status</code> processing|succeeded|failed；<code>is_partial</code>；entitlement_revoked_at</td></tr>"
    if "is_partial" not in text:
        text = text.replace(refunds_row, refunds_new)

    orders_status = "<tr><td>status / pay_status</td><td>pending_pay→paid→…；refunded</td></tr>"
    orders_new = "<tr><td>status / pay_status</td><td>pending_pay→paid→refunding→<b>refunded</b>|<b>partial_refunded</b>（§4.1.2）</td></tr>"
    if "partial_refunded" not in text:
        text = text.replace(orders_status, orders_new)

    MODEL.write_text(text, encoding="utf-8")
    print("model patched")


def patch_buyer_m00e() -> None:
    text = BUYER.read_text(encoding="utf-8")
    if 'id="m00e"' in text:
        print("M00-E already exists")
        return
    m00_close = '</article><article class="pdoc-panel" id="m01">'
    m00e = """</article><article class="pdoc-panel" id="m00e">
<div class="doc">
  <h2>M00-E · 店铺入口错误 <span class="tag tag-b">兜底</span></h2>
  <p class="sub">鉴权：无 <code>shop_id</code> 或非法时统一落点（§8.12 I4）。</p>
  <div class="phone" style="margin:12px auto">
    <div class="phone-notch"></div>
    <div class="ps" style="min-height:360px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center">
      <div style="font-size:40px;margin-bottom:12px">🏪</div>
      <div style="font-weight:800;font-size:16px;margin-bottom:8px">请从店铺入口进入</div>
      <div style="font-size:12px;color:#666;line-height:1.6">缺少店铺参数或链接已失效<br>请通过商家分享的二维码 / 小程序码重新打开</div>
    </div>
  </div>
  <table class="meta matrix" style="margin-top:12px">
    <tr><th>场景</th><th>HTTP</th><th>文案</th></tr>
    <tr><td>无 shop_id</td><td>400</td><td>请从店铺入口进入</td></tr>
    <tr><td>shop 不存在</td><td>404</td><td>店铺不存在</td></tr>
    <tr><td>暂停营业</td><td>403</td><td>店铺暂停营业（已购见 M06）</td></tr>
  </table>
</div>
</article><article class="pdoc-panel" id="m01">"""
    if m00_close in text:
        text = text.replace(m00_close, m00e)
        BUYER.write_text(text, encoding="utf-8")
        print("M00-E added")


if __name__ == "__main__":
    patch_prd()
    patch_flows()
    patch_model()
    patch_buyer_m00e()
