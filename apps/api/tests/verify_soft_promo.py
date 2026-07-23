#!/usr/bin/env python3
"""正文默认干货、必须覆盖点、方案三角色、伪数据约束。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

from tests.http_client import check
from app.services.prompt_builder import (
    COMPLIANCE_SELF_CHECK_BLOCK,
    CONTENT_WRITING_BLOCK,
    build_proposals_system_prompt,
    build_proposals_user_prompt,
    build_system_prompt,
    build_user_prompt,
    extract_must_cover_points,
    wants_soft_promo,
)

GARDEN_TOPIC = (
    "我是一名老板，业余时间在公司天台上种菜，要写一篇教人怎么种菜的文章，"
    "30*20平，教人按季节种什么菜，要注意什么。我是在深圳。"
)


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "VPROMO-1 brand_intro+种菜 非推广",
            not wants_soft_promo(topic=GARDEN_TOPIC, scene="brand_intro"),
            "",
        )
    )
    results.append(
        check(
            "VPROMO-2 明确种草 为推广",
            wants_soft_promo(topic="小红书种草笔记，推广有机肥"),
            "",
        )
    )

    points = extract_must_cover_points(topic=GARDEN_TOPIC)
    joined = "；".join(points)
    results.append(check("VCOVER-1 抽出面积约束", "30" in joined and "面积" in joined, joined))
    results.append(check("VCOVER-2 抽出深圳/天台", "深圳" in joined or "天台" in joined, joined))
    results.append(check("VCOVER-3 抽出四季清单", "推荐种植清单" in joined, joined))
    results.append(check("VCOVER-4 抽出注意事项", "注意" in joined or "避坑" in joined, joined))
    results.append(check("VCOVER-5 抽出可执行步骤", "可执行" in joined or "步骤" in joined, joined))

    dry = build_user_prompt(
        platform="wechat",
        scene="brand_intro",
        topic=GARDEN_TOPIC,
        brand_cta="加微信领取方案",
    )
    results.append(check("VPROMO-4 干货不注入 CTA", "行动号召" not in dry, ""))
    results.append(check("VCOVER-6 正文含必须覆盖", "【必须覆盖】" in dry, dry[:200]))
    results.append(check("VCOVER-7 正文禁伪数据提示", "百分比" in dry or "翻倍" in dry, ""))

    prop = build_proposals_user_prompt(
        platform="wechat",
        scene="brand_intro",
        topic=GARDEN_TOPIC,
        content_format="article",
        proposal_count=3,
    )
    results.append(check("VTRIO-1 方案含必须覆盖", "【必须覆盖】" in prop, ""))
    results.append(
        check(
            "VTRIO-2 方案三角色",
            "清单型" in prop and "避坑型" in prop and "上手型" in prop,
            prop[-200:],
        )
    )

    sys_p = build_proposals_system_prompt()
    results.append(check("VTRIO-3 方案 system 三角色", "清单型" in sys_p and "避坑型" in sys_p, ""))

    body_sys = build_system_prompt("wechat")
    results.append(
        check(
            "VFAKE-1 写作原则禁伪数据",
            "伪精确" in CONTENT_WRITING_BLOCK or "80%" in CONTENT_WRITING_BLOCK,
            "",
        )
    )
    results.append(
        check(
            "VFAKE-2 合规自检含伪数据",
            "伪精确" in COMPLIANCE_SELF_CHECK_BLOCK or "降低80%" in COMPLIANCE_SELF_CHECK_BLOCK,
            "",
        )
    )
    results.append(check("VFAKE-3 system 含写作原则", "正文写作原则" in body_sys, ""))

    promo_prop = build_proposals_user_prompt(
        platform="wechat",
        scene="brand_intro",
        topic="春季招生推广活动",
        content_format="article",
        proposal_count=3,
    )
    results.append(
        check(
            "VTRIO-4 推广题用好处/避坑/种草三角色",
            "好处型" in promo_prop and "种草转化型" in promo_prop and "清单型" not in promo_prop,
            promo_prop[-160:],
        )
    )

    edu = (
        "我是一名幼儿英语培训机构的老师，要写一篇文章给家长推广我们的课程，"
        "讲从小培养的好处及避坑，语气要温柔，里面多用亲，小孩多用宝贝称呼"
    )
    edu_points = "；".join(extract_must_cover_points(topic=edu))
    results.append(check("VEDU-1 推广识别", wants_soft_promo(topic=edu), ""))
    results.append(check("VEDU-2 覆盖好处", "好处" in edu_points, edu_points))
    results.append(check("VEDU-3 覆盖避坑清单", "避坑" in edu_points or "误区" in edu_points, edu_points))
    results.append(check("VEDU-4 覆盖亲", "亲" in edu_points, edu_points))
    results.append(check("VEDU-5 覆盖宝贝", "宝贝" in edu_points, edu_points))
    results.append(check("VEDU-6 覆盖温柔", "温柔" in edu_points, edu_points))
    results.append(check("VEDU-7 覆盖老师口吻", "老师" in edu_points or "第一人称" in edu_points, edu_points))
    edu_body = build_user_prompt(platform="wechat", scene="brand_intro", topic=edu, brand_cta="私信体验")
    results.append(check("VEDU-8 软营销结构块", "好处（独立成章" in edu_body or "避坑清单" in edu_body, ""))
    results.append(check("VEDU-9 注入 CTA", "行动号召" in edu_body and "私信体验" in edu_body, ""))
    results.append(
        check(
            "VEDU-10 写作原则含称呼密度",
            "亲" in CONTENT_WRITING_BLOCK and "宝贝" in CONTENT_WRITING_BLOCK,
            "",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_soft_promo: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
