<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** 多选 / 单选 */
  multiple: { type: Boolean, default: true },
  title: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'confirm'])

const drawerVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const dialogTitle = computed(() => props.title || (props.multiple ? '添加产品' : '选择产品'))

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const categoryId = ref('')
const categories = ref([])
const selectedMap = ref(new Map())
const tableRef = ref(null)
let searchTimer = null
let syncingSelection = false

const selectedList = computed(() => Array.from(selectedMap.value.values()))
const selectedCount = computed(() => selectedList.value.length)

function formatPrice(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function productKey(p) {
  return String(p.id)
}

async function loadCategories() {
  try {
    const { data } = await crmApi.listProductCategories({ active_only: true })
    categories.value = Array.isArray(data) ? data : []
  } catch {
    categories.value = []
  }
}

async function loadProducts() {
  loading.value = true
  try {
    const { data } = await crmApi.listProducts({
      page: page.value,
      page_size: pageSize.value,
      is_active: true,
      q: keyword.value.trim() || undefined,
      category_id: categoryId.value || undefined,
    })
    items.value = (data.items || []).map((p) => ({
      id: p.id,
      name: p.name,
      code: p.code,
      unit: p.unit || '',
      list_price: Number(p.list_price || 0),
      default_tax_rate: p.default_tax_rate != null ? Number(p.default_tax_rate) : null,
      price_includes_tax: !!p.price_includes_tax,
      category_id: p.category_id || null,
    }))
    total.value = data.total || 0
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
    await nextTick()
    syncTableSelection()
  }
}

function syncTableSelection() {
  const table = tableRef.value
  if (!table || !props.multiple) return
  syncingSelection = true
  table.clearSelection()
  for (const row of items.value) {
    if (selectedMap.value.has(productKey(row))) {
      table.toggleRowSelection(row, true)
    }
  }
  nextTick(() => {
    syncingSelection = false
  })
}

function scheduleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadProducts()
  }, 280)
}

function onSearchClear() {
  keyword.value = ''
  page.value = 1
  loadProducts()
}

function onCategoryChange() {
  page.value = 1
  loadProducts()
}

function onPageChange(p) {
  page.value = p
  loadProducts()
}

function onSelectionChange(rows) {
  if (!props.multiple || syncingSelection) return
  const pageIds = new Set(items.value.map(productKey))
  const next = new Map(selectedMap.value)
  for (const id of pageIds) {
    if (![...rows].some((r) => productKey(r) === id)) {
      next.delete(id)
    }
  }
  for (const row of rows) {
    next.set(productKey(row), row)
  }
  selectedMap.value = next
}

function onRowClick(row) {
  if (props.multiple) {
    const table = tableRef.value
    if (!table) return
    const key = productKey(row)
    const selected = selectedMap.value.has(key)
    table.toggleRowSelection(row, !selected)
    return
  }
  selectedMap.value = new Map([[productKey(row), row]])
  confirm()
}

function removeSelected(id) {
  const next = new Map(selectedMap.value)
  next.delete(String(id))
  selectedMap.value = next
  nextTick(syncTableSelection)
}

function clearSelected() {
  selectedMap.value = new Map()
  nextTick(syncTableSelection)
}

function confirm() {
  const list = selectedList.value
  if (!list.length) return
  emit('confirm', list.map((p) => ({ ...p })))
  drawerVisible.value = false
}

function resetState() {
  keyword.value = ''
  categoryId.value = ''
  page.value = 1
  selectedMap.value = new Map()
  items.value = []
  total.value = 0
}

