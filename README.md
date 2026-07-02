# 智营获客 — AI 内容营销系统

## 文档

| 文档 | 路径 |
|------|------|
| 需求规格 SRS | [docs/需求规格.md](docs/需求规格.md) |
| 实现步骤计划 | [docs/实现步骤计划.md](docs/实现步骤计划.md) |
| LLM 与 UI 计划 | [docs/LLM与UI计划.md](docs/LLM与UI计划.md) |

## 当前进度

- Web 管理端（Vue 3 + Element Plus）— 已接 API
- uni-app 移动端 H5 — 已接 API
- FastAPI 后端 — 认证、LLM 配置、内容生成、审核流

## 快速启动（本地开发）

### 1. 启动 API（端口 8001，避开 Frappe 的 8000）

```powershell
cd e:\ai-content-marketing\apps\api
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

验证：http://127.0.0.1:8001/health → `{"status":"ok"}`

> 开发期默认使用 SQLite（`apps/api/dev.db`）。生产可改 `.env` 中 `DATABASE_URL` 为 PostgreSQL。

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

打开 http://127.0.0.1:5173 → 注册/登录 → 营销创作

### 4. 启动移动端 H5

```powershell
cd e:\ai-content-marketing\apps\mp
npm.cmd install
npm.cmd run dev:h5 -- --port 5174
```

浏览器 F12 切换手机模式 → http://127.0.0.1:5174

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册租户 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户 |
| GET/PUT | `/api/v1/settings/llm` | LLM 配置 |
| POST | `/api/v1/settings/llm/test` | 测试模型连接 |
| POST | `/api/v1/content/generate` | AI 生成内容 |
| GET | `/api/v1/content` | 内容列表（支持 status/platform/q 筛选） |
| GET | `/api/v1/content/{id}` | 内容详情 |
| POST | `/api/v1/content/{id}/submit-review` | 提交审核 |
| POST | `/api/v1/content/{id}/approve` | 审核通过 |
| POST | `/api/v1/content/{id}/reject` | 审核驳回 |

## LLM 架构

```
LLMService → DeepSeekProvider / OpenAICompatibleProvider / DashScopeProvider
           ← 租户 llm_configs（优先）或环境变量
```

## 目录

```
apps/api/    FastAPI 后端
apps/web/    Web 管理端
apps/mp/     uni-app 移动端
packages/shared/  设计 token
```
