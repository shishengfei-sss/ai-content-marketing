#!/usr/bin/env python3
"""Apply audit report B1/B2 fixes to shop PRD HTML files."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "docs/01-PRD/21-内容获客商城-phase1"


def migrate_tabs(fname: str) -> None:
    p = BASE / fname
    text = p.read_text(encoding="utf-8")

    text = text.replace(".tabs{", ".pdoc-tabs{")
    text = text.replace(".tabs button{", ".pdoc-tabs button{")
    text = text.replace(".tabs button:hover", ".pdoc-tabs button:hover")
    text = text.replace(".tabs button.on", ".pdoc-tabs button.on")
    text = text.replace(".page{display:none}", ".pdoc-panel{display:none}")
    text = text.replace(".page.on{display:block}", ".pdoc-panel.on{display:block}")

    text = text.replace(
        'class="tabs" id="tabs"',
        'class="pdoc-tabs" id="tabs" role="tablist"',
    )
    text = text.replace("data-id=", "data-pdoc=")

    text = re.sub(r'<article class="page on"', '<article class="pdoc-panel on"', text)
    text = re.sub(r'<article class="page "', '<article class="pdoc-panel"', text)
    text = re.sub(r'<article class="page"', '<article class="pdoc-panel"', text)

    text = text.replace("querySelectorAll('.page')", "querySelectorAll('.pdoc-panel')")
    text = text.replace('button[data-id="', 'button[data-pdoc="')
    text = text.replace("getAttribute('data-id')", "getAttribute('data-pdoc')")
    text = text.replace("closest('button[data-id]')", "closest('button[data-pdoc]')")

    p.write_text(text, encoding="utf-8")
    print(f"migrated tabs: {fname}")


def patch_buyer_l1_l3() -> None:
    p = BASE / "02-买家端UI.html"
    text = p.read_text(encoding="utf-8")

    if "a.perm-link" not in text:
        text = text.replace(
            ".tag-g{background:#dcfce7;color:#166534}",
            ".tag-g{background:#dcfce7;color:#166534}\n"
            "a.perm-link{text-decoration:none}\n"
            "a.perm-link code{cursor:pointer}\n"
            "a.perm-link:hover code{text-decoration:underline;color:#0958d9}",
        )

    perm_default = (
        '<p class="sub">鉴权：买家 <code>mp session</code>（微信 openid）；'
        '与商家 <code>shop.*</code> 权限隔离 · '
        '<a href="05-角色权限.html#catalog" class="perm-link" title="查看权限说明">§六 权限说明</a></p>'
    )
    perm_login = (
        '<p class="sub">鉴权：<code>POST /mp/shop/auth/wx-login</code> 换取 session；'
        '买家无商家角色 · '
        '<a href="05-角色权限.html#catalog" class="perm-link" title="查看权限说明">§六 权限说明</a></p>'
    )
    perm_claim = (
        '<p class="sub">鉴权：领权 token + <code>mp session</code>；'
        '公域订单与买家身份绑定 · '
        '<a href="05-角色权限.html#catalog" class="perm-link" title="查看权限说明">§六 权限说明</a></p>'
    )

    pages = [
        ("m01", "P1-基础", perm_login),
        ("m02", "P1-07", perm_default),
        ("m03", "P0", perm_default),
        ("m04", "P1-07", perm_default),
        ("m05", "P1-07", perm_default),
        ("m06", "P1-09", perm_default),
        ("m07", "P1-10", perm_default),
        ("m08", "P1-10", perm_default),
        ("m09", "P1-03", perm_default),
        ("m10", "P1-04", perm_default),
        ("m10b", "P1-04", perm_default),
        ("m11", "P1-18", perm_default),
        ("m12", "P1-18", perm_default),
        ("m13", "P1-17", perm_default),
        ("m14", "P1-12", perm_claim),
        ("m15", "P1-基础", perm_default),
    ]

    for pid, tag, perm in pages:
        tag_cls = "tag-r" if tag in ("P0",) or tag.startswith("P1-") else "tag-b"
        tag_html = f' <span class="tag {tag_cls}">{tag}</span>'

        block_pat = re.compile(
            rf'(<article class="pdoc-panel[^"]*" id="{pid}">.*?<h2>)([^<]+)(</h2>)',
            re.DOTALL,
        )
        m = block_pat.search(text)
        if m and tag not in m.group(0):
            text = (
                text[: m.start()]
                + m.group(1)
                + m.group(2)
                + tag_html
                + m.group(3)
                + text[m.end() :]
            )

        block_pat2 = re.compile(
            rf'(<article class="pdoc-panel[^"]*" id="{pid}">.*?<h2>[^<]+(?:<span[^>]*>[^<]*</span>)?</h2>\s*)',
            re.DOTALL,
        )
        m2 = block_pat2.search(text)
        if m2 and "perm-link" not in m2.group(0):
            text = text[: m2.start()] + m2.group(1) + perm + "\n  " + text[m2.end() :]

    p.write_text(text, encoding="utf-8")
    print("patched buyer L1/L3")


def upgrade_buyer_tab_js() -> None:
    p = BASE / "02-买家端UI.html"
    text = p.read_text(encoding="utf-8")
    old_js = """<script>
