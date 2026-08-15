# 内容获客平台 · 代码 QC 深度检查手册

| 字段 | 值 |
|------|-----|
| 文档版本 | **v1.1-dev-qc-deep** |
| 配套主计划 | [内容获客平台-代码QC计划.md](./内容获客平台-代码QC计划.md) |
| 用途 | L2/L3 **可执行**审查剧本（命令 · 逐文件 · 逐风险）；主计划偏门禁，本册偏「怎么查」 |

---

## 1. 自评：主计划不够细的地方（已用本册补齐）

| 缺口 | 补齐位置 |
|------|----------|
| 只有原则勾选，缺「怎么扫代码」 | §2 扫描命令 |
| 无按文件审查顺序 | §3 模块走查 |
| 支付/状态机只写口号 | §4～§5 审查剧本（伪代码级） |
| 无 PR 体积/拆分标准 | §6 |
| 无现网债务与已知代码味道 | §7 |
| 无 L3 会议议程时序 | §8 |

---

## 2. 每次 PR 必跑的扫描命令（Windows / 仓库根）

> 在 `apps/api` 下执行；命中则 **人工确认**是否违规（不是一律误报）。

### 2.1 租户隔离

```text
# 商城模型查询是否可能漏 tenant_id（人工看 diff 上下文）
rg -n "db\.query\(Shop" app/services/shop app/routers/shop app/routers/platform_shop
rg -n "\.get\(|\.get\(" app/services/shop
rg -n "filter\(.*tenant_id" app/services/shop
```

**Pass 标准**：凡按主键取商城实体，随后必有 `tenant_id == ctx.tenant_id`（平台端则用 scope 规则）；禁止只 `get(id)` 返回。

### 2.2 权限

```text
rg -n "@router\.(post|put|patch|delete)" app/routers/shop app/routers/platform_shop
rg -n "require_permission|require_any_permission|require_platform" app/routers/shop app/routers/platform_shop
```

**Pass 标准**：每个写路由的 Depends 链能追溯到权限；仅 `get_tenant_context` 的写接口必须在 Review 注明「为何任意登录用户可写」并记入清单。

### 2.3 金额与浮点

```text
rg -n "float\(|Decimal\(|price_cents|amount_cents" app/services/shop app/routers
rg -n "\*[ ]*0\.01|/ [ ]*100" app/services/shop
```

**Pass 标准**：计算用整数分；转元仅在展示边界；禁止 `float` 累加金额。

### 2.4 PII / 密钥

```text
rg -n "print\(|logger\.(info|debug|warning|error).*mobile|id_no|api_v3|secret|password" app/
rg -n "contact_mobile|id_no" app/schemas/shop*.py
```

**Pass 标准**：默认 schema 脱敏或省略；日志无明文；密钥不进仓库。

### 2.5 状态机后门

```text
rg -n "on_sale|pending_review|approved" app/services/shop
rg -n "status\s*=" app/services/shop
```

**Pass 标准**：状态赋值走单一函数（如 `transition_product(state)`）；无「调试用」强制赋值 API。

### 2.6 CRM 污染

```text
rg -n "Contact|contacts" app/services/shop app/routers/shop app/routers/mp
```

**Pass 标准**：商城成交路径 **零** 自动写 Contact（活动桥接另议且须显式开关）。

### 2.7 前端危险模式

```text
rg -n "v-html" apps/web/src/views
rg -n "platform_admin|platformAdmin" apps/web/src
rg -n "#1677ff|#7c3aed|purple" apps/web/src/views/admin/shop apps/web/src/views/shop
```

**Pass 标准**：用户内容不用未消毒 v-html；不写死绕过权限；不引入紫系主题。

---

## 3. 模块走查顺序（L3 建议 45～60min）

### 3.1 当前已存在代码（M0）

