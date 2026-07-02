PLATFORM_LABELS = {
    "wechat": "微信公众号",
    "xhs": "小红书",
    "douyin": "抖音",
}

SCENE_LABELS = {
    "tax_deadline_reminder": "报税截止提醒",
    "bookkeeping_intro": "代理记账介绍",
    "small_company_register": "新公司注册指南",
    "case_penalty_story": "税务处罚案例",
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
    ephemeral_instruction: str = "",
) -> str:
    scene_label = SCENE_LABELS.get(scene, scene or "通用营销")
    platform_label = PLATFORM_LABELS.get(platform, platform)

    parts = [
        f"请为{platform_label}创作一篇「{scene_label}」主题的内容。",
        f"选题：{topic}",
    ]

    if platform == "wechat":
        parts.append("格式：适合公众号发布的 HTML 友好纯文本，含标题、分段、要点列表。")
    elif platform == "xhs":
        parts.append("格式：小红书笔记，含吸睛标题、正文、3-5个话题标签。")
    elif platform == "douyin":
        parts.append("格式：抖音口播分镜脚本，含镜号、画面描述、旁白、字幕、建议时长。")

    if ephemeral_instruction:
        parts.append(f"补充要求：{ephemeral_instruction}")

    return "\n".join(parts)
