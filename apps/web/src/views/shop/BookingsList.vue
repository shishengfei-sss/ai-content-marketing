<script setup>
/**
 * 全店预约名单。对照 PRD 01-管理端UI.html #a07a · #a11a-bookings · 04#select-common
 * 默认列：预约号 · 服务 · 店铺 · 时段 · 状态 · 核销码 · 来源订单 · 创建时间 · 操作
 * 缺口：导出完成站内信本批不接；无商家代取消、无到店标记。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { submitShopExport, SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../utils/shopExport'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../composables/useListColumnSettings'
import { useCurrentShop } from '../../composables/useCurrentShop'

const router = useRouter()
const { currentId } = useCurrentShop()

const loading = ref(false)
const exporting = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const advOpen = ref(false)
const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  booked_date: '',
  booked_from: '',
  booked_to: '',
})

const COL_STORAGE = 'shop.bookings.columns'
const ALL_COLS = [
  { key: 'booking_no', label: '预约号', locked: true, defaultOn: true },
  { key: 'product_name', label: '服务', defaultOn: true },
  { key: 'shop_name', label: '店铺', defaultOn: true },
  { key: 'slot', label: '时段', defaultOn: true },
  { key: 'status', label: '状态', defaultOn: true },
  { key: 'verify_code', label: '核销码', defaultOn: true },
  { key: 'order_no', label: '来源订单', defaultOn: true },
  { key: 'created_at', label: '创建时间', defaultOn: true },
  { key: 'cancel_source', label: '来源', defaultOn: false },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys,
  columnDialogVisible: colDialog,
  columnDraft,
  openColumnSettings,
  saveColumnSettings,
  isColVisible,
} = useListColumnSettings(ALL_COLS, COL_STORAGE)

const TABS = [
  { key: '', label: '全部' },
  { key: 'booked', label: '待服务' },
  { key: 'completed', label: '已完成' },
  { key: 'cancelled', label: '已取消' },
]

const STATUS_LABEL = {
  booked: '待服务',
  completed: '已完成',
  cancelled: '已取消',
}
const SOURCE_LABEL = {
  expired_unredeemed: '过期未核销',
  slot_closed: '关闭时段',
  buyer_cancel: '买家取消',
}

const rosterVisible = ref(false)
const rosterLoading = ref(false)
const roster = ref([])
const rosterMeta = ref('')

function statusText(row) {
  return row.status_label || STATUS_LABEL[row.status] || row.status || '—'
}
function sourceText(row) {
  if (row.status !== 'cancelled') return '—'
  return SOURCE_LABEL[row.cancel_reason] || '—'
}
function slotText(row) {
  return `${row.booked_date || ''} ${row.booked_time_slot || ''}`.trim() || '—'
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}

function listParams() {
  return {
    page: query.page,
    page_size: query.page_size,
    status: query.status || undefined,
    q: query.q || undefined,
    booked_date: query.booked_date || undefined,
    booked_from: query.booked_from || undefined,
    booked_to: query.booked_to || undefined,
    shop_id: currentId.value || undefined,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/bookings', { params: listParams() })
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function selectTab(key) {
  query.status = key
  query.page = 1
  load()
}

function resetAdv() {
  query.booked_from = ''
  query.booked_to = ''
  query.page = 1
  load()
}

function visibleExportColumns() {
  return visibleKeys.value.filter((k) => k !== 'ops')
}

async function exportCsv(mode) {
  exporting.value = true
  try {
    const body = { ...listParams() }
    delete body.page
    delete body.page_size
    if (mode === 'columns') {
      body.columns = visibleExportColumns()
    }
    await submitShopExport(
      '/api/v1/shop/bookings/export',
      body,
      '/api/v1/shop/bookings/export-tasks',
      'shop-bookings.csv',
      total.value,
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}


function goOrder(row) {
  if (!row.order_id) return
  router.push({ name: 'ShopOrderDetail', params: { id: row.order_id } })
}

async function openRoster(row) {
  if (!row.offer_id || !row.slot_id) {
    ElMessage.info('该预约无时段名单')
    return
  }
  rosterMeta.value = slotText(row)
  rosterVisible.value = true
  rosterLoading.value = true
  try {
    const { data } = await api.get(
      `/api/v1/shop/service-offers/${row.offer_id}/slots/${row.slot_id}/bookings`
    )
    roster.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    ElMessage.error(e.message || '加载名单失败')
    roster.value = []
  } finally {
    rosterLoading.value = false
  }
}

watch(currentId, () => {
  query.page = 1
  load()
})

onMounted(load)
</script>

<template>
  <div v-loading="loading" data-testid="shop-bookings">
    <div class="status-tabs">
      <button
        v-for="t in TABS"
        :key="t.key || 'all'"
        type="button"
        class="status-tab"
        :class="{ on: query.status === t.key }"
        @click="selectTab(t.key)"
      >
        {{ t.label }}
        <span class="cnt">{{ tabCount(t.key) }}</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="预约号 / 服务 / 核销码"
          style="width: 220px"
          @keyup.enter="() => { query.page = 1; load() }"
        />
        <el-date-picker
          v-model="query.booked_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="预约日期"
          clearable
          @change="() => { query.page = 1; load() }"
        />
        <el-button :type="advOpen ? 'primary' : 'default'" plain @click="advOpen = !advOpen">
          高级筛选
        </el-button>
      </div>
      <div class="right">
        <el-dropdown trigger="click" @command="exportCsv">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
              <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnSettings">列设置</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-date-picker
          v-model="query.booked_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="预约起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.booked_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="预约止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 已覆盖待服务/已完成/已取消；预约日期区间在高级筛选</span>
      </div>
    </div>

    <el-table :data="items" border stripe size="small">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column v-if="colKey === 'booking_no'" label="预约号" width="120">
        <template #default="{ row }">{{ row.booking_no || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'product_name'" prop="product_name" label="服务" min-width="140" />
      <el-table-column v-if="colKey === 'shop_name'" prop="shop_name" label="店铺" width="120" />
      <el-table-column v-if="colKey === 'slot'" label="时段" min-width="160">
        <template #default="{ row }">{{ slotText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'status'" label="状态" width="90">
        <template #default="{ row }">{{ statusText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'verify_code'" label="核销码" width="100">
        <template #default="{ row }">{{ row.verify_code || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'order_no'" label="来源订单" min-width="140">
        <template #default="{ row }">
          <el-button v-if="row.order_id" link type="primary" @click="goOrder(row)">
            {{ row.order_no }}
          </el-button>
          <span v-else>{{ row.order_no || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'created_at'" label="创建时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'cancel_source'" label="来源" width="110">
        <template #default="{ row }">{{ sourceText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'ops'" label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.offer_id && row.slot_id" link type="primary" @click="openRoster(row)">
            查看名单
          </el-button>
          <span v-else>只读</span>
        </template>
      </el-table-column>
      </template>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="load"
      />
    </div>

    <el-drawer v-model="rosterVisible" :title="`预约名单 · ${rosterMeta}`" size="420px">
      <div v-loading="rosterLoading">
        <el-table :data="roster" size="small">
          <el-table-column prop="buyer_mobile_masked" label="买家" min-width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              {{ { booked: '待服务', completed: '已核销', cancelled: '已取消' }[row.status] || row.status }}
            </template>
          </el-table-column>
          <el-table-column label="来源" min-width="100">
            <template #default="{ row }">{{ sourceText(row) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="columnDraft"
      @save="() => { saveColumnSettings(); ElMessage.success('列设置已保存') }"
    />
  </div>
</template>

<style scoped>
.status-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.status-tab {
  border: 0;
  background: transparent;
  padding: 8px 12px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
}
.status-tab.on {
  color: var(--el-color-primary);
  font-weight: 700;
  border-bottom: 2px solid var(--el-color-primary);
}
.cnt {
  margin-left: 4px;
  font-size: 12px;
  opacity: 0.75;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.left,
.right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.adv {
  margin-bottom: 12px;
  border: 1px solid #91caff;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f0f7ff;
  font-size: 12px;
}
.adv-t {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.adv-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.sep {
  color: #999;
}
.hint {
  color: #666;
  font-size: 11px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