| 顺序 | 路径 | 审查问题清单（逐条答 Yes/No/NA） |
|------|------|----------------------------------|
| 1 | `permissions.py` | 37/18 数量？管家/运营默认差是否与 PRD 一致？店员是否仅三权？ |
| 2 | `models/shop.py` | 字段长度与 04 一致？unique(tenant)？JSON 默认可变对象是否 `default=dict` 陷阱？ |
| 3 | `schemas/shop_platform.py` | 必填与枚举？响应是否泄露 id_no 明文？ |
| 4 | `services/shop/onboarding_*.py` | 重复 pending→409？审过建 merchant 同事务？驳回原因必填？ |
| 5 | `services/shop/merchant_service.py` | 列表 scope SQL 层过滤？ |
| 6 | `services/shop/service_log_service.py` | 仅追加？权限？ |
| 7 | `routers/platform_shop/*` | 写接口权限码正确？错误 detail 中文？ |
| 8 | `routers/shop/*` | OCR/入驻是否鉴权足够？跨租户 file_id？ |
| 9 | `auth_workspace` / `auth_service` | switchWorkspace 是否换发权限？旧 token 失效策略？ |
| 10 | `alembic 098～103` | 可 upgrade？无 DELETE 业务数据？102 是否在注释标明「未验收」？ |
| 11 | `verify_shop_m0.py` | 与 VS-1～26 及 QA TC 可追溯？负向是否有？ |
| 12 | 前端 Login/Register/auth store | workspace 参数真实生效？文案「注册≠入驻」？ |

**已观察味道（须在下一次 QC 核实）**：

| 味道 | 位置 | 风险 | 处理 |
|------|------|------|------|
| OCR 路由仅 `get_tenant_context`，无细粒度 permission | `routers/shop/onboarding.py` | 任意成员可刷 OCR | **豁免落地**：写接口 `require_self_onboarding`（企业管理员）；GET status 仍登录即可 |
| `_ = ctx` 未使用 tenant | 同上 | 若 OCR 读文件未校验归属 → IDOR | **已关闭**（2026-08-14 · `onboarding_files.assert_onboarding_file_owned`） |
| 102 结算表已建无 API | alembic 102 | 产品误认完成 | DEBT-SHOP-001 保持开放 |

### 3.2 后续批次加入时追加走查表

复制下表到批次 QC 记录：

**M1 套餐**

- [ ] merge 算法有单测或 verify 覆盖并集/互斥  
- [ ] 到期后交易守卫挂载点明确（中间件或 service 入口）  
- [ ] P11 开通权限码 ≠ 续费申请权限码  

**M3 支付**

- [ ] Provider 接口 + mock 实现分文件  
- [ ] notify handler：验签→锁单→校验金额→更新→开权益（同事务）  
- [ ] 唯一索引：(provider, transaction_id)  
- [ ] 重放短路径有集成测试  

**M4 商品**

- [x] `transition_*` 白名单字典（`PRODUCT_TRANSITION_ACTIONS` · 2026-08-14）  
- [ ] 提审前置校验与 PRD 422 文案一致  
- [ ] 审计表写入与人审同事务  

**M5 退款**

- [ ] 全额校验在服务端  
- [ ] revoked 后所有履约入口共用 `assert_entitlement_active`  

**M7 公域**

- [ ] 验签失败不落业务  
- [ ] 挂载闸与 audit 日志  
- [ ] channel_combo_not_enabled  

---

## 4. 支付权益审查剧本（逐行问）

审查 `notify` / `complete_payment` 类函数时，Reviewer 按序提问，开发口头/注释回答：

1. **入口**：如何验签？密钥从哪读？失败是否在验签前写库？  
2. **找单**：用什么键？找不到是否仍 200（防枚举）？  
3. **金额**：回调金额字段名？与 `order.payable_cents` 比较？  
4. **状态**：已 paid 如何短路？  
5. **锁**：`SELECT FOR UPDATE` / 唯一约束 / 分布式锁？哪一种？  
6. **权益**：插入前是否查已有 active？唯一键是什么？  
7. **事务**：commit 几次？失败是否半成功？  
8. **日志**：打了 event id 还是全文？有无密钥？  
9. **测试**：哪条 verify 覆盖重放？命令是什么？  

