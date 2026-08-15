#!/usr/bin/env python3
"""Inject 下拉/选择规格 tables — per article (A/M) or per sub-panel (P multi-tab)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "docs/01-PRD/21-内容获客商城-phase1"

Row = tuple[str, str, str, str, str, str]
NONE = "—"

COMMON_REF = (
    '<div class="op" style="font-size:12px;margin-top:8px">'
    '通用枚举 <a href="04-数据模型.html#select-common">04 §通用</a> · '
    '级联 <a href="04-数据模型.html#select-cascade">04 §级联</a> · '
    '<a href="../../00-总览/PRD写作规范.md#259-下拉与选择控件规格">§2.5.9</a></div>'
)

PLATFORM_SINGLE_ARTICLES = frozenset({"p00", "p01", "p06"})


def r(ctrl, mode, enum, logic, api=NONE, cascade=NONE) -> Row:
    return (ctrl, mode, enum, logic, cascade, api)


def table(anchor_id: str, rows: list[Row] | None, *, title: str = "下拉/选择规格") -> str:
    if rows is None:
        return (
            f'<div class="op" style="font-size:12px;margin-top:12px" id="{anchor_id}-select-spec">'
            f"<b>{title}</b>：本页无下拉/单选控件；无级联（§2.5.9）。</div>"
        )
    lines = [
        f'<h4 id="{anchor_id}-select-spec" style="font-size:13px;margin:16px 0 8px">{title}</h4>',
        '<table class="meta matrix" style="margin-bottom:8px">',
        "<tr><th>控件</th><th>单选/多选</th><th>枚举 / 来源</th><th>取值逻辑</th><th>级联</th><th>落库 / API</th></tr>",
    ]
    for row in rows:
        lines.append(
            f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td>"
            f"<td>{row[3]}</td><td>{row[4]}</td><td>{row[5]}</td></tr>"
        )
    lines.append("</table>")
    lines.append(COMMON_REF)
    return "\n  ".join(lines)


# --- 商家端 / 买家端：一 article 一表 ---
ARTICLE_SPECS: dict[str, list[Row] | None] = {
    "a00": None,
    "a01": [
        r("A01 · 时间范围", "单选", "今日/近7/近30/自定义", "刷新看板", "dashboard?range=", cascade="是：→指标图表"),
        r("A01 · 最近订单·渠道/状态", "单选×2", "渠道 · 订单状态", "内嵌筛选", api="shop_orders"),
        r("A01 · 每页条数", "单选", "04 §通用 5/10/20", "默认 10", api="page_size"),
        r("A01 · 当前店铺 ▾", "单选", "GET /shop/stores", "切换上下文", "current_shop_id", cascade="是：→全页 shop_id"),
    ],
    "a02": [
        r("A02 · 快捷视图", "单选", "CRM preset", "—", api="view_id"),
        r("A02 · 类型/状态/公域", "单选×3", "商品筛选枚举", "AND", "query", cascade="否"),
        r("A02 · 每页条数", "单选", "04 §通用", "默认 20", api="page_size"),
    ],
    "a03": [
        r("A03 · 商品类型", "单选", "course/digital/service", "保存后锁定", "product_type", cascade="是：→专栏显隐"),
        r("A03 · 关联专栏 ▾", "单选", "已发布专栏", "course 必填", "content_column_id", cascade="父：product_type"),
        r("A03 · 退款策略 ▾", "单选", "04 §refund_policy", "默认 A19", api="refund_policy"),
    ],
    "a04": [
        r("A04 · 视图/状态", "单选×2", "专栏状态", "—", api="shop_columns.status"),
        r("A04 · 每页条数", "单选", "04 §通用", "—", api="page_size"),
    ],
    "a05": [
        r("A05 · 课时状态/类型", "单选×2", "draft/published; video/article", "—", api="shop_lessons"),
        r("A05-A · 课时类型", "单选", "video · article", "—", api="media_type"),
    ],
    "a06": [r("A06 · 交付方式", "单选", "download · online_view", "—", api="delivery_mode")],
    "a07": [
        r("A07 · 服务模式", "单选", "appointment · punch_card", "—", "mode", cascade="是：→时段表显隐"),
        r("A07 · 时段视图/状态", "单选×2", "时段状态", "—", api="shop_service_slots"),
    ],
    "a08": None,
    "a09": [
        r("A09 · 视图/状态/渠道", "单选×3", "订单筛选", "AND", "shop_orders", cascade="否"),
        r("A09 · 导出 ▾", "单选", "筛选/选中", "—", api="POST export"),
        r("A09-B · 退款原因", "单选", "预设码", "≥4 字", api="reason_code"),
    ],
    "a10": [r("A10-A · 退款原因", "单选", "预设+纠纷", "—", api="reason_code")],
    "a11": [
        r("A11 · 快捷视图", "单选", "买家 preset", "—", api="GET /shop/buyers"),
        r("A11-A · 详情 Tab", "单选", "子列表 Tab", "只读", api="—"),
    ],
    "a12": [r("A12 · 视图/类型/状态", "单选×3", "权益筛选", "—", api="entitlements")],
    "a13": [
        r("A13 · 视图/类型", "单选×2", "开票筛选", "—", api="invoices"),
        r("A13-A · 驳回原因", "单选", "预设码", "≥4 字", api="reject_code"),
    ],
    "a14": [
        r("A14 · 映射/挂载/审核", "单选×3", "listing 枚举", "—", api="channel_listings"),
        r("A14-A · 本地商品 ▾", "单选", "在售商品", "—", "product_id", cascade="是：→路径→外部店"),
        r("A14-A · 对接路径 ▾", "单选", "A/B 路径", "—", "integration_path", cascade="父：商品"),
        r("A14-A · 外部店铺 ▾", "单选", "已绑定抖店", "—", "external_store_id", cascade="父：路径"),
    ],
    "a15": [
        r("A15 · 设置 Tab", "单选", "支付/短信", "—", api="—"),
        r("A15 · 短信签名 ▾", "单选", "已审核签名", "—", api="sms_signature_id"),
    ],
    "a16": [
        r("A16 · 子 Tab", "单选", "成员/矩阵", "—", api="—"),
        r("A16-A · 成员/角色", "单选×2", "成员搜索；角色", "—", "role_bindings", cascade="是：角色→店铺范围"),
        r("A16-A · 店铺范围", "多选", "各店/全部", "—", "store_ids[]", cascade="父：shop_clerk"),
    ],
    "a17": [r("A17 · 店铺视图/状态", "单选×2", "active/paused", "—", api="shop_stores")],
    "a18": [r("A18 · 设置子 Tab", "单选", "导航 Tab", "—", api="—")],
    "a19": [r("A19 · 退款默认", "单选", "04 §refund_policy", "新商品默认", api="default_refund_policy")],
    "a20": [r("A20 · 主体类型 ▾", "单选", "04 §entity_type", "草稿保留", "entity_type", cascade="是：→栏位显隐")],
    "a21": None,
    "a22": None,
    "m00": None,
    "m01": None,
    "m02": [
        r("M02 · 排序 ▾", "单选", "综合/价格/销量", "—", "sort", cascade="否：与 Chip AND"),
        r("M02 · 类型 Chip", "单选", "全部/课/资料/服务", "—", api="product_type"),
        r("M02 · 底栏 Tab", "单选", "首页/已购/我的", "—", api="—"),
    ],
    "m03": [r("M03 · 底栏 Tab", "单选", "底栏", "—", api="—")],
    "m04": [
        r("M04 · 协议勾选", "单选布尔", "同意/未同意", "未勾禁付", api="—"),
        r("M04 · 底栏 Tab", "单选", "底栏", "—", api="—"),
    ],
    "m05": [r("M05 · 底栏 Tab", "单选", "底栏", "—", api="—")],
    "m06": [
        r("M06 · 类型 Chip", "单选", "课/资料/服务", "—", api="type"),
        r("M06 · 底栏 Tab", "单选", "底栏", "—", api="—"),
    ],
    "m07": [r("M07 · 课时行", "单选", "目录项", "进播放器", api="lesson_id")],
    "m08": [r("M08 · 倍速", "单选", "1.0x～2.0x", "本地", api="playback_rate")],
    "m09": None,
    "m10": [
        r("M10 · 时段卡片", "单选", "开放时段", "已满灰显", api="slot_id"),
        r("M10c · 预约 Tab", "单选", "待服务/已完成", "—", api="status"),
    ],
    "m10b": None,
    "m11": [r("M11 · 状态 Tab", "单选", "订单状态 Tab", "—", api="orders.status")],
    "m12": [r("M12-A · 退款原因", "单选+文本", "预设+说明", "≥4 字", api="reason")],
    "m13": [r("M13 · 抬头类型", "单选", "个人/企业", "—", "buyer_type", cascade="是：→税号栏")],
    "m14": None,
    "m15": [r("M15 · 底栏 Tab", "单选", "底栏", "—", api="—")],
    "p00": None,
    "p01": None,
    "p06": None,
}

# --- 平台端多 Tab：各 pdoc-panel / 子段独立一表 ---
PANEL_SPECS: dict[str, list[Row] | None] = {
    "p02-list": [
        r("快捷 Tab", "单选", "全部/我的客户/待审/即将到期/已到期/已暂停", "P01 下钻", "tab", cascade="是：P01→Tab"),
        r("标签 ▾", "多选", "标签字典", "AND 筛选", api="tag_ids"),
        r("高级筛选×6", "单选各", "主体/入驻/套餐/管家/费率", "查询", "merchants list", cascade="否：独立 AND"),
        r("导出 ▾", "单选", "当前筛选/列配置", "—", api="POST export"),
        r("每页条数", "单选", "04 §通用", "默认 20", api="page_size"),
    ],
    "p02a": [
        r("关联租户 ▾", "单选", "未入驻 tenant 搜索", "不可新建", "tenant_id", cascade="是：→企业预填"),
        r("主体类型", "单选", "04 §entity_type", "—", "entity_type", cascade="是：→栏位/材料显隐"),
    ],
    "p02b-overview": None,
    "p02b-entitlements": None,
    "p02b-stores": None,
    "p02b-materials": None,
    "p02b-service": [
        r("类型 ▾", "单选", "note/call/visit/renewal_request…", "—", api="type"),
        r("状态 ▾", "单选", "logged/pending/completed…", "—", api="status"),
        r("每页条数", "单选", "10/20/50", "—", api="page_size"),
    ],
    "p02b-audit": [
        r("全部动作 ▾", "单选", "开通/暂停/分配管家…", "—", api="audit action"),
    ],
    "p02b-tags": [
        r("添加标签 ▾", "多选", "标签字典+新建", "≤20", api="tag_links"),
    ],
    "p02b-note": [
        r("跟进类型 ▾", "单选", "备注/电话/拜访/其他", "—", api="type"),
        r("跟进时间 ▾", "日期时间", "默认 now", "—", api="occurred_at"),
    ],
    "p02b-renewal": [
        r("申请类型 ▾", "单选", "renew/stack/replace", "—", "application_kind", cascade="是：套餐态→类型"),
        r("目标套餐 ▾", "单选", "P10 过滤套餐", "—", "target_plan_code", cascade="是：类型→套餐+标价"),
        r("应付金额", "输入", "默认=标价", "可议价/0", "quoted_amount_cents", cascade="父：目标套餐"),
    ],
    "p02b-view": None,
    "p02b-service-validation": None,
    "renewal-payment-flow": None,
    "p02c": [
        r("暂停原因 ▾", "单选", "违规/欠费/商家申请/其他", "说明 ≥4 字", api="reason_code"),
    ],
    "p02d": None,
    "p02e": [
        r("新管家 ▾", "单选", "GET platform_users?platform_shop_role=platform_shop_cs", "一家一管家", api="account_manager_user_id"),
    ],
    "p03-list": [
        r("视图 ▾", "单选", "全部申请…", "—", api="view"),
        r("主体类型 ▾", "单选", "04 §entity_type", "—", api="entity_type"),
        r("审核状态 ▾", "单选", "pending/approved/rejected", "—", api="status"),
    ],
    "p03a": [r("驳回原因码 ▾", "单选", "资质不全/主体不符/…", "+说明", api="reject_code")],
    "p03b": [
        r("首开套餐 ▾", "单选", "P10 上架套餐", "—", "plan_code", cascade="是：entity_type→allowed"),
    ],
    "p03c": None,
    "p04-list": [
        r("视图/状态", "单选×2", "类目 enabled/blocked", "—", api="categories"),
        r("每页条数", "单选", "04 §通用", "—", api="page_size"),
    ],
    "p04a": [
        r("父类目 ▾", "单选", "类目树", "—", "parent_id", cascade="是：树形父子"),
        r("分账规则 ▾", "单选", "规则模板", "—", api="settlement_rule_id"),
    ],
    "p04b": None,
    "p04c": [r("原因类型 ▾", "单选", "政策调整/费率重议/其他", "—", api="reason")],
    "p04d": None,
    "p11-list": [
        r("视图/待办", "单选", "全部/待处理续费…", "—", api="view"),
        r("状态/套餐", "单选×2", "订阅状态；plan_code", "—", api="subscriptions"),
    ],
    "p11a": [
        r("开通方式", "单选", "stack · replace", "—", "purchase_mode", cascade="是：→可选套餐"),
        r("目标套餐 ▾", "单选", "P10 过滤", "—", "plan_code", cascade="父：方式+主体"),
    ],
    "p11a-stack": [
        r("加购包 ▾", "单选", "stackable=true 模板", "stack 锁定", api="plan_code"),
    ],
    "p11a-renewal": [
        r("续期方式", "单选", "主套餐续期/叠加", "预填自申请", api="purchase_mode"),
        r("目标套餐 ▾", "单选", "renew 同档", "—", api="plan_code"),
    ],
    "p11b": [
        r("换档套餐 ▾", "单选", "同 replace_group 更高档", "replace 锁定", api="plan_code"),
    ],
    "p11c": None,
    "p11d": None,
    "p11e": None,
    "p08-admin-users": [
        r("平台角色 ▾", "单选", "user / platform_admin", "行内", api="role"),
        r("获客商城角色 ▾", "单选", "空 / platform_shop_*", "仅 platform_admin", api="platform_shop_role"),
        r("状态 ▾", "单选", "启用/禁用", "全局", api="is_active"),
    ],
    "p08b": [r("角色 ▾", "单选", "P08 内置角色", "编辑绑定", api="platform_shop_role")],
    "p08c": [
        r("选择用户 ▾", "单选", "User 搜索", "—", api="user_id"),
        r("角色 ▾", "单选", "P08 内置角色", "—", api="platform_shop_role"),
    ],
    "p08d": [r("停用原因 ▾", "单选", "岗位调整/离职/其他", "选填", api="reason")],
    "p08e": None,
}

SECTION_SPECS: dict[str, list[Row] | None] = {
    "p10-main": [
        r("字典·分类/类型", "单选×2", "quota/usage；int/bool", "—", api="plan_features"),
        r("套餐·类型/上架", "单选×2", "main/addon；is_public", "—", "plans", cascade="是：类型→stackable"),
        r("每页条数", "单选", "04 §通用", "—", api="page_size"),
    ],
    "p10a": [
        r("分类 ▾", "单选", "quota/usage/channel", "—", api="category"),
        r("数值类型 ▾", "单选", "int/counter/bool", "—", api="value_type"),
        r("合并方式 ▾", "单选", "max/sum/any", "—", api="aggregate_mode"),
        r("周期 ▾", "单选", "daily/monthly/—", "—", api="usage_period"),
    ],
    "p10b": None,
    "p10c": None,
    "p10d": None,
    "p05-main": [
        r("批次视图/状态", "单选×2", "pending/paid/failed", "—", api="settlements"),
        r("每页条数", "单选", "04 §通用", "—", api="page_size"),
    ],
    "p05c": [r("处理方式", "单选", "重试/退回待结算", "—", api="POST retry")],
    "p07-main": [
        r("工单视图/类型/状态", "单选×3", "稽查筛选", "—", api="tickets"),
    ],
    "p07b": [
        r("下架原因 ▾", "单选", "虚假宣传/违禁/…", "—", api="reason"),
        r("处理结果 ▾", "单选", "已下架/警告/误报/其他", "—", api="resolution"),
    ],
    "p09-main": [
        r("待审队列/机审/类目", "单选×3", "审核筛选", "—", api="reviews"),
    ],
    "p09a": [r("驳回原因码 ▾", "单选", "敏感/资质/虚假宣传/其他", "—", api="reject_code")],
}


def strip_all_select_specs(text: str) -> str:
    text = re.sub(
        r'\n\s*<h4 id="[a-z0-9-]+-select-spec"[^>]*>下拉/选择规格</h4>\s*'
        r'<table class="meta matrix"[\s\S]*?</table>\s*'
        r'<div class="op"[\s\S]*?§2\.5\.9</a></div>',
        "\n",
        text,
    )
    text = re.sub(
        r'\n\s*<div class="op"[^>]*id="[a-z0-9-]+-select-spec"[^>]*>[\s\S]*?</div>',
        "\n",
        text,
    )
    return text


def inject_at_panel_end(html: str, panel_id: str, spec_html: str) -> str:
    needle = f'id="{panel_id}"'
    start = html.find(needle)
    if start == -1:
        return html
    div_start = html.rfind("<div", 0, start)
    if div_start == -1:
        return html
    pos = div_start
    depth = 0
    while pos < len(html):
        next_open = html.find("<div", pos)
        next_close = html.find("</div>", pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6
            if depth == 0:
                return html[:next_close] + "\n  " + spec_html + "\n  " + html[next_close:]
    return html


def inject_before_marker(html: str, marker: str, spec_html: str) -> str:
    idx = html.find(marker)
    if idx == -1:
        return html
    return html[:idx] + "\n  " + spec_html + "\n  " + html[idx:]


def inject_articles(html: str, specs: dict[str, list[Row] | None], prefix: str) -> tuple[str, int]:
    count = 0

    def replacer(m: re.Match[str]) -> str:
        nonlocal count
        body, page_id, close = m.group(1), m.group(2), m.group(3)
        if not page_id.startswith(prefix) or page_id not in specs:
            return m.group(0)
        note = table(page_id, specs[page_id])
        count += 1
        return body + "\n  " + note + "\n" + close

    pattern = re.compile(
        r'(<article[^>]*\bid="([a-z0-9]+)"[^>]*>.*?)(</article>)',
        re.DOTALL | re.IGNORECASE,
    )
    return pattern.sub(replacer, html), count


def inject_platform(html: str) -> tuple[str, int]:
    count = 0
    for panel_id, rows in PANEL_SPECS.items():
        block = table(panel_id, rows)
        new_html = inject_at_panel_end(html, panel_id, block)
        if new_html != html:
            html = new_html
            count += 1
    section_markers = {
        "p10-main": '<h3 id="p10a">',
        "p10a": '<h3 id="p10b">',
        "p10b": '<h3 id="p10c">',
        "p10c": '<h3 id="p10d">',
        "p05-main": '<h3 id="p05a">',
        "p05c": '<h3 id="p05b">',
        "p07-main": '<h3 id="p07a">',
        "p07b": '<h3 id="p07c">',
        "p09-main": '<h3 id="p09a">',
        "p09a": '<h3 id="p09b">',
    }
    for anchor, marker in section_markers.items():
        block = table(anchor, SECTION_SPECS.get(anchor))
        new_html = inject_before_marker(html, marker, block)
        if new_html != html:
            html = new_html
            count += 1
    single = {k: ARTICLE_SPECS[k] for k in PLATFORM_SINGLE_ARTICLES if k in ARTICLE_SPECS}
    html, c = inject_articles(html, single, "p")
    count += c
    return html, count


def main() -> None:
    for name, prefix in (("01-管理端UI.html", "a"), ("02-买家端UI.html", "m")):
        text = strip_all_select_specs((MODULE / name).read_text(encoding="utf-8"))
        text, n = inject_articles(text, ARTICLE_SPECS, prefix)
        (MODULE / name).write_text(text, encoding="utf-8")
        print(f"{name}: {n} articles")

    path = MODULE / "06-平台端UI.html"
    text = strip_all_select_specs(path.read_text(encoding="utf-8"))
    text, n = inject_platform(text)
    path.write_text(text, encoding="utf-8")
    print(f"06-平台端UI.html: {n} panels/sections")


if __name__ == "__main__":
    main()
