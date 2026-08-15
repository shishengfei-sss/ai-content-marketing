# -*- coding: utf-8 -*-
"""Patch 02-买家端UI.html M02-M14 with §2.5 P02-aligned blocks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "docs/01-PRD/21-内容获客商城-phase1/02-买家端UI.html"
text = FILE.read_text(encoding="utf-8")

NOTES = {
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

CHAINS = {
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

UI_ROWS = {
    "m02": [("点商品卡", "商品卡", "M03 线框", "点击校验表")],
    "m03": [("立即购买/去学习等", "底栏主按钮", "M04/M07/M09/M10", "点击校验表"), ("试看", "目录行", "M08", "试看行")],
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


def ui_block(mid: str) -> str:
    rows = UI_ROWS.get(mid, [])
    trs = "\n".join(
        f"    <tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>"
        for a, b, c, d in rows
    )
    label = mid.upper().replace("M", "M")
    return f"""
  <h4 style="font-size:13px;margin:16px 0 8px">操作按钮 · UI 线框覆盖（{label} 本页）</h4>
  <table class="meta matrix" style="margin-bottom:8px">
    <tr><th>操作</th><th>触发位置</th><th>UI 线框</th><th>点击校验</th></tr>
{trs}
  </table>
  <div class="op" style="margin-top:8px"><b>操作链路小结</b>：{CHAINS[mid]}</div>
"""


for mid, note in NOTES.items():
    marker = f'id="{mid}-select-spec"'
    if marker not in text:
        print(f"skip {mid}: no select-spec")
        continue
    block = ui_block(mid)
    if block.strip() in text:
        print(f"skip {mid}: already patched")
        continue
    text = text.replace(
        f'  <h4 id="{mid}-select-spec"',
        block + f'  <h4 id="{mid}-select-spec"',
        1,
    )
    # note-b after h2
    h2_pat = f'<h2>{mid.upper().replace("M", "M")}'
    # find article and h2 - use simpler: after first h2 in article
    art_start = text.find(f'id="{mid}"')
    if art_start == -1:
        continue
    h2_start = text.find("<h2>", art_start)
    h2_end = text.find("</h2>", h2_start) + 5
    snippet = text[h2_start:h2_end + 20]
    if "note note-b" not in snippet:
        insert = f'\n  <div class="note note-b" style="margin-bottom:10px">{note}</div>'
        text = text[:h2_end] + insert + text[h2_end:]

FILE.write_text(text, encoding="utf-8")
print("done")
