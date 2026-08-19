<script setup>
/**
 * 入驻审核。对照 PRD 06-平台端UI.html
 * #p03-list · #p03-detail · #p03-detail-sensitive · #p03-approve · #p03-reject · #p03-readonly
 * 缺口：驳回/通过站内信与短信未接通。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'
import { useAuthStore } from '../../../stores/auth'
import { formatDateTime } from '../../../utils/datetime'

const auth = useAuthStore()
const route = useRoute()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
/** 快捷视图：all | pending | approved | rejected */
const viewTab = ref('pending')
const statusFilter = ref('pending')
const searchQ = ref('')
const entityTypeFilter = ref('')
const advExpanded = ref(false)
const advFilters = ref({
  initiator: '',
  submitted_range: null,
})

function syncStatusFromTab(tab) {
  viewTab.value = tab || 'all'
  statusFilter.value = tab === 'all' || !tab ? '' : tab
}

function syncTabFromStatus(status) {
  statusFilter.value = status || ''
  viewTab.value = status || 'all'
}

/** list = 申请列表；review = 审核详情（非顶栏 Tab） */
const viewMode = ref('list')
/** 审核二级：detail | approve | reject */
const reviewSubTab = ref('detail')
const current = ref(null)
/** file_id -> object URL */
const previewUrls = ref({})

const COLUMN_STORAGE_KEY = 'shop-onboarding-list-columns'
const ALL_COLUMNS = [
  { key: 'merchant', label: '商家', locked: true, defaultVisible: true },
  { key: 'application_no', label: '申请单号', defaultVisible: true },
  { key: 'entity_type', label: '主体类型', defaultVisible: true },
  { key: 'submitted_at', label: '申请时间', defaultVisible: true },
  { key: 'initiator', label: '发起方式', defaultVisible: true },
  { key: 'status', label: '状态', defaultVisible: true },
  { key: 'reviewer_name', label: '审核人', defaultVisible: false },
  { key: 'reviewed_at', label: '审核时间', defaultVisible: false },
  { key: 'merchant_code', label: '商家编码', defaultVisible: false },
  { key: 'tenant_id', label: 'tenant_id', defaultVisible: false },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
]
const {
  visibleKeys: visibleColumns,
  columnDialogVisible,
  columnDraft,
  openColumnSettings,
  saveColumnSettings,
  isColVisible,
} = useListColumnSettings(ALL_COLUMNS, COLUMN_STORAGE_KEY)

const sortBy = ref('submitted_at')
const sortDir = ref('desc')

function sortIcon(prop) {
  if (sortBy.value !== prop) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function toggleSort(prop) {
  if (sortBy.value === prop) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = prop
    sortDir.value = prop === 'display_name' ? 'asc' : 'desc'
  }
  page.value = 1
  loadList()
}

const canApprove = computed(() => auth.hasPlatformShopPermission('platform.shop.approve'))
const canReveal = computed(() =>
  auth.hasAnyPlatformShopPermission([
    'platform.shop.merchant.read',
    'platform.shop.approve',
  ]),
)
const isPending = computed(() => current.value?.status === 'pending')
const showReviewActions = computed(() => canApprove.value && isPending.value)

const revealedMobile = ref('')
const revealedIdNo = ref('')
const revealedBank = ref('')
let revealTimer = null

const approveForm = ref({
  plan_id: '',
  plan_label: '',
  trial_days: 7,
  store_quota: 1,
  benefits_from: '',
  benefits_until: '',
  account_manager_user_id: '',
})
const rejectForm = ref({
  reject_code: 'incomplete_docs',
  reject_reason: '',
})
const acting = ref(false)
const approveOptions = ref({ plans: [], managers: [], default_manager_user_id: '' })
const rejectGroups = ref([])

/** 对照 PRD #p03a · 04 §入驻驳回原因码（GET reject-reasons，15 项） */

function maskIdNo(v) {
  const s = String(v || '')
  if (s.length < 8) return s || '—'
  return `${s.slice(0, 3)}${'*'.repeat(Math.max(s.length - 7, 4))}${s.slice(-4)}`
}

