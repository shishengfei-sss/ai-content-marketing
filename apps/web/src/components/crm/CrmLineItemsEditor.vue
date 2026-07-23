<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Delete, Plus, Goods } from '@element-plus/icons-vue'
import CrmProductPicker from './CrmProductPicker.vue'

const props = defineProps({
  /** deal | quote */
  mode: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
  editable: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save'])

const draft = ref([])
const pickerVisible = ref(false)
const pickerMultiple = ref(true)
const replaceLineIndex = ref(-1)

const isDeal = computed(() => props.mode === 'deal')
const lineCount = computed(() => (props.editable ? draft.value : props.modelValue || []).length)

function emptyLine() {
  if (isDeal.value) {
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
  return {
    product_id: '',
    product_code: '',
    name: '',
    unit: '',
    quantity: 1,
    unit_price: 0,
    discount_rate: null,
    tax_rate: null,
    tax_amount: 0,
    line_total: 0,
  }
}

function money(n) {
  return Math.round(Number(n || 0) * 100) / 100
}

function syncFromProps() {
  const rows = Array.isArray(props.modelValue) ? props.modelValue : []
  draft.value = rows.map((l) => {
    if (isDeal.value) {
      return {
        product_id: l.product_id || '',
        product_code: l.product_code || '',
        product_name: l.product_name || '',
        unit: l.unit || '',
        quantity: Number(l.quantity) || 0,
        unit_price: Number(l.unit_price) || 0,
        discount_percent: Number(l.discount_percent) || 0,
        tax_rate: l.tax_rate != null ? Number(l.tax_rate) : null,
        tax_amount: Number(l.tax_amount || 0),
        subtotal: Number(l.subtotal) || 0,
      }
    }
    return {
      product_id: l.product_id || '',
      product_code: l.product_code || '',
      name: l.name || '',
      unit: l.unit || '',
      quantity: Number(l.quantity) || 0,
      unit_price: Number(l.unit_price) || 0,
      discount_rate: l.discount_rate != null ? Number(l.discount_rate) : null,
      tax_rate: l.tax_rate != null ? Number(l.tax_rate) : null,
      tax_amount: Number(l.tax_amount || 0),
      line_total: Number(l.line_total) || 0,
    }
  })
}

/** 镜像 tax_engine：行未税 + 税额 + ±0.01 末行尾差 */
function recomputeTaxes(lines) {
  const discKey = isDeal.value ? 'discount_percent' : 'discount_rate'
  const totalKey = isDeal.value ? 'subtotal' : 'line_total'
  lines.forEach((l) => {
    const qty = Number(l.quantity) || 0
    const price = Number(l.unit_price) || 0
    const d = Number(l[discKey]) || 0
    const ex = money(qty * price * (1 - d / 100))
    l[totalKey] = ex
    const rate = l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null
    l.tax_amount = rate != null && rate !== 0 ? money(ex * (rate / 100)) : 0
  })
  let exactAcc = 0
  lines.forEach((l) => {
    const rate = l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null
    if (rate != null && rate !== 0) exactAcc += Number(l[totalKey]) * (rate / 100)
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
}

function recompute() {
  recomputeTaxes(draft.value)
}

const total = computed(() => {
  const key = isDeal.value ? 'subtotal' : 'line_total'
  return money(draft.value.reduce((s, l) => s + (Number(l[key]) || 0), 0))
})
const taxTotal = computed(() => {
  const rows = props.editable ? draft.value : props.modelValue || []
  return money(rows.reduce((s, l) => s + Number(l.tax_amount || 0), 0))
})
const inclTotal = computed(() => money(total.value + taxTotal.value))

function displayName(row) {
  return isDeal.value ? row.product_name : row.name
}

function lineEx(row) {
  return Number(isDeal.value ? row.subtotal : row.line_total) || 0
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

function applyProductToLine(line, product) {
  line.product_id = product.id
  line.product_code = product.code || ''
  if (isDeal.value) {
    line.product_name = product.name || ''
  } else {
    line.name = product.name || ''
  }
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

function onProductsPicked(products) {
  if (!products?.length) return
  if (!pickerMultiple.value && replaceLineIndex.value >= 0) {
    const line = draft.value[replaceLineIndex.value]
    if (line) {
      applyProductToLine(line, products[0])
      recompute()
    }
    return
  }
  for (const p of products) {
    const line = emptyLine()
    applyProductToLine(line, p)
    draft.value.push(line)
  }
  recompute()
  ElMessage.success(`已添加 ${products.length} 个产品`)
}

function addLine() {
  draft.value.push(emptyLine())
}

function removeLine(idx) {
  draft.value.splice(idx, 1)
  recompute()
}

function duplicateLine(idx) {
  const src = draft.value[idx]
  if (!src) return
  const copy = { ...src, quantity: Number(src.quantity) || 1 }
  draft.value.splice(idx + 1, 0, copy)
  recompute()
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function handleSave() {
  for (const l of draft.value) {
    const name = isDeal.value ? l.product_name : l.name
    if (!String(name || '').trim()) {
      ElMessage.warning('请填写行项名称')
      return
    }
  }
  recompute()
  const payload = draft.value.map((l, i) => {
    if (isDeal.value) {
      return {
        product_id: l.product_id || null,
        product_name: String(l.product_name).trim(),
        unit: l.unit || null,
        quantity: Number(l.quantity) || 0,
        unit_price: Number(l.unit_price) || 0,
        discount_percent: Number(l.discount_percent) || 0,
        tax_rate: l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null,
        tax_amount: Number(l.tax_amount || 0),
        subtotal: Number(l.subtotal) || 0,
        sort_order: i,
      }
    }
    return {
      product_id: l.product_id || null,
      name: String(l.name).trim(),
      unit: l.unit || null,
      quantity: Number(l.quantity) || 0,
      unit_price: Number(l.unit_price) || 0,
      discount_rate: l.discount_rate != null ? Number(l.discount_rate) : null,
      tax_rate: l.tax_rate != null ? Number(l.tax_rate) : null,
      tax_amount: Number(l.tax_amount || 0),
      line_total: Number(l.line_total) || 0,
      sort_order: i,
    }
  })
  emit('update:modelValue', payload)
  emit('save', payload)
}

watch(
  () => props.modelValue,
  () => {
    if (!props.editable) syncFromProps()
  },
  { deep: true, immediate: true },
)

watch(
  () => props.editable,
  (v) => {
    if (v) syncFromProps()
  },
)
</script>

<template>
  <div class="crm-line-items">
    <div v-if="editable" class="crm-line-items__toolbar">
      <div class="crm-line-items__toolbar-left">
        <span class="crm-line-items__label">明细</span>
        <el-tag v-if="lineCount" size="small" effect="plain" type="info">{{ lineCount }} 行</el-tag>
      </div>
      <div class="crm-line-items__toolbar-right">
        <el-button size="small" :icon="Plus" @click="addLine">空白行</el-button>
        <el-button size="small" type="primary" :icon="Goods" @click="openAddProducts">添加产品</el-button>
        <el-button size="small" type="success" :loading="saving" @click="handleSave">保存明细</el-button>
      </div>
    </div>

    <div v-if="editable && !draft.length" class="crm-line-items__empty">
      <p>暂无明细，从产品库批量添加更高效</p>
      <el-button type="primary" size="small" :icon="Goods" @click="openAddProducts">添加产品</el-button>
    </div>

    <el-table
      v-else
      :data="editable ? draft : (modelValue || [])"
      border
      size="small"
      empty-text="暂无明细"
      class="crm-line-items__table"
    >
      <el-table-column label="产品" min-width="200">
        <template #default="{ row, $index }">
          <template v-if="editable">
            <div v-if="row.product_id || displayName(row)" class="line-product">
              <div class="line-product__main">
                <div class="line-product__name">{{ displayName(row) || '未命名' }}</div>
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
          <span v-else>{{ displayName(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="名称" min-width="140">
        <template #default="{ row }">
          <el-input
            v-if="editable"
            v-model="row[isDeal ? 'product_name' : 'name']"
            maxlength="200"
            size="small"
          />
          <span v-else>{{ displayName(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="单位" width="72">
        <template #default="{ row }">
          <el-input v-if="editable" v-model="row.unit" maxlength="30" size="small" />
          <span v-else>{{ row.unit || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="数量" width="100" align="right">
        <template #default="{ row }">
          <el-input-number
            v-if="editable"
            v-model="row.quantity"
            :min="0"
            :precision="2"
            :controls="false"
            size="small"
            style="width: 100%"
            @change="recompute"
          />
          <span v-else>{{ row.quantity }}</span>
        </template>
      </el-table-column>
      <el-table-column label="单价(未税)" width="110" align="right">
        <template #default="{ row }">
          <el-input-number
            v-if="editable"
            v-model="row.unit_price"
            :min="0"
            :precision="2"
            :controls="false"
            size="small"
            style="width: 100%"
            @change="recompute"
          />
          <span v-else>¥{{ formatAmount(row.unit_price) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="折扣%" width="88" align="right">
        <template #default="{ row }">
          <el-input-number
            v-if="editable"
            v-model="row[isDeal ? 'discount_percent' : 'discount_rate']"
            :min="0"
            :max="100"
            :precision="2"
            :controls="false"
            size="small"
            style="width: 100%"
            @change="recompute"
          />
          <span v-else>
            {{
              isDeal
                ? `${row.discount_percent ?? 0}%`
                : (row.discount_rate != null ? `${row.discount_rate}%` : '—')
            }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="税率%" width="88" align="right">
        <template #default="{ row }">
          <el-input-number
            v-if="editable"
            v-model="row.tax_rate"
            :min="0"
            :max="100"
            :precision="2"
            :controls="false"
            size="small"
            style="width: 100%"
            @change="recompute"
          />
          <span v-else>{{ row.tax_rate != null ? `${row.tax_rate}%` : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="税额" width="100" align="right">
        <template #default="{ row }">¥{{ formatAmount(row.tax_amount) }}</template>
      </el-table-column>
      <el-table-column label="未税" width="110" align="right">
        <template #default="{ row }">
          ¥{{ formatAmount(lineEx(row)) }}
        </template>
      </el-table-column>
      <el-table-column label="含税" width="110" align="right">
        <template #default="{ row }">
          ¥{{ formatAmount(lineEx(row) + Number(row.tax_amount || 0)) }}
        </template>
      </el-table-column>
      <el-table-column v-if="editable" label="" width="84" align="center" fixed="right">
        <template #default="{ $index }">
          <el-button link type="primary" :icon="CopyDocument" title="复制行" @click="duplicateLine($index)" />
          <el-button link type="danger" :icon="Delete" title="删除" @click="removeLine($index)" />
        </template>
      </el-table-column>
    </el-table>

    <div class="crm-line-items__total">
      未税 <b>¥{{ formatAmount(editable ? total : (
        (modelValue || []).reduce((s, l) => s + lineEx(l), 0)
      )) }}</b>
      <span class="crm-line-items__tax">税额 ¥{{ formatAmount(taxTotal) }}</span>
      价税 <b>¥{{ formatAmount(editable ? inclTotal : money(
        (modelValue || []).reduce((s, l) => s + lineEx(l) + Number(l.tax_amount || 0), 0),
      )) }}</b>
    </div>

    <CrmProductPicker
      v-if="editable"
      v-model:visible="pickerVisible"
      :multiple="pickerMultiple"
      :title="pickerMultiple ? '添加产品' : '更换产品'"
      @confirm="onProductsPicked"
    />
  </div>
</template>

<style scoped>
.crm-line-items__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.crm-line-items__toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.crm-line-items__label {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.crm-line-items__toolbar-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.crm-line-items__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px 16px;
  margin-bottom: 10px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  color: #94a3b8;
  font-size: 13px;
}

.crm-line-items__empty p {
  margin: 0;
}

.crm-line-items__table :deep(.el-table__header th) {
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

.crm-line-items__total {
  margin-top: 10px;
  text-align: right;
  font-size: 14px;
  color: #64748b;
}

.crm-line-items__total b {
  color: var(--el-color-primary);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.crm-line-items__tax {
  margin: 0 12px;
  color: #94a3b8;
}
</style>
