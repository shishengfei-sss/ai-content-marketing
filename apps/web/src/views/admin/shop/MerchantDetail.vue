<script setup>
/** 对照 PRD：06-平台端UI.html #p02b-overview · #p02b-entitlements · #p02b-stores · #p02b-materials · #p02b-payment · #p02b-service · #p02b-note · #p02b-renewal · #p02b-audit · #p02e · #p02b-tags
 * 缺口：站内信。暂停/恢复/清退仅列表行内（详情头不设入口）。标签字典治理（重命名/归档）为后续版本。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../../api/client'
import { formatDateTime } from '../../../utils/datetime'
import { useAuthStore } from '../../../stores/auth'
import ShopPaymentOnboardingPanel from '../../../components/shop/ShopPaymentOnboardingPanel.vue'
import ShopAssignManagerDialog from '../../../components/shop/ShopAssignManagerDialog.vue'
import ShopMerchantTagsDialog from '../../../components/shop/ShopMerchantTagsDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const detail = ref(null)
const activeTab = ref('overview')
const payment = ref(null)
const paymentActing = ref(false)
const canChannel = computed(() => auth.hasPlatformShopPermission('platform.shop.channel'))

const statusLabel = {
  active: '正常',
  suspended: '已暂停',
  closed: '已清退',
  reviewing: '审核中',
  not_onboarded: '未入驻',
}

const entityLabel = {
  personal: '个人',
  individual_business: '个体工商户',
  enterprise: '企业',
}

const planStatusLabel = {
  active: '生效中',
  expiring_soon: '即将到期',
  expired: '已到期',
}

const statusTagType = {
  active: 'success',
  suspended: 'warning',
  closed: 'info',
  reviewing: 'warning',
  not_onboarded: 'info',
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

const merchantCode = computed(() => detail.value?.merchant_code || '—')

const materialEntries = computed(() => {
  const files = detail.value?.onboarding_materials?.qualification_files || {}
  return Object.entries(files).map(([key, fileId]) => ({
    key,
    label: materialLabels[key] || key,
    fileId: String(fileId || ''),
  }))
})

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.getShopMerchant(route.params.tenantId)
    detail.value = data
    clearReveal()
    if (route.query.tab && typeof route.query.tab === 'string') {
      activeTab.value = route.query.tab
    }
    if (activeTab.value === 'payment') await loadPayment()
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载失败')
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.tenantId,
  () => load(),
)

async function loadPayment() {
  const tid = route.params.tenantId
  if (!tid) return
  try {
    const { data } = await adminApi.getShopPaymentOnboarding(tid)
    payment.value = data
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载进件失败')
    payment.value = null
  }
}

async function payRefresh() {
  if (!payment.value) return
  paymentActing.value = true
  try {
    const { data } = await adminApi.refreshShopPaymentOnboarding(payment.value.tenant_id)
    payment.value = data
    ElMessage.success('已刷新')
  } catch (e) {
    ElMessage.error(e.message || '刷新失败')
  } finally {
    paymentActing.value = false
  }
}

async function payReveal() {
  if (!payment.value) return
  try {
    const { data } = await adminApi.revealShopPaymentSensitive(payment.value.tenant_id)
    payment.value = data
  } catch (e) {
    ElMessage.error(e.message || '揭露失败')
  }
}

async function payNotify() {
  if (!payment.value) return
  paymentActing.value = true
  try {
    const { data } = await adminApi.notifyShopPaymentMerchant(payment.value.tenant_id)
    ElMessage.success(data?.message || '已通知商家')
    await loadPayment()
  } catch (e) {
    ElMessage.error(e.message || '通知失败')
  } finally {
    paymentActing.value = false
  }
}

const canManage = computed(() => auth.hasPlatformShopPermission('platform.shop.subscription.manage'))
const canAssign = computed(() => auth.hasPlatformShopPermission('platform.shop.merchant.assign'))
const canTag = computed(() => auth.hasPlatformShopPermission('platform.shop.merchant.tag'))
const isClosed = computed(() => detail.value?.onboarding_status === 'closed')
const canWriteFollow = computed(() => !isClosed.value && !!detail.value?.merchant_id)
const canAssignHere = computed(() =>
  canAssign.value &&
  ['active', 'suspended', 'not_onboarded'].includes(detail.value?.onboarding_status),
)
const canTagHere = computed(() =>
  canTag.value && ['active', 'suspended'].includes(detail.value?.onboarding_status),
)
const assignVisible = ref(false)
const tagsVisible = ref(false)
const revealedMobile = ref('')
const revealedIdNo = ref('')
let revealTimer = null
const subsPack = ref({ items: [], entitlements: {} })
const features = ref([])
const logItems = ref([])
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(20)
const logType = ref('')
const logStatus = ref('')
const logQ = ref('')
const logLoading = ref(false)
const noteVisible = ref(false)
const renewalVisible = ref(false)
const viewLogVisible = ref(false)
const viewLog = ref(null)
const submitting = ref(false)
const plans = ref([])
const noteForm = reactive({
  type: 'call',
  occurred_at: '',
  content: '',
  follow_up_at: '',
})
const renewalForm = reactive({
  application_kind: 'renew_same',
  target_plan: '',
  paid_yuan: 0,
  customer_confirmed: false,
  content: '',
})

const NOTE_TYPES = [
  { value: 'call', label: '电话沟通' },
  { value: 'visit', label: '拜访' },
  { value: 'wechat', label: '微信/企微' },
  { value: 'note', label: '文字备注' },
  { value: 'video', label: '视频会议' },
  { value: 'email', label: '邮件' },
  { value: 'training', label: '培训赋能' },
  { value: 'complaint', label: '投诉客诉' },
  { value: 'onboarding_assist', label: '入驻协助' },
  { value: 'other', label: '其他' },
]
const LOG_TYPE_LABEL = {
  call: '电话沟通',
  visit: '拜访',
  wechat: '微信/企微',
  note: '文字备注',
  video: '视频会议',
  email: '邮件',
  training: '培训赋能',
  complaint: '投诉客诉',
  onboarding_assist: '入驻协助',
  other: '其他',
  renewal_request: '申请续费',
  status_change: '状态变更',
  subscription: '订阅开通',
}
const LOG_STATUS_LABEL = {
  logged: '已记录',
  pending: '待处理',
  processing: '处理中',
  completed: '已完成',
  cancelled: '已取消',
}
const STORE_STATUS = { open: '营业', active: '营业', draft: '未开业', paused: '暂停', closed: '关闭' }
const AGG_LABEL = { max: '取最大', sum: '累加', any: '任一满足' }
const FALLBACK_FEAT = {
  'quota.max_shops': '店铺数',
  'quota.max_products': '在售商品上限',
  'usage.product_review_submit': '每日商品提审',
  'usage.sms_claim_send': '领权短信 / 月',
  'channel.doudian': '抖店公域',
  'feature.invoice': '电子发票',
}

function maskMobile(v) {
  const s = String(v || '')
  if (s.includes('*')) return s || '—'
  if (s.length < 7) return s || '—'
  return `${s.slice(0, 3)}****${s.slice(-4)}`
}

function displayMobile(v) {
  if (revealedMobile.value) return revealedMobile.value
  return maskMobile(v)
}

function displayIdNo(v) {
  if (revealedIdNo.value) return revealedIdNo.value
  const s = String(v || '')
  if (s.includes('*')) return s || '—'
  return maskIdNo(v)
}

function formatGmv(cents) {
  const n = Number(cents) || 0
  return `¥${(n / 100).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}

function bankDisplay(info, fallback) {
  if (fallback) return fallback
  if (!info || !Object.keys(info).length) return '—'
  const bank = info.bank_name || ''
  const tail = info.account_no_masked || ''
  const text = `${bank} ${tail}`.trim()
  return text || '—'
}

const OCR_FIELD_LABEL = {
  name: '姓名',
  legal_name: '执照名',
  id_no: '身份证号',
  unified_social_credit_code: '信用代码',
  legal_rep_name: '法人',
  address: '地址',
  issue_authority: '签发机关',
  valid_from: '有效期起',
  valid_to: '有效期止',
  business_scope: '经营范围',
}

const ocrRows = computed(() => {
  const mats = detail.value?.onboarding_materials
  const list = mats?.ocr_results || []
  const filled = {
    legal_name: mats?.legal_name,
    id_no: mats?.id_no,
    unified_social_credit_code: mats?.unified_social_credit_code,
    legal_rep_name: mats?.legal_rep_name,
    name: mats?.legal_name,
  }
  const rows = []
  for (const item of list) {
    const fields = item.fields || {}
    const conf = item.confidence != null ? Number(item.confidence).toFixed(2) : '—'
    const keys = Object.keys(fields)
    if (!keys.length) {
      rows.push({ field: '—', filled: '—', ocr: '无识别字段', confidence: conf, match: '' })
      continue
    }
    for (const [field, value] of Object.entries(fields)) {
      const ocr = String(value ?? '')
      const filledVal = filled[field] ?? '—'
      const match = filledVal && filledVal !== '—' && String(filledVal) === ocr ? '一致' : ''
      rows.push({
        field: OCR_FIELD_LABEL[field] || field,
        filled: filledVal || '—',
        ocr,
        confidence: conf,
        match,
      })
    }
  }
  return rows
})

function clearReveal() {
  revealedMobile.value = ''
  revealedIdNo.value = ''
  if (revealTimer) {
    clearTimeout(revealTimer)
    revealTimer = null
  }
}

async function revealField(field) {
  if (field === 'contact_mobile' && revealedMobile.value) {
    revealedMobile.value = ''
    return
  }
  if (field === 'id_no' && revealedIdNo.value) {
    revealedIdNo.value = ''
    return
  }
  try {
    const { data } = await adminApi.revealShopMerchantSensitive(route.params.tenantId, { field })
    if (field === 'contact_mobile') revealedMobile.value = data.value
    if (field === 'id_no') revealedIdNo.value = data.value
    if (revealTimer) clearTimeout(revealTimer)
    revealTimer = setTimeout(() => clearReveal(), 5 * 60 * 1000)
  } catch (e) {
    ElMessage.error(e.message || '揭露失败')
  }
}

function nowLocal() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:00`
}

function centsToYuan(c) {
  return ((Number(c) || 0) / 100).toFixed(2)
}

function yuanToCents(v) {
  return Math.round(Number(v || 0) * 100)
}

const activeSubs = computed(() =>
  (subsPack.value.items || []).filter((s) => s.status === 'active'),
)
const mainSub = computed(
  () => activeSubs.value.find((s) => s.plan_type === 'main') || activeSubs.value[0],
)
const selectedRenewPlan = computed(() => plans.value.find((p) => p.code === renewalForm.target_plan))
const filteredRenewPlans = computed(() => {
  if (renewalForm.application_kind === 'stack') {
    return plans.value.filter((p) => p.plan_type === 'addon' && p.stackable)
  }
  if (renewalForm.application_kind === 'replace') {
    const cur = mainSub.value
    const group = cur?.plan_snapshot?.replace_group
    const order = cur?.plan_snapshot?.sort_order ?? 0
    return plans.value.filter(
      (p) => p.plan_type === 'main' && (!group || p.replace_group === group) && (p.sort_order || 0) > order,
    )
  }
  const code = mainSub.value?.plan_code
  return plans.value.filter((p) => p.code === code)
})
const amountLabel = computed(() => {
  if (renewalForm.application_kind === 'stack') return '加购金额'
  if (renewalForm.application_kind === 'replace') return '换档金额'
  return '续费金额'
})
const currentPlanText = computed(() => {
  const d = detail.value
  if (!d) return '—'
  const until = d.benefits_until ? `（${d.benefits_until}）` : ''
  if (d.plan_status === 'expiring_soon') return `${d.plan_label || '套餐'} · 即将到期${until}`
  if (d.plan_status === 'expired') return d.plan_label || '免费版（已到期）'
  return `${d.plan_label || '免费版'} · ${planStatusLabel[d.plan_status] || ''}${until}`
})
const recentLogs = computed(() => (detail.value?.service_logs || []).slice(0, 5))
const collapsedGroups = ref({})
const entitlementRows = computed(() => {
  const ent = subsPack.value.entitlements || {}
  const featMap = Object.fromEntries(features.value.map((f) => [f.code, f]))
  const rows = []
  const push = (bag, kind) => {
    Object.entries(bag || {}).forEach(([code, val]) => {
      const meta = featMap[code] || {}
      rows.push({
        code,
        name: meta.name || FALLBACK_FEAT[code] || code,
        value: val === true || val === 'unlimited' ? '✓' : val,
        used: '—',
        mode: AGG_LABEL[meta.aggregate_mode] || (kind === 'feature' ? '任一满足' : '累加'),
        source: (ent.contributing_plans || []).map((p) => p.plan_name).filter(Boolean).join(' + ') || '—',
        group: meta.category || kind,
      })
    })
  }
  push(ent.quotas, 'quota')
  push(ent.usage_limits, 'usage')
  push(ent.features, 'feature')
  return rows
})
const entitlementGroups = computed(() => {
  const groups = subsPack.value.entitlements?.usage_groups
  if (Array.isArray(groups) && groups.length) return groups
  const rows = entitlementRows.value
  if (!rows.length) return []
  return [{ group: '权益', items: rows }]
})

function toggleGroup(name) {
  collapsedGroups.value = { ...collapsedGroups.value, [name]: !collapsedGroups.value[name] }
}

function isGroupCollapsed(name) {
  return !!collapsedGroups.value[name]
}

function leafName(row) {
  return row?.name || row?.label || '—'
}

function leafValue(row) {
  if (row?.value_display != null && row.value_display !== '') return row.value_display
  if (row?.value != null && row.value !== '') return row.value
  if (row?.limit_label != null && row.limit_label !== '') return row.limit_label
  return '—'
}

function leafUsed(row) {
  if (row?.used_display != null && row.used_display !== '') return row.used_display
  if (row?.used == null || row.used === '—') return '—'
  return row.used
}

function leafMode(row) {
  return row?.aggregate_mode_label || row?.mode || '—'
}
const paymentStatusText = computed(() => {
  const s = payment.value?.onboarding_status
  return (
    {
      not_submitted: '未提交',
      submitted: '审核中',
      approved: '已开通',
      active: '已开通',
      rejected: '已驳回',
    }[s] || s || '未提交'
  )
})

const auditAction = ref('')
const auditQ = ref('')
const auditPage = ref(1)
const auditPageSize = ref(20)
const AUDIT_ACTIONS = [
  '订阅开通',
  '订阅续费',
  '订阅换档',
  '叠加开通',
  '入驻通过',
  '分配管家',
  '暂停',
  '恢复',
  '清退',
  '查看敏感信息',
]
const filteredAuditLogs = computed(() => {
  let rows = detail.value?.operation_logs || []
  if (auditAction.value) rows = rows.filter((r) => r.action === auditAction.value)
  const q = auditQ.value.trim()
  if (q) {
    rows = rows.filter(
      (r) =>
        String(r.summary || '').includes(q) ||
        String(r.operator_name || '').includes(q) ||
        String(r.action || '').includes(q),
    )
  }
  return rows
})
const pagedAuditLogs = computed(() => {
  const start = (auditPage.value - 1) * auditPageSize.value
  return filteredAuditLogs.value.slice(start, start + auditPageSize.value)
})
watch([auditAction, auditQ, auditPageSize], () => {
  auditPage.value = 1
})
const confirmLabel = computed(() => {
  if (renewalForm.application_kind === 'stack') return '已与客户确认加购意向与金额'
  if (renewalForm.application_kind === 'replace') return '已与客户确认换档意向与金额'
  return '已与客户确认续费意向与金额'
})
const targetPlanFieldLabel = computed(() =>
  renewalForm.application_kind === 'stack' ? '目标加购包' : '目标套餐',
)
const expectedPeriodText = computed(() => {
  const p = selectedRenewPlan.value
  if (!p) return '选择目标套餐后按计费周期自动推算；最终以开通时为准'
  const days = p.billing_period === 'monthly' ? 30 : 365
  let start
  if (renewalForm.application_kind === 'stack') {
    start = new Date()
  } else if (detail.value?.benefits_until) {
    start = new Date(`${detail.value.benefits_until}T00:00:00`)
    start.setDate(start.getDate() + 1)
  } else {
    start = new Date()
  }
  const end = new Date(start)
  end.setDate(end.getDate() + days - 1)
  const fmt = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const period = p.billing_period === 'monthly' ? '月' : '年'
  return `${fmt(start)} ～ ${fmt(end)}（按目标套餐 ${period} 周期推算；最终以开通时为准）`
})
const addonSubs = computed(() => activeSubs.value.filter((s) => s.plan_type === 'addon'))
const entitlementSummary = computed(() => {
  const mains = activeSubs.value.filter((s) => s.plan_type === 'main')
  const addons = addonSubs.value
  const mainName = mains[0]?.plan_name || mains[0]?.plan_code || detail.value?.plan_label || '免费版'
  const addonName = addons[0]?.plan_name
  const extra = addons.length > 1 ? ` 等 ${addons.length} 个加购` : addonName ? ` + 加购 ${addonName}` : ''
  return `生效中 ${activeSubs.value.length} 条 · 主套餐 ${mainName}${extra}`
})

function formatDate(v) {
  if (!v) return '—'
  const s = String(v)
  return s.length >= 10 ? s.slice(0, 10) : s
}

function maskIdNo(v) {
  const s = String(v || '')
  if (s.length < 8) return s || '—'
  return `${s.slice(0, 3)}${'*'.repeat(Math.max(s.length - 7, 4))}${s.slice(-4)}`
}

function logTypeLabel(t) {
  return LOG_TYPE_LABEL[t] || t || '—'
}

function logStatusLabel(s) {
  return LOG_STATUS_LABEL[s] || s || '—'
}

function storeStatusLabel(s) {
  return STORE_STATUS[s] || s || '—'
}

function planTypeLabel(row) {
  if (row?.plan_type_label) return row.plan_type_label
  return subPlanType(row) === 'addon' ? '叠加' : '主套餐'
}

function subPlanType(row) {
  if (row?.plan_type) return row.plan_type
  return row?.purchase_mode === 'stack' ? 'addon' : 'main'
}

function canReplaceSub(row) {
  return canManage.value && !isClosed.value && subPlanType(row) === 'main' && row?.status === 'active'
}

function subStatusLabel(row) {
  if (row?.display_status === 'expiring_soon') return '即将到期'
  return row?.status_label || planStatusLabel[row?.status] || row?.status || '—'
}

async function loadEntitlements() {
  const tid = route.params.tenantId
  if (!tid) return
  try {
    const { data } = await adminApi.getShopMerchantSubscriptions(tid)
    subsPack.value = { items: data.items || [], entitlements: data.entitlements || {} }
  } catch {
    subsPack.value = { items: [], entitlements: {} }
  }
}

async function loadPlansAndFeatures() {
  try {
    const [pres, fres] = await Promise.all([
      adminApi.listShopPlanTemplates({ published: true, page_size: 50 }),
      adminApi.listShopFeatureDictionary({ is_active: true }),
    ])
    plans.value = pres.data.items || []
    features.value = Array.isArray(fres.data) ? fres.data : fres.data?.items || []
  } catch {
    plans.value = []
    features.value = []
  }
}

async function loadLogs() {
  const tid = route.params.tenantId
  if (!tid) return
  logLoading.value = true
  try {
    const { data } = await adminApi.listShopMerchantServiceLogs(tid, {
      page: logPage.value,
      page_size: logPageSize.value,
      type: logType.value || undefined,
      status: logStatus.value || undefined,
      q: logQ.value.trim() || undefined,
    })
    logItems.value = data.items || []
    logTotal.value = data.total || 0
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载服务记录失败')
    logItems.value = []
  } finally {
    logLoading.value = false
  }
}

function logOccurred(row) {
  return row?.payload_json?.occurred_at || row?.created_at
}

function recordedText(row) {
  const created = formatDateTime(row?.created_at)
  const updated = row?.updated_at && row.updated_at !== row.created_at ? formatDateTime(row.updated_at) : ''
  if (!created && !updated) return '—'
  if (updated) return `录入 ${created} · 更新 ${updated}`
  return `录入 ${created}`
}

function resolveRowOnboardingId(row) {
  return row?.related_onboarding_id || row?.payload_json?.application_id || null
}

function resolveMerchantOnboardingId() {
  return detail.value?.onboarding_application_id || detail.value?.onboarding_materials?.application_id || null
}

function canViewOnboarding(row) {
  return row?.type === 'onboarding_assist' && !!resolveRowOnboardingId(row)
}

function openViewLog(row) {
  viewLog.value = row
  viewLogVisible.value = true
}

function goOnboarding(row) {
  const id = resolveRowOnboardingId(row) || resolveMerchantOnboardingId()
  if (!id) {
    ElMessage.info('无关联入驻申请')
    return
  }
  router.push({ path: '/admin/shop/onboarding', query: { id: String(id) } })
}

watch([logType, logStatus, logPageSize], () => {
  logPage.value = 1
  if (activeTab.value === 'service') loadLogs()
})
watch(logPage, () => {
  if (activeTab.value === 'service') loadLogs()
})

function openNote() {
  noteForm.type = 'call'
  noteForm.occurred_at = nowLocal()
  noteForm.content = ''
  noteForm.follow_up_at = ''
  noteVisible.value = true
}

function searchLogs() {
  logPage.value = 1
  loadLogs()
}

async function submitNote() {
  const text = (noteForm.content || '').trim()
  if (text.length < 10) {
    ElMessage.error('请填写跟进内容')
    return
  }
  submitting.value = true
  try {
    await adminApi.createShopServiceNote(route.params.tenantId, {
      type: noteForm.type,
      content: text,
      follow_up_at: noteForm.follow_up_at ? `${noteForm.follow_up_at}T00:00:00` : undefined,
      payload_json: { occurred_at: noteForm.occurred_at || undefined },
    })
    ElMessage.success('已保存跟进')
    noteVisible.value = false
    await Promise.all([load(), loadLogs()])
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

function openRenewal() {
  renewalForm.application_kind = 'renew_same'
  renewalForm.target_plan = mainSub.value?.plan_code || ''
  renewalForm.paid_yuan = 0
  renewalForm.customer_confirmed = false
  renewalForm.content = ''
  const p = selectedRenewPlan.value
  if (p) renewalForm.paid_yuan = Number(centsToYuan(p.price_cents))
  renewalVisible.value = true
}

watch(
  () => renewalForm.application_kind,
  () => {
    const opts = filteredRenewPlans.value
    renewalForm.target_plan = opts[0]?.code || ''
  },
)
watch(
  () => renewalForm.target_plan,
  (code) => {
    const p = plans.value.find((x) => x.code === code)
    if (p) renewalForm.paid_yuan = Number(centsToYuan(p.price_cents))
  },
)

async function submitRenewal() {
  if (!renewalForm.target_plan) {
    ElMessage.error('请选择目标套餐')
    return
  }
  if (!renewalForm.customer_confirmed) {
    ElMessage.error('请先与客户确认')
    return
  }
  const catalog = selectedRenewPlan.value?.price_cents || 0
  const paid = yuanToCents(renewalForm.paid_yuan)
  const note = (renewalForm.content || '').trim()
  if (note.length < 4) {
    ElMessage.error('请填写说明')
    return
  }
  if ((paid === 0 || paid !== catalog) && note.length < 4) {
    ElMessage.error('金额为 0/议价须在说明写明原因')
    return
  }
  const mode =
    renewalForm.application_kind === 'stack'
      ? 'stack'
      : renewalForm.application_kind === 'replace'
        ? 'replace'
        : 'renew_same'
  submitting.value = true
  try {
    await adminApi.createShopRenewalRequest(route.params.tenantId, {
      purchase_mode: mode,
      target_plan: renewalForm.target_plan,
      quoted_amount_cents: paid,
      catalog_price_cents: catalog,
      customer_confirmed: true,
      content: note,
    })
    ElMessage.success('已提交申请')
    renewalVisible.value = false
    await Promise.all([load(), loadLogs()])
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

function goSubscriptions(extra = {}) {
  const tenantId = detail.value?.tenant_id || route.params.tenantId
  const q = detail.value?.display_name || ''
  router.push({ path: '/admin/shop/subscriptions', query: { q, tenant_id: tenantId, ...extra } })
}

function goReplaceSubscription(row) {
  if (!row?.id) {
    ElMessage.warning('未找到订阅单')
    return
  }
  goSubscriptions({ action: 'replace', subscription_id: row.id })
}

function goStackAddon() {
  goSubscriptions({ action: 'stack' })
}

function goSubscriptionAction(action, row) {
  if (!row?.id) {
    ElMessage.warning('未找到订阅单')
    return
  }
  goSubscriptions({ action, subscription_id: row.id })
}

function processRenewal() {
  router.push('/admin/shop/subscriptions?todo=renewal')
}

async function previewMaterial(m) {
  const appId = detail.value?.onboarding_materials?.application_id || detail.value?.onboarding_application_id
  if (!appId || !m.fileId) {
    ElMessage.info('无预览文件')
    return
  }
  try {
    const { data } = await adminApi.downloadShopOnboardingFile(appId, m.fileId)
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

watch(activeTab, (t) => {
  if (t === 'payment') loadPayment()
  if (t === 'entitlements') loadEntitlements()
  if (t === 'service') loadLogs()
})

onMounted(async () => {
  await load()
  await Promise.all([loadEntitlements(), loadPlansAndFeatures(), loadPayment()])
  if (activeTab.value === 'service') await loadLogs()
})
</script>

<template>
  <div v-loading="loading" class="page-card" data-testid="shop-merchant-detail">
    <div class="toolbar">
      <el-button link type="primary" @click="router.push('/admin/shop/merchants')">返回列表</el-button>
    </div>

    <template v-if="detail">
      <div class="detail-head">
        <h3 class="detail-title">{{ detail.display_name || detail.tenant_name }}</h3>
        <el-tag size="small" :type="statusTagType[detail.onboarding_status] || 'info'">
          {{ statusLabel[detail.onboarding_status] || detail.onboarding_status }}
        </el-tag>
        <el-tag v-if="detail.plan_label" size="small" type="info" effect="plain">
          {{ detail.plan_label }}
        </el-tag>
        <el-tag v-if="detail.plan_status" size="small" effect="plain">
          {{ planStatusLabel[detail.plan_status] || detail.plan_status }}
        </el-tag>
      </div>
      <p class="detail-sub">
        租户：{{ detail.tenant_name }} · 商家编码 {{ merchantCode }}
        · 管家 {{ detail.account_manager_name || '未分配' }}
        <span v-if="detail.has_pending_renewal"> · 续费申请中</span>
      </p>
      <div class="tag-row">
        <el-tag v-for="tag in detail.tags || []" :key="tag" size="small" style="margin-right: 6px">
          {{ tag }}
        </el-tag>
        <el-button v-if="canAssignHere" size="small" @click="assignVisible = true">分配管家</el-button>
        <el-button v-if="canTagHere" size="small" @click="tagsVisible = true">编辑标签</el-button>
        <span v-else-if="isClosed && (detail.tags || []).length" class="gap-note">清退只读</span>
      </div>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="概览" name="overview">
          <div class="overview-cards">
            <div class="ov-card">
              <div class="ov-k">主体</div>
              <div class="ov-v">
                {{ entityLabel[detail.entity_type] || detail.entity_type || '—' }}
                ·
                {{ detail.onboarding_materials?.legal_name || detail.display_name || '—' }}
              </div>
            </div>
            <div class="ov-card">
              <div class="ov-k">联系人</div>
              <div class="ov-v">
                {{ detail.contact_name || '—' }}
                ·
                {{ displayMobile(detail.contact_mobile) }}
                <el-button
                  v-if="detail.contact_mobile"
                  link
                  type="primary"
                  class="eye-btn"
                  data-testid="btn-reveal-contact-mobile"
                  title="查看完整手机号"
                  @click="revealField('contact_mobile')"
                >
                  👁
                </el-button>
              </div>
            </div>
            <div class="ov-card">
              <div class="ov-k">套餐健康度</div>
              <div class="ov-v">
                <el-tag size="small" effect="plain">
                  {{ planStatusLabel[detail.plan_status] || currentPlanText }}
                </el-tag>
                · 权益至 {{ detail.benefits_until || '永久' }}
              </div>
            </div>
            <div class="ov-card">
              <div class="ov-k">旗下店铺</div>
              <div class="ov-v">
                <b>{{ detail.store_count_active ?? 0 }}</b>
                家营业
                <span> · 本月 GMV {{ formatGmv(detail.month_gmv_cents) }}</span>
              </div>
            </div>
            <div class="ov-card">
              <div class="ov-k">支付进件</div>
              <div class="ov-v">
                {{ paymentStatusText }}
                ·
                <el-button link type="primary" @click="activeTab = 'payment'">查看 →</el-button>
              </div>
            </div>
          </div>

          <div class="ent-summary">
            <div class="ent-summary__line">
              {{ entitlementSummary }}
              ·
              <el-button link type="primary" @click="activeTab = 'entitlements'">查看全部订阅</el-button>
            </div>
            <div v-if="canManage && !isClosed" class="ent-summary__ops">
              <el-button type="primary" @click="goReplaceSubscription(mainSub)">换档升级</el-button>
              <el-button @click="goStackAddon">叠加加购</el-button>
            </div>
            <div v-else-if="canWriteFollow && !canManage" class="ent-summary__ops">
              <el-button type="warning" :disabled="detail.has_pending_renewal" @click="openRenewal">
                申请续费
              </el-button>
            </div>
          </div>

          <div class="section-label">
            最近服务记录
            <el-button link type="primary" @click="activeTab = 'service'">查看全部 →</el-button>
          </div>
          <el-table :data="recentLogs" stripe empty-text="暂无服务记录">
            <el-table-column label="跟进时间" width="170">
              <template #default="{ row }">{{ formatDateTime(logOccurred(row)) }}</template>
            </el-table-column>
            <el-table-column label="类型" width="120">
              <template #default="{ row }">{{ logTypeLabel(row.type) }}</template>
            </el-table-column>
            <el-table-column prop="content" label="摘要" min-width="220" show-overflow-tooltip />
            <el-table-column prop="operator_name" label="操作人" width="120" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="当前权益" name="entitlements">
          <div class="section-label">生效中订阅</div>
          <el-table :data="activeSubs" stripe empty-text="暂无生效中订阅">
            <el-table-column label="套餐" min-width="160">
              <template #default="{ row }">{{ row.plan_name || row.plan_code || '—' }}</template>
            </el-table-column>
            <el-table-column label="订阅类型" width="110">
              <template #default="{ row }">{{ planTypeLabel(row) }}</template>
            </el-table-column>
            <el-table-column label="生效起" width="120">
              <template #default="{ row }">{{ formatDate(row.effective_at) }}</template>
            </el-table-column>
            <el-table-column label="生效止" width="120">
              <template #default="{ row }">{{ formatDate(row.expires_at_inclusive) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">{{ subStatusLabel(row) }}</template>
            </el-table-column>
            <el-table-column v-if="canManage && !isClosed" label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <template v-if="subPlanType(row) !== 'addon'">
                  <el-button v-if="canReplaceSub(row)" link type="primary" @click="goReplaceSubscription(row)">
                    换档
                  </el-button>
                  <el-button link type="primary" @click="goSubscriptionAction('detail', row)">详情</el-button>
                </template>
                <template v-else>
                  <el-button link type="primary" @click="goSubscriptionAction('renew', row)">续费</el-button>
                  <el-button link type="primary" @click="goSubscriptionAction('cancel', row)">取消</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>

          <div class="section-label" style="margin-top: 16px">合并后有效权益</div>
          <div v-if="!entitlementGroups.length" class="detail-sub">暂无合并权益</div>
          <div v-for="g in entitlementGroups" :key="g.group" class="ent-group">
            <button type="button" class="ent-group__hd" @click="toggleGroup(g.group)">
              {{ isGroupCollapsed(g.group) ? '▸' : '▾' }} {{ g.group }}
              <span class="ent-group__hint">（分组 · 无合并值）</span>
            </button>
            <el-table v-show="!isGroupCollapsed(g.group)" :data="g.items" stripe empty-text="暂无">
              <el-table-column label="功能项" min-width="160">
                <template #default="{ row }">{{ leafName(row) }}</template>
              </el-table-column>
              <el-table-column label="合并值" width="100">
                <template #default="{ row }">{{ leafValue(row) }}</template>
              </el-table-column>
              <el-table-column label="已用" width="80">
                <template #default="{ row }">{{ leafUsed(row) }}</template>
              </el-table-column>
              <el-table-column label="合并方式" width="110">
                <template #default="{ row }">{{ leafMode(row) }}</template>
              </el-table-column>
              <el-table-column label="来源" min-width="160">
                <template #default="{ row }">{{ row.source || '—' }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="旗下店铺" name="stores">
          <p class="detail-sub">
            店铺 {{ detail.store_count_active ?? 0 }} / {{ detail.store_quota ?? '—' }}（合并配额）
          </p>
          <el-table :data="detail.stores || []" stripe empty-text="暂无店铺">
            <el-table-column prop="name" label="店铺" min-width="160" />
            <el-table-column prop="slug" label="店铺短码" min-width="120" />
            <el-table-column label="本月 GMV" width="140">
              <template #default="{ row }">{{ formatGmv(row.month_gmv_cents) }}</template>
            </el-table-column>
            <el-table-column label="商品数" width="90">
              <template #default="{ row }">{{ row.product_count ?? 0 }}</template>
            </el-table-column>
            <el-table-column label="创建时间" width="120">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">{{ storeStatusLabel(row.status) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="入驻材料" name="materials">
          <template v-if="detail.onboarding_materials">
            <el-descriptions :column="2" border style="margin-bottom: 16px">
              <el-descriptions-item label="主体类型">
                {{ entityLabel[detail.onboarding_materials.entity_type || detail.entity_type] || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="主体名称">
                {{ detail.onboarding_materials.legal_name || '—' }}
              </el-descriptions-item>
              <el-descriptions-item
                v-if="(detail.onboarding_materials.entity_type || detail.entity_type) === 'personal'"
                label="身份证号"
              >
                {{ displayIdNo(detail.onboarding_materials.id_no) }}
                <el-button
                  v-if="detail.onboarding_materials.id_no"
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
                {{ detail.onboarding_materials.unified_social_credit_code || '—' }}
              </el-descriptions-item>
              <el-descriptions-item
                v-if="(detail.onboarding_materials.entity_type || detail.entity_type) !== 'personal'"
                label="法定代表人"
              >
                {{ detail.onboarding_materials.legal_rep_name || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="入驻通过时间">
                {{ formatDateTime(detail.onboarding_approved_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="经营联系人">
                {{ detail.onboarding_materials.contact_name || detail.contact_name || '—' }}
                ·
                {{ displayMobile(detail.onboarding_materials.contact_mobile || detail.contact_mobile) }}
                <el-button
                  v-if="detail.onboarding_materials.contact_mobile || detail.contact_mobile"
                  link
                  type="primary"
                  class="eye-btn"
                  data-testid="btn-reveal-contact-mobile-materials"
                  title="查看完整手机号"
                  @click="revealField('contact_mobile')"
                >
                  👁
                </el-button>
              </el-descriptions-item>
              <el-descriptions-item
                v-if="(detail.onboarding_materials.entity_type || detail.entity_type) !== 'personal'"
                label="对公账户"
              >
                {{ bankDisplay(detail.onboarding_materials.bank_account_info, detail.onboarding_materials.bank_account_display) }}
              </el-descriptions-item>
              <el-descriptions-item label="来源申请单">
                <el-button
                  v-if="detail.onboarding_materials.application_id || detail.onboarding_application_id"
                  link
                  type="primary"
                  @click="goOnboarding({})"
                >
                  入驻申请 {{ detail.onboarding_materials.application_no || '查看' }}
                </el-button>
                <span v-else>—</span>
              </el-descriptions-item>
            </el-descriptions>
            <div class="section-label">资质证照</div>
            <div v-if="materialEntries.length" class="mat-list">
              <div v-for="m in materialEntries" :key="m.key" class="mat-item">
                <span>{{ m.label }}：已归档</span>
                <el-button v-if="m.fileId" link type="primary" @click="previewMaterial(m)">预览</el-button>
              </div>
            </div>
            <el-empty v-else description="无资质文件快照" :image-size="48" />
            <div class="section-label">OCR 识别快照</div>
            <el-table v-if="ocrRows.length" :data="ocrRows" stripe empty-text="无识别快照">
              <el-table-column prop="field" label="字段" width="120" />
              <el-table-column prop="filled" label="填写值" min-width="140" show-overflow-tooltip />
              <el-table-column prop="ocr" label="OCR 识别" min-width="140" show-overflow-tooltip />
              <el-table-column prop="confidence" label="置信度" width="90" />
              <el-table-column prop="match" label="对照" width="80" />
            </el-table>
            <el-empty v-else description="无识别快照" :image-size="48" />
          </template>
          <el-empty v-else description="暂无入驻材料快照" />
        </el-tab-pane>

        <el-tab-pane label="支付进件" name="payment">
          <ShopPaymentOnboardingPanel
            :detail="payment"
            variant="p02b"
            :can-channel="canChannel"
            :acting="paymentActing"
            @refresh="payRefresh"
            @reveal="payReveal"
            @notify="payNotify"
          />
        </el-tab-pane>

        <el-tab-pane label="服务记录" name="service">
          <div class="svc-toolbar">
            <el-button v-if="canWriteFollow" type="primary" @click="openNote">写跟进</el-button>
            <el-button
              v-if="canWriteFollow && !canManage"
              :disabled="detail.has_pending_renewal"
              @click="openRenewal"
            >
              申请续费
            </el-button>
            <el-select v-model="logType" clearable placeholder="全部类型" style="width: 160px">
              <el-option v-for="t in NOTE_TYPES" :key="t.value" :label="t.label" :value="t.value" />
              <el-option label="申请续费" value="renewal_request" />
              <el-option label="状态变更" value="status_change" />
            </el-select>
            <el-select v-model="logStatus" clearable placeholder="全部状态" style="width: 140px">
              <el-option label="已记录" value="logged" />
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="已完成" value="completed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
            <el-input
              v-model="logQ"
              clearable
              placeholder="搜索内容 / 操作人"
              style="width: 200px"
              @keyup.enter="searchLogs"
              @clear="searchLogs"
            />
          </div>
          <el-table v-loading="logLoading" :data="logItems" stripe empty-text="暂无服务记录">
            <el-table-column label="跟进时间" width="170">
              <template #default="{ row }">{{ formatDateTime(logOccurred(row)) }}</template>
            </el-table-column>
            <el-table-column label="录入 / 更新" min-width="200">
              <template #default="{ row }">{{ recordedText(row) }}</template>
            </el-table-column>
            <el-table-column label="类型" width="120">
              <template #default="{ row }">{{ logTypeLabel(row.type) }}</template>
            </el-table-column>
            <el-table-column prop="content" label="内容摘要" min-width="200" show-overflow-tooltip />
            <el-table-column prop="operator_name" label="操作人" width="120" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">{{ logStatusLabel(row.status) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openViewLog(row)">查看</el-button>
                <el-button
                  v-if="canManage && row.type === 'renewal_request' && row.status === 'pending'"
                  link
                  type="primary"
                  @click="processRenewal"
                >
                  处理续费
                </el-button>
                <el-button
                  v-if="canViewOnboarding(row)"
                  link
                  type="primary"
                  @click="goOnboarding(row)"
                >
                  查看入驻申请
                </el-button>
                <el-button
                  v-if="row.status === 'completed' && row.related_subscription_id"
                  link
                  type="primary"
                  @click="activeTab = 'entitlements'"
                >
                  查看订阅
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pager">
            <el-pagination
              v-model:current-page="logPage"
              v-model:page-size="logPageSize"
              :total="logTotal"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              small
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="操作日志" name="audit">
          <div class="svc-toolbar" data-testid="shop-merchant-audit">
            <el-select v-model="auditAction" clearable placeholder="全部动作" style="width: 160px">
              <el-option v-for="a in AUDIT_ACTIONS" :key="a" :label="a" :value="a" />
            </el-select>
            <el-input v-model="auditQ" clearable placeholder="搜索操作人 / 摘要" style="width: 220px" />
          </div>
          <el-table :data="pagedAuditLogs" stripe empty-text="暂无操作日志">
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.at) }}</template>
            </el-table-column>
            <el-table-column prop="action" label="动作" width="120" />
            <el-table-column prop="summary" label="摘要" min-width="220" show-overflow-tooltip />
            <el-table-column prop="operator_name" label="操作人" width="120" />
            <el-table-column prop="source" label="来源" width="120" />
          </el-table>
          <div class="pager">
            <el-pagination
              v-model:current-page="auditPage"
              v-model:page-size="auditPageSize"
              :total="filteredAuditLogs.length"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              small
            />
          </div>
        </el-tab-pane>
      </el-tabs>

      <el-dialog v-model="noteVisible" title="写跟进" width="520px">
        <el-form label-width="100px">
          <el-form-item label="跟进类型" required>
            <el-select v-model="noteForm.type" style="width: 100%">
              <el-option v-for="t in NOTE_TYPES" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="跟进时间" required>
            <el-date-picker
              v-model="noteForm.occurred_at"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="内容" required>
            <el-input v-model="noteForm.content" type="textarea" :rows="4" placeholder="至少 10 字" />
          </el-form-item>
          <el-form-item label="下次跟进">
            <el-date-picker v-model="noteForm.follow_up_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="noteVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitNote">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="renewalVisible" :title="`申请续费 · ${detail.display_name || ''}`" width="560px">
        <el-form label-width="130px">
          <el-form-item label="商家">
            <span>{{ detail.display_name }} · {{ detail.onboarding_materials?.legal_name || detail.tenant_name }}</span>
          </el-form-item>
          <el-form-item label="当前套餐">
            <span>{{ currentPlanText }}</span>
          </el-form-item>
          <el-form-item label="申请类型" required>
            <el-select v-model="renewalForm.application_kind" style="width: 100%">
              <el-option label="续费同档" value="renew_same" />
              <el-option label="叠加加购" value="stack" />
              <el-option label="主套餐升级" value="replace" />
            </el-select>
          </el-form-item>
          <el-form-item :label="targetPlanFieldLabel" required>
            <el-select v-model="renewalForm.target_plan" style="width: 100%" placeholder="请选择">
              <el-option
                v-for="p in filteredRenewPlans"
                :key="p.code"
                :label="`${p.name}（${p.billing_period === 'monthly' ? '月' : '年'}）`"
                :value="p.code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="套餐标价">
            <span>¥{{ centsToYuan(selectedRenewPlan?.price_cents) }}</span>
          </el-form-item>
          <el-form-item :label="amountLabel" required>
            <el-input-number v-model="renewalForm.paid_yuan" :min="0" :precision="2" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="预计生效区间">
            <span>{{ expectedPeriodText }}</span>
          </el-form-item>
          <el-form-item label="客户确认" required>
            <el-checkbox v-model="renewalForm.customer_confirmed">{{ confirmLabel }}</el-checkbox>
          </el-form-item>
          <el-form-item label="说明" required>
            <el-input
              v-model="renewalForm.content"
              type="textarea"
              :rows="3"
              placeholder="付款方式、到账要求或议价原因，至少 4 字"
            />
          </el-form-item>
          <el-form-item label="通知运营">
            <span class="ov-muted">提交后通知具备开通权限的运营，订阅台账待办增加一条（站内信本批未接通）</span>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="renewalVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitRenewal">提交申请</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="viewLogVisible" title="跟进详情" width="520px">
        <el-descriptions v-if="viewLog" :column="1" border>
          <el-descriptions-item label="商家">{{ detail.display_name }}</el-descriptions-item>
          <el-descriptions-item label="跟进时间">{{ formatDateTime(logOccurred(viewLog)) }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ logTypeLabel(viewLog.type) }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ viewLog.operator_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="内容">{{ viewLog.content }}</el-descriptions-item>
          <el-descriptions-item label="下次跟进">{{ formatDateTime(viewLog.follow_up_at) }}</el-descriptions-item>
          <el-descriptions-item label="录入时间">{{ formatDateTime(viewLog.created_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="canViewOnboarding(viewLog)" label="关联入驻申请">
            <el-button link type="primary" @click="goOnboarding(viewLog)">查看入驻申请</el-button>
          </el-descriptions-item>
        </el-descriptions>
        <template #footer>
          <el-button
            v-if="canViewOnboarding(viewLog)"
            type="primary"
            @click="goOnboarding(viewLog)"
          >
            查看入驻申请
          </el-button>
          <el-button
            v-if="canManage && viewLog?.type === 'renewal_request' && viewLog?.status === 'pending'"
            type="primary"
            @click="processRenewal"
          >
            处理续费
          </el-button>
          <el-button @click="viewLogVisible = false">关闭</el-button>
        </template>
      </el-dialog>
      <ShopAssignManagerDialog
        v-model="assignVisible"
        :tenant-id="detail.tenant_id"
        :display-name="detail.display_name || detail.tenant_name"
        :current-manager-id="detail.account_manager_user_id || ''"
        :current-manager-name="detail.account_manager_name || ''"
        @success="load"
      />
      <ShopMerchantTagsDialog
        v-model="tagsVisible"
        :tenant-id="detail.tenant_id"
        :display-name="detail.display_name || detail.tenant_name"
        :selected="detail.tag_items || detail.tags || []"
        :readonly="isClosed"
        @success="load"
      />
    </template>
    <el-empty v-else-if="!loading" description="未找到商家" />
  </div>
</template>

<style scoped>
.toolbar {
  margin-bottom: 8px;
}
.detail-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}
.detail-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}
.detail-sub {
  margin: 0 0 8px;
  color: #8c8c8c;
  font-size: 13px;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 0 0 16px;
}
.gap-note {
  margin: 12px 0 0;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.5;
}
.section-label {
  font-size: 13px;
  font-weight: 600;
  margin: 8px 0;
  color: #262626;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ent-group {
  margin-bottom: 8px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
}
.ent-group__hd {
  width: 100%;
  text-align: left;
  background: #fafafa;
  border: 0;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #262626;
}
.ent-group__hint {
  font-size: 11px;
  font-weight: 400;
  color: #888;
  margin-left: 6px;
}
.mat-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.mat-item {
  padding: 8px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.overview-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.ov-card {
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  padding: 10px 12px;
  background: #fafafa;
}
.ov-k {
  color: #8c8c8c;
  font-size: 12px;
  margin-bottom: 4px;
}
.ov-v {
  font-size: 13px;
  color: #262626;
  line-height: 1.5;
}
.ov-muted {
  color: #8c8c8c;
  font-size: 12px;
}
.eye-btn {
  padding: 0 4px;
  min-height: auto;
}
.ent-summary {
  border: 1px solid #d3adf7;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  background: #f9f0ff;
}
.ent-summary__line {
  font-size: 13px;
  margin-bottom: 8px;
}
.ent-summary__ops {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.svc-toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 12px;
}
.pager {
  margin-top: 12px;
}
</style>
