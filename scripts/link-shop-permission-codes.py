#!/usr/bin/env python3
"""Add catalog anchors in 05-角色权限.html and link permission codes across PRD docs."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRD_DIR = ROOT / "docs/01-PRD/21-内容获客商城-phase1"
CATALOG_FILE = PRD_DIR / "05-角色权限.html"
CATALOG_REL = "05-角色权限.html"
CATALOG_ANCHOR = "catalog"

# Full permission catalog: code -> (description, pages)
PERMISSIONS: dict[str, tuple[str, str]] = {
    # platform
    "platform.shop.analytics": ("平台总览指标、下钻与导出", "P01"),
    "platform.shop.merchant.read": ("商家列表与旗下店铺、商家详情（含只读）", "P02 · P02-B"),
    "platform.shop.merchant.list_all": ("全站商家列表数据范围", "P02"),
    "platform.shop.merchant.list_assigned": ("仅所辖商家（account_manager_user_id=本人）", "P02 我的客户"),
    "platform.shop.merchant.assign": ("分配 / 改派商家管家", "P02-B · P03"),
    "platform.shop.merchant.manage": ("暂停 / 恢复商家", "P02-C · P02-D"),
    "platform.shop.onboarding.initiate": ("管家代建 · 发起入驻申请（仅 platform_shop_cs）", "P02-A"),
    "platform.shop.approve": ("入驻审核（通过 / 驳回）", "P03"),
    "platform.shop.plan.manage": ("套餐模板与功能字典配置", "P10"),
    "platform.shop.subscription.read": ("查看商家订阅、权益与周期用量", "P02、P11"),
    "platform.shop.subscription.manage": ("开通/续费/升级/调整生效期", "P11"),
    "platform.shop.fee.manage": ("平台类目树、默认费率与分账规则", "P04"),
    "platform.shop.settlement": ("清结算批次、确认打款与重试", "P05"),
    "platform.shop.channel": ("抖店开放平台应用与全局回调配置", "P06"),
    "platform.shop.moderate": ("违规稽查工单处理与结案", "P07"),
    "platform.shop.product.review": ("平台商品人审队列", "P09"),
    "platform.shop.product.force_off": ("平台强制下架商品", "P07、P09"),
    # merchant shop.*
    "shop.analytics.read": ("交易看板与指标", "A01"),
    "shop.product.read": ("商品 SKU 查看", "A02–A03"),
    "shop.product.write": ("商品 SKU 编辑", "A02–A03"),
    "shop.product.delete": ("商品 SKU 删除", "A02–A03"),
    "shop.product.submit_review": ("提交商品合规审核（draft/rejected → pending_review）", "A03"),
    "shop.product.publish": ("审核通过后上架/下架（approved ↔ on_sale）", "A02–A03"),
    "shop.content.read": ("专栏、课时、资料包、服务时段查看", "A04–A07"),
    "shop.content.write": ("专栏、课时、资料包、服务时段编辑", "A04–A07"),
    "shop.redemption.read": ("核销台查询", "A08"),
    "shop.redemption.execute": ("核销台确认核销", "A08"),
    "shop.redemption.list_all": ("核销记录数据范围（全部）", "A08 审计"),
    "shop.redemption.list_own": ("核销记录数据范围（本人经手）", "A08 审计"),
    "shop.order.list_all": ("订单列表数据范围（全部）", "A09"),
    "shop.order.list_own": ("订单列表数据范围（本人经手）", "A09"),
    "shop.order.view": ("订单详情查看", "A10"),
    "shop.order.export": ("订单导出", "A10"),
    "shop.order.close": ("关闭待付款订单", "A10"),
    "shop.order.refund": ("订单退款", "A10"),
    "shop.order.resend_notify": ("重发领权/通知短信", "A10"),
    "shop.buyer.list_all": ("买家列表数据范围", "A11"),
    "shop.buyer.view": ("买家列表与详情", "A11"),
    "shop.entitlement.list_all": ("权益列表数据范围", "A12"),
    "shop.entitlement.view": ("权益查询", "A12"),
    "shop.entitlement.revoke": ("权益人工关闭", "A12"),
    "shop.invoice.list_all": ("开票列表数据范围", "A13"),
    "shop.invoice.view": ("开票查看", "A13"),
    "shop.invoice.process": ("开票审核处理", "A13"),
    "shop.channel.read": ("抖店绑定与回调配置查看", "A14"),
    "shop.channel.write": ("抖店绑定与回调配置编辑", "A14"),
    "shop.channel.map": ("商品公域映射（须过挂载闸）", "A14"),
    "shop.settings.read": ("微信支付/短信进件查看（商家级）", "A15"),
    "shop.settings.write": ("微信支付/短信进件编辑（商家级）", "A15"),
    "shop.subscription.usage.read": ("合并套餐权益与周期用量只读", "A18、提审/短信预检"),
    "shop.store.manage": ("创建/暂停店铺、切换当前店", "A17"),
    "shop.store.settings.read": ("单店展示、退款默认查看", "A19"),
    "shop.store.settings.write": ("单店展示、退款默认编辑", "A19"),
    "shop.role.manage": ("查看内置角色矩阵与成员绑定（仅 admin）", "A16"),
}

# Shorthand without platform.shop. prefix (platform UI docs)
SHORTHAND: dict[str, str] = {
    "approve": "platform.shop.approve",
    "subscription.manage": "platform.shop.subscription.manage",
    "subscription.read": "platform.shop.subscription.read",
    "merchant.manage": "platform.shop.merchant.manage",
    "merchant.read": "platform.shop.merchant.read",
    "product.force_off": "platform.shop.product.force_off",
    "product.review": "platform.shop.product.review",
}

PERM_CODE_RE = re.compile(
    r"(?P<prefix>platform\.shop\.|shop\.)[a-z][a-z0-9_.]*"
)


def perm_id(code: str) -> str:
    return "perm-" + code.replace(".", "-")


def perm_href(code: str, from_file: Path) -> str:
    anchor = perm_id(code)
    if from_file.resolve() == CATALOG_FILE.resolve():
        return f"#{anchor}"
    rel = Path(CATALOG_REL).as_posix()
    return f"{rel}#{anchor}"


def rebuild_catalog_html() -> None:
    text = CATALOG_FILE.read_text(encoding="utf-8")

    extra_css = """
