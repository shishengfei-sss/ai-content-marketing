#!/usr/bin/env python3
"""v0.7 CRM-2/3 Phase A 验收：建表 + 默认管道种子 + 权限种子 + schema_seeds（含 payments）。

详见 docs/v0.7-crm-deal执行计划.md §Phase A。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import is_at_expected_head
from tests.http_client import check


# v0.7 新增 CRM-2/3 权限码（与 app.permissions / alembic 037 一致）
CRM_23_NEW_PERMISSIONS: tuple[str, ...] = (
    "crm.deal.list_own",
    "crm.deal.list_team",
    "crm.deal.list_territory",
    "crm.deal.list_all",
    "crm.deal.view",
    "crm.deal.create",
    "crm.deal.edit",
    "crm.deal.assign",
    "crm.deal.convert",
    "crm.deal.close",
    "crm.deal.delete",
    "crm.pipeline.manage",
    "crm.product.manage",
    "crm.quote.list_own",
    "crm.quote.list_all",
    "crm.quote.view",
    "crm.quote.create",
    "crm.quote.edit",
    "crm.quote.send",
    "crm.quote.accept",
    "crm.quote.delete",
    "crm.contract.list_own",
    "crm.contract.list_all",
    "crm.contract.view",
    "crm.contract.create",
    "crm.contract.edit",
    "crm.contract.sign",
    "crm.contract.delete",
    "crm.order.list_own",
    "crm.order.list_team",
    "crm.order.list_territory",
    "crm.order.list_all",
    "crm.order.view",
    "crm.order.create",
    "crm.order.edit",
    "crm.order.assign",
    "crm.order.place",
    "crm.order.convert",
    "crm.order.delete",
    "crm.payment.list_own",
    "crm.payment.list_team",
    "crm.payment.list_territory",
    "crm.payment.list_all",
    "crm.payment.view",
    "crm.payment.create",
    "crm.payment.edit",
    "crm.payment.confirm",
    "crm.payment.reverse",
    "crm.payment.delete",
)

NEW_TABLES = (
    "sales_pipelines",
    "sales_pipeline_stages",
    "deals",
    "deal_stage_logs",
    "products",
    "quotes",
    "quote_lines",
    "contracts",
    "orders",
    "order_lines",
    "payment_plans",
    "payments",
)


def step_a1_permissions_catalog(results: list[bool]) -> None:
    from app.permissions import (
        ALL_PERMISSIONS,
        CRM_PERMISSIONS,
        EDITOR_DEFAULT_PERMISSIONS,
        MARKETING_DEFAULT_PERMISSIONS,
        SALES_DEFAULT_PERMISSIONS,
        SALES_MANAGER_DEFAULT_PERMISSIONS,
    )

    results.append(
        check(
            "VA-1-1 新增49条CRM-2/3权限",
            set(CRM_23_NEW_PERMISSIONS).issubset(set(CRM_PERMISSIONS)),
            f"{len(CRM_23_NEW_PERMISSIONS)} 条",
        )
    )
    results.append(
        check(
            "VA-1-2 ALL_PERMISSIONS含新权限",
            set(CRM_23_NEW_PERMISSIONS).issubset(set(ALL_PERMISSIONS)),
            f"ALL={len(ALL_PERMISSIONS)}",
        )
    )
    # sales 关键权限
    sales_must = {
        "crm.deal.list_own",
        "crm.deal.view",
        "crm.deal.create",
        "crm.deal.close",
        "crm.order.create",
        "crm.order.place",
        "crm.order.convert",
        "crm.payment.list_own",
        "crm.payment.create",
    }
    results.append(
        check(
            "VA-1-3 sales含商机/订单/回款基础",
            sales_must.issubset(SALES_DEFAULT_PERMISSIONS),
            str(sorted(sales_must - SALES_DEFAULT_PERMISSIONS)),
        )
    )
    # sales 不含 manager 专属
    sales_forbidden = {"crm.payment.confirm", "crm.payment.reverse", "crm.order.list_team"}
    results.append(
        check(
            "VA-1-4 sales不含确认/团队可见",
            sales_forbidden.isdisjoint(SALES_DEFAULT_PERMISSIONS),
            str(sorted(sales_forbidden & SALES_DEFAULT_PERMISSIONS)),
        )
    )
    # sales_manager 含确认/团队
    manager_must = {
        "crm.payment.confirm",
        "crm.payment.reverse",
        "crm.deal.list_team",
        "crm.order.list_team",
        "crm.contract.sign",
        "crm.quote.accept",
    }
    results.append(
        check(
            "VA-1-5 sales_manager含确认/团队",
            manager_must.issubset(SALES_MANAGER_DEFAULT_PERMISSIONS),
            str(sorted(manager_must - SALES_MANAGER_DEFAULT_PERMISSIONS)),
        )
    )
    # marketing 只读商机+新建
    mkt_must = {"crm.deal.view", "crm.deal.create", "crm.quote.view", "crm.order.view"}
    mkt_forbidden = {"crm.order.create", "crm.payment.create", "crm.contract.sign"}
    results.append(
        check(
            "VA-1-6 marketing只读商机+新建",
            mkt_must.issubset(MARKETING_DEFAULT_PERMISSIONS)
            and mkt_forbidden.isdisjoint(MARKETING_DEFAULT_PERMISSIONS),
            f"miss={mkt_must - MARKETING_DEFAULT_PERMISSIONS}",
        )
    )
    # editor 完全无 CRM
    editor_crm = [p for p in EDITOR_DEFAULT_PERMISSIONS if p.startswith("crm.")]
    results.append(check("VA-1-7 editor无CRM", len(editor_crm) == 0, str(editor_crm)))


def step_a2_tables_and_seeds(results: list[bool]) -> None:
    from sqlalchemy import text

    from app.database import engine

    with engine.connect() as conn:
        # SQLite 用 sqlite_master；PostgreSQL 用 information_schema
        dialect = conn.dialect.name
        if dialect == "sqlite":
            placeholders = ",".join([f"'{t}'" for t in NEW_TABLES])
            rows = conn.execute(
                text(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})"
                )
            ).fetchall()
        else:
            placeholders = ",".join([f":t{i}" for i in range(len(NEW_TABLES))])
            params = {f"t{i}": t for i, t in enumerate(NEW_TABLES)}
            rows = conn.execute(
                text(
                    f"SELECT table_name FROM information_schema.tables WHERE table_name IN ({placeholders})"
                ),
                params,
            ).fetchall()
        existing = {r[0] for r in rows}
        missing = set(NEW_TABLES) - existing
        results.append(check("VA-2-1 12张新表全部存在", len(missing) == 0, f"missing={sorted(missing)}"))

        # 默认管道种子：至少 1 个 is_default 管道，且每个默认管道有 6 阶段
        # 注意：CRUD 测试可能创建自定义阶段数的管道，故只校验默认管道
        default_rows = conn.execute(
            text(
                "SELECT p.id, COUNT(s.id) AS stage_n "
                "FROM sales_pipelines p LEFT JOIN sales_pipeline_stages s ON s.pipeline_id = p.id "
                "WHERE p.is_default = 1 GROUP BY p.id"
            )
        ).fetchall()
        pipeline_count = conn.execute(text("SELECT COUNT(*) FROM sales_pipelines")).scalar()
        results.append(check("VA-2-2 默认管道种子已写入", pipeline_count and pipeline_count > 0, f"{pipeline_count}"))
        default_with_6 = [r for r in default_rows if r[1] >= 6]
        results.append(
            check(
                "VA-2-3 默认管道每6阶段",
                len(default_rows) > 0 and len(default_with_6) == len(default_rows),
                f"default_pipelines={len(default_rows)} with_6_stages={len(default_with_6)}",
            )
        )
        stage_count = conn.execute(text("SELECT COUNT(*) FROM sales_pipeline_stages")).scalar()

        # 至少有 1 个 is_default 管道
        default_count = conn.execute(
            text("SELECT COUNT(*) FROM sales_pipelines WHERE is_default = 1")
        ).scalar()
        results.append(check("VA-2-4 存在默认管道", default_count and default_count > 0, f"{default_count}"))

        # 含赢单/输单阶段
        won_count = conn.execute(
            text("SELECT COUNT(*) FROM sales_pipeline_stages WHERE is_won_stage = 1")
        ).scalar()
        lost_count = conn.execute(
            text("SELECT COUNT(*) FROM sales_pipeline_stages WHERE is_lost_stage = 1")
        ).scalar()
        results.append(
            check(
                "VA-2-5 含赢单+输单阶段",
                won_count and lost_count and won_count > 0 and lost_count > 0,
                f"won={won_count} lost={lost_count}",
            )
        )


def step_a3_permission_seed_db(results: list[bool]) -> None:
    from sqlalchemy import text

    from app.database import engine
    from app.permissions import (
        ALL_PERMISSIONS,
        SALES_DEFAULT_PERMISSIONS,
        SYSTEM_ROLE_ADMIN,
        SYSTEM_ROLE_SALES,
    )

    with engine.connect() as conn:
        # admin 角色应包含全部新权限
        admin_perms = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT DISTINCT trp.permission_code
                    FROM tenant_role_permissions trp
                    JOIN tenant_roles tr ON tr.id = trp.role_id
                    WHERE tr.code = :code AND tr.is_system = 1
                    """
                ),
                {"code": SYSTEM_ROLE_ADMIN},
            ).fetchall()
        }
        missing_admin = set(CRM_23_NEW_PERMISSIONS) - admin_perms
        results.append(
            check(
                "VA-3-1 admin含全部49条新权限",
                len(missing_admin) == 0,
                f"missing={sorted(missing_admin)[:5]}（共 {len(missing_admin)}）",
            )
        )

        # admin 全权限 = ALL_PERMISSIONS
        results.append(
            check(
                "VA-3-2 admin含ALL_PERMISSIONS",
                set(ALL_PERMISSIONS).issubset(admin_perms),
                f"admin={len(admin_perms)} ALL={len(ALL_PERMISSIONS)}",
            )
        )

        # 取一个具体的 sales 角色，查其所有权限
        sales_role_row = conn.execute(
            text(
                """
                SELECT tr.id FROM tenant_roles tr
                WHERE tr.code = :code AND tr.is_system = 1
                ORDER BY tr.tenant_id
                LIMIT 1
                """
            ),
            {"code": SYSTEM_ROLE_SALES},
        ).fetchone()
        if sales_role_row:
            sales_role_id = str(sales_role_row[0])
            sales_perms = {
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT permission_code FROM tenant_role_permissions WHERE role_id = :rid"
                    ),
                    {"rid": sales_role_id},
                ).fetchall()
            }
        else:
            sales_perms = set()
        # 验证 sales 至少含本应新增的 22 条 v0.7 权限
        sales_v07 = {
            "crm.deal.list_own",
            "crm.deal.view",
            "crm.deal.create",
            "crm.deal.edit",
            "crm.deal.convert",
            "crm.deal.close",
            "crm.quote.list_own",
            "crm.quote.view",
            "crm.quote.create",
            "crm.quote.edit",
            "crm.contract.list_own",
            "crm.contract.view",
            "crm.order.list_own",
            "crm.order.view",
            "crm.order.create",
            "crm.order.edit",
            "crm.order.place",
            "crm.order.convert",
            "crm.payment.list_own",
            "crm.payment.view",
            "crm.payment.create",
            "crm.payment.edit",
        }
        missing_sales = sales_v07 - sales_perms
        results.append(
            check(
                "VA-3-3 sales含v0.7默认22条",
                len(missing_sales) == 0,
                f"missing={sorted(missing_sales)} sales_total={len(sales_perms)}",
            )
        )
        # sales 不含 confirm
        results.append(
            check(
                "VA-3-4 sales不含payment.confirm",
                "crm.payment.confirm" not in sales_perms,
                "",
            )
        )


