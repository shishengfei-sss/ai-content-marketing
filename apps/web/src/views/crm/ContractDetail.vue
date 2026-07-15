<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import CrmEntityTasks from '../../components/crm/CrmEntityTasks.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const contract = ref(null)
const customer = ref(null)
const relatedOrders = ref([])
const amendments = ref([])
const attachments = ref([])
const activities = ref([])
const activeTab = ref('basic')
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '' })
const activityLabels = { call: '电话', visit: '拜访', wechat: '微信', email: '邮件', other: '其他' }
const amendDialog = ref(false)
const amendSaving = ref(false)
const amendForm = ref({ title: '', change_type: 'amount_change', amount_delta: null, new_value: '' })

const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')
const canEdit = () => hasPermission(auth.permissions, 'crm.contract.edit')
const canRenew = () => hasPermission(auth.permissions, 'crm.deal.create')
const canDelete = () => hasPermission(auth.permissions, 'crm.contract.delete')
const canViewOrder = () =>
  hasPermission(auth.permissions, 'crm.order.view') ||
  hasPermission(auth.permissions, 'crm.order.list_own') ||
  hasPermission(auth.permissions, 'crm.order.list_all')
const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canDeleteActivity = (item) =>
  hasPermission(auth.permissions, 'crm.activity.create') &&
  (item.created_by_user_id === auth.user?.id || hasPermission(auth.permissions, 'crm.admin'))

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  sent: { label: '已发送', type: 'warning' },
  signed: { label: '已签署', type: 'success' },
  executing: { label: '执行中', type: 'success' },
  expired: { label: '已过期', type: 'info' },
  terminated: { label: '已终止', type: 'danger' },
}
const TYPE_META = { new: '新签', renewal: '续约', addon: '增订' }
const ORDER_STATUS = {
  draft: '草稿',
  pending_approval: '待审批',
  approved: '已审批',
  rejected: '已驳回',
  confirmed: '已确认',
  executing: '执行中',
  completed: '已完成',
  cancelled: '已取消',
}

async function loadContract() {
  loading.value = true
  try {
    const { data } = await crmApi.getContract(route.params.id)
    contract.value = data
    if (data.customer_id) {
      try { const c = await crmApi.getCustomer(data.customer_id); customer.value = c.data } catch { customer.value = null }
    }
    await Promise.all([loadRelatedOrders(), loadAmendments(), loadAttachments(), loadActivities()])
  } catch (e) {
    ElMessage.error(e.message || '加载合同失败')
  } finally {
    loading.value = false
  }
}

async function loadAmendments() {
  try {
    const { data } = await crmApi.listContractAmendments(route.params.id)
    amendments.value = Array.isArray(data) ? data : []
  } catch {
    amendments.value = []
  }
}

async function loadRelatedOrders() {
  if (!canViewOrder()) { relatedOrders.value = []; return }
  try {
    const { data } = await crmApi.listOrders({
      contract_id: route.params.id,
      page: 1,
      page_size: 50,
    })
    relatedOrders.value = data.items || []
  } catch {
    relatedOrders.value = []
  }
}

async function loadAttachments() {
  try {
    const { data } = await crmApi.listAttachments({ entity_type: 'contract', entity_id: route.params.id })
    attachments.value = Array.isArray(data) ? data : []
  } catch {
    attachments.value = []
  }
}

