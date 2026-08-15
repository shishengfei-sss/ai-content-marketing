# 内容获客商城 Phase 1 · M1–M8 执行计划（Cursor 专用）

| 项目 | 说明 |
|------|------|
| 文档版本 | v1.0-shop-m1-m8 |
| 关联 PRD | [PRD-内容获客商城-phase1.md](../01-PRD/21-内容获客商城-phase1/PRD-内容获客商城-phase1.md) |
| 关联执行计划 | [内容获客平台-执行计划.md](./内容获客平台-执行计划.md) |
| 技术栈 | FastAPI + Vue3 Web + uni-app 小程序 |
| 当前 Alembic Head | 103（M0 已完成：权限 Catalog · 入驻 · OCR · 服务记录 · 结算表 · 渠道写入） |
| 执行目标 | 完成 M1–M8 全批次，达到 Mx 公域验收 |
| 前置基线 | M0 全绿（`verify_shop_m0.py` PASS）· `run_crm_all.py` 全绿 · `run_agent_a_c.py` 全绿 |

---

## 0. 执行规则（Cursor 必须严格遵守）

### 0.1 一步一验

每个 Step 完成后**必须**运行该 Step 的验收脚本和回归门禁，**全 PASS 才能进入下一步**。不得跳步、不得批量执行多步后再验收。

### 0.2 回归门禁

每步完成后运行以下回归套件，确保不破坏已有功能：

```bash
# 后端回归（CRM + Agent）
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/run_agent_a_c.py

# 商城 M0 回归
cd apps/api && python tests/verify_shop_m0.py

# Alembic 一致性检查
cd apps/api && python tests/alembic_head.py
```

### 0.3 文件规范

- 新增 Alembic 迁移：`apps/api/alembic/versions/0XX_描述.py`，编号顺延（当前 head=103，下一步=104）
- 新增模型：追加到 `apps/api/app/models/shop.py`
- 新增 Schema：追加到 `apps/api/app/schemas/shop_platform.py` 或新建 `apps/api/app/schemas/shop.py`
- 新增路由：`apps/api/app/routers/shop/` 或 `apps/api/app/routers/platform_shop/`
- 验收脚本：`apps/api/tests/verify_shop_mN.py`
- 前端页面：`apps/web/src/views/shop/` 或 `apps/web/src/views/admin/shop/`

### 0.4 数据模型约束（项目硬约束）

- 学生数据存独立 `shop_enrollments` 表，通过 `crm_activities` 桥接 CRM，**禁止**直接映射到 CRM `Contact`
- `shop_orders` 使用独立模型，**禁止**复用 B2B `Order`
- 课程内容使用 `shop_courses` / `shop_columns` / `shop_lessons` 模型；`Content` 模型仅用于营销文案
- 套餐叠加使用 `merge_entitlements` 合并逻辑

### 0.5 API 前缀约定

| 端 | 前缀 | 认证 |
|----|------|------|
| 商家端 | `/api/v1/shop/*` | 商家 JWT + `shop.*` 权限 |
| 平台端 | `/api/v1/admin/shop/*` | 平台 JWT + `platform.shop.*` 权限 |
| 买家小程序 | `/api/v1/mp/shop/*` | 小程序 JWT / openid |

---

## 1. 实施顺序（依赖驱动，非 PRD 编号顺序）

```
M0 ✅ 已完成 (Alembic 098–103)
  ↓
M1 · 套餐订阅开通 (Alembic 104)
  ↓
M2 · 商家状态与入驻自申 (无新迁移)
  ↓
M4 · 商品与内容 + 人审 (Alembic 105)
  ↓
M5 · 订单、权益与退款 (Alembic 106)
  ↓
M3 · 私域支付硬验收 (Alembic 107)
  ↓
M6 · 核销、预约与开票 (Alembic 108)
  ↓
M7 · 公域链路 ① Mx (Alembic 109)
  ↓
M8 · 公域链路 ② (可选, Alembic 110)
```

**调整原因**：M3（支付）依赖 M5（订单模型）和 M4（商品模型），故 M4→M5→M3 为正确依赖序。PRD 编号 M3<M4<M5 是商务里程碑序，非实施序。

---

## 2. M1 · 套餐订阅开通

**目标**：平台可配置套餐模板（P10），管家可人工为商家开通/换档/加购订阅（P11），商家端可只读查看已购权益（A18）。

**Alembic**：104

### Step M1-1：套餐模板与订阅数据模型

| 项 | 内容 |
|----|------|
| 任务 | 新增 Alembic 104 迁移，创建套餐模板、订阅、套餐权益快照表 |
| 关键文件 | `apps/api/alembic/versions/104_shop_subscriptions.py` · `apps/api/app/models/shop.py`（追加模型） |

**需创建的表**：

```
shop_plan_templates          -- 套餐模板（P10 配置）
  id, code, name, tier(basic/standard/premium), status(active/off),
  store_quota, description, features_json, sort_order, created_at, updated_at

shop_plan_benefits           -- 套餐权益项模板
  id, plan_template_id, benefit_key, benefit_label, value_type(int/bool/json),
  value_json, sort_order

shop_subscriptions           -- 商家订阅记录（P11）
  id, merchant_id, tenant_id, plan_template_id, plan_code, plan_label,
  status(active/expired/cancelled), purchase_mode(initial/upgrade/addon/renewal),
  effective_from, effective_until, store_quota, benefits_snapshot_json,
  operated_by, operated_at, remark, created_at, updated_at

shop_plan_change_logs        -- 套餐变更日志
  id, subscription_id, merchant_id, action(open/upgrade/downgrade/renew/cancel),
  from_plan_code, to_plan_code, operated_by, detail_json, created_at
```

**验收**：

```bash
cd apps/api && alembic upgrade head
# 验证表已创建
python -c "from app.models.shop import ShopPlanTemplate, ShopSubscription, ShopPlanBenefit, ShopPlanChangeLog; print('models OK')"
```

- [ ] `alembic upgrade head` 无报错
- [ ] 4 张表在数据库中存在
- [ ] `alembic_head.py` 中 `EXPECTED_HEAD` 更新为 `"104"` 并 PASS
- [ ] `run_crm_all.py` 回归全绿

### Step M1-2：套餐模板 CRUD API（P10 平台端）

| 项 | 内容 |
|----|------|
| 任务 | 实现平台端套餐模板的增删改查 API |
| 关键文件 | `apps/api/app/routers/platform_shop/plans.py` · `apps/api/app/schemas/shop_platform.py` |

**API 端点**：

```
GET    /api/v1/admin/shop/plans              -- 列表（分页、状态筛选）
POST   /api/v1/admin/shop/plans              -- 创建套餐模板
GET    /api/v1/admin/shop/plans/{id}         -- 详情（含权益项）
PATCH  /api/v1/admin/shop/plans/{id}         -- 修改（name/description/features/sort）
POST   /api/v1/admin/shop/plans/{id}/toggle  -- 上架/下架
DELETE /api/v1/admin/shop/plans/{id}         -- 删除（仅 off 状态可删）
```

**权限**：`platform.shop.plan.manage`

**验收**：

- [ ] 创建 basic / standard / premium 三个模板，各含 3+ 权益项
- [ ] 列表返回正确分页和状态筛选
- [ ] toggle 切换 active↔off 成功
- [ ] active 状态模板不可删除（返回 409）
- [ ] 无权限用户返回 403

### Step M1-3：订阅开通/换档/加购 API（P11 平台端）

| 项 | 内容 |
|----|------|
| 任务 | 实现管家人工为商家开通、换档、加购、续费订阅的 API |
| 关键文件 | `apps/api/app/routers/platform_shop/subscriptions.py` · `apps/api/app/services/platform_shop_service.py`（追加） |

**API 端点**：

```
GET   /api/v1/admin/shop/merchants/{id}/subscriptions          -- 商家订阅历史
POST  /api/v1/admin/shop/merchants/{id}/subscriptions/open      -- 开通订阅
POST  /api/v1/admin/shop/merchants/{id}/subscriptions/upgrade   -- 换档
POST  /api/v1/admin/shop/merchants/{id}/subscriptions/addon     -- 加购
POST  /api/v1/admin/shop/merchants/{id}/subscriptions/renew     -- 续费
POST  /api/v1/admin/shop/merchants/{id}/subscriptions/cancel    -- 取消
```

**请求体示例（open）**：

```json
{
  "plan_template_id": "uuid",
  "effective_from": "2026-08-12",
  "effective_until": "2027-08-12",
  "remark": "首批客户赠送"
}
```

**业务逻辑**：