a.perm-link{text-decoration:none}
a.perm-link code{cursor:pointer}
a.perm-link:hover code{text-decoration:underline;color:#0958d9}
tr.perm-row:target{background:#e6f4ff}
tr.perm-row:target td{border-color:#91caff}
"""
    if "a.perm-link" not in text:
        text = text.replace("</style>", extra_css + "</style>", 1)

    rows = [
        "    <tr><th>权限码</th><th>说明</th><th>页面</th></tr>",
    ]
    for code in sorted(PERMISSIONS.keys(), key=lambda c: (0 if c.startswith("platform.") else 1, c)):
        desc, pages = PERMISSIONS[code]
        pid = perm_id(code)
        rows.append(
            f'    <tr class="perm-row" id="{pid}">'
            f"<td><code>{code}</code></td><td>{desc}</td><td>{pages}</td></tr>"
        )

    table_body = "\n".join(rows)
    new_catalog = f"""<div class="block" id="{CATALOG_ANCHOR}">
  <h2>权限码 Catalog（Phase 1）</h2>
  <p class="sub">本表为<strong>权威清单</strong>：各页面中出现的 <code>platform.shop.*</code> / <code>shop.*</code> 权限码均可点击跳转到对应行查看含义与落点页面。实现时写入 <code>permissions</code> 表并挂到 <code>SHOP_DEFAULT_PERMISSIONS</code> 种子；与 <code>app/permissions.py</code> 扩展对齐。</p>
  <table>
{table_body}
  </table>
</div>"""

    text = re.sub(
        r'<div class="block" id="catalog">.*?</div>\s*(?=</div>\s*</body>)',
        new_catalog + "\n\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    CATALOG_FILE.write_text(text, encoding="utf-8")


def link_code_in_html(code: str, from_file: Path) -> str:
    href = perm_href(code, from_file)
    return f'<a href="{href}" class="perm-link" title="查看权限说明"><code>{code}</code></a>'


def _replace_plain_code_tags(text: str, code: str, linked: str) -> str:
    plain = f"<code>{code}</code>"
    out: list[str] = []
    i = 0
    while True:
        idx = text.find(plain, i)
        if idx == -1:
            out.append(text[i:])
            break
        before = text[max(0, idx - 300) : idx]
        # skip if already inside an open perm-link anchor
        last_a = before.rfind('<a ')
        last_close = before.rfind("</a>")
        inside_link = last_a != -1 and (last_close == -1 or last_a > last_close)
        if inside_link and 'class="perm-link"' in before[last_a:]:
            out.append(text[i : idx + len(plain)])
        else:
            out.append(text[i:idx])
            out.append(linked)
        i = idx + len(plain)
    return "".join(out)


def repair_nested_perm_links(text: str) -> str:
    """Collapse accidental <a><a><code>...</code></a></a> from shorthand + full passes."""
    pattern = re.compile(
        r'<a href="([^"]+)" class="perm-link" title="查看权限说明">'
        r'<a href="\1" class="perm-link" title="查看权限说明">'
        r"(<code>[^<]+</code>)</a></a>"
    )
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(
            r'<a href="\1" class="perm-link" title="查看权限说明">\2</a>', text
        )
    return text


def link_html_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    original = text

    # Full codes first (longest first), then shorthand aliases
    for code in sorted(PERMISSIONS.keys(), key=len, reverse=True):
        text = _replace_plain_code_tags(text, code, link_code_in_html(code, path))

    for short, full in SHORTHAND.items():
        text = _replace_plain_code_tags(text, short, link_code_in_html(full, path))

    text = repair_nested_perm_links(text)

    count = text.count('class="perm-link"') - original.count('class="perm-link"')
    if text != original:
        path.write_text(text, encoding="utf-8")
    return count


def repair_markdown_perm_links(text: str) -> str:
    """Fix [[`code`](url)](url) double-wrapped markdown links."""
    pattern = re.compile(
        r"\[\[`([^`]+)`\]\(([^)]+)\)\]\(\2\)"
    )
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(r"[`\1`](\2)", text)
    return text


def link_markdown_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    original = text
    text = repair_markdown_perm_links(text)

    for short, full in SHORTHAND.items():
        pattern = rf"(?<!\])\`{re.escape(short)}\`(?!\()"
        replacement = f"[`{full}`]({CATALOG_REL}#{perm_id(full)})"
        text = re.sub(pattern, replacement, text)

    for code in sorted(PERMISSIONS.keys(), key=len, reverse=True):
        pattern = rf"(?<!\])\`{re.escape(code)}\`(?!\()"
        replacement = f"[`{code}`]({CATALOG_REL}#{perm_id(code)})"
        text = re.sub(pattern, replacement, text)

    # pipe-separated groups: platform.shop.subscription.read|manage
    def link_pipe_group(m: re.Match[str]) -> str:
        prefix = m.group(1)
        parts = m.group(2).split("|")
        linked = [
            f"[`{prefix}{p}`]({CATALOG_REL}#{perm_id(prefix + p)})"
            for p in parts
            if prefix + p in PERMISSIONS
        ]
        return " / ".join(linked) if linked else m.group(0)

    text = re.sub(
        r"`((?:platform\.shop\.|shop\.)[a-z0-9_.]*)([^`]*\|[^`]+)`",
        link_pipe_group,
        text,
    )

    text = repair_markdown_perm_links(text)
    count = text.count(f"]({CATALOG_REL}#perm-") - original.count(f"]({CATALOG_REL}#perm-")
    if text != original:
        path.write_text(text, encoding="utf-8")
    return count


def inject_perm_link_css(path: Path) -> None:
    if path.suffix != ".html":
        return
    text = path.read_text(encoding="utf-8")
    extra = """
a.perm-link{text-decoration:none}
a.perm-link code{cursor:pointer}
a.perm-link:hover code{text-decoration:underline;color:#0958d9}
"""
    if "a.perm-link" in text:
        return
    if "</style>" in text:
        text = text.replace("</style>", extra + "</style>", 1)
        path.write_text(text, encoding="utf-8")


def repair_html_files() -> None:
    for name in ("01-管理端UI.html", "06-平台端UI.html", "05-角色权限.html"):
        p = PRD_DIR / name
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        fixed = repair_nested_perm_links(text)
        if fixed != text:
            p.write_text(fixed, encoding="utf-8")
            print(f"repaired nested links: {name}")


def patch_index_link() -> None:
    path = PRD_DIR / "index.html"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'href="05-角色权限.html">角色与权限</a>',
        f'href="05-角色权限.html#{CATALOG_ANCHOR}">角色与权限（权限码清单）</a>',
    )
    text = text.replace(
        'href="05-角色权限.html">权限矩阵</a>',
        f'href="05-角色权限.html#{CATALOG_ANCHOR}">权限码清单</a>',
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    rebuild_catalog_html()
    repair_html_files()
    total = 0
    for name in ("01-管理端UI.html", "06-平台端UI.html", "05-角色权限.html"):
        p = PRD_DIR / name
        if p.exists():
            inject_perm_link_css(p)
            n = link_html_file(p)
            print(f"{name}: +{n} links")
            total += n
    md = PRD_DIR / "PRD-内容获客商城-phase1.md"
    if md.exists():
        n = link_markdown_file(md)
        print(f"PRD md: +{n} links")
        total += n
    patch_index_link()
    print(f"Done. Catalog: {CATALOG_FILE}#{CATALOG_ANCHOR} ({len(PERMISSIONS)} codes)")


if __name__ == "__main__":
    main()
