<script setup>
/** 对照 PRD 06#p12 · #p12-channel · #p12c · #p12-signatures · #p12-templates · #p12-assign · #p12-logs · 04#select-common
 * 缺口：连通性测试为凭据完备性探测（不调阿里云）；导出完成站内信本批不接。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'
import { useAuthStore } from '../../../stores/auth'
import { formatApiError } from '../../../utils/apiError'
import { formatDateTime } from '../../../utils/datetime'
import ShopMaterialUpload from '../../../components/shop/ShopMaterialUpload.vue'
import { SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../../utils/shopExport'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canChannel = computed(() => auth.hasPlatformShopPermission('platform.shop.channel'))
const sigDrawerTitle = computed(() => {
  if (viewSig.value) return '签名详情'
  if (sigResubmitId.value) return '修改并重新提交'
  return '新建签名申请'
})
const sigMerchantName = computed(() => {
  if (!sigForm.tenant_id) return ''
  const m = merchants.value.find((x) => x.tenant_id === sigForm.tenant_id)
  return m?.name || sigForm.tenant_id
})

const TAB_KEYS = ['channel', 'signatures', 'templates', 'assign', 'logs']
const TPL_CODE_RE = /^[A-Za-z0-9_]{4,64}$/
const activeTab = ref('signatures')

const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref(SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns)
const channelCfg = ref(null)
const channelForm = reactive({
  access_key_id: '',
  access_key_secret: '',
  default_notify_signature: '【智营获客】',
})
const saveChannelVisible = ref(false)
const credActing = ref(false)

const sigItems = ref([])
const sigTotal = ref(0)
const sigPage = ref(1)
const sigPageSize = ref(20)
const sigQ = ref('')
const sigStatus = ref('')

const tplItems = ref([])
const tplTotal = ref(0)
const tplPage = ref(1)
const tplPageSize = ref(20)
const tplPurpose = ref('')
const tplStatus = ref('')

const asgItems = ref([])
const asgTotal = ref(0)
const asgPage = ref(1)
const asgPageSize = ref(20)
const asgQ = ref('')
const asgStatus = ref('')

const logItems = ref([])
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(20)
const logPurpose = ref('')
const logStatus = ref('')
const logRange = ref('30d')
const logQ = ref('')
const logCustomFrom = ref('')
const logCustomUntil = ref('')

const merchants = ref([])
const sigDrawer = ref(false)
const sigResubmitId = ref(null)
const sigRejectReason = ref('')
const sigForm = reactive({
  tenant_id: '',
  content: '',
  remark: '',
  qualification_files: {},
  file_names: {},
})
const sigSubmitting = ref(false)
const viewSig = ref(null)

const tplDrawer = ref(false)
const tplForm = reactive({
  name: '',
  template_code: '',
  purpose: 'claim_link',
  content_preview: '',
  is_default_claim: false,
})
const tplEditingId = ref(null)
const tplSubmitting = ref(false)

const asgDrawer = ref(false)
const asgForm = reactive({
  tenant_id: '',
  merchant_name: '',
  sms_signature_id: '',
  claim_template_id: '',
})
const asgOptions = ref({ signatures: [], templates: [] })
const asgSubmitting = ref(false)

const logDrawer = ref(false)
const logDetail = ref(null)
const SIG_COL_DEFS = [
  { key: 'content', label: '签名', locked: true, defaultOn: true },
  { key: 'merchant_name', label: '关联商家', defaultOn: true },
  { key: 'status', label: '供应商审核', defaultOn: true },
  { key: 'applied_at', label: '申请时间', defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys: sigVisibleKeys,
  columnDialogVisible: sigColDlg,
  columnDraft: sigColDraft,
  openColumnSettings: openSigCol,
  saveColumnSettings: saveSigCol,
  isColVisible: sigColOn,
} = useListColumnSettings(SIG_COL_DEFS, 'shop-sms-sig-columns')

const TPL_COL_DEFS = [
  { key: 'name', label: '模板名称', locked: true, defaultOn: true },
  { key: 'code', label: '供应商 Code', defaultOn: true },
  { key: 'purpose', label: '用途', defaultOn: true },
  { key: 'status', label: '审核状态', defaultOn: true },
  { key: 'preview', label: '内容摘要', defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys: tplVisibleKeys,
  columnDialogVisible: tplColDlg,
  columnDraft: tplColDraft,
  openColumnSettings: openTplCol,
  saveColumnSettings: saveTplCol,
  isColVisible: tplColOn,
} = useListColumnSettings(TPL_COL_DEFS, 'shop-sms-tpl-columns')

const ASG_COL_DEFS = [
  { key: 'merchant_name', label: '商家', locked: true, defaultOn: true },
  { key: 'sms_signature', label: '领权签名', defaultOn: true },
  { key: 'claim_template', label: '领权模板', defaultOn: true },
  { key: 'month', label: '本月已发', defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys: asgVisibleKeys,
  columnDialogVisible: asgColDlg,
  columnDraft: asgColDraft,
  openColumnSettings: openAsgCol,
  saveColumnSettings: saveAsgCol,
  isColVisible: asgColOn,
} = useListColumnSettings(ASG_COL_DEFS, 'shop-sms-asg-columns')

const LOG_COL_DEFS = [
  { key: 'sent_at', label: '发送时间', locked: true, defaultOn: true },
  { key: 'merchant_name', label: '商家', defaultOn: true },
  { key: 'purpose', label: '用途', defaultOn: true },
  { key: 'sms_signature', label: '签名', defaultOn: true },
  { key: 'template_name', label: '模板', defaultOn: true },
  { key: 'mobile', label: '接收手机', defaultOn: true },
  { key: 'status', label: '状态', defaultOn: true },
  { key: 'order_no', label: '关联单号', defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys: logVisibleKeys,
  columnDialogVisible: logColDlg,
  columnDraft: logColDraft,
  openColumnSettings: openLogCol,
  saveColumnSettings: saveLogCol,
  isColVisible: logColOn,
} = useListColumnSettings(LOG_COL_DEFS, 'shop-sms-log-columns')

const sigStatusTag = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  withdrawn: 'info',
}
const logStatusTag = { sent: 'success', failed: 'danger', sending: 'warning' }

function downloadBlob(data, filename) {
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function loadChannel() {
  try {
    const { data } = await adminApi.getShopSmsChannelConfig()
    channelCfg.value = data
    channelForm.access_key_id = ''
    channelForm.access_key_secret = ''
    channelForm.default_notify_signature = data.default_notify_signature || '【智营获客】'
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载通道失败')
  }
}

function openSaveChannel() {
  if (!channelForm.access_key_id.trim() && !channelCfg.value?.configured) {
    ElMessage.error('AccessKey ID 不能为空')
    return
  }
  if (!channelForm.access_key_secret.trim() && !channelCfg.value?.configured) {
    ElMessage.error('AccessKey Secret 不能为空')
    return
  }
  saveChannelVisible.value = true
}

async function submitSaveChannel() {
  credActing.value = true
  try {
    const { data } = await adminApi.saveShopSmsChannelConfig({
      access_key_id: channelForm.access_key_id.trim(),
      access_key_secret: channelForm.access_key_secret.trim() || undefined,
      default_notify_signature: channelForm.default_notify_signature.trim() || undefined,
    })
    channelCfg.value = data
    channelForm.access_key_id = ''
    channelForm.access_key_secret = ''
    saveChannelVisible.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    credActing.value = false
  }
}

async function testChannel() {
  credActing.value = true
  try {
    const { data } = await adminApi.testShopSmsChannelConfig()
    channelCfg.value = data
    ElMessage.success(data?.last_test_ok ? '连通性测试通过' : '连通性测试失败')
  } catch (e) {
    ElMessage.error(e.message || '请先保存')
  } finally {
    credActing.value = false
  }
}

async function loadMerchants() {
  try {
    const { data } = await adminApi.listShopSmsMerchants()
    merchants.value = data.items || []
  } catch {
    merchants.value = []
  }
}

async function loadSignatures() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopSmsSignatures({
      q: sigQ.value.trim() || undefined,
      status: sigStatus.value || undefined,
      page: sigPage.value,
      page_size: sigPageSize.value,
    })
    sigItems.value = data.items || []
    sigTotal.value = data.total || 0
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopSmsTemplates({
      purpose: tplPurpose.value || undefined,
      status: tplStatus.value || undefined,
      page: tplPage.value,
      page_size: tplPageSize.value,
    })
    tplItems.value = data.items || []
    tplTotal.value = data.total || 0
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadAssignments() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopSmsAssignments({
      q: asgQ.value.trim() || undefined,
      assign_status: asgStatus.value || undefined,
      page: asgPage.value,
      page_size: asgPageSize.value,
    })
    asgItems.value = data.items || []
    asgTotal.value = data.total || 0
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function logQuery() {
  return {
    purpose: logPurpose.value || undefined,
    status: logStatus.value || undefined,
    q: logQ.value.trim() || undefined,
    range_key: logRange.value || '30d',
    date_from: logRange.value === 'custom' ? logCustomFrom.value || undefined : undefined,
    date_until: logRange.value === 'custom' ? logCustomUntil.value || undefined : undefined,
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopSmsLogs({
      ...logQuery(),
      page: logPage.value,
      page_size: logPageSize.value,
    })
    logItems.value = data.items || []
    logTotal.value = data.total || 0
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function closeSigDrawer() {
  sigDrawer.value = false
  sigResubmitId.value = null
  sigRejectReason.value = ''
  viewSig.value = null
}

function openSigCreate() {
  sigResubmitId.value = null
  sigRejectReason.value = ''
  sigForm.tenant_id = ''
  sigForm.content = ''
  sigForm.remark = ''
  sigForm.qualification_files = {}
  sigForm.file_names = {}
  viewSig.value = null
  sigDrawer.value = true
}

async function openSigResubmit(row) {
  const { data } = await adminApi.getShopSmsSignature(row.id)
  sigResubmitId.value = row.id
  sigRejectReason.value = data.reject_reason || ''
  viewSig.value = null
  sigForm.tenant_id = data.tenant_id || ''
  sigForm.content = data.content || ''
  sigForm.remark = data.remark || ''
  sigForm.qualification_files = { ...(data.qualification_files || {}) }
  sigForm.file_names = {}
  sigDrawer.value = true
}

async function submitSignature() {
  if (!sigForm.tenant_id) {
    ElMessage.warning('请选择关联商家')
    return
  }
  if (!sigForm.content.trim()) {
    ElMessage.warning('请填写短信签名')
    return
  }
  sigSubmitting.value = true
  try {
    if (sigResubmitId.value) {
      await adminApi.resubmitShopSmsSignature(sigResubmitId.value, {
        content: sigForm.content,
        remark: sigForm.remark || undefined,
        qualification_files: sigForm.qualification_files,
      })
      ElMessage.success('已重新提交供应商审核')
    } else {
      await adminApi.createShopSmsSignature({
        tenant_id: sigForm.tenant_id,
        content: sigForm.content,
        remark: sigForm.remark || undefined,
        qualification_files: sigForm.qualification_files,
      })
      ElMessage.success('已提交供应商审核')
    }
    sigDrawer.value = false
    closeSigDrawer()
    await loadSignatures()
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    sigSubmitting.value = false
  }
}

async function viewSignature(row) {
  sigResubmitId.value = null
  sigRejectReason.value = ''
  const { data } = await adminApi.getShopSmsSignature(row.id)
  viewSig.value = data
  sigDrawer.value = true
}

async function actSig(row, action) {
  try {
    if (action === 'sync') {
      await adminApi.syncShopSmsSignature(row.id)
      ElMessage.success('已同步，仍审核中')
    } else if (action === 'withdraw') {
      await ElMessageBox.confirm('撤回该签名申请？', '撤回')
      await adminApi.withdrawShopSmsSignature(row.id)
      ElMessage.success('已撤回')
    } else if (action === 'approve') {
      await adminApi.approveShopSmsSignature(row.id)
      ElMessage.success('已通过')
    } else if (action === 'reject') {
      const { value } = await ElMessageBox.prompt('驳回原因（≥4字）', '驳回', {
        inputPattern: /.{4,}/,
        inputErrorMessage: '至少4字',
      })
      await adminApi.rejectShopSmsSignature(row.id, { reason: value })
      ElMessage.success('已驳回')
    } else if (action === 'resubmit') {
      await openSigResubmit(row)
      return
    } else if (action === 'assign') {
      activeTab.value = 'assign'
      asgQ.value = row.merchant_name || ''
      await loadAssignments()
    }
    await loadSignatures()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

function openTplCreate() {
  tplEditingId.value = null
  tplForm.name = ''
  tplForm.template_code = ''
  tplForm.purpose = 'claim_link'
  tplForm.content_preview = ''
  tplForm.is_default_claim = false
  tplDrawer.value = true
}

function openTplEdit(row) {
  tplEditingId.value = row.id
  tplForm.name = row.name
  tplForm.template_code = row.template_code
  tplForm.purpose = row.purpose
  tplForm.content_preview = row.content_preview || ''
  tplForm.is_default_claim = !!row.is_default_claim
  tplDrawer.value = true
}

async function submitTemplate() {
  const name = (tplForm.name || '').trim()
  const code = (tplForm.template_code || '').trim()
  if (!name) {
    ElMessage.error('请填写模板名称')
    return
  }
  if (!tplEditingId.value) {
    if (!TPL_CODE_RE.test(code)) {
      ElMessage.error('供应商 Template Code 格式无效')
      return
    }
    if (tplItems.value.some((t) => String(t.template_code || '').toUpperCase() === code.toUpperCase())) {
      ElMessage.error('Code 已存在，请更换 Template Code 或编辑已有模板')
      return
    }
  }
  tplSubmitting.value = true
  try {
    if (tplEditingId.value) {
      await adminApi.updateShopSmsTemplate(tplEditingId.value, {
        name,
        content_preview: tplForm.content_preview,
      })
      ElMessage.success('已保存')
    } else {
      await adminApi.createShopSmsTemplate({
        name,
        template_code: code,
        purpose: tplForm.purpose,
        content_preview: tplForm.content_preview || undefined,
        is_default_claim: tplForm.is_default_claim,
      })
      ElMessage.success('已登记')
    }
    tplDrawer.value = false
    await loadTemplates()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存失败'))
  } finally {
    tplSubmitting.value = false
  }
}

async function setDefaultTpl(row) {
  try {
    await adminApi.setDefaultShopSmsTemplate(row.id)
    ElMessage.success('已设为默认领权模板')
    await loadTemplates()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function openAssign(row) {
  asgForm.tenant_id = row.tenant_id
  asgForm.merchant_name = row.merchant_name
  asgForm.sms_signature_id = row.sms_signature_id || ''
  asgForm.claim_template_id = row.claim_template_id || ''
  const { data } = await adminApi.getShopSmsAssignOptions(row.tenant_id)
  asgOptions.value = data
  asgDrawer.value = true
}

async function openAssignCreate() {
  asgForm.tenant_id = ''
  asgForm.merchant_name = ''
  asgForm.sms_signature_id = ''
  asgForm.claim_template_id = ''
  asgOptions.value = { signatures: [], templates: [] }
  asgDrawer.value = true
}

async function onAsgMerchantChange(tid) {
  const m = merchants.value.find((x) => x.tenant_id === tid)
  asgForm.merchant_name = m?.name || ''
  asgForm.sms_signature_id = ''
  asgForm.claim_template_id = ''
  if (!tid) {
    asgOptions.value = { signatures: [], templates: [] }
    return
  }
  const { data } = await adminApi.getShopSmsAssignOptions(tid)
  asgOptions.value = data
}

async function syncPendingSignatures() {
  const pending = sigItems.value.filter((r) => r.actions.includes('sync'))
  if (!pending.length) {
    ElMessage.info('当前页没有审核中的签名')
    return
  }
  for (const row of pending) {
    await adminApi.syncShopSmsSignature(row.id)
  }
  ElMessage.success('已同步供应商审核状态')
  await loadSignatures()
}

async function submitAssign() {
  if (!asgForm.sms_signature_id || !asgForm.claim_template_id) {
    ElMessage.warning('请选择已通过的签名与领权模板')
    return
  }
  asgSubmitting.value = true
  try {
    await adminApi.assignShopSms({
      tenant_id: asgForm.tenant_id,
      sms_signature_id: asgForm.sms_signature_id,
      claim_template_id: asgForm.claim_template_id,
    })
    ElMessage.success('已分配')
    asgDrawer.value = false
    await loadAssignments()
  } catch (e) {
    ElMessage.error(e.message || '分配失败')
  } finally {
    asgSubmitting.value = false
  }
}

async function openLog(row) {
  const { data } = await adminApi.getShopSmsLog(row.id)
  logDetail.value = data
  logDrawer.value = true
}

async function revealMobile() {
  if (!logDetail.value) return
  const { data } = await adminApi.revealShopSmsMobile(logDetail.value.id)
  logDetail.value = data
}

async function retryLog(row) {
  try {
    await adminApi.retryShopSmsLog(row.id)
    ElMessage.success('已重试')
    await loadLogs()
  } catch (e) {
    ElMessage.error(e.message || '不可重试')
  }
}

async function exportSig(mode) {
  exporting.value = true
  try {
    const body = {
      q: sigQ.value.trim() || undefined,
      status: sigStatus.value || undefined,
    }
    if (mode === 'columns') {
      body.columns = SIG_COL_DEFS.filter((c) => c.key !== 'ops' && sigColOn(c.key)).map((c) => c.key)
    }
    const { data } = await adminApi.createShopSmsSignatureExport(body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns : SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function exportTpl(mode) {
  exporting.value = true
  try {
    const body = {
      purpose: tplPurpose.value || undefined,
      status: tplStatus.value || undefined,
    }
    if (mode === 'columns') {
      body.columns = TPL_COL_DEFS.filter((c) => c.key !== 'ops' && tplColOn(c.key)).map((c) => c.key)
    }
    const { data } = await adminApi.createShopSmsTemplateExport(body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns : SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function exportAsg(mode) {
  exporting.value = true
  try {
    const body = {
      q: asgQ.value.trim() || undefined,
      assign_status: asgStatus.value || undefined,
    }
    if (mode === 'columns') {
      body.columns = ASG_COL_DEFS.filter((c) => c.key !== 'ops' && asgColOn(c.key)).map((c) => c.key)
    }
    const { data } = await adminApi.createShopSmsAssignmentExport(body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns : SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function exportLogs() {
  exporting.value = true
  try {
    const { data } = await adminApi.createShopSmsLogExport(logQuery())
    exportTask.value = data
    exportScope.value = SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns
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
    const id = exportTask.value.id
    const resource = exportTask.value.resource
    let res
    if (resource === 'sms_signatures') {
      res = await adminApi.getShopSmsSignatureExportFile(id)
    } else if (resource === 'sms_templates') {
      res = await adminApi.getShopSmsTemplateExportFile(id)
    } else if (resource === 'sms_assignments') {
      res = await adminApi.getShopSmsAssignmentExportFile(id)
    } else {
      res = await adminApi.getShopSmsLogExportFile(id)
    }
    downloadBlob(res.data, exportTask.value.file_name || 'export.csv')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function goMerchant(tenantId) {
  if (!tenantId) return
  router.push(`/admin/shop/merchants/${tenantId}`)
}

async function platformUpload(docType, file) {
  if (!sigForm.tenant_id) throw new Error('请先选择关联商家再上传材料')
  const { data } = await adminApi.uploadShopOnboardingFile(sigForm.tenant_id, docType, file)
  return data
}

function onMatUploaded({ docType, fileId, fileName }) {
  sigForm.qualification_files = { ...sigForm.qualification_files, [docType]: fileId }
  sigForm.file_names = { ...sigForm.file_names, [docType]: fileName }
}

function onMatCleared({ docType }) {
  const next = { ...sigForm.qualification_files }
  delete next[docType]
  sigForm.qualification_files = next
}

watch(activeTab, (t) => {
  if (t === 'signatures') loadSignatures()
  if (t === 'templates') loadTemplates()
  if (t === 'assign') loadAssignments()
  if (t === 'logs') loadLogs()
  if (t === 'channel') loadChannel()
})

onMounted(async () => {
  const t = String(route.query.tab || '')
  if (TAB_KEYS.includes(t)) activeTab.value = t
  await loadMerchants()
  await loadChannel()
  if (activeTab.value === 'signatures') await loadSignatures()
  else if (activeTab.value === 'templates') await loadTemplates()
  else if (activeTab.value === 'assign') await loadAssignments()
  else if (activeTab.value === 'logs') await loadLogs()
})
</script>

<template>
  <div class="page-card">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="通道配置" name="channel">
        <el-form label-width="180px" class="cfg-form">
          <el-form-item label="AccessKey ID" required>
            <el-input
              v-model="channelForm.access_key_id"
              :placeholder="channelCfg?.access_key_id_masked || '请输入'"
            />
          </el-form-item>
          <el-form-item label="AccessKey Secret" required>
            <el-input
              v-model="channelForm.access_key_secret"
              type="password"
              show-password
              placeholder="脱敏展示，留空则不改"
            />
          </el-form-item>
          <el-form-item label="默认签名（平台通知）">
            <el-input v-model="channelForm.default_notify_signature" />
          </el-form-item>
          <el-form-item label="连通性（只读）">
            {{ channelCfg?.connectivity_label || '未配置' }}
          </el-form-item>
        </el-form>
        <div v-if="canChannel" class="cfg-ops">
          <el-button type="primary" @click="openSaveChannel">保存</el-button>
          <el-button :loading="credActing" @click="testChannel">连通性测试</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="签名管理" name="signatures">
        <div class="toolbar">
          <el-button v-if="canChannel" type="primary" @click="openSigCreate">+ 新建签名申请</el-button>
          <el-button v-if="canChannel" @click="syncPendingSignatures">同步供应商审核状态</el-button>
          <el-input
            v-model="sigQ"
            clearable
            placeholder="搜索签名 / 商家"
            style="width: 200px"
            @keyup.enter="sigPage = 1; loadSignatures()"
          />
          <el-select v-model="sigStatus" clearable placeholder="审核状态" style="width: 140px" @change="sigPage = 1; loadSignatures()">
            <el-option label="审核中" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
          <el-button @click="sigPage = 1; loadSignatures()">搜索</el-button>
          <div class="spacer" />
          <el-dropdown trigger="click" @command="exportSig">
            <el-button :loading="exporting">导出 ▾</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
                <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button @click="openSigCol">列设置</el-button>
        </div>
        <el-table v-loading="loading" :data="sigItems" border stripe size="small">
          <template v-for="colKey in sigVisibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'content'" prop="content" label="签名" min-width="140" />
          <el-table-column v-if="colKey === 'merchant_name'" prop="merchant_name" label="关联商家" min-width="140" />
          <el-table-column v-if="colKey === 'status'" label="供应商审核" width="110">
            <template #default="{ row }">
              <el-tag :type="sigStatusTag[row.status] || 'info'" size="small">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'applied_at'" label="申请时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.applied_at, { withSeconds: false }) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewSignature(row)">查看</el-button>
              <el-button v-if="row.actions.includes('sync')" link type="warning" @click="actSig(row, 'sync')">刷新状态</el-button>
              <el-button v-if="row.actions.includes('withdraw')" link @click="actSig(row, 'withdraw')">撤回</el-button>
              <el-button v-if="row.actions.includes('approve')" link type="success" @click="actSig(row, 'approve')">通过</el-button>
              <el-button v-if="row.actions.includes('reject')" link type="danger" @click="actSig(row, 'reject')">驳回</el-button>
              <el-button v-if="row.actions.includes('resubmit')" link @click="actSig(row, 'resubmit')">重新提交</el-button>
              <el-button v-if="row.actions.includes('assign')" link type="primary" @click="actSig(row, 'assign')">重新分配</el-button>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="sigPage"
            v-model:page-size="sigPageSize"
            :total="sigTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadSignatures"
            @size-change="sigPage = 1; loadSignatures()"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="模板管理" name="templates">
        <div class="toolbar">
          <el-button v-if="canChannel" type="primary" @click="openTplCreate">+ 登记新模板</el-button>
          <el-select v-model="tplPurpose" clearable placeholder="用途" style="width: 140px" @change="tplPage = 1; loadTemplates()">
            <el-option label="领权" value="claim_link" />
            <el-option label="平台通知" value="notify" />
            <el-option label="测试" value="test" />
          </el-select>
          <el-select v-model="tplStatus" clearable placeholder="审核状态" style="width: 140px" @change="tplPage = 1; loadTemplates()">
            <el-option label="审核中" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
          <div class="spacer" />
          <el-dropdown trigger="click" @command="exportTpl">
            <el-button :loading="exporting">导出 ▾</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
                <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button @click="openTplCol">列设置</el-button>
        </div>
        <el-table v-loading="loading" :data="tplItems" border stripe size="small">
          <template v-for="colKey in tplVisibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'name'" prop="name" label="模板名称" min-width="140" />
          <el-table-column v-if="colKey === 'code'" label="供应商 Code" width="150">
            <template #default="{ row }"><code>{{ row.template_code }}</code></template>
          </el-table-column>
          <el-table-column v-if="colKey === 'purpose'" prop="purpose_label" label="用途" width="100" />
          <el-table-column v-if="colKey === 'status'" label="审核状态" width="140">
            <template #default="{ row }">
              <el-tag :type="sigStatusTag[row.status] || 'info'" size="small">{{ row.status_label }}</el-tag>
              <el-tag v-if="row.is_default_claim" size="small" type="primary" style="margin-left: 4px">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'preview'" prop="content_preview" label="内容摘要" min-width="180" show-overflow-tooltip />
          <el-table-column v-if="colKey === 'ops'" label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openTplEdit(row)">编辑</el-button>
              <el-button v-if="row.actions.includes('set_default')" link @click="setDefaultTpl(row)">设为默认</el-button>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="tplPage"
            v-model:page-size="tplPageSize"
            :total="tplTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadTemplates"
            @size-change="tplPage = 1; loadTemplates()"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="商家分配" name="assign">
        <div class="toolbar">
          <el-button v-if="canChannel" type="primary" @click="openAssignCreate">+ 分配短信资源</el-button>
          <el-input
            v-model="asgQ"
            clearable
            placeholder="搜索商家"
            style="width: 180px"
            @keyup.enter="asgPage = 1; loadAssignments()"
          />
          <el-select v-model="asgStatus" clearable placeholder="分配状态" style="width: 150px" @change="asgPage = 1; loadAssignments()">
            <el-option label="已分配" value="assigned" />
            <el-option label="未分配" value="unassigned" />
            <el-option label="签名审核中" value="signature_pending" />
          </el-select>
          <el-button @click="asgPage = 1; loadAssignments()">搜索</el-button>
          <div class="spacer" />
          <el-dropdown trigger="click" @command="exportAsg">
            <el-button :loading="exporting">导出 ▾</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
                <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button @click="openAsgCol">列设置</el-button>
        </div>
        <el-table v-loading="loading" :data="asgItems" border stripe size="small">
          <template v-for="colKey in asgVisibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'merchant_name'" prop="merchant_name" label="商家" min-width="140" />
          <el-table-column v-if="colKey === 'sms_signature'" label="领权签名" min-width="140">
            <template #default="{ row }">
              <span v-if="row.sms_signature">
                {{ row.sms_signature }}
                <el-tag v-if="row.sms_signature_status === 'pending'" size="small" type="warning">审核中</el-tag>
              </span>
              <el-tag v-else size="small" type="info">未分配</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'claim_template'" label="领权模板" min-width="140">
            <template #default="{ row }">{{ row.claim_template_name || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'month'" label="本月已发" width="120">
            <template #default="{ row }">{{ row.month_used }} / {{ row.month_limit }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <template v-if="row.assign_status === 'signature_pending'">待签名通过</template>
              <template v-else>
                <el-button v-if="canChannel" link type="primary" @click="openAssign(row)">
                  {{ row.assign_status === 'assigned' ? '修改分配' : '分配' }}
                </el-button>
                <el-button link type="primary" @click="goMerchant(row.tenant_id)">商家详情</el-button>
              </template>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="asgPage"
            v-model:page-size="asgPageSize"
            :total="asgTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadAssignments"
            @size-change="asgPage = 1; loadAssignments()"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="发送记录" name="logs">
        <div class="chips">
          <el-button size="small" :type="logPurpose === '' ? 'primary' : 'default'" @click="logPurpose = ''; logPage = 1; loadLogs()">全部</el-button>
          <el-button size="small" :type="logPurpose === 'claim' ? 'primary' : 'default'" @click="logPurpose = 'claim'; logPage = 1; loadLogs()">领权</el-button>
          <el-button size="small" :type="logPurpose === 'test' ? 'primary' : 'default'" @click="logPurpose = 'test'; logPage = 1; loadLogs()">测试</el-button>
          <el-button size="small" :type="logPurpose === 'notify' ? 'primary' : 'default'" @click="logPurpose = 'notify'; logPage = 1; loadLogs()">平台通知</el-button>
        </div>
        <div class="toolbar">
          <el-input
            v-model="logQ"
            clearable
            placeholder="手机号 / 订单号 / 商家"
            style="width: 220px"
            @keyup.enter="logPage = 1; loadLogs()"
          />
          <el-select v-model="logStatus" clearable placeholder="发送状态" style="width: 130px" @change="logPage = 1; loadLogs()">
            <el-option label="成功" value="sent" />
            <el-option label="失败" value="failed" />
            <el-option label="发送中" value="sending" />
          </el-select>
          <el-select v-model="logRange" placeholder="时间范围" style="width: 130px" @change="logPage = 1; loadLogs()">
            <el-option label="今天" value="today" />
            <el-option label="7天" value="7d" />
            <el-option label="30天" value="30d" />
            <el-option label="自定义" value="custom" />
          </el-select>
          <el-date-picker
            v-if="logRange === 'custom'"
            v-model="logCustomFrom"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="起"
            style="width: 140px"
            @change="logPage = 1; loadLogs()"
          />
          <el-date-picker
            v-if="logRange === 'custom'"
            v-model="logCustomUntil"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="止"
            style="width: 140px"
            @change="logPage = 1; loadLogs()"
          />
          <div class="spacer" />
          <el-button :loading="exporting" @click="exportLogs">导出 CSV</el-button>
          <el-button @click="openLogCol">列设置</el-button>
        </div>
        <el-table v-loading="loading" :data="logItems" border stripe size="small">
          <template v-for="colKey in logVisibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'sent_at'" label="发送时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.sent_at, { withSeconds: false }) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'merchant_name'" prop="merchant_name" label="商家" min-width="120" />
          <el-table-column v-if="colKey === 'purpose'" prop="purpose_label" label="用途" width="90" />
          <el-table-column v-if="colKey === 'sms_signature'" prop="sms_signature" label="签名" width="120" />
          <el-table-column v-if="colKey === 'template_name'" prop="template_name" label="模板" min-width="120" />
          <el-table-column v-if="colKey === 'mobile'" prop="mobile_masked" label="接收手机" width="130" />
          <el-table-column v-if="colKey === 'status'" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="logStatusTag[row.status] || 'info'" size="small">{{ row.status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'order_no'" label="关联单号" width="120">
            <template #default="{ row }">
              <code v-if="row.related_order_no">{{ row.related_order_no }}</code>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openLog(row)">详情</el-button>
              <el-button v-if="row.actions.includes('retry')" link type="warning" @click="retryLog(row)">重试</el-button>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="logPage"
            v-model:page-size="logPageSize"
            :total="logTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadLogs"
            @size-change="logPage = 1; loadLogs()"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="saveChannelVisible" title="保存短信服务商凭据？" width="480px">
      <el-form label-width="180px">
        <el-form-item label="AccessKey ID（只读）">
          <code>{{ channelForm.access_key_id || channelCfg?.access_key_id_masked || '—' }}</code>
        </el-form-item>
        <el-form-item label="Secret">
          {{ channelForm.access_key_secret ? '已更新（不回显明文）' : '未变更（沿用已保存）' }}
        </el-form-item>
        <el-form-item label="影响说明">
          全平台短信下发（领权/通知/测试）依赖此凭据；保存后建议立即「连通性测试」
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveChannelVisible = false">取消</el-button>
        <el-button type="primary" :loading="credActing" @click="submitSaveChannel">确认保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="sigDrawer" size="520px" :title="sigDrawerTitle" @close="closeSigDrawer">
      <div class="sig-drawer">
        <div v-if="viewSig" class="sig-drawer__body">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="关联商家">{{ viewSig.merchant_name }}</el-descriptions-item>
            <el-descriptions-item label="短信签名">{{ viewSig.content }}</el-descriptions-item>
            <el-descriptions-item label="供应商审核">
              <el-tag :type="sigStatusType(viewSig.status)" size="small">{{ viewSig.status_label }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="viewSig.reject_reason" label="驳回原因">
              <span class="reject-text">{{ viewSig.reject_reason }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="签名用途说明">{{ viewSig.remark || '—' }}</el-descriptions-item>
            <el-descriptions-item label="资质材料">
              <div v-if="Object.keys(viewSig.qualification_files || {}).length" class="materials-panel materials-panel--readonly">
                <div class="materials-list">
                  <div v-if="viewSig.qualification_files.business_license" class="material-readonly-row">
                    <span>营业执照</span>
                    <el-tag type="success" size="small">已上传</el-tag>
                  </div>
                  <div v-if="viewSig.qualification_files.trademark" class="material-readonly-row">
                    <span>商标授权（如有）</span>
                    <el-tag type="success" size="small">已上传</el-tag>
                  </div>
                </div>
              </div>
              <span v-else class="muted">未上传</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <template v-else>
          <div class="sig-drawer__body">
            <el-alert
              v-if="sigResubmitId && sigRejectReason"
              type="error"
              :closable="false"
              show-icon
              class="sig-reject-alert"
              title="上次驳回原因"
              :description="sigRejectReason"
            />
            <el-form label-position="top" class="sig-drawer__form">
              <el-form-item v-if="sigResubmitId" label="关联商家" required>
                <el-input :model-value="sigMerchantName" disabled />
              </el-form-item>
              <el-form-item v-else label="关联商家" required>
                <el-select
                  v-model="sigForm.tenant_id"
                  filterable
                  placeholder="请选择商家"
                  style="width: 100%"
                >
                  <el-option v-for="m in merchants" :key="m.tenant_id" :label="m.name" :value="m.tenant_id" />
                </el-select>
              </el-form-item>
              <el-form-item label="短信签名" required>
                <el-input v-model="sigForm.content" placeholder="【智学课堂】" maxlength="14" />
                <p class="form-tip">2–12 字，须含【】；与营业执照主体或商标一致</p>
              </el-form-item>
              <el-form-item label="签名用途说明">
                <el-input
                  v-model="sigForm.remark"
                  type="textarea"
                  :rows="3"
                  placeholder="如：抖店公域领权短信 · 与营业执照主体一致"
                />
              </el-form-item>
              <el-form-item label="资质材料">
                <p class="form-tip">
                  支持图片或 PDF，单文件不超过 10MB。
                  {{ sigResubmitId ? '驳回后请补全或更新材料后再提交。' : '新建时请先选择关联商家再上传。' }}
                </p>
                <div class="materials-panel">
                  <div class="materials-list">
                    <ShopMaterialUpload
                      doc-type="business_license"
                      title="营业执照"
                      :optional="true"
                      :disabled="!sigForm.tenant_id"
                      :file-id="sigForm.qualification_files.business_license || ''"
                      :file-name="sigForm.file_names.business_license || ''"
                      :upload-fn="platformUpload"
                      @uploaded="onMatUploaded"
                      @cleared="onMatCleared"
                    />
                    <ShopMaterialUpload
                      doc-type="trademark"
                      title="商标授权（如有）"
                      :optional="true"
                      :disabled="!sigForm.tenant_id"
                      :file-id="sigForm.qualification_files.trademark || ''"
                      :file-name="sigForm.file_names.trademark || ''"
                      :upload-fn="platformUpload"
                      @uploaded="onMatUploaded"
                      @cleared="onMatCleared"
                    />
                  </div>
                </div>
              </el-form-item>
            </el-form>
          </div>
          <div class="sig-drawer__footer">
            <el-button @click="closeSigDrawer">取消</el-button>
            <el-button type="primary" :loading="sigSubmitting" @click="submitSignature">
              {{ sigResubmitId ? '重新提交供应商审核' : '提交供应商审核' }}
            </el-button>
          </div>
        </template>
      </div>
    </el-drawer>

    <el-drawer v-model="tplDrawer" size="560px" :title="tplEditingId ? '编辑模板' : '登记新模板'">
      <el-form label-position="top">
        <el-form-item label="模板名称" required>
          <el-input v-model="tplForm.name" />
        </el-form-item>
        <el-form-item label="供应商 Template Code" required>
          <el-input v-model="tplForm.template_code" :disabled="!!tplEditingId" placeholder="SMS_2847xxxx" />
        </el-form-item>
        <el-form-item label="用途" required>
          <el-select v-model="tplForm.purpose" :disabled="!!tplEditingId" style="width: 100%">
            <el-option label="领权" value="claim_link" />
            <el-option label="平台通知" value="notify" />
            <el-option label="测试" value="test" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板内容（只读对照）">
          <el-input v-model="tplForm.content_preview" type="textarea" rows="3" />
        </el-form-item>
        <el-form-item v-if="!tplEditingId && tplForm.purpose === 'claim_link'">
          <el-checkbox v-model="tplForm.is_default_claim">设为默认领权模板</el-checkbox>
        </el-form-item>
        <el-button type="primary" :loading="tplSubmitting" @click="submitTemplate">保存登记</el-button>
      </el-form>
    </el-drawer>

    <el-drawer v-model="asgDrawer" size="520px" title="为商家分配签名与领权模板">
      <p class="muted">分配短信资源 · {{ asgForm.merchant_name || '请选择商家' }}</p>
      <el-form label-position="top">
        <el-form-item v-if="!asgForm.merchant_name || !asgForm.tenant_id" label="关联商家" required>
          <el-select
            v-model="asgForm.tenant_id"
            filterable
            placeholder="请选择商家"
            style="width: 100%"
            @change="onAsgMerchantChange"
          >
            <el-option v-for="m in merchants" :key="m.tenant_id" :label="m.name" :value="m.tenant_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="领权短信签名" required>
          <el-select v-model="asgForm.sms_signature_id" placeholder="仅已通过" style="width: 100%">
            <el-option v-for="s in asgOptions.signatures" :key="s.id" :label="s.content" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="领权短信模板" required>
          <el-select v-model="asgForm.claim_template_id" placeholder="仅已通过 · 领权用途" style="width: 100%">
            <el-option
              v-for="t in asgOptions.templates"
              :key="t.id"
              :label="`${t.name} · ${t.template_code}`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <p class="gap-note">分配后商家短信与领权页只读展示；商家仅可改领权域名/过期天数。</p>
        <el-button type="primary" :loading="asgSubmitting" @click="submitAssign">确认分配</el-button>
      </el-form>
    </el-drawer>

    <el-drawer v-model="logDrawer" size="560px" title="发送记录详情">
      <el-descriptions v-if="logDetail" :column="1" border>
        <el-descriptions-item label="发送时间">{{ formatDateTime(logDetail.sent_at) }}</el-descriptions-item>
        <el-descriptions-item label="商家">
          {{ logDetail.merchant_name }}
          <el-button link type="primary" @click="goMerchant(logDetail.tenant_id)">商家详情</el-button>
        </el-descriptions-item>
        <el-descriptions-item label="接收手机">
          {{ logDetail.mobile || logDetail.mobile_masked }}
          <el-button v-if="!logDetail.mobile" link type="primary" @click="revealMobile">👁</el-button>
        </el-descriptions-item>
        <el-descriptions-item label="用途">
          {{ logDetail.purpose_label }}
          <span v-if="logDetail.quota_note"> · {{ logDetail.quota_note }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="签名 / 模板">
          {{ logDetail.sms_signature || '—' }} · {{ logDetail.template_name || '—' }}
          <code v-if="logDetail.template_code">{{ logDetail.template_code }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="实际内容（脱敏）">{{ logDetail.content }}</el-descriptions-item>
        <el-descriptions-item label="供应商 BizId">{{ logDetail.provider_msg_id || '—' }}</el-descriptions-item>
        <el-descriptions-item label="触发来源">{{ logDetail.trigger_source || '—' }}</el-descriptions-item>
        <el-descriptions-item label="关联订单">{{ logDetail.related_order_no || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ logDetail.status_label }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="sigColDlg"
      v-model:columns="sigColDraft"
      @save="saveSigCol"
    />
    <CrmColumnSettingsDialog
      v-model:visible="tplColDlg"
      v-model:columns="tplColDraft"
      @save="saveTplCol"
    />
    <CrmColumnSettingsDialog
      v-model:visible="asgColDlg"
      v-model:columns="asgColDraft"
      @save="saveAsgCol"
    />
    <CrmColumnSettingsDialog
      v-model:visible="logColDlg"
      v-model:columns="logColDraft"
      @save="saveLogCol"
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
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.cfg-form {
  max-width: 640px;
}
.cfg-ops {
  display: flex;
  gap: 8px;
  margin: 8px 0 16px;
}
.gap-note,
.muted {
  color: #909399;
  font-size: 12px;
  margin: 8px 0 12px;
}
code {
  font-size: 12px;
}
</style>