def step_a4_schema_seeds(results: list[bool]) -> None:
    from app.services.crm.schema_seeds import (
        ENTITY_SEED_MAP,
        DEAL_FIELDS,
        QUOTE_FIELDS,
        CONTRACT_FIELDS,
        ORDER_FIELDS,
        PAYMENT_FIELDS,
        PRODUCT_FIELDS,
    )

    expected_keys = {"lead", "customer", "contact", "task", "campaign", "deal", "quote", "contract", "order", "payment", "product"}
    results.append(
        check(
            "VA-4-1 ENTITY_SEED_MAP含11实体",
            expected_keys.issubset(set(ENTITY_SEED_MAP.keys())),
            f"keys={sorted(ENTITY_SEED_MAP.keys())}",
        )
    )

    # 各实体种子字段数
    results.append(check("VA-4-2 deal种子字段>=15", len(DEAL_FIELDS) >= 15, str(len(DEAL_FIELDS))))
    results.append(check("VA-4-3 quote种子字段>=10", len(QUOTE_FIELDS) >= 10, str(len(QUOTE_FIELDS))))
    results.append(check("VA-4-4 contract种子字段>=13", len(CONTRACT_FIELDS) >= 13, str(len(CONTRACT_FIELDS))))
    results.append(check("VA-4-5 order种子字段>=11", len(ORDER_FIELDS) >= 11, str(len(ORDER_FIELDS))))
    results.append(check("VA-4-6 payment种子字段>=8", len(PAYMENT_FIELDS) >= 8, str(len(PAYMENT_FIELDS))))
    results.append(check("VA-4-7 product种子字段>=7", len(PRODUCT_FIELDS) >= 7, str(len(PRODUCT_FIELDS))))

    # 关键字段
    deal_keys = {f["field_key"] for f in DEAL_FIELDS}
    results.append(
        check(
            "VA-4-8 deal含关键字段",
            {"title", "customer_id", "pipeline_id", "stage_id", "amount", "status"}.issubset(deal_keys),
            str(sorted({"title", "customer_id", "pipeline_id", "stage_id", "amount", "status"} - deal_keys)),
        )
    )

    payment_keys = {f["field_key"] for f in PAYMENT_FIELDS}
    results.append(
        check(
            "VA-4-9 payment含order_id+amount+status",
            {"order_id", "amount", "status", "method"}.issubset(payment_keys),
            str(sorted({"order_id", "amount", "status", "method"} - payment_keys)),
        )
    )

    order_keys = {f["field_key"] for f in ORDER_FIELDS}
    results.append(
        check(
            "VA-4-10 order含source+amount+status",
            {"source", "amount", "status", "customer_id"}.issubset(order_keys),
            str(sorted({"source", "amount", "status", "customer_id"} - order_keys)),
        )
    )


