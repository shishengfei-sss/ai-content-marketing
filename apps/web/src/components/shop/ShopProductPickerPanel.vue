<script setup>
/**
 * 商家端在售商品单选面板（A14-A 步1 等）。支持搜索、类型筛选、分页。
 */
import { nextTick, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { authShopFileUrl } from '../../utils/shopContentUrl'
import { CHANNEL_MOUNT_BLOCK_TIPS } from '../../utils/shopChannelMap'

const props = defineProps({
  modelValue: { type: String, default: '' },
  shopId: { type: String, default: '' },
  /** 默认仅展示未映射商品 */
  onlyUnmapped: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'pick'])

const TYPE_LABEL = {
  course: '课程',
  digital: '资料',
  service: '服务',
}

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const type = ref('')
const showMapped = ref(!props.onlyUnmapped)
const tableRef = ref(null)
let searchTimer = null

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function mountTagType(row) {
  if (row.channel_mount === 'mapped') return 'success'
  if (row.channel_mount === 'rejected') return 'danger'
  if (row.channel_mount === 'pending' || row.channel_mount === 'syncing') return 'warning'
  return 'info'
}

function isSelectable(row) {
  return !row.channel_mount || row.channel_mount === 'none'
}

function onRowClick(row) {
  if (!isSelectable(row)) {
    ElMessage.warning(CHANNEL_MOUNT_BLOCK_TIPS[row.channel_mount] || '该商品暂不可新建映射')
    return
  }
  emit('update:modelValue', row.id)
  emit('pick', row)
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/products', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        status: 'on_sale',
        shop_id: props.shopId || undefined,
        q: keyword.value.trim() || undefined,
        type: type.value || undefined,
        channel_mount: showMapped.value ? undefined : 'none',
      },
    })
    items.value = data.items || []
    total.value = data.total || 0
    await nextTick()
    syncCurrentRow()
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function syncCurrentRow() {
  const table = tableRef.value
  if (!table || !props.modelValue) return
  const row = items.value.find((p) => p.id === props.modelValue)
  if (row) table.setCurrentRow(row)
}

function scheduleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 280)
}

function rowClassName({ row }) {
  return isSelectable(row) ? '' : 'is-disabled'
}

function onShowMappedChange() {
  page.value = 1
  load()
}

function onPageChange(p) {
  page.value = p
  load()
}

function onSizeChange(size) {
  pageSize.value = size
  page.value = 1
  load()
}

function refresh() {
  page.value = 1
  keyword.value = ''
  type.value = ''
  showMapped.value = !props.onlyUnmapped
  return load()
}

defineExpose({ refresh })

watch(
  () => props.shopId,
  () => {
    page.value = 1
    load()
  }
)

watch(
  () => props.modelValue,
  () => nextTick(syncCurrentRow)
)

load()
</script>

<template>
  <div class="shop-product-picker">
    <div class="shop-product-picker__toolbar">
      <el-input
        v-model="keyword"
        clearable
        placeholder="搜索商品名称"
        :prefix-icon="Search"
        class="shop-product-picker__search"
        @input="scheduleSearch"
        @clear="() => { page = 1; load() }"
        @keyup.enter="() => { page = 1; load() }"
      />
      <el-select
        v-model="type"
        clearable
        placeholder="全部类型"
        class="shop-product-picker__type"
        @change="() => { page = 1; load() }"
      >
        <el-option label="课程" value="course" />
        <el-option label="资料" value="digital" />
        <el-option label="服务" value="service" />
      </el-select>
    </div>

    <div class="shop-product-picker__filter">
      <el-checkbox v-model="showMapped" @change="onShowMappedChange">
        显示已映射/审核中商品
      </el-checkbox>
      <span class="shop-product-picker__hint">默认仅展示可新建映射的在售商品</span>
    </div>

    <div v-loading="loading" class="shop-product-picker__table-wrap">
      <el-table
        ref="tableRef"
        :data="items"
        height="320"
        row-key="id"
        highlight-current-row
        class="shop-product-picker__table"
        empty-text="未找到可映射商品，试试换个关键词或勾选「显示已映射/审核中商品」"
        :row-class-name="rowClassName"
        @row-click="onRowClick"
      >
        <el-table-column label="商品" min-width="220">
          <template #default="{ row }">
            <div class="shop-product-picker__product">
              <div class="shop-product-picker__cover">
                <img
                  v-if="row.cover_url"
                  :src="authShopFileUrl(row.cover_url)"
                  alt=""
                />
                <span v-else class="shop-product-picker__cover-ph">无图</span>
              </div>
              <div class="shop-product-picker__meta">
                <div class="shop-product-picker__name">{{ row.name }}</div>
                <div class="shop-product-picker__sub">
                  {{ TYPE_LABEL[row.type] || row.type || '商品' }}
                  <span v-if="row.channel_mount_label && row.channel_mount !== 'none'">
                    · {{ row.channel_mount_label }}
                  </span>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="售价" width="96" align="right">
          <template #default="{ row }">
            <span class="shop-product-picker__price">{{ fmtMoney(row.price_cents) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="公域" width="108" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="mountTagType(row)" effect="plain">
              {{ row.channel_mount_label || '未映射' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="shop-product-picker__pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        small
        background
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
.shop-product-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.shop-product-picker__toolbar {
  display: flex;
  gap: 8px;
}

.shop-product-picker__search {
  flex: 1;
  min-width: 0;
}

.shop-product-picker__type {
  width: 120px;
  flex-shrink: 0;
}

.shop-product-picker__filter {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.shop-product-picker__hint {
  color: #94a3b8;
}

.shop-product-picker__table-wrap {
  border: 1px solid #e8eef6;
  border-radius: 8px;
  overflow: hidden;
}

.shop-product-picker__table :deep(.el-table__row) {
  cursor: pointer;
}

.shop-product-picker__table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #f5f9ff !important;
}

.shop-product-picker__table :deep(.current-row > td.el-table__cell) {
  background: #e6f4ff !important;
}

.shop-product-picker__table :deep(.el-table__row.is-disabled) {
  cursor: not-allowed;
  opacity: 0.72;
}

.shop-product-picker__table :deep(.el-table__row.is-disabled:hover > td.el-table__cell) {
  background: #fafafa !important;
}

.shop-product-picker__product {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.shop-product-picker__cover {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  overflow: hidden;
  background: #f1f5f9;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.shop-product-picker__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.shop-product-picker__cover-ph {
  font-size: 10px;
  color: #94a3b8;
}

.shop-product-picker__meta {
  min-width: 0;
}

.shop-product-picker__name {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shop-product-picker__sub {
  margin-top: 2px;
  font-size: 12px;
  color: #94a3b8;
}

.shop-product-picker__price {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  color: #334155;
}

.shop-product-picker__pager {
  display: flex;
  justify-content: flex-end;
}
</style>