function displayMobile() {
  if (revealedMobile.value) return revealedMobile.value
  return current.value?.contact_mobile || '—'
}

function displayIdNo() {
  if (revealedIdNo.value) return revealedIdNo.value
  return current.value?.id_no || '—'
}

function displayBank() {
  if (revealedBank.value) return revealedBank.value
  return current.value?.bank_account_display || '—'
}

function clearReveal() {
  revealedMobile.value = ''
  revealedIdNo.value = ''
  revealedBank.value = ''
  if (revealTimer) {
    clearTimeout(revealTimer)
    revealTimer = null
  }
}

async function revealField(field) {
  if (!current.value?.id) return
  if (field === 'contact_mobile' && revealedMobile.value) {
    revealedMobile.value = ''
    return
  }
  if (field === 'id_no' && revealedIdNo.value) {
    revealedIdNo.value = ''
    return
  }
  if (field === 'bank_account_no' && revealedBank.value) {
    revealedBank.value = ''
    return
  }
  try {
    const { data } = await adminApi.revealShopOnboardingSensitive(current.value.id, { field })
    if (field === 'contact_mobile') revealedMobile.value = data.value
    if (field === 'id_no') revealedIdNo.value = data.value
    if (field === 'bank_account_no') revealedBank.value = data.value
    if (revealTimer) clearTimeout(revealTimer)
    revealTimer = setTimeout(() => clearReveal(), 5 * 60 * 1000)
    const { data: fresh } = await adminApi.getShopOnboardingApplication(current.value.id)
    current.value = fresh
  } catch (e) {
    ElMessage.error(e.message || '揭露失败')
  }
}

const filledFieldMap = computed(() => {
  const c = current.value
  if (!c) return {}
  return {
    执照名: c.legal_name,
    legal_name: c.legal_name,
    name: c.legal_name,
    信用代码: c.unified_social_credit_code,
    unified_social_credit_code: c.unified_social_credit_code,
    credit_code: c.unified_social_credit_code,
    法人: c.legal_rep_name,
    legal_rep_name: c.legal_rep_name,
    身份证号: c.id_no ? maskIdNo(c.id_no) : '',
    id_no: c.id_no ? maskIdNo(c.id_no) : '',
  }
})

const entityLabel = {
  personal: '个人',
  individual_business: '个体工商户',
  enterprise: '企业',
}

const initiatorLabel = {
  merchant_self: '商家自申',
  platform: '管家代建',
  ops_assisted: '管家代建',
}

const statusLabel = {
  pending: '待审',
  approved: '已通过',
  rejected: '已驳回',
}

const statusTagType = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}

const materialLabels = {
  id_card_front: '身份证正面',
  id_card_back: '身份证反面',
  business_license: '营业执照',
  legal_id_front: '法人证正面',
  legal_id_back: '法人证反面',
  bank_permit: '对公账户',
  icp: 'ICP 备案 / 类目资质',
  handheld: '手持照',
}

const materialEntries = computed(() => {
  const files = current.value?.qualification_files || {}
  return Object.entries(files).map(([key, fileId]) => ({
    key,
    label: materialLabels[key] || key,
    fileId: String(fileId || ''),
  }))
})

const applicationNo = computed(
  () => current.value?.application_no || '—',
)

const ocrRows = computed(() => {
  const list = current.value?.ocr_results || []
  const filled = filledFieldMap.value
  const rows = []
  for (const item of list) {
    const fields = item.fields || {}
    const conf =
      item.confidence != null ? Number(item.confidence).toFixed(2) : '—'
    for (const [field, value] of Object.entries(fields)) {
      const filledVal = filled[field] ?? filled[field.toLowerCase?.()] ?? '—'
      rows.push({
        field: String(field),
        filled: filledVal || '—',
        ocr: String(value ?? ''),
        confidence: conf,
      })
    }
    if (!Object.keys(fields).length) {
      rows.push({ field: '—', filled: '—', ocr: '无识别字段', confidence: conf })
    }
  }
  return rows
})

