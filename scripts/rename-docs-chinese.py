#!/usr/bin/env python3
"""Rename docs/ paths to Chinese names and update repository links."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"node_modules", ".venv", ".git", ".pytest_cache", ".workbuddy", ".trae-html-share-packages"}
TEXT_SUFFIXES = {".md", ".html", ".mdc", ".py", ".json", ".vue", ".txt", ".xlsx", ".ps1", ".sh"}


def git_mv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        print(f"SKIP missing: {src.relative_to(REPO)}")
        return
    if dst.exists():
        print(f"SKIP exists: {dst.relative_to(REPO)}")
        return
    import subprocess

    rel_src = str(src.relative_to(REPO)).replace("\\", "/")
    rel_dst = str(dst.relative_to(REPO)).replace("\\", "/")
    r = subprocess.run(["git", "mv", rel_src, rel_dst], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        shutil.move(str(src), str(dst))
    print(f"RENAMED {rel_src} -> {rel_dst}")


# --- PRD module directories (old -> new) ---
PRD_DIR_RENAMES = {
    "01-营销智能体-prd": "01-营销智能体-prd",
    "02-营销创作增强-prd": "02-营销创作增强-prd",
    "03-线索客户增强-prd": "03-线索客户增强-prd",
    "04-线索客户增强-详细版": "04-线索客户增强-详细版",
    "05-线索客户差异分析": "05-线索客户差异分析",
    "06-跨模块差异分析": "06-跨模块差异分析",
    "07-成交增强-prd": "07-成交增强-prd",
    "08-成交差异分析": "08-成交差异分析",
    "09-CRM五模块UI设计": "09-CRM五模块UI设计",
    "10-H5端CRM-UI重设计": "10-H5端CRM-UI重设计",
    "11-订单合同回款增强-prd": "11-订单合同回款增强-prd",
    "12-订单合同回款差异分析": "12-订单合同回款差异分析",
    "13-商机与CPQ-prd": "13-商机与CPQ-prd",
    "14-产品主数据增强-prd": "14-产品主数据增强-prd",
    "15-产品主数据UI交互": "15-产品主数据UI交互",
    "16-产品报价价税-prd": "16-产品报价价税-prd",
    "17-产品报价价税UI交互": "17-产品报价价税UI交互",
    "18-营销活动字段增强-prd": "18-营销活动字段增强-prd",
    "19-营销活动字段增强UI交互": "19-营销活动字段增强UI交互",
    "20-销售知识库-prd": "20-销售知识库-prd",
    "21-内容获客商城-phase1": "21-内容获客商城-phase1",
}

# Main HTML slug per module (basename without .html)
PRD_HTML_RENAMES = {
    "营销智能体-prd": "营销智能体-prd",
    "营销创作增强-prd": "营销创作增强-prd",
    "线索客户增强-prd": "线索客户增强-prd",
    "线索客户增强-详细版": "线索客户增强-详细版",
    "线索客户差异分析": "线索客户差异分析",
    "跨模块差异分析": "跨模块差异分析",
    "成交增强-prd": "成交增强-prd",
    "成交差异分析": "成交差异分析",
    "CRM五模块UI设计": "CRM五模块UI设计",
    "H5端CRM-UI重设计": "H5端CRM-UI重设计",
    "订单合同回款增强-prd": "订单合同回款增强-prd",
    "订单合同回款差异分析": "订单合同回款差异分析",
    "商机与CPQ-prd": "商机与CPQ-prd",
    "产品主数据增强-prd": "产品主数据增强-prd",
    "产品主数据UI交互": "产品主数据UI交互",
    "产品报价价税-prd": "产品报价价税-prd",
    "产品报价价税UI交互": "产品报价价税UI交互",
    "营销活动字段增强-prd": "营销活动字段增强-prd",
    "营销活动字段增强UI交互": "营销活动字段增强UI交互",
    "销售知识库-prd": "销售知识库-prd",
    "内容获客商城-prd-phase1": "内容获客商城-prd-phase1",
}

MODULE21_PAGE_RENAMES = {
    "01-管理端UI.html": "01-管理端UI.html",
    "02-买家端UI.html": "02-买家端UI.html",
    "03-数据流.html": "03-数据流.html",
    "04-数据模型.html": "04-数据模型.html",
    "05-角色权限.html": "05-角色权限.html",
    "06-平台端UI.html": "06-平台端UI.html",
}

OTHER_PATH_RENAMES = [
    ("docs/02-执行计划/内容获客平台-执行计划.md", "docs/02-执行计划/内容获客平台-执行计划.md"),
    ("docs/02-执行计划/v0.4-智能体执行计划.md", "docs/02-执行计划/v0.4-智能体执行计划.md"),
    (
        "docs/02-执行计划/支付抖音启动计划/支付抖音启动-执行计划.html",
        "docs/02-执行计划/支付抖音启动计划/支付抖音启动-执行计划.html",
    ),
    ("docs/02-执行计划/支付抖音启动计划", "docs/02-执行计划/支付抖音启动计划"),
    ("docs/05-测试与验收/自动化测试", "docs/05-测试与验收/自动化测试"),
    ("docs/05-测试与验收/测试用例", "docs/05-测试与验收/测试用例"),
    ("docs/05-测试与验收/验收报告", "docs/05-测试与验收/验收报告"),
    ("docs/05-测试与验收/自动化报告", "docs/05-测试与验收/自动化报告"),
]


def rename_prd_html_files() -> None:
    prd_root = REPO / "docs" / "01-PRD"
    for old_dir, new_dir in PRD_DIR_RENAMES.items():
        module_dir = prd_root / old_dir
        if not module_dir.exists():
            module_dir = prd_root / new_dir
        if not module_dir.exists():
            continue
        for old_slug, new_slug in PRD_HTML_RENAMES.items():
            old_file = module_dir / f"{old_slug}.html"
            new_file = module_dir / f"{new_slug}.html"
            if old_file.exists() and not new_file.exists():
                git_mv(old_file, new_file)
        if old_dir == "21-内容获客商城-phase1" or new_dir == "21-内容获客商城-phase1":
            for old_page, new_page in MODULE21_PAGE_RENAMES.items():
                src = module_dir / old_page
                dst = module_dir / new_page
                if src.exists() and not dst.exists():
                    git_mv(src, dst)


def rename_prd_directories() -> None:
    prd_root = REPO / "docs" / "01-PRD"
    for old_dir, new_dir in PRD_DIR_RENAMES.items():
        git_mv(prd_root / old_dir, prd_root / new_dir)


def rename_other_paths() -> None:
    for old_rel, new_rel in OTHER_PATH_RENAMES:
        git_mv(REPO / old_rel, REPO / new_rel)


def build_replace_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []

    for old_dir, new_dir in PRD_DIR_RENAMES.items():
        pairs.append((old_dir, new_dir))
    for old_slug, new_slug in PRD_HTML_RENAMES.items():
        pairs.append((f"{old_slug}.html", f"{new_slug}.html"))
        pairs.append((old_slug, new_slug))
    for old_page, new_page in MODULE21_PAGE_RENAMES.items():
        pairs.append((old_page, new_page))
        # anchor ids like #p02 on 06-platform-ui
        old_base = old_page.replace(".html", "")
        new_base = new_page.replace(".html", "")
        pairs.append((f"{old_base}#", f"{new_base}#"))
        pairs.append((f"{old_base}.html#", f"{new_page}#"))

    pairs.extend(
        [
            ("内容获客平台-执行计划.md", "内容获客平台-执行计划.md"),
            ("内容获客平台-执行计划", "内容获客平台-执行计划"),
            ("支付抖音启动计划", "支付抖音启动计划"),
            ("支付抖音启动-执行计划.html", "支付抖音启动-执行计划.html"),
            ("支付抖音启动-执行计划", "支付抖音启动-执行计划"),
            ("v0.4-智能体执行计划.md", "v0.4-智能体执行计划.md"),
            ("自动化测试", "自动化测试"),
            ("测试用例", "测试用例"),
            ("验收报告", "验收报告"),
            ("自动化报告", "自动化报告"),
        ]
    )

    # dedupe, longest first
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for old, new in sorted(pairs, key=lambda x: len(x[0]), reverse=True):
        if old in seen or old == new:
            continue
        seen.add(old)
        unique.append((old, new))
    return unique


def update_links(pairs: list[tuple[str, str]]) -> int:
    count = 0
    for f in REPO.rglob("*"):
        if not f.is_file():
            continue
        if any(s in f.parts for s in SKIP_DIRS):
            continue
        if f.suffix not in TEXT_SUFFIXES and f.name not in {"README"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        orig = text
        for old, new in pairs:
            text = text.replace(old, new)
        if text != orig:
            f.write_text(text, encoding="utf-8")
            count += 1
            print(f"UPDATED {f.relative_to(REPO)}")
    return count


def main() -> None:
    rename_prd_html_files()
    rename_other_paths()
    rename_prd_directories()
    pairs = build_replace_pairs()
    n = update_links(pairs)
    print(f"Done. Updated {n} files.")


if __name__ == "__main__":
    main()
