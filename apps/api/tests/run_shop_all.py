#!/usr/bin/env python3
"""商城全量测试运行器 — 7 轮验收。

轮次:
    1. 后端 API 验收     (verify_shop_m0 ~ m8)
    2. Web 端 UI 测试    (Playwright)
    3. 小程序 UI 测试    (Playwright Mobile)
    4. E2E 集成流程      (F0-F12)
    5. Mock 外部集成      (微信支付 + 抖音 + 短信)
    6. 安全 & PII 测试
    7. 回归测试          (CRM + Agent + M0)

用法:
    python run_shop_all.py                     # 全部 7 轮
    python run_shop_all.py --round 1           # 仅 Round 1
    python run_shop_all.py --through M6        # Round 1 截断到 M6
    python run_shop_all.py --round 1 --through M4
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any

# ── 路径常量 ──────────────────────────────────────────────────────

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
PY = sys.executable

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# ── 环境变量（必须在 import app / http_client 之前设置）──────────

os.environ["VERIFY_LIVE_API"] = "0"
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

# ── 导入测试配置（纯 Python，无 app 依赖）────────────────────────

from tests.shop_test_config import (  # noqa: E402
    MILESTONE_ORDER,
    ROUND_NAMES,
    get_round_steps,
    get_stub_env_vars,
    total_test_count,
)

# 注入 Stub 环境变量
for _k, _v in get_stub_env_vars().items():
    os.environ.setdefault(_k, _v)

# ── 导入 HTTP 客户端（依赖 app，须在 env 设置后）─────────────────

from tests.http_client import (  # noqa: E402
    check,
    clear_sms_rate_limits,
    req,
    reset_all_tenant_quotas,
    reset_test_client,
)

REPORT_PATH = ROOT / "shop_test_report.json"
SEP = "=" * 60
SUBPROCESS_TIMEOUT = 300  # 单脚本默认超时 5 分钟
PYTEST_TIMEOUT = 600      # Playwright 单文件最多 10 分钟
# CRM / Agent 全量回归输出量大，且 Windows 管道缓冲会死锁；单独加长超时
LONG_STEP_TIMEOUT = {
    "run_crm_all.py": 1200,
    "run_agent_a_c.py": 1800,
}


# ── 结果数据类 ────────────────────────────────────────────────────

@dataclass
class TestCaseResult:
    """单个测试用例执行结果。"""

    test_id: str
    name: str
    status: str  # PASS / FAIL / SKIP / ERROR
    detail: str = ""
    duration_sec: float = 0.0


@dataclass
class StepResult:
    """单个步骤（脚本）执行结果。"""

    name: str
    script: str
    milestone: str | None
    passed: bool
    duration_sec: float
    test_cases: list[TestCaseResult] = field(default_factory=list)
    output_tail: str = ""


@dataclass
class RoundResult:
    """单轮执行结果。"""

    round: int
    name: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(s.test_cases) for s in self.steps)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.steps for tc in s.test_cases if tc.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(
            1
            for s in self.steps
            for tc in s.test_cases
            if tc.status in ("FAIL", "ERROR")
        )

    @property
    def skipped(self) -> int:
        return sum(1 for s in self.steps for tc in s.test_cases if tc.status == "SKIP")


# ── 输出解析 ──────────────────────────────────────────────────────

# 匹配 verify 脚本中 check() 函数的输出：[PASS] name — detail
_CHECK_RE = re.compile(
    r"^\[(PASS|FAIL|SKIP|ERROR)\]\s*(.+?)(?:\s*[—–\-]\s*(.*))?$"
)

# 匹配 pytest -v 输出：PASSED test_file::test_name
_PYTEST_RE = re.compile(
    r"^(PASSED|FAILED|SKIPPED|ERROR)\s+(.+)$"
)

# 匹配 pytest 汇总行：15 passed, 2 failed in 3.45s
_PYTEST_SUMMARY_RE = re.compile(
    r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?(?:.*?(\d+)\s+skipped)?"
)


def parse_check_output(output: str) -> list[TestCaseResult]:
    """解析 verify 脚本输出中的 ``[PASS]`` / ``[FAIL]`` 行。

    verify 脚本通过 ``tests.http_client.check()`` 打印格式：
    ``[PASS] 用例名 — 详情``  或  ``[FAIL] 用例名 — 详情``
    """
    results: list[TestCaseResult] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _CHECK_RE.match(line)
        if m:
            status = m.group(1)
            name = m.group(2).strip()
            detail = (m.group(3) or "").strip()
            results.append(
                TestCaseResult(test_id="", name=name, status=status, detail=detail)
            )
    return results


def parse_pytest_output(output: str) -> list[TestCaseResult]:
    """解析 pytest ``-v`` 输出中的测试结果行。"""
    results: list[TestCaseResult] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _PYTEST_RE.match(line)
        if m:
            raw_status = m.group(1)
            name = m.group(2).strip()
            status_map = {
                "PASSED": "PASS",
                "FAILED": "FAIL",
                "SKIPPED": "SKIP",
                "ERROR": "ERROR",
            }
            results.append(
                TestCaseResult(test_id="", name=name, status=status_map[raw_status])
            )
    return results


# ── 执行函数 ──────────────────────────────────────────────────────

def _truncate(text: str, max_len: int = 800) -> str:
    """截断输出尾部，保留最后 *max_len* 个字符。"""
    if len(text) <= max_len:
        return text
    return "..." + text[-max_len:]


def _step_timeout(script: str, default: int) -> int:
    return LONG_STEP_TIMEOUT.get(Path(script).name, default)


def _kill_process_tree(pid: int) -> None:
    """杀掉子进程整树。Windows 上 TimeoutExpired 不会清掉孙进程。"""
    if pid <= 0:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def _print_line(line: str) -> None:
    try:
        print(line, end="", flush=True)
    except UnicodeEncodeError:
        print(
            line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"),
            end="",
            flush=True,
        )


def _run_streaming(
    cmd: list[str],
    timeout: int,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str, bool]:
    """流式读 stdout，避免 Windows 管道死锁；超时则杀进程树。

    返回 ``(returncode, output, timed_out)``。
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        cmd,
        cwd=API_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )
    chunks: list[str] = []
    q: Queue[str | None] = Queue()

    def _reader() -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                q.put(line)
        finally:
            q.put(None)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    t0 = time.monotonic()
    timed_out = False
    while True:
        remaining = timeout - (time.monotonic() - t0)
        if remaining <= 0:
            timed_out = True
            break
        try:
            line = q.get(timeout=min(1.0, remaining))
        except Empty:
            if proc.poll() is not None and q.empty():
                break
            continue
        if line is None:
            break
        chunks.append(line)
        _print_line(line)

    if timed_out:
        _kill_process_tree(proc.pid)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        return -1, "".join(chunks), True

    rc = proc.wait(timeout=30)
    while True:
        try:
            line = q.get_nowait()
        except Empty:
            break
        if line is None:
            break
        chunks.append(line)
        _print_line(line)
    return rc, "".join(chunks), False


