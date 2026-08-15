<script setup>
/**
 * 买家列表。对照 PRD 01-管理端UI.html #a11 · #a11-select-spec
 * 默认列：手机·昵称·账号状态·来源店铺·订单数·权益数·累计消费·注册渠道·最近下单·注册时间·操作
 * 列设置可选：首单时间 · buyer_id（技术）
 * 封禁：Phase1 无落库，Tab「已封禁」与账号状态「已封禁」恒空。
 * 缺口：站内信/短信本批不接（导出在页内下载，不发站内通知）。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'

const router = useRouter()
const { currentId } = useCurrentShop()
const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref('当前筛选')
const selectedRows = ref([])
const advOpen = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const revealed = reactive({})
const query = reactive({
  page: 1,
  page_size: 20,
  q: '',
  tab: '',
  account_status: '',
  order_count_min: '',
  entitlement_count_min: '',
  registered_from: '',
  registered_to: '',
  last_order_from: '',
  last_order_to: '',
})

const COL_STORAGE = 'shop.a11.columns'
const ALL_COLS = [
  { key: 'mobile', label: '手机', locked: true, defaultOn: true },
  { key: 'nickname', label: '昵称', locked: true, defaultOn: true },
  { key: 'account_status', label: '账号状态', locked: true, defaultOn: true },
  { key: 'source_shop_name', label: '来源店铺', locked: true, defaultOn: true },
  { key: 'order_count', label: '订单数', locked: true, defaultOn: true },
  { key: 'entitlement_count', label: '权益数', locked: true, defaultOn: true },
  { key: 'paid_amount', label: '累计消费', locked: true, defaultOn: true },
  { key: 'register_channel', label: '注册渠道', locked: true, defaultOn: true },
  { key: 'last_order_at', label: '最近下单', locked: true, defaultOn: true },
  { key: 'created_at', label: '注册时间', locked: true, defaultOn: true },
  { key: 'first_order_at', label: '首单时间', locked: false, defaultOn: false },
  { key: 'buyer_id', label: 'buyer_id（技术）', locked: false, defaultOn: false },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
function loadColPrefs() {
  try {
    const raw = localStorage.getItem(COL_STORAGE)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return Object.fromEntries(ALL_COLS.map((c) => [c.key, c.defaultOn]))
}
const colVisible = reactive(loadColPrefs())
const colDialog = ref(false)
const colDraft = reactive({ ...colVisible })

const TABS = [
  { key: '', label: '全部买家' },
  { key: 'with_entitlement', label: '有权益' },
  { key: 'new_7d', label: '近 7 日新注册' },
  { key: 'blocked', label: '已封禁' },
]
const STATUS_LABEL = { active: '正常', blocked: '已封禁' }

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}
function statusText(row) {
  return STATUS_LABEL[row.account_status] || '正常'
}

function numFilter(v) {
  if (v === '' || v == null) return undefined
  const n = Number(v)
  return Number.isFinite(n) ? n : undefined
}

function listParams(extra = {}) {
  return {
    q: query.q || undefined,
    tab: query.tab || undefined,
    shop_id: currentId.value || undefined,
    account_status: query.account_status || undefined,
    order_count_min: numFilter(query.order_count_min),
    entitlement_count_min: numFilter(query.entitlement_count_min),
    registered_from: query.registered_from || undefined,
    registered_to: query.registered_to || undefined,
    last_order_from: query.last_order_from || undefined,
    last_order_to: query.last_order_to || undefined,
    ...extra,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/buyers', {
      params: listParams({ page: query.page, page_size: query.page_size }),
    })
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
  query.tab = key
  query.page = 1
  load()
}

function resetAdv() {
  query.account_status = ''
  query.order_count_min = ''
  query.entitlement_count_min = ''
  query.registered_from = ''
  query.registered_to = ''
  query.last_order_from = ''
  query.last_order_to = ''
  query.page = 1
  load()
}

async function reveal(row) {
  try {
    const { data } = await api.post(`/api/v1/shop/buyers/${row.id}/reveal-sensitive`)
    revealed[row.id] = data.mobile
  } catch (e) {
    ElMessage.error(e.message || '无查看权限')
  }
}

async function exportCsv(mode) {
  if (mode === 'selected' && !selectedRows.value.length) {
    ElMessage.warning('请先选择要导出的买家')
    return
  }
  exporting.value = true
  try {
    const body = listParams(
      mode === 'selected' ? { buyer_ids: selectedRows.value.map((r) => r.id) } : {},
    )
    const { data } = await api.post('/api/v1/shop/buyers/export', body)
    exportTask.value = data
    exportScope.value = mode === 'selected' ? '选中行' : '当前筛选'
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function downloadExportFile() {
  if (!exportTask.value?.id) return
  try {
    const res = await api.get(`/api/v1/shop/buyers/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv; charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-buyers.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

function openColSettings() {
  Object.assign(colDraft, colVisible)
  colDialog.value = true
}
function saveCols() {
  Object.assign(colVisible, colDraft)
  localStorage.setItem(COL_STORAGE, JSON.stringify({ ...colVisible }))
  colDialog.value = false
}

function goDetail(row) {
  router.push({ name: 'ShopBuyerDetail', params: { id: row.id } })
}

watch(currentId, () => {
  query.page = 1
  load()
})

onMounted(load)
</script>

<template>
  <div v-loading="loading" data-testid="shop-buyers">
    <div class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key || 'all'"
        type="button"
        class="tab"
        :class="{ on: query.tab === t.key }"
        @click="selectTab(t.key)"
      >
        {{ t.label }}
        <span class="cnt">{{ tabCount(t.key === '' ? 'all' : t.key) }}</span>
      </button>
    </div>
    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="手机 / 昵称"
          style="width: 200px"
          @keyup.enter="() => { query.page = 1; load() }"
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
              <el-dropdown-item command="current">当前筛选</el-dropdown-item>
              <el-dropdown-item command="selected">选中行</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColSettings">列设置</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-select v-model="query.account_status" clearable placeholder="账号状态" style="width: 130px">
          <el-option label="正常" value="active" />
          <el-option label="已封禁" value="blocked" />
        </el-select>
        <el-input
          v-model="query.order_count_min"
          clearable
          placeholder="订单数 ≥"
          style="width: 120px"
        />
        <el-input
          v-model="query.entitlement_count_min"
          clearable
          placeholder="权益数 ≥"
          style="width: 120px"
        />
        <el-date-picker
          v-model="query.registered_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="注册起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.registered_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="注册止"
          style="width: 140px"
        />
        <el-date-picker
          v-model="query.last_order_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="最近下单起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.last_order_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="最近下单止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 与高级筛选账号状态/订单数/注册时间 AND 组合</span>
      </div>
    </div>

    <el-table
      :data="items"
      border
      stripe
      size="small"
      style="margin-top: 12px"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="42" />
      <el-table-column v-if="colVisible.mobile" label="手机" min-width="140">
        <template #default="{ row }">
          <span class="mobile">
            {{ revealed[row.id] || row.mobile_masked || '—' }}
            <el-button
              v-if="row.mobile_masked && !revealed[row.id]"
              link
              type="primary"
              :icon="View"
              @click="reveal(row)"
            />
          </span>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.nickname" prop="nickname" label="昵称" min-width="100" />
      <el-table-column v-if="colVisible.account_status" label="账号状态" width="100">
        <template #default="{ row }">{{ statusText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.source_shop_name" prop="source_shop_name" label="来源店铺" min-width="120" />
      <el-table-column v-if="colVisible.order_count" prop="order_count" label="订单数" width="80" />
      <el-table-column v-if="colVisible.entitlement_count" prop="entitlement_count" label="权益数" width="80" />
      <el-table-column v-if="colVisible.paid_amount" label="累计消费" width="100">
        <template #default="{ row }">{{ fmtMoney(row.paid_amount_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.register_channel" prop="register_channel" label="注册渠道" width="90" />
      <el-table-column v-if="colVisible.last_order_at" label="最近下单" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.last_order_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.created_at" label="注册时间" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.first_order_at" label="首单时间" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.first_order_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.buyer_id" label="buyer_id（技术）" min-width="220">
        <template #default="{ row }">{{ row.id }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.ops" label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 12px"
      @current-change="load"
      @size-change="load"
    />

    <el-dialog v-model="exportDialog" title="导出任务" width="420px">
      <el-form v-if="exportTask" label-width="100px">
        <el-form-item label="范围">{{ exportScope }}</el-form-item>
        <el-form-item label="条数">{{ exportTask.row_count ?? 0 }} 条</el-form-item>
        <el-form-item label="状态">{{ exportTask.status === 'done' ? '已完成' : (exportTask.status || '—') }}</el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :disabled="exportTask?.status !== 'done'" @click="downloadExportFile">
          下载
        </el-button>
        <el-button @click="exportDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="colDialog" title="列设置" width="360px">
      <el-checkbox
        v-for="c in ALL_COLS"
        :key="c.key"
        v-model="colDraft[c.key]"
        :disabled="c.locked"
        style="display: block; margin: 6px 0"
      >
        {{ c.label }}
      </el-checkbox>
      <template #footer>
        <el-button @click="colDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCols">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--el-border-color);
  margin-bottom: 12px;
}
.tab {
  border: 0;
  background: transparent;
  padding: 8px 14px;
  cursor: pointer;
  color: #666;
  font-size: 13px;
}
.tab.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom: 2px solid #1677ff;
}
.cnt {
  margin-left: 4px;
  font-size: 12px;
  color: #999;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
}
.left,
.right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.adv {
  margin-top: 10px;
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
.mobile {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>
