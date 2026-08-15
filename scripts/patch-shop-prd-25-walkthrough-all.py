# -*- coding: utf-8 -*-
"""Patch module 21 HTML files for §2.5 P02-aligned walkthrough."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "docs/01-PRD/21-内容获客商城-phase1"


def insert_after_h2(article_id: str, html: str, note_html: str) -> str:
    m = re.search(
        rf'(<article[^>]*id="{article_id}"[^>]*>.*?<h2>.*?</h2>)',
        html,
        re.DOTALL,
    )
    if not m:
        return html
    snippet = html[m.start():m.end() + 80]
    if "note note-b" in snippet and "先记住两句话" in snippet:
        return html
    return html[:m.end()] + note_html + html[m.end():]


def insert_before_marker(html: str, marker: str, block: str) -> str:
    if block.strip() in html:
        return html
    if marker not in html:
        return html
    return html.replace(marker, block + marker, 1)


def ui_table(label: str, rows: list) -> str:
    trs = "\n".join(
        f"    <tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>"
        for a, b, c, d in rows
    )
    return f"""
  <h4 style="font-size:13px;margin:16px 0 8px">操作按钮 · UI 线框覆盖（{label} 本页）</h4>
  <table class="meta matrix" style="margin-bottom:8px">
    <tr><th>操作</th><th>触发位置</th><th>UI 线框</th><th>点击校验</th></tr>
{trs}
  </table>
