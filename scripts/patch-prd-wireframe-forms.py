#!/usr/bin/env python3
"""Patch PRD wireframe HTML: wf-form structure, Chinese labels, required markers."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/01-PRD/21-内容获客商城-phase1"

WF_FORM_CSS = """
.wf-form{font-size:13px}
.wf-form .field{margin-bottom:10px}
.wf-form .field label{display:block;font-size:12px;color:#666;margin-bottom:4px;font-weight:500}
.wf-form .field label .req{color:var(--danger);margin-left:2px}
.wf-form .field .val,.wf-form .field .inp-line{min-height:28px;padding:6px 10px;border:1px solid var(--color-border);border-radius:6px;background:#fff;font-size:13px}
.wf-form .field .hint{font-size:11px;color:#999;margin-top:3px}
.wf-form .field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
"""

ADMIN_WF_CSS = """
.wf-form{font-size:13px}
.wf-form .field{margin-bottom:10px;background:transparent;border:0;padding:0;border-radius:0}
.wf-form .field label{display:block;font-size:12px;color:var(--color-text-secondary);margin-bottom:4px;font-weight:500}
.wf-form .field label .req{color:var(--danger);margin-left:2px}
.wf-form .field .val,.wf-form .field .inp-line{min-height:28px;padding:6px 10px;border:1px solid var(--color-border);border-radius:6px;background:#fff;font-size:13px}
.wf-form .field .hint{font-size:11px;color:#999;margin-top:3px}
.wf-form .field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
"""

BUYER_WF_CSS = """
.wf-form{font-size:13px}
.wf-form .field{margin-bottom:10px;background:transparent;border:0;padding:0;border-radius:0}
.wf-form .field label{display:block;font-size:11px;color:var(--muted);margin-bottom:3px;font-weight:500}
.wf-form .field label .req{color:var(--danger);margin-left:2px}
.wf-form .field .val,.wf-form .field .inp-line{min-height:28px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:#fff;font-size:13px}
.wf-form .field .hint{font-size:11px;color:#999;margin-top:3px}
.wf-form .field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
"""


def inject_css(content: str, css: str, marker: str = "</style>") -> str:
    if ".wf-form{" in content:
        return content
    return content.replace(marker, css + marker, 1)


def replace_between(content: str, start: str, end: str, new_block: str) -> str:
    i = content.find(start)
    if i < 0:
        print(f"  WARN: start not found: {start[:60]}...")
        return content
    j = content.find(end, i)
    if j < 0:
        print(f"  WARN: end not found after: {start[:60]}...")
        return content
    return content[:i] + new_block + content[j:]


def patch_platform(path: Path) -> int:
    c = path.read_text(encoding="utf-8")
    c = inject_css(c, WF_FORM_CSS)
    n = 0

    # Table headers
    hdr_repls = [
        ('<th class="sortable">tenant_id<span', '<th class="sortable">租户ID<span'),
        ('搜索商家名 / tenant_id', '搜索商家名 / 租户ID'),
        ('<th>slug</th>', '<th>店铺短码</th>'),
        ('<th class="sortable">功能 code<span', '<th class="sortable">编码<span'),
        ('<th>meter_key</th>', '<th>埋点标识</th>'),
        ('<td><b>max</b></td>', '<td>取最大值</td>'),
        ('<td><b>sum</b></td>', '<td>累加</td>'),
        ('aggregate_mode</code>（max/sum/any）', '叠加合并方式</code>（取最大值/累加/任一满足）'),
        ('status=rejected 时展示', '审核已驳回时展示'),
    ]
    for old, new in hdr_repls:
        if old in c:
            c = c.replace(old, new)
            n += 1

    blocks = {
        'p02a_form': (
            '    <div style="font-weight:600;margin-bottom:10px">发起入驻 · 运营代建</div>\n',
            '    <p style="margin-top:10px"><span class="btn btn-p">提交入驻申请</span>',
            '''    <div style="font-weight:600;margin-bottom:10px">发起入驻 · 运营代建</div>
    <div class="wf-form">
      <div class="field">
        <label>关联租户 <span class="req">*</span></label>
        <div class="val">搜索已有智营租户 ▾</div>
        <div class="hint">不可选已入驻或有待审单的租户</div>
      </div>
      <div class="field">
        <label>主体类型 <span class="req">*</span></label>
        <div class="val"><span style="color:var(--color-primary);font-weight:600">个人</span> / 个体工商户 / 企业 ▾</div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>主体名称 <span class="req">*</span></label>
          <div class="val">李老师</div>
          <div class="hint">个人=姓名；个体/企业=执照名；可 OCR 预填</div>
        </div>
        <div class="field">
          <label>商家展示名 <span class="req">*</span></label>
          <div class="val">李老师工作室</div>
          <div class="hint">默认=主体名，可改</div>
        </div>
      </div>
      <div class="field">
        <label>身份证号 <span class="req">*</span></label>
        <div class="val">440***********1234 <span class="badge b-b">OCR 已识别</span></div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>经营联系人 <span class="req">*</span></label>
          <div class="val">李老师</div>
        </div>
        <div class="field">
          <label>联系电话 <span class="req">*</span></label>
          <div class="val">138****8000</div>
          <div class="hint">用于通知补材料</div>
        </div>
      </div>
      <div class="field">
        <label>备注（选填）</label>
        <div class="val">线下已沟通，邀约补齐资质</div>
      </div>
      <div class="field" style="padding:10px;border:1px dashed #91caff;border-radius:6px;background:#fff">
        <label>材料上传（选填）</label>
        <div class="hint" style="margin-bottom:6px">留空由商家审核前补传</div>
        <div style="font-size:12px;margin-bottom:4px">身份证正面 <span class="btn" style="font-size:11px;padding:2px 8px">上传</span> <span class="badge b-g">OCR ✓ 姓名·证号</span></div>
        <div style="font-size:12px">身份证反面 <span class="btn" style="font-size:11px;padding:2px 8px">上传</span> <span class="badge b-g">OCR ✓ 有效期至 2035-06</span></div>
      </div>
    </div>
    <p style="margin-top:10px"><span class="btn btn-p">提交入驻申请</span>''',
        ),
        'p02c': (
            '<h3 id="p02c">P02-C · 暂停商家（确认弹窗）</h3>\n  <div style="border:1px solid #ffd591',
            '<p style="margin-top:10px"><span class="btn" style="background:var(--warn)',
            '''<h3 id="p02c">P02-C · 暂停商家（确认弹窗）</h3>
  <div style="border:1px solid #ffd591;border-radius:8px;padding:14px;margin-bottom:12px;background:#fffbe6;max-width:480px">
    <div style="font-weight:600;margin-bottom:8px;color:#ad6800">确认暂停「广州某某培训」？</div>
    <div class="wf-form">
      <div class="field"><label>影响说明（只读）</label><div class="val" style="background:#fafafa">商家端不可登录；旗下店铺强制不可营业；买家端展示「暂停营业」；进行中订单仍可履约/退款</div></div>
      <div class="field">
        <label>暂停原因 <span class="req">*</span></label>
        <div class="val">违规 / 欠费 / 商家申请 / 其他 ▾</div>
      </div>
      <div class="field">
        <label>说明 <span class="req">*</span></label>
        <div class="val inp-line">___________</div>
        <div class="hint">必填 ≥4 字</div>
      </div>
    </div>
    <p style="margin-top:10px"><span class="btn" style="background:var(--warn)''',
        ),
        'p10a': (
            '<h3 id="p10a">P10-A · 新增功能项（抽屉）</h3>\n  <div style="border:1px solid var(--color-border)',
            '<h3 id="p10b">P10-B',
            '''<h3 id="p10a">P10-A · 新增功能项（抽屉）</h3>
  <div style="border:1px solid var(--color-border);border-radius:8px;padding:14px;margin-bottom:12px;background:#fafafa;max-width:520px">
    <div style="font-weight:600;margin-bottom:10px">新增功能字典项</div>
    <div class="wf-form">
      <div class="field">
        <label>功能编码 <span class="req">*</span></label>
        <div class="val"><code>quota.xxx</code> ___________</div>
        <div class="hint">全局唯一，如 quota.max_products</div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>名称 <span class="req">*</span></label>
          <div class="val">___________</div>
        </div>
        <div class="field">
          <label>分类 <span class="req">*</span></label>
          <div class="val">配额 / 用量 / 渠道 ▾</div>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>数值类型 <span class="req">*</span></label>
          <div class="val">存量 int / 周期次数 / 开关 ▾</div>
        </div>
        <div class="field">
          <label>叠加合并方式 <span class="req">*</span></label>
          <div class="val">取最大值 / 累加 / 任一满足 ▾</div>
          <div class="hint"><code>aggregate_mode</code></div>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>统计周期</label>
          <div class="val">每日 / 每月 / — ▾</div>
          <div class="hint"><code>usage_period</code>；非周期型可留空</div>
        </div>
        <div class="field">
          <label>埋点标识（选填）</label>
          <div class="val">___________</div>
          <div class="hint"><code>meter_key</code></div>
        </div>
      </div>
      <div class="field">
        <label>说明（选填）</label>
        <div class="val">___________</div>
      </div>
      <div class="field">
        <label>默认启用</label>
        <div class="val">☑ 启用</div>
      </div>
    </div>
    <p style="margin-top:10px"><span class="btn btn-p">保存</span> <span class="btn">取消</span></p>
    <div class="note" style="margin-top:8px"><b>校验</b>：编码须符合命名规范且唯一；保存写 <code>shop_plan_features</code>，不影响已购 snapshot。</div>
  </div>

  <h3 id="p10b">P10-B''',
        ),
    }

    for key, (start, end, new) in blocks.items():
        before = c
        c = replace_between(c, start, end, new)
        if c != before:
            n += 1
            print(f"  platform: patched {key}")

    # P04-A through P04-B inline
    p04a_old = '''    <div class="op"><b>父类目</b>：根 / 职业培训 ▾（树形选择）</div>
    <div class="op"><b>类目名称</b>：___________ · <b>code</b>（唯一）：<code>cat.xxx</code> ___________</div>
    <div class="op"><b>平台费率</b>：____ % · <b>分账规则</b>：平台抽成 + 渠道费 ▾</div>
    <div class="op"><b>需资质</b>：☐ 办学许可证 ☐ ICP备案 ☐ 其他（多选）</div>
    <div class="op"><b>初始状态</b>：启用</div>'''
    p04a_new = '''    <div class="wf-form">
      <div class="field"><label>父类目 <span class="req">*</span></label><div class="val">根 / 职业培训 ▾</div><div class="hint">树形选择</div></div>
      <div class="field-row">
        <div class="field"><label>类目名称 <span class="req">*</span></label><div class="val">___________</div></div>
        <div class="field"><label>类目编码 <span class="req">*</span></label><div class="val"><code>cat.xxx</code> ___________</div><div class="hint">全局唯一</div></div>
      </div>
      <div class="field-row">
        <div class="field"><label>平台费率 <span class="req">*</span></label><div class="val">____ %</div></div>
        <div class="field"><label>分账规则 <span class="req">*</span></label><div class="val">平台抽成 + 渠道费 ▾</div></div>
      </div>
      <div class="field"><label>需资质（选填）</label><div class="val">☐ 办学许可证 ☐ ICP备案 ☐ 其他</div></div>
      <div class="field"><label>初始状态</label><div class="val">启用</div></div>
    </div>'''
    if p04a_old in c:
        c = c.replace(p04a_old, p04a_new)
        n += 1

    path.write_text(c, encoding="utf-8")
    return n


def patch_admin(path: Path) -> int:
    c = path.read_text(encoding="utf-8")
    c = inject_css(c, ADMIN_WF_CSS)
    n = 0

    repls = [
        ('<th>slug</th>', '<th>店铺短码</th>'),
        ('搜索店铺名 / slug', '搜索店铺名 / 店铺短码'),
        ('（status=rejected 时展示）', '（审核已驳回时展示）'),
        ('（status=published）：', '（已发布）：'),
    ]
    for old, new in repls:
        if old in c:
            c = c.replace(old, new)
            n += 1

    a17a_old = '''    <div class="op"><b>店铺名称</b> <span class="req">*</span>：___________<br><b>slug</b> <span class="req">*</span>：___________（全局唯一，小写英文）<br><b>简介</b>（选填）：___________</div>'''
    a17a_new = '''    <div class="wf-form">
      <div class="field"><label>店铺名称 <span class="req">*</span></label><div class="val">___________</div></div>
      <div class="field"><label>店铺短码 <span class="req">*</span></label><div class="val">___________</div><div class="hint">全局唯一，小写英文；字段 <code>slug</code></div></div>
      <div class="field"><label>简介（选填）</label><div class="val">___________</div></div>
    </div>'''
    if a17a_old in c:
        c = c.replace(a17a_old, a17a_new)
        n += 1

    a09b_old = '''    <div class="op"><b>退款金额</b>：¥199（可退上限 ¥199）<br><b>退款原因</b>（必填）：买家申请 / 错拍 / 其他 ▾ + 说明___________</div>'''
    a09b_new = '''    <div class="wf-form">
      <div class="field"><label>退款金额 <span class="req">*</span></label><div class="val">¥199.00</div><div class="hint">可退上限 ¥199</div></div>
      <div class="field"><label>退款原因 <span class="req">*</span></label><div class="val">买家申请 / 错拍 / 其他 ▾</div></div>
      <div class="field"><label>说明 <span class="req">*</span></label><div class="val inp-line">___________</div><div class="hint">必填 ≥4 字</div></div>
    </div>'''
    if a09b_old in c:
        c = c.replace(a09b_old, a09b_new)
        n += 1

    a10a_old = '''    <div class="op"><b>可退金额</b>：¥199.00（实付）<br><b>退款金额</b> <span class="req">*</span>：___________<br><b>退款原因</b> <span class="req">*</span>：买家申请 / 错拍 / 履约纠纷 / 其他 ▾<br><b>说明</b>：___________</div>'''
    a10a_new = '''    <div class="wf-form">
      <div class="field"><label>可退金额（只读）</label><div class="val" style="background:#fafafa">¥199.00（实付）</div></div>
      <div class="field"><label>退款金额 <span class="req">*</span></label><div class="val inp-line">___________</div></div>
      <div class="field"><label>退款原因 <span class="req">*</span></label><div class="val">买家申请 / 错拍 / 履约纠纷 / 其他 ▾</div></div>
      <div class="field"><label>说明（选填）</label><div class="val inp-line">___________</div></div>
    </div>'''
    if a10a_old in c:
        c = c.replace(a10a_old, a10a_new)
        n += 1

    a13a_old = '''    <div class="op"><b>驳回原因</b>（必填）：税号与抬头不匹配 / 金额有误 / 其他 ▾<br><b>说明</b>：___________</div>'''
    a13a_new = '''    <div class="wf-form">
      <div class="field"><label>驳回原因 <span class="req">*</span></label><div class="val">税号与抬头不匹配 / 金额有误 / 其他 ▾</div></div>
      <div class="field"><label>说明 <span class="req">*</span></label><div class="val inp-line">___________</div></div>
    </div>'''
    if a13a_old in c:
        c = c.replace(a13a_old, a13a_new)
        n += 1

    a14a_old = '''    <div class="op"><b>本地商品</b>：进阶成交课 ▾（仅已通过且可映射）<br><b>对接路径</b>：A 官方 API ▾<br><b>外部店铺</b>：已绑定抖店 xxx ▾</div>'''
    a14a_new = '''    <div class="wf-form">
      <div class="field"><label>本地商品 <span class="req">*</span></label><div class="val">进阶成交课 ▾</div><div class="hint">仅已通过且可映射</div></div>
      <div class="field"><label>对接路径 <span class="req">*</span></label><div class="val">A 官方 API ▾</div></div>
      <div class="field"><label>外部店铺 <span class="req">*</span></label><div class="val">已绑定抖店 xxx ▾</div></div>
    </div>'''
    if a14a_old in c:
        c = c.replace(a14a_old, a14a_new)
        n += 1

    a16a_inner = '''      <div style="font-size:12px;line-height:2">
        <div><b>选择成员</b>　<span class="sel" style="display:inline-block">搜索姓名 / 手机 ▾</span></div>
        <div><b>绑定角色</b>　<span class="sel" style="display:inline-block">内容运营 (shop_content) ▾</span></div>
        <div><b>店铺范围</b>　☑ 智学课堂　☐ 企业内训分店　☐ 全部店铺</div>
        <div style="font-size:11px;color:#ad6800;margin-top:6px">店员角色建议勾单店；企业管理员忽略店铺范围（全商家）。</div>
      </div>'''
    a16a_new = '''      <div class="wf-form">
        <div class="field"><label>选择成员 <span class="req">*</span></label><div class="val">搜索姓名 / 手机 ▾</div></div>
        <div class="field"><label>绑定角色 <span class="req">*</span></label><div class="val">内容运营 (shop_content) ▾</div></div>
        <div class="field"><label>店铺范围 <span class="req">*</span></label><div class="val">☑ 智学课堂　☐ 企业内训分店　☐ 全部店铺</div><div class="hint">店员角色建议勾单店；企业管理员忽略店铺范围（全商家）</div></div>
      </div>'''
    if a16a_inner in c:
        c = c.replace(a16a_inner, a16a_new)
        n += 1

    path.write_text(c, encoding="utf-8")
    return n


def patch_buyer(path: Path) -> int:
    c = path.read_text(encoding="utf-8")
    c = inject_css(c, BUYER_WF_CSS)
    n = 0

    m14_old = '<div class="field" style="margin:12px 0"><label>手机号</label><div class="val">授权 / 验证码</div></div>'
    m14_new = '<div class="field" style="margin:12px 0"><label>手机号 <span class="req">*</span></label><div class="val">授权 / 验证码</div><div class="hint" style="font-size:10px;color:#999;margin-top:2px">须与购买手机号一致</div></div>'
    if m14_old in c:
        c = c.replace(m14_old, m14_new)
        n += 1

    m15a_old = '''      <div class="op"><b>在线客服</b>：唤起小程序客服会话（若商家配置）</div>
      <div class="op"><b>电话</b>：400-xxx-xxxx（点击拨号）</div>
      <div class="op"><b>工作时间</b>：工作日 9:00–18:00</div>'''
    m15a_new = '''      <div class="wf-form">
        <div class="field"><label>在线客服</label><div class="val">唤起小程序客服会话（若商家配置）</div></div>
        <div class="field"><label>客服电话（只读）</label><div class="val">400-xxx-xxxx（点击拨号）</div></div>
        <div class="field"><label>工作时间（只读）</label><div class="val">工作日 9:00–18:00</div></div>
      </div>'''
    if m15a_old in c:
        c = c.replace(m15a_old, m15a_new)
        n += 1

    path.write_text(c, encoding="utf-8")
    return n


if __name__ == "__main__":
    total = 0
    print("06-平台端UI.html")
    total += patch_platform(BASE / "06-平台端UI.html")
    print("01-管理端UI.html")
    total += patch_admin(BASE / "01-管理端UI.html")
    print("02-买家端UI.html")
    total += patch_buyer(BASE / "02-买家端UI.html")
    print(f"Done. {total} patch groups applied.")
