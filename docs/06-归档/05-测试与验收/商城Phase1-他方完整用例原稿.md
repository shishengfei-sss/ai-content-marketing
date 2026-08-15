# 内容获客商城 Phase 1 — 完整测试用例文档（7 轮 · 500+ 用例 · 含边界值与业务场景）

| 项目 | 说明 |
|------|------|
| 文档版本 | v2.0-enhanced |
| 关联执行计划 | [商城Phase1-M1至M8-执行计划.md](../02-执行计划/商城Phase1-M1至M8-执行计划.md) |
| 关联 PRD | [PRD-内容获客商城-phase1.md](../01-PRD/21-内容获客商城-phase1/PRD-内容获客商城-phase1.md) |
| 测试框架 | 后端 pytest + TestClient；前端 Playwright (Python 驱动)；Mock stub |
| 运行命令 | `python tests/run_shop_all.py`（全量）· `--round N`（指定轮次）· `--through M6`（截断） |
| 执行者 | Cursor AI 自动化执行 |
| 总用例数 | 500+（含主用例 + 边界值变体 + 业务场景） |

---

## 测试策略总览

### 七轮测试架构

```
Round 1: 后端 API 测试（135 主用例 + 628 边界值 + 521 业务场景）
  ├── M0 权限入驻（60 用例，VS-1~30 + VS-N）← 已有 verify_shop_m0.py
  ├── M1 套餐订阅（35 用例，VM1-1~10 + VM1-N）
  ├── M2 商家状态（40 用例，VM2-1~10 + VM2-N）
  ├── M4 商品内容（50 用例，VM4-1~12 + VM4-N）
  ├── M5 订单权益（60 用例，VM5-1~14 + VM5-N）
  ├── M3 支付硬验收（45 用例，VM3-1~12 + VM3-N）← P1-07 硬验收
  ├── M6 核销开票（45 用例，VM6-1~12 + VM6-N）
  └── M7 公域Mx（40 用例，VM7-1~10 + VM7-N）← Mx 首演验收

Round 2: Web 前端 UI 测试（30 用例，UI-W-01~30）
  ├── 商家端页面（20 用例）
  └── 平台端页面（10 用例）

Round 3: 小程序 UI 测试（20 用例，UI-M-01~20）
  ├── 买家购物流程（10 用例）
  └── 买家履约流程（10 用例）

Round 4: E2E 集成流程测试（30 用例，E2E-01~30）
  ├── F0-F12 核心数据流（13 用例）
  └── 扩展场景（17 用例）

Round 5: Mock 外部对接测试（25 用例，MOCK-01~25）
  ├── 微信支付 Mock（8 用例）
  ├── 抖店 Webhook Mock（9 用例）
  ├── 短信发送 Mock（4 用例）
  └── 课程库 Mock（4 用例）

Round 6: 安全与 PII 测试（30 用例，SEC-01~30）
  ├── 数据加密（6 用例）
  ├── 日志脱敏（6 用例）
  ├── API 展示脱敏（6 用例）
  ├── 权限隔离（6 用例）
  └── 保留期合规（6 用例）

Round 7: 回归测试（10 用例，REG-01~10）
  ├── CRM/Agent 全量回归
  ├── M0 商城回归
  ├── Alembic 一致性
  └── 前端现有页面回归
```

### Mock/Stub 策略

| 外部服务 | Mock 方式 | 环境变量 | 说明 |
|----------|----------|----------|------|
| 微信支付 | stub 模式 | `WECHAT_PAY_MODE=stub` | 统一下单返回固定 prepay_id="wx_stub_xxx"；回调验签用测试密钥 |
| 抖店 Webhook | 本地模拟 | `DOUYIN_WEBHOOK_MODE=stub` | 模拟下单/退款 Webhook 推送 |
| 短信发送 | 内存记录 | `SMS_MODE=stub` | 不实际发送，写入 shop_sms_logs |
| 课程库 | 本地模拟 | `COURSE_LIB_MODE=stub` | 模拟课程库支付回调 |

### 测试环境配置

```bash
# 环境变量
export WECHAT_PAY_MODE=stub
export DOUYIN_WEBHOOK_MODE=stub
export SMS_MODE=stub
export COURSE_LIB_MODE=stub
export FORCE_FAKE_PLATFORM_LLM=1
export VERIFY_LIVE_API=0

# 服务端口
# Web 前端 (Vite): localhost:5173
# Mini-Program H5 (uni-app): localhost:5174
# API 后端 (FastAPI): localhost:8000
```

### 测试账号

| 角色 | 手机号 | 密码 | 说明 |
|------|--------|------|------|
| 平台管理员 | 13800000000 | admin123456 | 超级管理员，拥有全部 platform.shop.* 权限 |
| 商家用户 | 13900000099 | test123456 | 已入驻商家，status=active |
| 商家B | 13900000088 | test123456 | 第二个商家租户（用于多店隔离测试）|
| 买家A | 13800000001 | test123456 | 小程序买家 |

### 每个测试用例的标准格式

每个测试用例包含以下 6 个部分，确保 Cursor AI 可直接执行：

1. **前置条件** — 具体的数据状态、登录信息、环境变量
2. **API / 页面路由** — 精确的 HTTP 方法和路径，或前端路由
3. **请求体 / 测试步骤** — 完整的 JSON 请求体或 Playwright 操作步骤
4. **期望结果** — HTTP 状态码、响应字段、DOM 元素断言
5. **边界值测试** — 每个字段的边界值变体（空值/最小/最大/超长/格式错误/特殊字符）
6. **业务场景测试** — 正常流程/异常流程/状态转换/权限校验/并发/幂等

### 验收通过标准

#### 里程碑门禁

| 里程碑 | 硬验收 | 通过标准 | 可选 |
|--------|--------|----------|------|
| M0 | — | VS-1~30 + VS-N 全 PASS | — |
| M1 | — | VM1-1~10 + VM1-N 全 PASS | — |
| M2 | — | VM2-1~10 + VM2-N 全 PASS | — |
| M4 | — | VM4-1~12 + VM4-N 全 PASS | — |
| M5 | — | VM5-1~14 + VM5-N 全 PASS | — |
| **M3** | **P1-07** | **VM3-1~12 + VM3-N 全 PASS** | — |
| M6 | — | VM6-1~12 + VM6-N 全 PASS | — |
| **M7** | **Mx 首演** | **VM7-1~10 + VM7-N 全 PASS + E2E-13** | — |
| M8 | — | — | VM8-1~4 |

#### 整体通过标准

- Round 1（后端 API）：135 主用例 + 全部边界值 + 全部业务场景 PASS
- Round 2（Web UI）：30/30 PASS
- Round 3（MP UI）：20/20 PASS
- Round 4（E2E）：30/30 PASS
- Round 5（Mock）：25/25 PASS
- Round 6（安全）：30/30 PASS
- Round 7（回归）：10/10 PASS

#### 允许的例外

| 项 | 说明 | 处理 |
|----|------|------|
| M8 | 可选批次 | 跳过不影响整体通过 |
| 真实微信支付 | 需商户号 | stub 模式通过即验收 |
| 真实抖音报白 | 需邀约 | stub 模式通过即验收 |

---

## 执行顺序（依赖驱动，非 PRD 编号顺序）

```
M0 → M1(套餐) → M2(状态) → M4(商品) → M5(订单) → M3(支付) → M6(核销) → M7(公域) → M8(可选)
```

> M3 支付硬验收依赖 M5 订单创建；M6 核销依赖 M3 支付完成；M7 公域依赖 M4 商品上架。

---


---
# 内容获客商城 Phase 1 — Round 1 后端 API 测试用例

> **覆盖模块**: M0 权限入驻 / M1 套餐订阅 / M2 商家状态
> **测试环境**: WECHAT_PAY_MODE=stub
> **平台管理员**: 手机号 13800000000 / 密码 admin123456
> **商家用户**: 手机号 13900000099 / 密码 test123456
> **文档版本**: v1.0
> **日期**: 2026-08-12

---

## 目录

- [M0 权限入驻](#m0-权限入驻)
  - [认证与权限](#m0-认证与权限)
  - [商家列表管理](#m0-商家列表管理)
  - [入驻流程](#m0-入驻流程)
  - [OCR 识别](#m0-ocr-识别)
  - [服务日志与续费申请](#m0-服务日志与续费申请)
  - [商家状态变更](#m0-商家状态变更)
  - [权限隔离与边界](#m0-权限隔离与边界)
- [M1 套餐订阅](#m1-套餐订阅)
- [M2 商家状态](#m2-商家状态)

---

## M0 权限入驻

### M0 认证与权限

---

### VS-1: 平台管理员登录

**前置条件**:
- 数据库中存在平台管理员账号: 手机号 13800000000, 密码 admin123456
- 该管理员已绑定 platform_shop_ops 角色
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /auth/login`
**Headers**: `Content-Type: application/json`

**请求体**:
```json
{
  "phone": "13800000000",
  "password": "admin123456"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `access_token` (非空字符串), `token_type`="bearer"
- access_token 为有效 JWT, 可用于后续 Authorization Header

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-1-B1 | phone | "" | 空值 | 422 | 手机号不能为空 |
| VS-1-B2 | phone | "1380000000" (10位) | 格式错误 | 422 | 手机号格式不正确 |
| VS-1-B3 | phone | "138000000001" (12位) | 格式错误 | 422 | 手机号格式不正确 |
| VS-1-B4 | phone | "23800000000" (不以1开头) | 格式错误 | 422 | 手机号格式不正确 |
| VS-1-B5 | password | "" | 空值 | 422 | 密码不能为空 |
| VS-1-B6 | phone | "13800000000" | 不存在用户 | 401 | 用户不存在或密码错误 |
| VS-1-B7 | password | "wrongpass123" | 密码错误 | 401 | 用户不存在或密码错误 |
| VS-1-B8 | 请求体 | 缺少 phone 字段 | 缺失字段 | 422 | 字段必填 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-1-S1 | 正常登录 | 管理员已存在 | POST 登录 | 200, 返回 access_token |
| VS-1-S2 | 密码错误 | 管理员已存在 | 错误密码登录 | 401 |
| VS-1-S3 | 用户不存在 | 手机号未注册 | POST 登录 | 401 |
| VS-1-S4 | 连续错误登录后正确登录 | 连续3次密码错误 | 正确密码登录 | 200 (无频率限制或未触发) |
| VS-1-S5 | token 可用性验证 | 已获取 token | GET /auth/me 携带 token | 200, 返回用户信息 |

---

### VS-2: 商家用户登录

**前置条件**:
- 数据库中存在商家用户: 手机号 13900000099, 密码 test123456
- 该用户已绑定 shop_admin 角色, 关联到 active 状态的租户
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /auth/login`
**Headers**: `Content-Type: application/json`

**请求体**:
```json
{
  "phone": "13900000099",
  "password": "test123456"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `access_token` (非空字符串), `token_type`="bearer"
- 该 token 可访问 /shop/* 接口, 但不能访问 /admin/shop/* 接口

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-2-B1 | phone | "1390000009" (10位) | 格式错误 | 422 | 手机号格式不正确 |
| VS-2-B2 | phone | "139000000999" (12位) | 格式错误 | 422 | 手机号格式不正确 |
| VS-2-B3 | password | "" | 空值 | 422 | 密码不能为空 |
| VS-2-B4 | password | "test12345" (少一位) | 密码错误 | 401 | 用户不存在或密码错误 |
| VS-2-B5 | password | "test1234567" (多一位) | 密码错误 | 401 | 用户不存在或密码错误 |
| VS-2-B6 | phone | "13900000098" | 不存在用户 | 401 | 用户不存在或密码错误 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-2-S1 | 正常登录 | 商家用户已存在 | POST 登录 | 200, 返回 access_token |
| VS-2-S2 | 商家token访问admin接口 | 已获取商家token | GET /admin/shop/merchants | 403, 无权限 |
| VS-2-S3 | 商家token访问shop接口 | 已获取商家token | GET /shop/permissions/me | 200, 返回权限列表 |
| VS-2-S4 | 密码错误后正确登录 | 连续2次错误 | 正确密码 | 200 |

---

### VS-3: 获取当前用户信息

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 商家用户已登录, 获取 merchant_token

**API**: `GET /auth/me`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `user_id`, `phone`, `name`, `permissions` (数组)
- permissions 中包含 shop.* 权限项 (37 项中的子集)
- 包含 `platform_shop_permissions` 字段

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-3-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-3-B2 | Authorization | "Bearer invalid_token" | 无效token | 401 | 令牌无效 |
| VS-3-B3 | Authorization | "Bearer " (空值) | 空token | 401 | 令牌为空 |
| VS-3-B4 | Authorization | 过期的 token | 过期 | 401 | 令牌已过期 |
| VS-3-B5 | Authorization | 格式错误 "Token xxx" | 格式错误 | 401 | 认证格式不正确 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-3-S1 | 管理员获取自身信息 | admin 已登录 | GET /auth/me | 200, 含 platform_shop_permissions |
| VS-3-S2 | 商家获取自身信息 | merchant 已登录 | GET /auth/me | 200, 含 shop permissions |
| VS-3-S3 | 验证权限区分 | 管理员和商家各获取 | 对比 permissions | 管理员含 platform.shop.*, 商家含 shop.* |
| VS-3-S4 | 未携带token | 无 token | GET /auth/me | 401 |

---

### VS-4: 获取商城权限目录

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 数据库中 SHOP_MERCHANT_PERMISSIONS 常量已定义, 包含 37 项权限

**API**: `GET /shop/permissions/catalog`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `permissions` (数组, 长度 = 37)
- 每项权限包含: `code`, `name`, `description` 等字段
- 权限编码以 `shop.` 开头, 不包含 `platform.shop.*` 编码

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-4-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-4-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无 shop 权限 |
| VS-4-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-4-S1 | 商家获取权限目录 | merchant 已登录 | GET /shop/permissions/catalog | 200, 37 项权限 |
| VS-4-S2 | 验证权限编码前缀 | 已获取目录 | 检查 permissions | 全部以 shop. 开头 |
| VS-4-S3 | 验证不含 platform 权限 | 已获取目录 | 检查 permissions | 无 platform.shop.* 编码 |
| VS-4-S4 | 验证权限数量 | 已获取目录 | len(permissions) | 等于 37 |

---

### VS-5: 获取当前用户商城权限

**前置条件**:
- 商家用户已登录 (shop_admin 角色), 获取 merchant_token
- shop_admin 角色拥有全部 37 项商城权限

**API**: `GET /shop/permissions/me`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `permissions` (数组), `role` 或 `role_code` 字段
- shop_admin 角色用户返回全部 37 项权限

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-5-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-5-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无 shop 权限 |
| VS-5-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-5-S1 | shop_admin 获取权限 | shop_admin 已登录 | GET /shop/permissions/me | 200, 37 项权限 |
| VS-5-S2 | shop_clerk 获取权限 | shop_clerk 已登录 | GET /shop/permissions/me | 200, 仅 3 项 (redemption 相关) |
| VS-5-S3 | shop_content 获取权限 | shop_content 已登录 | GET /shop/permissions/me | 200, 内容相关权限 |
| VS-5-S4 | 验证 shop_clerk 权限范围 | clerk 权限已返回 | 检查权限列表 | 仅含 shop.redemption.execute, shop.redemption.list_own, shop.redemption.read |

---

### VS-6: 获取商城内置角色

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 数据库中 SHOP_BUILTIN_ROLE_CODES = {shop_admin, shop_content, shop_support, shop_clerk}

**API**: `GET /shop/roles`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: 角色数组, 长度 = 4
- 每个角色含: `code`, `name`, `permissions` 等字段
- 角色编码包含: shop_admin, shop_content, shop_support, shop_clerk

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-6-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-6-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无 shop 权限 |
| VS-6-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-6-S1 | 获取内置角色列表 | merchant 已登录 | GET /shop/roles | 200, 4 个角色 |
| VS-6-S2 | 验证角色编码 | 角色列表已返回 | 检查 code 字段 | 含 shop_admin, shop_content, shop_support, shop_clerk |
| VS-6-S3 | 验证 shop_clerk 权限 | 角色列表已返回 | 检查 clerk 的 permissions | 仅 3 项 redemption 权限 |
| VS-6-S4 | 验证 shop_admin 权限 | 角色列表已返回 | 检查 admin 的 permissions | 37 项全量权限 |

---

### VS-7: 获取平台商家管理权限目录

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中 PLATFORM_SHOP_PERMISSIONS 常量已定义, 包含 18 项权限
- 包含 role_templates 字段

**API**: `GET /admin/shop/permissions/catalog`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `permissions` (数组, 长度 = 18), `role_templates` (数组)
- 权限编码以 `platform.shop.` 开头
- role_templates 包含 platform_shop_ops, platform_shop_cs, platform_shop_finance

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-7-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-7-B2 | Authorization | 商家 token | 无 admin 权限 | 403 | 无平台管理权限 |
| VS-7-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-7-S1 | 管理员获取权限目录 | admin 已登录 | GET /admin/shop/permissions/catalog | 200, 18 项权限 |
| VS-7-S2 | 验证权限编码前缀 | 已获取目录 | 检查 permissions | 全部以 platform.shop. 开头 |
| VS-7-S3 | 验证 role_templates | 已获取目录 | 检查 role_templates | 含 ops, cs, finance 三个子角色模板 |
| VS-7-S4 | 商家无权访问 | merchant 已登录 | GET /admin/shop/permissions/catalog | 403 |

---

### VS-8: 获取当前平台管理员商家管理权限

**前置条件**:
- 平台管理员 (platform_shop_ops 角色) 已登录, 获取 admin_token
- platform_shop_ops 角色拥有 onboarding.initiate, tag.manage, merchant.tag 等权限

**API**: `GET /admin/shop/permissions/me`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `platform_shop_role` (如 "platform_shop_ops"), `permissions` (数组)
- ops 角色权限中包含 onboarding.initiate, tag.manage, merchant.tag

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-8-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-8-B2 | Authorization | 商家 token | 无 admin 权限 | 403 | 无平台管理权限 |
| VS-8-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-8-S1 | ops 获取自身权限 | ops admin 已登录 | GET /admin/shop/permissions/me | 200, 含 onboarding.initiate + tag.manage |
| VS-8-S2 | cs 获取自身权限 | cs admin 已登录 | GET /admin/shop/permissions/me | 200, 含 onboarding.initiate, 不含 tag.manage |
| VS-8-S3 | finance 获取自身权限 | finance admin 已登录 | GET /admin/shop/permissions/me | 200, 含财务权限, 不含 onboarding.initiate |
| VS-8-S4 | 验证 ops 和 cs 都有 merchant.tag | 分别获取权限 | 检查 permissions | 两者均含 merchant.tag |

---

### M0 商家列表管理

---

### VS-9: 获取商家列表

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在至少 5 个商家记录, 状态包括 active, suspended, closed
- 至少 1 个商家关联到当前管理员 (account_manager_user_id)

**API**: `GET /admin/shop/merchants`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total` (int), `page` (int, 默认1), `page_size` (int, 默认20), `scope` (字符串)
- items 中每个商家含: tenant_id, tenant_name, status, plan_status, onboarding_status 等字段

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-9-B1 | page | 0 | 最小值违规 | 422 | page 必须 >= 1 |
| VS-9-B2 | page | -1 | 负值 | 422 | page 必须 >= 1 |
| VS-9-B3 | page_size | 0 | 最小值违规 | 422 | page_size 必须 >= 1 |
| VS-9-B4 | page_size | 101 | 最大值违规 | 422 | page_size 必须 <= 100 |
| VS-9-B5 | page_size | 100 | 边界最大值 | 200 | page_size = 100 正常返回 |
| VS-9-B6 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-9-B7 | Authorization | 商家 token | 无权限 | 403 | 商家无权访问 |
| VS-9-B8 | q | "" | 空搜索词 | 200 | 返回全部商家 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-9-S1 | 默认分页查询 | 有商家数据 | GET 无参数 | 200, page=1, page_size=20 |
| VS-9-S2 | 搜索商家名称 | 有匹配数据 | GET ?q=测试 | 200, items 中含名称匹配项 |
| VS-9-S3 | 按入驻状态筛选 | 有 reviewing 数据 | GET ?onboarding_status=reviewing | 200, items 全为 reviewing |
| VS-9-S4 | 按套餐状态筛选 | 有 expiring_soon 数据 | GET ?plan_status=expiring_soon | 200, items 全为 expiring_soon |
| VS-9-S5 | 验证 scope 字段 | 有数据 | 检查 scope | scope 反映当前管理员的可见范围 |

---

### VS-10: 获取商家列表-多条件筛选

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在多个不同状态、不同客户经理的商家
- 存在 include_not_onboarded=true 时可见的未入驻租户

**API**: `GET /admin/shop/merchants?q=测试&onboarding_status=active&plan_status=active&account_manager_user_id={user_id}&tab=my_clients&page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- items 中商家同时满足所有筛选条件
- total 为满足条件的总数

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-10-B1 | tab | "invalid_tab" | 无效值 | 422 | tab 值不在允许列表中 |
| VS-10-B2 | onboarding_status | "invalid" | 无效值 | 422 | onboarding_status 值无效 |
| VS-10-B3 | plan_status | "invalid" | 无效值 | 422 | plan_status 值无效 |
| VS-10-B4 | account_manager_user_id | "not-a-uuid" | 格式错误 | 422 | UUID 格式不正确 |
| VS-10-B5 | include_not_onboarded | "true" | 布尔字符串 | 200 | 正常返回含未入驻租户 |
| VS-10-B6 | page | 999999 | 超出范围 | 200 | 返回空 items, total 不变 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-10-S1 | tab=my_clients | 有关联商家 | GET ?tab=my_clients | 200, 仅返回当前管理员关联的商家 |
| VS-10-S2 | tab=expiring_soon | 有即将到期商家 | GET ?tab=expiring_soon | 200, 仅返回套餐即将到期的商家 |
| VS-10-S3 | tab=expired | 有已过期商家 | GET ?tab=expired | 200, 仅返回套餐已过期的商家 |
| VS-10-S4 | tab=suspended | 有暂停商家 | GET ?tab=suspended | 200, 仅返回暂停状态商家 |
| VS-10-S5 | tab=reviewing | 有待审入驻 | GET ?tab=reviewing | 200, 仅返回有待审申请的商家 |
| VS-10-S6 | include_not_onboarded=true | 有未入驻租户 | GET ?include_not_onboarded=true | 200, 含未入驻租户 |

---

### VS-11: 获取待续费商家列表

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 plan_status=expiring_soon 和 plan_status=expired 的商家

**API**: `GET /admin/shop/merchants/pending-renewals`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total` (int)
- items 中商家的 plan_status 为 expiring_soon 或 expired

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-11-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-11-B2 | Authorization | 商家 token | 无权限 | 403 | 商家无权访问 |
| VS-11-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-11-S1 | 获取待续费列表 | 有到期/已过期商家 | GET /pending-renewals | 200, 返回待续费商家 |
| VS-11-S2 | 无待续费商家 | 无到期/过期商家 | GET /pending-renewals | 200, items=[], total=0 |
| VS-11-S3 | 验证7天内到期高亮 | 有7天内到期商家 | 检查 items | 含 red_highlight 标记或等效字段 |

---

### VS-12: 获取商家列表-tab综合筛选

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在满足各 tab 条件的商家

**API**: `GET /admin/shop/merchants?tab=my_clients&page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- items 中仅包含当前管理员 (account_manager) 关联的商家

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-12-B1 | tab | "my_clients" | 有效值 | 200 | 正常返回 |
| VS-12-B2 | tab | "expiring_soon" | 有效值 | 200 | 返回即将到期商家 |
| VS-12-B3 | tab | "expired" | 有效值 | 200 | 返回已过期商家 |
| VS-12-B4 | tab | "suspended" | 有效值 | 200 | 返回暂停商家 |
| VS-12-B5 | tab | "reviewing" | 有效值 | 200 | 返回待审商家 |
| VS-12-B6 | tab | "unknown" | 无效值 | 422 | tab 值不在允许列表 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-12-S1 | my_clients 筛选 | 有关联商家 | GET ?tab=my_clients | 200, 仅当前管理员关联商家 |
| VS-12-S2 | expiring_soon 筛选 | 有即将到期商家 | GET ?tab=expiring_soon | 200, 仅到期 <=30 天商家 |
| VS-12-S3 | reviewing 筛选 | 有待审申请 | GET ?tab=reviewing | 200, 仅含 reviewing 状态 |
| VS-12-S4 | tab + page 组合 | 有数据 | GET ?tab=my_clients&page=2 | 200, 正确分页 |

---

### M0 入驻流程

---

### VS-13: 获取可入驻租户选项

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 admin_token
- 数据库中存在: 未入驻的活跃租户、已入驻租户、有待审申请的租户、不活跃租户

**API**: `GET /admin/shop/onboarding/tenant-options?q=&limit=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total` (int)
- items 中排除: 已入驻租户、有待审申请的租户、不活跃租户
- limit 默认 20, 范围 1-50

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-13-B1 | limit | 0 | 最小值违规 | 422 | limit 必须 >= 1 |
| VS-13-B2 | limit | 51 | 最大值违规 | 422 | limit 必须 <= 50 |
| VS-13-B3 | limit | 1 | 最小有效值 | 200 | 返回 1 条 |
| VS-13-B4 | limit | 50 | 最大有效值 | 200 | 返回最多 50 条 |
| VS-13-B5 | limit | 不传 | 默认值 | 200 | limit=20 |
| VS-13-B6 | q | "测试租户" | 搜索词 | 200 | 返回匹配的租户 |
| VS-13-B7 | Authorization | 商家 token | 无权限 | 403 | 无 onboarding 权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-13-S1 | 获取可入驻租户 | 有未入驻活跃租户 | GET /tenant-options | 200, 返回可入驻租户列表 |
| VS-13-S2 | 排除已入驻租户 | 有已入驻租户 | GET /tenant-options | 200, items 不含已入驻租户 |
| VS-13-S3 | 排除有待审申请租户 | 有待审申请租户 | GET /tenant-options | 200, items 不含待审租户 |
| VS-13-S4 | 排除不活跃租户 | 有不活跃租户 | GET /tenant-options | 200, items 不含不活跃租户 |
| VS-13-S5 | 搜索租户名称 | 有匹配数据 | GET ?q=关键词 | 200, 仅返回匹配项 |

---

### VS-14: 获取租户预填信息

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 tenant_id=已知UUID 的未入驻租户, 含 tenant_name, legal_name, display_name, unified_social_credit_code

**API**: `GET /admin/shop/onboarding/tenants/{tenant_id}/prefill`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `tenant_name`, `legal_name`, `display_name`, `unified_social_credit_code`
- 字段值与数据库中租户信息一致

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-14-B1 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID 格式不正确 |
| VS-14-B2 | tenant_id | 不存在的 UUID | 不存在 | 404 | 租户不存在 |
| VS-14-B3 | tenant_id | "" | 空值 | 404 | 路径参数为空 |
| VS-14-B4 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-14-B5 | Authorization | 商家 token | 无权限 | 403 | 无 onboarding 权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-14-S1 | 获取已知租户预填 | 租户存在且未入驻 | GET /prefill | 200, 返回预填信息 |
| VS-14-S2 | 租户不存在 | UUID 不匹配 | GET /prefill | 404, 租户不存在 |
| VS-14-S3 | 已入驻租户预填 | 租户已入驻 | GET /prefill | 200 或 409 (取决于业务逻辑) |
| VS-14-S4 | 验证预填字段完整性 | 租户有完整信息 | 检查 response | 含 tenant_name, legal_name, display_name, unified_social_credit_code |

---

### VS-15: 创建入驻申请

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 admin_token
- 数据库中存在未入驻的活跃租户 tenant_id (已知 UUID)
- 该租户无待审入驻申请, 未已入驻
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已知未入驻租户UUID",
  "entity_type": "enterprise",
  "legal_name": "测试科技有限公司",
  "display_name": "测试科技",
  "contact_name": "张三",
  "contact_mobile": "13800001111",
  "unified_social_credit_code": "91110000MA01ABC123",
  "legal_rep_name": "李四",
  "bank_account_info": {
    "bank_name": "中国银行",
    "account_number": "6228480012345678"
  },
  "qualification_files": {
    "business_license": "file_id_001"
  },
  "ocr_results": [],
  "remark": "测试入驻申请"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `tenant_id`, `entity_type`="enterprise", `legal_name`, `status`="pending"
- 数据库: onboarding_applications 新增 1 条 status=pending 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-15-B1 | tenant_id | "" | 空值 | 422 | 租户ID不能为空 |
| VS-15-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-15-B3 | tenant_id | 不存在的UUID | 不存在 | 404 | 租户不存在 |
| VS-15-B4 | entity_type | "" | 空值 | 422 | 主体类型不能为空 |
| VS-15-B5 | entity_type | "invalid_type" | 无效值 | 422 | 主体类型无效 |
| VS-15-B6 | contact_mobile | "1380000111" (10位) | 格式错误 | 422 | 手机号格式不对 |
| VS-15-B7 | contact_mobile | "23800001111" (非1开头) | 格式错误 | 422 | 手机号格式不对 |
| VS-15-B8 | contact_name | "" | 空值 | 422 | 联系人姓名不能为空 |
| VS-15-B9 | legal_name | "" | 空值 | 422 | 法定名称不能为空 |
| VS-15-B10 | contact_mobile | "" | 空值 | 422 | 手机号不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-15-S1 | 正常创建企业入驻 | 未入驻租户 | POST 创建 | 201, status=pending |
| VS-15-S2 | 正常创建个人入驻 | 未入驻租户, entity_type=personal, 含 id_no | POST 创建 | 201 |
| VS-15-S3 | 重复创建(同租户) | 已有待审申请 | POST 创建 | 409, 该租户已有待审入驻申请 |
| VS-15-S4 | 已入驻租户创建 | 租户已入驻 | POST 创建 | 409, 该租户已入驻 |
| VS-15-S5 | 个人主体缺id_no | entity_type=personal, 无 id_no | POST 创建 | 422, 个人主体需提供身份证号 |

---

### VS-16: 获取入驻申请列表

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在多个入驻申请, 含 pending, approved, rejected 状态, 不同 entity_type

**API**: `GET /admin/shop/onboarding/applications?status=pending&page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total` (int), `page`, `page_size`
- status=pending 时, items 中所有申请状态为 pending

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-16-B1 | status | "invalid" | 无效值 | 422 | status 值不在 pending/approved/rejected 中 |
| VS-16-B2 | page | 0 | 最小值违规 | 422 | page >= 1 |
| VS-16-B3 | page_size | 101 | 最大值违规 | 422 | page_size <= 100 |
| VS-16-B4 | entity_type | "invalid" | 无效值 | 422 | entity_type 值无效 |
| VS-16-B5 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-16-B6 | q | "" | 空搜索词 | 200 | 返回全部申请 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-16-S1 | 按状态筛选pending | 有pending申请 | GET ?status=pending | 200, 仅返回 pending |
| VS-16-S2 | 按状态筛选approved | 有approved申请 | GET ?status=approved | 200, 仅返回 approved |
| VS-16-S3 | 按主体类型筛选 | 有enterprise申请 | GET ?entity_type=enterprise | 200, 仅返回 enterprise |
| VS-16-S4 | 搜索关键词 | 有匹配数据 | GET ?q=测试 | 200, 返回匹配项 |
| VS-16-S5 | 无筛选条件 | 有数据 | GET 无参数 | 200, 返回全部 |

---

### VS-17: 获取入驻申请详情

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 application_id=已知UUID 的入驻申请, status=pending

**API**: `GET /admin/shop/onboarding/applications/{application_id}`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含完整申请详情: `id`, `tenant_id`, `entity_type`, `legal_name`, `display_name`, `contact_name`, `contact_mobile`, `status`, `bank_account_info`, `qualification_files`, `ocr_results`, `remark`, `created_at`
- 详情字段比列表更完整

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-17-B1 | application_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-17-B2 | application_id | 不存在的UUID | 不存在 | 404 | 入驻申请不存在 |
| VS-17-B3 | application_id | "" | 空值 | 404 | 路径参数为空 |
| VS-17-B4 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-17-B5 | Authorization | 商家 token | 无权限 | 403 | 无 onboarding 权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-17-S1 | 获取pending申请详情 | 申请存在 | GET /{id} | 200, 完整详情 |
| VS-17-S2 | 获取approved申请详情 | 已审批申请 | GET /{id} | 200, 含审批信息 |
| VS-17-S3 | 获取rejected申请详情 | 已驳回申请 | GET /{id} | 200, 含驳回原因 |
| VS-17-S4 | 不存在的申请 | UUID不匹配 | GET /{id} | 404, 入驻申请不存在 |

---

### VS-18: 审批入驻申请

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 admin_token
- 数据库中存在 application_id=已知UUID 的入驻申请, status=pending
- 对应租户未已入驻
- 套餐模板 code="PL_BASIC" 已存在且已上架

**API**: `POST /admin/shop/onboarding/applications/{application_id}/approve`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "plan_label": "PL_BASIC",
  "benefits_from": "2026-08-12",
  "benefits_until": "2027-08-12",
  "trial_days": 7,
  "store_quota": 1,
  "account_manager_user_id": "管理员UUID"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `merchant_id` 或 `tenant_id`, `subscription_id`, `status`="approved"
- 数据库: 申请状态变为 approved, 创建 merchant 记录, 创建 subscription 记录
- 商家状态: active

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-18-B1 | plan_label | "" | 空值 | 422 | 首开套餐必选 |
| VS-18-B2 | plan_label | null | 空值 | 422 | 首开套餐必选 |
| VS-18-B3 | benefits_from | "invalid-date" | 格式错误 | 422 | 日期格式不正确 |
| VS-18-B4 | trial_days | -1 | 负值 | 422 | trial_days >= 0 |
| VS-18-B5 | store_quota | 0 | 最小值 | 422 或 200 | store_quota 默认 1, 0 可能无效 |
| VS-18-B6 | application_id | 不存在的UUID | 不存在 | 404 | 申请不存在 |
| VS-18-B7 | account_manager_user_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-18-B8 | benefits_until | "2025-01-01" (早于from) | 逻辑错误 | 422 | 截止日期早于开始日期 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-18-S1 | 正常审批 | pending申请 | POST approve | 200, 创建商家+订阅 |
| VS-18-S2 | 审批已审批申请 | approved申请 | POST approve | 409, 仅待审申请可审核 |
| VS-18-S3 | 审批已驳回申请 | rejected申请 | POST approve | 409, 仅待审申请可审核 |
| VS-18-S4 | 审批已入驻租户 | 租户已有merchant | POST approve | 409, 该租户已入驻 |
| VS-18-S5 | 不传benefits_until | pending申请 | POST approve (无until) | 200, 使用默认到期日 |

---

### VS-19: 驳回入驻申请

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 admin_token
- 数据库中存在 application_id=已知UUID 的入驻申请, status=pending

**API**: `POST /admin/shop/onboarding/applications/{application_id}/reject`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reject_code": "material_incomplete",
  "reject_reason": "营业执照照片不清晰，请重新上传清晰的营业执照"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `id`, `status`="rejected", `reject_code`, `reject_reason`
- 数据库: 申请状态变为 rejected

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-19-B1 | reject_reason | "" | 空值 | 422 | 请填写驳回原因 |
| VS-19-B2 | reject_reason | "123" (3字) | 长度不足 | 422 | 驳回原因至少4字 |
| VS-19-B3 | reject_reason | "   ab   " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VS-19-B4 | reject_reason | "材料不完整" (5字) | 最小有效值 | 200 | 正常驳回 |
| VS-19-B5 | reject_reason | null | 空值 | 422 | 请填写驳回原因 |
| VS-19-B6 | reject_code | 不传 | 默认值 | 200 | 默认 "other" |
| VS-19-B7 | application_id | 不存在的UUID | 不存在 | 404 | 申请不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-19-S1 | 正常驳回 | pending申请 | POST reject | 200, status=rejected |
| VS-19-S2 | 驳回已审批申请 | approved申请 | POST reject | 409, 仅待审申请可审核 |
| VS-19-S3 | 驳回已驳回申请 | rejected申请 | POST reject | 409, 仅待审申请可审核 |
| VS-19-S4 | 驳回后重新提交 | rejected申请 | POST 新申请 | 201, 新 pending 申请 |
| VS-19-S5 | 默认reject_code | 不传reject_code | POST reject | 200, reject_code="other" |

---

### M0 OCR 识别

---

### VS-20: OCR 识别-管理员端

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 环境变量: WECHAT_PAY_MODE=stub (OCR 返回 stub 数据)

**API**: `POST /admin/shop/onboarding/ocr`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "doc_type": "business_license",
  "file_id": "file_ocr_001"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `doc_type`="business_license", `file_id`, `fields` (dict), `confidence` (float, 如 0.92), `stub`=true
- fields 包含识别到的字段 (如 company_name, credit_code 等)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-20-B1 | doc_type | "" | 空值 | 422 | 证件类型不能为空 |
| VS-20-B2 | doc_type | "invalid_doc" | 无效值 | 422 | 证件类型无效 |
| VS-20-B3 | doc_type | "passport" | 不支持类型 | 422 | 证件类型无效 |
| VS-20-B4 | doc_type | "id_card_front" | 有效值 | 200 | 身份证正面识别 |
| VS-20-B5 | doc_type | "id_card_back" | 有效值 | 200 | 身份证背面识别 |
| VS-20-B6 | doc_type | "business_license" | 有效值 | 200 | 营业执照识别 |
| VS-20-B7 | file_id | 不传 | 可选字段 | 200 | file_id 可选 |
| VS-20-B8 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-20-S1 | 营业执照识别 | stub模式 | POST ocr(business_license) | 200, stub=true, fields非空 |
| VS-20-S2 | 身份证正面识别 | stub模式 | POST ocr(id_card_front) | 200, stub=true, fields含姓名等 |
| VS-20-S3 | 身份证背面识别 | stub模式 | POST ocr(id_card_back) | 200, stub=true, fields含有效期等 |
| VS-20-S4 | 无file_id识别 | stub模式 | POST ocr(无file_id) | 200, stub=true |
| VS-20-S5 | 验证confidence值 | 已返回结果 | 检查 confidence | 为 0-1 之间的浮点数 |

---

### VS-21: OCR 识别-商家端

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /shop/onboarding/ocr`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "doc_type": "id_card_front",
  "file_id": "file_ocr_002"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `doc_type`, `file_id`, `fields` (dict), `confidence` (float), `stub`=true
- 与管理员端返回结构一致

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-21-B1 | doc_type | "" | 空值 | 422 | 证件类型不能为空 |
| VS-21-B2 | doc_type | "invalid_doc" | 无效值 | 422 | 证件类型无效 |
| VS-21-B3 | doc_type | "id_card_front" | 有效值 | 200 | 正常识别 |
| VS-21-B4 | doc_type | "business_license" | 有效值 | 200 | 正常识别 |
| VS-21-B5 | Authorization | 管理员 token | 角色不匹配 | 403 | 无 shop 权限 |
| VS-21-B6 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-21-S1 | 商家端身份证识别 | merchant已登录 | POST ocr(id_card_front) | 200, stub=true |
| VS-21-S2 | 商家端营业执照识别 | merchant已登录 | POST ocr(business_license) | 200, stub=true |
| VS-21-S3 | 管理员不能访问商家端 | admin已登录 | POST /shop/onboarding/ocr | 403 |
| VS-21-S4 | 验证返回一致性 | 同时测试两端 | 对比 response 结构 | 结构一致, 均含 stub=true |

---

### M0 服务日志与续费申请

---

### VS-22: 添加服务日志-跟进备注

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 tenant_id=已知UUID 的 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/notes`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "type": "call",
  "content": "电话联系客户确认续费意向，客户表示需要考虑一周后回复",
  "follow_up_at": "2026-08-19T10:00:00Z",
  "payload_json": {
    "duration": 300,
    "outcome": "pending"
  }
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `type`="call", `content`, `follow_up_at`, `tenant_id`
- 数据库: service_logs 新增 1 条记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-22-B1 | content | "" | 空值 | 422 | 请填写跟进内容 |
| VS-22-B2 | content | "123456789" (9字) | 长度不足 | 422 | 跟进内容至少10字 |
| VS-22-B3 | content | "  1234567  " (strip后7字) | strip后不足 | 422 | strip后至少10字 |
| VS-22-B4 | content | "1234567890" (10字) | 最小有效值 | 201 | 正常创建 |
| VS-22-B5 | type | "invalid_type" | 无效值 | 422 | 无效的跟进类型 |
| VS-22-B6 | type | 不传 | 默认值 | 201 | 默认 type="call" |
| VS-22-B7 | type | "note" | 有效值 | 201 | 备注类型 |
| VS-22-B8 | type | "visit" | 有效值 | 201 | 拜访类型 |
| VS-22-B9 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VS-22-B10 | follow_up_at | "invalid-date" | 格式错误 | 422 | 日期时间格式不正确 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-22-S1 | 正常添加电话跟进 | 商家active | POST note(type=call) | 201 |
| VS-22-S2 | 默认类型 | 不传type | POST note(无type) | 201, type=call |
| VS-22-S3 | 微信跟进 | 商家active | POST note(type=wechat) | 201 |
| VS-22-S4 | 培训跟进 | 商家active | POST note(type=training) | 201 |
| VS-22-S5 | 商家不存在 | UUID不匹配 | POST note | 404, 商家不存在 |

---

### VS-23: 创建续费申请

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 tenant_id=已知UUID 的 active 状态商家
- 该商家套餐状态为 expiring_soon (即将到期)
- 该商家无待处理续费申请
- 套餐模板 code="PL_BASIC" 已存在且已上架

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "purchase_mode": "renew_same",
  "target_plan": "PL_BASIC",
  "quoted_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "customer_confirmed": true,
  "content": "客户确认续费基础版套餐一年"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `purchase_mode`="renew_same", `target_plan`, `status`="pending", `tenant_id`
- 数据库: service_logs 新增续费申请记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-23-B1 | purchase_mode | "" | 空值 | 422 | 申请类型不能为空 |
| VS-23-B2 | purchase_mode | "invalid_mode" | 无效值 | 422 | 申请类型无效 |
| VS-23-B3 | target_plan | "" | 空值 | 422 | 目标套餐不能为空 |
| VS-23-B4 | quoted_amount_cents | -1 | 负值 | 422 | 金额必须 >= 0 |
| VS-23-B5 | catalog_price_cents | -1 | 负值 | 422 | 金额必须 >= 0 |
| VS-23-B6 | customer_confirmed | false | 未确认 | 422 | 请先与客户确认续费意向 |
| VS-23-B7 | content | "" | 空值 | 422 | 请填写续费说明 |
| VS-23-B8 | content | "abc" (3字) | 长度不足 | 422 | 续费说明至少4字 |
| VS-23-B9 | content | "abcd" (4字) | 最小有效值 | 201 | 正常创建 |
| VS-23-B10 | quoted_amount_cents | 0 | 零值 | 201 | 金额为0有效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-23-S1 | 正常创建续费申请 | active+expiring_soon | POST renewal | 201, status=pending |
| VS-23-S2 | 非active商家续费 | suspended商家 | POST renewal | 409, 仅正常营业商家可申请续费 |
| VS-23-S3 | 套餐未到期续费 | active+plan_status=active | POST renewal | 409, 当前套餐未到期 |
| VS-23-S4 | 已有待处理续费 | 已有pending续费 | POST renewal | 409, 已有待处理续费申请 |
| VS-23-S5 | 叠加购买续费 | active+expiring | POST renewal(mode=stack) | 201 |
| VS-23-S6 | 替换套餐续费 | active+expiring | POST renewal(mode=replace) | 201 |

---

### VS-24: 取消续费申请

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 service_log_id=已知UUID 的续费申请, status=pending
- 该续费申请关联到 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{service_log_id}/cancel?note=客户取消续费`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**: 无 (note 在 query 参数中)

**期望结果**:
- HTTP Status: 200
- Response Body 含: `id`, `status`="cancelled"
- 数据库: 续费申请状态变为 cancelled

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-24-B1 | service_log_id | 不存在的UUID | 不存在 | 404 | 续费申请不存在 |
| VS-24-B2 | service_log_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-24-B3 | note | 不传 | 可选 | 200 | note 可选 |
| VS-24-B4 | note | "客户取消" | 有效值 | 200 | 正常取消 |
| VS-24-B5 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VS-24-B6 | Authorization | 无订阅管理权限的角色 | 无权限 | 403 | 无订阅管理权限 |
| VS-24-B7 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-24-S1 | 正常取消pending申请 | status=pending | POST cancel | 200, status=cancelled |
| VS-24-S2 | 取消processing申请 | status=processing | POST cancel | 200, status=cancelled |
| VS-24-S3 | 取消已结案申请 | status=approved | POST cancel | 409, 申请已结案 |
| VS-24-S4 | 取消已取消申请 | status=cancelled | POST cancel | 409, 申请已结案 |
| VS-24-S5 | 无权限用户取消 | 无订阅管理权限 | POST cancel | 403, 无订阅管理权限 |

---

### M0 商家状态变更

---

### VS-25: 商家状态-暂停

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 tenant_id=已知UUID 的 active 状态商家
- 该商家有至少 1 个 active 状态的店铺

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家违规操作需要暂停服务进行整改"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `status`="suspended"
- 数据库: merchant.status 变为 suspended
- 副作用: 该商家所有店铺状态变为 paused

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-25-B1 | reason_text | "" | 空值 | 422 | 暂停原因不能为空 |
| VS-25-B2 | reason_text | "123" (3字) | 长度不足 | 422 | 暂停原因至少4字 |
| VS-25-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VS-25-B4 | reason_text | "违规操作" (4字) | 最小有效值 | 200 | 正常暂停 |
| VS-25-B5 | reason_text | 不传 | 缺失 | 422 | 暂停原因不能为空 |
| VS-25-B6 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VS-25-B7 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-25-B8 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-25-S1 | 正常暂停active商家 | status=active | POST suspend | 200, status=suspended |
| VS-25-S2 | 暂停已暂停商家 | status=suspended | POST suspend | 409, 商家已暂停 |
| VS-25-S3 | 暂停已关闭商家 | status=closed | POST suspend | 409, 商家已关闭 |
| VS-25-S4 | 验证店铺副作用 | 有active店铺 | POST suspend后检查店铺 | 店铺状态变为paused |
| VS-25-S5 | 暂停后恢复 | suspended | POST resume | 200, status=active |

---

### VS-26: 商家状态-恢复

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 tenant_id=已知UUID 的 suspended 状态商家
- 该商家暂停前有 active 店铺, 暂停后变为 paused

**API**: `POST /admin/shop/merchants/{tenant_id}/resume`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `status`="active"
- 数据库: merchant.status 变为 active
- 注意: 店铺状态不自动恢复, 需手动操作

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-26-B1 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VS-26-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-26-B3 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VS-26-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-26-S1 | 正常恢复suspended商家 | status=suspended | POST resume | 200, status=active |
| VS-26-S2 | 恢复active商家 | status=active | POST resume | 409, 商家未暂停 |
| VS-26-S3 | 恢复closed商家 | status=closed | POST resume | 409, 商家已关闭 |
| VS-26-S4 | 验证店铺不自动恢复 | suspended+paused店铺 | POST resume后检查店铺 | 店铺仍为paused, 不自动恢复 |
| VS-26-S5 | 恢复后再次暂停 | active (恢复后) | POST suspend | 200, status=suspended |

---

### VS-27: 商家状态-关闭

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 tenant_id=已知UUID 的 active 状态商家
- 该商家有 active 店铺和 pending 状态的续费申请

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家主动申请关闭账号，不再继续经营",
  "ack_irreversible": true
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `status`="closed"
- 数据库: merchant.status 变为 closed (终态)
- 副作用: 所有店铺变为 paused, pending/processing 续费申请变为 cancelled, 租户永久阻断重新入驻

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-27-B1 | reason_text | "" | 空值 | 422 | 关闭原因不能为空 |
| VS-27-B2 | reason_text | "123" (3字) | 长度不足 | 422 | 关闭原因至少4字 |
| VS-27-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VS-27-B4 | reason_text | "商家关店" (4字) | 最小有效值 | 200 | 正常关闭 |
| VS-27-B5 | ack_irreversible | false | 未确认 | 422 | 请确认操作不可逆 |
| VS-27-B6 | ack_irreversible | 不传 | 缺失 | 422 | 请确认操作不可逆 |
| VS-27-B7 | ack_irreversible | true | 已确认 | 200 | 正常关闭 |
| VS-27-B8 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VS-27-B9 | reason_text | 不传 | 缺失 | 422 | 关闭原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-27-S1 | 正常关闭active商家 | status=active | POST close | 200, status=closed |
| VS-27-S2 | 关闭suspended商家 | status=suspended | POST close | 200, status=closed |
| VS-27-S3 | 关闭已关闭商家 | status=closed | POST close | 409, 商家已关闭 |
| VS-27-S4 | 关闭后不可重开 | status=closed | POST resume/suspend | 409, 不可逆操作 |
| VS-27-S5 | 关闭后不可重新入驻 | status=closed | POST onboarding | 409, 租户永久阻断 |
| VS-27-S6 | 验证店铺副作用 | 有active店铺 | POST close后检查 | 店铺全部变为paused |
| VS-27-S7 | 验证续费申请副作用 | 有pending续费 | POST close后检查 | 续费申请变为cancelled |

---

### M0 权限隔离与边界

---

### VS-28: 权限验证-管家(cs)有 onboarding.initiate, 运营(ops)无

**前置条件**:
- platform_shop_cs 角色管理员已登录, 获取 cs_token
- platform_shop_ops 角色管理员已登录, 获取 ops_token
- cs 角色权限包含 onboarding.initiate
- ops 角色权限不包含 onboarding.initiate (根据 PRD: 管家cs has onboarding.initiate; 运营ops does NOT)

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {cs_token 或 ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已知未入驻租户UUID",
  "entity_type": "enterprise",
  "legal_name": "测试科技有限公司",
  "contact_name": "张三",
  "contact_mobile": "13800001111",
  "unified_social_credit_code": "91110000MA01ABC123",
  "legal_rep_name": "李四"
}
```

**期望结果**:
- cs_token: HTTP Status 201 (有 onboarding.initiate 权限)
- ops_token: HTTP Status 403 (无 onboarding.initiate 权限)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-28-B1 | token | cs_token | 有权限 | 201 | 管家有onboarding.initiate |
| VS-28-B2 | token | ops_token | 无权限 | 403 | 运营无onboarding.initiate |
| VS-28-B3 | token | finance_token | 无权限 | 403 | 财务无onboarding.initiate |
| VS-28-B4 | token | merchant_token | 无权限 | 403 | 商家无onboarding权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-28-S1 | 管家发起入驻 | cs已登录 | POST application | 201, 创建成功 |
| VS-28-S2 | 运营发起入驻 | ops已登录 | POST application | 403, 无onboarding.initiate |
| VS-28-S3 | 验证cs权限列表 | cs已登录 | GET /admin/shop/permissions/me | permissions 含 onboarding.initiate |
| VS-28-S4 | 验证ops权限列表 | ops已登录 | GET /admin/shop/permissions/me | permissions 不含 onboarding.initiate |
| VS-28-S5 | 财务发起入驻 | finance已登录 | POST application | 403, 无onboarding.initiate |

---

### VS-29: 权限验证-运营(ops)有 tag.manage, 管家(cs)无

**前置条件**:
- platform_shop_ops 角色管理员已登录, 获取 ops_token
- platform_shop_cs 角色管理员已登录, 获取 cs_token
- ops 角色权限包含 tag.manage
- cs 角色权限不包含 tag.manage
- 两者都有 merchant.tag 权限

**API**: `POST /admin/shop/tags` (创建新标签名)
**Headers**: `Authorization: Bearer {ops_token 或 cs_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "name": "VIP客户"
}
```

**期望结果**:
- ops_token: HTTP Status 201 (有 tag.manage 权限)
- cs_token: HTTP Status 403 (无 tag.manage 权限)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-29-B1 | token | ops_token | 有权限 | 201 | 运营有tag.manage |
| VS-29-B2 | token | cs_token | 无权限 | 403 | 管家无tag.manage |
| VS-29-B3 | token | finance_token | 无权限 | 403 | 财务无tag.manage |
| VS-29-B4 | token | merchant_token | 无权限 | 403 | 商家无tag.manage |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-29-S1 | 运营创建标签 | ops已登录 | POST tag | 201, 创建成功 |
| VS-29-S2 | 管家创建标签 | cs已登录 | POST tag | 403, 无tag.manage |
| VS-29-S3 | 验证ops权限 | ops已登录 | GET /admin/shop/permissions/me | 含 tag.manage |
| VS-29-S4 | 验证cs无tag.manage | cs已登录 | GET /admin/shop/permissions/me | 不含 tag.manage |
| VS-29-S5 | 验证两者都有merchant.tag | 分别获取权限 | 检查 permissions | 两者均含 merchant.tag |

---

### VS-30: 跨租户隔离测试

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 商家用户 A (13900000099) 关联 tenant_A, 商家用户 B 关联 tenant_B
- tenant_A 有服务日志, tenant_B 有服务日志
- 两个租户互不关联

**API**: `GET /admin/shop/merchants/{tenant_A_id}/service-logs/notes` (商家A的token)
**Headers**: `Authorization: Bearer {merchant_A_token}`

**请求体**: 无

**期望结果**:
- 商家A的token只能访问 tenant_A 的数据
- 商家A的token访问 tenant_B 的数据返回 403

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-30-B1 | tenant_id | tenant_A (自己的) | 正常访问 | 200 | 返回自己的数据 |
| VS-30-B2 | tenant_id | tenant_B (他人的) | 跨租户 | 403 | 无权访问其他租户 |
| VS-30-B3 | tenant_id | 不存在的UUID | 不存在 | 404 | 租户不存在 |
| VS-30-B4 | Authorization | merchant_B_token 访问 tenant_A | 跨租户 | 403 | 无权访问 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-30-S1 | 商家A访问自己租户数据 | tenant_A已登录 | GET tenant_A/service-logs | 200, 返回A的数据 |
| VS-30-S2 | 商家A访问B租户数据 | tenant_A已登录 | GET tenant_B/service-logs | 403, 跨租户禁止 |
| VS-30-S3 | 管理员访问任意租户 | admin已登录 | GET tenant_A 和 tenant_B | 200, 管理员可跨租户 |
| VS-30-S4 | 商家A入驻申请隔离 | tenant_A已登录 | GET tenant_B/onboarding | 403 |
| VS-30-S5 | 跨租户标签隔离 | tenant_A有标签 | 检查tenant_B标签列表 | tenant_B看不到A的标签 |

---

### M0 新增测试用例

---

### VS-1-N: 无效手机号格式登录

**前置条件**:
- 无需登录
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /auth/login`
**Headers**: `Content-Type: application/json`

**请求体**:
```json
{
  "phone": "abc12345678",
  "password": "admin123456"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 手机号格式不正确

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-1-N-B1 | phone | "abc12345678" | 非数字 | 422 | 手机号格式不正确 |
| VS-1-N-B2 | phone | "12345" | 过短 | 422 | 手机号格式不正确 |
| VS-1-N-B3 | phone | "13800000000@example.com" | 非手机号 | 422 | 手机号格式不正确 |
| VS-1-N-B4 | phone | " 13800000000 " | 含空格 | 422 或 200 | 取决于是否trim |
| VS-1-N-B5 | phone | null | null值 | 422 | 字段不能为null |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-1-N-S1 | 字母手机号 | 无 | POST login(字母) | 422 |
| VS-1-N-S2 | 过短手机号 | 无 | POST login(5位) | 422 |
| VS-1-N-S3 | null手机号 | 无 | POST login(null) | 422 |
| VS-1-N-S4 | 缺少phone字段 | 无 | POST login(无phone) | 422 |

---

### VS-2-N: 错误密码登录

**前置条件**:
- 数据库中存在平台管理员: 13800000000 / admin123456
- 无需登录

**API**: `POST /auth/login`
**Headers**: `Content-Type: application/json`

**请求体**:
```json
{
  "phone": "13800000000",
  "password": "WrongPassword123"
}
```

**期望结果**:
- HTTP Status: 401
- Response Body 含错误信息: 用户不存在或密码错误

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-2-N-B1 | password | "admin12345" (少1位) | 接近密码 | 401 | 密码错误 |
| VS-2-N-B2 | password | "admin1234567" (多1位) | 接近密码 | 401 | 密码错误 |
| VS-2-N-B3 | password | "ADMIN123456" (大写) | 大小写 | 401 | 密码错误 |
| VS-2-N-B4 | password | "admin123456 " (尾空格) | 含空格 | 401 | 密码错误 |
| VS-2-N-B5 | password | null | null值 | 422 | 密码不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-2-N-S1 | 完全错误密码 | 用户存在 | POST login(错误密码) | 401 |
| VS-2-N-S2 | 大小写错误 | 用户存在 | POST login(大写密码) | 401 |
| VS-2-N-S3 | 空密码 | 用户存在 | POST login(空密码) | 422 |
| VS-2-N-S4 | 正确密码登录 | 用户存在 | POST login(正确密码) | 200 |

---

### VS-3-N: 未授权访问管理员接口

**前置条件**:
- 无需登录
- 不携带任何 Authorization Header

**API**: `GET /admin/shop/merchants`
**Headers**: 无 Authorization

**请求体**: 无

**期望结果**:
- HTTP Status: 401
- Response Body 含错误信息: 未提供认证令牌

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-3-N-B1 | Authorization | 不传 | 缺失 | 401 | 未提供认证令牌 |
| VS-3-N-B2 | Authorization | "Bearer " | 空token | 401 | 令牌为空 |
| VS-3-N-B3 | Authorization | "Bearer null" | 无效 | 401 | 令牌无效 |
| VS-3-N-B4 | Authorization | "Bearer expired_token" | 过期 | 401 | 令牌已过期 |
| VS-3-N-B5 | Authorization | "InvalidFormat token" | 格式错误 | 401 | 认证格式不正确 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-3-N-S1 | 无token访问admin | 无登录 | GET /admin/shop/merchants | 401 |
| VS-3-N-S2 | 商家token访问admin | merchant已登录 | GET /admin/shop/merchants | 403 |
| VS-3-N-S3 | 无token访问shop | 无登录 | GET /shop/permissions/me | 401 |
| VS-3-N-S4 | 过期token访问 | token已过期 | GET /admin/shop/merchants | 401 |

---

### VS-4-N: 获取租户预填-租户不存在

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- tenant_id 为随机不存在的 UUID

**API**: `GET /admin/shop/onboarding/tenants/00000000-0000-0000-0000-000000000000/prefill`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 404
- Response Body 含错误信息: 租户不存在

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-4-N-B1 | tenant_id | 随机不存在UUID | 不存在 | 404 | 租户不存在 |
| VS-4-N-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-4-N-B3 | tenant_id | "00000000-0000-0000-0000-000000000000" | 全零UUID | 404 | 租户不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-4-N-S1 | 不存在的租户 | 无匹配数据 | GET /prefill | 404 |
| VS-4-N-S2 | 格式错误UUID | 无 | GET /not-a-uuid/prefill | 422 |
| VS-4-N-S3 | 存在的租户 | 租户存在 | GET /valid_uuid/prefill | 200 |

---

### VS-5-N: 创建入驻申请-个人主体缺 id_no

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在未入驻的活跃租户

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已知未入驻租户UUID",
  "entity_type": "personal",
  "legal_name": "张三个人",
  "contact_name": "张三",
  "contact_mobile": "13800001111"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 个人主体需提供身份证号

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-5-N-B1 | id_no | 不传(personal) | 缺失 | 422 | 个人缺id_no |
| VS-5-N-B2 | id_no | "" (personal) | 空值 | 422 | 个人缺id_no |
| VS-5-N-B3 | id_no | "110101199001011234" (personal) | 有效值 | 201 | 正常创建 |
| VS-5-N-B4 | id_no | 不传(enterprise) | 非个人可选 | 201 | 企业不需要id_no |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-5-N-S1 | 个人缺id_no | 未入驻租户 | POST(personal,无id_no) | 422 |
| VS-5-N-S2 | 个人有id_no | 未入驻租户 | POST(personal,有id_no) | 201 |
| VS-5-N-S3 | 企业不需要id_no | 未入驻租户 | POST(enterprise,无id_no) | 201 |

---

### VS-6-N: 创建入驻申请-非个人缺 unified_social_credit_code

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在未入驻的活跃租户

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已知未入驻租户UUID",
  "entity_type": "enterprise",
  "legal_name": "测试科技有限公司",
  "contact_name": "张三",
  "contact_mobile": "13800001111",
  "legal_rep_name": "李四"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 非个人主体需提供统一社会信用代码

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-6-N-B1 | unified_social_credit_code | 不传(enterprise) | 缺失 | 422 | 非个人缺unified_social_credit_code |
| VS-6-N-B2 | unified_social_credit_code | "" (enterprise) | 空值 | 422 | 非个人缺unified_social_credit_code |
| VS-6-N-B3 | unified_social_credit_code | "91110000MA01ABC123" (enterprise) | 有效值 | 201 | 正常创建 |
| VS-6-N-B4 | unified_social_credit_code | 不传(personal) | 个人可选 | 201 | 个人不需要 |
| VS-6-N-B5 | unified_social_credit_code | 不传(individual_business) | 个体工商户 | 422 | 非个人缺unified_social_credit_code |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-6-N-S1 | 企业缺信用代码 | 未入驻租户 | POST(enterprise,无code) | 422 |
| VS-6-N-S2 | 企业有信用代码 | 未入驻租户 | POST(enterprise,有code) | 201 |
| VS-6-N-S3 | 个体工商户缺信用代码 | 未入驻租户 | POST(individual_business,无code) | 422 |
| VS-6-N-S4 | 个人不需要信用代码 | 未入驻租户 | POST(personal,无code) | 201 |

---

### VS-7-N: 创建入驻申请-非个人缺 legal_rep_name

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在未入驻的活跃租户

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已知未入驻租户UUID",
  "entity_type": "enterprise",
  "legal_name": "测试科技有限公司",
  "contact_name": "张三",
  "contact_mobile": "13800001111",
  "unified_social_credit_code": "91110000MA01ABC123"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 非个人主体需提供法定代表人姓名

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-7-N-B1 | legal_rep_name | 不传(enterprise) | 缺失 | 422 | 非个人缺legal_rep_name |
| VS-7-N-B2 | legal_rep_name | "" (enterprise) | 空值 | 422 | 非个人缺legal_rep_name |
| VS-7-N-B3 | legal_rep_name | "李四" (enterprise) | 有效值 | 201 | 正常创建 |
| VS-7-N-B4 | legal_rep_name | 不传(personal) | 个人可选 | 201 | 个人不需要 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-7-N-S1 | 企业缺法人姓名 | 未入驻租户 | POST(enterprise,无legal_rep) | 422 |
| VS-7-N-S2 | 企业有法人姓名 | 未入驻租户 | POST(enterprise,有legal_rep) | 201 |
| VS-7-N-S3 | 个人不需要法人姓名 | 未入驻租户 | POST(personal,无legal_rep) | 201 |

---

### VS-8-N: 创建入驻申请-租户不存在

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- tenant_id 为不存在的 UUID

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000000",
  "entity_type": "enterprise",
  "legal_name": "测试科技有限公司",
  "contact_name": "张三",
  "contact_mobile": "13800001111",
  "unified_social_credit_code": "91110000MA01ABC123",
  "legal_rep_name": "李四"
}
```

**期望结果**:
- HTTP Status: 404
- Response Body 含错误信息: 租户不存在

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-8-N-B1 | tenant_id | 不存在UUID | 不存在 | 404 | 租户不存在 |
| VS-8-N-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VS-8-N-B3 | tenant_id | "" | 空值 | 422 | 租户ID不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-8-N-S1 | 不存在的租户 | UUID不匹配 | POST application | 404 |
| VS-8-N-S2 | 格式错误UUID | 无 | POST application | 422 |
| VS-8-N-S3 | 存在的租户 | 租户存在 | POST application | 201 |

---

### VS-9-N: 创建入驻申请-已入驻租户

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在已入驻的租户 (merchant.status=active)

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已入驻租户UUID",
  "entity_type": "enterprise",
  "legal_name": "已入驻公司",
  "contact_name": "王五",
  "contact_mobile": "13800002222",
  "unified_social_credit_code": "91110000MA01DEF456",
  "legal_rep_name": "赵六"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 该租户已入驻

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-9-N-B1 | tenant_id | active租户 | 已入驻 | 409 | 该租户已入驻 |
| VS-9-N-B2 | tenant_id | suspended租户 | 已入驻 | 409 | 该租户已入驻 |
| VS-9-N-B3 | tenant_id | closed租户 | 永久阻断 | 409 | 该租户已入驻/永久阻断 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-9-N-S1 | active租户再入驻 | status=active | POST application | 409, 该租户已入驻 |
| VS-9-N-S2 | closed租户再入驻 | status=closed | POST application | 409, 永久阻断 |
| VS-9-N-S3 | 未入驻租户入驻 | 无merchant | POST application | 201, 创建成功 |

---

### VS-10-N: 创建入驻申请-已有待审申请

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在租户已有 status=pending 的入驻申请

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "有待审申请的租户UUID",
  "entity_type": "enterprise",
  "legal_name": "测试公司",
  "contact_name": "张三",
  "contact_mobile": "13800003333",
  "unified_social_credit_code": "91110000MA01GHI789",
  "legal_rep_name": "李四"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 该租户已有待审入驻申请

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-10-N-B1 | tenant_id | 有pending申请的租户 | 重复申请 | 409 | 已有待审申请 |
| VS-10-N-B2 | tenant_id | 有approved申请的租户 | 已入驻 | 409 | 该租户已入驻 |
| VS-10-N-B3 | tenant_id | 有rejected申请的租户 | 可重新申请 | 201 | 驳回后可重新提交 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-10-N-S1 | 有pending申请再创建 | 有pending | POST application | 409, 已有待审申请 |
| VS-10-N-S2 | rejected后重新创建 | 有rejected | POST application | 201, 新pending申请 |
| VS-10-N-S3 | 无申请的租户创建 | 无申请 | POST application | 201, 创建成功 |

---

### VS-11-N: 审批申请-首开套餐必选

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 status=pending 的入驻申请

**API**: `POST /admin/shop/onboarding/applications/{application_id}/approve`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "plan_label": "",
  "benefits_from": "2026-08-12",
  "store_quota": 1
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 首开套餐必选

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-11-N-B1 | plan_label | "" | 空值 | 422 | 首开套餐必选 |
| VS-11-N-B2 | plan_label | null | 空值 | 422 | 首开套餐必选 |
| VS-11-N-B3 | plan_label | 不传 | 缺失 | 422 | 首开套餐必选 |
| VS-11-N-B4 | plan_label | "   " | 空白 | 422 | 首开套餐必选 |
| VS-11-N-B5 | plan_label | "PL_BASIC" | 有效值 | 200 | 正常审批 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-11-N-S1 | 空套餐审批 | pending申请 | POST approve(plan_label="") | 422 |
| VS-11-N-S2 | null套餐审批 | pending申请 | POST approve(plan_label=null) | 422 |
| VS-11-N-S3 | 有效套餐审批 | pending申请 | POST approve(plan_label="PL_BASIC") | 200 |

---

### VS-12-N: 驳回申请-原因不足4字

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 status=pending 的入驻申请

**API**: `POST /admin/shop/onboarding/applications/{application_id}/reject`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reject_code": "other",
  "reject_reason": "不通过"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 请填写驳回原因（至少4字）

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-12-N-B1 | reject_reason | "" | 空值 | 422 | 请填写驳回原因 |
| VS-12-N-B2 | reject_reason | "123" (3字) | 长度不足 | 422 | 至少4字 |
| VS-12-N-B3 | reject_reason | "  12  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VS-12-N-B4 | reject_reason | "  1234  " (strip后4字) | strip后有效 | 200 | 正常驳回 |
| VS-12-N-B5 | reject_reason | "材料不齐全请补充" (8字) | 有效值 | 200 | 正常驳回 |
| VS-12-N-B6 | reject_reason | null | null值 | 422 | 请填写驳回原因 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-12-N-S1 | 3字原因 | pending申请 | POST reject(3字) | 422 |
| VS-12-N-S2 | 4字原因 | pending申请 | POST reject(4字) | 200 |
| VS-12-N-S3 | 空原因 | pending申请 | POST reject("") | 422 |
| VS-12-N-S4 | strip后不足 | pending申请 | POST reject("  ab  ") | 422 |

---

### VS-13-N: OCR-无效证件类型

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /admin/shop/onboarding/ocr`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "doc_type": "passport",
  "file_id": "file_001"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 证件类型无效

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-13-N-B1 | doc_type | "passport" | 不支持 | 422 | 证件类型无效 |
| VS-13-N-B2 | doc_type | "driver_license" | 不支持 | 422 | 证件类型无效 |
| VS-13-N-B3 | doc_type | "" | 空值 | 422 | 证件类型无效 |
| VS-13-N-B4 | doc_type | "id_card_front" | 有效 | 200 | 正常识别 |
| VS-13-N-B5 | doc_type | "id_card_back" | 有效 | 200 | 正常识别 |
| VS-13-N-B6 | doc_type | "business_license" | 有效 | 200 | 正常识别 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-13-N-S1 | 护照类型 | stub模式 | POST ocr(passport) | 422 |
| VS-13-N-S2 | 驾照类型 | stub模式 | POST ocr(driver_license) | 422 |
| VS-13-N-S3 | 空类型 | stub模式 | POST ocr("") | 422 |
| VS-13-N-S4 | 有效身份证正面 | stub模式 | POST ocr(id_card_front) | 200 |

---

### VS-14-N: 服务日志-内容不足10字

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/notes`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "type": "call",
  "content": "联系客户"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 请填写跟进内容（至少10字）

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-14-N-B1 | content | "" | 空值 | 422 | 请填写跟进内容 |
| VS-14-N-B2 | content | "123456789" (9字) | 长度不足 | 422 | 至少10字 |
| VS-14-N-B3 | content | "  1234567  " (strip后7字) | strip后不足 | 422 | strip后至少10字 |
| VS-14-N-B4 | content | "1234567890" (10字) | 最小有效 | 201 | 正常创建 |
| VS-14-N-B5 | content | "  1234567890  " (strip后10字) | strip后有效 | 201 | 正常创建 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-14-N-S1 | 4字内容 | active商家 | POST note(4字) | 422 |
| VS-14-N-S2 | 9字内容 | active商家 | POST note(9字) | 422 |
| VS-14-N-S3 | 10字内容 | active商家 | POST note(10字) | 201 |
| VS-14-N-S4 | strip后不足 | active商家 | POST note("  1234  ") | 422 |

---

### VS-15-N: 服务日志-无效跟进类型

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/notes`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "type": "invalid_type",
  "content": "这是一个有效的跟进内容至少十个字"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 无效的跟进类型

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-15-N-B1 | type | "invalid_type" | 无效值 | 422 | 无效的跟进类型 |
| VS-15-N-B2 | type | "" | 空值 | 201 | 默认call (或不传时默认) |
| VS-15-N-B3 | type | "note" | 有效 | 201 | 备注类型 |
| VS-15-N-B4 | type | "call" | 有效 | 201 | 电话类型 |
| VS-15-N-B5 | type | "visit" | 有效 | 201 | 拜访类型 |
| VS-15-N-B6 | type | "wechat" | 有效 | 201 | 微信类型 |
| VS-15-N-B7 | type | "video" | 有效 | 201 | 视频类型 |
| VS-15-N-B8 | type | "email" | 有效 | 201 | 邮件类型 |
| VS-15-N-B9 | type | "training" | 有效 | 201 | 培训类型 |
| VS-15-N-B10 | type | "complaint" | 有效 | 201 | 投诉类型 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-15-N-S1 | 无效类型 | active商家 | POST note(invalid) | 422 |
| VS-15-N-S2 | 有效类型note | active商家 | POST note(note) | 201 |
| VS-15-N-S3 | 不传type默认call | active商家 | POST note(无type) | 201, type=call |
| VS-15-N-S4 | onboarding_assist类型 | active商家 | POST note(onboarding_assist) | 201 |

---

### VS-16-N: 续费申请-非正常营业商家

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 suspended 状态商家 (非 active)

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "purchase_mode": "renew_same",
  "target_plan": "PL_BASIC",
  "quoted_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "customer_confirmed": true,
  "content": "客户确认续费基础版套餐"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 仅正常营业商家可申请续费

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-16-N-B1 | merchant.status | suspended | 非active | 409 | 仅正常营业商家可申请续费 |
| VS-16-N-B2 | merchant.status | closed | 非active | 409 | 仅正常营业商家可申请续费 |
| VS-16-N-B3 | merchant.status | active | 正常 | 201 | 正常创建 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-16-N-S1 | suspended商家续费 | status=suspended | POST renewal | 409 |
| VS-16-N-S2 | closed商家续费 | status=closed | POST renewal | 409 |
| VS-16-N-S3 | active商家续费 | status=active | POST renewal | 201 |

---

### VS-17-N: 续费申请-未确认客户意向

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家, 套餐即将到期

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "purchase_mode": "renew_same",
  "target_plan": "PL_BASIC",
  "quoted_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "customer_confirmed": false,
  "content": "客户确认续费基础版套餐"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 请先与客户确认续费意向

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-17-N-B1 | customer_confirmed | false | 未确认 | 422 | 请先与客户确认续费意向 |
| VS-17-N-B2 | customer_confirmed | 不传 | 默认false | 422 | 请先与客户确认续费意向 |
| VS-17-N-B3 | customer_confirmed | true | 已确认 | 201 | 正常创建 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-17-N-S1 | 未确认意向 | active+expiring | POST renewal(confirmed=false) | 422 |
| VS-17-N-S2 | 不传confirmed | active+expiring | POST renewal(无confirmed) | 422 |
| VS-17-N-S3 | 已确认意向 | active+expiring | POST renewal(confirmed=true) | 201 |

---

### VS-18-N: 续费申请-已有待处理续费

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家, 已有 status=pending 的续费申请

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "purchase_mode": "renew_same",
  "target_plan": "PL_BASIC",
  "quoted_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "customer_confirmed": true,
  "content": "客户确认续费基础版套餐"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 已有待处理续费申请

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-18-N-B1 | existing_renewal | status=pending | 待处理 | 409 | 已有待处理续费申请 |
| VS-18-N-B2 | existing_renewal | status=processing | 处理中 | 409 | 已有待处理续费申请 |
| VS-18-N-B3 | existing_renewal | status=cancelled | 已取消 | 201 | 可重新申请 |
| VS-18-N-B4 | existing_renewal | status=approved | 已完成 | 201 | 可重新申请 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-18-N-S1 | 有pending续费再申请 | 有pending | POST renewal | 409 |
| VS-18-N-S2 | 有processing续费再申请 | 有processing | POST renewal | 409 |
| VS-18-N-S3 | 有cancelled续费再申请 | 有cancelled | POST renewal | 201 |
| VS-18-N-S4 | 无续费申请 | 无 | POST renewal | 201 |

---

### VS-19-N: 续费申请-套餐未到期

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家, plan_status=active (套餐未到期, benefits_until > 30天后)

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "purchase_mode": "renew_same",
  "target_plan": "PL_BASIC",
  "quoted_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "customer_confirmed": true,
  "content": "客户确认续费基础版套餐"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 当前套餐未到期

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-19-N-B1 | plan_status | active (>30天) | 未到期 | 409 | 当前套餐未到期 |
| VS-19-N-B2 | plan_status | expiring_soon (<=30天) | 即将到期 | 201 | 可申请续费 |
| VS-19-N-B3 | plan_status | expired | 已过期 | 201 | 可申请续费 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-19-N-S1 | 套餐未到期续费 | plan_status=active | POST renewal | 409 |
| VS-19-N-S2 | 套餐即将到期续费 | plan_status=expiring_soon | POST renewal | 201 |
| VS-19-N-S3 | 套餐已过期续费 | plan_status=expired | POST renewal | 201 |

---

### VS-20-N: 取消续费-无订阅管理权限

**前置条件**:
- 存在 status=pending 的续费申请
- 使用无订阅管理权限的角色 token (如 platform_shop_finance)

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{service_log_id}/cancel`
**Headers**: `Authorization: Bearer {finance_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 403
- Response Body 含错误信息: 无订阅管理权限

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-20-N-B1 | token | finance_token | 无权限 | 403 | 无订阅管理权限 |
| VS-20-N-B2 | token | merchant_token | 无权限 | 403 | 无订阅管理权限 |
| VS-20-N-B3 | token | ops_token (有权限) | 有权限 | 200 | 正常取消 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-20-N-S1 | 财务取消续费 | finance已登录 | POST cancel | 403 |
| VS-20-N-S2 | 商家取消续费 | merchant已登录 | POST cancel | 403 |
| VS-20-N-S3 | 运营取消续费 | ops已登录 | POST cancel | 200 |

---

### VS-21-N: 取消续费-申请已结案

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 status=approved (已结案) 的续费申请

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests/{service_log_id}/cancel`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 申请已结案

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-21-N-B1 | status | approved | 已结案 | 409 | 申请已结案 |
| VS-21-N-B2 | status | rejected | 已结案 | 409 | 申请已结案 |
| VS-21-N-B3 | status | cancelled | 已结案 | 409 | 申请已结案 |
| VS-21-N-B4 | status | pending | 可取消 | 200 | 正常取消 |
| VS-21-N-B5 | status | processing | 可取消 | 200 | 正常取消 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-21-N-S1 | 取消已批准续费 | status=approved | POST cancel | 409 |
| VS-21-N-S2 | 取消已拒绝续费 | status=rejected | POST cancel | 409 |
| VS-21-N-S3 | 取消待处理续费 | status=pending | POST cancel | 200 |
| VS-21-N-S4 | 取消处理中续费 | status=processing | POST cancel | 200 |

---

### VS-22-N: 商家列表-分页参数边界

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中有足够多的商家数据

**API**: `GET /admin/shop/merchants?page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- 正确返回分页数据

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-22-N-B1 | page | 1 | 最小有效值 | 200 | 正常返回第一页 |
| VS-22-N-B2 | page | 0 | 最小值违规 | 422 | page >= 1 |
| VS-22-N-B3 | page | -1 | 负值 | 422 | page >= 1 |
| VS-22-N-B4 | page | 999999 | 超出范围 | 200 | 空items, total不变 |
| VS-22-N-B5 | page_size | 1 | 最小有效值 | 200 | 返回1条 |
| VS-22-N-B6 | page_size | 100 | 最大有效值 | 200 | 返回最多100条 |
| VS-22-N-B7 | page_size | 0 | 最小值违规 | 422 | page_size >= 1 |
| VS-22-N-B8 | page_size | 101 | 最大值违规 | 422 | page_size <= 100 |
| VS-22-N-B9 | page | 不传 | 默认值 | 200 | page=1 |
| VS-22-N-B10 | page_size | 不传 | 默认值 | 200 | page_size=20 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-22-N-S1 | page=0 | 有数据 | GET ?page=0 | 422 |
| VS-22-N-S2 | page_size=101 | 有数据 | GET ?page_size=101 | 422 |
| VS-22-N-S3 | page_size=100 | 有>100条数据 | GET ?page_size=100 | 200, 返回100条 |
| VS-22-N-S4 | 超出页码 | 有10条数据 | GET ?page=999 | 200, items=[] |

---

### VS-23-N: 租户选项-排除已入驻/待审/不活跃

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中有: 未入驻活跃租户A、已入驻租户B、有待审申请租户C、不活跃租户D

**API**: `GET /admin/shop/onboarding/tenant-options?limit=50`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- items 中包含租户A, 不包含B/C/D

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-23-N-B1 | limit | 1 | 最小有效值 | 200 | 返回1条 |
| VS-23-N-B2 | limit | 50 | 最大有效值 | 200 | 返回最多50条 |
| VS-23-N-B3 | limit | 0 | 最小值违规 | 422 | limit >= 1 |
| VS-23-N-B4 | limit | 51 | 最大值违规 | 422 | limit <= 50 |
| VS-23-N-B5 | limit | 不传 | 默认值 | 200 | limit=20 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-23-N-S1 | 排除已入驻租户 | 有已入驻B | GET /tenant-options | items不含B |
| VS-23-N-S2 | 排除待审租户 | 有待审C | GET /tenant-options | items不含C |
| VS-23-N-S3 | 排除不活跃租户 | 有不活跃D | GET /tenant-options | items不含D |
| VS-23-N-S4 | 包含未入驻活跃 | 有未入驻A | GET /tenant-options | items含A |
| VS-23-N-S5 | 搜索过滤 | 有匹配数据 | GET ?q=关键词 | 仅返回匹配的未入驻租户 |

---

### VS-24-N: 暂停-原因不足4字

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "违规"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 暂停原因至少4字

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-24-N-B1 | reason_text | "" | 空值 | 422 | 暂停原因不能为空 |
| VS-24-N-B2 | reason_text | "违规" (2字) | 长度不足 | 422 | 至少4字 |
| VS-24-N-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VS-24-N-B4 | reason_text | "违规操作" (4字) | 最小有效 | 200 | 正常暂停 |
| VS-24-N-B5 | reason_text | "  违规操作  " (strip后4字) | strip后有效 | 200 | 正常暂停 |
| VS-24-N-B6 | reason_text | 不传 | 缺失 | 422 | 暂停原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-24-N-S1 | 2字原因 | active商家 | POST suspend(2字) | 422 |
| VS-24-N-S2 | 4字原因 | active商家 | POST suspend(4字) | 200 |
| VS-24-N-S3 | 空原因 | active商家 | POST suspend("") | 422 |
| VS-24-N-S4 | strip后不足 | active商家 | POST suspend("  ab  ") | 422 |

---

### VS-25-N: 关闭-未确认不可逆

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家主动申请关闭账号",
  "ack_irreversible": false
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 请确认操作不可逆

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-25-N-B1 | ack_irreversible | false | 未确认 | 422 | 请确认操作不可逆 |
| VS-25-N-B2 | ack_irreversible | 不传 | 缺失 | 422 | 请确认操作不可逆 |
| VS-25-N-B3 | ack_irreversible | true | 已确认 | 200 | 正常关闭 |
| VS-25-N-B4 | ack_irreversible | "true" (字符串) | 类型错误 | 422 | 布尔值类型错误 |
| VS-25-N-B5 | ack_irreversible | null | null值 | 422 | 请确认操作不可逆 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-25-N-S1 | 未确认不可逆 | active商家 | POST close(ack=false) | 422 |
| VS-25-N-S2 | 确认不可逆 | active商家 | POST close(ack=true) | 200 |
| VS-25-N-S3 | 不传ack | active商家 | POST close(无ack) | 422 |

---

### VS-26-N: 关闭-closed不可重开

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 closed 状态商家 (终态)

**API**: `POST /admin/shop/merchants/{tenant_id}/resume`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 商家已关闭, 不可恢复

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-26-N-B1 | 操作 | POST resume | 恢复 | 409 | closed不可恢复 |
| VS-26-N-B2 | 操作 | POST suspend | 暂停 | 409 | closed不可暂停 |
| VS-26-N-B3 | 操作 | POST close | 再次关闭 | 409 | closed已关闭 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-26-N-S1 | closed恢复 | status=closed | POST resume | 409 |
| VS-26-N-S2 | closed暂停 | status=closed | POST suspend | 409 |
| VS-26-N-S3 | closed再关闭 | status=closed | POST close | 409 |
| VS-26-N-S4 | closed重新入驻 | status=closed | POST onboarding | 409, 永久阻断 |

---

### VS-27-N: 关闭-续费申请自动取消

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家, 有 status=pending 和 status=processing 的续费申请

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家主动申请关闭账号经营",
  "ack_irreversible": true
}
```

**期望结果**:
- HTTP Status: 200
- 副作用: pending 和 processing 续费申请变为 cancelled

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-27-N-B1 | renewal.status | pending | 待处理 | 200 | 关闭后变cancelled |
| VS-27-N-B2 | renewal.status | processing | 处理中 | 200 | 关闭后变cancelled |
| VS-27-N-B3 | renewal.status | approved | 已完成 | 200 | 不受影响 |
| VS-27-N-B4 | renewal.status | cancelled | 已取消 | 200 | 不受影响 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-27-N-S1 | 关闭后pending变cancelled | 有pending续费 | POST close | 续费变cancelled |
| VS-27-N-S2 | 关闭后processing变cancelled | 有processing续费 | POST close | 续费变cancelled |
| VS-27-N-S3 | 关闭后approved不变 | 有approved续费 | POST close | 续费状态不变 |
| VS-27-N-S4 | 验证店铺暂停 | 有active店铺 | POST close | 店铺变paused |

---

### VS-28-N: 关闭-永久阻断重新入驻

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 closed 状态商家的租户

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已关闭商家的租户UUID",
  "entity_type": "enterprise",
  "legal_name": "新公司名称",
  "contact_name": "新联系人",
  "contact_mobile": "13800004444",
  "unified_social_credit_code": "91110000MA01JKL012",
  "legal_rep_name": "新法人"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 该租户已入驻 / 租户永久阻断

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-28-N-B1 | tenant.status | closed | 永久阻断 | 409 | 租户永久阻断重新入驻 |
| VS-28-N-B2 | tenant.status | active | 正常 | 409 | 该租户已入驻 |
| VS-28-N-B3 | tenant.status | 未入驻 | 可入驻 | 201 | 正常创建 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-28-N-S1 | closed租户重新入驻 | status=closed | POST application | 409 |
| VS-28-N-S2 | closed租户在tenant-options中排除 | status=closed | GET /tenant-options | items不含该租户 |
| VS-28-N-S3 | 验证permanent block标记 | status=closed | 检查数据库 | 有permanent_block标记 |

---

### VS-29-N: 续费申请-续费说明不足4字

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家, 套餐即将到期

**API**: `POST /admin/shop/merchants/{tenant_id}/service-logs/renewal-requests`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "purchase_mode": "renew_same",
  "target_plan": "PL_BASIC",
  "quoted_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "customer_confirmed": true,
  "content": "续费"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 请填写续费说明（至少4字）

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-29-N-B1 | content | "" | 空值 | 422 | 请填写续费说明 |
| VS-29-N-B2 | content | "续费" (2字) | 长度不足 | 422 | 至少4字 |
| VS-29-N-B3 | content | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VS-29-N-B4 | content | "续费套餐" (4字) | 最小有效 | 201 | 正常创建 |
| VS-29-N-B5 | content | "  续费套餐  " (strip后4字) | strip后有效 | 201 | 正常创建 |
| VS-29-N-B6 | content | null | null值 | 422 | 请填写续费说明 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-29-N-S1 | 2字说明 | active+expiring | POST renewal(2字) | 422 |
| VS-29-N-S2 | 4字说明 | active+expiring | POST renewal(4字) | 201 |
| VS-29-N-S3 | 空说明 | active+expiring | POST renewal("") | 422 |
| VS-29-N-S4 | strip后不足 | active+expiring | POST renewal("  ab  ") | 422 |

---

### VS-30-N: 商家列表-scope 隔离

**前置条件**:
- platform_shop_ops 管理员 A 已登录, 获取 ops_A_token
- platform_shop_ops 管理员 B 已登录, 获取 ops_B_token
- 管理员 A 关联了商家 X, 管理员 B 关联了商家 Y

**API**: `GET /admin/shop/merchants?tab=my_clients`
**Headers**: `Authorization: Bearer {ops_A_token 或 ops_B_token}`

**请求体**: 无

**期望结果**:
- ops_A_token: items 中仅含商家 X, 不含商家 Y
- ops_B_token: items 中仅含商家 Y, 不含商家 X
- scope 字段反映各自可见范围

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VS-30-N-B1 | token | ops_A_token | 管理员A | 200 | 仅返回A关联的商家 |
| VS-30-N-B2 | token | ops_B_token | 管理员B | 200 | 仅返回B关联的商家 |
| VS-30-N-B3 | account_manager_user_id | A的user_id | 筛选 | 200 | 仅返回A关联的商家 |
| VS-30-N-B4 | account_manager_user_id | B的user_id | 筛选 | 200 | 仅返回B关联的商家 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VS-30-N-S1 | 管理员A查看my_clients | A关联商家X | GET ?tab=my_clients (A token) | 200, 仅含X |
| VS-30-N-S2 | 管理员B查看my_clients | B关联商家Y | GET ?tab=my_clients (B token) | 200, 仅含Y |
| VS-30-N-S3 | 管理员A按user_id筛选 | A的user_id | GET ?account_manager_user_id=A | 200, 仅含X |
| VS-30-N-S4 | 验证scope字段 | 分别请求 | 检查 scope | 各自反映可见范围 |

---

## M1 套餐订阅

### M1 套餐模板管理

---

### VM1-1: 创建套餐模板

**前置条件**:
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456, 获取 admin_token）
- 数据库中无 code="PL_TEST_001" 的套餐模板
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /admin/shop/plans`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "PL_TEST_001",
  "name": "测试基础版"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `code="PL_TEST_001"`, `name="测试基础版"`
- 数据库: shop_plan_templates 新增 1 条记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-1-B1 | code | "" | 空值 | 422 | 编码不能为空 |
| VM1-1-B2 | code | 重复code | 唯一约束 | 409 | 编码已存在 |
| VM1-1-B3 | name | "" | 空值 | 422 | 名称不能为空 |
| VM1-1-B4 | name | 重复name | 唯一约束 | 409 | 名称已存在 |
| VM1-1-B5 | code | null | null值 | 422 | 编码不能为空 |
| VM1-1-B6 | name | null | null值 | 422 | 名称不能为空 |
| VM1-1-B7 | stackable | true (addon) | 附加包 | 201 | 创建附加包模板 |
| VM1-1-B8 | stackable | false (main) | 主套餐 | 201 | 创建主套餐模板 |
| VM1-1-B9 | is_public | 不传 | 默认值 | 201 | is_public=false |
| VM1-1-B10 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-1-S1 | 正常创建 | 无模板 | POST创建 | 201 |
| VM1-1-S2 | 重复创建 | 已有同code | POST创建 | 409 |
| VM1-1-S3 | 创建主套餐 | 无模板 | POST(stackable=false, replace_group="main") | 201 |
| VM1-1-S4 | 创建附加包 | 无模板 | POST(stackable=true, replace_group=null) | 201 |
| VM1-1-S5 | 验证is_public默认false | 已创建 | 检查is_public | false |

---

### VM1-2: 修改套餐模板

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 code="PL_TEST_001" 的套餐模板 (未上架)

**API**: `PATCH /admin/shop/plans/{plan_id}`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "name": "测试基础版V2",
  "description": "更新后的描述"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `name="测试基础版V2"`, `description` 更新
- code 字段不可修改, 保持原值

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-2-B1 | code | "PL_NEW_CODE" | 只读字段 | 200 | code不可修改, 忽略或报错 |
| VM1-2-B2 | name | "" | 空值 | 422 | 名称不能为空 |
| VM1-2-B3 | name | 重复name | 唯一约束 | 409 | 名称已存在 |
| VM1-2-B4 | plan_id | 不存在的UUID | 不存在 | 404 | 套餐模板不存在 |
| VM1-2-B5 | plan_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM1-2-B6 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-2-S1 | 正常修改名称 | 模板存在 | PATCH name | 200, name更新 |
| VM1-2-S2 | 尝试修改code | 模板存在 | PATCH code | 200, code不变 |
| VM1-2-S3 | 修改不存在模板 | 无此模板 | PATCH /{invalid_id} | 404 |
| VM1-2-S4 | 修改已上架模板 | is_public=true | PATCH price | 200, 价格生效于新开通 |
| VM1-2-S5 | 验证已购snapshot不变 | 有已购订阅 | 修改价格后检查 | 旧订阅plan_snapshot不变 |

---

### VM1-3: 上架套餐模板

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 code="PL_TEST_001" 的套餐模板, is_public=false
- 该模板已有至少 1 个权益 (benefit)

**API**: `POST /admin/shop/plans/{plan_id}/publish`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `is_public`=true
- 数据库: shop_plan_templates.is_public 变为 true

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-3-B1 | benefits | 0个权益 | 无权益 | 422 | 至少需要1个权益 |
| VM1-3-B2 | benefits | 1个权益 | 最小有效 | 200 | 正常上架 |
| VM1-3-B3 | replace_group | null (main计划) | 无replace_group | 422 | main计划需replace_group |
| VM1-3-B4 | replace_group | "main" | 有效值 | 200 | 正常上架 |
| VM1-3-B5 | plan_id | 不存在的UUID | 不存在 | 404 | 套餐模板不存在 |
| VM1-3-B6 | is_public | 已上架 | 重复上架 | 200 或 409 | 已上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-3-S1 | 正常上架 | 有权益+replace_group | POST publish | 200, is_public=true |
| VM1-3-S2 | 无权益上架 | 0个权益 | POST publish | 422 |
| VM1-3-S3 | main无replace_group | stackable=false, replace_group=null | POST publish | 422 |
| VM1-3-S4 | addon上架 | stackable=true | POST publish | 200 |
| VM1-3-S5 | 已上架再上架 | is_public=true | POST publish | 200 或 409 |

---

### VM1-4: 下架套餐模板

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 code="PL_TEST_001" 的套餐模板, is_public=true

**API**: `POST /admin/shop/plans/{plan_id}/unpublish`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `is_public`=false
- 已购订阅不受影响

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-4-B1 | is_public | true (已上架) | 可下架 | 200 | 正常下架 |
| VM1-4-B2 | is_public | false (未上架) | 重复下架 | 200 或 409 | 已下架 |
| VM1-4-B3 | plan_id | 不存在的UUID | 不存在 | 404 | 套餐模板不存在 |
| VM1-4-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-4-S1 | 正常下架 | is_public=true | POST unpublish | 200, is_public=false |
| VM1-4-S2 | 下架后已购订阅不变 | 有active订阅 | POST unpublish后检查 | 旧订阅不受影响 |
| VM1-4-S3 | 下架后不可新开通 | is_public=false | POST subscription | 403/409 |
| VM1-4-S4 | 重新上架 | 下架后 | POST publish | 200, is_public=true |

---

### VM1-5: 获取套餐模板列表

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在多个套餐模板, 含已上架和未上架

**API**: `GET /admin/shop/plans?page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total` (int), `page`, `page_size`
- items 按sort_order排序

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-5-B1 | page | 0 | 最小值违规 | 422 | page >= 1 |
| VM1-5-B2 | page_size | 101 | 最大值违规 | 422 | page_size <= 100 |
| VM1-5-B3 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM1-5-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |
| VM1-5-B5 | is_public | true | 筛选已上架 | 200 | 仅返回已上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-5-S1 | 获取全部模板 | 有多个模板 | GET /plans | 200, 返回全部 |
| VM1-5-S2 | 筛选已上架 | 有上架和未上架 | GET ?is_public=true | 200, 仅已上架 |
| VM1-5-S3 | 验证sort_order | 有多个模板 | 检查排序 | 按sort_order升序 |
| VM1-5-S4 | 首个模板sort_order=10 | 第一个创建的 | 检查sort_order | 10 |

---

### VM1-6: 获取套餐模板详情

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 plan_id=已知UUID 的套餐模板

**API**: `GET /admin/shop/plans/{plan_id}`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `id`, `code`, `name`, `is_public`, `stackable`, `replace_group`, `benefits` (数组), `allowed_entity_types`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-6-B1 | plan_id | 不存在的UUID | 不存在 | 404 | 套餐模板不存在 |
| VM1-6-B2 | plan_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM1-6-B3 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM1-6-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-6-S1 | 获取模板详情 | 模板存在 | GET /{plan_id} | 200, 完整详情 |
| VM1-6-S2 | 获取不存在的模板 | UUID不匹配 | GET /{invalid_id} | 404 |
| VM1-6-S3 | 验证含benefits | 有权益 | 检查benefits字段 | 数组非空 |
| VM1-6-S4 | 验证含allowed_entity_types | 有配置 | 检查字段 | 数组含实体类型 |

---

### VM1-7: 创建套餐权益

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 plan_id=已知UUID 的套餐模板

**API**: `POST /admin/shop/plans/{plan_id}/benefits`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "benefit_type": "store_quota",
  "value": 5,
  "display_name": "店铺配额"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `benefit_type`, `value`, `display_name`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-7-B1 | benefit_type | "" | 空值 | 422 | 权益类型不能为空 |
| VM1-7-B2 | benefit_type | 重复类型 | 唯一约束 | 409 | 权益类型已存在 |
| VM1-7-B3 | value | -1 | 负值 | 422 | 值必须 >= 0 |
| VM1-7-B4 | value | 0 | 零值 | 201 | 有效值 |
| VM1-7-B5 | plan_id | 不存在的UUID | 不存在 | 404 | 套餐模板不存在 |
| VM1-7-B6 | display_name | "" | 空值 | 422 | 显示名称不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-7-S1 | 正常创建权益 | 模板存在 | POST benefit | 201 |
| VM1-7-S2 | 重复权益类型 | 已有同类型 | POST benefit | 409 |
| VM1-7-S3 | 创建多个权益 | 有1个权益 | POST另一个 | 201 |
| VM1-7-S4 | 上架前添加权益 | is_public=false | POST benefit | 201 |

---

### VM1-8: 开通订阅

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家, entity_type=enterprise
- 存在已上架套餐模板 code="PL_BASIC", is_public=true, allowed_entity_types含enterprise
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "remark": "正常开通一年期套餐"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `tenant_id`, `plan_label`, `status`="active", `effective_at`, `expires_at`
- 数据库: subscriptions 新增 1 条 active 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-8-B1 | tenant_id | suspended商家 | 非active | 409 | 商家状态非active |
| VM1-8-B2 | plan_label | 未上架套餐 | 非public | 403/409 | 套餐未上架 |
| VM1-8-B3 | allowed_entity_types | 不含商家类型 | 类型不匹配 | 409 | 主体类型不匹配 |
| VM1-8-B4 | effective_at | 晚于expires_at | 日期逻辑错误 | 422 | effective_at <= expires_at |
| VM1-8-B5 | paid_amount_cents | -1 | 负值 | 422 | 金额 >= 0 |
| VM1-8-B6 | paid_amount_cents | 0 (无remark) | 零金额无备注 | 422 | 零金额需备注 |
| VM1-8-B7 | paid_amount_cents | 0 (有remark) | 零金额有备注 | 201 | 正常开通 |
| VM1-8-B8 | paid_amount_cents | >catalog*2 | 金额异常 | 422 | 金额异常 |
| VM1-8-B9 | plan_label | "" | 空值 | 422 | 套餐不能为空 |
| VM1-8-B10 | tenant_id | 不存在UUID | 不存在 | 404 | 商家不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-8-S1 | 正常开通 | active商家+已上架套餐 | POST subscription | 201, status=active |
| VM1-8-S2 | 非active商家开通 | suspended商家 | POST subscription | 409 |
| VM1-8-S3 | 未上架套餐开通 | is_public=false | POST subscription | 403/409 |
| VM1-8-S4 | 主体类型不匹配 | enterprise商家, 套餐仅personal | POST subscription | 409 |
| VM1-8-S5 | 零金额有备注 | paid=0, remark非空 | POST subscription | 201 |
| VM1-8-S6 | 金额异常 | paid > catalog*2 | POST subscription | 422 |

---

### VM1-9: 获取订阅列表

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在多个订阅记录, 含 active, expired, cancelled 状态

**API**: `GET /admin/shop/subscriptions?tenant_id={tenant_id}&page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total`, `page`, `page_size`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-9-B1 | tenant_id | 不存在UUID | 不存在 | 200 | 空items |
| VM1-9-B2 | page | 0 | 最小值违规 | 422 | page >= 1 |
| VM1-9-B3 | page_size | 101 | 最大值违规 | 422 | page_size <= 100 |
| VM1-9-B4 | status | "invalid" | 无效值 | 422 | status值无效 |
| VM1-9-B5 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-9-S1 | 按租户筛选 | 有订阅数据 | GET ?tenant_id=xxx | 200, 仅返回该租户订阅 |
| VM1-9-S2 | 按状态筛选 | 有active订阅 | GET ?status=active | 200, 仅返回active |
| VM1-9-S3 | 无订阅的租户 | 无订阅 | GET ?tenant_id=xxx | 200, items=[] |
| VM1-9-S4 | 验证plan_snapshot | 有订阅 | 检查plan_snapshot字段 | 快照信息完整 |

---

### VM1-10: 取消订阅

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 subscription_id=已知UUID 的 addon 类型订阅, status=active

**API**: `POST /admin/shop/subscriptions/{subscription_id}/cancel`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason": "客户主动取消附加包"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `id`, `status`="cancelled"
- 数据库: subscription.status 变为 cancelled

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-10-B1 | subscription.type | main (非addon) | 非addon | 409 | 仅addon可取消 |
| VM1-10-B2 | subscription.type | addon | 可取消 | 200 | 正常取消 |
| VM1-10-B3 | subscription.status | expired | 非active | 409 | 仅active可取消 |
| VM1-10-B4 | subscription.status | cancelled | 已取消 | 409 | 已取消 |
| VM1-10-B5 | subscription_id | 不存在UUID | 不存在 | 404 | 订阅不存在 |
| VM1-10-B6 | reason | "" | 空值 | 422 | 取消原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-10-S1 | 正常取消addon | addon+active | POST cancel | 200, status=cancelled |
| VM1-10-S2 | 取消main订阅 | main+active | POST cancel | 409, 仅addon可取消 |
| VM1-10-S3 | 取消已过期订阅 | expired | POST cancel | 409 |
| VM1-10-S4 | 取消已取消订阅 | cancelled | POST cancel | 409 |

---

### M1 新增测试用例

---

### VM1-1-N: 创建套餐模板-code为空

**前置条件**:
- 平台管理员已登录, 获取 admin_token

**API**: `POST /admin/shop/plans`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "",
  "name": "测试空编码"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 编码不能为空

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-1-N-B1 | code | "" | 空值 | 422 | 编码不能为空 |
| VM1-1-N-B2 | code | null | null值 | 422 | 编码不能为空 |
| VM1-1-N-B3 | code | "   " | 空白 | 422 | 编码不能为空 |
| VM1-1-N-B4 | code | 不传 | 缺失 | 422 | 编码不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-1-N-S1 | 空code | 无 | POST(code="") | 422 |
| VM1-1-N-S2 | null code | 无 | POST(code=null) | 422 |
| VM1-1-N-S3 | 缺失code | 无 | POST(无code字段) | 422 |

---

### VM1-2-N: 创建套餐模板-code重复

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中已存在 code="PL_TEST_001" 的套餐模板

**API**: `POST /admin/shop/plans`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "PL_TEST_001",
  "name": "另一个名称"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 编码已存在

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-2-N-B1 | code | 已存在code | 重复 | 409 | 编码已存在 |
| VM1-2-N-B2 | code | "PL_TEST_002" (新) | 不重复 | 201 | 正常创建 |
| VM1-2-N-B3 | code | "pl_test_001" (大小写) | 大小写敏感 | 201 或 409 | 取决于是否大小写敏感 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-2-N-S1 | 重复code创建 | 已有PL_TEST_001 | POST(同code) | 409 |
| VM1-2-N-S2 | 不同code创建 | 已有PL_TEST_001 | POST(新code) | 201 |
| VM1-2-N-S3 | 大小写敏感测试 | 已有PL_TEST_001 | POST(PL_test_001) | 201 或 409 |

---

### VM1-3-N: 创建套餐模板-名称重复

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中已存在 name="测试基础版" 的套餐模板

**API**: `POST /admin/shop/plans`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "PL_NEW_CODE",
  "name": "测试基础版"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 名称已存在

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-3-N-B1 | name | 已存在name | 重复 | 409 | 名称已存在 |
| VM1-3-N-B2 | name | "新名称" | 不重复 | 201 | 正常创建 |
| VM1-3-N-B3 | name | "  测试基础版  " | trim后重复 | 409 | trim后已存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-3-N-S1 | 重复name创建 | 已有同name | POST(同name) | 409 |
| VM1-3-N-S2 | 不同name创建 | 已有其他name | POST(新name) | 201 |

---

### VM1-4-N: 创建套餐模板-sort_order自动计算

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中已有 2 个套餐模板, sort_order 分别为 10, 20

**API**: `POST /admin/shop/plans`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "PL_SORT_TEST",
  "name": "排序测试"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `sort_order`=30 (max+10)
- 首个模板 sort_order=10, 后续自动递增

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-4-N-B1 | sort_order | 不传 | 自动计算 | 201 | sort_order=max+10 |
| VM1-4-N-B2 | sort_order | 5 | 手动指定 | 201 | 使用手动值 |
| VM1-4-N-B3 | 第一个模板 | 无已有模板 | 首个 | 201 | sort_order=10 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-4-N-S1 | 首个模板sort_order | 无已有模板 | POST创建 | sort_order=10 |
| VM1-4-N-S2 | 第二个模板sort_order | 有1个(10) | POST创建 | sort_order=20 |
| VM1-4-N-S3 | 第三个模板sort_order | 有2个(10,20) | POST创建 | sort_order=30 |

---

### VM1-5-N: 创建套餐模板-is_public默认false

**前置条件**:
- 平台管理员已登录, 获取 admin_token

**API**: `POST /admin/shop/plans`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "PL_PUBLIC_TEST",
  "name": "默认不上架"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `is_public`=false (默认值)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-5-N-B1 | is_public | 不传 | 默认值 | 201 | is_public=false |
| VM1-5-N-B2 | is_public | false | 显式false | 201 | is_public=false |
| VM1-5-N-B3 | is_public | true | 显式true | 201 | is_public=true |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-5-N-S1 | 不传is_public | 无 | POST(无is_public) | 201, is_public=false |
| VM1-5-N-S2 | 显式false | 无 | POST(is_public=false) | 201, is_public=false |
| VM1-5-N-S3 | 验证默认不上架 | 已创建 | GET /{plan_id} | is_public=false |

---

### VM1-6-N: 修改套餐模板-code只读

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在 code="PL_TEST_001" 的套餐模板

**API**: `PATCH /admin/shop/plans/{plan_id}`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "code": "PL_NEW_CODE",
  "name": "新名称"
}
```

**期望结果**:
- HTTP Status: 200
- code 字段保持原值 "PL_TEST_001" (只读, 不可修改)
- name 字段更新为 "新名称"

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-6-N-B1 | code | "PL_NEW_CODE" | 尝试修改 | 200 | code不变, 忽略修改 |
| VM1-6-N-B2 | code | "" | 尝试清空 | 200 | code不变 |
| VM1-6-N-B3 | code | null | 尝试置null | 200 | code不变 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-6-N-S1 | 尝试修改code | 模板存在 | PATCH(code=new) | 200, code不变 |
| VM1-6-N-S2 | 修改name | 模板存在 | PATCH(name=new) | 200, name更新 |
| VM1-6-N-S3 | 修改description | 模板存在 | PATCH(desc=new) | 200, desc更新 |

---

### VM1-7-N: 上架-无权益

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在套餐模板, 无任何权益 (benefits=[])

**API**: `POST /admin/shop/plans/{plan_id}/publish`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 至少需要1个权益

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-7-N-B1 | benefits | [] (0个) | 无权益 | 422 | 至少1个权益 |
| VM1-7-N-B2 | benefits | [1个] | 最小有效 | 200 | 正常上架 |
| VM1-7-N-B3 | benefits | [多个] | 多个权益 | 200 | 正常上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-7-N-S1 | 无权益上架 | benefits=[] | POST publish | 422 |
| VM1-7-N-S2 | 有1个权益上架 | benefits=[1] | POST publish | 200 |
| VM1-7-N-S3 | 先添加权益再上架 | benefits=[] | POST benefit后publish | 200 |

---

### VM1-8-N: 上架-main无replace_group

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在套餐模板, stackable=false (main), replace_group=null, 有1个权益

**API**: `POST /admin/shop/plans/{plan_id}/publish`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: main计划需设置replace_group

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-8-N-B1 | replace_group | null (main) | 无replace_group | 422 | main需replace_group |
| VM1-8-N-B2 | replace_group | "main" | 有效值 | 200 | 正常上架 |
| VM1-8-N-B3 | replace_group | null (addon) | addon不需要 | 200 | addon无replace_group正常 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-8-N-S1 | main无replace_group | stackable=false, rg=null | POST publish | 422 |
| VM1-8-N-S2 | main有replace_group | stackable=false, rg="main" | POST publish | 200 |
| VM1-8-N-S3 | addon无replace_group | stackable=true, rg=null | POST publish | 200 |

---

### VM1-9-N: 已上架改价-新开通生效

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在已上架套餐模板 code="PL_BASIC", catalog_price_cents=98000
- 存在使用该模板的已购订阅 (plan_snapshot记录旧价格)

**API**: `PATCH /admin/shop/plans/{plan_id}`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "catalog_price_cents": 128000
}
```

**期望结果**:
- HTTP Status: 200
- 套餐模板价格更新为 128000
- 新开通的订阅使用新价格
- 已购订阅的 plan_snapshot 保持旧价格 98000

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-9-N-B1 | catalog_price_cents | 128000 | 正常改价 | 200 | 价格更新 |
| VM1-9-N-B2 | catalog_price_cents | 0 | 零价 | 200 | 价格更新为0 |
| VM1-9-N-B3 | catalog_price_cents | -1 | 负值 | 422 | 价格必须 >= 0 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-9-N-S1 | 改价后新开通使用新价 | 已改价 | POST subscription | paid使用新catalog_price |
| VM1-9-N-S2 | 已购订阅snapshot不变 | 已有旧订阅 | 检查plan_snapshot | 保持旧价格 |
| VM1-9-N-S3 | 改价后改能力 | 已上架 | PATCH abilities | 新开通使用新能力, 旧不变 |

---

### VM1-10-N: 开通-同replace_group叠加

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 已有 active 状态的 main 订阅 (replace_group="main")
- 存在另一个 main 套餐模板, replace_group="main"

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_PRO",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 198000,
  "catalog_price_cents": 198000
}
```

**期望结果**:
- purchase_mode=stack: HTTP Status 201, old subscription continues
- purchase_mode=replace: HTTP Status 201, old subscription status → superseded

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-10-N-B1 | purchase_mode | stack (main+main同rg) | 叠加 | 409 | main不可叠加同replace_group |
| VM1-10-N-B2 | purchase_mode | replace (main+main同rg) | 替换 | 201 | old变superseded |
| VM1-10-N-B3 | purchase_mode | stack (addon+addon) | 附加包叠加 | 201 | 正常叠加 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-10-N-S1 | main+stack同rg | 有active main订阅 | POST stack(main) | 409 |
| VM1-10-N-S2 | main+replace同rg | 有active main订阅 | POST replace(main) | 201, old=superseded |
| VM1-10-N-S3 | addon+stack | 有active addon订阅 | POST stack(addon) | 201, old continues |
| VM1-10-N-S4 | 验证superseded状态 | replace后 | 检查old订阅 | status=superseded |

---

### VM1-11-N: 开通-effective_at晚于expires_at

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家和已上架套餐

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2027-08-12",
  "expires_at": "2026-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 生效日期不能晚于到期日期

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-11-N-B1 | dates | effective > expires | 逻辑错误 | 422 | effective <= expires |
| VM1-11-N-B2 | dates | effective = expires | 同日 | 201 或 422 | 同日有效或无效 |
| VM1-11-N-B3 | dates | effective < expires | 正常 | 201 | 正常开通 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-11-N-S1 | effective晚于expires | 无 | POST(eff>exp) | 422 |
| VM1-11-N-S2 | effective早于expires | 无 | POST(eff<exp) | 201 |
| VM1-11-N-S3 | 同日 | 无 | POST(eff=exp) | 201 或 422 |

---

### VM1-12-N: 开通-金额异常

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家和已上架套餐, catalog_price_cents=98000

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 200000,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 金额异常
- paid_amount_cents > catalog_price_cents * 2

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-12-N-B1 | paid_amount_cents | catalog*2+1 | 超过2倍 | 422 | 金额异常 |
| VM1-12-N-B2 | paid_amount_cents | catalog*2 | 恰好2倍 | 201 或 422 | 边界值 |
| VM1-12-N-B3 | paid_amount_cents | catalog*2-1 | 低于2倍 | 201 | 正常 |
| VM1-12-N-B4 | paid_amount_cents | catalog | 等于目录价 | 201 | 正常 |
| VM1-12-N-B5 | paid_amount_cents | 0 (有remark) | 零金额 | 201 | 正常 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-12-N-S1 | 金额超过2倍 | catalog=98000 | POST(paid=200000) | 422, 金额异常 |
| VM1-12-N-S2 | 金额等于目录价 | catalog=98000 | POST(paid=98000) | 201 |
| VM1-12-N-S3 | 金额低于目录价 | catalog=98000 | POST(paid=50000, remark) | 201 |
| VM1-12-N-S4 | 零金额有备注 | catalog=98000 | POST(paid=0, remark) | 201 |

---

### VM1-13-N: 开通-零金额无备注

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家和已上架套餐

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 0,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 零金额或非目录价需备注说明

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-13-N-B1 | paid_amount_cents | 0 (无remark) | 零金额无备注 | 422 | 需备注 |
| VM1-13-N-B2 | paid_amount_cents | 0 (有remark) | 零金额有备注 | 201 | 正常开通 |
| VM1-13-N-B3 | paid_amount_cents | !=catalog (无remark) | 非目录价无备注 | 422 | 需备注 |
| VM1-13-N-B4 | paid_amount_cents | !=catalog (有remark) | 非目录价有备注 | 201 | 正常开通 |
| VM1-13-N-B5 | paid_amount_cents | =catalog (无remark) | 目录价无备注 | 201 | 正常开通 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-13-N-S1 | 零金额无备注 | 无 | POST(paid=0, 无remark) | 422 |
| VM1-13-N-S2 | 零金额有备注 | 无 | POST(paid=0, remark) | 201 |
| VM1-13-N-S3 | 非目录价无备注 | 无 | POST(paid≠catalog, 无remark) | 422 |
| VM1-13-N-S4 | 非目录价有备注 | 无 | POST(paid≠catalog, remark) | 201 |

---

### VM1-14-N: 续费衔接-日期计算

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 有 active 订阅, expires_at="2026-12-31"

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2027-01-01",
  "expires_at": "2027-12-31",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "purchase_mode": "renew_same"
}
```

**期望结果**:
- HTTP Status: 201
- new.effective_at = old.expires_at + 1 day = "2027-01-01"
- 续费衔接正确

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-14-N-B1 | effective_at | old.expires + 1 day | 正确衔接 | 201 | 续费衔接 |
| VM1-14-N-B2 | effective_at | old.expires (当天) | 重叠 | 422 或 409 | 日期重叠 |
| VM1-14-N-B3 | effective_at | old.expires - 1 day | 早于到期 | 422 或 409 | 日期冲突 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-14-N-S1 | 正确续费衔接 | old.exp=2026-12-31 | POST(eff=2027-01-01) | 201 |
| VM1-14-N-S2 | 续费日期重叠 | old.exp=2026-12-31 | POST(eff=2026-12-31) | 422 或 409 |
| VM1-14-N-S3 | 续费日期早于到期 | old.exp=2026-12-31 | POST(eff=2026-12-30) | 422 或 409 |

---

### VM1-15-N: expires_at标准化

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家和已上架套餐

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12T23:59:59",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 201
- expires_at 标准化为次日 00:00:00 (exclusive): "2027-08-13T00:00:00"
- inclusive → exclusive 转换

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-15-N-B1 | expires_at | "2027-08-12T23:59:59" | inclusive | 201 | 标准化为2027-08-13T00:00:00 |
| VM1-15-N-B2 | expires_at | "2027-08-12" | 日期only | 201 | 标准化为2027-08-13T00:00:00 |
| VM1-15-N-B3 | expires_at | "2027-08-13T00:00:00" | 已标准化 | 201 | 保持不变 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-15-N-S1 | inclusive转exclusive | 无 | POST(23:59:59) | expires标准化为次日00:00:00 |
| VM1-15-N-S2 | 日期only输入 | 无 | POST(日期only) | 标准化为次日00:00:00 |
| VM1-15-N-S3 | 验证标准化一致性 | 已创建 | 检查expires_at | 统一为exclusive格式 |

---

### VM1-16-N: 开通-商家非active

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 suspended 状态商家

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "suspended商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 商家状态非active

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-16-N-B1 | merchant.status | suspended | 非active | 409 | 商家状态非active |
| VM1-16-N-B2 | merchant.status | closed | 非active | 409 | 商家状态非active |
| VM1-16-N-B3 | merchant.status | active | 正常 | 201 | 正常开通 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-16-N-S1 | suspended商家开通 | status=suspended | POST subscription | 409 |
| VM1-16-N-S2 | closed商家开通 | status=closed | POST subscription | 409 |
| VM1-16-N-S3 | active商家开通 | status=active | POST subscription | 201 |

---

### VM1-17-N: 开通-套餐非public

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在套餐模板 is_public=false

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_PRIVATE",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 403 或 409
- Response Body 含错误信息: 套餐未上架

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-17-N-B1 | is_public | false | 未上架 | 403/409 | 套餐未上架 |
| VM1-17-N-B2 | is_public | true | 已上架 | 201 | 正常开通 |
| VM1-17-N-B3 | plan_label | 不存在的code | 不存在 | 404 | 套餐不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-17-N-S1 | 未上架套餐开通 | is_public=false | POST subscription | 403/409 |
| VM1-17-N-S2 | 已上架套餐开通 | is_public=true | POST subscription | 201 |
| VM1-17-N-S3 | 不存在的套餐 | 无此code | POST subscription | 404 |

---

### VM1-18-N: 开通-主体类型不匹配

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, entity_type=enterprise
- 存在已上架套餐, allowed_entity_types=["personal"]

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "enterprise商家UUID",
  "plan_label": "PL_PERSONAL_ONLY",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 主体类型不匹配

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-18-N-B1 | entity_type | enterprise, 套餐仅personal | 不匹配 | 409 | 主体类型不匹配 |
| VM1-18-N-B2 | entity_type | enterprise, 套餐含enterprise | 匹配 | 201 | 正常开通 |
| VM1-18-N-B3 | entity_type | personal, 套餐含all | 匹配 | 201 | 正常开通 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-18-N-S1 | enterprise商家+personal套餐 | 类型不匹配 | POST subscription | 409 |
| VM1-18-N-S2 | enterprise商家+enterprise套餐 | 类型匹配 | POST subscription | 201 |
| VM1-18-N-S3 | personal商家+all类型套餐 | 类型匹配 | POST subscription | 201 |

---

### VM1-19-N: 开通-store_quota指定

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家和已上架套餐

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "store_quota": 5
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `store_quota`=5

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-19-N-B1 | store_quota | 5 | 有效值 | 201 | 指定5个店铺 |
| VM1-19-N-B2 | store_quota | 1 | 默认值 | 201 | 默认1个 |
| VM1-19-N-B3 | store_quota | 不传 | 默认 | 201 | store_quota=1 |
| VM1-19-N-B4 | store_quota | 0 | 零值 | 422 或 201 | 零可能无效 |
| VM1-19-N-B5 | store_quota | -1 | 负值 | 422 | store_quota >= 0 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-19-N-S1 | 指定store_quota=5 | 无 | POST(store_quota=5) | 201, quota=5 |
| VM1-19-N-S2 | 不传store_quota | 无 | POST(无quota) | 201, quota=1 |
| VM1-19-N-S3 | store_quota=1 | 无 | POST(quota=1) | 201, quota=1 |

---

### VM1-20-N: 订阅状态-superseded

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 有 active main 订阅 (replace_group="main")
- 存在另一个 main 套餐模板, replace_group="main"

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_PRO",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 198000,
  "catalog_price_cents": 198000,
  "purchase_mode": "replace"
}
```

**期望结果**:
- HTTP Status: 201
- 新订阅 status=active
- 旧订阅 status=superseded (same replace_group)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-20-N-B1 | purchase_mode | replace (同rg) | 替换 | 201 | old→superseded |
| VM1-20-N-B2 | purchase_mode | stack (同rg, main) | 叠加 | 409 | main不可叠加 |
| VM1-20-N-B3 | purchase_mode | replace (不同rg) | 不同组 | 201 | 两者都active |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-20-N-S1 | replace同rg | 有active main(rg=main) | POST replace(main) | 201, old=superseded |
| VM1-20-N-S2 | 验证old状态 | replace后 | 检查old订阅 | status=superseded |
| VM1-20-N-S3 | 验证new状态 | replace后 | 检查new订阅 | status=active |

---

### VM1-21-N: 创建权益-重复类型

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在套餐模板已有 benefit_type="store_quota" 的权益

**API**: `POST /admin/shop/plans/{plan_id}/benefits`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "benefit_type": "store_quota",
  "value": 10,
  "display_name": "店铺配额2"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 权益类型已存在

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-21-N-B1 | benefit_type | 重复类型 | 已存在 | 409 | 权益类型已存在 |
| VM1-21-N-B2 | benefit_type | "new_type" | 新类型 | 201 | 正常创建 |
| VM1-21-N-B3 | benefit_type | "" | 空值 | 422 | 权益类型不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-21-N-S1 | 重复类型创建 | 已有store_quota | POST(store_quota) | 409 |
| VM1-21-N-S2 | 新类型创建 | 已有store_quota | POST(content_quota) | 201 |
| VM1-21-N-S3 | 空类型创建 | 无 | POST("") | 422 |

---

### VM1-22-N: 上架-allowed_entity_types校验

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在套餐模板, allowed_entity_types=["enterprise", "individual_business"]

**API**: `POST /admin/shop/plans/{plan_id}/publish`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- 上架后 allowed_entity_types 保持配置

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-22-N-B1 | allowed_entity_types | ["enterprise"] | 仅企业 | 200 | 正常上架 |
| VM1-22-N-B2 | allowed_entity_types | ["personal", "enterprise"] | 多类型 | 200 | 正常上架 |
| VM1-22-N-B3 | allowed_entity_types | [] (空) | 无限制 | 200 或 422 | 空可能表示全部 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-22-N-S1 | 仅enterprise上架 | allowed=["enterprise"] | POST publish | 200 |
| VM1-22-N-S2 | 多类型上架 | allowed=["personal","enterprise"] | POST publish | 200 |
| VM1-22-N-S3 | 验证开通时校验 | 已上架 | POST subscription(不匹配类型) | 409 |

---

### VM1-23-N: 已购plan_snapshot不变

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在已购订阅, plan_snapshot记录旧价格和能力
- 对应套餐模板已修改价格和能力

**API**: `GET /admin/shop/subscriptions/{subscription_id}`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- plan_snapshot 中的价格和能力保持购买时的值, 不随模板修改而变化

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-23-N-B1 | plan_snapshot.price | 旧价格 | 不变 | 200 | snapshot保持旧价 |
| VM1-23-N-B2 | plan_snapshot.benefits | 旧能力 | 不变 | 200 | snapshot保持旧能力 |
| VM1-23-N-B3 | template.price | 新价格 | 已变 | 200 | 模板价格为新价 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-23-N-S1 | 改价后检查snapshot | 模板改价 | GET subscription | snapshot价格=旧价 |
| VM1-23-N-S2 | 改能力后检查snapshot | 模板改能力 | GET subscription | snapshot能力=旧能力 |
| VM1-23-N-S3 | 新开通使用新价 | 模板改价 | POST subscription | 新订阅使用新价 |

---

### VM1-24-N: 开通-account_manager指定

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家和已上架套餐

**API**: `POST /admin/shop/subscriptions`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "active商家UUID",
  "plan_label": "PL_BASIC",
  "effective_at": "2026-08-12",
  "expires_at": "2027-08-12",
  "paid_amount_cents": 98000,
  "catalog_price_cents": 98000,
  "account_manager_user_id": "管理员UUID"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `account_manager_user_id`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-24-N-B1 | account_manager_user_id | 有效UUID | 正常 | 201 | 指定客户经理 |
| VM1-24-N-B2 | account_manager_user_id | 不传 | 可选 | 201 | 不指定 |
| VM1-24-N-B3 | account_manager_user_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM1-24-N-B4 | account_manager_user_id | 不存在的UUID | 不存在 | 201 或 404 | 可能不校验存在性 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-24-N-S1 | 指定客户经理 | 无 | POST(有manager) | 201, manager已指定 |
| VM1-24-N-S2 | 不指定客户经理 | 无 | POST(无manager) | 201, manager=null |
| VM1-24-N-S3 | 格式错误UUID | 无 | POST(invalid uuid) | 422 |

---

### VM1-25-N: 取消-非addon订阅

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 subscription_id=已知UUID 的 main 类型订阅, status=active

**API**: `POST /admin/shop/subscriptions/{subscription_id}/cancel`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason": "尝试取消主套餐"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 仅addon订阅可取消

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM1-25-N-B1 | type | main | 非addon | 409 | 仅addon可取消 |
| VM1-25-N-B2 | type | addon | addon | 200 | 正常取消 |
| VM1-25-N-B3 | type | main (expired) | 非active | 409 | 仅active可取消 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM1-25-N-S1 | 取消main订阅 | main+active | POST cancel | 409 |
| VM1-25-N-S2 | 取消addon订阅 | addon+active | POST cancel | 200 |
| VM1-25-N-S3 | 取消expired main | main+expired | POST cancel | 409 |

---

## M2 商家状态

### M2 商家状态变更

---

### VM2-1: 商家暂停

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 tenant_id=已知UUID 的 active 状态商家
- 该商家有至少 1 个 active 状态的店铺

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家违规操作需要暂停服务进行整改"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `status`="suspended"
- 数据库: merchant.status 变为 suspended
- 副作用: 该商家所有店铺状态变为 paused

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-1-B1 | reason_text | "" | 空值 | 422 | 暂停原因不能为空 |
| VM2-1-B2 | reason_text | "123" (3字) | 长度不足 | 422 | 至少4字 |
| VM2-1-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VM2-1-B4 | reason_text | "违规操作" (4字) | 最小有效 | 200 | 正常暂停 |
| VM2-1-B5 | reason_text | 不传 | 缺失 | 422 | 暂停原因不能为空 |
| VM2-1-B6 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VM2-1-B7 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM2-1-B8 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |
| VM2-1-B9 | reason_text | null | null值 | 422 | 暂停原因不能为空 |
| VM2-1-B10 | reason_text | "  违规操作  " (strip后4字) | strip后有效 | 200 | 正常暂停 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-1-S1 | 正常暂停active商家 | status=active | POST suspend | 200, status=suspended |
| VM2-1-S2 | 暂停已暂停商家 | status=suspended | POST suspend | 409, 商家已暂停 |
| VM2-1-S3 | 暂停已关闭商家 | status=closed | POST suspend | 409, 商家已关闭 |
| VM2-1-S4 | 验证店铺副作用 | 有active店铺 | POST suspend后检查 | 店铺状态变paused |
| VM2-1-S5 | 暂停后恢复 | suspended | POST resume | 200, status=active |

---

### VM2-2: 商家恢复

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 tenant_id=已知UUID 的 suspended 状态商家
- 该商家暂停前有 active 店铺, 暂停后变为 paused

**API**: `POST /admin/shop/merchants/{tenant_id}/resume`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `status`="active"
- 数据库: merchant.status 变为 active
- 注意: 店铺状态不自动恢复

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-2-B1 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VM2-2-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM2-2-B3 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-2-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |
| VM2-2-B5 | tenant_id | active商家 | 非suspended | 409 | 商家未暂停 |
| VM2-2-B6 | tenant_id | closed商家 | 终态 | 409 | 商家已关闭 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-2-S1 | 正常恢复suspended商家 | status=suspended | POST resume | 200, status=active |
| VM2-2-S2 | 恢复active商家 | status=active | POST resume | 409, 商家未暂停 |
| VM2-2-S3 | 恢复closed商家 | status=closed | POST resume | 409, 商家已关闭 |
| VM2-2-S4 | 验证店铺不自动恢复 | suspended+paused店铺 | POST resume后检查店铺 | 店铺仍为paused |
| VM2-2-S5 | 恢复后再次暂停 | active (恢复后) | POST suspend | 200, status=suspended |

---

### VM2-3: 商家关闭

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 tenant_id=已知UUID 的 active 状态商家
- 该商家有 active 店铺和 pending 续费申请

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家主动申请关闭账号，不再继续经营",
  "ack_irreversible": true
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `status`="closed"
- 数据库: merchant.status 变为 closed (终态)
- 副作用: 店铺变paused, 续费申请变cancelled, 永久阻断重新入驻

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-3-B1 | reason_text | "" | 空值 | 422 | 关闭原因不能为空 |
| VM2-3-B2 | reason_text | "123" (3字) | 长度不足 | 422 | 至少4字 |
| VM2-3-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VM2-3-B4 | reason_text | "商家关店" (4字) | 最小有效 | 200 | 正常关闭 |
| VM2-3-B5 | ack_irreversible | false | 未确认 | 422 | 请确认操作不可逆 |
| VM2-3-B6 | ack_irreversible | 不传 | 缺失 | 422 | 请确认操作不可逆 |
| VM2-3-B7 | ack_irreversible | true | 已确认 | 200 | 正常关闭 |
| VM2-3-B8 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VM2-3-B9 | reason_text | 不传 | 缺失 | 422 | 关闭原因不能为空 |
| VM2-3-B10 | ack_irreversible | null | null值 | 422 | 请确认操作不可逆 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-3-S1 | 正常关闭active商家 | status=active | POST close | 200, status=closed |
| VM2-3-S2 | 关闭suspended商家 | status=suspended | POST close | 200, status=closed |
| VM2-3-S3 | 关闭已关闭商家 | status=closed | POST close | 409, 商家已关闭 |
| VM2-3-S4 | 关闭后不可重开 | status=closed | POST resume/suspend | 409, 不可逆 |
| VM2-3-S5 | 关闭后不可重新入驻 | status=closed | POST onboarding | 409, 永久阻断 |
| VM2-3-S6 | 验证店铺副作用 | 有active店铺 | POST close后检查 | 店铺变paused |
| VM2-3-S7 | 验证续费申请副作用 | 有pending续费 | POST close后检查 | 续费变cancelled |

---

### VM2-4: 商家自主入驻提交

**前置条件**:
- 商家用户已登录 (13900000099), 获取 merchant_token
- 该用户关联的租户未入驻, 无待审申请
- 环境变量: WECHAT_PAY_MODE=stub

**API**: `POST /shop/onboarding/submit`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "entity_type": "enterprise",
  "legal_name": "商家自主入驻公司",
  "display_name": "自主入驻商家",
  "contact_name": "王五",
  "contact_mobile": "13800005555",
  "unified_social_credit_code": "91110000MA01MNO345",
  "legal_rep_name": "赵六",
  "bank_account_info": {},
  "qualification_files": {
    "business_license": "file_self_001"
  }
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id` (UUID), `status`="pending", `initiator`="merchant_self"
- 不传 tenant_id, 使用 active_tenant_id
- 数据库: onboarding_applications 新增记录, initiator=merchant_self

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-4-B1 | entity_type | "" | 空值 | 422 | 主体类型不能为空 |
| VM2-4-B2 | entity_type | "invalid" | 无效值 | 422 | 主体类型无效 |
| VM2-4-B3 | contact_mobile | "1380000555" (10位) | 格式错误 | 422 | 手机号格式不对 |
| VM2-4-B4 | contact_name | "" | 空值 | 422 | 联系人不能为空 |
| VM2-4-B5 | legal_name | "" | 空值 | 422 | 法定名称不能为空 |
| VM2-4-B6 | entity_type | "personal" (无id_no) | 缺字段 | 422 | 个人缺id_no |
| VM2-4-B7 | entity_type | "enterprise" (无credit_code) | 缺字段 | 422 | 非个人缺credit_code |
| VM2-4-B8 | entity_type | "enterprise" (无legal_rep) | 缺字段 | 422 | 非个人缺legal_rep_name |
| VM2-4-B9 | Authorization | 管理员 token | 角色不匹配 | 403 | 无shop权限 |
| VM2-4-B10 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-4-S1 | 正常自主入驻 | 未入驻租户 | POST submit | 201, initiator=merchant_self |
| VM2-4-S2 | 重复提交 | 已有pending申请 | POST submit | 409, 已有待审申请 |
| VM2-4-S3 | 已入驻再提交 | 已有merchant | POST submit | 409, 已入驻 |
| VM2-4-S4 | 驳回后重新提交 | 有rejected申请 | POST submit | 201, 新pending申请 |
| VM2-4-S5 | 验证不传tenant_id | 未入驻 | POST submit(无tenant_id) | 201, 使用active_tenant_id |

---

### VM2-5: 标签-添加标签

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 tenant_id=已知UUID 的 active 状态商家
- 标签名 "VIP客户" 在数据库中不存在 (需ops创建)

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["VIP客户", "重点商家"]
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tags` (数组, 含 "VIP客户" 和 "重点商家")
- 数据库: 创建新标签名 (如不存在), 关联到商家

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-5-B1 | tag_names[0] | "A" (1字) | 长度不足 | 422 | 标签名2-12字 |
| VM2-5-B2 | tag_names[0] | "这是一个超过十二个字的标签名" (13字) | 超长 | 422 | 标签名2-12字 |
| VM2-5-B3 | tag_names[0] | "AB" (2字) | 最小有效 | 200 | 正常添加 |
| VM2-5-B4 | tag_names[0] | "十二个字的标签名测试" (12字) | 最大有效 | 200 | 正常添加 |
| VM2-5-B5 | tag_names | [] (空数组) | 清空 | 200 | 清除所有标签 |
| VM2-5-B6 | tag_names | 21个标签 | 超出限制 | 422 | 每商家<=20标签 |
| VM2-5-B7 | tag_names[0] | "  VIP  " (strip后3字) | trim处理 | 200 | trim后"VIP" |
| VM2-5-B8 | Authorization | cs_token (无tag.manage) | 无权限 | 403 | 无tag.manage |
| VM2-5-B9 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VM2-5-B10 | tag_names[0] | "" | 空值 | 422 | 标签名不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-5-S1 | 正常添加标签 | 无标签 | PUT tags | 200, 添加2个标签 |
| VM2-5-S2 | 管家添加标签 | cs已登录 | PUT tags | 403, 无tag.manage |
| VM2-5-S3 | 添加21个标签 | 无标签 | PUT tags(21个) | 422, 超出限制 |
| VM2-5-S4 | 添加含新标签名 | 标签不存在 | PUT tags(新名) | 200, ops可创建新名 |
| VM2-5-S5 | trim处理 | 无 | PUT tags("  VIP  ") | 200, 存储为"VIP" |

---

### VM2-6: 标签-更新标签(全量覆盖)

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 tenant_id=已知UUID 的商家, 已有标签 ["VIP客户", "重点商家", "测试标签"]

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["VIP客户", "新标签"]
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tags`=["VIP客户", "新标签"]
- 全量覆盖: "重点商家"和"测试标签"被移除, "新标签"被添加
- 不是增量修改

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-6-B1 | tag_names | ["VIP客户"] (减少) | 部分覆盖 | 200 | 仅保留VIP客户 |
| VM2-6-B2 | tag_names | [] (空数组) | 清空 | 200 | 清除所有标签 |
| VM2-6-B3 | tag_names | ["VIP客户","新标签","A","B","C"] (增加) | 扩展 | 200 | 全量替换 |
| VM2-6-B4 | tag_names | ["VIP客户","VIP客户"] (重复) | 去重 | 200 | 去重后1个 |
| VM2-6-B5 | Authorization | cs_token | 无tag.manage | 403 | 无tag.manage权限 |
| VM2-6-B6 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-6-S1 | 全量覆盖减少标签 | 有3个标签 | PUT tags(1个) | 200, 仅保留1个 |
| VM2-6-S2 | 全量覆盖增加标签 | 有3个标签 | PUT tags(5个) | 200, 替换为5个 |
| VM2-6-S3 | 清空所有标签 | 有3个标签 | PUT tags([]) | 200, 无标签 |
| VM2-6-S4 | 验证非增量 | 有["A","B"] | PUT tags(["B","C"]) | 200, tags=["B","C"], A被移除 |
| VM2-6-S5 | 重复标签名去重 | 无 | PUT tags(["A","A"]) | 200, tags=["A"] |

---

### VM2-7: 标签-获取标签列表

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 tenant_id=已知UUID 的商家, 已有标签 ["VIP客户", "重点商家"]

**API**: `GET /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tags` (数组, 含 "VIP客户" 和 "重点商家")

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-7-B1 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VM2-7-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM2-7-B3 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-7-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |
| VM2-7-B5 | tenant_id | 无标签的商家 | 空标签 | 200 | tags=[] |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-7-S1 | 获取有标签的商家 | 有2个标签 | GET tags | 200, 返回2个标签 |
| VM2-7-S2 | 获取无标签的商家 | 无标签 | GET tags | 200, tags=[] |
| VM2-7-S3 | 获取不存在商家 | UUID不匹配 | GET tags | 404 |
| VM2-7-S4 | 跨租户标签隔离 | tenant_A有标签 | GET tenant_B/tags | tenant_B看不到A的标签 |

---

### VM2-8: 入驻状态查询

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户关联的租户有不同的入驻状态 (not_onboarded, pending, approved, rejected)

**API**: `GET /shop/onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status` (not_onboarded/pending/approved/rejected)
- 4 种状态之一

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-8-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-8-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无shop权限 |
| VM2-8-B3 | Authorization | 无效 token | 无效 | 401 | 令牌无效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-8-S1 | 未入驻状态 | 无merchant无申请 | GET status | 200, status=not_onboarded |
| VM2-8-S2 | 待审状态 | 有pending申请 | GET status | 200, status=pending |
| VM2-8-S3 | 已入驻状态 | merchant.status=active | GET status | 200, status=approved |
| VM2-8-S4 | 已驳回状态 | 有rejected申请 | GET status | 200, status=rejected |
| VM2-8-S5 | 驳回后重新提交 | rejected→新pending | GET status | 200, status=pending |

---

### VM2-9: 商家详情查询

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 tenant_id=已知UUID 的 active 状态商家

**API**: `GET /admin/shop/merchants/{tenant_id}`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tenant_id`, `tenant_name`, `status`, `plan_status`, `onboarding_status`, `entity_type`, `legal_name`, `contact_name`, `contact_mobile`, `tags`, `account_manager_user_id`, `created_at`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-9-B1 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |
| VM2-9-B2 | tenant_id | "not-a-uuid" | 格式错误 | 422 | UUID格式不正确 |
| VM2-9-B3 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-9-B4 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |
| VM2-9-B5 | tenant_id | 其他租户的商家 | 跨租户 | 200 或 403 | 取决于scope |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-9-S1 | 获取active商家详情 | status=active | GET /{tenant_id} | 200, 完整详情 |
| VM2-9-S2 | 获取suspended商家 | status=suspended | GET /{tenant_id} | 200, status=suspended |
| VM2-9-S3 | 获取closed商家 | status=closed | GET /{tenant_id} | 200, status=closed |
| VM2-9-S4 | 获取不存在商家 | UUID不匹配 | GET /{invalid_id} | 404 |
| VM2-9-S5 | 验证含标签信息 | 有标签 | 检查tags字段 | tags数组非空 |

---

### VM2-10: 商家列表查询

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 数据库中存在多个商家, 含不同状态

**API**: `GET /admin/shop/merchants?page=1&page_size=20`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items` (数组), `total` (int), `page`, `page_size`, `scope`
- items 中每个商家含: tenant_id, tenant_name, status, plan_status, onboarding_status

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-10-B1 | page | 0 | 最小值违规 | 422 | page >= 1 |
| VM2-10-B2 | page_size | 101 | 最大值违规 | 422 | page_size <= 100 |
| VM2-10-B3 | page_size | 100 | 最大有效 | 200 | 返回最多100条 |
| VM2-10-B4 | q | "测试" | 搜索词 | 200 | 返回匹配商家 |
| VM2-10-B5 | Authorization | 商家 token | 无权限 | 403 | 无管理权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-10-S1 | 默认查询 | 有数据 | GET /merchants | 200, page=1, page_size=20 |
| VM2-10-S2 | 搜索商家名称 | 有匹配 | GET ?q=测试 | 200, 匹配项 |
| VM2-10-S3 | 按状态筛选 | 有active | GET ?onboarding_status=active | 200, 仅active |
| VM2-10-S4 | 含未入驻租户 | 有未入驻 | GET ?include_not_onboarded=true | 200, 含未入驻 |
| VM2-10-S5 | 验证scope | 有数据 | 检查scope | 反映可见范围 |

---

### M2 新增测试用例

---

### VM2-1-N: 暂停-原因不足4字

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "违规"
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 暂停原因至少4字

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-1-N-B1 | reason_text | "" | 空值 | 422 | 暂停原因不能为空 |
| VM2-1-N-B2 | reason_text | "违规" (2字) | 长度不足 | 422 | 至少4字 |
| VM2-1-N-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VM2-1-N-B4 | reason_text | "违规操作" (4字) | 最小有效 | 200 | 正常暂停 |
| VM2-1-N-B5 | reason_text | "  违规操作  " (strip后4字) | strip后有效 | 200 | 正常暂停 |
| VM2-1-N-B6 | reason_text | 不传 | 缺失 | 422 | 暂停原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-1-N-S1 | 2字原因 | active商家 | POST suspend(2字) | 422 |
| VM2-1-N-S2 | 4字原因 | active商家 | POST suspend(4字) | 200 |
| VM2-1-N-S3 | 空原因 | active商家 | POST suspend("") | 422 |
| VM2-1-N-S4 | strip后不足 | active商家 | POST suspend("  ab  ") | 422 |

---

### VM2-2-N: 暂停-非active状态

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 suspended 和 closed 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "再次暂停操作测试"
}
```

**期望结果**:
- suspended商家: HTTP Status 409, 商家已暂停
- closed商家: HTTP Status 409, 商家已关闭

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-2-N-B1 | merchant.status | suspended | 已暂停 | 409 | 商家已暂停 |
| VM2-2-N-B2 | merchant.status | closed | 已关闭 | 409 | 商家已关闭 |
| VM2-2-N-B3 | merchant.status | active | 正常 | 200 | 正常暂停 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-2-N-S1 | 暂停已暂停商家 | status=suspended | POST suspend | 409 |
| VM2-2-N-S2 | 暂停已关闭商家 | status=closed | POST suspend | 409 |
| VM2-2-N-S3 | 暂停active商家 | status=active | POST suspend | 200 |

---

### VM2-3-N: 暂停-店铺自动暂停

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 有 2 个 active 店铺和 1 个 inactive 店铺

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "测试店铺自动暂停副作用"
}
```

**期望结果**:
- HTTP Status: 200
- 副作用: 所有 active 店铺变为 paused

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-3-N-B1 | store.status | active → paused | 自动暂停 | 200 | active店铺变paused |
| VM2-3-N-B2 | store.status | inactive (不变) | 非active | 200 | 非active店铺不变 |
| VM2-3-N-B3 | store.count | 2个active | 多店铺 | 200 | 全部变paused |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-3-N-S1 | 暂停后active店铺变paused | 有active店铺 | POST suspend | 店铺变paused |
| VM2-3-N-S2 | 暂停后inactive店铺不变 | 有inactive店铺 | POST suspend | 店铺状态不变 |
| VM2-3-N-S3 | 多个active店铺全部暂停 | 有2个active | POST suspend | 2个都变paused |

---

### VM2-4-N: 恢复-非suspended状态

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 和 closed 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/resume`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- active商家: HTTP Status 409, 商家未暂停
- closed商家: HTTP Status 409, 商家已关闭

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-4-N-B1 | merchant.status | active | 非suspended | 409 | 商家未暂停 |
| VM2-4-N-B2 | merchant.status | closed | 终态 | 409 | 商家已关闭 |
| VM2-4-N-B3 | merchant.status | suspended | 正常 | 200 | 正常恢复 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-4-N-S1 | 恢复active商家 | status=active | POST resume | 409 |
| VM2-4-N-S2 | 恢复closed商家 | status=closed | POST resume | 409 |
| VM2-4-N-S3 | 恢复suspended商家 | status=suspended | POST resume | 200 |

---

### VM2-5-N: 恢复-店铺不自动恢复

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 suspended 商家, 暂停前有 active 店铺, 暂停后变 paused

**API**: `POST /admin/shop/merchants/{tenant_id}/resume`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200, merchant.status=active
- 店铺状态不自动恢复, 仍为 paused

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-5-N-B1 | store.status | paused (恢复后不变) | 不自动恢复 | 200 | 店铺仍paused |
| VM2-5-N-B2 | merchant.status | active (恢复) | 商家恢复 | 200 | 商家变active |
| VM2-5-N-B3 | store.count | 多个paused店铺 | 多店铺 | 200 | 全部不恢复 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-5-N-S1 | 恢复后店铺仍paused | suspended+paused店铺 | POST resume | 店铺仍paused |
| VM2-5-N-S2 | 恢复后商家变active | suspended | POST resume | merchant=active |
| VM2-5-N-S3 | 需手动恢复店铺 | 恢复后 | 手动恢复店铺 | 店铺变active |

---

### VM2-6-N: 关闭-未确认不可逆

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家主动申请关闭账号",
  "ack_irreversible": false
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 请确认操作不可逆

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-6-N-B1 | ack_irreversible | false | 未确认 | 422 | 请确认操作不可逆 |
| VM2-6-N-B2 | ack_irreversible | 不传 | 缺失 | 422 | 请确认操作不可逆 |
| VM2-6-N-B3 | ack_irreversible | true | 已确认 | 200 | 正常关闭 |
| VM2-6-N-B4 | ack_irreversible | "true" (字符串) | 类型错误 | 422 | 布尔值类型错误 |
| VM2-6-N-B5 | ack_irreversible | null | null值 | 422 | 请确认操作不可逆 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-6-N-S1 | 未确认不可逆 | active商家 | POST close(ack=false) | 422 |
| VM2-6-N-S2 | 确认不可逆 | active商家 | POST close(ack=true) | 200 |
| VM2-6-N-S3 | 不传ack | active商家 | POST close(无ack) | 422 |

---

### VM2-7-N: 关闭-原因不足4字

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 状态商家

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "关店",
  "ack_irreversible": true
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 关闭原因至少4字

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-7-N-B1 | reason_text | "" | 空值 | 422 | 关闭原因不能为空 |
| VM2-7-N-B2 | reason_text | "关店" (2字) | 长度不足 | 422 | 至少4字 |
| VM2-7-N-B3 | reason_text | "  ab  " (strip后2字) | strip后不足 | 422 | strip后至少4字 |
| VM2-7-N-B4 | reason_text | "商家关店" (4字) | 最小有效 | 200 | 正常关闭 |
| VM2-7-N-B5 | reason_text | "  商家关店  " (strip后4字) | strip后有效 | 200 | 正常关闭 |
| VM2-7-N-B6 | reason_text | 不传 | 缺失 | 422 | 关闭原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-7-N-S1 | 2字原因 | active商家 | POST close(2字) | 422 |
| VM2-7-N-S2 | 4字原因 | active商家 | POST close(4字) | 200 |
| VM2-7-N-S3 | 空原因 | active商家 | POST close("") | 422 |
| VM2-7-N-S4 | strip后不足 | active商家 | POST close("  ab  ") | 422 |

---

### VM2-8-N: 关闭-closed不可重开

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 closed 状态商家 (终态)

**API**: `POST /admin/shop/merchants/{tenant_id}/resume`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 商家已关闭, 不可恢复

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-8-N-B1 | 操作 | POST resume | 恢复 | 409 | closed不可恢复 |
| VM2-8-N-B2 | 操作 | POST suspend | 暂停 | 409 | closed不可暂停 |
| VM2-8-N-B3 | 操作 | POST close | 再次关闭 | 409 | closed已关闭 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-8-N-S1 | closed恢复 | status=closed | POST resume | 409 |
| VM2-8-N-S2 | closed暂停 | status=closed | POST suspend | 409 |
| VM2-8-N-S3 | closed再关闭 | status=closed | POST close | 409 |
| VM2-8-N-S4 | closed重新入驻 | status=closed | POST onboarding | 409, 永久阻断 |

---

### VM2-9-N: 关闭-店铺自动暂停

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 有 2 个 active 店铺

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家主动关闭店铺经营",
  "ack_irreversible": true
}
```

**期望结果**:
- HTTP Status: 200
- 副作用: 所有 active 店铺变为 paused

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-9-N-B1 | store.status | active → paused | 自动暂停 | 200 | 店铺变paused |
| VM2-9-N-B2 | store.status | inactive (不变) | 非active | 200 | 不变 |
| VM2-9-N-B3 | store.count | 2个active | 多店铺 | 200 | 全部变paused |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-9-N-S1 | 关闭后active店铺变paused | 有active店铺 | POST close | 店铺变paused |
| VM2-9-N-S2 | 关闭后inactive不变 | 有inactive | POST close | 不变 |
| VM2-9-N-S3 | 多个active全暂停 | 有2个active | POST close | 2个都变paused |

---

### VM2-10-N: 关闭-续费申请取消

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 有 pending 和 processing 续费申请

**API**: `POST /admin/shop/merchants/{tenant_id}/close`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_text": "商家关闭账号停止经营",
  "ack_irreversible": true
}
```

**期望结果**:
- HTTP Status: 200
- 副作用: pending 和 processing 续费申请变为 cancelled

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-10-N-B1 | renewal.status | pending → cancelled | 自动取消 | 200 | 续费变cancelled |
| VM2-10-N-B2 | renewal.status | processing → cancelled | 自动取消 | 200 | 续费变cancelled |
| VM2-10-N-B3 | renewal.status | approved (不变) | 已完成 | 200 | 不受影响 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-10-N-S1 | 关闭后pending变cancelled | 有pending | POST close | 续费变cancelled |
| VM2-10-N-S2 | 关闭后processing变cancelled | 有processing | POST close | 续费变cancelled |
| VM2-10-N-S3 | 关闭后approved不变 | 有approved | POST close | 不变 |

---

### VM2-11-N: 关闭-永久阻断重新入驻

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 closed 状态商家的租户

**API**: `POST /admin/shop/onboarding/applications`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tenant_id": "已关闭商家的租户UUID",
  "entity_type": "enterprise",
  "legal_name": "新公司名称",
  "contact_name": "新联系人",
  "contact_mobile": "13800006666",
  "unified_social_credit_code": "91110000MA01PQR456",
  "legal_rep_name": "新法人"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 该租户已入驻 / 租户永久阻断

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-11-N-B1 | tenant.status | closed | 永久阻断 | 409 | 永久阻断 |
| VM2-11-N-B2 | tenant.status | active | 已入驻 | 409 | 已入驻 |
| VM2-11-N-B3 | tenant.status | 未入驻 | 可入驻 | 201 | 正常创建 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-11-N-S1 | closed租户重新入驻 | status=closed | POST application | 409 |
| VM2-11-N-S2 | closed租户在tenant-options排除 | status=closed | GET /tenant-options | 不含该租户 |
| VM2-11-N-S3 | 验证permanent block | status=closed | 检查数据库 | 有permanent_block标记 |

---

### VM2-12-N: 自主入驻-重复提交

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户已有 pending 状态的入驻申请

**API**: `POST /shop/onboarding/submit`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "entity_type": "enterprise",
  "legal_name": "重复提交公司",
  "contact_name": "张三",
  "contact_mobile": "13800007777",
  "unified_social_credit_code": "91110000MA01STU789",
  "legal_rep_name": "李四"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 已有待审入驻申请

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-12-N-B1 | existing | pending | 重复提交 | 409 | 已有待审申请 |
| VM2-12-N-B2 | existing | rejected | 可重新提交 | 201 | 驳回后可重新 |
| VM2-12-N-B3 | existing | approved | 已入驻 | 409 | 已入驻 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-12-N-S1 | 有pending再提交 | 有pending | POST submit | 409 |
| VM2-12-N-S2 | rejected后重新提交 | 有rejected | POST submit | 201 |
| VM2-12-N-S3 | 无申请首次提交 | 无申请 | POST submit | 201 |

---

### VM2-13-N: 自主入驻-已入驻

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户关联的租户已入驻 (merchant.status=active)

**API**: `POST /shop/onboarding/submit`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "entity_type": "enterprise",
  "legal_name": "已入驻公司",
  "contact_name": "张三",
  "contact_mobile": "13800008888",
  "unified_social_credit_code": "91110000MA01VWX012",
  "legal_rep_name": "李四"
}
```

**期望结果**:
- HTTP Status: 409
- Response Body 含错误信息: 该租户已入驻

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-13-N-B1 | merchant.status | active | 已入驻 | 409 | 已入驻 |
| VM2-13-N-B2 | merchant.status | 无merchant | 未入驻 | 201 | 正常创建 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-13-N-S1 | 已入驻再提交 | status=active | POST submit | 409 |
| VM2-13-N-S2 | 未入驻提交 | 无merchant | POST submit | 201 |

---

### VM2-14-N: 自主入驻-驳回后重新提交

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户有 rejected 状态的入驻申请

**API**: `POST /shop/onboarding/submit`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "entity_type": "enterprise",
  "legal_name": "修正后公司名称",
  "contact_name": "张三",
  "contact_mobile": "13800009999",
  "unified_social_credit_code": "91110000MA01YZA345",
  "legal_rep_name": "李四",
  "qualification_files": {
    "business_license": "file_resubmit_001"
  }
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `status`="pending"
- 新的 pending 申请创建, 旧 rejected 申请保留

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-14-N-B1 | existing | rejected | 可重新 | 201 | 新pending |
| VM2-14-N-B2 | existing | pending | 不可重复 | 409 | 已有待审 |
| VM2-14-N-B3 | existing | approved | 已入驻 | 409 | 已入驻 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-14-N-S1 | rejected后重新提交 | 有rejected | POST submit | 201, 新pending |
| VM2-14-N-S2 | 验证旧申请保留 | 有rejected | 检查旧申请 | rejected状态保留 |
| VM2-14-N-S3 | 新申请status=pending | rejected后 | 检查新申请 | status=pending |

---

### VM2-15-N: 入驻状态-not_onboarded

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户关联的租户无 merchant 记录, 无入驻申请

**API**: `GET /shop/onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status`="not_onboarded"

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-15-N-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-15-N-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无shop权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-15-N-S1 | 未入驻状态 | 无merchant无申请 | GET status | 200, not_onboarded |
| VM2-15-N-S2 | 验证可提交入驻 | not_onboarded | POST submit | 201 |
| VM2-15-N-S3 | 未入驻时无merchant数据 | not_onboarded | GET /shop/permissions/me | 200, 空权限 |

---

### VM2-16-N: 入驻状态-pending

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户有 pending 状态的入驻申请

**API**: `GET /shop/onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status`="pending"

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-16-N-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-16-N-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无shop权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-16-N-S1 | 待审状态 | 有pending申请 | GET status | 200, status=pending |
| VM2-16-N-S2 | pending时不可重复提交 | 有pending | POST submit | 409 |
| VM2-16-N-S3 | pending被审批后变approved | pending→approve | GET status | 200, status=approved |

---

### VM2-17-N: 入驻状态-approved

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户关联的租户已入驻, merchant.status=active

**API**: `GET /shop/onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status`="approved"

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-17-N-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-17-N-S1 | 已入驻状态 | merchant.status=active | GET status | 200, status=approved |
| VM2-17-N-S2 | approved时不可再提交 | status=approved | POST submit | 409, 已入驻 |
| VM2-17-N-S3 | approved后有shop权限 | status=approved | GET /shop/permissions/me | 200, 有权限 |

---

### VM2-18-N: 入驻状态-rejected

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户有 rejected 状态的入驻申请 (最新申请为rejected)

**API**: `GET /shop/onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status`="rejected"

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-18-N-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-18-N-S1 | 已驳回状态 | 有rejected申请 | GET status | 200, status=rejected |
| VM2-18-N-S2 | rejected后可重新提交 | status=rejected | POST submit | 201, 新pending |
| VM2-18-N-S3 | rejected后重新提交状态变pending | rejected→新pending | GET status | 200, status=pending |

---

### VM2-19-N: 默认预填-contact_name/mobile/display_name

**前置条件**:
- 商家用户已登录, 获取 merchant_token
- 该用户关联的租户有 contact_name, contact_mobile, display_name 数据
- 租户未入驻

**API**: `GET /shop/onboarding/prefill` (或等效商家端预填接口)
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含从租户数据预填的: `contact_name`, `contact_mobile`, `display_name`
- 字段值与租户数据一致

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-19-N-B1 | Authorization | 无 Header | 未认证 | 401 | 未提供认证令牌 |
| VM2-19-N-B2 | Authorization | 管理员 token | 角色不匹配 | 403 | 无shop权限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-19-N-S1 | 预填contact_name | 租户有contact_name | GET prefill | contact_name已预填 |
| VM2-19-N-S2 | 预填contact_mobile | 租户有contact_mobile | GET prefill | contact_mobile已预填 |
| VM2-19-N-S3 | 预填display_name | 租户有display_name | GET prefill | display_name已预填 |
| VM2-19-N-S4 | 无租户数据时预填空 | 租户无数据 | GET prefill | 字段为空或null |

---

### VM2-20-N: 标签-名称不足2字

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 active 状态商家

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["A"]
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 标签名长度需2-12字

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-20-N-B1 | tag_names[0] | "A" (1字) | 长度不足 | 422 | 标签名2-12字 |
| VM2-20-N-B2 | tag_names[0] | "" (0字) | 空值 | 422 | 标签名不能为空 |
| VM2-20-N-B3 | tag_names[0] | "AB" (2字) | 最小有效 | 200 | 正常添加 |
| VM2-20-N-B4 | tag_names[0] | "  A  " (strip后1字) | strip后不足 | 422 | trim后2-12字 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-20-N-S1 | 1字标签名 | 无标签 | PUT tags(1字) | 422 |
| VM2-20-N-S2 | 2字标签名 | 无标签 | PUT tags(2字) | 200 |
| VM2-20-N-S3 | 空标签名 | 无标签 | PUT tags("") | 422 |

---

### VM2-21-N: 标签-名称超过12字

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 active 状态商家

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["这是一个超过十二个字的标签名称测试"]
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 标签名长度需2-12字

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-21-N-B1 | tag_names[0] | "这是一个超过十二个字的标签名" (13字) | 超长 | 422 | 标签名2-12字 |
| VM2-21-N-B2 | tag_names[0] | "十二个字的标签名测试" (10字) | 有效 | 200 | 正常添加 |
| VM2-21-N-B3 | tag_names[0] | "十二个字的标签名测试啊" (12字) | 最大有效 | 200 | 正常添加 |
| VM2-21-N-B4 | tag_names[0] | "  十二个字的标签名测试  " (strip后10字) | trim后有效 | 200 | trim后正常 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-21-N-S1 | 13字标签名 | 无标签 | PUT tags(13字) | 422 |
| VM2-21-N-S2 | 12字标签名 | 无标签 | PUT tags(12字) | 200 |
| VM2-21-N-S3 | 10字标签名 | 无标签 | PUT tags(10字) | 200 |

---

### VM2-22-N: 标签-单商家超过20个

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 active 状态商家, 已有 15 个标签

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["标签1", "标签2", "标签3", "标签4", "标签5", "标签6", "标签7", "标签8", "标签9", "标签10", "标签11", "标签12", "标签13", "标签14", "标签15", "标签16", "标签17", "标签18", "标签19", "标签20", "标签21"]
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息: 每商家最多20个标签

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-22-N-B1 | tag_names | 21个标签 | 超出限制 | 422 | 每商家<=20标签 |
| VM2-22-N-B2 | tag_names | 20个标签 | 最大有效 | 200 | 正常添加 |
| VM2-22-N-B3 | tag_names | 19个标签 | 有效 | 200 | 正常添加 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-22-N-S1 | 21个标签 | 无标签 | PUT tags(21个) | 422 |
| VM2-22-N-S2 | 20个标签 | 无标签 | PUT tags(20个) | 200 |
| VM2-22-N-S3 | 全量覆盖到21个 | 有15个 | PUT tags(21个) | 422 |

---

### VM2-23-N: 标签-全量覆盖验证

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在商家已有标签 ["A", "B", "C"]

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["B", "D"]
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `tags`=["B", "D"]
- "A"和"C"被移除 (全量覆盖, 非增量)
- "D"被添加

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-23-N-B1 | tag_names | ["B","D"] (部分新部分旧) | 全量覆盖 | 200 | A/C移除, D添加 |
| VM2-23-N-B2 | tag_names | [] (空) | 清空 | 200 | 全部移除 |
| VM2-23-N-B3 | tag_names | ["A","B","C","D"] (增量) | 扩展 | 200 | 添加D, 保留ABC |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-23-N-S1 | 全量覆盖部分保留 | 有["A","B","C"] | PUT tags(["B","D"]) | tags=["B","D"] |
| VM2-23-N-S2 | 全量覆盖清空 | 有["A","B","C"] | PUT tags([]) | tags=[] |
| VM2-23-N-S3 | 验证非增量patch | 有["A","B"] | PUT tags(["B","C"]) | A被移除, C被添加 |

---

### VM2-24-N: 标签-仅运营可创建新标签名

**前置条件**:
- platform_shop_ops 已登录, 获取 ops_token
- platform_shop_cs 已登录, 获取 cs_token
- 标签名 "全新标签" 在数据库中不存在

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token 或 cs_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["全新标签"]
}
```

**期望结果**:
- ops_token: HTTP Status 200 (有 tag.manage 权限, 可创建新标签名)
- cs_token: HTTP Status 403 (无 tag.manage 权限, 不能创建新标签名)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-24-N-B1 | token | ops_token | 有tag.manage | 200 | 可创建新标签名 |
| VM2-24-N-B2 | token | cs_token | 无tag.manage | 403 | 不能创建新标签名 |
| VM2-24-N-B3 | token | finance_token | 无tag.manage | 403 | 不能创建新标签名 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-24-N-S1 | ops创建新标签名 | 标签不存在 | PUT tags(ops, 新名) | 200, 创建成功 |
| VM2-24-N-S2 | cs创建新标签名 | 标签不存在 | PUT tags(cs, 新名) | 403, 无tag.manage |
| VM2-24-N-S3 | cs使用已有标签名 | 标签已存在 | PUT tags(cs, 已有名) | 200, 可使用已有 |
| VM2-24-N-S4 | 验证ops权限 | ops已登录 | GET /admin/shop/permissions/me | 含tag.manage |

---

### VM2-25-N: 标签-管家无tag.manage

**前置条件**:
- platform_shop_cs 已登录, 获取 cs_token
- 标签名 "VIP客户" 已存在 (由ops创建)
- 标签名 "新标签" 不存在

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {cs_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["VIP客户", "新标签"]
}
```

**期望结果**:
- 如果请求中包含不存在的标签名: HTTP Status 403
- 如果全部为已有标签名: HTTP Status 200

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-25-N-B1 | tag_names | ["VIP客户"] (已有) | 已有名 | 200 | cs可使用已有标签 |
| VM2-25-N-B2 | tag_names | ["新标签"] (不存在) | 新名 | 403 | cs不能创建新名 |
| VM2-25-N-B3 | tag_names | ["VIP客户","新标签"] | 混合 | 403 | 含新名, 拒绝 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-25-N-S1 | cs使用已有标签 | VIP已存在 | PUT tags(cs, ["VIP"]) | 200 |
| VM2-25-N-S2 | cs创建新标签 | 新名不存在 | PUT tags(cs, ["新"]) | 403 |
| VM2-25-N-S3 | cs混合使用 | 有已有+新 | PUT tags(cs, 混合) | 403 |
| VM2-25-N-S4 | 验证cs有merchant.tag | cs已登录 | GET /admin/shop/permissions/me | 含merchant.tag, 不含tag.manage |

---

### VM2-26-N: 标签名称trim处理

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 active 状态商家

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["  VIP客户  "]
}
```

**期望结果**:
- HTTP Status: 200
- 标签名 trim 后存储为 "VIP客户" (去除前后空格)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-26-N-B1 | tag_names[0] | "  VIP  " (strip后3字) | trim后有效 | 200 | 存储为"VIP" |
| VM2-26-N-B2 | tag_names[0] | "VIP客户" (无空格) | 无空格 | 200 | 存储为"VIP客户" |
| VM2-26-N-B3 | tag_names[0] | "  A  " (strip后1字) | trim后不足 | 422 | trim后1字不足 |
| VM2-26-N-B4 | tag_names[0] | "   " (strip后0字) | trim后空 | 422 | trim后为空 |
| VM2-26-N-B5 | tag_names | ["VIP", "  VIP  "] | trim后重复 | 200 | 去重后1个"VIP" |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-26-N-S1 | 前后空格trim | 无 | PUT tags("  VIP  ") | 存储为"VIP" |
| VM2-26-N-S2 | trim后长度校验 | 无 | PUT tags("  A  ") | 422, trim后1字 |
| VM2-26-N-S3 | trim后去重 | 无 | PUT tags(["VIP","  VIP  "]) | 去重后1个 |
| VM2-26-N-S4 | 全空格标签 | 无 | PUT tags("   ") | 422, trim后为空 |

---

### VM2-27-N: 标签名称全局复用

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在商家 A 已有标签 "VIP客户"
- 存在商家 B 无标签

**API**: `PUT /admin/shop/merchants/{tenant_B_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["VIP客户"]
}
```

**期望结果**:
- HTTP Status: 200
- 商家 B 添加标签 "VIP客户"
- "VIP客户" 标签名全局复用 (UK约束在name上, 多个商家可关联同一标签名)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-27-N-B1 | tag_name | "VIP客户" (已被A使用) | 全局复用 | 200 | B也可使用 |
| VM2-27-N-B2 | tag_name | "新标签" (不存在) | 新创建 | 200 | ops创建新名 |
| VM2-27-N-B3 | tag_name | "vip客户" (大小写不同) | 大小写 | 200 或 409 | 取决于是否大小写敏感 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-27-N-S1 | 商家B使用A的标签名 | A有"VIP客户" | PUT tags(B, ["VIP客户"]) | 200, 全局复用 |
| VM2-27-N-S2 | 验证标签名UK | A和B都有"VIP客户" | 检查数据库 | tag_names表1条, merchant_tags表2条 |
| VM2-27-N-S3 | 多商家使用同标签 | A,B,C都用 | PUT tags(C, ["VIP客户"]) | 200 |

---

### VM2-28-N: 跨租户标签隔离

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 商家 A 有标签 ["VIP客户", "重点商家"]
- 商家 B 有标签 ["普通客户"]

**API**: `GET /admin/shop/merchants/{tenant_A_id}/tags`
**Headers**: `Authorization: Bearer {admin_token}`

**请求体**: 无

**期望结果**:
- 获取 A 的标签: ["VIP客户", "重点商家"]
- 获取 B 的标签: ["普通客户"]
- 两个商家的标签互不影响

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-28-N-B1 | tenant_id | tenant_A | 获取A标签 | 200 | 返回A的标签 |
| VM2-28-N-B2 | tenant_id | tenant_B | 获取B标签 | 200 | 返回B的标签 |
| VM2-28-N-B3 | tenant_id | 不存在的UUID | 不存在 | 404 | 商家不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-28-N-S1 | 获取A标签 | A有2个标签 | GET A/tags | ["VIP客户","重点商家"] |
| VM2-28-N-S2 | 获取B标签 | B有1个标签 | GET B/tags | ["普通客户"] |
| VM2-28-N-S3 | 修改A标签不影响B | A,B各有标签 | PUT A/tags后GET B/tags | B标签不变 |
| VM2-28-N-S4 | 同名标签跨租户 | A,B都有"VIP客户" | 分别GET | 各自独立关联 |

---

### VM2-29-N: 标签名称含特殊字符

**前置条件**:
- 平台管理员 (platform_shop_ops) 已登录, 获取 ops_token
- 存在 active 状态商家

**API**: `PUT /admin/shop/merchants/{tenant_id}/tags`
**Headers**: `Authorization: Bearer {ops_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "tag_names": ["VIP-客户"]
}
```

**期望结果**:
- HTTP Status: 200 (如允许特殊字符)
- 标签名 "VIP-客户" 被存储

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-29-N-B1 | tag_names[0] | "VIP-客户" (含连字符) | 特殊字符 | 200 或 422 | 取决于是否允许 |
| VM2-29-N-B2 | tag_names[0] | "VIP_客户" (含下划线) | 特殊字符 | 200 或 422 | 取决于是否允许 |
| VM2-29-N-B3 | tag_names[0] | "VIP客户1" (含数字) | 含数字 | 200 | 正常添加 |
| VM2-29-N-B4 | tag_names[0] | "VIP 客户" (含空格) | 含空格 | 200 或 422 | 取决于是否允许 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-29-N-S1 | 含连字符标签 | 无 | PUT tags("VIP-客户") | 200 或 422 |
| VM2-29-N-S2 | 含数字标签 | 无 | PUT tags("VIP客户1") | 200 |
| VM2-29-N-S3 | 含空格标签 | 无 | PUT tags("VIP 客户") | 200 或 422 |

---

### VM2-30-N: 暂停/恢复状态聚合

**前置条件**:
- 平台管理员已登录, 获取 admin_token
- 存在 active 商家, 执行暂停后恢复的完整流程

**API**: `POST /admin/shop/merchants/{tenant_id}/suspend` → `POST .../resume`
**Headers**: `Authorization: Bearer {admin_token}`, `Content-Type: application/json`

**请求体** (suspend):
```json
{
  "reason_text": "测试暂停恢复完整流程"
}
```

**期望结果**:
- 暂停: status=suspended, 店铺变paused
- 恢复: status=active, 店铺仍paused (不自动恢复)
- 商家列表中状态正确反映

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM2-30-N-B1 | flow | active→suspend→resume | 完整流程 | 200 | 各步骤成功 |
| VM2-30-N-B2 | flow | active→suspend→suspend | 重复暂停 | 409 | 已暂停 |
| VM2-30-N-B3 | flow | active→suspend→resume→suspend | 再次暂停 | 200 | 可再次暂停 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM2-30-N-S1 | 暂停后恢复 | active | suspend→resume | status=active, 店铺仍paused |
| VM2-30-N-S2 | 暂停后列表状态 | suspended | GET /merchants | onboarding_status=suspended |
| VM2-30-N-S3 | 恢复后列表状态 | active (恢复后) | GET /merchants | onboarding_status=active |
| VM2-30-N-S4 | 多次暂停恢复 | active | suspend→resume→suspend→resume | 最终status=active |
| VM2-30-N-S5 | 暂停后关闭 | suspended | suspend→close | status=closed (终态) |

---

## 附录: 测试用例统计

| 模块 | 现有用例 | 新增用例 | 边界值变体 | 业务场景 | 总计 |
|------|---------|---------|-----------|---------|------|
| M0 权限入驻 | VS-1 ~ VS-30 (30) | VS-1-N ~ VS-30-N (30) | ~250 | ~130 | ~60 用例 |
| M1 套餐订阅 | VM1-1 ~ VM1-10 (10) | VM1-1-N ~ VM1-25-N (25) | ~130 | ~80 | ~35 用例 |
| M2 商家状态 | VM2-1 ~ VM2-10 (10) | VM2-1-N ~ VM2-30-N (30) | ~150 | ~120 | ~40 用例 |
| **合计** | **50** | **85** | **~530** | **~330** | **~135 用例** |

---

> **文档结束**
> 本文档覆盖 M0 权限入驻、M1 套餐订阅、M2 商家状态三个模块的 Round 1 后端 API 测试用例。
> 所有测试用例均包含前置条件、API 路径、请求体、期望结果、边界值测试和业务场景测试。
> 测试环境: WECHAT_PAY_MODE=stub
> 平台管理员: 13800000000 / admin123456
> 商家用户: 13900000099 / test123456
---
# 内容获客商城 Phase 1 — Round 1 后端 API 测试用例

## 文档信息

| 项目 | 说明 |
|------|------|
| 模块 | M4 商品内容 + M5 订单权益 |
| 轮次 | Round 1（后端 API 级别） |
| 执行者 | Cursor AI 自动化执行 |
| 日期 | 2026-08-12 |
| 版本 | v1.0 |

---

## 通用前置条件

### 测试账号

| 角色 | 手机号 | 密码 | 说明 |
|------|--------|------|------|
| 商家A | 13900000099 | test123456 | tenant_id=TENANT_A, status=active |
| 商家B | 13900000088 | test123456 | tenant_id=TENANT_B, status=active |
| 买家A | 13800000001 | test123456 | buyer_id=BUYER_A |
| 买家B | 13800000002 | test123456 | buyer_id=BUYER_B |

### 登录获取 Token

**API**: `POST {base_url}/auth/login`

```json
{
  "mobile": "13900000099",
  "password": "test123456"
}
```

响应中获取 `merchant_token`（商家）或 `buyer_token`（买家）。

### 公共变量说明

| 变量名 | 说明 |
|--------|------|
| `{base_url}` | API 基础地址，如 `http://localhost:3000` |
| `{merchant_token}` | 商家A 的 Bearer Token |
| `{merchant_token_b}` | 商家B 的 Bearer Token |
| `{buyer_token}` | 买家A 的 Bearer Token |
| `{tenant_id}` | 商家A 租户 ID = TENANT_A |
| `{tenant_id_b}` | 商家B 租户 ID = TENANT_B |
| `{store_id}` | 商家A 店铺 ID |
| `{store_id_b}` | 商家B 店铺 ID |
| `{column_id}` | 已发布专栏 ID |
| `{digital_package_id}` | 已发布资料包 ID |
| `{service_offer_id}` | 已发布服务 ID |
| `{product_id}` | 商品 ID |
| `{buyer_id}` | 买家A ID = BUYER_A |
| `{order_id}` | 订单 ID |
| `{entitlement_id}` | 权益 ID |
| `{client_token}` | 客户端幂等 UUID |

### 数据库检查约定

所有"数据库"检查项默认通过直接 SQL 查询验证，表名和字段名以 PRD 定义为准。测试执行时应连接测试数据库执行验证 SQL。

---

# M4 商品内容

## M4 测试用例总览

| 用例ID | 标题 | 类型 | 优先级 |
|--------|------|------|--------|
| VM4-1 | 创建课程商品 | 正向+边界 | P0 |
| VM4-2 | 创建资料包商品 | 正向+边界 | P0 |
| VM4-3 | 创建服务商品 | 正向+边界 | P0 |
| VM4-4 | 商品编辑（状态校验） | 正向+边界 | P0 |
| VM4-5 | 商品提审 | 正向+边界 | P0 |
| VM4-6 | 商品上架 | 正向+边界 | P0 |
| VM4-7 | 商品下架 | 正向+边界 | P1 |
| VM4-8 | 多店隔离 | 场景 | P0 |
| VM4-9 | 专栏创建与发布 | 正向+边界 | P0 |
| VM4-10 | 课时创建（视频/图文） | 正向+边界 | P0 |
| VM4-11 | 试看设置 | 正向+边界 | P1 |
| VM4-12 | 资料包创建与校验 | 正向+边界 | P0 |
| VM4-1-N1 | 价格边界综合测试 | 边界 | P0 |
| VM4-1-N2 | 商品字段必填校验 | 边界 | P0 |
| VM4-1-N3 | 商品列表查询 | 正向+边界 | P1 |
| VM4-1-N4 | 商品详情查询 | 正向+边界 | P1 |
| VM4-4-N1 | 商品状态机非法转换 | 边界 | P0 |
| VM4-4-N2 | 权限校验（跨租户/非商家） | 场景 | P0 |
| VM4-5-N1 | 机审规则测试（stub 模式） | 场景 | P1 |
| VM4-5-N2 | 提审前置校验 | 边界 | P0 |
| VM4-5-N3 | 提审次数限制 | 边界 | P1 |
| VM4-6-N1 | 上架商品数上限 | 边界 | P1 |
| VM4-6-N2 | 非 approved 状态上架拒绝 | 边界 | P0 |
| VM4-7-N1 | 下架后再上架 | 场景 | P1 |
| VM4-8-N1 | 跨店商品查询隔离 | 场景 | P0 |
| VM4-9-N1 | 专栏下架不可再发布 | 边界 | P0 |
| VM4-10-N1 | 视频课时校验 | 边界 | P0 |
| VM4-10-N2 | 图文课时校验 | 边界 | P0 |
| VM4-10-N3 | 课时下架再发布 | 场景 | P1 |
| VM4-12-N1 | online_view 硬校验 | 边界 | P0 |
| VM4-12-N2 | online_view 软校验 | 边界 | P1 |
| VM4-3-N1 | 次数卡字段校验 | 边界 | P0 |

---

### VM4-1: 创建课程商品

**前置条件**:
- 商家A 已入驻且 status=active（tenant_id=TENANT_A, merchant_token 已获取）
- 已创建至少 1 个店铺（store_id）
- 已创建专栏 + 3 课时（1 试看），专栏状态为 published
- 专栏 ID = {column_id}

**API**: `POST {base_url}/shop/products`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "store_id": "{store_id}",
  "type": "course",
  "name": "测试课程商品",
  "subtitle": "面向初学者的系统课程",
  "price_cents": 9900,
  "line_price_cents": 19900,
  "ref_type": "column",
  "ref_id": "{column_id}",
  "refund_policy": "always_allow"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `status="draft"`, `type="course"`, `name="测试课程商品"`, `price_cents=9900`, `line_price_cents=19900`, `ref_type="column"`, `ref_id="{column_id}"`
- 数据库: `shop_products` 新增 1 条 `status=draft` 记录，`tenant_id=TENANT_A`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-1-B1 | name | "" | 空值 | 422 | 商品名不能为空 |
| VM4-1-B2 | name | null | 空值 | 422 | 商品名不能为 null |
| VM4-1-B3 | name | "a".repeat(256) | 超长 | 422 | 商品名超 255 字符 |
| VM4-1-B4 | price_cents | 0 | 最小值 | 422/201 | 验证是否允许 0 元（需确认 PRD） |
| VM4-1-B5 | price_cents | -1 | 负数 | 422 | 售价不能为负 |
| VM4-1-B6 | price_cents | 999999999 | 最大值 | 201 | 验证最大金额边界 |
| VM4-1-B7 | line_price_cents | 5000（< price_cents=9900） | 逻辑违反 | 422 | 划线价必须 >= 售价 |
| VM4-1-B8 | line_price_cents | 9900（= price_cents） | 等值边界 | 201 | 划线价 = 售价，允许 |
| VM4-1-B9 | ref_id | "non-existent-id" | 无效关联 | 422 | 关联专栏不存在 |
| VM4-1-B10 | type | "physical" | 非法枚举 | 422 | type 只允许 course/digital/service |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-1-S1 | 正常创建课程商品 | draft 专栏 published | POST 创建 | 201, status=draft |
| VM4-1-S2 | 专栏未发布 | 专栏 status=draft | POST 创建 | 422, 关联内容未发布 |
| VM4-1-S3 | 直接创建 on_sale 商品 | 新建商品 | POST 创建, body 含 `status="on_sale"` | 422, 不可直接创建 on_sale |
| VM4-1-S4 | 关联已下架专栏 | 专栏 status=off_sale | POST 创建 | 422, 关联内容已下架 |
| VM4-1-S5 | 不传 refund_policy | 默认值 | POST 创建, 不含 refund_policy | 201, refund_policy 使用默认值 |

---

### VM4-2: 创建资料包商品

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建店铺（store_id）
- 已创建资料包（shop_digital_packages），deliver_mode=download，包含 .pdf 文件，状态为 published
- 资料包 ID = {digital_package_id}

**API**: `POST {base_url}/shop/products`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "store_id": "{store_id}",
  "type": "digital",
  "name": "测试资料包商品",
  "price_cents": 2900,
  "line_price_cents": 5900,
  "ref_type": "digital_package",
  "ref_id": "{digital_package_id}",
  "refund_policy": "before_fulfill"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `status="draft"`, `type="digital"`, `ref_type="digital_package"`, `ref_id="{digital_package_id}"`
- 数据库: `shop_products` 新增 1 条 `status=draft`, `type=digital` 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-2-B1 | name | "" | 空值 | 422 | 商品名不能为空 |
| VM4-2-B2 | ref_type | "column"（与 type=digital 不匹配） | 类型不匹配 | 422 | ref_type 必须与 type 对应 |
| VM4-2-B3 | ref_id | null | 空值 | 422 | ref_id 不能为空 |
| VM4-2-B4 | price_cents | -100 | 负数 | 422 | 售价不能为负 |
| VM4-2-B5 | line_price_cents | 1000（< price=2900） | 逻辑违反 | 422 | 划线价 < 售价 |
| VM4-2-B6 | refund_policy | "invalid_policy" | 非法枚举 | 422 | refund_policy 非法值 |
| VM4-2-B7 | cover_file_id | "non-existent-file" | 无效文件 | 422 | 封面文件不存在 |
| VM4-2-B8 | store_id | "non-existent-store" | 无效店铺 | 404/422 | 店铺不存在或不属于当前商家 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-2-S1 | 正常创建资料包商品 | 资料包 published | POST 创建 | 201, status=draft |
| VM4-2-S2 | 资料包未发布 | 资料包 status=draft | POST 创建 | 422, 关联内容未发布 |
| VM4-2-S3 | 资料包 online_view 无可预览文件 | online_view 模式, 无 pdf/doc/docx | POST 创建 | 422, online_view 发布需 >=1 可预览文件 |
| VM4-2-S4 | 不传 line_price_cents | 可选字段 | POST 创建, 不含 line_price_cents | 201, line_price_cents=null |

---

### VM4-3: 创建服务商品

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建店铺（store_id）
- 已创建服务（shop_service_offers），mode=booking，状态为 published
- 服务 ID = {service_offer_id}

**API**: `POST {base_url}/shop/products`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "store_id": "{store_id}",
  "type": "service",
  "name": "测试服务商品-预约模式",
  "price_cents": 29900,
  "line_price_cents": 49900,
  "ref_type": "service_offer",
  "ref_id": "{service_offer_id}",
  "refund_policy": "manual_only"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `status="draft"`, `type="service"`, `ref_type="service_offer"`, `ref_id="{service_offer_id}"`
- 数据库: `shop_products` 新增 1 条 `status=draft`, `type=service` 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-3-B1 | name | "" | 空值 | 422 | 商品名不能为空 |
| VM4-3-B2 | ref_type | "column"（与 type=service 不匹配） | 类型不匹配 | 422 | ref_type 必须为 service_offer |
| VM4-3-B3 | price_cents | 0 | 最小值 | 422/201 | 服务售价 0 元校验 |
| VM4-3-B4 | price_cents | -1 | 负数 | 422 | 售价不能为负 |
| VM4-3-B5 | line_price_cents | 10000（< price=29900） | 逻辑违反 | 422 | 划线价 < 售价 |
| VM4-3-B6 | refund_policy | "always_allow" | 合法值 | 201 | 允许 always_allow |
| VM4-3-B7 | refund_policy | null | 空值 | 422/201 | 验证默认值处理 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-3-S1 | 正常创建预约服务商品 | 服务 published, mode=booking | POST 创建 | 201, status=draft |
| VM4-3-S2 | 服务未发布 | 服务 status=draft | POST 创建 | 422, 关联内容未发布 |
| VM4-3-S3 | 创建次数卡服务商品 | 服务 mode=times_card, total_times=10 | POST 创建 | 201, status=draft |
| VM4-3-S4 | 关联已下架服务 | 服务 status=off_sale | POST 创建 | 422, 关联内容已下架 |

---

### VM4-4: 商品编辑（状态校验）

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建 2 个商品：商品1 status=draft（{product_id_draft}），商品2 status=on_sale（{product_id_onsale}）
- 商品1 关联已发布专栏

**API**: `PUT {base_url}/shop/products/{product_id}`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**（编辑 draft 商品）:
```json
{
  "name": "修改后的课程商品名",
  "price_cents": 12900,
  "line_price_cents": 25900
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `name="修改后的课程商品名"`, `price_cents=12900`, `status="draft"`
- 数据库: `shop_products` 对应记录 name 和 price_cents 已更新

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-4-B1 | name | "" | 空值 | 422 | 编辑后商品名不能为空 |
| VM4-4-B2 | price_cents | -1 | 负数 | 422 | 编辑后售价不能为负 |
| VM4-4-B3 | line_price_cents | 5000（< price=12900） | 逻辑违反 | 422 | 划线价必须 >= 售价 |
| VM4-4-B4 | name | "a".repeat(256) | 超长 | 422 | 商品名超 255 字符 |
| VM4-4-B5 | price_cents | 0 | 最小值 | 200/422 | 编辑为 0 元的校验 |
| VM4-4-B6 | refund_policy | "invalid" | 非法枚举 | 422 | refund_policy 非法值 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-4-S1 | 编辑 draft 商品 | status=draft | PUT 编辑 name | 200, 更新成功 |
| VM4-4-S2 | 编辑 on_sale 商品 | status=on_sale | PUT 编辑 name | 409, 在售商品不可编辑 |
| VM4-4-S3 | 编辑 rejected 商品 | status=rejected | PUT 编辑 name | 200, rejected 可编辑 |
| VM4-4-S4 | 编辑 approved 商品 | status=approved | PUT 编辑 name | 200/409, 验证 approved 是否可编辑 |
| VM4-4-S5 | 编辑 pending_review 商品 | status=pending_review | PUT 编辑 name | 409, 审核中不可编辑 |

---

### VM4-5: 商品提审

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品 status=draft（{product_id_draft}），所有必填项已填写，关联内容已发布
- auto_review_mode=stub（Phase 1 固定 auto_result=flag，一律走人审）

**API**: `POST {base_url}/shop/products/{product_id}/submit-review`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status="pending_review"`, `auto_result="flag"`, `review_status="pending_manual"`
- 数据库: `shop_products` 记录 status 更新为 `pending_review`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-5-B1 | product_id | "non-existent" | 不存在 | 404 | 商品不存在 |
| VM4-5-B2 | product status | "on_sale" | 非法状态 | 409/422 | on_sale 不可提审 |
| VM4-5-B3 | product status | "pending_review" | 重复提审 | 409/422 | 已在审核中不可重复提审 |
| VM4-5-B4 | product status | "approved" | 非法状态 | 409/422 | approved 不可再提审 |
| VM4-5-B5 | name | ""（商品名为空） | 必填缺失 | 422 | 提审前置校验：必填项缺失 |
| VM4-5-B6 | ref_id | null（关联内容为空） | 必填缺失 | 422 | 提审前置校验：关联内容无效 |
| VM4-5-B7 | line_price_cents | 1000（< price=9900） | 逻辑违反 | 422 | 提审前置校验：line_price < price |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-5-S1 | 正常提审 draft 商品 | status=draft, 必填项齐全 | POST submit-review | 200, status=pending_review, auto_result=flag |
| VM4-5-S2 | 提审 on_sale 商品 | status=on_sale | POST submit-review | 409/422, 非法状态 |
| VM4-5-S3 | 提审 rejected 商品（修改后重新提审） | status=rejected, 已修改 | POST submit-review | 200, status=pending_review |
| VM4-5-S4 | 日提审次数用尽 | 当日提审已达上限 | POST submit-review | 422, PLAN_USAGE_EXCEEDED |
| VM4-5-S5 | 机审 reject（模拟） | 机审返回 reject | POST submit-review | 422, 机审未通过 |

---

### VM4-6: 商品上架

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品并审核通过 status=approved（{product_id_approved}）
- 在售商品数未达套餐上限

**API**: `POST {base_url}/shop/products/{product_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status="on_sale"`
- 数据库: `shop_products` 记录 status 更新为 `on_sale`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-6-B1 | product_id | "non-existent" | 不存在 | 404 | 商品不存在 |
| VM4-6-B2 | product status | "draft" | 非法状态 | 409/422 | draft 不可直接上架 |
| VM4-6-B3 | product status | "pending_review" | 非法状态 | 409/422 | 审核中不可上架 |
| VM4-6-B4 | product status | "off_sale" | 非法状态 | 409/422 | off_sale 不可直接上架（需走 approved→on_sale） |
| VM4-6-B5 | product status | "on_sale" | 重复上架 | 409/422 | 已在售不可重复上架 |
| VM4-6-B6 | product status | "rejected" | 非法状态 | 409/422 | rejected 不可上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-6-S1 | 正常上架 approved 商品 | status=approved | POST publish | 200, status=on_sale |
| VM4-6-S2 | 上架 draft 商品 | status=draft | POST publish | 409/422, 仅 approved 可上架 |
| VM4-6-S3 | 在售商品数达上限 | 已达套餐上限 | POST publish | 422, 已达套餐商品上限 |
| VM4-6-S4 | 上架 off_sale 商品 | status=off_sale | POST publish | 409/422, 需先重新审核 |

---

### VM4-7: 商品下架

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品 status=on_sale（{product_id_onsale}）

**API**: `POST {base_url}/shop/products/{product_id}/off-sale`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `status="off_sale"`
- 数据库: `shop_products` 记录 status 更新为 `off_sale`，保留 `approved` 状态

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-7-B1 | product_id | "non-existent" | 不存在 | 404 | 商品不存在 |
| VM4-7-B2 | product status | "draft" | 非法状态 | 409/422 | draft 不可下架 |
| VM4-7-B3 | product status | "approved" | 非法状态 | 409/422 | approved 未上架不可下架 |
| VM4-7-B4 | product status | "off_sale" | 重复下架 | 409/422 | 已下架不可重复下架 |
| VM4-7-B5 | product status | "pending_review" | 非法状态 | 409/422 | 审核中不可下架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-7-S1 | 正常下架 on_sale 商品 | status=on_sale | POST off-sale | 200, status=off_sale |
| VM4-7-S2 | 下架 draft 商品 | status=draft | POST off-sale | 409/422, 非法状态 |
| VM4-7-S3 | 下架后已购权益不受影响 | 有买家已购该商品权益 | POST off-sale | 200, 已购 entitlement 状态不变 |

---

### VM4-8: 多店隔离

**前置条件**:
- 商家A 已入驻（TENANT_A, store_id_A），商家B 已入驻（TENANT_B, store_id_B）
- 商家A 创建商品 {product_id_A} 属于 store_id_A
- merchant_token（A）和 merchant_token_b（B）均已获取

**API**: `GET {base_url}/shop/products/{product_id}`
**Headers**: `Authorization: Bearer {merchant_token_b}`

**请求体**: 无

**期望结果**:
- HTTP Status: 404（或 403）
- Response Body 含错误信息：商品不存在或无权访问
- 数据库: 无变更

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-8-B1 | merchant_token | merchant_token_b（B 商家） | 跨租户 | 404/403 | B 商家不可访问 A 商家商品 |
| VM4-8-B2 | product_id | "non-existent" | 不存在 | 404 | 商品不存在 |
| VM4-8-B3 | merchant_token | 无效 token | 未认证 | 401 | 未携带有效 token |
| VM4-8-B4 | merchant_token | buyer_token（买家 token） | 角色错误 | 403 | 买家不可访问商家管理 API |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-8-S1 | A 商家查询自己商品 | product 属于 A | GET with merchant_token | 200, 返回商品详情 |
| VM4-8-S2 | B 商家查询 A 商家商品 | product 属于 A | GET with merchant_token_b | 404/403, 多店隔离 |
| VM4-8-S3 | B 商家编辑 A 商家商品 | product 属于 A | PUT with merchant_token_b | 404/403, 多店隔离 |
| VM4-8-S4 | B 商家下架 A 商家商品 | product 属于 A | POST off-sale with merchant_token_b | 404/403, 多店隔离 |

---

### VM4-9: 专栏创建与发布

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建店铺（store_id）

**API**: `POST {base_url}/shop/columns`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "title": "测试专栏",
  "intro": "这是一个测试专栏的简介"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `status="draft"`, `title="测试专栏"`, `parent_column_id=null`
- 数据库: `shop_columns` 新增 1 条 `status=draft` 记录，`parent_column_id` 为 null（扁平结构）

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-9-B1 | title | "" | 空值 | 422 | 专栏标题不能为空 |
| VM4-9-B2 | title | "a".repeat(256) | 超长 | 422 | 标题超长 |
| VM4-9-B3 | intro | "a".repeat(10001) | 超长 | 422 | 简介超 10000 字符 |
| VM4-9-B4 | shop_id | "non-existent" | 无效店铺 | 404/422 | 店铺不存在 |
| VM4-9-B5 | parent_column_id | "some-id" | 非法字段 | 422 | Phase 1 专栏为扁平结构，无 parent |
| VM4-9-B6 | title | null | 空值 | 422 | 标题不能为 null |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-9-S1 | 正常创建专栏 | 店铺已存在 | POST 创建 | 201, status=draft |
| VM4-9-S2 | 发布专栏 | 专栏 status=draft, 含 >=1 课时 | POST .../publish | 200, status=published |
| VM4-9-S3 | 发布空专栏 | 专栏 status=draft, 无课时 | POST .../publish | 422, 专栏需至少 1 课时 |
| VM4-9-S4 | 专栏下架 | 专栏 status=published | POST .../off-sale | 200, status=off_sale |

---

### VM4-10: 课时创建（视频/图文）

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建专栏（{column_id}），status=draft
- 视频文件已上传：mp4 格式，大小 500MB，时长 1200 秒，转码状态 ready
- 图文素材已准备

**API**: `POST {base_url}/shop/columns/{column_id}/lessons`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**（视频课时）:
```json
{
  "title": "第一课时：课程导论",
  "type": "video",
  "video_file_id": "{video_file_id}",
  "duration_sec": 1200,
  "is_trial": false
}
```

**请求体**（图文课时）:
```json
{
  "title": "第二课时：图文笔记",
  "type": "article",
  "content_body": "这是图文课时的正文内容，至少 10 个字。",
  "images": [
    {"file_id": "{image_file_id_1}", "sort": 1}
  ]
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `status="draft"`, `type="video"` 或 `type="article"`
- 数据库: `shop_lessons` 新增 1 条记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-10-B1 | title | "" | 空值 | 422 | 课时标题不能为空 |
| VM4-10-B2 | type | "audio" | 非法枚举 | 422 | type 只允许 video/article |
| VM4-10-B3 | video format | .avi 文件 | 格式不符 | 422 | 仅允许 mp4/mov |
| VM4-10-B4 | video size | 2.1GB | 超大 | 422 | 视频 <=2GB/节 |
| VM4-10-B5 | duration_sec | 181分钟=10860秒 | 超时 | 422 | 视频 <=180 分钟 |
| VM4-10-B6 | video transcode | status=processing | 未转码完成 | 422 | 转码需 ready |
| VM4-10-B7 | content_body | "" | 空值 | 422 | 图文正文不能为空 |
| VM4-10-B8 | content_body | "短" | 不足最小长度 | 422 | 正文 >=10 字 |
| VM4-10-B9 | content_body | "a".repeat(50001) | 超长 | 422 | 正文 <=50000 字 |
| VM4-10-B10 | images count | 21 张 | 超量 | 422 | 图片 <=20 张 |
| VM4-10-B11 | image size | 单张 5.1MB | 超大 | 422 | 内嵌图 <=5MB |
| VM4-10-B12 | image format | .bmp | 格式不符 | 422 | 仅允许 jpg/png/gif |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-10-S1 | 正常创建视频课时 | 专栏 draft, 视频 ready | POST 创建 video 课时 | 201, status=draft |
| VM4-10-S2 | 正常创建图文课时 | 专栏 draft | POST 创建 article 课时 | 201, status=draft |
| VM4-10-S3 | 视频未转码完成 | 视频 status=processing | POST 创建 | 422, 转码未完成 |
| VM4-10-S4 | 图文无标题 | title="" | POST 创建 | 422, 标题不能为空 |
| VM4-10-S5 | 课时发布 | 课时 status=draft | POST .../publish | 200, status=published |

---

### VM4-11: 试看设置

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建专栏（{column_id}），含 5 个已发布视频课时
- 专栏已有 0 个试看课时

**API**: `PUT {base_url}/shop/lessons/{lesson_id}/trial`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "is_trial": true,
  "trial_seconds": 180
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含: `is_trial=true`, `trial_seconds=180`
- 数据库: `shop_lessons` 记录 `is_trial=true`, `trial_seconds=180`
- effective = min(180, duration_sec)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-11-B1 | trial_seconds | 60 | 最小可选值 | 200 | 60s 试看 |
| VM4-11-B2 | trial_seconds | 300 | 可选值 | 200 | 300s 试看 |
| VM4-11-B3 | trial_seconds | 600 | 可选值 | 200 | 600s 试看 |
| VM4-11-B4 | trial_seconds | null | 整节试看 | 200 | null = 整节试看 |
| VM4-11-B5 | trial_seconds | 100 | 非可选值 | 422 | 仅允许 60/180/300/600/null |
| VM4-11-B6 | trial_seconds | 0 | 非法值 | 422 | 0 不在可选范围 |
| VM4-11-B7 | lesson type | article（图文课时） | 类型不符 | 422 | 仅已发布视频可设试看 |
| VM4-11-B8 | lesson status | draft | 未发布 | 422 | 仅已发布视频可设试看 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-11-S1 | 设置 1 节试看 | 专栏 0 试看, 视频已发布 | PUT is_trial=true, trial_seconds=180 | 200, 试看设置成功 |
| VM4-11-S2 | 设置第 4 节试看（超限） | 专栏已有 3 试看 | PUT is_trial=true | 422, 最多 3 节/专栏试看 |
| VM4-11-S3 | 取消试看 | 课时 is_trial=true | PUT is_trial=false | 200, 取消试看 |
| VM4-11-S4 | 试看时长 > 视频时长 | duration_sec=120, trial_seconds=180 | PUT trial_seconds=180 | 200, effective=min(180,120)=120 |
| VM4-11-S5 | 对图文课时设试看 | 课时 type=article | PUT is_trial=true | 422, 仅视频可试看 |

---

### VM4-12: 资料包创建与校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建店铺（store_id）
- 文件已上传：.pdf 文件（{pdf_file_id}）、.zip 文件（{zip_file_id}）

**API**: `POST {base_url}/shop/digital-packages`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "title": "测试资料包",
  "intro": "包含 PDF 和 ZIP 文件",
  "deliver_mode": "download",
  "files": [
    {"file_id": "{pdf_file_id}", "sort": 1},
    {"file_id": "{zip_file_id}", "sort": 2}
  ]
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `status="draft"`, `deliver_mode="download"`
- 数据库: `shop_digital_packages` 新增 1 条记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-12-B1 | title | "" | 空值 | 422 | 资料包标题不能为空 |
| VM4-12-B2 | deliver_mode | "streaming" | 非法枚举 | 422 | 仅允许 download/online_view |
| VM4-12-B3 | files | 空数组 | 空值 | 422 | 至少 1 个文件 |
| VM4-12-B4 | file format | .exe 文件 | 格式不符 | 422 | 仅允许 .pdf/.doc/.docx/.zip |
| VM4-12-B5 | file format | .docx 文件 | 合法格式 | 201 | .docx 在白名单中 |
| VM4-12-B6 | deliver_mode | "online_view" + 仅 .zip 文件 | 无可预览文件 | 201(保存)/422(发布) | 保存软校验通过, 发布硬校验失败 |
| VM4-12-B7 | files | null | 空值 | 422 | 文件列表不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-12-S1 | 正常创建 download 资料包 | 文件已上传 | POST 创建 | 201, status=draft |
| VM4-12-S2 | 创建 online_view 资料包（含 pdf） | 含 .pdf 可预览文件 | POST 创建 | 201, status=draft |
| VM4-12-S3 | online_view 资料包发布（无可预览文件） | 仅 .zip 文件 | POST .../publish | 422, 发布硬校验需 >=1 可预览文件 |
| VM4-12-S4 | online_view 资料包保存（无可预览文件） | 仅 .zip 文件 | PUT 保存 | 200, 软校验通过+黄条警告 |
| VM4-12-S5 | online_view 资料包发布（有 pdf） | 含 .pdf 文件 | POST .../publish | 200, status=published |

---

### VM4-1-N1: 价格边界综合测试

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建店铺（store_id），已发布专栏（{column_id}）

**API**: `POST {base_url}/shop/products`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**（基准）:
```json
{
  "store_id": "{store_id}",
  "type": "course",
  "name": "价格边界测试商品",
  "price_cents": 9900,
  "ref_type": "column",
  "ref_id": "{column_id}"
}
```

**期望结果**:
- HTTP Status: 201（基准请求）
- Response Body 含: `id`, `status="draft"`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-1-N1-B1 | price_cents | 0 | 最小值 | 422/201 | 验证 0 元是否允许 |
| VM4-1-N1-B2 | price_cents | -1 | 负数 | 422 | 售价不能为负 |
| VM4-1-N1-B3 | price_cents | -999999 | 大负数 | 422 | 售价不能为负 |
| VM4-1-N1-B4 | price_cents | 1 | 最小正整数 | 201 | 1 分钱 |
| VM4-1-N1-B5 | price_cents | 2147483647 | int32 最大值 | 201/422 | 验证最大整数边界 |
| VM4-1-N1-B6 | price_cents | 9999999999 | 超 int32 | 422 | 超出整数范围 |
| VM4-1-N1-B7 | price_cents | 9900, line_price_cents=9900 | 等值 | 201 | 划线价 = 售价 |
| VM4-1-N1-B8 | price_cents | 9900, line_price_cents=9899 | line < price | 422 | 划线价 < 售价 |
| VM4-1-N1-B9 | price_cents | 9900, line_price_cents=0 | line=0 | 422/201 | 划线价 0 的处理 |
| VM4-1-N1-B10 | price_cents | "abc" | 非数字 | 422 | 类型错误 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-1-N1-S1 | price=0 的商品创建 | 专栏已发布 | POST price_cents=0 | 422/201（需确认 PRD 是否允许免费） |
| VM4-1-N1-S2 | line_price 远大于 price | 专栏已发布 | POST price=9900, line=999999999 | 201, 允许划线价远大于售价 |
| VM4-1-N1-S3 | 不传 line_price_cents | 专栏已发布 | POST 不含 line_price_cents | 201, line_price_cents=null |
| VM4-1-N1-S4 | 编辑时修改 line_price < price | 商品 status=draft | PUT price=12900, line=5000 | 422, 划线价 < 售价 |

---

### VM4-1-N2: 商品字段必填校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建店铺（store_id），已发布专栏（{column_id}）

**API**: `POST {base_url}/shop/products`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**（基准）:
```json
{
  "store_id": "{store_id}",
  "type": "course",
  "name": "必填校验测试",
  "price_cents": 9900,
  "ref_type": "column",
  "ref_id": "{column_id}"
}
```

**期望结果**:
- HTTP Status: 201（基准请求）

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-1-N2-B1 | type | 不传 | 缺失必填 | 422 | type 为必填 |
| VM4-1-N2-B2 | type | null | 空值 | 422 | type 不能为 null |
| VM4-1-N2-B3 | name | 不传 | 缺失必填 | 422 | name 为必填 |
| VM4-1-N2-B4 | price_cents | 不传 | 缺失必填 | 422 | price_cents 为必填 |
| VM4-1-N2-B5 | ref_type | 不传 | 缺失必填 | 422 | ref_type 为必填 |
| VM4-1-N2-B6 | ref_id | 不传 | 缺失必填 | 422 | ref_id 为必填 |
| VM4-1-N2-B7 | store_id | 不传 | 缺失必填 | 422 | store_id 为必填 |
| VM4-1-N2-B8 | type | "course", ref_type="digital_package" | 类型不匹配 | 422 | type=course 时 ref_type 必须为 column |
| VM4-1-N2-B9 | type | "digital", ref_type="column" | 类型不匹配 | 422 | type=digital 时 ref_type 必须为 digital_package |
| VM4-1-N2-B10 | type | "service", ref_type="digital_package" | 类型不匹配 | 422 | type=service 时 ref_type 必须为 service_offer |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-1-N2-S1 | 所有必填项齐全 | 专栏已发布 | POST 完整请求 | 201 |
| VM4-1-N2-S2 | 缺少 type | — | POST 不含 type | 422, type 必填 |
| VM4-1-N2-S3 | type 与 ref_type 不匹配 | — | POST type=course, ref_type=service_offer | 422, 类型不匹配 |
| VM4-1-N2-S4 | 仅传可选字段 | — | POST 仅 subtitle + cover_file_id | 422, 缺少必填项 |

---

### VM4-1-N3: 商品列表查询

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建 5 个商品：2 个 draft, 1 个 on_sale, 1 个 off_sale, 1 个 pending_review

**API**: `GET {base_url}/shop/products?page=1&page_size=20`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `items`（数组）, `total`, `page`, `page_size`
- items 中仅包含当前商家（TENANT_A）的商品

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-1-N3-B1 | page | 0 | 非法页码 | 422 | 页码从 1 开始 |
| VM4-1-N3-B2 | page | -1 | 负数 | 422 | 页码不能为负 |
| VM4-1-N3-B3 | page_size | 0 | 非法值 | 422 | page_size >= 1 |
| VM4-1-N3-B4 | page_size | 101 | 超大 | 422 | page_size <= 100 |
| VM4-1-N3-B5 | status | "on_sale" | 过滤 | 200 | 仅返回 on_sale 商品 |
| VM4-1-N3-B6 | status | "invalid" | 非法枚举 | 422 | status 非法值 |
| VM4-1-N3-B7 | page | 999 | 超出范围 | 200 | 返回空列表 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-1-N3-S1 | 查询全部商品 | 5 个商品 | GET 无过滤 | 200, total=5 |
| VM4-1-N3-S2 | 按 status 过滤 | 2 个 draft | GET status=draft | 200, total=2 |
| VM4-1-N3-S3 | 跨租户隔离 | 商家B 查询 | GET with merchant_token_b | 200, 仅返回 B 的商品 |
| VM4-1-N3-S4 | 分页查询 | 5 个商品 | GET page=1, page_size=2 | 200, items.length=2, total=5 |

---

### VM4-1-N4: 商品详情查询

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品 {product_id}，status=draft

**API**: `GET {base_url}/shop/products/{product_id}`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含: `id`, `name`, `type`, `price_cents`, `line_price_cents`, `status`, `ref_type`, `ref_id`, `refund_policy`, `created_at`, `updated_at`

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-1-N4-B1 | product_id | "non-existent" | 不存在 | 404 | 商品不存在 |
| VM4-1-N4-B2 | product_id | "" | 空值 | 404/422 | 无效 ID |
| VM4-1-N4-B3 | product_id | 含特殊字符 `<script>` | XSS 注入 | 404/422 | 安全校验 |
| VM4-1-N4-B4 | Authorization | 无 token | 未认证 | 401 | 需要登录 |
| VM4-1-N4-B5 | Authorization | buyer_token | 角色错误 | 403 | 买家不可访问管理 API |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-1-N4-S1 | 查询自己的商品 | 商品属于 A | GET with merchant_token | 200, 返回详情 |
| VM4-1-N4-S2 | 查询不存在商品 | — | GET non-existent-id | 404 |
| VM4-1-N4-S3 | 跨租户查询 | 商品属于 A | GET with merchant_token_b | 404/403 |

---

### VM4-4-N1: 商品状态机非法转换

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建多个不同状态的商品：draft、pending_review、approved、on_sale、off_sale、rejected

**API**: 各状态转换 API
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: 无（状态转换操作）

**期望结果**:
- 所有非法转换返回 409 或 422
- 合法转换返回 200

**边界值测试**:

| 变体ID | 当前状态 | 目标操作 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM4-4-N1-B1 | draft | publish（上架） | 409/422 | draft 不可直接上架 |
| VM4-4-N1-B2 | draft | off-sale（下架） | 409/422 | draft 不可下架 |
| VM4-4-N1-B3 | pending_review | publish | 409/422 | 审核中不可上架 |
| VM4-4-N1-B4 | pending_review | off-sale | 409/422 | 审核中不可下架 |
| VM4-4-N1-B5 | pending_review | submit-review（重复提审） | 409/422 | 不可重复提审 |
| VM4-4-N1-B6 | approved | submit-review | 409/422 | approved 不可再提审 |
| VM4-4-N1-B7 | approved | off-sale | 409/422 | approved 未上架不可下架 |
| VM4-4-N1-B8 | on_sale | submit-review | 409/422 | on_sale 不可提审 |
| VM4-4-N1-B9 | on_sale | publish（重复上架） | 409/422 | 已在售不可重复上架 |
| VM4-4-N1-B10 | off_sale | publish | 409/422 | off_sale 不可直接上架（需走 approved→on_sale） |
| VM4-4-N1-B11 | off_sale | submit-review | 200 | off_sale 可重新提审（保留 approved 可再上架场景需确认） |
| VM4-4-N1-B12 | rejected | publish | 409/422 | rejected 不可上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-4-N1-S1 | draft → pending_review（提审） | status=draft | POST submit-review | 200, 合法转换 |
| VM4-4-N1-S2 | approved → on_sale（上架） | status=approved | POST publish | 200, 合法转换 |
| VM4-4-N1-S3 | on_sale → off_sale（下架） | status=on_sale | POST off-sale | 200, 合法转换 |
| VM4-4-N1-S4 | rejected → pending_review（修改后重新提审） | status=rejected | POST submit-review | 200, 合法转换 |
| VM4-4-N1-S5 | 全链路：draft→提审→approved→上架→下架 | status=draft | 依次执行 | 全部 200, 最终 off_sale |

---

### VM4-4-N2: 权限校验（跨租户/非商家）

**前置条件**:
- 商家A（TENANT_A）创建商品 {product_id_A}
- 商家B（TENANT_B）已入驻
- 买家A（buyer_token）已注册

**API**: `PUT {base_url}/shop/products/{product_id_A}`
**Headers**: `Authorization: Bearer {merchant_token_b}` 或 `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "name": "B 商家尝试修改 A 商家商品"
}
```

**期望结果**:
- HTTP Status: 404 或 403
- 数据库: 商品 {product_id_A} 记录无变更

**边界值测试**:

| 变体ID | Token | 操作 | 期望Status | 说明 |
|--------|-------|------|-----------|------|
| VM4-4-N2-B1 | merchant_token_b | PUT 编辑 | 404/403 | 跨租户编辑 |
| VM4-4-N2-B2 | buyer_token | PUT 编辑 | 403 | 买家无权编辑商品 |
| VM4-4-N2-B3 | 无 token | PUT 编辑 | 401 | 未认证 |
| VM4-4-N2-B4 | 无效 token | PUT 编辑 | 401 | token 无效 |
| VM4-4-N2-B5 | merchant_token_b | POST submit-review | 404/403 | 跨租户提审 |
| VM4-4-N2-B6 | merchant_token_b | POST publish | 404/403 | 跨租户上架 |
| VM4-4-N2-B7 | merchant_token_b | POST off-sale | 404/403 | 跨租户下架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-4-N2-S1 | A 商家编辑自己商品 | 商品属于 A | PUT with merchant_token | 200 |
| VM4-4-N2-S2 | B 商家编辑 A 商家商品 | 商品属于 A | PUT with merchant_token_b | 404/403 |
| VM4-4-N2-S3 | 买家编辑商品 | 商品属于 A | PUT with buyer_token | 403 |
| VM4-4-N2-S4 | B 商家对 A 商家商品提审 | 商品属于 A | POST submit-review with merchant_token_b | 404/403 |

---

### VM4-5-N1: 机审规则测试（stub 模式）

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品 status=draft，必填项齐全
- auto_review_mode=stub（Phase 1 固定 auto_result=flag，一律走人审）

**API**: `POST {base_url}/shop/products/{product_id}/submit-review`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- HTTP Status: 200
- Response Body 含: `auto_result="flag"`, `review_status="pending_manual"`
- stub 模式下所有商品一律 flag，走人审

**边界值测试**:

| 变体ID | 商品内容 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|---------|--------|---------|-----------|------|
| VM4-5-N1-B1 | name 含敏感词 | "违禁词测试" | 敏感词 | 200, flag | stub 模式固定 flag |
| VM4-5-N1-B2 | name 含夸大承诺 | "100%赚钱保证" | 夸大承诺 | 200, flag | stub 模式固定 flag |
| VM4-5-N1-B3 | name 含外链 | "加微信 abc123" | 外链引流 | 200, flag | stub 模式固定 flag |
| VM4-5-N1-B4 | name 正常 | "正常课程名称" | 正常内容 | 200, flag | stub 模式固定 flag |
| VM4-5-N1-B5 | subtitle 含敏感词 | subtitle="违禁词" | 敏感词 | 200, flag | stub 模式固定 flag |
| VM4-5-N1-B6 | cover 含二维码 | 封面图含二维码 | 媒体合规 | 200, flag | stub 模式固定 flag |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-5-N1-S1 | stub 模式正常提审 | status=draft | POST submit-review | 200, auto_result=flag, 走人审 |
| VM4-5-N1-S2 | stub 模式含敏感词提审 | name 含违禁词 | POST submit-review | 200, auto_result=flag（stub 固定） |
| VM4-5-N1-S3 | stub 模式含禁售类目 | category_id 在 P04 blocked | POST submit-review | 200, flag（stub 模式下不实际 reject） |
| VM4-5-N1-S4 | 非法 category_id 提审 | category_id 不存在 | POST submit-review | 422, 前置校验失败 |

---

### VM4-5-N2: 提审前置校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品 status=draft

**API**: `POST {base_url}/shop/products/{product_id}/submit-review`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- 前置校验通过：200
- 前置校验失败：422，返回具体错误信息

**边界值测试**:

| 变体ID | 前置条件 | 边界类型 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM4-5-N2-B1 | name="" | 必填缺失 | 422 | 商品名不能为空 |
| VM4-5-N2-B2 | price_cents=null | 必填缺失 | 422 | 售价不能为空 |
| VM4-5-N2-B3 | ref_id=null | 关联内容无效 | 422 | 关联内容不能为空 |
| VM4-5-N2-B4 | ref_id 指向 draft 专栏 | 关联内容未发布 | 422 | 关联内容必须已发布 |
| VM4-5-N2-B5 | ref_id 指向 off_sale 专栏 | 关联内容已下架 | 422 | 关联内容已下架 |
| VM4-5-N2-B6 | line_price_cents < price_cents | 逻辑违反 | 422 | 划线价 < 售价 |
| VM4-5-N2-B7 | 当日提审次数已达上限 | 额度用尽 | 422 | PLAN_USAGE_EXCEEDED |
| VM4-5-N2-B8 | 商品 status=on_sale | 非法状态 | 409/422 | on_sale 不可提审 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-5-N2-S1 | 全部前置校验通过 | 必填项齐全, 关联已发布, 额度充足 | POST submit-review | 200, pending_review |
| VM4-5-N2-S2 | 关联内容未发布 | 专栏 status=draft | POST submit-review | 422, 关联内容未发布 |
| VM4-5-N2-S3 | line_price < price | line=5000, price=9900 | POST submit-review | 422, 划线价 < 售价 |
| VM4-5-N2-S4 | 日提审额度用尽 | 当日已达上限 | POST submit-review | 422, PLAN_USAGE_EXCEEDED |

---

### VM4-5-N3: 提审次数限制

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 商家A 套餐日提审上限为 N 次（如 5 次/天）
- 已创建 N+1 个 draft 商品

**API**: `POST {base_url}/shop/products/{product_id}/submit-review`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- 前 N 次提审：200
- 第 N+1 次：422, PLAN_USAGE_EXCEEDED

**边界值测试**:

| 变体ID | 提审次数 | 边界类型 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM4-5-N3-B1 | 第 1 次 | 正常 | 200 | 正常提审 |
| VM4-5-N3-B2 | 第 N 次（上限） | 边界值 | 200 | 刚好达到上限 |
| VM4-5-N3-B3 | 第 N+1 次 | 超限 | 422 | PLAN_USAGE_EXCEEDED |
| VM4-5-N3-B4 | 次日重置后第 1 次 | 跨天重置 | 200 | 日额度次日重置 |
| VM4-5-N3-B5 | 同一商品提审被拒后重新提审 | 额度计算 | 200/422 | 验证重新提审是否消耗额度 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-5-N3-S1 | 正常提审（未达上限） | 已提审 2 次, 上限 5 | POST submit-review | 200 |
| VM4-5-N3-S2 | 达到日提审上限 | 已提审 5 次, 上限 5 | POST submit-review | 422, PLAN_USAGE_EXCEEDED |
| VM4-5-N3-S3 | 次日额度重置 | 前一日已达上限 | POST submit-review | 200, 额度已重置 |

---

### VM4-6-N1: 上架商品数上限

**前置条件**:
- 商家A 已入驻，套餐在售商品上限为 M 个
- 已有 M 个 on_sale 商品
- 有 1 个 approved 商品待上架

**API**: `POST {base_url}/shop/products/{product_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息：已达套餐商品上限

**边界值测试**:

| 变体ID | 在售商品数 | 边界类型 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM4-6-N1-B1 | M-1 个 on_sale | 未达上限 | 200 | 正常上架 |
| VM4-6-N1-B2 | M 个 on_sale | 达上限 | 422 | 已达套餐商品上限 |
| VM4-6-N1-B3 | 下架 1 个后上架 | M→M-1→M | 200 | 下架后腾出名额 |
| VM4-6-N1-B4 | M 个 on_sale, 尝试第 M+1 个 | 超限 | 422 | 已达上限 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-6-N1-S1 | 未达上限正常上架 | M-1 个 on_sale | POST publish | 200, on_sale |
| VM4-6-N1-S2 | 达到上限上架失败 | M 个 on_sale | POST publish | 422, 已达套餐商品上限 |
| VM4-6-N1-S3 | 下架后可上架 | M 个 on_sale → 下架 1 个 → M-1 | POST publish | 200, 腾出名额后可上架 |

---

### VM4-6-N2: 非 approved 状态上架拒绝

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建不同状态的商品：draft、pending_review、off_sale、rejected、on_sale

**API**: `POST {base_url}/shop/products/{product_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- 仅 approved 状态可上架（200）
- 其他状态上架返回 409/422

**边界值测试**:

| 变体ID | 商品状态 | 期望Status | 说明 |
|--------|---------|-----------|------|
| VM4-6-N2-B1 | draft | 409/422 | draft 不可上架 |
| VM4-6-N2-B2 | pending_review | 409/422 | 审核中不可上架 |
| VM4-6-N2-B3 | off_sale | 409/422 | 下架状态不可直接上架 |
| VM4-6-N2-B4 | rejected | 409/422 | 驳回状态不可上架 |
| VM4-6-N2-B5 | on_sale | 409/422 | 已在售不可重复上架 |
| VM4-6-N2-B6 | approved | 200 | 合法上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-6-N2-S1 | approved 上架 | status=approved | POST publish | 200, on_sale |
| VM4-6-N2-S2 | draft 上架 | status=draft | POST publish | 409/422 |
| VM4-6-N2-S3 | off_sale 上架 | status=off_sale | POST publish | 409/422, 需先重新提审 |

---

### VM4-7-N1: 下架后再上架

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建商品，经历 draft→pending_review→approved→on_sale→off_sale

**API**: `POST {base_url}/shop/products/{product_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- off_sale 状态直接 publish → 409/422（需确认 PRD：off_sale 保留 approved, 可再上架）
- 若 PRD 允许 off_sale → on_sale：200

**边界值测试**:

| 变体ID | 当前状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM4-7-N1-B1 | off_sale | POST publish | 200/409 | 验证 off_sale 是否可直接再上架（PRD: 保留 approved, 可再上架） |
| VM4-7-N1-B2 | off_sale | POST submit-review → publish | 200 | 重新提审后再上架 |
| VM4-7-N1-B3 | off_sale | PUT 编辑 → submit-review → publish | 200 | 修改后重新提审上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-7-N1-S1 | 下架后直接再上架 | off_sale（保留 approved） | POST publish | 200（若 PRD 允许）/ 409（需重新提审） |
| VM4-7-N1-S2 | 下架后编辑再提审上架 | off_sale → 编辑 → submit-review → publish | 依次执行 | 最终 200, on_sale |
| VM4-7-N1-S3 | 下架后已购权益不变 | 有买家已购 | POST off-sale → 检查 entitlement | 200, entitlement 不受影响 |

---

### VM4-8-N1: 跨店商品查询隔离

**前置条件**:
- 商家A 有店铺 store_id_A，创建商品 {product_id_A} 属于 store_id_A
- 商家B 有店铺 store_id_B
- 买家A 通过 store_id_B 的入口访问

**API**: `GET {base_url}/mp/shop/{store_id_B}/products/{product_id_A}`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 404（或 403）
- 商品不属于 store_id_B，不可访问

**边界值测试**:

| 变体ID | 访问场景 | 期望Status | 说明 |
|--------|---------|-----------|------|
| VM4-8-N1-B1 | 买家通过 store_id_B 访问 store_id_A 的商品 | 404/403 | 跨店隔离 |
| VM4-8-N1-B2 | 买家通过 store_id_A 访问 store_id_A 的商品 | 200 | 同店正常访问 |
| VM4-8-N1-B3 | 买家通过不存在的 store_id 访问 | 404 | 店铺不存在 |
| VM4-8-N1-B4 | 买家无 token 访问公开商品 | 200/401 | 验证是否需要登录 |
| VM4-8-N1-B5 | 商家B 通过管理 API 查询 product_id_A | 404/403 | 跨租户隔离 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-8-N1-S1 | 同店买家访问商品 | 商品属于 store_id_A | GET via store_id_A | 200 |
| VM4-8-N1-S2 | 跨店买家访问商品 | 商品属于 store_id_A | GET via store_id_B | 404/403 |
| VM4-8-N1-S3 | 跨租户商家管理商品 | 商品属于 TENANT_A | GET/PUT with merchant_token_b | 404/403 |

---

### VM4-9-N1: 专栏下架不可再发布

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建专栏（{column_id}），含已发布课时，status=published

**API**: `POST {base_url}/shop/columns/{column_id}/off-sale` → `POST {base_url}/shop/columns/{column_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- 下架：200, status=off_sale
- 再次发布：422（Phase 1 专栏下架后不可再发布）

**边界值测试**:

| 变体ID | 专栏状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM4-9-N1-B1 | published | POST off-sale | 200 | 正常下架 |
| VM4-9-N1-B2 | off_sale | POST publish | 422 | 专栏下架后不可再发布 |
| VM4-9-N1-B3 | draft | POST publish | 200 | draft 可发布 |
| VM4-9-N1-B4 | draft | POST off-sale | 409/422 | draft 不可下架 |
| VM4-9-N1-B5 | off_sale | POST off-sale | 409/422 | 重复下架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-9-N1-S1 | 专栏下架后不可再发布 | published → off_sale | POST publish | 422, Phase 1 不可再发布 |
| VM4-9-N1-S2 | 专栏下架后 A05 整页只读 | off_sale | GET 专栏详情 | 200, 返回只读标记 |
| VM4-9-N1-S3 | 专栏下架后关联商品状态 | 商品 status=on_sale | POST off-sale 专栏 | 200, 验证商品是否同步下架 |
| VM4-9-N1-S4 | 课时下架后可再发布 | 课时 off_sale | POST lesson publish | 200, 课时可再发布（与专栏不同） |

---

### VM4-10-N1: 视频课时校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建专栏（{column_id}），status=draft

**API**: `POST {base_url}/shop/columns/{column_id}/lessons`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "title": "视频课时",
  "type": "video",
  "video_file_id": "{video_file_id}",
  "duration_sec": 1200
}
```

**期望结果**:
- 合法视频：201
- 非法视频：422

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-10-N1-B1 | video format | .mp4 | 合法格式 | 201 | mp4 允许 |
| VM4-10-N1-B2 | video format | .mov | 合法格式 | 201 | mov 允许 |
| VM4-10-N1-B3 | video format | .avi | 格式不符 | 422 | 仅 mp4/mov |
| VM4-10-N1-B4 | video format | .mkv | 格式不符 | 422 | 仅 mp4/mov |
| VM4-10-N1-B5 | video size | 2GB（=2048MB） | 边界值 | 201 | <=2GB |
| VM4-10-N1-B6 | video size | 2GB+1MB | 超大 | 422 | >2GB |
| VM4-10-N1-B7 | duration_sec | 180分钟=10800秒 | 边界值 | 201 | <=180 分钟 |
| VM4-10-N1-B8 | duration_sec | 181分钟=10860秒 | 超时 | 422 | >180 分钟 |
| VM4-10-N1-B9 | transcode status | processing | 未完成 | 422 | 需 ready |
| VM4-10-N1-B10 | transcode status | failed | 转码失败 | 422 | 需 ready |
| VM4-10-N1-B11 | video_file_id | null | 空值 | 422 | video 类型必须传 video_file_id |
| VM4-10-N1-B12 | duration_sec | 0 | 零值 | 422 | 时长不能为 0 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-10-N1-S1 | 正常创建 mp4 课时 | 视频 ready, 500MB, 1200s | POST 创建 | 201 |
| VM4-10-N1-S2 | avi 格式被拒 | 视频 .avi | POST 创建 | 422 |
| VM4-10-N1-S3 | 超 2GB 被拒 | 视频 2.1GB | POST 创建 | 422 |
| VM4-10-N1-S4 | 超 180 分钟被拒 | 视频 181 分钟 | POST 创建 | 422 |
| VM4-10-N1-S5 | 转码未完成被拒 | 视频 processing | POST 创建 | 422 |

---

### VM4-10-N2: 图文课时校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建专栏（{column_id}），status=draft
- 图片文件已上传：jpg/png/gif 格式，大小 <=5MB

**API**: `POST {base_url}/shop/columns/{column_id}/lessons`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "title": "图文课时",
  "type": "article",
  "content_body": "这是图文课时的正文内容，至少 10 个字。",
  "images": [
    {"file_id": "{image_file_id_1}", "sort": 1}
  ]
}
```

**期望结果**:
- 合法图文：201
- 非法图文：422

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-10-N2-B1 | content_body | "1234567890"（10 字） | 最小长度 | 201 | 正文 >=10 字 |
| VM4-10-N2-B2 | content_body | "123456789"（9 字） | 不足 | 422 | 正文 <10 字 |
| VM4-10-N2-B3 | content_body | "" | 空值 | 422 | 正文不能为空 |
| VM4-10-N2-B4 | content_body | "a".repeat(50000) | 最大长度 | 201 | 正文 <=50000 字 |
| VM4-10-N2-B5 | content_body | "a".repeat(50001) | 超长 | 422 | 正文 >50000 字 |
| VM4-10-N2-B6 | images count | 20 张 | 最大数量 | 201 | 图片 <=20 张 |
| VM4-10-N2-B7 | images count | 21 张 | 超量 | 422 | 图片 >20 张 |
| VM4-10-N2-B8 | image size | 5MB（单张） | 边界值 | 201 | 图片 <=5MB |
| VM4-10-N2-B9 | image size | 5.1MB（单张） | 超大 | 422 | 图片 >5MB |
| VM4-10-N2-B10 | image format | .jpg | 合法格式 | 201 | jpg 允许 |
| VM4-10-N2-B11 | image format | .bmp | 格式不符 | 422 | 仅 jpg/png/gif |
| VM4-10-N2-B12 | title | "" | 空值 | 422 | 标题不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-10-N2-S1 | 正常创建图文课时 | 正文 100 字 + 3 张 jpg | POST 创建 | 201 |
| VM4-10-N2-S2 | 正文 9 字被拒 | 正文 9 字 | POST 创建 | 422 |
| VM4-10-N2-S3 | 21 张图被拒 | 21 张图片 | POST 创建 | 422 |
| VM4-10-N2-S4 | 无标题被拒 | title="" | POST 创建 | 422 |
| VM4-10-N2-S5 | 正文+标题+图片齐全 | 正文 10 字 + 标题 + 1 张 png | POST 创建 | 201 |

---

### VM4-10-N3: 课时下架再发布

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建专栏（{column_id}），含已发布课时（{lesson_id}），课时 status=published

**API**: `POST {base_url}/shop/lessons/{lesson_id}/off-sale` → `POST {base_url}/shop/lessons/{lesson_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- 课时下架：200, status=off_sale
- 课时再发布：200, status=published（课时下架后可再发布，与专栏不同）

**边界值测试**:

| 变体ID | 课时状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM4-10-N3-B1 | published | POST off-sale | 200 | 正常下架 |
| VM4-10-N3-B2 | off_sale | POST publish | 200 | 课时可再发布 |
| VM4-10-N3-B3 | draft | POST off-sale | 409/422 | draft 不可下架 |
| VM4-10-N3-B4 | draft | POST publish | 200 | draft 可发布 |
| VM4-10-N3-B5 | off_sale | POST off-sale | 409/422 | 重复下架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-10-N3-S1 | 课时下架后可再发布 | published → off_sale | POST publish | 200, status=published |
| VM4-10-N3-S2 | 课时下架后编辑再发布 | off_sale → 编辑 → publish | 依次执行 | 200, published |
| VM4-10-N3-S3 | 多次下架上架循环 | published → off_sale → published → off_sale | 依次执行 | 每次 200 |

---

### VM4-12-N1: online_view 硬校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建 online_view 资料包（{digital_package_id}），仅含 .zip 文件（无可预览文件）

**API**: `POST {base_url}/shop/digital-packages/{digital_package_id}/publish`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**: `{}`

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息：online_view 模式发布需至少 1 个可预览文件（pdf/doc/docx）

**边界值测试**:

| 变体ID | 文件组成 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM4-12-N1-B1 | 仅 .zip | POST publish | 422 | 无可预览文件 |
| VM4-12-N1-B2 | .zip + .pdf | POST publish | 200 | 有可预览文件 |
| VM4-12-N1-B3 | .zip + .doc | POST publish | 200 | .doc 可预览 |
| VM4-12-N1-B4 | .zip + .docx | POST publish | 200 | .docx 可预览 |
| VM4-12-N1-B5 | 仅 .pdf | POST publish | 200 | 仅 pdf 可预览 |
| VM4-12-N1-B6 | .zip + .exe | POST publish | 422 | .exe 不可预览且不在白名单 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-12-N1-S1 | online_view 无可预览文件发布 | 仅 .zip | POST publish | 422, 硬校验失败 |
| VM4-12-N1-S2 | online_view 有 pdf 发布 | .zip + .pdf | POST publish | 200, published |
| VM4-12-N1-S3 | download 模式无可预览文件发布 | 仅 .zip | POST publish | 200, download 无此限制 |
| VM4-12-N1-S4 | 添加 pdf 后再发布 | .zip → 添加 .pdf → publish | PUT + POST publish | 200, published |

---

### VM4-12-N2: online_view 软校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建 online_view 资料包（{digital_package_id}），仅含 .zip 文件

**API**: `PUT {base_url}/shop/digital-packages/{digital_package_id}`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "title": "更新资料包标题"
}
```

**期望结果**:
- HTTP Status: 200
- Response Body 含警告信息（黄条警告）：无可预览文件
- 数据库: 记录已更新

**边界值测试**:

| 变体ID | 文件组成 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM4-12-N2-B1 | 仅 .zip | PUT 保存 | 200 + 警告 | 软校验通过, 黄条警告 |
| VM4-12-N2-B2 | .zip + .pdf | PUT 保存 | 200 无警告 | 有可预览文件 |
| VM4-12-N2-B3 | 无文件 | PUT 保存 | 422 | 至少 1 个文件 |
| VM4-12-N2-B4 | 仅 .zip → 添加 .pdf | PUT 保存 | 200 无警告 | 添加后警告消失 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-12-N2-S1 | online_view 无可预览文件保存 | 仅 .zip | PUT 保存 | 200, 黄条警告 |
| VM4-12-N2-S2 | online_view 有可预览文件保存 | .zip + .pdf | PUT 保存 | 200, 无警告 |
| VM4-12-N2-S3 | 软校验保存后尝试发布 | 仅 .zip | PUT 保存 → POST publish | 200(保存) → 422(发布) |

---

### VM4-3-N1: 次数卡字段校验

**前置条件**:
- 商家A 已入驻，merchant_token 已获取
- 已创建服务（shop_service_offers），mode=times_card

**API**: `POST {base_url}/shop/service-offers`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "mode": "times_card",
  "total_times": 10,
  "title": "10 次卡服务"
}
```

**期望结果**:
- 合法请求：201
- 非法请求：422

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM4-3-N1-B1 | mode | "times_card" | 合法值 | 201 | 次数卡模式 |
| VM4-3-N1-B2 | mode | "booking" | 合法值 | 201 | 预约模式 |
| VM4-3-N1-B3 | mode | "invalid" | 非法枚举 | 422 | 仅 booking/times_card |
| VM4-3-N1-B4 | total_times | 1 | 最小值 | 201 | 最少 1 次 |
| VM4-3-N1-B5 | total_times | 0 | 零值 | 422 | 次数卡需 >=1 |
| VM4-3-N1-B6 | total_times | -1 | 负数 | 422 | 不能为负 |
| VM4-3-N1-B7 | total_times | null（mode=times_card） | 缺失 | 422 | 次数卡模式必须传 total_times |
| VM4-3-N1-B8 | total_times | 999999 | 大值 | 201 | 无明确上限 |
| VM4-3-N1-B9 | mode | "booking", total_times=10 | 不匹配 | 422/201 | booking 模式不需要 total_times |
| VM4-3-N1-B10 | mode | 不传 | 缺失 | 422 | mode 为必填 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM4-3-N1-S1 | 创建次数卡服务 | mode=times_card, total_times=10 | POST 创建 | 201 |
| VM4-3-N1-S2 | 创建预约服务 | mode=booking | POST 创建 | 201 |
| VM4-3-N1-S3 | 次数卡不传 total_times | mode=times_card, 无 total_times | POST 创建 | 422, 必填 |
| VM4-3-N1-S4 | 预约模式传 total_times | mode=booking, total_times=10 | POST 创建 | 422/201, 验证是否忽略 |

---
---

# M5 订单权益

## M5 测试用例总览

| 用例ID | 标题 | 类型 | 优先级 |
|--------|------|------|--------|
| VM5-1 | 创建订单（私域） | 正向+边界 | P0 |
| VM5-2 | 订单幂等（client_token） | 场景 | P0 |
| VM5-3 | 订单状态流转 | 场景 | P0 |
| VM5-4 | 权益创建 | 正向+边界 | P0 |
| VM5-5 | 权益状态流转 | 场景 | P0 |
| VM5-6 | 退款 always_allow | 场景 | P0 |
| VM5-7 | 退款 before_fulfill | 场景 | P0 |
| VM5-8 | 退款 manual_only | 场景 | P0 |
| VM5-9 | 部分退款拒绝 | 边界 | P0 |
| VM5-10 | 已开票退款 | 场景 | P1 |
| VM5-11 | 买家身份归一 | 场景 | P0 |
| VM5-12 | 多店场景 | 场景 | P0 |
| VM5-13 | 商品下架与已购权益 | 场景 | P0 |
| VM5-14 | 内容版本策略 | 场景 | P1 |
| VM5-1-N1 | 公域订单创建（external_order_no 幂等） | 正向+边界 | P0 |
| VM5-1-N2 | 订单金额边界 | 边界 | P0 |
| VM5-1-N3 | 跨租户订单隔离 | 场景 | P0 |
| VM5-2-N1 | client_token 跨买家 | 边界 | P0 |
| VM5-3-N1 | 订单超时关单 | 场景 | P1 |
| VM5-3-N2 | 公域 Webhook 直写退款 | 场景 | P1 |
| VM5-3-N3 | 领权流程（claim_pending） | 场景 | P1 |
| VM5-3-N4 | 退款回调失败重试 | 场景 | P1 |
| VM5-4-N1 | 权益幂等（order_item_id） | 边界 | P0 |
| VM5-5-N1 | 权益过期 | 场景 | P1 |
| VM5-5-N2 | 次数卡用尽 | 场景 | P1 |
| VM5-6-N1 | always_allow 退款理由校验 | 边界 | P0 |
| VM5-7-N1 | before_fulfill 零履约判定 | 场景 | P0 |
| VM5-7-N2 | before_fulfill 非零履约禁退 | 场景 | P0 |
| VM5-9-N1 | 单 item 订单全额退款 | 边界 | P0 |
| VM5-10-N1 | 已开票 needs_red_flush | 场景 | P1 |
| VM5-11-N1 | mobile+openid 归一 | 场景 | P0 |
| VM5-13-N1 | 商家 suspended 已购不阻断 | 场景 | P1 |
| VM5-13-N2 | 平台强制下架拒单 | 场景 | P1 |

---

### VM5-1: 创建订单（私域）

**前置条件**:
- 商家A 已入驻，有店铺 store_id，有 on_sale 商品 {product_id}（type=course, price_cents=9900）
- 买家A 已注册，buyer_token 已获取
- 买家A 尚未购买该商品

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "product_id": "{product_id}",
  "client_token": "550e8400-e29b-41d4-a716-446655440000",
  "buyer_mobile": "13800000001"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `order_no`（如 202608120001）, `status="pending_payment"`, `amount_cents=9900`, `channel="wechat"`, `buyer_id`
- 数据库: `shop_orders` 新增 1 条 `status=pending_payment` 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM5-1-B1 | product_id | "non-existent" | 不存在 | 404/422 | 商品不存在 |
| VM5-1-B2 | product_id | null | 空值 | 422 | product_id 必填 |
| VM5-1-B3 | shop_id | "non-existent" | 不存在 | 404/422 | 店铺不存在 |
| VM5-1-B4 | client_token | null/不传 | 空值 | 422 | client_token 必填（幂等键） |
| VM5-1-B5 | client_token | "" | 空字符串 | 422 | client_token 不能为空 |
| VM5-1-B6 | buyer_mobile | "123" | 格式错误 | 422 | 手机号格式不正确 |
| VM5-1-B7 | buyer_mobile | null | 可选字段 | 201 | buyer_mobile 可选 |
| VM5-1-B8 | product status | "draft" | 不可购买 | 422 | 商品非 on_sale 不可购买 |
| VM5-1-B9 | product status | "off_sale" | 不可购买 | 422 | 商品已下架 |
| VM5-1-B10 | Authorization | 无 token | 未认证 | 401 | 需要买家登录 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-1-S1 | 正常创建私域订单 | 商品 on_sale | POST 创建 | 201, pending_payment |
| VM5-1-S2 | 商品 draft 不可购买 | 商品 status=draft | POST 创建 | 422, 商品未上架 |
| VM5-1-S3 | 商品 off_sale 不可购买 | 商品 status=off_sale | POST 创建 | 422, 商品已下架 |
| VM5-1-S4 | 不传 buyer_mobile | buyer_mobile 可选 | POST 创建, 不含 buyer_mobile | 201, buyer_mobile=null |
| VM5-1-S5 | 跨店购买 | 商品属于 store_id_A, 请求 store_id_B | POST 创建 | 422/404, 跨店隔离 |

---

### VM5-2: 订单幂等（client_token）

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}
- 买家A 已注册，buyer_token 已获取
- client_token = "idempotent-token-001"

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "product_id": "{product_id}",
  "client_token": "idempotent-token-001"
}
```

**期望结果**:
- 第一次请求：201, 返回 order_id=X
- 第二次请求（同 buyer + 同 client_token）：201, 返回同一 order_id=X
- 数据库: `shop_orders` 仅新增 1 条记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM5-2-B1 | client_token | 同一 token 重复请求 | 幂等 | 201, 同一 order_id | 同 buyer+token 返回同一订单 |
| VM5-2-B2 | client_token | 不同 token | 非幂等 | 201, 不同 order_id | 不同 token 创建不同订单 |
| VM5-2-B3 | client_token | 同一 token, 不同 buyer | 非幂等 | 201, 不同 order_id | 不同 buyer 不共享幂等 |
| VM5-2-B4 | client_token | 同一 token, 不同 product | 非幂等 | 422/201 | 验证是否允许变更商品 |
| VM5-2-B5 | client_token | "" | 空值 | 422 | client_token 不能为空 |
| VM5-2-B6 | client_token | null | 空值 | 422 | client_token 必填 |
| VM5-2-B7 | client_token | 超长字符串(>128) | 超长 | 422/201 | 验证长度限制 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-2-S1 | 重复请求返回同一订单 | 同 buyer + 同 client_token | POST 两次 | 201, 同一 order_id, DB 仅 1 条 |
| VM5-2-S2 | 不同 token 创建不同订单 | 同 buyer + 不同 client_token | POST 两次 | 201, 不同 order_id, DB 2 条 |
| VM5-2-S3 | 已支付订单重复请求 | 订单已 paid | POST 同 client_token | 201, 返回已存在的 paid 订单 |
| VM5-2-S4 | 已关闭订单重复请求 | 订单已 closed | POST 同 client_token | 201, 返回已存在的 closed 订单 |
| VM5-2-S5 | 并发请求同一 token | 同时 2 个请求 | POST 并发 | 201, 仅创建 1 个订单 |

---

### VM5-3: 订单状态流转

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}
- 买家A 已创建订单 {order_id}，status=pending_payment
- 支付回调 Webhook 已配置

**API**: 支付回调 `POST {base_url}/webhooks/payment` + 订单查询 `GET {base_url}/mp/shop/orders/{order_id}`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**（支付回调）:
```json
{
  "order_id": "{order_id}",
  "payment_status": "paid",
  "amount_cents": 9900,
  "channel": "wechat"
}
```

**期望结果**:
- 支付成功后：status=pending_payment → paid
- 超时未支付：status=pending_payment → closed
- 数据库: `shop_orders` 记录 status 更新

**边界值测试**:

| 变体ID | 当前状态 | 目标状态 | 触发条件 | 期望Status | 说明 |
|--------|---------|---------|---------|-----------|------|
| VM5-3-B1 | pending_payment | paid | 支付回调成功 | 200, status=paid | F1 支付完成 |
| VM5-3-B2 | pending_payment | closed | 超时未支付 | 200, status=closed | 订单超时关单 |
| VM5-3-B3 | pending_payment | closed | 买家主动取消 | 200, status=closed | 买家取消 |
| VM5-3-B4 | paid | refunding | 发起退款 | 200, status=refunding | 退款流程开始 |
| VM5-3-B5 | refunding | refunded | 退款回调成功 | 200, status=refunded | 全额退款完成 |
| VM5-3-B6 | refunding | partial_refunded | 部分退款回调 | 200, status=partial_refunded | 部分退款 |
| VM5-3-B7 | paid | closed | 非法转换 | 409/422 | 已支付不可关单 |
| VM5-3-B8 | closed | paid | 非法转换 | 409/422 | 已关单不可支付 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-3-S1 | 正常支付流程 | pending_payment | 支付回调 | status=paid, 自动创建 entitlement |
| VM5-3-S2 | 超时关单 | pending_payment, 超时 | 定时任务关单 | status=closed |
| VM5-3-S3 | 买家取消订单 | pending_payment | 买家取消 | status=closed |
| VM5-3-S4 | 全额退款流程 | paid → refunding → refunded | 发起退款 + 回调 | status=refunded, entitlement=revoked |
| VM5-3-S5 | 非法状态转换 | closed → paid | 支付回调 | 409/422, 已关单不可支付 |

---

### VM5-4: 权益创建

**前置条件**:
- 买家A 已支付订单 {order_id}，status=paid
- 订单含 1 个 order_item（product_id, type=course）

**API**: `GET {base_url}/mp/shop/entitlements`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- Response Body 含权益记录: `id`, `status="active"`, `order_item_id`, `times_total=null`（课程类）, `expires_at`
- 数据库: `shop_entitlements` 新增 1 条 `status=active` 记录，`order_item_id` 唯一

**边界值测试**:

| 变体ID | 商品类型 | 权益字段 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM5-4-B1 | course | times_total=null | 200 | 课程无次数限制 |
| VM5-4-B2 | digital | times_total=null | 200 | 资料包无次数限制 |
| VM5-4-B3 | service(booking) | times_total=null | 200 | 预约服务无次数限制 |
| VM5-4-B4 | service(times_card) | times_total=10, times_used=0 | 200 | 次数卡有总次数 |
| VM5-4-B5 | 重复支付回调 | 同一 order_item_id | 200, 不重复创建 | UK(order_item_id) 幂等 |
| VM5-4-B6 | order_item_id | null | 422 | order_item_id 不能为空 |
| VM5-4-B7 | 跨店权益 | 商品属于 store_A | GET via store_B | 404/403 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-4-S1 | 支付后自动创建权益 | 订单 paid | GET entitlements | 200, status=active |
| VM5-4-S2 | 次数卡权益 | service times_card, total_times=10 | GET entitlements | 200, times_total=10, times_used=0 |
| VM5-4-S3 | 权益幂等 | 重复支付回调 | GET entitlements | 200, 仅 1 条权益（UK order_item_id） |
| VM5-4-S4 | 权益 expires_at | 课程有有效期 | GET entitlements | 200, expires_at 正确设置 |

---

### VM5-5: 权益状态流转

**前置条件**:
- 买家A 有权益 {entitlement_id}，status=active
- 次数卡权益 times_total=5, times_used=4

**API**: `GET {base_url}/mp/shop/entitlements/{entitlement_id}`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**: 无

**期望结果**:
- 正常查询：200, status=active
- 权益过期：status=expired
- 次数用尽：status=consumed
- 退款撤销：status=revoked

**边界值测试**:

| 变体ID | 当前状态 | 目标状态 | 触发条件 | 期望Status | 说明 |
|--------|---------|---------|---------|-----------|------|
| VM5-5-B1 | pending | active | 支付完成 | 200, active | 支付后激活 |
| VM5-5-B2 | active | expired | expires_at 到期 | 200, expired | 过期自动变更 |
| VM5-5-B3 | active | revoked | 退款完成 | 200, revoked | 退款撤销权益 |
| VM5-5-B4 | active | consumed | times_used=times_total | 200, consumed | 次数卡用尽 |
| VM5-5-B5 | expired | active | 非法转换 | 409/422 | 过期不可恢复 |
| VM5-5-B6 | revoked | active | 非法转换 | 409/422 | 撤销不可恢复 |
| VM5-5-B7 | consumed | active | 非法转换 | 409/422 | 用尽不可恢复 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-5-S1 | 权益正常激活 | pending → active | 支付完成 | status=active |
| VM5-5-S2 | 权益过期 | active, expires_at 已过 | 定时任务检查 | status=expired |
| VM5-5-S3 | 次数卡用尽 | active, times_used=4 → 核销 1 次 | 核销 | status=consumed, times_used=5 |
| VM5-5-S4 | 退款撤销权益 | active | 退款完成 | status=revoked |
| VM5-5-S5 | 非法恢复 | expired | 尝试激活 | 409/422, 不可恢复 |

---

### VM5-6: 退款 always_allow

**前置条件**:
- 买家A 已购买商品 {product_id}，refund_policy=always_allow
- 订单 status=paid, 权益 status=active
- 零履约状态（无学习/下载/核销记录）

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**（买家自助退款）:
```json
{
  "reason_code": "buyer_request",
  "remark": "不想买了"
}
```

**期望结果**:
- HTTP Status: 200
- 订单 status=refunding → refunded
- 权益 status=revoked
- 数据库: `shop_orders` status 更新, `shop_entitlements` status=revoked

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM5-6-B1 | reason_code | "buyer_request" | 合法值 | 200 | 买家请求 |
| VM5-6-B2 | reason_code | "quality_issue" | 合法值 | 200 | 质量问题 |
| VM5-6-B3 | reason_code | "duplicate" | 合法值 | 200 | 重复购买 |
| VM5-6-B4 | reason_code | "other" | 合法值 | 200 | 其他原因 |
| VM5-6-B5 | reason_code | "invalid_reason" | 非法枚举 | 422 | 不在枚举范围 |
| VM5-6-B6 | reason_code | null | 空值 | 422 | reason_code 必填 |
| VM5-6-B7 | order status | "pending_payment" | 未支付 | 422/409 | 未支付不可退款 |
| VM5-6-B8 | order status | "closed" | 已关单 | 422/409 | 已关单不可退款 |
| VM5-6-B9 | order status | "refunded" | 已退款 | 422/409 | 不可重复退款 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-6-S1 | 买家零履约自助退款 | paid, 零履约, always_allow | POST refund | 200, refunding→refunded, entitlement=revoked |
| VM5-6-S2 | 买家非零履约自助退款 | paid, 有学习记录, always_allow | POST refund | 200（always_allow 允许）, entitlement=revoked |
| VM5-6-S3 | 商家发起退款 | paid, always_allow | POST refund with merchant_token | 200, refunding→refunded |
| VM5-6-S4 | always_allow 有履约仍可退 | paid, 有下载记录 | POST refund | 200, always_allow 不限制 |
| VM5-6-S5 | 已退款不可重复 | refunded | POST refund | 422/409, 不可重复退款 |

---

### VM5-7: 退款 before_fulfill

**前置条件**:
- 买家A 已购买商品 {product_id}，refund_policy=before_fulfill
- 订单 status=paid, 权益 status=active

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {buyer_token}` 或 `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "不想买了"
}
```

**期望结果**:
- 零履约 + 买家自助：200
- 非零履约 + 买家自助：422（买家端禁用）
- 商家发起（任意履约状态）：200

**边界值测试**:

| 变体ID | 履约状态 | 发起方 | 期望Status | 说明 |
|--------|---------|-------|-----------|------|
| VM5-7-B1 | 零履约 | 买家 | 200 | 零履约可自助退 |
| VM5-7-B2 | 课程有 progress>0 | 买家 | 422 | 有学习记录禁用 |
| VM5-7-B3 | 资料已下载 | 买家 | 422 | 已下载禁用 |
| VM5-7-B4 | 服务已核销 | 买家 | 422 | 已核销禁用 |
| VM5-7-B5 | 服务 used_count>0 | 买家 | 422 | 有使用记录禁用 |
| VM5-7-B6 | 零履约 | 商家 | 200 | 商家可发起 |
| VM5-7-B7 | 有学习记录 | 商家 | 200 | 商家可发起 |
| VM5-7-B8 | 有下载记录 | 商家 | 200 | 商家可发起 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-7-S1 | 买家零履约自助退款 | paid, 零履约, before_fulfill | POST refund (buyer) | 200, refunded, entitlement=revoked |
| VM5-7-S2 | 买家有学习记录自助退款 | paid, 课程 progress>0 | POST refund (buyer) | 422, 买家端禁用 |
| VM5-7-S3 | 买家有下载记录自助退款 | paid, 资料已下载 | POST refund (buyer) | 422, 买家端禁用 |
| VM5-7-S4 | 商家发起退款（有履约） | paid, 有学习记录 | POST refund (merchant) | 200, refunded, entitlement=revoked |
| VM5-7-S5 | 买家有核销记录自助退款 | paid, 服务已核销 | POST refund (buyer) | 422, 买家端禁用 |

---

### VM5-8: 退款 manual_only

**前置条件**:
- 买家A 已购买商品 {product_id}，refund_policy=manual_only
- 订单 status=paid, 权益 status=active

**API**: 
- 买家端查询：`GET {base_url}/mp/shop/orders/{order_id}`
- 商家退款：`POST {base_url}/shop/orders/{order_id}/refund`

**Headers**: `Authorization: Bearer {buyer_token}` 或 `Authorization: Bearer {merchant_token}`

**请求体**（商家退款）:
```json
{
  "reason_code": "buyer_request",
  "remark": "商家同意退款处理"
}
```

**期望结果**:
- 买家端不展示申请退款按钮
- 买家发起退款：422/403
- 商家发起退款：200

**边界值测试**:

| 变体ID | 发起方 | 履约状态 | 期望Status | 说明 |
|--------|-------|---------|-----------|------|
| VM5-8-B1 | 买家 | 零履约 | 403/422 | 买家端不可发起 |
| VM5-8-B2 | 买家 | 有履约 | 403/422 | 买家端不可发起 |
| VM5-8-B3 | 商家 | 零履约 | 200 | 商家可发起 |
| VM5-8-B4 | 商家 | 有履约 | 200 | 商家可发起 |
| VM5-8-B5 | 商家 | remark="abc"（3 字） | 422 | 商家发起 remark >=4 字 |
| VM5-8-B6 | 商家 | remark="" | 422 | remark 不能为空 |
| VM5-8-B7 | 商家 | reason_code=null | 422 | reason_code 必填 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-8-S1 | 买家端不展示退款入口 | paid, manual_only | GET order detail (buyer) | 200, 响应中无退款入口/按钮 |
| VM5-8-S2 | 买家发起退款被拒 | paid, manual_only | POST refund (buyer) | 403/422, 买家端不可发起 |
| VM5-8-S3 | 商家发起退款成功 | paid, 零履约 | POST refund (merchant) | 200, refunded, entitlement=revoked |
| VM5-8-S4 | 商家 remark 不足 4 字 | paid | POST refund, remark="abc" | 422, remark >=4 字 |
| VM5-8-S5 | 商家有履约仍可退 | paid, 有学习记录 | POST refund (merchant) | 200, 商家不受履约限制 |

---

### VM5-9: 部分退款拒绝

**前置条件**:
- 买家A 已购买商品 {product_id}，私域订单
- 订单 status=paid, amount_cents=9900

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**（部分退款）:
```json
{
  "reason_code": "buyer_request",
  "remark": "部分退款测试",
  "amount_cents": 5000
}
```

**期望结果**:
- HTTP Status: 422
- Response Body 含错误信息：Phase 1 仅支持全额退款

**边界值测试**:

| 变体ID | 退款金额 | 边界类型 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM5-9-B1 | 5000（< paid 9900） | 部分退款 | 422 | Phase 1 仅支持全额退款 |
| VM5-9-B2 | 9900（= paid） | 全额退款 | 200 | 全额退款允许 |
| VM5-9-B3 | 9901（> paid） | 超额 | 422 | 退款金额不可超过支付金额 |
| VM5-9-B4 | 0 | 零值 | 422 | 退款金额不能为 0 |
| VM5-9-B5 | -1 | 负数 | 422 | 退款金额不能为负 |
| VM5-9-B6 | 不传 amount_cents | 默认全额 | 200 | 不传金额默认全额退款 |
| VM5-9-B7 | 单 item 订单部分退款 | amount < paid | 422 | 单 item 仅全额退款关权 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-9-S1 | 私域部分退款被拒 | paid=9900, refund=5000 | POST refund | 422, Phase 1 仅支持全额退款 |
| VM5-9-S2 | 全额退款允许 | paid=9900, refund=9900 | POST refund | 200, refunded, entitlement=revoked |
| VM5-9-S3 | 不传金额默认全额 | paid=9900 | POST refund, 不含 amount_cents | 200, 全额退款 |
| VM5-9-S4 | 单 item 订单仅全额关权 | 单 item, paid | POST 全额退款 | 200, entitlement=revoked |

---

### VM5-10: 已开票退款

**前置条件**:
- 买家A 已购买商品，订单 status=paid
- 已开票：invoice_requests.status=issued
- refund_policy=always_allow

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "已开票退款测试"
}
```

**期望结果**:
- HTTP Status: 200
- 退款成功，但 needs_red_flush=true
- 数据库: `shop_orders` status=refunded, `invoice_requests` needs_red_flush=true

**边界值测试**:

| 变体ID | 开票状态 | 期望Status | 说明 |
|--------|---------|-----------|------|
| VM5-10-B1 | invoice_requests.status=issued | 200, needs_red_flush=true | 已开票需红冲 |
| VM5-10-B2 | invoice_requests.status=pending | 200, needs_red_flush=false | 未开票无需红冲 |
| VM5-10-B3 | invoice_requests.status=none | 200, needs_red_flush=false | 无发票请求 |
| VM5-10-B4 | invoice_requests.status=voided | 200, needs_red_flush=false | 已作废无需红冲 |
| VM5-10-B5 | 多张发票部分已开 | 1 issued + 1 pending | 200, needs_red_flush=true | 有任一已开需红冲 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-10-S1 | 已开票退款需红冲 | invoice issued | POST refund | 200, needs_red_flush=true |
| VM5-10-S2 | 未开票退款无需红冲 | invoice pending | POST refund | 200, needs_red_flush=false |
| VM5-10-S3 | 已开票退款仍允许退 | invoice issued, always_allow | POST refund | 200, 允许退但标记红冲 |
| VM5-10-S4 | 已开票退款权益仍撤销 | invoice issued | POST refund → GET entitlement | 200, entitlement=revoked |

---

### VM5-11: 买家身份归一

**前置条件**:
- 商家A 已入驻（TENANT_A）
- 买家A 手机号 13800000001，在 TENANT_A 维度已有 buyer 记录
- 买家A 有 openid=wx_open_id_001

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "product_id": "{product_id}",
  "client_token": "buyer-identity-test-001",
  "buyer_mobile": "13800000001"
}
```

**期望结果**:
- HTTP Status: 201
- buyer_id 为 TENANT_A 下 mobile=13800000001 对应的唯一 buyer
- 数据库: `shop_buyers` UK(tenant_id, mobile) 不产生重复记录

**边界值测试**:

| 变体ID | 场景 | 输入值 | 期望Status | 说明 |
|--------|------|--------|-----------|------|
| VM5-11-B1 | 同 mobile 再次下单 | mobile=13800000001 | 201, 同一 buyer_id | 归一到已有 buyer |
| VM5-11-B2 | 同 mobile 不同 openid | mobile 同, openid 不同 | 201, 同一 buyer_id | mobile 归一 |
| VM5-11-B3 | 不同 mobile 同 openid | mobile 不同, openid 同 | 201, 不同 buyer_id | 不同 mobile 不同 buyer |
| VM5-11-B4 | mobile=null | 不传 mobile | 201, 新 buyer 或已有 openid buyer | 无 mobile 时按 openid 归一 |
| VM5-11-B5 | 同 tenant 同 mobile 同 openid | 完全相同 | 201, 同一 buyer_id | 完全归一 |
| VM5-11-B6 | 不同 tenant 同 mobile | TENANT_B 同 mobile | 201, 不同 buyer_id | 跨租户不归一 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-11-S1 | 同 mobile 归一 | TENANT_A 已有 buyer(mobile=13800000001) | 下单, 同 mobile | 201, 同一 buyer_id, 无新 buyer |
| VM5-11-S2 | 禁止 FK 到 CRM contacts | buyer 创建时 | 检查 DB | buyer 表无 FK 关联 CRM contacts |
| VM5-11-S3 | 禁止同 tenant 双 buyer | 同 tenant 同 (mobile, openid) | 下单 | 201, 仅 1 条 buyer 记录 |
| VM5-11-S4 | 不同 tenant 不归一 | TENANT_B 同 mobile | 下单 | 201, TENANT_B 新 buyer_id |
| VM5-11-S5 | mobile 格式校验 | mobile="123" | 下单 | 422, 手机号格式错误 |

---

### VM5-12: 多店场景

**前置条件**:
- 商家A 有 2 个店铺：store_id_1, store_id_2
- store_id_1 有 on_sale 商品 {product_id_1}
- store_id_2 有 on_sale 商品 {product_id_2}
- 买家A 已注册

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id_1}",
  "product_id": "{product_id_1}",
  "client_token": "multi-store-test-001"
}
```

**期望结果**:
- HTTP Status: 201
- 订单绑定 shop_id=store_id_1
- 无跨店购物车，每次下单绑定当前 shop_id

**边界值测试**:

| 变体ID | 场景 | 输入值 | 期望Status | 说明 |
|--------|------|--------|-----------|------|
| VM5-12-B1 | 在 store_1 下单 product_1 | shop_id=store_1, product=product_1 | 201 | 正常同店下单 |
| VM5-12-B2 | 在 store_1 下单 product_2 | shop_id=store_1, product=product_2 | 422/404 | 跨店商品不可购买 |
| VM5-12-B3 | 在 store_2 下单 product_2 | shop_id=store_2, product=product_2 | 201 | 正常同店下单 |
| VM5-12-B4 | 不同店上架相同 product_id | store_1 和 store_2 都有 product_id_X | 下单 | 视为不同 SKU |
| VM5-12-B5 | 无 shop_id | 不传 shop_id | 422 | shop_id 必填 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-12-S1 | 每次下单绑定当前 shop_id | store_1 有商品 | POST shop_id=store_1 | 201, order.shop_id=store_1 |
| VM5-12-S2 | 无跨店购物车 | 买家已在 store_1 下单 | 尝试在 store_2 合并下单 | 422, 无跨店购物车 |
| VM5-12-S3 | M06 已购 tenant 级汇总 | 买家在 store_1 和 store_2 各购买 1 个 | GET 已购列表 | 200, 返回 tenant 级汇总（2 个权益） |
| VM5-12-S4 | M11 订单 tenant 级汇总 | 买家在 store_1 和 store_2 各 1 单 | GET 订单列表 | 200, 返回 tenant 级汇总（2 个订单） |
| VM5-12-S5 | 不同店相同 product_id 不同 SKU | store_1 和 store_2 都上架 product_id_X | 分别下单 | 201, 2 个不同 order_item, 2 个不同 entitlement |

---

### VM5-13: 商品下架与已购权益

**前置条件**:
- 买家A 已购买商品 {product_id}，订单 paid，权益 active
- 商品 {product_id} 当前 status=on_sale

**API**: 
1. `POST {base_url}/shop/products/{product_id}/off-sale`（商家下架）
2. `GET {base_url}/mp/shop/entitlements/{entitlement_id}`（买家查询权益）
3. `POST {base_url}/mp/shop/orders`（新买家尝试购买）

**Headers**: 商家操作用 `merchant_token`，买家操作用 `buyer_token`

**请求体**: 状态转换无需 body

**期望结果**:
- 商品下架：200, status=off_sale
- 已购权益不受影响：200, status=active
- 新买家购买：422, 商品已下架

**边界值测试**:

| 变体ID | 商品状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM5-13-B1 | off_sale | 新买家购买 | 422 | 下架商品新买家不可购 |
| VM5-13-B2 | off_sale | 已购买家查询权益 | 200, active | 已购权益不受影响 |
| VM5-13-B3 | off_sale | 已购买家学习课程 | 200 | 履约不阻断 |
| VM5-13-B4 | rejected | 新买家购买 | 422 | 驳回商品不可购 |
| VM5-13-B5 | rejected | 已购买家查询权益 | 200, active | 已购权益不受影响 |
| VM5-13-B6 | 商家 suspended | 新买家购买 | 422 | 商家 suspended 新购拦截 |
| VM5-13-B7 | 商家 suspended | 已购买家学习 | 200 | 履约不阻断 |
| VM5-13-B8 | 平台 P07 强制下架 | 新 Webhook 订单 | 拒单 | 新 Webhook 拒单 |
| VM5-13-B9 | 平台 P07 强制下架 | 已购买家权益 | 200, active | 已购保留 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-13-S1 | 商品下架已购权益不变 | on_sale → off_sale, 买家已购 | 下架 + 查询权益 | 200, entitlement=active |
| VM5-13-S2 | 商品下架新买家不可购 | off_sale | 新买家 POST order | 422, 商品已下架 |
| VM5-13-S3 | 商家 suspended 已购不阻断 | 商家 suspended, 买家已购 | 买家学习课程 | 200, 履约正常 |
| VM5-13-S4 | 平台强制下架已购保留 | P07 强制下架 | 查询已购权益 | 200, entitlement=active |
| VM5-13-S5 | 平台强制下架新单拒收 | P07 强制下架 | 新 Webhook 订单 | 拒单, 422 |

---

### VM5-14: 内容版本策略

**前置条件**:
- 买家A 已购买课程商品，权益 active
- 课程专栏有 3 个课时，买家已学习课时 1
- 商家在买家购买后新增课时 4 并发布

**API**: `GET {base_url}/mp/shop/entitlements/{entitlement_id}/content`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- 返回最新发布的课时列表（含新增课时 4）
- 课程课时跟最新发布，不锁定购买时版本
- order_items 中的 title_snapshot/product_snapshot 仅用于订单展示

**边界值测试**:

| 变体ID | 内容变更 | 查询时机 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM5-14-B1 | 新增课时 | 购买后新增 | GET content | 200, 含新课时 |
| VM5-14-B2 | 修改课时内容 | 购买后修改 | GET content | 200, 返回最新内容 |
| VM5-14-B3 | 删除课时 | 购买后删除 | GET content | 200, 不含已删课时 |
| VM5-14-B4 | 资料包新增文件 | 购买后新增 | GET content | 200, 含新文件 |
| VM5-14-B5 | 资料包替换文件 | 购买后替换 | GET content | 200, 返回最新文件 |
| VM5-14-B6 | 快照对比 | 购买时 vs 当前 | GET order detail | 200, title_snapshot=购买时, content=最新 |
| VM5-14-B7 | 专栏下架 | 购买后下架 | GET content | 200, 仍可访问已购内容 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-14-S1 | 课程课时跟最新 | 购买后新增课时 | GET content | 200, 含新增课时 |
| VM5-14-S2 | 数字资料跟最新 | 购买后替换文件 | GET content | 200, 返回最新文件 |
| VM5-14-S3 | 快照仅用于展示 | 购买时标题=X, 现标题=Y | GET order + GET content | order.title_snapshot=X, content.title=Y |
| VM5-14-S4 | 专栏下架后仍可访问已购 | 专栏 off_sale, 买家已购 | GET content | 200, 内容可访问 |
| VM5-14-S5 | 课时下架后已购仍可学 | 课时 off_sale, 买家已购 | GET content | 200, 该课时仍可学习 |

---

### VM5-1-N1: 公域订单创建（external_order_no 幂等）

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}
- 公域渠道（doudian/dy_knowledge）Webhook 已配置
- external_order_no = "DD202608120001"

**API**: `POST {base_url}/webhooks/orders`（公域 Webhook 回调）
**Headers**: `X-Webhook-Signature: {signature}`, `Content-Type: application/json`

**请求体**:
```json
{
  "channel": "doudian",
  "external_order_no": "DD202608120001",
  "product_id": "{product_id}",
  "amount_cents": 9900,
  "buyer_mobile": "13800000001"
}
```

**期望结果**:
- HTTP Status: 201
- Response Body 含: `id`, `order_no`, `status="paid"`（公域直接 paid）, `channel="doudian"`, `external_order_no="DD202608120001"`
- 数据库: `shop_orders` 新增 1 条, UK(channel, external_order_no) 幂等

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM5-1-N1-B1 | external_order_no | "DD202608120001" | 正常 | 201 | 正常公域订单 |
| VM5-1-N1-B2 | external_order_no | 同一值重复 | 幂等 | 201, 同一 order_id | UK 幂等 |
| VM5-1-N1-B3 | external_order_no | 不同值 | 非幂等 | 201, 不同 order_id | 不同外部单号 |
| VM5-1-N1-B4 | channel | "doudian" | 合法值 | 201 | 抖店渠道 |
| VM5-1-N1-B5 | channel | "dy_knowledge" | 合法值 | 201 | 抖音知识渠道 |
| VM5-1-N1-B6 | channel | "wx_mp" | 合法值 | 201 | 微信小程序渠道 |
| VM5-1-N1-B7 | channel | "wechat" | 合法值 | 201 | 微信渠道 |
| VM5-1-N1-B8 | channel | "invalid_channel" | 非法枚举 | 422 | 渠道非法 |
| VM5-1-N1-B9 | channel | null | 空值 | 422 | channel 必填 |
| VM5-1-N1-B10 | external_order_no | "" | 空值 | 422 | 外部订单号不能为空 |
| VM5-1-N1-B11 | external_order_no | null | 空值 | 422 | 外部订单号必填 |
| VM5-1-N1-B12 | 同 channel 不同 external_order_no | channel=doudian, 不同单号 | 非幂等 | 201, 不同 order_id | 同渠道不同单号 |
| VM5-1-N1-B13 | 不同 channel 同 external_order_no | channel 不同, 单号相同 | 非幂等 | 201, 不同 order_id | UK(channel, external_order_no) |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-1-N1-S1 | 正常公域订单创建 | 商品 on_sale, Webhook 签名有效 | POST webhook | 201, status=paid, channel=doudian |
| VM5-1-N1-S2 | 同渠道同单号幂等 | 已创建 DD202608120001 | POST webhook 同单号 | 201, 同一 order_id, 不重复创建 |
| VM5-1-N1-S3 | 不同渠道同单号不幂等 | doudian 已创建, dy_knowledge 同单号 | POST webhook | 201, 不同 order_id |
| VM5-1-N1-S4 | 无效 Webhook 签名 | 签名错误 | POST webhook | 401/403, 签名验证失败 |
| VM5-1-N1-S5 | 公域订单自动 paid | Webhook 回调 | POST webhook | 201, status=paid（公域直接支付完成） |

---

### VM5-1-N2: 订单金额边界

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}, price_cents=9900
- 买家A 已注册

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "product_id": "{product_id}",
  "client_token": "amount-boundary-test-001"
}
```

**期望结果**:
- 正常金额：201, amount_cents=9900
- 异常金额：422

**边界值测试**:

| 变体ID | 商品价格 | 期望 amount_cents | 期望Status | 说明 |
|--------|---------|------------------|-----------|------|
| VM5-1-N2-B1 | price_cents=1 | 1 | 201 | 最小正整数金额 |
| VM5-1-N2-B2 | price_cents=0 | 0 | 422/201 | 0 元商品下单（需确认 PRD） |
| VM5-1-N2-B3 | price_cents=999999999 | 999999999 | 201 | 大金额 |
| VM5-1-N2-B4 | price_cents=-1 | — | 422 | 负数价格（商品创建时已拦截） |
| VM5-1-N2-B5 | 金额篡改 | 请求体含 amount_cents=1（篡改） | 422/201 | 验证是否以商品价格为准 |
| VM5-1-N2-B6 | 优惠后金额 | 有优惠券, 实付=4900 | 201, amount=4900 | 优惠后金额 |
| VM5-1-N2-B7 | 多 item 订单 | 2 个商品, 总额=19800 | 201, amount=19800 | 多 item 金额汇总 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-1-N2-S1 | 正常金额订单 | price=9900 | POST order | 201, amount_cents=9900 |
| VM5-1-N2-S2 | 0 元商品下单 | price=0（若允许） | POST order | 422/201, 验证免费商品 |
| VM5-1-N2-S3 | 金额篡改防护 | price=9900, 请求含 amount=1 | POST order | 201/422, 以商品价格为准 |
| VM5-1-N2-S4 | 大金额订单 | price=999999999 | POST order | 201, amount=999999999 |

---

### VM5-1-N3: 跨租户订单隔离

**前置条件**:
- 商家A（TENANT_A）有商品 {product_id_A} 属于 store_id_A
- 商家B（TENANT_B）有商品 {product_id_B} 属于 store_id_B
- 买家A 属于 TENANT_A，买家B 属于 TENANT_B

**API**: `GET {base_url}/mp/shop/orders/{order_id}`
**Headers**: `Authorization: Bearer {buyer_token}` 或 `Authorization: Bearer {buyer_token_b}`

**请求体**: 无

**期望结果**:
- 买家A 查询自己订单：200
- 买家B 查询买家A 订单：404/403
- 买家A 查询不存在订单：404

**边界值测试**:

| 变体ID | 查询方 | 订单归属 | 期望Status | 说明 |
|--------|-------|---------|-----------|------|
| VM5-1-N3-B1 | 买家A | TENANT_A 的订单 | 200 | 同租户正常查询 |
| VM5-1-N3-B2 | 买家B | TENANT_A 的订单 | 404/403 | 跨租户隔离 |
| VM5-1-N3-B3 | 买家A | 不存在的 order_id | 404 | 订单不存在 |
| VM5-1-N3-B4 | 无 token | 任意订单 | 401 | 未认证 |
| VM5-1-N3-B5 | 买家A | TENANT_B 买家B 的订单 | 404/403 | 跨买家+跨租户 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-1-N3-S1 | 买家查询自己订单 | 买家A 的订单 | GET with buyer_token | 200 |
| VM5-1-N3-S2 | 跨租户买家查询 | 买家B 查买家A 订单 | GET with buyer_token_b | 404/403 |
| VM5-1-N3-S3 | 跨租户买家退款 | 买家B 对买家A 订单发起退款 | POST refund with buyer_token_b | 404/403 |
| VM5-1-N3-S4 | 跨租户权益查询 | 买家B 查买家A 权益 | GET entitlement with buyer_token_b | 404/403 |

---

### VM5-2-N1: client_token 跨买家

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}
- 买家A（buyer_token）和买家B（buyer_token_b）均已注册
- client_token = "shared-token-001"

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}` 或 `Authorization: Bearer {buyer_token_b}`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "product_id": "{product_id}",
  "client_token": "shared-token-001"
}
```

**期望结果**:
- 买家A 用 token "shared-token-001" 下单：201, order_id=X
- 买家B 用同一 token "shared-token-001" 下单：201, order_id=Y（不同买家不共享幂等）

**边界值测试**:

| 变体ID | 买家 | client_token | 期望Status | 说明 |
|--------|------|-------------|-----------|------|
| VM5-2-N1-B1 | 买家A | "shared-token-001" | 201, order_id=X | 买家A 首次下单 |
| VM5-2-N1-B2 | 买家B | "shared-token-001"（同 token） | 201, order_id=Y | 不同买家不共享幂等 |
| VM5-2-N1-B3 | 买家A | "shared-token-001"（重复） | 201, order_id=X | 同买家同 token 幂等 |
| VM5-2-N1-B4 | 买家A | "different-token" | 201, order_id=Z | 不同 token 创建新订单 |
| VM5-2-N1-B5 | 买家B | "shared-token-001"（重复） | 201, order_id=Y | 买家B 同 token 幂等 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-2-N1-S1 | 同买家同 token 幂等 | 买家A 已用 token 下单 | 买家A 再次用同 token | 201, 同一 order_id |
| VM5-2-N1-S2 | 不同买家同 token 不幂等 | 买家A 已用 token 下单 | 买家B 用同 token | 201, 不同 order_id |
| VM5-2-N1-S3 | 并发同买家同 token | 买家A 同时发 2 个请求 | 并发 POST | 201, 仅 1 个订单（幂等控制） |

---

### VM5-3-N1: 订单超时关单

**前置条件**:
- 买家A 已创建订单 {order_id}，status=pending_payment
- 订单超时时间设为 30 分钟（可配置）
- 订单创建时间已超过 30 分钟

**API**: 定时任务触发 `POST {base_url}/internal/orders/timeout-close`（内部 API）
**Headers**: `X-Internal-Key: {internal_key}`

**请求体**:
```json
{
  "order_id": "{order_id}"
}
```

**期望结果**:
- HTTP Status: 200
- 订单 status: pending_payment → closed
- 数据库: `shop_orders` 记录 status=closed, closed_at 已设置

**边界值测试**:

| 变体ID | 订单状态 | 超时时间 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM5-3-N1-B1 | pending_payment, 创建 31 分钟前 | 30 分钟 | 200, closed | 超时关单 |
| VM5-3-N1-B2 | pending_payment, 创建 29 分钟前 | 30 分钟 | 200, 不关单 | 未超时不关 |
| VM5-3-N1-B3 | pending_payment, 创建 30 分钟前 | 30 分钟 | 200, closed | 恰好超时 |
| VM5-3-N1-B4 | paid | 已支付 | 409/422 | 已支付不可关单 |
| VM5-3-N1-B5 | closed | 已关单 | 409/422 | 重复关单 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-3-N1-S1 | 超时自动关单 | pending_payment, 超 30 分钟 | 定时任务执行 | 200, status=closed |
| VM5-3-N1-S2 | 未超时不关单 | pending_payment, 未超 30 分钟 | 定时任务执行 | 200, status=pending_payment |
| VM5-3-N1-S3 | 超时关单后不可支付 | closed | 支付回调 | 409/422, 已关单不可支付 |
| VM5-3-N1-S4 | 买家超时前主动取消 | pending_payment, 未超时 | 买家取消 | 200, status=closed |

---

### VM5-3-N2: 公域 Webhook 直写退款

**前置条件**:
- 买家A 通过公域（doudian）购买商品，订单 status=paid
- 公域平台发起退款 Webhook 回调

**API**: `POST {base_url}/webhooks/refunds`（公域退款 Webhook）
**Headers**: `X-Webhook-Signature: {signature}`, `Content-Type: application/json`

**请求体**:
```json
{
  "channel": "doudian",
  "external_order_no": "DD202608120001",
  "refund_amount_cents": 9900,
  "refund_status": "refunded"
}
```

**期望结果**:
- HTTP Status: 200
- 订单 status: paid → refunded（公域 Webhook 直写）
- 权益 status: active → revoked

**边界值测试**:

| 变体ID | 订单状态 | 退款金额 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM5-3-N2-B1 | paid | 全额 9900 | 200, refunded | 公域全额退款 |
| VM5-3-N2-B2 | pending_payment | 9900 | 422/409 | 未支付不可退款 |
| VM5-3-N2-B3 | refunded | 9900 | 422/409 | 重复退款 |
| VM5-3-N2-B4 | paid | 部分 5000 | 422/200 | Phase 1 部分退款拒绝/允许 |
| VM5-3-N2-B5 | paid | 超额 10000 | 422 | 退款金额超支付金额 |
| VM5-3-N2-B6 | 无效签名 | 9900 | 401/403 | 签名验证失败 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-3-N2-S1 | 公域全额退款直写 | paid, doudian | POST webhook refund | 200, status=refunded, entitlement=revoked |
| VM5-3-N2-S2 | 公域退款幂等 | 已退款 | POST webhook 同退款 | 200, 不重复处理 |
| VM5-3-N2-S3 | 公域退款权益撤销 | paid, entitlement=active | POST webhook refund | 200, entitlement=revoked |

---

### VM5-3-N3: 领权流程（claim_pending）

**前置条件**:
- 抖店订单已创建，status=claim_pending（买家尚未领权）
- 买家A 通过 M14 领权入口提交领权请求

**API**: `POST {base_url}/mp/shop/orders/{order_id}/claim`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "buyer_mobile": "13800000001"
}
```

**期望结果**:
- 领权成功：status: claim_pending → paid, 自动创建权益
- 抖店退款未领权：status: claim_pending → refunded

**边界值测试**:

| 变体ID | 订单状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM5-3-N3-B1 | claim_pending | POST claim | 200, paid | 领权成功, 创建权益 |
| VM5-3-N3-B2 | claim_pending | 抖店退款 Webhook | 200, refunded | 退款未领权, 不创建权益 |
| VM5-3-N3-B3 | paid | POST claim | 409/422 | 已领权不可重复 |
| VM5-3-N3-B4 | refunded | POST claim | 409/422 | 已退款不可领权 |
| VM5-3-N3-B5 | claim_pending | POST claim, buyer_mobile 不匹配 | 422 | 手机号不匹配 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-3-N3-S1 | 抖店领权成功 | claim_pending | POST claim | 200, status=paid, 创建 entitlement |
| VM5-3-N3-S2 | 抖店退款未领权 | claim_pending | 退款 Webhook | 200, status=refunded, 不创建 entitlement |
| VM5-3-N3-S3 | 领权后退款 | claim_pending → paid → refunded | claim + refund | 领权后退款, entitlement=revoked |
| VM5-3-N3-S4 | 领权幂等 | 已领权 paid | POST claim 再次 | 409/422, 不可重复领权 |

---

### VM5-3-N4: 退款回调失败重试

**前置条件**:
- 买家A 已支付订单 {order_id}，status=paid
- 发起退款后 status=refunding
- 退款回调（Webhook）首次失败

**API**: `POST {base_url}/webhooks/refunds`（退款回调重试）
**Headers**: `X-Webhook-Signature: {signature}`, `Content-Type: application/json`

**请求体**:
```json
{
  "channel": "wechat",
  "order_id": "{order_id}",
  "refund_status": "failed"
}
```

**期望结果**:
- 退款回调失败：status: refunding → paid（可重试）
- 退款回调重试成功：status: paid → refunding → refunded

**边界值测试**:

| 变体ID | 退款状态 | 期望订单状态 | 说明 |
|--------|---------|------------|------|
| VM5-3-N4-B1 | refunding + 回调失败 | paid（回退, 可重试） | 回调失败回退到 paid |
| VM5-3-N4-B2 | paid + 重新发起退款 | refunding | 可重新发起退款 |
| VM5-3-N4-B3 | refunding + 回调成功 | refunded | 退款完成 |
| VM5-3-N4-B4 | refunded + 回调失败 | refunded（终态不变） | 终态不回退 |
| VM5-3-N4-B5 | paid + 多次回调失败 | paid | 多次失败仍保持 paid |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-3-N4-S1 | 退款回调失败回退 | refunding | 回调失败 | status=paid, 可重试 |
| VM5-3-N4-S2 | 回退后重新退款 | paid（回退后） | 重新发起退款 | status=refunding |
| VM5-3-N4-S3 | 重试后退款成功 | refunding | 回调成功 | status=refunded, entitlement=revoked |
| VM5-3-N4-S4 | 多次失败后成功 | paid → refunding → fail → paid → refunding → success | 多次重试 | 最终 status=refunded |

---

### VM5-4-N1: 权益幂等（order_item_id）

**前置条件**:
- 买家A 已支付订单 {order_id}，含 1 个 order_item
- 权益已自动创建，order_item_id 唯一
- 模拟重复支付回调

**API**: `POST {base_url}/webhooks/payment`（重复支付回调）
**Headers**: `X-Webhook-Signature: {signature}`, `Content-Type: application/json`

**请求体**:
```json
{
  "order_id": "{order_id}",
  "payment_status": "paid",
  "amount_cents": 9900
}
```

**期望结果**:
- 重复回调：200, 不重复创建权益
- 数据库: `shop_entitlements` 仍只有 1 条记录（UK(order_item_id)）

**边界值测试**:

| 变体ID | 场景 | 期望Status | 说明 |
|--------|------|-----------|------|
| VM5-4-N1-B1 | 首次支付回调 | 200, 创建 1 条权益 | 正常创建 |
| VM5-4-N1-B2 | 重复支付回调 | 200, 不创建新权益 | UK(order_item_id) 幂等 |
| VM5-4-N1-B3 | 并发支付回调 | 200, 仅 1 条权益 | 并发幂等控制 |
| VM5-4-N1-B4 | order_item_id=null | 422 | order_item_id 不能为空 |
| VM5-4-N1-B5 | 3 次重复回调 | 200, 仅 1 条权益 | 多次重复仍幂等 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-4-N1-S1 | 首次支付创建权益 | 订单 pending_payment | 支付回调 | 200, 1 条 entitlement |
| VM5-4-N1-S2 | 重复回调不重复创建 | 已有 1 条权益 | 重复支付回调 | 200, 仍 1 条 entitlement |
| VM5-4-N1-S3 | 并发回调幂等 | 同时 2 个回调 | 并发 POST | 200, 仅 1 条 entitlement |

---

### VM5-5-N1: 权益过期

**前置条件**:
- 买家A 有权益 {entitlement_id}，status=active
- expires_at 设为当前时间 - 1 分钟（已过期）

**API**: `GET {base_url}/mp/shop/entitlements/{entitlement_id}`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**: 无

**期望结果**:
- HTTP Status: 200
- 权益 status: active → expired（定时任务或查询时触发）
- 数据库: `shop_entitlements` status=expired

**边界值测试**:

| 变体ID | expires_at | 查询时机 | 期望Status | 说明 |
|--------|-----------|---------|-----------|------|
| VM5-5-N1-B1 | 当前时间 + 1 天 | 立即查询 | 200, active | 未过期 |
| VM5-5-N1-B2 | 当前时间 - 1 分钟 | 立即查询 | 200, expired | 已过期 |
| VM5-5-N1-B3 | 当前时间（恰好） | 立即查询 | 200, expired/active | 边界值 |
| VM5-5-N1-B4 | null（无过期时间） | 查询 | 200, active | 永不过期 |
| VM5-5-N1-B5 | 过期后尝试学习 | expired | POST 学习 | 403/422, 权益已过期 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-5-N1-S1 | 权益正常未过期 | expires_at 未来 | GET entitlement | 200, active |
| VM5-5-N1-S2 | 权益已过期 | expires_at 过去 | GET entitlement | 200, expired |
| VM5-5-N1-S3 | 过期后不可学习 | expired | POST 学习课程 | 403/422, 权益已过期 |
| VM5-5-N1-S4 | 过期后不可下载 | expired | POST 下载资料 | 403/422, 权益已过期 |

---

### VM5-5-N2: 次数卡用尽

**前置条件**:
- 买家A 有次数卡权益 {entitlement_id}，status=active
- times_total=5, times_used=4

**API**: `POST {base_url}/mp/shop/entitlements/{entitlement_id}/consume`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "times": 1
}
```

**期望结果**:
- 核销 1 次：200, times_used=5, status=consumed
- 数据库: `shop_entitlements` times_used=5, status=consumed

**边界值测试**:

| 变体ID | times_used | 核销次数 | 期望Status | 说明 |
|--------|-----------|---------|-----------|------|
| VM5-5-N2-B1 | 4/5 | 1 | 200, consumed | 最后 1 次, 用尽 |
| VM5-5-N2-B2 | 3/5 | 1 | 200, active | 还有剩余 |
| VM5-5-N2-B3 | 5/5（已用尽） | 1 | 422/409 | 已用尽不可核销 |
| VM5-5-N2-B4 | 4/5 | 2 | 422 | 超出剩余次数 |
| VM5-5-N2-B5 | 4/5 | 0 | 422 | 核销次数不能为 0 |
| VM5-5-N2-B6 | 4/5 | -1 | 422 | 核销次数不能为负 |
| VM5-5-N2-B7 | expired | 1 | 422 | 过期不可核销 |
| VM5-5-N2-B8 | revoked | 1 | 422 | 撤销不可核销 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-5-N2-S1 | 正常核销 1 次 | times_used=3/5 | POST consume times=1 | 200, times_used=4, active |
| VM5-5-N2-S2 | 核销最后 1 次用尽 | times_used=4/5 | POST consume times=1 | 200, times_used=5, consumed |
| VM5-5-N2-S3 | 已用尽不可核销 | times_used=5/5, consumed | POST consume | 422/409, 已用尽 |
| VM5-5-N2-S4 | 超出剩余次数 | times_used=4/5 | POST consume times=2 | 422, 超出剩余 |

---

### VM5-6-N1: always_allow 退款理由校验

**前置条件**:
- 买家A 已购买商品 {product_id}，refund_policy=always_allow
- 订单 status=paid, 权益 status=active, 零履约

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {buyer_token}` 或 `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "不需要了"
}
```

**期望结果**:
- 合法 reason_code：200
- 非法 reason_code：422
- 商家发起 remark < 4 字：422

**边界值测试**:

| 变体ID | 发起方 | reason_code | remark | 期望Status | 说明 |
|--------|-------|-------------|--------|-----------|------|
| VM5-6-N1-B1 | 买家 | "buyer_request" | "不需要了" | 200 | 合法理由 |
| VM5-6-N1-B2 | 买家 | "quality_issue" | "质量差" | 200 | 合法理由 |
| VM5-6-N1-B3 | 买家 | "duplicate" | "重复购买" | 200 | 合法理由 |
| VM5-6-N1-B4 | 买家 | "other" | "其他原因" | 200 | 合法理由 |
| VM5-6-N1-B5 | 买家 | "invalid" | "备注" | 422 | 非法 reason_code |
| VM5-6-N1-B6 | 买家 | null | "备注" | 422 | reason_code 必填 |
| VM5-6-N1-B7 | 商家 | "buyer_request" | "商"（1 字） | 422 | 商家 remark >=4 字 |
| VM5-6-N1-B8 | 商家 | "buyer_request" | "商家同意退"（5 字） | 200 | 合法 remark |
| VM5-6-N1-B9 | 商家 | "buyer_request" | "" | 422 | remark 不能为空 |
| VM5-6-N1-B10 | 商家 | "buyer_request" | null | 422 | remark 必填 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-6-N1-S1 | 买家合法理由退款 | paid, 零履约 | POST refund, reason=buyer_request | 200, refunded |
| VM5-6-N1-S2 | 买家非法理由被拒 | paid | POST refund, reason=invalid | 422, 非法 reason_code |
| VM5-6-N1-S3 | 商家 remark 不足被拒 | paid | POST refund, remark="abc" | 422, remark >=4 字 |
| VM5-6-N1-S4 | 商家合法退款 | paid | POST refund, remark="商家同意退款" | 200, refunded |
| VM5-6-N1-S5 | 买家不传 remark | paid | POST refund, 仅 reason_code | 200, 买家 remark 可选 |

---

### VM5-7-N1: before_fulfill 零履约判定

**前置条件**:
- 买家A 已购买 3 种商品，refund_policy 均为 before_fulfill
- 课程商品：无任一课时 progress > 0
- 资料包商品：未下载
- 服务商品（次数卡）：times_used=0, 无核销记录

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "零履约退款"
}
```

**期望结果**:
- 三种商品类型零履约均可买家自助退款：200
- 权益 status: active → revoked

**边界值测试**:

| 变体ID | 商品类型 | 履约状态 | 发起方 | 期望Status | 说明 |
|--------|---------|---------|-------|-----------|------|
| VM5-7-N1-B1 | course | 无课时 progress>0 | 买家 | 200 | 课程零履约 |
| VM5-7-N1-B2 | course | 课时1 progress=50% | 买家 | 422 | 有学习记录 |
| VM5-7-N1-B3 | digital | 未下载 | 买家 | 200 | 资料零履约 |
| VM5-7-N1-B4 | digital | 已下载 1 次 | 买家 | 422 | 有下载记录 |
| VM5-7-N1-B5 | service(times_card) | times_used=0, 无核销 | 买家 | 200 | 服务零履约 |
| VM5-7-N1-B6 | service(times_card) | times_used=1 | 买家 | 422 | 有使用记录 |
| VM5-7-N1-B7 | service(booking) | 无核销 | 买家 | 200 | 预约零履约 |
| VM5-7-N1-B8 | service(booking) | 已核销 1 次 | 买家 | 422 | 已核销 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-7-N1-S1 | 课程零履约可退 | 无 progress | POST refund (buyer) | 200, refunded |
| VM5-7-N1-S2 | 资料零履约可退 | 未下载 | POST refund (buyer) | 200, refunded |
| VM5-7-N1-S3 | 服务零履约可退 | times_used=0 | POST refund (buyer) | 200, refunded |
| VM5-7-N1-S4 | 课程有 progress 不可退 | 课时1 progress=10% | POST refund (buyer) | 422, 有学习记录 |
| VM5-7-N1-S5 | 所有类型零履约均可退 | 三种商品均零履约 | 分别 POST refund | 全部 200 |

---

### VM5-7-N2: before_fulfill 非零履约禁退

**前置条件**:
- 买家A 已购买商品，refund_policy=before_fulfill
- 课程商品：课时1 progress=10%
- 资料包商品：已下载 1 次
- 服务商品：已核销 1 次

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {buyer_token}` 或 `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "非零履约退款"
}
```

**期望结果**:
- 买家自助退款非零履约：422（买家端禁用）
- 商家发起退款非零履约：200（商家不受限制）

**边界值测试**:

| 变体ID | 商品类型 | 履约状态 | 发起方 | 期望Status | 说明 |
|--------|---------|---------|-------|-----------|------|
| VM5-7-N2-B1 | course | progress=1% | 买家 | 422 | 任一 progress>0 禁用 |
| VM5-7-N2-B2 | course | progress=100% | 买家 | 422 | 完成学习禁用 |
| VM5-7-N2-B3 | digital | 已下载 1 次 | 买家 | 422 | 有下载记录禁用 |
| VM5-7-N2-B4 | service | 已核销 1 次 | 买家 | 422 | 有核销记录禁用 |
| VM5-7-N2-B5 | service | used_count>0 | 买家 | 422 | 有使用记录禁用 |
| VM5-7-N2-B6 | course | progress=1% | 商家 | 200 | 商家不受履约限制 |
| VM5-7-N2-B7 | digital | 已下载 | 商家 | 200 | 商家不受履约限制 |
| VM5-7-N2-B8 | service | 已核销 | 商家 | 200 | 商家不受履约限制 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-7-N2-S1 | 买家课程有 progress 禁退 | progress=10% | POST refund (buyer) | 422, 买家端禁用 |
| VM5-7-N2-S2 | 买家资料已下载禁退 | 已下载 | POST refund (buyer) | 422, 买家端禁用 |
| VM5-7-N2-S3 | 买家服务已核销禁退 | 已核销 | POST refund (buyer) | 422, 买家端禁用 |
| VM5-7-N2-S4 | 商家对有履约订单退款 | progress=10% | POST refund (merchant) | 200, 商家可退 |
| VM5-7-N2-S5 | 商家对已下载订单退款 | 已下载 | POST refund (merchant) | 200, 商家可退 |

---

### VM5-9-N1: 单 item 订单全额退款

**前置条件**:
- 买家A 已购买商品 {product_id}，单 item 订单
- 订单 status=paid, amount_cents=9900, 1 个 order_item
- 权益 status=active

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "全额退款关权",
  "amount_cents": 9900
}
```

**期望结果**:
- 全额退款：200, status=refunded, entitlement=revoked
- 部分退款：422, Phase 1 仅支持全额退款

**边界值测试**:

| 变体ID | 退款金额 | 边界类型 | 期望Status | 说明 |
|--------|---------|---------|-----------|------|
| VM5-9-N1-B1 | 9900（= paid） | 全额 | 200 | 全额退款关权 |
| VM5-9-N1-B2 | 5000（< paid） | 部分 | 422 | Phase 1 不支持部分退款 |
| VM5-9-N1-B3 | 9901（> paid） | 超额 | 422 | 超出支付金额 |
| VM5-9-N1-B4 | 0 | 零值 | 422 | 退款金额不能为 0 |
| VM5-9-N1-B5 | 不传 amount_cents | 默认全额 | 200 | 默认全额退款 |
| VM5-9-N1-B6 | -1 | 负数 | 422 | 退款金额不能为负 |
| VM5-9-N1-B7 | "abc" | 非数字 | 422 | 类型错误 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-9-N1-S1 | 单 item 全额退款 | paid=9900 | POST refund, amount=9900 | 200, refunded, entitlement=revoked |
| VM5-9-N1-S2 | 单 item 部分退款被拒 | paid=9900 | POST refund, amount=5000 | 422, Phase 1 仅全额退款 |
| VM5-9-N1-S3 | 不传金额默认全额 | paid=9900 | POST refund, 不含 amount | 200, 全额退款 |
| VM5-9-N1-S4 | 全额退款后权益撤销 | active | POST refund → GET entitlement | 200, entitlement=revoked |

---

### VM5-10-N1: 已开票 needs_red_flush

**前置条件**:
- 买家A 已购买商品，订单 status=paid
- invoice_requests 记录 status=issued（已开票）
- refund_policy=always_allow

**API**: `POST {base_url}/mp/shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "reason_code": "buyer_request",
  "remark": "已开票退款需红冲"
}
```

**期望结果**:
- HTTP Status: 200
- 退款成功, needs_red_flush=true
- 数据库: `shop_orders` status=refunded, `invoice_requests` needs_red_flush=true

**边界值测试**:

| 变体ID | 开票状态 | 期望Status | needs_red_flush | 说明 |
|--------|---------|-----------|-----------------|------|
| VM5-10-N1-B1 | issued | 200 | true | 已开票需红冲 |
| VM5-10-N1-B2 | pending | 200 | false | 未开票无需红冲 |
| VM5-10-N1-B3 | none（无发票请求） | 200 | false | 无发票 |
| VM5-10-N1-B4 | voided | 200 | false | 已作废 |
| VM5-10-N1-B5 | 1 issued + 1 pending | 200 | true | 有任一已开需红冲 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-10-N1-S1 | 已开票退款标记红冲 | invoice issued | POST refund | 200, needs_red_flush=true |
| VM5-10-N1-S2 | 未开票退款不标记 | invoice pending | POST refund | 200, needs_red_flush=false |
| VM5-10-N1-S3 | 已开票仍允许退款 | invoice issued, always_allow | POST refund | 200, 允许退+红冲标记 |
| VM5-10-N1-S4 | 已开票退款权益撤销 | invoice issued, active | POST refund → GET entitlement | 200, entitlement=revoked |

---

### VM5-11-N1: mobile+openid 归一

**前置条件**:
- 商家A 已入驻（TENANT_A）
- 买家A 手机号 13800000001, openid=wx_001, 在 TENANT_A 已有 buyer 记录
- 买家B 手机号 13800000002, openid=wx_002

**API**: `POST {base_url}/mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`, `Content-Type: application/json`

**请求体**:
```json
{
  "shop_id": "{store_id}",
  "product_id": "{product_id}",
  "client_token": "identity-normalization-001",
  "buyer_mobile": "13800000001"
}
```

**期望结果**:
- 同 mobile 归一到同一 buyer_id
- 不同 tenant 同 mobile 不归一
- 禁止 FK 到 CRM contacts

**边界值测试**:

| 变体ID | mobile | openid | tenant | 期望 buyer_id | 说明 |
|--------|--------|--------|--------|-------------|------|
| VM5-11-N1-B1 | 13800000001 | wx_001 | TENANT_A | 同一 buyer_id | 完全匹配归一 |
| VM5-11-N1-B2 | 13800000001 | wx_002（不同 openid） | TENANT_A | 同一 buyer_id | mobile 归一 |
| VM5-11-N1-B3 | 13800000002（不同 mobile） | wx_001 | TENANT_A | 不同 buyer_id | 不同 mobile 不同 buyer |
| VM5-11-N1-B4 | null | wx_001 | TENANT_A | 同一 buyer_id | 无 mobile 按 openid 归一 |
| VM5-11-N1-B5 | 13800000001 | wx_001 | TENANT_B | 不同 buyer_id | 跨租户不归一 |
| VM5-11-N1-B6 | 13800000001 | null | TENANT_A | 同一 buyer_id | 无 openid 按 mobile 归一 |
| VM5-11-N1-B7 | "123"（格式错误） | wx_001 | TENANT_A | 422 | 手机号格式错误 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-11-N1-S1 | 同 mobile 归一 | TENANT_A 已有 buyer(13800000001) | 下单, 同 mobile | 201, 同一 buyer_id, 无新 buyer |
| VM5-11-N1-S2 | 同 mobile 不同 openid 归一 | TENANT_A 已有 buyer(13800000001, wx_001) | 下单, 同 mobile, 不同 openid | 201, 同一 buyer_id |
| VM5-11-N1-S3 | 禁止 FK 到 CRM contacts | buyer 表结构 | 检查 DB schema | buyer 表无 FK 关联 CRM contacts |
| VM5-11-N1-S4 | 禁止同 tenant 双 buyer | 同 tenant 同 (mobile, openid) | 下单 | 201, 仅 1 条 buyer |
| VM5-11-N1-S5 | 跨 tenant 不归一 | TENANT_B 同 mobile | 下单 | 201, TENANT_B 新 buyer_id |

---

### VM5-13-N1: 商家 suspended 已购不阻断

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}
- 买家A 已购买商品，订单 paid，权益 active
- 商家A 即将被 suspended

**API**:
1. `POST {base_url}/internal/merchants/{tenant_id}/suspend`（内部 API，暂停商家）
2. `GET {base_url}/mp/shop/entitlements/{entitlement_id}`（买家查询权益）
3. `POST {base_url}/mp/shop/orders`（新买家尝试购买）

**Headers**: 内部 API 用 `X-Internal-Key`, 买家操作用 `buyer_token`

**请求体**（暂停商家）:
```json
{
  "status": "suspended"
}
```

**期望结果**:
- 商家暂停：200
- 已购权益查询：200, status=active（不阻断）
- 新买家购买：422（新购拦截）

**边界值测试**:

| 变体ID | 商家状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM5-13-N1-B1 | suspended | 新买家购买 | 422 | 新购拦截 |
| VM5-13-N1-B2 | suspended | 已购买家查权益 | 200, active | 履约不阻断 |
| VM5-13-N1-B3 | suspended | 已购买家学习课程 | 200 | 履约不阻断 |
| VM5-13-N1-B4 | suspended | 已购买家下载资料 | 200 | 履约不阻断 |
| VM5-13-N1-B5 | closed | 新买家购买 | 422 | 商家关闭拦截 |
| VM5-13-N1-B6 | closed | 已购买家查权益 | 200, active | 履约不阻断 |
| VM5-13-N1-B7 | active（恢复正常） | 新买家购买 | 201 | 恢复后可购买 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-13-N1-S1 | 商家暂停新购拦截 | suspended | 新买家 POST order | 422, 商家已暂停 |
| VM5-13-N1-S2 | 商家暂停已购不阻断 | suspended, 买家已购 | 买家学习课程 | 200, 履约正常 |
| VM5-13-N1-S3 | 商家关闭已购不阻断 | closed, 买家已购 | 买家查权益 | 200, active |
| VM5-13-N1-S4 | 商家恢复后可购买 | active（恢复） | 新买家 POST order | 201, 恢复正常 |

---

### VM5-13-N2: 平台强制下架拒单

**前置条件**:
- 商家A 有 on_sale 商品 {product_id}
- 买家A 已购买商品，权益 active
- 平台 P07/P09 即将强制下架该商品

**API**:
1. `POST {base_url}/internal/products/{product_id}/force-off-sale`（内部 API，强制下架）
2. `POST {base_url}/webhooks/orders`（公域新订单 Webhook）

**Headers**: 内部 API 用 `X-Internal-Key`, Webhook 用 `X-Webhook-Signature`

**请求体**（强制下架）:
```json
{
  "reason": "P07_policy_violation"
}
```

**期望结果**:
- 强制下架：200, 商品 status=off_sale（平台强制标记）
- 已购权益：200, active（保留）
- 新 Webhook 订单：422/拒单

**边界值测试**:

| 变体ID | 商品状态 | 操作 | 期望Status | 说明 |
|--------|---------|------|-----------|------|
| VM5-13-N2-B1 | P07 强制下架 | 已购买家查权益 | 200, active | 已购保留 |
| VM5-13-N2-B2 | P07 强制下架 | 新私域订单 | 422 | 新购拦截 |
| VM5-13-N2-B3 | P07 强制下架 | 新公域 Webhook | 422/拒单 | 新 Webhook 拒单 |
| VM5-13-N2-B4 | P07 强制下架 | 已购买家学习 | 200 | 履约不阻断 |
| VM5-13-N2-B5 | P09 人审强制下架 | 新公域 Webhook | 422/拒单 | 人审下架拒单 |
| VM5-13-N2-B6 | P09 人审强制下架 | 已购买家查权益 | 200, active | 已购保留 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM5-13-N2-S1 | P07 强制下架已购保留 | 有买家已购 | 强制下架 → 查权益 | 200, entitlement=active |
| VM5-13-N2-S2 | P07 强制下架新单拒收 | 强制下架 | 新 Webhook 订单 | 422/拒单 |
| VM5-13-N2-S3 | P09 人审强制下架 | 有买家已购 | 强制下架 → 查权益 | 200, entitlement=active |
| VM5-13-N2-S4 | P09 强制下架新私域拦截 | 强制下架 | 新私域 POST order | 422, 商品已下架 |
| VM5-13-N2-S5 | 强制下架后已购履约正常 | 有买家已购 | 买家学习课程 | 200, 履约不阻断 |

---

## 测试用例统计

### M4 商品内容

| 类别 | 用例数 | 边界值变体 | 业务场景 | 小计 |
|------|--------|-----------|---------|------|
| VM4-1 ~ VM4-12（现有） | 12 | 87 | 48 | 147 |
| VM4-1-N1 ~ VM4-3-N1（新增） | 15 | 108 | 56 | 179 |
| **M4 合计** | **27** | **195** | **104** | **326** |

### M5 订单权益

| 类别 | 用例数 | 边界值变体 | 业务场景 | 小计 |
|------|--------|-----------|---------|------|
| VM5-1 ~ VM5-14（现有） | 14 | 96 | 61 | 171 |
| VM5-1-N1 ~ VM5-13-N2（新增） | 19 | 113 | 73 | 205 |
| **M5 合计** | **33** | **209** | **134** | **376** |

### 总计

| 模块 | 主用例 | 边界值变体 | 业务场景 | 总测试点 |
|------|--------|-----------|---------|---------|
| M4 商品内容 | 27 | 195 | 104 | 326 |
| M5 订单权益 | 33 | 209 | 134 | 376 |
| **总计** | **60** | **404** | **238** | **702** |

---

## 覆盖度检查清单

### M4 商品内容覆盖

- [x] 商品创建（course/digital/service 三种类型）
- [x] 价格边界测试（0、负数、最大值、line_price < price、line_price = price）
- [x] 商品字段必填校验（type/name/price/ref_type/ref_id/store_id）
- [x] 商品状态机全转换（draft→pending_review→approved→on_sale→off_sale, rejected）
- [x] 非法状态转换（所有非法路径）
- [x] 商品编辑权限（draft 可编辑, on_sale 不可编辑 409）
- [x] 商品提审（stub 模式固定 flag, 前置校验, 日额度限制）
- [x] 商品上架（仅 approved, 套餐上限）
- [x] 商品下架（on_sale → off_sale, 保留 approved）
- [x] 下架后再上架（off_sale → publish 流程）
- [x] 多店隔离（A 店商品 B 店访问 404/403）
- [x] 跨租户隔离（B 商家操作 A 商家商品 404/403）
- [x] 权限校验（买家不可访问商家 API, 无 token 401）
- [x] 专栏创建与发布（扁平结构, draft→published→off_sale）
- [x] 专栏下架不可再发布（Phase 1 限制）
- [x] 课时创建（视频 mp4/mov, 图文 content_body/images）
- [x] 视频校验（格式/大小<=2GB/时长<=180min/转码 ready）
- [x] 图文校验（正文>=10字/<=50000字, 图片<=20张/<=5MB, jpg/png/gif）
- [x] 课时下架可再发布（与专栏不同）
- [x] 试看设置（最多3节/专栏, 仅已发布视频, 时长 60/180/300/600/null）
- [x] 资料包创建（download/online_view, 文件白名单 .pdf/.doc/.docx/.zip）
- [x] online_view 硬校验（发布需>=1 可预览文件）
- [x] online_view 软校验（保存允许+黄条警告）
- [x] 服务商品（booking/times_card, total_times 校验）
- [x] 机审规则（stub 模式固定 flag）
- [x] 商品列表/详情查询

### M5 订单权益覆盖

- [x] 订单创建（私域 POST /mp/shop/orders, 公域 Webhook）
- [x] 订单幂等（client_token 同 buyer 返回同一 order_id）
- [x] client_token 跨买家（不同 buyer 不共享幂等）
- [x] external_order_no 幂等（UK(channel, external_order_no)）
- [x] 订单金额边界（0、负数、最大值、金额篡改防护）
- [x] 订单渠道（wx_mp/doudian/dy_knowledge/wechat）
- [x] 订单状态流转（pending_payment→paid/closed, paid→refunding→refunded）
- [x] 订单超时关单（定时任务）
- [x] 公域 Webhook 直写退款（paid→refunded）
- [x] 领权流程（claim_pending→paid/refunded）
- [x] 退款回调失败重试（refunding→paid 可重试）
- [x] 权益创建（自动创建, order_item_id 幂等）
- [x] 权益状态流转（pending→active→expired/consumed/revoked）
- [x] 权益过期（expires_at 到期）
- [x] 次数卡用尽（times_used=times_total → consumed）
- [x] 退款 always_allow（买家+商家, 零/非零履约均可）
- [x] 退款 before_fulfill（零履约可退, 非零买家禁退, 商家不限）
- [x] 退款 manual_only（买家端不展示, 仅商家发起, remark>=4字）
- [x] 退款理由校验（reason_code 枚举, 商家 remark>=4字）
- [x] 部分退款拒绝（Phase 1 仅全额退款）
- [x] 单 item 订单全额退款关权
- [x] 已开票退款（needs_red_flush=true）
- [x] 买家身份归一（UK(tenant_id, mobile), 禁止 FK CRM, 禁止双 buyer）
- [x] 多店场景（无跨店购物车, 每次绑定 shop_id, tenant 级汇总）
- [x] 商品下架与已购权益（off_sale/rejected 不影响已购）
- [x] 商家 suspended/closed（新购拦截, 已购不阻断）
- [x] 平台 P07/P09 强制下架（已购保留, 新 Webhook 拒单）
- [x] 内容版本策略（课程/资料跟最新, 快照仅展示）
- [x] 跨租户订单隔离

---

## 执行说明

1. **测试顺序**: 按照 VM4-1 → VM4-2 → ... → VM5-14 → VM5-1-N1 → ... 顺序执行，前置用例创建的数据供后续用例使用
2. **数据清理**: 每轮测试前建议重置测试数据库，确保前置条件准确
3. **变量替换**: 所有 `{variable}` 占位符需在执行前替换为实际值
4. **状态依赖**: 部分用例依赖前序用例的状态变更（如 VM4-5 提审依赖 VM4-1 创建的商品）
5. **数据库验证**: 所有"数据库"检查项需通过 SQL 查询验证，不仅依赖 API 响应
6. **并发测试**: VM5-2-S5 和 VM5-4-N1-B3 需使用并发工具模拟同时请求
7. **定时任务**: VM5-3-N1 超时关单和 VM5-5-N1 权益过期依赖定时任务，需手动触发或等待
8. **Webhook 测试**: VM5-1-N1、VM5-3-N2、VM5-3-N4 需模拟公域 Webhook 回调，注意签名验证
9. **内部 API**: VM5-3-N1、VM5-13-N1、VM5-13-N2 使用内部 API，需使用内部密钥认证

---

*文档结束*
---
# 内容获客商城 Phase 1 — Round 1 后端 API 测试用例

> **覆盖模块**: M3 支付硬验收 | M6 核销开票 | M7 公域Mx
> **测试环境**: WECHAT_PAY_MODE=stub, DOUYIN_WEBHOOK_MODE=stub
> **测试账号**: 商家用户 = 13900000099 / test123456, 平台管理员 = 13800000000 / admin123456
> **生成日期**: 2026-08-12
> **执行工具**: Cursor AI 自动化执行

---

## 一、M3 支付硬验收 (P1-07 硬验收)

> **模块说明**: 覆盖支付进件、支付配置、支付流程(下单→预支付→回调→兜底查单→退款)、支付日志、多店隔离、密钥轮换等全链路。
> **环境变量**: `WECHAT_PAY_MODE=stub` (微信支付Mock模式)
> **核心表**: shop_payment_configs, shop_orders, payment_logs, entitlements, enrollments

---

### VM3-1: 支付配置保存

**前置条件**:
- 商家已入驻且 status=active
- merchant_token 已获取 (13900000099/test123456)
- 环境变量: WECHAT_PAY_MODE=stub
- 当前店铺无已有支付配置或已有配置可更新

**API**: `POST /shop/payment-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "wx_api_key": "test_key_1234567890abcdef",
  "wx_mch_id": "1900000109",
  "wx_cert_pem": "-----BEGIN CERTIFICATE-----\nMIIEowIBAAKCAQEA...\n-----END CERTIFICATE-----",
  "wx_apiclient_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg...\n-----END PRIVATE KEY-----"
}
```

**期望结果**:
- HTTP Status: 200
- 响应体包含 config_id, wx_mch_id (明文)
- 数据库: shop_payment_configs 新增/更新记录
- 数据库: wx_api_key 为密文存储 (AES-256-GCM)
- 数据库: wx_cert_pem 为密文存储
- 响应不包含 wx_api_key 明文, wx_cert_pem 明文

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-1-B1 | wx_api_key | "" | 空值 | 422 | 密钥不能为空 |
| VM3-1-B2 | wx_api_key | "abc" | 长度不足 | 422 | 密钥长度<10字符 |
| VM3-1-B3 | wx_mch_id | "" | 空值 | 422 | 商户号不能为空 |
| VM3-1-B4 | wx_mch_id | "123" | 长度不足 | 422 | 商户号格式不合法(非8-20位数字) |
| VM3-1-B5 | wx_mch_id | "1900000109abc" | 含非数字 | 422 | 商户号必须为纯数字 |
| VM3-1-B6 | wx_cert_pem | "" | 空值 | 422 | 证书不能为空 |
| VM3-1-B7 | wx_cert_pem | "not_a_cert" | 格式错误 | 422 | 证书PEM格式不合法 |
| VM3-1-B8 | wx_api_key | null | null值 | 422 | 字段不能为null |
| VM3-1-B9 | wx_mch_id | "190000010919000010919" | 超长(>20) | 422 | 商户号长度超出限制 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-1-S1 | 正常保存 | 无配置 | POST 完整请求体 | 200, 新增配置 |
| VM3-1-S2 | 重复保存(更新) | 已有配置 | POST 修改wx_api_key | 200, 更新配置, 旧密钥被覆盖 |
| VM3-1-S3 | 无权限操作 | 非本店铺商家token | POST | 403, 无权操作他人店铺配置 |
| VM3-1-S4 | 未登录 | 无token | POST | 401, 未认证 |
| VM3-1-S5 | 商家suspended | merchant.status=suspended | POST | 403, 商家已暂停 |

---

### VM3-2: 支付配置读取与脱敏

**前置条件**:
- 商家已配置支付参数 (VM3-1已执行)
- merchant_token 已获取
- shop_payment_configs 存在记录

**API**: `GET /shop/payment-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 响应包含 wx_mch_id (明文)
- 响应包含 config_id, updated_at
- 响应不包含 wx_api_key 明文
- 响应不包含 wx_cert_pem 明文
- 响应不包含 wx_apiclient_key 明文
- 响应中敏感字段以 **** 脱敏或直接省略

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-2-B1 | 无配置时读取 | N/A | 空状态 | 404 | 店铺未配置支付参数 |
| VM3-2-B2 | token过期 | Authorization | 过期token | 401 | token已过期 |
| VM3-2-B3 | 无Authorization头 | Authorization | 缺失 | 401 | 未提供认证信息 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-2-S1 | 正常读取 | 已配置 | GET | 200, 返回脱敏配置 |
| VM3-2-S2 | 未配置读取 | 无配置 | GET | 404, 配置不存在 |
| VM3-2-S3 | 非本店铺读取 | 他店token | GET | 403, 无权读取 |

---

### VM3-3: 支付进件提交

**前置条件**:
- 商家已入驻 status=active
- onboarding_status=not_submitted
- merchant_token 已获取
- 营业执照、法人信息已完善

**API**: `POST /shop/payment-onboarding/submit`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "business_license_no": "91440101MA5XXXXXX",
  "legal_person_name": "张三",
  "legal_person_id_no": "440101199001011234",
  "settlement_account_no": "6225880123456789",
  "settlement_bank_name": "招商银行",
  "contact_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 响应包含 application_no (格式: OB+日期+4位流水)
- onboarding_status 变为 submitted
- 响应中 settlement_account_no 脱敏 (尾号4位: ****6789)
- 响应中 legal_person_id_no 脱敏
- 生成 audit_log 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-3-B1 | business_license_no | "" | 空值 | 422 | 营业执照号不能为空 |
| VM3-3-B2 | business_license_no | "abc" | 格式错误 | 422 | 统一社会信用代码格式不合法 |
| VM3-3-B3 | legal_person_name | "" | 空值 | 422 | 法人姓名不能为空 |
| VM3-3-B4 | legal_person_id_no | "123" | 格式错误 | 422 | 身份证号格式不合法 |
| VM3-3-B5 | settlement_account_no | "" | 空值 | 422 | 结算账号不能为空 |
| VM3-3-B6 | settlement_account_no | "abc" | 非数字 | 422 | 结算账号必须为数字 |
| VM3-3-B7 | contact_phone | "123" | 格式错误 | 422 | 手机号格式不合法 |
| VM3-3-B8 | legal_person_id_no | null | null | 422 | 字段不能为null |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-3-S1 | 正常提交 | not_submitted | POST 完整体 | 200, submitted |
| VM3-3-S2 | 重复提交 | 已submitted | POST | 409, 已提交不可重复 |
| VM3-3-S3 | 已审批通过再提交 | approved | POST | 409, 已审批不可再提交 |
| VM3-3-S4 | 被拒后重新提交 | rejected | POST | 200, 允许重新提交→submitted |

---

### VM3-4: 支付进件状态查询

**前置条件**:
- VM3-3 已执行, onboarding_status=submitted
- merchant_token 已获取

**API**: `GET /shop/payment-onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 响应包含 onboarding_status (not_submitted/submitted/rejected/approved)
- 响应包含 sub_mch_id (脱敏: 16********00) 仅approved时返回
- 响应包含 application_no
- rejected时返回 reject_reason

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-4-B1 | 未提交时查询 | N/A | 初始状态 | 200 | onboarding_status=not_submitted |
| VM3-4-B2 | token无效 | Authorization | 无效token | 401 | 认证失败 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-4-S1 | 查询submitted状态 | submitted | GET | 200, status=submitted |
| VM3-4-S2 | 查询approved状态 | approved | GET | 200, status=approved, sub_mch_id脱敏 |
| VM3-4-S3 | 查询rejected状态 | rejected | GET | 200, status=rejected, 含reject_reason |

---

### VM3-5: 创建订单 (pending_payment)

**前置条件**:
- 商家已配置支付参数 (VM3-1已执行)
- 商品已上架且 on_sale=true
- buyer_token 或 mp_token 已获取
- stock > 0

**API**: `POST /mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "quantity": 1,
  "buyer_phone": "13900000099",
  "buyer_name": "测试买家"
}
```

**期望结果**:
- HTTP Status: 201
- 响应包含 order_id, order_no
- order.status = pending_payment
- order.amount_cents > 0
- 生成 entitlement 记录 status=pending
- 扣减库存 (stock - quantity)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-5-B1 | product_id | "" | 空值 | 422 | 商品ID不能为空 |
| VM3-5-B2 | quantity | 0 | 零值 | 422 | 购买数量必须>0 |
| VM3-5-B3 | quantity | -1 | 负值 | 422 | 购买数量不能为负 |
| VM3-5-B4 | quantity | 100 | 超库存 | 422 | 库存不足 |
| VM3-5-B5 | buyer_phone | "123" | 格式错误 | 422 | 手机号格式不合法 |
| VM3-5-B6 | buyer_phone | "" | 空值 | 422 | 买家手机号不能为空 |
| VM3-5-B7 | product_id | "not_exist" | 不存在 | 404 | 商品不存在 |
| VM3-5-B8 | quantity | 999999 | 超大数 | 422 | 数量超出限制 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-5-S1 | 正常下单 | 商品on_sale, 有库存 | POST | 201, pending_payment |
| VM3-5-S2 | 商品下架下单 | on_sale=false | POST | 409, 商品已下架 |
| VM3-5-S3 | 库存不足下单 | stock=0 | POST | 422, 库存不足 |
| VM3-5-S4 | 无支付配置下单 | 无payment_config | POST | 422, 未配置支付参数 |

---

### VM3-6: 统一下单 prepay

**前置条件**:
- VM3-5 已执行, order.status=pending_payment
- 支付配置已存在
- WECHAT_PAY_MODE=stub

**API**: `POST /shop/orders/{order_id}/prepay`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "trade_type": "JSAPI",
  "openid": "oUpF8uMuAJO_M2pxb1Q9zNjWeS6o"
}
```

**期望结果**:
- HTTP Status: 200
- 响应包含 prepay_id (stub模式: wx_stub_xxx)
- 响应包含 pay_sign, timestamp, nonce_str
- payment_logs 新增 prepay 记录
- order.status 仍为 pending_payment

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-6-B1 | order_id | invalid_id | 不存在 | 404 | 订单不存在 |
| VM3-6-B2 | trade_type | "" | 空值 | 422 | 交易类型不能为空 |
| VM3-6-B3 | openid | "" | 空值(JSAPI) | 422 | JSAPI模式下openid不能为空 |
| VM3-6-B4 | order_id | closed_order | 已关单 | 409 | 订单已关闭不可支付 |
| VM3-6-B5 | order_id | paid_order | 已支付 | 409 | 订单已支付 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-6-S1 | 正常预支付 | pending_payment | POST | 200, 返回prepay_id |
| VM3-6-S2 | 重复预支付 | 已prepay过 | POST | 200, 返回新prepay_id |
| VM3-6-S3 | 已支付订单预支付 | paid | POST | 409, 不可重复支付 |
| VM3-6-S4 | stub模式返回固定值 | WECHAT_PAY_MODE=stub | POST | 200, prepay_id=wx_stub_xxx |

---

### VM3-7: 支付回调 notify (正常验签通过)

**前置条件**:
- VM3-6 已执行, 获得prepay_id
- order.status=pending_payment
- WECHAT_PAY_MODE=stub
- 使用测试密钥生成有效签名 (RSA-SHA256)

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {valid_signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD202608120001",
  "transaction_id": "wx_stub_tx_001",
  "amount_cents": 9900,
  "notify_id": "notify_001",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- 验签通过 (RSA-SHA256)
- order.status: pending_payment → paid
- entitlement.status: pending → active
- enrollment.status 创建为 active
- payment_logs 新增 notify 记录
- 响应: {"code": "SUCCESS", "message": "OK"}

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-7-B1 | order_no | not_exist | 订单不存在 | 404 | 订单不存在 |
| VM3-7-B2 | amount_cents | 0 | 零金额 | 400 | 金额不合法 |
| VM3-7-B3 | amount_cents | 9999 | 金额不匹配(<实付) | 400 | 回调金额与订单金额不一致 |
| VM3-7-B4 | notify_id | "" | 空值 | 400 | notify_id不能为空 |
| VM3-7-B5 | event_type | "UNKNOWN" | 未知事件 | 400 | 不支持的事件类型 |
| VM3-7-B6 | timestamp | 0 | 零时间戳 | 400 | 时间戳不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-7-S1 | 正常回调 | pending_payment | POST 有效签名 | 200, order→paid |
| VM3-7-S2 | 重复回调(幂等) | 已paid | POST 同notify_id | 200, 不重复处理 |
| VM3-7-S3 | 已关单回调 | closed | POST | 200, 忽略(订单已关闭) |

---

### VM3-8: 回调验签 (签名校验)

**前置条件**:
- VM3-6 已执行
- 存在有效测试密钥对
- 了解RSA-SHA256签名算法

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD202608120001",
  "transaction_id": "wx_stub_tx_001",
  "amount_cents": 9900,
  "notify_id": "notify_002",
  "timestamp": 1723420800
}
```

**期望结果**:
- 有效签名: HTTP 200, 正常处理
- 无效签名: HTTP 400, 拒绝处理
- 缺失签名头: HTTP 400
- 验签失败不修改任何数据
- 验签失败记录 payment_logs (type=notify, result=sign_fail)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-8-B1 | X-WeChat-Pay-Signature | tampered_sig | 篡改签名 | 400 | 验签失败 |
| VM3-8-B2 | X-WeChat-Pay-Signature | "" | 空签名 | 400 | 签名不能为空 |
| VM3-8-B3 | X-WeChat-Pay-Signature | (缺失) | 无签名头 | 400 | 缺少签名头 |
| VM3-8-B4 | X-WeChat-Pay-Signature | invalid_base64!! | 非法base64 | 400 | 签名格式不合法 |
| VM3-8-B5 | body | 修改amount_cents后未更新签名 | body被篡改 | 400 | body与签名不匹配 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-8-S1 | 有效签名 | pending_payment | POST 正确签名 | 200, 正常处理 |
| VM3-8-S2 | 篡改签名 | pending_payment | POST 错误签名 | 400, 验签失败 |
| VM3-8-S3 | 缺失签名头 | pending_payment | POST 无签名头 | 400, 缺少签名 |

---

### VM3-9: 回调幂等

**前置条件**:
- VM3-7 已执行, order已paid
- notify_id 已被处理过

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {valid_signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD202608120001",
  "transaction_id": "wx_stub_tx_001",
  "amount_cents": 9900,
  "notify_id": "notify_001",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- 不重复修改 order.status (仍为paid)
- 不重复激活 entitlement (仍为active)
- 不重复创建 enrollment
- payment_logs 可能新增幂等记录, 标注 idempotent=true
- 响应: {"code": "SUCCESS", "message": "OK"}

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-9-B1 | notify_id | same_notify_001 | 完全相同 | 200 | 幂等, 不重复处理 |
| VM3-9-B2 | notify_id | notify_001 | 相同ID不同body | 200 | 幂等, 以首次为准 |
| VM3-9-B3 | notify_id | notify_003 | 新notify_id | 200 | 新事件, 正常处理 |
| VM3-9-B4 | transaction_id | same_tx | 相同tx不同notify | 200 | 按notify_id幂等 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-9-S1 | 首次回调 | pending_payment | POST notify_001 | 200, pending→paid |
| VM3-9-S2 | 重复回调(同notify_id) | paid | POST notify_001 | 200, 不重复处理 |
| VM3-9-S3 | 不同notify_id回调 | paid | POST notify_004 | 200, 新事件处理 |

---

### VM3-10: 兜底查单

**前置条件**:
- VM3-6 已执行, order.status=pending_payment
- 支付已实际完成但回调未到达
- pending超时 (超过轮询阈值)
- WECHAT_PAY_MODE=stub (stub返回已支付)

**API**: `POST /shop/orders/{order_id}/query`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 查询微信支付侧订单状态 (stub返回PAID)
- order.status: pending_payment → paid (补偿)
- entitlement.status: pending → active
- payment_logs 新增 query 记录
- 微信支付轮询 <=30s 内完成

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-10-B1 | order_id | not_exist | 不存在 | 404 | 订单不存在 |
| VM3-10-B2 | order_id | paid_order | 已支付 | 200 | 返回已支付状态, 无副作用 |
| VM3-10-B3 | order_id | closed_order | 已关单 | 409 | 订单已关闭 |
| VM3-10-B4 | order_id | refunded_order | 已退款 | 200 | 返回已退款状态 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-10-S1 | pending补偿为paid | pending_payment(stub返回PAID) | POST query | 200, pending→paid |
| VM3-10-S2 | pending保持(stub返回PENDING) | pending_payment(stub返回PENDING) | POST query | 200, 保持pending |
| VM3-10-S3 | 已支付订单查单 | paid | POST query | 200, 无副作用 |
| VM3-10-S4 | 已关单订单查单 | closed | POST query | 409, 不可查询 |

---

### VM3-11: 退款申请

**前置条件**:
- VM3-7 已执行, order.status=paid
- entitlement.status=active
- merchant_token 已获取

**API**: `POST /shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "买家申请全额退款商品未使用",
  "amount_cents": 9900
}
```

**期望结果**:
- HTTP Status: 200
- order.status: paid → refunding
- refund 记录创建, status=processing
- payment_logs 新增 refund 记录
- stub模式: 退款立即成功, order.status → refunded
- entitlement.status: active → revoked
- enrollment.status: active → revoked

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-11-B1 | amount_cents | 5000 | 部分退款(<paid) | 422 | Phase1仅支持全额退款 |
| VM3-11-B2 | amount_cents | 9901 | 超出实付 | 422 | 退款金额不能超过实付金额 |
| VM3-11-B3 | reason_code | "invalid_code" | 非枚举值 | 422 | 退款理由编码不合法 |
| VM3-11-B4 | reason_code | "" | 空值 | 422 | 退款理由不能为空 |
| VM3-11-B5 | remark | "ab" | 长度<4 | 422 | 退款备注至少4个字符 |
| VM3-11-B6 | remark | "" | 空值 | 422 | 退款备注不能为空 |
| VM3-11-B7 | amount_cents | 0 | 零金额 | 422 | 退款金额必须>0 |
| VM3-11-B8 | amount_cents | null | null | 422 | 退款金额不能为null |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-11-S1 | 正常全额退款 | paid | POST 全额 | 200, paid→refunding→refunded |
| VM3-11-S2 | 部分退款 | paid | POST 部分 | 422, Phase1不支持部分退款 |
| VM3-11-S3 | 重复退款 | refunded | POST | 409, 已退款不可重复 |
| VM3-11-S4 | pending订单退款 | pending_payment | POST | 409, 未支付不可退款 |

---

### VM3-12: 退款→权益撤销链

**前置条件**:
- VM3-11 已执行, order.status=refunded
- 退款前 entitlement.status=active
- 退款前 enrollment.status=active

**API**: `GET /shop/orders/{order_id}`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- order.status = refunded
- entitlement.status = revoked
- enrollment.status = revoked
- entitlement.revoked_at 不为空
- 已开票退款: needs_red_flush=true (若之前已开票)
- payment_logs 包含完整 refund 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-12-B1 | entitlement检查 | revoked | 撤销验证 | 200 | entitlement已撤销 |
| VM3-12-B2 | enrollment检查 | revoked | 撤销验证 | 200 | enrollment已撤销 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-12-S1 | 退款后权益撤销 | 退款完成 | GET order | 200, entitlement=revoked |
| VM3-12-S2 | 退款后enrollment撤销 | 退款完成 | GET enrollment | 200, enrollment=revoked |
| VM3-12-S3 | 已开票退款红冲标记 | 退款前已开票 | GET invoice | 200, needs_red_flush=true |
| VM3-12-S4 | 未开票退款无红冲 | 退款前未开票 | GET invoice | 404, 无发票记录 |

---

### VM3-13: 无配置下单 422

**前置条件**:
- 商家未配置支付参数 (shop_payment_configs 无记录)
- 商品已上架 on_sale=true
- buyer_token 已获取

**API**: `POST /mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "quantity": 1,
  "buyer_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 422
- 错误码: payment_config_not_found
- 错误信息: 店铺未配置支付参数
- 不创建订单记录
- 不扣减库存

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-13-B1 | 无配置 | N/A | 缺失配置 | 422 | payment_config_not_found |
| VM3-13-B2 | 配置被删除 | 曾配置后删除 | 下单 | 422 | payment_config_not_found |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-13-S1 | 从未配置 | 无配置记录 | POST 下单 | 422, payment_config_not_found |
| VM3-13-S2 | 配置后删除再下单 | 配置已删除 | POST 下单 | 422, payment_config_not_found |
| VM3-13-S3 | 他店有配置本店无 | A店有配置B店无 | B店下单 | 422, 仅检查本店配置 |

---

### VM3-14: 多店支付隔离

**前置条件**:
- A店已配置支付参数 (wx_mch_id=1900000109)
- B店已配置不同支付参数 (wx_mch_id=1900000208)
- 两个店铺的商品均上架

**API**: `POST /shop/orders/{order_id}/prepay`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "trade_type": "JSAPI",
  "openid": "oUpF8uMuAJO_M2pxb1Q9zNjWeS6o"
}
```

**期望结果**:
- A店订单使用A店支付配置 (mch_id=1900000109)
- B店订单使用B店支付配置 (mch_id=1900000208)
- A店prepay不使用B店配置, 反之亦然
- payment_logs 记录对应的 mch_id
- 回调验签使用对应店铺的密钥

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-14-B1 | A店订单 | A配置 | prepay | 200 | 使用A的mch_id |
| VM3-14-B2 | B店订单 | B配置 | prepay | 200 | 使用B的mch_id |
| VM3-14-B3 | A店回调用B密钥 | A订单+B密钥 | notify | 400 | 验签失败(配置隔离) |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-14-S1 | A店下单+prepay | A店配置 | POST | 200, 使用A店mch_id |
| VM3-14-S2 | B店下单+prepay | B店配置 | POST | 200, 使用B店mch_id |
| VM3-14-S3 | A店回调用A密钥 | A订单+A密钥 | notify | 200, 验签通过 |
| VM3-14-S4 | A店回调用B密钥 | A订单+B密钥 | notify | 400, 验签失败 |

---

### VM3-15: 支付配置密文存储验证

**前置条件**:
- VM3-1 已执行, 配置已保存
- 拥有数据库直接查询权限 (平台管理员)

**API**: `GET /shop/payment-config (数据库验证)`
**Headers**: `Authorization: Bearer {platform_admin_token}`

**期望结果**:
- 数据库 shop_payment_configs.wx_api_key != 明文 (AES-256-GCM加密)
- 数据库 shop_payment_configs.wx_cert_pem != 明文
- 数据库 shop_payment_configs.wx_apiclient_key != 明文
- 解密后明文与输入一致
- 密文包含 GCM auth tag
- 不同记录的密文不同 (即使明文相同, IV不同)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-15-B1 | wx_api_key密文 | AES-256-GCM | 加密验证 | 200 | 存储为密文 |
| VM3-15-B2 | wx_cert_pem密文 | AES-256-GCM | 加密验证 | 200 | 存储为密文 |
| VM3-15-B3 | 相同明文不同密文 | 同key不同IV | IV验证 | 200 | 密文不同 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-15-S1 | 配置保存后密文验证 | 已保存 | 查询DB | 密文存储, 解密一致 |
| VM3-15-S2 | 配置更新后密文验证 | 已更新 | 查询DB | 新密文, 旧明文被覆盖 |
| VM3-15-S3 | 多店配置密文隔离 | A+B店配置 | 查询DB | 各自独立加密 |

---

### VM3-16: 子商户号脱敏验证

**前置条件**:
- VM3-3 已审批通过, 获得 sub_mch_id
- sub_mch_id = 16位子商户号 (如 1900000109000001)

**API**: `GET /shop/payment-onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 响应中 sub_mch_id 脱敏格式: 16********00
- 前2位 + 后2位明文, 中间脱敏
- 数据库存储完整 sub_mch_id
- API证书/v3密钥不返回 (P06平台维护)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-16-B1 | 16位子商户号 | 1900000109000001 | 脱敏 | 200 | 19********01 |
| VM3-16-B2 | 未审批查询 | not_submitted | 无子商户号 | 200 | 不含sub_mch_id字段 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-16-S1 | 审批通过查看脱敏 | approved | GET | 200, 19********01 |
| VM3-16-S2 | 未审批无子商户号 | submitted | GET | 200, 无sub_mch_id |
| VM3-16-S3 | 平台管理员查看完整 | approved | GET (admin) | 200, 完整sub_mch_id |

---

### VM3-17: 结算账号脱敏验证

**前置条件**:
- VM3-3 已提交, 包含 settlement_account_no

**API**: `GET /shop/payment-onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 响应中 settlement_account_no 脱敏: 尾号4位 (如 ****6789)
- 前4位隐藏, 仅显示后4位
- 数据库存储完整账号

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-17-B1 | 16位银行卡 | 6225880123456789 | 脱敏 | 200 | ****6789 |
| VM3-17-B2 | 短账号 | 123456 | 脱敏 | 200 | ****3456 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-17-S1 | 正常脱敏 | 已提交 | GET | 200, ****6789 |
| VM3-17-S2 | 平台管理员查看 | 已提交 | GET (admin) | 200, 完整账号 |

---

### VM3-18: 证书字段不返回

**前置条件**:
- VM3-1 已保存 wx_cert_pem 和 wx_apiclient_key

**API**: `GET /shop/payment-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 响应不包含 wx_cert_pem 字段
- 响应不包含 wx_apiclient_key 字段
- 响应不包含 wx_api_key 明文
- API证书/v3密钥归P06平台维护, 商家API不返回

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-18-B1 | 证书字段 | wx_cert_pem | 不应返回 | 200 | 字段不存在 |
| VM3-18-B2 | 密钥字段 | wx_apiclient_key | 不应返回 | 200 | 字段不存在 |
| VM3-18-B3 | API密钥明文 | wx_api_key | 不应返回明文 | 200 | 字段不存在或脱敏 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-18-S1 | 商家读取配置 | 已配置 | GET | 200, 无证书字段 |
| VM3-18-S2 | 平台管理员读取 | 已配置 | GET (admin) | 200, 可含证书引用 |

---

### VM3-19: 订单关单 (超时/取消)

**前置条件**:
- VM3-5 已执行, order.status=pending_payment
- 订单超过支付超时时间 (如30分钟)

**API**: `POST /shop/orders/{order_id}/close`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason": "payment_timeout"
}
```

**期望结果**:
- HTTP Status: 200
- order.status: pending_payment → closed
- 库存回补 (stock + quantity)
- entitlement.status: pending → cancelled
- closed订单不可再支付/关单

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-19-B1 | order_id | paid_order | 已支付 | 409 | 已支付订单不可关单 |
| VM3-19-B2 | order_id | closed_order | 已关单 | 409 | 重复关单 |
| VM3-19-B3 | order_id | refunded_order | 已退款 | 409 | 已退款不可关单 |
| VM3-19-B4 | reason | "" | 空值 | 422 | 关单理由不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-19-S1 | 超时关单 | pending_payment(超时) | POST close | 200, →closed |
| VM3-19-S2 | 手动关单 | pending_payment(未超时) | POST close | 200, →closed |
| VM3-19-S3 | 已支付关单 | paid | POST close | 409, 不可关单 |
| VM3-19-S4 | 关单后下单 | closed | POST new order | 201, 新订单 |

---

### VM3-20: 退款金额校验 (部分退款422)

**前置条件**:
- VM3-7 已执行, order.status=paid, amount_cents=9900

**API**: `POST /shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "买家申请部分退款",
  "amount_cents": 5000
}
```

**期望结果**:
- HTTP Status: 422
- 错误码: partial_refund_not_supported
- 错误信息: Phase1仅支持全额退款
- 不修改订单状态
- 不创建退款记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-20-B1 | amount_cents | 5000 | 部分退款 | 422 | partial_refund_not_supported |
| VM3-20-B2 | amount_cents | 9901 | 超出实付 | 422 | 超出实付金额 |
| VM3-20-B3 | amount_cents | 9900 | 全额退款 | 200 | 正常退款 |
| VM3-20-B4 | amount_cents | 0 | 零金额 | 422 | 退款金额必须>0 |
| VM3-20-B5 | amount_cents | -100 | 负值 | 422 | 退款金额不能为负 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-20-S1 | 部分退款 | paid(9900) | POST 5000 | 422, partial_refund_not_supported |
| VM3-20-S2 | 全额退款 | paid(9900) | POST 9900 | 200, 正常退款 |
| VM3-20-S3 | 超额退款 | paid(9900) | POST 10000 | 422, 超出实付 |

---

### VM3-21: 退款理由校验

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "买家申请全额退款商品未使用",
  "amount_cents": 9900
}
```

**期望结果**:
- HTTP Status: 200 (合法理由)
- reason_code 必须为枚举值: customer_request / quality_issue / service_issue / other
- remark 长度 >= 4 字符
- 退款记录保存 reason_code 和 remark

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-21-B1 | reason_code | "invalid" | 非枚举 | 422 | 理由编码不合法 |
| VM3-21-B2 | reason_code | "" | 空值 | 422 | 理由编码不能为空 |
| VM3-21-B3 | remark | "ab" | 长度<4 | 422 | 备注至少4字符 |
| VM3-21-B4 | remark | "" | 空值 | 422 | 备注不能为空 |
| VM3-21-B5 | remark | null | null | 422 | 备注不能为null |
| VM3-21-B6 | reason_code | "customer_request" | 合法枚举 | 200 | 正常退款 |
| VM3-21-B7 | reason_code | "quality_issue" | 合法枚举 | 200 | 正常退款 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-21-S1 | 合法理由退款 | paid | POST customer_request+4字remark | 200, 退款成功 |
| VM3-21-S2 | 非法枚举 | paid | POST invalid_code | 422, 理由编码不合法 |
| VM3-21-S3 | 备注过短 | paid | POST 2字remark | 422, 备注至少4字符 |

---

### VM3-22: 已开票退款 needs_red_flush

**前置条件**:
- VM3-7 已执行, order.status=paid
- VM6-9 已执行, 发票已开具 (invoice.status=issued)

**API**: `POST /shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "买家申请全额退款已开票",
  "amount_cents": 9900
}
```

**期望结果**:
- HTTP Status: 200
- order.status → refunded
- shop_invoice_requests.needs_red_flush = true
- entitlement.status → revoked
- Phase1人工红冲 (不自动红冲)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-22-B1 | 已开票退款 | invoice=issued | POST refund | 200 | needs_red_flush=true |
| VM3-22-B2 | 未开票退款 | 无invoice | POST refund | 200 | 无红冲标记 |
| VM3-22-B3 | 发票待开具退款 | invoice=submitted | POST refund | 200 | 先拒绝发票再退款 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-22-S1 | 已开票退款 | issued | POST refund | 200, needs_red_flush=true |
| VM3-22-S2 | 未开票退款 | 无发票 | POST refund | 200, 无红冲 |
| VM3-22-S3 | 红冲状态查询 | 退款后 | GET invoice | 200, needs_red_flush=true |

---

### VM3-23: 支付日志完整性

**前置条件**:
- 完整支付流程已执行: 下单→prepay→notify→refund

**API**: `GET /shop/orders/{order_id}/payment-logs`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- payment_logs 包含 create 记录 (下单时)
- payment_logs 包含 prepay 记录 (预支付时)
- payment_logs 包含 notify 记录 (回调时)
- payment_logs 包含 refund 记录 (退款时)
- 每条日志包含 type, result, amount_cents, created_at
- 日志按时间排序

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-23-B1 | 日志类型 | create | 下单日志 | 200 | 存在create记录 |
| VM3-23-B2 | 日志类型 | prepay | 预支付日志 | 200 | 存在prepay记录 |
| VM3-23-B3 | 日志类型 | notify | 回调日志 | 200 | 存在notify记录 |
| VM3-23-B4 | 日志类型 | refund | 退款日志 | 200 | 存在refund记录 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-23-S1 | 完整链路日志 | 全流程完成 | GET logs | 200, 4条日志 |
| VM3-23-S2 | 仅下单日志 | 只下单 | GET logs | 200, 1条create记录 |
| VM3-23-S3 | 验签失败日志 | notify验签失败 | GET logs | 200, 含sign_fail记录 |

---

### VM3-24: 回调验签失败-篡改签名

**前置条件**:
- VM3-6 已执行, order.status=pending_payment
- 持有正确签名, 将被篡改

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {tampered_signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD202608120001",
  "transaction_id": "wx_stub_tx_001",
  "amount_cents": 9900,
  "notify_id": "notify_005",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 400
- 错误信息: signature_verification_failed
- order.status 不变 (仍为 pending_payment)
- entitlement.status 不变
- payment_logs 记录验签失败

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-24-B1 | signature | 改1字符 | 微篡改 | 400 | 验签失败 |
| VM3-24-B2 | body.amount | 改金额不改签名 | body篡改 | 400 | 验签失败 |
| VM3-24-B3 | signature | 全替换 | 完全伪造 | 400 | 验签失败 |
| VM3-24-B4 | signature | (缺失) | 无签名 | 400 | 缺少签名 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-24-S1 | 篡改签名 | pending_payment | POST 篡改签名 | 400, 验签失败 |
| VM3-24-S2 | 正确签名 | pending_payment | POST 正确签名 | 200, 正常处理 |
| VM3-24-S3 | 验签失败后正确回调 | pending_payment | 先篡改后正确 | 200, 第二次成功 |

---

### VM3-25: 密钥轮换宽限期

**前置条件**:
- 支付配置已更新 (旧密钥→新密钥)
- 旧密钥在24h宽限期内
- 回调使用旧密钥签名

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {old_key_signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD202608120001",
  "transaction_id": "wx_stub_tx_001",
  "amount_cents": 9900,
  "notify_id": "notify_006",
  "timestamp": 1723420800
}
```

**期望结果**:
- 宽限期内: 旧密钥签名验签通过, HTTP 200
- 宽限期外 (>24h): 旧密钥验签失败, HTTP 400
- 新密钥签名始终验签通过
- 宽限期内同时接受新旧密钥

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-25-B1 | 旧密钥(宽限期内) | <24h | 宽限期 | 200 | 验签通过 |
| VM3-25-B2 | 旧密钥(宽限期外) | >24h | 过期 | 400 | 验签失败 |
| VM3-25-B3 | 新密钥 | 当前 | 正常 | 200 | 验签通过 |
| VM3-25-B4 | 旧密钥(边界23h59m) | ~24h | 边界 | 200 | 验签通过 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-25-S1 | 宽限期内旧密钥 | 更新<24h | POST 旧密钥签名 | 200, 验签通过 |
| VM3-25-S2 | 宽限期外旧密钥 | 更新>24h | POST 旧密钥签名 | 400, 验签失败 |
| VM3-25-S3 | 宽限期内新密钥 | 更新<24h | POST 新密钥签名 | 200, 验签通过 |

---

### VM3-26: 支付轮询超时

**前置条件**:
- VM3-6 已执行, order.status=pending_payment
- WECHAT_PAY_MODE=stub (模拟查询响应延迟)

**API**: `POST /shop/orders/{order_id}/query`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200 (或 408 超时)
- 微信支付轮询 <= 30s 内完成
- stub模式: 立即返回结果
- 超时: 返回 timeout 错误, order保持pending
- 轮询期间不阻塞其他请求

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-26-B1 | stub立即返回 | 0s | 正常 | 200 | 立即返回PAID |
| VM3-26-B2 | stub模拟延迟 | 25s | 接近超时 | 200 | 25s内返回 |
| VM3-26-B3 | stub模拟超时 | 35s | 超时 | 408 | 轮询超时 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-26-S1 | 正常查单(<30s) | stub 0s | POST query | 200, 及时返回 |
| VM3-26-S2 | 接近超时(25s) | stub 25s | POST query | 200, 在30s内返回 |
| VM3-26-S3 | 超时(>30s) | stub 35s | POST query | 408, 轮询超时 |

---

### VM3-27: 退款回调失败→paid可重试

**前置条件**:
- VM3-11 已执行退款, order.status=refunding
- 退款回调失败 (网络异常)

**API**: `POST /shop/orders/{order_id}/refund/retry`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- 退款回调失败: order.status: refunding → paid (可重试)
- 重试退款: order.status: paid → refunding → refunded
- payment_logs 记录退款回调失败
- 退款回调失败不影响已扣减的权益(若已撤销)
- 可多次重试直到成功

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-27-B1 | 回调失败→paid | refunding | 回调失败 | 200 | 回滚到paid |
| VM3-27-B2 | 重试退款 | paid(回调失败) | POST retry | 200 | refunding→refunded |
| VM3-27-B3 | 多次重试 | 多次失败 | POST retry x3 | 200 | 最终成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-27-S1 | 回调失败回滚 | refunding | 回调失败 | 200, →paid |
| VM3-27-S2 | 重试成功 | paid(回滚后) | POST retry | 200, →refunded |
| VM3-27-S3 | 多次失败后成功 | paid | POST retry x3 | 200, 最终refunded |

---

### VM3-28: claim_pending→paid (M14领权支付)

**前置条件**:
- M7抖店Webhook已创建 claim_pending 订单
- 买家已通过领权页面提交领权

**API**: `POST /claim/{token}`
**Headers**: `Authorization: Bearer {buyer_token} (可选)`

**请求体**:
```json
{
  "buyer_phone": "13900000099",
  "buyer_name": "测试买家"
}
```

**期望结果**:
- HTTP Status: 200
- order.status: claim_pending → paid
- entitlement.status: pending → active
- enrollment.status: active
- token 标记为已使用 (单次使用)
- payment_logs 新增 claim 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-28-B1 | token | invalid_token | 无效 | 404 | 领权码不存在 |
| VM3-28-B2 | token | used_token | 已使用 | 409 | 领权码已使用 |
| VM3-28-B3 | buyer_phone | "123" | 格式错误 | 422 | 手机号格式不合法 |
| VM3-28-B4 | buyer_phone | "" | 空值 | 422 | 手机号不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-28-S1 | 正常领权 | claim_pending | POST | 200, →paid |
| VM3-28-S2 | 重复领权 | 已paid(token已用) | POST | 409, 已使用 |
| VM3-28-S3 | 无效token | N/A | POST invalid | 404, 不存在 |

---

### VM3-29: claim_pending→refunded (抖店退款)

**前置条件**:
- M7抖店退款Webhook已触发
- order.status=claim_pending 或 paid

**API**: `POST /webhooks/douyin (refund webhook)`
**Headers**: `X-Douyin-Signature: {hmac_signature}`

**请求体**:
```json
{
  "event_id": "evt_refund_001",
  "event_type": "order.refund",
  "external_order_no": "DY_order_001",
  "refund_amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- order.status: claim_pending/paid → refunded (公域Webhook直写)
- entitlement.status → revoked
- enrollment.status → revoked
- payment_logs 新增 refund 记录
- Webhook幂等: 重复event_id不重复处理

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-29-B1 | event_id | 重复 | 幂等 | 200 | 不重复处理 |
| VM3-29-B2 | external_order_no | not_exist | 未映射 | 200 | 拒单+audit_log |
| VM3-29-B3 | refund_amount | 0 | 零金额 | 400 | 退款金额不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-29-S1 | claim_pending退款 | claim_pending | POST webhook | 200, →refunded |
| VM3-29-S2 | paid退款 | paid | POST webhook | 200, →refunded |
| VM3-29-S3 | 重复退款webhook | 已refunded | POST 同event_id | 200, 幂等 |

---

### VM3-30: 支付进件-拒绝后重新提交

**前置条件**:
- VM3-3 已提交, 被审批拒绝 (onboarding_status=rejected)
- reject_reason 已记录

**API**: `POST /shop/payment-onboarding/submit`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "business_license_no": "91440101MA5XXXXXX",
  "legal_person_name": "张三",
  "legal_person_id_no": "440101199001011234",
  "settlement_account_no": "6225880123456789",
  "settlement_bank_name": "招商银行",
  "contact_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- onboarding_status: rejected → submitted
- 生成新 application_no
- 保留历史拒绝记录 (audit_log)
- 新提交可修改之前被拒字段

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-30-B1 | rejected重新提交 | rejected | 修改字段后提交 | 200 | →submitted |
| VM3-30-B2 | 未修改重新提交 | rejected | 相同内容提交 | 200 | →submitted(允许) |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-30-S1 | 拒绝后重新提交 | rejected | POST 修改后 | 200, →submitted |
| VM3-30-S2 | 拒绝后查看历史 | rejected | GET audit_log | 200, 含拒绝记录 |
| VM3-30-S3 | 重新提交后审批通过 | submitted→approved | 平台审批 | 200, approved |

---

### VM3-31: 支付进件-审批通过查询

**前置条件**:
- VM3-3 已提交, 平台管理员已审批通过
- onboarding_status=approved

**API**: `GET /shop/payment-onboarding/status`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- onboarding_status=approved
- 返回 sub_mch_id (脱敏)
- 返回 approved_at
- 返回 application_no

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-31-B1 | approved状态 | approved | 查询 | 200 | 含sub_mch_id脱敏 |
| VM3-31-B2 | 刚approved | approved(刚通过) | 查询 | 200 | approved_at有值 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-31-S1 | 审批通过查询 | approved | GET | 200, approved+sub_mch_id |
| VM3-31-S2 | 审批通过后配置 | approved | POST config | 200, 可保存配置 |

---

### VM3-32: 订单关单后不可支付

**前置条件**:
- VM3-19 已执行, order.status=closed

**API**: `POST /shop/orders/{order_id}/prepay`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "trade_type": "JSAPI",
  "openid": "oUpF8uMuAJO_M2pxb1Q9zNjWeS6o"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: order_closed
- 不创建prepay记录
- 不修改订单状态

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-32-B1 | closed订单prepay | closed | POST prepay | 409 | 订单已关闭 |
| VM3-32-B2 | closed订单notify | closed | POST notify | 200 | 忽略回调 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-32-S1 | 关单后预支付 | closed | POST prepay | 409, order_closed |
| VM3-32-S2 | 关单后退款 | closed | POST refund | 409, 不可退款 |

---

### VM3-33: 已退款订单不可再次退款

**前置条件**:
- VM3-11 已执行, order.status=refunded

**API**: `POST /shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "再次申请退款",
  "amount_cents": 9900
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: already_refunded
- 不创建新退款记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-33-B1 | refunded退款 | refunded | POST refund | 409 | 已退款 |
| VM3-33-B2 | refunding退款 | refunding | POST refund | 409 | 退款中 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-33-S1 | 已退款再退款 | refunded | POST refund | 409, already_refunded |
| VM3-33-S2 | 退款中再退款 | refunding | POST refund | 409, 退款进行中 |

---

### VM3-34: prepay_id 有效性验证

**前置条件**:
- VM3-6 已执行, 获得 prepay_id=wx_stub_xxx

**API**: `POST /shop/orders/{order_id}/prepay`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "trade_type": "JSAPI",
  "openid": "oUpF8uMuAJO_M2pxb1Q9zNjWeS6o"
}
```

**期望结果**:
- HTTP Status: 200
- stub模式: prepay_id 固定为 wx_stub_xxx
- 响应包含签名所需字段: appId, timeStamp, nonceStr, package, signType, paySign
- paySign 使用对应店铺密钥生成

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-34-B1 | prepay_id格式 | wx_stub_xxx | stub固定值 | 200 | 格式正确 |
| VM3-34-B2 | paySign | 非空 | 签名验证 | 200 | 签名存在 |
| VM3-34-B3 | timeStamp | 当前时间 | 时效性 | 200 | 时间戳有效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-34-S1 | stub模式prepay | stub | POST | 200, wx_stub_xxx |
| VM3-34-S2 | 重复prepay | 已prepay | POST | 200, 新prepay_id |

---

### VM3-35: 支付配置更新(重复保存)

**前置条件**:
- VM3-1 已执行, 配置已存在

**API**: `POST /shop/payment-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "wx_api_key": "new_key_9876543210fedcba",
  "wx_mch_id": "1900000109",
  "wx_cert_pem": "-----BEGIN CERTIFICATE-----\nMIIEowIBAAKCAQEA...\n-----END CERTIFICATE-----",
  "wx_apiclient_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg...\n-----END PRIVATE KEY-----"
}
```

**期望结果**:
- HTTP Status: 200
- 不新增记录, 更新已有记录
- wx_api_key 更新为新密文
- 旧密钥进入24h宽限期
- config_id 不变, updated_at 更新

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-35-B1 | 更新wx_api_key | 新密钥 | 更新 | 200 | 密文更新 |
| VM3-35-B2 | 更新wx_mch_id | 新商户号 | 更新 | 200 | 商户号更新 |
| VM3-35-B3 | 完全相同内容 | 相同 | 重复保存 | 200 | 幂等更新 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-35-S1 | 更新密钥 | 已有配置 | POST 新key | 200, 更新+宽限期 |
| VM3-35-S2 | 更新后旧密钥宽限 | 更新<24h | notify 旧密钥 | 200, 验签通过 |
| VM3-35-S3 | 更新后新密钥 | 更新后 | notify 新密钥 | 200, 验签通过 |

---

### VM3-36: 订单金额校验

**前置条件**:
- 商品已上架, price_cents=9900

**API**: `POST /mp/shop/orders`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "quantity": 2,
  "buyer_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 201
- order.amount_cents = product.price_cents * quantity
- amount_cents = 9900 * 2 = 19800
- 服务端计算金额, 不信任客户端传入金额

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-36-B1 | quantity=2 | 9900*2 | 多件 | 201 | amount=19800 |
| VM3-36-B2 | quantity=1 | 9900*1 | 单件 | 201 | amount=9900 |
| VM3-36-B3 | quantity=10 | 9900*10 | 大批量 | 201 | amount=99000 |
| VM3-36-B4 | quantity=0 | 0 | 零值 | 422 | 数量必须>0 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-36-S1 | 单件订单 | quantity=1 | POST | 201, amount=9900 |
| VM3-36-S2 | 多件订单 | quantity=3 | POST | 201, amount=29700 |
| VM3-36-S3 | 金额服务端计算 | 传入amount | POST | 201, 忽略客户端amount |

---

### VM3-37: 支付回调-订单不存在

**前置条件**:
- 使用不存在的order_no构造回调

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {valid_signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD_NOT_EXIST_999",
  "transaction_id": "wx_stub_tx_002",
  "amount_cents": 9900,
  "notify_id": "notify_010",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 404
- 错误码: order_not_found
- 不修改任何数据
- payment_logs 可能记录异常

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-37-B1 | order_no | OD_NOT_EXIST | 不存在 | 404 | 订单不存在 |
| VM3-37-B2 | order_no | "" | 空值 | 400 | 订单号不能为空 |
| VM3-37-B3 | order_no | OD_deleted | 已删除 | 404 | 订单不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-37-S1 | 不存在订单回调 | N/A | POST | 404, order_not_found |
| VM3-37-S2 | 空订单号回调 | N/A | POST | 400, 参数错误 |

---

### VM3-38: 支付回调-金额不匹配

**前置条件**:
- VM3-5 已执行, order.amount_cents=9900

**API**: `POST /shop/payment/notify`
**Headers**: `Content-Type: application/json, X-WeChat-Pay-Signature: {valid_signature}`

**请求体**:
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "order_no": "OD202608120001",
  "transaction_id": "wx_stub_tx_003",
  "amount_cents": 5000,
  "notify_id": "notify_011",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 400
- 错误码: amount_mismatch
- order.status 不变
- 不激活entitlement

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-38-B1 | amount_cents | 5000(<9900) | 少付 | 400 | 金额不匹配 |
| VM3-38-B2 | amount_cents | 10000(>9900) | 多付 | 400 | 金额不匹配 |
| VM3-38-B3 | amount_cents | 9900(=实付) | 匹配 | 200 | 正常处理 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-38-S1 | 金额匹配 | 9900 | POST | 200, 正常处理 |
| VM3-38-S2 | 金额少付 | 5000 | POST | 400, amount_mismatch |
| VM3-38-S3 | 金额多付 | 10000 | POST | 400, amount_mismatch |

---

### VM3-39: 兜底查单-订单已paid

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/orders/{order_id}/query`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 返回 order.status=paid
- 不重复处理 (无副作用)
- 不重复激活entitlement

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-39-B1 | 已paid查单 | paid | POST query | 200 | 无副作用 |
| VM3-39-B2 | 已refunded查单 | refunded | POST query | 200 | 返回refunded |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-39-S1 | 已支付查单 | paid | POST query | 200, 无副作用 |
| VM3-39-S2 | 已退款查单 | refunded | POST query | 200, 返回refunded |

---

### VM3-40: 退款-entitlement不存在

**前置条件**:
- VM3-7 已执行, 但entitlement异常缺失

**API**: `POST /shop/orders/{order_id}/refund`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "买家申请退款",
  "amount_cents": 9900
}
```

**期望结果**:
- HTTP Status: 200 (或 500 取决于实现)
- order.status → refunded
- 退款不因entitlement缺失而失败
- payment_logs 记录 refund
- entitlement跳过撤销 (已不存在)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-40-B1 | 无entitlement退款 | entitlement缺失 | POST refund | 200 | 退款成功 |
| VM3-40-B2 | entitlement已revoked | revoked | POST refund | 200 | 不重复撤销 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-40-S1 | entitlement缺失退款 | paid(无entitlement) | POST refund | 200, 退款成功 |
| VM3-40-S2 | entitlement已撤销 | paid(revoked) | POST refund | 200, 不重复撤销 |

---

### VM3-41: 微信支付Mock stub模式验证

**前置条件**:
- WECHAT_PAY_MODE=stub

**API**: `POST /shop/orders/{order_id}/prepay`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "trade_type": "JSAPI",
  "openid": "oUpF8uMuAJO_M2pxb1Q9zNjWeS6o"
}
```

**期望结果**:
- stub模式: prepay_id 固定为 wx_stub_xxx
- stub模式: notify 验签使用测试密钥
- stub模式: query 返回固定 PAID 状态
- stub模式: refund 立即成功
- stub模式: 不实际调用微信支付API

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-41-B1 | stub prepay | stub | POST prepay | 200 | wx_stub_xxx |
| VM3-41-B2 | stub notify | stub | POST notify | 200 | 测试密钥验签 |
| VM3-41-B3 | stub query | stub | POST query | 200 | 返回PAID |
| VM3-41-B4 | stub refund | stub | POST refund | 200 | 立即成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-41-S1 | stub全链路 | stub | 完整流程 | 全200 |
| VM3-41-S2 | stub prepay固定值 | stub | POST prepay | 200, wx_stub_xxx |

---

### VM3-42: 订单状态机-paid→refunding→refunded 完整流程

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/orders/{order_id}/refund → 状态流转验证`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reason_code": "customer_request",
  "remark": "买家申请全额退款商品未使用",
  "amount_cents": 9900
}
```

**期望结果**:
- 退款发起: paid → refunding
- stub退款成功: refunding → refunded
- entitlement: active → revoked
- enrollment: active → revoked
- 状态不可逆: refunded 不可回退

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-42-B1 | paid→refunding | paid | POST refund | 200 | →refunding |
| VM3-42-B2 | refunding→refunded | refunding | stub回调 | 200 | →refunded |
| VM3-42-B3 | refunded不可回退 | refunded | POST任何 | 409 | 不可逆 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-42-S1 | 完整退款流程 | paid | POST refund | 200, paid→refunding→refunded |
| VM3-42-S2 | 退款后不可恢复 | refunded | POST any | 409, 不可逆 |
| VM3-42-S3 | 退款回调失败回滚 | refunding | 回调失败 | 200, →paid可重试 |

---

### VM3-43: 退款-enrollment状态验证

**前置条件**:
- VM3-7 已执行, enrollment.status=active
- VM3-11 已执行退款

**API**: `GET /shop/enrollments/{enrollment_id}`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- enrollment.status = revoked
- enrollment.revoked_at 不为空
- enrollment.revoked_reason 包含退款信息
- revoked后不可学习课程

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-43-B1 | 退款后enrollment | revoked | GET | 200 | status=revoked |
| VM3-43-B2 | revoked后学习 | revoked | POST learn | 403 | 已撤销不可学习 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-43-S1 | 退款后enrollment撤销 | 退款完成 | GET | 200, revoked |
| VM3-43-S2 | 撤销后不可学习 | revoked | POST learn | 403, 已撤销 |
| VM3-43-S3 | 撤销前可学习 | active | POST learn | 200, 正常学习 |

---

### VM3-44: 支付配置-wx_api_key长度校验

**前置条件**:
- 商家已入驻 status=active

**API**: `POST /shop/payment-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "wx_api_key": "test_key_1234567890",
  "wx_mch_id": "1900000109"
}
```

**期望结果**:
- wx_api_key 最小长度: 10 字符
- wx_api_key 最大长度: 128 字符
- 合法长度: HTTP 200
- 非法长度: HTTP 422

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-44-B1 | wx_api_key | "12345678" | 9字符(不足) | 422 | 长度<10 |
| VM3-44-B2 | wx_api_key | "1234567890" | 10字符(最小) | 200 | 最小合法长度 |
| VM3-44-B3 | wx_api_key | 129字符 | 超长 | 422 | 长度>128 |
| VM3-44-B4 | wx_api_key | 128字符 | 最大长度 | 200 | 最大合法长度 |
| VM3-44-B5 | wx_api_key | "" | 空值 | 422 | 不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-44-S1 | 最小合法长度 | 10字符 | POST | 200, 保存成功 |
| VM3-44-S2 | 最大合法长度 | 128字符 | POST | 200, 保存成功 |
| VM3-44-S3 | 不足最小长度 | 9字符 | POST | 422, 长度不足 |

---

### VM3-45: 兜底查单-订单已closed

**前置条件**:
- VM3-19 已执行, order.status=closed

**API**: `POST /shop/orders/{order_id}/query`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 409
- 错误码: order_closed
- 不查询微信支付侧
- 不修改订单状态

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM3-45-B1 | closed查单 | closed | POST query | 409 | 订单已关闭 |
| VM3-45-B2 | closed后退款 | closed | POST refund | 409 | 不可退款 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM3-45-S1 | 已关单查单 | closed | POST query | 409, order_closed |
| VM3-45-S2 | 已关单退款 | closed | POST refund | 409, 不可退款 |

---


## 二、M6 核销开票

> **模块说明**: 覆盖核销查询/执行、次数卡管理、预约管理(创建/取消/过期)、时段状态管理、发票申请/开具/驳回/红冲等全链路。
> **核心表**: shop_redemptions, shop_bookings, shop_service_slots, shop_invoice_requests, entitlements
> **核销结果枚举**: 可核销 / 码无效 / 已核销 / 已退款 / 次数用尽

---

### VM6-1: 核销查询-手机号lookup

**前置条件**:
- 买家已购买商品且 entitlement.status=active
- entitlement.times_used < times_total
- merchant_token 已获取 (13900000099/test123456)

**API**: `POST /shop/redemptions/lookup`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 返回买家所有有效权益列表
- 每条权益包含: entitlement_id, product_name, times_total, times_used, remaining, status
- 仅返回本店铺的权益
- 不返回已退款(revoked)的权益

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-1-B1 | phone | "" | 空值 | 422 | 手机号不能为空 |
| VM6-1-B2 | phone | "123" | 格式错误 | 422 | 手机号格式不合法 |
| VM6-1-B3 | phone | "13900000099" | 正常 | 200 | 返回权益列表 |
| VM6-1-B4 | phone | "abcde12345" | 非数字 | 422 | 手机号必须为数字 |
| VM6-1-B5 | phone | "1390000009" | 11位不足 | 422 | 手机号长度不合法 |
| VM6-1-B6 | phone | "139000000999" | 超长 | 422 | 手机号长度不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-1-S1 | 正常查询 | 有有效权益 | POST | 200, 返回权益列表 |
| VM6-1-S2 | 无权益查询 | 无购买记录 | POST | 200, 空列表 |
| VM6-1-S3 | 已退款权益不返回 | entitlement=revoked | POST | 200, 不含revoked |
| VM6-1-S4 | 多权益查询 | 多个有效权益 | POST | 200, 返回多条 |

---

### VM6-2: 核销执行-execute

**前置条件**:
- VM6-1 已查询, entitlement.status=active
- times_used < times_total (remaining > 0)
- merchant_token 已获取

**API**: `POST /shop/redemptions/execute`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- entitlement.times_used += 1
- 创建核销记录 (shop_redemptions)
- 若 times_used == times_total: entitlement.status → expired
- 若 times_used < times_total: entitlement.status 保持 active

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-2-B1 | entitlement_id | "" | 空值 | 422 | 权益ID不能为空 |
| VM6-2-B2 | entitlement_id | "not_exist" | 不存在 | 404 | 权益不存在 |
| VM6-2-B3 | phone | "" | 空值 | 422 | 手机号不能为空 |
| VM6-2-B4 | phone | "13900000099" | 正常 | 200 | 核销成功 |
| VM6-2-B5 | entitlement_id | other_shop_ent | 他店权益 | 403 | 无权核销他店权益 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-2-S1 | 正常核销 | active, remaining>0 | POST | 200, times_used+1 |
| VM6-2-S2 | 最后一次核销 | remaining=1 | POST | 200, →expired |
| VM6-2-S3 | 已核销核销 | expired | POST | 409, 次数用尽 |
| VM6-2-S4 | 已退款核销 | revoked | POST | 409, 已退款不可核销 |

---

### VM6-3: 次数耗尽-remaining=1→execute→expired

**前置条件**:
- entitlement.status=active
- times_total=3, times_used=2 (remaining=1)

**API**: `POST /shop/redemptions/execute`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- times_used: 2 → 3
- entitlement.status: active → expired
- entitlement.expired_at 不为空
- 核销记录创建

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-3-B1 | remaining=1核销 | active(1次) | POST | 200 | →expired |
| VM6-3-B2 | remaining=2核销 | active(2次) | POST | 200 | 保持active |
| VM6-3-B3 | remaining=0核销 | expired | POST | 409 | 次数用尽 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-3-S1 | 最后一次核销 | remaining=1 | POST | 200, →expired |
| VM6-3-S2 | 非最后一次核销 | remaining=2 | POST | 200, 保持active |
| VM6-3-S3 | 已耗尽再核销 | expired | POST | 409, 次数用尽 |

---

### VM6-4: revoked不可核销-409

**前置条件**:
- entitlement.status=revoked (已退款)

**API**: `POST /shop/redemptions/execute`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_revoked_001",
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: entitlement_revoked
- 错误信息: 权益已退款, 不可核销
- 不修改 times_used
- 不创建核销记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-4-B1 | revoked核销 | revoked | POST | 409 | 已退款不可核销 |
| VM6-4-B2 | expired核销 | expired | POST | 409 | 次数用尽 |
| VM6-4-B3 | pending核销 | pending | POST | 409 | 未激活不可核销 |
| VM6-4-B4 | active核销 | active | POST | 200 | 正常核销 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-4-S1 | 已退款核销 | revoked | POST | 409, entitlement_revoked |
| VM6-4-S2 | 已过期核销 | expired | POST | 409, 次数用尽 |
| VM6-4-S3 | 未激活核销 | pending | POST | 409, 未激活 |

---

### VM6-5: 预约创建

**前置条件**:
- entitlement.status=active, remaining>0
- shop_service_slots 存在 status=open 的时段
- 商品为预约制 (booking_type=appointment)

**API**: `POST /shop/bookings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "slot_id": "slot_001",
  "buyer_phone": "13900000099",
  "buyer_name": "测试买家"
}
```

**期望结果**:
- HTTP Status: 201
- 创建 shop_bookings 记录, status=booked
- booking 包含 booking_no, slot_id, entitlement_id
- slot 占用人数 +1
- 若 slot 达到容量: slot.status → full

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-5-B1 | slot_id | "" | 空值 | 422 | 时段ID不能为空 |
| VM6-5-B2 | slot_id | "not_exist" | 不存在 | 404 | 时段不存在 |
| VM6-5-B3 | entitlement_id | "" | 空值 | 422 | 权益ID不能为空 |
| VM6-5-B4 | buyer_phone | "123" | 格式错误 | 422 | 手机号格式不合法 |
| VM6-5-B5 | slot_id | full_slot | 已满 | 409 | 时段已满 |
| VM6-5-B6 | slot_id | closed_slot | 已关闭 | 409 | 时段已关闭 |
| VM6-5-B7 | entitlement_id | revoked_ent | 已退款 | 409 | 权益已退款 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-5-S1 | 正常预约 | slot=open | POST | 201, booked |
| VM6-5-S2 | 满时段预约 | slot=full | POST | 409, 时段已满 |
| VM6-5-S3 | 关闭时段预约 | slot=closed | POST | 409, 时段已关闭 |
| VM6-5-S4 | 重复预约同一时段 | 已预约 | POST | 409, 重复预约 |

---

### VM6-6: 预约取消

**前置条件**:
- VM6-5 已执行, booking.status=booked
- 当前时间 < slot.start_at - 2小时 (Phase1默认提前量)

**API**: `POST /shop/bookings/{booking_id}/cancel`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "cancel_reason": "买家取消预约"
}
```

**期望结果**:
- HTTP Status: 200
- booking.status: booked → cancelled
- slot 占用人数 -1
- 若 slot 之前为 full: slot.status → open
- entitlement.times_used 不回退 (取消不退还次数)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-6-B1 | booking_id | not_exist | 不存在 | 404 | 预约不存在 |
| VM6-6-B2 | booking_id | cancelled_booking | 已取消 | 409 | 重复取消 |
| VM6-6-B3 | booking_id | completed_booking | 已完成 | 409 | 已完成不可取消 |
| VM6-6-B4 | cancel_reason | "" | 空值 | 422 | 取消理由不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-6-S1 | 正常取消(提前>2h) | booked, 时间充足 | POST cancel | 200, →cancelled |
| VM6-6-S2 | 取消已取消 | cancelled | POST cancel | 409, 重复取消 |
| VM6-6-S3 | 取消已完成 | completed | POST cancel | 409, 不可取消 |

---

### VM6-7: 过期未核销

**前置条件**:
- VM6-5 已执行, booking.status=booked
- 预约模式: 当前时间 > slot.end_at + 15min
- 或 次数卡模式: 领码后超过48h

**API**: `POST /shop/bookings/{booking_id}/expire (系统自动)`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200 (或系统自动执行)
- 预约模式: slot.end_at + 15min 后 → booking.status=expired
- 次数卡模式: 领码后48h → entitlement保持但码过期
- 过期后不可核销该预约
- slot 占用人数 -1 (预约模式)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-7-B1 | 预约模式过期 | slot.end+15min | 自动过期 | 200 | →expired |
| VM6-7-B2 | 次数卡过期 | 领码48h后 | 自动过期 | 200 | 码过期 |
| VM6-7-B3 | 未过期执行 | slot.end+10min | 未过期 | 200 | 保持booked |
| VM6-7-B4 | 边界: slot.end+15min01s | 刚好过期 | 自动过期 | 200 | →expired |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-7-S1 | 预约过期 | slot.end+15min | 系统自动 | 200, →expired |
| VM6-7-S2 | 次数卡过期 | 领码48h后 | 系统自动 | 200, 码过期 |
| VM6-7-S3 | 未过期保持 | slot.end+10min | 系统检查 | 200, 保持booked |

---

### VM6-8: 时段状态管理

**前置条件**:
- 商家已创建服务时段
- shop_service_slots 存在多条记录

**API**: `GET /shop/service-slots?date={date}`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 返回指定日期的所有时段
- 每条时段包含: slot_id, start_at, end_at, capacity, booked_count, status
- status 枚举: open / full / closed
- open: booked_count < capacity
- full: booked_count == capacity
- closed: 商家手动关闭

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-8-B1 | date | "" | 空值 | 422 | 日期不能为空 |
| VM6-8-B2 | date | "invalid" | 格式错误 | 422 | 日期格式不合法 |
| VM6-8-B3 | date | "2026-08-12" | 正常 | 200 | 返回时段列表 |
| VM6-8-B4 | date | "2025-01-01" | 过去日期 | 200 | 返回空或历史数据 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-8-S1 | 查询开放时段 | slot=open | GET | 200, status=open |
| VM6-8-S2 | 查询满时段 | slot=full | GET | 200, status=full |
| VM6-8-S3 | 查询关闭时段 | slot=closed | GET | 200, status=closed |
| VM6-8-S4 | 查询无时段日期 | 无时段 | GET | 200, 空列表 |

---

### VM6-9: 发票申请

**前置条件**:
- VM3-7 已执行, order.status=paid
- entitlement.status=active (未退款)
- 买家token 已获取

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "company",
  "title": "广州测试科技有限公司",
  "tax_no": "91440101MA5XXXXXX",
  "email": "test@example.com"
}
```

**期望结果**:
- HTTP Status: 201
- 创建 shop_invoice_requests 记录, status=submitted
- amount_cents = 订单买家实付 (不含平台抽成), 服务端只读生成
- 响应包含 invoice_request_id, status=submitted
- 忽略客户端传入的 amount_cents (服务端计算)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-9-B1 | title_type | "invalid" | 非枚举 | 422 | 抬头类型必须为company/personal |
| VM6-9-B2 | title_type | "" | 空值 | 422 | 抬头类型不能为空 |
| VM6-9-B3 | title | "" | 空值 | 422 | 抬头不能为空 |
| VM6-9-B4 | title | "ab" | 长度<3 | 422 | 抬头至少3字符 |
| VM6-9-B5 | tax_no | "" | 空值(company) | 422 | 企业抬头税号不能为空 |
| VM6-9-B6 | tax_no | "invalid" | 格式错误 | 422 | 税号格式不合法 |
| VM6-9-B7 | email | "" | 空值 | 422 | 邮箱不能为空 |
| VM6-9-B8 | email | "not_email" | 格式错误 | 422 | 邮箱格式不合法 |
| VM6-9-B9 | order_id | "" | 空值 | 422 | 订单ID不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-9-S1 | 企业抬头申请 | paid | POST company | 201, submitted |
| VM6-9-S2 | 个人抬头申请 | paid | POST personal | 201, submitted |
| VM6-9-S3 | 已退款申请 | refunded | POST | 409, 已退款不可申请 |
| VM6-9-S4 | 重复申请 | 已submitted | POST | 409, 重复申请 |

---

### VM6-10: 发票开具

**前置条件**:
- VM6-9 已执行, invoice.status=submitted
- merchant_token 已获取

**API**: `POST /shop/invoices/{invoice_id}/issue`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "invoice_url": "https://example.com/invoice/001.pdf",
  "invoice_no": "INV20260812001"
}
```

**期望结果**:
- HTTP Status: 200
- invoice.status: submitted → issued
- invoice.invoice_url 保存
- invoice.invoice_no 保存
- invoice.issued_at 不为空

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-10-B1 | invoice_id | not_exist | 不存在 | 404 | 发票申请不存在 |
| VM6-10-B2 | invoice_id | issued_invoice | 已开具 | 409 | 重复开具 |
| VM6-10-B3 | invoice_id | rejected_invoice | 已驳回 | 409 | 已驳回不可开具 |
| VM6-10-B4 | invoice_url | "" | 空值 | 422 | 发票URL不能为空 |
| VM6-10-B5 | invoice_no | "" | 空值 | 422 | 发票号不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-10-S1 | 正常开具 | submitted | POST issue | 200, →issued |
| VM6-10-S2 | 重复开具 | issued | POST issue | 409, 已开具 |
| VM6-10-S3 | 驳回后开具 | rejected | POST issue | 409, 已驳回 |

---

### VM6-11: 发票驳回

**前置条件**:
- VM6-9 已执行, invoice.status=submitted
- merchant_token 已获取

**API**: `POST /shop/invoices/{invoice_id}/reject`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reject_reason": "税号信息有误, 请核实后重新申请"
}
```

**期望结果**:
- HTTP Status: 200
- invoice.status: submitted → rejected
- invoice.reject_reason 保存
- invoice.rejected_at 不为空
- 买家可重新申请发票

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-11-B1 | invoice_id | not_exist | 不存在 | 404 | 发票申请不存在 |
| VM6-11-B2 | invoice_id | issued_invoice | 已开具 | 409 | 已开具不可驳回 |
| VM6-11-B3 | invoice_id | rejected_invoice | 已驳回 | 409 | 重复驳回 |
| VM6-11-B4 | reject_reason | "" | 空值 | 422 | 驳回理由不能为空 |
| VM6-11-B5 | reject_reason | "ab" | 长度<4 | 422 | 驳回理由至少4字符 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-11-S1 | 正常驳回 | submitted | POST reject | 200, →rejected |
| VM6-11-S2 | 已开具驳回 | issued | POST reject | 409, 不可驳回 |
| VM6-11-S3 | 驳回后重新申请 | rejected | POST invoice | 201, 新申请 |

---

### VM6-12: 已开票退款-needs_red_flush

**前置条件**:
- VM6-10 已执行, invoice.status=issued
- VM3-11 已执行退款, order.status=refunded

**API**: `GET /shop/invoices/{invoice_id}`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- invoice.status 仍为 issued (Phase1不自动红冲)
- invoice.needs_red_flush = true
- Phase1人工红冲 (不自动更改状态)
- needs_red_flush 标记提示商家需人工处理

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-12-B1 | 已开票退款 | issued+refunded | GET | 200 | needs_red_flush=true |
| VM6-12-B2 | 未开票退款 | 无invoice | GET | 404 | 无发票记录 |
| VM6-12-B3 | 已开票未退款 | issued+paid | GET | 200 | needs_red_flush=false |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-12-S1 | 已开票退款红冲 | issued+refunded | GET | 200, needs_red_flush=true |
| VM6-12-S2 | 已开票未退款 | issued+paid | GET | 200, needs_red_flush=false |
| VM6-12-S3 | 未开票退款 | 无invoice+refunded | GET | 404, 无发票 |

---

### VM6-13: 核销查询-码无效

**前置条件**:
- 使用无效/不存在的核销码查询

**API**: `POST /shop/redemptions/lookup`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "phone": "13900000999"
}
```

**期望结果**:
- HTTP Status: 200
- 返回空列表 (无有效权益)
- 核销结果: 码无效

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-13-B1 | phone | 未购买手机号 | 无权益 | 200 | 空列表 |
| VM6-13-B2 | phone | 他店购买手机号 | 他店权益 | 200 | 空列表(本店无) |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-13-S1 | 无购买记录查询 | 无权益 | POST | 200, 空列表 |
| VM6-13-S2 | 他店权益查询 | 他店购买 | POST | 200, 空列表 |

---

### VM6-14: 核销查询-已核销

**前置条件**:
- entitlement.status=expired (次数已用完)

**API**: `POST /shop/redemptions/lookup`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 不返回已耗尽的权益 (或返回但标注已核销)
- 核销结果: 已核销

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-14-B1 | expired权益 | times_used=total | 已核销 | 200 | 不返回或标注 |
| VM6-14-B2 | active权益 | remaining>0 | 可核销 | 200 | 正常返回 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-14-S1 | 已核销查询 | expired | POST | 200, 不返回或标注已核销 |
| VM6-14-S2 | 可核销查询 | active | POST | 200, 正常返回 |

---

### VM6-15: 核销查询-已退款

**前置条件**:
- entitlement.status=revoked (已退款)

**API**: `POST /shop/redemptions/lookup`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 不返回已退款的权益
- 核销结果: 已退款

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-15-B1 | revoked权益 | 已退款 | 查询 | 200 | 不返回 |
| VM6-15-B2 | active权益 | 正常 | 查询 | 200 | 正常返回 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-15-S1 | 已退款查询 | revoked | POST | 200, 不返回 |
| VM6-15-S2 | 正常查询 | active | POST | 200, 正常返回 |

---

### VM6-16: 核销查询-次数用尽

**前置条件**:
- entitlement.status=expired, times_used=times_total

**API**: `POST /shop/redemptions/lookup`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 不返回次数用尽的权益
- 核销结果: 次数用尽

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-16-B1 | 次数用尽 | expired | 查询 | 200 | 不返回 |
| VM6-16-B2 | 有剩余次数 | active | 查询 | 200 | 正常返回 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-16-S1 | 次数用尽查询 | expired | POST | 200, 不返回 |
| VM6-16-S2 | 有剩余查询 | active | POST | 200, 正常返回 |

---

### VM6-17: 核销执行-merchant.status不影响已购履约

**前置条件**:
- merchant.status=suspended
- entitlement.status=active (已购)

**API**: `POST /shop/redemptions/execute`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 核销成功 (merchant.status不影响已购履约)
- times_used += 1
- 核销记录创建

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-17-B1 | suspended商家核销 | merchant=suspended | POST | 200 | 核销成功 |
| VM6-17-B2 | closed商家核销 | merchant=closed | POST | 200 | 核销成功(已购履约) |
| VM6-17-B3 | active商家核销 | merchant=active | POST | 200 | 核销成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-17-S1 | 暂停商家核销 | suspended+active | POST | 200, 核销成功 |
| VM6-17-S2 | 关闭商家核销 | closed+active | POST | 200, 核销成功 |
| VM6-17-S3 | 正常商家核销 | active+active | POST | 200, 核销成功 |

---

### VM6-18: 核销执行-Phase1不支持撤销

**前置条件**:
- VM6-2 已执行核销, times_used已增加

**API**: `POST /shop/redemptions/{redemption_id}/revoke`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 404 (或 405)
- Phase1不支持撤销核销
- times_used 不回退
- 核销记录不删除

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-18-B1 | 撤销核销 | 已核销 | POST revoke | 404 | 不支持撤销 |
| VM6-18-B2 | 撤销最后核销 | expired | POST revoke | 404 | 不支持撤销 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-18-S1 | 尝试撤销核销 | 已核销 | POST revoke | 404, 不支持 |
| VM6-18-S2 | 核销后times_used不回退 | 已核销 | GET entitlement | 200, times_used不变 |

---

### VM6-19: 核销→预约完成 (booked→execute→completed)

**前置条件**:
- VM6-5 已执行, booking.status=booked
- entitlement.status=active, remaining>0

**API**: `POST /shop/redemptions/execute`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "phone": "13900000099",
  "booking_id": "booking_001"
}
```

**期望结果**:
- HTTP Status: 200
- 核销成功, times_used += 1
- booking.status: booked → completed
- booking.completed_at 不为空
- 核销关联预约记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-19-B1 | 预约核销 | booked | POST execute+booking_id | 200 | →completed |
| VM6-19-B2 | 无预约核销 | active(无booking) | POST execute | 200 | 正常核销 |
| VM6-19-B3 | 已取消预约核销 | cancelled | POST execute+booking_id | 409 | 预约已取消 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-19-S1 | 预约核销完成 | booked | POST | 200, booking→completed |
| VM6-19-S2 | 无预约直接核销 | active | POST | 200, 正常核销 |
| VM6-19-S3 | 已取消预约核销 | cancelled | POST | 409, 预约已取消 |

---

### VM6-20: 预约取消提前量验证

**前置条件**:
- VM6-5 已执行, booking.status=booked
- slot.start_at = 当前时间 + 3小时
- 取消提前量: 当前时间 < slot.start_at - 2小时

**API**: `POST /shop/bookings/{booking_id}/cancel`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "cancel_reason": "买家取消预约"
}
```

**期望结果**:
- 当前时间 < slot.start_at - 2h: 允许取消, HTTP 200
- 当前时间 >= slot.start_at - 2h: 拒绝取消, HTTP 409
- 取消后 booking.status → cancelled
- 取消后 slot 占用人数 -1

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-20-B1 | 提前3h取消 | start_at-3h | 允许 | 200 | →cancelled |
| VM6-20-B2 | 提前2h取消 | start_at-2h(边界) | 允许 | 200 | →cancelled |
| VM6-20-B3 | 提前1h取消 | start_at-1h | 拒绝 | 409 | 不足提前量 |
| VM6-20-B4 | 提前30min取消 | start_at-30min | 拒绝 | 409 | 不足提前量 |
| VM6-20-B5 | 开始后取消 | start_at+10min | 拒绝 | 409 | 已开始不可取消 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-20-S1 | 充足提前量取消 | start_at-3h | POST cancel | 200, →cancelled |
| VM6-20-S2 | 边界提前量取消 | start_at-2h | POST cancel | 200, →cancelled |
| VM6-20-S3 | 不足提前量取消 | start_at-1h | POST cancel | 409, 不足提前量 |

---

### VM6-21: 预约取消-不足提前量-409

**前置条件**:
- VM6-5 已执行, booking.status=booked
- slot.start_at = 当前时间 + 1小时 (< 2小时提前量)

**API**: `POST /shop/bookings/{booking_id}/cancel`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "cancel_reason": "买家临时取消"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: cancellation_too_late
- 错误信息: 距开始不足2小时, 不可取消
- booking.status 不变 (仍为booked)
- slot 占用人数不变

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-21-B1 | 提前1h取消 | start_at-1h | 不足 | 409 | cancellation_too_late |
| VM6-21-B2 | 提前30min取消 | start_at-30min | 不足 | 409 | cancellation_too_late |
| VM6-21-B3 | 提前1h59m取消 | start_at-1h59m | 不足 | 409 | cancellation_too_late |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-21-S1 | 不足提前量取消 | start_at-1h | POST cancel | 409, cancellation_too_late |
| VM6-21-S2 | 已开始取消 | start_at+10min | POST cancel | 409, 已开始 |

---

### VM6-22: 预约-系统过期自动取消

**前置条件**:
- VM6-5 已执行, booking.status=booked
- slot.end_at 已过 + 15分钟

**API**: `系统自动执行 (定时任务)`
**Headers**: `N/A (系统自动)`

**期望结果**:
- slot.end_at + 15min 后: booking.status → expired
- slot 占用人数 -1
- entitlement.times_used 不变 (未核销不扣减)
- 过期记录包含 expired_at

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-22-B1 | 过期15min | end_at+15min | 自动过期 | 200 | →expired |
| VM6-22-B2 | 过期14min | end_at+14min | 未过期 | 200 | 保持booked |
| VM6-22-B3 | 过期16min | end_at+16min | 已过期 | 200 | →expired |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-22-S1 | 过期自动取消 | end_at+15min | 系统自动 | →expired |
| VM6-22-S2 | 未过期保持 | end_at+14min | 系统检查 | 保持booked |

---

### VM6-23: 预约-关闭时段自动取消

**前置条件**:
- VM6-5 已执行, booking.status=booked
- 商家关闭对应时段 slot.status=closed

**API**: `POST /shop/service-slots/{slot_id}/close`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- slot.status → closed
- 关联的所有 booked 预约 → cancelled
- 取消原因: slot_closed
- slot 占用人数归零

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-23-B1 | 关闭有预约时段 | booked | POST close | 200 | 预约→cancelled |
| VM6-23-B2 | 关闭无预约时段 | 无预约 | POST close | 200 | 正常关闭 |
| VM6-23-B3 | 关闭已关闭时段 | closed | POST close | 409 | 重复关闭 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-23-S1 | 关闭有预约时段 | 有booked | POST close | 200, 预约自动取消 |
| VM6-23-S2 | 关闭无预约时段 | 无预约 | POST close | 200, 正常关闭 |
| VM6-23-S3 | 重复关闭 | closed | POST close | 409, 重复关闭 |

---

### VM6-24: 时段-full不可预约

**前置条件**:
- slot.status=full (booked_count == capacity)

**API**: `POST /shop/bookings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "slot_id": "slot_full_001",
  "buyer_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: slot_full
- 不创建预约记录
- slot 占用人数不变

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-24-B1 | 满时段预约 | full | POST | 409 | slot_full |
| VM6-24-B2 | 开放时段预约 | open | POST | 201 | 预约成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-24-S1 | 满时段预约 | full | POST | 409, slot_full |
| VM6-24-S2 | 开放时段预约 | open | POST | 201, booked |

---

### VM6-25: 时段-closed不可预约

**前置条件**:
- slot.status=closed

**API**: `POST /shop/bookings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "slot_id": "slot_closed_001",
  "buyer_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: slot_closed
- 不创建预约记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-25-B1 | 关闭时段预约 | closed | POST | 409 | slot_closed |
| VM6-25-B2 | 开放时段预约 | open | POST | 201 | 预约成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-25-S1 | 关闭时段预约 | closed | POST | 409, slot_closed |
| VM6-25-S2 | 开放时段预约 | open | POST | 201, booked |

---

### VM6-26: 发票-个人抬头

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "personal",
  "title": "张三",
  "email": "zhangsan@example.com"
}
```

**期望结果**:
- HTTP Status: 201
- title_type=personal
- 个人抬头不需要 tax_no (可选)
- amount_cents 服务端只读生成
- invoice.status=submitted

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-26-B1 | title_type | "personal" | 个人 | 201 | 无需税号 |
| VM6-26-B2 | title | "" | 空值 | 422 | 抬头不能为空 |
| VM6-26-B3 | title | "张" | 长度1 | 422 | 抬头至少2字符(个人) |
| VM6-26-B4 | email | "" | 空值 | 422 | 邮箱不能为空 |
| VM6-26-B5 | email | "invalid" | 格式错误 | 422 | 邮箱格式不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-26-S1 | 个人抬头申请 | paid | POST personal | 201, submitted |
| VM6-26-S2 | 个人无税号 | paid | POST personal(无tax_no) | 201, 成功 |
| VM6-26-S3 | 个人抬头开具 | submitted | POST issue | 200, →issued |

---

### VM6-27: 发票-企业抬头

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "company",
  "title": "广州测试科技有限公司",
  "tax_no": "91440101MA5XXXXXX",
  "email": "finance@test.com"
}
```

**期望结果**:
- HTTP Status: 201
- title_type=company
- 企业抬头必须包含 tax_no
- tax_no 格式: 18位统一社会信用代码
- amount_cents 服务端只读生成

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-27-B1 | tax_no | "91440101MA5XXXXXX" | 正常18位 | 201 | 成功 |
| VM6-27-B2 | tax_no | "" | 空值 | 422 | 企业抬头税号不能为空 |
| VM6-27-B3 | tax_no | "12345" | 过短 | 422 | 税号格式不合法 |
| VM6-27-B4 | tax_no | "91440101MA5XXXXXX12" | 过长20位 | 422 | 税号格式不合法 |
| VM6-27-B5 | title | "" | 空值 | 422 | 抬头不能为空 |
| VM6-27-B6 | title | "ab" | 过短 | 422 | 抬头至少3字符(企业) |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-27-S1 | 企业抬头申请 | paid | POST company | 201, submitted |
| VM6-27-S2 | 企业无税号 | paid | POST company(无tax_no) | 422, 税号必填 |
| VM6-27-S3 | 企业抬头开具 | submitted | POST issue | 200, →issued |

---

### VM6-28: 发票-税号格式校验

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "company",
  "title": "广州测试科技有限公司",
  "tax_no": "91440101MA5XXXXXX",
  "email": "finance@test.com"
}
```

**期望结果**:
- 税号格式: 18位统一社会信用代码 (数字+大写字母)
- 合法: HTTP 201
- 非法: HTTP 422
- 个人抬头: tax_no 可选, 不校验格式

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-28-B1 | tax_no | "91440101MA5XXXXXX" | 正常18位 | 201 | 格式正确 |
| VM6-28-B2 | tax_no | "91440101ma5xxxxxx" | 小写字母 | 422 | 必须大写 |
| VM6-28-B3 | tax_no | "91440101MA5XXXXX" | 17位(不足) | 422 | 长度不足 |
| VM6-28-B4 | tax_no | "91440101MA5XXXXXXX" | 19位(超长) | 422 | 长度超长 |
| VM6-28-B5 | tax_no | "91440101-A5XXXXXX" | 含特殊字符 | 422 | 格式不合法 |
| VM6-28-B6 | tax_no | " 91440101MA5XX  " | 含空格 | 422 | 含空格 |
| VM6-28-B7 | tax_no | (空, personal) | 个人不传 | 201 | 个人可选 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-28-S1 | 合法税号 | 18位正确 | POST | 201, 成功 |
| VM6-28-S2 | 小写税号 | 小写 | POST | 422, 必须大写 |
| VM6-28-S3 | 个人无税号 | personal | POST | 201, 成功 |

---

### VM6-29: 发票-邮箱格式校验

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "personal",
  "title": "张三",
  "email": "zhangsan@example.com"
}
```

**期望结果**:
- 邮箱必须为有效格式: xxx@xxx.xxx
- 合法: HTTP 201
- 非法: HTTP 422

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-29-B1 | email | "test@example.com" | 正常 | 201 | 格式正确 |
| VM6-29-B2 | email | "not_email" | 无@ | 422 | 格式不合法 |
| VM6-29-B3 | email | "test@" | 无域名 | 422 | 格式不合法 |
| VM6-29-B4 | email | "@example.com" | 无用户名 | 422 | 格式不合法 |
| VM6-29-B5 | email | "" | 空值 | 422 | 邮箱不能为空 |
| VM6-29-B6 | email | "test@.com" | 无域名名 | 422 | 格式不合法 |
| VM6-29-B7 | email | "test@example" | 无TLD | 422 | 格式不合法 |
| VM6-29-B8 | email | null | null | 422 | 邮箱不能为null |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-29-S1 | 合法邮箱 | 正常格式 | POST | 201, 成功 |
| VM6-29-S2 | 无@邮箱 | not_email | POST | 422, 格式不合法 |
| VM6-29-S3 | 空邮箱 | "" | POST | 422, 不能为空 |

---

### VM6-30: 发票-amount_cents服务端只读

**前置条件**:
- VM3-7 已执行, order.amount_cents=9900

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "personal",
  "title": "张三",
  "email": "zhangsan@example.com",
  "amount_cents": 1
}
```

**期望结果**:
- HTTP Status: 201
- invoice.amount_cents = 订单买家实付 (9900), 非客户端传的1
- amount_cents 不含平台抽成
- 服务端只读生成, 忽略客户端传入值

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-30-B1 | amount_cents | 1(客户端传) | 篡改 | 201 | 服务端覆盖为9900 |
| VM6-30-B2 | amount_cents | 0(客户端传) | 篡改 | 201 | 服务端覆盖为9900 |
| VM6-30-B3 | amount_cents | 999999(客户端传) | 篡改 | 201 | 服务端覆盖为9900 |
| VM6-30-B4 | amount_cents | (不传) | 不传 | 201 | 服务端生成9900 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-30-S1 | 客户端传1 | 篡改 | POST | 201, 服务端9900 |
| VM6-30-S2 | 客户端传0 | 篡改 | POST | 201, 服务端9900 |
| VM6-30-S3 | 不传amount | 不传 | POST | 201, 服务端9900 |

---

### VM6-31: 发票-refunded不可申请-409

**前置条件**:
- VM3-11 已执行退款, order.status=refunded

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_refunded_001",
  "title_type": "personal",
  "title": "张三",
  "email": "zhangsan@example.com"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: order_refunded
- 错误信息: 已退款订单不可申请发票
- 不创建发票记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-31-B1 | refunded申请 | refunded | POST | 409 | order_refunded |
| VM6-31-B2 | paid申请 | paid | POST | 201 | 正常申请 |
| VM6-31-B3 | pending申请 | pending_payment | POST | 409 | 未支付不可申请 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-31-S1 | 已退款申请发票 | refunded | POST | 409, order_refunded |
| VM6-31-S2 | 已支付申请发票 | paid | POST | 201, 成功 |
| VM6-31-S3 | 未支付申请发票 | pending | POST | 409, 未支付 |

---

### VM6-32: 发票-已开票重复申请

**前置条件**:
- VM6-9 已执行, invoice.status=submitted
- 同一order_id

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "personal",
  "title": "李四",
  "email": "lisi@example.com"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: invoice_already_requested
- 错误信息: 该订单已有发票申请
- 不创建新发票记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-32-B1 | submitted重复申请 | submitted | POST | 409 | 已有申请 |
| VM6-32-B2 | issued重复申请 | issued | POST | 409 | 已开具 |
| VM6-32-B3 | rejected重新申请 | rejected | POST | 201 | 允许重新申请 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-32-S1 | 已申请重复 | submitted | POST | 409, 重复申请 |
| VM6-32-S2 | 已开具重复 | issued | POST | 409, 已开具 |
| VM6-32-S3 | 驳回后重新申请 | rejected | POST | 201, 允许 |

---

### VM6-33: 发票状态机-submitted→issued

**前置条件**:
- VM6-9 已执行, invoice.status=submitted

**API**: `POST /shop/invoices/{invoice_id}/issue`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "invoice_url": "https://example.com/invoice/001.pdf",
  "invoice_no": "INV20260812001"
}
```

**期望结果**:
- HTTP Status: 200
- invoice.status: submitted → issued
- issued_at 不为空
- invoice_url, invoice_no 保存

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-33-B1 | submitted→issued | submitted | POST issue | 200 | →issued |
| VM6-33-B2 | issued→issued | issued | POST issue | 409 | 重复开具 |
| VM6-33-B3 | rejected→issued | rejected | POST issue | 409 | 已驳回 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-33-S1 | 正常开具 | submitted | POST issue | 200, →issued |
| VM6-33-S2 | 重复开具 | issued | POST issue | 409, 已开具 |
| VM6-33-S3 | 驳回后开具 | rejected | POST issue | 409, 已驳回 |

---

### VM6-34: 发票状态机-submitted→rejected

**前置条件**:
- VM6-9 已执行, invoice.status=submitted

**API**: `POST /shop/invoices/{invoice_id}/reject`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "reject_reason": "抬头信息有误, 请核实后重新申请"
}
```

**期望结果**:
- HTTP Status: 200
- invoice.status: submitted → rejected
- rejected_at 不为空
- reject_reason 保存
- 买家可重新申请

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-34-B1 | submitted→rejected | submitted | POST reject | 200 | →rejected |
| VM6-34-B2 | issued→rejected | issued | POST reject | 409 | 已开具不可驳回 |
| VM6-34-B3 | rejected→rejected | rejected | POST reject | 409 | 重复驳回 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-34-S1 | 正常驳回 | submitted | POST reject | 200, →rejected |
| VM6-34-S2 | 已开具驳回 | issued | POST reject | 409, 不可驳回 |
| VM6-34-S3 | 驳回后重新申请 | rejected | POST invoice | 201, 新申请 |

---

### VM6-35: 核销-次数卡模式(48h过期)

**前置条件**:
- 商品为次数卡模式 (booking_type=times_card)
- entitlement.status=active
- 领码后未核销, 超过48h

**API**: `POST /shop/redemptions/execute (验证码过期)`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_card_001",
  "phone": "13900000099"
}
```

**期望结果**:
- 领码后48h内: 正常核销
- 领码后超过48h: 核销码过期
- 过期后: entitlement保持active但该码不可用
- 需重新领码

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-35-B1 | 领码47h核销 | <48h | 有效 | 200 | 核销成功 |
| VM6-35-B2 | 领码48h核销 | =48h(边界) | 有效 | 200 | 核销成功 |
| VM6-35-B3 | 领码49h核销 | >48h | 过期 | 409 | 码已过期 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-35-S1 | 48h内核销 | 领码47h | POST execute | 200, 成功 |
| VM6-35-S2 | 48h边界核销 | 领码48h | POST execute | 200, 成功 |
| VM6-35-S3 | 48h后核销 | 领码49h | POST execute | 409, 码过期 |

---

### VM6-36: 核销-预约模式(15min过期)

**前置条件**:
- 商品为预约模式 (booking_type=appointment)
- booking.status=booked
- slot.end_at + 15min已过

**API**: `POST /shop/redemptions/execute (验证预约过期)`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_appt_001",
  "phone": "13900000099",
  "booking_id": "booking_001"
}
```

**期望结果**:
- slot.end_at + 15min内: 正常核销
- slot.end_at + 15min后: 预约过期, 不可核销该预约
- 过期后 booking.status → expired
- entitlement.times_used 不扣减 (未核销)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-36-B1 | end_at+14min核销 | <15min | 有效 | 200 | 核销成功 |
| VM6-36-B2 | end_at+15min核销 | =15min(边界) | 有效 | 200 | 核销成功 |
| VM6-36-B3 | end_at+16min核销 | >15min | 过期 | 409 | 预约过期 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-36-S1 | 15min内核销 | end+14min | POST execute | 200, 成功 |
| VM6-36-S2 | 15min边界核销 | end+15min | POST execute | 200, 成功 |
| VM6-36-S3 | 15min后核销 | end+16min | POST execute | 409, 过期 |

---

### VM6-37: 核销查询-多权益返回

**前置条件**:
- 买家购买了多个商品, 有多个有效权益

**API**: `POST /shop/redemptions/lookup`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- 返回多个权益记录
- 每条包含 product_name, remaining, status
- 按购买时间或剩余次数排序

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-37-B1 | 3个有效权益 | 多权益 | 查询 | 200 | 返回3条 |
| VM6-37-B2 | 1个有效权益 | 单权益 | 查询 | 200 | 返回1条 |
| VM6-37-B3 | 0个有效权益 | 无权益 | 查询 | 200 | 空列表 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-37-S1 | 多权益查询 | 3个active | POST | 200, 3条记录 |
| VM6-37-S2 | 单权益查询 | 1个active | POST | 200, 1条记录 |
| VM6-37-S3 | 无权益查询 | 0个active | POST | 200, 空列表 |

---

### VM6-38: 发票-企业抬头税号为空

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "company",
  "title": "广州测试科技有限公司",
  "tax_no": "",
  "email": "finance@test.com"
}
```

**期望结果**:
- HTTP Status: 422
- 错误码: tax_no_required
- 错误信息: 企业抬头必须提供税号
- 不创建发票记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-38-B1 | tax_no | "" | 空值 | 422 | 企业税号必填 |
| VM6-38-B2 | tax_no | null | null | 422 | 企业税号必填 |
| VM6-38-B3 | tax_no | "  " | 空格 | 422 | 企业税号必填 |
| VM6-38-B4 | title_type | "personal"(无tax_no) | 个人无税号 | 201 | 个人可选 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-38-S1 | 企业空税号 | company+empty | POST | 422, tax_no_required |
| VM6-38-S2 | 个人无税号 | personal+no_tax | POST | 201, 成功 |
| VM6-38-S3 | 企业有税号 | company+tax | POST | 201, 成功 |

---

### VM6-39: 预约-买家自助取消

**前置条件**:
- VM6-5 已执行, booking.status=booked
- 当前时间 < slot.start_at - 2小时
- buyer_token 已获取

**API**: `POST /mp/bookings/{booking_id}/cancel`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "cancel_reason": "个人原因需要取消"
}
```

**期望结果**:
- HTTP Status: 200
- booking.status: booked → cancelled
- cancel_by = buyer (买家自助取消)
- slot 占用人数 -1

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-39-B1 | 买家取消(提前>2h) | 充足 | POST cancel | 200 | →cancelled |
| VM6-39-B2 | 买家取消(提前<2h) | 不足 | POST cancel | 409 | cancellation_too_late |
| VM6-39-B3 | 非本人取消 | 他买家token | POST cancel | 403 | 无权取消 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-39-S1 | 买家自助取消 | booked, 提前>2h | POST cancel | 200, →cancelled |
| VM6-39-S2 | 不足提前量 | booked, 提前<2h | POST cancel | 409, too_late |
| VM6-39-S3 | 非本人取消 | 他买家 | POST cancel | 403, 无权 |

---

### VM6-40: 时段-open可预约

**前置条件**:
- slot.status=open
- booked_count < capacity

**API**: `POST /shop/bookings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "slot_id": "slot_open_001",
  "buyer_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 201
- booking.status=booked
- slot.booked_count += 1
- 若达到capacity: slot.status → full

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-40-B1 | open预约 | open | POST | 201 | booked |
| VM6-40-B2 | open达满 | open(last_spot) | POST | 201 | slot→full |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-40-S1 | 开放时段预约 | open | POST | 201, booked |
| VM6-40-S2 | 最后一个名额 | open(last) | POST | 201, slot→full |

---

### VM6-41: 发票-title为空-422

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "personal",
  "title": "",
  "email": "test@example.com"
}
```

**期望结果**:
- HTTP Status: 422
- 错误码: title_required
- 错误信息: 发票抬头不能为空

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-41-B1 | title | "" | 空值 | 422 | 抬头不能为空 |
| VM6-41-B2 | title | null | null | 422 | 抬头不能为空 |
| VM6-41-B3 | title | "  " | 空格 | 422 | 抬头不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-41-S1 | 空抬头 | "" | POST | 422, title_required |
| VM6-41-S2 | 有抬头 | 张三 | POST | 201, 成功 |

---

### VM6-42: 发票-email为空-422

**前置条件**:
- VM3-7 已执行, order.status=paid

**API**: `POST /shop/invoices`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "order_id": "order_001",
  "title_type": "personal",
  "title": "张三",
  "email": ""
}
```

**期望结果**:
- HTTP Status: 422
- 错误码: email_required
- 错误信息: 接收邮箱不能为空

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-42-B1 | email | "" | 空值 | 422 | 邮箱不能为空 |
| VM6-42-B2 | email | null | null | 422 | 邮箱不能为空 |
| VM6-42-B3 | email | "  " | 空格 | 422 | 邮箱不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-42-S1 | 空邮箱 | "" | POST | 422, email_required |
| VM6-42-S2 | 有邮箱 | test@test.com | POST | 201, 成功 |

---

### VM6-43: 核销执行-times_used更新

**前置条件**:
- entitlement.status=active
- times_total=5, times_used=2

**API**: `POST /shop/redemptions/execute`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_001",
  "phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 200
- times_used: 2 → 3
- remaining: 3 → 2
- 核销记录创建, 包含 times_used_before=2, times_used_after=3
- entitlement.status 保持 active (remaining>0)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-43-B1 | 核销前times_used | 2 | 验证 | 200 | 核销前=2 |
| VM6-43-B2 | 核销后times_used | 3 | 验证 | 200 | 核销后=3 |
| VM6-43-B3 | remaining更新 | 2→2 | 验证 | 200 | remaining=2 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-43-S1 | 核销更新次数 | used=2 | POST execute | 200, used=3 |
| VM6-43-S2 | 核销记录验证 | 核销后 | GET redemption | 200, 记录存在 |
| VM6-43-S3 | remaining验证 | 核销后 | GET entitlement | 200, remaining=2 |

---

### VM6-44: 发票开具-url生成

**前置条件**:
- VM6-9 已执行, invoice.status=submitted

**API**: `POST /shop/invoices/{invoice_id}/issue`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "invoice_url": "https://example.com/invoice/001.pdf",
  "invoice_no": "INV20260812001"
}
```

**期望结果**:
- HTTP Status: 200
- invoice.invoice_url 保存且可访问
- invoice.invoice_no 格式正确
- 买家可通过 GET /shop/invoices/{id} 获取url

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-44-B1 | invoice_url | "https://..." | 正常URL | 200 | 保存成功 |
| VM6-44-B2 | invoice_url | "not_url" | 非URL | 422 | URL格式不合法 |
| VM6-44-B3 | invoice_url | "" | 空值 | 422 | URL不能为空 |
| VM6-44-B4 | invoice_no | "" | 空值 | 422 | 发票号不能为空 |
| VM6-44-B5 | invoice_no | "INV20260812001" | 正常 | 200 | 保存成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-44-S1 | 正常开具含URL | submitted | POST issue | 200, url保存 |
| VM6-44-S2 | 买家获取URL | issued | GET invoice | 200, 含url |
| VM6-44-S3 | 非法URL开具 | submitted | POST issue(not_url) | 422, 格式错误 |

---

### VM6-45: 预约-重复预约同一时段

**前置条件**:
- VM6-5 已执行, booking.status=booked
- 同一买家, 同一时段

**API**: `POST /shop/bookings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "entitlement_id": "ent_002",
  "slot_id": "slot_001",
  "buyer_phone": "13900000099"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: duplicate_booking
- 错误信息: 该买家已预约此时段
- 不创建新预约
- slot 占用人数不变

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM6-45-B1 | 同买家同时段 | 已booked | POST | 409 | 重复预约 |
| VM6-45-B2 | 同买家不同时段 | 已booked(slot_002) | POST slot_002 | 201 | 允许 |
| VM6-45-B3 | 不同买家同时段 | 他人已booked | POST | 201 | 允许(如有余位) |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM6-45-S1 | 重复预约同时段 | 已booked | POST same slot | 409, duplicate |
| VM6-45-S2 | 不同时段预约 | 已booked | POST diff slot | 201, 允许 |
| VM6-45-S3 | 不同买家同时段 | 他人booked | POST | 201, 允许 |

---


## 三、M7 公域Mx (Mx首演验收)

> **模块说明**: 覆盖公域映射(双轴状态机)、抖店Webhook(订单/退款)、领权流程(token生命周期)、Mx验收组合、公域挂载闸、端到端闭环等全链路。
> **环境变量**: `DOUYIN_WEBHOOK_MODE=stub`
> **核心表**: shop_mx_mappings, shop_orders, entitlements, audit_logs, claim_tokens
> **双轴状态机**: listing_status (unmounted/pending/mounted/paused_sync/blocked) + external_audit_status (submitted/approved/rejected)

---

### VM7-1: 公域映射创建

**前置条件**:
- 商家已入驻 status=active
- 商品已上架 on_sale=true
- merchant_token 已获取 (13900000099/test123456)
- external_audit_status 初始为 submitted

**API**: `POST /shop/mx/mappings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "channel": "douyin",
  "external_product_id": "DY_prod_001"
}
```

**期望结果**:
- HTTP Status: 201
- 创建 shop_mx_mappings 记录
- listing_status = pending (或 mounted, 取决于审核)
- external_audit_status = submitted
- 生成 audit_log 记录
- on_sale商品: 映射成功

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-1-B1 | product_id | [空] | 空值 | 422 | 商品ID不能为空 |
| VM7-1-B2 | product_id | not_exist | 不存在 | 404 | 商品不存在 |
| VM7-1-B3 | channel | [空] | 空值 | 422 | 渠道不能为空 |
| VM7-1-B4 | channel | unknown_ch | 不支持 | 422 | 不支持的渠道 |
| VM7-1-B5 | external_product_id | [空] | 空值 | 422 | 外部商品ID不能为空 |
| VM7-1-B6 | external_product_id | [超长>128] | 超长 | 422 | 外部商品ID长度超出限制 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-1-S1 | 正常映射 | on_sale商品 | POST | 201, mapping创建 |
| VM7-1-S2 | 重复映射 | 已映射 | POST | 409, 重复映射 |
| VM7-1-S3 | off_sale映射 | off_sale商品 | POST | 409, auto_reject |
| VM7-1-S4 | suspended商家映射 | merchant=suspended | POST | 409, 商家已暂停 |

---

### VM7-2: 公域映射状态机 (listing_status流转)

**前置条件**:
- VM7-1 已执行, mapping已创建
- 了解双轴状态机: listing_status + external_audit_status

**API**: `GET /shop/mx/mappings/{mapping_id}`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 返回 listing_status (unmounted/pending/mounted/paused_sync/blocked)
- 返回 external_audit_status (submitted/approved/rejected)
- 返回 audit_log 历史
- 状态流转可追溯

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-2-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-2-B2 | mapping_id | [空] | 空值 | 422 | 映射ID不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-2-S1 | 查询pending状态 | pending | GET | 200, listing=pending |
| VM7-2-S2 | 查询mounted状态 | mounted | GET | 200, listing=mounted |
| VM7-2-S3 | 查询blocked状态 | blocked | GET | 200, listing=blocked |
| VM7-2-S4 | 查询paused状态 | paused_sync | GET | 200, listing=paused_sync |

---

### VM7-3: 抖店Webhook-订单paid

**前置条件**:
- VM7-1 已执行, 商品已映射且 listing_status=mounted
- DOUYIN_WEBHOOK_MODE=stub
- 有效HMAC-SHA256签名
- timestamp在300s内

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_order_001",
  "event_type": "order.paid",
  "external_order_no": "DY_order_001",
  "external_product_id": "DY_prod_001",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- 创建 order: status=claim_pending
- 生成 claim_token (唯一, 有expires_at)
- 发送短信 (SMS) 含领权链接
- audit_log 记录Webhook接收
- Webhook幂等: event_id唯一

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-3-B1 | event_id | [空] | 空值 | 400 | event_id不能为空 |
| VM7-3-B2 | event_type | unknown | 未知类型 | 400 | 不支持的事件类型 |
| VM7-3-B3 | external_order_no | [空] | 空值 | 400 | 外部订单号不能为空 |
| VM7-3-B4 | external_product_id | [空] | 空值 | 400 | 外部商品ID不能为空 |
| VM7-3-B5 | buyer_phone | [空] | 空值 | 400 | 买家手机号不能为空 |
| VM7-3-B6 | amount_cents | 0 | 零金额 | 400 | 金额不合法 |
| VM7-3-B7 | timestamp | 0 | 零时间戳 | 400 | 时间戳不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-3-S1 | 正常Webhook | 已映射商品 | POST | 200, claim_pending+token+sms |
| VM7-3-S2 | 重复event_id | 已处理 | POST同event_id | 200, 幂等不重复处理 |
| VM7-3-S3 | 未映射商品 | 未映射 | POST | 200, 拒单+audit_log |
| VM7-3-S4 | 商家suspended | merchant=suspended | POST | 200, 拒单merchant_status_blocked |

---

### VM7-4: Webhook幂等

**前置条件**:
- VM7-3 已执行, event_id=evt_order_001已处理
- order已创建, claim_token已生成

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_order_001",
  "event_type": "order.paid",
  "external_order_no": "DY_order_001",
  "external_product_id": "DY_prod_001",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- 不重复创建order (幂等)
- 不重复生成claim_token
- 不重复发送SMS
- 响应包含幂等标识

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-4-B1 | event_id | evt_order_001(重复) | 完全相同 | 200 | 幂等, 不重复处理 |
| VM7-4-B2 | event_id | evt_order_001(不同body) | 相同ID不同body | 200 | 幂等, 以首次为准 |
| VM7-4-B3 | event_id | evt_order_002(新) | 新事件 | 200 | 新事件, 正常处理 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-4-S1 | 首次Webhook | 未处理 | POST evt_001 | 200, 正常处理 |
| VM7-4-S2 | 重复Webhook | 已处理 | POST evt_001 | 200, 幂等不重复 |
| VM7-4-S3 | 新event_id | 已处理evt_001 | POST evt_002 | 200, 新事件处理 |

---

### VM7-5: 未映射商品Webhook-拒单

**前置条件**:
- 抖店商品未在系统映射 (无shop_mx_mappings记录)
- DOUYIN_WEBHOOK_MODE=stub

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_order_unmapped",
  "event_type": "order.paid",
  "external_order_no": "DY_order_999",
  "external_product_id": "DY_prod_unmapped",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- 不创建order (拒单)
- audit_log 记录拒单原因: product_not_mapped
- 不生成claim_token
- 不发送SMS

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-5-B1 | external_product_id | DY_prod_unmapped | 未映射 | 200 | 拒单+audit_log |
| VM7-5-B2 | external_product_id | DY_prod_removed | 已删除映射 | 200 | 拒单+audit_log |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-5-S1 | 未映射商品Webhook | 无映射 | POST | 200, 拒单+audit_log |
| VM7-5-S2 | 已删除映射Webhook | 映射已删 | POST | 200, 拒单 |
| VM7-5-S3 | 已映射商品Webhook | 有映射 | POST | 200, 正常处理 |

---

### VM7-6: 抖店退款Webhook

**前置条件**:
- VM7-3 已执行, order.status=paid (已领权)
- 或 order.status=claim_pending (未领权)
- DOUYIN_WEBHOOK_MODE=stub

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_refund_001",
  "event_type": "order.refund",
  "external_order_no": "DY_order_001",
  "refund_amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- order.status: paid/claim_pending -> refunded (公域Webhook直写)
- entitlement.status -> revoked
- enrollment.status -> revoked
- payment_logs 新增 refund 记录
- audit_log 记录退款Webhook

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-6-B1 | event_id | [空] | 空值 | 400 | event_id不能为空 |
| VM7-6-B2 | event_type | order.refund | 退款 | 200 | 正常退款 |
| VM7-6-B3 | external_order_no | not_exist | 不存在 | 200 | 拒单+audit_log |
| VM7-6-B4 | refund_amount_cents | 0 | 零金额 | 400 | 金额不合法 |
| VM7-6-B5 | refund_amount_cents | 999999 | 超额 | 400 | 退款金额超过实付 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-6-S1 | 已领权退款 | paid | POST refund | 200, ->refunded |
| VM7-6-S2 | 未领权退款 | claim_pending | POST refund | 200, ->refunded |
| VM7-6-S3 | 重复退款Webhook | 已refunded | POST同event_id | 200, 幂等 |
| VM7-6-S4 | 已退款再退款 | refunded | POST新event_id | 200, 幂等/拒绝 |

---

### VM7-7: 领权GET

**前置条件**:
- VM7-3 已执行, claim_token已生成
- token未过期, 未使用

**API**: `GET /claim/{token}`
**Headers**: `Authorization: Bearer {buyer_token} (可选)`

**期望结果**:
- HTTP Status: 200
- 返回商品信息: product_name, product_image, description
- 返回手机尾号: ****0099
- 返回claim_status: pending (未领权)
- 返回expires_at
- 不暴露完整手机号

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-7-B1 | token | invalid_token | 无效 | 404 | 领权码不存在 |
| VM7-7-B2 | token | [空] | 空值 | 404 | 领权码不存在 |
| VM7-7-B3 | token | used_token | 已使用 | 200 | 返回claimed状态 |
| VM7-7-B4 | token | expired_token | 已过期 | 410 | 领权码已过期 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-7-S1 | 正常领权页 | pending(未用) | GET | 200, 商品信息+手机尾号 |
| VM7-7-S2 | 已领权页 | claimed(已用) | GET | 200, claimed状态 |
| VM7-7-S3 | 过期领权页 | expired | GET | 410, 已过期 |
| VM7-7-S4 | 无效领权码 | 不存在 | GET | 404, 不存在 |

---

### VM7-8: 领权POST

**前置条件**:
- VM7-3 已执行, claim_token已生成
- token未过期, 未使用
- 买家提供完整手机号验证

**API**: `POST /claim/{token}`
**Headers**: `Authorization: Bearer {buyer_token} (可选)`

**请求体**:
```json
{
  "buyer_phone": "13900000099",
  "buyer_name": "测试买家"
}
```

**期望结果**:
- HTTP Status: 200
- order.status: claim_pending -> paid
- entitlement.status: pending -> active
- enrollment.status: active
- claim_token标记为已使用 (单次使用)
- payment_logs 新增 claim 记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-8-B1 | token | invalid_token | 无效 | 404 | 领权码不存在 |
| VM7-8-B2 | token | used_token | 已使用 | 409 | 领权码已使用 |
| VM7-8-B3 | token | expired_token | 已过期 | 410 | 领权码已过期 |
| VM7-8-B4 | buyer_phone | [空] | 空值 | 422 | 手机号不能为空 |
| VM7-8-B5 | buyer_phone | 123 | 格式错误 | 422 | 手机号格式不合法 |
| VM7-8-B6 | buyer_phone | 13900000999 | 不匹配尾号 | 422 | 手机号与订单不匹配 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-7-S1 | 正常领权 | claim_pending | POST | 200, ->paid+active |
| VM7-8-S2 | 重复领权 | 已paid(token已用) | POST | 409, 已使用 |
| VM7-8-S3 | 过期领权 | expired | POST | 410, 已过期 |
| VM7-8-S4 | 手机号不匹配 | pending | POST错误手机号 | 422, 不匹配 |

---

### VM7-9: token过期-410

**前置条件**:
- claim_token已生成, 但已超过expires_at
- claim_expire_days默认7天 (A15-S可改)

**API**: `GET /claim/{token}`
**Headers**: `Authorization: Bearer {buyer_token} (可选)`

**期望结果**:
- HTTP Status: 410
- 错误码: claim_token_expired
- 错误信息: 领权码已过期
- 不返回商品信息
- 不可再领权

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-9-B1 | token | expired_7d | 过期7天 | 410 | 已过期 |
| VM7-9-B2 | token | expired_8d | 过期8天 | 410 | 已过期 |
| VM7-9-B3 | token | valid_6d | 6天(未过期) | 200 | 正常返回 |
| VM7-9-B4 | token | valid_7d_exact | 7天(边界) | 200 | 最后一天有效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-9-S1 | 过期token GET | expired | GET | 410, 已过期 |
| VM7-9-S2 | 过期token POST | expired | POST | 410, 已过期 |
| VM7-9-S3 | 未过期token GET | valid | GET | 200, 正常返回 |
| VM7-9-S4 | 边界7天token | 7天(最后) | GET | 200, 有效 |

---

### VM7-10: Mx验收组合

**前置条件**:
- Phase1只验收4种组合中的1种 (默认组合1-A)
- 了解4种组合定义
- merchant_token 已获取

**API**: `POST /shop/mx/mappings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "channel": "douyin",
  "channel_combo": "1-A",
  "external_product_id": "DY_prod_001"
}
```

**期望结果**:
- 默认组合1-A: HTTP 201, 映射成功
- 未开通组合: HTTP 422, channel_combo_not_enabled
- 建单幂等: UK(channel, external_order_no)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-10-B1 | channel_combo | 1-A | 默认组合 | 201 | 映射成功 |
| VM7-10-B2 | channel_combo | 2-B | 未开通组合 | 422 | channel_combo_not_enabled |
| VM7-10-B3 | channel_combo | 3-C | 未开通组合 | 422 | channel_combo_not_enabled |
| VM7-10-B4 | channel_combo | 4-D | 未开通组合 | 422 | channel_combo_not_enabled |
| VM7-10-B5 | channel_combo | invalid | 非法组合 | 422 | 组合编码不合法 |
| VM7-10-B6 | channel_combo | [空] | 空值 | 422 | 组合不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-10-S1 | 默认组合1-A | 未映射 | POST 1-A | 201, 映射成功 |
| VM7-10-S2 | 未开通组合2-B | 未映射 | POST 2-B | 422, channel_combo_not_enabled |
| VM7-10-S3 | 建单幂等 | 已建单 | POST同external_order_no | 409, 重复建单 |

---

### VM7-11: 公域映射-off_sale商品-409

**前置条件**:
- 商品 on_sale=false (已下架)
- merchant_token 已获取

**API**: `POST /shop/mx/mappings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "product_id": "prod_offsale",
  "channel": "douyin",
  "external_product_id": "DY_prod_offsale"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: product_not_on_sale
- 自动拒绝 (auto_reject)
- audit_log 记录拒审原因
- 不创建映射记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-11-B1 | product_id | prod_offsale | 下架商品 | 409 | auto_reject |
| VM7-11-B2 | product_id | prod_onsale | 上架商品 | 201 | 映射成功 |
| VM7-11-B3 | product_id | prod_deleted | 已删除 | 404 | 商品不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-11-S1 | 下架商品映射 | on_sale=false | POST | 409, auto_reject |
| VM7-11-S2 | 上架商品映射 | on_sale=true | POST | 201, 映射成功 |
| VM7-11-S3 | 已删除商品映射 | deleted | POST | 404, 不存在 |

---

### VM7-12: 公域映射-suspended商家-409

**前置条件**:
- merchant.status=suspended
- 商品 on_sale=true

**API**: `POST /shop/mx/mappings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "channel": "douyin",
  "external_product_id": "DY_prod_001"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: merchant_suspended
- 不创建映射记录
- audit_log 记录拒审原因

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-12-B1 | merchant | suspended | 暂停 | 409 | merchant_suspended |
| VM7-12-B2 | merchant | closed | 关闭 | 409 | merchant_closed |
| VM7-12-B3 | merchant | active | 正常 | 201 | 映射成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-12-S1 | 暂停商家映射 | suspended | POST | 409, merchant_suspended |
| VM7-12-S2 | 关闭商家映射 | closed | POST | 409, merchant_closed |
| VM7-12-S3 | 正常商家映射 | active | POST | 201, 映射成功 |

---

### VM7-13: listing_status: unmounted->pending

**前置条件**:
- VM7-1 已执行, mapping已创建
- 初始 listing_status=unmounted (或直接pending)

**API**: `POST /shop/mx/mappings/{mapping_id}/submit`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- listing_status: unmounted -> pending
- external_audit_status: -> submitted
- audit_log 记录状态变更

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-13-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-13-B2 | mapping_id | already_pending | 已pending | 409 | 重复提交 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-13-S1 | 初始提交 | unmounted | POST submit | 200, ->pending |
| VM7-13-S2 | 重复提交 | pending | POST submit | 409, 重复提交 |

---

### VM7-14: listing_status: pending->mounted

**前置条件**:
- VM7-13 已执行, listing_status=pending
- external_audit_status=approved (外部审核通过)

**API**: `POST /shop/mx/mappings/{mapping_id}/mount`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- listing_status: pending -> mounted
- external_audit_status: approved
- audit_log 记录上架
- 商品在公域渠道可见

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-14-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-14-B2 | mapping_id | not_approved | 未过审 | 409 | 未过审不可上架 |
| VM7-14-B3 | mapping_id | already_mounted | 已上架 | 409 | 重复上架 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-14-S1 | 过审上架 | pending+approved | POST mount | 200, ->mounted |
| VM7-14-S2 | 未过审上架 | pending+submitted | POST mount | 409, 未过审 |
| VM7-14-S3 | 重复上架 | mounted | POST mount | 409, 已上架 |

---

### VM7-15: listing_status: mounted->paused_sync

**前置条件**:
- VM7-14 已执行, listing_status=mounted

**API**: `POST /shop/mx/mappings/{mapping_id}/pause`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- listing_status: mounted -> paused_sync
- 商品在公域渠道暂停同步
- audit_log 记录暂停
- 可恢复为mounted

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-15-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-15-B2 | mapping_id | not_mounted | 未上架 | 409 | 未上架不可暂停 |
| VM7-15-B3 | mapping_id | already_paused | 已暂停 | 409 | 重复暂停 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-15-S1 | 上架后暂停 | mounted | POST pause | 200, ->paused_sync |
| VM7-15-S2 | 未上架暂停 | pending | POST pause | 409, 不可暂停 |
| VM7-15-S3 | 重复暂停 | paused_sync | POST pause | 409, 已暂停 |

---

### VM7-16: listing_status: paused_sync->mounted

**前置条件**:
- VM7-15 已执行, listing_status=paused_sync

**API**: `POST /shop/mx/mappings/{mapping_id}/resume`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- listing_status: paused_sync -> mounted
- 商品恢复公域同步
- audit_log 记录恢复

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-16-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-16-B2 | mapping_id | not_paused | 未暂停 | 409 | 未暂停不可恢复 |
| VM7-16-B3 | mapping_id | already_mounted | 已上架 | 409 | 重复恢复 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-16-S1 | 暂停后恢复 | paused_sync | POST resume | 200, ->mounted |
| VM7-16-S2 | 未暂停恢复 | mounted | POST resume | 409, 不可恢复 |
| VM7-16-S3 | 双向切换 | mounted<->paused | POST pause/resume | 200, 状态切换 |

---

### VM7-17: listing_status: pending->blocked (外部拒审)

**前置条件**:
- VM7-13 已执行, listing_status=pending
- external_audit_status: submitted -> rejected (外部审核拒绝)

**API**: `POST /shop/mx/mappings/{mapping_id}/block`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "block_reason": "external_audit_rejected",
  "block_detail": "商品图片不符合规范"
}
```

**期望结果**:
- HTTP Status: 200
- listing_status: pending -> blocked
- external_audit_status: rejected
- audit_log 记录拒审原因
- blocked后可重新提交 (blocked -> pending)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-17-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-17-B2 | mapping_id | not_pending | 非pending | 409 | 非pending不可block |
| VM7-17-B3 | block_reason | [空] | 空值 | 422 | 拒审原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-17-S1 | 外部拒审 | pending+rejected | POST block | 200, ->blocked |
| VM7-17-S2 | 非pending拒审 | mounted | POST block | 409, 不可block |
| VM7-17-S3 | blocked后重新提交 | blocked | POST resubmit | 200, ->pending |

---

### VM7-18: listing_status: blocked->pending (重新提交)

**前置条件**:
- VM7-17 已执行, listing_status=blocked

**API**: `POST /shop/mx/mappings/{mapping_id}/resubmit`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "resubmit_note": "已修改商品图片, 重新提交审核"
}
```

**期望结果**:
- HTTP Status: 200
- listing_status: blocked -> pending
- external_audit_status: -> submitted (重新提交审核)
- audit_log 记录重新提交
- 可再次进入审核流程

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-18-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-18-B2 | mapping_id | not_blocked | 非blocked | 409 | 非blocked不可resubmit |
| VM7-18-B3 | resubmit_note | [空] | 空值 | 422 | 重新提交说明不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-18-S1 | blocked重新提交 | blocked | POST resubmit | 200, ->pending |
| VM7-18-S2 | 非blocked重新提交 | mounted | POST resubmit | 409, 不可重新提交 |
| VM7-18-S3 | 重新提交后过审 | pending | POST mount | 200, ->mounted |

---

### VM7-19: external_audit_status: submitted

**前置条件**:
- VM7-1 已执行, mapping刚创建

**API**: `GET /shop/mx/mappings/{mapping_id}`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- external_audit_status = submitted
- listing_status = pending
- audit_log 包含提交记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-19-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-19-S1 | 查询submitted | 刚创建 | GET | 200, audit=submitted |
| VM7-19-S2 | 查询audit_log | submitted | GET logs | 200, 含提交记录 |

---

### VM7-20: external_audit_status: approved

**前置条件**:
- VM7-13 已执行, external_audit_status=submitted
- 外部审核通过 (stub模拟)

**API**: `POST /shop/mx/mappings/{mapping_id}/audit-callback`
**Headers**: `X-Douyin-Signature: {hmac_sha256}`

**请求体**:
```json
{
  "external_product_id": "DY_prod_001",
  "audit_status": "approved",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- external_audit_status: submitted -> approved
- listing_status可从pending变为mounted
- audit_log 记录审核通过

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-20-B1 | audit_status | approved | 通过 | 200 | ->approved |
| VM7-20-B2 | audit_status | rejected | 拒绝 | 200 | ->rejected+blocked |
| VM7-20-B3 | audit_status | invalid | 非法 | 422 | 审核状态不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-20-S1 | 审核通过 | submitted | POST approved | 200, ->approved |
| VM7-20-S2 | 通过后上架 | approved | POST mount | 200, ->mounted |
| VM7-20-S3 | 审核拒绝 | submitted | POST rejected | 200, ->rejected+blocked |

---

### VM7-21: external_audit_status: rejected

**前置条件**:
- VM7-13 已执行, external_audit_status=submitted
- 外部审核拒绝 (stub模拟)

**API**: `POST /shop/mx/mappings/{mapping_id}/audit-callback`
**Headers**: `X-Douyin-Signature: {hmac_sha256}`

**请求体**:
```json
{
  "external_product_id": "DY_prod_001",
  "audit_status": "rejected",
  "reject_reason": "商品描述不符合规范",
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- external_audit_status: submitted -> rejected
- listing_status: pending -> blocked
- audit_log 记录拒审原因
- 可重新提交 (resubmit)

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-21-B1 | audit_status | rejected | 拒绝 | 200 | ->rejected+blocked |
| VM7-21-B2 | reject_reason | [空] | 空值 | 422 | 拒审原因不能为空 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-21-S1 | 审核拒绝 | submitted | POST rejected | 200, ->rejected+blocked |
| VM7-21-S2 | 拒绝后重新提交 | blocked | POST resubmit | 200, ->pending |
| VM7-21-S3 | 拒绝后不可上架 | blocked | POST mount | 409, 不可上架 |

---

### VM7-22: Webhook验签-HMAC-SHA256

**前置条件**:
- DOUYIN_WEBHOOK_MODE=stub
- 持有HMAC-SHA256测试密钥

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_sign_test",
  "event_type": "order.paid",
  "external_order_no": "DY_order_sign",
  "external_product_id": "DY_prod_001",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- 有效签名: HTTP 200, 正常处理
- 无效签名: HTTP 401, 拒绝处理
- 缺失签名: HTTP 401
- 验签算法: HMAC-SHA256
- 验签失败不创建任何数据

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-22-B1 | X-Douyin-Signature | valid_sig | 有效签名 | 200 | 正常处理 |
| VM7-22-B2 | X-Douyin-Signature | tampered_sig | 篡改签名 | 401 | 验签失败 |
| VM7-22-B3 | X-Douyin-Signature | [缺失] | 无签名头 | 401 | 缺少签名 |
| VM7-22-B4 | X-Douyin-Signature | [空] | 空签名 | 401 | 签名不能为空 |
| VM7-22-B5 | body | 篡改body不改签名 | body被篡改 | 401 | 验签失败 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-22-S1 | 有效签名 | 正常 | POST 正确签名 | 200, 正常处理 |
| VM7-22-S2 | 篡改签名 | 正常 | POST 错误签名 | 401, 验签失败 |
| VM7-22-S3 | 缺失签名 | 正常 | POST 无签名 | 401, 缺少签名 |

---

### VM7-23: Webhook验签-timestamp>300s-401

**前置条件**:
- DOUYIN_WEBHOOK_MODE=stub
- 有效HMAC-SHA256签名
- timestamp超过300秒

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {old_timestamp}`

**请求体**:
```json
{
  "event_id": "evt_old_ts",
  "event_type": "order.paid",
  "external_order_no": "DY_order_old",
  "external_product_id": "DY_prod_001",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420000
}
```

**期望结果**:
- timestamp <= 300s: HTTP 200, 正常处理
- timestamp > 300s: HTTP 401, 时间戳过期
- 缺失timestamp: HTTP 401
- timestamp验证防重放攻击

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-23-B1 | timestamp | current(0s) | 当前 | 200 | 正常处理 |
| VM7-23-B2 | timestamp | current-299s | 299s前 | 200 | 正常处理 |
| VM7-23-B3 | timestamp | current-300s | 300s前(边界) | 200 | 正常处理 |
| VM7-23-B4 | timestamp | current-301s | 301s前 | 401 | 时间戳过期 |
| VM7-23-B5 | timestamp | current-600s | 10分钟前 | 401 | 时间戳过期 |
| VM7-23-B6 | timestamp | [缺失] | 无timestamp | 401 | 缺少时间戳 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-23-S1 | 当前时间戳 | 0s | POST | 200, 正常处理 |
| VM7-23-S2 | 300s边界 | 300s前 | POST | 200, 正常处理 |
| VM7-23-S3 | 超过300s | 301s前 | POST | 401, 时间戳过期 |

---

### VM7-24: Webhook-商家closed/suspended-拒单

**前置条件**:
- 商品已映射, 但merchant.status=closed或suspended
- DOUYIN_WEBHOOK_MODE=stub

**API**: `POST /webhooks/douyin`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_blocked_merchant",
  "event_type": "order.paid",
  "external_order_no": "DY_order_blocked",
  "external_product_id": "DY_prod_001",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200
- Webhook默认拒单: merchant_status_blocked
- 不创建order
- 不生成claim_token
- audit_log 记录拒单原因

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-24-B1 | merchant | closed | 关闭 | 200 | 拒单merchant_status_blocked |
| VM7-24-B2 | merchant | suspended | 暂停 | 200 | 拒单merchant_status_blocked |
| VM7-24-B3 | merchant | active | 正常 | 200 | 正常处理 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-24-S1 | 关闭商家Webhook | closed | POST | 200, 拒单 |
| VM7-24-S2 | 暂停商家Webhook | suspended | POST | 200, 拒单 |
| VM7-24-S3 | 正常商家Webhook | active | POST | 200, 正常处理 |

---

### VM7-25: 领权-已领token-claimed状态

**前置条件**:
- VM7-8 已执行, claim_token已使用
- order.status=paid (已领权)

**API**: `GET /claim/{token}`
**Headers**: `Authorization: Bearer {buyer_token} (可选)`

**期望结果**:
- HTTP Status: 200
- 返回 claim_status: claimed
- 返回商品信息
- 提示已领权, 不可重复领权
- 不返回领权表单

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-25-B1 | token | used_token | 已使用 | 200 | claimed状态 |
| VM7-25-B2 | token | unused_token | 未使用 | 200 | pending状态 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-25-S1 | 已领权GET | claimed | GET | 200, claimed状态 |
| VM7-25-S2 | 已领权POST | claimed | POST | 409, 已使用 |
| VM7-25-S3 | 未领权GET | pending | GET | 200, pending状态 |

---

### VM7-26: 领权-token单次使用

**前置条件**:
- VM7-8 已执行, claim_token已使用一次

**API**: `POST /claim/{token}`
**Headers**: `Authorization: Bearer {buyer_token}`

**请求体**:
```json
{
  "buyer_phone": "13900000099",
  "buyer_name": "测试买家"
}
```

**期望结果**:
- HTTP Status: 409
- 错误码: claim_token_already_used
- 错误信息: 领权码已使用
- 不重复创建order/entitlement
- token标记为used, 不可再用

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-26-B1 | token | used_once | 已使用1次 | 409 | 已使用 |
| VM7-26-B2 | token | used_twice | 尝试第3次 | 409 | 已使用 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-26-S1 | 首次领权 | 未使用 | POST | 200, 领权成功 |
| VM7-26-S2 | 第二次领权 | 已使用 | POST | 409, 已使用 |
| VM7-26-S3 | 第三次领权 | 已使用2次 | POST | 409, 已使用 |

---

### VM7-27: 领权-UK(token)唯一约束

**前置条件**:
- VM7-3 已执行, claim_token已生成
- 数据库验证UK(token)

**API**: `数据库验证 (DB check)`
**Headers**: `N/A`

**期望结果**:
- claim_tokens表: UK(token) 唯一约束
- 每个Webhook生成唯一token
- 重复Webhook不生成新token (幂等)
- token格式: UUID或随机字符串

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-27-B1 | token | unique_uuid_1 | 唯一 | 200 | 正常 |
| VM7-27-B2 | token | unique_uuid_2 | 唯一 | 200 | 正常 |
| VM7-27-B3 | UK约束 | 重复token | 违反UK | 500 | DB约束拒绝 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-27-S1 | token唯一性 | 正常生成 | 验证DB | UK(token)有效 |
| VM7-27-S2 | 幂等不重复生成 | 重复Webhook | 验证DB | 不生成新token |

---

### VM7-28: 领权-expires_at验证

**前置条件**:
- VM7-3 已执行, claim_token有expires_at
- claim_expire_days默认7天

**API**: `GET /claim/{token} (验证expires_at)`
**Headers**: `Authorization: Bearer {buyer_token}`

**期望结果**:
- expires_at = token创建时间 + claim_expire_days (默认7天)
- expires_at之前: 正常领权
- expires_at之后: 410 Gone
- expires_at精确到秒

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-28-B1 | expires_at | 7天后 | 正常 | 200 | 有效 |
| VM7-28-B2 | expires_at | 7天+1秒 | 过期 | 410 | 已过期 |
| VM7-28-B3 | expires_at | 6天23h59m | 将过期 | 200 | 有效 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-28-S1 | 有效期内领权 | 7天内 | GET/POST | 200, 正常 |
| VM7-28-S2 | 过期领权 | 7天后 | GET | 410, 已过期 |
| VM7-28-S3 | 边界过期 | 7天+1秒 | GET | 410, 已过期 |

---

### VM7-29: 领权-claim_landing_base配置

**前置条件**:
- 商家已配置 claim_landing_base
- VM7-3 已执行, SMS已发送

**API**: `GET /shop/mx/sms-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- 返回 claim_landing_base (领权短链域名, 商家可写)
- 返回 claim_expire_days
- 返回 sms_signature (只读, 平台P12分配)
- 返回 claim_template_* (只读, 平台P12分配)
- SMS中领权链接 = claim_landing_base + /claim/ + token

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-29-B1 | claim_landing_base | https://claim.example.com | 正常 | 200 | 可写 |
| VM7-29-B2 | claim_landing_base | [空] | 空值 | 200 | 使用默认域名 |
| VM7-29-B3 | sms_signature | [平台分配] | 只读 | 200 | 不可修改 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-29-S1 | 读取SMS配置 | 已配置 | GET | 200, 含所有字段 |
| VM7-29-S2 | 修改claim_landing_base | 已配置 | PUT | 200, 更新成功 |
| VM7-29-S3 | 修改sms_signature | 已配置 | PUT | 403, 只读字段 |

---

### VM7-30: 领权-claim_expire_days默认7

**前置条件**:
- 商家未自定义 claim_expire_days

**API**: `GET /shop/mx/sms-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- claim_expire_days = 7 (默认值)
- 商家可修改 claim_expire_days (A15-S)
- token的expires_at = 创建时间 + claim_expire_days天

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-30-B1 | claim_expire_days | 7(默认) | 默认 | 200 | 7天 |
| VM7-30-B2 | claim_expire_days | 3(自定义) | 修改 | 200 | 3天 |
| VM7-30-B3 | claim_expire_days | 30(自定义) | 修改 | 200 | 30天 |
| VM7-30-B4 | claim_expire_days | 0 | 零值 | 422 | 必须>0 |
| VM7-30-B5 | claim_expire_days | -1 | 负值 | 422 | 必须>0 |
| VM7-30-B6 | claim_expire_days | 366 | 超1年 | 422 | 超出限制 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-30-S1 | 默认7天 | 未配置 | GET | 200, 7天 |
| VM7-30-S2 | 修改为3天 | 已配置 | PUT 3 | 200, 3天 |
| VM7-30-S3 | 修改后token过期 | 3天配置 | 领权验证 | expires_at=3天 |

---

### VM7-31: 领权-sms_signature只读

**前置条件**:
- 商家已有 sms_signature (平台P12分配)

**API**: `PUT /shop/mx/sms-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "sms_signature": "自定义签名"
}
```

**期望结果**:
- HTTP Status: 403
- 错误码: field_readonly
- 错误信息: sms_signature为只读字段, 由平台分配
- sms_signature 不被修改

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-31-B1 | sms_signature | 自定义 | 尝试修改 | 403 | 只读字段 |
| VM7-31-B2 | sms_signature | [空] | 尝试清空 | 403 | 只读字段 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-31-S1 | 修改sms_signature | 已分配 | PUT | 403, 只读 |
| VM7-31-S2 | 读取sms_signature | 已分配 | GET | 200, 返回平台分配值 |

---

### VM7-32: 领权-claim_template只读

**前置条件**:
- 商家已有 claim_template_* (平台P12分配)

**API**: `PUT /shop/mx/sms-config`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "claim_template_sms": "自定义模板内容"
}
```

**期望结果**:
- HTTP Status: 403
- 错误码: field_readonly
- 错误信息: claim_template为只读字段, 由平台分配
- claim_template_* 不被修改

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-32-B1 | claim_template_sms | 自定义 | 尝试修改 | 403 | 只读字段 |
| VM7-32-B2 | claim_template_landing | 自定义 | 尝试修改 | 403 | 只读字段 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-32-S1 | 修改claim_template | 已分配 | PUT | 403, 只读 |
| VM7-32-S2 | 读取claim_template | 已分配 | GET | 200, 返回平台分配值 |

---

### VM7-33: Mx未开通组合-422 channel_combo_not_enabled

**前置条件**:
- Phase1只验收默认组合1-A
- 其他组合未开通

**API**: `POST /shop/mx/mappings`
**Headers**: `Authorization: Bearer {merchant_token}`

**请求体**:
```json
{
  "product_id": "prod_001",
  "channel": "douyin",
  "channel_combo": "2-B",
  "external_product_id": "DY_prod_001"
}
```

**期望结果**:
- HTTP Status: 422
- 错误码: channel_combo_not_enabled
- 错误信息: 该渠道组合未开通
- 不创建映射记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-33-B1 | channel_combo | 2-B | 未开通 | 422 | channel_combo_not_enabled |
| VM7-33-B2 | channel_combo | 3-C | 未开通 | 422 | channel_combo_not_enabled |
| VM7-33-B3 | channel_combo | 4-D | 未开通 | 422 | channel_combo_not_enabled |
| VM7-33-B4 | channel_combo | 1-A | 已开通 | 201 | 映射成功 |
| VM7-33-B5 | channel_combo | invalid | 非法 | 422 | 组合编码不合法 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-33-S1 | 未开通组合 | 2-B | POST | 422, channel_combo_not_enabled |
| VM7-33-S2 | 已开通组合 | 1-A | POST | 201, 映射成功 |
| VM7-33-S3 | 非法组合 | invalid | POST | 422, 编码不合法 |

---

### VM7-34: 建单幂等-UK(channel, external_order_no)

**前置条件**:
- VM7-3 已执行, 已创建order(channel=douyin, external_order_no=DY_order_001)

**API**: `POST /webhooks/douyin (不同event_id, 相同external_order_no)`
**Headers**: `X-Douyin-Signature: {hmac_sha256}, X-Douyin-Timestamp: {timestamp}`

**请求体**:
```json
{
  "event_id": "evt_order_001_different",
  "event_type": "order.paid",
  "external_order_no": "DY_order_001",
  "external_product_id": "DY_prod_001",
  "buyer_phone": "139****0099",
  "amount_cents": 9900,
  "timestamp": 1723420800
}
```

**期望结果**:
- HTTP Status: 200 (或 409)
- UK(channel, external_order_no) 唯一约束
- 相同external_order_no不同event_id: 幂等处理
- 不重复创建order
- 不重复生成claim_token

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-34-B1 | external_order_no | DY_order_001(重复) | 重复 | 200 | 幂等不重复 |
| VM7-34-B2 | external_order_no | DY_order_002(新) | 新订单 | 200 | 正常处理 |
| VM7-34-B3 | channel+order_no | 同channel同order_no | UK违反 | 200 | 幂等 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-34-S1 | 重复external_order_no | 已存在 | POST | 200, 幂等 |
| VM7-34-S2 | 新external_order_no | 不存在 | POST | 200, 新建 |
| VM7-34-S3 | UK约束验证 | DB验证 | 查询 | UK(channel, external_order_no)有效 |

---

### VM7-35: 公域挂载闸(F7)-未过审->映射被拒

**前置条件**:
- 商品已映射, listing_status=pending
- external_audit_status=submitted (未过审)
- 尝试在公域上架/挂载

**API**: `POST /shop/mx/mappings/{mapping_id}/mount`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 409
- 错误码: audit_not_approved
- 错误信息: 未通过审核, 不可挂载
- listing_status 不变 (仍为pending)
- 商品在公域渠道不可见

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-35-B1 | audit_status | submitted | 未过审 | 409 | 映射被拒 |
| VM7-35-B2 | audit_status | rejected | 已拒审 | 409 | 映射被拒 |
| VM7-35-B3 | audit_status | approved | 已过审 | 200 | 映射成功 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-35-S1 | 未过审挂载 | submitted | POST mount | 409, 映射被拒 |
| VM7-35-S2 | 已拒审挂载 | rejected | POST mount | 409, 映射被拒 |
| VM7-35-S3 | 已过审挂载 | approved | POST mount | 200, 映射成功 |

---

### VM7-36: 公域挂载闸(F7)-过审->映射成功

**前置条件**:
- 商品已映射, listing_status=pending
- external_audit_status=approved (已过审)

**API**: `POST /shop/mx/mappings/{mapping_id}/mount`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- listing_status: pending -> mounted
- 商品在公域渠道可见
- audit_log 记录挂载成功
- 可接收公域Webhook订单

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-36-B1 | audit_status | approved | 已过审 | 200 | 映射成功 |
| VM7-36-B2 | listing_status | mounted | 已挂载 | 409 | 重复挂载 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-36-S1 | 过审后挂载 | pending+approved | POST mount | 200, ->mounted |
| VM7-36-S2 | 挂载后收单 | mounted | POST webhook | 200, 接收订单 |
| VM7-36-S3 | 重复挂载 | mounted | POST mount | 409, 已挂载 |

---

### VM7-37: 公域挂载闸(F7)-强制下架

**前置条件**:
- VM7-14 已执行, listing_status=mounted
- 平台管理员强制下架

**API**: `POST /admin/mx/mappings/{mapping_id}/force-unmount`
**Headers**: `Authorization: Bearer {platform_admin_token}`

**请求体**:
```json
{
  "reason": "违规商品强制下架"
}
```

**期望结果**:
- HTTP Status: 200
- listing_status: mounted -> paused_sync (或 unmounted)
- 商品在公域渠道不可见
- audit_log 记录强制下架原因
- 商家收到下架通知

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-37-B1 | mapping_id | not_exist | 不存在 | 404 | 映射不存在 |
| VM7-37-B2 | mapping_id | not_mounted | 未挂载 | 409 | 未挂载不可下架 |
| VM7-37-B3 | reason | [空] | 空值 | 422 | 下架原因不能为空 |
| VM7-37-B4 | reason | ab | 长度<4 | 422 | 原因至少4字符 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-37-S1 | 强制下架 | mounted | POST force-unmount | 200, ->paused/unmounted |
| VM7-37-S2 | 非管理员下架 | merchant_token | POST | 403, 无权操作 |
| VM7-37-S3 | 下架后不可收单 | paused | POST webhook | 200, 拒单 |

---

### VM7-38: Mx端到端8步闭环 (3.5.4最小集)

**前置条件**:
- 完整环境: WECHAT_PAY_MODE=stub, DOUYIN_WEBHOOK_MODE=stub
- 商家已入驻, 商品已创建
- 步骤1: 上架商品 (on_sale=true)
- 步骤2: 公域映射 (POST mapping)
- 步骤3: 抖店付款 (POST webhook order.paid)
- 步骤4: 领权 (POST claim/{token})
- 步骤5: 学课 (POST learn)
- 步骤6: 退款 (POST webhook refund)
- 步骤7: 验证不可学 (GET/POST learn)
- 步骤8: 验证entitlement=revoked

**API**: `端到端流程验证 (多API组合)`
**Headers**: `Authorization: Bearer {merchant_token/buyer_token}`

**请求体**:
```json
// 步骤1: PUT /shop/products/{id} {on_sale: true}
// 步骤2: POST /shop/mx/mappings
// 步骤3: POST /webhooks/douyin (order.paid)
// 步骤4: POST /claim/{token}
// 步骤5: POST /courses/{id}/learn
// 步骤6: POST /webhooks/douyin (order.refund)
// 步骤7: POST /courses/{id}/learn (验证不可学)
// 步骤8: GET /shop/orders/{id} (验证entitlement=revoked)
```

**期望结果**:
- 步骤1: 200, on_sale=true
- 步骤2: 201, mapping创建, listing=pending
- 步骤3: 200, order=claim_pending, claim_token生成, SMS发送
- 步骤4: 200, order=paid, entitlement=active
- 步骤5: 200, 学习成功
- 步骤6: 200, order=refunded, entitlement=revoked
- 步骤7: 403, 已退款不可学习
- 步骤8: 200, entitlement=revoked, enrollment=revoked
- 全链路8步全部通过

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-38-B1 | 步骤1上架 | on_sale=true | 验证 | 200 | 上架成功 |
| VM7-38-B2 | 步骤2映射 | on_sale商品 | 验证 | 201 | 映射成功 |
| VM7-38-B3 | 步骤3付款 | 已映射 | 验证 | 200 | claim_pending+token |
| VM7-38-B4 | 步骤4领权 | pending | 验证 | 200 | paid+active |
| VM7-38-B5 | 步骤5学课 | active | 验证 | 200 | 学习成功 |
| VM7-38-B6 | 步骤6退款 | paid | 验证 | 200 | refunded+revoked |
| VM7-38-B7 | 步骤7不可学 | revoked | 验证 | 403 | 已退款不可学 |
| VM7-38-B8 | 步骤8验证 | refunded | 验证 | 200 | entitlement=revoked |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-38-S1 | 完整8步闭环 | 初始状态 | 依次执行8步 | 全200/403, 闭环通过 |
| VM7-38-S2 | 步骤3失败回退 | 映射未完成 | 跳到步骤3 | 200, 拒单(未映射) |
| VM7-38-S3 | 步骤4过期 | token过期 | 步骤4 | 410, 需重新领权 |

---

### VM7-39: 抖店Webhook-claim_token生成

**前置条件**:
- VM7-3 已执行, Webhook已接收
- order.status=claim_pending

**API**: `GET /shop/orders/{order_id} (验证claim_token)`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- order包含 claim_token (唯一)
- claim_token有expires_at (默认7天后)
- claim_token有claim_url (claim_landing_base + /claim/ + token)
- claim_token初始status=pending

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-39-B1 | claim_token | [非空] | 生成 | 200 | token已生成 |
| VM7-39-B2 | expires_at | [未来时间] | 有效 | 200 | 未过期 |
| VM7-39-B3 | claim_url | [完整URL] | 格式 | 200 | 可访问 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-39-S1 | 验证token生成 | claim_pending | GET order | 200, 含token |
| VM7-39-S2 | 验证token唯一 | 多个Webhook | GET orders | 每个token不同 |
| VM7-39-S3 | 验证expires_at | 刚生成 | GET order | 200, 7天后过期 |

---

### VM7-40: 抖店Webhook-SMS发送

**前置条件**:
- VM7-3 已执行, Webhook已处理
- claim_token已生成
- claim_landing_base已配置

**API**: `验证SMS发送记录 (GET /shop/orders/{order_id}/sms-logs)`
**Headers**: `Authorization: Bearer {merchant_token}`

**期望结果**:
- HTTP Status: 200
- SMS记录包含: phone (尾号), content, claim_url, sent_at
- SMS内容包含领权链接 (claim_landing_base + /claim/ + token)
- SMS使用平台分配的 sms_signature
- SMS使用平台分配的 claim_template
- stub模式: SMS不实际发送, 仅记录

**边界值测试**:

| 变体ID | 字段 | 输入值 | 边界类型 | 期望Status | 说明 |
|--------|------|--------|---------|-----------|------|
| VM7-40-B1 | sms记录 | [存在] | 已发送 | 200 | 记录存在 |
| VM7-40-B2 | claim_url | [完整] | 链接 | 200 | 含领权链接 |
| VM7-40-B3 | sms_signature | [平台分配] | 签名 | 200 | 使用平台签名 |

**业务场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| VM7-40-S1 | 验证SMS发送 | Webhook后 | GET sms-logs | 200, 记录存在 |
| VM7-40-S2 | 验证领权链接 | SMS内容 | GET sms-logs | 200, 含claim_url |
| VM7-40-S3 | stub模式不实际发送 | stub | 验证 | 仅记录, 不实际发送 |

---


## 四、附录

### 4.1 测试账号汇总

| 角色 | 手机号 | 密码 | 用途 |
|------|--------|------|------|
| 商家用户 | 13900000099 | test123456 | 商家端API操作 |
| 平台管理员 | 13800000000 | admin123456 | 平台管理端API操作 |
| 测试买家 | 13900000088 | buyer123456 | 买家端API操作 |

### 4.2 环境变量汇总

| 变量名 | 值 | 说明 |
|--------|-----|------|
| WECHAT_PAY_MODE | stub | 微信支付Mock模式 |
| DOUYIN_WEBHOOK_MODE | stub | 抖店Webhook Mock模式 |

### 4.3 平台业务编码规则

| 编码类型 | 格式 | 示例 |
|----------|------|------|
| 商家merchant_no | SH + 日期 + 4位流水 | SH202608100001 |
| 入驻application_no | OB + 日期 + 4位流水 | OB202608100001 |
| 续费log_no | RF + 日期 + 4位流水 | RF202608100001 |
| 服务记录log_no | SV + 日期 + 4位流水 | SV202608100001 |
| 订阅subscription_no | DY + 日期 + 4位流水 | DY202608100001 |
| 清结算batch_no | JS + ISO年周 + 4位流水 | JS2026320001 |
| 店铺store_no | DP + 4位流水 | DP0001 |
| 违规工单case_no | WG + 日期 + 4位流水 | WG202608100001 |
| 套餐模板code | PL + 3位数字 | PL001 |

### 4.4 测试用例统计

| 模块 | 用例数 | 边界值变体 | 业务场景 | 总计 |
|------|--------|-----------|---------|------|
| M3 支付硬验收 | 45 | ~210 | ~150 | ~405 |
| M6 核销开票 | 45 | ~210 | ~150 | ~405 |
| M7 公域Mx | 40 | ~190 | ~130 | ~360 |
| **合计** | **130** | **~610** | **~430** | **~1170** |

---

> **文档版本**: v1.0
> **生成日期**: 2026-08-12
> **执行工具**: Cursor AI 自动化执行
> **审核状态**: 待审核

---
# 内容获客商城 Phase 1 — Round 2-7 增强测试用例文档

> **文档版本**: v2.0
> **生成日期**: 2026-08-12
> **执行环境**: Cursor AI 自动化执行
> **测试框架**: Playwright (Web/MP H5) + pytest (API/E2E/Mock/Security/Regression)

---

## 目录

- [Round 2: Web UI 测试用例 (商家端 + 平台端)](#round-2-web-ui-测试用例)
- [Round 3: Mini-Program UI 测试用例](#round-3-mini-program-ui-测试用例)
- [Round 4: E2E 集成测试用例](#round-4-e2e-集成测试用例)
- [Round 5: Mock 外部集成测试用例](#round-5-mock-外部集成测试用例)
- [Round 6: Security/PII 安全测试用例](#round-6-securitypii-安全测试用例)
- [Round 7: 回归测试用例](#round-7-回归测试用例)

---

## 全局测试环境配置

### 环境变量

```bash
# Web 前端 (Vite)
PORT_WEB=5173
# Mini-Program H5 (uni-app)
PORT_MP=5174
# API 后端 (FastAPI)
PORT_API=8000

# Mock 服务模式
WECHAT_PAY_MODE=stub
DOUYIN_WEBHOOK_MODE=stub
SMS_MODE=stub
COURSE_LIB_MODE=stub

# 加密密钥
SHOP_PII_KEY=test-pii-key-for-unit-test-only-32b

# 数据库
DATABASE_URL=postgresql://test:test@localhost:5432/test_shop
```

### 测试账号

| 角色 | 手机号 | 密码 | 说明 |
|------|--------|------|------|
| 商家 (未入驻) | 13900000099 | test123456 | 无 merchant 记录 |
| 商家 (已入驻-active) | 13900000088 | test123456 | merchant.status=active |
| 商家 (审核中-pending) | 13900000077 | test123456 | 有 pending 入驻申请 |
| 商家 (暂停-suspended) | 13900000066 | test123456 | merchant.status=suspended |
| 平台管理员 | 13800000000 | admin123456 | role=platform_admin |
| 买家 | 13700000000 | buyer123456 | 普通买家用户 |

### Playwright 全局配置

```typescript
// playwright.config.ts
export default {
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    viewport: { width: 1280, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    locale: 'zh-CN',
  },
  projects: [
    { name: 'web', testDir: './tests/web', use: { baseURL: 'http://localhost:5173' } },
    { name: 'mp', testDir: './tests/mp', use: { baseURL: 'http://localhost:5174', viewport: { width: 375, height: 812 } } },
  ],
};
```

---

## Round 2: Web UI 测试用例

> 覆盖商家端 (15 existing + 15 new) + 平台端页面，共 30 个用例
> 测试框架: Playwright Chromium headless
> 视口: 1280×900 (Web), 375×812 (MP H5)

---

### UI-W-01: Dashboard 入驻横幅

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 未入驻商家用户已登录（手机号: 13900000099, 密码: test123456）
- Playwright Chromium headless, 视口 1280×900

**页面**: `/dashboard`
**路由**: `/dashboard`

**测试步骤**:
1. 导航到 http://localhost:5173/dashboard
2. 等待页面加载完成 (等待 `[data-testid="dashboard-container"]` 可见)
3. 验证入驻横幅存在: `page.locator('[data-testid="shop-onboarding-banner"]')`
4. 验证横幅文案包含「开通内容获客商城」
5. 验证「立即申请」按钮可见且可点击

**期望结果**:
- 横幅元素可见
- 文案包含「开通内容获客商城」
- 「立即申请」按钮存在且 enabled

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-01-S1 | 未入驻显示横幅 | merchant不存在 | 访问dashboard | 横幅可见 |
| UI-W-01-S2 | 已入驻不显示 | merchant.status=active | 访问dashboard | 横幅不可见 |
| UI-W-01-S3 | 审核中显示状态 | 有pending申请 | 访问dashboard | 显示审核中 |

---

### UI-W-02: 入驻申请表单 (A20)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 未入驻商家用户已登录（手机号: 13900000099, 密码: test123456）
- 用户 profile 已有 contact_name 和 mobile 字段

**页面**: `/shop/onboarding`
**路由**: `/shop/onboarding`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/onboarding
2. 等待 `[data-testid="onboarding-form"]` 可见
3. 验证 contact_name 字段已自动带出: `page.locator('[data-testid="input-contact-name"]')` 有值
4. 验证 mobile 字段已自动带出且脱敏显示: `page.locator('[data-testid="input-contact-mobile"]')` 值格式为 `139****0099`
5. 填写店铺名称: `page.fill('[data-testid="input-shop-name"]', '测试内容商城')`
6. 选择经营类目: `page.click('[data-testid="select-category"]')` → 选择「教育培训」
7. 上传营业执照: `page.setInputFiles('[data-testid="upload-business-license"]', 'tests/fixtures/license.png')`
8. 填写法人姓名: `page.fill('[data-testid="input-legal-person"]', '张三')`
9. 填写身份证号: `page.fill('[data-testid="input-id-no"]', '440101199001011234')`
10. 点击提交: `page.click('[data-testid="btn-submit-onboarding"]')`
11. 等待跳转到 `/dashboard` 或显示成功提示 `[data-testid="onboarding-success-toast"]`

**期望结果**:
- contact_name 和 mobile 自动带出
- mobile 脱敏显示 (138****8000 格式)
- 提交后跳转 dashboard 或显示成功提示
- API POST /api/v1/shop/onboarding 返回 201

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-02-S1 | 正常提交 | 所有必填项已填 | 点击提交 | 201 + 跳转 |
| UI-W-02-S2 | 店铺名为空 | shop_name留空 | 点击提交 | 表单校验错误「请填写店铺名称」 |
| UI-W-02-S3 | 身份证号格式错误 | id_no='123' | 点击提交 | 校验错误「身份证号格式不正确」 |
| UI-W-02-S4 | 营业执照未上传 | 无文件 | 点击提交 | 校验错误「请上传营业执照」 |
| UI-W-02-S5 | 重复提交 | 已有pending申请 | 访问onboarding | 显示「审核中」状态页 |

---

### UI-W-03: 交易看板 (A01)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456, merchant.status=active）
- 数据库有订单数据: 今日3笔已支付, 昨日2笔, 本月累计15笔

**页面**: `/shop/dashboard`
**路由**: `/shop/dashboard`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/dashboard
2. 等待 `[data-testid="shop-dashboard-container"]` 可见
3. 验证今日交易额卡片: `page.locator('[data-testid="card-today-revenue"]')` 显示金额
4. 验证今日订单数卡片: `page.locator('[data-testid="card-today-orders"]')` 显示「3」
5. 验证本月累计卡片: `page.locator('[data-testid="card-month-revenue"]')` 显示金额
6. 验证待核销订单数: `page.locator('[data-testid="card-pending-verification"]')`
7. 验证趋势图表存在: `page.locator('[data-testid="chart-revenue-trend"]')` 可见
8. 验证时间范围切换器: `page.locator('[data-testid="select-time-range"]')` 有「今日/7天/30天」选项

**期望结果**:
- 今日订单数显示「3」
- 各统计卡片均有数值
- 趋势图表渲染完成 (canvas 或 svg 元素存在)
- 时间范围切换器功能正常

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-03-S1 | 今日有数据 | 今日3笔订单 | 访问看板 | 今日订单=3, 金额正确 |
| UI-W-03-S2 | 今日无数据 | 今日0笔订单 | 访问看板 | 今日订单=0, 金额=¥0.00 |
| UI-W-03-S3 | 切换7天范围 | 默认今日 | 选择7天 | 图表更新为7天数据 |
| UI-W-03-S4 | 切换30天范围 | 默认今日 | 选择30天 | 图表更新为30天数据 |

---

### UI-W-04: 商品列表 (A02)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 数据库有商品数据: 5个on_sale, 3个draft, 2个under_review, 1个rejected

**页面**: `/shop/products`
**路由**: `/shop/products`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/products
2. 等待 `[data-testid="products-list-container"]` 可见
3. 验证商品卡片渲染: `page.locator('[data-testid^="product-card-"]')` 数量 > 0
4. 验证状态标签存在: `page.locator('[data-testid="product-status-tag"]').first()` 可见
5. 验证状态筛选器: `page.locator('[data-testid="filter-product-status"]')` 有「全部/在售/草稿/审核中/已驳回」
6. 点击「草稿」筛选: `page.click('[data-testid="filter-product-status"] [data-value="draft"]')`
7. 验证列表只显示 draft 状态商品
8. 验证分页器: `page.locator('[data-testid="pagination"]')` 可见
9. 验证分页大小选择器有 10/20/50/100 选项

**期望结果**:
- 商品卡片正确渲染，含图片、名称、价格、状态标签
- 状态筛选功能正常
- 分页器存在且有 10/20/50/100 下拉
- 默认 page_size=20

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-04-S1 | 全部商品 | 11个商品 | 默认访问 | 显示20条(分页) |
| UI-W-04-S2 | 筛选on_sale | 5个on_sale | 选在售 | 仅显示5个 |
| UI-W-04-S3 | 分页切换100 | 11个商品 | page_size=100 | 一页显示11个 |
| UI-W-04-S4 | 空列表 | 0个商品 | 访问 | 显示空状态图 |
| UI-W-04-S5 | 搜索商品名 | 有匹配商品 | 输入关键词 | 返回匹配结果 |

---

### UI-W-05: 商品创建 - 类型切换 (A03)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）

**页面**: `/shop/products/edit`
**路由**: `/shop/products/edit`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/products/edit
2. 等待 `[data-testid="product-edit-form"]` 可见
3. 验证商品类型选择器: `page.locator('[data-testid="select-product-type"]')` 有「课程/资料/服务」
4. 默认选择「课程」类型
5. 验证课程编排区域可见: `page.locator('[data-testid="course-arrangement-section"]')` 可见
6. 切换到「资料」类型: `page.click('[data-testid="select-product-type"] [data-value="material"]')`
7. 验证课程编排区域不可见: `page.locator('[data-testid="course-arrangement-section"]')` 不可见
8. 验证文件上传区域可见: `page.locator('[data-testid="material-upload-section"]')` 可见
9. 切换到「服务」类型: `page.click('[data-testid="select-product-type"] [data-value="service"]')`
10. 验证服务配置区域可见: `page.locator('[data-testid="service-config-section"]')` 可见
11. 验证次数输入框: `page.locator('[data-testid="input-service-count"]')` 可见

**期望结果**:
- 类型选择器有3个选项
- 选择「课程」时显示课程编排区
- 选择「资料」时显示文件上传区，隐藏课程编排
- 选择「服务」时显示服务配置区（含次数）

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-05-S1 | 默认课程类型 | 新建页面 | 访问 | 课程编排区可见 |
| UI-W-05-S2 | 切换资料 | 课程类型 | 选资料 | 文件上传区可见, 课程区隐藏 |
| UI-W-05-S3 | 切换服务 | 资料类型 | 选服务 | 服务配置区可见, 文件区隐藏 |
| UI-W-05-S4 | 再切回课程 | 服务类型 | 选课程 | 课程编排区恢复可见 |

---

### UI-W-06: 商品创建 - 课程编排 (A03)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 商品类型为「课程」

**页面**: `/shop/products/edit`
**路由**: `/shop/products/edit`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/products/edit
2. 选择商品类型「课程」
3. 验证「添加专栏」按钮: `page.locator('[data-testid="btn-add-column"]')` 可见
4. 点击「添加专栏」: `page.click('[data-testid="btn-add-column"]')`
5. 验证专栏表单出现: `page.locator('[data-testid^="column-form-"]')` 可见
6. 填写专栏标题: `page.fill('[data-testid="column-form-0-title"]', '第一专栏')`
7. 点击「添加课时」: `page.click('[data-testid="column-form-0-btn-add-lesson"]')`
8. 验证课时行出现: `page.locator('[data-testid^="lesson-row-"]')` 可见
9. 填写课时标题: `page.fill('[data-testid="lesson-row-0-title"]', '课时1')`
10. 设置试看: `page.check('[data-testid="lesson-row-0-preview"]')`
11. 再添加一个课时: `page.click('[data-testid="column-form-0-btn-add-lesson"]')`
12. 验证课时数为2

**期望结果**:
- 专栏可添加，标题可填
- 课时可在专栏下添加
- 试看标记可设置
- 课时顺序正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-06-S1 | 添加多专栏 | 1个专栏 | 再添加1个 | 2个专栏并存 |
| UI-W-06-S2 | 删除课时 | 2个课时 | 删除第1个 | 剩1个, 序号重排 |
| UI-W-06-S3 | 课时拖拽排序 | 2个课时 | 拖拽交换 | 顺序更新 |
| UI-W-06-S4 | 试看限制 | 设置试看 | 保存 | preview=true 保存成功 |

---

### UI-W-07: 商品创建 - 保存草稿 (A03)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）

**页面**: `/shop/products/edit`
**路由**: `/shop/products/edit`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/products/edit
2. 填写商品名称: `page.fill('[data-testid="input-product-name"]', '测试课程商品')`
3. 填写商品价格: `page.fill('[data-testid="input-product-price"]', '99.00')`
4. 选择商品类型「课程」并添加1个专栏1个课时
5. 点击「保存草稿」: `page.click('[data-testid="btn-save-draft"]')`
6. 等待成功提示: `page.locator('[data-testid="save-success-toast"]')` 可见
7. 验证跳转到商品列表或停留在编辑页并显示成功
8. 验证 API 调用 POST /api/v1/shop/products 返回 201, body.status='draft'

**期望结果**:
- 草稿保存成功
- 商品状态为 draft
- 返回商品 ID
- 页面显示成功提示

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-07-S1 | 最少必填项 | 仅填名称 | 保存草稿 | 成功, status=draft |
| UI-W-07-S2 | 价格为0 | price=0 | 保存草稿 | 成功(允许免费) |
| UI-W-07-S3 | 价格为空 | price留空 | 保存草稿 | 校验错误「请填写价格」 |
| UI-W-07-S4 | 提交审核 | 草稿已存 | 点提交审核 | status=under_review |

---

### UI-W-08: 订单管理 - 列表 (A09)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 数据库有订单数据: 10笔paid, 5笔pending, 3笔refunded

**页面**: `/shop/orders`
**路由**: `/shop/orders`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/orders
2. 等待 `[data-testid="orders-list-container"]` 可见
3. 验证订单列表渲染: `page.locator('[data-testid^="order-row-"]')` 数量 > 0
4. 验证每行包含: 订单号、商品名、买家手机(脱敏)、金额、状态标签
5. 验证买家手机脱敏: `page.locator('[data-testid="order-buyer-mobile"]').first()` 文本格式为 `138****8000`
6. 验证状态标签颜色: paid=绿色, pending=灰色, refunded=红色
7. 验证分页器存在且有 10/20/50/100 下拉

**期望结果**:
- 订单列表正确渲染
- 买家手机号脱敏显示
- 状态标签颜色正确
- 分页功能正常

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-08-S1 | 默认20条 | 18笔订单 | 访问 | 一页显示18条 |
| UI-W-08-S2 | 超过100条 | 105笔订单 | page_size=100 | 显示100条, 有第2页 |
| UI-W-08-S3 | 空列表 | 0笔订单 | 访问 | 显示空状态 |
| UI-W-08-S4 | 手机脱敏 | 有订单 | 检查 | 138****8000格式 |

---

### UI-W-09: 订单管理 - 详情抽屉 (A09)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 有1笔 paid 状态订单 (order_no=TEST_ORDER_001)

**页面**: `/shop/orders`
**路由**: `/shop/orders`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/orders
2. 等待列表加载完成
3. 点击第一行订单: `page.click('[data-testid^="order-row-"] >> nth=0')`
4. 验证详情抽屉滑出: `page.locator('[data-testid="order-detail-drawer"]')` 可见
5. 验证抽屉内容包含: 订单号、商品信息、买家信息(脱敏)、支付信息、时间线
6. 验证「查看买家完整手机」按钮: `page.locator('[data-testid="btn-reveal-buyer-mobile"]')` 可见
7. 点击「查看买家完整手机」: `page.click('[data-testid="btn-reveal-buyer-mobile"]')`
8. 验证手机号短暂显示明文后回退脱敏
9. 验证退款按钮 (paid状态): `page.locator('[data-testid="btn-refund"]')` 可见
10. 点击关闭抽屉: `page.click('[data-testid="btn-close-drawer"]')`
11. 验证抽屉关闭

**期望结果**:
- 抽屉正确滑出并展示订单详情
- 买家手机默认脱敏
- 揭露按钮可揭露明文
- paid 状态显示退款按钮
- 抽屉可关闭

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-09-S1 | paid订单详情 | paid | 点击行 | 显示退款按钮 |
| UI-W-09-S2 | pending订单 | pending | 点击行 | 无退款按钮, 显示取消按钮 |
| UI-W-09-S3 | refunded订单 | refunded | 点击行 | 显示退款信息 |
| UI-W-09-S4 | 揭露手机 | 脱敏显示 | 点揭露 | 明文5分钟后回退 |
| UI-W-09-S5 | 关闭抽屉回退 | 已揭露明文 | 关闭抽屉 | 手机号回退脱敏 |

---

### UI-W-10: 订单管理 - 状态筛选 (A09)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 数据库有不同状态订单: 10 paid, 5 pending, 3 refunded

**页面**: `/shop/orders`
**路由**: `/shop/orders`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/orders
2. 验证状态筛选器: `page.locator('[data-testid="filter-order-status"]')` 有「全部/待支付/已支付/已退款」
3. 点击「已支付」: `page.click('[data-testid="filter-order-status"] [data-value="paid"]')`
4. 验证列表只显示 paid 状态订单
5. 验证每行状态标签为绿色「已支付」
6. 点击「已退款」: `page.click('[data-testid="filter-order-status"] [data-value="refunded"]')`
7. 验证列表只显示 refunded 状态订单
8. 验证每行状态标签为红色「已退款」
9. 点击「全部」恢复

**期望结果**:
- 筛选器有4个选项
- 筛选结果准确
- 状态标签颜色对应正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-10-S1 | 筛选pending | 有5笔pending | 选待支付 | 仅显示5笔 |
| UI-W-10-S2 | 筛选paid | 有10笔paid | 选已支付 | 仅显示10笔 |
| UI-W-10-S3 | 筛选refunded | 有3笔refunded | 选已退款 | 仅显示3笔 |
| UI-W-10-S4 | 切回全部 | 已筛选 | 选全部 | 显示全部18笔 |

---

### UI-W-11: 核销台 (A08)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 有买家 13812345678 购买了服务商品, entitlement 有效, 剩余次数=2

**页面**: `/shop/verifications`
**路由**: `/shop/verifications`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/verifications
2. 等待 `[data-testid="verification-container"]` 可见
3. 验证手机号输入框: `page.locator('[data-testid="input-verify-mobile"]')` 可见
4. 输入买家手机号: `page.fill('[data-testid="input-verify-mobile"]', '13812345678')`
5. 点击查询: `page.click('[data-testid="btn-verify-query"]')`
6. 验证查询结果显示: `page.locator('[data-testid="verify-result"]')` 可见
7. 验证结果显示: 买家姓名、商品名、剩余次数=2
8. 点击「核销」: `page.click('[data-testid="btn-verify-confirm"]')`
9. 验证核销成功提示: `page.locator('[data-testid="verify-success-toast"]')` 可见
10. 验证剩余次数更新为1
11. 再次核销, 验证剩余次数变为0, 状态变为 expired

**期望结果**:
- 手机号查询返回有效 entitlement
- 核销后次数递减
- 次数耗尽后 entitlement 状态变 expired
- API POST /api/v1/shop/verifications 返回 200

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-11-S1 | 正常核销 | 剩余2次 | 核销1次 | 剩余1次 |
| UI-W-11-S2 | 最后一次核销 | 剩余1次 | 核销1次 | 剩余0次, status=expired |
| UI-W-11-S3 | 无效手机号 | 手机号不存在 | 查询 | 显示「未找到可核销权益」 |
| UI-W-11-S4 | 已过期权益 | entitlement expired | 查询 | 显示「权益已过期」 |
| UI-W-11-S5 | 手机号格式错误 | 输入'123' | 查询 | 校验错误 |

---

### UI-W-12: 支付配置 - 保存 (A15)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 尚未配置支付信息

**页面**: `/shop/payment-config`
**路由**: `/shop/payment-config`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/payment-config
2. 等待 `[data-testid="payment-config-form"]` 可见
3. 填写微信支付商户号: `page.fill('[data-testid="input-wx-mch-id"]', '1234567890')`
4. 填写 API 密钥: `page.fill('[data-testid="input-wx-api-key"]', 'test_api_key_32_characters_xx')`
5. 上传证书文件: `page.setInputFiles('[data-testid="upload-wx-cert"]', 'tests/fixtures/cert.pem')`
6. 填写回调URL: `page.fill('[data-testid="input-wx-notify-url"]', 'https://example.com/api/v1/payment/wx/notify')`
7. 点击保存: `page.click('[data-testid="btn-save-payment-config"]')`
8. 等待成功提示: `page.locator('[data-testid="save-success-toast"]')` 可见

**期望结果**:
- 保存成功
- API POST /api/v1/shop/payment-config 返回 201
- 数据库 wx_api_key 存储为密文 (AES-256-GCM)
- 数据库 wx_cert_pem 存储为密文

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-12-S1 | 正常保存 | 无配置 | 填写并保存 | 成功, 密钥加密存储 |
| UI-W-12-S2 | 商户号为空 | mch_id留空 | 保存 | 校验错误 |
| UI-W-12-S3 | API密钥太短 | key='123' | 保存 | 校验错误「密钥至少32位」 |
| UI-W-12-S4 | 证书未上传 | 无文件 | 保存 | 校验错误 |
| UI-W-12-S5 | 更新配置 | 已有配置 | 修改后保存 | 成功更新 |

---

### UI-W-13: 支付配置 - 测试连通性 (A15)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 已保存支付配置 (WECHAT_PAY_MODE=stub)

**页面**: `/shop/payment-config`
**路由**: `/shop/payment-config`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/payment-config
2. 等待已保存的配置加载 (字段有值)
3. 验证「测试连通性」按钮: `page.locator('[data-testid="btn-test-connectivity"]')` 可见且 enabled
4. 点击「测试连通性」: `page.click('[data-testid="btn-test-connectivity"]')`
5. 等待结果: `page.locator('[data-testid="connectivity-result"]')` 可见
6. 验证结果显示「连通正常」(stub 模式下返回成功)
7. 验证 API 调用 POST /api/v1/shop/payment-config/test 返回 200

**期望结果**:
- 测试连通性按钮可点击
- stub 模式返回连通正常
- 结果区域显示成功状态

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-13-S1 | stub模式连通 | WECHAT_PAY_MODE=stub | 测试 | 显示「连通正常」 |
| UI-W-13-S2 | 未保存配置 | 无配置 | 测试 | 按钮不可点击 |
| UI-W-13-S3 | 配置已修改未保存 | 修改了字段 | 测试 | 提示「请先保存配置」 |

---

### UI-W-14: 套餐权益展示 (A18)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 商家已开通 basic 套餐, 到期日为 2026-12-31

**页面**: `/shop/subscription`
**路由**: `/shop/subscription`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/subscription
2. 等待 `[data-testid="subscription-container"]` 可见
3. 验证套餐名称: `page.locator('[data-testid="plan-name"]')` 文本为「基础版」
4. 验证到期日: `page.locator('[data-testid="plan-expire-date"]')` 文本为「2026-12-31」
5. 验证权益列表: `page.locator('[data-testid^="entitlement-item-"]')` 数量 > 0
6. 验证权益项包含: 商品上限、订单上限、核销次数等
7. 验证「升级套餐」按钮: `page.locator('[data-testid="btn-upgrade-plan"]')` 可见
8. 验证到期天数提醒 (如果 <=7天显示红色)

**期望结果**:
- 套餐名称正确显示
- 到期日正确
- 权益列表完整展示
- 升级按钮可见

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-14-S1 | basic套餐 | basic, 到期>7天 | 访问 | 套餐名+权益列表 |
| UI-W-14-S2 | 即将到期 | 到期<=7天 | 访问 | 红色到期提醒 |
| UI-W-14-S3 | standard套餐 | standard | 访问 | 显示standard权益 |
| UI-W-14-S4 | 无套餐 | 未开通 | 访问 | 显示「未开通套餐」+开通按钮 |

---

### UI-W-15: 商品审核状态标签

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 数据库有不同状态商品各1个

**页面**: `/shop/products`
**路由**: `/shop/products`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/products
2. 等待列表加载完成
3. 对每个商品卡片验证状态标签:
   - draft: `page.locator('[data-testid="product-status-tag"][data-status="draft"]')` 文本「草稿」, 灰色
   - under_review: 文本「审核中」, 灰色
   - on_sale: 文本「在售」, 绿色
   - rejected: 文本「已驳回」, 红色
4. 验证标签颜色通过 CSS class 或 style 属性判断

**期望结果**:
- draft → 灰色「草稿」
- under_review → 灰色「审核中」
- on_sale → 绿色「在售」
- rejected → 红色「已驳回」

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-15-S1 | draft标签 | status=draft | 检查 | 灰色「草稿」 |
| UI-W-15-S2 | on_sale标签 | status=on_sale | 检查 | 绿色「在售」 |
| UI-W-15-S3 | rejected标签 | status=rejected | 检查 | 红色「已驳回」 |
| UI-W-15-S4 | under_review标签 | status=under_review | 检查 | 灰色「审核中」 |

---

### UI-W-16-N: 平台端 - 商家列表 (P02)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 数据库有商家: 3个active, 2个pending, 1个suspended, 1个closed, 2个expiring_soon

**页面**: `/admin/shop/merchants`
**路由**: `/admin/shop/merchants`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/merchants
2. 等待 `[data-testid="admin-merchants-container"]` 可见
3. 验证商家列表渲染: `page.locator('[data-testid^="merchant-row-"]')` 数量 > 0
4. 验证每行包含: 商家名、状态标签、套餐名、到期日、续费待办标识
5. 验证状态标签颜色:
   - active=绿色, pending=灰色, suspended=黄色, closed=红色, expiring_soon=黄色(<=7天红色)
6. 验证续费待办标识: `page.locator('[data-testid="renewal-badge"]')` 在 expiring_soon/closed 商家行可见
7. 验证状态筛选器: `page.locator('[data-testid="filter-merchant-status"]')`
8. 验证搜索框: `page.locator('[data-testid="input-search-merchant"]')`
9. 输入搜索关键词: `page.fill('[data-testid="input-search-merchant"]', '测试')` 并验证结果过滤

**期望结果**:
- 商家列表正确渲染
- 状态标签颜色符合规范
- 续费待办标识正确显示
- 搜索和筛选功能正常

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-16-N-S1 | 筛选active | 3个active | 选active | 仅显示3个 |
| UI-W-16-N-S2 | 搜索商家名 | 有匹配 | 输入关键词 | 返回匹配结果 |
| UI-W-16-N-S3 | expiring_soon | 到期<=7天 | 检查标签 | 红色标签 |
| UI-W-16-N-S4 | 续费待办 | 即将到期 | 检查行 | 显示续费待办badge |

---

### UI-W-17-N: 平台端 - 商家列表续费待办 (P02)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 有2个商家套餐即将到期 (<=7天), 1个已过期

**页面**: `/admin/shop/merchants`
**路由**: `/admin/shop/merchants`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/merchants
2. 验证续费待办筛选: `page.click('[data-testid="filter-renewal-pending"]')`
3. 验证列表只显示有续费待办的商家
4. 验证每行有「续费」按钮: `page.locator('[data-testid="btn-renew-merchant"]')`
5. 点击「续费」按钮: `page.click('[data-testid="btn-renew-merchant"]')`
6. 验证跳转到订阅开通页面或弹窗

**期望结果**:
- 续费待办筛选准确
- 即将到期商家显示续费按钮
- 点击续费跳转正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-17-N-S1 | 7天内到期 | 到期=5天后 | 检查 | 显示续费待办 |
| UI-W-17-N-S2 | 已过期 | 到期=昨天 | 检查 | 显示续费待办+红色 |
| UI-W-17-N-S3 | 远未到期 | 到期=30天后 | 检查 | 无续费待办 |

---

### UI-W-18-N: 平台端 - 入驻审核通过 (P03)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 有1个 pending 入驻申请 (applicant: 13900000077)

**页面**: `/admin/shop/onboarding`
**路由**: `/admin/shop/onboarding`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/onboarding
2. 等待 `[data-testid="onboarding-review-container"]` 可见
3. 验证待审核列表: `page.locator('[data-testid^="onboarding-application-"]')` 数量 >= 1
4. 点击第一条申请: `page.click('[data-testid^="onboarding-application-"] >> nth=0')`
5. 验证详情展开: `page.locator('[data-testid="onboarding-detail-panel"]')` 可见
6. 验证详情内容: 店铺名、类目、营业执照图片、法人信息(id_no脱敏)
7. 验证「通过」按钮: `page.locator('[data-testid="btn-approve-onboarding"]')` 可见
8. 点击「通过」: `page.click('[data-testid="btn-approve-onboarding"]')`
9. 验证确认弹窗: `page.locator('[data-testid="confirm-approve-dialog"]')` 可见
10. 确认通过: `page.click('[data-testid="btn-confirm-approve"]')`
11. 验证成功提示
12. 验证 API POST /api/v1/admin/shop/onboarding/{id}/approve 返回 200
13. 验证数据库 merchant 表新增记录, status=active

**期望结果**:
- 审核通过后创建 merchant 记录
- merchant.status=active
- 申请状态变为 approved
- 页面刷新后该申请从待审核列表消失

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-18-N-S1 | 正常通过 | pending申请 | 点通过+确认 | merchant创建, status=active |
| UI-W-18-N-S2 | 已通过申请 | approved | 检查 | 不在待审核列表 |
| UI-W-18-N-S3 | 已驳回申请 | rejected | 检查 | 不在待审核列表 |

---

### UI-W-19-N: 平台端 - 入驻审核驳回 (P03)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 有1个 pending 入驻申请

**页面**: `/admin/shop/onboarding`
**路由**: `/admin/shop/onboarding`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/onboarding
2. 点击第一条待审核申请
3. 验证「驳回」按钮: `page.locator('[data-testid="btn-reject-onboarding"]')` 可见
4. 点击「驳回」: `page.click('[data-testid="btn-reject-onboarding"]')`
5. 验证驳回原因输入框: `page.locator('[data-testid="input-reject-reason"]')` 可见
6. 输入驳回原因: `page.fill('[data-testid="input-reject-reason"]', '营业执照信息不完整，请补充')`
7. 提交驳回: `page.click('[data-testid="btn-confirm-reject"]')`
8. 验证成功提示
9. 验证 API POST /api/v1/admin/shop/onboarding/{id}/reject 返回 200
10. 验证申请状态变为 rejected, reject_reason 有值

**期望结果**:
- 驳回需填写原因
- 驳回原因 >= 4字 (表单校验)
- 申请状态变为 rejected
- 驳回原因留痕

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-19-N-S1 | 正常驳回 | pending | 填原因+驳回 | rejected + 原因留痕 |
| UI-W-19-N-S2 | 原因太短 | 原因='不' | 提交 | 校验错误「驳回原因至少4个字」 |
| UI-W-19-N-S3 | 原因为空 | 不填 | 提交 | 校验错误 |

---

### UI-W-20-N: 平台端 - 套餐配置 (P10)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 已有3档套餐模板: basic/standard/premium

**页面**: `/admin/shop/plans`
**路由**: `/admin/shop/plans`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/plans
2. 等待 `[data-testid="plans-config-container"]` 可见
3. 验证3档套餐模板卡片: `page.locator('[data-testid^="plan-card-"]')` 数量 = 3
4. 验证 basic 卡片: 名称、价格、权益项列表
5. 点击 basic 卡片编辑: `page.click('[data-testid="plan-card-basic"] [data-testid="btn-edit-plan"]')`
6. 验证编辑表单: `page.locator('[data-testid="plan-edit-form"]')` 可见
7. 修改商品上限: `page.fill('[data-testid="input-plan-product-limit"]', '50')`
8. 添加权益项: `page.click('[data-testid="btn-add-entitlement-item"]')`
9. 填写权益项名称: `page.fill('[data-testid="entitlement-item-name-0"]', '短信通知')`
10. 保存: `page.click('[data-testid="btn-save-plan"]')`
11. 验证成功提示

**期望结果**:
- 3档套餐模板显示
- 编辑功能正常
- 权益项可增删
- 保存成功

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|20-N-S1 | 编辑basic | basic存在 | 修改+保存 | 更新成功 |
| UI-W-20-N-S2 | 权益项名称校验 | 添加权益项 | 名称为空 | 校验错误 |
| UI-W-20-N-S3 | 价格为0 | 修改价格=0 | 保存 | 校验错误「价格必须大于0」 |

---

### UI-W-21-N: 平台端 - 套餐配置3档模板验证 (P10)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）

**页面**: `/admin/shop/plans`
**路由**: `/admin/shop/plans`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/plans
2. 验证 basic 套餐: 价格 < standard < premium
3. 验证各套餐权益项数量: basic < standard < premium
4. 验证 basic 权益: 商品上限20, 订单上限1000/月, 短信100条/月
5. 验证 standard 权益: 商品上限100, 订单上限5000/月, 短信500条/月
6. 验证 premium 权益: 商品上限不限, 订单上限不限, 短信2000条/月

**期望结果**:
- 3档套餐层级递进
- 权益项随套餐升级增加
- 各套餐权益配置正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-21-N-S1 | basic权益 | basic模板 | 检查 | 商品20/订单1000/短信100 |
| UI-W-21-N-S2 | standard权益 | standard模板 | 检查 | 商品100/订单5000/短信500 |
| UI-W-21-N-S3 | premium权益 | premium模板 | 检查 | 不限/不限/短信2000 |

---

### UI-W-22-N: 平台端 - 订阅开通 (P11)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 有1个商家未开通套餐

**页面**: `/admin/shop/subscriptions`
**路由**: `/admin/shop/subscriptions`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/subscriptions
2. 等待 `[data-testid="subscription-create-container"]` 可见
3. 选择商家: `page.click('[data-testid="select-merchant"]')` → 选择目标商家
4. 选择套餐: `page.click('[data-testid="select-plan"]')` → 选择「standard」
5. 设置有效期: `page.fill('[data-testid="input-subscription-duration"]', '12')` (月)
6. 点击开通: `page.click('[data-testid="btn-create-subscription"]')`
7. 验证成功提示
8. 验证 API POST /api/v1/admin/shop/subscriptions 返回 201
9. 验证数据库 subscription 记录, status=active

**期望结果**:
- 订阅开通成功
- subscription.status=active
- 套餐权益生效

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-22-N-S1 | 开通basic | 未开通 | 选basic+开通 | 成功, status=active |
| UI-W-22-N-S2 | 重复开通 | 已有active | 再次开通 | 422「已有有效订阅」 |
| UI-W-22-N-S3 | 未选商家 | 商家为空 | 开通 | 校验错误 |

---

### UI-W-23-N: 平台端 - 商品审核通过 (P09)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 有1个 under_review 商品

**页面**: `/admin/shop/products/review`
**路由**: `/admin/shop/products/review`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/products/review
2. 等待 `[data-testid="product-review-container"]` 可见
3. 验证待审核列表: `page.locator('[data-testid^="review-product-"]')` 数量 >= 1
4. 点击第一条: `page.click('[data-testid^="review-product-"] >> nth=0')`
5. 验证详情: 商品名、类型、价格、课程编排/文件信息
6. 验证「通过」按钮: `page.locator('[data-testid="btn-approve-product"]')` 可见
7. 点击「通过」: `page.click('[data-testid="btn-approve-product"]')`
8. 确认: `page.click('[data-testid="btn-confirm-approve-product"]')`
9. 验证 API POST /api/v1/admin/shop/products/{id}/approve 返回 200
10. 验证商品状态变为 on_sale

**期望结果**:
- 审核通过后商品 status=on_sale
- 商品可在小程序上架

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-23-N-S1 | 正常通过 | under_review | 通过 | status=on_sale |
| UI-W-23-N-S2 | 已通过商品 | on_sale | 检查 | 不在待审列表 |

---

### UI-W-24-N: 平台端 - 商品审核驳回 (P09)

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 有1个 under_review 商品

**页面**: `/admin/shop/products/review`
**路由**: `/admin/shop/products/review`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/products/review
2. 点击第一条待审核商品
3. 点击「驳回」: `page.click('[data-testid="btn-reject-product"]')`
4. 验证驳回原因输入框可见
5. 输入原因: `page.fill('[data-testid="input-product-reject-reason"]', '商品描述不符合规范，请修改后重新提交')`
6. 提交: `page.click('[data-testid="btn-confirm-reject-product"]')`
7. 验证 API POST /api/v1/admin/shop/products/{id}/reject 返回 200
8. 验证商品状态变为 rejected, reject_reason 有值

**期望结果**:
- 驳回需填写原因 (>= 4字)
- 商品状态变为 rejected
- 驳回原因留痕

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-24-N-S1 | 正常驳回 | under_review | 填原因+驳回 | rejected + 原因 |
| UI-W-24-N-S2 | 原因太短 | 原因='不' | 提交 | 校验错误 |

---

### UI-W-25-N: 分页 - 下拉切换

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 数据库有 55 条商品

**页面**: `/shop/products`
**路由**: `/shop/products`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/products
2. 验证默认 page_size=20: 列表显示20条, 分页器显示共3页
3. 点击分页大小下拉: `page.click('[data-testid="select-page-size"]')`
4. 验证选项: 10/20/50/100
5. 选择50: `page.click('[data-testid="select-page-size"] [data-value="50"]')`
6. 验证列表显示50条, 分页器显示共2页
7. 选择100: `page.click('[data-testid="select-page-size"] [data-value="100"]')`
8. 验证列表显示55条 (不足100全部显示), 分页器显示共1页
9. 选择10: `page.click('[data-testid="select-page-size"] [data-value="10"]')`
10. 验证列表显示10条, 分页器显示共6页

**期望结果**:
- 默认 page_size=20
- 可切换 10/20/50/100
- 切换后列表数量和分页器正确更新

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-25-N-S1 | 默认20 | 55条 | 访问 | 显示20条, 3页 |
| UI-W-25-N-S2 | 切换10 | 55条 | 选10 | 显示10条, 6页 |
| UI-W-25-N-S3 | 切换50 | 55条 | 选50 | 显示50条, 2页 |
| UI-W-25-N-S4 | 切换100 | 55条 | 选100 | 显示55条, 1页 |

---

### UI-W-26-N: CSV 导出

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 数据库有 120 条订单

**页面**: `/shop/orders`
**路由**: `/shop/orders`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/orders
2. 验证「导出CSV」按钮: `page.locator('[data-testid="btn-export-csv"]')` 可见
3. 点击导出: `page.click('[data-testid="btn-export-csv"]')`
4. 验证下载开始 (Playwright download 事件)
5. 验证 API GET /api/v1/shop/orders/export?format=csv 返回 200, Content-Type=text/csv
6. 验证 CSV 行数 <= 5000
7. 验证 CSV 中买家手机号脱敏

**期望结果**:
- CSV 导出成功
- 行数 <= 5000
- 买家手机号在 CSV 中脱敏

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-26-N-S1 | 正常导出 | 120条 | 导出 | CSV 120行+表头 |
| UI-W-26-N-S2 | 超过5000条 | 5500条 | 导出 | 仅导出5000条 |
| UI-W-26-N-S3 | 空数据 | 0条 | 导出 | CSV仅表头或提示无数据 |
| UI-W-26-N-S4 | 筛选后导出 | 筛选paid | 导出 | CSV仅含paid订单 |

---

### UI-W-27-N: 表单验证 - 手机号格式

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）

**页面**: `/shop/verifications`
**路由**: `/shop/verifications`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/verifications
2. 输入手机号 '123': `page.fill('[data-testid="input-verify-mobile"]', '123')`
3. 点击查询: `page.click('[data-testid="btn-verify-query"]')`
4. 验证校验错误: `page.locator('[data-testid="mobile-error-msg"]')` 显示「手机号格式不正确」
5. 输入手机号 '1381234567' (10位): 验证校验错误
6. 输入手机号 '138123456789' (12位): 验证校验错误
7. 输入手机号 '23812345678' (非1开头): 验证校验错误
8. 输入手机号 '13812345678' (正确): 验证无校验错误, 可查询

**期望结果**:
- 手机号必须 11 位, 匹配 ^1\d{10}$
- 错误时显示校验提示
- 正确时可正常查询

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-27-N-S1 | 3位手机号 | 空 | 输入'123' | 校验错误 |
| UI-W-27-N-S2 | 10位手机号 | 空 | 输入'1381234567' | 校验错误 |
| UI-W-27-N-S3 | 12位手机号 | 空 | 输入'138123456789' | 校验错误 |
| UI-W-27-N-S4 | 非1开头 | 空 | 输入'23812345678' | 校验错误 |
| UI-W-27-N-S5 | 正确11位 | 空 | 输入'13812345678' | 通过校验 |

---

### UI-W-28-N: 状态标签颜色验证

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录（手机号: 13800000000, 密码: admin123456）
- 数据库有各状态商家记录

**页面**: `/admin/shop/merchants`
**路由**: `/admin/shop/merchants`

**测试步骤**:
1. 导航到 http://localhost:5173/admin/shop/merchants
2. 找到 active 商家行, 验证状态标签 CSS:
   - `page.locator('[data-testid="merchant-status-tag"][data-status="active"]')` 有绿色 class (如 `bg-green-100 text-green-700`)
3. 找到 pending 商家行, 验证灰色标签
4. 找到 suspended 商家行, 验证黄色标签
5. 找到 closed 商家行, 验证红色标签
6. 找到 expiring_soon (<=7天) 商家行, 验证红色标签
7. 找到 expiring_soon (>7天) 商家行, 验证黄色标签

**期望结果**:
- active → 绿色
- pending → 灰色
- suspended → 黄色
- closed → 红色
- expiring_soon <=7天 → 红色
- expiring_soon >7天 → 黄色

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-28-N-S1 | active颜色 | status=active | 检查CSS | 绿色 |
| UI-W-28-N-S2 | pending颜色 | status=pending | 检查CSS | 灰色 |
| UI-W-28-N-S3 | suspended颜色 | status=suspended | 检查CSS | 黄色 |
| UI-W-28-N-S4 | closed颜色 | status=closed | 检查CSS | 红色 |
| UI-W-28-N-S5 | expiring<=7天 | 到期=3天 | 检查CSS | 红色 |
| UI-W-28-N-S6 | expiring>7天 | 到期=10天 | 检查CSS | 黄色 |

---

### UI-W-29-N: 店员绑定店铺唯一性

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 已入驻商家用户已登录（手机号: 13900000088, 密码: test123456）
- 该用户已绑定店铺A

**页面**: `/shop/settings`
**路由**: `/shop/settings`

**测试步骤**:
1. 导航到 http://localhost:5173/shop/settings
2. 验证当前绑定店铺显示: `page.locator('[data-testid="current-shop-binding"]')` 显示店铺A
3. 尝试绑定店铺B: `page.click('[data-testid="btn-bind-shop"]')`
4. 输入店铺B邀请码: `page.fill('[data-testid="input-shop-invite-code"]', 'SHOP_B_CODE')`
5. 点击确认绑定: `page.click('[data-testid="btn-confirm-bind"]')`
6. 验证错误提示: `page.locator('[data-testid="bind-error-toast"]')` 显示「已绑定店铺，无法重复绑定」
7. 验证 API POST /api/v1/shop/staff/bind 返回 422

**期望结果**:
- 店员已绑定店铺时, 重复绑定返回 422
- 页面显示错误提示

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-29-N-S1 | 已绑定再绑 | 已绑店铺A | 绑店铺B | 422错误 |
| UI-W-29-N-S2 | 未绑定首次绑 | 未绑定 | 绑店铺A | 成功绑定 |

---

### UI-W-30-N: 权限隔离 - 跨店访问

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- 商家A用户已登录（手机号: 13900000088, 密码: test123456, 绑定店铺A）
- 数据库有店铺A和店铺B, 各有商品

**页面**: `/shop/products`
**路由**: `/shop/products`

**测试步骤**:
1. 以商家A身份登录
2. 导航到 http://localhost:5173/shop/products
3. 验证仅显示店铺A的商品
4. 尝试通过 URL 直接访问店铺B商品详情: 导航到 `http://localhost:5173/shop/products/edit?id=SHOP_B_PRODUCT_ID`
5. 验证页面显示404或403提示: `page.locator('[data-testid="error-forbidden"]')` 或 `[data-testid="error-not-found"]` 可见
6. 验证 API GET /api/v1/shop/products/{SHOP_B_PRODUCT_ID} 返回 403 或 404

**期望结果**:
- 商家A只能看到店铺A的商品
- 访问店铺B商品返回 403/404
- 页面显示错误提示

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-W-30-N-S1 | A访问A商品 | A绑定A店 | 访问A商品 | 正常显示 |
| UI-W-30-N-S2 | A访问B商品 | A绑定A店 | 访问B商品 | 403/404 |
| UI-W-30-N-S3 | A访问B订单 | A绑定A店 | 访问B订单 | 403/404 |

---

## Round 3: Mini-Program UI 测试用例

> 覆盖小程序 H5 模式全部页面，共 20 个用例 (10 existing + 10 new)
> 测试框架: Playwright Chromium headless, H5 模式
> 视口: 375×812 (iPhone X 尺寸)
> 前端: uni-app dev server at localhost:5174

---

### UI-M-01: 店铺首页 (M02)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174, H5 mode)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录（手机号: 13700000000, 密码: buyer123456）
- 店铺A有5个 on_sale 商品 (3课程, 1资料, 1服务)

**页面**: `pages/shop/index`
**路由**: `http://localhost:5174/#/pages/shop/index?shop_id=SHOP_A_ID`

**测试步骤**:
1. 导航到 `http://localhost:5174/#/pages/shop/index?shop_id=SHOP_A_ID`
2. 等待 `[data-testid="mp-shop-index"]` 可见
3. 验证店铺名称显示: `page.locator('[data-testid="mp-shop-name"]')` 有值
4. 验证在售商品列表: `page.locator('[data-testid^="mp-product-card-"]')` 数量 = 5
5. 验证每个卡片包含: 商品图片、名称、价格、类型标签
6. 验证课程商品价格显示「¥99.00」格式
7. 验证搜索框存在: `page.locator('[data-testid="mp-search-input"]')` 可见

**期望结果**:
- 店铺首页正确渲染
- 5个在售商品卡片显示
- 搜索框可见
- 商品信息完整

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-01-S1 | 有5个商品 | 5个on_sale | 访问 | 显示5个卡片 |
| UI-M-01-S2 | 无商品 | 0个on_sale | 访问 | 显示空状态 |
| UI-M-01-S3 | 含下架商品 | 3on_sale+2draft | 访问 | 仅显示3个 |
| UI-M-01-S4 | 店铺不存在 | 无效shop_id | 访问 | 显示「店铺不存在」 |

---

### UI-M-02: 店铺首页 - 搜索框

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 店铺A有商品: 「Python入门课程」「Java高级教程」「设计资料包」

**页面**: `pages/shop/index`
**路由**: `http://localhost:5174/#/pages/shop/index?shop_id=SHOP_A_ID`

**测试步骤**:
1. 导航到店铺首页
2. 点击搜索框: `page.click('[data-testid="mp-search-input"]')`
3. 输入关键词: `page.fill('[data-testid="mp-search-input"]', 'Python')`
4. 点击搜索或回车: `page.press('[data-testid="mp-search-input"]', 'Enter')`
5. 验证搜索结果: `page.locator('[data-testid^="mp-product-card-"]')` 仅显示含「Python」的商品
6. 清空搜索: `page.fill('[data-testid="mp-search-input"]', '')`
7. 验证恢复全部商品显示
8. 搜索不存在关键词: `page.fill('[data-testid="mp-search-input"]', '不存在商品')`
9. 验证显示「未找到相关商品」

**期望结果**:
- 搜索功能正常
- 关键词匹配商品名称
- 空搜索恢复全部
- 无结果显示提示

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-02-S1 | 搜索Python | 有Python商品 | 输入Python | 显示1个结果 |
| UI-M-02-S2 | 搜索空 | 有结果 | 清空 | 恢复全部 |
| UI-M-02-S3 | 无匹配 | 输入不存在 | 搜索 | 显示无结果 |
| UI-M-02-S4 | 搜索Java | 有Java商品 | 输入Java | 显示1个结果 |

---

### UI-M-03: 商品详情 (M03)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 有1个 on_sale 课程商品 (id=PRODUCT_001, name='Python入门课程', price=99.00, 含3课时, 1课时试看)

**页面**: `pages/shop/product`
**路由**: `http://localhost:5174/#/pages/shop/product?id=PRODUCT_001`

**测试步骤**:
1. 导航到商品详情页
2. 等待 `[data-testid="mp-product-detail"]` 可见
3. 验证商品名称: `page.locator('[data-testid="mp-product-name"]')` 文本为「Python入门课程」
4. 验证商品价格: `page.locator('[data-testid="mp-product-price"]')` 文本为「¥99.00」
5. 验证商品描述: `page.locator('[data-testid="mp-product-desc"]')` 可见
6. 验证课时列表: `page.locator('[data-testid^="mp-lesson-item-"]')` 数量 = 3
7. 验证试看标记: `page.locator('[data-testid="mp-lesson-item-0"][data-preview="true"]')` 有试看标识
8. 验证「立即购买」按钮: `page.locator('[data-testid="mp-btn-buy"]')` 可见且 enabled
9. 验证「试看」按钮: `page.locator('[data-testid="mp-btn-preview-lesson"]')` 可见

**期望结果**:
- 商品详情完整展示
- 价格正确
- 课时列表展示
- 试看标记正确
- 购买和试看按钮可见

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-03-S1 | 课程商品 | on_sale课程 | 访问 | 显示课时列表 |
| UI-M-03-S2 | 资料商品 | on_sale资料 | 访问 | 显示文件信息, 无课时 |
| UI-M-03-S3 | 服务商品 | on_sale服务 | 访问 | 显示次数信息 |
| UI-M-03-S4 | 下架商品 | status=draft | 访问 | 显示「商品已下架」 |
| UI-M-03-S5 | 不存在商品 | 无效id | 访问 | 显示「商品不存在」 |

---

### UI-M-04: 商品详情 - 试看课时

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 课程商品有3课时, 课时1可试看 (preview=true), 课时2/3不可试看

**页面**: `pages/shop/product`
**路由**: `http://localhost:5174/#/pages/shop/product?id=PRODUCT_001`

**测试步骤**:
1. 导航到商品详情页
2. 验证课时1有「试看」标签: `page.locator('[data-testid="mp-lesson-item-0"] [data-testid="mp-preview-tag"]')` 可见
3. 点击课时1的「试看」: `page.click('[data-testid="mp-lesson-item-0"] [data-testid="mp-btn-preview"]')`
4. 验证视频播放器出现: `page.locator('[data-testid="mp-video-player"]')` 可见
5. 验证视频开始播放 (video 元素 readyState > 0)
6. 关闭播放器: `page.click('[data-testid="mp-btn-close-video"]')`
7. 验证课时2无试看标签: `page.locator('[data-testid="mp-lesson-item-1"] [data-testid="mp-preview-tag"]')` 不存在
8. 点击课时2: 验证提示「购买后可查看」

**期望结果**:
- 试看课时可播放视频
- 非试看课时提示购买
- 视频播放器正常关闭

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-04-S1 | 试看课时1 | preview=true | 点击试看 | 视频播放 |
| UI-M-04-S2 | 非试看课时2 | preview=false | 点击 | 提示购买 |
| UI-M-04-S3 | 关闭播放器 | 播放中 | 点关闭 | 播放器消失 |
| UI-M-04-S4 | 无试看课时 | 全部不可试看 | 检查 | 无试看标签 |

---

### UI-M-05: 下单支付 - 确认 (M04)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录（手机号: 13700000000, 密码: buyer123456）
- 课程商品 PRODUCT_001 价格 ¥99.00

**页面**: `pages/shop/checkout`
**路由**: `http://localhost:5174/#/pages/shop/checkout?product_id=PRODUCT_001`

**测试步骤**:
1. 从商品详情页点击「立即购买」: `page.click('[data-testid="mp-btn-buy"]')`
2. 验证跳转到结算页: URL 包含 `pages/shop/checkout`
3. 等待 `[data-testid="mp-checkout-container"]` 可见
4. 验证商品信息: `page.locator('[data-testid="mp-checkout-product-name"]')` 显示「Python入门课程」
5. 验证价格: `page.locator('[data-testid="mp-checkout-price"]')` 显示「¥99.00」
6. 验证买家手机号(脱敏): `page.locator('[data-testid="mp-checkout-buyer-mobile"]')` 显示「137****0000」
7. 验证「确认支付」按钮: `page.locator('[data-testid="mp-btn-confirm-pay"]')` 可见且 enabled
8. 验证支付方式显示微信支付

**期望结果**:
- 结算页正确显示商品信息
- 价格正确
- 买家手机号脱敏
- 确认支付按钮可用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-05-S1 | 正常结算 | on_sale商品 | 进入结算 | 显示完整信息 |
| UI-M-05-S2 | 免费商品 | price=0 | 进入结算 | 显示¥0.00 |
| UI-M-05-S3 | 未登录 | 未登录 | 点击购买 | 跳转登录页 |

---

### UI-M-06: 下单支付 - 支付stub (M04)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- WECHAT_PAY_MODE=stub
- 已进入结算页

**页面**: `pages/shop/checkout`
**路由**: `http://localhost:5174/#/pages/shop/checkout?product_id=PRODUCT_001`

**测试步骤**:
1. 在结算页点击「确认支付」: `page.click('[data-testid="mp-btn-confirm-pay"]')`
2. 验证 API POST /api/v1/shop/orders 返回 201, body 包含 order_no
3. 验证 API POST /api/v1/shop/orders/{order_no}/prepay 返回 200, body.prepay_id 以 `wx_stub_` 开头
4. 验证页面显示支付中状态: `page.locator('[data-testid="mp-paying-status"]')` 可见
5. 验证 stub 模式自动触发回调: 等待3秒
6. 验证 API GET /api/v1/shop/orders/{order_no} 返回 status=paid

**期望结果**:
- 订单创建成功 (201)
- prepay_id 以 wx_stub_ 开头
- stub 自动完成支付
- 订单状态变为 paid

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-06-S1 | stub支付 | WECHAT_PAY_MODE=stub | 确认支付 | 自动完成, status=paid |
| UI-M-06-S2 | 重复提交 | 支付中 | 再次点击 | 按钮禁用, 防重复 |

---

### UI-M-07: 下单支付 - 成功 (M04)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- WECHAT_PAY_MODE=stub
- 订单已创建并进入支付流程

**页面**: `pages/shop/checkout`
**路由**: `http://localhost:5174/#/pages/shop/checkout`

**测试步骤**:
1. 确认支付后等待支付完成
2. 验证跳转到支付成功页: `page.locator('[data-testid="mp-pay-success"]')` 可见
3. 验证成功提示: 文本包含「支付成功」
4. 验证订单号显示: `page.locator('[data-testid="mp-success-order-no"]')` 有值
5. 验证「查看订单」按钮: `page.locator('[data-testid="mp-btn-view-orders"]')` 可见
6. 验证「继续学习」按钮: `page.locator('[data-testid="mp-btn-continue-learn"]')` 可见
7. 点击「查看订单」: 验证跳转到订单列表
8. 验证 API GET /api/v1/shop/orders/{order_no} 返回 status=paid, entitlement_id 有值

**期望结果**:
- 支付成功页正确显示
- 订单状态为 paid
- entitlement 已创建 (status=active)
- 可跳转到订单列表或学习页

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-07-S1 | 支付成功 | stub模式 | 等待完成 | 成功页显示 |
| UI-M-07-S2 | 查看订单 | 成功页 | 点击查看 | 跳转订单列表 |
| UI-M-07-S3 | 继续学习 | 成功页 | 点击学习 | 跳转学习页 |

---

### UI-M-08: 我的订单 - 列表 (M11)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 买家有订单: 3笔paid, 2笔pending, 1笔refunded

**页面**: `pages/shop/orders`
**路由**: `http://localhost:5174/#/pages/shop/orders`

**测试步骤**:
1. 导航到 `http://localhost:5174/#/pages/shop/orders`
2. 等待 `[data-testid="mp-orders-list"]` 可见
3. 验证订单列表渲染: `page.locator('[data-testid^="mp-order-item-"]')` 数量 = 6
4. 验证每个订单项包含: 商品名、金额、状态标签、下单时间
5. 验证状态标签: paid=绿色「已支付」, pending=灰色「待支付」, refunded=红色「已退款」
6. 验证分页/滚动加载: 滚动到底部加载更多 (如果 >20 条)
7. 点击第一笔订单: 验证跳转到订单详情

**期望结果**:
- 订单列表正确渲染
- 状态标签颜色正确
- 可点击查看详情

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-08-S1 | 6笔订单 | 3paid+2pending+1refunded | 访问 | 显示6条 |
| UI-M-08-S2 | 空列表 | 0笔 | 访问 | 显示空状态 |
| UI-M-08-S3 | 滚动加载 | 25笔 | 滚动 | 加载更多 |

---

### UI-M-09: 我的订单 - 状态标签

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 买家有不同状态订单

**页面**: `pages/shop/orders`
**路由**: `http://localhost:5174/#/pages/shop/orders`

**测试步骤**:
1. 导航到订单列表
2. 验证状态筛选标签栏: `page.locator('[data-testid="mp-order-status-tabs"]')` 可见
3. 验证标签: 全部/待支付/已支付/已退款
4. 点击「待支付」: `page.click('[data-testid="mp-order-tab-pending"]')`
5. 验证列表只显示 pending 订单
6. 验证每个标签的样式: 选中态有底部高亮线
7. 点击「已退款」: 验证列表只显示 refunded 订单
8. 点击「全部」: 验证恢复全部订单

**期望结果**:
- 状态标签筛选功能正常
- 选中态有视觉反馈
- 筛选结果准确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-09-S1 | 筛选pending | 有2笔pending | 选待支付 | 仅显示2笔 |
| UI-M-09-S2 | 筛选paid | 有3笔paid | 选已支付 | 仅显示3笔 |
| UI-M-09-S3 | 筛选refunded | 有1笔refunded | 选已退款 | 仅显示1笔 |
| UI-M-09-S4 | 全部 | 已筛选 | 选全部 | 恢复全部 |

---

### UI-M-10: 已购列表 - 分类 (M06)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 买家有已购: 2个课程, 1个资料, 1个服务

**页面**: `pages/shop/entitlements`
**路由**: `http://localhost:5174/#/pages/shop/entitlements`

**测试步骤**:
1. 导航到 `http://localhost:5174/#/pages/shop/entitlements`
2. 等待 `[data-testid="mp-entitlements-container"]` 可见
3. 验证分类标签: 课程/资料/服务
4. 验证「全部」分类显示4个权益: `page.locator('[data-testid^="mp-entitlement-item-"]')` 数量 = 4
5. 点击「课程」: `page.click('[data-testid="mp-entitlement-tab-course"]')`
6. 验证仅显示2个课程权益
7. 点击「资料」: `page.click('[data-testid="mp-entitlement-tab-material"]')`
8. 验证仅显示1个资料权益
9. 点击「服务」: `page.click('[data-testid="mp-entitlement-tab-service"]')`
10. 验证仅显示1个服务权益, 含剩余次数

**期望结果**:
- 已购列表分类正确
- 课程/资料/服务分类切换准确
- 服务权益显示剩余次数

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-10-S1 | 全部 | 4个权益 | 默认 | 显示4个 |
| UI-M-10-S2 | 课程分类 | 2课程 | 选课程 | 显示2个 |
| UI-M-10-S3 | 资料分类 | 1资料 | 选资料 | 显示1个 |
| UI-M-10-S4 | 服务分类 | 1服务 | 选服务 | 显示1个+次数 |
| UI-M-10-S5 | 空列表 | 0权益 | 访问 | 显示空状态 |

---

### UI-M-11-N: 已购列表 - 多店合并

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 买家在店铺A购买了1个课程, 在店铺B购买了1个课程

**页面**: `pages/shop/entitlements`
**路由**: `http://localhost:5174/#/pages/shop/entitlements`

**测试步骤**:
1. 导航到已购列表
2. 验证列表显示2个课程权益 (来自不同店铺)
3. 验证每个权益项显示来源店铺名: `page.locator('[data-testid^="mp-entitlement-item-"] [data-testid="mp-shop-name-tag"]')`
4. 验证权益1来自店铺A, 权益2来自店铺B
5. 验证两个权益都可点击进入学习页

**期望结果**:
- 多店权益合并展示
- 每个权益显示来源店铺
- 不同店权益均可学习

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-11-N-S1 | 两店各1课程 | A+B各1 | 访问 | 合并显示2个 |
| UI-M-11-N-S2 | 三店各1课程 | A+B+C各1 | 访问 | 合并显示3个 |
| UI-M-11-N-S3 | 单店多课程 | A店2课程 | 访问 | 显示2个, 同店 |

---

### UI-M-12-N: 课程学习 - 视频 (M07)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 买家有1个课程权益 (3课时), entitlement.status=active

**页面**: `pages/shop/learn`
**路由**: `http://localhost:5174/#/pages/shop/learn?entitlement_id=ENT_001`

**测试步骤**:
1. 导航到学习页
2. 等待 `[data-testid="mp-learn-container"]` 可见
3. 验证视频播放器: `page.locator('[data-testid="mp-learn-video-player"]')` 可见
4. 验证默认加载第一课时视频
5. 点击播放: `page.click('[data-testid="mp-learn-video-play"]')`
6. 验证视频开始播放 (currentTime > 0)
7. 验证播放进度条可见: `page.locator('[data-testid="mp-learn-video-progress"]')` 可见
8. 验证可暂停: `page.click('[data-testid="mp-learn-video-pause"]')` (如有)

**期望结果**:
- 视频播放器正常渲染
- 默认加载第一课时
- 播放/暂停功能正常
- 进度条可见

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-12-N-S1 | 正常播放 | active权益 | 播放 | 视频播放 |
| UI-M-12-N-S2 | 暂停 | 播放中 | 暂停 | 视频暂停 |
| UI-M-12-N-S3 | 权益已撤销 | revoked | 访问 | 显示「权益已失效」 |

---

### UI-M-13-N: 课程学习 - 课时列表

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 课程有3课时, 买家已学习课时1 (progress=100%), 课时2未学

**页面**: `pages/shop/learn`
**路由**: `http://localhost:5174/#/pages/shop/learn?entitlement_id=ENT_001`

**测试步骤**:
1. 导航到学习页
2. 验证课时列表: `page.locator('[data-testid^="mp-learn-lesson-"]')` 数量 = 3
3. 验证课时1有已完成标记: `page.locator('[data-testid="mp-learn-lesson-0"]')` 有完成图标
4. 验证课时2无完成标记
5. 点击课时2: `page.click('[data-testid="mp-learn-lesson-1"]')`
6. 验证视频切换到课时2
7. 验证课时列表高亮当前课时

**期望结果**:
- 课时列表完整显示
- 已学课时有完成标记
- 可切换课时
- 当前课时高亮

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-13-N-S1 | 课时1已完成 | progress=100% | 检查 | 有完成标记 |
| UI-M-13-N-S2 | 切换课时2 | 课时1播放中 | 点击课时2 | 视频切换 |
| UI-M-13-N-S3 | 全部已完成 | 3课时都100% | 检查 | 全部有完成标记 |

---

### UI-M-14-N: 课程学习 - 进度

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 课程3课时, 课时1完成100%, 课时2完成50%, 课时3未学

**页面**: `pages/shop/learn`
**路由**: `http://localhost:5174/#/pages/shop/learn?entitlement_id=ENT_001`

**测试步骤**:
1. 导航到学习页
2. 验证整体进度: `page.locator('[data-testid="mp-learn-overall-progress"]')` 显示「50%」(1.5/3)
3. 播放课时2视频至结束
4. 验证 API POST /api/v1/shop/entitlements/{id}/progress 被调用
5. 验证课时2完成标记出现
6. 验证整体进度更新为「67%」(2/3)
7. 播放课时3视频至结束
8. 验证整体进度更新为「100%」
9. 验证显示「课程已完成」提示

**期望结果**:
- 进度实时更新
- 课时完成后标记出现
- 整体进度正确计算
- 全部完成有提示

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-14-N-S1 | 50%进度 | 1.5/3完成 | 检查 | 显示50% |
| UI-M-14-N-S2 | 完成课时2 | 课时2=50% | 看完 | 升至67% |
| UI-M-14-N-S3 | 全部完成 | 3/3 | 检查 | 100%+完成提示 |
| UI-M-14-N-S4 | 中途退出 | 课时2=30% | 退出再进 | 从30%继续 |

---

### UI-M-15-N: 预约服务 (M10)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 买家购买了服务商品, entitlement剩余次数=2
- 商家设置了可预约时段: 周一至周五 10:00-12:00, 14:00-18:00

**页面**: `pages/shop/booking`
**路由**: `http://localhost:5174/#/pages/shop/booking?entitlement_id=ENT_SERVICE_001`

**测试步骤**:
1. 导航到预约页
2. 等待 `[data-testid="mp-booking-container"]` 可见
3. 验证日期选择器: `page.locator('[data-testid="mp-booking-calendar"]')` 可见
4. 选择明天日期: `page.click('[data-testid="mp-booking-date-tomorrow"]')`
5. 验证可选时段显示: `page.locator('[data-testid^="mp-booking-slot-"]')` 数量 > 0
6. 选择 10:00-12:00 时段: `page.click('[data-testid="mp-booking-slot-0"]')`
7. 验证「确认预约」按钮可点击: `page.locator('[data-testid="mp-btn-confirm-booking"]')` enabled
8. 点击确认预约: `page.click('[data-testid="mp-btn-confirm-booking"]')`
9. 验证成功提示: `page.locator('[data-testid="mp-booking-success"]')` 可见
10. 验证 API POST /api/v1/shop/bookings 返回 201

**期望结果**:
- 日历和时段选择正常
- 预约成功后创建预约记录
- entitlement 剩余次数不变 (核销时才扣减)

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-15-N-S1 | 正常预约 | 剩余2次 | 选日期+时段+确认 | 预约成功 |
| UI-M-15-N-S2 | 时段已满 | 时段已被预约 | 选择该时段 | 显示「已满」不可选 |
| UI-M-15-N-S3 | 过去日期 | 昨天日期 | 检查 | 不可选 |
| UI-M-15-N-S4 | 无可用时段 | 商家未设置 | 检查 | 显示「暂无可预约时段」 |

---

### UI-M-16-N: 发票申请 - 个人 (M13)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 有1笔 paid 订单未开票

**页面**: `pages/shop/invoice`
**路由**: `http://localhost:5174/#/pages/shop/invoice?order_no=TEST_ORDER_001`

**测试步骤**:
1. 导航到发票申请页
2. 等待 `[data-testid="mp-invoice-form"]` 可见
3. 选择发票类型「个人」: `page.click('[data-testid="mp-invoice-type-personal"]')`
4. 验证个人抬头输入框: `page.locator('[data-testid="mp-input-invoice-title"]')` 可见
5. 填写抬头: `page.fill('[data-testid="mp-input-invoice-title"]', '张三')`
6. 填写接收邮箱: `page.fill('[data-testid="mp-input-invoice-email"]', 'zhangsan@example.com')`
7. 点击提交: `page.click('[data-testid="mp-btn-submit-invoice"]')`
8. 验证成功提示: `page.locator('[data-testid="mp-invoice-success"]')` 可见
9. 验证 API POST /api/v1/shop/invoices 返回 201

**期望结果**:
- 个人发票可申请
- 抬头和邮箱必填
- 提交成功

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-16-N-S1 | 正常申请 | paid未开票 | 填写+提交 | 成功 |
| UI-M-16-N-S2 | 抬头为空 | 空 | 提交 | 校验错误 |
| UI-M-16-N-S3 | 邮箱格式错误 | 'abc' | 提交 | 校验错误 |
| UI-M-16-N-S4 | 已开票订单 | 已开票 | 访问 | 显示已开票状态 |

---

### UI-M-17-N: 发票申请 - 企业 (M13)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 有1笔 paid 订单未开票

**页面**: `pages/shop/invoice`
**路由**: `http://localhost:5174/#/pages/shop/invoice?order_no=TEST_ORDER_001`

**测试步骤**:
1. 导航到发票申请页
2. 选择发票类型「企业」: `page.click('[data-testid="mp-invoice-type-enterprise"]')`
3. 验证企业字段出现: 公司名称、税号、地址、电话、开户行、账号
4. 填写公司名称: `page.fill('[data-testid="mp-input-company-name"]', '测试科技有限公司')`
5. 填写税号: `page.fill('[data-testid="mp-input-tax-no"]', '91110108MA01XX1234')`
6. 填写接收邮箱: `page.fill('[data-testid="mp-input-invoice-email"]', 'finance@example.com')`
7. 点击提交: `page.click('[data-testid="mp-btn-submit-invoice"]')`
8. 验证成功提示
9. 验证 API POST /api/v1/shop/invoices 返回 201, body.invoice_type='enterprise'

**期望结果**:
- 企业发票可申请
- 企业专属字段显示
- 税号必填
- 提交成功

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-17-N-S1 | 正常企业发票 | paid未开票 | 填写+提交 | 成功 |
| UI-M-17-N-S2 | 税号为空 | 空 | 提交 | 校验错误 |
| UI-M-17-N-S3 | 税号格式错误 | '123' | 提交 | 校验错误 |
| UI-M-17-N-S4 | 公司名为空 | 空 | 提交 | 校验错误 |

---

### UI-M-18-N: 领权页 (M14)

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 有1个 claim_pending 订单, claim_token 有效
- 短信链接格式: `http://localhost:5174/#/pages/shop/claim?token=CLAIM_TOKEN_001`

**页面**: `pages/shop/claim`
**路由**: `http://localhost:5174/#/pages/shop/claim?token=CLAIM_TOKEN_001`

**测试步骤**:
1. 导航到领权页 (带 claim_token)
2. 等待 `[data-testid="mp-claim-container"]` 可见
3. 验证商品信息显示: `page.locator('[data-testid="mp-claim-product-name"]')` 有值
4. 验证需要确认手机号: `page.locator('[data-testid="mp-claim-mobile-input"]')` 可见
5. 输入手机号: `page.fill('[data-testid="mp-claim-mobile-input"]', '13700000000')`
6. 点击「确认领权」: `page.click('[data-testid="mp-btn-confirm-claim"]')`
7. 验证成功提示: `page.locator('[data-testid="mp-claim-success"]')` 可见
8. 验证 API POST /api/v1/shop/claims/confirm 返回 200
9. 验证订单状态变为 paid, entitlement 创建 (status=active)

**期望结果**:
- 领权页正确显示商品信息
- 需确认手机号
- 领权成功后创建权益
- 订单从 claim_pending 变为 paid

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-18-N-S1 | 正常领权 | token有效 | 确认 | 成功+权益创建 |
| UI-M-18-N-S2 | 无效token | token不存在 | 访问 | 显示「链接无效」 |
| UI-M-18-N-S3 | 已领权 | token已使用 | 访问 | 显示「已领取」 |
| UI-M-18-N-S4 | 手机号不匹配 | 输入错误手机 | 确认 | 错误提示 |
| UI-M-18-N-S5 | token过期 | token已过期 | 访问 | 显示「链接已过期」 |

---

### UI-M-19-N: 商家暂停 - 已购不阻断

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 店铺A merchant.status=suspended
- 买家在店铺A有1个 active 课程权益

**页面**: `pages/shop/learn`
**路由**: `http://localhost:5174/#/pages/shop/learn?entitlement_id=ENT_001`

**测试步骤**:
1. 导航到已购列表
2. 验证已购列表仍显示店铺A的权益
3. 点击进入学习页
4. 验证学习页正常加载, 视频可播放
5. 验证 API GET /api/v1/shop/entitlements 返回 200 (不受商家暂停影响)
6. 验证 API GET /api/v1/shop/entitlements/{id} 返回 200
7. 尝试在店铺A首页新购商品: 导航到 `pages/shop/index?shop_id=SHOP_A_ID`
8. 验证新购被拦截: 显示「店铺已暂停营业」或购买按钮禁用

**期望结果**:
- 已购权益不受商家暂停影响, 可继续学习
- 新购被拦截
- 店铺首页显示暂停状态

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-19-N-S1 | 已购学习 | suspended | 学习 | 正常学习 |
| UI-M-19-N-S2 | 新购拦截 | suspended | 购买 | 被拦截 |
| UI-M-19-N-S3 | 店铺首页 | suspended | 访问 | 显示暂停 |
| UI-M-19-N-S4 | closed商家 | closed | 学习 | 正常学习(已购) |

---

### UI-M-20-N: 视口适配

**前置条件**:
- uni-app dev server 已启动 (apps/mp, port 5174)
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录

**页面**: 多页面
**路由**: 多路由

**测试步骤**:
1. 设置视口为 375×812 (iPhone X)
2. 导航到店铺首页, 验证无水平滚动条
3. 验证商品卡片宽度适配 (2列布局或1列)
4. 导航到商品详情, 验证内容不溢出
5. 导航到结算页, 验证表单元素宽度适配
6. 导航到学习页, 验证视频播放器宽度 100%
7. 设置视口为 320×568 (iPhone SE)
8. 重复步骤2-6, 验证小屏适配
9. 设置视口为 414×896 (iPhone XR)
10. 重复步骤2-6, 验证大屏适配
11. 检查所有页面无内容溢出、无水平滚动条

**期望结果**:
- 各尺寸视口下页面正常显示
- 无水平滚动条
- 元素宽度自适应
- 按钮可点击区域 >= 44px

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| UI-M-20-N-S1 | iPhone X | 375×812 | 检查 | 无溢出 |
| UI-M-20-N-S2 | iPhone SE | 320×568 | 检查 | 无溢出 |
| UI-M-20-N-S3 | iPhone XR | 414×896 | 检查 | 无溢出 |
| UI-M-20-N-S4 | 横屏 | 812×375 | 检查 | 布局调整 |

---

## Round 4: E2E 集成测试用例

> 覆盖 F0-F12 全流程端到端集成, 共 30 个用例 (13 existing + 17 new)
> 测试框架: pytest + httpx (API 调用) + Playwright (UI 交互)
> API: localhost:8000

---

### E2E-01: F0 入驻全流程 - 管家代建

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- WECHAT_PAY_MODE=stub, DOUYIN_WEBHOOK_MODE=stub, SMS_MODE=stub
- 管家账号已登录 (agent token: AGENT_TOKEN_001)
- 未入驻商家用户存在 (13900000099)

**测试步骤**:

```
Step 1: 管家创建预入驻记录
  POST /api/v1/agent/shop/onboarding/pre-create
  Headers: Authorization: Bearer AGENT_TOKEN_001
  Body: { "contact_name": "张三", "contact_mobile": "13900000099", "shop_name": "测试内容商城" }
  Assert: 201, body.id 非空, body.status='pre_created'

Step 2: 管家上传营业执照 (OCR)
  POST /api/v1/agent/shop/onboarding/{id}/upload-license
  Headers: Authorization: Bearer AGENT_TOKEN_001
  Body: multipart/form-data, file=license.png
  Assert: 200, body.ocr_result.company_name 非空, body.ocr_result.legal_person 非空

Step 3: 提交入驻申请
  POST /api/v1/agent/shop/onboarding/{id}/submit
  Headers: Authorization: Bearer AGENT_TOKEN_001
  Assert: 200, body.status='pending'

Step 4: 平台管理员审核通过
  POST /api/v1/admin/shop/onboarding/{id}/approve
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200, body.merchant_id 非空

Step 5: 验证 merchant 记录创建
  GET /api/v1/admin/shop/merchants/{merchant_id}
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200, body.status='active', body.shop_name='测试内容商城'
```

**期望结果**:
- 预入驻记录创建成功
- OCR 识别营业执照信息
- 审核通过后创建 merchant 记录 (status=active)
- merchant.contact_name='张三', contact_mobile 脱敏存储

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-01-S1 | 正常全流程 | 管家已登录 | 5步全通 | merchant创建 |
| E2E-01-S2 | 重复提交 | 已pending | 再次submit | 422 |
| E2E-01-S3 | 非管家角色 | buyer token | pre-create | 403 |

---

### E2E-02: F0 OCR 营业执照识别

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 管家账号已登录
- 测试图片: tests/fixtures/license.png (含公司名、法人、统一社会信用代码)

**测试步骤**:

```
Step 1: 上传营业执照
  POST /api/v1/agent/shop/onboarding/{id}/upload-license
  Headers: Authorization: Bearer AGENT_TOKEN_001
  Body: multipart/form-data, file=license.png
  Assert: 200

Step 2: 验证 OCR 结果
  Assert: body.ocr_result.company_name = '测试科技有限公司'
  Assert: body.ocr_result.legal_person = '张三'
  Assert: body.ocr_result.credit_code = '91110108MA01XX1234'
  Assert: body.ocr_result.business_scope 非空

Step 3: 验证 OCR 结果自动填充
  GET /api/v1/agent/shop/onboarding/{id}
  Assert: body.company_name = '测试科技有限公司'
  Assert: body.legal_person = '张三'
```

**期望结果**:
- OCR 正确识别公司名、法人、信用代码
- 识别结果自动填充到入驻申请

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-02-S1 | 正常OCR | 清晰图片 | 上传 | 识别成功 |
| E2E-02-S2 | 模糊图片 | 模糊license | 上传 | OCR部分失败, 提示手动填写 |
| E2E-02-S3 | 非图片文件 | txt文件 | 上传 | 400 错误 |

---

### E2E-03: F0 P03 审核通过 - merchant 创建

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录
- 有1个 pending 入驻申请

**测试步骤**:

```
Step 1: 获取待审核列表
  GET /api/v1/admin/shop/onboarding?status=pending
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200, body.items 数量 >= 1

Step 2: 查看申请详情
  GET /api/v1/admin/shop/onboarding/{id}
  Assert: 200, body.status='pending'

Step 3: 审核通过
  POST /api/v1/admin/shop/onboarding/{id}/approve
  Body: { "note": "材料齐全，审核通过" }
  Assert: 200, body.merchant_id 非空

Step 4: 验证 merchant 创建
  GET /api/v1/admin/shop/merchants/{merchant_id}
  Assert: 200, body.status='active', body.shop_name 非空

Step 5: 验证申请状态更新
  GET /api/v1/admin/shop/onboarding/{id}
  Assert: body.status='approved', body.reviewed_by 非空, body.reviewed_at 非空

Step 6: 验证用户已关联 merchant
  GET /api/v1/shop/profile
  Headers: Authorization: Bearer MERCHANT_TOKEN (13900000099)
  Assert: 200, body.merchant_id = {merchant_id}
```

**期望结果**:
- 审核通过后自动创建 merchant (status=active)
- 申请状态变为 approved
- 用户自动关联 merchant

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-03-S1 | 正常通过 | pending | approve | merchant创建 |
| E2E-03-S2 | 已通过再审 | approved | approve | 422 |
| E2E-03-S3 | 非管理员 | merchant token | approve | 403 |

---

### E2E-04: F0 A20 自申对比

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家用户已登录 (13900000099)
- 该用户已有管家代建的入驻记录 (status=approved, merchant已创建)

**测试步骤**:

```
Step 1: 商家自申入驻 (已有merchant)
  POST /api/v1/shop/onboarding
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "shop_name": "自申店铺", "contact_name": "张三", "contact_mobile": "13900000099", ... }
  Assert: 422 或 200 (根据业务逻辑, 已有merchant时处理)

Step 2: 对比管家代建 vs 自申信息
  GET /api/v1/shop/onboarding/self
  Assert: 返回已有入驻信息, 含管家代建标记

Step 3: 验证信息一致性
  Assert: contact_name 与管家代建一致
  Assert: contact_mobile 脱敏一致
```

**期望结果**:
- 已有 merchant 的用户不可重复申请
- 自申信息与管家代建信息可对比
- 脱敏显示一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-04-S1 | 已有merchant | approved | 自申 | 422或显示已有 |
| E2E-04-S2 | 无merchant | 无记录 | 自申 | 正常创建申请 |

---

### E2E-05: F1 私域支付开权 - 下单

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录 (13700000000)
- 店铺A有1个 on_sale 课程商品 (PRODUCT_001, price=99.00)
- WECHAT_PAY_MODE=stub

**测试步骤**:

```
Step 1: 获取商品信息
  GET /api/v1/shop/products/PRODUCT_001
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200, body.status='on_sale', body.price=99.00

Step 2: 创建订单
  POST /api/v1/shop/orders
  Headers: Authorization: Bearer BUYER_TOKEN
  Body: { "product_id": "PRODUCT_001", "quantity": 1 }
  Assert: 201, body.order_no 非空, body.status='pending', body.amount=99.00

Step 3: 验证订单详情
  GET /api/v1/shop/orders/{order_no}
  Assert: 200, body.status='pending', body.product.name='Python入门课程'
```

**期望结果**:
- 订单创建成功, status=pending
- 订单金额正确
- 订单关联正确的商品

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-05-S1 | 正常下单 | on_sale | 创建 | 201 |
| E2E-05-S2 | 下架商品 | draft | 创建 | 422 |
| E2E-05-S3 | 重复下单 | 已有pending | 创建 | 允许(多个pending) |

---

### E2E-06: F1 私域支付开权 - prepay

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 买家用户已登录
- 已创建订单 (order_no=TEST_ORDER_001, status=pending)
- WECHAT_PAY_MODE=stub

**测试步骤**:

```
Step 1: 调用预下单
  POST /api/v1/shop/orders/TEST_ORDER_001/prepay
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200, body.prepay_id 以 'wx_stub_' 开头
  Assert: body.nonce_str 非空
  Assert: body.sign 非空

Step 2: 验证订单状态未变
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='pending' (prepay不改变状态)

Step 3: 验证 prepay 记录
  GET /api/v1/shop/orders/TEST_ORDER_001/prepay-records
  Assert: body.items[-1].prepay_id 以 'wx_stub_' 开头
```

**期望结果**:
- prepay 返回 wx_stub_ 前缀的 prepay_id
- 订单状态仍为 pending
- prepay 记录留痕

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-06-S1 | 正常prepay | pending | prepay | wx_stub_ prepay_id |
| E2E-06-S2 | 已paid订单 | paid | prepay | 422 |
| E2E-06-S3 | 不存在订单 | 无效order_no | prepay | 404 |

---

### E2E-07: F1 私域支付开权 - 支付 notify

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 已创建订单并 prepay (order_no=TEST_ORDER_001)
- WECHAT_PAY_MODE=stub

**测试步骤**:

```
Step 1: stub 自动触发支付回调
  (stub 模式下, prepay 后自动调用 notify)
  Assert: 等待3秒后订单状态变为 paid

Step 2: 验证订单状态
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='paid', body.paid_at 非空

Step 3: 验证支付回调记录
  GET /api/v1/admin/shop/payments?order_no=TEST_ORDER_001
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items[0].status='success', body.items[0].transaction_id 非空

Step 4: 手动模拟回调验签
  POST /api/v1/payment/wx/notify
  Body: { "out_trade_no": "TEST_ORDER_001", "transaction_id": "wx_stub_tx_001", "sign": "valid_test_sign" }
  Assert: 200 (幂等, 不重复处理)

Step 5: 验签失败
  POST /api/v1/payment/wx/notify
  Body: { "out_trade_no": "TEST_ORDER_001", "sign": "invalid_sign" }
  Assert: 400
```

**期望结果**:
- 支付回调后订单 status=paid
- 支付记录留痕 (transaction_id)
- 回调幂等 (重复不处理)
- 验签失败返回 400

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-07-S1 | 正常回调 | pending | notify | status=paid |
| E2E-07-S2 | 重复回调 | 已paid | notify | 幂等, 200 |
| E2E-07-S3 | 验签失败 | pending | 错误sign | 400 |

---

### E2E-08: F1 entitlement active

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 订单已支付 (TEST_ORDER_001, status=paid)

**测试步骤**:

```
Step 1: 验证 entitlement 自动创建
  GET /api/v1/shop/entitlements?order_no=TEST_ORDER_001
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200, body.items 数量 = 1
  Assert: body.items[0].status='active'
  Assert: body.items[0].product_id='PRODUCT_001'
  Assert: body.items[0].buyer_id 非空

Step 2: 验证 entitlement 详情
  GET /api/v1/shop/entitlements/{entitlement_id}
  Assert: 200, body.status='active', body.activated_at 非空

Step 3: 验证权益内容
  Assert: body.product_type='course' (课程类型)
  Assert: body.lessons_count = 3 (3课时可学)
```

**期望结果**:
- 支付后自动创建 entitlement (status=active)
- entitlement 关联正确的商品和订单
- 课程类型权益包含课时信息

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-08-S1 | 课程权益 | paid课程 | 检查 | active+课时信息 |
| E2E-08-S2 | 资料权益 | paid资料 | 检查 | active+文件信息 |
| E2E-08-S3 | 服务权益 | paid服务 | 检查 | active+次数信息 |

---

### E2E-09: F1 enrollment 创建

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 订单已支付, entitlement 已创建 (课程类型)

**测试步骤**:

```
Step 1: 验证 enrollment 自动创建
  GET /api/v1/shop/entitlements/{entitlement_id}/enrollments
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200, body.items 数量 = 3 (3课时3条enrollment)

Step 2: 验证每条 enrollment
  Assert: body.items[0].status='active'
  Assert: body.items[0].progress=0 (初始进度0)
  Assert: body.items[0].lesson_id 非空

Step 3: 更新学习进度
  POST /api/v1/shop/entitlements/{entitlement_id}/progress
  Body: { "lesson_id": "LESSON_001", "progress": 50 }
  Assert: 200, body.progress=50

Step 4: 完成课时
  POST /api/v1/shop/entitlements/{entitlement_id}/progress
  Body: { "lesson_id": "LESSON_001", "progress": 100 }
  Assert: 200, body.status='completed'
```

**期望结果**:
- 支付后自动创建 enrollment (每课时1条)
- enrollment 初始 status=active, progress=0
- 可更新进度
- progress=100 时 status=completed

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-09-S1 | 3课时 | active | 检查 | 3条enrollment |
| E2E-09-S2 | 更新进度 | progress=0 | 更新50% | progress=50 |
| E2E-09-S3 | 完成课时 | progress=50 | 更新100% | status=completed |

---

### E2E-10: F2 退款关权

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 订单已支付 (TEST_ORDER_001, status=paid)
- entitlement 已创建 (status=active)
- enrollment 已创建 (3条, status=active)
- 商家已登录

**测试步骤**:

```
Step 1: 商家发起退款
  POST /api/v1/shop/orders/TEST_ORDER_001/refund
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "reason": "买家申请退款", "amount": 99.00 }
  Assert: 200, body.status='refunding'

Step 2: 验证微信退款 (stub)
  Assert: stub 自动完成退款, 等待3秒
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='refunded', body.refunded_at 非空

Step 3: 验证 entitlement 被撤销
  GET /api/v1/shop/entitlements?order_no=TEST_ORDER_001
  Assert: body.items[0].status='revoked', body.revoked_at 非空
  Assert: body.items[0].revoke_reason='refund'

Step 4: 验证 enrollment 被撤销
  GET /api/v1/shop/entitlements/{entitlement_id}/enrollments
  Assert: 所有 enrollment status='revoked'

Step 5: 验证买家无法继续学习
  GET /api/v1/shop/entitlements/{entitlement_id}
  Assert: body.status='revoked' (学习API应拒绝)
  POST /api/v1/shop/entitlements/{entitlement_id}/progress
  Assert: 403 (权益已撤销)
```

**期望结果**:
- 退款后订单 status=refunded
- entitlement status=revoked
- enrollment 全部 status=revoked
- 买家无法继续学习 (API 403)

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-10-S1 | 全额退款 | paid | 退款 | refunded+权益撤销 |
| E2E-10-S2 | 重复退款 | refunded | 退款 | 422 |
| E2E-10-S3 | pending退款 | pending | 退款 | 422 (未支付不可退) |

---

### E2E-11: F2 已开票 needs_red_flush

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 订单已支付且已开票 (invoice.status='issued')
- 即将发起退款

**测试步骤**:

```
Step 1: 验证发票已开具
  GET /api/v1/shop/invoices?order_no=TEST_ORDER_001
  Assert: body.items[0].status='issued', body.items[0].invoice_url 非空

Step 2: 发起退款
  POST /api/v1/shop/orders/TEST_ORDER_001/refund
  Body: { "reason": "买家申请退款" }
  Assert: 200

Step 3: 等待退款完成
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='refunded'

Step 4: 验证发票状态变为 needs_red_flush
  GET /api/v1/shop/invoices?order_no=TEST_ORDER_001
  Assert: body.items[0].status='needs_red_flush'
  Assert: body.items[0].red_flush_reason='refund'

Step 5: 验证商家有待处理红冲提醒
  GET /api/v1/shop/invoices?status=needs_red_flush
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.items 数量 >= 1
```

**期望结果**:
- 已开票订单退款后, 发票状态变为 needs_red_flush
- 商家有待处理红冲列表

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-11-S1 | 已开票退款 | issued | 退款 | needs_red_flush |
| E2E-11-S2 | 未开票退款 | 无发票 | 退款 | 无红冲 |
| E2E-11-S3 | 红冲完成 | needs_red_flush | 红冲 | status=red_flushed |

---

### E2E-12: F3 抖店领权 - claim_pending

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- DOUYIN_WEBHOOK_MODE=stub
- 商品已在抖店映射 (PRODUCT_001 → douyin_product_id=DY_PROD_001)

**测试步骤**:

```
Step 1: 模拟抖店下单 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.create",
    "data": {
      "douyin_order_id": "DY_ORDER_001",
      "douyin_product_id": "DY_PROD_001",
      "buyer_mobile": "13700000000",
      "amount": 9900
    }
  }
  Assert: 200

Step 2: 验证 claim_pending 订单创建
  GET /api/v1/admin/shop/orders?status=claim_pending
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items 数量 >= 1
  Assert: body.items[-1].source='douyin'
  Assert: body.items[-1].status='claim_pending'
  Assert: body.items[-1].claim_token 非空

Step 3: 验证 claim_token 生成
  Assert: claim_token 长度 >= 32 (随机安全token)
  Assert: claim_token 唯一
```

**期望结果**:
- 抖店下单 Webhook 触发 claim_pending 订单创建
- 生成唯一的 claim_token
- 订单 source='douyin'

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-12-S1 | 正常webhook | 已映射商品 | webhook | claim_pending+token |
| E2E-12-S2 | 未映射商品 | 无映射 | webhook | 拒单 |
| E2E-12-S3 | 重复webhook | 已处理 | webhook | 幂等, 200 |

---

### E2E-13: F3 抖店领权 - 短信发送

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- DOUYIN_WEBHOOK_MODE=stub, SMS_MODE=stub
- claim_pending 订单已创建 (含 claim_token)

**测试步骤**:

```
Step 1: 验证领权短信已发送
  GET /api/v1/admin/shop/sms-logs?type=claim_link&order_no=DY_ORDER_001
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items 数量 >= 1
  Assert: body.items[0].type='claim_link'
  Assert: body.items[0].mobile = '137****0000' (脱敏)
  Assert: body.items[0].content 包含 claim URL
  Assert: body.items[0].content 包含 claim_token

Step 2: 验证短信内容
  Assert: sms_log.content 包含 'http://localhost:5174/#/pages/shop/claim?token='
  Assert: sms_log.status='sent'

Step 3: 验证 stub 模式短信
  Assert: SMS_MODE=stub 时, 短信不实际发送, 仅记录 sms_log
```

**期望结果**:
- claim_pending 订单创建后自动发送领权短信
- 短信内容包含领权链接 (含 claim_token)
- sms_log 记录完整
- 手机号脱敏存储

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-13-S1 | 正常发短信 | claim_pending | 检查 | sms_log已发送 |
| E2E-13-S2 | 短信额度不足 | 额度=0 | 发送 | 422 |
| E2E-13-S3 | 重复发送 | 已发送 | 再次发送 | 幂等或允许 |

---

### E2E-14-N: F3 抖店领权 - M14 领权完成

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- claim_pending 订单已创建, 短信已发送
- claim_token 有效

**测试步骤**:

```
Step 1: 买家确认领权
  POST /api/v1/shop/claims/confirm
  Headers: Authorization: Bearer BUYER_TOKEN (或无token, 根据设计)
  Body: { "claim_token": "CLAIM_TOKEN_001", "mobile": "13700000000" }
  Assert: 200, body.order_no 非空

Step 2: 验证订单状态变为 paid
  GET /api/v1/shop/orders/{order_no}
  Assert: body.status='paid', body.source='douyin'

Step 3: 验证 entitlement 创建
  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: body.items[0].status='active'

Step 4: 验证 claim_token 失效
  POST /api/v1/shop/claims/confirm
  Body: { "claim_token": "CLAIM_TOKEN_001", "mobile": "13700000000" }
  Assert: 422 (token已使用)

Step 5: 验证买家可学习
  GET /api/v1/shop/entitlements/{entitlement_id}/enrollments
  Assert: 200, enrollment 数量 > 0, status='active'
```

**期望结果**:
- 领权成功后订单从 claim_pending 变为 paid
- entitlement 自动创建 (active)
- claim_token 使用后失效
- 买家可正常学习

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-14-N-S1 | 正常领权 | token有效 | 确认 | paid+权益创建 |
| E2E-14-N-S2 | 重复领权 | 已领权 | 确认 | 422 |
| E2E-14-N-S3 | 手机不匹配 | 错误手机 | 确认 | 422 |
| E2E-14-N-S4 | token过期 | 过期token | 确认 | 422 |

---

### E2E-15-N: F4 核销流程

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 买家购买了服务商品 (次数=3), entitlement.status=active, remaining_count=3

**测试步骤**:

```
Step 1: 预约服务
  POST /api/v1/shop/bookings
  Headers: Authorization: Bearer BUYER_TOKEN
  Body: { "entitlement_id": "ENT_SERVICE_001", "date": "2026-08-15", "slot": "10:00-12:00" }
  Assert: 201, body.id 非空, body.status='booked'

Step 2: 商家核销
  POST /api/v1/shop/verifications
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "buyer_mobile": "13700000000", "booking_id": "BOOKING_001" }
  Assert: 200, body.remaining_count=2, body.verification_id 非空

Step 3: 验证 entitlement 次数扣减
  GET /api/v1/shop/entitlements/ENT_SERVICE_001
  Assert: body.remaining_count=2

Step 4: 再次核销
  POST /api/v1/shop/verifications
  Body: { "buyer_mobile": "13700000000", "booking_id": "BOOKING_002" }
  Assert: 200, body.remaining_count=1

Step 5: 第三次核销
  POST /api/v1/shop/verifications
  Body: { "buyer_mobile": "13700000000", "booking_id": "BOOKING_003" }
  Assert: 200, body.remaining_count=0
```

**期望结果**:
- 每次核销后 remaining_count 递减
- 核销记录留痕
- 3次核销后 remaining_count=0

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-15-N-S1 | 第一次核销 | remaining=3 | 核销 | remaining=2 |
| E2E-15-N-S2 | 第二次核销 | remaining=2 | 核销 | remaining=1 |
| E2E-15-N-S3 | 第三次核销 | remaining=1 | 核销 | remaining=0 |
| E2E-15-N-S4 | 无预约核销 | 无booking | 核销 | 422 |

---

### E2E-16-N: F4 次数耗尽 expired

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 服务商品权益 remaining_count=0 (刚完成最后一次核销)

**测试步骤**:

```
Step 1: 验证 entitlement 状态变为 expired
  GET /api/v1/shop/entitlements/ENT_SERVICE_001
  Assert: body.status='expired', body.remaining_count=0
  Assert: body.expired_at 非空

Step 2: 尝试再次核销
  POST /api/v1/shop/verifications
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "buyer_mobile": "13700000000" }
  Assert: 422, body.detail='权益已用完' 或类似

Step 3: 尝试预约
  POST /api/v1/shop/bookings
  Body: { "entitlement_id": "ENT_SERVICE_001", "date": "2026-08-20", "slot": "10:00-12:00" }
  Assert: 422, body.detail='权益已过期'
```

**期望结果**:
- 次数耗尽后 entitlement status=expired
- 无法再核销或预约
- API 返回 422

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-16-N-S1 | 次数耗尽 | remaining=0 | 检查 | expired |
| E2E-16-N-S2 | 过期核销 | expired | 核销 | 422 |
| E2E-16-N-S3 | 过期预约 | expired | 预约 | 422 |

---

### E2E-17-N: F5 开票流程

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有1笔 paid 订单, 未开票

**测试步骤**:

```
Step 1: 买家申请发票
  POST /api/v1/shop/invoices
  Headers: Authorization: Bearer BUYER_TOKEN
  Body: {
    "order_no": "TEST_ORDER_001",
    "invoice_type": "personal",
    "title": "张三",
    "email": "zhangsan@example.com"
  }
  Assert: 201, body.id 非空, body.status='pending'

Step 2: 商家开具发票
  POST /api/v1/shop/invoices/{id}/issue
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 200, body.status='issued', body.invoice_url 非空

Step 3: 验证发票状态
  GET /api/v1/shop/invoices/{id}
  Assert: body.status='issued', body.invoice_url 包含 http

Step 4: 验证买家可查看发票
  GET /api/v1/shop/invoices
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: body.items[0].status='issued', body.items[0].invoice_url 非空
```

**期望结果**:
- 买家可申请发票
- 商家可开具发票 (status=issued)
- 发票 URL 生成
- 买家可查看

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-17-N-S1 | 个人发票 | paid | 申请+开具 | issued |
| E2E-17-N-S2 | 企业发票 | paid | 申请+开具 | issued |
| E2E-17-N-S3 | 重复申请 | 已有pending | 申请 | 422 |
| E2E-17-N-S4 | 非paid订单 | pending | 申请 | 422 |

---

### E2E-18-N: F5 退款后 needs_red_flush

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 订单已支付且已开票 (invoice.status='issued')

**测试步骤**:

```
Step 1: 验证发票已开具
  GET /api/v1/shop/invoices?order_no=TEST_ORDER_001
  Assert: body.items[0].status='issued'

Step 2: 发起退款
  POST /api/v1/shop/orders/TEST_ORDER_001/refund
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "reason": "买家申请退款" }
  Assert: 200

Step 3: 等待退款完成
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='refunded'

Step 4: 验证发票状态
  GET /api/v1/shop/invoices?order_no=TEST_ORDER_001
  Assert: body.items[0].status='needs_red_flush'

Step 5: 商家执行红冲
  POST /api/v1/shop/invoices/{id}/red-flush
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 200, body.status='red_flushed'
```

**期望结果**:
- 退款后发票状态变为 needs_red_flush
- 商家可执行红冲
- 红冲后 status=red_flushed

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-18-N-S1 | 已开票退款 | issued | 退款 | needs_red_flush |
| E2E-18-N-S2 | 执行红冲 | needs_red_flush | 红冲 | red_flushed |
| E2E-18-N-S3 | 未开票退款 | 无发票 | 退款 | 无红冲需求 |

---

### E2E-19-N: F6 合规机审

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有1个 under_review 商品 (含课程内容/图片/描述)

**测试步骤**:

```
Step 1: 商品提审触发机审
  POST /api/v1/shop/products/{id}/submit-review
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 200, body.status='under_review'

Step 2: 验证机审执行 (stub 6类规则)
  GET /api/v1/admin/shop/products/{id}/review-result
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.machine_review.status='completed'
  Assert: body.machine_review.rules 数量 = 6
  Assert: body.machine_review.rules 包含: 敏感词/违禁品/价格异常/图片合规/描述规范/版权

Step 3: 验证机审结果
  Assert: 各规则有 pass/flag 状态
  Assert: 如果有 flag, body.machine_review.flagged_rules 非空
```

**期望结果**:
- 提审后自动执行机审 (6类规则)
- 每类规则有明确结果 (pass/flag)
- flag 的规则有详细原因

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-19-N-S1 | 机审全通过 | 无违规 | 提审 | 6规则全pass |
| E2E-19-N-S2 | 机审flag | 含敏感词 | 提审 | 有flag+原因 |
| E2E-19-N-S3 | 6类规则 | 新商品 | 提审 | 执行6类检查 |

---

### E2E-20-N: F6 人审通过/驳回

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商品已通过机审或有 flag, 等待人审

**测试步骤**:

```
Step 1: 平台获取人审列表
  GET /api/v1/admin/shop/products/review?status=under_review
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200, body.items 数量 >= 1

Step 2: 人审通过
  POST /api/v1/admin/shop/products/{id}/approve
  Body: { "note": "内容合规" }
  Assert: 200, body.status='on_sale'

Step 3: 验证商品上架
  GET /api/v1/shop/products/{id}
  Assert: body.status='on_sale'

Step 4: (另一商品) 人审驳回
  POST /api/v1/admin/shop/products/{id2}/reject
  Body: { "reason": "课程内容不符合规范，请修改" }
  Assert: 200, body.status='rejected'

Step 5: 验证驳回原因留痕
  GET /api/v1/shop/products/{id2}
  Assert: body.status='rejected', body.reject_reason 非空
  Assert: body.reject_reason 长度 >= 4
```

**期望结果**:
- 人审通过后商品 status=on_sale
- 人审驳回后商品 status=rejected
- 驳回原因留痕 (>= 4字)

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-20-N-S1 | 人审通过 | under_review | approve | on_sale |
| E2E-20-N-S2 | 人审驳回 | under_review | reject | rejected+原因 |
| E2E-20-N-S3 | 原因太短 | under_review | reject(原因='不') | 校验失败 |

---

### E2E-21-N: F7 公域挂载闸 - 未过审拒映射

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商品 PRODUCT_001 status=under_review (未过审)
- 商家尝试将商品映射到抖店

**测试步骤**:

```
Step 1: 尝试映射未过审商品
  POST /api/v1/shop/product-mappings
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "product_id": "PRODUCT_001", "platform": "douyin", "external_product_id": "DY_PROD_001" }
  Assert: 422, body.detail 包含 '商品未通过审核'

Step 2: 验证映射未创建
  GET /api/v1/shop/product-mappings?product_id=PRODUCT_001
  Assert: body.items 数量 = 0
```

**期望结果**:
- 未过审商品不可映射到公域平台
- 返回 422 错误
- 映射记录未创建

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-21-N-S1 | 未过审映射 | under_review | 映射 | 422 |
| E2E-21-N-S2 | 草稿映射 | draft | 映射 | 422 |
| E2E-21-N-S3 | 已驳回映射 | rejected | 映射 | 422 |

---

### E2E-22-N: F7 公域挂载闸 - 过审映射成功

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商品 PRODUCT_001 status=on_sale (已过审)

**测试步骤**:

```
Step 1: 映射已过审商品
  POST /api/v1/shop/product-mappings
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "product_id": "PRODUCT_001", "platform": "douyin", "external_product_id": "DY_PROD_001" }
  Assert: 201, body.id 非空, body.status='active'

Step 2: 验证映射记录
  GET /api/v1/shop/product-mappings?product_id=PRODUCT_001
  Assert: body.items[0].platform='douyin'
  Assert: body.items[0].external_product_id='DY_PROD_001'
  Assert: body.items[0].status='active'

Step 3: 验证抖店 webhook 可路由
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.create", "data": { "douyin_product_id": "DY_PROD_001", "buyer_mobile": "13700000000", "amount": 9900 } }
  Assert: 200 (映射存在, 可创建 claim_pending 订单)
```

**期望结果**:
- 过审商品可成功映射
- 映射记录 status=active
- 抖店 webhook 可通过映射路由

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-22-N-S1 | 正常映射 | on_sale | 映射 | 201 |
| E2E-22-N-S2 | 重复映射 | 已映射 | 映射 | 422 |
| E2E-22-N-S3 | 不同平台 | on_sale | 映射到微信 | 201 |

---

### E2E-23-N: F7 强制下架

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商品已上架且有公域映射 (status=on_sale, mapping active)

**测试步骤**:

```
Step 1: 平台强制下架商品
  POST /api/v1/admin/shop/products/{id}/force-offline
  Headers: Authorization: Bearer ADMIN_TOKEN
  Body: { "reason": "收到版权投诉" }
  Assert: 200, body.status='force_offline'

Step 2: 验证商品状态
  GET /api/v1/shop/products/{id}
  Assert: body.status='force_offline'

Step 3: 验证映射被禁用
  GET /api/v1/shop/product-mappings?product_id={id}
  Assert: body.items[0].status='disabled'

Step 4: 验证买家无法购买
  POST /api/v1/shop/orders
  Headers: Authorization: Bearer BUYER_TOKEN
  Body: { "product_id": "{id}", "quantity": 1 }
  Assert: 422, body.detail 包含 '商品已下架'

Step 5: 验证抖店 webhook 拒单
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.create", "data": { "douyin_product_id": "DY_PROD_001", "buyer_mobile": "13700000000", "amount": 9900 } }
  Assert: 200 但 body.action='rejected' (拒单)

Step 6: 验证已购权益不受影响
  GET /api/v1/shop/entitlements (已购的买家)
  Assert: 已有权益 status 仍为 active
```

**期望结果**:
- 强制下架后商品 status=force_offline
- 公域映射被禁用
- 新购被拦截 (422)
- 抖店 webhook 拒单
- 已购权益不受影响

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-23-N-S1 | 强制下架 | on_sale | force-offline | force_offline |
| E2E-23-N-S2 | 下架后新购 | force_offline | 购买 | 422 |
| E2E-23-N-S3 | 下架后已购 | force_offline | 学习 | 正常 |
| E2E-23-N-S4 | 抖店拒单 | force_offline | webhook | rejected |

---

### E2E-24-N: F8 套餐叠加 - 开通 basic

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已入驻但未开通套餐
- 平台管理员已登录

**测试步骤**:

```
Step 1: 开通 basic 套餐
  POST /api/v1/admin/shop/subscriptions
  Headers: Authorization: Bearer ADMIN_TOKEN
  Body: { "merchant_id": "MERCHANT_001", "plan_code": "basic", "duration_months": 12 }
  Assert: 201, body.id 非空, body.status='active', body.plan_code='basic'

Step 2: 验证套餐权益
  GET /api/v1/shop/subscription
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.plan_name='基础版'
  Assert: body.entitlements.product_limit=20
  Assert: body.entitlements.order_limit=1000
  Assert: body.expire_date 非空 (12个月后)
```

**期望结果**:
- basic 套餐开通成功
- 权益配置正确
- 到期日为12个月后

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-24-N-S1 | 开通basic | 未开通 | 开通 | active+权益 |
| E2E-24-N-S2 | 重复开通 | 已有basic | 开通 | 422 |

---

### E2E-25-N: F8 套餐叠加 - upgrade standard

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已有 basic 套餐 (status=active)

**测试步骤**:

```
Step 1: 升级到 standard 套餐
  POST /api/v1/admin/shop/subscriptions/upgrade
  Headers: Authorization: Bearer ADMIN_TOKEN
  Body: { "merchant_id": "MERCHANT_001", "new_plan_code": "standard" }
  Assert: 200, body.plan_code='standard', body.status='active'

Step 2: 验证旧套餐状态
  GET /api/v1/admin/shop/subscriptions?merchant_id=MERCHANT_001
  Assert: basic 套餐 status='upgraded'
  Assert: standard 套餐 status='active'

Step 3: 验证新权益
  GET /api/v1/shop/subscription
  Assert: body.plan_name='标准版'
  Assert: body.entitlements.product_limit=100 (升级后)
  Assert: body.entitlements.order_limit=5000

Step 4: 验证到期日延续
  Assert: body.expire_date 保持原到期日或延长
```

**期望结果**:
- 升级后 standard 套餐 active
- basic 套餐标记为 upgraded
- 权益升级
- 到期日合理处理

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-25-N-S1 | basic升级standard | basic active | upgrade | standard active |
| E2E-25-N-S2 | 降级 | standard | 降级basic | 422或允许 |
| E2E-25-N-S3 | 无套餐升级 | 无套餐 | upgrade | 422 |

---

### E2E-26-N: F8 套餐叠加 - 到期失效

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家套餐到期日为昨天 (expire_date < today)

**测试步骤**:

```
Step 1: 验证套餐已过期
  GET /api/v1/shop/subscription
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.status='expired', body.is_expired=true

Step 2: 验证功能受限
  POST /api/v1/shop/products (创建商品)
  Assert: 403, body.detail='套餐已过期'

  POST /api/v1/shop/orders (查看是否有新订单限制)
  Assert: 功能受限

Step 3: 验证已有数据不受影响
  GET /api/v1/shop/products
  Assert: 200 (可查看已有商品)

  GET /api/v1/shop/orders
  Assert: 200 (可查看已有订单)

Step 4: 续费后恢复
  POST /api/v1/admin/shop/subscriptions/renew
  Headers: Authorization: Bearer ADMIN_TOKEN
  Body: { "merchant_id": "MERCHANT_001", "duration_months": 12 }
  Assert: 200, body.status='active', body.expire_date 延长12个月
```

**期望结果**:
- 到期后套餐 status=expired
- 新增功能受限 (403)
- 已有数据可查看
- 续费后恢复

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-26-N-S1 | 到期失效 | expired | 检查 | 功能受限 |
| E2E-26-N-S2 | 到期查看 | expired | 查看商品 | 200 |
| E2E-26-N-S3 | 续费恢复 | expired | 续费 | active |

---

### E2E-27-N: F10 清结算

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 昨日有3笔 paid 订单 (merchant_id=MERCHANT_001, 总额=297.00)
- 有1笔退款 (金额=99.00)

**测试步骤**:

```
Step 1: 验证 T+1 批次生成
  GET /api/v1/admin/shop/settlement-batches?merchant_id=MERCHANT_001
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items[0].date = yesterday
  Assert: body.items[0].total_amount=297.00
  Assert: body.items[0].refund_amount=99.00
  Assert: body.items[0].net_amount=198.00
  Assert: body.items[0].status='pending'

Step 2: 验证批次包含的订单
  GET /api/v1/admin/shop/settlement-batches/{batch_id}/orders
  Assert: 订单数量=3 (paid) + 1 (refunded)

Step 3: 执行打款
  POST /api/v1/admin/shop/settlement-batches/{batch_id}/pay
  Body: { "pay_amount": 198.00, "pay_channel": "bank_transfer", "pay_ref": "BANK_TX_001" }
  Assert: 200, body.status='paid', body.paid_at 非空

Step 4: 验证打款确认
  GET /api/v1/admin/shop/settlement-batches/{batch_id}
  Assert: body.status='paid', body.pay_ref='BANK_TX_001'

Step 5: 验证退款冲正
  GET /api/v1/admin/shop/settlement-batches/{batch_id}/breakdown
  Assert: 退款订单在冲正明细中, 冲正金额=99.00
```

**期望结果**:
- T+1 自动生成结算批次
- 批次含 paid 订单总额 - 退款金额 = 净额
- 打款后 status=paid
- 退款在冲正明细中

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-27-N-S1 | T+1批次 | 昨日有订单 | 检查 | 批次自动生成 |
| E2E-27-N-S2 | 打款 | pending | pay | status=paid |
| E2E-27-N-S3 | 无订单日 | 昨日0笔 | 检查 | 无批次或空批次 |
| E2E-27-N-S4 | 全退款 | 3笔全退 | 检查 | net_amount=0 |

---

### E2E-28-N: 多店权益合并

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 买家在店铺A购买了1个课程 (entitlement active)
- 买家在店铺B购买了1个课程 (entitlement active)

**测试步骤**:

```
Step 1: 查询买家全部权益
  GET /api/v1/shop/entitlements
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200, body.items 数量 = 2
  Assert: body.items[0].merchant_id != body.items[1].merchant_id
  Assert: body.items[0].shop_name != body.items[1].shop_name

Step 2: 验证权益来自不同店铺
  Assert: body.items[0].shop_name = '店铺A'
  Assert: body.items[1].shop_name = '店铺B'

Step 3: 验证两店权益均可学习
  GET /api/v1/shop/entitlements/{ent_a_id}/enrollments
  Assert: 200, 数量 > 0

  GET /api/v1/shop/entitlements/{ent_b_id}/enrollments
  Assert: 200, 数量 > 0

Step 4: 验证进度独立
  POST /api/v1/shop/entitlements/{ent_a_id}/progress
  Body: { "lesson_id": "A_LESSON_1", "progress": 50 }
  Assert: 200

  GET /api/v1/shop/entitlements/{ent_b_id}/enrollments
  Assert: B店权益进度不受A店影响
```

**期望结果**:
- 买家多店权益合并展示
- 不同店权益独立
- 学习进度互不影响

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-28-N-S1 | 两店权益 | A+B各1 | 查询 | 合并显示2个 |
| E2E-28-N-S2 | 进度独立 | A进度50% | 检查B | B不受影响 |
| E2E-28-N-S3 | 三店 | A+B+C | 查询 | 合并显示3个 |

---

### E2E-29-N: 商家暂停 - 已购不阻断

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 店铺A merchant.status=suspended
- 买家在店铺A有1个 active 课程权益

**测试步骤**:

```
Step 1: 平台暂停商家
  POST /api/v1/admin/shop/merchants/{id}/suspend
  Headers: Authorization: Bearer ADMIN_TOKEN
  Body: { "reason": "违规操作" }
  Assert: 200, body.status='suspended'

Step 2: 验证新购被拦截
  POST /api/v1/shop/orders
  Headers: Authorization: Bearer BUYER_TOKEN
  Body: { "product_id": "PRODUCT_A_001", "quantity": 1 }
  Assert: 422, body.detail 包含 '店铺已暂停'

Step 3: 验证已购权益不受影响
  GET /api/v1/shop/entitlements
  Assert: 200, 店铺A的权益仍 active

Step 4: 验证已购可学习
  GET /api/v1/shop/entitlements/{ent_a_id}/enrollments
  Assert: 200, enrollment.status='active'

  POST /api/v1/shop/entitlements/{ent_a_id}/progress
  Body: { "lesson_id": "A_LESSON_1", "progress": 80 }
  Assert: 200 (正常更新)

Step 5: 恢复商家
  POST /api/v1/admin/shop/merchants/{id}/resume
  Assert: 200, body.status='active'

Step 6: 验证新购恢复
  POST /api/v1/shop/orders
  Body: { "product_id": "PRODUCT_A_001", "quantity": 1 }
  Assert: 201 (可正常下单)
```

**期望结果**:
- 暂停后新购被拦截 (422)
- 已购权益不受影响, 可继续学习
- 恢复后新购恢复

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-29-N-S1 | 暂停后新购 | suspended | 下单 | 422 |
| E2E-29-N-S2 | 暂停后已购 | suspended | 学习 | 正常 |
| E2E-29-N-S3 | 恢复后新购 | resumed | 下单 | 201 |
| E2E-29-N-S4 | closed商家 | closed | 学习 | 正常(已购) |

---

### E2E-30-N: Mx 端到端完整闭环 (8步全通)

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- WECHAT_PAY_MODE=stub, DOUYIN_WEBHOOK_MODE=stub, SMS_MODE=stub
- 商家已入驻, 套餐已开通
- 全链路环境就绪

**测试步骤**:

```
Step 1: 上架商品
  POST /api/v1/shop/products
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "name": "Mx闭环测试课程", "type": "course", "price": 199.00, "lessons": [...] }
  Assert: 201, body.status='draft'

  POST /api/v1/shop/products/{id}/submit-review
  Assert: 200, body.status='under_review'

  POST /api/v1/admin/shop/products/{id}/approve
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200, body.status='on_sale'

Step 2: 映射抖店
  POST /api/v1/shop/product-mappings
  Body: { "product_id": "{id}", "platform": "douyin", "external_product_id": "DY_MX_001" }
  Assert: 201

Step 3: 抖店付款 (webhook)
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.create", "data": { "douyin_product_id": "DY_MX_001", "buyer_mobile": "13700000000", "amount": 19900 } }
  Assert: 200, claim_pending 订单创建

Step 4: 领权
  POST /api/v1/shop/claims/confirm
  Body: { "claim_token": "{token}", "mobile": "13700000000" }
  Assert: 200, 订单 status='paid', entitlement 创建

Step 5: 学课
  GET /api/v1/shop/entitlements/{ent_id}/enrollments
  Assert: 200, enrollment 数量 > 0, status='active'

  POST /api/v1/shop/entitlements/{ent_id}/progress
  Body: { "lesson_id": "{lesson_id}", "progress": 100 }
  Assert: 200, status='completed'

Step 6: 退款
  POST /api/v1/shop/orders/{order_no}/refund
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "reason": "买家申请退款" }
  Assert: 200

  GET /api/v1/shop/orders/{order_no}
  Assert: body.status='refunded'

Step 7: 验证不可学
  GET /api/v1/shop/entitlements/{ent_id}
  Assert: body.status='revoked'

  POST /api/v1/shop/entitlements/{ent_id}/progress
  Assert: 403

Step 8: 验证全链路一致性
  GET /api/v1/admin/shop/orders/{order_no}
  Assert: status='refunded', entitlement.status='revoked', enrollment.status='revoked'
  Assert: 支付记录存在, 退款记录存在
```

**期望结果**:
- 8步全通: 上架 → 映射 → 抖店付款 → 领权 → 学课 → 退款 → 不可学 → 一致性验证
- 每步 API 调用成功
- 退款后权益撤销, 不可学习
- 全链路数据一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| E2E-30-N-S1 | 8步全通 | 全环境就绪 | 执行 | 全通 |
| E2E-30-N-S2 | 中途失败 | step3失败 | 检查 | 前序数据完整 |
| E2E-30-N-S3 | 退款后再学 | refunded | 学习 | 403 |

---

## Round 5: Mock 外部集成测试用例

> 覆盖微信支付 Mock / 抖店 Webhook Mock / 短信 Mock / 课程库 Mock, 共 25 个用例 (13 existing + 12 new)
> 测试框架: pytest + httpx
> 环境变量: WECHAT_PAY_MODE=stub, DOUYIN_WEBHOOK_MODE=stub, SMS_MODE=stub, COURSE_LIB_MODE=stub

---

### MOCK-01: 微信支付 Mock - 统一下单

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 环境变量: `WECHAT_PAY_MODE=stub`
- 商家已配置支付信息 (mch_id, api_key, cert)
- 买家已创建订单 (order_no=TEST_ORDER_001, status=pending)

**测试步骤**:

```
Step 1: 调用统一下单 API
  POST /api/v1/shop/orders/TEST_ORDER_001/prepay
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200

Step 2: 验证 stub 返回格式
  Assert: body.prepay_id 以 'wx_stub_' 开头
  Assert: body.prepay_id 格式: wx_stub_{order_no}_{timestamp}
  Assert: body.nonce_str 非空 (32位随机字符串)
  Assert: body.sign 非空
  Assert: body.sign_type = 'MD5'
  Assert: body.trade_type = 'JSAPI'

Step 3: 验证 stub 不实际调用微信
  Assert: 无外部 HTTP 请求发出 (通过 mock interceptor 验证)
  Assert: 响应延迟 < 100ms (stub 即时返回)

Step 4: 验证 prepay 记录写入数据库
  SELECT * FROM shop_prepay_records WHERE order_no = 'TEST_ORDER_001'
  Assert: prepay_id 以 'wx_stub_' 开头
  Assert: created_at 非空
```

**期望结果**:
- stub 模式返回 wx_stub_ 前缀的 prepay_id
- 返回格式符合微信支付 JSAPI 规范
- 无外部请求
- prepay 记录入库

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-01-S1 | stub统一下单 | WECHAT_PAY_MODE=stub | prepay | wx_stub_ prepay_id |
| MOCK-01-S2 | 格式校验 | stub返回 | 检查字段 | 符合JSAPI规范 |
| MOCK-01-S3 | 无外部请求 | stub模式 | 检查 | 无HTTP外发 |

---

### MOCK-02: 微信支付 Mock - prepay_id 格式

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 买家已创建订单

**测试步骤**:

```
Step 1: 创建多个订单并 prepay
  POST /api/v1/shop/orders (order_no=ORDER_A)
  POST /api/v1/shop/orders/ORDER_A/prepay
  Assert: body.prepay_id = 'wx_stub_ORDER_A_{timestamp}'

  POST /api/v1/shop/orders (order_no=ORDER_B)
  POST /api/v1/shop/orders/ORDER_B/prepay
  Assert: body.prepay_id = 'wx_stub_ORDER_B_{timestamp}'

Step 2: 验证 prepay_id 唯一性
  Assert: ORDER_A 的 prepay_id != ORDER_B 的 prepay_id

Step 3: 验证 prepay_id 包含 order_no
  Assert: prepay_id 包含对应 order_no

Step 4: 验证同一订单重复 prepay
  POST /api/v1/shop/orders/ORDER_A/prepay (再次)
  Assert: 200, 新的 prepay_id (timestamp 不同)
```

**期望结果**:
- prepay_id 格式: wx_stub_{order_no}_{timestamp}
- 每个订单的 prepay_id 唯一
- prepay_id 可追溯 order_no

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-02-S1 | 不同订单 | 2个订单 | prepay | prepay_id不同 |
| MOCK-02-S2 | 同订单重复 | 1个订单 | prepay2次 | 新prepay_id |
| MOCK-02-S3 | 格式验证 | stub返回 | 检查 | wx_stub_{order}_{ts} |

---

### MOCK-03: 微信支付 Mock - 回调验签

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 订单已 prepay (order_no=TEST_ORDER_001)
- 测试密钥: `TEST_SIGN_KEY`

**测试步骤**:

```
Step 1: stub 自动触发回调 (有效签名)
  (stub 模式下 prepay 后自动调用 notify, 使用测试密钥签名)
  Assert: 订单状态变为 paid

Step 2: 手动模拟回调 (正确签名)
  计算签名: sign = MD5(sorted_params + TEST_SIGN_KEY)
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "result_code": "SUCCESS",
    "sign": "{calculated_sign}"
  }
  Assert: 200 (幂等, 不重复处理)

Step 3: 验证签名验证逻辑
  Assert: 服务端使用 TEST_SIGN_KEY 验签
  Assert: 验签通过后处理业务逻辑

Step 4: 验证回调数据格式
  Assert: 回调包含 out_trade_no, transaction_id, result_code, sign
```

**期望结果**:
- stub 模式自动触发有效签名回调
- 回调验签使用测试密钥
- 验签通过后处理业务
- 回调数据格式正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-03-S1 | 正确签名 | stub自动 | 回调 | 验签通过 |
| MOCK-03-S2 | 幂等处理 | 已paid | 回调 | 200不重复 |
| MOCK-03-S3 | 签名格式 | stub返回 | 检查 | 包含sign字段 |

---

### MOCK-04: 微信支付 Mock - 退款

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 订单已支付 (status=paid)

**测试步骤**:

```
Step 1: 发起退款
  POST /api/v1/shop/orders/TEST_ORDER_001/refund
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "reason": "测试退款", "amount": 99.00 }
  Assert: 200, body.status='refunding'

Step 2: 验证 stub 退款回调
  Assert: stub 自动完成退款 (等待3秒)
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='refunded', body.refunded_at 非空

Step 3: 验证退款记录
  GET /api/v1/admin/shop/refunds?order_no=TEST_ORDER_001
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items[0].status='success'
  Assert: body.items[0].refund_id 以 'wx_stub_refund_' 开头
  Assert: body.items[0].amount=99.00

Step 4: 验证 stub 退款不实际调用微信
  Assert: 无外部 HTTP 请求
```

**期望结果**:
- stub 退款自动完成
- 退款记录包含 wx_stub_refund_ 前缀
- 无外部请求

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-04-S1 | 正常退款 | paid | 退款 | refunded |
| MOCK-04-S2 | 重复退款 | refunded | 退款 | 422 |
| MOCK-04-S3 | 部分退款 | paid=99 | 退49 | 成功(如支持) |

---

### MOCK-05: 微信支付 Mock - 查单

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 订单已支付 (status=paid, transaction_id=wx_stub_tx_001)

**测试步骤**:

```
Step 1: 调用查单 API
  GET /api/v1/shop/orders/TEST_ORDER_001/payment-status
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 200, body.trade_state='SUCCESS'
  Assert: body.transaction_id='wx_stub_tx_001'

Step 2: 验证 stub 查单返回
  Assert: body.trade_state='SUCCESS' (已支付)
  Assert: body.out_trade_no='TEST_ORDER_001'

Step 3: 未支付订单查单
  (另一订单 status=pending)
  GET /api/v1/shop/orders/ORDER_PENDING/payment-status
  Assert: 200, body.trade_state='NOTPAY'

Step 4: 已退款订单查单
  (另一订单 status=refunded)
  GET /api/v1/shop/orders/ORDER_REFUNDED/payment-status
  Assert: 200, body.trade_state='REFUND'
```

**期望结果**:
- stub 查单返回正确状态
- paid → SUCCESS, pending → NOTPAY, refunded → REFUND
- transaction_id 正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-05-S1 | 已支付查单 | paid | 查单 | SUCCESS |
| MOCK-05-S2 | 未支付查单 | pending | 查单 | NOTPAY |
| MOCK-05-S3 | 已退款查单 | refunded | 查单 | REFUND |

---

### MOCK-06: 微信支付 Mock - 验签失败 400

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 订单已 prepay (order_no=TEST_ORDER_001)

**测试步骤**:

```
Step 1: 发送错误签名的回调
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "result_code": "SUCCESS",
    "sign": "invalid_sign_xxx"
  }
  Assert: 400, body.detail 包含 '签名验证失败'

Step 2: 发送无签名的回调
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "result_code": "SUCCESS"
  }
  Assert: 400, body.detail 包含 '签名' 或 'sign'

Step 3: 发送篡改数据的回调
  计算正确签名后, 修改 amount 字段
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "total_fee": 1,  // 篡改金额
    "sign": "{原签名}"  // 用原数据计算的签名
  }
  Assert: 400 (签名不匹配)

Step 4: 验证订单状态未变
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='pending' (验签失败不影响订单)
```

**期望结果**:
- 错误签名返回 400
- 无签名返回 400
- 篡改数据签名不匹配返回 400
- 验签失败不影响订单状态

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-06-S1 | 错误签名 | pending | 回调 | 400 |
| MOCK-06-S2 | 无签名 | pending | 回调 | 400 |
| MOCK-06-S3 | 篡改数据 | pending | 回调 | 400 |
| MOCK-06-S4 | 状态不变 | 验签失败 | 检查 | 仍pending |

---

### MOCK-07: 抖店 Webhook Mock - 下单

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`
- 商品已映射 (PRODUCT_001 → DY_PROD_001)

**测试步骤**:

```
Step 1: 模拟抖店下单 Webhook
  POST /api/v1/webhooks/douyin/order
  Headers: X-Douyin-Signature: {test_signature}
  Body: {
    "event": "order.create",
    "timestamp": 1691827200,
    "data": {
      "douyin_order_id": "DY_ORDER_001",
      "douyin_product_id": "DY_PROD_001",
      "buyer_mobile": "13700000000",
      "amount": 9900,
      "pay_time": "2026-08-12 10:00:00"
    }
  }
  Assert: 200

Step 2: 验证 claim_pending 订单创建
  GET /api/v1/admin/shop/orders?source=douyin&status=claim_pending
  Assert: body.items[-1].source='douyin'
  Assert: body.items[-1].external_order_id='DY_ORDER_001'
  Assert: body.items[-1].status='claim_pending'

Step 3: 验证订单金额
  Assert: body.items[-1].amount=99.00 (9900分 → 99.00元)
```

**期望结果**:
- Webhook 正确创建 claim_pending 订单
- source='douyin', external_order_id 正确
- 金额转换正确 (分→元)

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-07-S1 | 正常webhook | 已映射 | webhook | claim_pending |
| MOCK-07-S2 | 金额转换 | 9900分 | 检查 | 99.00元 |
| MOCK-07-S3 | 缺少字段 | 无buyer_mobile | webhook | 400 |

---

### MOCK-08: 抖店 Webhook Mock - claim_pending + claim_token

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`, `SMS_MODE=stub`
- 抖店下单 Webhook 已触发

**测试步骤**:

```
Step 1: 验证 claim_token 生成
  GET /api/v1/admin/shop/orders?source=douyin&status=claim_pending
  Assert: body.items[-1].claim_token 非空
  Assert: len(claim_token) >= 32
  Assert: claim_token 是 URL-safe 字符串

Step 2: 验证 claim_token 唯一性
  (触发另一个 webhook)
  POST /api/v1/webhooks/douyin/order
  Body: { ... "douyin_order_id": "DY_ORDER_002" ... }
  Assert: 新的 claim_token != 之前的 claim_token

Step 3: 验证 claim_token 过期时间
  Assert: claim_token 有 expiry 字段
  Assert: expiry 默认 24 小时 (或配置值)

Step 4: 验证 sms_log 生成
  GET /api/v1/admin/shop/sms-logs?type=claim_link
  Assert: body.items[-1].content 包含 claim_token
  Assert: body.items[-1].mobile = '137****0000' (脱敏)
```

**期望结果**:
- claim_token 唯一, >= 32字符, URL-safe
- 有过期时间
- 短信内容包含 claim_token
- 手机号脱敏

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-08-S1 | token生成 | webhook后 | 检查 | >=32字符 |
| MOCK-08-S2 | token唯一 | 2个webhook | 检查 | 不同token |
| MOCK-08-S3 | token过期 | 过期后 | 领权 | 422 |
| MOCK-08-S4 | sms_log | webhook后 | 检查 | 含token+脱敏 |

---

### MOCK-09: 抖店 Webhook Mock - 退款

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`
- 有抖店订单已领权 (status=paid, entitlement active)

**测试步骤**:

```
Step 1: 模拟抖店退款 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.refund",
    "data": {
      "douyin_order_id": "DY_ORDER_001",
      "refund_amount": 9900,
      "refund_time": "2026-08-12 12:00:00"
    }
  }
  Assert: 200

Step 2: 验证订单状态变为 refunded
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_001
  Assert: body.items[0].status='refunded'

Step 3: 验证 entitlement 被撤销
  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: body.items[0].status='revoked'
  Assert: body.items[0].revoke_reason='douyin_refund'

Step 4: 验证 enrollment 被撤销
  GET /api/v1/shop/entitlements/{ent_id}/enrollments
  Assert: 所有 enrollment status='revoked'
```

**期望结果**:
- 退款 Webhook 后订单 status=refunded
- entitlement status=revoked
- enrollment 全部 revoked

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-09-S1 | 正常退款webhook | paid | webhook | refunded+revoked |
| MOCK-09-S2 | 已退款再退 | refunded | webhook | 幂等 |
| MOCK-09-S3 | 未领权退款 | claim_pending | webhook | refunded(无entitlement) |

---

### MOCK-10: 抖店 Webhook Mock - 重复幂等

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`
- 已处理过一次下单 Webhook (DY_ORDER_001)

**测试步骤**:

```
Step 1: 发送重复 Webhook (相同 douyin_order_id)
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.create",
    "data": { "douyin_order_id": "DY_ORDER_001", ... (与首次相同) }
  }
  Assert: 200 (幂等, 不重复创建)

Step 2: 验证未创建重复订单
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_001
  Assert: body.items 数量 = 1 (仍只有1条)

Step 3: 发送第3次重复
  POST /api/v1/webhooks/douyin/order
  Body: { ... 同上 ... }
  Assert: 200 (幂等)

Step 4: 验证 claim_token 未重新生成
  Assert: claim_token 与首次相同 (未重新生成)
```

**期望结果**:
- 重复 Webhook 幂等处理 (200)
- 不创建重复订单
- claim_token 不重新生成

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-10-S1 | 重复2次 | 已处理 | webhook | 幂等200 |
| MOCK-10-S2 | 重复3次 | 已处理2次 | webhook | 幂等200 |
| MOCK-10-S3 | 无重复订单 | 重复后 | 检查 | 仍1条 |

---

### MOCK-11: 抖店 Webhook Mock - 未映射商品拒单

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`
- 抖店商品 ID DY_UNMAPPED_001 未在系统映射

**测试步骤**:

```
Step 1: 发送未映射商品的 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.create",
    "data": {
      "douyin_order_id": "DY_ORDER_UNMAPPED_001",
      "douyin_product_id": "DY_UNMAPPED_001",
      "buyer_mobile": "13700000000",
      "amount": 9900
    }
  }
  Assert: 200, body.action='rejected'
  Assert: body.reason 包含 '商品未映射' 或 '未找到映射'

Step 2: 验证未创建订单
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_UNMAPPED_001
  Assert: body.items 数量 = 0

Step 3: 验证拒单记录
  GET /api/v1/admin/shop/webhook-logs?external_order_id=DY_ORDER_UNMAPPED_001
  Assert: body.items[0].action='rejected'
  Assert: body.items[0].reason 包含 '未映射'
```

**期望结果**:
- 未映射商品 Webhook 被拒单
- 不创建订单
- 拒单记录留痕

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-11-S1 | 未映射拒单 | 无映射 | webhook | rejected |
| MOCK-11-S2 | 映射已禁用 | mapping disabled | webhook | rejected |
| MOCK-11-S3 | 拒单记录 | rejected后 | 检查 | 有日志 |

---

### MOCK-12: 抖店 Webhook Mock - 领权 token 流转

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`, `SMS_MODE=stub`
- claim_pending 订单已创建, claim_token 已生成

**测试步骤**:

```
Step 1: 验证 token 在 sms_log 中
  GET /api/v1/admin/shop/sms-logs?type=claim_link&order_no=DY_ORDER_001
  Assert: body.items[0].content 包含 claim_token
  Assert: body.items[0].content 包含领权URL

Step 2: 使用 token 领权
  POST /api/v1/shop/claims/confirm
  Body: { "claim_token": "{token}", "mobile": "13700000000" }
  Assert: 200

Step 3: 验证 token 状态变为 used
  GET /api/v1/admin/shop/claims?token={token}
  Assert: body.status='used', body.used_at 非空

Step 4: 再次使用已用 token
  POST /api/v1/shop/claims/confirm
  Body: { "claim_token": "{token}", "mobile": "13700000000" }
  Assert: 422, body.detail 包含 '已使用' 或 '已领取'

Step 5: 验证完整流转链路
  webhook → claim_pending → sms_log → claim → paid → entitlement
  Assert: 每步数据一致
```

**期望结果**:
- token 从生成到使用完整流转
- 使用后 token 失效
- 完整链路数据一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-12-S1 | token流转 | claim_pending | 领权 | paid+active |
| MOCK-12-S2 | 重复使用 | used | 领权 | 422 |
| MOCK-12-S3 | 链路一致 | 领权后 | 检查 | 数据一致 |

---

### MOCK-13: 短信 Mock - 领权短信

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SMS_MODE=stub`
- claim_pending 订单已创建

**测试步骤**:

```
Step 1: 验证领权短信自动发送
  GET /api/v1/admin/shop/sms-logs?type=claim_link
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items 数量 >= 1

Step 2: 验证 sms_log 结构
  Assert: body.items[0].type='claim_link'
  Assert: body.items[0].mobile = '137****0000' (脱敏)
  Assert: body.items[0].content 非空
  Assert: body.items[0].content 包含领权URL
  Assert: body.items[0].status='sent'
  Assert: body.items[0].created_at 非空

Step 3: 验证 stub 不实际发送
  Assert: 无外部 SMS API 调用
  Assert: sms_log.provider='stub'

Step 4: 验证短信内容格式
  Assert: content 格式: '您购买的商品{product_name}已到账，请点击链接领取：{claim_url}'
  Assert: claim_url 包含 claim_token
```

**期望结果**:
- 领权短信自动发送 (stub)
- sms_log 结构完整
- 手机号脱敏
- 内容包含领权URL+token
- 无外部调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-13-S1 | 自动发送 | claim_pending | 检查 | sms_log已发送 |
| MOCK-13-S2 | 内容格式 | sms_log | 检查 | 含URL+token |
| MOCK-13-S3 | 脱敏 | sms_log | 检查 | 137****0000 |
| MOCK-13-S4 | 无外发 | stub模式 | 检查 | 无外部调用 |

---

### MOCK-14-N: 短信 Mock - 通知短信

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SMS_MODE=stub`
- 买家已支付订单 (触发通知短信)

**测试步骤**:

```
Step 1: 验证通知短信发送
  GET /api/v1/admin/shop/sms-logs?type=notify
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items 数量 >= 1

Step 2: 验证通知短信结构
  Assert: body.items[-1].type='notify'
  Assert: body.items[-1].mobile = '137****0000' (脱敏)
  Assert: body.items[-1].content 非空
  Assert: body.items[-1].status='sent'

Step 3: 验证通知类型
  Assert: 通知短信包含: 支付成功通知/发货通知/退款通知等
  Assert: 不同事件触发不同 type 的通知短信

Step 4: 验证 stub 模式
  Assert: sms_log.provider='stub'
  Assert: 无外部 SMS API 调用
```

**期望结果**:
- 通知短信自动发送 (stub)
- sms_log.type='notify'
- 手机号脱敏
- 无外部调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-14-N-S1 | 支付通知 | paid | 检查 | notify sms_log |
| MOCK-14-N-S2 | 退款通知 | refunded | 检查 | notify sms_log |
| MOCK-14-N-S3 | 脱敏 | sms_log | 检查 | 137****0000 |

---

### MOCK-15-N: 短信 Mock - 额度校验超额 422

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SMS_MODE=stub`
- 商家套餐短信额度=100条/月, 已用100条

**测试步骤**:

```
Step 1: 验证当前额度
  GET /api/v1/shop/subscription
  Assert: body.entitlements.sms_quota=100
  Assert: body.entitlements.sms_used=100

Step 2: 触发短信发送 (额度已满)
  (触发一个需要发短信的事件, 如抖店领权)
  POST /api/v1/webhooks/douyin/order
  Body: { ... }
  Assert: 200 (webhook本身成功)

Step 3: 验证短信发送失败
  GET /api/v1/admin/shop/sms-logs?order_no=DY_ORDER_NEW
  Assert: sms_log.status='failed' 或 无 sms_log
  Assert: 失败原因='额度不足'

Step 4: 验证额度校验逻辑
  Assert: 发送前检查 sms_used >= sms_quota → 拒绝
  Assert: 返回 422 (如果是 API 直接调用发短信)
```

**期望结果**:
- 短信额度用完时发送失败
- sms_log 记录失败状态
- 或直接返回 422

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-15-N-S1 | 额度满 | used=100/quota=100 | 发送 | 失败/422 |
| MOCK-15-N-S2 | 额度余1 | used=99/quota=100 | 发送 | 成功, used=100 |
| MOCK-15-N-S3 | 无限额度 | quota=-1 | 发送 | 成功 |

---

### MOCK-16-N: 课程库 Mock - 支付回调

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `COURSE_LIB_MODE=stub`
- 有课程库关联的商品

**测试步骤**:

```
Step 1: 模拟课程库支付回调
  POST /api/v1/webhooks/course-lib/payment
  Body: {
    "event": "payment.success",
    "data": {
      "course_id": "CL_COURSE_001",
      "buyer_id": "BUYER_001",
      "amount": 9900,
      "transaction_id": "CL_TX_001"
    }
  }
  Assert: 200

Step 2: 验证 entitlement 创建
  GET /api/v1/shop/entitlements?buyer_id=BUYER_001
  Assert: body.items[-1].source='course_lib'
  Assert: body.items[-1].status='active'

Step 3: 验证 stub 模式不实际调用课程库
  Assert: 无外部 HTTP 请求
  Assert: 回调直接处理

Step 4: 验证幂等
  POST /api/v1/webhooks/course-lib/payment (重复)
  Body: { ... 相同 transaction_id ... }
  Assert: 200 (幂等, 不重复创建)
```

**期望结果**:
- 课程库回调创建 entitlement
- source='course_lib'
- stub 模式无外部调用
- 幂等处理

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-16-N-S1 | 正常回调 | stub模式 | webhook | entitlement创建 |
| MOCK-16-N-S2 | 重复回调 | 已处理 | webhook | 幂等 |
| MOCK-16-N-S3 | 无效课程 | 不存在course_id | webhook | 400 |

---

### MOCK-17-N: 微信支付 Mock - 回调成功处理

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 订单已 prepay (status=pending)

**测试步骤**:

```
Step 1: 等待 stub 自动回调
  (prepay 后 stub 自动调用 notify, 等待3秒)
  Assert: 订单状态变为 paid

Step 2: 验证回调处理流程
  Assert: 1. 验签通过
  Assert: 2. 更新订单 status=paid, paid_at=now
  Assert: 3. 创建支付记录 (transaction_id, amount, status=success)
  Assert: 4. 创建 entitlement (status=active)
  Assert: 5. 创建 enrollment (课程类型)
  Assert: 6. 发送通知短信 (如有)

Step 3: 验证各步骤数据一致
  GET /api/v1/shop/orders/{order_no}
  Assert: status='paid', paid_at 非空

  GET /api/v1/admin/shop/payments?order_no={order_no}
  Assert: items[0].status='success', transaction_id 以 'wx_stub_' 开头

  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: items[0].status='active'
```

**期望结果**:
- 回调成功后完整执行业务流程
- 订单/支付/权益/选课全部创建
- 数据一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-17-N-S1 | 回调全流程 | pending | 自动回调 | paid+ent+enr |
| MOCK-17-N-S2 | 数据一致 | paid后 | 检查 | 各表一致 |
| MOCK-17-N-S3 | 通知发送 | paid后 | 检查 | sms_log已发 |

---

### MOCK-18-N: 抖店 Webhook Mock - 退款 entitlement revoked

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `DOUYIN_WEBHOOK_MODE=stub`
- 抖店订单已领权 (status=paid, entitlement active, enrollment active)

**测试步骤**:

```
Step 1: 模拟退款 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.refund", "data": { "douyin_order_id": "DY_ORDER_001", "refund_amount": 9900 } }
  Assert: 200

Step 2: 验证 entitlement 撤销
  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: items[0].status='revoked'
  Assert: items[0].revoke_reason='douyin_refund'
  Assert: items[0].revoked_at 非空

Step 3: 验证 enrollment 撤销
  GET /api/v1/shop/entitlements/{ent_id}/enrollments
  Assert: 所有 items[].status='revoked'

Step 4: 验证买家无法学习
  POST /api/v1/shop/entitlements/{ent_id}/progress
  Assert: 403

Step 5: 验证退款金额一致
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_001
  Assert: items[0].status='refunded'
  Assert: items[0].refund_amount=99.00
```

**期望结果**:
- 退款 Webhook 后权益和选课全部撤销
- 买家无法继续学习
- 退款金额正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-18-N-S1 | 退款撤销权益 | paid | refund webhook | revoked |
| MOCK-18-N-S2 | 无法学习 | revoked | progress | 403 |
| MOCK-18-N-S3 | 金额一致 | refunded | 检查 | 99.00 |

---

### MOCK-19-N: 短信 Mock - sms_log 结构验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SMS_MODE=stub`
- 已有多条 sms_log 记录

**测试步骤**:

```
Step 1: 查询全部 sms_log
  GET /api/v1/admin/shop/sms-logs
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200

Step 2: 验证 sms_log 字段结构
  对每条记录验证:
  Assert: id 非空
  Assert: type in ['claim_link', 'notify']
  Assert: mobile 格式为脱敏 (如 137****0000)
  Assert: content 非空
  Assert: status in ['sent', 'failed']
  Assert: provider='stub'
  Assert: created_at 非空
  Assert: merchant_id 非空 (关联商家)

Step 3: 验证按类型筛选
  GET /api/v1/admin/shop/sms-logs?type=claim_link
  Assert: 所有记录 type='claim_link'

  GET /api/v1/admin/shop/sms-logs?type=notify
  Assert: 所有记录 type='notify'

Step 4: 验证按状态筛选
  GET /api/v1/admin/shop/sms-logs?status=sent
  Assert: 所有记录 status='sent'

Step 5: 验证时间范围筛选
  GET /api/v1/admin/shop/sms-logs?start_date=2026-08-01&end_date=2026-08-31
  Assert: 所有记录在时间范围内
```

**期望结果**:
- sms_log 结构完整
- 手机号脱敏
- provider='stub'
- 支持类型/状态/时间筛选

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-19-N-S1 | 字段完整 | 有记录 | 检查 | 所有字段非空 |
| MOCK-19-N-S2 | 类型筛选 | 有2种类型 | 筛选 | 准确过滤 |
| MOCK-19-N-S3 | 脱敏验证 | 有记录 | 检查 | 137****0000 |
| MOCK-19-N-S4 | 时间范围 | 有记录 | 筛选31天 | 准确 |

---

### MOCK-20-N: 课程库 Mock - stub 模式验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `COURSE_LIB_MODE=stub`

**测试步骤**:

```
Step 1: 验证环境变量
  Assert: os.environ['COURSE_LIB_MODE'] == 'stub'

Step 2: 验证 stub 不发起外部请求
  (通过 mock interceptor 或日志验证)
  Assert: 无向课程库真实地址的 HTTP 请求

Step 3: 验证 stub 返回固定数据
  GET /api/v1/shop/course-lib/courses
  Assert: 200, body.items 为 stub 预设数据

Step 4: 验证 stub 支付回调
  POST /api/v1/webhooks/course-lib/payment
  Body: { "event": "payment.success", "data": { ... } }
  Assert: 200 (stub 直接处理)

Step 5: 切换为非 stub 模式
  (设置 COURSE_LIB_MODE=real, 重启)
  Assert: API 尝试调用真实课程库地址 (预期失败, 因为无真实服务)
```

**期望结果**:
- stub 模式不发起外部请求
- 返回预设数据
- 直接处理回调
- 非 stub 模式尝试真实调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-20-N-S1 | stub无外发 | COURSE_LIB_MODE=stub | 检查 | 无HTTP |
| MOCK-20-N-S2 | stub固定数据 | stub模式 | 查询 | 预设数据 |
| MOCK-20-N-S3 | 非stub调用 | COURSE_LIB_MODE=real | 查询 | 尝试真实调用 |

---

### MOCK-21-N: 微信支付 Mock - stub 模式环境变量

**前置条件**:
- FastAPI API server 可启动
- 可修改环境变量

**测试步骤**:

```
Step 1: 验证 stub 模式环境变量
  Assert: os.environ['WECHAT_PAY_MODE'] == 'stub'

Step 2: stub 模式下 prepay
  POST /api/v1/shop/orders/{order_no}/prepay
  Assert: 200, prepay_id 以 'wx_stub_' 开头

Step 3: 验证 stub 使用测试密钥
  Assert: 验签使用 TEST_SIGN_KEY (非真实密钥)
  Assert: 密钥来自环境变量或配置

Step 4: 验证 stub 响应延迟
  Assert: prepay 响应时间 < 100ms (即时返回)

Step 5: (可选) 验证非 stub 模式
  设置 WECHAT_PAY_MODE=real
  Assert: prepay 尝试调用真实微信 API (预期超时/失败)
```

**期望结果**:
- WECHAT_PAY_MODE=stub 时使用 stub 逻辑
- 使用测试密钥
- 即时响应
- 非 stub 模式尝试真实调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-21-N-S1 | stub环境变量 | WECHAT_PAY_MODE=stub | 检查 | stub逻辑 |
| MOCK-21-N-S2 | 测试密钥 | stub模式 | 验签 | TEST_SIGN_KEY |
| MOCK-21-N-S3 | 响应延迟 | stub模式 | 计时 | <100ms |

---

### MOCK-22-N: 抖店 Webhook Mock - stub 模式环境变量

**前置条件**:
- FastAPI API server 可启动
- 可修改环境变量

**测试步骤**:

```
Step 1: 验证 stub 模式环境变量
  Assert: os.environ['DOUYIN_WEBHOOK_MODE'] == 'stub'

Step 2: stub 模式下接收 webhook
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.create", "data": { ... } }
  Assert: 200 (stub 直接处理, 不验证真实抖店签名)

Step 3: 验证 stub 不验证真实签名
  Assert: webhook 请求不需要真实抖店签名
  Assert: 或使用测试签名密钥

Step 4: 验证 stub 模式完整流程
  webhook → claim_pending → sms_log → claim → paid → entitlement
  Assert: 全流程在 stub 模式下可完成

Step 5: (可选) 非 stub 模式
  设置 DOUYIN_WEBHOOK_MODE=real
  Assert: webhook 需要验证真实抖店签名 (预期验签失败)
```

**期望结果**:
- DOUYIN_WEBHOOK_MODE=stub 时使用 stub 逻辑
- 不验证真实签名
- 全流程可完成

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-22-N-S1 | stub环境变量 | DOUYIN_WEBHOOK_MODE=stub | 检查 | stub逻辑 |
| MOCK-22-N-S2 | 不验证签名 | stub模式 | webhook | 200 |
| MOCK-22-N-S3 | 全流程 | stub模式 | 完整流程 | 全通 |

---

### MOCK-23-N: Mock 服务 - 并发幂等

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`, `DOUYIN_WEBHOOK_MODE=stub`
- 并发测试工具 (pytest-asyncio / httpx async)

**测试步骤**:

```
Step 1: 并发发送相同抖店 webhook
  (同时发送5个相同 douyin_order_id 的 webhook)
  async def concurrent_webhooks():
    tasks = [client.post('/api/v1/webhooks/douyin/order', json=same_body) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    return results

  Assert: 所有响应 200
  Assert: 仅创建1条订单 (幂等)

Step 2: 并发发送相同微信回调
  (同时发送5个相同 transaction_id 的 notify)
  Assert: 所有响应 200
  Assert: 订单状态仅更新一次

Step 3: 并发领权
  (同时用相同 claim_token 领权)
  Assert: 仅1个成功 (200), 其余 422
  Assert: entitlement 仅创建1条

Step 4: 验证数据库一致性
  SELECT COUNT(*) FROM shop_orders WHERE external_order_id = 'DY_ORDER_CONCURRENT'
  Assert: count = 1
```

**期望结果**:
- 并发请求幂等处理
- 不创建重复数据
- 数据库一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-23-N-S1 | 并发webhook | stub模式 | 5并发 | 1条订单 |
| MOCK-23-N-S2 | 并发回调 | stub模式 | 5并发 | 1次更新 |
| MOCK-23-N-S3 | 并发领权 | 有效token | 5并发 | 1成功4失败 |

---

### MOCK-24-N: Mock 服务 - 错误重试

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `WECHAT_PAY_MODE=stub`
- 可模拟 stub 返回错误

**测试步骤**:

```
Step 1: 模拟 stub 支付回调处理失败
  (通过测试钩子让 stub 首次回调处理失败)
  POST /api/v1/payment/wx/notify
  Body: { "out_trade_no": "TEST_RETRY_001", ..., "simulate_failure": true }
  Assert: 500 (首次失败)

Step 2: 验证重试机制
  (stub 或系统自动重试)
  Assert: 第2次回调成功
  GET /api/v1/shop/orders/TEST_RETRY_001
  Assert: body.status='paid'

Step 3: 模拟抖店 webhook 处理失败
  POST /api/v1/webhooks/douyin/order
  Body: { ..., "simulate_failure": true }
  Assert: 500 (首次失败)

Step 4: 验证 webhook 重试
  (重试 webhook)
  POST /api/v1/webhooks/douyin/order
  Body: { ... (相同, 无 simulate_failure) }
  Assert: 200

Step 5: 验证最终数据一致
  Assert: 订单正确创建, 数据完整
```

**期望结果**:
- 失败后可重试
- 重试后数据一致
- 不产生重复数据

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-24-N-S1 | 回调失败重试 | 模拟失败 | 重试 | 成功 |
| MOCK-24-N-S2 | webhook失败重试 | 模拟失败 | 重试 | 成功 |
| MOCK-24-N-S3 | 重试不重复 | 失败后 | 重试 | 无重复 |

---

### MOCK-25-N: Mock 服务 - 清理重置

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 所有 Mock 模式开启
- 测试数据已产生

**测试步骤**:

```
Step 1: 清理测试数据
  POST /api/v1/test/reset-mock-data
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200

Step 2: 验证清理结果
  GET /api/v1/admin/shop/sms-logs
  Assert: body.items 数量 = 0

  GET /api/v1/admin/shop/orders?source=douyin
  Assert: body.items 数量 = 0

  GET /api/v1/admin/shop/webhook-logs
  Assert: body.items 数量 = 0

Step 3: 验证 stub 状态重置
  GET /api/v1/test/mock-status
  Assert: stub 计数器归零
  Assert: stub 状态干净

Step 4: 重新执行完整流程
  (重新执行 F1 私域支付开权全流程)
  Assert: 流程正常完成
  Assert: 数据正确生成

Step 5: 验证无残留数据影响
  Assert: 新数据与清理前无关联
  Assert: claim_token 全新生成
```

**期望结果**:
- 清理后所有 mock 数据清空
- stub 状态重置
- 重新执行流程正常
- 无残留数据

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-25-N-S1 | 清理数据 | 有数据 | reset | 清空 |
| MOCK-25-N-S2 | 重置stub | 有计数 | reset | 归零 |
| MOCK-25-N-S3 | 重新执行 | 清理后 | 执行流程 | 正常 |
| MOCK-25-N-S4 | 无残留 | 清理后 | 检查 | 无关联 |

---

## Round 6: Security/PII 安全测试用例

> 覆盖加密存储/日志脱敏/API脱敏/权限隔离/敏感字段揭露/保留期, 共 30 个用例 (15 existing + 15 new)
> 测试框架: pytest + SQLAlchemy (数据库验证) + grep (日志验证)
> 加密密钥: SHOP_PII_KEY 环境变量

---

### SEC-01: 支付密钥 AES-256-GCM 加密存储

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SHOP_PII_KEY=test-pii-key-for-unit-test-only-32b`
- 商家已保存支付配置 (wx_api_key='test_api_key_32_characters_xx')

**测试步骤**:

```
Step 1: 保存支付配置
  POST /api/v1/shop/payment-config
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "wx_mch_id": "1234567890", "wx_api_key": "test_api_key_32_characters_xx", ... }

Step 2: 数据库直查验证加密
  SELECT wx_api_key FROM shop_payment_configs WHERE merchant_id = 'MERCHANT_001';
  Assert: wx_api_key != 'test_api_key_32_characters_xx' (不是明文)
  Assert: wx_api_key 以 'gcm:' 或加密前缀开头
  Assert: len(wx_api_key) > len('test_api_key_32_characters_xx') (密文更长)

Step 3: 验证加密算法
  Assert: 密文可使用 SHOP_PII_KEY 解密回明文
  Python: from app.security import decrypt_field
  plaintext = decrypt_field(db_value, SHOP_PII_KEY)
  Assert: plaintext == 'test_api_key_32_characters_xx'

Step 4: 验证 AES-256-GCM
  Assert: 解密使用 AES-256-GCM 算法
  Assert: 密文包含 nonce + ciphertext + tag
```

**期望结果**:
- wx_api_key 存储为密文, 非明文
- 使用 AES-256-GCM 加密
- 可用 SHOP_PII_KEY 解密

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-01-S1 | 密钥加密 | 保存配置 | 查DB | 密文非明文 |
| SEC-01-S2 | 可解密 | 有密文 | 解密 | 还原明文 |
| SEC-01-S3 | GCM算法 | 密文 | 验证 | AES-256-GCM |

---

### SEC-02: 证书加密存储

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SHOP_PII_KEY` 环境变量已设置
- 商家已上传证书 (wx_cert_pem)

**测试步骤**:

```
Step 1: 上传证书
  POST /api/v1/shop/payment-config
  Body: multipart/form-data, cert=@cert.pem

Step 2: 数据库直查
  SELECT wx_cert_pem FROM shop_payment_configs WHERE merchant_id = 'MERCHANT_001';
  Assert: wx_cert_pem != 原始证书内容 (不是明文)
  Assert: wx_cert_pem 以加密前缀开头
  Assert: 不包含 'BEGIN CERTIFICATE' 明文

Step 3: 验证解密
  Python: plaintext = decrypt_field(db_value, SHOP_PII_KEY)
  Assert: plaintext 包含 'BEGIN CERTIFICATE'
  Assert: plaintext == 原始证书内容

Step 4: 验证 API 不返回明文
  GET /api/v1/shop/payment-config
  Assert: body.wx_cert_pem 不包含 'BEGIN CERTIFICATE'
  Assert: body.wx_cert_pem 为 null 或 '***' 或脱敏标识
```

**期望结果**:
- 证书密文存储
- 不含明文证书内容
- API 不返回明文证书

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-02-S1 | 证书加密 | 上传后 | 查DB | 密文 |
| SEC-02-S2 | 可解密 | 有密文 | 解密 | 还原证书 |
| SEC-02-S3 | API不返回 | 查API | 检查 | 无明文 |

---

### SEC-03: PII 字段加密 - 买家手机号

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- `SHOP_PII_KEY` 环境变量已设置
- 有买家记录 (mobile=13812345678)

**测试步骤**:

```
Step 1: 数据库直查买家手机号
  SELECT mobile FROM shop_buyers WHERE id = 'BUYER_001';
  Assert: mobile != '13812345678' (不是明文)
  Assert: mobile 以加密前缀开头
  Assert: len(mobile) > 11 (密文更长)

Step 2: 验证应用层加密
  Python: plaintext = decrypt_field(db_value, SHOP_PII_KEY)
  Assert: plaintext == '13812345678'

Step 3: 验证不同买家手机号加密结果不同
  SELECT mobile FROM shop_buyers WHERE id IN ('BUYER_001', 'BUYER_002');
  Assert: BUYER_001 密文 != BUYER_002 密文 (不同明文不同密文)

Step 4: 验证加密可逆
  (解密所有买家手机号, 验证均为11位手机号格式)
  Assert: 所有解密结果匹配 ^1\d{10}$
```

**期望结果**:
- 买家手机号应用层加密存储
- 非明文
- 可解密还原
- 不同手机号加密结果不同

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-03-S1 | 手机号加密 | 有买家 | 查DB | 密文 |
| SEC-03-S2 | 可解密 | 有密文 | 解密 | 11位手机号 |
| SEC-03-S3 | 不同密文 | 2个买家 | 查DB | 密文不同 |

---

### SEC-04: 加密密钥来源 - SHOP_PII_KEY

**前置条件**:
- FastAPI API server 可启动
- 可修改环境变量

**测试步骤**:

```
Step 1: 验证密钥来源
  Assert: os.environ.get('SHOP_PII_KEY') 非空
  Assert: 加密/解密使用 os.environ['SHOP_PII_KEY']

Step 2: 验证无密钥时行为
  (删除 SHOP_PII_KEY, 重启服务)
  Assert: 启动时报错或加密操作失败
  Assert: 错误信息提示 'SHOP_PII_KEY 未设置'

Step 3: 验证密钥变更后旧密文不可解密
  (用 KEY_A 加密数据, 切换为 KEY_B)
  Assert: 用 KEY_B 解密 KEY_A 加密的数据失败
  Assert: 需要数据迁移脚本

Step 4: 验证密钥长度
  Assert: len(SHOP_PII_KEY) >= 32 (AES-256 需要32字节密钥)
```

**期望结果**:
- 密钥来自 SHOP_PII_KEY 环境变量
- 无密钥时启动失败
- 密钥变更后旧密文不可解密
- 密钥长度 >= 32

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-04-S1 | 密钥来源 | 已设置 | 检查 | 来自环境变量 |
| SEC-04-S2 | 无密钥 | 删除环境变量 | 启动 | 报错 |
| SEC-04-S3 | 密钥变更 | 切换密钥 | 解密旧密文 | 失败 |
| SEC-04-S4 | 密钥长度 | 检查 | len | >=32 |

---

### SEC-05: 日志脱敏 - 买家手机

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有买家操作日志 (含手机号 13812345678)

**测试步骤**:

```
Step 1: 触发含手机号的日志
  (执行买家下单/查询等操作)

Step 2: grep 日志文件
  grep -r '13812345678' /var/log/app/
  Assert: 无匹配 (明文手机号不出现在日志中)

  grep -r '1381234' /var/log/app/
  Assert: 无匹配 (部分明文也不出现)

  grep -r '138****' /var/log/app/
  Assert: 有匹配 (脱敏格式出现)

Step 3: 验证脱敏格式
  grep -oP '1\d{2}\*{4}\d{4}' /var/log/app/*.log
  Assert: 匹配格式为 138****5678 (前3+星4+后4)

Step 4: 验证结构化日志
  (检查 JSON 格式日志)
  grep '"mobile"' /var/log/app/*.log
  Assert: 所有 mobile 字段值为脱敏格式
  Assert: 无 "mobile": "13812345678" 明文
```

**期望结果**:
- 日志中无明文手机号
- 脱敏格式: 138****5678
- 结构化日志字段均为脱敏

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-05-S1 | 无明文 | 有日志 | grep明文 | 无匹配 |
| SEC-05-S2 | 脱敏格式 | 有日志 | grep脱敏 | 有匹配 |
| SEC-05-S3 | 结构化日志 | JSON日志 | 检查字段 | 脱敏 |

---

### SEC-06: 日志脱敏 - 证号

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有入驻申请日志 (含身份证号 440101199001011234)

**测试步骤**:

```
Step 1: 触发含证号的日志
  (执行入驻申请/审核操作)

Step 2: grep 日志文件
  grep -r '440101199001011234' /var/log/app/
  Assert: 无匹配 (明文证号不出现在日志中)

  grep -r '440101' /var/log/app/
  Assert: 无匹配 (前6位明文也不出现)

Step 3: 验证脱敏格式
  grep -oP '\d{3}\*{11}\d{4}' /var/log/app/*.log
  Assert: 匹配格式为 440***********1234 (前3+星11+后4)

Step 4: 验证结构化日志
  grep '"id_no"' /var/log/app/*.log
  Assert: 所有 id_no 字段值为脱敏格式
  Assert: 无 "id_no": "440101199001011234" 明文
```

**期望结果**:
- 日志中无明文证号
- 脱敏格式: 440***********1234
- 结构化日志字段均为脱敏

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-06-S1 | 无明文 | 有日志 | grep明文 | 无匹配 |
| SEC-06-S2 | 脱敏格式 | 有日志 | grep脱敏 | 有匹配 |
| SEC-06-S3 | 结构化日志 | JSON日志 | 检查字段 | 脱敏 |

---

### SEC-07: 结构化日志无明文

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有各类操作日志 (含 PII 数据)

**测试步骤**:

```
Step 1: 收集所有结构化日志
  cat /var/log/app/*.log | python -m json.tool

Step 2: 检查所有 PII 字段
  对每条 JSON 日志检查:
  Assert: "mobile" 字段值匹配 1\d{2}\*{4}\d{4} (脱敏)
  Assert: "id_no" 字段值匹配 \d{3}\*{11}\d{4} (脱敏)
  Assert: "contact_mobile" 字段值为脱敏
  Assert: "wx_api_key" 字段不出现在日志中
  Assert: "wx_cert_pem" 字段不出现在日志中

Step 3: 全文搜索明文 PII
  grep -rP '1[3-9]\d{9}' /var/log/app/
  Assert: 无匹配 (无11位手机号明文)

  grep -rP '\d{17}[\dXx]' /var/log/app/
  Assert: 无匹配 (无18位证号明文)

Step 4: 验证错误日志也脱敏
  grep -i 'error' /var/log/app/*.log | grep -P '1[3-9]\d{9}'
  Assert: 无匹配 (错误日志也脱敏)
```

**期望结果**:
- 所有结构化日志 PII 字段脱敏
- 无明文手机号/证号
- 错误日志也脱敏
- 敏感密钥不出现在日志中

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-07-S1 | 全文搜明文手机 | 有日志 | grep | 无匹配 |
| SEC-07-S2 | 全文搜明文证号 | 有日志 | grep | 无匹配 |
| SEC-07-S3 | 错误日志 | 有错误 | 检查 | 也脱敏 |
| SEC-07-S4 | 密钥不在日志 | 有日志 | 搜api_key | 无匹配 |

---

### SEC-08: API 展示脱敏 - 买家 mobile

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已登录
- 有订单 (买家手机号 13812345678)

**测试步骤**:

```
Step 1: 查询订单列表
  GET /api/v1/shop/orders
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.items[0].buyer_mobile = '138****5678' (脱敏)

Step 2: 查询订单详情
  GET /api/v1/shop/orders/{order_no}
  Assert: body.buyer_mobile = '138****5678'

Step 3: 验证脱敏格式
  Assert: buyer_mobile 匹配 ^1\d{2}\*{4}\d{4}$
  Assert: 前3位 + 4星 + 后4位

Step 4: 验证不同手机号脱敏不同
  (另一买家 13912345678)
  Assert: buyer_mobile = '139****5678'

Step 5: 验证 API 响应无明文
  Assert: response body 中无 '13812345678' 字符串
```

**期望结果**:
- API 响应中买家手机号脱敏
- 格式: 138****5678
- 不同手机号脱敏不同
- 无明文泄露

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-08-S1 | 列表脱敏 | 有订单 | 查列表 | 138****5678 |
| SEC-08-S2 | 详情脱敏 | 有订单 | 查详情 | 138****5678 |
| SEC-08-S3 | 格式验证 | 脱敏值 | 正则 | ^1\d{2}\*{4}\d{4}$ |
| SEC-08-S4 | 无明文 | API响应 | 搜明文 | 无匹配 |

---

### SEC-09: API 展示脱敏 - 入驻 contact_mobile

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录
- 有入驻申请 (contact_mobile=13900000099)

**测试步骤**:

```
Step 1: 查询入驻申请列表
  GET /api/v1/admin/shop/onboarding
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items[0].contact_mobile = '139****0099' (脱敏)

Step 2: 查询入驻申请详情
  GET /api/v1/admin/shop/onboarding/{id}
  Assert: body.contact_mobile = '139****0099'

Step 3: 验证商家端自查
  GET /api/v1/shop/onboarding/self
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.contact_mobile = '139****0099'

Step 4: 验证无明文
  Assert: response body 中无 '13900000099' 字符串
```

**期望结果**:
- 入驻 contact_mobile 在所有 API 中脱敏
- 格式: 139****0099
- 无明文泄露

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-09-S1 | 列表脱敏 | 有申请 | 查列表 | 139****0099 |
| SEC-09-S2 | 详情脱敏 | 有申请 | 查详情 | 139****0099 |
| SEC-09-S3 | 商家自查 | 已登录 | 查self | 139****0099 |

---

### SEC-10: API 展示脱敏 - id_no

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录
- 有入驻申请 (id_no=440101199001011234)

**测试步骤**:

```
Step 1: 查询入驻申请详情
  GET /api/v1/admin/shop/onboarding/{id}
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.id_no = '440***********1234' (脱敏)

Step 2: 验证脱敏格式
  Assert: id_no 匹配 ^\d{3}\*{11}\d{4}$
  Assert: 前3位 + 11星 + 后4位

Step 3: 验证不同证号脱敏不同
  (另一申请 id_no=110101198801012345)
  Assert: id_no = '110***********2345'

Step 4: 验证无明文
  Assert: response body 中无 '440101199001011234' 字符串
```

**期望结果**:
- 身份证号在 API 中脱敏
- 格式: 440***********1234
- 无明文泄露

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-10-S1 | 详情脱敏 | 有申请 | 查详情 | 440***...1234 |
| SEC-10-S2 | 格式验证 | 脱敏值 | 正则 | ^\d{3}\*{11}\d{4}$ |
| SEC-10-S3 | 无明文 | API响应 | 搜明文 | 无匹配 |

---

### SEC-11: 权限隔离 - 商家不可访问 platform API

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已登录 (MERCHANT_TOKEN)
- 平台管理员已登录 (ADMIN_TOKEN)

**测试步骤**:

```
Step 1: 商家尝试访问平台 API
  GET /api/v1/admin/shop/merchants
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 403, body.detail 包含 '权限不足' 或 'forbidden'

Step 2: 商家尝试审核入驻
  POST /api/v1/admin/shop/onboarding/{id}/approve
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 403

Step 3: 商家尝试审核商品
  POST /api/v1/admin/shop/products/{id}/approve
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 403

Step 4: 商家尝试开通订阅
  POST /api/v1/admin/shop/subscriptions
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 403

Step 5: 验证平台管理员可访问
  GET /api/v1/admin/shop/merchants
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200
```

**期望结果**:
- 商家访问所有 /admin/ API 返回 403
- 平台管理员正常访问

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-11-S1 | 商家访问商家列表 | merchant | GET admin | 403 |
| SEC-11-S2 | 商家审核入驻 | merchant | POST approve | 403 |
| SEC-11-S3 | 商家审核商品 | merchant | POST approve | 403 |
| SEC-11-S4 | 平台正常访问 | admin | GET admin | 200 |

---

### SEC-12: 权限隔离 - 平台不可访问商家 API

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 平台管理员已登录 (ADMIN_TOKEN)
- 商家已登录 (MERCHANT_TOKEN)

**测试步骤**:

```
Step 1: 平台尝试访问商家创建商品
  POST /api/v1/shop/products
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 403

Step 2: 平台尝试商家退款
  POST /api/v1/shop/orders/{order_no}/refund
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 403

Step 3: 平台尝试商家核销
  POST /api/v1/shop/verifications
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 403

Step 4: 平台尝试保存支付配置
  POST /api/v1/shop/payment-config
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 403

Step 5: 验证商家可正常访问
  POST /api/v1/shop/products
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 201
```

**期望结果**:
- 平台访问所有 /shop/ 商家操作 API 返回 403
- 商家正常访问

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-12-S1 | 平台创建商品 | admin | POST shop | 403 |
| SEC-12-S2 | 平台退款 | admin | POST refund | 403 |
| SEC-12-S3 | 平台核销 | admin | POST verify | 403 |
| SEC-12-S4 | 商家正常 | merchant | POST shop | 201 |

---

### SEC-13: 权限隔离 - A 店不可操作 B 店

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家A已登录 (绑定店铺A, MERCHANT_A_TOKEN)
- 商家B已登录 (绑定店铺B, MERCHANT_B_TOKEN)
- 店铺A有商品 PRODUCT_A_001, 店铺B有商品 PRODUCT_B_001

**测试步骤**:

```
Step 1: A 尝试查看 B 的商品
  GET /api/v1/shop/products/PRODUCT_B_001
  Headers: Authorization: Bearer MERCHANT_A_TOKEN
  Assert: 404 或 403

Step 2: A 尝试修改 B 的商品
  PUT /api/v1/shop/products/PRODUCT_B_001
  Headers: Authorization: Bearer MERCHANT_A_TOKEN
  Body: { "name": "hacked" }
  Assert: 404 或 403

Step 3: A 尝试查看 B 的订单
  GET /api/v1/shop/orders?product_id=PRODUCT_B_001
  Headers: Authorization: Bearer MERCHANT_A_TOKEN
  Assert: 返回空列表或 403

Step 4: A 尝试核销 B 的买家
  POST /api/v1/shop/verifications
  Headers: Authorization: Bearer MERCHANT_A_TOKEN
  Body: { "buyer_mobile": "13812345678" } (B店买家)
  Assert: 404 或 422 (找不到权益)

Step 5: 验证 A 正常操作自己的资源
  GET /api/v1/shop/products/PRODUCT_A_001
  Headers: Authorization: Bearer MERCHANT_A_TOKEN
  Assert: 200
```

**期望结果**:
- A 店不可查看/修改 B 店资源
- 返回 404 或 403
- A 店正常操作自己的资源

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-13-S1 | A查B商品 | A登录 | GET B product | 404/403 |
| SEC-13-S2 | A改B商品 | A登录 | PUT B product | 404/403 |
| SEC-13-S3 | A查B订单 | A登录 | GET B orders | 空/403 |
| SEC-13-S4 | A核销B买家 | A登录 | POST verify | 404/422 |
| SEC-13-S5 | A操作A资源 | A登录 | GET A product | 200 |

---

### SEC-14: 敏感字段揭露 API

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已登录
- 有订单 (买家手机号 13812345678, API 默认脱敏 138****5678)

**测试步骤**:

```
Step 1: 默认查询 (脱敏)
  GET /api/v1/shop/orders/{order_no}
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.buyer_mobile = '138****5678'

Step 2: 调用揭露 API
  POST /api/v1/shop/orders/{order_no}/reveal-sensitive
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "fields": ["buyer_mobile"] }
  Assert: 200, body.buyer_mobile = '13812345678' (明文)
  Assert: body.reveal_token 非空 (或 session 标记)

Step 3: 再次查询 (会话内明文)
  GET /api/v1/shop/orders/{order_no}
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: body.buyer_mobile = '13812345678' (明文, 会话内有效)

Step 4: 验证其他字段仍脱敏 (如 id_no 未申请揭露)
  Assert: body.id_no 仍为脱敏格式 (如存在)
```

**期望结果**:
- 揭露 API 返回明文
- 会话内后续查询也显示明文
- 仅揭露申请的字段

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-14-S1 | 揭露手机号 | 脱敏状态 | reveal | 明文 |
| SEC-14-S2 | 会话内明文 | 已揭露 | 查询 | 明文 |
| SEC-14-S3 | 未揭露字段 | 揭露mobile | 查id_no | 仍脱敏 |
| SEC-14-S4 | 无权限揭露 | buyer token | reveal | 403 |

---

### SEC-15: 揭露后写审计日志

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已登录
- 已执行敏感字段揭露

**测试步骤**:

```
Step 1: 执行揭露
  POST /api/v1/shop/orders/{order_no}/reveal-sensitive
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "fields": ["buyer_mobile"] }
  Assert: 200

Step 2: 查询审计日志
  GET /api/v1/admin/shop/audit-logs?action=reveal_sensitive
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items[-1].action='reveal_sensitive'
  Assert: body.items[-1].user_id = 商家用户ID
  Assert: body.items[-1].target = order_no
  Assert: body.items[-1].fields = ['buyer_mobile']
  Assert: body.items[-1].created_at 非空
  Assert: body.items[-1].ip_address 非空

Step 3: 验证审计日志内容
  Assert: 日志记录了谁、何时、对哪个订单、揭露了哪些字段
  Assert: 日志中不包含揭露的明文值 (审计日志也不存明文)

Step 4: 验证每次揭露都有审计
  (再次揭露)
  POST /api/v1/shop/orders/{order_no}/reveal-sensitive
  Assert: 审计日志新增1条
```

**期望结果**:
- 揭露操作写入审计日志
- 审计日志含完整操作信息
- 审计日志不含明文值
- 每次揭露都有审计记录

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-15-S1 | 审计记录 | 揭露后 | 查日志 | 有记录 |
| SEC-15-S2 | 日志不含明文 | 有审计 | 检查 | 无明文值 |
| SEC-15-S3 | 每次有审计 | 揭露2次 | 查日志 | 2条记录 |

---

### SEC-16-N: 会话内明文 - 离开页回退脱敏

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- Vite dev server 已启动 (port 5173)
- 商家已登录
- 已执行敏感字段揭露 (会话内明文状态)

**测试步骤**:

```
Step 1: 揭露后查询 (明文)
  GET /api/v1/shop/orders/{order_no}
  Assert: body.buyer_mobile = '13812345678' (明文)

Step 2: 离开订单页面
  (导航到其他页面, 如 /shop/products)

Step 3: 重新返回订单页面
  GET /api/v1/shop/orders/{order_no}
  Assert: body.buyer_mobile = '138****5678' (回退脱敏)

Step 4: 验证需要重新揭露
  Assert: 离开页面后会话内明文标记失效
  Assert: 需要再次调用 reveal API 才能查看明文
```

**期望结果**:
- 离开页面后明文回退为脱敏
- 需重新揭露才能再查看明文

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-16-N-S1 | 离开回退 | 已揭露 | 离开返回 | 脱敏 |
| SEC-16-N-S2 | 重新揭露 | 已回退 | reveal | 明文 |
| SEC-16-N-S3 | 刷新页面 | 已揭露 | F5 | 脱敏(新会话) |

---

### SEC-17-N: 5 分钟回退脱敏

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已登录
- 已执行敏感字段揭露

**测试步骤**:

```
Step 1: 揭露后查询 (明文)
  POST /api/v1/shop/orders/{order_no}/reveal-sensitive
  GET /api/v1/shop/orders/{order_no}
  Assert: body.buyer_mobile = '13812345678' (明文)

Step 2: 等待 4 分 59 秒
  (time.sleep(299))
  GET /api/v1/shop/orders/{order_no}
  Assert: body.buyer_mobile = '13812345678' (仍明文, <5分钟)

Step 3: 等待至 5 分钟
  (time.sleep(1) → 总计 300 秒)
  GET /api/v1/shop/orders/{order_no}
  Assert: body.buyer_mobile = '138****5678' (回退脱敏)

Step 4: 验证 5 分钟窗口
  Assert: 揭露有效期 = 5 分钟 (300 秒)
  Assert: 超时后自动回退
```

**期望结果**:
- 揭露明文有效期 5 分钟
- 超时自动回退脱敏
- 5 分钟内仍可查看明文

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-17-N-S1 | 4分59秒 | 已揭露 | 查询 | 明文 |
| SEC-17-N-S2 | 5分钟 | 已揭露 | 查询 | 脱敏 |
| SEC-17-N-S3 | 5分后重新揭露 | 已回退 | reveal | 明文 |

---

### SEC-18-N: 保留期 - 订单/支付 >= 5 年

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 数据库有 5 年前的订单和支付记录

**测试步骤**:

```
Step 1: 验证 5 年前订单仍存在
  SELECT * FROM shop_orders WHERE created_at < NOW() - INTERVAL '5 years';
  Assert: 记录存在, 未被删除

Step 2: 验证 5 年前支付记录仍存在
  SELECT * FROM shop_payments WHERE created_at < NOW() - INTERVAL '5 years';
  Assert: 记录存在

Step 3: 验证保留策略
  Assert: 订单/支付数据保留期 >= 5 年
  Assert: 无自动清理任务删除 5 年内数据

Step 4: 验证 6 年前数据 (如有)
  SELECT * FROM shop_orders WHERE created_at < NOW() - INTERVAL '6 years';
  Assert: 可能被清理或保留 (根据策略)
```

**期望结果**:
- 订单/支付数据保留 >= 5 年
- 5 年内数据不被删除

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-18-N-S1 | 5年订单 | 有5年前 | 查询 | 存在 |
| SEC-18-N-S2 | 5年支付 | 有5年前 | 查询 | 存在 |
| SEC-18-N-S3 | 保留策略 | 检查配置 | 验证 | >=5年 |

---

### SEC-19-N: 保留期 - 审计日志 >= 1 年

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 数据库有 1 年前的审计日志

**测试步骤**:

```
Step 1: 验证 1 年前审计日志仍存在
  SELECT * FROM audit_logs WHERE created_at < NOW() - INTERVAL '1 year';
  Assert: 记录存在

Step 2: 验证保留策略
  Assert: 审计日志保留期 >= 1 年
  Assert: 无自动清理删除 1 年内日志

Step 3: 验证审计日志完整性
  Assert: 1 年前日志未被篡改
  Assert: 日志含完整字段 (user_id, action, target, timestamp, ip)
```

**期望结果**:
- 审计日志保留 >= 1 年
- 1 年内日志不被删除

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-19-N-S1 | 1年日志 | 有1年前 | 查询 | 存在 |
| SEC-19-N-S2 | 保留策略 | 检查配置 | 验证 | >=1年 |
| SEC-19-N-S3 | 完整性 | 有日志 | 检查 | 未篡改 |

---

### SEC-20-N: 保留期 - 入驻申请 >= 3 年

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 数据库有 3 年前的入驻申请

**测试步骤**:

```
Step 1: 验证 3 年前入驻申请仍存在
  SELECT * FROM shop_onboarding_applications WHERE created_at < NOW() - INTERVAL '3 years';
  Assert: 记录存在

Step 2: 验证保留策略
  Assert: 入驻申请保留期 >= 3 年

Step 3: 验证申请数据完整性
  Assert: 含营业执照图片URL, 法人信息等
  Assert: PII 字段仍加密存储
```

**期望结果**:
- 入驻申请保留 >= 3 年
- 数据完整

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-20-N-S1 | 3年申请 | 有3年前 | 查询 | 存在 |
| SEC-20-N-S2 | 保留策略 | 检查配置 | 验证 | >=3年 |

---

### SEC-21-N: 支付密钥密文数据库验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已保存支付配置

**测试步骤**:

```
Step 1: 数据库直查
  SELECT wx_api_key, wx_mch_id FROM shop_payment_configs WHERE merchant_id = 'MERCHANT_001';

Step 2: 验证 wx_api_key 密文
  Assert: wx_api_key != 明文密钥
  Assert: wx_api_key 匹配加密格式 (如以 'enc:' 或 'gcm:' 开头)
  Assert: len(wx_api_key) > 32 (密文比明文长)

Step 3: 验证可解密
  Python:
  from app.security import decrypt_field
  import os
  plaintext = decrypt_field(encrypted_value, os.environ['SHOP_PII_KEY'])
  Assert: plaintext == 原始明文密钥

Step 4: 验证无明文泄露
  SELECT * FROM shop_payment_configs WHERE wx_api_key LIKE '%test_api_key%';
  Assert: 0 rows (明文不在数据库中)
```

**期望结果**:
- wx_api_key 密文存储
- 可解密
- 数据库无明文

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-21-N-S1 | 密文格式 | 有配置 | 查DB | 加密格式 |
| SEC-21-N-S2 | 可解密 | 有密文 | 解密 | 还原明文 |
| SEC-21-N-S3 | 无明文 | 查DB | LIKE明文 | 0 rows |

---

### SEC-22-N: 证书密文数据库验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已上传证书

**测试步骤**:

```
Step 1: 数据库直查
  SELECT wx_cert_pem FROM shop_payment_configs WHERE merchant_id = 'MERCHANT_001';

Step 2: 验证密文
  Assert: wx_cert_pem != 原始证书内容
  Assert: wx_cert_pem 不包含 'BEGIN CERTIFICATE'
  Assert: wx_cert_pem 不包含 'END CERTIFICATE'

Step 3: 验证可解密
  Python: plaintext = decrypt_field(encrypted, SHOP_PII_KEY)
  Assert: plaintext 包含 'BEGIN CERTIFICATE'
  Assert: plaintext == 原始证书

Step 4: 验证无明文
  SELECT * FROM shop_payment_configs WHERE wx_cert_pem LIKE '%CERTIFICATE%';
  Assert: 0 rows
```

**期望结果**:
- 证书密文存储
- 不含明文证书标记
- 可解密

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-22-N-S1 | 密文 | 有证书 | 查DB | 密文 |
| SEC-22-N-S2 | 无明文标记 | 查DB | LIKE | 0 rows |
| SEC-22-N-S3 | 可解密 | 有密文 | 解密 | 含CERTIFICATE |

---

### SEC-23-N: PII 加密数据库验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有买家数据

**测试步骤**:

```
Step 1: 数据库直查买家表
  SELECT mobile FROM shop_buyers;

Step 2: 验证所有手机号加密
  Assert: 所有 mobile 字段值 != 11位数字明文
  Assert: 所有 mobile 匹配加密格式

Step 3: 验证无明文
  SELECT * FROM shop_buyers WHERE mobile ~ '^1\d{10}$';
  Assert: 0 rows (无明文手机号)

Step 4: 验证可批量解密
  Python:
  for buyer in buyers:
    plaintext = decrypt_field(buyer.mobile, SHOP_PII_KEY)
    Assert: plaintext 匹配 ^1\d{10}$
```

**期望结果**:
- 所有买家手机号加密存储
- 无明文
- 可解密为有效手机号

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-23-N-S1 | 全部加密 | 有买家 | 查DB | 全密文 |
| SEC-23-N-S2 | 无明文 | 查DB | 正则 | 0 rows |
| SEC-23-N-S3 | 可解密 | 有密文 | 解密 | 有效手机号 |

---

### SEC-24-N: 日志 grep 验证脱敏

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 有操作日志 (含买家手机号 13812345678, 证号 440101199001011234)

**测试步骤**:

```
Step 1: grep 明文手机号
  grep -rn '13812345678' /var/log/app/
  Assert: 返回 0 行 (无明文)

Step 2: grep 明文证号
  grep -rn '440101199001011234' /var/log/app/
  Assert: 返回 0 行 (无明文)

Step 3: grep 脱敏手机号
  grep -rn '138****5678' /var/log/app/
  Assert: 返回 > 0 行 (有脱敏记录)

Step 4: grep 脱敏证号
  grep -rn '440***********1234' /var/log/app/
  Assert: 返回 > 0 行 (有脱敏记录)

Step 5: grep 通用手机号模式
  grep -rnP '1[3-9]\d{9}' /var/log/app/
  Assert: 返回 0 行 (无任何11位手机号明文)

Step 6: grep 通用证号模式
  grep -rnP '\d{17}[\dXx]' /var/log/app/
  Assert: 返回 0 行 (无任何18位证号明文)
```

**期望结果**:
- 无明文 PII 在日志中
- 有脱敏 PII 在日志中
- 通用模式也无明文匹配

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-24-N-S1 | grep明文手机 | 有日志 | grep | 0行 |
| SEC-24-N-S2 | grep明文证号 | 有日志 | grep | 0行 |
| SEC-24-N-S3 | grep脱敏 | 有日志 | grep | >0行 |
| SEC-24-N-S4 | grep通用手机模式 | 有日志 | grep -P | 0行 |

---

### SEC-25-N: API 响应字段脱敏验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家/平台已登录
- 有完整数据

**测试步骤**:

```
Step 1: 验证订单 API 响应
  GET /api/v1/shop/orders
  Assert: body.items[*].buyer_mobile 匹配 ^1\d{2}\*{4}\d{4}$
  Assert: response 不含 11 位手机号明文

Step 2: 验证入驻 API 响应
  GET /api/v1/admin/shop/onboarding
  Assert: body.items[*].contact_mobile 匹配脱敏格式
  Assert: body.items[*].id_no 匹配脱敏格式

Step 3: 验证商家列表 API 响应
  GET /api/v1/admin/shop/merchants
  Assert: body.items[*].contact_mobile 匹配脱敏格式

Step 4: 验证支付配置 API 响应
  GET /api/v1/shop/payment-config
  Assert: body.wx_api_key 为 null 或 '***' (不返回)
  Assert: body.wx_cert_pem 为 null 或 '***'

Step 5: 验证 sms_log API 响应
  GET /api/v1/admin/shop/sms-logs
  Assert: body.items[*].mobile 匹配脱敏格式

Step 6: 全文搜索 response body
  (将所有 API 响应拼接, 搜索明文 PII)
  Assert: 无 11 位手机号明文
  Assert: 无 18 位证号明文
```

**期望结果**:
- 所有 API 响应 PII 字段脱敏
- 支付密钥/证书不返回
- 无明文 PII 泄露

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-25-N-S1 | 订单mobile | 有订单 | 查API | 脱敏 |
| SEC-25-N-S2 | 入驻id_no | 有申请 | 查API | 脱敏 |
| SEC-25-N-S3 | 支付密钥 | 有配置 | 查API | null/*** |
| SEC-25-N-S4 | sms_log | 有日志 | 查API | 脱敏 |

---

### SEC-26-N: 权限隔离 403 验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家/平台/买家已登录

**测试步骤**:

```
Step 1: 商家访问平台 API → 403
  GET /api/v1/admin/shop/merchants (merchant token)
  Assert: 403, body.detail 包含 '权限' 或 'forbidden'

Step 2: 平台访问商家操作 API → 403
  POST /api/v1/shop/products (admin token)
  Assert: 403

Step 3: 买家访问商家 API → 403
  POST /api/v1/shop/products (buyer token)
  Assert: 403

Step 4: 买家访问平台 API → 403
  GET /api/v1/admin/shop/merchants (buyer token)
  Assert: 403

Step 5: 无 token 访问 → 401
  GET /api/v1/shop/orders (无 Authorization)
  Assert: 401

Step 6: 无效 token → 401
  GET /api/v1/shop/orders (Authorization: Bearer invalid)
  Assert: 401
```

**期望结果**:
- 越权访问返回 403
- 无 token/无效 token 返回 401
- 错误信息不泄露系统细节

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-26-N-S1 | 商家→平台 | merchant | GET admin | 403 |
| SEC-26-N-S2 | 平台→商家 | admin | POST shop | 403 |
| SEC-26-N-S3 | 买家→商家 | buyer | POST shop | 403 |
| SEC-26-N-S4 | 无token | 无 | GET | 401 |
| SEC-26-N-S5 | 无效token | invalid | GET | 401 |

---

### SEC-27-N: 权限隔离 404 验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家A已登录, 商家B已登录
- A 店和 B 店各有资源

**测试步骤**:

```
Step 1: A 查询 B 的商品 → 404
  GET /api/v1/shop/products/PRODUCT_B_001 (merchant A token)
  Assert: 404 (不暴露资源存在性)

Step 2: A 查询 B 的订单 → 404
  GET /api/v1/shop/orders/ORDER_B_001 (merchant A token)
  Assert: 404

Step 3: A 查询 B 的权益 → 404
  GET /api/v1/shop/entitlements/ENT_B_001 (merchant A token)
  Assert: 404

Step 4: 验证 404 不泄露信息
  Assert: 404 body.detail = 'Not Found' 或通用消息
  Assert: 不包含 '属于商家B' 等信息泄露
```

**期望结果**:
- 跨店访问返回 404
- 不泄露资源存在性
- 错误信息通用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-27-N-S1 | A查B商品 | A登录 | GET B | 404 |
| SEC-27-N-S2 | A查B订单 | A登录 | GET B | 404 |
| SEC-27-N-S3 | 不泄露 | 404 | 检查body | 通用消息 |

---

### SEC-28-N: 揭露 API 审计日志验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 已执行敏感字段揭露操作

**测试步骤**:

```
Step 1: 查询审计日志
  GET /api/v1/admin/shop/audit-logs?action=reveal_sensitive
  Headers: Authorization: Bearer ADMIN_TOKEN

Step 2: 验证审计日志字段
  Assert: body.items[-1].action = 'reveal_sensitive'
  Assert: body.items[-1].user_id 非空 (操作者)
  Assert: body.items[-1].user_role = 'merchant'
  Assert: body.items[-1].target_type = 'order'
  Assert: body.items[-1].target_id = order_no
  Assert: body.items[-1].revealed_fields = ['buyer_mobile']
  Assert: body.items[-1].ip_address 非空
  Assert: body.items[-1].created_at 非空

Step 3: 验证日志不含明文
  Assert: 审计日志中无 '13812345678' 明文
  Assert: revealed_fields 仅记录字段名, 不记录值

Step 4: 验证日志不可篡改
  (尝试修改审计日志)
  UPDATE audit_logs SET user_id = 'hacker' WHERE id = '{log_id}';
  Assert: 数据库约束或审计机制阻止修改 (如有)
```

**期望结果**:
- 审计日志记录完整揭露操作
- 不含明文值
- 日志不可篡改

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-28-N-S1 | 字段完整 | 揭露后 | 查日志 | 所有字段非空 |
| SEC-28-N-S2 | 不含明文 | 有日志 | 检查 | 无明文值 |
| SEC-28-N-S3 | 不可篡改 | 有日志 | UPDATE | 阻止(如有) |

---

### SEC-29-N: 会话明文窗口验证

**前置条件**:
- FastAPI API server 已启动 (port 8000)
- 商家已登录

**测试步骤**:

```
Step 1: 揭露前查询 (脱敏)
  GET /api/v1/shop/orders/{order_no}
  Assert: buyer_mobile = '138****5678'

Step 2: 揭露
  POST /api/v1/shop/orders/{order_no}/reveal-sensitive
  Assert: 200

Step 3: 揭露后立即查询 (明文)
  GET /api/v1/shop/orders/{order_no}
  Assert: buyer_mobile = '13812345678'

Step 4: 1 分钟后查询 (明文)
  (sleep 60)
  GET /api/v1/shop/orders/{order_no}
  Assert: buyer_mobile = '13812345678' (仍明文)

Step 5: 5 分钟后查询 (脱敏)
  (sleep 240 → 总计 300 秒)
  GET /api/v1/shop/orders/{order_no}
  Assert: buyer_mobile = '138****5678' (回退脱敏)

Step 6: 不同订单需分别揭露
  POST /api/v1/shop/orders/{order_no}/reveal-sensitive (订单A)
  GET /api/v1/shop/orders/{order_no_B}
  Assert: 订单B 仍脱敏 (揭露不跨订单)
```

**期望结果**:
- 揭露后 5 分钟内明文
- 5 分钟后自动回退
- 揭露不跨订单

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-29-N-S1 | 0分钟 | 刚揭露 | 查询 | 明文 |
| SEC-29-N-S2 | 1分钟 | 已揭露 | 查询 | 明文 |
| SEC-29-N-S3 | 5分钟 | 已揭露 | 查询 | 脱敏 |
| SEC-29-N-S4 | 不跨订单 | 揭露A | 查B | 脱敏 |

---

### SEC-30-N: 保留期 DDL 验证

**前置条件**:
- 数据库可访问
- 有数据库 schema/迁移文件

**测试步骤**:

```
Step 1: 检查订单表保留策略
  \d shop_orders
  Assert: 检查是否有保留期相关约束或注释
  -- 或检查迁移文件中的保留策略配置

Step 2: 检查支付表保留策略
  \d shop_payments
  Assert: 保留期 >= 5 年 (通过配置或策略验证)

Step 3: 检查审计日志表保留策略
  \d audit_logs
  Assert: 保留期 >= 1 年

Step 4: 检查入驻申请表保留策略
  \d shop_onboarding_applications
  Assert: 保留期 >= 3 年

Step 5: 验证无过早清理的定时任务
  (检查 cron / celery beat 配置)
  Assert: 无删除 5 年内订单的任务
  Assert: 无删除 1 年内审计日志的任务
  Assert: 无删除 3 年内入驻申请的任务
```

**期望结果**:
- 各表保留期符合要求
- 无过早清理任务

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| SEC-30-N-S1 | 订单保留 | 查DDL | 验证 | >=5年 |
| SEC-30-N-S2 | 审计保留 | 查DDL | 验证 | >=1年 |
| SEC-30-N-S3 | 入驻保留 | 查DDL | 验证 | >=3年 |
| SEC-30-N-S4 | 无过早清理 | 查cron | 验证 | 无违规任务 |

---

## Round 7: 回归测试用例

> 覆盖 CRM/Agent/M0 商城/Alembic/前端回归, 共 10 个用例 (5 existing + 5 new)
> 测试框架: pytest + Playwright + Alembic
> 执行方式: 命令行脚本

---

### REG-01: CRM 全量回归

**前置条件**:
- Python 3.11+ 已安装
- 项目依赖已安装 (pip install -r requirements.txt)
- 数据库可连接
- CRM 测试数据已准备

**测试步骤**:

```
Step 1: 执行 CRM 全量回归
  Command: python tests/run_crm_all.py --through latest
  CWD: project root
  Timeout: 600s

Step 2: 验证执行结果
  Assert: 退出码 = 0
  Assert: 输出包含 'All tests passed' 或类似
  Assert: 无 FAILED 用例

Step 3: 验证测试覆盖
  Assert: 输出包含测试用例数量 > 0
  Assert: 覆盖 CRM 核心功能: 客户管理/跟进/标签/分配等

Step 4: 验证 --through latest 参数
  Assert: 使用最新版本测试数据
  Assert: 数据版本号匹配
```

**期望结果**:
- CRM 全量回归通过
- 退出码 0
- 无失败用例

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-01-S1 | 正常回归 | 依赖已装 | 执行 | 通过 |
| REG-01-S2 | --through latest | 最新数据 | 执行 | 版本匹配 |
| REG-01-S3 | 有失败 | (模拟) | 执行 | 退出码!=0 |

---

### REG-02: Agent 全量回归

**前置条件**:
- Python 3.11+ 已安装
- 项目依赖已安装
- Agent 相关测试数据已准备

**测试步骤**:

```
Step 1: 执行 Agent 全量回归
  Command: python tests/run_agent_a_c.py
  CWD: project root
  Timeout: 300s

Step 2: 验证执行结果
  Assert: 退出码 = 0
  Assert: 无 FAILED 用例

Step 3: 验证测试覆盖
  Assert: 覆盖 Agent 核心功能: 入驻代建/OCR/跟进等
  Assert: 覆盖 A-C 阶段所有用例
```

**期望结果**:
- Agent 全量回归通过
- 退出码 0

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-02-S1 | 正常回归 | 依赖已装 | 执行 | 通过 |
| REG-02-S2 | 覆盖A-C | 检查输出 | 验证 | 全覆盖 |

---

### REG-03: M0 商城回归

**前置条件**:
- Python 3.11+ 已安装
- 项目依赖已安装
- M0 商城基础设施已就绪

**测试步骤**:

```
Step 1: 执行 M0 商城回归
  Command: python tests/verify_shop_m0.py
  CWD: project root
  Timeout: 120s

Step 2: 验证执行结果
  Assert: 退出码 = 0
  Assert: 输出包含 'M0 verification passed' 或类似

Step 3: 验证 M0 基础设施
  Assert: 数据库表已创建 (shop_*)
  Assert: API 路由已注册 (/api/v1/shop/*)
  Assert: 基础模型已定义 (Merchant, Product, Order 等)

Step 4: 验证 M0 基础功能
  Assert: 商家模型可 CRUD
  Assert: 商品模型可 CRUD
  Assert: 订单模型可 CRUD
```

**期望结果**:
- M0 商城回归通过
- 基础设施验证通过

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-03-S1 | 正常回归 | 基础就绪 | 执行 | 通过 |
| REG-03-S2 | 表已创建 | 检查 | 验证 | shop_* 存在 |
| REG-03-S3 | 路由注册 | 检查 | 验证 | /api/v1/shop/* |

---

### REG-04: Alembic 一致性

**前置条件**:
- Python 3.11+ 已安装
- Alembic 已配置
- 数据库可连接

**测试步骤**:

```
Step 1: 执行 Alembic 一致性检查
  Command: python tests/alembic_head.py
  CWD: project root
  Timeout: 60s

Step 2: 验证执行结果
  Assert: 退出码 = 0
  Assert: 输出包含 'Alembic head matches' 或类似

Step 3: 验证数据库 head 版本
  alembic current
  Assert: 当前 head = EXPECTED_HEAD

Step 4: 验证无未执行迁移
  alembic heads
  Assert: 只有一个 head (无分叉)
  Assert: head 版本 = EXPECTED_HEAD

Step 5: 验证迁移可回滚
  alembic downgrade -1
  alembic upgrade head
  Assert: 可正常回滚和升级
```

**期望结果**:
- Alembic head 与 EXPECTED_HEAD 匹配
- 无分叉
- 迁移可回滚

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-04-S1 | head匹配 | 已迁移 | 检查 | 匹配 |
| REG-04-S2 | 无分叉 | 检查 | heads | 1个head |
| REG-04-S3 | 可回滚 | 当前head | downgrade+upgrade | 正常 |

---

### REG-05: 前端现有页面回归

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- Playwright 已安装

**测试步骤**:

```
Step 1: 执行现有 CRM UI 测试
  Command: npx playwright test tests/web/crm/
  CWD: apps/web
  Timeout: 300s

Step 2: 验证执行结果
  Assert: 所有测试通过
  Assert: 无 FAILED 用例

Step 3: 验证 CRM 页面功能
  Assert: 客户列表页正常渲染
  Assert: 客户详情页正常渲染
  Assert: 跟进记录页正常渲染
  Assert: 标签管理页正常渲染

Step 4: 验证无回归
  Assert: 新增商城页面不影响现有 CRM 页面
  Assert: 路由不冲突
  Assert: 共享组件正常
```

**期望结果**:
- CRM UI 测试全部通过
- 无回归问题

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-05-S1 | CRM UI | dev已启动 | 执行 | 全通过 |
| REG-05-S2 | 路由不冲突 | 检查 | 验证 | 无冲突 |
| REG-05-S3 | 共享组件 | 检查 | 验证 | 正常 |

---

### REG-06-N: CRM 回归 - EXPECTED_HEAD 匹配

**前置条件**:
- Python 3.11+ 已安装
- Alembic 已配置
- tests/alembic_head.py 中 EXPECTED_HEAD 已定义

**测试步骤**:

```
Step 1: 查看 EXPECTED_HEAD
  grep 'EXPECTED_HEAD' tests/alembic_head.py
  Assert: EXPECTED_HEAD = '{具体版本号}'

Step 2: 查看数据库当前 head
  alembic current
  Assert: current = EXPECTED_HEAD

Step 3: 执行一致性脚本
  python tests/alembic_head.py
  Assert: 退出码 = 0
  Assert: 输出 'Alembic head matches EXPECTED_HEAD'

Step 4: 验证迁移文件完整
  ls alembic/versions/
  Assert: 迁移文件数量 > 0
  Assert: 最新迁移文件 revision = EXPECTED_HEAD
```

**期望结果**:
- EXPECTED_HEAD 与数据库 head 一致
- 迁移文件完整

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-06-N-S1 | head匹配 | 已迁移 | 检查 | 一致 |
| REG-06-N-S2 | 迁移完整 | 检查文件 | 验证 | 文件存在 |

---

### REG-07-N: Agent 回归 - 全量用例

**前置条件**:
- Python 3.11+ 已安装
- 项目依赖已安装

**测试步骤**:

```
Step 1: 执行 Agent 全量回归
  python tests/run_agent_a_c.py
  Assert: 退出码 = 0

Step 2: 验证用例数量
  Assert: 输出包含用例总数 > 0
  Assert: PASSED 数量 = 总数 (无 FAILED)

Step 3: 验证覆盖阶段
  Assert: 覆盖阶段 A (入驻代建)
  Assert: 覆盖阶段 B (跟进管理)
  Assert: 覆盖阶段 C (其他 Agent 功能)

Step 4: 验证用例详情
  Assert: 每个用例有明确的 assert
  Assert: 无 skip 的用例 (或 skip 有合理原因)
```

**期望结果**:
- Agent 全量用例通过
- 覆盖 A-C 阶段

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-07-N-S1 | 全量通过 | 依赖已装 | 执行 | PASSED=总数 |
| REG-07-N-S2 | A-C覆盖 | 检查输出 | 验证 | 3阶段 |
| REG-07-N-S3 | 无skip | 检查 | 验证 | 无skip |

---

### REG-08-N: M0 回归 - verify_shop_m0 详细验证

**前置条件**:
- Python 3.11+ 已安装
- 项目依赖已安装
- 数据库可连接

**测试步骤**:

```
Step 1: 执行 M0 验证
  python tests/verify_shop_m0.py
  Assert: 退出码 = 0

Step 2: 验证数据库表
  Assert: shop_merchants 表存在
  Assert: shop_products 表存在
  Assert: shop_orders 表存在
  Assert: shop_buyers 表存在
  Assert: shop_entitlements 表存在
  Assert: shop_enrollments 表存在
  Assert: shop_payment_configs 表存在
  Assert: shop_onboarding_applications 表存在

Step 3: 验证 API 路由
  Assert: GET /api/v1/shop/products 可访问
  Assert: POST /api/v1/shop/orders 可访问
  Assert: GET /api/v1/shop/entitlements 可访问

Step 4: 验证模型关系
  Assert: Merchant → Products (一对多)
  Assert: Product → Orders (一对多)
  Assert: Order → Entitlement (一对一)
  Assert: Entitlement → Enrollments (一对多)

Step 5: 验证基础 CRUD
  Assert: Merchant 可创建/查询/更新
  Assert: Product 可创建/查询/更新
  Assert: Order 可创建/查询/更新
```

**期望结果**:
- M0 基础设施全部验证通过
- 表/路由/模型/CRUD 均正常

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-08-N-S1 | 表存在 | 已迁移 | 检查 | 全部存在 |
| REG-08-N-S2 | 路由可访问 | API已启动 | 检查 | 200 |
| REG-08-N-S3 | 模型关系 | 检查 | 验证 | 关系正确 |
| REG-08-N-S4 | CRUD | 执行 | 验证 | 可增查改 |

---

### REG-09-N: Alembic - EXPECTED_HEAD 详细验证

**前置条件**:
- Alembic 已配置
- 数据库可连接

**测试步骤**:

```
Step 1: 获取 EXPECTED_HEAD
  Python: from tests.alembic_head import EXPECTED_HEAD
  Assert: EXPECTED_HEAD 非空

Step 2: 获取数据库当前 head
  alembic current
  Assert: current head 非空

Step 3: 验证匹配
  Assert: current head == EXPECTED_HEAD

Step 4: 验证迁移链完整
  alembic history
  Assert: 从初始迁移到 EXPECTED_HEAD 的链路完整
  Assert: 无断裂

Step 5: 验证可从零迁移到 head
  (在空数据库上)
  alembic upgrade head
  Assert: 成功, head = EXPECTED_HEAD

Step 6: 验证可降级
  alembic downgrade base
  Assert: 成功, 所有表删除
  alembic upgrade head
  Assert: 成功恢复
```

**期望结果**:
- EXPECTED_HEAD 与数据库一致
- 迁移链完整
- 可从零迁移到 head
- 可降级和恢复

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-09-N-S1 | head匹配 | 已迁移 | 比对 | 一致 |
| REG-09-N-S2 | 链路完整 | 检查history | 验证 | 无断裂 |
| REG-09-N-S3 | 从零迁移 | 空数据库 | upgrade | 成功 |
| REG-09-N-S4 | 降级恢复 | 当前head | down+up | 正常 |

---

### REG-10-N: Playwright CRM UI 回归

**前置条件**:
- Vite dev server 已启动 (apps/web, port 5173)
- FastAPI API server 已启动 (port 8000)
- Playwright 已安装 (npx playwright install)

**测试步骤**:

```
Step 1: 执行 CRM UI Playwright 测试
  Command: npx playwright test tests/web/ --grep "@crm"
  CWD: apps/web
  Timeout: 300s

Step 2: 验证测试结果
  Assert: 所有 @crm 标记的测试通过
  Assert: 无 FAILED

Step 3: 验证 CRM 页面渲染
  - 客户列表: /customers 正常渲染
  - 客户详情: /customers/{id} 正常渲染
  - 跟进记录: /followups 正常渲染
  - 标签管理: /tags 正常渲染
  - 数据看板: /dashboard 正常渲染

Step 4: 验证 CRM 功能
  - 客户搜索功能正常
  - 客户筛选功能正常
  - 跟进添加功能正常
  - 标签管理功能正常

Step 5: 验证无商城影响
  - CRM 页面路由不受商城路由影响
  - 共享布局组件正常
  - 共享 API 客户端正常

Step 6: 验证截图
  Assert: Playwright 生成截图无异常
  Assert: 截图中页面正常渲染
```

**期望结果**:
- CRM UI Playwright 测试全通过
- 页面渲染正常
- 功能正常
- 无商城影响

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| REG-10-N-S1 | 全部通过 | dev已启动 | 执行 | PASSED |
| REG-10-N-S2 | 页面渲染 | 检查 | 访问各页 | 正常 |
| REG-10-N-S3 | 功能正常 | 检查 | 操作 | 正常 |
| REG-10-N-S4 | 无影响 | 检查 | 比对 | 无回归 |

---

## 附录

### A. 测试用例 ID 汇总

| Round | 前缀 | 现有用例 | 新增用例 | 合计 |
|-------|------|---------|---------|------|
| Round 2 (Web UI) | UI-W | 15 (UI-W-01~15) | 15 (UI-W-16-N~30-N) | 30 |
| Round 3 (MP UI) | UI-M | 10 (UI-M-01~10) | 10 (UI-M-11-N~20-N) | 20 |
| Round 4 (E2E) | E2E | 13 (E2E-01~13) | 17 (E2E-14-N~30-N) | 30 |
| Round 5 (Mock) | MOCK | 13 (MOCK-01~13) | 12 (MOCK-14-N~25-N) | 25 |
| Round 6 (Security) | SEC | 15 (SEC-01~15) | 15 (SEC-16-N~30-N) | 30 |
| Round 7 (Regression) | REG | 5 (REG-01~05) | 5 (REG-06-N~10-N) | 10 |
| **合计** | | **71** | **74** | **145** |

### B. 测试环境快速启动

```bash
# 1. 启动数据库
docker-compose up -d postgres

# 2. 执行迁移
alembic upgrade head

# 3. 启动 API
WECHAT_PAY_MODE=stub DOUYIN_WEBHOOK_MODE=stub SMS_MODE=stub COURSE_LIB_MODE=stub \
  SHOP_PII_KEY=test-pii-key-for-unit-test-only-32b \
  python -m uvicorn app.main:app --port 8000 --reload

# 4. 启动 Web 前端
cd apps/web && npm run dev

# 5. 启动 MP H5 前端
cd apps/mp && npm run dev:h5

# 6. 运行测试
# Web UI
npx playwright test tests/web/
# MP UI
npx playwright test tests/mp/
# E2E
python -m pytest tests/e2e/ -v
# Mock
python -m pytest tests/mock/ -v
# Security
python -m pytest tests/security/ -v
# Regression
python tests/run_crm_all.py --through latest
python tests/run_agent_a_c.py
python tests/verify_shop_m0.py
python tests/alembic_head.py
```

### C. data-testid 选择器索引

| 选择器 | 页面 | 用途 |
|--------|------|------|
| `[data-testid="dashboard-container"]` | /dashboard | Dashboard 容器 |
| `[data-testid="shop-onboarding-banner"]` | /dashboard | 入驻横幅 |
| `[data-testid="onboarding-form"]` | /shop/onboarding | 入驻表单 |
| `[data-testid="shop-dashboard-container"]` | /shop/dashboard | 交易看板 |
| `[data-testid="products-list-container"]` | /shop/products | 商品列表 |
| `[data-testid="product-edit-form"]` | /shop/products/edit | 商品编辑 |
| `[data-testid="orders-list-container"]` | /shop/orders | 订单列表 |
| `[data-testid="order-detail-drawer"]` | /shop/orders | 订单详情抽屉 |
| `[data-testid="verification-container"]` | /shop/verifications | 核销台 |
| `[data-testid="payment-config-form"]` | /shop/payment-config | 支付配置 |
| `[data-testid="subscription-container"]` | /shop/subscription | 套餐权益 |
| `[data-testid="admin-merchants-container"]` | /admin/shop/merchants | 商家列表 |
| `[data-testid="onboarding-review-container"]` | /admin/shop/onboarding | 入驻审核 |
| `[data-testid="plans-config-container"]` | /admin/shop/plans | 套餐配置 |
| `[data-testid="subscription-create-container"]` | /admin/shop/subscriptions | 订阅开通 |
| `[data-testid="product-review-container"]` | /admin/shop/products/review | 商品审核 |
| `[data-testid="mp-shop-index"]` | pages/shop/index | MP 店铺首页 |
| `[data-testid="mp-product-detail"]` | pages/shop/product | MP 商品详情 |
| `[data-testid="mp-checkout-container"]` | pages/shop/checkout | MP 结算页 |
| `[data-testid="mp-orders-list"]` | pages/shop/orders | MP 订单列表 |
| `[data-testid="mp-entitlements-container"]` | pages/shop/entitlements | MP 已购列表 |
| `[data-testid="mp-learn-container"]` | pages/shop/learn | MP 学习页 |
| `[data-testid="mp-booking-container"]` | pages/shop/booking | MP 预约页 |
| `[data-testid="mp-invoice-form"]` | pages/shop/invoice | MP 发票申请 |
| `[data-testid="mp-claim-container"]` | pages/shop/claim | MP 领权页 |

---