"""


def chain_op(text: str) -> str:
    return f'  <div class="op" style="margin-top:8px"><b>操作链路小结</b>：{text}</div>\n'


def patch_buyer():
    f = MOD / "02-买家端UI.html"
    text = f.read_text(encoding="utf-8")

    notes = {
        "m02": "<b>先记住两句话</b>：① 买家只见<strong>在售</strong>商品；已下架默认不展示。② 点卡进 M03，购买主干 M04→M05→M06。",
        "m03": "<b>先记住两句话</b>：① 底栏主按钮随<strong>购买/权益状态</strong>五态切换。② 试看仅标记课时，进 M08 试看模式。",
        "m04": "<b>先记住两句话</b>：① 须微信登录且店铺<strong>营业中</strong>才可下单。② 0 元商品走免费领取直达 M05。",
        "m05": "<b>先记住两句话</b>：① 支付结果页须轮询直到 paid/fail/timeout。② 成功按商品类型分流履约页。",
        "m06": "<b>先记住两句话</b>：① 已购列表按<strong>商品类型</strong>进不同履约页。② 权益 revoked 灰显不可点。",
        "m07": "<b>先记住两句话</b>：① 课时目录依赖<strong>课程权益 active</strong>。② 试看节进 M08 试看，锁定节提示购买。",
        "m08": "<b>先记住两句话</b>：① 播放凭证由 API 下发，试看与全片权限不同。② 试看结束卡引导回 M03/M04。",
        "m09": "<b>先记住两句话</b>：① 资料权益 active 才可下载/预览。② 下载次数受套餐与商品策略限制。",
        "m10": "<b>先记住两句话</b>：① 服务类须选<strong>开放时段</strong>再确认预约。② 取消预约见 M10-D 规则。",
        "m11": "<b>先记住两句话</b>：① 订单中心与「已购」分离 — 查售后/退款进度。② 待付款可取消，已付款走退款申请。",
        "m12": "<b>先记住两句话</b>：① 详情页聚合退款/开票/领权状态。② 抖店单可能显示待领权引导 M14。",
        "m13": "<b>先记住两句话</b>：① 仅<strong>已付款</strong>订单可申请开票。② 提交后商家在 A13 处理。",
        "m14": "<b>先记住两句话</b>：① 抖店链路①<strong>领权短信</strong>落地本页。② 绑定手机后写 buyer_id 并开通权益。",
    }
    chains = {
        "m02": "M02 浏览 → M03 详情 → M04 下单 → M05 支付 → M06 已购 → M07/M09/M10 履约。",
        "m03": "M02 → M03 →（未购）M04 → M05；（已购）M07 / M09 / M10；（试看）M08。",
        "m04": "M03 → M04 确认 → 微信支付 → M05 结果。",
        "m05": "M04 → M05 轮询 → M06 / M07 / M09 / M10 按类型分流。",
        "m06": "M05 成功 → M06 → M07 学课 / M09 资料 / M10 预约。",
        "m07": "M06 → M07 目录 → M08 播放（全片/试看）。",
        "m08": "M07 点课时 → M08 播放；试看结束 → M03 购买卡。",
        "m09": "M06 → M09 资料列表 → 下载/预览。",
        "m10": "M06 → M10 选时段 → 确认预约 → M10b 核销码（到店）。",
        "m11": "M11 列表 → M12 详情 → M12-A 退款 / M13 开票。",
        "m12": "M11 → M12 详情 → M12-A 退款弹窗 / M13 开票 / 链 M14 领权。",
        "m13": "M12 → M13 填抬头 → 商家 A13 开具 → M13b 查看。",
        "m14": "抖店 Webhook → 短信 → M14 领权 → M06 已购。",
    }
    ui_rows = {
        "m02": [("点商品卡", "商品卡", "M03 线框", "点击校验表"), ("排序/Chip", "筛选条", "本页", "点击校验表")],
        "m03": [("立即购买/去学习", "底栏主按钮", "M04/M07/M09/M10", "点击校验表"), ("试看", "目录行", "M08", "试看行")],
        "m04": [("确认支付", "底栏", "M05", "点击校验表")],
        "m05": [("查看已购/去学习", "结果页按钮", "M06/M07等", "点击校验表")],
        "m06": [("进履约", "已购卡", "M07/M09/M10", "点击校验表")],
        "m07": [("播放课时", "目录行", "M08", "点击校验表")],
        "m08": [("试看结束购买", "结束卡", "M03/M04", "点击校验表")],
        "m09": [("下载/预览", "文件行", "本页", "点击校验表")],
        "m10": [("确认预约", "底栏", "M10b/M11", "点击校验表")],
        "m11": [("进详情", "订单行", "M12", "点击校验表")],
        "m12": [("申请退款", "顶栏/底栏", "M12-A", "点击校验表"), ("申请开票", "顶栏", "M13", "点击校验表")],
        "m13": [("提交申请", "底栏", "—", "点击校验表")],
        "m14": [("绑定领权", "底栏", "M06", "点击校验表")],
    }

    for mid, note in notes.items():
        note_div = f'\n  <div class="note note-b" style="margin-bottom:10px">{note}</div>'
        text = insert_after_h2(mid, text, note_div)
        label = mid.upper()
        block = ui_table(label, ui_rows[mid]) + chain_op(chains[mid])
        text = insert_before_marker(text, f'  <h4 id="{mid}-select-spec"', block)
        if f'id="{mid}-select-spec"' not in text and f'id="{mid}b-select-spec"' in text:
            text = insert_before_marker(text, f'  <div class="op" style="font-size:12px;margin-top:12px" id="{mid}b-select-spec"', block)

    # M02 matrix: add 落点列
    text = text.replace(
        "<tr><th>商品状态（买家可见）</th><th>卡片/详情操作</th></tr>\n"
        "    <tr><td>在售 <code>on_sale</code></td><td>点卡进 M03 · 立即购买</td></tr>\n"
        "    <tr><td>已下架</td><td>列表不展示（或灰显不可点）</td></tr>",
        "<tr><th>状态</th><th>行内操作</th><th>落点页面</th></tr>\n"
        "    <tr><td>在售 <code>on_sale</code></td><td>点卡 · 立即购买</td><td><b>M03</b> → M04</td></tr>\n"
        "    <tr><td>已下架</td><td>灰显不可点</td><td>—</td></tr>",
        1,
    )

    f.write_text(text, encoding="utf-8")
    print("buyer: ok")


def patch_admin():
    f = MOD / "01-管理端UI.html"
    text = f.read_text(encoding="utf-8")

    pages = {
        "a01": {
            "note": "<b>先记住两句话</b>：① 看板指标卡可<strong>下钻</strong>到 A09/A13/A14 等待办列表。② 最近订单嵌表与 A09 同协议，点单号进 A10。",
            "ui": [("进订单详情", "最近订单行", "A10", "点击校验表"), ("待办下钻", "指标卡", "A09/A13/A14", "点击校验表")],
            "chain": "A01 看板 → 待办下钻 A09/A13/A14 → A10 详情；商品下架数 → A02 已下架 Tab。",
        },
        "a03": {
            "note": "<b>先记住两句话</b>：① 商品类型保存后<strong>锁定</strong>，课类须关联已发布专栏。② 「提交审核」≠「上架」— 须 P09 人审通过后再上架。",
            "ui": [("存草稿/提审/上架", "底栏按钮组", "A03 本页", "点击校验表"), ("类型卡片", "表单顶", "栏位显隐", "下拉规格表")],
            "chain": "A02 新建 → A03 编辑 → 提审 → P09 → approved → 上架 → A02 在售。",
            "matrix": """
  <h3>状态 × 操作矩阵</h3>
  <table class="meta matrix">
    <tr><th>状态</th><th>行内操作</th><th>落点页面</th><th>权限</th></tr>
    <tr><td>草稿</td><td>存草稿 · 提交审核</td><td>本页</td><td><code>shop.product.write</code></td></tr>
    <tr><td>审核中</td><td>只读查看</td><td>本页</td><td><code>shop.product.read</code></td></tr>
    <tr><td>已驳回</td><td>修改 · 重新提审</td><td>本页</td><td><code>shop.product.write</code></td></tr>
    <tr><td>已通过 approved</td><td>上架销售</td><td>→ A02 在售</td><td><code>shop.product.publish</code></td></tr>
    <tr><td>在售</td><td>改价/下架走变更</td><td>A02 行内</td><td><code>shop.product.write</code></td></tr>
  </table>