def run_subprocess_step(step_name: str, script: str, milestone: str | None) -> StepResult:
    """以子进程运行单个 verify 脚本（流式输出，避免管道死锁）。"""
    script_path = ROOT / script
    t0 = time.monotonic()

    if not script_path.is_file():
        duration = time.monotonic() - t0
        print(f"  [SKIP] {step_name}: 脚本未创建 — {script}")
        return StepResult(
            name=step_name,
            script=script,
            milestone=milestone,
            passed=False,
            duration_sec=duration,
            test_cases=[
                TestCaseResult(
                    test_id="",
                    name=step_name,
                    status="SKIP",
                    detail=f"脚本未创建: {script}",
                )
            ],
        )

    timeout = _step_timeout(script, SUBPROCESS_TIMEOUT)
    extra_env = {}
    # Round 7 另有独立 Agent 步骤；CRM FINAL 再嵌套 run_agent_a_c 会每步重跑 M0-M8
    if Path(script).name == "run_crm_all.py":
        extra_env["VERIFY_SKIP_AGENT"] = "1"
    rc, output, timed_out = _run_streaming([PY, "-B", str(script_path)], timeout, extra_env)
    duration = time.monotonic() - t0

    if timed_out:
        print(f"  [ERROR] {step_name}: 超时 ({timeout}s)")
        return StepResult(
            name=step_name,
            script=script,
            milestone=milestone,
            passed=False,
            duration_sec=duration,
            test_cases=[
                TestCaseResult(
                    test_id="",
                    name=step_name,
                    status="ERROR",
                    detail=f"超时 ({timeout}s)",
                )
            ],
            output_tail=_truncate(output),
        )

    tc_results = parse_check_output(output)
    if not tc_results:
        tc_results = [
            TestCaseResult(
                test_id="",
                name=step_name,
                status="PASS" if rc == 0 else "FAIL",
                detail=f"exit_code={rc}",
            )
        ]

    return StepResult(
        name=step_name,
        script=script,
        milestone=milestone,
        passed=rc == 0,
        duration_sec=duration,
        test_cases=tc_results,
        output_tail=_truncate(output),
    )