任一项答不出 → **Request Changes**。

---

## 5. 状态机审查剧本（商品 / 入驻 / 退款）

对每个状态字段：

1. 列出允许边（从表或代码常量）  
2. 指出非法边的 HTTP 码  
3. 确认无「admin force」或 force 有独立权限+审计  
4. 确认 UI 与 API 双拒绝  

商品最小边集（Phase1）：

```text
draft → pending_review → approved → on_sale
pending_review → rejected → draft（改稿）
on_sale → off_sale → on_sale（再上架规则按 PRD）
禁止：draft → on_sale；rejected → on_sale
```

---

## 6. PR 体积与拆分标准

| 指标 | 建议上限 | 超限处理 |
|------|----------|----------|
| 业务 PR 净行数 | ≤ 800（不含 lock/生成物） | 拆 Step / 拆 API+UI |
| 单 PR 跨批次 | 禁止（M3+M7 同 PR） | 拆开 |
| 迁移+业务+大前端 | 不建议混 | 迁移可先合、标债 |
| Review 时限 | 1 个工作日 | TL 升级 |

**合入顺序**：迁移 → 模型/权限 → service → router → verify → 前端。

---

## 7. 安全检查表（发布 L4 加做）

| ID | 检查 | 方法 |
|----|------|------|
| SEC-01 | IDOR | 用 MCH_OTHER token 带 MCH_OK 的 id 调详情/写 |
| SEC-02 | 水平越权 | 店员调商品编辑 |
| SEC-03 | 垂直越权 | 商家调 /admin/shop |
| SEC-04 | Webhook 伪造 | 错签、空签、过期时间戳 |
| SEC-05 | 重放 | 支付/Webhook/核销码 |
| SEC-06 | 批量 | page_size=100000 是否被钳制 |
| SEC-07 | 文件 | 猜 file_id 读邻租户 |
| SEC-08 | XSS | 商品详情/驳回原因存 script |
| SEC-09 | 敏感日志 | 打开最近支付日志目视 |
| SEC-10 | 依赖 | 新包许可证与已知 CVE（人工） |

---

## 8. L3 会议议程（45～60min）

| 分钟 | 议程 |
|------|------|
| 0～5 | 范围：本批 Step、commit、head |
| 5～15 | 跑 §2 扫描，记录命中 |
| 15～30 | §3 模块走查表打勾 |
| 30～40 | 高风险剧本（本批相关 §4/§5） |
| 40～50 | verify 与 QA TC 映射抽 3 条 |
| 50～55 | 债务新增/关闭 |
| 55～60 | 结论：准许提测 / 驳回；填写 QC 记录 |

输出文件：`docs/05-测试与验收/验收报告/QC-SHOP-M{n}-YYYYMMDD.md`。

---

## 9. QC 记录完整模板

```markdown
# QC-SHOP-M_-YYYYMMDD

## 元信息
- 批次/Step：
- Commit：
- Alembic：
- TL：
- 开发：

## §2 扫描命中
| 命令 | 命中摘要 | 结论 Safe/Fix |
|------|----------|---------------|

## §3 模块走查
（粘贴 Yes/No 表）

## 高风险剧本
- 支付/状态机/…：Pass/Fail + 证据

## 测试映射
| TC ID | verify 用例 | 结果 |
|-------|-------------|------|

## 债务
| ID | 动作 open/close | 说明 |
|----|-----------------|------|

## 结论
☐ 准许提测 QA R1
☐ 驳回（阻塞项：）

签字：__________  日期：__________
```

---

## 10. 与主计划关系

- 日常 PR：主计划 L0/L2 + 本册 §2  
- 批次出口：主计划 L3 + 本册 §3～§8  
- 发版：主计划 L4 + 本册 §7  

主计划版本升为 **v1.1** 时须链接本文。
