<script setup>
/**
 * 商家租户列表。对照 PRD 06-平台端UI.html
 * #p02-list · #p02a · #p02c · #p02d · #p02e · #p02f · #p02b-tags
 * 缺口：暂停/清退站内信未接通；改派站内信未接通；导出完成站内信本批不接。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import ShopMaterialUpload from '../../../components/shop/ShopMaterialUpload.vue'
import ShopAssignManagerDialog from '../../../components/shop/ShopAssignManagerDialog.vue'
import ShopMerchantTagsDialog from '../../../components/shop/ShopMerchantTagsDialog.vue'
import { useAuthStore } from '../../../stores/auth'
import { formatDate, formatDateTime, parseApiDateTime } from '../../../utils/datetime'
import { SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../../utils/shopExport'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const COLUMN_STORAGE_KEY = 'shop-merchant-list-columns'

const ALL_COLUMNS = [
  { key: 'display_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'merchant_code', label: '商家编码', defaultVisible: true },
  { key: 'entity_type', label: '主体', defaultVisible: true },
  { key: 'plan_label', label: '当前套餐', defaultVisible: true },
  { key: 'plan_status', label: '套餐状态', defaultVisible: true },
  { key: 'benefits_until', label: '权益至', defaultVisible: true },
  { key: 'store_count', label: '店铺数', defaultVisible: true },
  { key: 'account_manager_name', label: '商家管家', defaultVisible: true },
  { key: 'tags', label: '标签', defaultVisible: true },
  { key: 'created_at', label: '创建时间', defaultVisible: true },
  { key: 'onboarding_status', label: '入驻状态', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
]

const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref(SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQ = ref('')
const tagFilter = ref([])
const activeTab = ref('all')
const advExpanded = ref(false)
const columnDialogVisible = ref(false)
const columnDraft = ref([])
/** 对照 PRD #p02-list 可排序列：商家 · 商家编码 · 权益至 · 店铺数 · 创建时间 */
const SORTABLE_COLS = new Set([
  'display_name',
  'merchant_code',
  'benefits_until',
  'store_count',
  'created_at',
])
const sortBy = ref('created_at')
const sortDir = ref('desc')

function sortIcon(prop) {
  if (sortBy.value !== prop) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function toggleSort(prop) {
  if (!SORTABLE_COLS.has(prop)) return
  if (sortBy.value === prop) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = prop
    sortDir.value = prop === 'display_name' || prop === 'merchant_code' ? 'asc' : 'desc'
  }
  page.value = 1
  loadList()
}

const advFilters = ref({
  entity_type: '',
  onboarding_status: '',
  plan_status: '',
  plan_label: '',
  fee_tier: '',
  benefits_range: null,
  store_count_min: null,
  store_count_max: null,
  created_range: null,
})

const canListAll = computed(() =>
  auth.hasPlatformShopPermission('platform.shop.merchant.list_all'),
)

const canInitiate = computed(() =>
  auth.hasAnyPlatformShopPermission(['platform.shop.onboarding.initiate']),
)
const canManage = computed(() => auth.hasPlatformShopPermission('platform.shop.merchant.manage'))
const canAssign = computed(() => auth.hasPlatformShopPermission('platform.shop.merchant.assign'))
const canTag = computed(() => auth.hasPlatformShopPermission('platform.shop.merchant.tag'))
const tagOptions = ref([])
const assignVisible = ref(false)
const tagsVisible = ref(false)
const actionTarget = ref(null)
const selectedRows = ref([])
const assignTargets = ref([])

const SUSPEND_REASONS = [
  { code: 'violation', label: '违规' },
  { code: 'arrears', label: '欠费' },
  { code: 'merchant_request', label: '商家申请' },
  { code: 'other', label: '其他' },
]
const CLOSE_REASONS = [
  { code: 'violation', label: '违规' },
  { code: 'contract_end', label: '合同到期' },
  { code: 'merchant_request', label: '商家申请' },
  { code: 'fraud', label: '欺诈' },
  { code: 'other', label: '其它' },
]

const statusTarget = ref(null)
const statusActing = ref(false)
const suspendVisible = ref(false)
const resumeVisible = ref(false)
const closeVisible = ref(false)
const suspendForm = ref({ reason_code: 'violation', reason_text: '' })
const resumeNote = ref('')
const closeForm = ref({ reason_code: 'violation', reason_text: '', ack_irreversible: false })

const resumeWarnNoPlan = computed(() => {
  const row = statusTarget.value
  if (!row) return false
  return !row.plan_label || row.plan_status === 'expired'
})

const tabs = computed(() => {
  const list = [
    { name: 'all', label: '全部商家' },
    { name: 'my_clients', label: '我的客户' },
    { name: 'reviewing', label: '待审入驻' },
    { name: 'expiring_soon', label: '即将到期' },
    { name: 'expired', label: '已到期' },
    { name: 'suspended', label: '已暂停' },
  ]
  if (!canListAll.value) {
    return list.filter((t) => t.name !== 'all')
  }
  return list
})

const visibleColumns = ref(loadColumnSettings())

