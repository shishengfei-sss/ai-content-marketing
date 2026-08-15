import sys, json
sys.path.insert(0, ".")
from helpers import register
from playwright.sync_api import sync_playwright
tok, phone, err = register("H5表单探针")
print("phone", phone, "err", err)

with sync_playwright() as p:
    b=p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
    pg=b.new_page()
    # login
    pg.goto("http://127.0.0.1:5174/#/",timeout=25000); pg.wait_for_timeout(3000)
    ins=pg.locator("input"); ins.nth(0).fill(phone); ins.nth(1).fill("Test@123456")
    pg.get_by_text("登录",exact=True).click(); pg.wait_for_timeout(3000)
    print("after login url:", pg.url)

    for route in ["pages/crm/lead-create","pages/create/create","pages/crm/customers","pages/crm/deals","pages/settings/tenant","pages/mine/mine","pages/todo/todo"]:
        pg.goto(f"http://127.0.0.1:5174/#/{route}",timeout=20000); pg.wait_for_timeout(2500)
        print(f"\n===== {route} =====")
        print("url:", pg.url)
        print("body head:", repr(pg.locator("body").inner_text()[:160]))
        inputs=pg.locator("input")
        print("input count:", inputs.count())
        for i in range(inputs.count()):
            e=inputs.nth(i)
            print(f"  in[{i}] type={e.get_attribute('type')!r} ph={e.get_attribute('placeholder')!r} name={e.get_attribute('name')!r} cls={e.get_attribute('class')!r}")
        # textarea
        tas=pg.locator("textarea")
        print("textarea count:", tas.count())
        for i in range(tas.count()):
            print(f"  ta[{i}] ph={tas.nth(i).get_attribute('placeholder')!r}")
        # buttons / clickable with 提交/保存/创建/发布
        for label in ["提交","保存","创建","发布","确定","下一步","退出","退出登录"]:
            n=pg.locator(f"text={label}").count()
            if n: print(f"  clickable '{label}' count={n}")
    b.close()
