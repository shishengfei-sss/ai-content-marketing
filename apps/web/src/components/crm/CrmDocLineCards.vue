<script setup>
/**
 * 报价 / 订单 / 合同 共用的明细卡片编辑器（价税 + 产品选择）
 * 行字段：name / discount_rate / line_total / tax_rate / tax_amount
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Delete, Plus, Goods } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import CrmProductPicker from './CrmProductPicker.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  title: { type: String, default: '产品明细' },
  emptyDesc: { type: String, default: '从产品库批量添加，自动带入单价与税率' },
  /** 整单折扣%（报价用）；订单/合同传 null */
  headerDiscountRate: { type: Number, default: null },
  /** 是否启用 CPQ 单价解析（报价） */
  resolveCpq: { type: Boolean, default: false },
  pickerTitleAdd: { type: String, default: '添加产品' },
  pickerTitleReplace: { type: String, default: '更换产品' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const TAX_PRESETS = [13, 9, 6, 0]
const pickerVisible = ref(false)
const pickerMultiple = ref(true)
const replaceLineIndex = ref(-1)

const lines = computed({
  get: () => props.modelValue || [],
  set: (v) => emit('update:modelValue', v),
})

const lineCount = computed(() => lines.value.length)

function money(n) {
  return Math.round(Number(n || 0) * 100) / 100
}

function formatMoney(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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
    tax_amount: 0,
    line_total: 0,
  }
}

function recomputeAllLines() {
  const rows = lines.value
  if (!rows.length) {
    emit('change')
    return
  }
  const hdr = Number(props.headerDiscountRate || 0)
  const befores = rows.map((l) => {
    const qty = Number(l.quantity || 0)
    const price = Number(l.unit_price || 0)
    const disc = Number(l.discount_rate || 0)
    return money(qty * price * (1 - disc / 100))
  })
  const sub = money(befores.reduce((a, b) => a + b, 0))
  const target = hdr > 0 && sub > 0 ? money(sub * (1 - hdr / 100)) : sub
  let allocated = 0
  rows.forEach((l, i) => {
    let ex
    if (hdr <= 0) ex = befores[i]
    else if (i < rows.length - 1) {
      ex = sub > 0 ? money((befores[i] * target) / sub) : 0
      allocated = money(allocated + ex)
    } else {
      ex = money(target - allocated)
    }
    l.line_total = ex
    const rate = l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null
    l.tax_amount = rate != null && rate !== 0 ? money(ex * (rate / 100)) : 0
  })
  let exactAcc = 0
  rows.forEach((l) => {
    const rate = l.tax_rate != null && l.tax_rate !== '' ? Number(l.tax_rate) : null
    if (rate != null && rate !== 0) exactAcc += Number(l.line_total) * (rate / 100)
  })
  const exact = money(exactAcc)
  const taxSum = money(rows.reduce((a, l) => a + Number(l.tax_amount || 0), 0))
  const delta = money(exact - taxSum)
  if (Math.abs(delta) === 0.01 && rows.length) {
    let idx = rows.length - 1
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      if (rows[i].tax_rate != null && Number(rows[i].tax_rate) !== 0) {
        idx = i
        break
      }
    }
    rows[idx].tax_amount = money(Number(rows[idx].tax_amount || 0) + delta)
  }
  emit('change')
}

const subTotalBeforeHeader = computed(() =>
  money(
    lines.value.reduce((acc, l) => {
      const qty = Number(l.quantity || 0)
      const price = Number(l.unit_price || 0)
      const disc = Number(l.discount_rate || 0)
      return acc + qty * price * (1 - disc / 100)
    }, 0),
  ),
)
const discountAmount = computed(() => {
  const rate = Number(props.headerDiscountRate || 0)
  if (!rate || !subTotalBeforeHeader.value) return 0
  return money(subTotalBeforeHeader.value * (rate / 100))
})
const hasOrderDiscount = computed(
  () => Number(props.headerDiscountRate || 0) > 0 || discountAmount.value > 0,
)
const grandTotal = computed(() =>
  money(lines.value.reduce((acc, l) => acc + Number(l.line_total || 0), 0)),
)
const taxTotal = computed(() =>
  money(lines.value.reduce((acc, l) => acc + Number(l.tax_amount || 0), 0)),
)
const amountInclTax = computed(() => money(grandTotal.value + taxTotal.value))

watch(
  () => props.headerDiscountRate,
  () => recomputeAllLines(),
)

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
  lines.value = [...lines.value, emptyLine()]
}

