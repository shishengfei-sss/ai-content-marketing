<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import QuoteFormDialog from './QuoteFormDialog.vue'
import CrmEntityTags from '../../components/crm/CrmEntityTags.vue'
import CrmEntityAttachments from '../../components/crm/CrmEntityAttachments.vue'
import CrmLineItemsEditor from '../../components/crm/CrmLineItemsEditor.vue'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const quote = ref(null)
const customer = ref(null)
const editVisible = ref(false)
const pdfBusy = ref(false)
const pdfStatus = ref(null)
const linesEditing = ref(false)
const linesSaving = ref(false)
const activities = ref([])
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '' })
const activityLabels = { call: '电话', visit: '拜访', wechat: '微信', email: '邮件', other: '其他' }

const canEdit = () => hasPermission(auth.permissions, 'crm.quote.edit')
const canCreate = () => hasPermission(auth.permissions, 'crm.quote.create')
const canSend = () => hasPermission(auth.permissions, 'crm.quote.send')
const canAccept = () => hasPermission(auth.permissions, 'crm.quote.accept')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')
const canDelete = () => hasPermission(auth.permissions, 'crm.quote.delete')
const canView = () => hasPermission(auth.permissions, 'crm.quote.view')
const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canDeleteActivity = (item) =>
  hasPermission(auth.permissions, 'crm.activity.create') &&
  (item.created_by_user_id === auth.user?.id || hasPermission(auth.permissions, 'crm.admin'))

const linesSubTotal = computed(() =>
  (quote.value?.lines || []).reduce((s, l) => s + Number(l.line_total || 0), 0),
)
const orderDiscountAmount = computed(() => {
  const rate = Number(quote.value?.discount_rate || 0)
  if (!rate || !linesSubTotal.value) return 0
  return Math.round(linesSubTotal.value * (rate / 100) * 100) / 100
})

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  sent: { label: '已发送', type: 'warning' },
  accepted: { label: '已接受', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
  expired: { label: '已过期', type: 'info' },
  ordered: { label: '已转单', type: 'success' },
}

async function loadQuote() {
  loading.value = true
  try {
    const { data } = await crmApi.getQuote(route.params.id)
    quote.value = data
    if (data.customer_id) {
      try { const c = await crmApi.getCustomer(data.customer_id); customer.value = c.data } catch { customer.value = null }
    }
    await loadActivities()
  } catch (e) {
    ElMessage.error(e.message || '加载报价失败')
  } finally {
    loading.value = false
  }
}

