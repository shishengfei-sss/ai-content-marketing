# 智营获客 · 整合产品需求文档（PRD）v1.3

> 文档基线：v1.3（Alembic 085）｜覆盖范围：v0.3.3 → v1.3｜生成日期：2026-07-17
> 配套可视化版：`docs/PRD-智营获客-整合v1.3.html`
> 来源：docs/需求规格.md（SRS v0.8.5）、各版本执行计划、人格库手册、现有模块 PRD（*-prd）

## 一、产品概述与目标

**智营获客** = 通用 AI 营销内容创作顾问 + 内置 SaaS CRM 获客转化闭环一体化系统。支持公众号/小红书/抖音多形态内容任意题材生成，结合租户知识库、品牌语气与内置 CRM，打通「AI 创作 → 线索沉淀 → 商机推进 → 报价合同 → 订单回款」。

**主业务链路**：AI 创作 → 活动关联 → 线索/客户 → 商机 Deal → 报价/CPQ → 合同 → 订单 → 回款/发票
**支线**：招标线索（平台 L1 → 租户 L2 ICP → claim 入线索）、运营报表与提醒、工作台、长期记忆。

**三端形态**：
- API（FastAPI/Python）：全部业务逻辑；生产强制 PostgreSQL+pgvector，开发期 SQLite；可插拔 LLM（默认 DeepSeek，租户可配自有 Key）。
- Web（Vue 3）：全功能；平台后台 `/admin` 仅 Web。双端对齐基准端。
- H5（uni-app）：按权限对齐 Web 主流程；v1.3 招标线索与 CPQ 仅 Web，H5 延后。

**目标用户**：中小企业市场/销售负责人、营销运营、销售（sales）、平台运营（platform_admin）。

## 二、角色与权限

**账户-公司解耦**：一个账号（User）可加入多家公司（Membership）；登录后选/切当前公司（active_tenant_id），数据/菜单/权限随公司切换；个人偏好全局共用；数据隔离以 `tenant_id` 过滤为硬边界。

| 角色 | 说明 | 默认权限要点 |
|------|------|------|
| `admin` | 企业管理员（不可删、权限全开不可削弱，至少 1 名） | 全部 `crm.*` + `crm.org.manage` + `crm.schema.manage` |
| `editor` | 编辑（新成员默认，偏内容） | 仅 `content.create`/本人内容库/工作台本人/偏好 |
| `sales` | 销售（线索/客户/任务本人 scope） | `list_own`、convert、import；不含 `task.assign`/`lead.assign` |
| `sales_manager` | 销售经理 | sales + `list_team`/`list_territory` + 分配 + 公开视图 + `analytics.view_all` |
| `marketing` | 市场运营 | 营销活动全功能 + 内容全链 + 线索本人/列表全公司只读+新建 |
| `platform_admin` | 平台运营（仅 Web `/admin`） | 租户/成员/转移管理员/全局账号/公共知识库/平台 AI；不参与企业 Membership |

**数据范围 scope（服务端强制，并集规则）**：`list_all` OR 本人 `owner_user_id` OR 汇报下级 `list_team` OR 销售地区子树 `list_territory`。联系人随客户继承；任务按 assignee/owner/territory 套用同一并集。「本人」=`*.view_own`/`*.list_own`；「全公司」=`*.view_all`/`*.list_all`。

**双端对齐**：Web 与 H5 强制对齐（选公司、设置、权限菜单、创作页接 Agent API、历史会话列表与切换）。

## 三、关键术语

- **多租户/Tenant**：一家企业，数据隔离单元（`tenant_id`）。
- **Membership**：账号在某公司的成员身份（角色、启用状态）；一人可多加公司。
- **ICP**：Ideal Customer Profile，租户理想客户画像，用于招标线索 L2 五维加权匹配（权重和=100%）。
- **CPQ**：Configure-Price-Quote；本产品为轻量版，强制写入现有 `quotes`+`quote_lines`。
- **BANT**：预算/授权/需求/时间评估（`bant_evaluations`），转化时联动建议金额。
- **scope**：数据可见性规则（`*.view_own`/`*.list_own`=当前用户；`*.view_all`/`*.list_all`=当前 tenant 全量）。
- **L1/L2**：L1=平台公共招标池（无 tenant_id，仅平台维护）；L2=租户匹配池（按 tenant 打分）。
- **claim**：销售将 L2 匹配线索纳入本租户 CRM 为线索（仅建 `leads`，禁建 `deals`）。
- **ReAct/propose-resume**：Agent 多步推理（MAX_STEPS=8）；先出方案暂停，用户确认后 resume。
- **RAG**：检索增强生成；MVP 关键词检索，Agent 侧 Hybrid（向量+关键词）。
- **额度**：平台默认 100 次/租户；正文成功扣 1，方案不扣；`llm_source=platform|tenant`。

## 四、AI 创作域 ✅

