# 代码 QC 比对报告 · 内容获客商城 Phase 1（代码 vs PRD / 需求设计文档）

| 字段 | 内容 |
|------|------|
| 编号 | QC-SHOP-P1-PRD-20260815 |
| 层级 | L4 发布前全面比对（代码实现 ↔ PRD / 需求设计文档） |
| 日期 | 2026-08-15 |
| 代码基准 | commit `50ef06f` + 本机未提交；Alembic head **137** |
| 代码范围 | `apps/api`（shop 全栈：routers/shop · platform_shop · mp/shop · services/shop · models/shop · schemas/shop* · permissions.py · alembic 098–137）；`apps/web`（views/shop · views/admin/shop）；`apps/mp`（买家 H5 shop pages） |
| 文档基准 | PRD-内容获客商城-phase1.md（主 PRD）；功能实施清单；04-数据模型.html；05-角色权限.html；07-支付与结算说明.html；代码QC计划 + 深度检查手册 |
| 起草 | 自动 QC（代码扫描 + 文档基准抽取比对） |
| TL / 研发负责人 | **未签** |

> 本文是「代码能不能进测试/发版」的质量门禁，与功能测试报告（QA R1~R7）分离。判定口径沿用 `代码QC计划.md` 的 DR-1~DR-10 与 QC-A/S/D/P/F/T 检查项。

---

## 1. 结论速览

| 维度 | 判定 | 说明 |
|------|------|------|
| 核心架构（金额/状态机/租户隔离/CRM 解耦/前端 XSS&主题&权限守卫） | ✅ 通过 | 见 §4、§5 |
| 与 PRD 契约一致性 | 🟡 有条件通过 | 发现 **1 项 P1 真偏差** + 多项 P2/P3 |
| 开箱 / 发版 | ☑ 可继续；**P1 项须在开箱前修复** | 不等同于 QC L4 签字放行 |

**一句话**：代码工程质量整体达标，无资金/权限类 P0 阻断；但与 PRD 比对发现 **P03 入驻审核通知（短信+站内信）未接通** 这一明确的功能缺口（PRD §350/551/2511 要求），以及孤儿权限码、PII 明文落库、支付回调无行锁、下单无防重等需整改项。

---

## 2. 比对方法

1. 后端代码扫描（Explore Agent 全量梳理 router/service/model/schema/permissions/migration）
2. 前端代码扫描（Explore Agent 梳理页面、路由守卫、表单、v-html、主题色）
3. 关键安全 Grep（`Contact` 耦合、`float` 金额、权限依赖、租户隔离）
4. PRD 基准抽取：权限数量（§4314）、角色模型（§2220）、PII 治理（§十二）、退款 F2（§1157/1346/3666）、P03 通知（§350/551/2511）、API 契约（§八）
5. 逐项对照，区分「符合 PRD」「真实偏差」「误报澄清」

---

## 3. 偏差与缺陷清单（按优先级）

| ID | 等级 | 主题 | PRD 依据 | 代码现状 | 风险 |
|----|------|------|----------|----------|------|
| **QC-P1-01** | 🔴 P1 | **P03 审核通知未接通** | §350「驳回→通知」§551「短信 contact_mobile + 站内信预分配管家」§2511「通知短信/站内信格式」 | `OnboardingApplications.vue:5` 注释自承「驳回/通过站内信与短信未接通」 | 入驻通过/驳回后商家/管家收不到通知，违反 PRD 验收项 |
| **QC-P2-01** | 🟠 P2 | 孤儿权限码 `shop.entitlement.revoke` | §1203 列出该码（退款 F2 关权益原因） | permissions.py 定义并授予 `shop_support`，**全仓无 router/service 引用** | 权限声明无对应能力；前端无入口，属悬空码 |
| **QC-P2-02** | 🟠 P2 | 孤儿 label `platform.user.manage` | 无对应 code | `PLATFORM_SHOP_PERMISSION_LABELS` 含该 label，但 `PLATFORM_SHOP_PERMISSIONS` 元组无此 code | 权限目录可能渲染无效标签，误导 |
| **QC-P2-03** | 🟠 P2 | **PII 身份证/手机号明文落库** | §十二要求脱敏输出（已满足）；未要求加密 | `id_no`/`contact_mobile`/`shop_buyers.mobile` 明文存储；仅 API 层 `mask_*` 脱敏；支付密钥已加密 | 个保法/等保合规风险，建议落库前加密或 token 化 |
| **QC-P3-01** | 🟡 P3 | 支付回调无行锁 | §8.4/§8.5 幂等；QC-P06 无双开 | `apply_payment_notify` 靠「状态早退 + `UK(order_id)`」抑制双开，**无 `SELECT FOR UPDATE`** | 极端并发下两回调可能同时过状态检查，靠唯一约束兜底，异常路径需补偿 |
| **QC-P3-02** | 🟡 P3 | 下单无防重 | 需求隐含幂等 | `create_order` 未查「同买家+同商品+未支付」在途订单 | 前端重复点击生成多笔 pending 订单 |
| **QC-P3-03** | 🟡 P3 | P05 结算表无完整 API | DEBT-SHOP-001（已知债） | Alembic 102 建 `shop_settlement_*` 表，无完整业务 API/周关账任务 | 不得对外宣称「清结算已完成」 |
| **QC-P3-04** | 🟡 P3 | 商家端 `shop.*` API 散写内联 | 可维护性（QC-T05） | 仅 `shopApi` 暴露 onboarding 4 函数；其余商品/订单/权益等 `api.get('/api/v1/shop/...')` 散落各 view | 不利于 baseURL/拦截/类型统一与重构（admin 端已集中 `adminApi`） |
| **QC-P3-05** | 🟡 P3 | `/mp/shop/payments POST /notify` 验签为 stub | §8 支付剧本要求真验签 | `wechat_pay_service` 现 `NotImplementedError` stub，测试会抛 503 | 上线前必须替换为真实渠道 + 验签 |
| **QC-P3-06** | 🟡 P3 | 平台 CS 角色矩阵展示与实际授予不一致 | 05-角色权限 | `PLATFORM_SHOP_ROLE_MATRIX_CODES` 的 CS 含 `approve`/`subscription.manage`/`merchant.manage`，但 `PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS` 不含 | 前端「角色权限预览」可能误导（实际授予正确，展示顺序错） |