watch(
  () => props.visible,
  async (v) => {
    if (!v) {
      if (searchTimer) clearTimeout(searchTimer)
      return
    }
    resetState()
    await loadCategories()
    await loadProducts()
  },
)
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="dialogTitle"
    size="640px"
    append-to-body
    destroy-on-close
    class="crm-product-picker-drawer"
  >
    <div class="picker">
      <div class="picker__toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索编码 / 名称"
          :prefix-icon="Search"
          class="picker__search"
          @input="scheduleSearch"
          @clear="onSearchClear"
          @keyup.enter="() => { page = 1; loadProducts() }"
        />
        <el-select
          v-model="categoryId"
          clearable
          filterable
          placeholder="全部分类"
          class="picker__category"
          @change="onCategoryChange"
        >
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </div>

      <div v-if="multiple && selectedCount" class="picker__chips">
        <div class="picker__chips-head">
          <span>已选 <b>{{ selectedCount }}</b> 个</span>
          <el-button link type="primary" size="small" @click="clearSelected">清空</el-button>
        </div>
        <div class="picker__chip-list">
          <el-tag
            v-for="p in selectedList"
            :key="p.id"
            closable
            type="info"
            effect="plain"
            class="picker__chip"
            @close="removeSelected(p.id)"
          >
            <span class="picker__chip-code">{{ p.code }}</span>
            <span class="picker__chip-name">{{ p.name }}</span>
          </el-tag>
        </div>
      </div>

      <div class="picker__table-wrap" v-loading="loading">
        <el-table
          ref="tableRef"
          :data="items"
          height="100%"
          row-key="id"
          highlight-current-row
          class="picker__table"
          empty-text="未找到产品，试试换个关键词"
          @selection-change="onSelectionChange"
          @row-click="onRowClick"
        >
          <el-table-column v-if="multiple" type="selection" width="44" reserve-selection />
          <el-table-column label="产品" min-width="220">
            <template #default="{ row }">
              <div class="picker__product">
                <div class="picker__product-name">{{ row.name }}</div>
                <div class="picker__product-code">{{ row.code }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="单位" width="72" align="center">
            <template #default="{ row }">{{ row.unit || '—' }}</template>
          </el-table-column>
          <el-table-column label="单价" width="110" align="right">
            <template #default="{ row }">
              <span class="picker__price">¥{{ formatPrice(row.list_price) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="picker__pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          small
          background
          @current-change="onPageChange"
        />
      </div>
    </div>

    <template #footer>
      <div class="picker__footer">
        <span class="picker__footer-hint">
          <template v-if="multiple">点击行可勾选，支持跨页多选</template>
          <template v-else>点击一行即可选择</template>
        </span>
        <div class="picker__footer-actions">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button
            v-if="multiple"
            type="primary"
            :disabled="!selectedCount"
            @click="confirm"
          >
            添加 {{ selectedCount ? `(${selectedCount})` : '' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 12px;
}

.picker__toolbar {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.picker__search {
  flex: 1;
  min-width: 0;
}

.picker__category {
  width: 160px;
  flex-shrink: 0;
}

.picker__chips {
  flex-shrink: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f7f9fc 0%, #f0f4fa 100%);
  border: 1px solid #e8eef6;
}

.picker__chips-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: #5b6b7c;
}

.picker__chips-head b {
  color: var(--el-color-primary);
  font-weight: 600;
}

.picker__chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 88px;
  overflow-y: auto;
}

.picker__chip {
  max-width: 220px;
}

.picker__chip-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  margin-right: 6px;
  color: #64748b;
}

.picker__chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.picker__table-wrap {
  flex: 1;
  min-height: 280px;
  border: 1px solid #e8eef6;
  border-radius: 10px;
  overflow: hidden;
}

.picker__table {
  --el-table-header-bg-color: #f8fafc;
}

.picker__table :deep(.el-table__row) {
  cursor: pointer;
}

.picker__table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #f5f9ff !important;
}

.picker__product-name {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker__product-code {
  margin-top: 2px;
  font-size: 12px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.picker__price {
  font-variant-numeric: tabular-nums;
  color: #334155;
  font-weight: 500;
}

.picker__pager {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
}

.picker__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.picker__footer-hint {
  font-size: 12px;
  color: #94a3b8;
}

.picker__footer-actions {
  display: flex;
  gap: 8px;
}
</style>

<style>
.crm-product-picker-drawer .el-drawer__body {
  display: flex;
  flex-direction: column;
  padding: 12px 20px 0;
  overflow: hidden;
  height: calc(100% - 120px);
}

.crm-product-picker-drawer .el-drawer__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid #eef2f7;
}
</style>