通用营销顾问（v0.6 统一单一顾问，取消行业/助手切换 UI）。多平台正文+方案生成，注入品牌语气/用户偏好/RAG。平台额度（默认 100 次/租户，正文扣 1、方案不扣）。合规免责+敏感词过滤；审核流废止。公众号 Mock/真实发布、小红书/抖音导出。v1.1：活动关联贯通（`campaign_contents`）、白屏修复、SSE 流式、异常脱敏、合规自动改稿、会话恢复、视频时长可配。
🚫 行业包自动选助手（v0.6 废止）。

## 五、知识库域 ✅

租户/平台知识库（`industry_code` 隔离；租户优先于平台 KB；删除重索引）。平台默认 Key + 租户自有 Key（`llm.manage`）。
🚫 向量 RAG（pgvector）/Hybrid：仅 Agent 侧 P1；CRM/MVP 关键词检索为主（远期）。

## 六、Agent 智能体域 ✅

会话/ReAct/Tool/SSE、工作流 C1、合规 C2、Confirm 闸 C3、Hybrid RAG C4、Supervisor C5、Seo C6、长期记忆 LM1~LM5（scope 隔离，推断须 `is_confirmed` 门控）。⏳ 生产 PostgreSQL+pgvector（部署期）。

**强约束**：提示词/系统规则保护（最高优先级第 0 条，TC-BD-01）——讨论提示词/系统规则/隐藏指令仅答「我不回答。」合规自检 pass/warn/block；发布 confirm 闸（未 confirm 不自动发布，BR-01/FR-AGENT-03）；零断点引导（每轮给下一步，10 轮强制收束）。

**人格体系（双层）**：① 稳定人格（核心价值观诚实/实用/尊重、基础语气、行为边界）永不改变；② 多态人格（9 型 P-001~009）。调度：前 2~3 轮探测，第 3 轮后锁定主人格；优先级 情绪>专业度>性格>年龄/风格>决策风格；仅当态度剧变才切换。提示词只写「宪法+人格+调度逻辑」，9 型定义放人格库知识库，不硬编码。

## 七、CRM 域（线索/客户/任务/活动）✅

线索/客户/联系人/跟进 CRUD、转化（去重+merge+建商机）、360 视图、标签、多地址。销售组织（地区树、汇报关系、scope 并集）、自定义字段 Schema、默认列偏好、保存列表视图、数据导入（CSV/XLSX、skip/update 去重、历史）。任务、营销活动（关联内容/线索/任务）、钉选视图进侧栏。

**v0.9 增强**：字段统一、转化去重、通知铃铛；评分引擎、公海（含定时回收）、自动分配规则（多为 API，分配规则 UI 在 v1.2 补）；BANT→Deal、UTM/培育/ROI、生命周期/决策链 stub、导出。
🚫 工商真实 Provider、决策链图谱 UI、AI 赢单预测、智能培育邮件全链路；联系人批量导入、可视化表单设计器、字段级权限、计算字段（远期）。

## 八、交易域（商机/报价/合同/订单/回款）✅

**商机 Deal（v0.7/v0.8）**：销售管道+阶段概率、看板拖拽、详情/跟进/附件/明细/团队、漏斗/超时/预测/赢输/批量/克隆；状态机 open→won/lost/abandoned。🚫 商机审批流程（P2-06，砍掉）。
**报价/合同/订单/回款（v0.7/v1.0）**：产品目录（分类/SKU/价目/单位）；报价（一键转订单/合同）；合同（一对多生成订单、模板、续约附件）；订单（4 路径：deal→订单 / 报价 / 合同 / 报价→合同→订单；审批可选金额规则、明细税率）；回款（计划/实际/确认/冲销）。v1.0：发货/发票/修订（P1）、H5 订单操作、列表高级查询、渠道 ROI。
> 订单四路径：避免平行主报价表。

## 九、招标线索域（v1.3，仅 Web）✅

- L1 平台公共池 `platform_tender_leads`：手工/Excel/附件 AI 人审；持久化 `source_url` 原文链接；仅 platform_admin 维护。
- L2 租户匹配池 `scored_tender_leads`：ICP 五维权重=100% 打分排序。
- claim → 仅写 `leads`（不直建 Deal）；状态机 pending/valid/invalid/expired；效果看板（W11–12 试点 UAT 可选）。
🚫 爬虫/抓取、租户向 L1 投稿、平行主报价表、BOM 约束。

## 十、轻量 CPQ 域（v1.3，仅 Web）✅

产品启用 CPQ（`products.cpq_enabled`）、参数价差映射（fixed/percentage/multiplier）、实时计价 `POST /crm/cpq/calculate`、价目扩展 `price_books`（禁止平行价目主数据）、毛利红线告警（须确认）、写入现有 `quotes`+`quote_lines`（可加 `cpq_config_snapshot`，可转订单）、异步 PDF、AI 需求解析人审、历史/复制、Deal/线索唤起 CPQ。
🚫 复杂 CPQ（BOM/约束引擎）、促销动态定价、AI 全自动报价。

