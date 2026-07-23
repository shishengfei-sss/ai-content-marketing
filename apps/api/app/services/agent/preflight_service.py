"""创作预检：Workflow 启动前判断用户输入是否足够。"""



from __future__ import annotations



import re

from uuid import UUID



from sqlalchemy.orm import Session



from app.models import AgentSession

from app.services.assistant_service import normalize_advisor_code
from app.services.agent.intent_parser import parse_create_preflight

from app.services.agent.session_service import append_message, list_messages

from app.services.proposal_count import resolve_proposal_count



_GREETING_RE = re.compile(

    r"^(你好|您好|hi|hello|在吗|试试|测试|help)[!.?。！？\s]*$",

    re.IGNORECASE,

)

_TOO_VAGUE_RE = re.compile(

    r"^(写(一)?篇|帮我写|生成(一个)?|来(一)?个|写个|写脚本|写笔记|创作)[!.?。！？\s]*$",

)



STANDARD_REPLIES: dict[str, str] = {

    "greeting": (
        "你好！我是小营，你的 AI 营销创作顾问。请告诉我你想创作的主题、目标平台和受众，"
        "我来帮你理清需求并生成方案。下一步：直接说「平台 + 主题」即可开始。"
    ),

    "too_short": (
        "你的描述太简短，我无法判断创作方向。请补充主题、目标读者或核心卖点。"
        "下一步：例如「小红书笔记，少儿编程招生，面向家长」。"
    ),

    "vague": (
        "请补充具体主题与要点，例如：「抖音视频脚本，讲新公司注册流程，面向首次创业的老板」。"
        "下一步：告诉我平台、题材和受众，我就能出方案。"
    ),

    "joke": (
        "哈哈，这个我先当玩笑收下啦。我是营销创作顾问，擅长帮你写公众号、小红书、抖音内容。"
        "下一步：说一个你想推广的产品或话题，我们开始创作。"
    ),

    "off_topic": (
        "这个话题不在我的服务范围内。我只帮你做营销内容创作（公众号 / 小红书 / 抖音）。"
        "下一步：告诉我你想写的主题和平台，我马上帮你出方案。"
    ),

    "insult": (
        "我理解你可能有些着急，但我会始终保持尊重。我是营销创作顾问，准备好就告诉我你的创作主题。"
        "下一步：说一个你想推广的产品或服务，我们继续。"
    ),

    "unsafe": (
        "这类内容涉及人身攻击、辱骂或危险表述，我无法协助创作。"
        "我只帮你写合规的营销内容（公众号 / 小红书 / 抖音）。"
        "下一步：换一个产品、服务或品牌话题，我们重新开始。"
    ),

    "revise_feedback": (
        "收到，上一批方案没对上你的需求。"
        "请具体告诉我：想要的语气、受众、切入角度，或必须包含的要点，我按你的要求重新出方案。"
        "下一步：直接说你希望怎么改。"
    ),

}


_REPLY_OVERRIDE_CLASSES = frozenset({"joke", "off_topic", "insult", "unsafe", "revise_feedback"})

_PLATFORM_PREFIX_RE = re.compile(r"\[平台[^\]]*\]\s*", re.IGNORECASE)

_MAX_CLARIFY_TURNS = 2

_MIN_EFFECTIVE_CHARS = 4

_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")

_INSULT_RE = re.compile(
    r"(傻子|傻逼|白痴|脑残|智障|废物|滚蛋|去死吧|你妈的|他妈的|草你|操你|垃圾货)",
    re.IGNORECASE,
)

_UNSAFE_RE = re.compile(
    r"(自杀|自尽|去死吧|问候.*(妈|母)|骂(他|她|你)?妈|人身攻击|喷死|问候她妈|问候他妈)",
    re.IGNORECASE,
)

# 模糊不满：需要追问怎么改
_REVISE_VAGUE_RE = re.compile(
    r"(不一样|不满意|不是我想要|认真(思考|点|一点)?|换一批|不对劲|跑偏)",
    re.IGNORECASE,
)

