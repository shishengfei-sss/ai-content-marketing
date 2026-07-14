<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const contract = ref(null)
const customer = ref(null)

const canSign = () => hasPermission(auth.permissions, 'crm.contract.sign')
const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')
const canDelete = () => hasPermission(auth.permissions, 'crm.contract.delete')

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  sent: { label: '已发送', type: 'warning' },
  signed: { label: '已签署', type: 'success' },
  executing: { label: '执行中', type: 'success' },
  expired: { label: '已过期', type: 'info' },
  terminated: { label: '已终止', type: 'danger' },
}
const TYPE_META = { new: '新签', renewal: '续约', addon: '增订' }

async function loadContract() {
  loading.value = true
  try {
    const { data } = await crmApi.getContract(route.params.id)
    contract.value = data
    if (data.customer_id) {
      try { const c = await crmApi.getCustomer(data.customer_id); customer.value = c.data } catch { customer.value = null }
    }
  } catch (e) {
    ElMessage.error(e.message || '加载合同失败')
  } finally {
    loading.value = false
  }
}

async function handleConvert() {
  try {
    await ElMessageBox.confirm('将合同生成订单？（合同可重复生成订单）', '生成订单')
    const { data } = await crmApi.convertContractToOrder(contract.value.id)
    ElMessage.success('已生成订单')
    router.push(`/crm/orders/${data.order_id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '转化失败') }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(`确定删除合同「${contract.value.title}」？`, '删除')
    await crmApi.deleteContract(contract.value.id)
    ElMessage.success('已删除')
    router.push('/crm/contracts')
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' }

onMounted(async () => { await loadMembers(); loadContract() })
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="detail-page__back">
      <el-button link @click="router.push('/crm/contracts')"><el-icon><ArrowLeft /></el-icon> 返回合同列表</el-button>
    </div>

    <div v-if="contract" class="page-card detail-page__head">
      <div>
        <h2 class="detail-page__title">{{ contract.title }}</h2>
        <div class="detail-page__meta">
          <el-tag :type="STATUS_META[contract.status]?.type">{{ STATUS_META[contract.status]?.label }}</el-tag>
          <el-tag size="small" type="info">{{ TYPE_META[contract.contract_type] }}</el-tag>
          <span class="detail-page__amount">¥{{ formatAmount(contract.signed_amount != null ? contract.signed_amount : contract.amount) }}</span>
          <span>{{ contract.contract_number }}</span>
          <span>负责人：{{ resolveMemberName(contract.owner_user_id) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button v-if="canConvert() && (contract.status === 'signed' || contract.status === 'executing')" type="primary" @click="handleConvert">生成订单</el-button>
        <el-button v-if="canDelete()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="contract" class="detail-page__body">
      <el-card shadow="never">
        <template #header>基本信息</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="合同号">{{ contract.contract_number }}</el-descriptions-item>
          <el-descriptions-item label="客户">
            <el-link v-if="customer" type="primary" @click="router.push(`/crm/customers/${customer.id}`)">{{ customer.company_name }}</el-link>
            <span v-else>{{ contract.customer_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="合同金额">¥{{ formatAmount(contract.amount) }}</el-descriptions-item>
          <el-descriptions-item label="签署金额">{{ contract.signed_amount != null ? '¥' + formatAmount(contract.signed_amount) : '—' }}</el-descriptions-item>
          <el-descriptions-item label="生效日">{{ formatDate(contract.start_date) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="到期日">{{ formatDate(contract.end_date) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="签署时间">{{ formatDate(contract.signed_at) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="附件">
            <el-link v-if="contract.file_url" :href="contract.file_url" target="_blank" type="primary">查看附件</el-link>
            <span v-else>—</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(contract.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(contract.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
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
</style>