async function loadActivities() {
  try {
    const { data } = await crmApi.listActivities({
      entity_type: 'quote',
      entity_id: route.params.id,
    })
    activities.value = Array.isArray(data) ? data : []
  } catch {
    activities.value = []
  }
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    ElMessage.warning('请填写跟进内容')
    return
  }
  try {
    await crmApi.createActivity({
      entity_type: 'quote',
      entity_id: route.params.id,
      activity_type: activityForm.value.activity_type,
      content: activityForm.value.content.trim(),
      next_follow_up_at: activityForm.value.next_follow_up_at || null,
    })
    ElMessage.success('跟进已保存')
    activityForm.value = { activity_type: 'call', content: '', next_follow_up_at: '' }
    await loadActivities()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function deleteActivity(item) {
  try {
    await ElMessageBox.confirm('确定删除该跟进？', '删除')
    await crmApi.deleteActivity(item.id)
    ElMessage.success('已删除')
    await loadActivities()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function handleSend() {
  try { await crmApi.sendQuote(quote.value.id); ElMessage.success('已发送'); await loadQuote() }
  catch (e) { ElMessage.error(e.message || '发送失败') }
}

async function handleAccept() {
  try { await crmApi.acceptQuote(quote.value.id); ElMessage.success('已接受'); await loadQuote() }
  catch (e) { ElMessage.error(e.message || '操作失败') }
}

async function handleReject() {
  try {
    await ElMessageBox.confirm('确定拒绝该报价？', '拒绝报价', { type: 'warning' })
    await crmApi.updateQuote(quote.value.id, { status: 'rejected' })
    ElMessage.success('已拒绝')
    await loadQuote()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作失败')
  }
}

async function handleConvert() {
  try {
    await ElMessageBox.confirm('将该报价转化为订单？', '转化为订单')
    const { data } = await crmApi.convertQuoteToOrder(quote.value.id)
    ElMessage.success('已转化为订单')
    router.push(`/crm/orders/${data.order_id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '转化失败') }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(`确定删除报价「${quote.value.subject}」？`, '删除')
    await crmApi.deleteQuote(quote.value.id)
    ElMessage.success('已删除')
    router.push('/crm/quotes')
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

async function handleClone() {
  try {
    const { data } = await crmApi.cloneQuote(quote.value.id)
    ElMessage.success('已复制为新草稿')
    router.push(`/crm/quotes/${data.id}`)
  } catch (e) {
    ElMessage.error(e.message || '复制失败')
  }
}

function goCpqReconfigure() {
  router.push({ path: '/crm/quotes/cpq/new', query: { from_quote_id: quote.value.id } })
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function pollPdfStatus(maxTries = 20) {
  for (let i = 0; i < maxTries; i++) {
    const { data } = await crmApi.getQuotePdfStatus(quote.value.id)
    pdfStatus.value = data
    if (data.status === 'completed' || data.status === 'failed') return data
    await sleep(400)
  }
  return pdfStatus.value
}

async function handleGeneratePdf() {
  pdfBusy.value = true
  try {
    const { data } = await crmApi.startQuotePdf(quote.value.id)
    pdfStatus.value = data
    if (data.status === 'generating') {
      ElMessage.info('正在生成报价单…')
      const done = await pollPdfStatus()
      if (done?.status === 'completed') {
        ElMessage.success('报价单已生成')
        openPdfDownload()
      } else if (done?.status === 'failed') {
        ElMessage.error(done.error_message || '生成失败')
      } else {
        ElMessage.warning('生成超时，请稍后在状态中刷新')
      }
    } else if (data.status === 'completed') {
      openPdfDownload()
    }
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    pdfBusy.value = false
  }
}

function openPdfDownload() {
  const token = localStorage.getItem('token')
  const url = crmApi.downloadQuotePdfUrl(quote.value.id)
  // 带 token 的新窗口：用 fetch blob
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then(async (res) => {
      if (!res.ok) throw new Error(await res.text())
      const blob = await res.blob()
      const obj = URL.createObjectURL(blob)
      window.open(obj, '_blank')
    })
    .catch((e) => ElMessage.error(e.message || '打开失败'))
}

async function refreshPdfStatus() {
  try {
    const { data } = await crmApi.getQuotePdfStatus(quote.value.id)
    pdfStatus.value = data
  } catch {
    pdfStatus.value = null
  }
}

async function saveLines(lines) {
  linesSaving.value = true
  try {
    await crmApi.updateQuote(quote.value.id, { lines })
    linesEditing.value = false
    ElMessage.success('明细已保存')
    await loadQuote()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    linesSaving.value = false
  }
}

function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' }

onMounted(async () => {
  await loadMembers()
  await loadQuote()
  if (quote.value) refreshPdfStatus()
})
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="detail-page__back">
      <el-button link @click="router.push('/crm/quotes')"><el-icon><ArrowLeft /></el-icon> 返回报价列表</el-button>
    </div>

    <div v-if="quote" class="page-card detail-page__head">
      <div>
        <h2 class="detail-page__title">{{ quote.subject }}</h2>
        <div class="detail-page__meta">
          <el-tag :type="STATUS_META[quote.status]?.type">{{ STATUS_META[quote.status]?.label }}</el-tag>
          <el-tag v-if="quote.cpq_config_snapshot" type="warning" size="small">CPQ</el-tag>
          <span class="detail-page__amount">¥{{ formatAmount(quote.total_amount) }}</span>
          <span>{{ quote.quote_number }}</span>
          <span>负责人：{{ resolveMemberName(quote.owner_user_id) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button v-if="canView()" :loading="pdfBusy" @click="handleGeneratePdf">生成报价单</el-button>
        <el-button v-if="canCreate()" @click="handleClone">复制</el-button>
        <el-button
          v-if="canCreate() && quote.cpq_config_snapshot"
          type="warning"
          @click="goCpqReconfigure"
        >CPQ 改参</el-button>
        <el-button v-if="canEdit() && quote.status === 'draft'" @click="editVisible = true">编辑</el-button>
        <el-button v-if="canSend() && quote.status === 'draft'" type="warning" @click="handleSend">发送</el-button>
        <el-button v-if="canAccept() && quote.status === 'sent'" type="success" @click="handleAccept">接受</el-button>
        <el-button v-if="canEdit() && quote.status === 'sent'" type="danger" plain @click="handleReject">拒绝</el-button>
        <el-button v-if="canConvert() && quote.status === 'accepted'" type="primary" @click="handleConvert">转化为订单</el-button>
        <el-button v-if="canDelete()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="quote" class="detail-page__body">
      <el-card shadow="never">
        <template #header>标签</template>
        <CrmEntityTags
          entity-type="quote"
          :entity-id="quote.id"
          :editable="canEdit() && quote.status === 'draft'"
        />
      </el-card>

      <el-card shadow="never">
        <template #header>基本信息</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="报价单号">{{ quote.quote_number }}</el-descriptions-item>
          <el-descriptions-item label="客户">
            <el-link v-if="customer" type="primary" @click="router.push(`/crm/customers/${customer.id}`)">{{ customer.company_name }}</el-link>
            <span v-else>{{ quote.customer_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="整单折扣">{{ quote.discount_rate != null ? quote.discount_rate + '%' : '—' }}</el-descriptions-item>
          <el-descriptions-item label="折扣金额">
            {{ orderDiscountAmount > 0 ? `¥${formatAmount(orderDiscountAmount)}` : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="有效期">{{ formatDate(quote.valid_until) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(quote.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(quote.updated_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="quote.converted_order_id" label="转出订单">
            <el-link type="primary" @click="router.push(`/crm/orders/${quote.converted_order_id}`)">查看订单</el-link>
          </el-descriptions-item>
          <el-descriptions-item v-if="pdfStatus" label="报价单状态">
            <span>{{ pdfStatus.status }}</span>
            <el-button
              v-if="pdfStatus.status === 'completed'"
              link
              type="primary"
              @click="openPdfDownload"
            >打开/打印</el-button>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="quote-lines-head">
            <span>报价明细</span>
            <div>
              <el-button
                v-if="canEdit() && quote.status === 'draft' && !linesEditing"
                size="small"
                type="primary"
                @click="linesEditing = true"
              >页内编辑</el-button>
              <el-button v-if="linesEditing" size="small" @click="linesEditing = false">取消</el-button>
            </div>
          </div>
        </template>
        <CrmLineItemsEditor
          mode="quote"
          :model-value="quote.lines || []"
          :editable="linesEditing"
          :saving="linesSaving"
          @save="saveLines"
        />
      </el-card>

      <el-card shadow="never">
        <CrmEntityAttachments
          entity-type="quote"
          :entity-id="quote.id"
          :editable="canEdit() && quote.status === 'draft'"
        />
      </el-card>

      <el-card shadow="never">
        <template #header>跟进</template>
        <div v-if="canWriteActivity()" class="activity-form" style="margin-bottom: 16px">
          <el-select v-model="activityForm.activity_type" style="width: 120px">
            <el-option label="电话" value="call" />
            <el-option label="拜访" value="visit" />
            <el-option label="微信" value="wechat" />
            <el-option label="邮件" value="email" />
            <el-option label="其他" value="other" />
          </el-select>
          <el-input v-model="activityForm.content" placeholder="记录本次沟通要点…" />
          <el-date-picker
            v-model="activityForm.next_follow_up_at"
            type="datetime"
            placeholder="下次跟进"
            style="width: 190px"
          />
          <el-button type="primary" @click="submitActivity">提交</el-button>
        </div>
        <el-timeline v-if="activities.length">
          <el-timeline-item
            v-for="item in activities"
            :key="item.id"
            :timestamp="new Date(item.created_at).toLocaleString('zh-CN')"
            placement="top"
          >
            <div class="crm-timeline__card">
              <el-tag size="small" type="info">{{ activityLabels[item.activity_type] || item.activity_type }}</el-tag>
              <p class="crm-timeline__content">{{ item.content }}</p>
              <el-button
                v-if="canDeleteActivity(item)"
                link
                type="danger"
                size="small"
                @click="deleteActivity(item)"
              >删除</el-button>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无跟进记录" :image-size="64" />
      </el-card>

      <el-card v-if="quote.cpq_config_snapshot" shadow="never">
        <template #header>CPQ 配置快照</template>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="数量">{{ quote.cpq_config_snapshot.quantity ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="折扣">{{ quote.cpq_config_snapshot.discount_rate ?? 0 }}%</el-descriptions-item>
          <el-descriptions-item label="运费">¥{{ formatAmount(quote.cpq_config_snapshot.shipping_cost) }}</el-descriptions-item>
          <el-descriptions-item label="成交价">
            ¥{{ formatAmount(quote.cpq_config_snapshot.calculation?.final_price ?? quote.total_amount) }}
          </el-descriptions-item>
          <el-descriptions-item label="参数" :span="2">
            <template v-if="quote.cpq_config_snapshot.selected_params && Object.keys(quote.cpq_config_snapshot.selected_params).length">
              <el-tag
                v-for="(v, k) in quote.cpq_config_snapshot.selected_params"
                :key="k"
                size="small"
                class="cpq-param-tag"
              >{{ k }}={{ v }}</el-tag>
            </template>
            <span v-else>—</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>

    <QuoteFormDialog v-model:visible="editVisible" :record="quote" @saved="loadQuote" />
  </div>
</template>

<style scoped>
.detail-page__back { margin-bottom: 8px; }
.detail-page__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.detail-page__title { margin: 0 0 8px 0; font-size: 20px; font-weight: 600; }
.detail-page__meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--el-text-color-secondary); font-size: 13px; }
.detail-page__amount { font-size: 16px; font-weight: 600; color: var(--el-color-primary); }
.detail-page__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-page__body { margin-top: 16px; display: flex; flex-direction: column; gap: 16px; }
.quote-lines-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.detail-page__total { margin-top: 12px; text-align: right; font-size: 15px; }
.detail-page__total b { color: var(--el-color-primary); font-size: 18px; }
.cpq-param-tag { margin-right: 6px; margin-bottom: 4px; }
.activity-form { display: flex; flex-wrap: wrap; gap: 8px; }
.activity-form .el-input { flex: 1; min-width: 200px; }
.crm-timeline__card {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
}
.crm-timeline__content { margin: 8px 0 0; line-height: 1.6; }
</style>