# 具体改稿指令：应继续改正文，不可当违规/不可再空追问
_REVISE_EDIT_RE = re.compile(
    r"(改一下|修改|改成|改改|改下|去掉|删掉|删除|不要出现|别写|"
    r"字数|太长|太短|缩短|精简|压缩|语气|风格|幽默|"
    r"配图|图片|插图|题目|标题|"
    r"例子|案例|换一个|换掉|换成|不好|不对|重写|润色|优化|调整|这段|这句|这里|"
    r"写清楚|写详细|讲清楚|说清楚|补充|加上|展开|完善|充实|再补|"
    r"详细写|详细一点|再详细|怎么种|如何种|注意事项|要注意|推荐的|"
    r"输出视频|视频脚本|改成笔记|换成脚本|转为脚本|改成小红书|改成抖音|改成公众号)",
    re.IGNORECASE,
)


def _local_input_class(text: str) -> str | None:
    """本地边界分类，避免短句辱骂/违规稿被当「过短」或误放行出方案。"""
    # 具体改稿优先：避免会话历史里的违规词让 LLM 误判当前改稿指令
    if _REVISE_EDIT_RE.search(text):
        return "revise_edit"
    if _UNSAFE_RE.search(text):
        return "unsafe"
    if _INSULT_RE.search(text):
        return "insult"
    if _REVISE_VAGUE_RE.search(text):
        return "revise_feedback"
    return None


def is_content_revise_request(text: str) -> bool:
    """供创作页判断：用户是否在对已有正文提修改意见。"""
    return bool(_REVISE_EDIT_RE.search(_strip_platform_prefix(text) or text))


def _strip_platform_prefix(message: str) -> str:
    return _PLATFORM_PREFIX_RE.sub("", message).strip()


def _effective_length(text: str) -> int:
    return len(_CHINESE_CHAR_RE.findall(text))


def _count_clarify_messages(db: Session, session: AgentSession) -> int:
    return sum(
        1
        for msg in list_messages(db, session.id)
        if msg.role == "assistant" and msg.message_type == "clarify"
    )


def _last_clarify_question(db: Session, session: AgentSession) -> str | None:
    last: str | None = None
    for msg in list_messages(db, session.id):
        if msg.role == "assistant" and msg.message_type == "clarify":
            last = msg.content
    return last


