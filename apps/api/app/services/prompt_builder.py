PLATFORM_LABELS = {
    "wechat": "微信公众号",
    "xhs": "小红书",
    "douyin": "抖音",
}


def build_system_prompt(platform: str) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    return f"""你是一名专业的财税营销内容创作助手，为代理记账公司撰写{label}营销内容。

硬性要求：
1. 内容必须合规，不得承诺「保证不被查」「零风险」等表述
2. 文末必须包含免责声明：本文仅供参考，具体政策以税务机关最新规定为准
3. 语气专业、亲切，适合中小企业主阅读
4. 直接输出正文内容，不要输出 JSON 或多余解释"""


def build_user_prompt(
    *,
    platform: str,
    scene: str,
    topic: str,
    scene_name: str = "",
    template_hint: str = "",
    rag_snippets: list[str] | None = None,
    brand_name: str = "",
    brand_tone: str = "",
    brand_cta: str = "",
    brand_sample: str = "",
    user_instructions: str = "",
    ephemeral_instruction: str = "",
) -> str:
    scene_label = scene_name or scene or "通用营销"
    platform_label = PLATFORM_LABELS.get(platform, platform)

    parts = [
        f"请为{platform_label}创作一篇「{scene_label}」主题的内容。",
        f"选题：{topic}",
    ]

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

    if platform == "wechat":
        parts.append("格式：适合公众号发布的 HTML 友好纯文本，含标题、分段、要点列表。")
    elif platform == "xhs":
        parts.append("格式：小红书笔记，含吸睛标题、正文、3-5个话题标签。")
    elif platform == "douyin":
        parts.append("格式：抖音口播分镜脚本，含镜号、画面描述、旁白、字幕、建议时长。")

    if ephemeral_instruction:
        parts.append(f"补充要求：{ephemeral_instruction}")

    return "\n".join(parts)