def run_pytest_step(step_name: str, script: str, milestone: str | None) -> StepResult:
    """以 pytest 运行 UI 测试文件。

    遵循 run_automated.py 的模式：
    ``subprocess.run([PY, "-m", "pytest", path, "-v", "--tb=short"], cwd=API_ROOT)``
    """
    script_path = ROOT / script
    t0 = time.monotonic()

    if not script_path.is_file():
        duration = time.monotonic() - t0
        print(f"  [SKIP] {step_name}: 测试文件未创建 — {script}")
        return StepResult(
            name=step_name,
            script=script,
            milestone=milestone,
            passed=False,
            duration_sec=duration,
            test_cases=[
                TestCaseResult(
                    test_id="",
                    name=step_name,
                    status="SKIP",
                    detail=f"测试文件未创建: {script}",
                )
            ],
        )

    cmd = [PY, "-m", "pytest", str(script_path), "-v", "--tb=short", "-q"]
    timeout = _step_timeout(script, PYTEST_TIMEOUT)
    rc, output, timed_out = _run_streaming(cmd, timeout)
    duration = time.monotonic() - t0

    if timed_out:
        print(f"  [ERROR] {step_name}: pytest 超时 ({timeout}s)")
        return StepResult(
            name=step_name,
            script=script,
            milestone=milestone,
            passed=False,
            duration_sec=duration,
            test_cases=[
                TestCaseResult(
                    test_id="",
                    name=step_name,
                    status="ERROR",
                    detail=f"pytest 超时 ({timeout}s)",
                )
            ],
            output_tail=_truncate(output),
        )

    tc_results = parse_pytest_output(output)

    if not tc_results:
        tc_results = [
            TestCaseResult(
                test_id="",
                name=step_name,
                status="PASS" if rc == 0 else "FAIL",
                detail=f"exit_code={rc}",
            )
        ]

    return StepResult(
        name=step_name,
        script=script,
        milestone=milestone,
        passed=rc == 0,
        duration_sec=duration,
        test_cases=tc_results,
        output_tail=_truncate(output),
    )


# ── 前置检查 ──────────────────────────────────────────────────────

def preflight_check() -> bool:
    """运行前环境检查：登录 + 平台 LLM 配置。

    使用 ``check()`` 和 ``req()`` 验证 TestClient 可用，
    确保 FakeLLM 已生效。
    """
    print(f"\n{SEP}")
    print("  前置检查 — 环境与登录")
    print(f"{SEP}")

    results: list[bool] = []

    # 登录租户管理员
    code, data = req("POST", "/auth/login", body={"phone": "13900000099", "password": "test123456"})
    results.append(check("PF-1 租户管理员登录", code == 200, str(code)))

    if code == 200:
        token = data.get("access_token", "")
        code2, me = req("GET", "/auth/me", token=token)
        results.append(
            check(
                "PF-2 /auth/me 响应正常",
                code2 == 200 and "permissions" in me,
                str(code2),
            )
        )

    # 登录平台管理员
    code, data = req("POST", "/auth/login", body={"phone": "13800000000", "password": "admin123456"})
    results.append(check("PF-3 平台管理员登录", code == 200, str(code)))

    ok = all(results)
    print(f"\n  前置检查: {'PASS' if ok else 'FAIL'}")
    return ok