function revokePreviews() {
  Object.values(previewUrls.value).forEach((url) => {
    try {
      URL.revokeObjectURL(url)
    } catch {
      /* ignore */
    }
  })
  previewUrls.value = {}
}

async function loadMaterialPreviews() {
  revokePreviews()
  if (!current.value?.id) return
  const next = {}
  for (const m of materialEntries.value) {
    if (!m.fileId) continue
    try {
      const { data } = await adminApi.downloadShopOnboardingFile(current.value.id, m.fileId)
      const blob = data instanceof Blob ? data : new Blob([data])
      next[m.fileId] = URL.createObjectURL(blob)
    } catch {
      /* 预览失败仍显示占位 */
    }
  }
  previewUrls.value = next
}

function buildListParams() {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
  }
  const q = searchQ.value.trim()
  if (q) params.q = q
  if (statusFilter.value) params.status = statusFilter.value
  if (entityTypeFilter.value) params.entity_type = entityTypeFilter.value
  if (advFilters.value.initiator) params.initiator = advFilters.value.initiator
  if (advFilters.value.submitted_range?.[0]) {
    params.submitted_from = advFilters.value.submitted_range[0]
  }
  if (advFilters.value.submitted_range?.[1]) {
    params.submitted_until = advFilters.value.submitted_range[1]
  }
  return params
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopOnboardingApplications(buildListParams())
    items.value = data.items ?? []
    total.value = data.total ?? 0
  } catch (e) {
    if (isBenignEmptyError(e)) {
      items.value = []
      total.value = 0
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  loadList()
}

function resetAdvFilters() {
  advFilters.value = { initiator: '', submitted_range: null }
  page.value = 1
  loadList()
}

function downloadCsv(filename, header, rows) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const blob = new Blob(
    ['\ufeff' + [header.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\n')],
    { type: 'text/csv;charset=utf-8' },
  )
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function exportList() {
  downloadCsv(
    '入驻申请.csv',
    ['商家', '申请单号', '主体类型', '申请时间', '发起方式', '状态', '审核人', '审核时间', '商家编码'],
    items.value.map((r) => [
      r.legal_name || r.display_name || '',
      r.application_no || '',
      entityLabel[r.entity_type] || r.entity_type,
      formatDateTime(r.submitted_at),
      initiatorLabel[r.initiator] || r.initiator,
      statusLabel[r.status] || r.status,
      r.reviewer_name || '',
      formatDateTime(r.reviewed_at),
      r.merchant_code || '',
    ]),
  )
}

async function loadRejectReasons() {
  try {
    const { data } = await adminApi.listShopOnboardingRejectReasons()
    rejectGroups.value = data.groups || []
  } catch {
    rejectGroups.value = []
  }
}

async function loadApproveOptions(entityType) {
  try {
    const { data } = await adminApi.listShopOnboardingApproveOptions(
      entityType ? { entity_type: entityType } : {},
    )
    approveOptions.value = {
      plans: data.plans || [],
      managers: data.managers || [],
      default_manager_user_id: data.default_manager_user_id || '',
    }
  } catch {
    approveOptions.value = { plans: [], managers: [], default_manager_user_id: '' }
  }
}

function resetAllFilters() {
  searchQ.value = ''
  entityTypeFilter.value = ''
  syncTabFromStatus('')
  resetAdvFilters()
}

async function openReview(row, preferSub = 'detail') {
  try {
    clearReveal()
    const { data } = await adminApi.getShopOnboardingApplication(row.id)
    current.value = data
    reviewSubTab.value = data.status === 'pending' ? preferSub : 'detail'
    viewMode.value = 'review'
    rejectForm.value.reject_reason = ''
    const today = new Date()
    const ymd = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, '0'),
      String(today.getDate()).padStart(2, '0'),
    ].join('-')
    await loadApproveOptions(data.entity_type)
    const firstPlan = approveOptions.value.plans[0]
    approveForm.value = {
      plan_id: firstPlan?.id || '',
      plan_label: firstPlan?.name || '',
      trial_days: 7,
      store_quota: 1,
      benefits_from: ymd,
      benefits_until: '',
      account_manager_user_id: approveOptions.value.default_manager_user_id || '',
    }
    await loadMaterialPreviews()
  } catch (e) {
    ElMessage.error(e.message || '加载详情失败')
  }
}

async function openReviewById(id) {
  if (!id) return
  await openReview({ id })
}

function backToList() {
  viewMode.value = 'list'
  current.value = null
  reviewSubTab.value = 'detail'
  clearReveal()
  revokePreviews()
  loadList()
}

async function openPreview(fileId, label) {
  let url = previewUrls.value[fileId]
  if (!url && current.value?.id) {
    try {
      const { data } = await adminApi.downloadShopOnboardingFile(current.value.id, fileId)
      const blob = data instanceof Blob ? data : new Blob([data])
      url = URL.createObjectURL(blob)
      previewUrls.value = { ...previewUrls.value, [fileId]: url }
    } catch (e) {
      ElMessage.error(e.message || '无法打开附件')
      return
    }
  }
  if (!url) {
    ElMessage.warning('附件不可用')
    return
  }
  window.open(url, '_blank', 'noopener')
}

async function doApprove() {
  if (!current.value) return
  if (!approveForm.value.plan_id && !approveForm.value.plan_label?.trim()) {
    ElMessage.warning('请选择首开套餐')
    return
  }
  if (!approveForm.value.benefits_from) {
    ElMessage.warning('请选择生效起')
    return
  }
  if (!approveForm.value.benefits_until && !approveForm.value.trial_days) {
    ElMessage.warning('请填写生效止或试用天数')
    return
  }
  acting.value = true
  try {
    const payload = {
      trial_days: approveForm.value.trial_days,
      store_quota: approveForm.value.store_quota,
      benefits_from: approveForm.value.benefits_from,
    }
    if (approveForm.value.plan_id) payload.plan_id = approveForm.value.plan_id
    if (approveForm.value.plan_label?.trim()) payload.plan_label = approveForm.value.plan_label.trim()
    if (approveForm.value.account_manager_user_id) {
      payload.account_manager_user_id = approveForm.value.account_manager_user_id
    }
    if (approveForm.value.benefits_until) payload.benefits_until = approveForm.value.benefits_until
    const { data } = await adminApi.approveShopOnboarding(current.value.id, payload)
    const subNo = data?.subscription_no
    ElMessage.success(subNo ? `已通过并开通，订阅 ${subNo}` : '已通过并开通商家')
    backToList()
  } catch (e) {
    ElMessage.error(e.message || '审核失败')
  } finally {
    acting.value = false
  }
}

function onPlanChange(planId) {
  const plan = approveOptions.value.plans.find((p) => p.id === planId)
  approveForm.value.plan_label = plan?.name || ''
}

async function doReject() {
  if (!current.value) return
  if (!rejectForm.value.reject_code) {
    ElMessage.warning('请选择驳回原因码')
    return
  }
  if (!rejectForm.value.reject_reason || rejectForm.value.reject_reason.trim().length < 4) {
    ElMessage.warning('驳回原因至少 4 个字')
    return
  }
  acting.value = true
  try {
    await adminApi.rejectShopOnboarding(current.value.id, {
      reject_code: rejectForm.value.reject_code,
      reject_reason: rejectForm.value.reject_reason.trim(),
    })
    ElMessage.success('已驳回')
    backToList()
  } catch (e) {
    ElMessage.error(e.message || '驳回失败')
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  const st = route.query.status
  if (st) syncTabFromStatus(String(st))
  loadRejectReasons()
  await loadList()
  const appId = route.query.id
  if (appId) await openReviewById(String(appId))
})
onBeforeUnmount(() => {
  clearReveal()
  revokePreviews()
})
</script>

<template>
  <div class="page-card onboarding-applications" data-testid="shop-onboarding">
    <div v-show="viewMode === 'list'">
      <el-tabs
        :model-value="viewTab"
        @tab-change="
          (name) => {
            syncStatusFromTab(name)
            page = 1
            loadList()
          }
        "
      >
        <el-tab-pane label="全部申请" name="all" />
        <el-tab-pane label="待审" name="pending" />
        <el-tab-pane label="已通过" name="approved" />
        <el-tab-pane label="已驳回" name="rejected" />
      </el-tabs>

      <div class="toolbar">
        <el-input
          v-model="searchQ"
          clearable
          placeholder="搜索商家名"
          style="width: 220px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-select
          v-model="entityTypeFilter"
          clearable
          placeholder="主体类型"
          style="width: 140px"
          @change="onSearch"
        >
          <el-option label="个人" value="personal" />
          <el-option label="个体工商户" value="individual_business" />
          <el-option label="企业" value="enterprise" />
        </el-select>
        <el-select
          v-model="statusFilter"
          clearable
          placeholder="审核状态"
          style="width: 120px"
          @change="
            (v) => {
              syncTabFromStatus(v)
              onSearch()
            }
          "
        >
          <el-option label="待审" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
        <el-button :type="advExpanded ? 'primary' : 'default'" plain @click="advExpanded = !advExpanded">
          高级筛选 {{ advExpanded ? '▴' : '▾' }}
        </el-button>
        <div class="toolbar-spacer" />
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button @click="exportList">导出</el-button>
      </div>

      <div v-show="advExpanded" class="adv-panel">
        <div class="adv-panel-title">高级筛选</div>
        <div class="adv-grid">
          <el-select
            v-model="advFilters.initiator"
            clearable
            placeholder="发起方式"
            style="width: 140px"
          >
            <el-option label="商家自申" value="merchant_self" />
            <el-option label="管家代建" value="platform" />
          </el-select>
          <el-date-picker
            v-model="advFilters.submitted_range"
            type="daterange"
            range-separator="—"
            start-placeholder="申请起"
            end-placeholder="申请止"
            value-format="YYYY-MM-DD"
            style="width: 280px"
          />
        </div>
        <div class="adv-actions">
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="resetAdvFilters">重置</el-button>
          <el-button link type="primary" @click="resetAllFilters">清空全部筛选</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="items" stripe style="margin-top: 4px">
        <template v-for="colKey in visibleColumns" :key="colKey">
        <el-table-column v-if="colKey === 'merchant'" min-width="160" fixed="left">
          <template #header>
            <button type="button" class="th-sort" @click="toggleSort('display_name')">
              商家 <span class="sort-ico">{{ sortIcon('display_name') }}</span>
            </button>
          </template>
          <template #default="{ row }">
            <div>{{ row.legal_name || row.display_name || '—' }}</div>
            <div
              v-if="row.display_name && row.display_name !== row.legal_name"
              class="cell-sub"
            >
              {{ row.display_name }}
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="colKey === 'application_no'" label="申请单号" width="150">
          <template #default="{ row }">
            <code>{{ row.application_no || '—' }}</code>
          </template>
        </el-table-column>
        <el-table-column v-if="colKey === 'entity_type'" label="主体类型" width="120">
          <template #default="{ row }">
            {{ entityLabel[row.entity_type] || row.entity_type }}
          </template>
        </el-table-column>
        <el-table-column v-if="colKey === 'submitted_at'" width="180">
          <template #header>
            <button type="button" class="th-sort" @click="toggleSort('submitted_at')">
              申请时间 <span class="sort-ico">{{ sortIcon('submitted_at') }}</span>
            </button>
          </template>
          <template #default="{ row }">{{ formatDateTime(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'initiator'" label="发起方式" width="110">
          <template #default="{ row }">
            {{ initiatorLabel[row.initiator] || row.initiator }}
          </template>
        </el-table-column>
        <el-table-column v-if="colKey === 'status'" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType[row.status] || 'info'">
              {{ statusLabel[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="colKey === 'reviewer_name'" label="审核人" width="110">
          <template #default="{ row }">{{ row.reviewer_name || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'reviewed_at'" label="审核时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.reviewed_at) }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'merchant_code'" label="商家编码" width="140">
          <template #default="{ row }">{{ row.merchant_code || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'tenant_id'" label="tenant_id" min-width="220">
          <template #default="{ row }">{{ row.tenant_id || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'ops'" label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending' && canApprove"
              link
              type="primary"
              size="small"
              @click="openReview(row, 'detail')"
            >
              审核
            </el-button>
            <el-button v-else link type="primary" size="small" @click="openReview(row, 'detail')">
              查看
            </el-button>
          </template>
        </el-table-column>
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          :page-size="pageSize"
          :current-page="page"
          @size-change="
            (s) => {
              pageSize = s
              page = 1
              loadList()
            }
          "
          @current-change="
            (p) => {
              page = p
              loadList()
            }
          "
        />
      </div>
    </div>

    <CrmColumnSettingsDialog
      v-model:visible="columnDialogVisible"
      v-model:columns="columnDraft"
      @save="saveColumnSettings"
    />

    <div v-if="viewMode === 'review' && current" class="review-panel">
      <div class="review-head">
        <div class="review-head-main">
          <el-button link type="primary" @click="backToList">← 返回列表</el-button>
          <div class="detail-head">
            <h3 class="detail-title">{{ current.display_name || current.legal_name }}</h3>
            <el-tag size="small" :type="statusTagType[current.status] || 'info'">
              {{ statusLabel[current.status] || current.status }}
            </el-tag>
            <el-tag size="small" type="info" effect="plain">
              {{ entityLabel[current.entity_type] || current.entity_type }}
            </el-tag>
          </div>
          <p class="detail-sub">
            租户：{{ current.tenant_name || '—' }} ·
            {{ initiatorLabel[current.initiator] || current.initiator }} ·
            {{ formatDateTime(current.submitted_at) }}
          </p>
        </div>
      </div>

      <el-tabs v-if="showReviewActions" v-model="reviewSubTab" class="review-subtabs">
        <el-tab-pane label="申请详情" name="detail" />
        <el-tab-pane label="通过并开通" name="approve" />
        <el-tab-pane label="驳回" name="reject" />
      </el-tabs>
      <p v-else class="readonly-hint">已审出申请仅可查阅详情</p>

      <div v-show="reviewSubTab === 'detail'" class="sub-panel sub-panel--detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="申请单号">
            <code>{{ applicationNo }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="关联租户">{{ current.tenant_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="主体类型">
            {{ entityLabel[current.entity_type] || current.entity_type }}
          </el-descriptions-item>
          <el-descriptions-item label="发起方式">
            {{ initiatorLabel[current.initiator] || current.initiator }}
          </el-descriptions-item>
          <el-descriptions-item label="申请时间">
            {{ formatDateTime(current.submitted_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="商家展示名">{{ current.display_name || '—' }}</el-descriptions-item>
          <el-descriptions-item
            :label="current.entity_type === 'personal' ? '主体名称' : '主体名称（执照名）'"
          >
            {{ current.legal_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="current.entity_type === 'personal'" label="身份证号">
            {{ displayIdNo() }}
            <el-button
              v-if="canReveal && current.id_no"
              link
              type="primary"
              class="eye-btn"
              data-testid="btn-reveal-id-no"
              title="查看完整身份证号"
              @click="revealField('id_no')"
            >
              👁
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item v-else label="统一社会信用代码">
            {{ current.unified_social_credit_code || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="current.entity_type !== 'personal'" label="法定代表人">
            {{ current.legal_rep_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="current.entity_type === 'enterprise'"
            label="对公账户"
          >
            {{ displayBank() }}
            <el-button
              v-if="canReveal && (current.bank_account_display || current.bank_account_info?.account_no_masked)"
              link
              type="primary"
              class="eye-btn"
              data-testid="btn-reveal-bank-account"
              title="查看完整对公账号"
              @click="revealField('bank_account_no')"
            >
              👁
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item label="经营联系人">
            {{ current.contact_name }} · {{ displayMobile() }}
            <el-button
              v-if="canReveal && current.contact_mobile"
              link
              type="primary"
              class="eye-btn"
              data-testid="btn-reveal-contact-mobile"
              title="查看完整手机号"
              @click="revealField('contact_mobile')"
            >
              👁
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTagType[current.status] || 'info'">
              {{ statusLabel[current.status] || current.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="运营备注" :span="2">
            {{ current.remark || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="current.reject_reason" label="驳回说明" :span="2">
            {{ current.reject_reason }}
          </el-descriptions-item>
          <el-descriptions-item label="支付进件（只读）" :span="2">
            入驻通过后由商家在「支付与进件」提交（本批只读提示）
          </el-descriptions-item>
        </el-descriptions>

        <div class="materials-block">
          <div class="section-title">资质材料（只读预览）</div>
          <div v-if="materialEntries.length" class="materials-grid">
            <div
              v-for="m in materialEntries"
              :key="m.key"
              class="material-card"
              @click="openPreview(m.fileId, m.label)"
            >
              <div class="material-thumb">
                <img v-if="previewUrls[m.fileId]" :src="previewUrls[m.fileId]" :alt="m.label" />
                <span v-else class="thumb-fallback">点击查看</span>
              </div>
              <div class="material-label">{{ m.label }}</div>
              <el-button link type="primary" size="small" @click.stop="openPreview(m.fileId, m.label)">
                预览
              </el-button>
            </div>
          </div>
          <p v-else class="compact-empty">暂无材料</p>
        </div>

        <div class="materials-block">
          <div class="section-title">OCR 对照</div>
          <el-table
            v-if="ocrRows.length"
            :data="ocrRows"
            size="small"
            border
            style="max-width: 720px"
          >
            <el-table-column prop="field" label="字段" width="120" />
            <el-table-column prop="filled" label="填写值" min-width="140" />
            <el-table-column prop="ocr" label="OCR 识别" min-width="140" />
            <el-table-column prop="confidence" label="置信度" width="100" />
          </el-table>
          <p v-else class="compact-empty">暂无 OCR 快照</p>
        </div>

        <div class="materials-block">
          <div class="section-title">审核日志</div>
          <el-table
            v-if="(current.review_logs || []).length"
            :data="current.review_logs"
            size="small"
            border
            data-testid="shop-onboarding-review-logs"
            style="max-width: 880px"
          >
            <el-table-column label="时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="action_label" label="动作" width="140" />
            <el-table-column prop="summary" label="摘要" min-width="200" />
            <el-table-column prop="operator_name" label="操作人" width="140" />
          </el-table>
          <p v-else class="compact-empty">暂无审核日志</p>
        </div>
      </div>

      <div
        v-if="showReviewActions && reviewSubTab === 'detail'"
        class="review-sticky-bar"
      >
        <el-button type="danger" plain @click="reviewSubTab = 'reject'">驳回</el-button>
        <el-button type="primary" @click="reviewSubTab = 'approve'">通过并开通</el-button>
      </div>

      <div v-show="reviewSubTab === 'approve' && showReviewActions" class="sub-panel">
        <el-form label-position="top" style="max-width: 480px">
          <el-form-item label="首开套餐" required>
            <el-select
              v-model="approveForm.plan_id"
              filterable
              placeholder="请选择上架套餐"
              style="width: 100%"
              @change="onPlanChange"
            >
              <el-option
                v-for="p in approveOptions.plans"
                :key="p.id"
                :label="p.name"
                :value="p.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="生效起" required>
            <el-date-picker
              v-model="approveForm.benefits_from"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="必选"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="生效止" required>
            <el-date-picker
              v-model="approveForm.benefits_until"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="可与试用天数配合"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="试用天数">
            <el-input-number v-model="approveForm.trial_days" :min="1" :max="365" />
            <span class="form-hint">未填生效止时按天数计算</span>
          </el-form-item>
          <el-form-item label="店铺配额">
            <el-input-number v-model="approveForm.store_quota" :min="1" :max="99" />
          </el-form-item>
          <el-form-item label="分配商家管家">
            <el-select
              v-model="approveForm.account_manager_user_id"
              filterable
              placeholder="默认=当前审核人"
              style="width: 100%"
            >
              <el-option
                v-for="m in approveOptions.managers"
                :key="m.id"
                :label="m.is_current ? `${m.display_name}（当前审核人）` : m.display_name"
                :value="m.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="将创建（只读）">
            <p class="form-hint" style="margin: 0; color: var(--el-text-color-regular)">商家（正常）+ 订阅快照</p>
          </el-form-item>
          <div class="form-actions">
            <el-button @click="reviewSubTab = 'detail'">取消</el-button>
            <el-button type="primary" :loading="acting" @click="doApprove">确认通过并开通</el-button>
          </div>
        </el-form>
      </div>

      <div v-show="reviewSubTab === 'reject' && showReviewActions" class="sub-panel">
        <el-form label-position="top" style="max-width: 480px">
          <el-form-item label="驳回原因码" required>
            <el-select v-model="rejectForm.reject_code" style="width: 100%" placeholder="请选择">
              <el-option-group v-for="g in rejectGroups" :key="g.group" :label="g.group">
                <el-option v-for="c in g.items" :key="c.code" :label="c.label" :value="c.code" />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="说明" required>
            <el-input
              v-model="rejectForm.reject_reason"
              type="textarea"
              :rows="3"
              placeholder="至少 4 字；选「需补充材料」或「其他」时须写明"
            />
          </el-form-item>
          <div class="form-actions">
            <el-button @click="reviewSubTab = 'detail'">取消</el-button>
            <el-button type="danger" :loading="acting" @click="doReject">确认驳回</el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}
.toolbar-spacer {
  flex: 1;
  min-width: 8px;
}
.adv-panel {
  border: 1px solid #91caff;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #f0f7ff;
}
.adv-panel-title {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 10px;
  font-size: 13px;
}
.adv-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.adv-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.column-item {
  margin-bottom: 8px;
}
.th-sort {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  margin: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.th-sort:hover {
  color: var(--el-color-primary);
}
.sort-ico {
  display: inline-block;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1;
}
.th-sort:hover .sort-ico {
  color: var(--el-color-primary);
}
.review-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.review-head-main {
  min-width: 0;
  flex: 1;
}
.detail-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 4px 0;
}
.detail-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}
.detail-sub {
  margin: 0 0 4px;
  font-size: 13px;
  color: #8c8c8c;
}
.readonly-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #8c8c8c;
}
.sub-panel {
  margin-top: 8px;
}
.sub-panel--detail {
  padding-bottom: 72px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 10px;
  color: #262626;
}
.compact-empty {
  margin: 0;
  padding: 10px 12px;
  font-size: 13px;
  color: #8c8c8c;
  background: #fafafa;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
}
.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.material-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
  text-align: center;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s;
}
.material-card:hover {
  border-color: var(--el-color-primary);
}
.material-thumb {
  height: 100px;
  border-radius: 6px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  margin-bottom: 8px;
}
.material-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.thumb-fallback {
  font-size: 12px;
  color: #8c8c8c;
}
.material-label {
  font-size: 13px;
  color: #262626;
  margin-bottom: 2px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #8c8c8c;
}
.eye-btn {
  padding: 0 4px;
  min-height: auto;
}
.review-sticky-bar {
  position: sticky;
  bottom: 0;
  z-index: 20;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
  padding: 12px 0;
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.04);
}
.onboarding-applications.page-card {
  /* 让 sticky 底栏贴内容区底部时不被裁切观感突兀 */
  position: relative;
}
.cell-sub {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 2px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
