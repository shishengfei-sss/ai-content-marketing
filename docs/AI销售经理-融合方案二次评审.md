# AI 销售经理 · 融合方案二次评审（v1.1.1 vs 我方 v1.6）

> 评审对象：`sales-manager-ai-plan/sales-manager-ai-plan.html`（其他 AI 在我方对比报告基础上产出的「融合版 v1.1.1」）
> 基准：`docs/PRD-智营获客-AI销售经理-v1.6.md` + `AI资深销售经理-总体方案.md` + `docs/v1.6-ai销售经理-执行计划.md`
> 日期：2026-07-20

## 一、一句话结论

融合版**本质上是「以我方 v1.6 为主架构 + 吸收初版优点」的合格整合稿**，并把我们对比报告里的 A/B/C/D 建议落成了设计细节（7 层 Prompt、文件清单、D7、标准化模型）。**事实性假设经代码核验基本成立，建议采纳为工作设计稿**，但有 **4 处需补强/修正**，其中「制造业护城河 + 商业模式」是创业主线，必须恢复。

## 二、事实假设核验（已实际查代码）

| 融合版假设 | 核验结果 | 说明 |
|---|---|---|
| `bant_evaluations` 表存在（`evaluate_bant` 工具依据） | ✅ 真存在 | `apps/api/alembic/versions/058_bant_evaluations.py` + `bant_service.py` |
| `supervisor_service.py` / `tools.py` / `assistant_service.py` 路径 | ✅ 准确（仅缺 `apps/api` 前缀） | 实际在 `apps/api/app/services/` 下 |
| `persona_service.py`（`P-MGR` 人格定义落点） | ✅ 存在 | `apps/api/app/services/persona_service.py` |
| `AGENT_REGISTRY`（子 Agent 注册机制） | ✅ 存在 | 定义在 `supervisor_service.py` |
| `sub_agents/analyst.py` 等 | ⚠️ 目录尚不存在 | 融合版已标「新增」，需新建 `app/services/agent/sub_agents/` |
| `CrmAdapter` / `NormalizedDeal` 等 | 🚫 尚未实现 | 融合版明确为 Phase 3 占位，可接受 |

**结论**：融合版没有"凭空造表/造路径"，技术可信度高于初版。

## 三、融合版做对的事（建议保留）

1. **主架构采用我方 Supervisor + 子 Agent 分层**，否决了初版的「30 扁平工具」「通用方法论知识库」「P0 CRM 适配器」——与我们的对比报告结论一致。
2. **新增 D7（CRM 解耦原则）**：MVP 直调内置 `services/crm/`，Phase 3 切 `CrmAdapter`，Phase 5 才接第三方。这正确化解了「初版对接 Salesforce/纷享销客」与 SRS「不对接外部 CRM」的冲突，且不阻塞 MVP。
3. **7 层 System Prompt 具体化**：把 P-MGR 人格、Supervisor 角色锁定、溯源强制、Confirm 闸边界、零断点引导都写成了可落地的提示词分层——这是我方 PRD 偏宏观、落地时最缺的"血肉"。**直接采纳为 P-MGR 提示词蓝本**。
4. **文件变更清单 + 验收场景**：给出了 13 项文件级变更（新增/修改/迁移/测试）和 3 个 MVP 演示场景，与执行计划对齐，可直译为开发任务。
5. **人格多变体 P-010~P-013 正确延后到 Phase 5**，对客沟通复用 P-001~P-009 镜像——与对比报告一致。

## 四、需补强 / 修正（4 处）

### P1（重要）制造业护城河 + 商业模式被弱化 —— 必须恢复
融合版「项目背景」把定位写成「技术基座完备，AI 销售经理 = 新增中枢 + 分层 + 工具 + 人格，而非重构底层」。这句话技术正确，但**丢掉了创业主线**：
- 我方总体方案强调的 **B2B 制造业护城河**（工艺 / 成本 / BOM / 招投标 / 产品主数据）在融合版里只剩 CPQ 库的「BOM/成本/底价」一句带过；
- 融合版**完全没有**我方总体方案的「竞品对标（Salesforce Agentforce / 销售易 NeoAgent / 大模型应用）+ 创业差异化 + 商业模式（私有化标杆→SaaS）」章节。

