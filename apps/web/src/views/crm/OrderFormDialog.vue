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
const form = ref(emptyForm())
function emptyForm() {
  return {
    id: '',
    title: '',
    customer_id: '',
    contact_id: '',
    deal_id: '',
    source: 'deal',
    order_date: '',
    amount: null,
    status: 'draft',
    lines: [],
  }
}

const isEdit = computed(() => !!props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑订单' : '新建订单'))
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

function resetForm() {
  form.value = emptyForm()
  form.value.status = 'draft'
  if (props.presetCustomerId) form.value.customer_id = props.presetCustomerId
  if (props.presetDealId) form.value.deal_id = props.presetDealId
}

async function loadOrder() {
  if (!props.record?.id) {
    resetForm()
    return
  }
  try {
    const { data } = await crmApi.getOrder(props.record.id)
    form.value = {
      id: data.id,
      title: data.title,
      customer_id: data.customer_id,
      contact_id: data.contact_id || '',
      deal_id: data.deal_id || '',
      source: data.source,
      order_date: data.order_date ? String(data.order_date).slice(0, 10) : '',
      amount: Number(data.amount),
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
        tax_amount: l.tax_amount != null ? Number(l.tax_amount) : null,
        line_total: Number(l.line_total),
      })),
    }
    if (data.customer_id) {
      customerOptions.value = [{ id: data.customer_id, company_name: data.customer_name || '(已绑定客户)' }]
    }
  } catch (e) {
    ElMessage.error(e.message || '加载订单失败')
    resetForm()
  }
}

async function submit() {
  if (!form.value.title?.trim()) {
    ElMessage.warning('请填写订单标题')
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
    title: form.value.title.trim(),
    customer_id: form.value.customer_id,
    source: form.value.source,
    order_date: form.value.order_date || null,
    lines: form.value.lines.map((l) => ({
      product_id: l.product_id || null,
      name: l.name,
      unit: l.unit || null,
      quantity: Number(l.quantity),
      unit_price: Number(l.unit_price),
      discount_rate: l.discount_rate,
      tax_rate: l.tax_rate,
      tax_amount: l.tax_amount,
      line_total: Number(l.line_total),
    })),
  }
  if (form.value.deal_id) payload.deal_id = form.value.deal_id
  if (!isEdit.value) payload.status = 'draft'

  saving.value = true
  try {
    if (isEdit.value) {
      await crmApi.updateOrder(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createOrder(payload)
      ElMessage.success('订单已创建')
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
  if (isEdit.value) await loadOrder()
  else resetForm()
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
      <el-form-item label="订单标题" required>
        <el-input v-model="form.title" maxlength="200" placeholder="例如：XX 项目订单" />
      </el-form-item>
      <div class="order-form__meta-row">
        <el-form-item label="客户" required>
          <el-select
            v-model="form.customer_id"
            filterable
            remote
            :remote-method="searchCustomers"
            :loading="customerLoading"
            placeholder="搜索客户名称"
            style="width: 100%"
          >
            <el-option
              v-for="c in customerOptions"
              :key="c.id"
              :label="c.company_name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="下单日期">
          <el-date-picker
            v-model="form.order_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </div>

      <CrmDocLineCards
        v-model="form.lines"
        title="订单明细"
        picker-title-add="添加产品到订单"
        picker-title-replace="更换产品"
      />
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存订单</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.order-form__meta-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0 16px;
}
</style>