# ── Round 执行 ────────────────────────────────────────────────────

def run_round(round_num: int, through: str | None = None) -> RoundResult:
    """执行指定 Round 的全部步骤。

    Args:
        round_num: Round 编号 (1-7)。
        through:   截断里程碑（仅 Round 1 生效）。
    """
    round_name = ROUND_NAMES.get(round_num, f"Round {round_num}")
    print(f"\n{SEP}")
    print(f"  {round_name}")
    print(f"{SEP}")

    steps = get_round_steps(round_num, through)
    result = RoundResult(round=round_num, name=round_name)

    # ── Round 前重置 ──
    if round_num == 1:
        reset_test_client()
        reset_all_tenant_quotas()
        clear_sms_rate_limits()
    elif round_num in (4, 5):
        clear_sms_rate_limits()
        reset_all_tenant_quotas()

    for step in steps:
        print(f"\n>>> {step.name} ({step.script})")

        if step.runner == "pytest":
            sr = run_pytest_step(step.name, step.script, step.milestone)
        else:
            sr = run_subprocess_step(step.name, step.script, step.milestone)

        result.steps.append(sr)

        # 步骤级汇总
        status = "PASS" if sr.passed else "FAIL"
        n_pass = sum(1 for tc in sr.test_cases if tc.status == "PASS")
        n_fail = sum(1 for tc in sr.test_cases if tc.status in ("FAIL", "ERROR"))
        n_skip = sum(1 for tc in sr.test_cases if tc.status == "SKIP")
        print(
            f"  [{status}] {step.name} — "
            f"{n_pass} pass / {n_fail} fail / {n_skip} skip, "
            f"{sr.duration_sec:.1f}s"
        )

        # Round 1 每步后重置 SMS 频控（同 run_m0_m8.py）
        if round_num == 1:
            clear_sms_rate_limits()

    # ── Round 汇总 ──
    print(
        f"\n  Round {round_num} 汇总: "
        f"{result.passed} pass / {result.failed} fail / {result.skipped} skip "
        f"(共 {result.total})"
    )

    return result


# ── JSON 报告 ─────────────────────────────────────────────────────

def generate_json_report(
    round_results: list[RoundResult],
    env: dict[str, str],
    through: str | None,
    only_round: int | None,
) -> None:
    """生成 JSON 测试报告，写入 ``shop_test_report.json``。"""
    total_cases = sum(r.total for r in round_results)
    total_passed = sum(r.passed for r in round_results)
    total_failed = sum(r.failed for r in round_results)
    total_skipped = sum(r.skipped for r in round_results)

    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "runner": "run_shop_all.py",
        "env": env,
        "filter": {
            "round": only_round,
            "through": through,
        },
        "summary": {
            "total_rounds": len(round_results),
            "total_steps": sum(len(r.steps) for r in round_results),
            "total_cases": total_cases,
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
            "pass_rate": f"{(total_passed / total_cases * 100):.1f}%"
            if total_cases
            else "0%",
        },
        "rounds": [],
    }

    for r in round_results:
        round_data: dict[str, Any] = {
            "round": r.round,
            "name": r.name,
            "summary": {
                "total": r.total,
                "passed": r.passed,
                "failed": r.failed,
                "skipped": r.skipped,
            },
            "steps": [],
        }
        for s in r.steps:
            step_data: dict[str, Any] = {
                "name": s.name,
                "script": s.script,
                "milestone": s.milestone,
                "passed": s.passed,
                "duration_sec": round(s.duration_sec, 2),
                "test_cases": [
                    {
                        "test_id": tc.test_id,
                        "name": tc.name,
                        "status": tc.status,
                        "detail": tc.detail,
                        "duration_sec": round(tc.duration_sec, 2),
                    }
                    for tc in s.test_cases
                ],
            }
            round_data["steps"].append(step_data)
        report["rounds"].append(round_data)

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  JSON 报告: {REPORT_PATH}")


