"""CRM 数据导入服务。"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import TenantContext
from app.models.crm import (
    IMPORT_ROW_STATUSES,
    CrmImportJob,
    CrmImportRow,
    Customer,
    Lead,
)
from app.schemas.crm import validate_customer_status, validate_lead_status, validate_lead_mobile_value
from app.permissions import SYSTEM_ROLE_ADMIN
from app.services.crm.crm_scope_service import assert_can_view_customer, assert_can_view_lead
from app.services.crm.schema_service import ensure_entity_schema, list_active_fields, validate_extra_data
from app.services.membership_service import get_membership

IMPORT_ENTITY_TYPES = frozenset({"lead", "customer"})

# CSV 表头常见别名 → field_key（label 变更后仍兼容旧模板）
IMPORT_COLUMN_ALIASES: dict[str, str] = {
    "联系人": "contact_name",
}
MAX_IMPORT_ROWS = 5000
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

LEAD_DB_KEYS = frozenset(
    {"company_name", "contact_name", "mobile", "phone", "email", "source", "status", "remark"}
)
CUSTOMER_DB_KEYS = frozenset({"company_name", "mobile", "phone", "email", "status", "remark"})

# 导入模板必填（与前端 ENTITY_REQUIRED_KEYS / 导入校验一致，覆盖存量 schema）
LEAD_IMPORT_REQUIRED_KEYS = frozenset({"company_name", "contact_name", "mobile", "status"})
CUSTOMER_IMPORT_REQUIRED_KEYS = frozenset({"company_name"})


def _import_field_required(entity_type: str, field_key: str, *, schema_required: bool) -> bool:
    if schema_required:
        return True
    keys = LEAD_IMPORT_REQUIRED_KEYS if entity_type == "lead" else CUSTOMER_IMPORT_REQUIRED_KEYS
    return field_key in keys


def _import_dir(tenant_id: UUID, job_id: UUID) -> Path:
    d = Path(settings.STORAGE_DIR) / "crm_imports" / str(tenant_id) / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _default_options(entity_type: str) -> dict:
    if entity_type == "customer":
        return {
            "duplicate_key": "mobile",
            "on_duplicate": "skip",
            "default_status": "潜在",
            "default_source": "导入",
        }
    return {
        "duplicate_key": "mobile",
        "on_duplicate": "skip",
        "default_status": "待跟进",
        "default_source": "导入",
    }


def _decode_csv_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="无法识别 CSV 编码，请另存为 UTF-8 或 GBK")


def _parse_csv(content: bytes) -> tuple[list[str], list[dict]]:
    text = _decode_csv_text(content)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV 缺少表头")
    columns = [c.strip() for c in reader.fieldnames if c and c.strip()]
    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):
        if i - 1 > MAX_IMPORT_ROWS:
            raise HTTPException(status_code=400, detail=f"超过最大行数 {MAX_IMPORT_ROWS}")
        cleaned = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        if any(v for v in cleaned.values()):
            rows.append(cleaned)
    return columns, rows


def _parse_xlsx(content: bytes) -> tuple[list[str], list[dict]]:
    try:
        import openpyxl
    except ImportError as e:
        raise HTTPException(status_code=400, detail="XLSX 解析需要 openpyxl") from e
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if not header:
        raise HTTPException(status_code=400, detail="XLSX 缺少表头")
    columns = [str(c).strip() for c in header if c is not None and str(c).strip()]
    rows: list[dict] = []
    for i, cells in enumerate(rows_iter, start=2):
        if i - 1 > MAX_IMPORT_ROWS:
            raise HTTPException(status_code=400, detail=f"超过最大行数 {MAX_IMPORT_ROWS}")
        data = {}
        for idx, col in enumerate(columns):
            val = cells[idx] if idx < len(cells) else None
            if val is not None:
                if isinstance(val, float):
                    rounded = round(val)
                    if abs(val - rounded) < 1e-6:
                        val = str(int(rounded))
                    else:
                        val = str(val).strip()
                elif isinstance(val, int):
                    val = str(val)
                else:
                    val = str(val).strip()
                data[col] = val
        if any(data.values()):
            rows.append(data)
    return columns, rows


def parse_upload_file(filename: str, content: bytes) -> tuple[list[str], list[dict]]:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return _parse_csv(content)
    if lower.endswith(".xlsx"):
        return _parse_xlsx(content)
    raise HTTPException(status_code=400, detail="仅支持 CSV 或 XLSX")


def _import_header_label(label: str, *, is_required: bool) -> str:
    return f"{label}*" if is_required else label


def _strip_import_header(col: str) -> str:
    return col.rstrip("*").strip()


def suggest_mapping(
    db: Session, tenant_id: UUID, entity_type: str, columns: list[str]
) -> dict[str, str]:
    ensure_entity_schema(db, tenant_id, entity_type)
    fields = list_active_fields(db, tenant_id, entity_type)
    label_map: dict[str, str] = {}
    for f in fields:
        label_map[f.label] = f.field_key
        if _import_field_required(entity_type, f.field_key, schema_required=bool(f.is_required)):
            label_map[_import_header_label(f.label, is_required=True)] = f.field_key
    key_set = {f.field_key for f in fields}
    out: dict[str, str] = {}
    for col in columns:
        bare = _strip_import_header(col)
        if col in key_set:
            out[col] = col
        elif bare in key_set:
            out[col] = bare
        elif col in label_map:
            out[col] = label_map[col]
        elif bare in label_map:
            out[col] = label_map[bare]
        elif bare in IMPORT_COLUMN_ALIASES and IMPORT_COLUMN_ALIASES[bare] in key_set:
            out[col] = IMPORT_COLUMN_ALIASES[bare]
    return out


def build_template_csv(db: Session, tenant_id: UUID, entity_type: str) -> str:
    ensure_entity_schema(db, tenant_id, entity_type)
    fields = list_active_fields(db, tenant_id, entity_type)
    skip = {"created_by_user_id", "created_at", "updated_at", "converted_customer_id", "converted_from_lead_id"}
    headers: list[str] = []
    for f in fields:
        if f.field_key in skip:
            continue
        if f.field_type in ("user_ref", "territory_ref", "ref"):
            continue
        if not f.is_active:
            continue
        headers.append(
            _import_header_label(
                f.label,
                is_required=_import_field_required(entity_type, f.field_key, schema_required=bool(f.is_required)),
            )
        )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    return buf.getvalue()


def create_import_job(
    db: Session,
    ctx: TenantContext,
    entity_type: str,
    filename: str,
    content: bytes,
) -> tuple[CrmImportJob, list[str], dict[str, str]]:
    if entity_type not in IMPORT_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持导入实体: {entity_type}")

    columns, rows = parse_upload_file(filename, content)
    job = CrmImportJob(
        tenant_id=ctx.tenant_id,
        entity_type=entity_type,
        status="draft",
        file_name=filename,
        file_storage_path="",
        mapping={},
        options=_default_options(entity_type),
        created_by_user_id=ctx.user.id,
        total_rows=len(rows),
        columns=columns,
    )
    db.add(job)
    db.flush()

    dest = _import_dir(ctx.tenant_id, job.id) / filename
    dest.write_bytes(content)
    job.file_storage_path = str(dest)
    db.commit()
    db.refresh(job)

    job._parsed_rows = rows  # type: ignore[attr-defined]
    suggested = suggest_mapping(db, ctx.tenant_id, entity_type, columns)
    return job, columns, suggested


def get_job(db: Session, tenant_id: UUID, job_id: UUID) -> CrmImportJob | None:
    return (
        db.query(CrmImportJob)
        .filter(CrmImportJob.id == job_id, CrmImportJob.tenant_id == tenant_id)
        .first()
    )


def _load_rows(job: CrmImportJob) -> list[dict]:
    path = Path(job.file_storage_path)
    if not path.is_file():
        raise HTTPException(status_code=400, detail="导入文件不存在")
    _, rows = parse_upload_file(path.name, path.read_bytes())
    return rows


def _perm_set(ctx: TenantContext, db: Session) -> set[str]:
    membership = get_membership(db, ctx.user.id, ctx.tenant_id)
    if not membership or not membership.role:
        return set()
    return {p.permission_code for p in membership.role.permissions}


def _row_to_payload(
    db: Session,
    ctx: TenantContext,
    entity_type: str,
    raw: dict,
    mapping: dict,
    options: dict,
) -> tuple[dict, dict, str | None]:
    """返回 db_fields, extra_data, error。"""
    ensure_entity_schema(db, ctx.tenant_id, entity_type)
    field_map = {f.field_key: f for f in list_active_fields(db, ctx.tenant_id, entity_type)}
    db_keys = LEAD_DB_KEYS if entity_type == "lead" else CUSTOMER_DB_KEYS

    db_fields: dict = {}
    extra: dict = {}
    for col, field_key in mapping.items():
        if col not in raw:
            continue
        val = raw.get(col)
        if val is None or val == "":
            continue
        fdef = field_map.get(field_key)
        if not fdef or not fdef.is_active:
            continue
        if field_key in db_keys:
            db_fields[field_key] = val
        else:
            extra[field_key] = val

    if not db_fields.get("company_name"):
        return {}, {}, "公司名称不能为空"

    if entity_type == "lead":
        if not db_fields.get("contact_name") or not str(db_fields.get("contact_name")).strip():
            return {}, {}, "联系人姓名不能为空"
        db_fields.setdefault("status", options.get("default_status") or "待跟进")
        db_fields.setdefault("source", options.get("default_source") or "导入")
        try:
            validate_lead_status(db_fields["status"])
        except ValueError as e:
            return {}, {}, str(e)
        mobile, mobile_err = validate_lead_mobile_value(db_fields.get("mobile"), required=True)
        if mobile_err:
            return {}, {}, mobile_err
        db_fields["mobile"] = mobile
    else:
        db_fields.setdefault("status", options.get("default_status") or "潜在")
        try:
            validate_customer_status(db_fields["status"])
        except ValueError as e:
            return {}, {}, str(e)

        mobile = db_fields.get("mobile")
        if mobile:
            mobile_str = str(mobile).strip()
            if _PHONE_RE.match(mobile_str):
                db_fields["mobile"] = mobile_str
            else:
                db_fields.pop("mobile", None)

    owner = options.get("default_owner_user_id") or str(ctx.user.id)
    db_fields["owner_user_id"] = UUID(str(owner))

    try:
        extra = validate_extra_data(db, ctx.tenant_id, entity_type, extra, is_create=True)
    except HTTPException as e:
        return {}, {}, str(e.detail)

    return db_fields, extra, None


def _is_admin(ctx: TenantContext) -> bool:
    return ctx.membership.role.is_system and ctx.membership.role.code == SYSTEM_ROLE_ADMIN


def list_import_jobs(
    db: Session,
    ctx: TenantContext,
    *,
    page: int = 1,
    page_size: int = 20,
    entity_type: str | None = None,
) -> tuple[list[CrmImportJob], int]:
    query = db.query(CrmImportJob).filter(CrmImportJob.tenant_id == ctx.tenant_id)
    if not _is_admin(ctx):
        query = query.filter(CrmImportJob.created_by_user_id == ctx.user.id)
    if entity_type:
        if entity_type not in IMPORT_ENTITY_TYPES:
            raise HTTPException(status_code=400, detail=f"不支持的 entity_type: {entity_type}")
        query = query.filter(CrmImportJob.entity_type == entity_type)
    total = query.count()
    items = (
        query.order_by(CrmImportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def _apply_update_to_entity(
    db: Session,
    ctx: TenantContext,
    existing: Lead | Customer,
    entity_type: str,
    db_fields: dict,
    extra: dict,
) -> None:
    if entity_type == "lead":
        assert_can_view_lead(ctx, db, existing.owner_user_id, existing.territory_id)
        if "company_name" in db_fields:
            existing.company_name = db_fields["company_name"]
        for key in ("contact_name", "mobile", "phone", "email", "source", "remark"):
            if key in db_fields:
                setattr(existing, key, db_fields[key])
        if "status" in db_fields:
            validate_lead_status(db_fields["status"])
            existing.status = db_fields["status"]
    else:
        assert_can_view_customer(ctx, db, existing.owner_user_id, existing.territory_id)
        if "company_name" in db_fields:
            existing.company_name = db_fields["company_name"]
        for key in ("mobile", "phone", "email", "remark"):
            if key in db_fields:
                setattr(existing, key, db_fields[key])
        if "status" in db_fields:
            validate_customer_status(db_fields["status"])
            existing.status = db_fields["status"]
    if extra:
        merged = dict(existing.extra_data or {})
        merged.update(extra)
        existing.extra_data = validate_extra_data(db, ctx.tenant_id, entity_type, merged)


def _find_duplicate(db: Session, tenant_id: UUID, entity_type: str, key: str, value) -> Lead | Customer | None:
    if not value:
        return None
    if entity_type == "lead":
        if key == "mobile":
            return (
                db.query(Lead)
                .filter(Lead.tenant_id == tenant_id, Lead.mobile == value, Lead.deleted_at.is_(None))
                .first()
            )
    elif entity_type == "customer":
        if key == "mobile":
            return (
                db.query(Customer)
                .filter(Customer.tenant_id == tenant_id, Customer.mobile == value, Customer.deleted_at.is_(None))
                .first()
            )
    return None


def preview_job(db: Session, ctx: TenantContext, job: CrmImportJob) -> dict:
    rows = _load_rows(job)
    mapping = job.mapping or {}
    options = {**_default_options(job.entity_type), **(job.options or {})}
    preview_rows: list[dict] = []
    error_count = 0
    ok_count = 0

    for i, raw in enumerate(rows[:20], start=1):
        db_fields, extra, err = _row_to_payload(db, ctx, job.entity_type, raw, mapping, options)
        if err:
            preview_rows.append(
                {"row_number": i, "status": "preview_error", "error_message": err, "data": raw}
            )
            error_count += 1
        else:
            dup_key = options.get("duplicate_key")
            dup = None
            if dup_key and db_fields.get(dup_key):
                dup = _find_duplicate(db, ctx.tenant_id, job.entity_type, dup_key, db_fields.get(dup_key))
            if dup and options.get("on_duplicate") == "skip":
                preview_rows.append(
                    {
                        "row_number": i,
                        "status": "preview_ok",
                        "error_message": "将跳过重复",
                        "data": raw,
                    }
                )
            elif dup and options.get("on_duplicate") == "update":
                preview_rows.append(
                    {
                        "row_number": i,
                        "status": "preview_ok",
                        "error_message": "将更新已有记录",
                        "data": raw,
                    }
                )
            else:
                preview_rows.append({"row_number": i, "status": "preview_ok", "data": raw})
            ok_count += 1

    job.status = "previewing"
    db.commit()
    return {"preview_rows": preview_rows, "error_count": error_count, "ok_count": ok_count}


def run_import(db: Session, ctx: TenantContext, job: CrmImportJob) -> CrmImportJob:
    if job.status == "completed":
        return job
    rows = _load_rows(job)
    mapping = job.mapping or {}
    options = {**_default_options(job.entity_type), **(job.options or {})}

    db.query(CrmImportRow).filter(CrmImportRow.job_id == job.id).delete()
    job.status = "importing"
    job.started_at = datetime.now(timezone.utc)
    job.success_count = 0
    job.skip_count = 0
    job.error_count = 0
    job.total_rows = len(rows)
    db.commit()

    perms = _perm_set(ctx, db)
    assign_perm = "crm.lead.assign" if job.entity_type == "lead" else "crm.customer.assign"
    create_perm = "crm.lead.create" if job.entity_type == "lead" else "crm.customer.create"
    if create_perm not in perms:
        job.status = "failed"
        db.commit()
        raise HTTPException(status_code=403, detail="无创建权限")

    for i, raw in enumerate(rows, start=1):
        db_fields, extra, err = _row_to_payload(db, ctx, job.entity_type, raw, mapping, options)
        if err:
            job.error_count += 1
            db.add(
                CrmImportRow(
                    job_id=job.id,
                    row_number=i,
                    raw_data=raw,
                    status="error",
                    error_message=err,
                )
            )
            continue

        owner_id = db_fields.pop("owner_user_id", ctx.user.id)
        if owner_id != ctx.user.id and assign_perm not in perms:
            owner_id = ctx.user.id

        dup_key = options.get("duplicate_key")
        dup_val = db_fields.get(dup_key) if dup_key else None
        existing = _find_duplicate(db, ctx.tenant_id, job.entity_type, dup_key or "", dup_val) if dup_val else None

        if existing and options.get("on_duplicate") == "skip":
            job.skip_count += 1
            db.add(
                CrmImportRow(
                    job_id=job.id,
                    row_number=i,
                    raw_data=raw,
                    status="skip",
                    error_message="重复跳过",
                    target_id=existing.id,
                )
            )
            continue

        if existing and options.get("on_duplicate") == "update":
            try:
                update_fields = dict(db_fields)
                update_fields.pop("owner_user_id", None)
                _apply_update_to_entity(db, ctx, existing, job.entity_type, update_fields, extra)
                job.success_count += 1
                db.add(
                    CrmImportRow(
                        job_id=job.id,
                        row_number=i,
                        raw_data=raw,
                        status="success",
                        error_message="已更新",
                        target_id=existing.id,
                    )
                )
            except HTTPException as e:
                job.error_count += 1
                db.add(
                    CrmImportRow(
                        job_id=job.id,
                        row_number=i,
                        raw_data=raw,
                        status="error",
                        error_message=str(e.detail),
                    )
                )
            except Exception as e:
                job.error_count += 1
                db.add(
                    CrmImportRow(
                        job_id=job.id,
                        row_number=i,
                        raw_data=raw,
                        status="error",
                        error_message=str(e),
                    )
                )
            continue

        try:
            if job.entity_type == "lead":
                lead = Lead(
                    tenant_id=ctx.tenant_id,
                    company_name=db_fields.pop("company_name"),
                    contact_name=db_fields.get("contact_name"),
                    mobile=db_fields.get("mobile"),
                    phone=db_fields.get("phone"),
                    email=db_fields.get("email"),
                    source=db_fields.get("source"),
                    status=db_fields.get("status", "待跟进"),
                    remark=db_fields.get("remark"),
                    owner_user_id=owner_id,
                    extra_data=extra,
                    created_by_user_id=ctx.user.id,
                )
                db.add(lead)
                db.flush()
                target_id = lead.id
            else:
                customer = Customer(
                    tenant_id=ctx.tenant_id,
                    company_name=db_fields.pop("company_name"),
                    mobile=db_fields.get("mobile"),
                    phone=db_fields.get("phone"),
                    email=db_fields.get("email"),
                    status=db_fields.get("status", "潜在"),
                    remark=db_fields.get("remark"),
                    owner_user_id=owner_id,
                    extra_data=extra,
                    created_by_user_id=ctx.user.id,
                )
                db.add(customer)
                db.flush()
                target_id = customer.id

            job.success_count += 1
            db.add(
                CrmImportRow(
                    job_id=job.id,
                    row_number=i,
                    raw_data=raw,
                    status="success",
                    target_id=target_id,
                )
            )
        except Exception as e:
            job.error_count += 1
            db.add(
                CrmImportRow(
                    job_id=job.id,
                    row_number=i,
                    raw_data=raw,
                    status="error",
                    error_message=str(e),
                )
            )

    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def build_errors_csv(db: Session, job: CrmImportJob) -> str:
    rows = (
        db.query(CrmImportRow)
        .filter(CrmImportRow.job_id == job.id, CrmImportRow.status.in_(("error", "skip")))
        .order_by(CrmImportRow.row_number)
        .all()
    )
    if not rows:
        return "row_number,error_message\n"
    all_keys: list[str] = []
    for r in rows:
        for k in r.raw_data:
            if k not in all_keys:
                all_keys.append(k)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["row_number", "error_message", "status", *all_keys])
    writer.writeheader()
    for r in rows:
        line = {"row_number": r.row_number, "error_message": r.error_message or "", "status": r.status}
        line.update(r.raw_data)
        writer.writerow(line)
    return buf.getvalue()


def update_job_mapping(
    db: Session, job: CrmImportJob, mapping: dict, options: dict | None
) -> CrmImportJob:
    job.mapping = mapping
    if options:
        merged = {**_default_options(job.entity_type), **job.options, **options}
        job.options = merged
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
