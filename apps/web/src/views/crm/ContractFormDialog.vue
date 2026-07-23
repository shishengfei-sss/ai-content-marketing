<script setup>
import { computed, ref, watch } from 'vue'
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
function emptyForm() {
  return {
    id: '',
    title: '',
    customer_id: '',
    deal_id: '',
    quote_id: '',
    contract_type: 'new',
    amount: null,
    start_date: '',
    end_date: '',
    status: 'draft',
    file_url: '',
    lines: [],
  }
}

const isEdit = computed(() => !!props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑合同' : '新建合同'))
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

async function applyPresetDealCustomer() {
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

async function loadContract() {
  if (!props.record?.id) {
    resetForm()
    return
  }
  try {
    const { data } = await crmApi.getContract(props.record.id)
    form.value = {
      id: data.id,
      title: data.title,
      customer_id: data.customer_id,
      deal_id: data.deal_id || '',
      quote_id: data.quote_id || '',
      contract_type: data.contract_type || 'new',
      amount: Number(data.amount),
      start_date: data.start_date ? String(data.start_date).slice(0, 10) : '',
      end_date: data.end_date ? String(data.end_date).slice(0, 10) : '',
      status: data.status,
      file_url: data.file_url || '',
      lines: (data.lines || []).map((l) => ({
        product_id: l.product_id || '',
        product_code: l.product_code || '',
        name: l.name,
        unit: l.unit || '',
        quantity: Number(l.quantity),
        unit_price: Number(l.unit_price),
        discount_rate: l.discount_rate != null ? Number(l.discount_rate) : null,
        tax_rate: l.tax_rate != null ? Number(l.tax_rate) : null,
        tax_amount: l.tax_amount != null ? Number(l.tax_amount) : null,
        line_total: Number(l.line_total),
      })),
    }
    if (data.customer_id) {
      customerOptions.value = [{ id: data.customer_id, company_name: data.customer_name || '(已绑定客户)' }]
    }
  } catch (e) {
    ElMessage.error(e.message || '加载合同失败')
    resetForm()
  }
}

async function submit() {
  if (!form.value.title?.trim()) {
    ElMessage.warning('请填写合同标题')
    return
  }
  if (!form.value.customer_id) {
    ElMessage.warning('请选择客户')
    return
  }
  if (!form.value.lines.length && !isEdit.value) {
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
    title: form.value.title.trim(),
    customer_id: form.value.customer_id,
    contract_type: form.value.contract_type,
    start_date: form.value.start_date || null,
    end_date: form.value.end_date || null,
    status: form.value.status,
    file_url: form.value.file_url || null,
  }
  // 有明细时提交 lines（金额由后端按明细重算）；编辑旧合同且无明细时不传 lines，保留原金额
  if (form.value.lines.length) {
    payload.lines = form.value.lines.map((l) => ({
      product_id: l.product_id || null,
      name: l.name,
      unit: l.unit || null,
      quantity: Number(l.quantity),
      unit_price: Number(l.unit_price),
      discount_rate: l.discount_rate,
      tax_rate: l.tax_rate,
      tax_amount: l.tax_amount,
      line_total: Number(l.line_total),
    }))
  }
  if (form.value.deal_id) payload.deal_id = form.value.deal_id
  if (form.value.quote_id) payload.quote_id = form.value.quote_id

  saving.value = true
  try {
    if (isEdit.value) {
      await crmApi.updateContract(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createContract(payload)
      ElMessage.success('合同已创建')
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
    await loadContract()
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
    width="1060px"
    destroy-on-close
    align-center
  >
    <el-form label-width="80px" :model="form">
      <el-form-item label="合同标题" required>
        <el-input v-model="form.title" maxlength="200" placeholder="例如：XX 项目服务合同" />
      </el-form-item>
      <div class="contract-form__meta-row">
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
      </div>
      <div class="contract-form__meta-row">
        <el-form-item label="合同类型">
          <el-select v-model="form.contract_type" style="width: 100%">
            <el-option label="新签" value="new" />
            <el-option label="续约" value="renewal" />
            <el-option label="增订" value="addon" />
          </el-select>
        </el-form-item>
        <el-form-item label="生效日">
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </div>
      <div class="contract-form__meta-row">
        <el-form-item label="到期日">
          <el-date-picker
            v-model="form.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="附件URL">
          <el-input v-model="form.file_url" maxlength="500" placeholder="可选外部链接" />
        </el-form-item>
      </div>

      <CrmDocLineCards
        v-model="form.lines"
        title="合同明细"
        picker-title-add="添加产品到合同"
        picker-title-replace="更换产品"
      />
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存合同</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.contract-form__meta-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0 16px;
}
</style>
