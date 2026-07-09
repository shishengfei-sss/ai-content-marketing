"""方案数量与合规改稿循环验收。"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.services.agent.compliance_revise import (
    MAX_COMPLIANCE_REVISE_ROUNDS,
    build_compliance_revise_instruction,
)
from app.services.proposal_count import (
    MAX_PROPOSAL_COUNT,
    extract_proposal_count_from_text,
    resolve_proposal_count,
)
from app.services.prompt_builder import parse_proposals_json
from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "VPC1-1 默认未指定为 None",
            resolve_proposal_count(text="公众号财税科普") is None,
            "None",
        )
    )
    results.append(
        check(
            "VPC1-2 解析 10 个方向",
            extract_proposal_count_from_text("请生成10个创作方向，股市分析") == 10,
            str(extract_proposal_count_from_text("请生成10个创作方向，股市分析")),
        )
    )
    results.append(
        check(
            "VPC1-3 上限 clamp 10",
            resolve_proposal_count(explicit=20) == MAX_PROPOSAL_COUNT,
            str(resolve_proposal_count(explicit=20)),
        )
    )

    raw10 = "[" + ",".join(f'{{"title":"方向{i}号切入点"}}' for i in range(1, 11)) + "]"
    parsed10 = parse_proposals_json(raw10, proposal_count=10)
    results.append(check("VPC1-4 parse 恰好10个", len(parsed10) == 10, str(len(parsed10))))

    raw5 = "[" + ",".join(f'{{"title":"方向{i}"}}' for i in range(1, 6)) + "]"
    parsed5 = parse_proposals_json(raw5, proposal_count=None)
    results.append(check("VPC1-5 parse 默认3-5", len(parsed5) == 5, str(len(parsed5))))

    instruction = build_compliance_revise_instruction(
        {
            "_compliance_issues": [
                {"severity": "block", "message": "含违规承诺用语：稳赚不赔"},
            ],
            "_compliance_suggestions": ["补充免责声明"],
        }
    )
    results.append(
        check(
            "VPC1-6 改稿指令含 block 与免责声明",
            "稳赚不赔" in instruction and "免责声明" in instruction,
            instruction[:80],
        )
    )
    results.append(
        check(
            "VPC1-7 改稿最多3轮",
            MAX_COMPLIANCE_REVISE_ROUNDS == 3,
            str(MAX_COMPLIANCE_REVISE_ROUNDS),
        )
    )

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=token,
        body={"industry_code": "finance", "title": "ProposalCount"},
    )
    sid = session.get("id")
    if sid:
        code, pre = req(
            "POST",
            f"/agent/sessions/{sid}/preflight",
            token=token,
            body={
                "message": "公众号图文：请给出10个股市行情分析创作方向，面向普通投资者",
                "platform": "wechat",
                "content_format": "article",
                "llm_source": "platform",
            },
        )
        results.append(
            check(
                "VPC1-8 preflight proposal_count=10",
                code == 200 and pre.get("ready") is True and pre.get("proposal_count") == 10,
                str(pre),
            )
        )

    passed = all(results)
    print("\n=== VPC1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