const drawerVisible = ref(false)
const submitting = ref(false)
const tenantOptions = ref([])
const tenantSearch = ref('')
const fileNames = ref({})
const form = ref({
  tenant_id: '',
  entity_type: 'enterprise',
  legal_name: '',
  display_name: '',
  contact_name: '',
  contact_mobile: '',
  id_no: '',
  unified_social_credit_code: '',
  legal_rep_name: '',
  remark: '',
  qualification_files: {},
  ocr_results: [],
})

const entityTypeLabel = {
  personal: '个人',
  individual_business: '个体工商户',
  enterprise: '企业',
}

const onboardingStatusLabel = {
  active: '正常',
  suspended: '已暂停',
  closed: '已清退',
  reviewing: '审核中',
  not_onboarded: '未入驻',
}

const onboardingStatusTagType = {
  active: 'success',
  suspended: 'warning',
  closed: 'info',
  reviewing: 'warning',
  not_onboarded: 'info',
}

const planStatusLabel = {
  active: '生效中',
  expiring_soon: '即将到期',
  expired: '已到期',
}

const planStatusTagType = {
  active: 'success',
  expiring_soon: 'warning',
  expired: 'info',
}

const planLabelOptions = ['体验版', '基础版', '旗舰版', '免费版']
const feeTierOptions = ['标准', '优惠']

function loadColumnSettings() {
  const defaults = ALL_COLUMNS.filter((c) => c.defaultVisible).map((c) => c.key)
  try {
    const raw = localStorage.getItem(COLUMN_STORAGE_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed) || !parsed.length) return defaults
    const valid = parsed.filter((key) => ALL_COLUMNS.some((c) => c.key === key))
    const known = new Set(valid)
    for (const col of ALL_COLUMNS) {
      if ((col.locked || col.defaultVisible) && !known.has(col.key)) valid.push(col.key)
    }
    return valid
  } catch {
    return defaults
  }
}

function buildColumnDraft() {
  const hidden = ALL_COLUMNS.map((c) => c.key).filter((k) => !visibleColumns.value.includes(k))
  const orderedKeys = [...visibleColumns.value, ...hidden]
  return orderedKeys.map((key) => {
    const col = ALL_COLUMNS.find((c) => c.key === key)
    return {
      field_key: key,
      label: col.label,
      visible: visibleColumns.value.includes(key),
      list_locked: !!col.locked,
    }
  })
}

function saveColumnSettings() {
  visibleColumns.value = columnDraft.value
    .filter((c) => c.visible || c.list_locked)
    .map((c) => c.field_key)
  localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(visibleColumns.value))
  columnDialogVisible.value = false
  ElMessage.success('列设置已保存')
}

function openColumnSettings() {
  columnDraft.value = buildColumnDraft()
  columnDialogVisible.value = true
}


function fileIdOf(docType) {
  return form.value.qualification_files?.[docType] || ''
}

function fileNameOf(docType) {
  return fileNames.value[docType] || ''
}

async function platformUpload(docType, file) {
  if (!form.value.tenant_id) {
    throw new Error('请先选择关联租户再上传材料')
  }
  const { data } = await adminApi.uploadShopOnboardingFile(form.value.tenant_id, docType, file)
  return data
}

async function platformOcr(payload) {
  if (!form.value.tenant_id) {
    throw new Error('请先选择关联租户再识别')
  }
  const { data } = await adminApi.shopOnboardingOcr({
    ...payload,
    tenant_id: form.value.tenant_id,
  })
  return data
}

function onMaterialUploaded({ docType, fileId, fileName }) {
  form.value.qualification_files = {
    ...form.value.qualification_files,
    [docType]: fileId,
  }
  fileNames.value = { ...fileNames.value, [docType]: fileName }
}

function onMaterialCleared({ docType }) {
  const next = { ...form.value.qualification_files }
  delete next[docType]
  form.value.qualification_files = next
  const names = { ...fileNames.value }
  delete names[docType]
  fileNames.value = names
  form.value.ocr_results = (form.value.ocr_results || []).filter((r) => r.doc_type !== docType)
}

function onOcrFilled({ docType, fileId, fields, confidence, stub, raw }) {
  form.value.ocr_results = [
    ...(form.value.ocr_results || []).filter((r) => r.doc_type !== docType),
    {
      doc_type: docType,
      file_id: fileId,
      fields: fields || {},
      confidence,
      stub,
      ...(raw || {}),
    },
  ]
  if (docType === 'id_card_front') {
    if (fields.name) form.value.legal_name = fields.name
    if (fields.id_no) form.value.id_no = fields.id_no
  }
  if (docType === 'legal_id_front' && fields.name) {
    form.value.legal_rep_name = fields.name
  }
  if (docType === 'business_license') {
    if (fields.legal_name) form.value.legal_name = fields.legal_name
    if (fields.unified_social_credit_code) {
      form.value.unified_social_credit_code = fields.unified_social_credit_code
    }
    if (fields.legal_rep_name) form.value.legal_rep_name = fields.legal_rep_name
  }
}

function daysUntilBenefits(row) {
  if (!row?.benefits_until) return null
  const target = parseApiDateTime(row.benefits_until)
  if (!target) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.ceil((target.getTime() - today.getTime()) / 86400000)
}

