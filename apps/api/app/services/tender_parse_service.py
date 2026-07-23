"""招标附件 AI 解析（FR-TENDER-03）：异步 parse_jobs + 人审 confirm 后写 L1。"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.models.tender import ParseJob, PlatformTenderLead, TenderAttachment
from app.schemas.platform_tender import (
    ParseJobConfirmOut,
    ParseJobConfirmRequest,
    ParseJobOut,
    PlatformTenderLeadOut,
    TenderAttachmentOut,
)
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.platform_tender_service import _assert_source_url
from app.runtime_stamp import TENDER_PARSER_VERSION

_MAX_SIZE = 50 * 1024 * 1024
_MAX_TEXT_CHARS = 100_000
_ALLOWED_EXT = {".pdf", ".doc", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}
_JUNK_VALUES = frozenset(
    {
        "信息",
        "名称",
        "地址",
        "详见",
        "见附件",
        "见下文",
        "如下",
        "如下表",
        "无",
        "暂无",
        "/",
        "-",
        "—",
        "－",
        "首页",
        "详情",
        "公告",
    }
)
_PRODUCT_JUNK = frozenset(
    {
        "企业",
        "货物",
        "货物类",
        "服务",
        "服务类",
        "工程",
        "工程类",
        "项目",
        "采购",
        "招标",
        "大厅",
        "详情",
        "首页",
        "其他",
        "内容",
    }
)
_TENDER_LLM_SYSTEM = """你是招投标公告结构化抽取助手。从公告正文提取字段，仅输出 JSON（无 markdown）：
{
  "buyer_name": "采购人/招标人全称",
  "industry": "行业或null",
  "region": "省市区，如广东广州",
  "product_name": "采购标的/产品简称",
  "quantity": "数量描述或null",
  "budget_min": null或数字,
  "budget_max": null或数字,
  "deadline": "投标截止日期 YYYY-MM-DD或null",
  "contact_name": "联系人或null",
  "contact_phone": "电话或null",
  "source_url": "http(s)原文链接或null",
  "summary": "一句话项目摘要",
  "project_no": "项目编号或null",
  "published_at": "公告发布日 YYYY-MM-DD或null",
  "procurement_method": "公开招标/询价/竞争性谈判等或null",
  "agent_name": "招标代理/集中采购机构名称或null",
  "buyer_address": "采购人详细地址或null",
  "category": "品目分类（比行业更细）或null",
  "bid_open_date": "开标日期 YYYY-MM-DD或null",
  "sme_preference": true/false/null（是否专门面向中小企业）,
  "qualification_summary": "资格要求摘要（一两句）或null",
  "max_price_limit": null或数字（最高限价）
}
规则：
1. buyer_name 必须是机构全称，不要填「信息」「名称」等表头字。
2. product_name 是采购标的，不要填投标须知/承诺条款长句。
3. region 只要地区名；buyer_address 填详细地址。
4. source_url 只要干净 URL。
5. deadline 是投标截止；bid_open_date 是开标日，二者勿混淆。
6. 无法确定的字段用 null；不要编造。
7. 这是草稿，最终由人工确认。"""


def _tender_attach_dir() -> Path:
    d = Path(settings.STORAGE_DIR) / "tender-attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _attachment_out(att: TenderAttachment) -> TenderAttachmentOut:
    return TenderAttachmentOut.model_validate(att)


def _job_out(job: ParseJob, att: TenderAttachment | None = None) -> ParseJobOut:
    data = ParseJobOut.model_validate(job)
    if att is not None:
        data.attachment = _attachment_out(att)
    return data


def get_parse_job(db: Session, job_id: UUID) -> ParseJob:
    job = db.query(ParseJob).filter(ParseJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="解析任务不存在")
    return job


def get_parse_job_detail(db: Session, job_id: UUID) -> ParseJobOut:
    job = get_parse_job(db, job_id)
    att = db.query(TenderAttachment).filter(TenderAttachment.id == job.attachment_id).first()
    return _job_out(job, att)


def list_parse_jobs(
    db: Session,
    *,
    status_filter: str | None,
    page: int,
    page_size: int,
) -> tuple[list[ParseJobOut], int]:
    q = db.query(ParseJob)
    if status_filter:
        q = q.filter(ParseJob.status == status_filter)
    total = q.count()
    rows = q.order_by(ParseJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    att_ids = {r.attachment_id for r in rows}
    atts = (
        {
            a.id: a
            for a in db.query(TenderAttachment).filter(TenderAttachment.id.in_(att_ids)).all()
        }
        if att_ids
        else {}
    )
    return [_job_out(r, atts.get(r.attachment_id)) for r in rows], total


def enqueue_parse_attachment(db: Session, admin: User, file: UploadFile) -> tuple[ParseJob, bool]:
    file_name = (file.filename or "未命名").strip() or "未命名"
    ext = Path(file_name).suffix.lower()
    if ext and ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的文件类型 {ext}，允许: {', '.join(sorted(_ALLOWED_EXT))}",
        )
    data = file.file.read(_MAX_SIZE + 1)
    if len(data) > _MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 50MB 限制")

    storage_name = f"{uuid.uuid4().hex}_{file_name}"
    path = _tender_attach_dir() / storage_name
    path.write_bytes(data)

    att = TenderAttachment(
        platform_tender_lead_id=None,
        file_name=file_name,
        file_path=str(path),
        file_size=len(data),
        mime_type=file.content_type or None,
        uploaded_by=admin.id,
    )
    db.add(att)
    db.flush()

    job = ParseJob(
        attachment_id=att.id,
        status="pending",
        created_by=admin.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def enqueue_parse_text(db: Session, admin: User, text: str) -> tuple[ParseJob, bool]:
    """粘贴正文：写成 txt 附件，复用同一异步解析 + 人审 confirm。"""
    content = (text or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="正文不能为空")
    if len(content) > _MAX_TEXT_CHARS:
        raise HTTPException(status_code=413, detail=f"正文超过 {_MAX_TEXT_CHARS} 字限制")

    file_name = f"paste-{uuid.uuid4().hex[:10]}.txt"
    data = content.encode("utf-8")
    storage_name = f"{uuid.uuid4().hex}_{file_name}"
    path = _tender_attach_dir() / storage_name
    path.write_bytes(data)

    att = TenderAttachment(
        platform_tender_lead_id=None,
        file_name=file_name,
        file_path=str(path),
        file_size=len(data),
        mime_type="text/plain; charset=utf-8",
        uploaded_by=admin.id,
    )
    db.add(att)
    db.flush()

    job = ParseJob(
        attachment_id=att.id,
        status="pending",
        created_by=admin.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True


def _read_text_snippet(path: Path, file_name: str = "", limit: int = 50000) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    name = file_name or path.name
    ext = Path(name).suffix.lower()
    if ext in (".pdf", ".docx", ".doc", ".txt", ".md"):
        try:
            from app.services.document_text_extract import extract_text_from_bytes

            return extract_text_from_bytes(name, raw)[:limit]
        except Exception:  # noqa: BLE001
            pass
    for enc in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            text = raw.decode(enc)
            if "\x00" in text[:2000]:
                continue
            return text[:limit]
        except UnicodeDecodeError:
            continue
    return f"[二进制附件 {path.name}，请结合文件名与运营补录字段]"


def _is_junk_value(val: str | None) -> bool:
    if not val:
        return True
    s = val.strip()
    if not s or s in _JUNK_VALUES:
        return True
    if len(s) < 2:
        return True
    if s.startswith(("必须", "请", "详见", "参与投标", "以招标文件")):
        return True
    if "必须选择" in s or "用户需求书" in s:
        return True
    return False


def _clean_str(val: Any, max_len: int = 200) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if _is_junk_value(s):
        return None
    s = re.sub(r"\s+", " ", s)
    return s[:max_len] or None


def _clean_url(val: str | None) -> str | None:
    if not val:
        return None
    m = re.search(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", str(val))
    if not m:
        return None
    url = m.group(0).rstrip(".,);]，。》）\"'")
    if len(url) < 10:
        return None
    return url[:500]


def _field_line(text: str, *labels: str) -> str | None:
    """按标签取值；优先「标签：值」完整形式，过滤表头 junk。"""
    for lab in labels:
        patterns = [
            rf"{re.escape(lab)}(?:名称|单位)?\s*[：:]\s*(.+)",
            rf"{re.escape(lab)}\s*[：:=\-]\s*(.+)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if not m:
                continue
            val = m.group(1).strip().splitlines()[0].strip()
            val = re.split(r"[；;。\|｜]", val)[0].strip()
            cleaned = _clean_str(val)
            if cleaned:
                return cleaned
    return None


def _buyer_from_section(text: str) -> str | None:
    """采购人信息块：名称：xxx"""
    m = re.search(
        r"采购人(?:信息|名称)?[\s\S]{0,120}?名称\s*[：:]\s*([^\n]{2,80})",
        text,
    )
    if m:
        return _clean_str(m.group(1).split("地址")[0])
    m2 = re.search(r"(?:^|\n)\s*名称\s*[：:]\s*([^\n]{4,80})", text)
    if m2:
        val = _clean_str(m2.group(1))
        # 避免误取政府集中采购机构名称
        if val and "交易中心" not in val and "采购中心" not in val:
            return val
    return None


def _is_junk_product(val: str | None) -> bool:
    if _is_junk_value(val):
        return True
    s = (val or "").strip()
    if s in _PRODUCT_JUNK:
        return True
    if len(s) <= 2:
        return True
    if re.fullmatch(r"[货物服务工程类]+", s):
        return True
    return False


def _clean_project_name(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    s = re.split(r"[（(]\s*项目编号", s)[0].strip()
    s = re.sub(r"[。；;）)]+$", "", s).strip()
    return _clean_str(s, 200)


def _clean_project_no(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    m = re.search(r"([A-Za-z0-9][A-Za-z0-9\-]{4,40})", s)
    return m.group(1) if m else _clean_str(s, 100)


def _title_line(text: str) -> str | None:
    for line in text.splitlines()[:40]:
        s = line.strip().strip("【】[]「」")
        if len(s) < 8:
            continue
        # 跳过网站导航/面包屑
        if any(x in s for x in ("首页", "登录", "注册", "友情链接", "版权所有")):
            continue
        if s.count("/") >= 2 or s.count("|") >= 2:
            continue
        if re.search(r"(招标公告|采购公告|竞争性谈判|询价公告|中标公告|更正公告)", s):
            return s[:200]
        if re.search(r".{6,}(采购|招标).{0,12}$", s) and "必须" not in s:
            return s[:200]
    # 优先取「项目名称：」后的值作标题兜底
    pn = _clean_project_name(_field_line(text, "采购项目名称", "项目名称"))
    if pn:
        return pn
    first = next(
        (
            ln.strip()
            for ln in text.splitlines()
            if len(ln.strip()) >= 8
            and "首页" not in ln
            and ln.count("/") < 2
        ),
        None,
    )
    return first[:200] if first else None


def _product_from_title(title: str | None) -> str | None:
    if not title:
        return None
    # 去掉后缀「…招标公告/采购公告」
    base = re.sub(r"(招标公告|采购公告|更正公告|中标公告)$", "", title).strip()
    for key in (
        "办公设备",
        "医疗设备",
        "教学设备",
        "信息化设备",
        "便携式计算机",
        "学生电脑",
        "办公电脑",
        "服务器",
        "计算机",
        "家具",
        "校服",
        "培训基地",
        "人才培训",
    ):
        if key in base:
            # 培训基地类：优先整项目名
            if key in ("培训基地", "人才培训") and len(base) >= 8:
                return base[:200]
            return key
    m = re.search(
        r"([\u4e00-\u9fffA-Za-z0-9（）()]{4,80}?)(?:采购|招标|询价|竞争性谈判)",
        title,
    )
    if not m:
        # 标题本身已是项目名
        if len(base) >= 6 and not _is_junk_product(base):
            return base[:200]
        return None
    chunk = m.group(1).strip()
    if _is_junk_product(chunk):
        return None
    org = _buyer_from_title(title)
    if org and chunk.startswith(org):
        product = chunk[len(org) :].strip(" -—_")
        if len(product) >= 4 and not _is_junk_product(product):
            return product[:200]
        # 去掉买方后过短 → 用整段项目名
        if len(chunk) >= 8:
            return chunk[:200]
    if len(chunk) >= 4 and not re.search(r"(学校|医院|局|委|公司|中心)$", chunk):
        return chunk[:200]
    return None


def _resolve_product_name(text: str, title: str | None) -> str | None:
    """产品/标的：有需求表明细用表；否则用项目名称；再回退标题抽取。"""
    project_name = _clean_project_name(_field_line(text, "采购项目名称", "项目名称"))
    table_product, _ = _products_from_table(text)
    from_title = _product_from_title(title)

    # 1) 采购需求表明细（多品类清单更具体）
    if table_product and not _is_junk_product(table_product):
        return table_product
    # 2) 明确的项目名称（无明细表时，项目名称即标的）
    if project_name and not _is_junk_product(project_name):
        return project_name
    # 3) 标题抽取
    if from_title and not _is_junk_product(from_title):
        return from_title
    # 4) 标题去「招标公告」后缀
    if title:
        base = re.sub(r"(招标公告|采购公告|更正公告|中标公告)$", "", title).strip()
        if len(base) >= 6 and not _is_junk_product(base):
            return base[:200]
    return None


def _buyer_from_title(title: str | None) -> str | None:
    if not title:
        return None
    # 优先截到「学校/医院/局/公司/集团…」机构后缀
    m_org = re.match(
        r"^(.+?(?:学校|学院|大学|医院|局|委|办|中心|公司|集团|研究院))",
        title,
    )
    if m_org:
        buyer = m_org.group(1).strip()
        if len(buyer) >= 4:
            return buyer[:120]
    m = re.match(
        r"^(.+?)(?:办公设备|设备|服务|工程|货物|项目)?(?:采购|招标|询价|谈判)",
        title,
    )
    if m:
        buyer = m.group(1).strip().strip(" （([【")
        buyer = re.sub(r"(办公|教学|医疗|信息化|宝安高中部)$", "", buyer).strip()
        if len(buyer) >= 4 and not _is_junk_value(buyer):
            return buyer[:120]
    return None


def _products_from_table(text: str) -> tuple[str | None, str | None]:
    """从采购需求表抽取标的与数量。"""
    rows: list[tuple[str, str]] = []
    for m in re.finditer(
        r"(?:^|\n)\s*([^\n\t]{2,40}?)\s*[|\t]\s*(\d{1,6})\s*[|\t]\s*台",
        text,
    ):
        name = m.group(1).strip().lstrip("0123456789.、. ")
        name = re.sub(r"^(标的名称|名称)$", "", name).strip()
        if name and "技术需求" not in name and "备注" not in name:
            rows.append((name, m.group(2)))
    if not rows:
        for m in re.finditer(
            r"(?:^|\n)\s*((?:宝安|深圳)?[^\n]{2,30}(?:计算机|电脑|设备|服务器|显示器))\s+(\d{1,6})\s*台",
            text,
        ):
            rows.append((m.group(1).strip(), m.group(2)))
    if not rows:
        return None, None
    # 产品：多项时汇总简称
    short = []
    for name, _ in rows[:5]:
        for key in ("便携式计算机", "学生电脑", "办公电脑", "办公设备", "计算机", "电脑"):
            if key in name:
                short.append(key)
                break
        else:
            short.append(name[-12:])
    # 去重保序
    seen = set()
    uniq = []
    for s in short:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    product = "、".join(uniq) if uniq else rows[0][0]
    if len(rows) == 1:
        qty = f"{rows[0][1]}台"
    else:
        qty = "；".join(f"{n} {q}台" for n, q in rows[:5])
        if len(qty) > 80:
            total = sum(int(q) for _, q in rows)
            qty = f"共{total}台（{len(rows)}项）"
    return _clean_str(product, 200), _clean_str(qty, 80)


def _best_source_url(text: str) -> str | None:
    urls = re.findall(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", text)
    cleaned = []
    for u in urls:
        u = u.rstrip(".,);]，。》）\"'")
        if len(u) >= 10:
            cleaned.append(u)
    if not cleaned:
        return None
    preferred = [
        u
        for u in cleaned
        if "szggzy.com" in u or "zfcg.sz.gov.cn" in u or "ccgp.gov.cn" in u
    ]
    # 平台首页优先于登录子路径
    for u in preferred:
        if re.search(r"szggzy\.com:8081/?$", u) or u.rstrip("/").endswith("zfcg.sz.gov.cn"):
            return u[:500]
    return (preferred[0] if preferred else cleaned[0])[:500]


def _contact_phone(text: str) -> str | None:
    # 优先项目联系人电话 / 采购人联系方式
    for lab in ("项目联系人电话", "项目联系电话", "采购人联系方式"):
        m = re.search(rf"{lab}\s*[：:]\s*([0-9\-转]{{8,20}})", text)
        if m:
            return m.group(1).strip()[:50]
    m = re.search(r"项目联系人[\s\S]{0,40}?电话\s*[：:]\s*([0-9\-转]{8,20})", text)
    if m:
        return m.group(1).strip()[:50]
    # 采购人信息块内联系方式
    m = re.search(r"采购人信息[\s\S]{0,200}?联系方式\s*[：:]\s*([0-9\-转]{8,20})", text)
    if m:
        return m.group(1).strip()[:50]
    # 排除技术支持段落后的手机号
    for m in re.finditer(r"(1[3-9]\d{9}|0\d{2,3}-\d{7,8})", text):
        ctx = text[max(0, m.start() - 40) : m.start()]
        if any(x in ctx for x in ("技术支持", "电子营业执照", "CA办理", "咨询电话", "拨打")):
            continue
        return m.group(1)
    return None


def _region_from_text(text: str, title: str | None) -> str | None:
    addr = _field_line(text, "地址", "项目地点", "交货地点", "实施地点")
    if addr and "必须" not in addr:
        # 深圳市南山区茶光路 → 深圳市南山区
        m = re.match(r"((?:[\u4e00-\u9fff]+省)?[\u4e00-\u9fff]+市(?:[\u4e00-\u9fff]+区)?)", addr)
        if m:
            return m.group(1)
        return addr[:40]

    if title:
        m2 = re.search(r"([\u4e00-\u9fff]{2,}市)", title)
        if m2:
            return m2.group(1)

    # 避免「必须选择 广东省-深圳市-…」提示语：仅在非“必须选择”上下文取
    for m in re.finditer(
        r"((?:[\u4e00-\u9fff]+省)[\-—/](?:[\u4e00-\u9fff]+市))",
        text,
    ):
        ctx = text[max(0, m.start() - 12) : m.start()]
        if "必须" in ctx or "选择" in ctx:
            continue
        return m.group(1).replace("—", "-")[:100]
    return None


def _parse_budget(text: str) -> tuple[float | None, float | None]:
    budget_min = budget_max = None
    patterns = [
        r"(?:项目预算|预算金额|采购预算|最高限价)\s*[：:为]?\s*(\d+(?:\.\d+)?)\s*万",
        r"(?:项目预算|预算金额|采购预算|最高限价)\s*[：:为]?\s*(\d{4,}(?:\.\d+)?)\s*元?",
        r"(?:项目预算|预算金额|采购预算|最高限价)[^0-9]{0,12}(\d+(?:\.\d+)?)\s*[-~到至]\s*(\d+(?:\.\d+)?)",
    ]
    for i, pat in enumerate(patterns):
        m = re.search(pat, text)
        if not m:
            continue
        try:
            if i == 0:
                budget_max = float(m.group(1)) * 10000
            elif i == 1:
                budget_max = float(m.group(1))
            elif m.lastindex and m.lastindex >= 2:
                budget_min = float(m.group(1))
                budget_max = float(m.group(2))
            break
        except ValueError:
            continue
    return budget_min, budget_max


def _parse_deadline(text: str) -> str | None:
    # 优先：投标文件递交截止（真实投标截止）
    for lab in (
        "投标文件递交截止时间",
        "投标文件递交截止",
        "递交投标文件截止",
        "投标截止时间",
        "递交截止时间",
    ):
        d = _parse_ymd(text, lab)
        if d:
            return d
    dm = re.search(
        r"(?:投标截止|递交截止|截止时间|报名截止|前递交投标)[^0-9]{0,24}"
        r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})",
        text,
    )
    if not dm:
        dm = re.search(
            r"于\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[^。]{0,20}递交",
            text,
        )
    if not dm:
        # 公告截止时间优先级低于投标递交截止，作兜底
        d2 = _parse_ymd(text, "公告截止时间", "公告截止")
        if d2:
            return d2
        dm = re.search(r"截止[^0-9]{0,8}(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
        if dm:
            y, mo, d = dm.group(1), dm.group(2), dm.group(3)
        else:
            return None
    else:
        y, mo, d = dm.group(1), dm.group(2), dm.group(3)
    try:
        return date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return None


def _parse_ymd(text: str, *label_patterns: str) -> str | None:
    for lab in label_patterns:
        m = re.search(
            rf"{lab}[^0-9]{{0,12}}(\d{{4}})\s*[-/年]\s*(\d{{1,2}})\s*[-/月]\s*(\d{{1,2}})",
            text,
        )
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
            except ValueError:
                continue
    return None


def _extract_sales_fields(text: str) -> dict[str, Any]:
    """销售跟进增强字段抽取。"""
    project_no = _clean_project_no(_field_line(text, "项目编号", "采购编号", "招标编号", "标段编号"))
    if not project_no:
        m_pn = re.search(r"项目编号\s*[：:]\s*([A-Za-z0-9\-]+)", text)
        if m_pn:
            project_no = m_pn.group(1)
    published_at = _parse_ymd(text, "发布时间", "公告时间", "发布日期")
    bid_open = _parse_ymd(text, "开标时间", "开标日期", "投标文件解密时间", "解密时间")
    # 投标截止优先走 _parse_deadline；此处仅补开标
    method = _field_line(text, "招标方式", "采购方式", "招采方式")
    if not method:
        for key in ("公开招标", "询价", "竞争性谈判", "竞争性磋商", "单一来源", "邀请招标"):
            if key in text[:3000]:
                method = key
                break
    agent = _field_line(
        text,
        "代理单位",
        "招标代理",
        "代理机构",
        "集中采购机构",
        "政府集中采购机构",
    )
    if not agent:
        m = re.search(
            r"(?:政府集中采购机构|招标代理(?:机构)?)\s*[\n\r\s]*名称\s*[：:]\s*([^\n]{4,80})",
            text,
        )
        if m:
            agent = _clean_str(m.group(1), 200)
    buyer_address = None
    m_addr = re.search(r"采购人信息[\s\S]{0,200}?地址\s*[：:]\s*([^\n]{4,120})", text)
    if m_addr:
        buyer_address = _clean_str(m_addr.group(1), 200)
    if not buyer_address:
        buyer_address = _field_line(text, "采购人地址", "单位地址")

    category = _field_line(text, "项目类别", "品目分类", "品目", "采购品目", "行业大类", "招采类型")
    max_price = None
    mp = re.search(r"最高限价\s*[：:为]?\s*(\d{4,}(?:\.\d+)?)\s*元?", text)
    if mp:
        try:
            max_price = float(mp.group(1))
        except ValueError:
            pass

    sme: bool | None = None
    if re.search(r"专门面向中小企业|本项目面向中小企业采购", text):
        sme = True
    elif re.search(r"非专门面向中小企业|不专门面向中小企业|本项目非专门面向中小企业", text):
        sme = False

    # 招标人地址（企业标常见）
    if not buyer_address:
        m_ba = re.search(r"招标人地址\s*[：:]\s*([^\n]{4,120})", text)
        if m_ba:
            buyer_address = _clean_str(m_ba.group(1), 200)

    qual = None
    m_q = re.search(
        r"(?:申请人的资格要求|投标人资格要求|资格要求|本项目特定的资格要求)[：:\s]*([\s\S]{20,800}?)(?:\n\s*[三四五六七八]、|\n\s*1\.\d|\n\s*注：)",
        text,
    )
    if m_q:
        raw = re.sub(r"\s+", " ", m_q.group(1)).strip()
        qual = raw[:400] if raw else None
    if not qual:
        bits = []
        for key in ("ISO9001", "独立法人", "营业执照", "三年", "业绩", "注册资金"):
            if key in text:
                bits.append(key)
        if bits:
            qual = "；".join(bits[:6])

    return {
        "project_no": project_no,
        "published_at": published_at,
        "procurement_method": method,
        "agent_name": agent,
        "buyer_address": buyer_address,
        "category": category,
        "bid_open_date": bid_open,
        "sme_preference": sme,
        "qualification_summary": qual,
        "max_price_limit": max_price,
    }


def _heuristic_extract(text: str, file_name: str) -> dict[str, Any]:
    title = _title_line(text)
    source_url = _best_source_url(text)
    budget_min, budget_max = _parse_budget(text)
    deadline = _parse_deadline(text)
    _, table_qty = _products_from_table(text)

    buyer = (
        _field_line(text, "招标人名称", "采购人名称", "招标人", "采购单位", "采购方", "业主单位")
        or _buyer_from_section(text)
        or _buyer_from_title(title)
    )
    # 避免「采购人」匹配到「采购人信息」→「信息」；避免导航词
    if buyer in ("信息", "企业") or _is_junk_value(buyer):
        buyer = (
            _field_line(text, "招标人名称", "采购人名称")
            or _buyer_from_section(text)
            or _buyer_from_title(title)
        )
    if not buyer:
        stem = Path(file_name).stem
        buyer = title[:40] if title else (stem[:80] if stem and not stem.startswith("paste-") else "待补录采购方")

    product = _resolve_product_name(text, title)
    project_name = _clean_project_name(_field_line(text, "采购项目名称", "项目名称"))

    region = _region_from_text(text, title)
    industry = _field_line(text, "所属行业", "行业分类", "行业")
    if not industry and (product or title or project_name):
        blob = f"{product or ''}{title or ''}{project_name or ''}"
        for k, ind in (
            ("培训", "教育/培训"),
            ("人才", "教育/培训"),
            ("办公", "教育/办公"),
            ("电脑", "教育/办公"),
            ("计算机", "教育/办公"),
            ("汽车", "汽车制造"),
            ("医疗", "医疗"),
            ("教学", "教育"),
            ("信息化", "信息化"),
            ("工程", "工程"),
            ("货物", "货物采购"),
        ):
            if k in blob:
                industry = ind
                break

    summary = project_name or title or (text.strip().splitlines()[0][:200] if text.strip() else None)
    contact_name = _field_line(text, "项目联系人", "联系人")
    contact_phone = _contact_phone(text)
    sales = _extract_sales_fields(text)

    # 数量：确定 N 家中标人
    qty = table_qty
    if not qty:
        m_qty = re.search(r"确定\s*(\d+)\s*家中标", text)
        if m_qty:
            qty = f"{m_qty.group(1)}家"
        else:
            qty = _clean_str(_field_line(text, "采购数量"), 50)

    return {
        "buyer_name": _clean_str(buyer, 200) or "待补录采购方",
        "industry": _clean_str(industry, 100),
        "region": _clean_str(region, 100),
        "product_name": _clean_str(product, 200),
        "quantity": qty,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "deadline": deadline,
        "contact_name": _clean_str(contact_name, 100),
        "contact_phone": contact_phone,
        "source_url": source_url,
        "summary": _clean_str(summary, 200),
        **sales,
        "_parse_source": "heuristic",
        "_input": "paste" if file_name.startswith("paste-") else "attachment",
        "_parser_version": TENDER_PARSER_VERSION,
    }


def _extract_json_obj(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _merge_llm_result(base: dict[str, Any], llm: dict[str, Any], provider: str) -> dict[str, Any]:
    out = dict(base)
    for key in (
        "buyer_name",
        "industry",
        "region",
        "product_name",
        "quantity",
        "contact_name",
        "contact_phone",
        "summary",
        "project_no",
        "procurement_method",
        "agent_name",
        "buyer_address",
        "category",
        "qualification_summary",
    ):
        cleaned = _clean_str(llm.get(key), 400 if key == "qualification_summary" else 200)
        if not cleaned:
            continue
        if key == "product_name" and _is_junk_product(cleaned):
            continue
        # 不让短 junk 覆盖已有优质字段
        if key == "product_name" and out.get("product_name") and len(cleaned) < 6:
            continue
        if key == "product_name" and out.get("product_name") and len(str(out["product_name"])) > len(cleaned) + 4:
            continue
        out[key] = cleaned
    url = _clean_url(llm.get("source_url"))
    if url:
        out["source_url"] = url
    for bk in ("budget_min", "budget_max", "max_price_limit"):
        if llm.get(bk) is not None:
            try:
                out[bk] = float(llm[bk])
            except (TypeError, ValueError):
                pass
    for dk in ("deadline", "published_at", "bid_open_date"):
        if llm.get(dk):
            raw_d = str(llm[dk]).strip()[:10]
            if re.match(r"\d{4}-\d{2}-\d{2}", raw_d):
                out[dk] = raw_d
    if llm.get("sme_preference") is not None:
        out["sme_preference"] = bool(llm["sme_preference"])
    out["_parse_source"] = "llm" if provider != "fake" else "fake"
    return out


async def _llm_extract(db: Session, text: str, tenant_id: UUID | None) -> tuple[dict[str, Any] | None, str]:
    tid = tenant_id or UUID(int=0)
    result = await llm_service.chat(
        db,
        tid,
        [
            LLMMessage(role="system", content=_TENDER_LLM_SYSTEM),
            LLMMessage(role="user", content=text[:12000]),
        ],
        llm_source="platform",
        check_platform_quota=False,
    )
    data = _extract_json_obj(result.content)
    return data, result.provider


def _llm_extract_sync(db: Session, text: str, tenant_id: UUID | None) -> tuple[dict[str, Any] | None, str]:
    try:
        return asyncio.run(_llm_extract(db, text, tenant_id))
    except Exception:  # noqa: BLE001
        return None, "none"


def run_parse_job(job_id: str) -> None:
    """Background：pending/running → succeeded/failed。启发式 + 平台 LLM（失败则回退启发式）。"""
    db = SessionLocal()
    try:
        job = db.query(ParseJob).filter(ParseJob.id == UUID(job_id)).first()
        if not job or job.status not in ("pending", "running"):
            return
        job.status = "running"
        db.commit()

        att = db.query(TenderAttachment).filter(TenderAttachment.id == job.attachment_id).first()
        if not att:
            job.status = "failed"
            job.error_message = "附件不存在"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        path = Path(att.file_path)
        snippet = _read_text_snippet(path, att.file_name)
        result = _heuristic_extract(snippet, att.file_name)

        admin = db.query(User).filter(User.id == job.created_by).first()
        llm_data, provider = _llm_extract_sync(db, snippet, admin.tenant_id if admin else None)
        if llm_data:
            result = _merge_llm_result(result, llm_data, provider)

        job.result_json = result
        job.status = "succeeded"
        job.error_message = None
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            job = db.query(ParseJob).filter(ParseJob.id == UUID(job_id)).first()
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:500]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


def confirm_parse_job(
    db: Session,
    admin: User,
    job_id: UUID,
    body: ParseJobConfirmRequest,
) -> ParseJobConfirmOut:
    job = get_parse_job(db, job_id)
    if job.status == "confirmed":
        raise HTTPException(status_code=409, detail="该解析任务已确认入库")
    if job.status != "succeeded":
        raise HTTPException(
            status_code=409,
            detail=f"仅 succeeded 状态可确认（当前 {job.status}）；未确认不得 published",
        )

    _assert_source_url(
        source_url=body.source_url,
        has_source_document=body.has_source_document,
        status_value="draft",
    )

    lead = PlatformTenderLead(
        buyer_name=body.buyer_name.strip(),
        industry=body.industry,
        region=body.region,
        product_name=body.product_name,
        quantity=body.quantity,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
        deadline=body.deadline,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        source_url=body.source_url,
        summary=body.summary,
        project_no=body.project_no,
        published_at=body.published_at,
        procurement_method=body.procurement_method,
        agent_name=body.agent_name,
        buyer_address=body.buyer_address,
        category=body.category,
        bid_open_date=body.bid_open_date,
        sme_preference=body.sme_preference,
        qualification_summary=body.qualification_summary,
        max_price_limit=body.max_price_limit,
        source_channel="attachment_ai",
        status="draft",  # D7：confirm 只写草稿，禁止直接 published
        created_by=admin.id,
    )
    db.add(lead)
    db.flush()

    att = db.query(TenderAttachment).filter(TenderAttachment.id == job.attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    att.platform_tender_lead_id = lead.id

    job.status = "confirmed"
    job.confirmed_lead_id = lead.id
    db.commit()
    db.refresh(lead)
    db.refresh(job)

    return ParseJobConfirmOut(
        parse_job_id=job.id,
        lead=PlatformTenderLeadOut.model_validate(lead),
        attachment_id=att.id,
    )