(function(){
  var tabs=document.querySelectorAll('#tabs button'), pages=document.querySelectorAll('.pdoc-panel');
  tabs.forEach(function(btn){btn.onclick=function(){
    tabs.forEach(function(b){b.classList.remove('on')});pages.forEach(function(p){p.classList.remove('on')});
    btn.classList.add('on');document.getElementById(btn.getAttribute('data-pdoc')).classList.add('on');
    window.scrollTo({top:0,behavior:'smooth'});
  }});
})();
</script>"""
    new_js = """<script>
(function(){
  var tabsEl=document.getElementById('tabs');
  var tabs=tabsEl?tabsEl.querySelectorAll('button'):[];
  var pages=document.querySelectorAll('.pdoc-panel');
  function activate(target){
    if(!target)return false;
    var btn=tabsEl&&tabsEl.querySelector('button[data-pdoc="'+target+'"]');
    var page=document.getElementById(target);
    if(!btn||!page)return false;
    tabs.forEach(function(b){b.classList.toggle('on',b===btn);});
    pages.forEach(function(p){p.classList.toggle('on',p.id===target);});
    requestAnimationFrame(function(){
      var el=document.getElementById(target);
      if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
      else window.scrollTo({top:0,behavior:'smooth'});
    });
    return true;
  }
  if(tabsEl){
    tabsEl.addEventListener('click',function(e){
      var btn=e.target.closest('button[data-pdoc]');
      if(!btn)return;
      var id=btn.getAttribute('data-pdoc');
      activate(id);
      if(location.hash!=='#'+id) history.replaceState(null,'','#'+id);
    });
  }
  function fromHash(){
    var h=(location.hash||'').replace(/^#/,'');
    if(h&&activate(h)) return;
  }
  window.addEventListener('hashchange',fromHash);
  fromHash();
})();
</script>"""
    if old_js in text:
        text = text.replace(old_js, new_js)
        p.write_text(text, encoding="utf-8")
        print("upgraded buyer tab JS with hash routing")


def patch_index_screenshot_copy() -> None:
    p = BASE / "index.html"
    text = p.read_text(encoding="utf-8")
    old = (
        '<p class="section-sub">静态线框请打开上方链接交互切换 Tab；'
        "正式截图待 M1 联调后补入 <code>screenshots/</code></p>"
    )
    new = (
        '<p class="section-sub">静态线框请打开上方链接交互切换 Tab；'
        "部分页面截图见 <code>screenshots/</code>（"
        '<code>merchant-a01.png</code> · <code>buyer-m02.png</code> · <code>index.png</code>），'
        "其余页待 M1 联调后补全</p>"
    )
    if old in text:
        text = text.replace(old, new)
        p.write_text(text, encoding="utf-8")
        print("updated index screenshot copy")


def patch_readme_tab_note() -> None:
    p = BASE / "README.md"
    text = p.read_text(encoding="utf-8")
    old = "| Tab 机制 | 自研 `<div class=\"tabs\">` + `<article class=\"page\">`（非 `.pdoc-tabs`/`.pdoc-panel`） |"
    new = "| Tab 机制 | `.pdoc-tabs` + `.pdoc-panel`（与平台端 §2.5.1 L4 一致；买家端保留独立配色） |"
    if old in text:
        text = text.replace(old, new)
        p.write_text(text, encoding="utf-8")
        print("updated README tab note")


if __name__ == "__main__":
    migrate_tabs("01-管理端UI.html")
    migrate_tabs("02-买家端UI.html")
    patch_buyer_l1_l3()
    upgrade_buyer_tab_js()
    patch_index_screenshot_copy()
    patch_readme_tab_note()
