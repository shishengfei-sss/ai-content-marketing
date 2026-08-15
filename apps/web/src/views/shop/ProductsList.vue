<script setup>
/**
 * A02 商品列表。对照 PRD 01-管理端UI.html #a02 · #a02a · #a02b · #a02c · 04#select-common
 * §0b 列完备；批量提审/下架；删除闸；A02-A/B/C 确认弹窗。
 * 缺口：导出完成站内信本批不接。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'

const router = useRouter()
const route = useRoute()
const { currentId } = useCurrentShop()
const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref('当前筛选')
const batchBusy = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const advOpen = ref(false)
const colDialog = ref(false)
const selectedRows = ref([])

const dlg = reactive({
  visible: false,
  kind: '', // submit | off | delete | delete_blocked
  row: null,
  rows: [],
  precheck: null,
  busy: false,
})

const STATUS_LABEL = {
  draft: '草稿',
  pending_review: '审核中',
  approved: '已通过',
  on_sale: '在售',
  rejected: '已驳回',
  off_sale: '已下架',
}
const TYPE_LABEL = { course: '课程', digital: '资料', service: '服务' }
const REF_LABEL = {
  column: '专栏',
  digital_package: '资料包',
  service_offer: '服务',
}
const MOUNT_TAG = {
  mapped: 'success',
  none: 'info',
  rejected: 'danger',
}

const STATUS_TABS = [
  { key: '', label: '全部商品' },
  { key: 'draft', label: '草稿' },
  { key: 'pending_review', label: '审核中' },
  { key: 'on_sale', label: '在售' },
  { key: 'off_sale', label: '已下架' },
]

const COL_STORAGE = 'shop.a02.columns'
const ALL_COLS = [
  { key: 'cover', label: '封面', locked: true, defaultOn: true },
  { key: 'name', label: '名称', locked: true, defaultOn: true },
  { key: 'type', label: '类型', locked: true, defaultOn: true },
  { key: 'price', label: '售价', locked: true, defaultOn: true },
  { key: 'sales_count', label: '销量', locked: true, defaultOn: true },
  { key: 'status', label: '状态', locked: true, defaultOn: true },
  { key: 'updated_at', label: '更新时间', locked: true, defaultOn: true },
  { key: 'ref', label: '关联', locked: true, defaultOn: true },
  { key: 'channel_mount', label: '公域', locked: true, defaultOn: true },
  { key: 'created_at', label: '创建时间', locked: false, defaultOn: false },
  { key: 'created_by', label: '创建人', locked: false, defaultOn: false },
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
const colDraft = reactive({ ...colVisible })

const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  type: '',
  q: '',
  channel_mount: '',
  price_min: undefined,
  price_max: undefined,
  updated_from: '',
  updated_to: '',
})

function listParams() {
  const priceMin =
    query.price_min === undefined || query.price_min === null || query.price_min === ''
      ? undefined
      : Math.round(Number(query.price_min) * 100)
  const priceMax =
    query.price_max === undefined || query.price_max === null || query.price_max === ''
      ? undefined
      : Math.round(Number(query.price_max) * 100)
  return {
    page: query.page,
    page_size: query.page_size,
    shop_id: currentId.value || undefined,
    status: query.status || undefined,
    type: query.type || undefined,
    q: query.q || undefined,
    channel_mount: query.channel_mount || undefined,
    price_min_cents: Number.isFinite(priceMin) ? priceMin : undefined,
    price_max_cents: Number.isFinite(priceMax) ? priceMax : undefined,
    updated_from: query.updated_from || undefined,
    updated_to: query.updated_to || undefined,
  }
}

function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}

function setTab(key) {
  query.status = key
  query.page = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/products', { params: listParams() })
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
    selectedRows.value = []
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function resetAdv() {
  query.channel_mount = ''
  query.price_min = undefined
  query.price_max = undefined
  query.updated_from = ''
  query.updated_to = ''
  query.page = 1
  load()
}

function visibleExportColumns() {
  return ALL_COLS.filter((c) => c.key !== 'ops' && c.key !== 'cover' && colVisible[c.key]).map((c) => c.key)
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
    const { data } = await api.post('/api/v1/shop/products/export', body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? '列配置' : '当前筛选'
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
    const res = await api.get(`/api/v1/shop/products/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-products.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function openColSettings() {
  Object.assign(colDraft, colVisible)
  colDialog.value = true
}

function saveColSettings() {
  Object.assign(colVisible, colDraft)
  localStorage.setItem(COL_STORAGE, JSON.stringify({ ...colVisible }))
  colDialog.value = false
  ElMessage.success('列设置已保存')
}

function goNew() {
  router.push({ name: 'ShopProductNew' })
}
function goView(row) {
  router.push({ name: 'ShopProductEdit', params: { id: row.id }, query: { mode: 'view' } })
}
function goEdit(row) {
  router.push({ name: 'ShopProductEdit', params: { id: row.id }, query: { mode: 'edit' } })
}
function goMap(row) {
  router.push({ name: 'ShopChannelMappings', query: { product_id: row.id } })
}

function onSelectionChange(rows) {
  selectedRows.value = rows.slice(0, 50)
}

function openSubmit(row) {
  dlg.kind = 'submit'
  dlg.row = row
  dlg.rows = [row]
  dlg.precheck = null
  dlg.visible = true
}

function openOffSale(row) {
  dlg.kind = 'off'
  dlg.row = row
  dlg.rows = [row]
  dlg.precheck = null
  dlg.visible = true
}

async function openDelete(row) {
  dlg.row = row
  dlg.rows = [row]
  try {
    const { data } = await api.get(`/api/v1/shop/products/${row.id}/delete-precheck`)
    dlg.precheck = data
    dlg.kind = data.can_delete ? 'delete' : 'delete_blocked'
    dlg.visible = true
  } catch (e) {
    ElMessage.error(e.message || '无法校验删除条件')
  }
}

function openBatchSubmit() {
  if (!selectedRows.value.length) {
    ElMessage.warning('未选择商品')
    return
  }
  const eligible = selectedRows.value.filter((r) =>
    ['draft', 'rejected'].includes(r.status)
  )
  if (!eligible.length) {
    ElMessage.warning(`部分行状态不符（列出 ${selectedRows.value.length} 条）`)
    return
  }
  if (eligible.length < selectedRows.value.length) {
    ElMessage.warning(
      `部分行状态不符（跳过 ${selectedRows.value.length - eligible.length} 条）`
    )
  }
  dlg.kind = 'submit'
  dlg.row = null
  dlg.rows = eligible.slice(0, 50)
  dlg.precheck = null
  dlg.visible = true
}

function openBatchOff() {
  if (!selectedRows.value.length) {
    ElMessage.warning('未选择商品')
    return
  }
  const eligible = selectedRows.value.filter((r) => r.status === 'on_sale')
  if (!eligible.length) {
    ElMessage.warning(`部分行状态不符（列出 ${selectedRows.value.length} 条）`)
    return
  }
  if (eligible.length < selectedRows.value.length) {
    ElMessage.warning(
      `部分行状态不符（跳过 ${selectedRows.value.length - eligible.length} 条）`
    )
  }
  dlg.kind = 'off'
  dlg.row = null
  dlg.rows = eligible.slice(0, 50)
  dlg.precheck = null
  dlg.visible = true
}

async function confirmDlg() {
  dlg.busy = true
  try {
    if (dlg.kind === 'submit') {
      if (dlg.rows.length === 1) {
        await api.post(`/api/v1/shop/products/${dlg.rows[0].id}/submit-review`, {})
        ElMessage.success('已提交审核')
      } else {
        batchBusy.value = true
        const { data } = await api.post('/api/v1/shop/products/batch-submit-review', {
          product_ids: dlg.rows.map((r) => r.id),
        })
        ElMessage.success(`批量提审：成功 ${data.ok_count} · 失败 ${data.fail_count}`)
      }
    } else if (dlg.kind === 'off') {
      if (dlg.rows.length === 1) {
        await api.post(`/api/v1/shop/products/${dlg.rows[0].id}/off-sale`)
        ElMessage.success('已下架')
      } else {
        batchBusy.value = true
        const { data } = await api.post('/api/v1/shop/products/batch-off-sale', {
          product_ids: dlg.rows.map((r) => r.id),
        })
        ElMessage.success(`批量下架：成功 ${data.ok_count} · 失败 ${data.fail_count}`)
      }
    } else if (dlg.kind === 'delete') {
      await api.delete(`/api/v1/shop/products/${dlg.row.id}`)
      ElMessage.success('已删除')
    }
    dlg.visible = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    dlg.busy = false
    batchBusy.value = false
  }
}

async function withdraw(row) {
  try {
    dlg.kind = 'withdraw'
    // 撤回用简洁确认
    const { ElMessageBox } = await import('element-plus')
    await ElMessageBox.confirm('确认撤回？撤回后可再编辑并提交审核。', '撤回', { type: 'warning' })
    await api.post(`/api/v1/shop/products/${row.id}/withdraw`)
    ElMessage.success('已撤回')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '撤回失败')
  }
}

async function publish(row) {
  try {
    await api.post(`/api/v1/shop/products/${row.id}/publish`)
    ElMessage.success('已上架')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '上架失败')
  }
}

function contentLabel(row) {
  if (!row.ref_type) return '未关联'
  return REF_LABEL[row.ref_type] || row.ref_type
}

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}

function coverSrc(url) {
  if (!url) return ''
  if (url.startsWith('http') || url.startsWith('/api/')) return url
  return url
}

function mountStatusLabel(st) {
  return (
    { mapped: '已挂载', pending: '审核中', paused: '暂停同步', syncing: '同步中', blocked: '已阻断' }[
      st
    ] || st
  )
}

onMounted(() => {
  if (route.query.status) query.status = String(route.query.status)
  load()
})

watch(currentId, () => {
  query.page = 1
  load()
})
</script>

<template>
  <div v-loading="loading">
    <div class="tabs">
      <button
        v-for="t in STATUS_TABS"
        :key="t.key || 'all'"
        type="button"
        class="tab"
        :class="{ on: query.status === t.key }"
        @click="setTab(t.key)"
      >
        {{ t.label }}
        <span v-if="t.key" class="cnt">{{ tabCount(t.key) }}</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="搜索名称"
          style="width: 200px"
          @change="() => { query.page = 1; load() }"
        />
        <el-select
          v-model="query.type"
          clearable
          placeholder="类型"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="课程" value="course" />
          <el-option label="资料" value="digital" />
          <el-option label="服务" value="service" />
        </el-select>
        <el-select
          v-model="query.status"
          clearable
          placeholder="状态"
          style="width: 140px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="审核中" value="pending_review" />
          <el-option label="已通过" value="approved" />
          <el-option label="在售" value="on_sale" />
          <el-option label="已驳回" value="rejected" />
          <el-option label="已下架" value="off_sale" />
        </el-select>
        <el-button :type="advOpen ? 'primary' : 'default'" plain @click="advOpen = !advOpen">
          高级筛选
        </el-button>
      </div>
      <div class="right">
        <el-button :disabled="!selectedRows.length" :loading="batchBusy" @click="openBatchSubmit">
          批量提交审核
        </el-button>
        <el-button :disabled="!selectedRows.length" :loading="batchBusy" @click="openBatchOff">
          批量下架
        </el-button>
        <el-dropdown trigger="click" @command="exportCsv">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">当前筛选</el-dropdown-item>
              <el-dropdown-item command="columns">列配置</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColSettings">列设置</el-button>
        <el-button type="primary" @click="goNew">+ 新建商品</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-select v-model="query.channel_mount" clearable placeholder="公域挂载" style="width: 140px">
          <el-option label="已挂载" value="mapped" />
          <el-option label="未挂载" value="none" />
          <el-option label="挂载被拒" value="rejected" />
        </el-select>
        <el-input-number
          v-model="query.price_min"
          :min="0"
          :precision="2"
          :controls="false"
          placeholder="售价 ≥"
          style="width: 110px"
        />
        <el-input-number
          v-model="query.price_max"
          :min="0"
          :precision="2"
          :controls="false"
          placeholder="售价 ≤"
          style="width: 110px"
        />
        <el-date-picker
          v-model="query.updated_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="更新起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.updated_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="更新止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 覆盖草稿/审核中/在售/已下架；公域/售价/时间在高级筛选</span>
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
      <el-table-column type="selection" width="42" :selectable="() => true" />
      <el-table-column v-if="colVisible.cover" label="封面" width="64">
        <template #default="{ row }">
          <div class="cover">
            <img v-if="row.cover_url" :src="coverSrc(row.cover_url)" alt="" />
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.name" prop="name" label="名称" min-width="160" />
      <el-table-column v-if="colVisible.type" label="类型" width="80">
        <template #default="{ row }">{{ TYPE_LABEL[row.type] || row.type }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.price" label="售价" width="100">
        <template #default="{ row }">{{ fmtMoney(row.price_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.sales_count" label="销量" width="80" prop="sales_count" />
      <el-table-column v-if="colVisible.status" label="状态" width="90">
        <template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.updated_at" label="更新时间" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.ref" label="关联" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.ref_id ? 'success' : 'danger'">{{ contentLabel(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.channel_mount" label="公域" width="100">
        <template #default="{ row }">
          <template v-if="!row.channel_mount">—</template>
          <el-tag
            v-else
            size="small"
            :type="MOUNT_TAG[row.channel_mount] || 'info'"
          >
            {{ row.channel_mount_label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.created_at" label="创建时间" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.created_by" label="创建人" width="100">
        <template #default="{ row }">{{ row.created_by_name || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.ops" label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="['pending_review', 'approved', 'on_sale'].includes(row.status)"
            link
            type="primary"
            @click="goView(row)"
          >
            查看
          </el-button>
          <el-button
            v-if="['draft', 'rejected', 'off_sale'].includes(row.status)"
            link
            type="primary"
            @click="goEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="row.status === 'draft' || row.status === 'rejected'"
            link
            type="primary"
            @click="openSubmit(row)"
          >
            提交审核
          </el-button>
          <el-button
            v-if="row.status === 'pending_review' || row.status === 'approved'"
            link
            type="warning"
            @click="withdraw(row)"
          >
            撤回
          </el-button>
          <el-button
            v-if="row.status === 'approved' || row.status === 'off_sale'"
            link
            type="success"
            @click="publish(row)"
          >
            上架
          </el-button>
          <el-button v-if="row.status === 'on_sale'" link type="warning" @click="openOffSale(row)">
            下架
          </el-button>
          <el-button v-if="row.status === 'on_sale'" link type="primary" @click="goMap(row)">
            公域映射
          </el-button>
          <el-button
            v-if="row.status === 'draft' || row.status === 'off_sale'"
            link
            type="danger"
            @click="openDelete(row)"
          >
            删除
          </el-button>
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
      @size-change="() => { query.page = 1; load() }"
    />

    <el-dialog v-model="colDialog" title="列设置" width="360px">
      <div v-for="c in ALL_COLS" :key="c.key" class="col-row">
        <el-checkbox v-model="colDraft[c.key]" :disabled="c.locked">{{ c.label }}</el-checkbox>
        <span v-if="c.locked" class="locked">锁定</span>
      </div>
      <template #footer>
        <el-button @click="colDialog = false">取消</el-button>
        <el-button type="primary" @click="saveColSettings">保存</el-button>
      </template>
    </el-dialog>

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

    <!-- A02-A 提交审核 -->
    <el-dialog
      v-model="dlg.visible"
      :title="
        dlg.kind === 'submit'
          ? `确认提交「${dlg.rows.length === 1 ? dlg.rows[0].name : dlg.rows.length + ' 个商品'}」审核？`
          : dlg.kind === 'off'
            ? `确认下架「${dlg.rows.length === 1 ? dlg.rows[0].name : dlg.rows.length + ' 个商品'}」？`
            : dlg.kind === 'delete'
              ? `确认删除「${dlg.row?.name}」？`
              : `无法删除「${dlg.row?.name}」`
      "
      width="520px"
    >
      <template v-if="dlg.kind === 'submit'">
        <div class="dlg-field">
          <div class="dlg-lab">提交说明（只读）</div>
          <div class="dlg-val">
            提交后将进入平台人审队列；将占用提审额度（共 {{ dlg.rows.length }} 次）。
          </div>
        </div>
      </template>
      <template v-else-if="dlg.kind === 'off'">
        <div class="dlg-field">
          <div class="dlg-lab">买家端（只读）</div>
          <div class="dlg-val warn">
            小程序停止新购；<b>已购用户不受影响</b>，可继续学习/使用
          </div>
        </div>
        <div class="dlg-field">
          <div class="dlg-lab">公域渠道（只读）</div>
          <div class="dlg-val warn">
            已挂载的映射将<b>自动暂停同步</b>，不再接收该渠道新订单；重新上架后须在公域对接手动恢复。
          </div>
        </div>
      </template>
      <template v-else-if="dlg.kind === 'delete'">
        <div class="dlg-field">
          <div class="dlg-lab">删除后（只读）</div>
          <div class="dlg-val danger">商品从列表移除，<b>不可恢复</b></div>
        </div>
        <div class="dlg-field">
          <div class="dlg-lab">不影响（只读）</div>
          <div class="dlg-val danger">已完成订单、已购用户权益与学习记录</div>
        </div>
        <div class="dlg-field">
          <div class="dlg-lab">删除前须满足（只读）</div>
          <div class="dlg-val danger">
            · 无未完成订单 — 当前：<b class="ok">无</b><br />
            · 无公域映射 — 当前：<b class="ok">无</b>
          </div>
        </div>
      </template>
      <template v-else-if="dlg.kind === 'delete_blocked'">
        <div class="dlg-field">
          <div class="dlg-lab">原因（只读）</div>
          <div class="dlg-val danger">
            <template v-if="dlg.precheck?.blockers?.includes('channel_mappings')">
              该商品仍有公域映射，请先前往公域对接解除：
              <ul>
                <li v-for="m in dlg.precheck.mappings || []" :key="m.id">
                  · <b>{{ m.channel_label }}</b> — {{ mountStatusLabel(m.status) }}（{{
                    m.channel_product_id
                  }}）
                </li>
              </ul>
            </template>
            <template v-else-if="dlg.precheck?.blockers?.includes('open_orders')">
              存在未完成订单（{{ dlg.precheck.open_order_count }}），不可删除
            </template>
            <template v-else>当前状态不可删除</template>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="dlg.visible = false">
          {{ dlg.kind === 'delete_blocked' ? '关闭' : '取消' }}
        </el-button>
        <el-button
          v-if="dlg.kind === 'delete_blocked' && dlg.precheck?.blockers?.includes('channel_mappings')"
          type="primary"
          @click="
            () => {
              dlg.visible = false
              goMap(dlg.row)
            }
          "
        >
          去公域对接
        </el-button>
        <el-button
          v-if="dlg.kind === 'submit'"
          type="primary"
          :loading="dlg.busy"
          @click="confirmDlg"
        >
          确认提交
        </el-button>
        <el-button
          v-if="dlg.kind === 'off'"
          type="warning"
          :loading="dlg.busy"
          @click="confirmDlg"
        >
          确认下架
        </el-button>
        <el-button
          v-if="dlg.kind === 'delete'"
          type="danger"
          :loading="dlg.busy"
          @click="confirmDlg"
        >
          确认删除
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color);
  flex-wrap: wrap;
}
.tab {
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  font-size: 13px;
}
.tab.on {
  color: var(--el-color-primary);
  font-weight: 700;
  border-bottom: 2px solid var(--el-color-primary);
  margin-bottom: -1px;
}
.cnt {
  margin-left: 4px;
  font-size: 11px;
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
.cover {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  background: #e2e8f0;
  overflow: hidden;
}
.cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.col-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.locked {
  font-size: 11px;
  color: #999;
}
.dlg-field {
  margin-bottom: 12px;
}
.dlg-lab {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}
.dlg-val {
  font-size: 13px;
  line-height: 1.6;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fafafa;
}
.dlg-val.warn {
  background: #fffbe6;
}
.dlg-val.danger {
  background: #fff2f0;
}
.dlg-val .ok {
  color: #389e0d;
}
.dlg-val ul {
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}
</style>
