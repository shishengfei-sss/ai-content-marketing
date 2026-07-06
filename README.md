# 智营获客 — AI 内容营销系统

## 文档

| 文档 | 路径 |
|------|------|
| 需求规格 SRS | [docs/需求规格.md](docs/需求规格.md) |
| v0.3.3 执行计划 | [docs/v0.3.3执行计划.md](docs/v0.3.3执行计划.md) |
| **v0.4 Agent 执行计划** | [docs/v0.4-agent执行计划.md](docs/v0.4-agent执行计划.md) |
| 实现步骤计划 | [docs/实现步骤计划.md](docs/实现步骤计划.md) |
| LLM 与 UI 计划 | [docs/LLM与UI计划.md](docs/LLM与UI计划.md) |

## 当前进度

### v0.3.3 MVP

- ✅ 企业与权限：一人多公司、Membership、角色权限、选/切换公司
- ✅ 忘记密码（Web + H5）；测试验证码 **1111**
- ✅ 工作台/看板 scope（本人 / 全公司）；取消 reviewer 审核流
- ✅ 平台 AI 免费额度（方案不扣、正文扣 1）
- ✅ Web + H5 双端对齐（选公司、设置、权限菜单）
- ✅ 平台后台：**企业管理**（成员 + 转移管理员）、**账号管理**（Membership；删账号不删租户）
- ✅ 手机号注册登录 / JWT、可插拔 LLM、RAG、Mock 发布、导出
- ⏳ 部署上线 + 真实微信 API（需备案与服务号）

### v0.4 Agent 智能体（后端 + 双端创作）

- ✅ 会话 / ReAct / Tool / SSE / 长期记忆 LM1～LM5
- ✅ 工作流 C1、合规 C2、Confirm 闸 C3、Hybrid RAG C4、Supervisor C5、Seo C6
- ✅ Web + H5 创作页接 Agent API；**历史会话**列表与切换
- ⏳ 生产 PostgreSQL + pgvector（部署时再配）

## 测试账号（开发 / UAT）

| 角色 | 手机号 | 密码 | 说明 |
|------|--------|------|------|
| platform_admin | `13800000000` | `admin123456` | 平台后台 `/admin` |
| 单公司 admin | `13900000099` | `test123456` | 默认单租户管理员 |
| 多公司用户 | `13900008888` | `Test123456` | 甲 admin + 乙 editor，测选/切换公司 |
| 验证码 Mock | — | **`1111`** | 登录短信、找回密码均用 1111 |

环境变量（`.env`）：`SMS_PROVIDER=mock`，`SMS_MOCK_CODE=1111`

## 自动验收（发布门禁 M0～M8）

无需启动 uvicorn，使用 FastAPI TestClient：

```powershell
cd e:\ai-content-marketing\apps\api
.\.venv\Scripts\python.exe tests\run_m0_m8.py
```

仅跑 M8 总验收：

```powershell
.\.venv\Scripts\python.exe tests\verify_m8.py
```

## 自动验收（v0.4 Agent T0～AG8）

```powershell
cd e:\ai-content-marketing\apps\api
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe tests\run_agent_a_c.py
```

单步示例：`verify_c6.py`（Seo + 会话历史）、`verify_ag8.py`（含 M0～M8 回归 + 发布安全闸）。

Agent 健康检查：`GET /api/v1/agent/health`

## 快速启动（本地开发）

### 1. 启动 API

```powershell
cd e:\ai-content-marketing\apps\api
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

验证：http://127.0.0.1:8000/health → `{"status":"ok"}`

> Web/H5 通过 Vite 代理访问 API（见各端 `.env.development` 中 `VITE_API_PROXY_TARGET`），**须与 uvicorn 端口一致**。

> 开发期默认 SQLite（`apps/api/dev.db`）。生产可改 `.env` 中 `DATABASE_URL` 为 PostgreSQL。

### 2. 配置 DeepSeek Key（二选一）

**方式 A — 环境变量**（复制 `.env.example` → `.env`）：

```ini
DEEPSEEK_API_KEY=sk-你的key
```

**方式 B — Web 设置页**：登录后 → 设置 → AI 模型 → 填写 Key → 测试连接 → 保存

### 3. 启动 Web

```powershell
cd e:\ai-content-marketing\apps\web
npm.cmd install
npm.cmd run dev
```

打开 Vite **Local** 地址（默认约 5173）→ `/login` 手机号登录

平台管理员：`13800000000` / `admin123456` → `/admin`（企业管理、账号管理、全站内容等）

### 4. 启动移动端 H5

```powershell
cd e:\ai-content-marketing\apps\mp
npm.cmd install
npm.cmd run dev:h5
```

浏览器 F12 手机模式 → 终端 **Local** 地址（默认约 5174）→ `#/pages/login/login`

## API 端点（节选）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 手机号注册 |
| POST | `/api/v1/auth/login` | 手机号登录 |
| GET | `/api/v1/auth/me` | 当前用户（permissions、tenants） |
| POST | `/api/v1/auth/select-tenant` | 多公司选公司 |
| POST | `/api/v1/auth/switch-tenant` | 切换公司 |
| POST | `/api/v1/auth/password/forgot/send-code` | 忘记密码发码（Mock：**1111**） |
| GET/PATCH | `/api/v1/tenant/profile` | 企业信息（admin） |
| GET/POST | `/api/v1/team/members` | 角色与成员 |
| GET | `/api/v1/settings/llm/quota` | 平台免费额度 |
| POST | `/api/v1/content/proposals` | 生成方案（不扣额度） |
| POST | `/api/v1/content/generate` | 生成正文（扣 1 次） |
| GET | `/api/v1/admin/tenants` | 平台：企业管理 |
| GET | `/api/v1/admin/users` | 平台：账号管理 |

## LLM 架构

```
LLMService → DeepSeekProvider / OpenAICompatibleProvider / DashScopeProvider
           ← 租户 llm_configs（优先）或环境变量 / 平台 AI
```

## 目录

```
apps/api/    FastAPI 后端
apps/web/    Web 管理端
apps/mp/     uni-app 移动端（H5）
packages/shared/  设计 token
docs/        需求规格与执行计划
```