function formatBenefitsCell(row) {
  if (!row.benefits_until) {
    if (row.plan_label && String(row.plan_label).includes('免费')) {
      return { text: '永久' }
    }
    return { text: '—' }
  }
  const days = daysUntilBenefits(row)
  const dateText = formatDate(row.benefits_until)
  if (row.plan_status === 'expired' || (days != null && days < 0)) {
    return { expired: true, text: `已到期 · ${dateText}` }
  }
  if (days != null && days >= 0 && days <= 7) {
    return { urgent: true, text: `剩 ${days} 天 · ${dateText}` }
  }
  return { text: dateText }
}

function formatStoreCount(row) {
  const active = row.store_count_active
  const quota = row.store_quota
  if (active == null && quota == null) return '—'
  return `${active ?? '—'}/${quota ?? '—'}`
}

function rowClassName({ row }) {
  if (row.onboarding_status === 'suspended') return 'row-muted'
  const days = daysUntilBenefits(row)
  if (days != null && days >= 0 && days <= 7 && row.plan_status !== 'expired') {
    return 'row-warn'
  }
  return ''
}

function buildListParams() {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    include_not_onboarded: true,
  }
  const q = searchQ.value.trim()
  if (q) params.q = q
  if (activeTab.value && activeTab.value !== 'all') params.tab = activeTab.value

  const f = advFilters.value
  if (f.entity_type) params.entity_type = f.entity_type
  if (f.onboarding_status) params.onboarding_status = f.onboarding_status
  if (f.plan_status) params.plan_status = f.plan_status
  if (f.plan_label) params.plan_label = f.plan_label
  if (f.fee_tier) params.fee_tier = f.fee_tier
  if (f.benefits_range?.[0]) params.benefits_from = f.benefits_range[0]
  if (f.benefits_range?.[1]) params.benefits_until = f.benefits_range[1]
  if (f.store_count_min != null && f.store_count_min !== '') {
    params.store_count_min = Number(f.store_count_min)
  }
  if (f.store_count_max != null && f.store_count_max !== '') {
    params.store_count_max = Number(f.store_count_max)
  }
  if (f.created_range?.[0]) params.created_from = f.created_range[0]
  if (f.created_range?.[1]) params.created_until = f.created_range[1]
  if (sortBy.value) {
    params.sort_by = sortBy.value
    params.sort_dir = sortDir.value || 'desc'
  }
  if (tagFilter.value?.length) {
    params.tag_ids = tagFilter.value.join(',')
  }

  return params
}


async function loadList() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopMerchants(buildListParams())
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

async function handleExport(mode) {
  exporting.value = true
  try {
    const body = { ...buildListParams() }
    delete body.page
    delete body.page_size
    if (mode === 'columns') {
      body.columns = visibleColumns.value.filter((k) => k !== 'ops')
    }
    const { data } = await adminApi.createShopMerchantExport(body)
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
    const res = await adminApi.getShopMerchantExportFile(exportTask.value.id)
    const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-merchants.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function onTabChange(name) {
  activeTab.value = name
  page.value = 1
  loadList()
}

function onSearch() {
  page.value = 1
  loadList()
}

function resetAdvFilters() {
  advFilters.value = {
    ...advFilters.value,
    plan_status: '',
    plan_label: '',
    fee_tier: '',
    benefits_range: null,
    store_count_min: null,
    store_count_max: null,
    created_range: null,
  }
  tagFilter.value = []
  page.value = 1
  loadList()
}

function resetAllFilters() {
  searchQ.value = ''
  advFilters.value.entity_type = ''
  advFilters.value.onboarding_status = ''
  resetAdvFilters()
}

function goDetail(row) {
  router.push(`/admin/shop/merchants/${row.tenant_id}`)
}

function goEntitlements(row) {
  router.push(`/admin/shop/merchants/${row.tenant_id}?tab=entitlements`)
}

function goOnboardingReview(row) {
  const query = {}
  if (row.onboarding_application_id) query.id = row.onboarding_application_id
  router.push({ path: '/admin/shop/onboarding', query })
}

function merchantTitle(row) {
  return row?.display_name || row?.legal_name || row?.tenant_name || '该商家'
}

function openSuspend(row) {
  statusTarget.value = row
  suspendForm.value = { reason_code: 'violation', reason_text: '' }
  suspendVisible.value = true
}

function openResume(row) {
  statusTarget.value = row
  resumeNote.value = ''
  resumeVisible.value = true
}

function openClose(row) {
  statusTarget.value = row
  closeForm.value = { reason_code: 'violation', reason_text: '', ack_irreversible: false }
  closeVisible.value = true
}

function openAssign(row) {
  actionTarget.value = row
  assignTargets.value = row ? [row] : []
  assignVisible.value = true
}

function onSelectionChange(rows) {
  selectedRows.value = rows || []
}

function openBatchAssign() {
  const rows = selectedRows.value
  if (!rows.length) {
    ElMessage.warning('请先勾选商家')
    return
  }
  if (rows.length > 50) {
    ElMessage.warning('单次最多分配 50 家')
    return
  }
  if (rows.some((r) => !['active', 'suspended', 'not_onboarded'].includes(r.onboarding_status))) {
    ElMessage.warning('所选含不可分配商家')
    return
  }
  assignTargets.value = rows
  actionTarget.value = rows[0]
  assignVisible.value = true
}

const assignTenantIds = computed(() => assignTargets.value.map((r) => r.tenant_id).filter(Boolean))
const assignDisplayName = computed(() => {
  if (assignTargets.value.length > 1) return `已选 ${assignTargets.value.length} 家`
  return merchantTitle(assignTargets.value[0] || actionTarget.value)
})

function openTags(row) {
  actionTarget.value = row
  tagsVisible.value = true
}

function canAssignRow(row) {
  return (
    canAssign.value &&
    ['active', 'suspended', 'not_onboarded'].includes(row.onboarding_status)
  )
}

function canTagRow(row) {
  return canTag.value && ['active', 'suspended'].includes(row.onboarding_status)
}

async function confirmSuspend() {
  if (!statusTarget.value) return
  if ((suspendForm.value.reason_text || '').trim().length < 4) {
    ElMessage.warning('说明至少 4 个字')
    return
  }
  statusActing.value = true
  try {
    await adminApi.suspendShopMerchant(statusTarget.value.tenant_id, {
      reason_code: suspendForm.value.reason_code,
      reason_text: suspendForm.value.reason_text.trim(),
    })
    ElMessage.success('已暂停')
    suspendVisible.value = false
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '暂停失败')
  } finally {
    statusActing.value = false
  }
}

async function confirmResume() {
  if (!statusTarget.value) return
  statusActing.value = true
  try {
    await adminApi.resumeShopMerchant(statusTarget.value.tenant_id, {
      note: (resumeNote.value || '').trim() || undefined,
    })
    ElMessage.success('已恢复')
    resumeVisible.value = false
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '恢复失败')
  } finally {
    statusActing.value = false
  }
}