# ── 汇总表 ────────────────────────────────────────────────────────

def print_summary_table(round_results: list[RoundResult]) -> None:
    """打印最终汇总表。"""
    print(f"\n{SEP}")
    print("  商城全量测试 — 汇总")
    print(f"{SEP}")

    header = f"  {'Round':<8}{'名称':<52}{'总数':>6}{'通过':>6}{'失败':>6}{'跳过':>6}  {'状态':<6}"
    print(header)
    print(f"  {'-' * 88}")

    g_total = g_pass = g_fail = g_skip = 0

    for r in round_results:
        t, p, f, s = r.total, r.passed, r.failed, r.skipped
        g_total += t
        g_pass += p
        g_fail += f
        g_skip += s

        status = "PASS" if f == 0 else "FAIL"
        name = r.name[:50]
        print(
            f"  R{r.round:<7}{name:<52}{t:>6}{p:>6}{f:>6}{s:>6}  {status:<6}"
        )

    print(f"  {'-' * 88}")
    overall = "PASS" if g_fail == 0 else "FAIL"
    print(
        f"  {'总计':<8}{'':<52}{g_total:>6}{g_pass:>6}{g_fail:>6}{g_skip:>6}  {overall:<6}"
    )

    if g_total:
        rate = g_pass / g_total * 100
        print(f"\n  通过率: {rate:.1f}%  ({g_pass}/{g_total})")

    verdict = "ALL PASS" if g_fail == 0 else "HAS FAILURES"
    print(f"  结论: {verdict}")


# ── CLI ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="商城全量测试运行器 — 7 轮验收",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python run_shop_all.py                         # 全部 7 轮\n"
            "  python run_shop_all.py --round 1               # 仅 Round 1\n"
            "  python run_shop_all.py --round 5               # 仅 Round 5 (Mock)\n"
            "  python run_shop_all.py --through M6            # Round 1 截断到 M6\n"
            "  python run_shop_all.py --round 1 --through M4  # Round 1 截断到 M4\n"
        ),
    )
    parser.add_argument(
        "--round",
        type=int,
        choices=[1, 2, 3, 4, 5, 6, 7],
        default=None,
        help="仅运行指定 Round (1-7)",
    )
    parser.add_argument(
        "--through",
        choices=MILESTONE_ORDER,
        default=None,
        help="Round 1 截断到指定里程碑 (仅对 Round 1 生效, 如 M0-M8)",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="跳过前置环境检查",
    )
    args = parser.parse_args()

    env = {
        "FORCE_FAKE_PLATFORM_LLM": os.environ.get("FORCE_FAKE_PLATFORM_LLM", "0"),
        "VERIFY_LIVE_API": os.environ.get("VERIFY_LIVE_API", "0"),
    }

    # ── 打印启动信息 ──
    print(f"\n{SEP}")
    print("  商城全量测试运行器 (run_shop_all.py)")
    print(f"{SEP}")
    print(f"  FORCE_FAKE_PLATFORM_LLM = {env['FORCE_FAKE_PLATFORM_LLM']}")
    print(f"  VERIFY_LIVE_API         = {env['VERIFY_LIVE_API']}")
    print(f"  测试用例总数              = {total_test_count()}")
    if args.round:
        print(f"  运行范围                 = Round {args.round} only")
    if args.through:
        print(f"  截断里程碑               = {args.through}")

    # ── 前置检查 ──
    if not args.no_preflight:
        if not preflight_check():
            print("\n  前置检查失败，终止运行。使用 --no-preflight 跳过。")
            return 1

    # ── 确定运行的 rounds ──
    if args.round is not None:
        rounds_to_run: list[int] = [args.round]
    else:
        rounds_to_run = list(range(1, 8))

    # ── 逐轮执行 ──
    round_results: list[RoundResult] = []
    for rnd in rounds_to_run:
        result = run_round(rnd, through=args.through)
        round_results.append(result)

    # ── 生成报告 ──
    generate_json_report(round_results, env, args.through, args.round)

    # ── 汇总表 ──
    print_summary_table(round_results)

    # ── 返回码 ──
    total_failed = sum(r.failed for r in round_results)
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
