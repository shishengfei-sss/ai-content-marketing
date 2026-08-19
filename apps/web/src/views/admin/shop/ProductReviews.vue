<script setup>
/**
 * P09 商品合规审核。对照 PRD 06-平台端UI.html
 * #p09-pending-queue · #p09-review-panel · #p09-reviewed-queue · #p09a · #p09b · #p09c
 * 缺口：驳回/下架站内信未接通；机审 reject 提审时自动出队（对照 F6 可免人审）；
 * 是否首单公域按有无公域映射近似；关联内容为快照摘要。
 */
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'
import { useAuthStore } from '../../../stores/auth'
import { formatDateTime } from '../../../utils/datetime'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canReview = computed(() => auth.hasPlatformShopPermission('platform.shop.product.review'))
const canForceOff = computed(() => auth.hasPlatformShopPermission('platform.shop.product.force_off'))

const PENDING_COLS = [
  { key: 'product_name', label: '商品', locked: true, defaultVisible: true },
  { key: 'merchant_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'shop_name', label: '店铺', defaultVisible: true },
  { key: 'product_type', label: '类型', defaultVisible: true },
  { key: 'auto_result', label: '机审', defaultVisible: true },
  { key: 'submitted_at', label: '提交时间', defaultVisible: true },
  { key: 'status', label: '状态', locked: true, defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'category_path', label: '类目', defaultVisible: false },
]
const REVIEWED_COLS = [
  { key: 'product_name', label: '商品', locked: true, defaultVisible: true },
  { key: 'merchant_name', label: '商家', locked: true, defaultVisible: true },
  { key: 'shop_name', label: '店铺', defaultVisible: true },
  { key: 'product_type', label: '类型', defaultVisible: true },
  { key: 'manual_result', label: '审出结果', defaultVisible: true },
  { key: 'reviewed_at', label: '审出时间', defaultVisible: true },
  { key: 'sale_status', label: '在售状态', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'category_path', label: '类目', defaultVisible: false },
]

const tab = ref('pending')
const loading = ref(false)
const submitting = ref(false)
const items = ref([])
const total = ref(0)
const pendingCount = ref(0)
const flaggedCount = ref(0)
const reviewedCount = ref(0)
const categoryOptions = ref([])
const page = ref(1)
const pageSize = ref(20)
const searchQ = ref('')
const autoResult = ref('')
const categoryId = ref('')
const productStatus = ref('')
const adv = ref(false)
const submittedRange = ref(null)
const planLabel = ref('')
const firstPublic = ref('')
const sortBy = ref('submitted_at')
const sortDir = ref('desc')
const {
  visibleKeys: pendingVisibleKeys,
  columnDialogVisible: pendingColDialog,
  columnDraft: pendingColDraft,
  openColumnSettings: openPendingCol,
  saveColumnSettings: savePendingCol,
  isColVisible: isPendingCol,
} = useListColumnSettings(PENDING_COLS, 'shop-product-review-pending-columns')
const {
  visibleKeys: reviewedVisibleKeys,
  columnDialogVisible: reviewedColDialog,
  columnDraft: reviewedColDraft,
  openColumnSettings: openReviewedCol,
  saveColumnSettings: saveReviewedCol,
  isColVisible: isReviewedCol,
} = useListColumnSettings(REVIEWED_COLS, 'shop-product-review-reviewed-columns')

const selected = ref(null)
const reviewDrawer = ref(false)
const panelTab = ref('snapshot')
const note = ref('')
const rejectDlg = ref(false)
const rejectForm = reactive({ reject_code: '', reject_reason: '' })
const offDlg = ref(false)
const offReason = ref('')
const coverBlobUrl = ref('')
const lessonPreviewDlg = reactive({ visible: false, title: '', content: '' })
const refPreviewDlg = reactive({ visible: false, title: '', html: '' })
const coverPreviewDlg = reactive({ visible: false })

const AUTO_RULE_ROWS = [
  ['sensitive_word', '敏感词库'],
  ['exaggerated_claim', '夸大承诺'],
  ['prohibited_category', '禁售类目'],
  ['category_qualification', '类目资质'],
  ['media_compliance', '封面素材'],
  ['external_link', '外链引流'],
]

const TYPE_LABEL = { course: '课程', digital: '资料', service: '服务' }
const AUTO_LABEL = { pass: '通过', flag: '标黄', reject: '拒绝' }
const AUTO_TAG = { pass: 'success', flag: 'warning', reject: 'danger' }
const MANUAL_LABEL = { pending: '待审', approved: '已通过', rejected: '已驳回' }
const REJECT_CODE_LABEL = {
  sensitive: '敏感内容',
  qualification: '资质不符',
  false_ad: '虚假宣传',
  other: '其他',
}
const MANUAL_TAG = { pending: 'warning', approved: 'success', rejected: 'danger' }
const ENTITY_LABEL = { personal: '个人', individual_business: '个体', enterprise: '企业' }
const REFUND_LABEL = {
  before_fulfill: '履约前可退',
  always_allow: '随时可退',
  manual_only: '仅人工审核',
}
const RULE_LABEL = {
  sensitive_word: '敏感词库',
  exaggerated_claim: '夸大承诺',
  prohibited_category: '禁售类目',
  category_qualification: '类目资质',
  media_compliance: '封面素材',
  external_link: '外链引流',
}

const visibleKeys = computed(() => (tab.value === 'reviewed' ? reviewedVisibleKeys.value : pendingVisibleKeys.value))
function isCol(key) {
  return tab.value === 'reviewed' ? isReviewedCol(key) : isPendingCol(key)
}
function openCol() {
  if (tab.value === 'reviewed') openReviewedCol()
  else openPendingCol()
}

function centsYuan(cents) {
  return `¥ ${(Number(cents || 0) / 100).toFixed(2)}`
}
function saleText(row) {
  if (row.product_status === 'on_sale') return '在售'
  if (row.product_status === 'off_sale') return '已下架'
  return '未上架'
}
function refundText(row) {
  const code = row.snapshot_json?.refund_policy
  if (row.product_type === 'service' && code === 'before_fulfill') return '未使用可退'
  return REFUND_LABEL[code] || code || '—'
}
function snap(row) {
  return row?.snapshot_json || {}
}
function refSummary(row) {
  return row?.ref_summary || null
}
function autoDetailRows(row) {
  if (!row) return []
  const flags = row.auto_flags || []
  const hitByRule = Object.fromEntries(flags.filter((f) => f.rule).map((f) => [f.rule, f]))
  const rows = []
  for (const [key, label] of AUTO_RULE_ROWS) {
    const hit = hitByRule[key]
    if (hit) {
      rows.push({
        rule_label: label,
        level: hit.level || row.auto_result,
        snippet: hit.snippet || '—',
        message: hit.message || '—',
      })
    } else if (row.auto_result === 'pass') {
      rows.push({ rule_label: label, level: 'pass', snippet: '—', message: '未命中' })
    }
  }
  for (const hit of flags) {
    if (hit.rule && !AUTO_RULE_ROWS.some(([k]) => k === hit.rule)) {
      rows.push({
        rule_label: RULE_LABEL[hit.rule] || hit.rule,
        level: hit.level || row.auto_result,
        snippet: hit.snippet || '—',
        message: hit.message || '—',
      })
    }
  }
  if (!rows.length && row.auto_result === 'pass') {
    rows.push({
      rule_label: '综合结论',
      level: 'pass',
      snippet: '—',
      message: '机审通过，未命中敏感词/夸大承诺等规则',
    })
  }
  return rows
}

function revokeCoverBlob() {
  if (coverBlobUrl.value) {
    URL.revokeObjectURL(coverBlobUrl.value)
    coverBlobUrl.value = ''
  }
}
async function loadCoverBlob(reviewId) {
  revokeCoverBlob()
  if (!reviewId) return
  try {
    const { data } = await adminApi.getShopProductReviewCover(reviewId)
    if (data instanceof Blob) coverBlobUrl.value = URL.createObjectURL(data)
  } catch {
    coverBlobUrl.value = ''
  }
}
function coverDisplayUrl(row) {
  if (coverBlobUrl.value && selected.value?.id === row?.id) return coverBlobUrl.value
  return row?.cover_preview_url || snap(row).cover_url || ''
}

function openCoverPreview() {
  if (!coverDisplayUrl(selected.value)) return
  coverPreviewDlg.visible = true
}

function setReviewQuery(id) {
  const q = { ...route.query }
  if (id) q.review_id = String(id)
  else delete q.review_id
  router.replace({ query: q })
}

function saveBlob(blob, filename) {
  const data = blob instanceof Blob ? blob : new Blob([blob])
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'download'
  a.click()
  URL.revokeObjectURL(url)
}

async function previewLesson(lesson) {
  if (!selected.value?.id || !lesson?.id) return
  if (!lesson.previewable) {
    ElMessage.warning('该课时尚未上传可预览内容')
    return
  }
  try {
    const { data } = await adminApi.getShopProductReviewLesson(selected.value.id, lesson.id)
    if (data.media_type === 'article') {
      lessonPreviewDlg.title = data.title || lesson.title
      lessonPreviewDlg.content = data.content_body || ''
      lessonPreviewDlg.visible = true
      return
    }
    const { data: blob } = await adminApi.getShopProductReviewLessonMedia(selected.value.id, lesson.id)
    const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]))
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 120_000)
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