async function confirmClose() {
  if (!statusTarget.value) return
  if ((closeForm.value.reason_text || '').trim().length < 4) {
    ElMessage.warning('说明至少 4 个字')
    return
  }
  if (!closeForm.value.ack_irreversible) {
    ElMessage.warning('须确认不可恢复')
    return
  }
  statusActing.value = true
  try {
    await adminApi.closeShopMerchant(statusTarget.value.tenant_id, {
      reason_code: closeForm.value.reason_code,
      reason_text: closeForm.value.reason_text.trim(),
      ack_irreversible: true,
    })
    ElMessage.success('已清退')
    closeVisible.value = false
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '清退失败')
  } finally {
    statusActing.value = false
  }
}

async function openInitiate(prefillTenantId) {
  if (!canInitiate.value) {
    ElMessage.warning('无发起入驻权限')
    return
  }
  form.value = {
    tenant_id: '',
    entity_type: 'enterprise',
    legal_name: '',
    display_name: '',
    contact_name: '',
    contact_mobile: '',
    id_no: '',
    unified_social_credit_code: '',
    legal_rep_name: '',
    remark: '',
    qualification_files: {},
    ocr_results: [],
  }
  fileNames.value = {}
  drawerVisible.value = true
  await loadTenantOptions()
  if (prefillTenantId) {
    form.value.tenant_id = prefillTenantId
    await onTenantPick(prefillTenantId)
  }
}

async function loadTenantOptions() {
  try {
    const { data } = await adminApi.listShopOnboardingTenantOptions({
      q: tenantSearch.value.trim() || undefined,
      limit: 30,
    })
    tenantOptions.value = data.items ?? []
  } catch (e) {
    tenantOptions.value = []
    ElMessage.error(e.message || '加载租户候选失败')
  }
}

async function onTenantPick(tenantId) {
  if (!tenantId) return
  try {
    const { data } = await adminApi.getShopOnboardingPrefill(tenantId)
    form.value.legal_name = data.legal_name || ''
    form.value.display_name = data.display_name || ''
    form.value.unified_social_credit_code = data.unified_social_credit_code || ''
  } catch (e) {
    ElMessage.error(e.message || '预填失败')
  }
}