""",
        },
        "a05": {
            "note": "<b>先记住两句话</b>：① 课时「发布」后买家可见；试看仅已发布视频且≤3 节。② 拖拽排序影响 M07 目录顺序。",
            "ui": [("添加课时", "顶栏", "A05-A 抽屉", "点击校验表"), ("发布/下架", "行内", "A05-B 弹窗", "点击校验表")],
            "chain": "A04 → A05 课时 → 发布 → A03 关联专栏 → A02 提审上架 → 买家 M07。",
        },
        "a06": {
            "note": "<b>先记住两句话</b>：① 资料包是<strong>数字商品内容容器</strong>，买家在 M09 下载。② 文件须上传成功才可关联商品。",
            "ui": [("上传文件", "资料列表", "A06 本页", "点击校验表"), ("删除", "行内", "确认弹窗", "点击校验表")],
            "chain": "A06 上传资料 → A03 关联资料包 → A02 上架 → 买家 M09 领取。",
        },
        "a07": {
            "note": "<b>先记住两句话</b>：① 服务商品依赖<strong>开放时段</strong>，买家 M10 预约。② 次数卡与预约服务核销走 A08。",
            "ui": [("添加时段", "顶栏", "A07-A", "点击校验表"), ("编辑服务", "行内", "A07-B", "点击校验表")],
            "chain": "A07 配置服务/时段 → A03 服务商品 → M10 预约 → M10b 核销码 → A08 核销。",
        },
        "a08": {
            "note": "<b>先记住两句话</b>：① 核销扣减<strong>服务权益次数</strong>，与订单退款联动关权益。② Phase 1 不支持撤销核销。",
            "ui": [("查询", "输入区", "结果卡", "点击校验表"), ("确认核销", "结果卡", "本页刷新", "点击校验表")],
            "chain": "M10b 出示码 → A08 查询 → 确认核销 → A12 权益次数刷新。",
        },
        "a10": {
            "note": "<b>先记住两句话</b>：① 顶栏按钮随<strong>订单状态</strong>显隐（待付/已付/退款中/关闭）。② 抖店待领权显示重发短信链 M14。",
            "ui": [("退款", "顶栏/摘要", "A10-A", "点击校验表"), ("重发领权短信", "顶栏", "—", "点击校验表"), ("查看开票", "顶栏", "A13/M13", "点击校验表")],
            "chain": "A09 列表 → A10 详情 → A10-A 退款 → F2 关权益；抖店待领权 → 重发短信 → M14。",
            "matrix": """
  <h3>状态 × 操作矩阵</h3>
  <table class="meta matrix">
    <tr><th>状态</th><th>行内操作</th><th>落点页面</th><th>权限</th></tr>
    <tr><td>待付款</td><td>关闭订单</td><td>本页</td><td><code>shop.order.close</code></td></tr>
    <tr><td>已付款</td><td>退款 · 重发短信(抖店) · 查看开票</td><td>A10-A / M13</td><td><code>shop.order.refund</code> 等</td></tr>
    <tr><td>退款中</td><td>只读 · 进度条</td><td>本页</td><td><code>shop.order.view</code></td></tr>
    <tr><td>已关闭</td><td>只读</td><td>本页</td><td><code>shop.order.view</code></td></tr>
  </table>
