"""AI 生成 Prompt 组装。



组装顺序（不可调整，见 docs/需求规格.md §3.4）：

合规 System → 场景模板 → RAG → 品牌 → 个人提示词 → 本次 topic/补充指令。

"""



import json

import re

from app.services.assistant_service import AssistantProfile



PLATFORM_LABELS = {

    "wechat": "微信公众号",

    "xhs": "小红书",

    "douyin": "抖音",

}



FORMAT_LABELS = {

    "article": "图文文章",

    "note": "图文笔记",

    "video_script": "视频脚本",

}



VIDEO_SCRIPT_MAX_SECONDS = 30





def default_content_format(platform: str) -> str:

    if platform == "xhs":

        return "note"

    if platform == "douyin":

        return "video_script"

    return "article"





def validate_platform_format(platform: str, content_format: str) -> None:

    allowed: dict[str, set[str]] = {

        "wechat": {"article", "video_script"},

        "xhs": {"note", "video_script"},

        "douyin": {"video_script"},

    }

    if content_format not in allowed.get(platform, set()):

        raise ValueError("INVALID_PLATFORM_FORMAT")





def build_system_prompt(
    platform: str,
    *,
    content_format: str = "article",
    assistant: AssistantProfile | None = None,
) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    fmt = FORMAT_LABELS.get(content_format, content_format)

    if assistant is None:
        from app.services.assistant_service import AssistantProfile as AP

        assistant = AP(
            code="finance",
            name="财税营销专家",
            description="",
            system_role="你是一名专业的财税营销内容创作助手，为代理记账公司撰写{platform}{format}。",
            compliance_rules=(
                "1. 内容必须合规，不得承诺「保证不被查」「零风险」等表述\n"
                "2. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}\n"
                "3. 语气专业、亲切，适合中小企业主阅读\n"
                "4. 直接输出正文内容，不要输出 JSON 或多余解释"
            ),
            disclaimer="本文仅供参考，具体政策以税务机关最新规定为准",
            default_tone="专业亲切",
            welcome_message="",
        )

    role = assistant.system_role.format(platform=label, format=fmt)
    rules = assistant.compliance_rules.format(
        disclaimer=assistant.disclaimer,
        platform=label,
        format=fmt,
        tone=assistant.default_tone,
    )
    base = f"""{role}

硬性要求：
{rules}"""

    if content_format == "video_script":

        base += (
            f"\n5. 输出完整分镜脚本，含镜号、画面描述、旁白、字幕、建议时长"
            f"\n6. 全片总时长不得超过 {VIDEO_SCRIPT_MAX_SECONDS} 秒，各镜建议时长之和须 ≤ {VIDEO_SCRIPT_MAX_SECONDS} 秒"
        )

    return base





def build_proposals_system_prompt(*, assistant: AssistantProfile | None = None) -> str:
    name = assistant.name if assistant else "营销"
    return f"""你是一名{name}方向的选题策划助手。用户将选定其中一个方向后再撰写正文。

每个方案只需一句话点明创作方向，不要标题、不要大纲、不要展开。

只输出 JSON 数组，不要 markdown 代码块，不要任何解释文字。"""





def build_proposals_user_prompt(

    *,

    platform: str,

    scene: str,

    topic: str,

    content_format: str,

    scene_name: str = "",

    template_hint: str = "",

    proposal_count: int | None = None,

) -> str:

    scene_label = scene_name or scene or "通用营销"

    platform_label = PLATFORM_LABELS.get(platform, platform)

    fmt = FORMAT_LABELS.get(content_format, content_format)

    parts = [

        f"请为{platform_label}的「{scene_label}」主题，创作形态为「{fmt}」。",

        f"用户选题：{topic}",

    ]

    if proposal_count is not None:
        parts.append(
            f"请给出恰好 {proposal_count} 个不同创作方向，JSON 数组长度必须等于 {proposal_count}，每项仅一个字段："
        )
    else:
        parts.append("请给出 3 到 5 个不同创作方向，JSON 数组，每项仅一个字段：")

    parts.append(
        '- "title"：一句话创作方向（15～40 字，只说切入点，不要标题、不要分点、不要大纲）'
    )

    if template_hint:

        parts.append(f"场景参考：{template_hint}")

    if content_format == "video_script":

        parts.append(
            f"方向须适合 {VIDEO_SCRIPT_MAX_SECONDS} 秒内竖屏短视频口播。"
        )

    return "\n".join(parts)