1. `open`：商家无 active 订阅时可开通；写 `shop_subscriptions` + `shop_plan_change_logs`；更新 `shop_merchant_accounts.current_subscription_id` / `plan_label` / `plan_status` / `benefits_until` / `store_quota`
2. `upgrade`：需有 active 订阅；旧订阅 `expired`，新订阅 `active`；记录变更日志
3. `addon`：延长 `effective_until`；不改变 plan_label
4. `renew`：续期，更新 `effective_until`；标记 `has_pending_renewal=false`
5. `cancel`：`status=cancelled`，`effective_until=now()`

**验收**：

- [ ] 为 M0 种子商家开通 basic 套餐，merchant 字段正确更新
- [ ] upgrade basic→standard 后，旧订阅 expired、新订阅 active
- [ ] addon 延长 effective_until 30 天
- [ ] renew 续费后 has_pending_renewal=false
- [ ] 无 active 订阅时 upgrade 返回 409
- [ ] 续费待办列表（`GET /api/v1/admin/shop/merchants/pending-renewals`）正确反映状态

### Step M1-4：商家端套餐权益只读（A18）

| 项 | 内容 |
|----|------|
| 任务 | 商家端 API + Web 页面展示当前套餐权益 |
| 关键文件 | `apps/api/app/routers/shop/subscriptions.py` · `apps/web/src/views/shop/ShopPlan.vue` |

**API 端点**：

```
GET /api/v1/shop/subscription/current   -- 当前有效订阅 + 权益快照
GET /api/v1/shop/subscription/history   -- 订阅变更历史
```

**验收**：

- [ ] 返回当前 active 订阅的 plan_label / benefits_until / store_quota / benefits_snapshot
- [ ] 无订阅时返回 404 + 友好提示
- [ ] history 返回按时间倒序的变更日志
- [ ] Web 页面 A18 正确渲染权益列表和到期日期

### Step M1-5：验收脚本与门禁

| 项 | 内容 |
|----|------|
| 任务 | 编写 M1 验收脚本，运行全部回归 |
| 关键文件 | `apps/api/tests/verify_shop_m1.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM1-1 | 套餐模板创建 | 3 档模板创建成功，含权益项 |
| VM1-2 | 模板列表 | 分页正确，status 筛选生效 |
| VM1-3 | 模板 toggle | active↔off 切换成功 |
| VM1-4 | 模板删除保护 | active 模板不可删（409） |
| VM1-5 | 开通订阅 | merchant 字段正确更新 |
| VM1-6 | 换档 | 旧 expired + 新 active + 日志 |
| VM1-7 | 加购 | effective_until 延长 |
| VM1-8 | 续费 | has_pending_renewal=false |
| VM1-9 | 取消 | status=cancelled |
| VM1-10 | 重复开通 | 已有 active 时返回 409 |
| VM1-11 | 商家只读 | current + history 正确返回 |
| VM1-12 | 权限隔离 | 商家角色不可访问 platform API（403） |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m0.py    # M0 回归
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/alembic_head.py      # EXPECTED_HEAD = "104"
```

- [ ] `verify_shop_m1.py` 全 PASS（12/12）
- [ ] M0 回归全绿
- [ ] CRM 回归全绿
- [ ] Alembic head = 104

---

## 3. M2 · 商家状态与入驻自申

**目标**：平台可暂停/恢复/清退商家（P02-C/D/F）；商家可自行提交入驻申请（A20）。

**Alembic**：无新迁移（复用 M0 表结构）

### Step M2-1：商家状态写操作 API（P02-C/D/F 平台端）

| 项 | 内容 |
|----|------|
| 任务 | 实现商家暂停、恢复、清退 API |
| 关键文件 | `apps/api/app/routers/platform_shop/merchants.py`（追加） |

**API 端点**：

```
POST /api/v1/admin/shop/merchants/{id}/suspend    -- 暂停商家
POST /api/v1/admin/shop/merchants/{id}/resume     -- 恢复商家
POST /api/v1/admin/shop/merchants/{id}/dismiss    -- 清退商家
```

**状态机**：

```
active ⇄ suspended → dismissed (终态)
```

**业务规则**：

| 操作 | 前置状态 | 后置状态 | 附加效果 |
|------|----------|----------|----------|
| suspend | active | suspended | 店铺同步 paused；买家端 M02–M04 拦截 |
| resume | suspended | active | 店铺恢复 active；买家端可购 |
| dismiss | active/suspended | dismissed | 终态；所有店铺 closed；写入服务记录 |

**请求体**：

```json
{
  "reason": "违规操作",
  "remark": "经核实，暂停处理"
}
```

**验收**：

- [ ] active→suspended 成功，状态变更 + 服务记录写入
- [ ] suspended→active 恢复成功
- [ ] dismissed 为终态，不可恢复（返回 409）
- [ ] suspended 状态下店铺自动 paused
- [ ] 操作日志写入 `shop_merchant_service_logs`

### Step M2-2：商家自申入驻 API（A20 商家端）

| 项 | 内容 |
|----|------|
| 任务 | 商家端自行提交入驻申请，查看审核状态 |
| 关键文件 | `apps/api/app/routers/shop/onboarding.py`（追加） · `apps/api/app/schemas/shop.py`（新建） |

**API 端点**：

```
GET  /api/v1/shop/onboarding/status     -- 查询入驻状态（not_onboarded/pending/approved/rejected）
POST /api/v1/shop/onboarding/submit     -- 提交入驻申请
POST /api/v1/shop/onboarding/ocr        -- OCR 识别证件（stub）
GET  /api/v1/shop/onboarding/detail     -- 查看申请详情（含驳回原因）
```

**提交请求体**：

```json
{
  "entity_type": "enterprise",
  "legal_name": "某某科技有限公司",
  "display_name": "某某课堂",
  "contact_name": "张老师",
  "contact_mobile": "13800138000",
  "unified_social_credit_code": "91110000XXXXX",
  "legal_rep_name": "张三",
  "bank_account_info": {},
  "qualification_files": {}
}
```

**业务逻辑**：

1. `status`：查 `shop_onboarding_applications` + `shop_merchant_accounts`，返回聚合状态
2. `submit`：`initiator=merchant_self`；已有 pending 不可重复提交（409）；已 approved 不可提交（409）
3. `ocr`：stub 返回固定结果（复用 M0 的 OCR stub 模式）
4. `detail`：返回申请全量字段 + 驳回原因（rejected 时）

**默认带出逻辑**（从当前登录用户/租户）：

| 字段 | 默认值 | 可改 |
|------|--------|:----:|
| contact_name | users.display_name | ✓ |
| contact_mobile | users.phone | ✓ |
| display_name | tenants.name | ✓ |
| unified_social_credit_code | tenants.credit_code（若有） | ✓ |

**验收**：