async function loadActivities() {
  try {
    const { data } = await crmApi.listActivities({
      entity_type: 'contract',
      entity_id: route.params.id,
    })
    activities.value = Array.isArray(data) ? data : []
  } catch { activities.value = [] }
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    ElMessage.warning('请填写跟进内容')
    return
  }
  try {
    await crmApi.createActivity({
      entity_type: 'contract',
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
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

async function handleConvert() {
  try {
    await ElMessageBox.confirm('将合同生成订单？（合同可重复生成订单）', '生成订单')
    const { data } = await crmApi.convertContractToOrder(contract.value.id)
    ElMessage.success('已生成订单')
    router.push(`/crm/orders/${data.order_id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '转化失败') }
}

async function handleRenew() {
  try {
    await ElMessageBox.confirm('为该合同创建续约商机？', '续约')
    const { data } = await crmApi.renewContract(contract.value.id)
    ElMessage.success('已创建续约商机')
    router.push(`/crm/deals/${data.deal_id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '续约失败') }
}

function openAmend() {
  amendForm.value = { title: '', change_type: 'amount_change', amount_delta: null, new_value: '' }
  amendDialog.value = true
}

async function submitAmend() {
  if (!amendForm.value.title.trim()) { ElMessage.warning('请填写标题'); return }
  amendSaving.value = true
  try {
    await crmApi.createContractAmendment(contract.value.id, {
      title: amendForm.value.title.trim(),
      change_type: amendForm.value.change_type,
      amount_delta: amendForm.value.amount_delta,
      new_value: amendForm.value.new_value || null,
    })
    ElMessage.success('补充协议已创建')
    amendDialog.value = false
    await loadAmendments()
    activeTab.value = 'amendments'
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    amendSaving.value = false
  }
}

async function approveAmend(row) {
  try {
    await crmApi.approveContractAmendment(row.id)
    ElMessage.success('已批准')
    await loadAmendments()
  } catch (e) { ElMessage.error(e.message || '批准失败') }
}

async function executeAmend(row) {
  try {
    await crmApi.executeContractAmendment(row.id)
    ElMessage.success('已执行')
    await Promise.all([loadAmendments(), loadContract()])
  } catch (e) { ElMessage.error(e.message || '执行失败') }
}

const AMEND_STATUS = {
  draft: { label: '草稿', type: 'info' },
  approved: { label: '已批准', type: 'success' },
  executed: { label: '已执行', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
}
const AMEND_TYPE = {
  amount_change: '金额变更',
  term_change: '条款变更',
  party_change: '主体变更',
  other: '其他',
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
        <el-button v-if="canRenew() && ['signed', 'executing', 'expired'].includes(contract.status)" @click="handleRenew">续约商机</el-button>
        <el-button v-if="canEdit()" @click="openAmend">补充协议</el-button>
        <el-button v-if="canDelete()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="contract" class="detail-page__body page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
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
            <el-descriptions-item label="创建时间">{{ formatDate(contract.created_at) }}</el-descriptions-item>
          </el-descriptions>

          <div class="sub-block">
            <div class="sub-block__title">附件</div>
            <ul v-if="attachments.length" class="att-list">
              <li v-for="a in attachments" :key="a.id">{{ a.file_name }}（{{ formatDate(a.created_at) }}）</li>
            </ul>
            <div v-else class="att-fallback">
              <el-link v-if="contract.file_url" :href="contract.file_url" target="_blank" type="primary">查看 legacy 附件</el-link>
              <span v-else>暂无附件</span>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="`关联订单（${relatedOrders.length}）`" name="orders">
          <el-table :data="relatedOrders" border size="small" empty-text="暂无关联订单">
            <el-table-column prop="order_number" label="订单号" width="160" />
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="金额" width="130" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110" align="center">
              <template #default="{ row }">{{ ORDER_STATUS[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90" align="center">
              <template #default="{ row }">
                <el-button link type="primary" @click="router.push(`/crm/orders/${row.id}`)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`补充协议（${amendments.length}）`" name="amendments">
          <el-table :data="amendments" border size="small" empty-text="暂无补充协议">
            <el-table-column prop="amendment_number" label="编号" width="150" />
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="类型" width="110">
              <template #default="{ row }">{{ AMEND_TYPE[row.change_type] || row.change_type }}</template>
            </el-table-column>
            <el-table-column label="金额变更" width="110" align="right">
              <template #default="{ row }">
                {{ row.amount_delta != null ? '¥' + formatAmount(row.amount_delta) : '—' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="AMEND_STATUS[row.status]?.type">
                  {{ AMEND_STATUS[row.status]?.label || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button
                  v-if="canEdit() && row.status === 'draft'"
                  link
                  type="success"
                  @click="approveAmend(row)"
                >批准</el-button>
                <el-button
                  v-if="canEdit() && (row.status === 'draft' || row.status === 'approved')"
                  link
                  type="primary"
                  @click="executeAmend(row)"
                >执行</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="跟进" name="activities">
          <div v-if="canWriteActivity()" class="crm-panel">
            <div class="crm-panel__title">写跟进</div>
            <div class="activity-form">
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
        </el-tab-pane>

        <el-tab-pane label="任务" name="tasks">
          <CrmEntityTasks
            v-if="contract.customer_id"
            entity-type="customer"
            :entity-id="contract.customer_id"
            :default-assignee-id="contract.owner_user_id || ''"
          />
          <el-empty v-else description="合同未关联客户" :image-size="64" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="amendDialog" title="新建补充协议" width="480px">
      <el-form label-width="96px">
        <el-form-item label="标题" required>
          <el-input v-model="amendForm.title" maxlength="200" />
        </el-form-item>
        <el-form-item label="变更类型">
          <el-select v-model="amendForm.change_type" style="width: 100%">
            <el-option label="金额变更" value="amount_change" />
            <el-option label="条款变更" value="term_change" />
            <el-option label="主体变更" value="party_change" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="amendForm.change_type === 'amount_change'" label="金额变更">
          <el-input-number v-model="amendForm.amount_delta" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="新值说明">
          <el-input v-model="amendForm.new_value" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="amendDialog = false">取消</el-button>
        <el-button type="primary" :loading="amendSaving" @click="submitAmend">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-page__back { margin-bottom: 8px; }
.detail-page__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.detail-page__title { margin: 0 0 8px 0; font-size: 20px; font-weight: 600; }
.detail-page__meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--el-text-color-secondary); font-size: 13px; }
.detail-page__amount { font-size: 16px; font-weight: 600; color: var(--el-color-primary); }
.detail-page__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-page__body { margin-top: 16px; }
.sub-block { margin-top: 16px; }
.sub-block__title { font-weight: 600; margin-bottom: 8px; }
.att-list { margin: 0; padding-left: 18px; font-size: 13px; color: var(--el-text-color-regular); }
.att-fallback { font-size: 13px; color: var(--el-text-color-secondary); }
.activity-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.crm-panel { margin-bottom: 16px; }
.crm-panel__title { font-weight: 600; margin-bottom: 8px; }
.crm-timeline__card { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.crm-timeline__content { margin: 0; font-size: 14px; color: var(--el-text-color-regular); }
</style>