def _format_instruction(platform: str, content_format: str) -> str:

    if content_format == "video_script":

        duration_rule = (
            f"全片总时长不超过 {VIDEO_SCRIPT_MAX_SECONDS} 秒，"
            f"每镜标注建议时长，各镜时长之和须 ≤ {VIDEO_SCRIPT_MAX_SECONDS} 秒"
        )

        if platform == "wechat":

            return (

                f"格式：公众号短视频/视频号口播分镜脚本（{duration_rule}），"

                "含镜号、画面描述、旁白、字幕、建议时长，结尾口播含免责声明。"

            )

        if platform == "xhs":

            return (

                f"格式：小红书竖屏短视频脚本（{duration_rule}），"

                "含镜号、画面描述、旁白、字幕、建议时长，文末附 3～5 个话题标签。"

            )

        return f"格式：抖音口播分镜脚本（{duration_rule}），含镜号、画面描述、旁白、字幕、建议时长。"

    if platform == "wechat":

        return "格式：适合公众号发布的 HTML 友好纯文本，含标题、分段、要点列表。"

    if platform == "xhs":

        return "格式：小红书笔记，含吸睛标题、正文、3-5个话题标签。"

    return "格式：短视频口播分镜脚本。"





def build_user_prompt(

    *,

    platform: str,

    scene: str,

    topic: str,

    content_format: str = "article",

    scene_name: str = "",

    template_hint: str = "",

    rag_snippets: list[str] | None = None,

    brand_name: str = "",

    brand_tone: str = "",

    brand_cta: str = "",

    brand_sample: str = "",

    user_instructions: str = "",

    ephemeral_instruction: str = "",

    selected_proposal_title: str = "",

    selected_proposal_angle: str = "",

    selected_proposal_outline: str = "",

) -> str:

    scene_label = scene_name or scene or "通用营销"

    platform_label = PLATFORM_LABELS.get(platform, platform)

    fmt = FORMAT_LABELS.get(content_format, content_format)



    parts = [

        f"请为{platform_label}创作一篇「{scene_label}」主题的{fmt}。",

        f"选题：{topic}",

    ]



    if selected_proposal_title:

        parts.append(

            f"用户已选定创作方向：{selected_proposal_title}\n"

            f"请按该方向撰写完整正文。"

        )



    if template_hint:

        parts.append(f"场景写作要点：{template_hint}")



    if brand_name:

        parts.append(f"品牌/公司名：{brand_name}，语气：{brand_tone or '专业亲切'}")

    if brand_cta:

        parts.append(f"行动号召（CTA）：{brand_cta}")

    if brand_sample:

        parts.append(f"品牌范文参考（模仿风格，勿照抄）：\n{brand_sample}")



    if rag_snippets:

        joined = "\n---\n".join(rag_snippets)

        parts.append(f"以下知识库片段供参考（请自然融入，不要生硬堆砌）：\n{joined}")



    if user_instructions:

        parts.append(f"用户个人写作偏好：{user_instructions}")



    parts.append(_format_instruction(platform, content_format))



    if ephemeral_instruction:

        parts.append(f"补充要求：{ephemeral_instruction}")



    return "\n".join(parts)





def parse_proposals_json(raw: str, *, proposal_count: int | None = None) -> list[dict[str, str]]:

    text = raw.strip()

    if text.startswith("```"):

        text = re.sub(r"^```(?:json)?\s*", "", text)

        text = re.sub(r"\s*```$", "", text)

    try:

        data = json.loads(text)

    except json.JSONDecodeError:

        match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)

        if not match:

            raise ValueError("PROPOSALS_PARSE_FAILED") from None

        data = json.loads(match.group())



    if not isinstance(data, list):

        raise ValueError("PROPOSALS_PARSE_FAILED")

    max_items = proposal_count if proposal_count is not None else 5

    proposals: list[dict[str, str]] = []

    for item in data[:max_items]:

        if not isinstance(item, dict):

            continue

        title = str(item.get("title") or item.get("direction") or "").strip()

        if len(title) >= 2:

            proposals.append({"title": title, "angle": "", "outline": ""})



    if proposal_count is not None:
        if len(proposals) < proposal_count:
            raise ValueError("PROPOSALS_PARSE_FAILED")
        return proposals[:proposal_count]

    if len(proposals) < 3:

        raise ValueError("PROPOSALS_PARSE_FAILED")

    return proposals[:5]


