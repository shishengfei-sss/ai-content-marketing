#!/usr/bin/env python3
"""Apply S1-S5 suggestions from 21-PRD-Phase1-业务与数据闭环分析.md."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/01-PRD/21-内容获客商城-phase1"
PRD = BASE / "PRD-内容获客商城-phase1.md"
FLOWS = BASE / "03-数据流.html"
ADMIN = BASE / "01-管理端UI.html"
INDEX = BASE / "index.html"
P08_SNIPPET = BASE / "06-平台端UI.html"


def patch_flows_s1() -> None:
    text = FLOWS.read_text(encoding="utf-8")
    nav_old = '<a href="#f10">F10 清结算</a>\n</div>'
    nav_new = '<a href="#f10">F10 清结算</a><a href="#f11">F11 IP演示</a>\n</div>'
    if "#f11" not in text:
        text = text.replace(nav_old, nav_new)

    f11 = """
<div class="block" id="f11">
<h2>F11 · IP 获客演示编排（P1-16 · 非 Mx 硬验收）</h2>
<p class="sub">将创作内容、公域挂载与成交串成<strong>可演示脚本</strong>；复用既有子流，不新增表。权威步骤见 <a href="index.html#p1-16-demo">index §P1-16</a> · PRD §9.3。</p>
<div class="canvas">
<svg viewBox="0 0 920 200" xmlns="http://www.w3.org/2000/svg" font-size="12" font-family="sans-serif">
<defs><marker id="f11m" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#94a3b8"/></marker></defs>
<rect x="10" y="30" width="100" height="40" rx="8" fill="#a78bfa"/><text x="60" y="54" text-anchor="middle" fill="#fff" font-weight="700">内容/CTA</text>
<rect x="130" y="30" width="100" height="40" rx="8" fill="#34d399"/><text x="180" y="54" text-anchor="middle" fill="#0f172a" font-weight="700">A03 建品</text>
<rect x="250" y="30" width="90" height="40" rx="8" fill="#fbbf24"/><text x="295" y="54" text-anchor="middle" fill="#0f172a" font-weight="700">F6+P09</text>
<rect x="360" y="30" width="90" height="40" rx="8" fill="#818cf8"/><text x="405" y="54" text-anchor="middle" fill="#fff" font-weight="700">A14+F7</text>
<rect x="470" y="30" width="100" height="40" rx="8" fill="#38bdf8"/><text x="520" y="54" text-anchor="middle" fill="#0f172a" font-weight="700">挂载曝光</text>
<rect x="590" y="30" width="100" height="40" rx="8" fill="#34d399"/><text x="640" y="54" text-anchor="middle" fill="#0f172a" font-weight="700">下单支付</text>
<rect x="710" y="30" width="100" height="40" rx="8" fill="#818cf8"/><text x="760" y="54" text-anchor="middle" fill="#fff" font-weight="700">履约</text>
<rect x="820" y="30" width="80" height="40" rx="8" fill="#7f1d1d"/><text x="860" y="54" text-anchor="middle" fill="#fecaca" font-weight="700">可选退款</text>
<path d="M110,50 H130" stroke="#94a3b8" marker-end="url(#f11m)"/>
<path d="M230,50 H250" stroke="#94a3b8" marker-end="url(#f11m)"/>
<path d="M340,50 H360" stroke="#94a3b8" marker-end="url(#f11m)"/>
<path d="M450,50 H470" stroke="#94a3b8" marker-end="url(#f11m)"/>
<path d="M570,50 H590" stroke="#94a3b8" marker-end="url(#f11m)"/>
<path d="M690,50 H710" stroke="#94a3b8" marker-end="url(#f11m)"/>
<path d="M810,50 H820" stroke="#94a3b8" marker-end="url(#f11m)"/>
<text x="460" y="110" text-anchor="middle" fill="#cbd5e1">私域演示：步骤 4–5 走 F1（M04 微信付）· 公域演示：步骤 6 走 F3 领权 或 F3b 内付</text>
<text x="460" y="135" text-anchor="middle" fill="#86efac">创作顾问素材 → 手工粘贴 A03 详情（自动导入 Phase 2 · 见 A03 灰显按钮）</text>
<text x="460" y="165" text-anchor="middle" fill="#94a3b8">编排流不计入 Mx 硬验收；Mx 仍只验 §3.5 选定的一条公域链路</text>
</svg>
</div>
<table>
<tr><th>步骤</th><th>子流</th><th>验收点</th></tr>
<tr><td>1 内容带 CTA</td><td>创作顾问导出（可选）</td><td>落地页/短视频描述含店铺入口</td></tr>
<tr><td>2 建品上架</td><td><a href="#f6">F6</a> + P09</td><td><code>products.status=on_sale</code></td></tr>
<tr><td>3 公域映射</td><td><a href="#f7">F7</a> + A14</td><td><code>listing_status=mapped</code></td></tr>
<tr><td>4 成交</td><td><a href="#f1">F1</a> 或 <a href="#f3">F3</a>/<a href="#f3b">F3b</a></td><td><code>orders.paid</code> + entitlement active</td></tr>
<tr><td>5 履约</td><td>M06–M10</td><td>学课/领取/核销任一条通</td></tr>
<tr><td>6（可选）</td><td><a href="#f2">F2</a></td><td>演示退款关权</td></tr>
</table>
</div>
"""
    if 'id="f11"' not in text:
        text = text.replace("</div></body></html>", f11 + "\n</div></body></html>")
    FLOWS.write_text(text, encoding="utf-8")
    print("S1: F11 added")


def patch_prd() -> None:
    text = PRD.read_text(encoding="utf-8")

    f11_row = "| **F10** | **清结算批次生成与打款** | [F10](./03-数据流.html#f10) |\n"
    f11_new = f11_row + "| **F11** | **IP 获客演示编排（P1-16）** | [F11](./03-数据流.html#f11)（编排流，非交易主干） |\n"
    if "**F11**" not in text:
        text = text.replace(f11_row, f11_new)

    s3_block = """
