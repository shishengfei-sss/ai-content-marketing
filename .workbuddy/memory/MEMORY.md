# AI内容营销系统 QA 自动化 — 长期记忆（项目级）

## 运行环境（务必先确认）
- 后端 apps/api：FastAPI + SQLAlchemy + Alembic，默认 SQLite(`sqlite:///./dev.db`)。启动：`alembic upgrade head` + `uvicorn app.main:app --port 8000`（设 `LLM_PROVIDER=fake`、`SMS_PROVIDER=mock` 离线跑）。
- 登录体系：**手机号 + 密码**（非 Excel 写的邮箱）；mock 短信验证码固定 `1111`；无 `/auth/refresh`；token 仅 `access_token`，存前端 `localStorage['token']`（web）/ `ai_marketing_token`（H5）。
- 前端两个独立服务，端口易混：
  - **5173 = apps/web（Vue3, 真实被测系统）**：登录 `placeholder="请输入手机号"` + `<button>登录</button>`；路由 /crm/*、/settings/*、/admin/* 正常渲染。
  - **5174 = apps/mp（uni-app H5 移动端）**：div 式登录无 button/placeholder；hash 路由 `#/pages/...`；token 键 `ai_marketing_token`。
  - `web_base()` 只应指向 **5173(web)**，不要误指 5174(H5)。
- 平台管理员：13800000000 / admin123456（`require_platform_admin` 守卫，登录免选租户）。
- Python 必须用 **managed venv**：`C:/Users/admin/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（Playwright/openpyxl/httpx/jose 都装这里）。

## Playwright 自动化铁律（踩过坑）
1. **复用全局浏览器，绝不每用例 `sync_playwright()` 起关**。Playwright Sync API 全局 event loop 只能 `start()` 一次；每用例 `with sync_playwright()` 起+关会导致第 2 条用例报 `Event loop is closed / inside asyncio loop`。正确模式见 `ui_helpers._ensure_browser()`：全局 `_browser` 只在首次 `sync_playwright().start()`，每条用例只 `browser.new_context()`，`run.py` 末尾 `close_browser()` 统一回收。
2. H5 用例也用 `from ui_helpers import _ensure_browser` 复用同一全局浏览器（仅 base=5174、state 文件独立）。
3. `storage_state` 是 origin 锁定的：在 5173 固化的 token 拿到 5174 用会失效（反之亦然）。换端口必须重新登录固化。

## 关键业务约束（避免用例误判）
- 建线索/客户需 `territory_id`（销售区域）：`GET /crm/territories` 自动播种，取第一条。
- 手机号注册用「时间+随机」避免重跑冲突；租户名全局唯一需加随机后缀。
- 客户表单 UI 有「行业/规模」字段，但后端 `CustomerCreate` 无此字段、不持久化（规格偏差，非缺陷）。
- H5 创建线索必填含 `*销售区域`（uni-data-select 下拉），需先点「请选择销售区域」再点「华东」才能提交。

## 已知真实缺陷 / 功能缺失（持续积累）
- SEC-002 存储型 XSS：后端原样存 `<script>`。
- AUTH-009 无防暴破锁定；SEC-004 无 API 限速(429)。
- ADM-002 无租户禁用/启用接口；ADM-007 九种人格仅 finance/legal/marketing。
- CUST-002 客户名无唯一约束（重名仍 201，疑似缺陷）。
- TENDER-002 ICP 匹配度：recalculate-score 后 `icp_score` 仍为 null（疑似未真正计算）。
- 功能缺失（空页非缺陷）：TEAM-001~004(/settings/members)、LLM-001/MEM-001/MEM-002(/agent)。

## 文件地图
- `config.py` 配置 / `helpers.py`(req/register/login/admin_login) / `ui_helpers.py`(全局浏览器+登录态固化) / `cases_api.py`(后端API,末尾注入多批 REGISTRY) / `cases_ui.py`(Playwright UI,末尾注入 REGISTRY_UI) / `cases_h5.py` / `cases_features_extra.py` / `cases_auth_sec.py` / `cases_admin_extra.py` / `cases_crm_extra.py` / `cases_rest_extra.py` / `run.py`(编排+写回副本 Excel+report.json)。
- 结果写回副本：`AI内容营销系统-测试用例-自动化结果.xlsx`（不经手原件）；机器报告 `report.json`。
