"""26 UX 全页走查：量测现网 token + 截图 + 自动打分底稿。

对照 docs/05-测试与验收/测试用例/内容获客商城-phase1/26-UX专家走查.md
输出：docs/05-测试与验收/验收报告/ux-shots-20260815/
Windows 上 browser.close() 可能挂起：截图与 metrics 落盘后即视为成功。
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.automated.ui.gold_live import admin_token, live_json, merchant_token  # noqa: E402
from tests.seed_shop_demo import BUYER_OPENID, CLAIM_TOKEN, seed  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "05-测试与验收" / "验收报告" / "ux-shots-20260815"
OUT.mkdir(parents=True, exist_ok=True)

WEB = "http://localhost:5173"
MP = "http://localhost:5174"
PLATFORM_PHONE = "13800000000"
PLATFORM_PASSWORD = "admin123456"
MERCHANT_PHONE = "13900000099"
MERCHANT_PASSWORD = "test123456"

JS_METRICS = """() => {
  const cs = getComputedStyle(document.documentElement);
  const header = document.querySelector('.app-header, .admin-header, header, .header, .hero, .nav');
  const aside = document.querySelector('.app-sidebar, .admin-sidebar, aside.admin-sidebar, .sidebar');
  const body = document.body.innerText || '';
  const primaryBtn = document.querySelector('.el-button--primary, .btn-primary, .primary');
  const tabbar = document.querySelector('.uni-tabbar, .tabbar, .bottom-nav');
  const hdr = header ? getComputedStyle(header).backgroundColor : null;
  return {
    tokenPrimary: cs.getPropertyValue('--color-primary').trim(),
    tokenHeader: cs.getPropertyValue('--header-height').trim(),
    tokenSidebar: cs.getPropertyValue('--sidebar-width').trim(),
    tokenFont: cs.getPropertyValue('--font-size-base').trim(),
    headerH: header ? Math.round(header.getBoundingClientRect().height) : null,
    sidebarW: aside ? Math.round(aside.getBoundingClientRect().width) : null,
    headerBg: hdr,
    primaryBg: primaryBtn ? getComputedStyle(primaryBtn).backgroundColor : null,
    hasTable: !!document.querySelector('.el-table'),
    hasPager: !!document.querySelector('.el-pagination'),
    hasEmpty: /暂无|空空|还没有/.test(body) || !!document.querySelector('.el-empty, .empty'),
    hasFilter: /筛选|搜索|导出|列设置/.test(body),
    hasTabbar: !!tabbar,
    bodyLen: body.replace(/\\s+/g, '').length,
    bodySnippet: body.replace(/\\s+/g, '').slice(0, 120),
    title: document.title,
    url: location.href,
  };
}"""


def _goto(page, url: str, wait_ms: int = 900) -> str | None:
    last = None
    for i in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(wait_ms)
            return None
        except Exception as e:
            last = e
            print("goto fail", i + 1, url, e, flush=True)
            page.wait_for_timeout(1800)
    return str(last) if last else "goto failed"


def _wait_shell(page, kind: str) -> None:
    sel = {
        "web-admin": ".admin-sidebar, .admin-header, aside, .el-table, .el-empty, .page-title",
        "web-merchant": ".app-sidebar, .app-header, header, .el-table, .el-form, .el-empty",
        "mp": ".uni-page-head, .uni-tabbar, .hero, .header, .page, uni-page-head, uni-page-body",
    }.get(kind, "body")
    try:
        page.wait_for_selector(sel, timeout=12000)
    except Exception:
        pass
    page.wait_for_timeout(400)


def _login_web(page, *, admin: bool, phone: str, password: str) -> None:
    url = f"{WEB}/admin/login" if admin else f"{WEB}/login"
    print("login", url, flush=True)
    err = _goto(page, url, wait_ms=500)
    if err:
        raise RuntimeError(err)
    seg = page.locator(".el-segmented__item", has_text="密码登录")
    if seg.count():
        seg.first.click()
    page.get_by_placeholder("请输入手机号").fill(phone)
    page.get_by_placeholder("请输入密码").fill(password)
    page.click('button:has-text("登录")')
    page.wait_for_timeout(1800)


def _blank_row(name: str, kind: str, is_list: bool, err: str) -> dict:
    return {
        "page": name,
        "file": f"{name}.png",
        "kind": kind,
        "isList": is_list,
        "headerH": None,
        "sidebarW": None,
        "tokenPrimary": "",
        "headerBg": None,
        "hasTable": False,
        "hasPager": False,
        "hasFilter": False,
        "hasEmpty": False,
        "hasTabbar": False,
        "bodyLen": 0,
        "url": "",
        "title": "",
        "navError": err,
    }


def _visit(page, slug: str, url: str, kind: str, is_list: bool) -> dict:
    print("goto", slug, url, flush=True)
    err = _goto(page, url)
    if err:
        return _blank_row(slug, kind, is_list, err)
    _wait_shell(page, kind)
    row = _shot(page, slug, kind, is_list)
    min_body = 8 if kind == "mp" else 40
    if int(row.get("bodyLen") or 0) < min_body:
        page.wait_for_timeout(1200)
        try:
            page.reload(wait_until="domcontentloaded", timeout=25000)
            _wait_shell(page, kind)
            row = _shot(page, slug, kind, is_list)
        except Exception as e:
            row["navError"] = f"reload: {e}"
        if int(row.get("bodyLen") or 0) < min_body:
            row["navError"] = row.get("navError") or "白屏或未加载"
    return row


def _shot(page, name: str, kind: str, is_list: bool) -> dict:
    page.wait_for_timeout(500)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    metrics = page.evaluate(JS_METRICS)
    metrics["file"] = path.name
    metrics["kind"] = kind
    metrics["isList"] = is_list
    metrics["page"] = name
    print("shot", name, "body", metrics.get("bodyLen"), "h", metrics.get("headerH"), flush=True)
    return metrics


def _inject_token(context, token: str) -> None:
    context.add_init_script(
        f"try {{ localStorage.setItem('token', {json.dumps(token)}); }} catch (e) {{}}"
    )


def _login_page(url: str) -> bool:
    u = (url or "").split("?")[0]
    return u.endswith("/login") or u.endswith("/admin/login") or "/admin/login" in u


def _score(row: dict) -> dict:
    url = row.get("url") or ""
    name = row.get("page") or ""
    kind = row.get("kind") or ""
    snippet = row.get("bodySnippet") or ""
    if _login_page(url) and name not in ("A21-login",):
        return {
            "cons": 0,
            "ux": 0,
            "vis": 0,
            "avg": 0,
            "block": "错页：掉登录",
            "ok": False,
        }
    min_len = 8 if kind == "mp" else 40
    blank = int(row.get("bodyLen") or 0) < min_len
    if blank:
        return {
            "cons": 0,
            "ux": 0,
            "vis": 0,
            "avg": 0,
            "block": row.get("navError") or "白屏或未加载",
            "ok": False,
        }
    cons = 2.0
    if kind == "web-admin":
        sw = row.get("sidebarW")
        if sw and abs(int(sw) - 220) > 12:
            cons = min(cons, 1.5)
    elif kind == "web-merchant":
        hh = row.get("headerH")
        sw = row.get("sidebarW")
        if hh and abs(int(hh) - 56) > 8:
            cons = min(cons, 1.5)
        if sw and abs(int(sw) - 200) > 16:
            cons = min(cons, 1.5)
        tp = (row.get("tokenPrimary") or "").lower()
        if tp and "1677ff" not in tp and tp not in ("#1677ff",):
            cons = min(cons, 1.5)
    elif kind == "mp":
        bg = (row.get("headerBg") or "").lower().replace(" ", "")
        dark = "10,22,40" in bg or "0a1628" in bg or bg in ("rgb(10,22,40)", "rgba(10,22,40,1)")
        cons = 2.0 if dark else 1.5
    ux = 2.0
    if row.get("isList"):
        if not (row.get("hasTable") or row.get("hasEmpty")):
            ux = min(ux, 1.5)
        if not row.get("hasFilter"):
            ux = min(ux, 1.5)
    vis = 2.0 if int(row.get("bodyLen") or 0) >= 80 else 1.5
    block = ""
    if "订单不存在" in snippet or "链接无效" in snippet:
        block = snippet[:40]
        vis = min(vis, 1.5)
    avg = round((cons + ux + vis) / 3, 1)
    return {
        "cons": cons,
        "ux": ux,
        "vis": vis,
        "avg": avg,
        "block": block,
        "ok": avg >= 1.5,
    }


def _first_id(items, *keys):
    if not items:
        return None
    it = items[0]
    for k in keys:
        if it.get(k):
            return str(it[k])
    return None


def _ids(demo: dict) -> dict:
    out = {
        "tenant_id": demo["tenant_id"],
        "shop_id": demo["shop_id"],
        "claim": CLAIM_TOKEN,
        "product_id": None,
        "order_id": None,
        "buyer_order_id": None,
        "column_id": None,
        "ent_course": None,
        "ent_digital": None,
        "ent_service": None,
    }
    try:
        tok = merchant_token()
        _, data = live_json("GET", "/shop/products?page=1&page_size=20", token=tok)
        items = (data or {}).get("items") or []
        out["product_id"] = _first_id(items, "id")
        _, data = live_json("GET", "/shop/orders?page=1&page_size=20", token=tok)
        items = (data or {}).get("items") or []
        out["order_id"] = _first_id(items, "id")
        _, data = live_json("GET", "/shop/columns?page=1&page_size=10", token=tok)
        items = (data or {}).get("items") or []
        out["column_id"] = _first_id(items, "id")
    except Exception as e:
        print("merchant ids fail", e, flush=True)
    try:
        code, auth = live_json(
            "POST",
            "/mp/shop/auth/login",
            body={"tenant_id": demo["tenant_id"], "code": f"mock:{BUYER_OPENID}"},
        )
        if code == 200:
            bt = auth.get("access_token")
            _, store = live_json("GET", f"/mp/shop/store?shop_id={demo['shop_id']}")
            prods = (store or {}).get("products") or []
            if prods:
                out["product_id"] = out["product_id"] or str(prods[0].get("id"))
            _, ents = live_json("GET", "/mp/shop/entitlements?page=1&page_size=50", token=bt)
            for it in (ents or {}).get("items") or []:
                if it.get("status") != "active":
                    continue
                pt = it.get("product_type")
                if pt == "course" and not out["ent_course"]:
                    out["ent_course"] = str(it["id"])
                if pt == "digital" and not out["ent_digital"]:
                    out["ent_digital"] = str(it["id"])
                if pt == "service" and not out["ent_service"]:
                    out["ent_service"] = str(it["id"])
            _, orders = live_json("GET", "/mp/shop/orders?page=1&page_size=20", token=bt)
            oitems = (orders or {}).get("items") or []
            if oitems:
                out["buyer_order_id"] = str(oitems[0].get("id"))
                out["order_id"] = out["order_id"] or out["buyer_order_id"]
    except Exception as e:
        print("buyer ids fail", e, flush=True)
    try:
        code, claim = live_json("GET", f"/mp/shop/claim/{CLAIM_TOKEN}")
        if code == 200 and (claim or {}).get("status") == "pending":
            out["claim"] = CLAIM_TOKEN
        else:
            print("claim token check", code, claim, flush=True)
    except Exception as e:
        print("claim check fail", e, flush=True)
    return out


def _safe_stop(browser) -> None:
    def _c():
        try:
            browser.close()
        except Exception:
            pass

    t = threading.Thread(target=_c, daemon=True)
    t.start()
    t.join(timeout=6)


def main() -> int:
    print("seed", flush=True)
    demo = seed(reset=False)
    ids = _ids(demo)
    qs = f"tenant_id={demo['tenant_id']}&openid={BUYER_OPENID}&shop_id={demo['shop_id']}"
    print("ids", {k: v for k, v in ids.items() if v}, flush=True)
    plat_tok = admin_token()
    merch_tok = merchant_token()
    print("tokens ok", flush=True)
    rows: list[dict] = []

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    try:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        _inject_token(ctx, plat_tok)
        page = ctx.new_page()
        page.set_default_timeout(18000)

        platform = [
            ("P01-dashboard", "/admin/shop/dashboard", False),
            ("P02-merchants", "/admin/shop/merchants", True),
            ("P03-onboarding", "/admin/shop/onboarding", True),
            ("P04-categories", "/admin/shop/categories", True),
            ("P05-settlements", "/admin/shop/settlements", True),
            ("P06-channels", "/admin/shop/channels", True),
            ("P07-moderation", "/admin/shop/moderation", True),
            ("P08-roles", "/admin/shop/roles-codes", False),
            ("P09-reviews", "/admin/shop/product-reviews", True),
            ("P10-plans", "/admin/shop/plans", True),
            ("P11-subs", "/admin/shop/subscriptions", True),
            ("P12-sms", "/admin/shop/sms", True),
        ]
        for slug, path, is_list in platform:
            rows.append(_visit(page, slug, f"{WEB}{path}", "web-admin", is_list))
            if slug == "P02-merchants":
                try:
                    btn = page.locator("button:has-text('帮客户开通商城')").first
                    if btn.count():
                        btn.click()
                        page.wait_for_timeout(500)
                        rows.append(_shot(page, "P02A-initiate", "web-admin", False))
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(300)
                    pause_btn = page.locator("button:has-text('暂停')").first
                    if pause_btn.count():
                        pause_btn.click()
                        page.wait_for_timeout(400)
                        rows.append(_shot(page, "P02C-suspend", "web-admin", False))
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(250)
                    close_btn = page.locator("button:has-text('清退')").first
                    if close_btn.count():
                        close_btn.click()
                        page.wait_for_timeout(400)
                        rows.append(_shot(page, "P02F-close", "web-admin", False))
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(250)
                except Exception as e:
                    print("p02 acf dialogs fail", e, flush=True)
                try:
                    tab = page.locator(".el-tabs__item", has_text="已暂停")
                    if tab.count():
                        tab.first.click()
                        page.wait_for_timeout(900)
                    resume_btn = page.locator("button:has-text('恢复')").first
                    if resume_btn.count():
                        resume_btn.click()
                        page.wait_for_timeout(400)
                        rows.append(_shot(page, "P02D-resume", "web-admin", False))
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(250)
                    else:
                        print("p02d: no resume button on suspended tab", flush=True)
                except Exception as e:
                    print("p02d fail", e, flush=True)

        rows.append(
            _visit(
                page,
                "P02B-detail",
                f"{WEB}/admin/shop/merchants/{ids['tenant_id']}",
                "web-admin",
                False,
            )
        )

        ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
        page2 = ctx2.new_page()
        page2.set_default_timeout(18000)
        rows.append(_visit(page2, "A21-login", f"{WEB}/login", "web-merchant", False))
        rows.append(_visit(page2, "A22-register", f"{WEB}/register", "web-merchant", False))
        ctx2.close()
        ctxm = browser.new_context(viewport={"width": 1440, "height": 900})
        _inject_token(ctxm, merch_tok)
        page2 = ctxm.new_page()
        page2.set_default_timeout(18000)

        merchant = [
            ("A01-overview", "/shop/overview", False),
            ("A02-products", "/shop/products", True),
            ("A03-new", "/shop/products/new", False),
            ("A04-columns", "/shop/columns", True),
            ("A06-packages", "/shop/digital-packages", True),
            ("A07-offers", "/shop/service-offers", True),
            ("A08-verify", "/shop/verifications", False),
            ("A08b-bookings", "/shop/bookings", True),
            ("A09-orders", "/shop/orders", True),
            ("A11-buyers", "/shop/buyers", True),
            ("A12-ents", "/shop/entitlements", True),
            ("A13-invoices", "/shop/invoices", True),
            ("A14-mappings", "/shop/channel-mappings", True),
            ("A15-payment", "/shop/payment", False),
            ("A15S-sms", "/shop/sms-settings", False),
            ("A16-roles", "/shop/roles-members", True),
            ("A17-stores", "/shop/stores", True),
            ("A18-plan", "/shop/subscription", False),
            ("A19-store", "/shop/store-settings", False),
            ("A20-onboarding", "/shop/onboarding", False),
            ("A23-channel", "/shop/channel-settings", False),
            ("ASET-settings", "/shop/settings", False),
        ]
        for slug, path, is_list in merchant:
            rows.append(_visit(page2, slug, f"{WEB}{path}", "web-merchant", is_list))
        if ids.get("product_id"):
            rows.append(
                _visit(
                    page2,
                    "A03-edit",
                    f"{WEB}/shop/products/{ids['product_id']}",
                    "web-merchant",
                    False,
                )
            )
        if ids.get("column_id"):
            rows.append(
                _visit(
                    page2,
                    "A05-lessons",
                    f"{WEB}/shop/columns/{ids['column_id']}",
                    "web-merchant",
                    False,
                )
            )
        if ids.get("order_id"):
            rows.append(
                _visit(
                    page2,
                    "A10-order",
                    f"{WEB}/shop/orders/{ids['order_id']}",
                    "web-merchant",
                    False,
                )
            )

        mctx = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        mp = mctx.new_page()
        mp.set_default_timeout(18000)
        mp_pages = [
            ("M02-home", f"/#/pages/shop/home?{qs}", False),
            ("M06-ents", f"/#/pages/shop/entitlements?{qs}", False),
            ("M11-orders", f"/#/pages/shop/orders?{qs}", False),
            ("M15-mine", f"/#/pages/shop/mine?{qs}", False),
            ("M-cs", f"/#/pages/shop/cs?{qs}", False),
            ("M-legal", f"/#/pages/shop/legal?{qs}", False),
        ]
        if ids.get("product_id"):
            mp_pages.append(
                ("M03-product", f"/#/pages/shop/product?id={ids['product_id']}&{qs}", False)
            )
            mp_pages.append(
                ("M04-checkout", f"/#/pages/shop/checkout?id={ids['product_id']}&{qs}", False)
            )
        oid = ids.get("buyer_order_id") or ids.get("order_id")
        if oid:
            mp_pages.append(
                ("M05-pay", f"/#/pages/shop/pay-result?id={oid}&{qs}", False)
            )
            mp_pages.append(
                ("M12-detail", f"/#/pages/shop/order-detail?id={oid}&{qs}", False)
            )
            mp_pages.append(
                ("M13-invoice", f"/#/pages/shop/invoice?id={oid}&{qs}", False)
            )
        if ids.get("ent_course"):
            mp_pages.append(
                ("M07-learn", f"/#/pages/shop/learn?entitlement_id={ids['ent_course']}&{qs}", False)
            )
        if ids.get("ent_digital"):
            mp_pages.append(
                (
                    "M09-materials",
                    f"/#/pages/shop/materials?entitlement_id={ids['ent_digital']}&{qs}",
                    False,
                )
            )
        if ids.get("ent_service"):
            mp_pages.append(
                (
                    "M10-booking",
                    f"/#/pages/shop/booking?entitlement_id={ids['ent_service']}&{qs}",
                    False,
                )
            )
            mp_pages.append(
                (
                    "M10b-code",
                    f"/#/pages/shop/verify-code?entitlement_id={ids['ent_service']}&{qs}",
                    False,
                )
            )
        for slug, path, is_list in mp_pages:
            rows.append(_visit(mp, slug, f"{MP}{path}", "mp", is_list))
        cctx = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        cp = cctx.new_page()
        cp.set_default_timeout(18000)
        rows.append(
            _visit(
                cp,
                "M14-claim",
                f"{MP}/#/pages/shop/claim?token={ids['claim']}&tenant_id={demo['tenant_id']}&shop_id={demo['shop_id']}",
                "mp",
                False,
            )
        )
    finally:
        scored = []
        for r in rows:
            s = _score(r)
            scored.append({**{k: r.get(k) for k in (
                "page", "file", "kind", "headerH", "sidebarW", "tokenPrimary",
                "headerBg", "hasTable", "hasPager", "hasFilter", "hasEmpty",
                "hasTabbar", "bodyLen", "bodySnippet", "url", "title", "navError",
            )}, **s})
        (OUT / "metrics.json").write_text(
            json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary = [{k: x.get(k) for k in ("page", "avg", "cons", "ux", "vis", "ok", "block", "bodyLen")} for x in scored]
        text = json.dumps(summary, ensure_ascii=True, indent=2)
        print(text, flush=True)
        print(f"wrote {OUT} n={len(scored)}", flush=True)
        _safe_stop(browser)
        def _stop():
            try:
                pw.stop()
            except Exception:
                pass
        t = threading.Thread(target=_stop, daemon=True)
        t.start()
        t.join(timeout=4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
