<script setup>
/**
 * P05 清结算。对照 PRD 06-平台端UI.html #p05 · #p05a · #p05b · #p05c
 * 默认列：结算批次、商家、周期、成交额、平台抽成、退款冲正、应结、生成时间、状态、操作
 * 缺口：打款为人工确认（不对接银行）；凭证导出为 CSV（非 PDF）；导出完成站内信本批不接。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'
import { formatDateTime } from '../../../utils/datetime'
import ShopMaterialUpload from '../../../components/shop/ShopMaterialUpload.vue'
import { SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../../utils/shopExport'

const COLUMN_KEY = 'shop-settlement-list-columns'
const ALL_COLUMNS = [
  { key: 'batch_no', label: '结算批次', locked: true, defaultVisible: true },
  { key: 'merchant_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'period', label: '周期', defaultVisible: true },
  { key: 'gross', label: '成交额', defaultVisible: true },
  { key: 'fee', label: '平台抽成', defaultVisible: true },
  { key: 'reversal', label: '退款冲正', defaultVisible: true },
  { key: 'net', label: '应结', defaultVisible: true },
  { key: 'generated_at', label: '生成时间', defaultVisible: true },
  { key: 'status', label: '状态', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'paid_at', label: '打款时间', defaultVisible: false },
  { key: 'operator_name', label: '打款人', defaultVisible: false },
  { key: 'opening', label: '上期结转', defaultVisible: false },
]

const route = useRoute()
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
const viewTab = ref('all')
const advExpanded = ref(false)
const advStatus = ref('')
const advPeriodStart = ref('')
const advPeriodEnd = ref('')
const sortBy = ref('generated_at')
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
const confirmVisible = ref(false)
const retryVisible = ref(false)
const submitting = ref(false)
const confirmForm = reactive({ remark: '', file_id: '', file_name: '' })
const retryAction = ref('retry')

const TABS = [
  { name: 'todo', label: '待办' },
  { name: 'all', label: '全部批次' },
  { name: 'paid', label: '已打款' },
  { name: 'closed', label: '已关账' },
  { name: 'carried_forward', label: '结转中' },
  { name: 'offset_settled', label: '已抵扣' },
]

const STATUS_TAG = {
  pending: 'warning',
  paid: 'success',
  payment_failed: 'danger',
  closed: 'info',
  carried_forward: 'warning',
  offset_settled: 'info',
}

function fmtMoney(cents) {
  const n = Number(cents) || 0
  const sign = n < 0 ? '−' : ''
  return `${sign}¥${(Math.abs(n) / 100).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function fmtReversal(cents) {
  if (!cents) return '—'
  return fmtMoney(cents)
}

function fmtPeriod(row) {
  if (!row.period_start) return '—'
  const a = String(row.period_start).slice(5).replace('-', '.')
  const b = String(row.period_end).slice(5).replace('-', '.')
  return `${a}–${b}`
}

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
    period_start: advPeriodStart.value || undefined,
    period_end: advPeriodEnd.value || undefined,
  }
  if (viewTab.value === 'todo') p.view = 'todo'
  else if (viewTab.value !== 'all') p.status = viewTab.value
  if (advStatus.value) p.status = advStatus.value
  return p
}

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopSettlementBatches(listParams())
    items.value = data.items || []
    total.value = data.total || 0
    stats.value = data.stats || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onTabChange(name) {
  viewTab.value = name
  advStatus.value = ''
  page.value = 1
  load()
}

function onSearch() {
  page.value = 1
  load()
}

async function openDetail(row) {
  try {
    const { data } = await adminApi.getShopSettlementBatch(row.id)
    detail.value = data
    detailVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '详情加载失败')
  }
}

function openConfirm(row) {
  confirmForm.remark = ''
  confirmForm.file_id = ''
  confirmForm.file_name = ''
  if (!detail.value || detail.value.id !== row.id) {
    openDetail(row).then(() => {
      confirmVisible.value = true
    })
  } else {
    confirmVisible.value = true
  }
}

function openRetry(row) {
  retryAction.value = 'retry'
  if (!detail.value || detail.value.id !== row.id) {
    openDetail(row).then(() => {
      retryVisible.value = true
    })
  } else {
    retryVisible.value = true
  }
}

async function submitConfirm() {
  if (!detail.value) return
  submitting.value = true
  try {
    const { data } = await adminApi.confirmShopSettlement(detail.value.id, {
      remark: confirmForm.remark || undefined,
      transfer_voucher_url: confirmForm.file_id || undefined,
    })
    detail.value = data
    confirmVisible.value = false
    ElMessage.success('已确认打款')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '打款失败')
  } finally {
    submitting.value = false
  }
}

async function submitRetry() {
  if (!detail.value) return
  submitting.value = true
  try {
    const { data } = await adminApi.retryShopSettlement(detail.value.id, {
      action: retryAction.value,
    })
    detail.value = data
    retryVisible.value = false
    ElMessage.success(retryAction.value === 'return_pending' ? '已退回待结算' : '已重试')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '重试失败')
  } finally {
    submitting.value = false
  }
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
    const { data } = await adminApi.createShopSettlementExport(body)
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
    const res = await adminApi.getShopSettlementExportFile(exportTask.value.id)
    downloadBlob(res.data, exportTask.value.file_name || 'shop-settlement-batches.csv')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

async function exportVoucher(row) {
  try {
    const { data } = await adminApi.exportShopSettlementVoucher(row.id)
    downloadBlob(data, `${row.batch_no}-凭证.csv`)
  } catch (e) {
    ElMessage.error(e.message || '仅已打款批次可导出')
  }
}

async function exportItems() {
  if (!detail.value) return
  try {
    const { data } = await adminApi.exportShopSettlementItems(detail.value.id)
    downloadBlob(data, `${detail.value.batch_no}-明细.csv`)
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  }
}

async function uploadVoucher(_docType, file) {
  if (!detail.value?.id) throw new Error('请先打开批次')
  const { data } = await adminApi.uploadShopSettlementVoucher(detail.value.id, file)
  return data
}

function onVoucherUploaded(payload) {
  confirmForm.file_id = payload.fileId
  confirmForm.file_name = payload.fileName || ''
}

function onVoucherCleared() {
  confirmForm.file_id = ''
  confirmForm.file_name = ''
}

async function previewVoucher() {
  const fileId = detail.value?.transfer_voucher_url
  if (!detail.value?.id || !fileId) return
  try {
    const { data } = await adminApi.downloadShopSettlementVoucher(detail.value.id, fileId)
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    ElMessage.error(e.message || '凭证预览失败')
  }
}

function carrySourceText(src) {
  if (!src) return '—'
  const period = src.period_start ? `${fmtPeriod(src)} · ` : ''
  const net = src.net_amount_cents != null ? `应结 ${fmtMoney(src.net_amount_cents)} · ` : ''
  const st = src.status_label || ''
  return `${src.batch_no || '—'}（${period}${net}${st}）`.replace(' · ）', '）')
}

async function openCarrySource(src) {
  if (!src?.id) return
  await openDetail({ id: src.id })
}

async function openOffsetBatch() {
  if (!detail.value?.offset_by_batch_id) return
  await openDetail({ id: detail.value.offset_by_batch_id })
}

const confirmTitle = computed(() =>
  detail.value?.batch_no ? `确认打款「${detail.value.batch_no}」？` : '确认打款',
)
const retryTitle = computed(() =>
  detail.value?.batch_no ? `重试打款「${detail.value.batch_no}」？` : '重试打款',
)

onMounted(() => {
  const st = String(route.query.status || '')
  if (st === 'pending' || st === 'payment_failed') viewTab.value = 'todo'
  else if (TABS.some((t) => t.name === st)) viewTab.value = st
  if (st === 'pending' || st === 'payment_failed') advStatus.value = st
  load().then(() => {
    if (route.query.id) {
      const row = items.value.find((x) => x.id === String(route.query.id))
      if (row) openDetail(row)
    }
  })
})

watch(pageSize, () => {
  page.value = 1
  load()
})
</script>

<template>
  <div class="page-card" data-testid="shop-settlement-page">
    <el-row :gutter="16" class="dash-stats">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card__label">本月平台收入</div>
          <div class="stat-card__value">{{ fmtMoney(stats.month_platform_fee_cents) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card__label">待结算给商家</div>
          <div class="stat-card__value stat-card__value--primary">{{ fmtMoney(stats.pending_payout_cents) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card__label">退款冲正</div>
          <div class="stat-card__value">{{ fmtMoney(stats.month_refund_reversal_cents) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-card__label">默认出账周期</div>
          <div class="stat-card__value">周结</div>
        </div>
      </el-col>
    </el-row>

    <el-tabs :model-value="viewTab" @tab-change="onTabChange">
      <el-tab-pane v-for="t in TABS" :key="t.name" :label="t.label" :name="t.name" />
    </el-tabs>

    <div class="toolbar">
      <el-input
        v-model="searchQ"
        clearable
        placeholder="批次号 / 商家名"
        style="width: 240px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-select v-model="advStatus" clearable placeholder="状态" style="width: 140px" @change="onSearch">
        <el-option label="待结算" value="pending" />
        <el-option label="打款失败" value="payment_failed" />
        <el-option label="已打款" value="paid" />
        <el-option label="已关账" value="closed" />
        <el-option label="结转中" value="carried_forward" />
        <el-option label="已抵扣" value="offset_settled" />
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
    <div v-if="advExpanded" class="adv">
      <el-date-picker
        v-model="advPeriodStart"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="周期起"
        style="width: 160px"
        @change="onSearch"
      />
      <el-date-picker
        v-model="advPeriodEnd"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="周期止"
        style="width: 160px"
        @change="onSearch"
      />
      <span class="adv-hint-inline">按出账周期筛选（默认周结）</span>
    </div>

    <el-table v-loading="loading" :data="items" border stripe size="small">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column v-if="colKey === 'batch_no'" min-width="140">
        <template #header>
          <span class="th-sort" @click="toggleSort('batch_no')">结算批次 {{ sortIcon('batch_no') }}</span>
        </template>
        <template #default="{ row }">{{ row.batch_no }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'merchant_name'" prop="merchant_name" label="商家" min-width="140" />
      <el-table-column v-if="colKey === 'period'" label="周期" width="120">
        <template #default="{ row }">{{ fmtPeriod(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'gross'" width="120" align="right">
        <template #header>
          <span class="th-sort" @click="toggleSort('gross_amount_cents')">成交额 {{ sortIcon('gross_amount_cents') }}</span>
        </template>
        <template #default="{ row }">{{ fmtMoney(row.gross_amount_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'fee'" label="平台抽成" width="110" align="right">
        <template #default="{ row }">{{ fmtMoney(row.platform_fee_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'reversal'" label="退款冲正" width="110" align="right">
        <template #default="{ row }">{{ fmtReversal(row.refund_reversal_cents) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'opening'" label="上期结转" width="110" align="right">
        <template #default="{ row }">{{ row.opening_balance_cents ? fmtMoney(row.opening_balance_cents) : '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'net'" label="应结" width="120" align="right">
        <template #default="{ row }">
          <span :class="{ 'net-neg': row.net_amount_cents < 0 }">{{ fmtMoney(row.net_amount_cents) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'generated_at'" width="160">
        <template #header>
          <span class="th-sort" @click="toggleSort('generated_at')">生成时间 {{ sortIcon('generated_at') }}</span>
        </template>
        <template #default="{ row }">{{ formatDateTime(row.generated_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'status'" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'paid_at'" label="打款时间" width="160">
        <template #default="{ row }">{{ formatDateTime(row.paid_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'operator_name'" prop="operator_name" label="打款人" width="110" />
      <el-table-column v-if="colKey === 'ops'" label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'pending'" link type="primary" @click="openConfirm(row)">确认打款</el-button>
          <el-button v-if="row.status === 'paid'" link @click="exportVoucher(row)">导出凭证</el-button>
          <el-button v-if="row.status === 'payment_failed'" link type="primary" @click="openRetry(row)">重试</el-button>
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

    <el-drawer v-model="detailVisible" size="560px" :title="detail?.batch_no || '批次详情'">
      <template v-if="detail">
        <div class="detail-hd">
          <el-tag size="small" :type="STATUS_TAG[detail.status] || 'info'">{{ detail.status_label }}</el-tag>
          <span class="muted">{{ detail.merchant_name }} · 周期 {{ fmtPeriod(detail) }}</span>
        </div>
        <div class="detail-ops">
          <el-button v-if="detail.status === 'pending'" type="primary" size="small" @click="confirmVisible = true">确认打款</el-button>
          <el-button v-if="detail.status === 'payment_failed'" type="primary" size="small" @click="retryVisible = true">重试</el-button>
          <el-button v-if="detail.status === 'paid'" size="small" @click="exportVoucher(detail)">导出凭证</el-button>
          <el-button size="small" @click="exportItems">导出明细</el-button>
        </div>
        <el-descriptions :column="1" border size="small" class="block">
          <el-descriptions-item label="汇总（只读）">
            成交额 {{ fmtMoney(detail.gross_amount_cents) }} · 平台抽成 {{ fmtMoney(detail.platform_fee_cents) }}
            · 退款冲正 {{ fmtReversal(detail.refund_reversal_cents) }}
            <template v-if="detail.opening_balance_cents">
              · 本期净额 {{ fmtMoney(detail.period_net_cents) }}
              · 上期结转 {{ fmtMoney(detail.opening_balance_cents) }}
            </template>
            · <b>应结 {{ fmtMoney(detail.net_amount_cents) }}</b>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="(detail.carry_sources || []).length"
            label="结转来源（只读）"
          >
            <el-button
              v-for="src in detail.carry_sources"
              :key="src.id"
              link
              type="primary"
              @click="openCarrySource(src)"
            >
              {{ carrySourceText(src) }}
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item label="收款账户（只读）">
            {{ detail.payout_account?.valid ? detail.payout_account.label : '收款账户异常' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.status === 'carried_forward'" label="说明">
            本期无需打款；负额将计入下期抵扣。下期打款完成后，本批次将更新为「已抵扣」。
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.status === 'offset_settled'" label="抵扣信息（只读）">
            已于
            <el-button v-if="detail.offset_by_batch_id" link type="primary" @click="openOffsetBatch">
              {{ detail.offset_by_batch_no || '—' }}
            </el-button>
            <template v-else>{{ detail.offset_by_batch_no || '—' }}</template>
            确认打款时抵扣
            {{ detail.offset_settled_at ? ' · ' + formatDateTime(detail.offset_settled_at) : '' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.fail_reason" label="失败原因">
            {{ detail.fail_reason }}
            <span v-if="detail.paid_at"> · 上次打款 {{ formatDateTime(detail.paid_at) }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.transfer_voucher_url" label="打款凭证">
            <el-button link type="primary" @click="previewVoucher">预览</el-button>
          </el-descriptions-item>
        </el-descriptions>
        <h4>订单明细</h4>
        <el-table :data="detail.items || []" border size="small">
          <el-table-column prop="item_type_label" label="类型" width="100" />
          <el-table-column label="关联" min-width="120">
            <template #default="{ row }">{{ row.order_no || row.source_batch_no || '—' }}</template>
          </el-table-column>
          <el-table-column label="金额" width="110" align="right">
            <template #default="{ row }">{{ fmtMoney(row.amount_cents) }}</template>
          </el-table-column>
          <el-table-column label="抽成" width="100" align="right">
            <template #default="{ row }">{{ fmtMoney(row.fee_cents) }}</template>
          </el-table-column>
          <el-table-column label="应结" width="110" align="right">
            <template #default="{ row }">{{ fmtMoney(row.net_cents) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <el-dialog v-model="confirmVisible" :title="confirmTitle" width="480px">
      <el-form label-width="140px">
        <el-form-item label="商家（只读）">{{ detail?.merchant_name }}</el-form-item>
        <el-form-item label="应结金额（只读）">
          {{ fmtMoney(detail?.net_amount_cents) }}
          <span v-if="detail?.payout_account?.last4"> → 对公尾号 {{ detail.payout_account.last4 }}</span>
        </el-form-item>
        <el-form-item label="打款凭证（选填）">
          <ShopMaterialUpload
            v-if="detail?.id"
            doc-type="settlement_voucher"
            title="打款凭证"
            :optional="true"
            :file-id="confirmForm.file_id"
            :file-name="confirmForm.file_name"
            :upload-fn="uploadVoucher"
            @uploaded="onVoucherUploaded"
            @cleared="onVoucherCleared"
          />
        </el-form-item>
        <el-form-item label="备注（选填）">
          <el-input v-model="confirmForm.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitConfirm">确认打款</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="retryVisible" :title="retryTitle" width="480px">
      <el-form label-width="140px">
        <el-form-item label="上次失败（只读）">{{ detail?.fail_reason || '—' }}</el-form-item>
        <el-form-item label="应结金额（只读）">
          {{ fmtMoney(detail?.net_amount_cents) }}
          <span v-if="detail?.payout_account?.last4"> · 账户尾号 {{ detail.payout_account.last4 }}</span>
        </el-form-item>
        <el-form-item label="处理方式" required>
          <el-radio-group v-model="retryAction">
            <el-radio value="retry">修正账户后重试</el-radio>
            <el-radio value="return_pending">退回待结算（商家改账户）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="retryVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRetry">确认重试</el-button>
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
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.toolbar-right { margin-left: auto; display: flex; gap: 8px; }
.adv { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.adv-hint-inline { font-size: 12px; color: var(--color-text-secondary); }
.pager { margin-top: 12px; }
.th-sort { cursor: pointer; user-select: none; }
.net-neg { color: #cf1322; }
.detail-hd { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.muted { color: var(--color-text-secondary); font-size: 13px; }
.detail-ops { display: flex; gap: 8px; margin-bottom: 12px; }
.block { margin-bottom: 16px; }
.column-item { margin-bottom: 8px; }
</style>
