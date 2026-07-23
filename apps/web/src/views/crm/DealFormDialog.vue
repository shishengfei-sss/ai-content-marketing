<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Delete, Plus, Goods } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { formatApiError } from '../../utils/apiError'
import CrmProductPicker from '../../components/crm/CrmProductPicker.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  pipelines: { type: Array, default: () => [] },
  record: { type: Object, default: null },
  mode: { type: String, default: 'create' },
})
const emit = defineEmits(['update:visible', 'saved'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)
const customerOptions = ref([])
const customerLoading = ref(false)
const contactOptions = ref([])
const contactLoading = ref(false)
const form = ref(emptyForm())
const pickerVisible = ref(false)
const pickerMultiple = ref(true)
const replaceLineIndex = ref(-1)

function emptyForm() {
  return {
    title: '',
    customer_id: '',
    contact_id: '',
    pipeline_id: '',
    stage_id: '',
    amount: 0,
    expected_close_date: '',
    probability: null,
    status: 'open',
    source: '',
    loss_reason: '',
    description: '',
    next_step: '',
    deal_type: '',
    priority: 'medium',
    competitor: '',
    contact_role: '',
    lines: [],
  }
}

function emptyLine() {
  return {
    product_id: '',
    product_code: '',
    product_name: '',
    unit: '',
    quantity: 1,
    unit_price: 0,
    discount_percent: 0,
    tax_rate: null,
    tax_amount: 0,
    subtotal: 0,
  }
}

function money(n) {
  return Math.round(Number(n || 0) * 100) / 100
}

function formatMoney(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 镜像 tax_engine：行未税 + 税额 + ±0.01 末行尾差 */
function recomputeAllLines() {
  const lines = form.value.lines
  lines.forEach((l) => {
    const qty = Number(l.quantity) || 0
    const price = Number(l.unit_price) || 0
    const d = Number(l.discount_percent) || 0
    const ex = money(qty * price * (1 - d / 100))
    l.subtotal = ex
    const rate = l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null
    l.tax_amount = rate != null && rate !== 0 ? money(ex * (rate / 100)) : 0
  })
  let exactAcc = 0
  lines.forEach((l) => {
    const rate = l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null
    if (rate != null && rate !== 0) exactAcc += Number(l.subtotal) * (rate / 100)
  })
  const exact = money(exactAcc)
  const taxSum = money(lines.reduce((a, l) => a + Number(l.tax_amount || 0), 0))
  const delta = money(exact - taxSum)
  if (Math.abs(delta) === 0.01 && lines.length) {
    let idx = lines.length - 1
    for (let i = lines.length - 1; i >= 0; i -= 1) {
      if (lines[i].tax_rate != null && Number(lines[i].tax_rate) !== 0) {
        idx = i
        break
      }
    }
    lines[idx].tax_amount = money(Number(lines[idx].tax_amount || 0) + delta)
  }
  if (lines.length) {
    form.value.amount = money(lines.reduce((s, l) => s + Number(l.subtotal || 0), 0))
  }
}

const lineCount = computed(() => form.value.lines.length)
const linesExTotal = computed(() =>
  money(form.value.lines.reduce((s, l) => s + (Number(l.subtotal) || 0), 0)),
)
const linesTaxTotal = computed(() =>
  money(form.value.lines.reduce((s, l) => s + (Number(l.tax_amount) || 0), 0)),
)
const linesInclTotal = computed(() => money(linesExTotal.value + linesTaxTotal.value))
const hasLines = computed(() => form.value.lines.length > 0)

const stages = computed(() => {
  const p = props.pipelines.find((x) => String(x.id) === String(form.value.pipeline_id))
  return p?.stages || []
})

const isEdit = computed(() => props.mode === 'edit' && props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑商机' : '新建商机'))

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({
      id: c.id,
      company_name: c.company_name,
    }))
  } catch (e) {
    customerOptions.value = []
  } finally {
    customerLoading.value = false
  }
}

async function loadContacts(customerId) {
  if (!customerId) { contactOptions.value = []; return }
  contactLoading.value = true
  try {
    const { data } = await crmApi.listContacts(customerId)
    contactOptions.value = (data || []).map((c) => ({
      id: c.id,
      label: c.name || c.contact_name || '(未命名)',
    }))
  } catch (e) {
    contactOptions.value = []
  } finally {
    contactLoading.value = false
  }
}

