# 智营获客 — AI 内容营销系统

## 文档

| 文档 | 路径 |
|------|------|
| 需求规格 SRS | [docs/需求规格.md](docs/需求规格.md) |
| 实现步骤计划 | [docs/实现步骤计划.md](docs/实现步骤计划.md) |
| LLM 与 UI 计划 | [docs/LLM与UI计划.md](docs/LLM与UI计划.md) |

## 当前进度（MVP 功能闭环）

- ✅ 手机号注册登录 / JWT / 一人一号（租户隔离）
- ✅ 可插拔 LLM + 设置页配置
- ✅ 行业模板 + RAG 知识库检索（按 AI 助手 / industry_code 隔离）
- ✅ **多 AI 助手**：管理后台配置行业专家 Prompt；创作页切换助手；内置 finance + legal 示例
- ✅ 租户知识库上传 / 粘贴 / 删除
- ✅ 品牌设置 + 个人提示词
- ✅ 内容生成：**先出 3～5 方案 → 选定后再生成正文**；支持图文 / 视频脚本（公众号、小红书、抖音）
- ✅ 公众号绑定：**服务号**可 Mock 自动发图文；**订阅号**仅复制/下载
- ✅ 草稿 → Mock 公众号发布 / 排期（免审核，仅服务号图文）
- ✅ 小红书 ZIP 导出 / 视频脚本导出（含公众号、小红书脚本）
- ✅ Web 工作台 / 内容库 / 日历 / 数据看板
- ✅ 管理后台：全站内容 / **AI 助手** / 公共知识库 / 用户管理
- ✅ uni-app H5：两阶段创作、内容形态、服务号/订阅号、内容箱
- ⏳ 部署上线 + 真实微信 API（第 11 步，需备案与 service 号）

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
> 若曾启动过旧版 API 占用 8001，请关闭旧进程，避免前端连到过期服务。

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

打开终端里 Vite 打印的 **Local** 地址（默认约 5173）→ `/login` 手机号登录

**平台管理员（迁移 005 种子账号）：** 手机号 `13800000000`，密码 `admin123456` → 登录后进入 `/admin` 管理后台。

### 4. 启动移动端 H5

```powershell
cd e:\ai-content-marketing\apps\mp
npm.cmd install
npm.cmd run dev:h5
```

浏览器 F12 切换手机模式 → 终端 **Local** 地址（默认约 5174）→ `#/pages/login/login`

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 手机号注册（一人一号） |
| POST | `/api/v1/auth/login` | 手机号登录 |
| GET | `/api/v1/auth/me` | 当前用户 |
| GET/PUT | `/api/v1/settings/llm` | LLM 配置 |
| POST | `/api/v1/settings/llm/test` | 测试模型连接 |
| POST | `/api/v1/content/generate` | AI 生成内容（草稿） |
| GET | `/api/v1/content` | 内容列表（支持 status/platform/q 筛选） |
| GET | `/api/v1/content/{id}` | 内容详情 |
| POST | `/api/v1/content/{id}/schedule` | 排期发布 |
| POST | `/api/v1/content/{id}/publish` | 草稿/排期 → Mock 发布 |
| POST | `/api/v1/content/{id}/retry-publish` | 重试发布 |
| GET | `/api/v1/content/calendar` | 发布日历 |
| GET | `/api/v1/dashboard/stats` | 工作台统计（含 draft_count） |
| POST | `/api/v1/content/proposals` | 生成 3～5 个创作方案 |
| POST | `/api/v1/content/generate` | 选定方案后生成正文 |
| GET/POST | `/api/v1/settings/wechat` | 公众号绑定（服务号/订阅号） |
| GET/POST | `/api/v1/knowledge/documents` | 租户知识库 |
| GET | `/api/v1/templates` | 场景模板列表 |
| GET/PUT | `/api/v1/settings/brand` | 品牌设置 |
| GET/PUT | `/api/v1/settings/user-prompt` | 个人提示词 |
| GET | `/api/v1/analytics/stats` | 数据看板统计 |
| POST | `/api/v1/content/{id}/export/xhs` | 小红书 ZIP 导出 |
| POST | `/api/v1/content/{id}/export/douyin` | 抖音脚本导出 |
| GET | `/api/v1/admin/contents` | 管理后台：全站内容 |
| GET | `/api/v1/assistants` | AI 助手列表（公开，注册/创作页可用） |
| GET/POST/PATCH | `/api/v1/admin/assistants` | 管理后台：AI 助手配置 |
| GET/POST/DELETE | `/api/v1/admin/knowledge/documents` | 管理后台：公共知识库 |

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