async function downloadLesson(lesson) {
  if (!selected.value?.id || !lesson?.id) return
  if (!lesson.previewable) {
    ElMessage.warning('该课时尚未上传可下载内容')
    return
  }
  try {
    const { data: detail } = await adminApi.getShopProductReviewLesson(selected.value.id, lesson.id)
    if (detail.media_type === 'article') {
      saveBlob(
        new Blob([detail.content_body || ''], { type: 'text/plain;charset=utf-8' }),
        `${detail.title || lesson.title || '课时'}.txt`,
      )
      return
    }
    const { data: blob } = await adminApi.getShopProductReviewLessonMedia(selected.value.id, lesson.id, {
      download: true,
    })
    saveBlob(blob, lesson.title || '课时媒体')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function refFileExt(file) {
  const n = String(file?.name || '').toLowerCase()
  const i = n.lastIndexOf('.')
  return i >= 0 ? n.slice(i) : ''
}

async function previewRefAsset(file) {
  if (!selected.value?.id || !file?.file_id) return
  const ext = refFileExt(file)
  if (ext === '.zip') {
    ElMessage.info('zip 请下载后本地解压')
    return
  }
  if (ext === '.doc') {
    ElMessage.info('旧版 .doc 请下载后用 Word 打开')
    return
  }
  try {
    if (ext === '.docx') {
      const { data: html } = await adminApi.getShopProductReviewRefAssetHtmlPreview(
        selected.value.id,
        file.file_id,
      )
      refPreviewDlg.title = file.name || 'Word 文档'
      refPreviewDlg.html = html || ''
      refPreviewDlg.visible = true
      return
    }
    const { data: blob } = await adminApi.getShopProductReviewRefAsset(selected.value.id, file.file_id)
    const type = ext === '.pdf' ? 'application/pdf' : blob?.type || 'application/octet-stream'
    const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob], { type }))
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 120_000)
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