function openAddProducts() {
  pickerMultiple.value = true
  replaceLineIndex.value = -1
  pickerVisible.value = true
}

function openReplaceProduct(idx) {
  pickerMultiple.value = false
  replaceLineIndex.value = idx
  pickerVisible.value = true
}

function addBlankLine() {
  form.value.lines.push(emptyLine())
}

function removeLine(idx) {
  form.value.lines.splice(idx, 1)
  recomputeAllLines()
}

function duplicateLine(idx) {
  const src = form.value.lines[idx]
  if (!src) return
  form.value.lines.splice(idx + 1, 0, { ...src, quantity: Number(src.quantity) || 1 })
  recomputeAllLines()
}

const TAX_PRESETS = [13, 9, 6, 0]

function applyProductToLine(line, product) {
  line.product_id = product.id
  line.product_code = product.code || ''
  line.product_name = product.name || ''
  line.unit = product.unit || ''
  const taxRate = product.default_tax_rate != null ? Number(product.default_tax_rate) : null
  line.tax_rate = taxRate
  let unitPrice = Number(product.list_price) || 0
  if (product.price_includes_tax && taxRate != null && taxRate > 0) {
    unitPrice = money(unitPrice / (1 + taxRate / 100))
  }
  line.unit_price = unitPrice
  if (!line.quantity) line.quantity = 1
}

function setTaxRate(line, rate) {
  line.tax_rate = rate
  recomputeAllLines()
}

function onProductsPicked(products) {
  if (!products?.length) return
  if (!pickerMultiple.value && replaceLineIndex.value >= 0) {
    const line = form.value.lines[replaceLineIndex.value]
    if (line) {
      applyProductToLine(line, products[0])
      recomputeAllLines()
    }
    return
  }
  for (const p of products) {
    const line = emptyLine()
    applyProductToLine(line, p)
    form.value.lines.push(line)
  }
  recomputeAllLines()
  ElMessage.success(`已添加 ${products.length} 个产品`)
}

async function onCustomerChange() {
  form.value.contact_id = ''
  await loadContacts(form.value.customer_id)
}

function syncStageProbability() {
  const stage = stages.value.find((s) => String(s.id) === String(form.value.stage_id))
  if (stage?.probability != null) form.value.probability = stage.probability
}

function onPipelineChange() {
  form.value.stage_id = stages.value[0]?.id || ''
  syncStageProbability()
}

function onStageChange() {
  syncStageProbability()
}

function resetForm() {
  form.value = emptyForm()
  if (props.pipelines.length) {
    const def = props.pipelines.find((p) => p.is_default) || props.pipelines[0]
    form.value.pipeline_id = def?.id || ''
    form.value.stage_id = def?.stages?.[0]?.id || ''
    syncStageProbability()
  }
  form.value.status = 'open'
  contactOptions.value = []
}

async function loadDeal() {
  if (!props.record?.id) { resetForm(); return }
  try {
    const { data } = await crmApi.getDeal(props.record.id)
    form.value = {
      title: data.title || '',
      customer_id: data.customer_id || '',
      contact_id: data.contact_id || '',
      pipeline_id: data.pipeline_id || '',
      stage_id: data.stage_id || '',
      amount: data.amount ?? 0,
      expected_close_date: data.expected_close_date || '',
      probability: data.probability ?? null,
      status: data.status || 'open',
      source: data.source || '',
      loss_reason: data.loss_reason || '',
      description: data.description || '',
      next_step: data.next_step || '',
      deal_type: data.deal_type || '',
      priority: data.priority || 'medium',
      competitor: data.competitor || '',
      contact_role: data.contact_role || '',
      lines: (data.lines || []).map((l) => ({
        product_id: l.product_id || '',
        product_code: l.product_code || '',
        product_name: l.product_name || '',
        unit: l.unit || '',
        quantity: Number(l.quantity) || 1,
        unit_price: Number(l.unit_price) || 0,
        discount_percent: Number(l.discount_percent) || 0,
        tax_rate: l.tax_rate != null ? Number(l.tax_rate) : null,
        tax_amount: Number(l.tax_amount || 0),
        subtotal: Number(l.subtotal) || 0,
      })),
    }
    recomputeAllLines()
    if (data.customer_id) {
      customerOptions.value = [{ id: data.customer_id, company_name: data.customer_name || '(已绑定客户)' }]
      await loadContacts(data.customer_id)
    }
  } catch (e) {
    ElMessage.error(e.message || '加载商机失败')
    resetForm()
  }
}