**修正**：保留融合版作"技术设计稿"，但单独保留/恢复 `AI资深销售经理-总体方案.md` 的「行业聚焦 + 护城河 + 商业模式」作为战略母本；并在商机官/报价官工具说明里显式点出制造业特征（BOM 成本拆解、招标应标、行业知识图谱）。

### P2（中）写动作的"硬约束"不能只靠 Prompt 软约束
融合版在 Prompt 层写了"发邮件/对外报价/改分配须人确认"，但**Confirm 闸应在工具层强制**（复用 `FR-AGENT-03` propose-resume），而非仅靠人格提示词。尤其商机官的 `recommend_next_action`、报价官的 `configure_quote` 输出"建议"时，要在工具返回结构里带 `requires_confirm=true` 标志，由 Supervisor 统一拦截。
**修正**：在 FR-SALES-MGR-05/06/07 补一条「工具返回结构含 `requires_confirm` 字段，Supervisor 据此插闸」。

### P3（低）路径前缀 + 目录
融合版文件清单写 `app/services/agent/...`，实际根目录是 `apps/api/app/services/agent/`。照抄进执行计划前统一加 `apps/api` 前缀；`sub_agents/` 目录标记"新建"即可。
**修正**：并入执行计划时改路径，无实质阻碍。

### P4（低）主动预警骨架被整体推到 Phase 4-5
我方 PRD 的 `FR-SALES-MGR-10` 承诺 MVP 留"主动预警骨架"。融合版 MVP 只保留被动的 `detect_stalled_deals`（ stagnant 检测），把"主动订阅/周期触发"推到 🚫 本版不做。
**修正**：可接受，但建议 MVP 仍保留一个"预警订阅接口占位"（如 `register_alert_hook`），方便 Phase 4 直接点亮，避免后期返工。

## 五、采纳行动清单

| 动作 | 内容 | 落点 |
|---|---|---|
| 采纳 | 7 层 System Prompt 作为 P-MGR 提示词蓝本 | 并入 `v1.6-ai销售经理-执行计划.md` Phase 1 |
| 采纳 | D7 CRM 解耦原则 + `Normalized*` 标准化模型 | 并入 PRD §硬决议 + Phase 3 占位 |
| 采纳 | 13 项文件变更清单 + 3 个验收场景 | 并入执行计划 Phase 1/2 |
| 采纳 | `evaluate_bant` 等工具（已验证有表） | 并入 FR-SALES-MGR-05 工具表 |
| 修正 | P1：恢复制造业护城河 + 商业模式章节，引用总体方案 | 战略母本单列，技术稿引用 |
| 修正 | P2：工具层 `requires_confirm` 硬约束 | 补 FR-SALES-MGR-05/06/07 |
| 修正 | P3：路径加 `apps/api` 前缀 | 执行计划改路径 |
| 修正 | P4：MVP 留 `register_alert_hook` 占位 | PRD FR-SALES-MGR-10 |

## 六、给胜非的决策点

1. **技术设计稿是否就以这份融合版为准？**（我建议：是，合并上述 4 处修正后作为开发蓝本）
2. **战略母本（护城河/商业模式）是否单独立档保留，还是合回 PRD？**（我建议：单独立档，PRD 引用，避免技术稿臃肿）
3. 是否现在就按修正后的融合版**开工 Phase 1**（Supervisor 骨架 + P-MGR + Confirm 闸 + 对话台）？

---
*附：核验命令已实地执行，非凭记忆。其余子 Agent（线索官/客户官/报价官/教练官/协同官）与 CRM 适配器均按融合版正确延后，与 SRS 硬决议无冲突。*