""",
        },
        "a15": {
            "note": "<b>先记住两句话</b>：① 支付进件是<strong>商家级</strong>，旗下店铺共用商户号。② 与套餐 A18 分离 — 未进件无法收款但可申请入驻。",
            "ui": [("保存支付配置", "底栏", "A15 本页", "点击校验表"), ("短信/领权 Tab", "子 Tab", "同页下半", "点击校验表")],
            "chain": "入驻通过 → A15 进件 → 买家 M04 支付；抖店领权短信配置 → A09 重发。",
        },
        "a18": {
            "note": "<b>先记住两句话</b>：① 展示<strong>合并权益</strong>（主套餐+加购），驱动提审/短信/店铺数上限。② 升级引导链平台 P11 或管家续费。",
            "ui": [("升级套餐", "摘要区", "P11 / 联系管家", "点击校验表"), ("查看用量", "卡片", "本页", "点击校验表")],
            "chain": "P11 开通 → A18 核对权益 → A02/A17/A15 受配额约束。",
        },
        "a19": {
            "note": "<b>先记住两句话</b>：① 店铺级<strong>默认策略</strong>（退款/开票），新建商品可继承。② 不改历史已售订单策略。",
            "ui": [("保存策略", "底栏", "A19 本页", "点击校验表")],
            "chain": "A19 默认策略 → A03 新建商品默认带出 → M12 退款规则。",
        },
        "a16": {
            "note": "<b>先记住两句话</b>：① 商家端角色绑定<strong>内置模板</strong>，不可自建 role code。② 权限变更即时生效，无缓存会话特权。",
            "ui": [("添加成员", "顶栏", "A16-A", "点击校验表"), ("编辑权限", "行内", "A16-B", "点击校验表")],
            "chain": "A16 成员与角色 → 各 A* 页按钮显隐；对标平台 P08。",
        },
        "a20": {
            "note": "<b>先记住两句话</b>：① 企业 admin <strong>自申入驻</strong>，栏位与 P02-A 同源按主体显隐。② 提交后进 P03 待审，通过后 A17 建店。",
            "ui": [("提交入驻", "表单底栏", "A20-P 待审", "点击校验表"), ("修改重提", "驳回卡", "A20-R", "点击校验表")],
            "chain": "注册/Dashboard → A20 申请 → P03 审核 → A17 首店 → A02 上架。",
        },
        "a21": {
            "note": "<b>先记住两句话</b>：① <strong>注册智营</strong> ≠ 商城入驻 — 须另走 A20。② 本页仅账号与店铺入口导航。",
            "ui": [("开通商城", "页脚/侧栏", "A20", "点击校验表"), ("进入商家端", "顶栏", "A01", "—")],
            "chain": "M01/注册 → A21 引导 → A20 入驻 或 已入驻 → A01。",
        },
        "a22": {
            "note": "<b>先记住两句话</b>：① 店员账号仅<strong>核销/只读</strong>等受限模板，无商品写权限。② 登录壳对标 A08-C 简化侧栏。",
            "ui": [("核销", "侧栏", "A08", "点击校验表"), ("查看订单", "侧栏", "A09 只读", "权限码")],
            "chain": "A16 店员角色 → A22 壳 → A08 核销 / A09 只读。",
        },
    }

    for pid, data in pages.items():
        note_div = f'\n  <div class="note note-b" style="margin-bottom:10px">{data["note"]}</div>'
        text = insert_after_h2(pid, text, note_div)
        label = pid.upper()
        block = ""
        if "matrix" in data:
            block += data["matrix"]
        block += ui_table(label, data["ui"]) + chain_op(data["chain"])
        marker = f'  <h4 id="{pid}-select-spec"'
        if marker in text:
            text = insert_before_marker(text, marker, block)
        elif f'id="{pid}-select-spec"' in text:
            # a08 uses div op for select-spec
            text = insert_before_marker(
                text,
                f'  <div class="op" style="font-size:12px;margin-top:12px" id="{pid}-select-spec"',
                block,
            )

    # A05 matrix: add 落点列
    text = text.replace(
        "<tr><th>课时状态</th><th>行内操作</th><th>权限</th></tr>",
        "<tr><th>状态</th><th>行内操作</th><th>落点页面</th><th>权限</th></tr>",
        1,
    )
    text = re.sub(
        r"(<tr><td><span class=\"badge b-gy\">草稿</span></td><td>编辑 · <b>发布</b> · 删除</td><td>)",
        r"<tr><td><span class=\"badge b-gy\">草稿</span></td><td>编辑 · <b>发布</b> · 删除</td><td>A05-A / A05-B</td><td>",
        text,
        count=1,
    )
    text = re.sub(
        r"(<tr><td><span class=\"badge b-g\">已发布</span></td><td>编辑 · 设试看/取消试看 · <b>下架</b></td><td>)",
        r"<tr><td><span class=\"badge b-g\">已发布</span></td><td>编辑 · 设试看/取消试看 · <b>下架</b></td><td>A05-A</td><td>",
        text,
        count=1,
    )

    # A01 chain if UI exists but no chain
    if "操作链路小结" not in text[text.find('id="a01"'):text.find('id="a02"')]:
        text = insert_before_marker(
            text,
            '  <h4 id="a01-select-spec"',
            chain_op(pages["a01"]["chain"]),
        )

    f.write_text(text, encoding="utf-8")
    print("admin: ok")


def patch_platform():
    f = MOD / "06-平台端UI.html"
    text = f.read_text(encoding="utf-8")

    # P09 note-b + quick tabs + expanded adv filter + chain
    if "id=\"p09\"" in text and "P09 先记住" not in text:
        text = insert_after_h2(
            "p09",
            text,
            '\n  <div class="note note-b" style="margin-bottom:10px">'
            "<b>先记住两句话</b>：① 虚拟商品<strong>上架前人审</strong>，机审 reject 须人工复核。② 强制下架联动 P07 违规与 A14 公域阻断。</div>",
        )

    p09_tabs = """
