"""统一测试运行器 — 运行所有基于测试用例文件的自动化测试。"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

API_ROOT = Path(__file__).resolve().parents[2]
AUTOMATED_DIR = Path(__file__).resolve().parent

# 确保 FORCE_FAKE_PLATFORM_LLM 开启
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"

TEST_GROUPS = [
    ("认证API (API-AUTH-001~005)", "test_auth.py"),
    ("CRM API (API-CRM-001~005)", "api/test_crm.py"),
    ("安全测试 (SEC-001~005)", "api/test_security.py"),
    ("内容/Agent API (API-CT/AG-001~004)", "api/test_content_agent.py"),
    ("CRM UI-线索 (LEAD-001~005)", "ui/test_ui_crm_leads.py"),
    ("CRM UI-客户 (CUST-001~005)", "ui/test_ui_crm_customers.py"),
    ("CRM UI-商机 (DEAL-001~011)", "ui/test_ui_crm_deals.py"),
    ("CRM UI-报价 (QUOTE-001~007)", "ui/test_ui_crm_quotes.py"),
    ("CRM UI-合同/订单 (CONT/ORDER)", "ui/test_ui_crm_contracts_orders.py"),
    ("CRM UI-产品/任务/活动 (PROD/TASK/CAMP)", "ui/test_ui_crm_products_tasks.py"),
    ("CRM UI-补充A (DEAL/QUOTE/LEAD缺失)", "ui/test_ui_crm_extra_a.py"),
    ("CRM UI-补充B (CONT/ORDER缺失)", "ui/test_ui_crm_extra_b.py"),
    ("CRM UI-补充C (PROD/TASK/ACT/CAMP缺失)", "ui/test_ui_crm_extra_c.py"),
    ("CRM UI-系统设置 (SET-001~013)", "ui/test_ui_settings.py"),
    ("CRM UI-平台管理 (ADMIN-001~008)", "ui/test_ui_admin.py"),
    ("CRM UI-数据权限 (PERM-001~006)", "ui/test_ui_permissions.py"),
    ("回归测试 (REG-001~015)", "ui/test_ui_regression.py"),
    ("性能测试 (PERF-001~004)", "ui/test_ui_performance.py"),
    ("H5移动端 (H5-AUTH~SET)", "ui/test_ui_h5.py"),
]

REPORT_PATH = AUTOMATED_DIR / "test_report.json"
REPORT_HTML = AUTOMATED_DIR / "test_report.html"


def run_pytest(test_path: str, verbose: bool = False) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pytest", str(test_path), "-v" if verbose else "-q", "--tb=short"]
    r = subprocess.run(cmd, cwd=API_ROOT, capture_output=True, text=True, timeout=120)
    return r.returncode == 0, r.stdout + r.stderr


def generate_html_report(results: list[dict]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed
    rows = ""
    for r in results:
        cls = "pass" if r["ok"] else "fail"
        rows += f'<tr class="{cls}"><td>{r["group"]}</td><td>{r["file"]}</td><td class="{cls}">{"PASS" if r["ok"] else "FAIL"}</td><td>{r.get("output", "")[:200]}</td></tr>\n'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>自动化测试报告</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f5f7fa; }}
h1 {{ color: #1a1a2e; }}
.summary {{ display: flex; gap: 20px; margin: 20px 0; }}
.card {{ padding: 20px; border-radius: 8px; min-width: 120px; text-align: center; }}
.card.total {{ background: #e3f2fd; color: #1565c0; }}
.card.pass {{ background: #e8f5e9; color: #2e7d32; }}
.card.fail {{ background: #ffebee; color: #c62828; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th {{ background: #1a1a2e; color: white; padding: 12px; text-align: left; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
tr:nth-child(even) {{ background: #fafafa; }}
.pass {{ color: #2e7d32; }} .fail {{ color: #c62828; font-weight: bold; }}
.footer {{ margin-top: 20px; color: #888; font-size: 12px; }}
</style></head><body>
<h1>AI内容营销系统 — 自动化测试报告</h1>
<p>生成时间: {ts}</p>
<div class="summary">
  <div class="card total"><div style="font-size:32px">{total}</div><div>总计</div></div>
  <div class="card pass"><div style="font-size:32px">{passed}</div><div>通过</div></div>
  <div class="card fail"><div style="font-size:32px">{failed}</div><div>失败</div></div>
</div>
<table><tr><th>测试组</th><th>测试文件</th><th>状态</th><th>输出摘要</th></tr>
{rows}</table>
<div class="footer">基于 AI内容营销系统-测试用例.xlsx 自动生成</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="自动化测试运行器")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--html", action="store_true", help="生成HTML报告")
    parser.add_argument("--group", "-g", choices=[g[0] for g in TEST_GROUPS] + ["all"], default="all", help="运行指定测试组")
    args = parser.parse_args()

    results: list[dict] = []
    groups = TEST_GROUPS if args.group == "all" else [(g[0], g[1]) for g in TEST_GROUPS if g[0] == args.group]

    print(f"\n{'='*60}")
    print(f"  AI内容营销系统 — 自动化测试")
    print(f"  {'='*60}\n")

    for group_name, test_file in groups:
        test_path = AUTOMATED_DIR / test_file
        print(f"▶ {group_name}")
        ok, output = run_pytest(test_path, verbose=args.verbose)
        results.append({"group": group_name, "file": test_file, "ok": ok, "output": output.strip()})
        print(f"  {'[PASS]' if ok else '[FAIL]'} {group_name}\n")

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed
    print(f"{'='*60}")
    print(f"  结果: {passed}/{total} 通过, {failed} 失败")
    print(f"{'='*60}\n")

    # 生成 HTML 报告
    if args.html:
        html = generate_html_report(results)
        REPORT_HTML.write_text(html, encoding="utf-8")
        print(f"  HTML报告已生成: {REPORT_HTML}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
