<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'

const route = useRoute()
const router = useRouter()

const saving = ref(false)
const calculating = ref(false)
const customerLoading = ref(false)
const customerOptions = ref([])
const dealOptions = ref([])
const dealLoading = ref(false)
const cpqProducts = ref([])
const params = ref([])
const calc = ref(null)
const configTab = ref('form')
const aiText = ref('')
const aiParsing = ref(false)
const aiResult = ref(null)
const aiSelected = ref([])
const form = ref({
  customer_id: '',
  deal_id: '',
  scored_tender_lead_id: '',
  subject: '',
  product_id: '',
  quantity: 1,
  discount_rate: 0,
  shipping_cost: 0,
  min_margin_pct: null,
  selected_params: {},
})
const contextHint = ref('')

const selectedProduct = computed(() =>
  cpqProducts.value.find((p) => p.id === form.value.product_id) || null,
)

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({
      id: c.id,
      company_name: c.company_name,
    }))
  } catch {
    customerOptions.value = []
  } finally {
    customerLoading.value = false
  }
}

function formatDealLabel(d) {
  const amt = Number(d.amount || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
  const st = d.status && d.status !== 'open' ? ` · ${d.status}` : ''
  return `${d.title || '未命名商机'}（¥${amt}${st}）`
}

async function loadDealOptions() {
  dealLoading.value = true
  try {
    const listParams = { page: 1, page_size: 50, status: 'open' }
    if (form.value.customer_id) listParams.customer_id = form.value.customer_id
    const { data } = await crmApi.listDeals(listParams)
    let items = data.items || []
    if (form.value.deal_id && !items.some((d) => String(d.id) === String(form.value.deal_id))) {
      try {
        const { data: deal } = await crmApi.getDeal(form.value.deal_id)
        if (deal) items = [deal, ...items]
      } catch {
        /* keep */
      }
    }
    dealOptions.value = items.map((d) => ({
      id: d.id,
      label: formatDealLabel(d),
      customer_id: d.customer_id,
    }))
  } catch {
    dealOptions.value = []
  } finally {
    dealLoading.value = false
  }
}

async function onCustomerChange() {
  form.value.deal_id = ''
  await loadDealOptions()
}

async function onDealChange(dealId) {
  if (!dealId) return
  const opt = dealOptions.value.find((d) => String(d.id) === String(dealId))
  const customerId = opt?.customer_id
  if (!customerId || form.value.customer_id) return
  form.value.customer_id = customerId
  try {
    const { data: cust } = await crmApi.getCustomer(customerId)
    customerOptions.value = [
      { id: customerId, company_name: cust?.company_name || '(商机客户)' },
      ...customerOptions.value.filter((c) => String(c.id) !== String(customerId)),
    ]
  } catch {
    if (!customerOptions.value.some((c) => String(c.id) === String(customerId))) {
      customerOptions.value = [{ id: customerId, company_name: '(商机客户)' }, ...customerOptions.value]
    }
  }
  await loadDealOptions()
}

async function loadCpqProducts() {
  try {
    const { data } = await crmApi.listCpqProducts()
    cpqProducts.value = Array.isArray(data) ? data : []
  } catch {
    cpqProducts.value = []
  }
}

async function onProductChange() {
  form.value.selected_params = {}
  params.value = []
  calc.value = null
  const pid = form.value.product_id
  if (!pid) return
  const p = selectedProduct.value
  if (p && !form.value.subject) {
    form.value.subject = `${p.name} CPQ 报价`
  }
  try {
    const { data } = await crmApi.listCpqProductParams(pid)
    params.value = Array.isArray(data) ? data.filter((x) => x.is_active !== false) : []
    for (const param of params.value) {
      if (param.param_type === 'select' && Array.isArray(param.options) && param.options.length) {
        form.value.selected_params[param.param_name] = String(param.options[0])
      } else {
        form.value.selected_params[param.param_name] = ''
      }
    }
  } catch {
    params.value = []
  }
  await runCalculate()
}

function buildCalcBody(confirmLow = false) {
  return {
    product_id: form.value.product_id,
    quantity: Number(form.value.quantity) || 1,
    selected_params: { ...form.value.selected_params },
    discount_rate: Number(form.value.discount_rate) || 0,
    shipping_cost: Number(form.value.shipping_cost) || 0,
    min_margin_pct: form.value.min_margin_pct != null && form.value.min_margin_pct !== ''
      ? Number(form.value.min_margin_pct)
      : null,
    confirm_low_margin: confirmLow,
  }
}

async function runCalculate(confirmLow = false) {
  if (!form.value.product_id) {
    calc.value = null
    return null
  }
  calculating.value = true
  try {
    const { data } = await crmApi.calculateCpq(buildCalcBody(confirmLow))
    calc.value = data
    return data
  } catch (e) {
    let detail = null
    try { detail = JSON.parse(e.message) } catch { /* not json */ }
    if (detail?.code === 'LOW_MARGIN') {
      calc.value = {
        ...(calc.value || {}),
        margin_warning: true,
        profit_margin_pct: detail.profit_margin_pct,
        final_price: calc.value?.final_price,
      }
      throw Object.assign(new Error(detail.message || e.message), { lowMargin: true, detail })
    }
    calc.value = null
    throw e
  } finally {
    calculating.value = false
  }
}

let calcTimer = null
function scheduleCalculate() {
  if (calcTimer) clearTimeout(calcTimer)
  calcTimer = setTimeout(() => {
    runCalculate().catch(() => {})
  }, 280)
}

watch(
  () => [
    form.value.quantity,
    form.value.discount_rate,
    form.value.shipping_cost,
    form.value.min_margin_pct,
    form.value.selected_params,
  ],
  () => {
    if (form.value.product_id) scheduleCalculate()
  },
  { deep: true },
)

function formatAmount(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function runAiParse() {
  if (!form.value.product_id) { ElMessage.warning('请先选择产品'); return }
  if (!aiText.value.trim()) { ElMessage.warning('请粘贴客户需求文本'); return }
  aiParsing.value = true
  aiResult.value = null
  aiSelected.value = []
  try {
    const { data } = await crmApi.parseCpqRequirements({
      product_id: form.value.product_id,
      text: aiText.value.trim(),
    })
    aiResult.value = data
    aiSelected.value = (data.recommendations || []).map((r) => r.param_name)
    if (!(data.recommendations || []).length) {
      ElMessage.info('未识别到可匹配参数，请改写需求或手工配置')
    }
  } catch (e) {
    ElMessage.error(e.message || '解析失败')
  } finally {
    aiParsing.value = false
  }
}

function adoptAiRecommendations() {
  if (!aiResult.value?.recommendations?.length) {
    ElMessage.warning('没有可采纳的推荐')
    return
  }
  const picked = aiResult.value.recommendations.filter((r) =>
    aiSelected.value.includes(r.param_name),
  )
  if (!picked.length) {
    ElMessage.warning('请勾选要采纳的推荐')
    return
  }
  for (const r of picked) {
    if (r.suggested_value !== undefined && r.suggested_value !== '') {
      form.value.selected_params[r.param_name] = r.suggested_value
    }
  }
  if (aiResult.value.quantity != null && Number(aiResult.value.quantity) > 0) {
    form.value.quantity = Number(aiResult.value.quantity)
  }
  configTab.value = 'form'
  ElMessage.success(`已采纳 ${picked.length} 项（人审写入配置）`)
  scheduleCalculate()
}

async function submit() {
  if (!form.value.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!form.value.subject?.trim()) { ElMessage.warning('请填写主题'); return }
  if (!form.value.product_id) { ElMessage.warning('请选择 CPQ 产品'); return }

  saving.value = true
  try {
    let confirmLow = false
    try {
      await runCalculate(false)
    } catch (e) {
      if (e.lowMargin) {
        await ElMessageBox.confirm(
          `${e.message || '毛利率低于红线'}。确认仍要保存报价？`,
          '低毛利确认',
          { type: 'warning', confirmButtonText: '确认保存', cancelButtonText: '取消' },
        )
        confirmLow = true
        await runCalculate(true)
      } else {
        throw e
      }
    }

    const payload = {
      customer_id: form.value.customer_id,
      deal_id: form.value.deal_id || null,
      scored_tender_lead_id: form.value.scored_tender_lead_id || null,
      subject: form.value.subject.trim(),
      ...buildCalcBody(confirmLow),
    }
    const { data } = await crmApi.createCpqQuote(payload)
    ElMessage.success('已保存为报价草稿')
    router.push(`/crm/quotes/${data.id}`)
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadCpqProducts(), searchCustomers()])
  if (route.query.from_quote_id) {
    try {
      const { data } = await crmApi.getQuote(String(route.query.from_quote_id))
      const snap = data.cpq_config_snapshot || {}
      form.value.customer_id = data.customer_id
      form.value.deal_id = data.deal_id || ''
      form.value.scored_tender_lead_id = snap.scored_tender_lead_id || ''
      form.value.subject = `${data.subject || '报价'}（改参）`
      if (data.customer_id) {
        customerOptions.value = [{
          id: data.customer_id,
          company_name: '(来源报价客户)',
        }]
      }
      if (snap.product_id) {
        form.value.product_id = snap.product_id
        form.value.quantity = Number(snap.quantity) || 1
        form.value.discount_rate = Number(snap.discount_rate) || 0
        form.value.shipping_cost = Number(snap.shipping_cost) || 0
        form.value.min_margin_pct = snap.min_margin_pct != null ? Number(snap.min_margin_pct) : null
        await onProductChange()
        form.value.selected_params = { ...(snap.selected_params || {}) }
        await runCalculate().catch(() => {})
      }
    } catch (e) {
      ElMessage.error(e.message || '加载来源报价失败')
    }
  } else {
    if (route.query.product_id) {
      form.value.product_id = String(route.query.product_id)
      await onProductChange()
    }
    if (route.query.customer_id) {
      form.value.customer_id = String(route.query.customer_id)
    }
    if (route.query.deal_id) {
      form.value.deal_id = String(route.query.deal_id)
      try {
        const { data: deal } = await crmApi.getDeal(String(route.query.deal_id))
        if (deal?.customer_id) {
          form.value.customer_id = deal.customer_id
          customerOptions.value = [{
            id: deal.customer_id,
            company_name: deal.customer_name || '(商机客户)',
          }]
        }
        if (!form.value.subject && deal?.title) {
          form.value.subject = `${deal.title} CPQ 报价`
        }
        contextHint.value = '已从商机带入客户与关联'
      } catch (e) {
        ElMessage.warning(e.message || '加载商机失败，请手动选择客户')
      }
    }
    if (route.query.tender_lead_id) {
      form.value.scored_tender_lead_id = String(route.query.tender_lead_id)
      try {
        const { data: scored } = await crmApi.getTenderLead(String(route.query.tender_lead_id))
        if (!scored.converted_lead_id) {
          ElMessage.warning('请先纳入 CRM 线索并转化为客户后再报价')
          contextHint.value = '招标线索尚未纳入 CRM，暂不可报价'
        } else {
          const { data: lead } = await crmApi.getLead(String(scored.converted_lead_id))
          if (!lead?.converted_customer_id) {
            ElMessage.warning('请先将线索转化为客户后再报价')
            contextHint.value = '线索未转客户，暂不可报价'
            router.replace({ path: `/crm/leads/${lead.id}` })
          } else {
            form.value.customer_id = lead.converted_customer_id
            customerOptions.value = [{
              id: lead.converted_customer_id,
              company_name: lead.company_name || '(招标线索客户)',
            }]
            if (!form.value.subject) {
              form.value.subject = `${scored.buyer_name || lead.company_name || '招标'} CPQ 报价`
            }
            if (scored.summary || scored.product_name) {
              aiText.value = [scored.product_name, scored.summary, scored.quantity].filter(Boolean).join('\n')
            }
            contextHint.value = '已从招标线索带入客户（须已 claim + 转客户）'
          }
        }
      } catch (e) {
        ElMessage.warning(e.message || '加载招标线索失败')
      }
    } else if (route.query.lead_id && route.query.customer_id) {
      contextHint.value = '已从线索带入客户'
    }
  }
  await loadDealOptions()
})
</script>

