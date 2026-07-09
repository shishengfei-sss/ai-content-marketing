"""M1 验收：Membership / TenantRole / Permission 迁移与种子数据。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from app.config import settings  # noqa: E402
from app.permissions import (  # noqa: E402
    ALL_PERMISSIONS,
    EDITOR_DEFAULT_PERMISSIONS,
    PLATFORM_ADMIN_ROLE,
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_EDITOR,
)


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    results: list[bool] = []

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check(f"V1-0 alembic={EXPECTED_HEAD}(head)", is_at_expected_head(out), out.strip()))

    engine = create_engine(settings.DATABASE_URL)
    insp = inspect(engine)

    for table in ("tenant_memberships", "tenant_roles", "tenant_role_permissions"):
        results.append(check(f"V1-1 table {table}", insp.has_table(table)))

    results.append(check("V1-1 tenants.credit_code", "credit_code" in [c["name"] for c in insp.get_columns("tenants")]))

    with engine.connect() as conn:
        tenant_count = conn.execute(text("SELECT COUNT(*) FROM tenants")).scalar() or 0
        role_pairs = conn.execute(
            text(
                """
                SELECT tenant_id, COUNT(*) AS c FROM tenant_roles
                WHERE is_system = 1
                GROUP BY tenant_id
                HAVING c = 5
                """
            )
        ).fetchall()
        tenants_with_admin = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT tenant_id) FROM tenant_roles
                WHERE is_system = 1 AND code = 'admin'
                """
            )
        ).scalar()
        results.append(
            check(
                "V1-2 每tenant五内置角色",
                len(role_pairs) == tenants_with_admin,
                f"admin_tenants={tenants_with_admin} full5={len(role_pairs)} total_tenants={tenant_count}",
            )
        )

        editor_perms = conn.execute(
            text(
                """
                SELECT trp.permission_code FROM tenant_role_permissions trp
                JOIN tenant_roles tr ON tr.id = trp.role_id
                WHERE tr.code = :code AND tr.is_system = 1
                LIMIT 1
                """
            ),
            {"code": SYSTEM_ROLE_EDITOR},
        ).fetchall()
        # count for one editor role
        editor_count_row = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM tenant_role_permissions trp
                JOIN tenant_roles tr ON tr.id = trp.role_id
                WHERE tr.code = :code AND tr.is_system = 1
                """
            ),
            {"code": SYSTEM_ROLE_EDITOR},
        ).scalar()
        editor_role_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM tenant_roles
                WHERE code = :code AND is_system = 1
                """
            ),
            {"code": SYSTEM_ROLE_EDITOR},
        ).scalar()
        expected_editor = len(EDITOR_DEFAULT_PERMISSIONS) * (editor_role_count or 0)
        results.append(
            check(
                "V1-3 editor默认权限",
                editor_count_row == expected_editor,
                f"count={editor_count_row} expected={expected_editor} roles={editor_role_count}",
            )
        )

        admin_perm_count = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT trp.permission_code) FROM tenant_role_permissions trp
                JOIN tenant_roles tr ON tr.id = trp.role_id
                WHERE tr.code = :code AND tr.is_system = 1
                """
            ),
            {"code": SYSTEM_ROLE_ADMIN},
        ).scalar()
        results.append(
            check(
                "V1-4 admin全部权限",
                admin_perm_count == len(ALL_PERMISSIONS),
                f"admin_perms={admin_perm_count} all={len(ALL_PERMISSIONS)}",
            )
        )

        non_admin_users = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE role != :role"),
            {"role": PLATFORM_ADMIN_ROLE},
        ).scalar()
        memberships = conn.execute(text("SELECT COUNT(*) FROM tenant_memberships")).scalar()
        results.append(
            check(
                "V1-5 旧用户Membership",
                memberships >= non_admin_users,
                f"users={non_admin_users} memberships={memberships}",
            )
        )

        dup = conn.execute(
            text(
                """
                SELECT user_id, tenant_id, COUNT(*) c FROM tenant_memberships
                GROUP BY user_id, tenant_id HAVING c > 1
                """
            )
        ).fetchall()
        results.append(check("V1-6 唯一约束", len(dup) == 0, f"dup={len(dup)}"))

    passed = all(results)
    print("\n=== M1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