def _is_similar_question(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a_clean = re.sub(r"[，。！？\s]", "", a)
    b_clean = re.sub(r"[，。！？\s]", "", b)
    if a_clean == b_clean:
        return True
    shorter, longer = sorted([a_clean, b_clean], key=len)
    if shorter and longer.startswith(shorter[: max(len(shorter) - 2, 1)]):
        return True
    overlap = sum(1 for ch in shorter if ch in longer)
    return overlap / max(len(shorter), 1) > 0.8


def _merge_user_messages(db: Session, session: AgentSession, current: str) -> str:
    parts: list[str] = []
    for msg in list_messages(db, session.id)[-16:]:
        if msg.role == "user":
            cleaned = _strip_platform_prefix(msg.content)
            if cleaned:
                parts.append(cleaned)
    cleaned_current = _strip_platform_prefix(current)
    if cleaned_current:
        parts.append(cleaned_current)
    return "，".join(parts) if parts else current.strip()





def _local_clarify(message: str) -> str | None:

    text = _strip_platform_prefix(message)

    boundary = _local_input_class(text)
    if boundary and boundary in STANDARD_REPLIES:
        return STANDARD_REPLIES[boundary]

    if _effective_length(text) < _MIN_EFFECTIVE_CHARS:

        return "请补充更具体的创作需求，例如：主题、目标读者或想强调的核心要点。"

    if _GREETING_RE.match(text):

        return "请告诉我您想创作的主题、目标读者或核心卖点，我再为您生成方案。"

    if _TOO_VAGUE_RE.match(text):

        return "请补充具体主题与要点，例如：「抖音视频脚本，讲新公司注册流程，面向首次创业的老板」。"

    return None





def _has_clarify_history(db: Session, session: AgentSession) -> bool:

    for msg in list_messages(db, session.id):

        if msg.role == "assistant" and msg.message_type == "clarify":

            return True

    return False





def _build_conversation_context(db: Session, session: AgentSession, current: str) -> str:

    lines: list[str] = []

    for msg in list_messages(db, session.id)[-16:]:

        if msg.role == "user":

            lines.append(f"用户：{msg.content}")

        elif msg.role == "assistant" and msg.message_type == "clarify":

            lines.append(f"助手：{msg.content}")

    lines.append(f"用户（本轮）：{current.strip()}")

    return "\n".join(lines)





async def run_create_preflight(

    db: Session,

    tenant_id: UUID,

    *,

    message: str,

    platform: str,

    content_format: str,

    industry_code: str,

    llm_source: str = "platform",

    session: AgentSession | None = None,

    persist_messages: bool = True,

) -> dict:

    """返回 {ready, action, clarify_question?, topic?, proposal_count?}。"""

    raw_text = message.strip()
    text = _strip_platform_prefix(raw_text) or raw_text
    advisor_code = normalize_advisor_code(industry_code)
    in_clarify_flow = bool(session and _has_clarify_history(db, session))
    clarify_count = _count_clarify_messages(db, session) if session else 0
    last_question = _last_clarify_question(db, session) if session else None

    conversation = (

        _build_conversation_context(db, session, text) if session else text

    )



    if not in_clarify_flow:

        local_q = _local_clarify(text)

        if local_q:

            if session and persist_messages:

                append_message(db, session, role="user", content=raw_text)

                append_message(db, session, role="assistant", content=local_q, message_type="clarify")

            return {

                "ready": False,

                "action": "clarify",

                "clarify_question": local_q,

                "topic": None,

                "proposal_count": None,

            }



    intent = await parse_create_preflight(

        db,

        tenant_id,

        message=text,

        platform=platform,

        content_format=content_format,

        industry_code=advisor_code,

        llm_source=llm_source,

        conversation_context=conversation,

    )

    # 本地边界优先：辱骂/违规不可被 LLM 误判为 proceed；具体改稿不可被误判为 unsafe
    local_cls = _local_input_class(text)
    if local_cls == "revise_edit":
        intent.action = "proceed"
        intent.input_class = "revise_edit"
        intent.clarify_question = None
        if not (intent.topic or "").strip():
            intent.topic = text
    elif local_cls in _REPLY_OVERRIDE_CLASSES:
        intent.action = "clarify"
        intent.input_class = local_cls
        intent.clarify_question = STANDARD_REPLIES[local_cls]
        intent.topic = ""

    if intent.action == "clarify" or not (intent.topic or text):

        question = intent.clarify_question or "请补充具体主题、目标读者或想强调的核心要点。"

        input_class = (intent.input_class or "").strip().lower()

        if input_class in _REPLY_OVERRIDE_CLASSES and input_class in STANDARD_REPLIES:

            question = STANDARD_REPLIES[input_class]

        repeated = _is_similar_question(question, last_question or "")

        has_content = _effective_length(text) >= _MIN_EFFECTIVE_CHARS

        if (clarify_count >= _MAX_CLARIFY_TURNS or repeated) and has_content and input_class not in _REPLY_OVERRIDE_CLASSES:

            topic = _merge_user_messages(db, session, text) if session else text

            proposal_count = resolve_proposal_count(explicit=intent.proposal_count, text=conversation)

            if session and persist_messages:

                append_message(db, session, role="user", content=raw_text)

            return {

                "ready": True,

                "action": "proceed",

                "clarify_question": None,

                "topic": topic,

                "proposal_count": proposal_count,

            }

        if session and persist_messages:

            append_message(db, session, role="user", content=raw_text)

            append_message(db, session, role="assistant", content=question, message_type="clarify")

        return {

            "ready": False,

            "action": "clarify",

            "clarify_question": question,

            "topic": None,

            "proposal_count": None,

        }



    topic = (intent.topic or text).strip()

    proposal_count = resolve_proposal_count(

        explicit=intent.proposal_count,

        text=conversation,

    )

    if session and persist_messages:

        append_message(db, session, role="user", content=raw_text)

    return {

        "ready": True,

        "action": "proceed",

        "clarify_question": None,

        "topic": topic,

        "proposal_count": proposal_count,

    }


