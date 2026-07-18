<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Delete, Plus, Goods } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import CrmProductPicker from '../../components/crm/CrmProductPicker.vue'

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
const pickerVisible = ref(false)
const pickerMultiple = ref(true)
const replaceLineIndex = ref(-1)

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
  return {
    product_id: '',
    product_code: '',
    name: '',
    unit: '',
    quantity: 1,
    unit_price: 0,
    discount_rate: null,
    tax_rate: null,
    tax_amount: null,
    line_total: 0,
  }
}

const isEdit = computed(() => !!props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑订单' : '新建订单'))
const lineCount = computed(() => form.value.lines.length)
const grandTotal = computed(() => form.value.lines.reduce((acc, l) => acc + Number(l.line_total || 0), 0))
const taxGrandTotal = computed(() => form.value.lines.reduce((acc, l) => acc + Number(l.tax_amount || 0), 0))
const inclGrandTotal = computed(() => grandTotal.value + taxGrandTotal.value)

function formatMoney(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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
}

function duplicateLine(idx) {
  const src = form.value.lines[idx]
  if (!src) return
  const copy = { ...src, quantity: Number(src.quantity) || 1 }
  recomputeLine(copy)
  form.value.lines.splice(idx + 1, 0, copy)
}

function applyProductToLine(line, product) {
  line.product_id = product.id
  line.product_code = product.code || ''
  line.name = product.name || ''
  line.unit = product.unit || ''
  line.unit_price = Number(product.list_price) || 0
  if (!line.quantity) line.quantity = 1
  recomputeLine(line)
}

function onProductsPicked(products) {
  if (!products?.length) return
  if (!pickerMultiple.value && replaceLineIndex.value >= 0) {
    const line = form.value.lines[replaceLineIndex.value]
    if (line) applyProductToLine(line, products[0])
    return
  }
  for (const p of products) {
    const line = emptyLine()
    applyProductToLine(line, p)
    form.value.lines.push(line)
  }
  ElMessage.success(`已添加 ${products.length} 个产品`)
}

function recomputeLine(line) {
  const qty = Number(line.quantity || 0)
  const price = Number(line.unit_price || 0)
  const disc = Number(line.discount_rate || 0)
  line.line_total = Math.round(qty * price * (1 - disc / 100) * 100) / 100
  const taxRate = Number(line.tax_rate || 0)
  line.tax_amount = Math.round(line.line_total * (taxRate / 100) * 100) / 100
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
    status: form.value.status,
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

      <div class="order-lines">
        <div class="order-lines__head">
          <div class="order-lines__title">
            <span>订单明细</span>
            <el-tag v-if="lineCount" size="small" effect="plain" type="info">{{ lineCount }} 行</el-tag>
          </div>
          <div class="order-lines__actions">
            <el-button size="small" :icon="Plus" @click="addBlankLine">空白行</el-button>
            <el-button type="primary" size="small" :icon="Goods" @click="openAddProducts">
              添加产品
            </el-button>
          </div>
        </div>

        <div v-if="!form.lines.length" class="order-lines__empty">
          <div class="order-lines__empty-icon">
            <el-icon :size="28"><Goods /></el-icon>
          </div>
          <p class="order-lines__empty-title">还没有明细</p>
          <p class="order-lines__empty-desc">从产品库批量添加，或先加一行手动填写</p>
          <div class="order-lines__empty-btns">
            <el-button type="primary" :icon="Goods" @click="openAddProducts">添加产品</el-button>
            <el-button :icon="Plus" @click="addBlankLine">添加空白行</el-button>
          </div>
        </div>

        <el-table v-else :data="form.lines" border size="small" class="order-lines__table">
          <el-table-column label="产品" min-width="200">
            <template #default="{ row, $index }">
              <div v-if="row.product_id || row.name" class="line-product">
                <div class="line-product__main">
                  <div class="line-product__name" :title="row.name">{{ row.name || '未命名' }}</div>
                  <div v-if="row.product_code" class="line-product__code">{{ row.product_code }}</div>
                </div>
                <el-button link type="primary" size="small" @click="openReplaceProduct($index)">
                  {{ row.product_id ? '更换' : '选产品' }}
                </el-button>
              </div>
              <el-button v-else link type="primary" size="small" @click="openReplaceProduct($index)">
                选择产品
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="名称" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" placeholder="显示名称" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="68">
            <template #default="{ row }"><el-input v-model="row.unit" size="small" /></template>
          </el-table-column>
          <el-table-column label="数量" width="88">
            <template #default="{ row }">
              <el-input-number
                v-model="row.quantity"
                :min="0"
                :precision="2"
                :controls="false"
                size="small"
                style="width: 100%"
                @change="recomputeLine(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="96">
            <template #default="{ row }">
              <el-input-number
                v-model="row.unit_price"
                :min="0"
                :precision="2"
                :controls="false"
                size="small"
                style="width: 100%"
                @change="recomputeLine(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="折扣%" width="78">
            <template #default="{ row }">
              <el-input-number
                v-model="row.discount_rate"
                :min="0"
                :max="100"
                :precision="2"
                :controls="false"
                size="small"
                style="width: 100%"
                @change="recomputeLine(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="税率%" width="78">
            <template #default="{ row }">
              <el-input-number
                v-model="row.tax_rate"
                :min="0"
                :max="100"
                :precision="2"
                :controls="false"
                size="small"
                style="width: 100%"
                @change="recomputeLine(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="税额" width="90" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.tax_amount) }}</template>
          </el-table-column>
          <el-table-column label="未税" width="96" align="right">
            <template #default="{ row }">
              <span class="line-subtotal">¥{{ formatMoney(row.line_total) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="84" align="center" fixed="right">
            <template #default="{ $index }">
              <el-button link type="primary" :icon="CopyDocument" title="复制行" @click="duplicateLine($index)" />
              <el-button link type="danger" :icon="Delete" title="删除" @click="removeLine($index)" />
            </template>
          </el-table-column>
        </el-table>

        <div class="order-lines__bar">
          <el-button v-if="form.lines.length" size="small" :icon="Goods" @click="openAddProducts">
            继续添加
          </el-button>
          <div v-else />
          <div class="order-lines__totals">
            <span>未税 <b>¥{{ formatMoney(grandTotal) }}</b></span>
            <span class="order-lines__tax">税额 ¥{{ formatMoney(taxGrandTotal) }}</span>
            <span>含税 <b class="order-lines__incl">¥{{ formatMoney(inclGrandTotal) }}</b></span>
          </div>
        </div>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存订单</el-button>
    </template>
  </el-dialog>

  <CrmProductPicker
    v-model:visible="pickerVisible"
    :multiple="pickerMultiple"
    :title="pickerMultiple ? '添加产品到订单' : '更换产品'"
    @confirm="onProductsPicked"
  />
</template>

<style scoped>
.order-form__meta-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0 16px;
}

.order-lines {
  margin-top: 4px;
  padding: 14px 16px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #f4f7fb 100%);
  border: 1px solid #e8eef6;
}

.order-lines__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.order-lines__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.order-lines__actions {
  display: flex;
  gap: 8px;
}

.order-lines__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 36px 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px dashed #cbd5e1;
}

.order-lines__empty-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: var(--el-color-primary);
  margin-bottom: 12px;
}

.order-lines__empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.order-lines__empty-desc {
  margin: 6px 0 16px;
  font-size: 13px;
  color: #94a3b8;
}

.order-lines__empty-btns {
  display: flex;
  gap: 8px;
}

.order-lines__table {
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.order-lines__table :deep(.el-table__header th) {
  background: #f8fafc !important;
}

.line-product {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.line-product__main {
  min-width: 0;
  flex: 1;
}

.line-product__name {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.line-product__code {
  margin-top: 2px;
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.line-subtotal {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  color: #334155;
}

.order-lines__bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  gap: 12px;
  flex-wrap: wrap;
}

.order-lines__totals {
  display: flex;
  gap: 14px;
  align-items: center;
  font-size: 14px;
  color: #64748b;
}

.order-lines__totals b {
  color: var(--el-color-primary);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.order-lines__incl {
  font-size: 18px !important;
  font-weight: 700;
}

.order-lines__tax {
  color: #94a3b8;
}
</style>
