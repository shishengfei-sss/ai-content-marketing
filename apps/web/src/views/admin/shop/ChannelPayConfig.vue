<script setup>
/** 对照 PRD 06#p06 · #p06-doudian · #p06-wechat-pay · #p06a · #p06b · #p06c · #p06d · #p06-onboarding-list · #p06e
 * 缺口：微信开放平台票据未接；通知商家站内信未接通；连通性测试为凭据完备性探测（不调外部开放平台）；导出完成站内信本批不接。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../../api/client'
import { useAuthStore } from '../../../stores/auth'
import { formatDateTime } from '../../../utils/datetime'
import ShopPaymentOnboardingPanel from '../../../components/shop/ShopPaymentOnboardingPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const COLUMN_STORAGE_KEY = 'shop-p06-onboarding-columns'
const ALL_COLUMNS = [
  { key: 'merchant_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'entity_type', label: '主体', defaultVisible: true },
  { key: 'onboarding_status', label: '进件状态', defaultVisible: true },
  { key: 'wx_sub_mch_id', label: '子商户号', defaultVisible: true },
  { key: 'settlement', label: '结算账户', defaultVisible: true },
  { key: 'submitted_at', label: '最近提交', defaultVisible: true },
  { key: 'account_manager_name', label: '商家管家', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
]

const TAB_KEYS = ['doudian', 'wechat-pay', 'onboarding', 'wechat-open']
const activeTab = ref('doudian')
const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref('当前筛选')
const acting = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQ = ref('')
const statusChip = ref('')
const entityType = ref('')
const managerId = ref('')
const statusCounts = ref({})
const managers = ref([])
const sortBy = ref('submitted_at')
const sortDir = ref('desc')
const channelCfg = ref(null)
const drawerVisible = ref(false)
const drawerDetail = ref(null)
const columnDialogVisible = ref(false)
const columnDraft = ref([])
const visibleColumns = ref(loadColumnSettings())

const canChannel = computed(() => auth.hasPlatformShopPermission('platform.shop.channel'))

const doudianForm = reactive({ app_key: '', app_secret: '' })
const wechatForm = reactive({
  mch_id: '',
  app_id: '',
  api_v3_key: '',
  cert_pem: '',
  cert_key: '',
  platform_pub: '',
  cert_name: '',
})
const rotateSecret = ref('')
const rotateV3 = ref('')
const rotateCertPem = ref('')
const rotateCertKey = ref('')
const rotateCertName = ref('')
const saveDoudianVisible = ref(false)
const rotateDoudianVisible = ref(false)
const saveWechatVisible = ref(false)
const rotateCertVisible = ref(false)
const rotateV3Visible = ref(false)
const credActing = ref(false)

const doudianCfg = computed(() => channelCfg.value?.doudian || {})
const wechatCfg = computed(() => channelCfg.value?.wechat_pay || {})

function connectivityText(row) {
  if (!row?.last_tested_at) return '未测试'
  const tag = row.last_test_ok ? '通过' : '失败'
  const t = formatDateTime(row.last_tested_at, { withSeconds: false })
  return `上次测试 ${tag}（${t}）`
}

function savedText(row) {
  if (!row?.updated_at) return '—'
  const t = formatDateTime(row.updated_at, { withSeconds: false })
  return row.updated_by_name ? `${t} · ${row.updated_by_name}` : t
}

function readTextFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsText(file)
  })
}

async function onCertPair(ev, target) {
  const files = [...(ev.target.files || [])]
  ev.target.value = ''
  if (!files.length) return
  try {
    let pem = ''
    let key = ''
    const names = []
    for (const f of files) {
      const text = await readTextFile(f)
      names.push(f.name)
      if (text.includes('BEGIN CERTIFICATE')) pem = text
      else if (text.includes('BEGIN') && text.includes('PRIVATE KEY')) key = text
      else if (f.name.includes('key')) key = text
      else pem = text
    }
    if (target === 'save') {
      wechatForm.cert_pem = pem
      wechatForm.cert_key = key
      wechatForm.cert_name = names.join(' + ')
    } else {
      rotateCertPem.value = pem
      rotateCertKey.value = key
      rotateCertName.value = names.join(' + ')
    }
    ElMessage.success('已选择证书文件')
  } catch (e) {
    ElMessage.error(e.message || '读取证书失败')
  }
}

function openSaveDoudian() {
  if (!doudianForm.app_key.trim() || doudianForm.app_key.trim().length < 8) {
    ElMessage.warning('AppKey 格式错误')
    return
  }
  if (!doudianCfg.value.configured && !doudianForm.app_secret.trim()) {
    ElMessage.warning('请填写抖音应用密钥')
    return
  }
  saveDoudianVisible.value = true
}

async function submitSaveDoudian() {
  credActing.value = true
  try {
    const { data } = await adminApi.saveShopDoudianConfig({
      app_key: doudianForm.app_key.trim(),
      app_secret: doudianForm.app_secret.trim() || undefined,
    })
    channelCfg.value = data
    doudianForm.app_secret = ''
    saveDoudianVisible.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    credActing.value = false
  }
}

function openRotateDoudian() {
  if (!doudianCfg.value.configured) {
    ElMessage.warning('请先完成首次配置')
    return
  }
  rotateSecret.value = ''
  rotateDoudianVisible.value = true
}

async function submitRotateDoudian() {
  if (!rotateSecret.value.trim()) {
    ElMessage.warning('请填写新抖音应用密钥')
    return
  }
  credActing.value = true
  try {
    const { data } = await adminApi.rotateShopDoudianSecret({ app_secret: rotateSecret.value.trim() })
    channelCfg.value = data
    rotateDoudianVisible.value = false
    ElMessage.success('已轮换')
  } catch (e) {
    ElMessage.error(e.message || '轮换失败')
  } finally {
    credActing.value = false
  }
}

async function testDoudian() {
  credActing.value = true
  try {
    const { data } = await adminApi.testShopDoudianConfig()
    channelCfg.value = data
    ElMessage.success(data?.doudian?.last_test_ok ? '连通性测试通过' : '连通性测试失败')
  } catch (e) {
    ElMessage.error(e.message || '请先保存配置')
  } finally {
    credActing.value = false
  }
}

function openSaveWechat() {
  if (!wechatForm.mch_id.trim() || !wechatForm.app_id.trim()) {
    ElMessage.warning('服务商商户号与 AppID 不能为空')
    return
  }
  if (!wechatCfg.value.cert_serial && (!wechatForm.cert_pem || !wechatForm.cert_key)) {
    ElMessage.warning('请先上传 API 证书')
    return
  }
  if (!wechatCfg.value.configured && wechatForm.api_v3_key.trim().length !== 32) {
    ElMessage.warning('v3 密钥长度须 32 位')
    return
  }
  if (wechatForm.api_v3_key.trim() && wechatForm.api_v3_key.trim().length !== 32) {
    ElMessage.warning('v3 密钥长度须 32 位')
    return
  }
  saveWechatVisible.value = true
}

async function submitSaveWechat() {
  credActing.value = true
  try {
    const { data } = await adminApi.saveShopWechatPayConfig({
      mch_id: wechatForm.mch_id.trim(),
      app_id: wechatForm.app_id.trim(),
      api_v3_key: wechatForm.api_v3_key.trim() || undefined,
      cert_pem: wechatForm.cert_pem || undefined,
      cert_key: wechatForm.cert_key || undefined,
      platform_pub: wechatForm.platform_pub || undefined,
    })
    channelCfg.value = data
    wechatForm.api_v3_key = ''
    wechatForm.cert_pem = ''
    wechatForm.cert_key = ''
    wechatForm.platform_pub = ''
    saveWechatVisible.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    credActing.value = false
  }
}

function openRotateCert() {
  if (!wechatCfg.value.configured) {
    ElMessage.warning('请先保存配置')
    return
  }
  rotateCertPem.value = ''
  rotateCertKey.value = ''
  rotateCertName.value = ''
  rotateCertVisible.value = true
}

async function submitRotateCert() {
  if (!rotateCertPem.value || !rotateCertKey.value) {
    ElMessage.warning('请上传新证书文件')
    return
  }
  credActing.value = true
  try {
    const { data } = await adminApi.rotateShopWechatCert({
      cert_pem: rotateCertPem.value,
      cert_key: rotateCertKey.value,
    })
    channelCfg.value = data
    rotateCertVisible.value = false
    ElMessage.success('已轮换证书')
  } catch (e) {
    ElMessage.error(e.message || '证书解析失败')
  } finally {
    credActing.value = false
  }
}

function openRotateV3() {
  if (!wechatCfg.value.configured) {
    ElMessage.warning('请先保存配置')
    return
  }
  rotateV3.value = ''
  rotateV3Visible.value = true
}

async function submitRotateV3() {
  if (rotateV3.value.trim().length !== 32) {
    ElMessage.warning('v3 密钥长度须 32 位')
    return
  }
  credActing.value = true
  try {
    const { data } = await adminApi.rotateShopWechatV3({ api_v3_key: rotateV3.value.trim() })
    channelCfg.value = data
    rotateV3Visible.value = false
    ElMessage.success('已轮换密钥')
  } catch (e) {
    ElMessage.error(e.message || '轮换失败')
  } finally {
    credActing.value = false
  }
}

async function testWechat() {
  credActing.value = true
  try {
    const { data } = await adminApi.testShopWechatPayConfig()
    channelCfg.value = data
    ElMessage.success(data?.wechat_pay?.last_test_ok ? '连通性测试通过' : '连通性测试失败')
  } catch (e) {
    ElMessage.error(e.message || '请先保存配置')
  } finally {
    credActing.value = false
  }
}

const statusTag = {
  not_submitted: 'info',
  submitted: 'warning',
  rejected: 'danger',
  approved: 'success',
}

const chips = computed(() => [
  { key: '', label: '全部', count: statusCounts.value.all },
  { key: 'not_submitted', label: '未提交', count: statusCounts.value.not_submitted },
  { key: 'submitted', label: '审核中', count: statusCounts.value.submitted },
  { key: 'rejected', label: '已驳回', count: statusCounts.value.rejected },
  { key: 'approved', label: '已开通', count: statusCounts.value.approved },
])

function loadColumnSettings() {
  const defaults = ALL_COLUMNS.filter((c) => c.defaultVisible).map((c) => c.key)
  try {
    const raw = localStorage.getItem(COLUMN_STORAGE_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed) || !parsed.length) return defaults
    const locked = ALL_COLUMNS.filter((c) => c.locked).map((c) => c.key)
    const merged = [...new Set([...locked, ...parsed])]
    return merged.filter((key) => ALL_COLUMNS.some((c) => c.key === key))
  } catch {
    return defaults
  }
}

function saveColumnSettings() {
  const locked = ALL_COLUMNS.filter((c) => c.locked).map((c) => c.key)
  const next = [...new Set([...locked, ...columnDraft.value])]
  visibleColumns.value = next.filter((key) => ALL_COLUMNS.some((c) => c.key === key))
  localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(visibleColumns.value))
  columnDialogVisible.value = false
  ElMessage.success('列设置已保存')
}

function openColumnSettings() {
  columnDraft.value = ALL_COLUMNS.filter(
    (c) => !c.locked && visibleColumns.value.includes(c.key),
  ).map((c) => c.key)
  columnDialogVisible.value = true
}

function isColVisible(key) {
  return visibleColumns.value.includes(key)
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
    sortDir.value = prop === 'merchant' ? 'asc' : 'desc'
  }
  page.value = 1
  loadList()
}

function buildParams() {
  return {
    status: statusChip.value || undefined,
    q: searchQ.value.trim() || undefined,
    entity_type: entityType.value || undefined,
    account_manager_user_id: managerId.value || undefined,
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
    page: page.value,
    page_size: pageSize.value,
  }
}

async function loadChannelCfg() {
  try {
    const { data } = await adminApi.getShopChannelConfig()
    channelCfg.value = data
  } catch (e) {
    if (!isBenignEmptyError(e)) ElMessage.error(e.message || '加载渠道配置失败')
  }
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopPaymentOnboarding(buildParams())
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
    managers.value = data.account_managers || []
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

function setChip(key) {
  statusChip.value = key
  onSearch()
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

async function exportList(mode) {
  exporting.value = true
  try {
    const body = {
      status: statusChip.value || undefined,
      q: searchQ.value.trim() || undefined,
      entity_type: entityType.value || undefined,
      account_manager_user_id: managerId.value || undefined,
      sort_by: sortBy.value,
      sort_dir: sortDir.value,
    }
    if (mode === 'columns') {
      body.columns = visibleColumns.value.filter((k) => k !== 'ops')
    }
    const { data } = await adminApi.createShopPaymentOnboardingExport(body)
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
    const res = await adminApi.getShopPaymentOnboardingExportFile(exportTask.value.id)
    downloadBlob(res.data, exportTask.value.file_name || 'shop-payment-onboarding.csv')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

async function openDrawer(row) {
  try {
    const { data } = await adminApi.getShopPaymentOnboarding(row.tenant_id)
    drawerDetail.value = data
    drawerVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载详情失败')
  }
}

function goP02b(row) {
  router.push(`/admin/shop/merchants/${row.tenant_id}?tab=payment`)
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function doRefresh() {
  if (!drawerDetail.value) return
  acting.value = true
  try {
    const { data } = await adminApi.refreshShopPaymentOnboarding(drawerDetail.value.tenant_id)
    drawerDetail.value = data
    ElMessage.success('已刷新')
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '刷新失败')
  } finally {
    acting.value = false
  }
}

async function doSubmitWechat() {
  if (!drawerDetail.value) return
  acting.value = true
  try {
    const { data } = await adminApi.submitShopPaymentWechat(drawerDetail.value.tenant_id)
    drawerDetail.value = data
    ElMessage.success('已代提微信')
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '代提失败')
  } finally {
    acting.value = false
  }
}

async function doNotify() {
  if (!drawerDetail.value) return
  acting.value = true
  try {
    const { data } = await adminApi.notifyShopPaymentMerchant(drawerDetail.value.tenant_id)
    ElMessage.success(data?.message || '已通知商家')
    const { data: fresh } = await adminApi.getShopPaymentOnboarding(drawerDetail.value.tenant_id)
    drawerDetail.value = fresh
    await loadList()
  } catch (e) {
    ElMessage.error(e.message || '通知失败')
  } finally {
    acting.value = false
  }
}

async function doReveal() {
  if (!drawerDetail.value) return
  try {
    const { data } = await adminApi.revealShopPaymentSensitive(drawerDetail.value.tenant_id)
    drawerDetail.value = data
  } catch (e) {
    ElMessage.error(e.message || '揭露失败')
  }
}

async function doApprove() {
  if (!drawerDetail.value) return
  try {
    const { value } = await ElMessageBox.prompt('子商户号（8–12 位数字）', '开通', {
      confirmButtonText: '确认开通',
      cancelButtonText: '取消',
      inputPattern: /^\d{8,12}$/,
      inputErrorMessage: '子商户号须为 8–12 位数字',
    })
    acting.value = true
    const { data } = await adminApi.approveShopPaymentOnboarding(drawerDetail.value.tenant_id, {
      wx_sub_mch_id: value,
    })
    drawerDetail.value = data
    ElMessage.success('已开通')
    await loadList()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  } finally {
    acting.value = false
  }
}

async function doReject() {
  if (!drawerDetail.value) return
  try {
    const { value } = await ElMessageBox.prompt('驳回原因（≥4字）', '驳回', {
      confirmButtonText: '确认驳回',
      cancelButtonText: '取消',
      inputPattern: /.{4,}/,
      inputErrorMessage: '驳回原因至少 4 字',
    })
    acting.value = true
    const { data } = await adminApi.rejectShopPaymentOnboarding(drawerDetail.value.tenant_id, {
      reason: value,
    })
    drawerDetail.value = data
    ElMessage.success('已驳回')
    await loadList()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  } finally {
    acting.value = false
  }
}

function applyRouteTab() {
  const t = String(route.query.tab || '')
  if (TAB_KEYS.includes(t)) activeTab.value = t
}

async function maybeOpenFromQuery() {
  const tid = route.query.tenant_id
  if (tid && typeof tid === 'string') {
    activeTab.value = 'onboarding'
    await openDrawer({ tenant_id: tid })
  }
}

watch(
  () => route.query.tab,
  () => applyRouteTab(),
)

watch(activeTab, (t) => {
  if (t === 'onboarding') loadList()
})

onMounted(async () => {
  applyRouteTab()
  await loadChannelCfg()
  if (activeTab.value === 'onboarding') await loadList()
  await maybeOpenFromQuery()
})
</script>

<template>
  <div class="page-card" data-testid="shop-channels">
    <div class="p06-extra">
      <el-button link type="primary" @click="router.push('/admin/shop/sms')">短信管理 →</el-button>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="抖店公域" name="doudian">
        <el-form label-width="160px" class="cfg-form">
          <el-form-item label="抖音应用 Key" required>
            <el-input v-model="doudianForm.app_key" :placeholder="doudianCfg.app_key_masked || '请输入'" />
          </el-form-item>
          <el-form-item label="抖音应用密钥" required>
            <el-input v-model="doudianForm.app_secret" type="password" show-password placeholder="脱敏展示，留空则不改" />
          </el-form-item>
          <el-form-item label="回调 URL（只读）">
            <code>{{ channelCfg?.doudian_webhook_url || '—' }}</code>
            <el-button
              v-if="channelCfg?.doudian_webhook_url"
              link
              type="primary"
              @click="copyText(channelCfg.doudian_webhook_url)"
            >
              复制
            </el-button>
          </el-form-item>
          <el-form-item label="上次保存（只读）">{{ savedText(doudianCfg) }}</el-form-item>
          <el-form-item label="连通性（只读）">{{ connectivityText(doudianCfg) }}</el-form-item>
        </el-form>
        <div v-if="canChannel" class="cfg-ops">
          <el-button type="primary" @click="openSaveDoudian">保存配置</el-button>
          <el-button type="warning" plain @click="openRotateDoudian">密钥轮换</el-button>
          <el-button :loading="credActing" @click="testDoudian">连通性测试</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="微信支付服务商" name="wechat-pay">
        <el-form label-width="180px" class="cfg-form">
          <el-form-item label="服务商商户号" required>
            <el-input v-model="wechatForm.mch_id" :placeholder="wechatCfg.mch_id_masked || '请输入'" />
          </el-form-item>
          <el-form-item label="服务商 AppID" required>
            <el-input v-model="wechatForm.app_id" :placeholder="wechatCfg.app_id_masked || '请输入'" />
          </el-form-item>
          <el-form-item label="API v3 密钥" required>
            <el-input v-model="wechatForm.api_v3_key" type="password" show-password placeholder="脱敏展示，留空则不改" maxlength="32" />
          </el-form-item>
          <el-form-item label="商户 API 证书">
            <div>
              <span v-if="wechatCfg.cert_serial">
                已配置 · 序列号 {{ wechatCfg.cert_serial }}
                <span v-if="wechatCfg.cert_expires"> · 有效期至 {{ wechatCfg.cert_expires }}</span>
              </span>
              <span v-else>未上传</span>
              <div class="cert-row">
                <input type="file" multiple accept=".pem,.key,.crt" @change="(e) => onCertPair(e, 'save')" />
                <span v-if="wechatForm.cert_name" class="muted">已选 {{ wechatForm.cert_name }}</span>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="平台公钥（可选）">
            <el-input v-model="wechatForm.platform_pub" type="textarea" rows="2" placeholder="选填，用于敏感字段加密" />
          </el-form-item>
          <el-form-item label="支付结果 notify（只读）">
            <code>{{ channelCfg?.wechat_pay_notify_url || '—' }}</code>
            <el-button
              v-if="channelCfg?.wechat_pay_notify_url"
              link
              type="primary"
              @click="copyText(channelCfg.wechat_pay_notify_url)"
            >
              复制
            </el-button>
          </el-form-item>
          <el-form-item label="退款结果 notify（只读）">
            <code>{{ channelCfg?.wechat_refund_notify_url || '—' }}</code>
            <el-button
              v-if="channelCfg?.wechat_refund_notify_url"
              link
              type="primary"
              @click="copyText(channelCfg.wechat_refund_notify_url)"
            >
              复制
            </el-button>
          </el-form-item>
          <el-form-item label="上次保存（只读）">{{ savedText(wechatCfg) }}</el-form-item>
          <el-form-item label="连通性（只读）">{{ connectivityText(wechatCfg) }}</el-form-item>
        </el-form>
        <div v-if="canChannel" class="cfg-ops">
          <el-button type="primary" @click="openSaveWechat">保存配置</el-button>
          <el-button type="warning" plain @click="openRotateCert">证书轮换</el-button>
          <el-button type="warning" plain @click="openRotateV3">v3 密钥轮换</el-button>
          <el-button :loading="credActing" @click="testWechat">连通性测试</el-button>
          <el-button @click="activeTab = 'onboarding'">商户进件管理 →</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="商户支付进件" name="onboarding">
        <div class="chips">
          <el-button
            v-for="c in chips"
            :key="c.key || 'all'"
            :type="statusChip === c.key ? 'primary' : 'default'"
            size="small"
            @click="setChip(c.key)"
          >
            {{ c.label }}
            <el-tag v-if="c.count != null" size="small" effect="plain" style="margin-left: 6px">
              {{ c.count }}
            </el-tag>
          </el-button>
        </div>
        <div class="toolbar">
          <el-input
            v-model="searchQ"
            clearable
            placeholder="搜索商家名 / 子商户号"
            style="width: 220px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          />
          <el-select
            v-model="managerId"
            clearable
            placeholder="商家管家"
            style="width: 160px"
            @change="onSearch"
          >
            <el-option label="未分配" value="none" />
            <el-option v-for="m in managers" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
          <el-select
            v-model="entityType"
            clearable
            placeholder="主体类型"
            style="width: 140px"
            @change="onSearch"
          >
            <el-option label="企业" value="enterprise" />
            <el-option label="个体" value="individual_business" />
            <el-option label="个人" value="personal" />
          </el-select>
          <el-button @click="onSearch">搜索</el-button>
          <div class="spacer" />
          <div class="toolbar-right">
            <el-dropdown trigger="click" @command="exportList">
              <el-button :loading="exporting">导出 ▾</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="current">当前筛选</el-dropdown-item>
                  <el-dropdown-item command="columns">列配置</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button @click="openColumnSettings">列设置</el-button>
          </div>
        </div>
        <el-table v-loading="loading" :data="items" border stripe size="small">
          <el-table-column v-if="isColVisible('merchant_name')" min-width="160">
            <template #header>
              <span class="sortable" @click="toggleSort('merchant')">商家 {{ sortIcon('merchant') }}</span>
            </template>
            <template #default="{ row }">{{ row.merchant_name }}</template>
          </el-table-column>
          <el-table-column v-if="isColVisible('entity_type')" label="主体" width="80">
            <template #default="{ row }">{{ row.entity_type_label }}</template>
          </el-table-column>
          <el-table-column v-if="isColVisible('onboarding_status')" label="进件状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTag[row.onboarding_status] || 'info'" size="small">
                {{ row.onboarding_status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="isColVisible('wx_sub_mch_id')" label="子商户号" width="140">
            <template #default="{ row }">
              <code v-if="row.wx_sub_mch_id_masked">{{ row.wx_sub_mch_id_masked }}</code>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column v-if="isColVisible('settlement')" label="结算账户" min-width="160">
            <template #default="{ row }">
              <span v-if="row.settlement_bank || row.settlement_account_masked">
                {{ row.settlement_bank }} {{ row.settlement_account_masked }}
              </span>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column v-if="isColVisible('submitted_at')" width="170">
            <template #header>
              <span class="sortable" @click="toggleSort('submitted_at')">最近提交 {{ sortIcon('submitted_at') }}</span>
            </template>
            <template #default="{ row }">
              {{ formatDateTime(row.submitted_at, { withSeconds: false }) }}
            </template>
          </el-table-column>
          <el-table-column
            v-if="isColVisible('account_manager_name')"
            label="商家管家"
            width="120"
          >
            <template #default="{ row }">{{ row.account_manager_name || '未分配' }}</template>
          </el-table-column>
          <el-table-column v-if="isColVisible('ops')" label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.actions.includes('view_materials')" link type="primary" @click="openDrawer(row)">
                查看材料
              </el-button>
              <el-button link type="primary" @click="goP02b(row)">商家详情</el-button>
              <el-button
                v-if="canChannel && row.actions.includes('refresh')"
                link
                type="warning"
                @click="openDrawer(row)"
              >
                刷新状态
              </el-button>
              <el-button v-if="row.actions.includes('notify')" link @click="openDrawer(row)">通知商家</el-button>
              <el-button v-if="row.actions.includes('remind')" link @click="openDrawer(row)">提醒商家</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadList"
            @size-change="onSearch"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="微信开放平台" name="wechat-open">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="component_verify_ticket">未接入</el-descriptions-item>
          <el-descriptions-item label="授权小程序数">—</el-descriptions-item>
        </el-descriptions>
        <p class="gap-note">第三方平台票据状态本批只读占位，未接开放平台。</p>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="drawerVisible" size="640px" :title="drawerDetail?.merchant_name || '进件详情'">
      <p v-if="drawerDetail" class="drawer-sub">
        租户 {{ String(drawerDetail.tenant_id).slice(0, 8) }}… · {{ drawerDetail.entity_type_label }}
        · 管家 {{ drawerDetail.account_manager_name || '未分配' }}
        ·
        <el-button link type="primary" @click="goP02b(drawerDetail)">商家详情 →</el-button>
      </p>
      <ShopPaymentOnboardingPanel
        :detail="drawerDetail"
        variant="p06e"
        :can-channel="canChannel"
        :acting="acting"
        @refresh="doRefresh"
        @submit-wechat="doSubmitWechat"
        @notify="doNotify"
        @reveal="doReveal"
        @approve="doApprove"
        @reject="doReject"
      />
    </el-drawer>

    <el-dialog v-model="saveDoudianVisible" title="保存抖音应用配置？" width="480px">
      <el-form label-width="160px">
        <el-form-item label="抖音应用 Key（只读）">{{ doudianForm.app_key }}</el-form-item>
        <el-form-item label="抖音应用密钥">已更新（不回显明文）</el-form-item>
        <el-form-item label="影响说明（只读）">全站抖店回流依赖此应用；保存后建议立即「连通性测试」</el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDoudianVisible = false">取消</el-button>
        <el-button type="primary" :loading="credActing" @click="submitSaveDoudian">确认保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rotateDoudianVisible" title="轮换抖音 AppSecret？" width="480px">
      <el-form label-width="160px">
        <el-form-item label="轮换说明（只读）">旧 Secret 24 小时内仍可用；期满仅新 Secret 有效。须在抖店开放平台同步更新</el-form-item>
        <el-form-item label="新抖音应用密钥" required>
          <el-input v-model="rotateSecret" type="password" show-password />
        </el-form-item>
        <el-form-item label="告警（只读）">
          当前 {{ channelCfg?.doudian_mapping_count || 0 }} 家商家已绑定抖店映射，轮换期间可能短暂回调失败
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rotateDoudianVisible = false">取消</el-button>
        <el-button type="warning" :loading="credActing" @click="submitRotateDoudian">确认轮换</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="saveWechatVisible" title="保存微信支付服务商配置？" width="480px">
      <el-form label-width="160px">
        <el-form-item label="服务商商户号（只读）">{{ wechatForm.mch_id }}</el-form-item>
        <el-form-item label="API v3 密钥">已更新（不回显明文）</el-form-item>
        <el-form-item label="商户 API 证书">
          {{ wechatCfg.cert_serial || wechatForm.cert_name || '已上传' }}
        </el-form-item>
        <el-form-item label="影响说明（只读）">全站私域支付、代进件、退款 notify 验签均依赖此配置；保存后建议「连通性测试」</el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveWechatVisible = false">取消</el-button>
        <el-button type="primary" :loading="credActing" @click="submitSaveWechat">确认保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rotateCertVisible" title="轮换微信支付 API 证书？" width="480px">
      <el-form label-width="160px">
        <el-form-item label="轮换说明（只读）">旧证书 24 小时内仍可用于验签；期满仅新证书有效。须在微信商户平台同步申请新证书</el-form-item>
        <el-form-item label="新证书文件" required>
          <input type="file" multiple accept=".pem,.key,.crt" @change="(e) => onCertPair(e, 'rotate')" />
          <div v-if="rotateCertName" class="muted">已选 {{ rotateCertName }}</div>
        </el-form-item>
        <el-form-item label="新证书序列号（只读）">解析后自动填入</el-form-item>
        <el-form-item label="告警（只读）">
          当前 {{ channelCfg?.wechat_sub_stats?.approved || 0 }} 家子商户已开通；轮换期间支付回调可能短暂验签失败
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rotateCertVisible = false">取消</el-button>
        <el-button type="warning" :loading="credActing" @click="submitRotateCert">确认轮换</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rotateV3Visible" title="轮换 API v3 密钥？" width="480px">
      <el-form label-width="140px">
        <el-form-item label="新 v3 密钥" required>
          <el-input v-model="rotateV3" type="password" show-password maxlength="32" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rotateV3Visible = false">取消</el-button>
        <el-button type="warning" :loading="credActing" @click="submitRotateV3">确认轮换</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="columnDialogVisible" title="列设置" width="420px">
      <el-checkbox-group v-model="columnDraft">
        <el-checkbox
          v-for="col in ALL_COLUMNS.filter((c) => !c.locked)"
          :key="col.key"
          :label="col.key"
        >
          {{ col.label }}
        </el-checkbox>
      </el-checkbox-group>
      <p class="gap-note">商家、操作列为锁定列，不可关闭。</p>
      <template #footer>
        <el-button @click="columnDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveColumnSettings">保存</el-button>
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
  </div>
</template>

<style scoped>
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.toolbar-right {
  display: flex;
  gap: 8px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.sortable {
  cursor: pointer;
  user-select: none;
}
.gap-note {
  color: #909399;
  font-size: 12px;
  margin-top: 12px;
}
.drawer-sub {
  color: #666;
  font-size: 12px;
  margin: 0 0 12px;
}
.p06-extra {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 4px;
}
.cfg-form { max-width: 720px; }
.cfg-ops { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 16px; }
.cert-row { margin-top: 6px; display: flex; gap: 8px; align-items: center; }
.muted { color: #909399; font-size: 12px; }
code {
  font-size: 12px;
}
</style>
