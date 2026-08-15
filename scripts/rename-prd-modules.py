#!/usr/bin/env python3
"""Rename docs/01-PRD/* module folders to NN-name format and update links."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PRD_ROOT = REPO / "docs" / "01-PRD"

# Version / feature order (matches 01-PRD/README.md)
MODULES = [
    "营销智能体-prd",
    "营销创作增强-prd",
    "线索客户增强-prd",
    "线索客户增强-详细版",
    "线索客户差异分析",
    "跨模块差异分析",
    "成交增强-prd",
    "成交差异分析",
    "CRM五模块UI设计",
    "H5端CRM-UI重设计",
    "订单合同回款增强-prd",
    "订单合同回款差异分析",
    "商机与CPQ-prd",
    "产品主数据增强-prd",
    "产品主数据UI交互",
    "产品报价价税-prd",
    "产品报价价税UI交互",
    "营销活动字段增强-prd",
    "营销活动字段增强UI交互",
    "销售知识库-prd",
    "内容获客商城-prd-phase1",
]

SKIP = {"node_modules", ".venv", ".git", ".pytest_cache", ".workbuddy"}


def new_name(old: str) -> str:
    idx = MODULES.index(old) + 1
    return f"{idx:02d}-{old}"


def rename_dirs() -> dict[str, str]:
    mapping = {m: new_name(m) for m in MODULES}
    for old, new in mapping.items():
        src = PRD_ROOT / old
        dst = PRD_ROOT / new
        if not src.exists():
            print(f"SKIP missing: {old}")
            continue
        if dst.exists():
            print(f"SKIP exists: {new}")
            continue
        r = subprocess.run(
            ["git", "mv", str(src.relative_to(REPO)).replace("\\", "/"),
             str(dst.relative_to(REPO)).replace("\\", "/")],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            src.rename(dst)
        print(f"{old} -> {new}")
    return mapping


def update_links(mapping: dict[str, str]) -> int:
    # longest old names first to avoid partial replacement
    items = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)
    count = 0
    for f in REPO.rglob("*"):
        if not f.is_file() or any(s in f.parts for s in SKIP):
            continue
        if f.suffix not in {".md", ".html", ".mdc", ".py", ".json"}:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        orig = text
        for old, new in items:
            text = text.replace(f"01-PRD/{old}/", f"01-PRD/{new}/")
            text = text.replace(f"01-PRD/{old}\"", f"01-PRD/{new}\"")
            text = text.replace(f"./{old}/", f"./{new}/")
            text = text.replace(f"({old}/", f"({new}/")
            text = text.replace(f"/{old}/", f"/{new}/")
        if text != orig:
            f.write_text(text, encoding="utf-8")
            count += 1
    return count


def main():
    mapping = rename_dirs()
    n = update_links(mapping)
    print(f"Updated {n} files")


if __name__ == "__main__":
    main()