async function submit() {
  if (!form.value.title?.trim()) { ElMessage.warning('请填写商机名称'); return }
  if (!form.value.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!form.value.pipeline_id) { ElMessage.warning('请选择销售管道'); return }
  if (!form.value.stage_id) { ElMessage.warning('请选择阶段'); return }
  for (const l of form.value.lines) {
    if (!String(l.product_name || '').trim()) {
      ElMessage.warning('请填写明细名称')
      return
    }
  }
  recomputeAllLines()

  const payload = {
    title: form.value.title.trim(),
    customer_id: form.value.customer_id,
    pipeline_id: form.value.pipeline_id,
    stage_id: form.value.stage_id,
    amount: form.value.amount == null || form.value.amount === '' ? 0 : Number(form.value.amount),
    expected_close_date: form.value.expected_close_date || null,
    probability: form.value.probability === '' || form.value.probability == null
      ? null
      : Number(form.value.probability),
    status: form.value.status,
    source: form.value.source || null,
    loss_reason: form.value.loss_reason || null,
    description: form.value.description || null,
    next_step: form.value.next_step || null,
    deal_type: form.value.deal_type || null,
    priority: form.value.priority || 'medium',
    competitor: form.value.competitor || null,
    contact_role: form.value.contact_role || null,
    lines: form.value.lines.map((l, i) => ({
      product_id: l.product_id || null,
      product_name: String(l.product_name || '').trim(),
      unit: l.unit || null,
      quantity: Number(l.quantity) || 0,
      unit_price: Number(l.unit_price) || 0,
      discount_percent: Number(l.discount_percent) || 0,
      tax_rate: l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null,
      tax_amount: Number(l.tax_amount || 0),
      subtotal: Number(l.subtotal) || 0,
      sort_order: i,
    })),
  }
  if (form.value.contact_id) payload.contact_id = form.value.contact_id

  saving.value = true
  try {
    if (isEdit.value) {
      await crmApi.updateDeal(props.record.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createDeal(payload)
      ElMessage.success('商机已创建')
    }
    dialogVisible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

watch(dialogVisible, async (v) => {
  if (!v) return
  if (isEdit.value) {
    await loadDeal()
  } else {
    resetForm()
    if (!customerOptions.value.length) searchCustomers('')
  }
})

const statusOptions = [
  { value: 'open', label: '进行中' },
  { value: 'won', label: '赢单' },
  { value: 'lost', label: '输单' },
  { value: 'abandoned', label: '放弃' },
]
const sourceOptions = [
  '官网', '公众号', '小红书', '抖音', '线下', '转介绍', '电话', '导入', '营销活动', '其他',
].map((v) => ({ value: v, label: v }))
const dealTypeOptions = [
  { value: '新业务', label: '新业务' },
  { value: '续约', label: '续约' },
  { value: '升级', label: '升级' },
  { value: '交叉销售', label: '交叉销售' },
]
const priorityOptions = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]
const contactRoleOptions = [
  { value: '决策者', label: '决策者' },
  { value: '影响者', label: '影响者' },
  { value: '使用者', label: '使用者' },
  { value: '评估者', label: '评估者' },
]
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="980px"
    destroy-on-close
    align-center
    class="deal-form-dialog"
  >
    <el-form label-width="100px" :model="form" class="deal-form">
      <section class="deal-form__section">
        <h4 class="deal-form__section-title">基本信息</h4>
        <el-form-item label="商机名称" required>
          <el-input v-model="form.title" placeholder="请输入商机名称" maxlength="200" />
        </el-form-item>
        <div class="deal-form__grid2">
          <el-form-item label="客户" required>
            <el-select
              v-model="form.customer_id"
              filterable
              remote
              :remote-method="searchCustomers"
              :loading="customerLoading"
              placeholder="选择客户"
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
          <el-form-item label="联系人">
            <el-select
              v-model="form.contact_id"
              clearable
              :loading="contactLoading"
              :placeholder="form.customer_id ? '选择联系人' : '请先选择客户'"
              :disabled="!form.customer_id"
              style="width: 100%"
            >
              <el-option v-for="c in contactOptions" :key="c.id" :label="c.label" :value="c.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="商机类型">
          <el-select v-model="form.deal_type" clearable placeholder="请选择" style="width: 100%">
            <el-option v-for="o in dealTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
      </section>

      <section class="deal-form__section">
        <h4 class="deal-form__section-title">销售信息</h4>
        <div class="deal-form__grid2">
          <el-form-item label="销售管道" required>
            <el-select v-model="form.pipeline_id" placeholder="默认管道" style="width: 100%" @change="onPipelineChange">
              <el-option v-for="p in pipelines" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="阶段" required>
            <el-select v-model="form.stage_id" style="width: 100%" @change="onStageChange">
              <el-option v-for="s in stages" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
        </div>
        <div class="deal-form__amount-row">
          <el-form-item label="商机金额" class="deal-form__amount">
            <el-input-number
              v-model="form.amount"
              :min="0"
              :precision="2"
              :controls="false"
              :disabled="hasLines"
              placeholder="0.00"
              style="width: 100%"
            />
            <p v-if="hasLines" class="deal-form__hint">已按产品明细未税合计自动汇总</p>
          </el-form-item>
          <el-form-item label="概率" class="deal-form__probability">
            <div class="deal-form__probability-input">
              <el-input-number
                v-model="form.probability"
                :min="0"
                :max="100"
                :precision="0"
                :controls="false"
                style="width: 100%"
              />
              <span class="deal-form__percent">%</span>
            </div>
          </el-form-item>
        </div>
        <el-form-item label="预计成交日">
          <el-date-picker
            v-model="form.expected_close_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择日期"
            style="width: 100%"
          />
        </el-form-item>
      </section>

      <section class="deal-form__section">
        <h4 class="deal-form__section-title">分类与跟踪</h4>
        <div class="deal-form__grid2">
          <el-form-item label="优先级">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option v-for="o in priorityOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源">
            <el-select v-model="form.source" clearable placeholder="请选择" style="width: 100%">
              <el-option v-for="s in sourceOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="竞争对手">
            <el-input v-model="form.competitor" maxlength="200" placeholder="主要竞争对手名称" />
          </el-form-item>
          <el-form-item label="联系人角色">
            <el-select v-model="form.contact_role" clearable placeholder="请选择" style="width: 100%">
              <el-option v-for="o in contactRoleOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
        </div>
        <template v-if="isEdit">
          <el-form-item label="商机状态">
            <el-select v-model="form.status" style="width: 100%">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.status === 'lost'" label="输单原因">
            <el-input v-model="form.loss_reason" maxlength="200" />
          </el-form-item>
        </template>
      </section>

      <section class="deal-form__section">
        <h4 class="deal-form__section-title">描述与下一步</h4>
        <el-form-item label="下一步行动">
          <el-input v-model="form.next_step" maxlength="200" placeholder="如：周三约客户演示方案" />
        </el-form-item>
        <el-form-item label="商机描述" class="deal-form__description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="请输入商机详细背景、需求摘要..."
          />
        </el-form-item>
      </section>

      <section class="deal-form__section deal-form__section--last deal-lines">
        <div class="deal-lines__head">
          <div class="deal-lines__title">
            <span>产品明细</span>
            <el-tag v-if="lineCount" size="small" effect="plain" round>{{ lineCount }} 行</el-tag>
          </div>
          <div class="deal-lines__actions">
            <el-button text bg size="small" :icon="Plus" @click="addBlankLine">空白行</el-button>
            <el-button type="primary" size="small" :icon="Goods" @click="openAddProducts">
              添加产品
            </el-button>
          </div>
        </div>

        <div v-if="!form.lines.length" class="deal-lines__empty">
          <div class="deal-lines__empty-icon">
            <el-icon :size="26"><Goods /></el-icon>
          </div>
          <p class="deal-lines__empty-title">还没有明细</p>
          <p class="deal-lines__empty-desc">从产品库批量添加，自动带入单价与税率</p>
          <div class="deal-lines__empty-btns">
            <el-button type="primary" :icon="Goods" @click="openAddProducts">添加产品</el-button>
            <el-button :icon="Plus" @click="addBlankLine">添加空白行</el-button>
          </div>
        </div>

        <div v-else class="deal-lines__list">
          <article
            v-for="(row, idx) in form.lines"
            :key="idx"
            class="deal-line-card"
          >
            <header class="deal-line-card__head">
              <div class="deal-line-card__index">{{ idx + 1 }}</div>
              <div class="deal-line-card__product">
                <template v-if="row.product_id || row.product_name">
                  <div class="deal-line-card__name" :title="row.product_name">
                    {{ row.product_name || '未命名' }}
                  </div>
                  <div v-if="row.product_code" class="deal-line-card__code">{{ row.product_code }}</div>
                </template>
                <el-button
                  v-else
                  link
                  type="primary"
                  size="small"
                  @click="openReplaceProduct(idx)"
                >
                  选择产品
                </el-button>
              </div>
              <div class="deal-line-card__ops">
                <el-button link type="primary" size="small" @click="openReplaceProduct(idx)">
                  {{ row.product_id ? '更换' : '选产品' }}
                </el-button>
                <el-button
                  link
                  type="primary"
                  :icon="CopyDocument"
                  title="复制行"
                  @click="duplicateLine(idx)"
                />
                <el-button
                  link
                  type="danger"
                  :icon="Delete"
                  title="删除"
                  @click="removeLine(idx)"
                />
              </div>
            </header>

            <div class="deal-line-card__fields">
              <label class="deal-field deal-field--grow">
                <span>名称</span>
                <el-input v-model="row.product_name" placeholder="显示名称" />
              </label>
              <label class="deal-field deal-field--sm">
                <span>单位</span>
                <el-input v-model="row.unit" placeholder="个" />
              </label>
              <label class="deal-field">
                <span>数量</span>
                <el-input-number
                  v-model="row.quantity"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  style="width: 100%"
                  @change="recomputeAllLines"
                />
              </label>
              <label class="deal-field">
                <span>单价(未税)</span>
                <el-input-number
                  v-model="row.unit_price"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  style="width: 100%"
                  @change="recomputeAllLines"
                />
              </label>
              <label class="deal-field deal-field--sm">
                <span>折扣%</span>
                <el-input-number
                  v-model="row.discount_percent"
                  :min="0"
                  :max="100"
                  :precision="2"
                  :controls="false"
                  style="width: 100%"
                  @change="recomputeAllLines"
                />
              </label>
            </div>

            <div class="deal-line-card__tax">
              <div class="deal-line-card__tax-left">
                <span class="deal-field__label">税率</span>
                <div class="tax-chips">
                  <button
                    v-for="r in TAX_PRESETS"
                    :key="r"
                    type="button"
                    class="tax-chip"
                    :class="{ 'is-active': Number(row.tax_rate) === r }"
                    @click="setTaxRate(row, r)"
                  >
                    {{ r }}%
                  </button>
                  <el-input-number
                    v-model="row.tax_rate"
                    class="tax-chip__custom"
                    :min="0"
                    :max="100"
                    :precision="2"
                    :controls="false"
                    placeholder="自定义"
                    @change="recomputeAllLines"
                  />
                </div>
              </div>
              <div class="deal-line-card__amounts">
                <div class="amt">
                  <span>未税</span>
                  <b>¥{{ formatMoney(row.subtotal) }}</b>
                </div>
                <div class="amt">
                  <span>税额</span>
                  <b>¥{{ formatMoney(row.tax_amount) }}</b>
                </div>
                <div class="amt amt--incl">
                  <span>含税</span>
                  <b>¥{{ formatMoney(Number(row.subtotal || 0) + Number(row.tax_amount || 0)) }}</b>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div v-if="form.lines.length" class="deal-lines__footer">
          <el-button text bg size="small" :icon="Goods" @click="openAddProducts">继续添加</el-button>
          <div class="deal-lines__summary">
            <div class="sum-pill">
              <span>未税</span>
              <b>¥{{ formatMoney(linesExTotal) }}</b>
            </div>
            <div class="sum-pill">
              <span>税额</span>
              <b>¥{{ formatMoney(linesTaxTotal) }}</b>
            </div>
            <div class="sum-pill sum-pill--grand">
              <span>价税合计</span>
              <b>¥{{ formatMoney(linesInclTotal) }}</b>
            </div>
          </div>
        </div>
      </section>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>

  <CrmProductPicker
    v-model:visible="pickerVisible"
    :multiple="pickerMultiple"
    :title="pickerMultiple ? '添加产品到商机' : '更换产品'"
    @confirm="onProductsPicked"
  />
</template>

<style scoped>
.deal-form__section {
  margin-bottom: 14px;
  padding: 14px 16px 4px;
  border: 1px solid #e8eef5;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02);
}

.deal-form__section--last {
  margin-bottom: 0;
  padding-bottom: 14px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  border-color: #e2e8f0;
}

.deal-form__section-title {
  margin: 0 0 12px;
  padding-left: 10px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: #0f172a;
  line-height: 1.2;
}

.deal-form__grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}

.deal-form__amount-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.deal-form__amount {
  flex: 1;
  min-width: 0;
}

.deal-form__hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.3;
}