### 误报澄清（已比对，确认符合 PRD，非问题）

| 疑似项 | 结论与依据 |
|--------|------------|
| 平台权限 19 个 ≠ QC 计划 §7.4 的「18」 | **符合 PRD**。主 PRD §4314 明确「商家 37 · 平台 19 = 56」。QC 计划 §7.4 数字已过时，应以 PRD 为准 |
| 商家端 `shop.*` 权限前端不可分配/勾选 | **符合 PRD**。§2220「不可自定义角色、不可改勾选（Phase 2）」；前端 RolesMembers 已标注只读 |
| CRM Contact 耦合 | **符合/优于 PRD**。全 `services/shop`/`routers/shop|platform_shop|mp` Grep `Contact` **零命中**；`shop_buyers` 独立建表，仅经 `crm_activities` 桥接（DR-5 通过） |
| 金额用 `float` 累加 | **不存在**。`services/shop` Grep `float(` 仅 4 处，皆为费率百分比（`bps/100`）与展示格式化（`:.2f`），金额库/计算均为整数 cents |
| 前端 v-html XSS | **无**。全仓 `v-html` 零命中 |
| 主题色冲突 | **无**。统一 `#1677ff`；紫系仅在非主题装饰色零星出现 |
| 权限按钮仅 disabled 糊弄 | **否**。商家/运营端按钮 `v-if=hasPermission` 从 DOM 擦除 + 路由守卫双控（QC-F02 通过） |
| 迁移删业务数据 | **否**。098/099/103 的 `DELETE` 仅清权限/角色种子（按 code 精确），无业务表删除（DR-7 通过） |

---

## 4. DR-1~DR-10 逐条判定

| ID | 规则 | 判定 | 证据 |
|----|------|------|------|
| DR-1 写接口权限依赖 | 每个写路由有权限依赖 | ✅ Pass | 商家端 router 全部 `require_permission`；A20 写走 `require_self_onboarding`（企业管理员），豁免已落地 |
| DR-2 租户隔离 | 商家查询带 tenant_id | ✅ Pass | 商家端统一 `TenantContext` 注入；OCR 按租户目录校验 `assert_onboarding_file_owned`；平台列表按 `account_manager_user_id` scope |
| DR-3 支付+权益同事务/幂等 | 无双开权益 | ✅ Pass（Mock） | `apply_payment_notify` 同 txn_id 短路；`UK(order_id)` DB 级防双开；退款 `_complete_refund_success` 同事务置 `revoked`（见 QC-P3-01 并发备注） |
| DR-4 商品状态机/挂载闸 | 禁止 `draft→on_sale` | ✅ Pass | `transition_product` 白名单；`publish` 仅 `approved/off_sale`；公域映射前校验在售+挂载闸 |
| DR-5 买家不成 Contact | 禁止硬映射 CRM | ✅ Pass | 全 shop 代码 Grep `Contact` 零命中 |
| DR-6 PII 脱敏 | 默认脱敏；明文仅 reveal | 🟡 Partial | 输出层脱敏满足；**DB 明文存储**（QC-P2-03）。输出侧 ✅，存储侧 ⚠️ |
| DR-7 Alembic 只 upgrade | 无删业务数据 | ✅ Pass | 098+ `DELETE` 仅权限/角色种子 |
| DR-8 Provider | 经 Provider 接口 | 🟡 Partial | 支付/抖店/短信均有 mock/live 分支；**微信 pay 现 stub**（QC-P3-05），真机替换前不得发版 |
| DR-9 自测脚本 | verify + run_m0_m8 | ✅ Pass | R1 896/896、R7 CRM+Agent 全过（见 QA 报告 2026-08-14） |
| DR-10 Windows 硬重启 | /health 验证 | ✅ Pass | 本批已硬重启，`GET /health` 端口 8003 正常 |

