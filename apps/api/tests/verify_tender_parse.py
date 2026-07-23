#!/usr/bin/env python3
"""v1.3 FR-TENDER-03：附件解析 + 人审 confirm；未 confirm 不得 published。"""
from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import USE_LIVE, check, req, _get_test_client
from tests.verify_crm_helpers import finish_phase


def alembic_current() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def upload_parse(token: str, content: bytes, filename: str = "tender.txt"):
    path = "/api/v1/admin/platform-tender-leads/parse-attachment"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, content, "text/plain")}
    if not USE_LIVE:
        client = _get_test_client()
        r = client.post(path, headers=headers, files=files)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.status_code, data
    raise RuntimeError("verify_tender_parse 请用 TestClient（勿设 VERIFY_LIVE_API=1）")


def main() -> int:
    results: list[bool] = []
    out = alembic_current()
    results.append(check(f"VTP-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()[:200]))

    pa = login("13800000000", "admin123456")
    tenant = login("13900000099", "test123456")
    tag = uuid.uuid4().hex[:6]

    code, _ = req("POST", "/admin/platform-tender-leads/parse-attachment", token=tenant)
    results.append(check("VTP-1 非平台不可解析", code in (403, 422, 400), f"{code}"))

    # 造一条仍为 pending 的任务，验证未 succeeded 不可 confirm（避开 TestClient 后台竞态）
    from app.database import SessionLocal
    from app.models import User
    from app.models.tender import ParseJob, TenderAttachment

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.phone == "13800000000").first()
        att = TenderAttachment(
            file_name=f"pending-{tag}.txt",
            file_path=str(API_ROOT / "storage" / "tender-attachments" / f"pending-{tag}.txt"),
            file_size=1,
            mime_type="text/plain",
            uploaded_by=admin.id,
        )
        db.add(att)
        db.flush()
        pending_job = ParseJob(attachment_id=att.id, status="pending", created_by=admin.id)
        db.add(pending_job)
        db.commit()
        db.refresh(pending_job)
        pending_id = str(pending_job.id)
    finally:
        db.close()

    code, blocked = req(
        "POST",
        f"/admin/platform-tender-leads/parse-jobs/{pending_id}/confirm",
        token=pa,
        body={"buyer_name": f"抢跑-{tag}"},
    )
    results.append(check("VTP-3 未 succeeded 不可 confirm", code == 409, f"{code} {blocked}"))

    sample = f"""采购方：附件医院-{tag}
行业：医疗
地区：浙江杭州
产品：离心泵
数量：2台
预算：50000-120000
截止：2026-12-31
联系人：李工
联系电话：13912345678
原文链接：https://example.com/parse/{tag}
摘要：人审冒烟样本
""".encode("utf-8")

    code, job = upload_parse(pa, sample, f"tender-{tag}.txt")
    results.append(check("VTP-2 上传创建 parse_job", code == 201 and bool((job or {}).get("id")), f"{code}"))
    job_id = (job or {}).get("id")

    paste_body = {
        "text": f"采购方：粘贴医院-{tag}\n行业：教育\n地区：上海\n产品：投影仪\n原文链接：https://example.com/paste/{tag}\n"
    }
    code, paste_job = req("POST", "/admin/platform-tender-leads/parse-text", token=pa, body=paste_body)
    results.append(
        check("VTP-2b 粘贴创建 parse_job", code == 201 and bool((paste_job or {}).get("id")), f"{code}")
    )
    paste_id = (paste_job or {}).get("id")
    if paste_id and (paste_job or {}).get("status") == "pending":
        from app.services.tender_parse_service import run_parse_job

        run_parse_job(str(paste_id))
        code, paste_final = req("GET", f"/admin/platform-tender-leads/parse-jobs/{paste_id}", token=pa)
        prj = (paste_final or {}).get("result_json") or {}
        results.append(
            check(
                "VTP-2c 粘贴解析抽字段",
                (paste_final or {}).get("status") == "succeeded" and tag in str(prj.get("buyer_name") or ""),
                f"status={(paste_final or {}).get('status')} buyer={prj.get('buyer_name')}",
            )
        )
    else:
        results.append(check("VTP-2c 粘贴解析抽字段", False, f"no paste job: {paste_job}"))

    final = job
    for _ in range(20):
        if not job_id:
            break
        code, final = req("GET", f"/admin/platform-tender-leads/parse-jobs/{job_id}", token=pa)
        if code == 200 and (final or {}).get("status") in ("succeeded", "failed", "confirmed"):
            break
        time.sleep(0.1)
        if (final or {}).get("status") == "pending":
            from app.services.tender_parse_service import run_parse_job

            run_parse_job(str(job_id))

    rj = (final or {}).get("result_json") or {}
    buyer = str(rj.get("buyer_name") or "")
    results.append(
        check(
            "VTP-4 解析 succeeded 且抽到采购方/链接",
            (final or {}).get("status") == "succeeded"
            and tag in buyer
            and bool(rj.get("source_url")),
            f"status={(final or {}).get('status')} buyer={buyer} url={rj.get('source_url')}",
        )
    )

    code, confirmed = req(
        "POST",
        f"/admin/platform-tender-leads/parse-jobs/{job_id}/confirm",
        token=pa,
        body={
            "buyer_name": rj.get("buyer_name") or f"附件医院-{tag}",
            "industry": rj.get("industry"),
            "region": rj.get("region"),
            "product_name": rj.get("product_name"),
            "quantity": rj.get("quantity"),
            "budget_min": rj.get("budget_min"),
            "budget_max": rj.get("budget_max"),
            "deadline": rj.get("deadline"),
            "contact_name": rj.get("contact_name"),
            "contact_phone": rj.get("contact_phone"),
            "source_url": rj.get("source_url"),
            "summary": rj.get("summary"),
            "has_source_document": True,
        },
    )
    lead = (confirmed or {}).get("lead") or {}
    results.append(
        check(
            "VTP-5 confirm 写 L1 草稿 attachment_ai",
            code == 200
            and lead.get("status") == "draft"
            and lead.get("source_channel") == "attachment_ai"
            and bool(lead.get("source_url")),
            f"{code} status={lead.get('status')} ch={lead.get('source_channel')}",
        )
    )
    lead_id = lead.get("id")

    code, again = req(
        "POST",
        f"/admin/platform-tender-leads/parse-jobs/{job_id}/confirm",
        token=pa,
        body={"buyer_name": "二次确认"},
    )
    results.append(check("VTP-6 重复 confirm 409", code == 409, f"{code} {again}"))

    if lead_id:
        code, pub = req("POST", f"/admin/platform-tender-leads/{lead_id}/publish", token=pa)
        results.append(
            check("VTP-7 人审后可发布", code == 200 and (pub or {}).get("status") == "published", f"{code}")
        )
        req("DELETE", f"/admin/platform-tender-leads/{lead_id}", token=pa)

    return finish_phase("v1.3-tender-parse", results)


if __name__ == "__main__":
    raise SystemExit(main())