- [ ] 未入驻 tenant 调 status 返回 `not_onboarded`
- [ | 提交后 status 返回 `pending`
- [ ] pending 状态重复提交返回 409
- [ ] approved 状态再提交返回 409
- [ ] rejected 后可修改重提
- [ ] OCR stub 返回正常
- [ ] detail 含驳回原因（rejected 时）

### Step M2-3：前端页面（A20 + Dashboard 横幅）

| 项 | 内容 |
|----|------|
| 任务 | 实现 A20 入驻申请页面 + Dashboard 入驻引导横幅 |
| 关键文件 | `apps/web/src/views/shop/ShopOnboarding.vue` · `apps/web/src/views/Dashboard.vue`（追加横幅） |

**页面要求**：

| 页面 | 路由 | 内容 |
|------|------|------|
| Dashboard 横幅 | `/dashboard` | 按 onboarding_status 显示不同横幅（not_onboarded/pending/rejected/active） |
| A20 入驻申请 | `/shop/onboarding` | 表单提交 · 审核中只读 · 驳回可重提 |

**验收**：

- [ ] 未入驻时 Dashboard 显示「开通内容获客商城」横幅
- [ ] pending 时横幅显示「审核中」
- [ ] rejected 时横幅红色提示 + 驳回原因
- [ ] active 时横幅隐藏，侧栏出现「内容获客商城」入口
- [ ] A20 表单默认带出 contact_name / contact_mobile / display_name
- [ ] 提交成功跳转审核中页面

### Step M2-4：验收脚本与门禁

| 项 | 内容 |
|----|------|
| 任务 | 编写 M2 验收脚本 |
| 关键文件 | `apps/api/tests/verify_shop_m2.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM2-1 | 暂停商家 | active→suspended + 服务记录 |
| VM2-2 | 恢复商家 | suspended→active |
| VM2-3 | 清退商家 | →dismissed（终态） |
| VM2-4 | 清退后恢复 | 409 |
| VM2-5 | 自申入驻-提交 | pending + initiator=merchant_self |
| VM2-6 | 重复提交 | 409 |
| VM2-7 | 已入驻再提交 | 409 |
| VM2-8 | 驳回后重提 | 新申请 pending |
| VM2-9 | OCR stub | 返回固定结果 |
| VM2-10 | status 聚合 | 四态正确返回 |
| VM2-11 | 默认带出 | contact_name/mobile/display_name 预填 |
| VM2-12 | 权限隔离 | 非 platform 用户不可 suspend/resume/dismiss |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/run_crm_all.py --through latest
```

- [ ] `verify_shop_m2.py` 全 PASS（12/12）
- [ ] M0 + M1 回归全绿
- [ ] CRM 回归全绿

---

## 4. M4 · 商品与内容 + 人审

**目标**：商家可创建商品（课程/专栏/课时/数字资料/服务），提交审核；平台可人审通过/驳回；商品状态机正确流转。

**Alembic**：105

### Step M4-1：商品与内容数据模型

| 项 | 内容 |
|----|------|
| 任务 | 新增 Alembic 105 迁移，创建商品、课程、专栏、课时、资料、服务表 |
| 关键文件 | `apps/api/alembic/versions/105_shop_products.py` · `apps/api/app/models/shop.py`（追加） |

**需创建的表**：

```
shop_products                -- 商品主表
  id, tenant_id, shop_id, type(course/digital/service),
  title, subtitle, cover_url, detail_html, price_cents, original_price_cents,
  status(draft/pending_review/on_sale/off_sale/rejected),
  sort_order, sales_count, reject_reason, submitted_at, reviewed_by, reviewed_at,
  compliance_flags_json, created_at, updated_at

shop_courses                 -- 课程（商品 type=course 的扩展）
  id, product_id, course_type(video/audio/graphic), total_lessons, trial_lesson_ids_json,
  created_at, updated_at

shop_columns                 -- 专栏（课程分组容器）
  id, course_id, title, sort_order, lesson_count, status(draft/published/off_sale),
  created_at, updated_at

shop_lessons                 -- 课时
  id, column_id, title, content_type(video/graphic), video_url, graphic_content,
  duration_seconds, is_trial, sort_order, effective_watch_seconds,
  created_at, updated_at

shop_digital_assets          -- 数字资料包
  id, product_id, file_url, file_size, file_format, online_view(bool),
  download_limit, created_at, updated_at

shop_services                -- 服务类型商品
  id, product_id, service_type(appointment/times_card), total_count, valid_days,
  created_at, updated_at

shop_product_audit_logs      -- 商品审核日志
  id, product_id, action(submit/approve/reject/auto_flag), operator_id,
  detail_json, created_at
```

**验收**：

- [ ] `alembic upgrade head` 无报错
- [ ] 7 张表在数据库中存在
- [ ] `alembic_head.py` 更新 `EXPECTED_HEAD = "105"` 并 PASS
- [ ] 模型关系正确：product→course→column→lesson 级联

### Step M4-2：商品 CRUD API（商家端 A02–A06）

| 项 | 内容 |
|----|------|
| 任务 | 实现商品及内容容器的增删改查 API |
| 关键文件 | `apps/api/app/routers/shop/products.py` · `apps/api/app/schemas/shop.py` |

**API 端点**：

```
# 商品
GET    /api/v1/shop/products                    -- 列表（分页、类型/状态筛选）
POST   /api/v1/shop/products                    -- 创建商品
GET    /api/v1/shop/products/{id}               -- 详情
PATCH  /api/v1/shop/products/{id}               -- 编辑
DELETE /api/v1/shop/products/{id}               -- 删除（仅 draft）
POST   /api/v1/shop/products/{id}/submit        -- 提审

# 课程内容
POST   /api/v1/shop/products/{id}/columns       -- 创建专栏
PATCH  /api/v1/shop/products/{id}/columns/{cid} -- 编辑专栏
POST   /api/v1/shop/columns/{cid}/lessons       -- 创建课时
PATCH  /api/v1/shop/lessons/{lid}               -- 编辑课时
DELETE /api/v1/shop/lessons/{lid}               -- 删除课时

# 数字资料
POST   /api/v1/shop/products/{id}/digital-asset -- 上传资料
PATCH  /api/v1/shop/digital-assets/{id}         -- 编辑

# 服务
POST   /api/v1/shop/products/{id}/service       -- 配置服务
PATCH  /api/v1/shop/services/{id}               -- 编辑
```

**商品状态机**：

```
draft → pending_review → on_sale ⇄ off_sale
              ↓
          rejected → draft（修改后可重提）
```

**验收**：

- [ ] 创建 course 类型商品，含 1 专栏 3 课时（其中 1 节试看）
- [ ] 创建 digital 类型商品，含资料包
- [ ] 创建 service 类型商品，配置次数卡
- [ ] draft 状态可编辑、可删除
- [ ] on_sale 状态不可编辑（返回 409）
- [ ] 列表支持 type / status 筛选
- [ ] 多店隔离：A 店商品 B 店不可见（403/404）

### Step M4-3：商品审核 API（平台端 P09 + F6 机审 stub）

| 项 | 内容 |
|----|------|
| 任务 | 平台审核队列 + 通过/驳回 + 机审 stub |
| 关键文件 | `apps/api/app/routers/platform_shop/products.py` · `apps/api/app/services/shop_compliance_service.py`（新建） |

**API 端点**：

```
# 平台审核
GET   /api/v1/admin/shop/products/pending       -- 待审列表
GET   /api/v1/admin/shop/products/{id}/review   -- 审核详情
POST  /api/v1/admin/shop/products/{id}/approve  -- 通过
POST  /api/v1/admin/shop/products/{id}/reject   -- 驳回

# 机审（F6 stub）
POST  /api/v1/shop/products/{id}/auto-check     -- 提审时自动调用
```

**机审 stub 规则**（Phase 1 全走人审）：

```python
# compliance.auto_review_mode = "stub"
# 固定返回 auto_result = "flag"（一律转人审）
# 六类规则 stub：title_check / price_check / category_check / media_check /资质_check / content_check
# 全部返回 passed=True 但聚合结果=flag（不阻塞，转人审）
```

**驳回请求体**：

```json
{
  "reason": "标题包含违禁词",
  "category": "title_violation"
}
```

**验收**：

- [ ] 提审后商品 pending_review，机审 stub 返回 flag
- [ ] P09 待审列表正确返回 pending 商品
- [ | approve 后商品 on_sale
- [ ] reject 后商品 rejected + reject_reason
- [ ] rejected 商品修改后可重新提审
- [ ] 审核日志写入 `shop_product_audit_logs`
- [ ] on_sale 商品下架（off_sale）后买家不可购买

### Step M4-4：前端页面（A02–A06 商品管理）

| 项 | 内容 |
|----|------|
| 任务 | 实现商家端商品管理 Web 页面 |
| 关键文件 | `apps/web/src/views/shop/ShopProducts.vue` · `ShopProductEdit.vue` · `ShopProductReview.vue` |

**页面清单**：

| 页面 | 路由 | 功能 |
|------|------|------|
| 商品列表 | `/shop/products` | 列表 + 筛选 + 状态标签 |
| 商品创建/编辑 | `/shop/products/edit/:id?` | 表单（类型切换 / 课程编排 / 资料上传 / 服务配置） |
| 提审确认 | 弹窗 | 确认提审 + 机审结果提示 |

**验收**：

- [ ] 列表正确展示商品卡片 + 状态标签（draft/pending_review/on_sale/off_sale/rejected）
- [ ] 创建课程商品时可添加专栏和课时
- [ ] 课时可标记试看
- [ ] 提审后按钮变为「审核中」（不可编辑）
- [ ] rejected 商品显示驳回原因 + 可修改重提

### Step M4-5：验收脚本与门禁

| 项 | 内容 |
|----|------|
| 任务 | 编写 M4 验收脚本 |
| 关键文件 | `apps/api/tests/verify_shop_m4.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM4-1 | 创建课程商品 | draft + 关联 course/column/lesson |
| VM4-2 | 创建数字资料商品 | draft + 关联 digital_asset |
| VM4-3 | 创建服务商品 | draft + 关联 service（次数卡） |
| VM4-4 | 商品状态机-draft→pending | submit 后 pending_review |
| VM4-5 | 机审 stub | auto_result=flag |
| VM4-6 | 人审通过 | on_sale |
| VM4-7 | 人审驳回 | rejected + reason |
| VM4-8 | 驳回后重提 | rejected→draft→pending |
| VM4-9 | 下架 | on_sale→off_sale |
| VM4-10 | 下架后重新上架 | off_sale→on_sale |
| VM4-11 | 多店隔离 | A 店不可操作 B 店商品 |
| VM4-12 | on_sale 不可编辑 | 409 |
| VM4-13 | draft 删除 | 成功 |
| VM4-14 | 审核日志 | audit_logs 正确记录 |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m4.py
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/alembic_head.py      # EXPECTED_HEAD = "105"
```

- [ ] `verify_shop_m4.py` 全 PASS（14/14）
- [ ] M0–M2 回归全绿
- [ ] CRM 回归全绿
- [ ] Alembic head = 105

---

## 5. M5 · 订单、权益与退款

**目标**：买家下单 → 支付 → 权益开通；退款 → 权益撤销（F2）；商家可管理订单和权益。

**Alembic**：106

### Step M5-1：订单与权益数据模型

| 项 | 内容 |
|----|------|
| 任务 | 新增 Alembic 106 迁移，创建订单、买家、权益、退款表 |
| 关键文件 | `apps/api/alembic/versions/106_shop_orders.py` · `apps/api/app/models/shop.py`（追加） |

**需创建的表**：

```
shop_buyers                  -- 买家
  id, tenant_id, mobile, wx_openid, nickname, avatar_url,
  created_at, updated_at
  -- 唯一约束：(tenant_id, mobile)

shop_orders                  -- 订单（独立模型，不复用 B2B Order）
  id, tenant_id, shop_id, buyer_id, product_id, product_snapshot_json,
  order_no, type(course/digital/service), amount_cents,
  status(pending/paid/claim_pending/refunded/cancelled),
  paid_amount_cents, paid_at, paid_channel(wxpay/douyin/course_lib),
  refund_amount_cents, refunded_at, refund_reason,
  claim_token, claim_expires_at, claimed_buyer_id,
  needs_red_flush(bool), source(private/public_douyin/public_course_lib),
  wx_transaction_id, created_at, updated_at

shop_entitlements            -- 权益
  id, tenant_id, buyer_id, order_id, product_id, shop_id,
  status(active/revoked/expired),
  source_order_id, activated_at, revoked_at, revoke_reason,
  remaining_count,  -- 服务次数卡剩余次数
  expires_at, created_at, updated_at

shop_enrollments             -- 选课记录（独立表，不映射 CRM Contact）
  id, tenant_id, buyer_id, entitlement_id, course_id, lesson_id,
  status(active/revoked), progress_json, last_learned_at,
  created_at, updated_at

shop_refunds                 -- 退款记录
  id, order_id, tenant_id, amount_cents, reason, status(pending/success/failed),
  initiated_by(buyer/merchant), operator_id, processed_at,
  created_at, updated_at
```

**验收**：

- [ ] `alembic upgrade head` 无报错
- [ ] 5 张表存在
- [ ] `alembic_head.py` 更新 `EXPECTED_HEAD = "106"` 并 PASS
- [ ] shop_orders 不复用 B2B Order 模型

### Step M5-2：买家注册与身份归一

| 项 | 内容 |
|----|------|
| 任务 | 实现买家身份模型：mobile 归一 + openid 绑定 |
| 关键文件 | `apps/api/app/routers/mp/shop/auth.py`（新建） · `apps/api/app/services/shop_buyer_service.py`（新建） |

**API 端点**：

```
POST /api/v1/mp/shop/auth/login    -- 小程序登录（code→openid→查/建 buyer）
POST /api/v1/mp/shop/auth/bind     -- 绑定手机号
GET  /api/v1/mp/shop/auth/me       -- 当前买家信息
```

**身份归一逻辑**：

1. 小程序登录：按 `openid` 查 `shop_buyers`；无则创建（仅 openid，无 mobile）
2. 绑定手机号：按 `(tenant_id, mobile)` 查已有 buyer；有则合并 openid；无则更新当前 buyer 的 mobile
3. 下单时：须有 mobile（无 mobile 引导 M04 绑定）

**验收**：

- [ ] openid 登录创建 buyer（无 mobile）
- [ ] 绑定手机号后 buyer.mobile 有值
- [ ] 同手机号不同 openid 合并到同一 buyer
- [ ] 跨 tenant 不合并（tenant_id 隔离）

### Step M5-3：订单创建与权益开通 API（F1 流程）

| 项 | 内容 |
|----|------|
| 任务 | 实现下单 → 支付回调 → 权益开通的完整 F1 流程 |
| 关键文件 | `apps/api/app/routers/mp/shop/orders.py`（新建） · `apps/api/app/services/shop_order_service.py`（新建） |

**API 端点**：

```
# 买家端
POST /api/v1/mp/shop/orders                -- 下单（校验商品 on_sale + 店铺 active）
GET  /api/v1/mp/shop/orders                -- 我的订单列表
GET  /api/v1/mp/shop/orders/{id}           -- 订单详情

# 支付回调
POST /api/v1/mp/shop/payments/notify       -- 微信支付回调（F1）
POST /api/v1/mp/shop/payments/query        -- 主动查单（兜底）

# 商家端
GET  /api/v1/shop/orders                   -- 商家订单列表
GET  /api/v1/shop/orders/{id}              -- 订单详情
```

**F1 流程**：

```
买家下单 → order.status=pending
  → 调微信支付统一下单 → 返回 prepay_id
  → 买家支付 → 微信回调 notify
  → 验签 + 幂等校验 → order.status=paid + paid_amount_cents
  → 开通权益：entitlement.status=active
  → 课程类型：创建 enrollment 记录
  → 服务类型：remaining_count = total_count
```

**幂等设计**：

- notify 接口：按 `wx_transaction_id` 幂等；重复回调返回成功但不重复处理
- 下单接口：按 `buyer_id + product_id + 幂等 key` 防重

**验收**：

- [ ] 商品 on_sale 时可下单，off_sale 不可下（409）
- [ ] 店铺 suspended 时不可下单（409）
- [ ] 下单后 order.status=pending
- [ ] 模拟支付回调后 order.status=paid + entitlement.status=active
- [ ] 课程类型自动创建 enrollment
- [ ] 服务类型 remaining_count 正确
- [ ] 重复回调幂等（不重复开权益）
- [ ] 商家端订单列表正确展示

### Step M5-4：退款与权益撤销 API（F2 流程）

| 项 | 内容 |
|----|------|
| 任务 | 实现退款 → 撤销权益的 F2 流程 |
| 关键文件 | `apps/api/app/services/shop_order_service.py`（追加退款逻辑） |

**API 端点**：

```
# 买家端
POST /api/v1/mp/shop/orders/{id}/refund    -- 买家发起退款

# 商家端
POST /api/v1/shop/orders/{id}/refund       -- 商家发起退款
GET  /api/v1/shop/refunds                  -- 退款列表
```

**F2 流程**：

```
退款请求 → shop_refunds.status=pending
  → Phase 1 仅支持全额退款（amount_cents = paid_amount_cents）
  → 执行退款（微信支付退款 API / stub）
  → shop_refunds.status=success
  → order.status=refunded + refund_amount_cents
  → entitlement.status=revoked + revoked_at
  → enrollment.status=revoked（课程类型）
  → 已开票：needs_red_flush=true（不自动红冲）
```

**验收**：

- [ ] paid 订单可退款，退款后 order.status=refunded
- [ ] 退款后 entitlement.status=revoked
- [ ] 退款后 enrollment.status=revoked
- [ ] Phase 1 部分退款返回 422（仅支持全额）
- [ ] 已开票订单退款后 needs_red_flush=true
- [ ] refunded 订单不可再次退款（409）
- [ ] revoked 权益不可履约（M06–M10 拦截）

### Step M5-5：权益合并查询（A12）

| 项 | 内容 |
|----|------|
| 任务 | 实现多店套餐权益合并查询 |
| 关键文件 | `apps/api/app/routers/shop/entitlements.py`（新建） · `apps/api/app/services/shop_entitlement_service.py`（新建） |

**API 端点**：

```
# 商家端
GET /api/v1/shop/entitlements              -- 权益列表（含多店合并）
GET /api/v1/shop/entitlements/{id}         -- 权益详情

# 买家端
GET /api/v1/mp/shop/entitlements           -- 我的已购（tenant 级汇总）
```

**merge_entitlements 逻辑**：

- 同一 buyer 在同一 tenant 下多个店铺的权益合并展示
- 课程类：展示所有已购课程，标注来源店铺
- 服务类：展示剩余次数（不跨店合并次数）

**验收**：

- [ ] 买家在 A 店和 B 店各买 1 课程，M06 汇总展示 2 个课程
- [ ] 服务次数卡不跨店合并
- [ ] revoked 权益不在列表展示（或灰显）
- [ ] 商家端仅展示自己店铺的权益

### Step M5-6：前端页面（A09–A12 + M04–M06）

| 项 | 内容 |
|----|------|
| 任务 | 实现商家端订单/买家/权益管理 + 买家端下单/订单/已购页面 |
| 关键文件 | `apps/web/src/views/shop/ShopOrders.vue` · `ShopBuyers.vue` · `ShopEntitlements.vue` · `apps/mp/src/pages/shop/` |

**商家端页面**：

| 页面 | 路由 | 功能 |
|------|------|------|
| 订单管理 | `/shop/orders` | 列表 + 筛选 + 详情 + 退款操作 |
| 买家管理 | `/shop/buyers` | 买家列表 + 权益查看 |
| 权益管理 | `/shop/entitlements` | 权益列表 + 状态管理 |

**买家端页面（小程序）**：

| 页面 | 路径 | 功能 |
|------|------|------|
| 商品详情 | `pages/shop/product` | 商品信息 + 购买按钮 |
| 订单确认 | `pages/shop/checkout` | 确认订单 + 支付 |
| 我的订单 | `pages/shop/orders` | 订单列表 + 退款 |
| 我的已购 | `pages/shop/entitlements` | 已购课程/资料/服务 |

**验收**：

- [ ] 商家订单列表支持状态筛选（pending/paid/refunded）
- [ ] 退款操作弹窗确认 + 原因输入
- [ ] 买家商品详情页正确展示价格和购买按钮
- [ ] 买家订单列表展示各状态订单
- [ ] 买家已购页面展示课程/资料/服务分类

### Step M5-7：验收脚本与门禁

| 项 | 内容 |
|----|------|
| 任务 | 编写 M5 验收脚本 |
| 关键文件 | `apps/api/tests/verify_shop_m5.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM5-1 | 买家登录 | openid→buyer 创建 |
| VM5-2 | 绑定手机号 | mobile 归一 + openid 合并 |
| VM5-3 | 下单-pending | order.status=pending |
| VM5-4 | 支付回调-paid | order.status=paid + entitlement.active |
| VM5-5 | 课程权益 | enrollment 创建 |
| VM5-6 | 服务权益 | remaining_count 正确 |
| VM5-7 | 回调幂等 | 重复回调不重复处理 |
| VM5-8 | 退款-全额 | order.refunded + entitlement.revoked |
| VM5-9 | 退款-enrollment | enrollment.revoked |
| VM5-10 | 部分退款 | 422 |
| VM5-11 | 已开票退款 | needs_red_flush=true |
| VM5-12 | revoked 不可履约 | 权益状态校验 |
| VM5-13 | 多店权益合并 | tenant 级汇总 |
| VM5-14 | 商家订单列表 | 正确分页筛选 |
| VM5-15 | 下单校验-off_sale | 409 |
| VM5-16 | 下单校验-suspended | 409 |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m5.py
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/verify_shop_m4.py
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/alembic_head.py      # EXPECTED_HEAD = "106"
```

- [ ] `verify_shop_m5.py` 全 PASS（16/16）
- [ ] M0–M4 回归全绿
- [ ] CRM 回归全绿
- [ ] Alembic head = 106

---

## 6. M3 · 私域支付硬验收

**目标**：微信支付完整闭环——下单 → 统一下单 → 支付 → 回调 → 权益开通。**此为 P1-07 硬验收里程碑**。

**Alembic**：107（支付配置表）

### Step M3-1：支付配置数据模型

| 项 | 内容 |
|----|------|
| 任务 | 新增 Alembic 107 迁移，创建商家支付配置表 |
| 关键文件 | `apps/api/alembic/versions/107_shop_payment_config.py` · `apps/api/app/models/shop.py` |

**需创建的表**：

```
shop_payment_configs         -- 商家支付配置
  id, merchant_id, tenant_id, shop_id,
  wx_mch_id, wx_app_id, wx_api_key_encrypted, wx_cert_sn, wx_cert_pem_encrypted,
  wx_notify_url, status(active/disabled),
  onboarded_at, onboarded_by, created_at, updated_at

shop_payment_logs            -- 支付日志
  id, order_id, tenant_id, event(create/prepay/notify/refund/query),
  wx_transaction_id, request_json, response_json, status, error_msg,
  created_at
```

**验收**：

- [ ] `alembic upgrade head` 无报错
- [ ] 2 张表存在
- [ ] `alembic_head.py` 更新 `EXPECTED_HEAD = "107"` 并 PASS

### Step M3-2：微信支付集成服务

| 项 | 内容 |
|----|------|
| 任务 | 实现微信支付统一下单、回调验签、退款、查单 |
| 关键文件 | `apps/api/app/services/wechat_pay_service.py`（新建） · `apps/api/app/config.py`（追加配置） |

**核心方法**：

```python
class WeChatPayService:
    def create_prepay(order, payment_config) -> dict
    # 调微信统一下单 API，返回 prepay_id + 签名

    def verify_notify(raw_body, headers) -> dict | None
    # 验证微信回调签名，返回解密数据或 None

    def query_order(wx_transaction_id) -> dict
    # 主动查单（兜底机制）

    def refund(order, refund_amount_cents) -> dict
    # 调微信退款 API
```

**配置项**（`.env`）：

```ini
WECHAT_PAY_MODE=stub  # stub | production
WECHAT_PAY_CERT_PATH=
WECHAT_PAY_API_KEY=
```

**stub 模式**（开发/测试环境）：

```python
# stub 模式下：
# create_prepay → 返回固定 prepay_id="wx_stub_xxx"
# verify_notify → 验证测试签名后返回固定成功结果
# refund → 直接返回成功
# 用于 M3 验收无真实微信环境时跑通流程
```

**验收**：

- [ ] stub 模式下 create_prepay 返回有效 prepay_id
- [ ] stub 模式下 verify_notify 正确解析回调
- [ ] production 模式下（需真实密钥）接口正确组装请求
- [ ] 支付日志写入 shop_payment_logs

### Step M3-3：支付闭环端到端（F1 完整流程）

| 项 | 内容 |
|----|------|
| 任务 | 将 M5 的订单流程与微信支付服务对接，实现完整闭环 |
| 关键文件 | `apps/api/app/routers/mp/shop/orders.py`（完善） · `apps/api/app/services/shop_order_service.py`（完善） |

**完整流程**：

```
1. 买家 M04 下单 → POST /orders
   → 创建 order(status=pending)
   → 调 WeChatPayService.create_prepay()
   → 返回 prepay_id + 签名参数

2. 买家前端拉起微信支付
   → wx.requestPayment()

3. 微信回调 → POST /payments/notify
   → WeChatPayService.verify_notify()
   → 幂等校验（wx_transaction_id）
   → order.status=paid + paid_amount_cents + paid_at
   → 开通权益（entitlement.active）
   → 创建 enrollment（课程类型）
   → 写支付日志

4. 兜底查单（定时任务 / 手动触发）
   → WeChatPayService.query_order()
   → 处理未收到回调的订单
```

**幂等关键点**：

| 场景 | 幂等键 | 处理 |
|------|--------|------|
| 回调重复 | `wx_transaction_id` | 重复回调返回成功，不重复处理 |
| 下单重复 | `buyer_id + product_id + idempotency_key` | 返回已有 pending 订单 |
| 退款重复 | `order_id + refund_request_id` | 返回已有退款记录 |

**验收**：

- [ ] 下单→支付→回调→权益开通 全流程跑通（stub 模式）
- [ ] 回调验签失败返回 400
- [ ] 重复回调幂等
- [ ] 兜底查单能补偿未回调订单
- [ ] 支付日志完整记录每步

### Step M3-4：商家支付进件（A15）

| 项 | 内容 |
|----|------|
| 任务 | 商家端配置微信支付参数 |
| 关键文件 | `apps/api/app/routers/shop/payments.py`（新建） · `apps/web/src/views/shop/ShopPaymentConfig.vue` |

**API 端点**：

```
GET   /api/v1/shop/payment-config           -- 查看当前配置
POST  /api/v1/shop/payment-config           -- 保存支付配置
POST  /api/v1/shop/payment-config/test      -- 测试配置连通性
```

**验收**：

- [ ] 商家可保存 mch_id / app_id / api_key / cert
- [ ] api_key 和 cert 加密存储
- [ ] test 接口返回连通性结果（stub 模式返回 ok）
- [ ] 无支付配置时下单返回 422（需先配置）

### Step M3-5：验收脚本与门禁（P1-07 硬验收）

| 项 | 内容 |
|----|------|
| 任务 | 编写 M3 验收脚本——**此为 P1-07 硬验收，必须全 PASS** |
| 关键文件 | `apps/api/tests/verify_shop_m3.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM3-1 | 支付配置保存 | 配置加密存储 |
| VM3-2 | 支付配置测试 | stub 模式返回 ok |
| VM3-3 | 下单→prepay | 返回 prepay_id |
| VM3-4 | 回调→paid | order.paid + entitlement.active |
| VM3-5 | 回调→enrollment | 课程权益创建 |
| VM3-6 | 回调幂等 | 重复回调不重复开权益 |
| VM3-7 | 回调验签失败 | 400 |
| VM3-8 | 兜底查单 | 补偿 pending→paid |
| VM3-9 | 退款→revoked | order.refunded + entitlement.revoked |
| VM3-10 | 支付日志 | 每步有日志记录 |
| VM3-11 | 无配置下单 | 422 |
| VM3-12 | 多店支付隔离 | A 店配置不影响 B 店 |
| VM3-13 | 下单校验完整 | off_sale/suspended 不可下单 |
| VM3-14 | 端到端完整流程 | 下单→支付→回调→权益→退款→撤销 |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m3.py
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/verify_shop_m4.py
cd apps/api && python tests/verify_shop_m5.py
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/run_agent_a_c.py
cd apps/api && python tests/alembic_head.py      # EXPECTED_HEAD = "107"
```

- [ ] `verify_shop_m3.py` 全 PASS（14/14）—— **P1-07 硬验收**
- [ ] M0–M5 回归全绿
- [ ] CRM + Agent 回归全绿
- [ ] Alembic head = 107

---

## 7. M6 · 核销、预约与开票

**目标**：服务核销（A08）、预约管理（A07）、C 端发票申请（A13/M13）。

**Alembic**：108

### Step M6-1：核销与预约数据模型

| 项 | 内容 |
|----|------|
| 任务 | 新增 Alembic 108 迁移，创建预约、核销、发票表 |
| 关键文件 | `apps/api/alembic/versions/108_shop_fulfillment.py` · `apps/api/app/models/shop.py` |

**需创建的表**：

```
shop_bookings                -- 预约记录
  id, tenant_id, shop_id, buyer_id, entitlement_id, service_product_id,
  status(booked/completed/cancelled/no_show),
  booked_date, booked_time_slot, cancelled_at, cancel_reason,
  created_at, updated_at

shop_verifications           -- 核销记录
  id, tenant_id, shop_id, buyer_id, entitlement_id, booking_id,
  type(service_refund/times_card_deduct),
  status(success/failed), operator_id, verify_code,
  deducted_count, created_at

shop_invoice_requests        -- 发票申请
  id, tenant_id, shop_id, buyer_id, order_id,
  invoice_type(normal/special), title_type(person/company),
  title, tax_no, bank_name, bank_account, address, phone,
  email, amount_cents, status(pending/issued/rejected),
  issued_at, invoice_url, needs_red_flush(bool),
  reject_reason, created_at, updated_at
```

**验收**：

- [ ] `alembic upgrade head` 无报错
- [ ] 3 张表存在
- [ ] `alembic_head.py` 更新 `EXPECTED_HEAD = "108"` 并 PASS

### Step M6-2：核销 API（A08）

| 项 | 内容 |
|----|------|
| 任务 | 实现核销台 lookup + execute |
| 关键文件 | `apps/api/app/routers/shop/verifications.py`（新建） · `apps/api/app/services/shop_verification_service.py`（新建） |

**API 端点**：

```
# 商家端（核销台）
POST /api/v1/shop/verifications/lookup    -- 查找买家权益（手机号/核销码）
POST /api/v1/shop/verifications/execute   -- 执行核销
GET  /api/v1/shop/verifications           -- 核销记录列表
GET  /api/v1/shop/verifications/{id}      -- 核销详情
```

**核销流程（F4）**：

```
1. lookup：按手机号/核销码查找 buyer 的 active 权益
2. execute：
   → 校验权益 active + remaining_count > 0
   → 扣减 remaining_count
   → 写 shop_verifications 记录
   → 若有预约：更新 booking.status=completed
   → remaining_count=0 时 entitlement.status=expired
```

**验收**：

- [ ] 按手机号查找买家权益返回正确结果
- [ ] 核销扣减次数成功
- [ | remaining_count=0 后自动 expired
- [ ] revoked 权益不可核销（409）
- [ ] 核销记录正确写入
- [ ] `shop_clerk` 角色仅有核销台权限

### Step M6-3：预约 API（A07 + M10）

| 项 | 内容 |
|----|------|
| 任务 | 买家预约服务 + 商家查看预约名单 |
| 关键文件 | `apps/api/app/routers/mp/shop/bookings.py`（新建） · `apps/api/app/routers/shop/bookings.py`（新建） |

**API 端点**：

```
# 买家端
POST   /api/v1/mp/shop/bookings             -- 创建预约
GET    /api/v1/mp/shop/bookings             -- 我的预约列表
POST   /api/v1/mp/shop/bookings/{id}/cancel -- 取消预约

# 商家端
GET    /api/v1/shop/bookings                -- 预约名单
GET    /api/v1/shop/bookings/{id}           -- 预约详情
```

**业务规则**：

- 仅 service 类型商品且有 active 权益可预约
- 预约状态：booked → completed（核销后）/ cancelled（买家取消/超时）
- Phase 1 不支持撤销核销

**验收**：

- [ ] 买家可创建预约（booked）
- [ ] 买家可取消预约（cancelled）
- [ ] 商家可查看预约名单（按日期筛选）
- [ ] 核销后预约自动 completed
- [ ] 无权益不可预约（403）

### Step M6-4：发票 API（A13 + M13）

| 项 | 内容 |
|----|------|
| 任务 | 买家申请发票 + 商家开具 |
| 关键文件 | `apps/api/app/routers/mp/shop/invoices.py`（新建） · `apps/api/app/routers/shop/invoices.py`（新建） |

**API 端点**：

```
# 买家端
POST /api/v1/mp/shop/invoices              -- 申请发票
GET  /api/v1/mp/shop/invoices              -- 我的发票列表

# 商家端
GET  /api/v1/shop/invoices                 -- 发票申请列表
POST /api/v1/shop/invoices/{id}/issue      -- 开具发票
POST /api/v1/shop/invoices/{id}/reject     -- 驳回
```

**业务规则**：

- 仅 paid 订单可申请发票
- 发票抬头：个人（姓名）/ 企业（名称+税号）
- 商家开具后 status=issued + invoice_url
- 已开票订单退款时 needs_red_flush=true

**验收**：

- [ ] 买家可提交发票申请（个人/企业抬头）
- [ ] 商家可查看申请列表
- [ ] 开具后 status=issued
- [ ] 驳回后 status=rejected + reason
- [ ] refunded 订单不可申请发票（409）
- [ ] 退款时检查发票状态 → needs_red_flush

### Step M6-5：前端页面（A07/A08/A13 + M10–M13）

| 项 | 内容 |
|----|------|
| 任务 | 实现核销台、预约管理、发票管理 Web + 小程序页面 |
| 关键文件 | `apps/web/src/views/shop/ShopVerifications.vue` · `ShopBookings.vue` · `ShopInvoices.vue` · `apps/mp/src/pages/shop/` |

**验收**：

- [ ] 核销台页面：输入手机号 → 显示权益 → 确认核销
- [ ] 预约管理：日历视图 + 名单详情
- [ ] 发票管理：申请列表 + 开具操作
- [ ] 小程序 M10 预约页面正常
- [ ] 小程序 M13 发票申请页面正常

### Step M6-6：验收脚本与门禁

| 项 | 内容 |
|----|------|
| 任务 | 编写 M6 验收脚本 |
| 关键文件 | `apps/api/tests/verify_shop_m6.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM6-1 | 核销 lookup | 按手机号返回权益 |
| VM6-2 | 核销 execute | 扣减次数 + 记录 |
| VM6-3 | 次数耗尽 | entitlement.expired |
| VM6-4 | revoked 不可核销 | 409 |
| VM6-5 | 预约创建 | booked |
| VM6-6 | 预约取消 | cancelled |
| VM6-7 | 核销→预约完成 | booking.completed |
| VM6-8 | 发票申请-个人 | pending |
| VM6-9 | 发票申请-企业 | pending + 税号 |
| VM6-10 | 发票开具 | issued + url |
| VM6-11 | 发票驳回 | rejected + reason |
| VM6-12 | refunded 不可申请发票 | 409 |
| VM6-13 | 退款→红冲标记 | needs_red_flush=true |
| VM6-14 | shop_clerk 权限 | 仅核销台可访问 |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m6.py
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/verify_shop_m3.py
cd apps/api && python tests/verify_shop_m4.py
cd apps/api && python tests/verify_shop_m5.py
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/alembic_head.py      # EXPECTED_HEAD = "108"
```

- [ ] `verify_shop_m6.py` 全 PASS（14/14）
- [ ] M0–M5 回归全绿
- [ ] CRM 回归全绿
- [ ] Alembic head = 108

---

## 8. M7 · 公域链路 ①（Mx 验收）

**目标**：抖音公域链路 ①——抖店付款 → Webhook 回调 → 领权短信 → 买家绑定 → 履约。**此为 Mx 首演验收**。

**Alembic**：109

### Step M7-1：公域对接数据模型

| 项 | 内容 |
|----|------|
| 任务 | 新增 Alembic 109 迁移，创建公域渠道映射、Webhook 日志、领权 token 表 |
| 关键文件 | `apps/api/alembic/versions/109_shop_public_channel.py` · `apps/api/app/models/shop.py` |

**需创建的表**：

```
shop_channel_mappings        -- 公域商品映射
  id, tenant_id, shop_id, product_id,
  channel(douyin/course_lib), channel_product_id, channel_product_url,
  status(mapped/unmapped/syncing), synced_at, created_at, updated_at

shop_channel_audit_logs      -- 公域挂载审核日志
  id, tenant_id, shop_id, product_id, channel,
  event(map_attempt/unmount/auto_reject), detail_json, created_at

shop_webhook_events          -- Webhook 事件日志
  id, tenant_id, channel(douyin/course_lib),
  event_type, event_id, raw_payload_json, processed(bool),
  processed_at, processing_error, created_at

shop_claim_tokens            -- 领权令牌
  id, tenant_id, order_id, buyer_mobile,
  token, status(pending/claimed/expired),
  expires_at, claimed_buyer_id, claimed_at, created_at

shop_sms_logs                -- 短信发送记录
  id, tenant_id, shop_id, buyer_mobile,
  type(claim_link/notify/verify), content, status(sent/failed),
  provider_msg_id, sent_at, created_at
```

**验收**：

- [ ] `alembic upgrade head` 无报错
- [ ] 5 张表存在
- [ ] `alembic_head.py` 更新 `EXPECTED_HEAD = "109"` 并 PASS

### Step M7-2：公域挂载闸（A14 + P06 + F7）

| 项 | 内容 |
|----|------|
| 任务 | 实现商品映射到公域前的合规校验（挂载闸） |
| 关键文件 | `apps/api/app/routers/shop/channels.py`（新建） · `apps/api/app/services/shop_channel_service.py`（新建） |

**API 端点**：

```
# 商家端
GET   /api/v1/shop/channel-mappings             -- 映射列表
POST  /api/v1/shop/channel-mappings             -- 创建映射（触发挂载闸）
DELETE /api/v1/shop/channel-mappings/{id}        -- 解除映射

# 平台端
GET   /api/v1/admin/shop/channel-mappings       -- 全平台映射
POST  /api/v1/admin/shop/channel-mappings/{id}/force-unmount  -- 强制下架
```

**挂载闸校验（F7）**：

```
映射前校验：
  1. 商品 status=on_sale
  2. 商品已通过人审（compliance_flags 全 passed）
  3. 店铺 status=active
  4. 商家 status=active
  5. 课程库/抖店提审状态（如有）
任一不满足 → 拒绝映射 + 写 audit_log(auto_reject)
```

**验收**：

- [ ] on_sale 商品可映射到抖音
- [ ] off_sale / rejected 商品不可映射（409）
- [ ] suspended 商家不可映射（409）
- [ ] 审核日志记录每次映射尝试
- [ ] 平台可强制下架（force-unmount）

### Step M7-3：抖店 Webhook 接收与处理（F3 链路 ①）

| 项 | 内容 |
|----|------|
| 任务 | 接收抖店订单回调，创建 claim_pending 订单，发送领权短信 |
| 关键文件 | `apps/api/app/routers/webhooks/douyin.py`（新建） · `apps/api/app/services/shop_channel_service.py`（追加） |

**Webhook 端点**：

```
POST /api/v1/webhooks/douyin/order        -- 抖店下单回调
POST /api/v1/webhooks/douyin/refund       -- 抖店退款回调
```

**F3 链路 ① 流程**：

```
1. 抖店付款 → Webhook(order.paid)
   → 写 shop_webhook_events
   → 查 channel_mapping → 找到 product_id
   → 创建 order(status=claim_pending, source=public_douyin, paid_amount_cents)
   → 生成 claim_token + 过期时间(24h)
   → 发送领权短信（含 H5 领权链接）

2. 买家点击领权链接 → M14 领权页
   → 按 token 查 order + mobile
   → 查/建 buyer（mobile 归一）
   → 绑定 buyer_id 到 order
   → order.status=paid（从 claim_pending 转为 paid）
   → 开通权益 entitlement.active
   → claim_token.status=claimed

3. 抖店退款 → Webhook(order.refund)
   → 同 F2 逻辑：order.refunded + entitlement.revoked
```

**验收**：

- [ ] Webhook 接收后创建 claim_pending 订单
- [ ] 领权短信发送（stub 模式写 sms_log）
- [ ] claim_token 生成且有效
- [ ] 领权后 order.paid + entitlement.active
- [ ] Webhook 重复幂等（event_id 去重）
- [ ] 抖店退款 Webhook → 权益撤销
- [ ] 过期 token 领权返回 410

### Step M7-4：领权页面（M14 小程序）

| 项 | 内容 |
|----|------|
| 任务 | 实现买家领权小程序页面 |
| 关键文件 | `apps/mp/src/pages/shop/claim.vue`（新建） · `apps/api/app/routers/mp/shop/claim.py`（新建） |

**API 端点**：

```
GET  /api/v1/mp/shop/claim/{token}         -- 查看领权信息（商品名/手机号尾号）
POST /api/v1/mp/shop/claim/{token}         -- 确认领权（绑定 openid）
```

**页面状态**：

| 状态 | 展示 |
|------|------|
| pending | 商品信息 + 手机号尾号 + 「确认领权」按钮 |
| claimed | 「已领取」+ 去学习入口 |
| expired | 「链接已过期，请联系客服」 |

**验收**：

- [ ] pending token 展示商品信息和手机尾号
- [ ] 确认领权后绑定 openid + 开通权益
- [ ] 已领权 token 再次访问显示 claimed
- [ ] 过期 token 显示过期提示

### Step M7-5：公域对接设置（A23）

| 项 | 内容 |
|----|------|
| 任务 | 商家端配置公域对接参数（抖店 Webhook URL / 绑店 / 密钥） |
| 关键文件 | `apps/api/app/routers/shop/channel_settings.py`（新建） · `apps/web/src/views/shop/ShopChannelSettings.vue` |

**API 端点**：

```
GET  /api/v1/shop/channel-settings          -- 查看公域对接配置
POST /api/v1/shop/channel-settings          -- 保存配置
GET  /api/v1/shop/channel-settings/webhook-url -- 获取 Webhook 回调地址
```

**验收**：

- [ ] 商家可保存抖店对接参数
- [ ] Webhook URL 自动生成（含 tenant 标识）
- [ ] 配置未完成时不可创建映射

### Step M7-6：验收脚本与门禁（Mx 验收）

| 项 | 内容 |
|----|------|
| 任务 | 编写 M7 验收脚本——**此为 Mx 首演验收** |
| 关键文件 | `apps/api/tests/verify_shop_m7.py` |

**验收用例**：

| 编号 | 用例 | 期望 |
|------|------|------|
| VM7-1 | 创建映射-正常 | mapped + audit_log |
| VM7-2 | 创建映射-off_sale | 409 + auto_reject |
| VM7-3 | 创建映射-suspended | 409 |
| VM7-4 | 抖店 Webhook-下单 | claim_pending + claim_token + sms |
| VM7-5 | 领权-pending | token 信息返回 |
| VM7-6 | 领权-确认 | order.paid + entitlement.active |
| VM7-7 | 领权-已领 | claimed |
| VM7-8 | 领权-过期 | 410 |
| VM7-9 | Webhook 幂等 | 重复 event_id 不重复处理 |
| VM7-10 | 抖店退款 | order.refunded + entitlement.revoked |
| VM7-11 | 强制下架 | mapping 状态更新 |
| VM7-12 | 对接配置保存 | 参数保存成功 |
| VM7-13 | Mx 端到端 | 挂载→付款→领权→履约→退款→撤销 |

**门禁命令**：

```bash
cd apps/api && python tests/verify_shop_m7.py
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/verify_shop_m3.py
cd apps/api && python tests/verify_shop_m4.py
cd apps/api && python tests/verify_shop_m5.py
cd apps/api && python tests/verify_shop_m6.py
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/run_agent_a_c.py
cd apps/api && python tests/alembic_head.py      # EXPECTED_HEAD = "109"
```

- [ ] `verify_shop_m7.py` 全 PASS（13/13）—— **Mx 首演验收**
- [ ] M0–M6 回归全绿
- [ ] CRM + Agent 回归全绿
- [ ] Alembic head = 109

---

## 9. M8 · 公域链路 ②（可选）

**目标**：课程库/小程序交易 Webhook 链路 ②。与链路 ① 二选一先通，M7 已通则 M8 为可选。

**Alembic**：110

### Step M8-1：课程库 Webhook（F3b 链路 ②）

| 项 | 内容 |
|----|------|
| 任务 | 接收课程库/小程序交易 Webhook，直接开通权益（无领权环节） |
| 关键文件 | `apps/api/app/routers/webhooks/course_lib.py`（新建） |

**F3b 流程**：

```
课程库/小程序支付 → Webhook(order.paid)
  → 查 channel_mapping → 找到 product_id
  → 按 mobile 查/建 buyer
  → 创建 order(status=paid, source=public_course_lib)
  → 直接开通权益（无 claim_pending）
```

**与链路 ① 区别**：

| 维度 | 链路 ①（抖店） | 链路 ②（课程库） |
|------|----------------|------------------|
| 支付 | 抖店收银台 | 课程库/小程序支付 |
| 领权 | 需领权短信+M14 | 直接开通（mobile 归一） |
| 订单状态 | claim_pending→paid | 直接 paid |
| 短信 | 发送领权链接 | 可选通知短信 |

### Step M8-2：验收脚本

| 编号 | 用例 | 期望 |
|------|------|------|
| VM8-1 | 课程库 Webhook-下单 | order.paid + entitlement.active |
| VM8-2 | Webhook 幂等 | 重复不重复处理 |
| VM8-3 | 课程库退款 | order.refunded + entitlement.revoked |
| VM8-4 | 端到端 | 挂载→支付→直接开通→退款→撤销 |

---

## 10. 最终集成验收

### 10.1 全批次回归

```bash
# 全部商城验收脚本
cd apps/api && python tests/verify_shop_m0.py
cd apps/api && python tests/verify_shop_m1.py
cd apps/api && python tests/verify_shop_m2.py
cd apps/api && python tests/verify_shop_m3.py
cd apps/api && python tests/verify_shop_m4.py
cd apps/api && python tests/verify_shop_m5.py
cd apps/api && python tests/verify_shop_m6.py
cd apps/api && python tests/verify_shop_m7.py
# cd apps/api && python tests/verify_shop_m8.py  # 可选

# 全部 CRM 回归
cd apps/api && python tests/run_crm_all.py --through latest
cd apps/api && python tests/run_agent_a_c.py

# Alembic 一致性
cd apps/api && python tests/alembic_head.py
```

### 10.2 Mx 端到端验收场景

| 场景 | 步骤 | 期望结果 |
|------|------|----------|
| 私域完整闭环 | 下单→支付→学课→退款→不可学 | 全流程 PASS |
| 公域链路 ① | 抖店挂载→付款→领权短信→绑定→学课→退款→不可学 | 全流程 PASS |
| 多店权益 | 买家在 A/B 两店各购课程→M06 汇总展示 | 两课程均可见 |
| 服务核销 | 购买 5 次卡→预约→核销 1 次→剩余 4 次→核销完毕→expired | 次数正确 |
| 合规闸 | 未过审商品→不可映射公域→不可购买 | 拦截成功 |
| 发票退款 | 开票后退款→needs_red_flush=true | 标记正确 |
| 商家暂停 | suspend→买家不可新购→已购可继续学 | 仅拦截新购 |

### 10.3 验收清单汇总

| 批次 | 脚本 | 用例数 | Alembic | 状态 |
|------|------|--------|---------|------|
| M0 | `verify_shop_m0.py` | 26 | 098–103 | ✅ 已完成 |
| M1 | `verify_shop_m1.py` | 12 | 104 | ⬜ |
| M2 | `verify_shop_m2.py` | 12 | — | ⬜ |
| M4 | `verify_shop_m4.py` | 14 | 105 | ⬜ |
| M5 | `verify_shop_m5.py` | 16 | 106 | ⬜ |
| M3 | `verify_shop_m3.py` | 14 | 107 | ⬜ |
| M6 | `verify_shop_m6.py` | 14 | 108 | ⬜ |
| M7 | `verify_shop_m7.py` | 13 | 109 | ⬜ |
| M8 | `verify_shop_m8.py` | 4 | 110 | ⬜ 可选 |
| **合计** | — | **125** | 104–110 | — |

---

## 11. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 微信支付进件延迟 | M3 硬验收阻塞 | stub 模式先跑通全流程；进件并行推进 |
| 抖音教培报白未通过 | M7 Mx 验收阻塞 | 链路 ②（M8）作为 Plan B；私域先行 |
| 商品合规规则复杂 | M4 延期 | Phase 1 机审 stub（全转人审），不阻塞 |
| 多店权益合并逻辑复杂 | M5 延期 | 先实现单店，多店合并迭代 |
| 小程序审核延迟 | 买家端联调阻塞 | H5 调试模式 + 真机预览并行 |
| Alembic 迁移冲突 | 多人并行开发阻塞 | 每步结束确认 head 一致；禁止跳号 |

---

## 12. 关键文件索引（实施时核对）

| 模块 | 路径 |
|------|------|
| 数据模型 | `apps/api/app/models/shop.py` |
| Alembic 迁移 | `apps/api/alembic/versions/` |
| 商家端路由 | `apps/api/app/routers/shop/` |
| 平台端路由 | `apps/api/app/routers/platform_shop/` |
| 买家端路由 | `apps/api/app/routers/mp/shop/`（新建） |
| Webhook 路由 | `apps/api/app/routers/webhooks/`（新建） |
| Schema | `apps/api/app/schemas/shop.py`（新建） · `shop_platform.py` |
| 服务层 | `apps/api/app/services/shop_*.py`（新建） |
| 微信支付 | `apps/api/app/services/wechat_pay_service.py`（新建） |
| 验收脚本 | `apps/api/tests/verify_shop_m*.py` |
| Web 前端 | `apps/web/src/views/shop/`（新建） |
| 小程序前端 | `apps/mp/src/pages/shop/`（新建） |
| PRD 主文档 | `docs/01-PRD/21-内容获客商城-phase1/PRD-内容获客商城-phase1.md` |
| UI 原型 | `docs/01-PRD/21-内容获客商城-phase1/01-管理端UI.html` · `02-买家端UI.html` · `06-平台端UI.html` |
| 数据流图 | `docs/01-PRD/21-内容获客商城-phase1/03-数据流.html` |
| 数据模型图 | `docs/01-PRD/21-内容获客商城-phase1/04-数据模型.html` |

---

## 13. Cursor 执行指令模板

每个 Step 执行时，按以下模板向 Cursor 下达指令：

```
请执行 [Step 编号] 的任务：

1. 阅读 PRD 相关章节：[PRD 章节引用]
2. 创建/修改以下文件：[文件列表]
3. 实现 [具体功能描述]
4. 编写验收脚本 [脚本名]，包含以下用例：[用例列表]
5. 运行验收脚本，确保全 PASS
6. 运行回归门禁：[回归命令列表]
7. 更新 alembic_head.py 中的 EXPECTED_HEAD（如涉及新迁移）

约束：
- 不得破坏已有功能（回归必须全绿）
- 不得跳过验收步骤
- 每个验收用例必须有明确的 PASS/FAIL 判定
- 代码风格与现有项目一致（FastAPI + SQLAlchemy 2.0 + Pydantic v2）
```

---

> 本执行计划严格遵循项目硬约束：学生数据独立表、shop_orders 独立模型、课程内容使用 shop_courses 模型。实施顺序按依赖关系调整为 M1→M2→M4→M5→M3→M6→M7→M8，每步一步一验，回归全绿才进下一步。