**暂停/恢复期间订单积压（S3）**：

| 场景 | Phase 1 做法 |
|------|----------------|
| 暂停中买家下单 | M02–M04 拦截「暂停营业」；原则上无新单 |
| 暂停前已付款待处理 | 订单状态不变；商家不可登录，**积压自然累积** |
| 恢复后提醒 | 商家首次登录 A01 展示**黄色横幅**：「店铺已恢复，您有 N 笔订单待处理」；N = `pending_fulfill` + `refund` 相关待办 |
| 批量处理 | [A09](./01-管理端UI.html#a09) 快捷 Tab「待发货/待处理」+ 高级筛选 `created_during=suspended`（可选）；支持导出 CSV（≤5000 条，同列表导出权限） |
| 平台侧 | P02 恢复后不在平台代操作订单；管家可在 P02-B 服务记录写跟进提醒商家 |

"""
    if "**暂停/恢复期间订单积压（S3）**" not in text:
        text = text.replace(
            "与 **A17-B 单店暂停** 区别：商家暂停 = 全 tenant 关店 + 禁登 + 平台订阅写全禁。与 **closed 清退** 区别：暂停可恢复，订阅倒计时继续。\n\n**API**：",
            "与 **A17-B 单店暂停** 区别：商家暂停 = 全 tenant 关店 + 禁登 + 平台订阅写全禁。与 **closed 清退** 区别：暂停可恢复，订阅倒计时继续。\n"
            + s3_block
            + "**API**：",
        )

    cs_expand = """线框见 [P02](./06-平台端UI.html#p02) · [P08](./06-平台端UI.html#p08) · 权限见 [05-角色权限#platform](./05-角色权限.html#platform)。

**Phase 1 无独立「管家工作台」页（S4）**：`platform_shop_cs` 的全部操作落在 **P02 列表/详情**（发起入驻 P02-A、服务记录 P02-B、续费申请 P02-B-R）与 **P03 入驻协助只读**；P01「我的客户」指标卡下钻即所辖商家列表。Phase 2 可评估独立 CS 工作台。

#### 2.4.2a 商家客服（`shop_support` · S4）

商家 tenant 内置角色，**无独立会话/工单页**（Phase 2）。Phase 1 工作流：

| 能力 | 落点页面 | 说明 |
|------|----------|------|
| 订单处理/退款 | A09 · A10 | 与 `shop_admin` 共享列表；`shop_support` 无商品/店铺写权限 |
| 买家/权益查询 | A11 · A12 | 只读 + 退款/重发短信 |
| 开票 | A13 | 处理 M13 提交的申请 |
| 核销 | — | 一般由 `shop_clerk` 在 A08；`shop_support` 可选只读 |

配置入口：[A16](./01-管理端UI.html#a16) 启用内置角色并分配成员。与平台 `platform_shop_cs`（跨租户管家）**不同域**。"""

    if "#### 2.4.2a 商家客服" not in text:
        text = text.replace(
            "线框见 [P02](./06-平台端UI.html#p02) · [P08](./06-平台端UI.html#p08) · 权限见 [05-角色权限#platform](./05-角色权限.html#platform)。\n\n#### 2.4.3 套餐续费付费流程",
            cs_expand + "\n\n#### 2.4.3 套餐续费付费流程",
        )

    s5_block = """
#### 3.5.6 四链路组合矩阵与 Phase 2 门槛（S5）

路径（A/B）× 链路（①/②）共 **4 种组合**；Phase 1 Mx **只验收其中 1 种**（与商务合同一致），其余 3 种列为 Phase 2 门槛，避免范围蔓延。

| 组合 | 路径 | 链路 | Phase 1 | Phase 2 验收门槛（摘要） |
|------|------|------|---------|-------------------------|
| **①-A** | 平台官方店 | 抖店付+领权 | ✅ **Mx 首选** | — |
| ①-B | 商家自有抖店 | 抖店付+领权 | ⏳ Phase 2 | 商家子店进件 + A14 绑商家 AppKey + 同 Mx 8 步 |
| ②-A | 平台官方店 | 小程序内付+学 | ⏳ Phase 2 | 课程库提审 + F3b + 平台店分账 |
| ②-B | 商家交付店 | 小程序内付+学 | ⏳ Phase 2 | 商家小程序 + 微信子商户 + F3b 全链路 |

**Phase 1 未选组合的处理**：配置界面可展示但须标注「未开通」；Webhook/映射 API 对未开通组合返回 `422 channel_combo_not_enabled`；文档与验收脚本不覆盖。

"""
    if "#### 3.5.6 四链路组合矩阵" not in text:
        text = text.replace(
            "#### 3.5.5 与 API 的对应\n\n- 商家映射与同步：§8.11",
            "#### 3.5.5 与 API 的对应\n\n- 商家映射与同步：§8.11",
        )
        text = text.replace(
            "- 平台渠道配置：P06 · `GET/PUT /admin/shop/channel-config`\n\n### 3.6 可选",
            "- 平台渠道配置：P06 · `GET/PUT /admin/shop/channel-config`\n" + s5_block + "\n### 3.6 可选",
        )

    a03_note = """| 🚫 创作顾问→商品草稿自动导入 | A03「从创作顾问导入」Phase 2；**Phase 1 按钮灰显不可点**（见 [A03](./01-管理端UI.html#a03)） |"""
    if "灰显不可点" not in text:
        text = text.replace(
            "| 🚫 创作顾问→商品草稿自动导入 | A03「从创作顾问导入」Phase 2 |",
            a03_note,
        )

    p116 = """**P1-16 IP 演示包**：见 [index.html#p1-16-demo](./index.html#p1-16-demo)（CTA → 挂载 → 下单最小脚本，非 Mx 硬验收）。"""
    p116_new = """**P1-16 IP 演示包**：见 [index.html#p1-16-demo](./index.html#p1-16-demo) · 编排流 [F11](./03-数据流.html#f11)（CTA → 挂载 → 下单，非 Mx 硬验收）。"""
    if "编排流 [F11]" not in text:
        text = text.replace(p116, p116_new)

    PRD.write_text(text, encoding="utf-8")
    print("S3-S5: PRD patched")


def patch_admin_s2_s3() -> None:
    text = ADMIN.read_text(encoding="utf-8")

    btn_old = '  <span class="btn" style="font-size:12px;border-style:dashed">从创作顾问导入（Phase 2）</span>'
    btn_new = '  <span class="btn" style="font-size:12px;border-style:dashed;opacity:.45;color:#999;cursor:not-allowed" title="Phase 2 规划，Phase 1 不可点击">从创作顾问导入（Phase 2 · 灰显）</span>'
    if "灰显" not in text:
        text = text.replace(btn_old, btn_new)

    note_old = '<div class="note" style="margin-top:8px"><b>approved 态样例</b>：'
    note_new = '<div class="note" style="margin-top:8px"><b>Phase 2 灰显</b>：「从创作顾问导入」仅展示占位，<code>pointer-events:none</code> + 禁用样式；点击不发起 API；悬停 tooltip「Phase 2 开放」。<br><b>approved 态样例</b>：'
    if "Phase 2 灰显" not in text:
        text = text.replace(note_old, note_new)

    val_old = """    <tr>
      <td><b>上架销售</b></td>
      <td>① <a href="05-角色权限.html#perm-shop-product-publish"""
    val_import = """    <tr>
      <td><b>从创作顾问导入</b></td>
      <td>—（Phase 1 禁用）</td>
      <td>「功能即将开放」· 按钮灰显</td>
      <td>—（无落点）</td>
    </tr>
    <tr>
      <td><b>上架销售</b></td>
      <td>① <a href="05-角色权限.html#perm-shop-product-publish"""
    if "<b>从创作顾问导入</b></td>" not in text:
        text = text.replace(val_old, val_import)

    ui_row_old = '<tr><td><b>类型卡片</b></td><td>表单顶</td><td>栏位显隐</td><td>下拉规格表</td></tr>'
    ui_row_new = ui_row_old + '\n    <tr><td><b>从创作顾问导入</b></td><td>底栏灰显按钮</td><td>A03 占位</td><td>Phase 1 禁用行</td></tr>'
    if "从创作顾问导入</b></td><td>底栏" not in text:
        text = text.replace(ui_row_old, ui_row_new)

    # S3: A01 backlog banner - find A01 section
    a01_banner = """<div class="note" style="margin-bottom:10px;border-color:#ffe58f;background:#fffbe6;color:#ad6800"><b>恢复营业提醒</b>（<code>merchant</code> 刚从 suspended 恢复时展示一次）：店铺已恢复营业，您有 <b>3</b> 笔订单待处理 · <a href="#a09" style="color:var(--color-primary)">去订单列表</a> · <a href="#a09" style="color:var(--color-primary)">导出积压 CSV</a></div>
"""
    if "恢复营业提醒" not in text:
        text = text.replace(
            '<h2>A01 交易看板（概览） <span class="tag tag-r">P1-14</span></h2>',
            '<h2>A01 交易看板（概览） <span class="tag tag-r">P1-14</span></h2>\n' + a01_banner,
        )

    ADMIN.write_text(text, encoding="utf-8")
    print("S2-S3: admin UI patched")


def patch_index() -> None:
    text = INDEX.read_text(encoding="utf-8")
    old = '<p class="section-sub">非 Mx 硬验收；用于招商/内部分享时演示「内容 → 挂载 → 成交」闭环。验收见'
    new = '<p class="section-sub">非 Mx 硬验收；用于招商/内部分享时演示「内容 → 挂载 → 成交」闭环。数据流编排见 <a href="03-数据流.html#f11">F11 IP 获客演示</a>。验收见'
    if "03-数据流.html#f11" not in text:
        text = text.replace(old, new)

    desc_old = "F8 套餐、<strong>F9 用量</strong>、<strong>F10 清结算</strong>"
    desc_new = "F8 套餐、<strong>F9 用量</strong>、<strong>F10 清结算</strong>、<strong>F11 演示编排</strong>"
    if "F11 演示编排" not in text:
        text = text.replace(desc_old, desc_new)

    INDEX.write_text(text, encoding="utf-8")
    print("S1: index patched")


def patch_p08_s4() -> None:
    text = P08_SNIPPET.read_text(encoding="utf-8")
    old = '<p class="sub">内置 <b>4</b> 个模板；Phase 1 可启用/停用模板、查看默认权限；给账号绑定时可<strong>微调勾选</strong>（落库到用户权限集，不改模板本身）。<strong>商家管家</strong>（<code>platform_shop_cs</code>）仅看所辖客户，负责入驻协助与续费跟进。</p>'
    new = '<p class="sub">内置 <b>4</b> 个模板；Phase 1 可启用/停用模板、查看默认权限；给账号绑定时可<strong>微调勾选</strong>（落库到用户权限集，不改模板本身）。<strong>商家管家</strong>（<code>platform_shop_cs</code>）仅看所辖客户，负责入驻协助与续费跟进。<b>无独立管家工作台</b>（Phase 1 操作均在 <a href="#p02">P02</a> / <a href="#p02b-service">P02-B 服务记录</a>）；详见 PRD <a href="PRD-内容获客商城-phase1.md#242-商家管家platform_shop_cs">§2.4.2</a>。</p>'
    if "无独立管家工作台" not in text:
        text = text.replace(old, new)
        P08_SNIPPET.write_text(text, encoding="utf-8")
        print("S4: P08 patched")


if __name__ == "__main__":
    patch_flows_s1()
    patch_prd()
    patch_admin_s2_s3()
    patch_index()
    patch_p08_s4()
