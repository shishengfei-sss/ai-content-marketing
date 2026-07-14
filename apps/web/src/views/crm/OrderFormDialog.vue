<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'

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
const productOptions = ref([])
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
function emptyLine() {
  return { product_id: '', name: '', unit: '', quantity: 1, unit_price: 0, discount_rate: null, line_total: 0 }
}

const isEdit = computed(() => !!props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑订单' : '新建订单'))
const grandTotal = computed(() => form.value.lines.reduce((acc, l) => acc + Number(l.line_total || 0), 0))

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({ id: c.id, company_name: c.company_name }))
  } catch { customerOptions.value = [] } finally { customerLoading.value = false }
}

async function loadProducts() {
  try {
    const { data } = await crmApi.listProducts({ page: 1, page_size: 200, is_active: true })
    productOptions.value = (data.items || []).map((p) => ({ id: p.id, name: p.name, code: p.code, list_price: Number(p.list_price), unit: p.unit }))
  } catch { productOptions.value = [] }
}

function addLine() { form.value.lines.push(emptyLine()) }
function removeLine(idx) { form.value.lines.splice(idx, 1) }
function onProductChange(line) {
  const p = productOptions.value.find((x) => x.id === line.product_id)
  if (p) { line.name = p.name; line.unit = p.unit || ''; line.unit_price = p.list_price; recomputeLine(line) }
}
function recomputeLine(line) {
  const qty = Number(line.quantity || 0)
  const price = Number(line.unit_price || 0)
  const disc = Number(line.discount_rate || 0)
  line.line_total = Math.round(qty * price * (1 - disc / 100) * 100) / 100
}

function resetForm() {
  form.value = emptyForm()
  form.value.status = 'draft'
  if (props.presetCustomerId) form.value.customer_id = props.presetCustomerId
  if (props.presetDealId) form.value.deal_id = props.presetDealId
}

async function loadOrder() {
  if (!props.record?.id) { resetForm(); return }
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
        name: l.name,
        unit: l.unit || '',
        quantity: Number(l.quantity),
        unit_price: Number(l.unit_price),
        discount_rate: l.discount_rate != null ? Number(l.discount_rate) : null,
        line_total: Number(l.line_total),
      })),
    }
    if (data.customer_id) customerOptions.value = [{ id: data.customer_id, company_name: '(已绑定客户)' }]
  } catch (e) {
    ElMessage.error(e.message || '加载订单失败')
    resetForm()
  }
}

async function submit() {
  if (!form.value.title?.trim()) { ElMessage.warning('请填写订单标题'); return }
  if (!form.value.customer_id) { ElMessage.warning('请选择客户'); return }
  for (const l of form.value.lines) {
    if (!l.name?.trim()) { ElMessage.warning('明细名称不能为空'); return }
  }
  const payload = {
    title: form.value.title.trim(),
    customer_id: form.value.customer_id,
    source: form.value.source,
    order_date: form.value.order_date || null,
    status: form.value.status,
    lines: form.value.lines.map((l) => ({
      product_id: l.product_id || null,
      name: l.name,
      unit: l.unit || null,
      quantity: Number(l.quantity),
      unit_price: Number(l.unit_price),
      discount_rate: l.discount_rate,
      line_total: Number(l.line_total),
    })),
  }
  if (form.value.deal_id) payload.deal_id = form.value.deal_id

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
  await Promise.all([loadProducts(), searchCustomers('')])
  if (isEdit.value) { await loadOrder() } else { resetForm() }
})
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="860px" destroy-on-close align-center>
    <el-form label-width="88px" :model="form">
      <el-form-item label="订单标题" required><el-input v-model="form.title" maxlength="200" /></el-form-item>
      <el-form-item label="客户" required>
        <el-select v-model="form.customer_id" filterable remote :remote-method="searchCustomers" :loading="customerLoading" placeholder="搜索客户" style="width: 100%">
          <el-option v-for="c in customerOptions" :key="c.id" :label="c.company_name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="下单日期">
        <el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" style="width: 200px" />
      </el-form-item>
      <el-form-item label="明细">
        <div class="order-lines">
          <el-table :data="form.lines" border size="small">
            <el-table-column label="产品" width="200">
              <template #default="{ row }">
                <el-select v-model="row.product_id" filterable placeholder="选产品" size="small" @change="onProductChange(row)">
                  <el-option v-for="p in productOptions" :key="p.id" :label="`${p.name} (${p.code})`" :value="p.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="160"><template #default="{ row }"><el-input v-model="row.name" size="small" /></template></el-table-column>
            <el-table-column label="单位" width="80"><template #default="{ row }"><el-input v-model="row.unit" size="small" /></template></el-table-column>
            <el-table-column label="数量" width="100">
              <template #default="{ row }"><el-input-number v-model="row.quantity" :min="0" :precision="2" :controls="false" size="small" @change="recomputeLine(row)" /></template>
            </el-table-column>
            <el-table-column label="单价" width="120">
              <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" :controls="false" size="small" @change="recomputeLine(row)" /></template>
            </el-table-column>
            <el-table-column label="折扣%" width="90">
              <template #default="{ row }"><el-input-number v-model="row.discount_rate" :min="0" :max="100" :precision="2" :controls="false" size="small" @change="recomputeLine(row)" /></template>
            </el-table-column>
            <el-table-column label="小计" width="120" align="right"><template #default="{ row }">¥{{ Number(row.line_total || 0).toFixed(2) }}</template></el-table-column>
            <el-table-column label="" width="60" align="center"><template #default="{ $index }"><el-button link type="danger" size="small" @click="removeLine($index)">删</el-button></template></el-table-column>
          </el-table>
          <div class="order-lines__bar">
            <el-button size="small" @click="addLine">+ 添加明细</el-button>
            <div class="order-lines__total">合计：<b>¥{{ grandTotal.toFixed(2) }}</b></div>
          </div>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.order-lines { width: 100%; }
.order-lines__bar { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.order-lines__total { font-size: 14px; }
.order-lines__total b { color: var(--el-color-primary); font-size: 16px; }
</style>
