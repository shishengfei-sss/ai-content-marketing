# 内容获客平台 · Phase 1 代码 QC 计划（资深开发）

| 字段 | 值 |
|------|-----|
| 文档版本 | **v1.1-dev-qc** |
| 角色视角 | 资深开发 / Tech Lead · 代码质量门禁 |
| 更新日期 | 2026-08-12 |
| 状态 | 📋 强制执行（与研发 Step 绑定） |
| 研发执行计划 | [内容获客平台-执行计划.md](./内容获客平台-执行计划.md) **v2.0** |
| **深度检查手册** | [内容获客平台-代码QC计划-深度检查手册.md](./内容获客平台-代码QC计划-深度检查手册.md)（扫描命令 · 逐文件 · 支付剧本 · L3 议程） |
| QA 用例库 | [内容获客商城-phase1 测试包](../05-测试与验收/测试用例/内容获客商城-phase1/) |
| QA 报告模板 | [测试报告模板](../05-测试与验收/验收报告/内容获客商城-phase1-测试报告模板.md) |
| PRD / API | [PRD §八](../01-PRD/21-内容获客商城-phase1/PRD-内容获客商城-phase1.md#八phase-1-api-契约) · [§十二 PII](../01-PRD/21-内容获客商城-phase1/PRD-内容获客商城-phase1.md#十二数据安全与-pii-治理附录6) |
| 设计 Token | `packages/shared/design-tokens.css` |

> **定位**：本文件管 **「代码能不能进测试」**；QA 包管 **「功能能不能签收」**。  
> **顺序**：开发自测 → **代码 QC 门禁** → QA R1 → 报告。跳过 QC 直接提测 = 无效提测。  
> **不够细时读**：扫描命令、逐文件问题清单、支付逐行提问见 [深度检查手册](./内容获客平台-代码QC计划-深度检查手册.md)。

---

## 0. 自评与补强说明（v1.1）

主计划 v1.0 偏门禁「原则表」，执行时容易变成口头勾选。v1.1 起强制：

| 动作 | 要求 |
|------|------|
| 每个业务 PR | 跑深度手册 **§2 扫描**，命中写在 PR 描述 |
| 每个批次 L3 | 按深度手册 **§3 模块表 + §8 议程** 出 QC 记录，禁止只写「L3 Pass」 |
| M3/M5/M7 | 必须过深度手册 **§4/§5 剧本** 问答 |

## 1. 目标与原则

### 1.1 目标

在内容获客商城 Phase 1（`shop_*` / `platform.shop.*`）交付过程中，建立可重复的 **代码质量控制系统**，保证：

1. 无租户串数据、无权限穿透、无权益双开、无跳过合规闸  
2. API / 模型 / 迁移 / 前端与 PRD 契约一致  
3. 支付与公域变更可 Mock、可幂等、可审计  
4. 不破坏主产品（CRM / Agent）回归基线  
5. 技术债显式登记，禁止「先合再说」

### 1.2 不可谈判原则（Dev Hard Rules）

| ID | 规则 | 违反后果 |
|----|------|----------|
| DR-1 | 一切写接口必须有权限依赖（`require_permission` / platform 等价物） | QC **拒收** |
| DR-2 | 商家域查询必须带 `tenant_id`（及需要时 `shop_id`）；禁止「先全表再过滤」 | QC **拒收** |
| DR-3 | 支付成功与权益开通必须同事务或可证明的幂等补偿；禁止双开权益 | QC **拒收** |
| DR-4 | 商品不可 `draft→on_sale` 跳状态；公域映射前必须过挂载闸 | QC **拒收** |
| DR-5 | `shop_buyers` **禁止**硬映射 / 自动创建 CRM `Contact` | QC **拒收** |
| DR-6 | PII（手机、证号、支付密钥）默认脱敏；明文仅走 reveal + 审计 | QC **拒收** |
| DR-7 | Alembic **只 upgrade**；禁止迁移里删生产数据、改 `.env`、动 `storage/` | QC **拒收** |
| DR-8 | 外对接必须经 Provider 接口（`mock` / `live`）；业务代码不得直耦合 SDK 散落 | QC **拒收** |
| DR-9 | 每个 Step 合入前：自测脚本 + `run_m0_m8` + 本 QC 清单勾选 | 不得提测 |
| DR-10 | Windows 改 API 后硬重启验证 `/health`，不信任 `--reload` | 提测前必做 |

### 1.3 与 QA / 执行计划的边界

```
执行计划 Step 完成编码
        ↓
   【代码 QC】← 本文（架构·安全·契约·可维护性）
        ↓ PASS
   QA R1（功能·边界·UI·UX）
        ↓ PASS
   批次 ✅ + 测试报告
```

- QC **不替代** 字段边界的 QA 穷举，但须保证校验在 **服务端真实存在**（前端校验只是体验）。  
- QC **必须** 覆盖资金/权限/状态机类缺陷（这类被 QA 漏掉也不可上线）。

---

## 2. QC 分层与门禁点

| 层 | 名称 | 时机 | 责任人 | 产出 |
|----|------|------|--------|------|
| **L0** | 作者自检 | 提 PR / 提测前 | 开发本人 | 自检清单勾选 |
| **L1** | 静态与契约 | 每次合入 | 开发 + 可选 CI | lint / 类型 / OpenAPI 抽检 |
| **L2** | 同行评审（PR Review） | 合入 master 前 | 另一名开发 / TL | Review 评论 + Approve |
| **L3** | 批次架构 QC | 批次 Step 全部编码完、进 QA R1 前 | Tech Lead | 《批次 QC 记录》 |
| **L4** | 发布前代码冻结 QC | Mx / 发版 | TL + 研发负责人 | 冻结清单 + 债列表 |

**门禁**：L0+L2 不过 → 禁止合入；L3 不过 → 禁止进入 QA R1；L4 不过 → 禁止宣称 Phase1/Mx 完成。  
**对用户交付**：另须满足 [开箱即用交付标准](./内容获客商城-开箱即用交付标准.md) D1～D7（种子、账号、启动说明、演示剧本、你方冒烟）。

---

## 3. 目录与模块所有权（QC 扫描范围）

| 区域 | 路径 | 关键风险 |
|------|------|----------|
| 权限码 | `apps/api/app/permissions.py` | 默认角色多授/漏授 |
| 平台 API | `apps/api/app/routers/platform_shop/` | scope 过滤、管家数据范围 |
| 商家 API | `apps/api/app/routers/shop/` | tenant 隔离、入驻态 |
| 买家/支付（后续） | `routers/mp/...` · integrations | 幂等、验签、金额 |
| 领域服务 | `apps/api/app/services/shop/` | 状态机、事务边界 |
| 模型 | `apps/api/app/models/shop.py` | 约束、软删、金额单位 |
| Schema | `apps/api/app/schemas/shop_*.py` | 必填、枚举、对外字段 |
| 迁移 | `apps/api/alembic/versions/098+` | 可回滚性（逻辑）、索引、默认值 |
| 验收脚本 | `apps/api/tests/verify_shop_*.py` | 与 PRD/QA `TC-*` 映射 |
| Web 平台 | `apps/web/src/views/admin/shop/`（规划） | 权限显隐、路由守卫 |
| Web 商家 | `apps/web/src/views/shop/` · layouts | 壳切换、入驻横幅 |
| Auth | `auth_service` · `auth_workspace` · `stores/auth.js` | workspace 串权 |
| 设计 | Vue + token | 禁止另起主题色 |

**债务资产（合入时必须点名）**：Alembic **102** 结算表无完整业务、**103** 权限微调——不得在注释/演示中标「P05 已完成」。

---

## 4. L0 作者自检清单（每个 PR 必贴）

提测/PR 描述中复制以下区块并勾选：

```markdown
### Code QC L0
- [ ] 范围仅本 Step；无无关大重构
- [ ] 新增/变更 API 与 PRD §8 路径·字段·错误码一致
- [ ] 写操作有权限依赖；测过无权限 403
- [ ] 商家查询含 tenant_id；用另一租户 ID 测过 404/403
- [ ] 状态迁移有白名单；非法迁移 409/422
- [ ] 金额：库/计算用分或明确转换；无 float 金额累加
- [ ] 对外错误 `detail` 为中文可 toast；无堆栈泄露
- [ ] PII 列表默认脱敏；无日志打印明文手机/证号/密钥
- [ ] 迁移：upgrade 可重复说明；EXPECTED_HEAD 已更新
- [ ] 有 verify_shop_* 或 Step 断言；本地跑绿
- [ ] run_m0_m8.py 绿（或注明 VERIFY_SKIP_AGENT 原因）
- [ ] 前端：无权限按钮不渲染；主色/布局跟 token
- [ ] Mock Provider 可切换；未写死 live 密钥
- [ ] Windows：已硬重启 API 并核对 /health
- [ ] 文档：执行计划状态 / 若改契约则 PRD 同步
```

未贴 L0 清单的 PR → Reviewer **直接 Request Changes**。

---

## 5. L2 PR Review 强制检查表（Reviewer）

### 5.1 架构与分层

| QC ID | 检查项 | Pass 标准 |
|-------|--------|-----------|
| QC-A01 | Router 瘦 | Router 只做鉴权·取参·调 service·返回 schema；无大段业务 SQL |
| QC-A02 | Service 边界 | 状态机/权益/支付在 service；禁止页面拼凑多表无事务 |
| QC-A03 | Schema 出入站 | 响应模型不直接吐 ORM；敏感字段不在默认 schema |
| QC-A04 | 依赖注入 | 统一 `TenantContext` / platform admin 依赖；禁止手解 JWT 散落 |
| QC-A05 | 命名空间 | `/admin/shop` vs `/shop` vs `/mp/shop` vs `/integrations` 不混用权限模型 |

### 5.2 安全与多租户

| QC ID | 检查项 | Pass 标准 |
|-------|--------|-----------|
| QC-S01 | 权限 | 每个突变接口有 permission；与 `05-角色权限` / `permissions.py` 一致 |
| QC-S02 | 租户隔离 | `filter(Model.tenant_id == ctx.tenant_id)`；IDOR 用例在脚本或 Review 备注 |
| QC-S03 | 平台 scope | 管家 `list_assigned` 不可见非分配商家；SQL 层过滤 |
| QC-S04 | Workspace | `platform` token 不能当商家写；切换后权限集正确 |
| QC-S05 | 集成端点 | Webhook **无 JWT** 但必须验签+时间窗+幂等键 |
| QC-S06 | 批量接口 | 禁止无限制的全表导出；分页强制上限 |
| QC-S07 | 文件 | 上传类型白名单；file_id 不可跨租户读 |

### 5.3 数据与状态机

| QC ID | 检查项 | Pass 标准 |
|-------|--------|-----------|
| QC-D01 | 枚举 | 状态值与 PRD/`04-数据模型` 一致（如 `pending_payment` 统一） |
| QC-D02 | 迁移合法性 | 仅允许文档中的边；禁止「方便」开后门 API |
| QC-D03 | 软删 | `deleted_at` 查询默认排除；删除不物理抹资金凭证 |
| QC-D04 | 唯一约束 | 订单号、支付流水、映射 external_id 有 DB 或应用层唯一 |
| QC-D05 | 金额 | 分整数；展示转换单点；禁止字符串金额运算 |
| QC-D06 | 时区 | 对外 ISO8601；筛选日期规则与 §8.3 一致 |
| QC-D07 | 事务 | 支付↔权益、退款↔撤销、清退副作用在同一事务或 outbox |

### 5.4 支付 / 公域 / Mock（M3+）

| QC ID | 检查项 | Pass 标准 |
|-------|--------|-----------|
| QC-P01 | Provider | `WxPayProvider` / `DoudianProvider` 接口；env 切换 mock/live |
| QC-P02 | 幂等键 | `transaction_id` / webhook event id 去重表或唯一索引 |
| QC-P03 | 验签失败 | 不改业务状态；可观测日志（无敏感明文） |
| QC-P04 | 金额校验 | notify 金额与订单不一致 → 拒 |
| QC-P05 | 挂载闸 | 未过审商品 Webhook 拒单 + `shop_channel_audit_logs` |
| QC-P06 | 无双开 | 重放 10 次权益行数=1（脚本或 Review 要求附测试） |

### 5.5 前端（Vue）

| QC ID | 检查项 | Pass 标准 |
|-------|--------|-----------|
| QC-F01 | 路由 meta | `platformAdmin` / permission 与侧栏过滤一致 |
| QC-F02 | 按钮显隐 | 状态×权限矩阵；禁止全显示靠 disable 糊弄主路径 |
| QC-F03 | 错误处理 | toast API `detail`；422 字段可锚定 |
| QC-F04 | 表单 | 必填 `*`；提交防抖；金额输入与分转换清晰 |
| QC-F05 | Token | 主色 `#1677ff`；顶栏 56 / 侧栏 200；不引入新设计体系 |
| QC-F06 | 列表 | 分页·空态·loading；不一次拉爆全量 |
| QC-F07 | 密钥展示 | 进件/渠道密钥掩码；无 v-html 未消毒用户内容 |
| QC-F08 | 买家端 | 独立视觉按 PRD；不误用 Admin 布局 |

### 5.6 测试与可维护性

| QC ID | 检查项 | Pass 标准 |
|-------|--------|-----------|
| QC-T01 | 脚本映射 | `VS-*` / 断言注释含 QA `TC-*` 或执行计划用例 ID |
| QC-T02 | 负向 | 至少 403/409/422/幂等之一覆盖本 PR 核心风险 |
| QC-T03 | 无 flaky | 不依赖执行顺序上的脏数据；可单文件跑 |
| QC-T04 | 魔法数 | 权限数量等变更时同步 verify 与 PRD |
| QC-T05 | 注释 | 复杂状态机有「为什么」；禁止大段注释掉的死代码合入 |

### 5.7 Review 结论等级

| 结论 | 含义 |
|------|------|
| **Approve** | 可合入 |
| **Approve + Debt** | 可合入但必须建债项（编号+到期日） |
| **Request Changes** | 阻塞；列 QC ID |
| **Reject** | 方向错误（如跳过状态机）；需重做方案 |

---

## 6. L3 批次架构 QC（进 QA 前）

每个研发批次（M0f、M1、M2…）在提 QA R1 前，TL 召开 **30～45 分钟** QC，按批次勾选。

### 6.1 通用批次出口（全部批次）

- [ ] 本批 API 清单与 PRD §8  diff 已核对（多的删、少的补）  
- [ ] `permissions.py` 变更有角色默认值评审（防管家误授开通权）  
- [ ] `alembic_head.EXPECTED_HEAD` = 实际 head  
- [ ] `verify_shop_mN.py` 绿；`run_shop_all --through` 绿  
- [ ] `run_m0_m8.py` 绿  
- [ ] 前端路由/菜单无死链；无权限账号抽检  
- [ ] 无 DR-1～DR-10 违规  
- [ ] 技术债表已更新  
- [ ] 同意进入 QA R1（签字）

### 6.2 分批次加测（架构焦点）

| 批次 | 额外 QC 焦点 |
|------|----------------|
| **M0 / M0f** | 入驻双通道互斥；OCR stub 不自动过审；workspace 串权；P02 scope |
| **M1** | `merge_entitlements` 正确性；到期守卫挂点；管家不能开通 |
| **M2** | 清退不可逆确认；暂停 vs 已购履约；closed 写拒绝 |
| **M3** | **支付事务+幂等+金额**；Mock Provider；禁止 Contact；价格以服务端为准 |
| **M4** | 状态机无后门；机审+人审审计字段；软删隔离 |
| **M5** | 退款全额；revoked 后履约拒绝；reveal 审计；红冲标记 |
| **M6** | 核销幂等；店员最小权限；开票字段服务端校验 |
| **M7** | 挂载闸；验签；claim 过期；组合未开通 422；审计日志 |
| **M8** | 与①权益模型共用；不双开 |

### 6.3 批次 QC 记录模板（归档）

路径建议：`docs/05-测试与验收/验收报告/QC-SHOP-M{n}-YYYYMMDD.md`

```markdown
# 批次代码 QC 记录 · M_
- 日期 / TL / 参与开发：
- Commit / Alembic head：
- L0/L2 抽检 PR 列表：
- 分批焦点结果：（Pass/Fail + 证据）
- 债务项：
- 结论：☐ 准许提测 QA R1　☐ 驳回
- 签字：
```

---

## 7. 静态质量与工程约定

### 7.1 后端

| 项 | 约定 |
|----|------|
| 风格 | 现有 FastAPI + SQLAlchemy 模式；新代码与 `services/shop/` 一致 |
| 异常 | 业务用 HTTPException/`detail` 中文；不吃掉异常 |
| 日志 | 结构化；`mobile`/`id_no` mask；支付回调打 event id 不打完整报文密钥 |
| 配置 | 密钥仅环境变量；禁止提交 `.env`、商户证书 |
| 依赖 | 新增第三方库需 TL 批准（许可证、体积、维护状态） |

### 7.2 前端

| 项 | 约定 |
|----|------|
| 栈 | Vue3 + 现有 layout；商城独立 `ShopLayout` |
| API | 经 `api/client.js`；统一错误拦截 |
| 状态 | 权限来自 `auth` store；不本地伪造 admin |
| 无障碍基线 | 表单 label；危险按钮确认框 |

### 7.3 迁移

| 项 | 约定 |
|----|------|
| 编号 | 自 **104** 起递增（102/103 已占用） |
| 内容 | 表/索引/权限种子；禁止 DML 清业务数据 |
| 校验 | 本地 `upgrade head` + 相关 verify |
| 文档 | 执行计划 §1.3 与 PRD §8.13 同步 |

### 7.4 建议的自动化门禁（有则启用）

| 检查 | 命令/方式 | 阻塞级别 |
|------|-----------|----------|
| Alembic head | `alembic_head.py` | 阻塞合入 |
| 商城脚本 | `verify_shop_mN.py` | 阻塞提测 |
| 主产品 | `run_m0_m8.py` | 阻塞提测 |
| 权限常量漂移 | 断言 37/18 或快照文件 | 阻塞 |
| 密钥扫描 | 禁止 commit 私钥/商户号明文 | 阻塞 |

（仓库若无 CI，由 L0/L2 **人工等价执行**，不得省略。）

---

## 8. 高风险代码路径 · 专项 QC 剧本

### 8.1 权益开通（M3）

```
审查顺序：
1. 下单是否锁定 SKU 价格快照
2. notify 验签 → 找单 → 金额校验 → 更新支付单
3. 同事务：order=paid + entitlement=active
4. 唯一键：支付流水 / (order_id, type)
5. 重放：第二次走「已处理」短路径
6. 失败：不留 paid 无权益的脏态（或有补偿任务且可测）
```

### 8.2 退款关权（M5）

```
1. 仅全额；部分金额 422
2. 退款成功态与 entitlement.revoked 同事务
3. 履约入口统一校验 active
4. 已开票 needs_red_flush
5. 重入安全
```

### 8.3 合规闸（M4/M7）

```
1. 状态枚举迁移表在代码中单点定义
2. 无 admin 内部「强制上架」或有则双人审计+权限码
3. 映射 API 读商品状态+审核结果
4. Webhook 拒单写 audit
```

### 8.4 清退（M2）

```
1. ack_irreversible 服务端校验非仅前端
2. closed 后订阅/上架/入驻写路径全拒
3. 列表/详情只读分支
```

---

## 9. 技术债与例外管理

| 规则 | 说明 |
|------|------|
| 建债 | Approve 时写：编号 `DEBT-SHOP-xxx`、原因、风险、到期批次、负责人 |
| 禁止 | 「P0 安全债」带入 QA；资金/权限类不得 Approve + Debt |
| 登记处 | 本文件附录 B + 执行计划 §1.4 |
| 关闭 | 须有修复 PR + QC 复验 |

### 附录 B · 已知债务（起始）

| ID | 项 | 风险 | 到期 |
|----|----|------|------|
| DEBT-SHOP-001 | Alembic 102 结算表无 P05 API/任务 | 误宣称清结算完成 | M5s / P05 专项前 |
| DEBT-SHOP-002 | 商城前端未建（M0f） | ~~无法端到端演示~~ | **已关闭**（2026-08-14 · 平台/商家 Web + 买家 H5） |
| DEBT-SHOP-003 | run_shop_all / UI 自动化未建 | ~~回归靠人工~~ | **已关闭**（2026-08-14 · R1～R7 runner） |
| DEBT-SHOP-004 | A20 写接口仅 `get_tenant_context`，无 `shop.onboarding.*` | ~~任意租户成员可提交入驻/刷 OCR~~ | **豁免落地**（2026-08-14 · `require_self_onboarding` 企业管理员；不新增 shop.onboarding.*） |
| DEBT-SHOP-005 | OCR `_ = ctx`，file_id 未校验租户目录 | ~~stub 不读盘；真 OCR 时 IDOR~~ | **已关闭**（2026-08-14 · 租户目录校验 + 平台必填 tenant_id） |
| DEBT-SHOP-007 | 入驻申请/材料 schema 默认回传证号与手机明文 | ~~相对「仅 reveal」~~ | **已关闭**（2026-08-14 · Out/status/材料脱敏；OCR 填表接口仍明文） |
| DEBT-SHOP-008 | 商品状态边未收敛到单一 `transition_*` | ~~可维护性；非已证实后门~~ | **已关闭**（2026-08-14 · `transition_product`） |

---

## 10. 角色与节奏

| 角色 | 职责 |
|------|------|
| 功能开发 | L0 自检；补 verify；不甩给 QA 契约错误 |
| Reviewer | L2 按 §5 勾选；对 DR 违规零容忍 |
| Tech Lead | L3 批次 QC；债批准；架构决策 |
| QA | 拒绝无 QC 记录的提测；回传 P0 必开 QC 复盘 |
| 研发负责人 | L4 冻结；发版签字 |

**节奏**：

- 每 PR：L0+L2  
- 每 Step 提测：L3 简表（可与 PR 合并若 Step=单 PR）  
- 每批次结束：完整 L3 记录归档  
- Mx 前：L4 + 安全路径 §8 复审  

---

## 11. 提测单（开发 → QA）必含字段

```markdown
## 提测单 · 内容获客 · {批次}/{Step}
- 需求：PRD 章节 / 执行计划 Step
- Commit / 分支：
- Alembic head：
- 影响页面与 API：
- L0 清单：已贴 PR
- L2 Reviewer / 结论：
- L3（若批次出口）：链接
- 自测证据：verify 命令输出摘要
- Mock 开关说明：
- 已知问题 / 债：
- 请 QA 执行：R1 对应用例章节（链接 TC）
```

QA 若缺任一项 → **退回**，不计测试轮次。

---

## 12. 代码 QC 报告（L3/L4 输出）

与功能测试报告分离；模板如下：

| 字段 | 内容 |
|------|------|
| 编号 | QC-SHOP-{批次}-YYYYMMDD |
| 范围 | |
| DR-1～10 | 逐条 Pass/Fail |
| §5 抽检 | 失败 QC ID 列表 |
| 高风险剧本 §8 | 结果 |
| 债 | 新增/关闭 |
| 结论 | 准许提测 / 准许发版 / 驳回 |
| 签字 | TL · 研发负责人 |

归档：`docs/05-测试与验收/验收报告/`。

---

## 13. 反模式（见到即 Request Changes）

1. Router 内复制粘贴大段 SQL，无 service  
2. `db.query(Model).get(id)` 后不校验 `tenant_id`  
3. 前端隐藏按钮当唯一权限控制  
4. 支付回调里直接 `commit` 多次导致部分成功  
5. 用 `float` 算钱  
6. 日志打印 webhook 全文含密钥  
7. 「临时」跳过审核的 `if force: on_sale`  
8. 迁移 `op.execute("DELETE FROM ...")` 清业务表  
9. 商家买家 ID 写入 `contacts.id`  
10. 引入与 `#1677ff` 体系冲突的整套 CSS 主题  

---

## 14. 文档同步义务

| 代码变更 | 必须同步 |
|----------|----------|
| 权限码/默认角色 | `permissions.py` + PRD/05 HTML + verify |
| API 路径/字段 | PRD §8 + 前端 client |
| 状态枚举 | PRD + 04 数据模型 + 前端字典 |
| 迁移 head | `alembic_head.py` + 执行计划 |
| QC 结论 | 本计划附录债 + 验收报告目录 |

---

## 15. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0-dev-qc | 2026-08-12 | 首版：门禁分层、DR 硬规则、PR/批次清单、高风险剧本、提测单 |
| v1.1-dev-qc | 2026-08-12 | 挂接深度检查手册；强制扫描与 L3 议程；承认 v1.0 偏原则 |