def step_a5_alembic_head(results: list[bool]) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check("VA-5-1 alembic head=037", is_at_expected_head(out), out.strip()[:120]))


def step_a6_models_import(results: list[bool]) -> None:
    from app.models.crm import (
        Contract,
        Deal,
        DealStageLog,
        Order,
        OrderLine,
        Payment,
        PaymentPlan,
        Product,
        Quote,
        QuoteLine,
        SalesPipeline,
        SalesPipelineStage,
    )

    models = [
        SalesPipeline,
        SalesPipelineStage,
        Deal,
        DealStageLog,
        Product,
        Quote,
        QuoteLine,
        Contract,
        Order,
        OrderLine,
        PaymentPlan,
        Payment,
    ]
    results.append(check("VA-6-1 12新模型可导入", len(models) == 12, str([m.__name__ for m in models])))
    # 验证关键字段映射
    results.append(check("VA-6-2 Deal表名", Deal.__tablename__ == "deals", Deal.__tablename__))
    results.append(check("VA-6-3 Payment表名", Payment.__tablename__ == "payments", Payment.__tablename__))


STEPS = {
    "A-1": step_a1_permissions_catalog,
    "A-2": step_a2_tables_and_seeds,
    "A-3": step_a3_permission_seed_db,
    "A-4": step_a4_schema_seeds,
    "A-5": step_a5_alembic_head,
    "A-6": step_a6_models_import,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=list(STEPS.keys()))
    args = parser.parse_args()

    results: list[bool] = []
    try:
        if args.step:
            STEPS[args.step](results)
        else:
            for fn in STEPS.values():
                fn(results)
    except Exception as e:
        print(f"ERROR: {e}")
        raise

    passed = all(results) if results else False
    print("\n=== v0.7 CRM-2/3 Phase A", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
