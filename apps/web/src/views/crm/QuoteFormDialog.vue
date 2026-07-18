<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Delete, Plus, Goods } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import CrmProductPicker from '../../components/crm/CrmProductPicker.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  record: { type: Object, default: null },
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

function emptyLine() {
  return {
    product_id: '',
    product_code: '',
    name: '',
    unit: '',
    quantity: 1,
    unit_price: 0,
    discount_rate: null,
    line_total: 0,
  }
}

const isEdit = computed(() => !!props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑报价' : '新建报价'))
const lineCount = computed(() => form.value.lines.length)
const subTotal = computed(() =>
  form.value.lines.reduce((acc, l) => acc + Number(l.line_total || 0), 0),
)
const discountAmount = computed(() => {
  const rate = Number(form.value.discount_rate || 0)
  if (!rate || !subTotal.value) return 0
  return Math.round(subTotal.value * (rate / 100) * 100) / 100
})
const grandTotal = computed(() => {
  return Math.round((subTotal.value - discountAmount.value) * 100) / 100
})
const hasOrderDiscount = computed(() => Number(form.value.discount_rate || 0) > 0 || discountAmount.value > 0)

function formatMoney(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 按折扣金额反算整单折扣%（仍存 discount_rate，与后端兼容） */
function onDiscountAmountInput(val) {
  const sub = subTotal.value
  if (!sub || sub <= 0) {
    form.value.discount_rate = null
    return
  }
  const amount = Math.min(Math.max(Number(val) || 0, 0), sub)
  if (amount <= 0) {
    form.value.discount_rate = null
    return
  }
  form.value.discount_rate = Math.round((amount / sub) * 10000) / 100
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

async function applyProductToLine(line, product) {
  line.product_id = product.id
  line.product_code = product.code || ''
  line.name = product.name || ''
  line.unit = product.unit || ''
  line.unit_price = Number(product.list_price) || 0
  if (!line.quantity) line.quantity = 1
  try {
    const { data } = await crmApi.resolveCpqPrice({
      product_id: line.product_id,
      quantity: Number(line.quantity) || 1,
    })
    if (data?.unit_price != null) line.unit_price = Number(data.unit_price)
  } catch {
    /* keep list_price */
  }
  recomputeLine(line)
}

async function onProductsPicked(products) {
  if (!products?.length) return
  if (!pickerMultiple.value && replaceLineIndex.value >= 0) {
    const line = form.value.lines[replaceLineIndex.value]
    if (line) await applyProductToLine(line, products[0])
    return
  }
  for (const p of products) {
    const line = emptyLine()
    await applyProductToLine(line, p)
    form.value.lines.push(line)
  }
  ElMessage.success(`已添加 ${products.length} 个产品`)
}

async function onQuantityChange(line) {
  if (line.product_id) {
    try {
      const { data } = await crmApi.resolveCpqPrice({
        product_id: line.product_id,
        quantity: Number(line.quantity) || 1,
      })
      if (data?.unit_price != null) line.unit_price = Number(data.unit_price)
    } catch {
      /* keep */
    }
  }
  recomputeLine(line)
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
        line_total: Number(l.line_total),
      })),
    }
    if (data.customer_id) {
      customerOptions.value = [{ id: data.customer_id, company_name: data.customer_name || '(已绑定客户)' }]
    }
  } catch (e) {
    ElMessage.error(e.message || '加载报价失败')
    resetForm()
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
      await crmApi.updateQuote(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createQuote(payload)
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
  if (isEdit.value) await loadQuote()
  else resetForm()
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
              :max="Math.max(subTotal, 0)"
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

      <div class="quote-lines">
        <div class="quote-lines__head">
          <div class="quote-lines__title">
            <span>报价明细</span>
            <el-tag v-if="lineCount" size="small" effect="plain" type="info">{{ lineCount }} 行</el-tag>
          </div>
          <div class="quote-lines__actions">
            <el-button size="small" :icon="Plus" @click="addBlankLine">空白行</el-button>
            <el-button type="primary" size="small" :icon="Goods" @click="openAddProducts">
              添加产品
            </el-button>
          </div>
        </div>

        <div v-if="!form.lines.length" class="quote-lines__empty">
          <div class="quote-lines__empty-icon">
            <el-icon :size="28"><Goods /></el-icon>
          </div>
          <p class="quote-lines__empty-title">还没有明细</p>
          <p class="quote-lines__empty-desc">从产品库批量添加，或先加一行手动填写</p>
          <div class="quote-lines__empty-btns">
            <el-button type="primary" :icon="Goods" @click="openAddProducts">添加产品</el-button>
            <el-button :icon="Plus" @click="addBlankLine">添加空白行</el-button>
          </div>
        </div>

        <el-table
          v-else
          :data="form.lines"
          border
          size="small"
          class="quote-lines__table"
        >
          <el-table-column label="产品" min-width="240">
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
              <el-button
                v-else
                link
                type="primary"
                size="small"
                @click="openReplaceProduct($index)"
              >
                选择产品
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="名称" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" placeholder="显示名称" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="72">
            <template #default="{ row }">
              <el-input v-model="row.unit" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="数量" width="100">
            <template #default="{ row }">
              <el-input-number
                v-model="row.quantity"
                :min="0"
                :precision="2"
                :controls="false"
                size="small"
                style="width: 100%"
                @change="onQuantityChange(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="110">
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
          <el-table-column label="折扣%" width="88">
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
          <el-table-column label="小计" width="110" align="right">
            <template #default="{ row }">
              <span class="line-subtotal">¥{{ formatMoney(row.line_total) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="84" align="center" fixed="right">
            <template #default="{ $index }">
              <el-button
                link
                type="primary"
                :icon="CopyDocument"
                title="复制行"
                @click="duplicateLine($index)"
              />
              <el-button
                link
                type="danger"
                :icon="Delete"
                title="删除"
                @click="removeLine($index)"
              />
            </template>
          </el-table-column>
        </el-table>

        <div class="quote-lines__bar">
          <div class="quote-lines__bar-left">
            <el-button v-if="form.lines.length" size="small" :icon="Goods" @click="openAddProducts">
              继续添加
            </el-button>
          </div>
          <div class="quote-lines__totals">
            <div v-if="hasOrderDiscount" class="quote-lines__sum-row">
              <span>小计</span>
              <span>¥{{ formatMoney(subTotal) }}</span>
            </div>
            <div v-if="hasOrderDiscount" class="quote-lines__sum-row quote-lines__sum-row--discount">
              <span>折扣金额{{ form.discount_rate ? ` (${form.discount_rate}%)` : '' }}</span>
              <span>-¥{{ formatMoney(discountAmount) }}</span>
            </div>
            <div class="quote-lines__grand">
              <span>合计</span>
              <b>¥{{ formatMoney(grandTotal) }}</b>
            </div>
          </div>
        </div>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存报价</el-button>
    </template>
  </el-dialog>

  <CrmProductPicker
    v-model:visible="pickerVisible"
    :multiple="pickerMultiple"
    :title="pickerMultiple ? '添加产品到报价' : '更换产品'"
    @confirm="onProductsPicked"
  />
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

.quote-lines {
  margin-top: 4px;
  padding: 14px 16px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #f4f7fb 100%);
  border: 1px solid #e8eef6;
}

.quote-lines__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.quote-lines__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.quote-lines__actions {
  display: flex;
  gap: 8px;
}

.quote-lines__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 36px 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px dashed #cbd5e1;
}

.quote-lines__empty-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: var(--el-color-primary);
  margin-bottom: 12px;
}

.quote-lines__empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.quote-lines__empty-desc {
  margin: 6px 0 16px;
  font-size: 13px;
  color: #94a3b8;
}

.quote-lines__empty-btns {
  display: flex;
  gap: 8px;
}

.quote-lines__table {
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.quote-lines__table :deep(.el-table__header th) {
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

.quote-lines__bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  gap: 12px;
}

.quote-lines__totals {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 220px;
}

.quote-lines__sum-row {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  width: 100%;
  font-size: 13px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.quote-lines__sum-row--discount {
  color: #ef4444;
}

.quote-lines__grand {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 24px;
  width: 100%;
  margin-top: 2px;
  padding-top: 6px;
  border-top: 1px dashed #dbe3ee;
  font-size: 14px;
  color: #64748b;
}

.quote-lines__grand b {
  color: var(--el-color-primary);
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