function removeLine(idx) {
  const next = [...lines.value]
  next.splice(idx, 1)
  lines.value = next
  recomputeAllLines()
}

function duplicateLine(idx) {
  const src = lines.value[idx]
  if (!src) return
  const next = [...lines.value]
  next.splice(idx + 1, 0, { ...src, quantity: Number(src.quantity) || 1 })
  lines.value = next
  recomputeAllLines()
}

function setTaxRate(row, rate) {
  row.tax_rate = rate
  recomputeAllLines()
}

async function applyProductToLine(line, product) {
  line.product_id = product.id
  line.product_code = product.code || ''
  line.name = product.name || ''
  line.unit = product.unit || ''
  const taxRate = product.default_tax_rate != null ? Number(product.default_tax_rate) : null
  line.tax_rate = taxRate
  let unitPrice = Number(product.list_price) || 0
  if (product.price_includes_tax && taxRate != null && taxRate > 0) {
    unitPrice = money(unitPrice / (1 + taxRate / 100))
  }
  line.unit_price = unitPrice
  if (!line.quantity) line.quantity = 1
  if (props.resolveCpq && line.product_id) {
    try {
      const { data } = await crmApi.resolveCpqPrice({
        product_id: line.product_id,
        quantity: Number(line.quantity) || 1,
      })
      if (data?.unit_price != null) {
        let cpqPrice = Number(data.unit_price)
        if (product.price_includes_tax && taxRate != null && taxRate > 0) {
          cpqPrice = money(cpqPrice / (1 + taxRate / 100))
        }
        line.unit_price = cpqPrice
      }
    } catch {
      /* keep */
    }
  }
}

async function onProductsPicked(products) {
  if (!products?.length) return
  if (!pickerMultiple.value && replaceLineIndex.value >= 0) {
    const line = lines.value[replaceLineIndex.value]
    if (line) {
      await applyProductToLine(line, products[0])
      recomputeAllLines()
    }
    return
  }
  const next = [...lines.value]
  for (const p of products) {
    const line = emptyLine()
    await applyProductToLine(line, p)
    next.push(line)
  }
  lines.value = next
  recomputeAllLines()
  ElMessage.success(`已添加 ${products.length} 个产品`)
}

async function onQuantityChange(row) {
  if (props.resolveCpq && row.product_id) {
    try {
      const { data } = await crmApi.resolveCpqPrice({
        product_id: row.product_id,
        quantity: Number(row.quantity) || 1,
      })
      if (data?.unit_price != null) {
        let price = Number(data.unit_price)
        const rate = row.tax_rate != null ? Number(row.tax_rate) : null
        // CPQ 返回的是标价口径；若产品含税需由调用方传入——此处仅更新数量后重算
        row.unit_price = price
        void rate
      }
    } catch {
      /* keep */
    }
  }
  recomputeAllLines()
}

defineExpose({ recomputeAllLines, openAddProducts, addBlankLine })
</script>

