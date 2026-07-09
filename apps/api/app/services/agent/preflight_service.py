"""创作预检：Workflow 启动前判断用户输入是否足够。"""



from __future__ import annotations



import re

from uuid import UUID



from sqlalchemy.orm import Session



from app.models import AgentSession

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





def _local_clarify(message: str) -> str | None:

    text = message.strip()

    if len(text) < 6:

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

    text = message.strip()

    in_clarify_flow = bool(session and _has_clarify_history(db, session))

    conversation = (

        _build_conversation_context(db, session, text) if session else text

    )



    if not in_clarify_flow:

        local_q = _local_clarify(text)

        if local_q:

            if session and persist_messages:

                append_message(db, session, role="user", content=text)

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

        industry_code=industry_code,

        llm_source=llm_source,

        conversation_context=conversation,

    )



    if intent.action == "clarify" or not (intent.topic or text):

        question = intent.clarify_question or "请补充具体主题、目标读者或想强调的核心要点。"

        if session and persist_messages:

            append_message(db, session, role="user", content=text)

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

        append_message(db, session, role="user", content=text)

    return {

        "ready": True,

        "action": "proceed",

        "clarify_question": None,

        "topic": topic,

        "proposal_count": proposal_count,

    }


