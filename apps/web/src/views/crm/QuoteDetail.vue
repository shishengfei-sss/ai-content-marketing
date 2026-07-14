<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import QuoteFormDialog from './QuoteFormDialog.vue'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const quote = ref(null)
const customer = ref(null)
const editVisible = ref(false)

const canEdit = () => hasPermission(auth.permissions, 'crm.quote.edit')
const canSend = () => hasPermission(auth.permissions, 'crm.quote.send')
const canAccept = () => hasPermission(auth.permissions, 'crm.quote.accept')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')
const canDelete = () => hasPermission(auth.permissions, 'crm.quote.delete')

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
  } catch (e) {
    ElMessage.error(e.message || '加载报价失败')
  } finally {
    loading.value = false
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

function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' }

onMounted(async () => { await loadMembers(); loadQuote() })
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
          <span class="detail-page__amount">¥{{ formatAmount(quote.total_amount) }}</span>
          <span>{{ quote.quote_number }}</span>
          <span>负责人：{{ resolveMemberName(quote.owner_user_id) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button v-if="canEdit() && quote.status === 'draft'" @click="editVisible = true">编辑</el-button>
        <el-button v-if="canSend() && quote.status === 'draft'" type="warning" @click="handleSend">发送</el-button>
        <el-button v-if="canAccept() && quote.status === 'sent'" type="success" @click="handleAccept">接受</el-button>
        <el-button v-if="canConvert() && quote.status === 'accepted'" type="primary" @click="handleConvert">转化为订单</el-button>
        <el-button v-if="canDelete()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="quote" class="detail-page__body">
      <el-card shadow="never">
        <template #header>基本信息</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="报价单号">{{ quote.quote_number }}</el-descriptions-item>
          <el-descriptions-item label="客户">
            <el-link v-if="customer" type="primary" @click="router.push(`/crm/customers/${customer.id}`)">{{ customer.company_name }}</el-link>
            <span v-else>{{ quote.customer_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="整单折扣">{{ quote.discount_rate != null ? quote.discount_rate + '%' : '—' }}</el-descriptions-item>
          <el-descriptions-item label="有效期">{{ formatDate(quote.valid_until) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(quote.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(quote.updated_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="quote.converted_order_id" label="转出订单">
            <el-link type="primary" @click="router.push(`/crm/orders/${quote.converted_order_id}`)">查看订单</el-link>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>报价明细</template>
        <el-table :data="quote.lines || []" border size="small">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column label="数量" width="100" align="right"><template #default="{ row }">{{ row.quantity }}</template></el-table-column>
          <el-table-column label="单价" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.unit_price) }}</template></el-table-column>
          <el-table-column label="折扣%" width="80" align="center"><template #default="{ row }">{{ row.discount_rate != null ? row.discount_rate + '%' : '—' }}</template></el-table-column>
          <el-table-column label="小计" width="130" align="right"><template #default="{ row }">¥{{ formatAmount(row.line_total) }}</template></el-table-column>
        </el-table>
        <div class="detail-page__total">合计：<b>¥{{ formatAmount(quote.total_amount) }}</b></div>
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
.detail-page__total { margin-top: 12px; text-align: right; font-size: 15px; }
.detail-page__total b { color: var(--el-color-primary); font-size: 18px; }
</style>
