#!/usr/bin/env python3
"""Check relative links in docs/ and project-docs-index for broken targets."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [REPO / "docs", REPO / "project-docs-index", REPO / "README.md"]
SKIP = {"node_modules", ".venv", ".git", ".workbuddy", ".trae-html-share-packages", ".slidep", ".cache"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)|href=[\"']([^\"'#]+)[\"']", re.I)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".md", ".html", ".mdc"}:
                    if not any(s in f.parts for s in SKIP):
                        files.append(f)
    return files


def resolve_link(source: Path, raw: str) -> Path | None:
    target = raw.split("#")[0].split("?")[0].strip()
    if not target or target.endswith("/"):
        return None
    if target.startswith("/"):
        return REPO / target.lstrip("/")
    if target.startswith("docs/"):
        return REPO / target
    return (source.parent / target).resolve()


def main() -> None:
    broken: list[tuple[str, str, str]] = []
    checked = 0
    for f in iter_files():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in LINK_RE.finditer(text):
            raw = (m.group(1) or m.group(2) or "").strip()
            if not raw or raw.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            if "://" in raw:
                continue
            tp = resolve_link(f, raw)
            if tp is None:
                continue
            checked += 1
            if not tp.exists():
                try:
                    rel = tp.relative_to(REPO)
                except ValueError:
                    rel = tp
                broken.append((str(f.relative_to(REPO)), raw, str(rel)))

    seen: set[tuple[str, str, str]] = set()
    uniq = []
    for item in broken:
        if item not in seen:
            seen.add(item)
            uniq.append(item)

    print(f"Checked {checked} relative links under docs/ + project-docs-index + README")
    print(f"Broken: {len(uniq)}")
    for src, link, resolved in sorted(uniq):
        print(f"  {src}")
        print(f"    -> {link}")
        print(f"       ({resolved})")


if __name__ == "__main__":
    main()
