<script setup>
/**
 * 开票申请处理。对照 PRD 01-管理端UI.html #a13 / #a13c / #a13a / #a13b / #a13-select-spec
 * 默认列：订单·抬头·类型·税号·邮箱·金额·申请时间·状态·操作
 * 列设置可选：处理人、开具时间、发票号码
 * 缺口：站内信/短信通知买家本批不接（导出在页内下载，不发站内信）。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'
import ShopMaterialUpload from '../../components/shop/ShopMaterialUpload.vue'

const route = useRoute()
const { currentId } = useCurrentShop()

const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  title_type: '',
  created_from: '',
  created_to: '',
})
const advOpen = ref(false)
const issueDrawer = ref(false)
const issueRow = ref(null)
const invoiceNo = ref('')
const invoiceUrl = ref('')
const issueRemark = ref('')
const pdfFileId = ref('')
const pdfFileName = ref('')
const detailDrawer = ref(false)
const detail = ref(null)
const rejectDialog = ref(false)
const rejectRow = ref(null)
const rejectCode = ref('')
const rejectNote = ref('')

const COL_STORAGE = 'shop.a13.columns'
const ALL_COLS = [
  { key: 'order_no', label: '订单', locked: true, defaultOn: true },
  { key: 'title', label: '抬头', locked: true, defaultOn: true },
  { key: 'title_type', label: '类型', locked: true, defaultOn: true },
  { key: 'tax_no', label: '税号', locked: true, defaultOn: true },
  { key: 'email', label: '邮箱', locked: true, defaultOn: true },
  { key: 'amount', label: '金额', locked: true, defaultOn: true },
  { key: 'created_at', label: '申请时间', locked: true, defaultOn: true },
  { key: 'status', label: '状态', locked: true, defaultOn: true },
  { key: 'operator_name', label: '处理人', locked: false, defaultOn: false },
  { key: 'issued_at', label: '开具时间', locked: false, defaultOn: false },
  { key: 'invoice_no', label: '发票号码', locked: false, defaultOn: false },
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

const STATUS_LABEL = { submitted: '待处理', pending: '待处理', issued: '已开票', rejected: '已驳回' }
const TABS = [
  { key: '', label: '全部申请' },
  { key: 'submitted', label: '待处理' },
  { key: 'issued', label: '已开票' },
  { key: 'rejected', label: '已驳回' },
]
const REJECT_REASONS = [
  { value: 'mismatch', label: '税号与抬头不匹配' },
  { value: 'amount', label: '金额有误' },
  { value: 'other', label: '其他' },
]

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
function titleTypeText(row) {
  return row?.title_type === 'company' ? '企业' : '个人'
}
function titleWithType(row) {
  if (!row) return '—'
  return `${row.title || '—'} · ${titleTypeText(row)}`
}

function listParams(extra = {}) {
  return {
    status: query.status || undefined,
    q: query.q || undefined,
    title_type: query.title_type || undefined,
    shop_id: currentId.value || undefined,
    created_from: query.created_from || undefined,
    created_to: query.created_to || undefined,
    ...extra,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/invoices', {
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
  query.status = key
  query.page = 1
  load()
}

function resetAdv() {
  query.created_from = ''
  query.created_to = ''
  query.page = 1
  load()
}

function openIssue(row) {
  issueRow.value = row
  invoiceNo.value = ''
  invoiceUrl.value = ''
  issueRemark.value = ''
  pdfFileId.value = ''
  pdfFileName.value = ''
  issueDrawer.value = true
}

async function uploadInvoicePdf(_docType, file) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post('/api/v1/shop/content/files', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  invoiceUrl.value = data.file_url
  return { file_id: data.file_id, file_name: data.file_name }
}

function onPdfUploaded(payload) {
  pdfFileId.value = payload.file_id || ''
  pdfFileName.value = payload.file_name || ''
}

function onPdfCleared() {
  pdfFileId.value = ''
  pdfFileName.value = ''
  invoiceUrl.value = ''
}

async function confirmIssue() {
  if (!invoiceNo.value.trim()) {
    ElMessage.warning('请填写发票号码')
    return
  }
  try {
    await api.post(`/api/v1/shop/invoices/${issueRow.value.id}/issue`, {
      invoice_no: invoiceNo.value.trim(),
      invoice_url: invoiceUrl.value || undefined,
      remark: issueRemark.value.trim() || undefined,
    })
    ElMessage.success('已开票')
    issueDrawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '开具失败')
  }
}

function openReject(row) {
  rejectRow.value = row
  rejectCode.value = ''
  rejectNote.value = ''
  rejectDialog.value = true
}

async function confirmReject() {
  const picked = REJECT_REASONS.find((r) => r.value === rejectCode.value)
  if (!picked) {
    ElMessage.warning('请选择驳回原因')
    return
  }
  const note = rejectNote.value.trim()
  if (note.length < 4) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  const reason = picked.value === 'other' ? note : `${picked.label}：${note}`
  try {
    await api.post(`/api/v1/shop/invoices/${rejectRow.value.id}/reject`, { reason })
    ElMessage.success('已驳回')
    rejectDialog.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '驳回失败')
  }
}

async function openDetail(row) {
  try {
    const { data } = await api.get(`/api/v1/shop/invoices/${row.id}`)
    detail.value = data
    detailDrawer.value = true
  } catch (e) {
    ElMessage.error(e.message || '无查看权限')
  }
}

async function exportCsv() {
  exporting.value = true
  try {
    const { data } = await api.post('/api/v1/shop/invoices/export', listParams())
    exportTask.value = data
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
    const res = await api.get(`/api/v1/shop/invoices/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'invoices.csv'
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
function saveCols() {
  Object.assign(colVisible, colDraft)
  localStorage.setItem(COL_STORAGE, JSON.stringify({ ...colVisible }))
  colDialog.value = false
}

watch(currentId, () => {
  query.page = 1
  load()
})

watch(
  () => route.query.id,
  async (id) => {
    if (id) await openDetail({ id })
  }
)

onMounted(async () => {
  if (route.query.q) query.q = String(route.query.q)
  if (route.query.status) query.status = String(route.query.status)
  await load()
  if (route.query.id) await openDetail({ id: route.query.id })
})
</script>

<template>
  <div v-loading="loading" class="a13" data-testid="shop-invoices">
    <div class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key || 'all'"
        type="button"
        class="tab"
        :class="{ on: query.status === t.key }"
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
          placeholder="订单号 / 抬头"
          style="width: 200px"
          @keyup.enter="() => { query.page = 1; load() }"
        />
        <el-select
          v-model="query.title_type"
          clearable
          placeholder="类型"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="个人" value="person" />
          <el-option label="企业" value="company" />
        </el-select>
        <el-button :type="advOpen ? 'primary' : 'default'" plain @click="advOpen = !advOpen">
          高级筛选
        </el-button>
      </div>
      <div class="right">
        <el-dropdown trigger="click" @command="(cmd) => cmd === 'current' && exportCsv()">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">当前筛选</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColSettings">列设置</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-select v-model="query.status" clearable placeholder="状态" style="width: 140px">
          <el-option label="待处理" value="submitted" />
          <el-option label="已开票" value="issued" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-date-picker
          v-model="query.created_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="申请起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.created_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="申请止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
      </div>
    </div>

    <el-table :data="items" border stripe size="small" style="margin-top: 12px">
      <el-table-column v-if="colVisible.order_no" prop="order_no" label="订单" min-width="140" />
      <el-table-column v-if="colVisible.title" prop="title" label="抬头" min-width="120" />
      <el-table-column v-if="colVisible.title_type" label="类型" width="80">
        <template #default="{ row }">{{ titleTypeText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.tax_no" prop="tax_no" label="税号" width="160">
        <template #default="{ row }">{{ row.tax_no || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.email" prop="email" label="邮箱" min-width="120">
        <template #default="{ row }">{{ row.email || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.amount" label="金额" width="100">
        <template #default="{ row }">{{ fmtMoney(row.amount_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.created_at" label="申请时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.status" label="状态" width="110">
        <template #default="{ row }">
          {{ STATUS_LABEL[row.status] || row.status }}
          <el-tag v-if="row.needs_red_flush" type="danger" size="small" style="margin-left: 4px">待红冲</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colVisible.operator_name" label="处理人" width="110">
        <template #default="{ row }">{{ row.operator_name || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.issued_at" label="开具时间" width="140">
        <template #default="{ row }">{{ fmtTime(row.issued_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colVisible.invoice_no" prop="invoice_no" label="发票号码" width="120" />
      <el-table-column v-if="colVisible.ops" label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'submitted' || row.status === 'pending'">
            <el-button link type="primary" @click="openIssue(row)">开具</el-button>
            <el-button link type="danger" @click="openReject(row)">驳回</el-button>
          </template>
          <el-button v-else link type="primary" @click="openDetail(row)">查看</el-button>
        </template>
      </el-table-column>
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

    <el-drawer v-model="issueDrawer" size="420px">
      <template #header>
        <span>开具发票 · 订单 {{ issueRow?.order_no }}</span>
      </template>
      <el-form v-if="issueRow" label-width="120px">
        <el-form-item label="抬头（只读）">
          <span>{{ titleWithType(issueRow) }}</span>
        </el-form-item>
        <el-form-item label="税号（只读）">
          <span>{{ issueRow.tax_no || '—' }}</span>
        </el-form-item>
        <el-form-item label="邮箱（只读）">
          <span>{{ issueRow.email || '—' }}</span>
        </el-form-item>
        <el-form-item label="金额（只读）">
          <span>{{ fmtMoney(issueRow.amount_cents) }}</span>
        </el-form-item>
        <el-form-item label="发票号码" required>
          <el-input v-model="invoiceNo" placeholder="税控开具后填入" />
        </el-form-item>
        <el-form-item label="电子发票 PDF">
          <ShopMaterialUpload
            doc-type="invoice_pdf"
            title="电子发票 PDF"
            optional
            :upload-fn="uploadInvoicePdf"
            :file-id="pdfFileId"
            :file-name="pdfFileName"
            @uploaded="onPdfUploaded"
            @cleared="onPdfCleared"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="issueRemark"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="选填"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="confirmIssue">确认开具</el-button>
          <el-button @click="issueDrawer = false">取消</el-button>
        </el-form-item>
      </el-form>
    </el-drawer>

    <el-drawer v-model="detailDrawer" size="420px">
      <template #header>
        <span>
          开票详情 · 订单 {{ detail?.order_no }}
          <el-tag
            :type="detail?.status === 'issued' ? 'success' : 'danger'"
            size="small"
            style="margin-left: 8px"
          >
            {{ STATUS_LABEL[detail?.status] || detail?.status }}
          </el-tag>
        </span>
      </template>
      <el-form v-if="detail" label-width="130px">
        <el-form-item label="抬头（只读）">
          <span>{{ titleWithType(detail) }}</span>
        </el-form-item>
        <el-form-item label="金额（只读）">
          <span>{{ fmtMoney(detail.amount_cents) }}</span>
        </el-form-item>
        <template v-if="detail.status === 'issued'">
          <el-form-item label="发票号（只读）">
            <span>{{ detail.invoice_no || '—' }}</span>
          </el-form-item>
          <el-form-item label="开具时间（只读）">
            <span>{{ fmtTime(detail.issued_at) }} · {{ detail.operator_name || '—' }}</span>
          </el-form-item>
          <el-form-item label="备注（只读）">
            <span>{{ detail.remark || '—' }}</span>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="申请时间（只读）">
            <span>{{ fmtTime(detail.created_at) }}</span>
          </el-form-item>
          <el-form-item label="审核状态（只读）">
            <span>{{ STATUS_LABEL[detail.status] || detail.status }}</span>
          </el-form-item>
          <el-form-item label="驳回原因（只读）">
            <span>{{ detail.reject_reason || '—' }}</span>
          </el-form-item>
          <el-form-item label="处理人（只读）">
            <span>{{ detail.operator_name || '—' }} · {{ fmtTime(detail.updated_at) }}</span>
          </el-form-item>
        </template>
        <el-form-item>
          <el-button @click="detailDrawer = false">关闭</el-button>
        </el-form-item>
      </el-form>
    </el-drawer>

    <el-dialog
      v-model="rejectDialog"
      :title="`驳回开票申请 · 订单 ${rejectRow?.order_no || ''}`"
      width="480px"
    >
      <el-form label-width="100px">
        <el-form-item label="驳回原因" required>
          <el-select v-model="rejectCode" placeholder="请选择驳回原因" style="width: 100%">
            <el-option
              v-for="r in REJECT_REASONS"
              :key="r.value"
              :label="r.label"
              :value="r.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input v-model="rejectNote" type="textarea" :rows="3" placeholder="请填写说明（至少 4 字）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="danger" @click="confirmReject">确认驳回</el-button>
        <el-button @click="rejectDialog = false">取消</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog" title="导出任务" width="420px">
      <el-form v-if="exportTask" label-width="100px">
        <el-form-item label="范围">当前筛选</el-form-item>
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
  gap: 0;
  flex-wrap: wrap;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color);
  font-size: 13px;
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
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