## 十一、运营报表与提醒域（v1.2）✅

交易报表（路径占比/回款率/账龄/负责人业绩）、工作台回款/合同到期提醒、分配规则 Settings UI、发票核销、订单退款 Tab、阶段停留报表。⏳ CRM-1.5 内容外 CRM 报表（转化率/活动 ROI/待跟进队列）仍缺口。

## 十二、平台管理域（仅 Web /admin）✅

企业管理（租户列表/成员/转移管理员一换一）、账号管理（Membership 汇总/设 platform_admin/禁用/重置/删账号不删租户）、公共知识库/平台 AI。

## 十三、版本交付线与硬决议

v0.3.3（多租户/权限/额度）→ v0.4（Agent 半智能体）→ v0.5~2f（CRM 全链路）→ v0.6/0.6.1（统一顾问/人格）→ v0.7（交易全链路）→ v0.8（商机增强）→ v0.9（线索客户增强）→ v1.0（订单/合同/回款）→ v1.1（创作止血）→ v1.2（运营报表）→ **v1.3（招标+CPQ，current）**。

**v1.3 七项硬决议（D1~D7）**：
- D1 外源数据=招标线索，路由 `/crm/tender-leads`，不称「商机」。
- D2 `claim` 只写 `leads`，断言无新建 `deals`。
- D3 CPQ 强制写入现有 `quotes`+`quote_lines`。
- D4 价目扩展 `price_books`，禁止平行价目主数据。
- D5 L1 仅 platform_admin 维护，租户不可投稿，只消费 L2。
- D6 无爬虫。
- D7 附件 AI 必须人审（未 confirm 不得 published）。

**≥v1.4 候选（未立项）**：创作效果闭环（A/B、发布回流、热点、Multi-Agent）或财务售后闭环（退货、发票红冲、对账单、坏账）。

## 十四、非功能性需求与部署

- 架构：`LLMService → DeepSeek/OpenAI兼容/DashScope Provider ← 租户 llm_configs(优先)/环境变量/平台 AI`；API FastAPI+SQLAlchemy+Alembic(085)；Web Vue3+Vite；H5 uni-app；DB PostgreSQL+pgvector(生产)/SQLite(开发)。
- 部署：生产强制 PostgreSQL+pgvector，禁 SQLite；手机号/JWT 鉴权，验证码 Mock 固定 `1111`（开发/UAT）；Web/H5 经 Vite 代理访问 API。⏳ 生产部署上线、真实微信 API（需备案+服务号）。
- 自动验收：`tests/run_m0_m8.py`（M0~M8）、`tests/run_agent_a_c.py`（T0~AG8）、`tests/verify_tender_cpq_v13.py --mode impl`（v1.3 回归）。

## 十五、砍掉 / 延后需求清单

**SRS 暂不包含/远期**：小红书/抖音官方自动发布 API；计费与支付；向量 RAG 全量；微信 wx.login(P2)/小程序原生包；Twilio 通话；复杂 CPQ（BOM/约束引擎）；爬虫抓取平台；租户向公共招标池投稿；可视化表单设计器/计算字段/字段级权限；联系人批量导入；内容实体自定义字段；外部 Frappe CRM 对接（已被内置 CRM 替代）。
**各版刻意砍掉**：v0.8 商机审批(P2-06)/智能查重/AI 赢单预测/商机共享/价格表；v0.9 工商真实 Provider/决策链 UI 图谱/智能培育全链路/Web 全量配置台；v1.1 场景选择 UI/A/B/热点/Multi-Agent；v1.2 退货/红冲/对账单/Create A/B。
**≥v1.4 明确延后**：创作效果闭环（A/B、发布回流、热点、Multi-Agent）；财务售后闭环（退货、红冲、对账单、坏账）；CRM-1.5 报表（转化率/活动 ROI/待跟进队列/负责人业绩）。

## 十六、成功标准与风险

**成功标准**：主链路贯通运行；tenant_id 硬隔离 + scope 并集服务端强制；Agent 提示词保护(TC-BD-01)/发布 confirm 闸/合规自检 100% 触发；M0~M8 + T0~AG8 + v1.3 回归全绿。
**风险**：① 文档滞后于代码——《版本交付线梳理》标 083，实际迁移已至 085（084 编号规则 suffix、085 平台招标 L1 销售跟进字段），建议同步。② 上线阻塞——生产部署、真实微信对接（需备案+服务号）、生产 PostgreSQL+pgvector 仍依赖环境，未完成。

---
*修订记录：v1.3 整合 PRD 重建，覆盖 v0.3.3→v1.3 全链路，对齐 Alembic 085 与 v1.3 七项硬决议（2026-07-17）。原稿为 docs/需求规格.md 及分散模块级 PRD。*