async function downloadRefAsset(file) {
  if (!selected.value?.id || !file?.file_id) return
  try {
    const { data: blob } = await adminApi.getShopProductReviewRefAsset(selected.value.id, file.file_id, {
      download: true,
    })
    saveBlob(blob, file.name || '资料文件')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function listParams() {
  const params = {
    page: page.value,
    page_size: pageSize.value,
    q: searchQ.value.trim() || undefined,
    sort_by: sortBy.value || undefined,
    sort_dir: sortDir.value,
  }
  if (tab.value === 'pending') params.status = 'pending'
  else params.queue = tab.value
  if (tab.value !== 'reviewed' && autoResult.value) params.auto_result = autoResult.value
  if (categoryId.value) params.category_id = categoryId.value
  if (tab.value === 'reviewed' && productStatus.value) params.product_status = productStatus.value
  if (adv.value && submittedRange.value?.length === 2) {
    params.submitted_from = submittedRange.value[0]
    params.submitted_to = submittedRange.value[1]
  }
  if (adv.value && planLabel.value.trim()) params.plan_label = planLabel.value.trim()
  if (adv.value && (firstPublic.value === 'yes' || firstPublic.value === 'no')) {
    params.first_public = firstPublic.value
  }
  return params
}

async function load() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopProductReviews(listParams())
    items.value = data.items || []
    total.value = data.total || 0
    pendingCount.value = data.pending_count || 0
    flaggedCount.value = data.flagged_count || 0
    reviewedCount.value = data.reviewed_count || 0
    categoryOptions.value = data.category_options || []
    if (selected.value) {
      const fresh = items.value.find((x) => x.id === selected.value.id)
      selected.value = fresh || selected.value
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function downloadCsv(filename, header, rows) {
  const lines = [header.join(','), ...rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))]
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
function exportList() {
  if (tab.value === 'reviewed') {
    downloadCsv(
      '已审出队.csv',
      ['商品', '商家', '店铺', '类型', '审出结果', '审出时间', '在售状态'],
      items.value.map((r) => [
        r.product_name,
        r.merchant_name,
        r.shop_name || '—',
        TYPE_LABEL[r.product_type] || r.product_type,
        MANUAL_LABEL[r.manual_result] || r.manual_result,
        formatDateTime(r.reviewed_at),
        saleText(r),
      ]),
    )
  } else {
    downloadCsv(
      '待审队列.csv',
      ['商品', '商家', '店铺', '类型', '机审', '提交时间', '状态'],
      items.value.map((r) => [
        r.product_name,
        r.merchant_name,
        r.shop_name || '—',
        TYPE_LABEL[r.product_type] || r.product_type,
        AUTO_LABEL[r.auto_result] || r.auto_result,
        formatDateTime(r.submitted_at),
        MANUAL_LABEL[r.manual_result] || r.manual_result,
      ]),
    )
  }
}

function toggleSort(prop) {
  if (sortBy.value === prop) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortBy.value = prop
    sortDir.value = 'desc'
  }
  page.value = 1
  load()
}
function sortIcon(prop) {
  if (sortBy.value !== prop) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

async function selectRow(row, { openDrawer = false } = {}) {
  selected.value = row
  panelTab.value = 'snapshot'
  note.value = row.internal_note || ''
  if (openDrawer) reviewDrawer.value = true
  try {
    const { data } = await adminApi.getShopProductReview(row.id)
    selected.value = data
    await loadCoverBlob(data.id)
  } catch (e) {
    ElMessage.error(e.message || '加载审核单失败')
    if (openDrawer) reviewDrawer.value = false
  }
}

async function openReviewById(id) {
  if (!id) return
  const hit = items.value.find((x) => String(x.id) === String(id))
  if (hit) {
    openReview(hit)
    return
  }
  try {
    const { data } = await adminApi.getShopProductReview(id)
    await selectRow(data, { openDrawer: true })
    setReviewQuery(data.id)
  } catch (e) {
    ElMessage.error(e.message || '加载审核单失败')
  }
}

function openReview(row) {
  selectRow(row, { openDrawer: true })
  setReviewQuery(row.id)
}
function closeReview() {
  reviewDrawer.value = false
  selected.value = null
  revokeCoverBlob()
  setReviewQuery(null)
}
function openReject(row) {
  selected.value = row
  rejectForm.reject_code = ''
  rejectForm.reject_reason = ''
  rejectDlg.value = true
}
function openForceOff(row) {
  selected.value = row
  offReason.value = ''
  offDlg.value = true
}

async function doApprove() {
  if (!selected.value) return
  if (selected.value.auto_result === 'reject' && (note.value || '').trim().length < 4) {
    ElMessage.error('请填写覆写备注')
    return
  }
  submitting.value = true
  try {
    await adminApi.approveShopProductReview(selected.value.id, {
      note: note.value.trim() || undefined,
    })
    ElMessage.success('已通过')
    closeReview()
    await load()
  } catch (e) {
    ElMessage.error(e.message || '通过失败')
  } finally {
    submitting.value = false
  }
}
async function doReject() {
  if (!rejectForm.reject_code) {
    ElMessage.error('请填写驳回原因')
    return
  }
  if ((rejectForm.reject_reason || '').trim().length < 4) {
    ElMessage.error('请填写驳回原因')
    return
  }
  const target = selected.value
  if (!target) return
  submitting.value = true
  try {
    await adminApi.rejectShopProductReview(target.id, {
      reject_code: rejectForm.reject_code,
      reject_reason: rejectForm.reject_reason.trim(),
    })
    ElMessage.success('已驳回')
    rejectDlg.value = false
    closeReview()
    await load()
  } catch (e) {
    ElMessage.error(e.message || '驳回失败')
  } finally {
    submitting.value = false
  }
}
async function doForceOff() {
  if ((offReason.value || '').trim().length < 1) {
    ElMessage.error('请填写下架原因')
    return
  }
  const target = selected.value
  if (!target) return
  submitting.value = true
  try {
    await adminApi.forceOffShopProductReview(target.id, { reason: offReason.value.trim() })
    ElMessage.success('已强制下架')
    offDlg.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '下架失败')
  } finally {
    submitting.value = false
  }
}

function goMerchant(row) {
  if (!row?.tenant_id) return
  const href = router.resolve({ path: `/admin/shop/merchants/${row.tenant_id}` }).href
  window.open(href, '_blank', 'noopener,noreferrer')
}

function escHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]))
}