**DR 总判**：无 P0 资金/权限/租户串数据类拒收项。DR-6/DR-8 为部分通过（存储加密 + 真机验签待补）。

---

## 5. §5 QC 检查项抽检（重点项）

| QC ID | 检查项 | 判定 |
|-------|--------|------|
| QC-A01 Router 瘦 | 路由仅鉴权/取参/调 service | ✅ 抽检通过 |
| QC-S01 权限 | 突变接口有权限 | ✅（QC-P2-01/02 为码表瑕疵，非路由缺失） |
| QC-S02 租户隔离 | filter tenant_id | ✅ |
| QC-S04 Workspace | platform token 不能当商家写 | ✅ 双工作区切换换发权限 |
| QC-S05 集成端点 | Webhook 无 JWT 但须验签 | 🟡 /notify 无鉴权属预期，但验签为 stub（QC-P3-05） |
| QC-D01 枚举 | 状态值与 PRD/04 一致 | ✅ 商品 6 态、订单 5 态、权益 5 态、退款 3 态与文档一致 |
| QC-D05 金额 | 分整数 | ✅ |
| QC-D07 事务 | 支付↔权益/退款↔撤销同事务 | ✅（并发锁见 QC-P3-01） |
| QC-F01 路由 meta | platformAdmin/permission 一致 | ✅ |
| QC-F07 密钥展示 | 掩码、无 v-html | ✅ |

---

## 6. 整改建议与优先级

| 优先级 | 项 | 建议动作 | 负责人 |
|--------|----|----------|--------|
| **P1（开箱前必修）** | QC-P1-01 P03 通知 | 接通通过/驳回的短信 + 站内信（复用现有 SMS_MOCK / 站内信机制），补齐 PRD §2511 格式 | 研发 |
| **P2** | QC-P2-01/02 孤儿码/label | 删除 `shop.entitlement.revoke` 授予或补实现；清理 `platform.user.manage` label（如 PRD 确无此码） | 研发 |
| **P2** | QC-P2-03 PII 加密 | `id_no`/`contact_mobile`/`buyers.mobile` 落库加密或 token 化（对齐支付密钥加密做法） | 研发 + 安全 |
| **P3** | QC-P3-01 行锁 | `apply_payment_notify` 加 `SELECT FOR UPDATE` 或 `ON CONFLICT` 兜底 | 研发 |
| **P3** | QC-P3-02 下单防重 | 未支付同商品订单去重或前端幂等 | 研发 |
| **P3** | QC-P3-03 P05 | 建 M5s 专项补 P05 API + 周关账，关闭 DEBT-SHOP-001 | 研发 |
| **P3** | QC-P3-04 API 封装 | 商家端 `shop.*` 抽成 `shopApi` 命名函数对齐 admin 端 | 研发 |
| **P3** | QC-P3-05 真机验签 | 替换微信支付 stub 为真渠道 + 验签（发版前阻断项） | 研发 |
| **P3** | QC-P3-06 矩阵展示 | 统一 CS 角色矩阵与实际授予顺序 | 前端 |

---

## 7. 结论

- ☑ **准许进入开箱核验前的修复清单**：先修 QC-P1-01（P03 通知），其余 P2/P3 可排期。
- ☑ 不等同于 QC L4 签字放行（须研发负责人签 `准许发版`）。
- ☐ 已知债更新：DEBT-SHOP-001（P05）保持开放；建议新增 DEBT-SHOP-009（PII 明文落库）、DEBT-SHOP-010（支付回调并发锁）。
- 数据模型（04-数据模型.html）本次为字段/约束/隔离抽查，未逐表全比，建议 L3 走查补 04 逐表字段级对表（QC 计划 §3.2）。

---

## 附录 A · 本次比对未覆盖（建议后续）

| 项 | 说明 |
|----|------|
| 04-数据模型 逐表字段级对表 | 本次确认 tenant_id/唯一约束/金额 cents 健康，未逐字段比对 60+ 表 |
| 05-角色权限 全码表对码 | 已确认 37/19 数量与 PRD 一致，逐个码语义未全比对 |
| 07-支付与结算 逐字段 | 支付链路已 Mock 绿，真机契约待商务就绪后核 |
| UX 专家走查（26 册） | 不在本 QC 范围，归 QA R 轮 |