<div style="display:flex;gap:0;margin-bottom:12px;font-size:13px;border-bottom:1px solid var(--color-border);flex-wrap:wrap">
  <div style="padding:8px 14px;border-bottom:2px solid var(--color-primary);color:var(--color-primary);font-weight:700">待审队列 <span class="badge b-p">12</span></div>
  <div style="padding:8px 14px;color:#666">机审 flagged <span class="badge b-o">3</span></div>
  <div style="padding:8px 14px;color:#666">已售出队 <span class="badge b-gy">5</span></div>
</div>
"""
    if "待审队列" not in text[text.find('id="p09"'):text.find('id="p09-main-select-spec"')]:
        text = text.replace(
            '<article class="page" id="p09">\n<div class="doc">\n  <h2>P09 商品合规审核',
            '<article class="page" id="p09">\n<div class="doc">\n  <h2>P09 商品合规审核',
            1,
        )
        # insert tabs after sub paragraph
        text = re.sub(
            r'(id="p09">.*?<p class="sub">.*?</p>)',
            r"\1\n" + p09_tabs,
            text,
            count=1,
            flags=re.DOTALL,
        )

    text = text.replace(
        '<span class="btn-f adv">高级筛选</span>\n    </div>\n    <div class="crm-toolbar-right">\n      <span class="btn-f">列设置</span>\n    </div>\n  </div>\n  <div class="two" style="display:grid;grid-template-columns:1.1fr 0.9fr',
        '<span class="btn-f adv on">高级筛选 ▴</span>\n    </div>\n    <div class="crm-toolbar-right">\n      <span class="btn-f">列设置</span>\n    </div>\n  </div>\n  <div style="background:#e6f4ff;border:1px solid #91caff;border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:12px">\n  <div style="font-weight:600;color:var(--color-primary);margin-bottom:8px">高级筛选（已展开 · 对照 P02 走查样例）</div>\n  <span class="sel">提交时间 ▾</span> <span class="sel">商家套餐 ▾</span> <span class="sel">是否首单公域 ▾</span>\n  <span class="btn btn-p" style="margin-left:8px">查询</span> <span class="btn">重置</span>\n  </div>\n  <div class="two" style="display:grid;grid-template-columns:1.1fr 0.9fr',
        1,
    )

    p09_chain = chain_op(
        "商家 A02 提审 → P09 待审 → 通过 → 商家上架 · 驳回 → A03 修改；已售出队强制下架 → P09-B → A14 阻断。"
    )
    text = insert_before_marker(text, '  <h4 id="p09-main-select-spec"', p09_chain)

    # P04/P05/P07 note-b
    platform_notes = {
        "p04": "<b>先记住两句话</b>：① 类目费率影响<strong>平台抽成</strong>，禁用类目阻止新商品挂载。② 禁入启用须审批 P04-D。",
        "p05": "<b>先记住两句话</b>：① 清结算按<strong>结算周期</strong>聚合，待结算须人工确认打款。② 失败批次可重试 P05-C。",
        "p07": "<b>先记住两句话</b>：① 违规工单可<strong>强制下架</strong>商品并联动 P09。② 待处理优先展示高危举报。",
        "p11": "<b>先记住两句话</b>：① 套餐<strong>开通/续费/换档</strong>写商家权益，商家 A18 只读核对。② 续费待办与 P01 指标卡下钻联动。",
    }
    for pid, note in platform_notes.items():
        text = insert_after_h2(
            pid,
            text,
            f'\n  <div class="note note-b" style="margin-bottom:10px">{note}</div>',
        )

    f.write_text(text, encoding="utf-8")
    print("platform: ok")


def patch_prd_table():
    f = MOD / "PRD-内容获客商城-phase1.md"
    text = f.read_text(encoding="utf-8")

    new_table = """