<template>
  <div class="cpq-page">
    <div class="cpq-page__back">
      <el-button link @click="router.push('/crm/quotes')">
        <el-icon><ArrowLeft /></el-icon> 返回报价列表
      </el-button>
    </div>

    <div class="page-card cpq-page__head">
      <h2 class="cpq-page__title">CPQ 配置报价</h2>
      <p class="hint">选产品与参数 → 实时计价 → 保存到现有报价单（含配置快照）</p>
      <el-alert
        v-if="contextHint"
        :title="contextHint"
        type="info"
        :closable="false"
        style="margin-top: 10px"
      />
    </div>

    <div class="cpq-page__grid">
      <div class="page-card">
        <el-form label-width="96px">
          <el-form-item label="客户" required>
            <el-select
              v-model="form.customer_id"
              filterable
              remote
              clearable
              :remote-method="searchCustomers"
              :loading="customerLoading"
              placeholder="搜索客户"
              style="width: 100%"
              @change="onCustomerChange"
            >
              <el-option
                v-for="c in customerOptions"
                :key="c.id"
                :label="c.company_name"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="关联商机">
            <el-select
              v-model="form.deal_id"
              filterable
              clearable
              :loading="dealLoading"
              placeholder="可选，按客户筛选进行中商机"
              style="width: 100%"
              @change="onDealChange"
            >
              <el-option
                v-for="d in dealOptions"
                :key="d.id"
                :label="d.label"
                :value="d.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="主题" required>
            <el-input v-model="form.subject" maxlength="200" placeholder="报价主题" />
          </el-form-item>
          <el-form-item label="产品" required>
            <el-select
              v-model="form.product_id"
              filterable
              placeholder="选择已启用 CPQ 的产品"
              style="width: 100%"
              @change="onProductChange"
            >
              <el-option
                v-for="p in cpqProducts"
                :key="p.id"
                :label="`${p.name}（¥${formatAmount(p.list_price)}）`"
                :value="p.id"
              />
            </el-select>
            <p v-if="!cpqProducts.length" class="hint">
              暂无 CPQ 产品，请先在产品详情开启 CPQ 并配置参数
            </p>
          </el-form-item>
          <el-form-item label="数量">
            <el-input-number v-model="form.quantity" :min="0.01" :precision="2" :controls="false" style="width: 100%" />
          </el-form-item>
          <el-form-item label="折扣 %">
            <el-input-number v-model="form.discount_rate" :min="0" :max="100" :precision="2" :controls="false" style="width: 100%" />
          </el-form-item>
          <el-form-item label="运费">
            <el-input-number v-model="form.shipping_cost" :min="0" :precision="2" :controls="false" style="width: 100%" />
          </el-form-item>
          <el-form-item label="毛利红线 %">
            <el-input-number
              v-model="form.min_margin_pct"
              :min="0"
              :max="100"
              :precision="2"
              :controls="false"
              placeholder="可选"
              style="width: 100%"
            />
          </el-form-item>

          <el-tabs v-model="configTab" class="config-tabs">
            <el-tab-pane label="表单配置" name="form">
              <template v-if="params.length">
                <el-form-item
                  v-for="param in params"
                  :key="param.id"
                  :label="param.param_name"
                >
                  <el-select
                    v-if="param.param_type === 'select'"
                    v-model="form.selected_params[param.param_name]"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="o in (param.options || [])"
                      :key="String(o)"
                      :label="String(o)"
                      :value="String(o)"
                    />
                  </el-select>
                  <el-input-number
                    v-else-if="param.param_type === 'number'"
                    v-model="form.selected_params[param.param_name]"
                    :controls="false"
                    style="width: 100%"
                  />
                  <el-input
                    v-else
                    v-model="form.selected_params[param.param_name]"
                  />
                </el-form-item>
              </template>
              <p v-else class="hint">选择产品后显示可配置参数</p>
            </el-tab-pane>

            <el-tab-pane label="AI 需求解析" name="ai">
              <p class="hint ai-hint">粘贴客户需求 → 生成推荐 → <strong>勾选后采纳</strong>（不会自动写入）</p>
              <el-input
                v-model="aiText"
                type="textarea"
                :rows="6"
                placeholder="例如：需要 2 台不锈钢材质水泵，用于化工场景…"
              />
              <div class="ai-actions">
                <el-button
                  type="primary"
                  :loading="aiParsing"
                  :disabled="!form.product_id"
                  @click="runAiParse"
                >解析推荐</el-button>
                <el-button
                  :disabled="!aiResult?.recommendations?.length"
                  @click="adoptAiRecommendations"
                >采纳选中</el-button>
              </div>
              <div v-if="aiResult" class="ai-result">
                <p class="hint">来源：{{ aiResult.source }} · {{ aiResult.notes }}</p>
                <p v-if="aiResult.quantity != null" class="hint">建议数量：{{ aiResult.quantity }}</p>
                <el-checkbox-group v-model="aiSelected">
                  <div
                    v-for="r in aiResult.recommendations"
                    :key="r.param_name"
                    class="ai-rec"
                  >
                    <el-checkbox :value="r.param_name">
                      <span class="ai-rec__name">{{ r.param_name }}</span>
                      → <strong>{{ r.suggested_value || '（待填）' }}</strong>
                      <span class="hint">（置信 {{ Math.round((r.confidence || 0) * 100) }}%）{{ r.reason }}</span>
                    </el-checkbox>
                  </div>
                </el-checkbox-group>
                <el-empty
                  v-if="!aiResult.recommendations?.length"
                  description="无推荐项"
                  :image-size="48"
                />
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-form>

        <div class="cpq-page__actions">
          <el-button @click="router.push('/crm/quotes')">取消</el-button>
          <el-button type="primary" :loading="saving" @click="submit">保存为报价</el-button>
        </div>
      </div>

      <div class="page-card calc-card" v-loading="calculating">
        <h3 class="calc-card__title">计价预览</h3>
        <template v-if="calc">
          <div class="calc-row"><span>基价</span><strong>¥{{ formatAmount(calc.base_unit_price) }}</strong></div>
          <div class="calc-row"><span>调整后单价</span><strong>¥{{ formatAmount(calc.adjusted_unit_price) }}</strong></div>
          <div class="calc-row"><span>小计</span><strong>¥{{ formatAmount(calc.subtotal) }}</strong></div>
          <div class="calc-row"><span>折扣</span><strong>-¥{{ formatAmount(calc.discount_amount) }}</strong></div>
          <div class="calc-row"><span>运费</span><strong>¥{{ formatAmount(calc.shipping_cost) }}</strong></div>
          <div class="calc-row calc-row--total"><span>成交价</span><strong>¥{{ formatAmount(calc.final_price) }}</strong></div>
          <div class="calc-row">
            <span>毛利率</span>
            <strong :class="{ warn: calc.margin_warning }">
              {{ calc.profit_margin_pct != null ? calc.profit_margin_pct + '%' : '—' }}
            </strong>
          </div>
          <div class="calc-meta">取价来源：{{ calc.price_source }}</div>
          <ul v-if="calc.param_adjustments?.length" class="adj-list">
            <li v-for="(a, i) in calc.param_adjustments" :key="i">
              {{ a.param_name }}={{ a.option_value }} → {{ a.delta >= 0 ? '+' : '' }}¥{{ formatAmount(a.delta) }}
            </li>
          </ul>
        </template>
        <el-empty v-else description="选择产品后显示计价" :image-size="64" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.cpq-page__back { margin-bottom: 8px; }
.cpq-page__head { margin-bottom: 16px; }
.cpq-page__title { margin: 0 0 6px; font-size: 20px; font-weight: 600; }
.cpq-page__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.8fr);
  gap: 16px;
  align-items: start;
}
.cpq-page__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.hint { margin: 4px 0 0; font-size: 12px; color: var(--el-text-color-secondary); }
.config-tabs { margin-top: 4px; }
.ai-hint { margin-bottom: 8px; }
.ai-actions { display: flex; gap: 8px; margin: 10px 0; }
.ai-result { margin-top: 8px; }
.ai-rec { margin-bottom: 8px; }
.ai-rec__name { color: var(--el-text-color-regular); }
.calc-card__title { margin: 0 0 16px; font-size: 16px; }
.calc-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
}
.calc-row--total { font-size: 15px; padding-top: 12px; }
.calc-row .warn { color: var(--el-color-danger); }
.calc-meta { margin-top: 12px; font-size: 12px; color: var(--el-text-color-secondary); }
.adj-list {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
@media (max-width: 900px) {
  .cpq-page__grid { grid-template-columns: 1fr; }
}
</style>