<template>
  <div class="doc-lines">
    <div class="doc-lines__head">
      <div class="doc-lines__title">
        <span>{{ title }}</span>
        <el-tag v-if="lineCount" size="small" effect="plain" round>{{ lineCount }} 行</el-tag>
      </div>
      <div class="doc-lines__actions">
        <el-button text bg size="small" :icon="Plus" @click="addBlankLine">空白行</el-button>
        <el-button type="primary" size="small" :icon="Goods" @click="openAddProducts">
          添加产品
        </el-button>
      </div>
    </div>

    <div v-if="!lines.length" class="doc-lines__empty">
      <div class="doc-lines__empty-icon">
        <el-icon :size="26"><Goods /></el-icon>
      </div>
      <p class="doc-lines__empty-title">还没有明细</p>
      <p class="doc-lines__empty-desc">{{ emptyDesc }}</p>
      <div class="doc-lines__empty-btns">
        <el-button type="primary" :icon="Goods" @click="openAddProducts">添加产品</el-button>
        <el-button :icon="Plus" @click="addBlankLine">添加空白行</el-button>
      </div>
    </div>

    <div v-else class="doc-lines__list">
      <article v-for="(row, idx) in lines" :key="idx" class="doc-line-card">
        <header class="doc-line-card__head">
          <div class="doc-line-card__index">{{ idx + 1 }}</div>
          <div class="doc-line-card__product">
            <template v-if="row.product_id || row.name">
              <div class="doc-line-card__name" :title="row.name">{{ row.name || '未命名' }}</div>
              <div v-if="row.product_code" class="doc-line-card__code">{{ row.product_code }}</div>
            </template>
            <el-button v-else link type="primary" size="small" @click="openReplaceProduct(idx)">
              选择产品
            </el-button>
          </div>
          <div class="doc-line-card__ops">
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

        <div class="doc-line-card__fields">
          <label class="doc-field">
            <span>名称</span>
            <el-input v-model="row.name" placeholder="显示名称" />
          </label>
          <label class="doc-field doc-field--sm">
            <span>单位</span>
            <el-input v-model="row.unit" placeholder="个" />
          </label>
          <label class="doc-field">
            <span>数量</span>
            <el-input-number
              v-model="row.quantity"
              :min="0"
              :precision="2"
              :controls="false"
              style="width: 100%"
              @change="onQuantityChange(row)"
            />
          </label>
          <label class="doc-field">
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
          <label class="doc-field doc-field--sm">
            <span>折扣%</span>
            <el-input-number
              v-model="row.discount_rate"
              :min="0"
              :max="100"
              :precision="2"
              :controls="false"
              style="width: 100%"
              @change="recomputeAllLines"
            />
          </label>
        </div>

        <div class="doc-line-card__tax">
          <div class="doc-line-card__tax-left">
            <span class="doc-field__label">税率</span>
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
          <div class="doc-line-card__amounts">
            <div class="amt">
              <span>未税</span>
              <b>¥{{ formatMoney(row.line_total) }}</b>
            </div>
            <div class="amt">
              <span>税额</span>
              <b>¥{{ formatMoney(row.tax_amount) }}</b>
            </div>
            <div class="amt amt--incl">
              <span>含税</span>
              <b>¥{{ formatMoney(Number(row.line_total || 0) + Number(row.tax_amount || 0)) }}</b>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="lines.length" class="doc-lines__footer">
      <el-button text bg size="small" :icon="Goods" @click="openAddProducts">继续添加</el-button>
      <div class="doc-lines__summary">
        <div v-if="hasOrderDiscount" class="sum-pill sum-pill--muted">
          <span>行未税</span>
          <b>¥{{ formatMoney(subTotalBeforeHeader) }}</b>
        </div>
        <div v-if="hasOrderDiscount" class="sum-pill sum-pill--muted">
          <span>整单折扣</span>
          <b>-¥{{ formatMoney(discountAmount) }}</b>
        </div>
        <div class="sum-pill">
          <span>未税</span>
          <b>¥{{ formatMoney(grandTotal) }}</b>
        </div>
        <div class="sum-pill">
          <span>税额</span>
          <b>¥{{ formatMoney(taxTotal) }}</b>
        </div>
        <div class="sum-pill sum-pill--grand">
          <span>价税合计</span>
          <b>¥{{ formatMoney(amountInclTax) }}</b>
        </div>
      </div>
    </div>

    <CrmProductPicker
      v-model:visible="pickerVisible"
      :multiple="pickerMultiple"
      :title="pickerMultiple ? pickerTitleAdd : pickerTitleReplace"
      @confirm="onProductsPicked"
    />
  </div>
</template>

<style scoped>
.doc-lines {
  margin-top: 4px;
  padding: 14px 16px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
}

.doc-lines__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.doc-lines__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 650;
  color: #0f172a;
}

.doc-lines__actions {
  display: flex;
  gap: 6px;
}

.doc-lines__empty {
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

.doc-lines__empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: var(--el-color-primary);
  margin-bottom: 4px;
}

.doc-lines__empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.doc-lines__empty-desc {
  margin: 0 0 10px;
  font-size: 13px;
}

.doc-lines__empty-btns {
  display: flex;
  gap: 8px;
}

.doc-lines__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.doc-line-card {
  padding: 12px 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.doc-line-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

.doc-line-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.doc-line-card__index {
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

.doc-line-card__product {
  min-width: 0;
  flex: 1;
}

.doc-line-card__name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-line-card__code {
  margin-top: 2px;
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.doc-line-card__ops {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.doc-line-card__fields {
  display: grid;
  grid-template-columns: minmax(140px, 1.6fr) 72px 100px 120px 88px;
  gap: 10px;
  margin-bottom: 12px;
}

.doc-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  margin: 0;
}

.doc-field > span,
.doc-field__label {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  letter-spacing: 0.02em;
}

.doc-line-card__tax {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
  flex-wrap: wrap;
}

.doc-line-card__tax-left {
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

.doc-line-card__amounts {
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

.doc-lines__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.doc-lines__summary {
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

.sum-pill--muted b {
  color: #64748b;
  font-size: 13px;
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

@media (max-width: 900px) {
  .doc-line-card__fields {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
