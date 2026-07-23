<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import CrmDocLineCards from '../../components/crm/CrmDocLineCards.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  record: { type: Object, default: null },
  presetCustomerId: { type: String, default: '' },
  presetDealId: { type: String, default: '' },
})
const emit = defineEmits(['update:visible', 'saved'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)
const customerOptions = ref([])
const customerLoading = ref(false)
const dealOptions = ref([])
const dealLoading = ref(false)
const form = ref(emptyForm())
const lineCardsRef = ref(null)

function emptyForm() {
  return {
    id: '',
    customer_id: '',
    contact_id: '',
    deal_id: '',
    subject: '',
    discount_rate: null,
    valid_until: '',
    status: 'draft',
    lines: [],
  }
}

const isEdit = computed(() => !!props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑报价' : '新建报价'))
function money(n) {
  return Math.round(Number(n || 0) * 100) / 100
}

const subTotalBeforeHeader = computed(() =>
  money(
    form.value.lines.reduce((acc, l) => {
      const qty = Number(l.quantity || 0)
      const price = Number(l.unit_price || 0)
      const disc = Number(l.discount_rate || 0)
      return acc + qty * price * (1 - disc / 100)
    }, 0),
  ),
)
const discountAmount = computed(() => {
  const rate = Number(form.value.discount_rate || 0)
  if (!rate || !subTotalBeforeHeader.value) return 0
  return money(subTotalBeforeHeader.value * (rate / 100))
})

/** 按折扣金额反算整单折扣%（仍存 discount_rate，与后端兼容） */
function onDiscountAmountInput(val) {
  const sub = subTotalBeforeHeader.value
  if (!sub || sub <= 0) {
    form.value.discount_rate = null
    return
  }
  const amount = Math.min(Math.max(Number(val) || 0, 0), sub)
  if (amount <= 0) {
    form.value.discount_rate = null
  } else {
    form.value.discount_rate = Math.round((amount / sub) * 10000) / 100
  }
}

function onDiscountRateChange(val) {
  if (val == null || Number(val) <= 0) form.value.discount_rate = null
}

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({ id: c.id, company_name: c.company_name }))
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
        /* keep list */
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

function resetForm() {
  form.value = emptyForm()
  form.value.status = 'draft'
  if (props.presetCustomerId) form.value.customer_id = props.presetCustomerId
  if (props.presetDealId) form.value.deal_id = props.presetDealId
}

async function loadQuote() {
  if (!props.record?.id) {
    resetForm()
    return
  }
  try {
    const { data } = await crmApi.getQuote(props.record.id)
    form.value = {
      id: data.id,
      customer_id: data.customer_id,
      contact_id: data.contact_id || '',
      deal_id: data.deal_id || '',
      subject: data.subject,
      discount_rate: data.discount_rate != null ? Number(data.discount_rate) : null,
      valid_until: data.valid_until ? String(data.valid_until).slice(0, 10) : '',
      status: data.status,
      lines: (data.lines || []).map((l) => ({
        product_id: l.product_id || '',
        product_code: l.product_code || '',
        name: l.name,
        unit: l.unit || '',
        quantity: Number(l.quantity),
        unit_price: Number(l.unit_price),
        discount_rate: l.discount_rate != null ? Number(l.discount_rate) : null,
        tax_rate: l.tax_rate != null ? Number(l.tax_rate) : null,
        tax_amount: Number(l.tax_amount || 0),
        line_total: Number(l.line_total),
      })),
    }
    await nextTick()
    lineCardsRef.value?.recomputeAllLines()
    if (data.customer_id) {
      customerOptions.value = [{ id: data.customer_id, company_name: data.customer_name || '(已绑定客户)' }]
    }
  } catch (e) {
    ElMessage.error(e.message || '加载报价失败')
    resetForm()
  }
}

/** 从预填商机带出客户（新建且仅有 deal 预填时） */
async function applyPresetDealCustomer() {
  // 预填客户选项，避免 remote 搜索未命中导致下拉空白
  if (props.presetCustomerId && form.value.customer_id) {
    try {
      const { data: cust } = await crmApi.getCustomer(props.presetCustomerId)
      const row = { id: props.presetCustomerId, company_name: cust?.company_name || '(商机客户)' }
      customerOptions.value = [row, ...customerOptions.value.filter((c) => String(c.id) !== String(row.id))]
    } catch {
      if (!customerOptions.value.some((c) => String(c.id) === String(props.presetCustomerId))) {
        customerOptions.value = [{ id: props.presetCustomerId, company_name: '(商机客户)' }, ...customerOptions.value]
      }
    }
  }
  if (props.presetDealId && !form.value.subject) {
    try {
      const { data: deal } = await crmApi.getDeal(props.presetDealId)
      if (deal?.title) form.value.subject = `${deal.title} - 报价`
      if (deal?.customer_id && !form.value.customer_id) {
        form.value.customer_id = deal.customer_id
      }
    } catch {
      /* ignore */
    }
  }
  if (!form.value.deal_id || form.value.customer_id) return
  try {
    const { data: deal } = await crmApi.getDeal(form.value.deal_id)
    if (!deal?.customer_id) return
    form.value.customer_id = deal.customer_id
    try {
      const { data: cust } = await crmApi.getCustomer(deal.customer_id)
      customerOptions.value = [{ id: deal.customer_id, company_name: cust?.company_name || '(商机客户)' }]
    } catch {
      customerOptions.value = [{ id: deal.customer_id, company_name: '(商机客户)' }]
    }
  } catch {
    /* ignore */
  }
}

async function submit() {
  if (!form.value.subject?.trim()) {
    ElMessage.warning('请填写报价主题')
    return
  }
  if (!form.value.customer_id) {
    ElMessage.warning('请选择客户')
    return
  }
  if (!form.value.lines.length) {
    ElMessage.warning('请至少添加一条明细')
    return
  }
  for (const l of form.value.lines) {
    if (!l.name?.trim()) {
      ElMessage.warning('明细名称不能为空')
      return
    }
  }
  const payload = {
    customer_id: form.value.customer_id,
    subject: form.value.subject.trim(),
    discount_rate: form.value.discount_rate,
    valid_until: form.value.valid_until || null,
    lines: form.value.lines.map((l) => ({
      product_id: l.product_id || null,
      name: l.name,
      unit: l.unit || null,
      quantity: Number(l.quantity),
      unit_price: Number(l.unit_price),
      discount_rate: l.discount_rate,
      tax_rate: l.tax_rate,
      tax_amount: Number(l.tax_amount || 0),
      line_total: Number(l.line_total),
    })),
  }
  if (form.value.deal_id) payload.deal_id = form.value.deal_id
  // 创建时固定 draft；编辑禁止 PATCH status（状态机专用接口）

  saving.value = true
  try {
    if (isEdit.value) {
      await crmApi.updateQuote(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createQuote({ ...payload, status: 'draft' })
      ElMessage.success('报价已创建')
    }
    dialogVisible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

watch(dialogVisible, async (v) => {
  if (!v) return
  await searchCustomers('')
  if (isEdit.value) {
    await loadQuote()
  } else {
    resetForm()
    await applyPresetDealCustomer()
  }
  await loadDealOptions()
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="980px"
    destroy-on-close
    align-center
    class="quote-form-dialog"
  >
    <el-form label-width="80px" :model="form" class="quote-form">
      <div class="quote-form__meta">
        <el-form-item label="主题" required class="quote-form__subject">
          <el-input v-model="form.subject" maxlength="200" placeholder="例如：XX 项目报价" />
        </el-form-item>
        <el-form-item label="客户" required>
          <el-select
            v-model="form.customer_id"
            filterable
            remote
            clearable
            :remote-method="searchCustomers"
            :loading="customerLoading"
            placeholder="搜索客户名称"
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
        <div class="quote-form__meta-row quote-form__meta-row--3">
          <el-form-item label="整单折扣%">
            <el-input-number
              v-model="form.discount_rate"
              :min="0"
              :max="100"
              :precision="2"
              :controls="false"
              placeholder="0"
              style="width: 100%"
              @change="onDiscountRateChange"
            />
          </el-form-item>
          <el-form-item label="折扣金额">
            <el-input-number
              :model-value="discountAmount || null"
              :min="0"
              :max="Math.max(subTotalBeforeHeader, 0)"
              :precision="2"
              :controls="false"
              placeholder="0.00"
              style="width: 100%"
              @update:model-value="onDiscountAmountInput"
            />
          </el-form-item>
          <el-form-item label="有效期">
            <el-date-picker
              v-model="form.valid_until"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
          </el-form-item>
        </div>
      </div>

      <CrmDocLineCards
        ref="lineCardsRef"
        v-model="form.lines"
        title="报价明细"
        :header-discount-rate="form.discount_rate"
        resolve-cpq
        picker-title-add="添加产品到报价"
        picker-title-replace="更换产品"
      />
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存报价</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.quote-form__meta {
  margin-bottom: 4px;
}

.quote-form__meta-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.quote-form__meta-row--3 {
  grid-template-columns: 1fr 1fr 1fr;
}
</style>
