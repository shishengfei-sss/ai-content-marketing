"""自动化测试框架配置。

被测系统：本仓库 apps/api（FastAPI，SQLite dev.db，fake LLM）。
测试真源：桌面上的《AI内容营销系统-测试用例.xlsx》。
"""
import os

from pathlib import Path

# 被测后端地址（本机 uvicorn，端口 8000）
BASE_URL = os.environ.get("QA_BASE_URL", "http://127.0.0.1:8000")
API_PREFIX = "/api/v1"

_QA_DIR = Path(__file__).resolve().parent
# 用例真源（读取）与结果落盘（写出，另存副本不破坏原件）
EXCEL_PATH = r"C:\Users\admin\Desktop\临时\AI内容营销系统-测试用例.xlsx"
RESULT_PATH = str(_QA_DIR / "AI内容营销系统-测试用例-自动化结果.xlsx")

# 写回 Excel 时填的测试人
TESTER = "自动化-小沃"

# 开发环境 JWT 密钥（config.py 默认值），用于生成“过期 token”做鉴权用例
JWT_SECRET = "dev-change-me-in-production"

# 测试账号统一密码
TEST_PASSWORD = "Test@123456"

# 平台管理员（platform_admin 角色）账号：由迁移 005_phone_user_admin.py 种入，
# 拥有 /api/v1/admin 全量后台权限，前端 /admin 路由仅对该角色开放。
PLATFORM_ADMIN_PHONE = "13800000000"
PLATFORM_ADMIN_PASSWORD = "admin123456"