| 页面 | 四张规格表 | note-b | 快捷 Tab | 高级筛选 ▴ | 链路小结 | 对照 P02 |
|------|------------|--------|----------|-------------|----------|----------|
| **P02** 商家租户 | ✅ | ✅ | ✅ | ✅ | ✅ | **金标准样例** |
| P01 看板 | ✅ | ✅ | — | — | ✅ | 已对照 |
| P03 入驻审核 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| P04 类目费率 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| P05 清结算 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| P06 对接配置 | ✅ | — | — | — | ✅ | 已对照 |
| P07 违规稽查 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| P08 账号角色 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| P09 商品审核 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| P10 套餐字典 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| P11 商家权益 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| **A01** 看板 | ✅ | ✅ | — | — | ✅ | 已对照 |
| **A02** 商品 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| A03 商品编辑 | ✅ | ✅ | — | — | ✅ | 已对照 |
| **A04** 专栏 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| A05 课时 | ✅ | ✅ | — | — | ✅ | 已对照 |
| A06 资料 | ✅ | ✅ | — | — | ✅ | 已对照 |
| A07 服务 | ✅ | ✅ | — | ✅ | ✅ | 已对照 |
| A08 核销 | ✅ | ✅ | — | — | ✅ | 已对照 |
| **A09** 订单 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| A10 订单详情 | ✅ | ✅ | — | — | ✅ | 已对照 |
| **A11** 买家 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| **A12** 权益 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| **A13** 开票 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| **A14** 公域 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| A15 支付进件 | ✅ | ✅ | Tab | — | ✅ | 已对照 |
| A16 成员角色 | ✅ | ✅ | — | — | ✅ | 已对照 |
| **A17** 店铺 | ✅ | ✅ | ✅ | ✅ | ✅ | 已对照 |
| A18 套餐权益 | ✅ | ✅ | — | — | ✅ | 已对照 |
| A19 店铺策略 | ✅ | ✅ | — | — | ✅ | 已对照 |
| A20 入驻申请 | ✅ | ✅ | — | — | ✅ | 已对照 |
| A21 引导页 | ✅ | ✅ | — | — | ✅ | 已对照 |
| A22 店员壳 | ✅ | ✅ | — | — | ✅ | 已对照 |
| M02–M14 买家 | ✅ | ✅ | Chip | — | ✅ | 已对照 |
| M00/M01/M15 总览 | 部分 | — | — | — | — | 导航/登录页简化 |
"""

    text = re.sub(
        r"\| 页面 \| 四张规格表.*?\n\| A12/A13 等 \| 部分.*?\n",
        new_table + "\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    # fix triple specs table header still says 三张
    text = text.replace(
        "**三张规格表**（操作页必备，样例见 P02）",
        "**四张规格表**（操作页必备，样例见 P02）",
        1,
    )

    f.write_text(text, encoding="utf-8")
    print("prd: ok")


if __name__ == "__main__":
    patch_buyer()
    patch_admin()
    patch_platform()
    patch_prd_table()
    print("all done")
