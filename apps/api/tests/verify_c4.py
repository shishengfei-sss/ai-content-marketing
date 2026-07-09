"""C4 验收：pgvector hybrid RAG（embedding + 关键词）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.services.knowledge_service import backfill_knowledge_embeddings
from tests.alembic_head import is_at_expected_head
from tests.http_client import _get_test_client, check, req


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def column_exists(table: str, column: str) -> bool:
    from sqlalchemy import inspect

    db = SessionLocal()
    try:
        cols = {c["name"] for c in inspect(db.bind).get_columns(table)}
        return column in cols
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    token = login("13900000099", "test123456")
    client = _get_test_client()

    out = alembic_head()
    results.append(check("VC4-1 alembic=022(head)", is_at_expected_head(out), out.strip()))
    results.append(check("VC4-1 embedding_json 列", column_exists("knowledge_chunks", "embedding_json")))

    db = SessionLocal()
    try:
        filled = backfill_knowledge_embeddings(db, limit=500)
        db.commit()
    finally:
        db.close()
    results.append(check("VC4-2 backfill 可执行", filled >= 0, str(filled)))

    relevant_marker = f"C4REL_{uuid4().hex[:8]}"
    noise_marker = f"C4NOI_{uuid4().hex[:8]}"
    req(
        "POST",
        "/knowledge/documents/text",
        token=token,
        body={
            "title": "C4 语义检索相关",
            "text": (
                f"{relevant_marker} "
                "企业应通过电子税局门户完成增值税线上申报缴款；若逾期未缴将产生滞纳金并纳入信用惩戒记录。"
            ),
            "industry_code": "finance",
        },
    )
    req(
        "POST",
        "/knowledge/documents/text",
        token=token,
        body={
            "title": "C4 噪声文档",
            "text": f"{noise_marker} 周末健身房瑜伽课程优惠活动与私教体验课介绍。",
            "industry_code": "finance",
        },
    )

    r = client.get(
        "/api/v1/knowledge/search",
        params={
            "q": f"{relevant_marker} 电子税局门户 线上申报缴款 滞纳金 信用惩戒",
            "mode": "hybrid",
            "limit": 5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    data = r.json()
    hits = data.get("results") or []
    rel_rank = next((i for i, h in enumerate(hits) if relevant_marker in (h.get("content") or "")), -1)
    noise_rank = next((i for i, h in enumerate(hits) if noise_marker in (h.get("content") or "")), 99)
    results.append(
        check(
            "VC4-3 hybrid 语义命中相关文档",
            r.status_code == 200
            and data.get("mode") == "hybrid"
            and rel_rank >= 0
            and rel_rank < noise_rank,
            f"rel={rel_rank} noise={noise_rank}",
        )
    )

    r_kw = client.get(
        "/api/v1/knowledge/search",
        params={"q": relevant_marker, "mode": "keyword", "limit": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    kw_data = r_kw.json()
    results.append(
        check(
            "VC4-4 keyword 模式仍可用",
            r_kw.status_code == 200
            and kw_data.get("mode") == "keyword"
            and any(relevant_marker in (x.get("content") or "") for x in kw_data.get("results") or []),
            str(len(kw_data.get("results") or [])),
        )
    )

    code, tool = req(
        "POST",
        "/agent/tools/execute",
        token=token,
        body={"name": "search_knowledge", "arguments": {"query": relevant_marker, "mode": "hybrid"}},
    )
    tool_results = tool.get("results") or [] if isinstance(tool, dict) else []
    results.append(
        check(
            "VC4-5 工具 hybrid 返回 score",
            code == 200 and tool.get("mode") == "hybrid" and tool_results and "score" in tool_results[0],
            str(tool_results[0] if tool_results else {}),
        )
    )

    proc = subprocess.run([sys.executable, "tests/verify_c3.py"], cwd=API_ROOT)
    results.append(check("VC4-6 verify_c3 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== C4", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