function safeCover(u) {
  const s = String(u || '').trim()
  if (!s) return ''
  if (s.startsWith('blob:')) return s
  if (s.startsWith('/') && !s.startsWith('//')) {
    const base = import.meta.env.VITE_API_BASE_URL || window.location.origin
    return `${base.replace(/\/$/, '')}${s}`
  }
  try {
    const x = new URL(s)
    if (x.protocol === 'http:' || x.protocol === 'https:') return s
  } catch {
    return ''
  }
  return ''
}

function renderBuyerPreviewHtml(data) {
  const name = escHtml(data.product_name || '商品')
  const sub = escHtml(data.subtitle || '')
  const intro = escHtml(data.intro || '')
  const shop = escHtml(data.shop_name || data.merchant_name || '')
  const price = `¥ ${((Number(data.price_cents) || 0) / 100).toFixed(2)}`
  const coverSrc = safeCover(data.cover_url)
  const cover = coverSrc
    ? `<img src="${escHtml(coverSrc)}" alt="" style="width:100%;max-height:220px;object-fit:cover;border-radius:8px" />`
    : `<div style="height:160px;background:#f5f5f5;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#999">封面</div>`
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${name} · 买家页预览</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#f6f7fb;color:#1f2937}
.wrap{max-width:420px;margin:24px auto;background:#fff;border-radius:12px;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.06);position:relative;overflow:hidden}
.wm{position:fixed;inset:0;pointer-events:none;z-index:9;display:flex;flex-wrap:wrap;align-content:space-around;justify-content:space-around;opacity:.14;transform:rotate(-22deg);font-size:42px;font-weight:700;color:#cf1322}
.wm span{margin:28px}
h1{font-size:18px;margin:12px 0 4px}
.sub{color:#666;font-size:13px;margin:0 0 8px}
.price{color:#1677ff;font-size:20px;font-weight:700}
.shop{font-size:12px;color:#888;margin-top:8px}
.intro{font-size:13px;line-height:1.6;margin-top:12px;color:#444}
.tag{display:inline-block;background:#fff2f0;color:#cf1322;border:1px solid #ffccc7;border-radius:4px;padding:2px 8px;font-size:12px}
</style></head><body>
<div class="wm">${Array.from({ length: 18 }, () => `<span>${escHtml(data.watermark || '未上架')}</span>`).join('')}</div>
<div class="wrap">
  <span class="tag">${escHtml(data.watermark || '未上架')}</span>
  ${cover}
  <h1>${name}</h1>
  <p class="sub">${sub || '—'}</p>
  <div class="price">${price}</div>
  <div class="shop">${shop}</div>
  <div class="intro">${intro || '—'}</div>
</div></body></html>`
}

async function previewBuyer() {
  if (!selected.value?.id) {
    ElMessage.warning('请先选择审核单')
    return
  }
  try {
    const [{ data }, coverRes] = await Promise.all([
      adminApi.getShopProductReviewBuyerPreview(selected.value.id),
      adminApi.getShopProductReviewCover(selected.value.id).catch(() => null),
    ])
    let coverSrc = ''
    if (coverRes?.data instanceof Blob) {
      coverSrc = URL.createObjectURL(coverRes.data)
    } else {
      coverSrc = safeCover(data.cover_url)
    }
    const w = window.open('', '_blank')
    if (!w) {
      ElMessage.error('请允许弹出窗口以预览买家页')
      if (coverSrc.startsWith('blob:')) URL.revokeObjectURL(coverSrc)
      return
    }
    w.document.write(renderBuyerPreviewHtml({ ...data, cover_url: coverSrc }))
    w.document.close()
    if (coverSrc.startsWith('blob:')) {
      setTimeout(() => URL.revokeObjectURL(coverSrc), 60_000)
    }
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

function resetAdv() {
  submittedRange.value = null
  planLabel.value = ''
  firstPublic.value = ''
  autoResult.value = ''
  categoryId.value = ''
  productStatus.value = ''
  page.value = 1
  load()
}

watch(tab, () => {
  page.value = 1
  closeReview()
  sortBy.value = tab.value === 'reviewed' ? 'reviewed_at' : 'submitted_at'
  sortDir.value = 'desc'
  load()
})

onMounted(async () => {
  const st = String(route.query.status || '')
  if (st === 'pending_review' || st === 'pending') tab.value = 'pending'
  else if (st === 'flag' || st === 'flagged') tab.value = 'flagged'
  else if (st === 'approved' || st === 'rejected' || st === 'reviewed') tab.value = 'reviewed'
  await load()
  const rid = route.query.review_id
  if (rid) await openReviewById(String(rid))
})

onUnmounted(() => {
  revokeCoverBlob()
})
</script>

<template>
  <div v-loading="loading" class="page-card" data-testid="shop-product-reviews">
    <el-tabs v-model="tab">
      <el-tab-pane name="pending">
        <template #label>待审队列 <el-badge :value="pendingCount" :hidden="!pendingCount" /></template>
      </el-tab-pane>
      <el-tab-pane name="flagged">
        <template #label>机审 flagged <el-badge :value="flaggedCount" :hidden="!flaggedCount" type="warning" /></template>
      </el-tab-pane>
      <el-tab-pane name="reviewed">
        <template #label>已审出队 <el-badge :value="reviewedCount" :hidden="!reviewedCount" type="info" /></template>
      </el-tab-pane>
    </el-tabs>

    <div class="toolbar">
      <el-input v-model="searchQ" clearable placeholder="搜索商品 / 商家" style="width: 200px" @keyup.enter=";(page = 1), load()" />
      <el-select v-if="tab !== 'reviewed'" v-model="autoResult" clearable placeholder="机审" style="width: 110px" @change=";(page = 1), load()">
        <el-option label="通过" value="pass" />
        <el-option label="标黄" value="flag" />
        <el-option label="拒绝" value="reject" />
      </el-select>
      <el-select v-model="categoryId" clearable placeholder="类目" style="width: 160px" @change=";(page = 1), load()">
        <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-select
        v-if="tab === 'reviewed'"
        v-model="productStatus"
        clearable
        placeholder="在售状态"
        style="width: 120px"
        @change=";(page = 1), load()"
      >
        <el-option label="在售" value="on_sale" />
        <el-option label="已下架" value="off_sale" />
        <el-option label="未上架" value="approved" />
      </el-select>
      <el-button @click="adv = !adv">高级筛选</el-button>
      <span class="spacer" />
      <el-button @click="openCol">列设置</el-button>
      <el-button @click="exportList">导出</el-button>
    </div>
    <div v-if="adv" class="adv">
      <el-date-picker
        v-model="submittedRange"
        type="datetimerange"
        start-placeholder="提交时间起"
        end-placeholder="提交时间止"
        value-format="YYYY-MM-DDTHH:mm:ss"
      />
      <el-input v-model="planLabel" clearable placeholder="商家套餐" style="width: 140px" />
      <el-select v-model="firstPublic" clearable placeholder="是否首单公域" style="width: 150px">
        <el-option label="是" value="yes" />
        <el-option label="否" value="no" />
      </el-select>
      <el-button type="primary" @click=";(page = 1), load()">查询</el-button>
      <el-button @click="resetAdv">重置</el-button>
    </div>

    <div class="split">
      <div class="list">
        <el-table :data="items" border stripe highlight-current-row @row-click="openReview">
          <template v-for="colKey in visibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'product_name'" min-width="180">
            <template #header>
              <span class="sortable" @click.stop="toggleSort('product_name')">商品 {{ sortIcon('product_name') }}</span>
            </template>
            <template #default="{ row }">{{ row.product_name }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'merchant_name'" min-width="140">
            <template #header>
              <span class="sortable" @click.stop="toggleSort('merchant_name')">商家 {{ sortIcon('merchant_name') }}</span>
            </template>
            <template #default="{ row }">{{ row.merchant_name || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'shop_name'" label="店铺" min-width="120">
            <template #default="{ row }">{{ row.shop_name || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'product_type'" label="类型" width="80">
            <template #default="{ row }">{{ TYPE_LABEL[row.product_type] || row.product_type }}</template>
          </el-table-column>
          <el-table-column v-if="tab !== 'reviewed' && colKey === 'auto_result'" width="90">
            <template #header>
              <span class="sortable" @click.stop="toggleSort('auto_result')">机审 {{ sortIcon('auto_result') }}</span>
            </template>
            <template #default="{ row }">
              <el-tag size="small" :type="AUTO_TAG[row.auto_result]">{{ AUTO_LABEL[row.auto_result] || row.auto_result }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="tab !== 'reviewed' && colKey === 'submitted_at'" width="170">
            <template #header>
              <span class="sortable" @click.stop="toggleSort('submitted_at')">提交时间 {{ sortIcon('submitted_at') }}</span>
            </template>
            <template #default="{ row }">{{ formatDateTime(row.submitted_at) }}</template>
          </el-table-column>
          <el-table-column v-if="tab !== 'reviewed' && colKey === 'status'" label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="MANUAL_TAG[row.manual_result]">{{ MANUAL_LABEL[row.manual_result] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="tab === 'reviewed' && colKey === 'manual_result'" label="审出结果" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="MANUAL_TAG[row.manual_result]">{{ MANUAL_LABEL[row.manual_result] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="tab === 'reviewed' && colKey === 'reviewed_at'" width="170">
            <template #header>
              <span class="sortable" @click.stop="toggleSort('reviewed_at')">审出时间 {{ sortIcon('reviewed_at') }}</span>
            </template>
            <template #default="{ row }">{{ formatDateTime(row.reviewed_at) }}</template>
          </el-table-column>
          <el-table-column v-if="tab === 'reviewed' && colKey === 'sale_status'" label="在售状态" width="90">
            <template #default="{ row }">{{ saleText(row) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'category_path'" label="类目" min-width="140">
            <template #default="{ row }">{{ row.category_path || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <template v-if="row.manual_result === 'pending'">
                <el-button v-if="row.auto_result !== 'reject'" link type="primary" @click.stop="openReview(row)">审核</el-button>
                <el-button v-else link type="primary" @click.stop="openReview(row)">查看</el-button>
                <el-button v-if="canReview && row.auto_result === 'reject'" link type="danger" @click.stop="openReject(row)">驳回</el-button>
              </template>
              <template v-else>
                <el-button link type="primary" @click.stop="openReview(row)">查看</el-button>
                <el-button
                  v-if="canForceOff && (row.product_status === 'on_sale' || row.paid_order_count > 0)"
                  link
                  type="warning"
                  @click.stop="openForceOff(row)"
                >
                  强制下架
                </el-button>
              </template>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="pager">
          <span class="pager-total">
            共 {{ total }} 条{{ tab === 'pending' ? '（待审）' : tab === 'reviewed' ? '（已审出队）' : '' }}
          </span>
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="sizes, prev, pager, next"
            small
            @current-change="load"
            @size-change=";(page = 1), load()"
          />
        </div>
      </div>
    </div>

    <el-drawer
      v-model="reviewDrawer"
      :title="selected ? `${selected.manual_result === 'pending' ? '审核' : '详情'} · ${selected.product_name}` : '商品审核'"
      size="640px"
      direction="rtl"
      destroy-on-close
      @close="closeReview"
    >
      <aside v-if="selected" class="panel" data-testid="shop-product-review-panel">
        <div class="panel-hd">
          <div class="panel-hd-main">
            <div class="panel-title-row">
              <b>{{ selected.product_name }}</b>
              <el-tag size="small" class="ml">{{ MANUAL_LABEL[selected.manual_result] }}</el-tag>
              <el-tag size="small" :type="AUTO_TAG[selected.auto_result]" class="ml">机审{{ AUTO_LABEL[selected.auto_result] }}</el-tag>
            </div>
            <div class="muted panel-meta">
              审核单 {{ String(selected.id).slice(0, 8) }} · 商品 {{ String(selected.product_id).slice(0, 8) }} ·
              商家 {{ selected.merchant_name || '—' }} · 店铺 {{ selected.shop_name || '—' }} ·
              提交 {{ formatDateTime(selected.submitted_at) }}
              <span v-if="selected.submitted_by_name"> · {{ selected.submitted_by_name }}</span>
            </div>
          </div>
          <div class="panel-hd-actions">
            <el-button size="small" @click="goMerchant(selected)">↗ 商家（新窗）</el-button>
            <el-button size="small" @click="previewBuyer">预览买家页</el-button>
          </div>
        </div>
        <el-tabs v-model="panelTab">
          <el-tab-pane label="商品快照" name="snapshot" />
          <el-tab-pane label="机审明细" name="auto" />
          <el-tab-pane label="关联内容" name="refs" />
          <el-tab-pane label="审核日志" name="log" />
        </el-tabs>
        <div v-show="panelTab === 'snapshot'" class="panel-body">
          <div class="cover-block">
            <img
              v-if="coverDisplayUrl(selected)"
              :src="coverDisplayUrl(selected)"
              class="cover"
              alt="封面"
              title="点击放大查看"
              @click="openCoverPreview"
            />
            <div v-else class="cover ph">无封面</div>
            <div v-if="coverDisplayUrl(selected)" class="cover-tip">点击封面可放大查看原图</div>
          </div>
          <div class="snap-head">
            <div class="ttl">{{ snap(selected).name || selected.product_name }}</div>
            <div class="muted">副标题：{{ snap(selected).subtitle || '—' }}</div>
            <div class="meta">
              <el-tag size="small">{{ TYPE_LABEL[selected.product_type] || selected.product_type }}</el-tag>
              <span>类目：{{ selected.category_path || '—' }}</span>
              <b>{{ centsYuan(snap(selected).price_cents) }}</b>
            </div>
          </div>
          <el-descriptions :column="1" border size="small" class="snap-desc">
            <el-descriptions-item label="商品 ID">{{ selected.product_id }}</el-descriptions-item>
            <el-descriptions-item label="店铺">{{ selected.shop_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="商家套餐">{{ selected.plan_label || '—' }}</el-descriptions-item>
            <el-descriptions-item label="主体资质">
              {{ selected.entity_status === 'active' ? '已入驻' : selected.entity_status || '—' }}
              {{ ENTITY_LABEL[selected.entity_type] || selected.entity_type || '' }}
            </el-descriptions-item>
            <el-descriptions-item label="退款策略">{{ refundText(selected) }}</el-descriptions-item>
            <el-descriptions-item label="是否首单公域">
              {{ selected.first_public_domain ? '是' : '否（首单须人审通过后才可映射）' }}
            </el-descriptions-item>
            <el-descriptions-item label="商品简介">{{ snap(selected).intro || '—' }}</el-descriptions-item>
          </el-descriptions>
          <div class="note">
            <b>机审结论</b>：
            <el-tag size="small" :type="AUTO_TAG[selected.auto_result]">{{ AUTO_LABEL[selected.auto_result] }}</el-tag>
            <span v-if="selected.auto_result === 'pass'"> 机审通过，仍须人审确认材料</span>
            <span v-else-if="selected.auto_result === 'flag'"> 须人工复核，不可因机审通过跳过人审。</span>
            <span v-else> 机审已拒绝，建议直接驳回。</span>
          </div>
          <template v-if="selected.manual_result === 'pending' && canReview">
            <h4>人审操作</h4>
            <el-form label-position="top" class="review-form">
              <el-form-item label="内部备注（选填）">
                <el-input v-model="note" type="textarea" :rows="2" placeholder="机审 flagged 或覆写通过时建议填写" />
              </el-form-item>
              <p class="review-hint">通过后商品可上架；驳回须填原因码与说明（≥4 字）。</p>
            </el-form>
            <div class="review-actions">
              <el-button type="primary" :loading="submitting" @click="doApprove">通过</el-button>
              <el-button type="danger" plain @click="openReject(selected)">驳回</el-button>
            </div>
          </template>
          <template v-else-if="selected.manual_result !== 'pending'">
            <h4>审出结果</h4>
            <el-descriptions :column="1" border size="small" class="snap-desc">
              <el-descriptions-item label="审出结果">
                <el-tag size="small" :type="MANUAL_TAG[selected.manual_result]">
                  {{ MANUAL_LABEL[selected.manual_result] }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="审核人">{{ selected.reviewer_name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="审出时间">{{ formatDateTime(selected.reviewed_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="selected.manual_result === 'rejected'" label="驳回原因码">
                {{ REJECT_CODE_LABEL[selected.reject_code] || selected.reject_code || '—' }}
              </el-descriptions-item>
              <el-descriptions-item v-if="selected.manual_result === 'rejected'" label="驳回说明">
                {{ selected.reject_reason || '—' }}
              </el-descriptions-item>
              <el-descriptions-item v-if="selected.internal_note" label="内部备注">
                {{ selected.internal_note }}
              </el-descriptions-item>
            </el-descriptions>
            <div v-if="canForceOff && (selected.product_status === 'on_sale' || selected.paid_order_count > 0)" class="review-actions">
              <el-button type="warning" plain @click="openForceOff(selected)">强制下架</el-button>
            </div>
          </template>
        </div>
        <div v-show="panelTab === 'auto'" class="panel-body">
          <p v-if="selected.auto_result === 'pass'" class="auto-hint">
            机审通过：下列为规则扫描结果；「未命中」表示该规则未触发，仍须人审确认材料。
          </p>
          <el-table :data="autoDetailRows(selected)" border size="small">
            <el-table-column label="规则" min-width="110">
              <template #default="{ row }">{{ row.rule_label }}</template>
            </el-table-column>
            <el-table-column label="命中" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="AUTO_TAG[row.level] || 'info'">{{ AUTO_LABEL[row.level] || row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="snippet" label="片段" min-width="120" />
            <el-table-column label="建议" min-width="120">
              <template #default="{ row }">{{ row.message || '—' }}</template>
            </el-table-column>
          </el-table>
        </div>
        <div v-show="panelTab === 'refs'" class="panel-body">
          <template v-if="refSummary(selected)">
            <div class="ref-summary">
              <div class="ref-line"><b>{{ refSummary(selected).ref_type_label }}</b>：{{ refSummary(selected).title || '—' }}</div>
              <div class="muted">{{ refSummary(selected).summary }}</div>
              <div v-if="refSummary(selected).intro" class="muted">简介：{{ refSummary(selected).intro }}</div>
            </div>
            <template v-if="(refSummary(selected).lessons || []).length">
              <h4 class="sub-h">课时清单（{{ refSummary(selected).lessons.length }}）</h4>
              <el-table :data="refSummary(selected).lessons" border size="small">
                <el-table-column label="#" width="48">
                  <template #default="{ row }">{{ row.sort }}</template>
                </el-table-column>
                <el-table-column prop="title" label="课时标题" min-width="140" />
                <el-table-column label="类型" width="72">
                  <template #default="{ row }">{{ row.media_type_label || row.media_type }}</template>
                </el-table-column>
                <el-table-column label="时长" width="88">
                  <template #default="{ row }">{{ row.duration_label || '—' }}</template>
                </el-table-column>
                <el-table-column label="状态" width="80">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.status === 'published' ? 'success' : 'info'">
                      {{ row.status_label || row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="试看" width="56">
                  <template #default="{ row }">{{ row.is_trial ? '是' : '—' }}</template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      v-if="row.previewable"
                      link
                      type="primary"
                      size="small"
                      @click.stop="previewLesson(row)"
                    >
                      预览
                    </el-button>
                    <el-button
                      v-if="row.previewable"
                      link
                      type="primary"
                      size="small"
                      @click.stop="downloadLesson(row)"
                    >
                      下载
                    </el-button>
                    <span v-if="!row.previewable" class="muted">未上传</span>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <template v-else-if="(refSummary(selected).files || []).length">
              <h4 class="sub-h">资料文件（{{ refSummary(selected).files.length }}）</h4>
              <el-table :data="refSummary(selected).files" border size="small">
                <el-table-column prop="name" label="文件名" min-width="160" />
                <el-table-column prop="mime" label="类型" width="120" />
                <el-table-column prop="size_label" label="大小" width="88" />
                <el-table-column label="可预览" width="72">
                  <template #default="{ row }">{{ row.previewable ? '是' : '否' }}</template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" size="small" @click.stop="previewRefAsset(row)">预览</el-button>
                    <el-button link type="primary" size="small" @click.stop="downloadRefAsset(row)">下载</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <p v-else-if="selected.product_type === 'service'" class="muted">
              服务定义已关联；具体可约时段请在商家端服务定义中查看。
            </p>
          </template>
          <p v-else class="muted">未关联内容或关联已失效</p>
        </div>
        <div v-show="panelTab === 'log'" class="panel-body">
          <p v-for="(ev, i) in selected.audit_log || []" :key="i" class="tl">
            {{ ev.at ? formatDateTime(ev.at) : '—' }} {{ ev.label }}
          </p>
        </div>
      </aside>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="pendingColDialog"
      v-model:columns="pendingColDraft"
      @save="savePendingCol"
    />
    <CrmColumnSettingsDialog
      v-model:visible="reviewedColDialog"
      v-model:columns="reviewedColDraft"
      @save="saveReviewedCol"
    />

    <el-dialog v-model="rejectDlg" :title="`驳回「${selected?.product_name || ''}」？`" width="480px">
      <el-form label-width="100px">
        <el-form-item label="原因码" required>
          <el-select v-model="rejectForm.reject_code" placeholder="请选择" style="width: 100%">
            <el-option label="敏感内容" value="sensitive" />
            <el-option label="资质不符" value="qualification" />
            <el-option label="虚假宣传" value="false_ad" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input v-model="rejectForm.reject_reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDlg = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="doReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="offDlg" :title="`强制下架「${selected?.product_name || ''}」？`" width="480px">
      <el-form label-width="140px">
        <el-form-item label="影响说明（只读）">强制下架 + listing blocked；暂停公域映射；已购买家权益保留，不可新购</el-form-item>
        <el-form-item label="告警（只读）">当前有 {{ selected?.paid_order_count || 0 }} 笔已付款订单</el-form-item>
        <el-form-item label="下架原因" required>
          <el-input v-model="offReason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="offDlg = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="doForceOff">确认强制下架</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="lessonPreviewDlg.visible" :title="lessonPreviewDlg.title || '图文课时'" width="560px">
      <div class="lesson-preview-body">{{ lessonPreviewDlg.content || '（无正文）' }}</div>
      <template #footer>
        <el-button @click="lessonPreviewDlg.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="coverPreviewDlg.visible"
      :title="`${selected?.product_name || '商品'} · 封面`"
      width="720px"
      class="cover-preview-dialog"
      append-to-body
    >
      <img
        v-if="coverDisplayUrl(selected)"
        :src="coverDisplayUrl(selected)"
        class="cover-full"
        alt="封面原图"
      />
      <template #footer>
        <el-button @click="coverPreviewDlg.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="refPreviewDlg.visible"
      :title="refPreviewDlg.title || '文档预览'"
      width="720px"
      class="ref-preview-dialog"
    >
      <div class="ref-preview-body" v-html="refPreviewDlg.html" />
      <template #footer>
        <el-button @click="refPreviewDlg.visible = false">关闭</el-button>
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
.spacer {
  flex: 1;
}
.adv {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: -4px 0 12px;
  padding: 10px 12px;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 8px;
}
.split {
  display: block;
}
.list {
  min-width: 0;
  overflow-x: auto;
}
.pager {
  margin-top: 8px;
}
.panel {
  border: none;
  border-radius: 0;
  background: #fff;
  max-height: none;
  overflow: visible;
}
.panel :deep(.el-tabs__header) {
  margin-bottom: 8px;
}
.panel-hd {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 0 0 12px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.panel-hd-main {
  flex: 1;
  min-width: 0;
}
.panel-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.panel-meta {
  margin-top: 6px;
  line-height: 1.55;
}
.panel-hd-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}
.panel-body {
  padding: 4px 0 12px;
  font-size: 13px;
}
.snap-desc :deep(.el-descriptions__label) {
  width: 96px;
}
.review-form {
  margin-top: 8px;
}
.review-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #666;
  line-height: 1.55;
}
.review-actions {
  display: flex;
  gap: 8px;
}
.auto-hint,
.ref-summary {
  margin: 0 0 10px;
  padding: 10px 12px;
  background: #f6f8fa;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
}
.ref-line {
  margin-bottom: 4px;
}
.sub-h {
  margin: 12px 0 8px;
  font-size: 13px;
  font-weight: 600;
}
.lesson-preview-body {
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  line-height: 1.65;
  font-size: 13px;
  color: #333;
}
.ref-preview-body {
  max-height: 60vh;
  overflow: auto;
  padding: 4px 8px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.cover-block {
  margin-bottom: 12px;
}
.cover {
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #eee;
  background: #f8fafc;
  cursor: zoom-in;
  display: block;
}
.cover-tip {
  margin-top: 6px;
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
}
.snap-head {
  margin-bottom: 12px;
}
.cover.ph {
  width: 100%;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  color: #999;
  font-size: 12px;
  border-radius: 8px;
  border: 1px dashed #e2e8f0;
}
.cover-full {
  display: block;
  max-width: 100%;
  max-height: 72vh;
  margin: 0 auto;
  object-fit: contain;
  border-radius: 8px;
  background: #f8fafc;
}
.ttl {
  font-weight: 600;
  font-size: 14px;
}
.muted {
  color: #666;
  font-size: 11px;
  margin-top: 4px;
  line-height: 1.5;
}
.meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 6px;
}
.note {
  margin: 10px 0;
  padding: 10px;
  background: #e6f4ff;
  border-radius: 6px;
  line-height: 1.65;
}
.ml {
  margin-left: 6px;
}
.sortable {
  cursor: pointer;
}
.tl {
  margin: 0 0 6px;
  font-size: 12px;
}
h4 {
  margin: 12px 0 8px;
  font-size: 12px;
}
</style>