.deal-form__probability {
  width: 160px;
  flex-shrink: 0;
}

.deal-form__probability :deep(.el-form-item__label) {
  width: 48px !important;
  padding-right: 8px;
}

.deal-form__probability-input {
  display: flex;
  align-items: center;
  gap: 4px;
}

.deal-form__percent {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.deal-lines__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.deal-lines__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 650;
  color: #0f172a;
}

.deal-lines__actions {
  display: flex;
  gap: 6px;
}

.deal-lines__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 40px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px dashed #cbd5e1;
  color: #94a3b8;
}

.deal-lines__empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: var(--el-color-primary);
  margin-bottom: 4px;
}

.deal-lines__empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.deal-lines__empty-desc {
  margin: 0 0 10px;
  font-size: 13px;
}

.deal-lines__empty-btns {
  display: flex;
  gap: 8px;
}

.deal-lines__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.deal-line-card {
  padding: 12px 14px 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.deal-line-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

.deal-line-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.deal-line-card__index {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  background: #f1f5f9;
}

.deal-line-card__product {
  min-width: 0;
  flex: 1;
}

.deal-line-card__name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deal-line-card__code {
  margin-top: 2px;
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.deal-line-card__ops {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.deal-line-card__fields {
  display: grid;
  grid-template-columns: minmax(140px, 1.6fr) 72px 100px 120px 88px;
  gap: 10px;
  margin-bottom: 12px;
}

.deal-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  margin: 0;
}

.deal-field > span,
.deal-field__label {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  letter-spacing: 0.02em;
}

.deal-line-card__tax {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
  flex-wrap: wrap;
}

.deal-line-card__tax-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tax-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tax-chip {
  height: 28px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.12s ease;
}

.tax-chip:hover {
  border-color: #93c5fd;
  color: var(--el-color-primary);
}

.tax-chip.is-active {
  border-color: var(--el-color-primary);
  background: #eff6ff;
  color: var(--el-color-primary);
}

.tax-chip__custom {
  width: 72px !important;
}

.tax-chip__custom :deep(.el-input__wrapper) {
  padding-left: 8px;
  padding-right: 8px;
}

.deal-line-card__amounts {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}

.amt {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  min-width: 72px;
}

.amt span {
  font-size: 11px;
  color: #94a3b8;
}

.amt b {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  font-variant-numeric: tabular-nums;
}

.amt--incl b {
  font-size: 15px;
  color: var(--el-color-primary);
}

.deal-lines__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.deal-lines__summary {
  display: flex;
  align-items: stretch;
  gap: 8px;
  margin-left: auto;
  flex-wrap: wrap;
}

.sum-pill {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  min-width: 96px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.sum-pill span {
  font-size: 11px;
  color: #94a3b8;
}

.sum-pill b {
  font-size: 14px;
  font-weight: 650;
  color: #334155;
  font-variant-numeric: tabular-nums;
}

.sum-pill--grand {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border-color: #bfdbfe;
  min-width: 128px;
}

.sum-pill--grand b {
  font-size: 18px;
  color: var(--el-color-primary);
}

.deal-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.deal-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #64748b;
}

@media (max-width: 900px) {
  .deal-form__grid2 {
    grid-template-columns: 1fr;
  }

  .deal-line-card__fields {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