async function submitInitiate() {
  if (!form.value.tenant_id) {
    ElMessage.warning('请选择租户')
    return
  }
  if (!form.value.legal_name?.trim() || !form.value.contact_name?.trim() || !form.value.contact_mobile?.trim()) {
    ElMessage.warning('请填写主体名称、经营联系人与联系电话')
    return
  }
  if (form.value.entity_type === 'personal') {
    if (!form.value.id_no?.trim()) {
      ElMessage.warning('请填写身份证号')
      return
    }
    if (!fileIdOf('id_card_front')) {
      ElMessage.warning('请先选择并上传身份证正面')
      return
    }
    if (!fileIdOf('id_card_back')) {
      ElMessage.warning('请先选择并上传身份证反面')
      return
    }
  } else {
    if (!form.value.unified_social_credit_code?.trim() || !form.value.legal_rep_name?.trim()) {
      ElMessage.warning('请填写统一社会信用代码与法定代表人')
      return
    }
    if (!fileIdOf('business_license')) {
      ElMessage.warning('请先选择并上传营业执照')
      return
    }
    if (!fileIdOf('legal_id_front')) {
      ElMessage.warning('请先选择并上传法人身份证正面')
      return
    }
    if (!fileIdOf('legal_id_back')) {
      ElMessage.warning('请先选择并上传法人身份证反面')
      return
    }
  }
  submitting.value = true
  try {
    await adminApi.createShopOnboardingApplication({
      tenant_id: form.value.tenant_id,
      entity_type: form.value.entity_type,
      legal_name: form.value.legal_name,
      display_name: form.value.display_name || undefined,
      contact_name: form.value.contact_name,
      contact_mobile: form.value.contact_mobile,
      id_no: form.value.id_no || undefined,
      unified_social_credit_code: form.value.unified_social_credit_code || undefined,
      legal_rep_name: form.value.legal_rep_name || undefined,
      remark: form.value.remark || undefined,
      qualification_files: form.value.qualification_files || {},
      ocr_results: form.value.ocr_results || [],
    })
    ElMessage.success('已提交入驻申请，待审核')
    drawerVisible.value = false
    loadList()
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

watch(tenantSearch, () => {
  loadTenantOptions()
})

onMounted(() => {
  if (route.query.tab) {
    const tab = String(route.query.tab)
    if (tabs.value.some((t) => t.name === tab)) {
      activeTab.value = tab
    }
  } else if (!canListAll.value) {
    activeTab.value = 'my_clients'
  }
  if (route.query.q) {
    searchQ.value = String(route.query.q)
  }
  loadTagOptions()
  loadList()
})

async function loadTagOptions() {
  try {
    const { data } = await adminApi.listShopMerchantTags()
    tagOptions.value = data.items || []
  } catch {
    tagOptions.value = []
  }
}
</script>

<template>
  <div class="page-card" data-testid="shop-merchants">
    <el-tabs :model-value="activeTab" @tab-change="onTabChange">
      <el-tab-pane v-for="t in tabs" :key="t.name" :label="t.label" :name="t.name" />
    </el-tabs>

    <div class="toolbar">
      <el-input
        v-model="searchQ"
        clearable
        placeholder="商家名 / 商家编码"
        style="width: 240px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-select
        v-model="advFilters.entity_type"
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
        v-model="advFilters.onboarding_status"
        clearable
        placeholder="入驻状态"
        style="width: 130px"
        @change="onSearch"
      >
        <el-option label="未入驻" value="not_onboarded" />
        <el-option label="审核中" value="reviewing" />
        <el-option label="正常" value="active" />
        <el-option label="已暂停" value="suspended" />
        <el-option label="已清退" value="closed" />
      </el-select>
      <el-button :type="advExpanded ? 'primary' : 'default'" plain @click="advExpanded = !advExpanded">
        高级筛选 {{ advExpanded ? '▴' : '▾' }}
      </el-button>
      <div class="toolbar-spacer" />
      <el-button
        v-if="canAssign"
        data-testid="shop-batch-assign"
        @click="openBatchAssign"
      >
        分配管家
      </el-button>
      <el-dropdown trigger="click" @command="handleExport">
        <el-button :loading="exporting">
          导出 ▾
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
            <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button @click="openColumnSettings">列设置</el-button>
      <el-button v-if="canInitiate" type="primary" @click="openInitiate()">
        + 帮客户开通商城
      </el-button>
    </div>

    <div v-show="advExpanded" class="adv-panel">
      <div class="adv-panel-title">高级筛选</div>
      <div class="adv-grid">
        <el-select v-model="advFilters.plan_status" clearable placeholder="套餐状态" style="width: 130px">
          <el-option label="生效中" value="active" />
          <el-option label="即将到期" value="expiring_soon" />
          <el-option label="已到期" value="expired" />
        </el-select>
        <el-select
          v-model="advFilters.plan_label"
          clearable
          filterable
          allow-create
          default-first-option
          placeholder="当前套餐"
          style="width: 140px"
        >
          <el-option v-for="opt in planLabelOptions" :key="opt" :label="opt" :value="opt" />
        </el-select>
        <el-select
          v-model="advFilters.fee_tier"
          clearable
          filterable
          allow-create
          default-first-option
          placeholder="费率档"
          style="width: 120px"
        >
          <el-option v-for="opt in feeTierOptions" :key="opt" :label="opt" :value="opt" />
        </el-select>
      </div>
      <div class="adv-grid">
        <el-date-picker
          v-model="advFilters.benefits_range"
          type="daterange"
          range-separator="—"
          start-placeholder="权益起"
          end-placeholder="权益止"
          value-format="YYYY-MM-DD"
          style="width: 280px"
        />
        <el-input-number
          v-model="advFilters.store_count_min"
          :min="0"
          :controls="false"
          placeholder="店铺数 ≥"
          style="width: 110px"
        />
        <el-input-number
          v-model="advFilters.store_count_max"
          :min="0"
          :controls="false"
          placeholder="店铺数 ≤"
          style="width: 110px"
        />
        <el-date-picker
          v-model="advFilters.created_range"
          type="daterange"
          range-separator="—"
          start-placeholder="创建起"
          end-placeholder="创建止"
          value-format="YYYY-MM-DD"
          style="width: 280px"
        />
        <el-select
          v-model="tagFilter"
          multiple
          collapse-tags
          collapse-tags-tooltip
          filterable
          clearable
          placeholder="标签"
          style="width: 200px"
        >
          <el-option v-for="tag in tagOptions" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
      </div>
      <div class="adv-actions">
        <el-button type="primary" @click="onSearch">查询</el-button>
        <el-button @click="resetAdvFilters">重置</el-button>
        <el-button link type="primary" @click="resetAllFilters">清空全部筛选</el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="items"
      stripe
      row-key="tenant_id"
      :row-class-name="rowClassName"
      style="margin-top: 4px"
      @selection-change="onSelectionChange"
    >
      <el-table-column v-if="canAssign" type="selection" width="42" :reserve-selection="true" />
      <template v-for="colKey in visibleColumns" :key="colKey">
      <el-table-column
        v-if="colKey === 'display_name'"
        prop="display_name"
        min-width="160"
        fixed="left"
      >
        <template #header>
          <button type="button" class="th-sort" @click="toggleSort('display_name')">
            商家 <span class="sort-ico">{{ sortIcon('display_name') }}</span>
          </button>
        </template>
        <template #default="{ row }">
          <div class="merchant-cell-main">{{ row.display_name || '—' }}</div>
          <div v-if="row.tenant_name" class="merchant-cell-sub">{{ row.tenant_name }}</div>
        </template>
      </el-table-column>

      <el-table-column
        v-if="colKey === 'merchant_code'"
        prop="merchant_code"
        min-width="130"
        show-overflow-tooltip
      >
        <template #header>
          <button type="button" class="th-sort" @click="toggleSort('merchant_code')">
            商家编码 <span class="sort-ico">{{ sortIcon('merchant_code') }}</span>
          </button>
        </template>
        <template #default="{ row }">
          <span v-if="row.merchant_code">{{ row.merchant_code }}</span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column v-if="colKey === 'entity_type'" label="主体" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.entity_type" size="small" type="info">
            {{ entityTypeLabel[row.entity_type] || row.entity_type }}
          </el-tag>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column v-if="colKey === 'plan_label'" label="当前套餐" width="120">
        <template #default="{ row }">{{ row.plan_label || '—' }}</template>
      </el-table-column>

      <el-table-column v-if="colKey === 'plan_status'" label="套餐状态" width="110">
        <template #default="{ row }">
          <el-tag
            v-if="row.plan_status"
            size="small"
            :type="planStatusTagType[row.plan_status] || 'info'"
          >
            {{ planStatusLabel[row.plan_status] || row.plan_status }}
          </el-tag>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column
        v-if="colKey === 'benefits_until'"
        prop="benefits_until"
        width="170"
      >
        <template #header>
          <button type="button" class="th-sort" @click="toggleSort('benefits_until')">
            权益至 <span class="sort-ico">{{ sortIcon('benefits_until') }}</span>
          </button>
        </template>
        <template #default="{ row }">
          <span
            v-if="formatBenefitsCell(row).urgent"
            class="benefits-urgent"
          >
            {{ formatBenefitsCell(row).text }}
          </span>
          <span
            v-else-if="formatBenefitsCell(row).expired"
            class="benefits-expired"
          >
            {{ formatBenefitsCell(row).text }}
          </span>
          <span v-else>{{ formatBenefitsCell(row).text }}</span>
        </template>
      </el-table-column>

      <el-table-column
        v-if="colKey === 'store_count'"
        prop="store_count"
        width="100"
        align="center"
      >
        <template #header>
          <button type="button" class="th-sort" @click="toggleSort('store_count')">
            店铺数 <span class="sort-ico">{{ sortIcon('store_count') }}</span>
          </button>
        </template>
        <template #default="{ row }">{{ formatStoreCount(row) }}</template>
      </el-table-column>

      <el-table-column v-if="colKey === 'account_manager_name'" label="商家管家" width="110">
        <template #default="{ row }">
          {{ row.account_manager_name || '未分配' }}
        </template>
      </el-table-column>

      <el-table-column v-if="colKey === 'tags'" label="标签" min-width="140">
        <template #default="{ row }">
          <template v-if="row.tags?.length">
            <el-tag
              v-for="tag in row.tags"
              :key="tag"
              size="small"
              style="margin: 2px 4px 2px 0"
            >
              {{ tag }}
            </el-tag>
          </template>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column
        v-if="colKey === 'created_at'"
        prop="created_at"
        width="180"
      >
        <template #header>
          <button type="button" class="th-sort" @click="toggleSort('created_at')">
            创建时间 <span class="sort-ico">{{ sortIcon('created_at') }}</span>
          </button>
        </template>
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>

      <el-table-column v-if="colKey === 'onboarding_status'" label="入驻状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="onboardingStatusTagType[row.onboarding_status] || 'info'">
            {{ onboardingStatusLabel[row.onboarding_status] || row.onboarding_status }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column v-if="colKey === 'ops'" label="操作" min-width="360" fixed="right">
        <template #default="{ row }">
          <template v-if="row.onboarding_status === 'not_onboarded'">
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
            <el-button
              v-if="canInitiate"
              link
              type="primary"
              size="small"
              @click="openInitiate(row.tenant_id)"
            >
              发起入驻
            </el-button>
            <el-button v-if="canAssignRow(row)" link type="primary" size="small" @click="openAssign(row)">
              分配管家
            </el-button>
          </template>

          <template v-else-if="row.onboarding_status === 'reviewing'">
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
            <el-button link type="primary" size="small" @click="goOnboardingReview(row)">
              查看入驻
            </el-button>
          </template>

          <template v-else-if="row.onboarding_status === 'active'">
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
            <el-button link type="primary" size="small" @click="goEntitlements(row)">当前权益</el-button>
            <el-button v-if="canAssignRow(row)" link type="primary" size="small" @click="openAssign(row)">
              分配管家
            </el-button>
            <el-button v-if="canTagRow(row)" link type="primary" size="small" @click="openTags(row)">
              编辑标签
            </el-button>
            <el-button v-if="canManage" link type="warning" size="small" @click="openSuspend(row)">
              暂停
            </el-button>
            <el-button v-if="canManage" link type="danger" size="small" @click="openClose(row)">
              清退
            </el-button>
          </template>

          <template v-else-if="row.onboarding_status === 'suspended'">
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
            <el-button v-if="canAssignRow(row)" link type="primary" size="small" @click="openAssign(row)">
              分配管家
            </el-button>
            <el-button v-if="canTagRow(row)" link type="primary" size="small" @click="openTags(row)">
              编辑标签
            </el-button>
            <el-button v-if="canManage" link type="primary" size="small" @click="openResume(row)">
              恢复
            </el-button>
            <el-button v-if="canManage" link type="danger" size="small" @click="openClose(row)">
              清退
            </el-button>
          </template>

          <template v-else>
            <el-button link type="primary" size="small" @click="goDetail(row)">详情</el-button>
          </template>

          <span v-if="row.has_pending_renewal" class="renewal-tip">续费申请中</span>
        </template>
      </el-table-column>
      </template>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        background
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        @current-change="loadList"
        @size-change="() => { page = 1; loadList() }"
      />
    </div>

    <CrmColumnSettingsDialog
      v-model:visible="columnDialogVisible"
      v-model:columns="columnDraft"
      @save="saveColumnSettings"
    />

    <el-drawer v-model="drawerVisible" title="发起入驻" size="520px">
      <el-form label-position="top">
        <el-form-item label="关联租户" required>
          <el-select
            v-model="form.tenant_id"
            filterable
            remote
            :remote-method="(q) => { tenantSearch = q; loadTenantOptions() }"
            placeholder="搜索租户"
            style="width: 100%"
            @change="onTenantPick"
          >
            <el-option
              v-for="t in tenantOptions"
              :key="t.tenant_id"
              :label="`${t.tenant_name}${t.credit_code ? ' · ' + t.credit_code : ''}`"
              :value="t.tenant_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="主体类型" required>
          <el-radio-group v-model="form.entity_type">
            <el-radio-button value="personal">个人</el-radio-button>
            <el-radio-button value="individual_business">个体工商户</el-radio-button>
            <el-radio-button value="enterprise">企业</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item
          :label="form.entity_type === 'personal' ? '主体名称' : '主体名称（执照名）'"
          required
        >
          <el-input v-model="form.legal_name" />
        </el-form-item>
        <el-form-item label="商家展示名" required>
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="经营联系人" required>
          <el-input v-model="form.contact_name" />
        </el-form-item>
        <el-form-item label="联系电话" required>
          <el-input v-model="form.contact_mobile" maxlength="11" />
        </el-form-item>
        <el-form-item v-if="form.entity_type === 'personal'" label="身份证号" required>
          <el-input v-model="form.id_no" />
        </el-form-item>
        <template v-else>
          <el-form-item label="统一社会信用代码" required>
            <el-input v-model="form.unified_social_credit_code" />
          </el-form-item>
          <el-form-item label="法定代表人" required>
            <el-input v-model="form.legal_rep_name" />
          </el-form-item>
        </template>

        <el-form-item label="材料" required>
          <p class="form-tip">请先选择关联租户，再选择文件上传</p>
          <div class="materials-list">
            <template v-if="form.entity_type === 'personal'">
              <ShopMaterialUpload
                doc-type="id_card_front"
                title="身份证正面"
                required
                ocr-enabled
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('id_card_front')"
                :file-name="fileNameOf('id_card_front')"
                :upload-fn="platformUpload"
                :ocr-fn="platformOcr"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="id_card_back"
                title="身份证反面"
                required
                ocr-enabled
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('id_card_back')"
                :file-name="fileNameOf('id_card_back')"
                :upload-fn="platformUpload"
                :ocr-fn="platformOcr"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="handheld"
                title="手持照"
                optional
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('handheld')"
                :file-name="fileNameOf('handheld')"
                :upload-fn="platformUpload"
                @uploaded="onMaterialUploaded"
                @cleared="onMaterialCleared"
              />
            </template>
            <template v-else>
              <ShopMaterialUpload
                doc-type="business_license"
                title="营业执照"
                required
                ocr-enabled
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('business_license')"
                :file-name="fileNameOf('business_license')"
                :upload-fn="platformUpload"
                :ocr-fn="platformOcr"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="legal_id_front"
                title="法人身份证正面"
                required
                ocr-enabled
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('legal_id_front')"
                :file-name="fileNameOf('legal_id_front')"
                :upload-fn="platformUpload"
                :ocr-fn="platformOcr"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="legal_id_back"
                title="法人身份证反面"
                required
                ocr-enabled
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('legal_id_back')"
                :file-name="fileNameOf('legal_id_back')"
                :upload-fn="platformUpload"
                :ocr-fn="platformOcr"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                v-if="form.entity_type === 'enterprise'"
                doc-type="bank_permit"
                title="对公账户"
                optional
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('bank_permit')"
                :file-name="fileNameOf('bank_permit')"
                :upload-fn="platformUpload"
                @uploaded="onMaterialUploaded"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                v-if="form.entity_type === 'enterprise'"
                doc-type="icp"
                title="ICP 备案 / 类目资质"
                optional
                :disabled="!form.tenant_id"
                :file-id="fileIdOf('icp')"
                :file-name="fileNameOf('icp')"
                :upload-fn="platformUpload"
                @uploaded="onMaterialUploaded"
                @cleared="onMaterialCleared"
              />
            </template>
          </div>
        </el-form-item>

        <el-form-item label="运营备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-button type="primary" :loading="submitting" @click="submitInitiate">提交待审</el-button>
      </el-form>
    </el-drawer>

    <el-dialog
      v-model="suspendVisible"
      :title="statusTarget ? `确认暂停「${merchantTitle(statusTarget)}」？` : '确认暂停'"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item label="影响说明（只读）">
          <div class="ro">
            商家端不可登录；旗下店铺强制不可营业；买家端展示「暂停营业」；进行中订单仍可履约/退款
          </div>
        </el-form-item>
        <el-form-item label="暂停原因" required>
          <el-select v-model="suspendForm.reason_code" style="width: 100%">
            <el-option v-for="r in SUSPEND_REASONS" :key="r.code" :label="r.label" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input
            v-model="suspendForm.reason_text"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="至少 4 字"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="suspendVisible = false">取消</el-button>
        <el-button type="warning" :loading="statusActing" @click="confirmSuspend">确认暂停</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="resumeVisible"
      :title="statusTarget ? `确认恢复「${merchantTitle(statusTarget)}」？` : '确认恢复'"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item label="恢复后影响（只读）">
          <div class="ro">商家端可登录；店铺需商家自行「恢复营业」（不自动开店）</div>
        </el-form-item>
        <el-form-item v-if="resumeWarnNoPlan" label="告警（只读）">
          <div class="ro warn">当前无生效主套餐 → 建议先开通/续费（仍可强制恢复）</div>
        </el-form-item>
        <el-form-item label="备注（选填）">
          <el-input v-model="resumeNote" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resumeVisible = false">取消</el-button>
        <el-button type="primary" :loading="statusActing" @click="confirmResume">确认恢复</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="closeVisible"
      :title="statusTarget ? `确认清退「${merchantTitle(statusTarget)}」？` : '确认清退'"
      width="520px"
    >
      <el-form label-position="top">
        <el-form-item label="原因码" required>
          <el-select v-model="closeForm.reason_code" style="width: 100%">
            <el-option v-for="r in CLOSE_REASONS" :key="r.code" :label="r.label" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input
            v-model="closeForm.reason_text"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="至少 4 字"
          />
        </el-form-item>
        <el-form-item label="影响（只读）">
          <div class="ro">
            商家禁登 · 全店强制暂停 · 买家新购拦截 · 已购履约不撤销 · 套餐继续倒计时 · 续费申请全禁 · pending
            续费自动取消
          </div>
        </el-form-item>
        <el-form-item label="确认">
          <el-checkbox v-model="closeForm.ack_irreversible">我已知晓清退不可恢复</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeVisible = false">取消</el-button>
        <el-button type="danger" :loading="statusActing" @click="confirmClose">确认清退</el-button>
      </template>
    </el-dialog>

    <ShopAssignManagerDialog
      v-model="assignVisible"
      :tenant-ids="assignTenantIds"
      :display-name="assignDisplayName"
      :current-manager-id="actionTarget?.account_manager_user_id || ''"
      :current-manager-name="actionTarget?.account_manager_name || ''"
      @success="loadList"
    />
    <ShopMerchantTagsDialog
      v-model="tagsVisible"
      :tenant-id="actionTarget?.tenant_id"
      :display-name="merchantTitle(actionTarget)"
      :selected="actionTarget?.tags || []"
      @success="loadList"
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
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
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

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.merchant-cell-main {
  font-weight: 500;
  line-height: 1.4;
}

.merchant-cell-sub {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 2px;
  line-height: 1.3;
}

.text-muted {
  color: #8c8c8c;
}

.benefits-urgent {
  color: #cf1322;
  font-weight: 600;
}

.benefits-expired {
  color: #8c8c8c;
}

.renewal-tip {
  font-size: 12px;
  color: #d46b08;
  margin-left: 6px;
}

.form-tip {
  margin: 0 0 8px;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.4;
}

.materials-list {
  width: 100%;
}

:deep(.el-table .row-warn > td.el-table__cell) {
  background-color: #fffbe6 !important;
}

:deep(.el-table .row-muted > td.el-table__cell) {
  background-color: #fafafa !important;
}

:deep(.el-table--striped .el-table__body tr.row-warn.el-table__row--striped > td.el-table__cell) {
  background-color: #fffbe6 !important;
}

:deep(.el-table--striped .el-table__body tr.row-muted.el-table__row--striped > td.el-table__cell) {
  background-color: #fafafa !important;
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

.ro {
  color: #606266;
  line-height: 1.5;
}

.warn {
  background: #fffbe6;
  padding: 8px 10px;
  border-radius: 4px;
}
</style>
