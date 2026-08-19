<script setup>
/**
 * A17 店铺管理。对照 PRD 01-管理端UI.html #a17 · #a17a · #a17b · #a17c · #a17d · 04#select-common
 * 默认列：店铺名、店铺短码、商品数、本月 GMV、创建时间、状态、操作
 * 缺口：导出完成站内信本批不接。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/client'
import { submitShopExport, SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../utils/shopExport'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import { setCurrentShopId, useCurrentShop } from '../../composables/useCurrentShop'

const COL_STORAGE = 'shop.a17.columns'

const router = useRouter()
const { currentId: currentShopId } = useCurrentShop()
const loading = ref(false)
const exporting = ref(false)
const items = ref([])
const total = ref(0)
const quota = ref({ used: 0, max: null, at_limit: false })
const statusCounts = ref({})

const query = reactive({
  page: 1,
  page_size: 20,
  q: '',
  tab: '',
  status: '',
  product_count_min: undefined,
  product_count_max: undefined,
  created_from: '',
  created_to: '',
  sort: '',
})
const advOpen = ref(false)

const TABS = [
  { key: '', label: '全部店铺', countKey: 'all' },
  { key: 'draft', label: '待开业', countKey: 'draft' },
  { key: 'active', label: '营业', countKey: 'active' },
  { key: 'paused', label: '已暂停', countKey: 'paused' },
]

const ALL_COLS = [
  { key: 'name', label: '店铺名', locked: true, defaultOn: true },
  { key: 'slug', label: '店铺短码', defaultOn: true },
  { key: 'product_count', label: '商品数', defaultOn: true },
  { key: 'month_gmv', label: '本月 GMV', defaultOn: true },
  { key: 'created_at', label: '创建时间', defaultOn: true },
  { key: 'status', label: '状态', defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]

const visibleCols = ref(loadCols())
const colDialogVisible = ref(false)
const columnDraft = ref([])

function loadCols() {
  const defaults = ALL_COLS.filter((c) => c.defaultOn).map((c) => c.key)
  try {
    const raw = JSON.parse(localStorage.getItem(COL_STORAGE) || 'null')
    if (!Array.isArray(raw) || !raw.length) return defaults
    const valid = raw.filter((key) => ALL_COLS.some((c) => c.key === key))
    const known = new Set(valid)
    for (const col of ALL_COLS) {
      if ((col.locked || col.defaultOn) && !known.has(col.key)) valid.push(col.key)
    }
    return valid
  } catch {
    return defaults
  }
}

function buildColumnDraft() {
  const hidden = ALL_COLS.map((c) => c.key).filter((k) => !visibleCols.value.includes(k))
  const orderedKeys = [...visibleCols.value, ...hidden]
  return orderedKeys.map((key) => {
    const col = ALL_COLS.find((c) => c.key === key)
    return {
      field_key: key,
      label: col.label,
      visible: visibleCols.value.includes(key),
      list_locked: !!col.locked,
    }
  })
}

function openColSettings() {
  columnDraft.value = buildColumnDraft()
  colDialogVisible.value = true
}

function saveColSettings() {
  visibleCols.value = columnDraft.value
    .filter((c) => c.visible || c.list_locked)
    .map((c) => c.field_key)
  localStorage.setItem(COL_STORAGE, JSON.stringify(visibleCols.value))
  colDialogVisible.value = false
  ElMessage.success('列设置已保存')
}

function colOn(key) {
  return visibleCols.value.includes(key)
}

const createVisible = ref(false)
const creating = ref(false)
const form = reactive({ name: '', slug: '', intro: '' })

const quotaText = computed(() => {
  const mx = quota.value.max
  const used = quota.value.used ?? 0
  return mx == null ? `店铺 ${used} / 不限` : `店铺 ${used} / ${mx}`
})

const createDisabled = computed(() => !!quota.value.at_limit)

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 10)
}
function statusType(s) {
  return { active: 'success', paused: 'warning', draft: 'info', closed: 'info' }[s] || 'info'
}
function tabCount(t) {
  return statusCounts.value[t.countKey] ?? 0
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/stores', {
      params: {
        page: query.page,
        page_size: query.page_size,
        q: query.q || undefined,
        tab: query.tab || undefined,
        status: query.status || undefined,
        product_count_min: query.product_count_min,
        product_count_max: query.product_count_max,
        created_from: query.created_from || undefined,
        created_to: query.created_to || undefined,
        sort: query.sort || undefined,
        include_closed: query.status === 'closed' ? true : undefined,
      },
    })
    items.value = data.items || []
    total.value = data.total || 0
    quota.value = data.quota || { used: 0, max: null, at_limit: false }
    statusCounts.value = data.status_counts || {}
    if (!currentShopId.value && items.value.length) {
      enterShop(items.value[0], { silent: true })
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function enterShop(row, { silent } = {}) {
  setCurrentShopId(row.id)
  if (!silent) ElMessage.success(`已切换当前店：${row.name}`)
}

function goSettings(row) {
  enterShop(row, { silent: true })
  router.push({ path: '/shop/store-settings', query: { shop_id: row.id } })
}

function openCreate() {
  if (createDisabled.value) {
    ElMessage.warning('已达套餐店铺上限，请升级')
    return
  }
  form.name = ''
  form.slug = ''
  form.intro = ''
  createVisible.value = true
}

async function submitCreate() {
  if ((form.name || '').trim().length < 2) {
    ElMessage.warning('请填写店铺名称')
    return
  }
  if ((form.slug || '').trim().length < 2) {
    ElMessage.warning('请填写店铺短码')
    return
  }
  creating.value = true
  try {
    await api.post('/api/v1/shop/stores', {
      name: form.name.trim(),
      slug: form.slug.trim().toLowerCase(),
      intro: form.intro || undefined,
    })
    ElMessage.success('已创建（草稿，须开业后方可对外）')
    createVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function pauseStore(row) {
  try {
    await ElMessageBox.confirm(
      '买家端该店不可访问/下单；进行中订单可继续履约',
      `确认暂停「${row.name}」？`,
      { type: 'warning', confirmButtonText: '确认暂停', cancelButtonText: '取消' }
    )
    await api.post(`/api/v1/shop/stores/${row.id}/pause`)
    ElMessage.success('已暂停')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '暂停失败')
  }
}

async function resumeStore(row) {
  try {
    await ElMessageBox.confirm(
      '买家端可正常访问；商品须仍在售状态',
      `确认恢复「${row.name}」营业？`,
      { type: 'success', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
    )
    await api.post(`/api/v1/shop/stores/${row.id}/resume`)
    ElMessage.success('已恢复营业')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '恢复失败')
  }
}

async function openStore(row) {
  try {
    const { data: ready } = await api.get(`/api/v1/shop/stores/${row.id}/open-readiness`)
    const pre = [
      ready.a19_ready ? 'A19 必填项已齐' : 'A19 必填项未齐',
      `在售商品 ${ready.on_sale_count || 0} 个`,
    ].join(' · ')
    await ElMessageBox.confirm(
      `开业前置：${pre}\n开业影响：买家端可访问/下单；状态由「待开业」变为「营业中」`,
      `确认「${row.name}」开业？`,
      { type: 'info', confirmButtonText: '确认开业', cancelButtonText: '取消' }
    )
    await api.post(`/api/v1/shop/stores/${row.id}/open`)
    ElMessage.success('已开业')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '开业失败')
  }
}

function visibleExportColumns() {
  return ALL_COLS.filter((c) => c.key !== 'ops' && colOn(c.key)).map((c) => c.key)
}

async function exportCsv(mode) {
  exporting.value = true
  try {
    const body = {
      q: query.q || undefined,
      tab: query.tab || undefined,
      status: query.status || undefined,
      product_count_min: query.product_count_min,
      product_count_max: query.product_count_max,
      created_from: query.created_from || undefined,
      created_to: query.created_to || undefined,
      sort: query.sort || undefined,
      include_closed: query.status === 'closed' ? true : undefined,
    }
    if (mode === 'columns') {
      body.columns = visibleExportColumns()
    }
    await submitShopExport(
      '/api/v1/shop/stores/export',
      body,
      '/api/v1/shop/stores/export-tasks',
      'shop-stores.csv',
      total.value,
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}


function toggleSort(key) {
  if (query.sort === key) query.sort = `-${key}`
  else if (query.sort === `-${key}`) query.sort = ''
  else query.sort = key
  load()
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="hd">
      <h3>我的店铺</h3>
      <div class="quota">
        合并权益：{{ quotaText }}（已用含草稿+暂停）·
        <a class="link" href="javascript:;" @click.prevent="router.push('/shop/subscription')">套餐</a>
      </div>
    </div>

    <div class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key || 'all'"
        type="button"
        class="tab"
        :class="{ on: query.tab === t.key }"
        @click="query.tab = t.key; query.page = 1; load()"
      >
        {{ t.label }}
        <span class="cnt">{{ tabCount(t) }}</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="搜索店铺名 / 店铺短码"
          style="width: 220px"
          @change="() => { query.page = 1; load() }"
        />
        <el-select
          v-model="query.status"
          clearable
          placeholder="状态"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="营业" value="active" />
          <el-option label="已暂停" value="paused" />
          <el-option label="已关闭" value="closed" />
        </el-select>
        <el-button :type="advOpen ? 'primary' : 'default'" @click="advOpen = !advOpen">
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
        <el-button @click="openColSettings">列设置</el-button>
        <el-button
          type="primary"
          :disabled="createDisabled"
          :title="createDisabled ? '已达套餐店铺上限，请升级' : ''"
          @click="openCreate"
        >
          + 新建店铺
        </el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <el-input-number
        v-model="query.product_count_min"
        :min="0"
        controls-position="right"
        placeholder="商品数 ≥"
      />
      <el-input-number
        v-model="query.product_count_max"
        :min="0"
        controls-position="right"
        placeholder="商品数 ≤"
      />
      <el-date-picker
        v-model="query.created_from"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="创建起"
      />
      <span class="dash">—</span>
      <el-date-picker
        v-model="query.created_to"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="创建止"
      />
      <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
      <el-button
        @click="
          query.product_count_min = undefined;
          query.product_count_max = undefined;
          query.created_from = '';
          query.created_to = '';
          query.page = 1;
          load()
        "
      >
        重置
      </el-button>
    </div>

    <el-table :data="items" border stripe>
      <template v-for="colKey in visibleCols" :key="colKey">
      <el-table-column v-if="colKey === 'name'" label="店铺名" min-width="160">
        <template #header>
          <span class="sortable" @click="toggleSort('name')">店铺名 ↕</span>
        </template>
        <template #default="{ row }">
          <b>{{ row.name }}</b>
          <el-tag v-if="String(row.id) === currentShopId" size="small" type="primary" style="margin-left: 6px">
            当前
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'slug'" prop="slug" label="店铺短码" min-width="110" />
      <el-table-column v-if="colKey === 'product_count'" label="商品数" width="100" align="right">
        <template #header>
          <span class="sortable" @click="toggleSort('product_count')">商品数 ↕</span>
        </template>
        <template #default="{ row }">{{ row.product_count }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'month_gmv'" label="本月 GMV" width="120" align="right">
        <template #header>
          <span class="sortable" @click="toggleSort('month_gmv')">本月 GMV ↕</span>
        </template>
        <template #default="{ row }">{{ fmtMoney(row.month_gmv_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'created_at'" label="创建时间" width="120">
        <template #header>
          <span class="sortable" @click="toggleSort('created_at')">创建时间 ↕</span>
        </template>
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'status'" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'ops'" label="操作" min-width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="enterShop(row)">进入</el-button>
          <el-button link type="primary" @click="goSettings(row)">
            {{ row.status === 'active' ? '单店设置' : '设置' }}
          </el-button>
          <el-button
            v-if="row.status === 'active'"
            link
            type="warning"
            @click="pauseStore(row)"
          >
            暂停
          </el-button>
          <el-button
            v-if="row.status === 'paused'"
            link
            type="success"
            @click="resumeStore(row)"
          >
            恢复营业
          </el-button>
          <el-button
            v-if="row.status === 'draft'"
            link
            type="primary"
            @click="openStore(row)"
          >
            开业
          </el-button>
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
        @size-change="() => { query.page = 1; load() }"
      />
    </div>

    <el-drawer v-model="createVisible" title="新建店铺" size="420px">
      <el-alert
        :closable="false"
        type="info"
        :title="`配额 ${quotaText}`"
        style="margin-bottom: 12px"
      />
      <el-form label-position="top">
        <el-form-item label="店铺名称" required>
          <el-input v-model="form.name" maxlength="30" show-word-limit placeholder="2–30 字" />
        </el-form-item>
        <el-form-item label="店铺短码" required>
          <el-input v-model="form.slug" maxlength="30" show-word-limit placeholder="小写字母/数字" />
        </el-form-item>
        <el-form-item label="简介（选填）">
          <el-input v-model="form.intro" type="textarea" :rows="3" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="colDialogVisible"
      v-model:columns="columnDraft"
      @save="saveColSettings"
    />
  </div>
</template>

<style scoped>
.page {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
}
.hd {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.hd h3 {
  margin: 0;
  font-size: 16px;
}
.quota {
  font-size: 12px;
  color: #666;
}
.quota .link {
  color: #1677ff;
}
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--el-border-color);
  margin-bottom: 12px;
  flex-wrap: wrap;
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
  margin-bottom: -1px;
}
.tab .cnt {
  margin-left: 4px;
  font-size: 12px;
  color: #94a3b8;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.toolbar .left,
.toolbar .right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.adv {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 12px;
  border: 1px solid #91caff;
  border-radius: 8px;
  background: #f0f7ff;
}
.dash {
  color: #999;
}
.sortable {
  cursor: pointer;
  user-select: none;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
