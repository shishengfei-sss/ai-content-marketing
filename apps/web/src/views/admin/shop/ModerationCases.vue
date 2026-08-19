<script setup>
/**
 * P07 违规稽查。对照 PRD 06-平台端UI.html #p07 · #p07a · #p07b · #p07c
 * 默认列：类型、对象、商家、上报时间、处理人、状态、操作
 * 列设置可选：结案时间
 * 缺口：站内信/短信通知商家仅落库未接通（含导出完成通知）。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'
import { useAuthStore } from '../../../stores/auth'
import { formatDateTime } from '../../../utils/datetime'
import { SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../../utils/shopExport'

const COLUMN_KEY = 'shop-moderation-list-columns'
const ALL_COLUMNS = [
  { key: 'case_type', label: '类型', locked: true, defaultVisible: true },
  { key: 'object_ref', label: '对象', locked: true, defaultVisible: true },
  { key: 'merchant_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'reported_at', label: '上报时间', defaultVisible: true },
  { key: 'assignee_name', label: '处理人', defaultVisible: true },
  { key: 'status', label: '状态', locked: true, defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'closed_at', label: '结案时间', defaultVisible: false },
]

const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref(SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns)
const items = ref([])
const total = ref(0)
const stats = ref({})
const page = ref(1)
const pageSize = ref(20)
const searchQ = ref('')
const viewSel = ref('all')
const advExpanded = ref(false)
const filterType = ref('')
const filterStatus = ref('')
const filterSource = ref('')
const sortBy = ref('reported_at')
const sortDir = ref('desc')
const {
  visibleKeys,
  columnDialogVisible,
  columnDraft,
  openColumnSettings,
  saveColumnSettings,
  isColVisible,
} = useListColumnSettings(ALL_COLUMNS, COLUMN_KEY)

const detail = ref(null)
const detailVisible = ref(false)
const offVisible = ref(false)
const closeVisible = ref(false)
const submitting = ref(false)
const offForm = reactive({ reason_type: '', reason: '' })
const closeForm = reactive({
  resolution: '',
  conclusion: '',
  notify_in_app: false,
  notify_sms: false,
})

const canForceOff = computed(() => auth.hasPlatformShopPermission('platform.shop.product.force_off'))

const STATUS_TAG = {
  pending: 'warning',
  processing: 'primary',
  closed: 'success',
}

const VIEW_OPTIONS = [
  { value: 'all', label: '全部工单' },
  { value: 'open', label: '待处理+处理中' },
  { value: 'pending', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'closed', label: '已结案' },
]

function sortIcon(prop) {
  if (sortBy.value !== prop) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function toggleSort(prop) {
  if (sortBy.value === prop) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = prop
    sortDir.value = 'desc'
  }
  page.value = 1
  load()
}

function downloadBlob(data, filename) {
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function listParams() {
  const p = {
    page: page.value,
    page_size: pageSize.value,
    q: searchQ.value.trim() || undefined,
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
    case_type: filterType.value || undefined,
    source: advExpanded.value ? filterSource.value || undefined : undefined,
  }
  if (filterStatus.value) p.status = filterStatus.value
  else if (viewSel.value && viewSel.value !== 'all') p.view = viewSel.value
  return p
}

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopModerationCases(listParams())
    items.value = data.items || []
    total.value = data.total || 0
    stats.value = data.stats || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  load()
}

function onViewChange() {
  filterStatus.value = ''
  page.value = 1
  load()
}

function onCardClick(key) {
  if (key === 'force_off') return
  filterStatus.value = ''
  if (key === 'pending') viewSel.value = 'pending'
  else if (key === 'processing') viewSel.value = 'processing'
  else if (key === 'closed_month') viewSel.value = 'closed_month'
  page.value = 1
  load()
}

function cardActive(key) {
  if (key === 'pending') return viewSel.value === 'pending'
  if (key === 'processing') return viewSel.value === 'processing'
  if (key === 'closed_month') return viewSel.value === 'closed_month'
  return false
}

async function openDetail(row) {
  try {
    const { data } = await adminApi.getShopModerationCase(row.id)
    detail.value = data
    detailVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '无稽查查看权限')
  }
}

async function ensureDetail(row) {
  if (detail.value && detail.value.id === row.id) return detail.value
  const { data } = await adminApi.getShopModerationCase(row.id)
  detail.value = data
  return data
}

async function openOff(row) {
  if (!canForceOff.value) {
    ElMessage.error('无强制下架权限')
    return
  }
  try {
    await ensureDetail(row)
    offForm.reason_type = ''
    offForm.reason = ''
    offVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  }
}

async function openClose(row) {
  try {
    await ensureDetail(row)
    closeForm.resolution = ''
    closeForm.conclusion = ''
    closeForm.notify_in_app = false
    closeForm.notify_sms = false
    closeVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  }
}

async function submitTake(row) {
  submitting.value = true
  try {
    await adminApi.takeShopModerationCase(row.id)
    ElMessage.success('已接单')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '接单失败')
  } finally {
    submitting.value = false
  }
}

function alarmText(d) {
  if (!d) return '—'
  const st = d.product_status === 'on_sale' ? '当前在售' : d.product_status === 'off_sale' ? '当前已下架' : '当前非在售'
  return `${st}，近 7 日 ${d.recent_7d_order_count || 0} 笔订单`
}

async function submitOff() {
  if (!detail.value) return
  if (!offForm.reason_type) {
    ElMessage.error('请选择下架原因类型')
    return
  }
  if (!offForm.reason.trim()) {
    ElMessage.error('请填写说明')
    return
  }
  submitting.value = true
  try {
    const { data } = await adminApi.forceOffShopModerationCase(detail.value.id, {
      reason_type: offForm.reason_type,
      reason: offForm.reason.trim(),
    })
    detail.value = data
    offVisible.value = false
    ElMessage.success('已下架并更新工单')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '下架失败')
  } finally {
    submitting.value = false
  }
}

async function submitClose() {
  if (!detail.value) return
  if (!closeForm.resolution) {
    ElMessage.error('请选择处理结果')
    return
  }
  if ((closeForm.conclusion || '').trim().length < 4) {
    ElMessage.error('请填写结案说明')
    return
  }
  submitting.value = true
  try {
    const { data } = await adminApi.closeShopModerationCase(detail.value.id, {
      resolution: closeForm.resolution,
      conclusion: closeForm.conclusion.trim(),
      notify_in_app: closeForm.notify_in_app,
      notify_sms: closeForm.notify_sms,
    })
    detail.value = data
    closeVisible.value = false
    ElMessage.success('已结案')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '结案失败')
  } finally {
    submitting.value = false
  }
}

async function previewAttachment(att) {
  if (!detail.value?.id || !att?.file_id) {
    ElMessage.warning('无可预览文件')
    return
  }
  try {
    const { data } = await adminApi.downloadShopModerationAttachment(detail.value.id, att.file_id)
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    ElMessage.error(e.message || '附件预览失败')
  }
}

function attachmentKindLabel(att) {
  if (att?.kind_label) return att.kind_label
  if (att?.kind === 'chat_screenshot') return '聊天截图'
  if (att?.kind === 'order_snapshot') return '订单快照'
  return '附件'
}

async function exportList(mode) {
  exporting.value = true
  try {
    const body = { ...listParams() }
    delete body.page
    delete body.page_size
    if (mode === 'columns') {
      body.columns = visibleKeys.value.filter((k) => k !== 'ops')
    }
    const { data } = await adminApi.createShopModerationExport(body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns : SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns
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
    const res = await adminApi.getShopModerationExportFile(exportTask.value.id)
    downloadBlob(res.data, exportTask.value.file_name || 'shop-moderation-cases.csv')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function showForceOff(row) {
  return row.status === 'pending' && row.is_product_case && canForceOff.value
}

function showTake(row) {
  return row.status === 'pending' && !row.is_product_case
}

function showClose(row) {
  return row.status === 'processing'
}

onMounted(() => {
  const st = String(route.query.status || '')
  const view = String(route.query.view || '')
  if (view === 'open' || view === 'pending' || view === 'processing' || view === 'closed' || view === 'closed_month') {
    viewSel.value = view
  } else if (st === 'pending' || st === 'processing' || st === 'closed') {
    viewSel.value = st
  }
  load()
})

watch(pageSize, () => {
  page.value = 1
  load()
})
</script>

<template>
  <div class="page-card" data-testid="shop-moderation-page">
    <el-row :gutter="16" class="dash-stats">
      <el-col :span="6">
        <div class="stat-card" :class="{ 'stat-card--on': cardActive('pending') }" @click="onCardClick('pending')">
          <div class="stat-card__label">待处理</div>
          <div class="stat-card__value stat-card__value--warn">{{ stats.pending_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card" :class="{ 'stat-card--on': cardActive('processing') }" @click="onCardClick('processing')">
          <div class="stat-card__label">处理中</div>
          <div class="stat-card__value stat-card__value--primary">{{ stats.processing_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card" :class="{ 'stat-card--on': cardActive('closed_month') }" @click="onCardClick('closed_month')">
          <div class="stat-card__label">本月已结案</div>
          <div class="stat-card__value">{{ stats.closed_month_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card--readonly">
          <div class="stat-card__label">本月强制下架</div>
          <div class="stat-card__value">{{ stats.force_off_month_count || 0 }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="toolbar">
      <el-select v-model="viewSel" style="width: 160px" @change="onViewChange">
        <el-option v-for="o in VIEW_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        <el-option label="本月已结案" value="closed_month" />
      </el-select>
      <el-input
        v-model="searchQ"
        clearable
        placeholder="搜索对象 / 商家"
        style="width: 220px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-select v-model="filterType" clearable placeholder="类型" style="width: 140px" @change="onSearch">
        <el-option label="敏感词命中" value="sensitive_word" />
        <el-option label="商品违规" value="product_violation" />
        <el-option label="买家投诉" value="buyer_complaint" />
        <el-option label="用户举报" value="user_report" />
        <el-option label="外部审核" value="external_audit" />
        <el-option label="运营巡查" value="manual" />
      </el-select>
      <el-select v-model="filterStatus" clearable placeholder="状态" style="width: 120px" @change="onSearch">
        <el-option label="待处理" value="pending" />
        <el-option label="处理中" value="processing" />
        <el-option label="已结案" value="closed" />
      </el-select>
      <el-button :type="advExpanded ? 'primary' : 'default'" plain @click="advExpanded = !advExpanded">
        高级筛选
      </el-button>
      <div class="toolbar-right">
        <el-dropdown trigger="click" @command="exportList">
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
    <div v-if="advExpanded" class="adv-row">
      <el-select v-model="filterSource" clearable placeholder="建单来源" style="width: 160px" @change="onSearch">
        <el-option label="机审" value="f6_auto" />
        <el-option label="公域拒审" value="f7_callback" />
        <el-option label="服务记录" value="service_log" />
        <el-option label="买家投诉" value="buyer_report" />
        <el-option label="运营手工" value="ops_manual" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="items" border stripe size="small">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column v-if="colKey === 'case_type'" label="类型" width="120">
        <template #default="{ row }">{{ row.case_type_label }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'object_ref'" prop="object_ref" label="对象" min-width="160" />
      <el-table-column v-if="colKey === 'merchant_name'" prop="merchant_name" label="商家" min-width="120" />
      <el-table-column v-if="colKey === 'reported_at'" min-width="160">
        <template #header>
          <span class="th-sort" @click="toggleSort('reported_at')">上报时间 {{ sortIcon('reported_at') }}</span>
        </template>
        <template #default="{ row }">{{ formatDateTime(row.reported_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'assignee_name'" label="处理人" width="110">
        <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'status'" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'closed_at'" label="结案时间" width="160">
        <template #default="{ row }">{{ formatDateTime(row.closed_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'ops'" label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="showForceOff(row)" link type="primary" @click="openOff(row)">下架</el-button>
          <el-button v-if="showTake(row)" link type="primary" :disabled="submitting" @click="submitTake(row)">接单</el-button>
          <el-button v-if="showClose(row)" link type="primary" @click="openClose(row)">结案</el-button>
          <el-button link @click="openDetail(row)">查看</el-button>
        </template>
      </el-table-column>
      </template>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-drawer v-model="detailVisible" size="560px" :title="detail ? `工单 ${detail.case_no}` : '工单详情'">
      <template v-if="detail">
        <div class="detail-hd">
          <el-tag size="small" :type="STATUS_TAG[detail.status] || 'info'">{{ detail.status_label }}</el-tag>
        </div>
        <div class="detail-ops">
          <el-button v-if="showForceOff(detail)" type="warning" size="small" @click="openOff(detail)">下架</el-button>
          <el-button v-if="showTake(detail)" type="primary" size="small" :disabled="submitting" @click="submitTake(detail)">接单</el-button>
          <el-button v-if="showClose(detail)" type="primary" size="small" @click="openClose(detail)">结案</el-button>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="类型（只读）">{{ detail.case_type_label }}</el-descriptions-item>
          <el-descriptions-item label="对象（只读）">{{ detail.object_ref }}</el-descriptions-item>
          <el-descriptions-item label="商家（只读）">{{ detail.merchant_name }}</el-descriptions-item>
          <el-descriptions-item label="时间线（只读）">
            <div v-if="(detail.timeline || []).length">
              <p v-for="(ev, i) in detail.timeline" :key="i" class="tl">
                {{ formatDateTime(ev.at) }} {{ ev.label }}
              </p>
            </div>
            <span v-else>—</span>
          </el-descriptions-item>
          <el-descriptions-item label="处理结果（只读）">
            {{ detail.resolution_label || detail.conclusion || '—' }}
            <span v-if="detail.resolution_label && detail.conclusion"> · {{ detail.conclusion }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="附件（只读）">
            <div v-if="(detail.attachments || []).length" class="att-list">
              <div v-for="(att, i) in detail.attachments" :key="att.file_id || i" class="att-row">
                {{ attachmentKindLabel(att) }} · {{ att.file_name || '未命名' }}
                <el-button v-if="att.file_id" link type="primary" @click="previewAttachment(att)">预览</el-button>
              </div>
            </div>
            <span v-else>无</span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-drawer>

    <el-dialog v-model="offVisible" :title="`下架商品「${detail?.object_ref || ''}」？`" width="520px">
      <el-form label-width="140px">
        <el-form-item label="工单（只读）">
          {{ detail?.case_no }} · {{ detail?.case_type_label }} · {{ detail?.merchant_name }}
        </el-form-item>
        <el-form-item label="将执行（只读）">
          {{ detail?.will_execute || '写强制下架 + listing blocked；暂停公域映射；已购权益保留' }}
        </el-form-item>
        <el-form-item label="告警（只读）">{{ alarmText(detail) }}</el-form-item>
        <el-form-item label="下架原因类型" required>
          <el-select v-model="offForm.reason_type" placeholder="请选择" style="width: 100%">
            <el-option label="虚假宣传" value="false_ad" />
            <el-option label="违禁内容" value="prohibited" />
            <el-option label="资质缺失" value="missing_qual" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input v-model="offForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="offVisible = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="submitOff">确认下架并更新工单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="closeVisible" :title="`结案「${detail?.case_type_label || ''} · ${detail?.object_ref || ''}」`" width="520px">
      <el-form label-width="140px">
        <el-form-item label="处理结果" required>
          <el-select v-model="closeForm.resolution" placeholder="请选择" style="width: 100%">
            <el-option label="已下架商品" value="off_sale" />
            <el-option label="已警告商家" value="warned" />
            <el-option label="误报无责" value="false_positive" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="结案说明" required>
          <el-input v-model="closeForm.conclusion" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="是否通知商家">
          <el-checkbox v-model="closeForm.notify_in_app">站内信</el-checkbox>
          <el-checkbox v-model="closeForm.notify_sms">短信</el-checkbox>
          <p class="gap-hint">本批勾选仅落库，站内信/短信通道未接通。</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitClose">确认结案</el-button>
      </template>
    </el-dialog>

    <CrmColumnSettingsDialog
      v-model:visible="columnDialogVisible"
      v-model:columns="columnDraft"
      @save="saveColumnSettings"
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
  </div>
</template>

<style scoped>
.dash-stats { margin-bottom: 16px; }
.stat-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  background: var(--el-bg-color);
}
.stat-card--readonly { cursor: default; }
.stat-card--on { border-color: var(--el-color-primary); }
.stat-card__label { font-size: 13px; color: var(--el-text-color-secondary); }
.stat-card__value { font-size: 22px; font-weight: 600; margin-top: 4px; }
.stat-card__value--warn { color: var(--el-color-warning); }
.stat-card__value--primary { color: var(--el-color-primary); }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.toolbar-right { margin-left: auto; display: flex; gap: 8px; }
.adv-row { margin: -4px 0 12px; }
.pager { margin-top: 12px; }
.th-sort { cursor: pointer; user-select: none; }
.detail-hd { margin-bottom: 8px; }
.detail-ops { display: flex; gap: 8px; margin-bottom: 12px; }
.tl { margin: 0 0 4px; font-size: 13px; }
.column-item { margin-bottom: 8px; }
.gap-hint { margin: 4px 0 0; font-size: 12px; color: var(--el-text-color-secondary); }
.att-list { display: flex; flex-direction: column; gap: 6px; }
.att-row { font-size: 13px; }
</style>
