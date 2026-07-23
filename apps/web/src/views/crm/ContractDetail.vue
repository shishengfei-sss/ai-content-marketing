<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import CrmEntityTasks from '../../components/crm/CrmEntityTasks.vue'
import CrmEntityTags from '../../components/crm/CrmEntityTags.vue'
import CrmEntityAttachments from '../../components/crm/CrmEntityAttachments.vue'
import ContractFormDialog from './ContractFormDialog.vue'
import { formatDate, formatDateTime } from '../../utils/datetime'
import { CONTRACT_STATUS_META, CONTRACT_TYPE_META, contractActions } from '../../composables/contractActions'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const contract = ref(null)
const customer = ref(null)
const relatedOrders = ref([])
const amendments = ref([])
const activities = ref([])
const activeTab = ref('basic')
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '' })
const activityLabels = { call: '电话', visit: '拜访', wechat: '微信', email: '邮件', other: '其他' }
const amendDialog = ref(false)
const amendSaving = ref(false)
const amendForm = ref({ title: '', change_type: 'amount_change', amount_delta: null, new_value: '' })
const editVisible = ref(false)
const signDialog = ref(false)
const signSaving = ref(false)
const signForm = ref({ signed_amount: null, signed_at: '' })
const rejectVisible = ref(false)
const rejectReason = ref('')

const canConvert = () => hasPermission(auth.permissions, 'crm.order.convert')
const canEdit = () => hasPermission(auth.permissions, 'crm.contract.edit')
const canSign = () => hasPermission(auth.permissions, 'crm.contract.sign')
const canApprove = () => hasPermission(auth.permissions, 'crm.contract.approve')
const canCreate = () => hasPermission(auth.permissions, 'crm.contract.create')
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

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
const isOwner = computed(() => sameUserId(contract.value?.owner_user_id, auth.user?.id))
const canMutate = computed(() => isOwner.value)
const STATUS_META = CONTRACT_STATUS_META
const TYPE_META = CONTRACT_TYPE_META
const actions = computed(() =>
  contractActions({
    status: contract.value?.status,
    isOwner: isOwner.value,
    canEdit: canEdit(),
    canSign: canSign(),
    canApprove: canApprove(),
    canCreate: canCreate(),
    canDelete: canDelete(),
    canConvert: canConvert(),
    canRenewDeal: canRenew(),
  }),
)
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
    await Promise.all([loadRelatedOrders(), loadAmendments(), loadActivities()])
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

const amountInclTax = computed(() => {
  const lines = contract.value?.lines || []
  if (!lines.length) return Number(contract.value?.amount || 0)
  return lines.reduce(
    (acc, l) => acc + Number(l.line_total || 0) + Number(l.tax_amount || 0),
    0,
  )
})

function lineInclTax(row) {
  return Number(row.line_total || 0) + Number(row.tax_amount || 0)
}

function openEdit() {
  if (!contract.value) return
  editVisible.value = true
}

function openSign() {
  signForm.value = {
    signed_amount: Number(contract.value?.signed_amount ?? contract.value?.amount ?? 0),
    signed_at: '',
  }
  signDialog.value = true
}

async function submitSign() {
  signSaving.value = true
  try {
    const { data } = await crmApi.signContract(contract.value.id, {
      signed_amount: signForm.value.signed_amount,
      signed_at: signForm.value.signed_at || null,
    })
    contract.value = data
    signDialog.value = false
    ElMessage.success('已签署')
  } catch (e) {
    ElMessage.error(e.message || '签署失败')
  } finally {
    signSaving.value = false
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

async function handleSend() {
  try {
    await crmApi.sendContract(contract.value.id)
    ElMessage.success('已发送')
    await loadContract()
  } catch (e) { ElMessage.error(e.message || '发送失败') }
}

async function handleSubmit() {
  try {
    await crmApi.submitContract(contract.value.id)
    ElMessage.success('已提交审批')
    await loadContract()
  } catch (e) { ElMessage.error(e.message || '提交失败') }
}

async function handleWithdraw() {
  try {
    await ElMessageBox.confirm('确定撤回审批？合同将回到草稿。', '撤回审批')
    await crmApi.withdrawContract(contract.value.id)
    ElMessage.success('已撤回')
    await loadContract()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '撤回失败') }
}

async function handleApprove() {
  try {
    await crmApi.approveContract(contract.value.id)
    ElMessage.success('审批已通过')
    await loadContract()
  } catch (e) { ElMessage.error(e.message || '审批失败') }
}

async function submitReject() {
  if (!rejectReason.value.trim()) { ElMessage.warning('请填写驳回原因'); return }
  try {
    await crmApi.rejectContract(contract.value.id, { reason: rejectReason.value.trim() })
    ElMessage.success('已驳回')
    rejectVisible.value = false
    rejectReason.value = ''
    await loadContract()
  } catch (e) { ElMessage.error(e.message || '驳回失败') }
}

async function handleActivate() {
  try {
    await ElMessageBox.confirm('确定开始执行该合同？', '开始执行')
    await crmApi.activateContract(contract.value.id)
    ElMessage.success('已开始执行')
    await loadContract()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '操作失败') }
}

async function handleTerminate() {
  try {
    await ElMessageBox.confirm('确定终止该合同？', '终止合同')
    await crmApi.terminateContract(contract.value.id)
    ElMessage.success('已终止')
    await loadContract()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '终止失败') }
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

async function handleRenewContract() {
  try {
    await ElMessageBox.confirm('基于本合同生成续约合同草稿？', '续约合同')
    const { data } = await crmApi.renewAsContract(contract.value.id)
    ElMessage.success('已生成续约合同')
    router.push(`/crm/contracts/${data.id}`)
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '续约失败') }
}

async function handleClone() {
  try {
    const { data } = await crmApi.cloneContract(contract.value.id)
    ElMessage.success('已复制为新草稿')
    router.push(`/crm/contracts/${data.id}`)
  } catch (e) { ElMessage.error(e.message || '复制失败') }
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
        <el-button v-if="actions.edit" @click="openEdit">编辑</el-button>
        <el-button v-if="actions.send" @click="handleSend">发送</el-button>
        <el-button v-if="actions.submit" type="primary" @click="handleSubmit">提交审批</el-button>
        <el-button v-if="actions.withdraw" @click="handleWithdraw">撤回</el-button>
        <el-button v-if="actions.approve" type="success" @click="handleApprove">通过</el-button>
        <el-button v-if="actions.reject" type="danger" @click="rejectVisible = true">驳回</el-button>
        <el-button v-if="actions.sign" type="success" @click="openSign">签署</el-button>
        <el-button v-if="actions.activate" type="primary" @click="handleActivate">开始执行</el-button>
        <el-button v-if="actions.terminate" type="warning" @click="handleTerminate">终止</el-button>
        <el-button v-if="actions.convert" type="primary" @click="handleConvert">生成订单</el-button>
        <el-button v-if="actions.amend" @click="openAmend">补充协议</el-button>
        <el-button v-if="actions.renewDeal" @click="handleRenew">续约商机</el-button>
        <el-button v-if="actions.renewContract" @click="handleRenewContract">续约合同</el-button>
        <el-button v-if="actions.clone" @click="handleClone">复制</el-button>
        <el-button v-if="actions.delete" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="contract" class="detail-page__kpi page-card">
      <div class="kpi"><div class="kpi__label">合同金额</div><div class="kpi__value">¥{{ formatAmount(contract.amount) }}</div></div>
      <div class="kpi">
        <div class="kpi__label">签约金额</div>
        <div class="kpi__value">{{ contract.signed_amount != null ? '¥' + formatAmount(contract.signed_amount) : '—' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">差额</div>
        <div class="kpi__value">{{ contract.amount_diff != null ? '¥' + formatAmount(contract.amount_diff) : '—' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi__label">关联订单数/金额</div>
        <div class="kpi__value">
          {{ contract.related_order_count ?? relatedOrders.length }}
          <span class="kpi__sub">/ ¥{{ formatAmount(contract.related_order_amount ?? relatedOrders.reduce((a, o) => a + Number(o.amount || 0), 0)) }}</span>
        </div>
      </div>
      <div class="kpi">
        <div class="kpi__label">剩余天数</div>
        <div class="kpi__value">{{ contract.days_remaining != null ? contract.days_remaining + ' 天' : '—' }}</div>
      </div>
    </div>

    <div v-if="contract" class="detail-page__body page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <div class="sub-block" style="margin-top: 0; margin-bottom: 16px">
            <div class="sub-block__title">标签</div>
            <CrmEntityTags
              entity-type="contract"
              :entity-id="contract.id"
              :editable="canEdit() && canMutate"
            />
          </div>
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
            <el-descriptions-item label="签署时间">{{ formatDateTime(contract.signed_at, { withSeconds: false, empty: '—' }) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(contract.created_at, { withSeconds: false }) }}</el-descriptions-item>
          </el-descriptions>

          <div class="sub-block">
            <CrmEntityAttachments
              entity-type="contract"
              :entity-id="contract.id"
              :editable="canEdit() && canMutate"
            />
            <div v-if="contract.file_url" class="att-fallback" style="margin-top: 8px">
              <el-link :href="contract.file_url" target="_blank" type="primary">查看 legacy 附件链接</el-link>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="合同明细" name="lines">
          <el-table :data="contract.lines || []" border size="small" empty-text="暂无产品明细">
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="数量" width="90" align="right"><template #default="{ row }">{{ row.quantity }}</template></el-table-column>
            <el-table-column label="单价" width="110" align="right"><template #default="{ row }">¥{{ formatAmount(row.unit_price) }}</template></el-table-column>
            <el-table-column label="折扣%" width="80" align="center"><template #default="{ row }">{{ row.discount_rate != null ? row.discount_rate + '%' : '—' }}</template></el-table-column>
            <el-table-column label="税率%" width="80" align="center"><template #default="{ row }">{{ row.tax_rate != null ? row.tax_rate + '%' : '—' }}</template></el-table-column>
            <el-table-column label="税额" width="110" align="right"><template #default="{ row }">¥{{ formatAmount(row.tax_amount) }}</template></el-table-column>
            <el-table-column label="未税小计" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.line_total) }}</template></el-table-column>
            <el-table-column label="含税" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(lineInclTax(row)) }}</template></el-table-column>
          </el-table>
          <div v-if="(contract.lines || []).length" class="detail-page__total">
            未税合计：<b>¥{{ formatAmount(contract.amount) }}</b>
            <span class="detail-page__total-sep">含税合计：<b>¥{{ formatAmount(amountInclTax) }}</b></span>
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
              :timestamp="formatDateTime(item.created_at)"
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

    <ContractFormDialog v-model:visible="editVisible" :record="contract" @saved="loadContract" />

    <el-dialog v-model="signDialog" title="签署合同" width="420px">
      <el-form label-width="96px">
        <el-form-item label="签署金额">
          <el-input-number v-model="signForm.signed_amount" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="签署时间">
          <el-date-picker
            v-model="signForm.signed_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signDialog = false">取消</el-button>
        <el-button type="primary" :loading="signSaving" @click="submitSign">确认签署</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="驳回审批" width="440px">
      <el-input v-model="rejectReason" type="textarea" :rows="3" maxlength="500" placeholder="请填写驳回原因" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">确认驳回</el-button>
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
.detail-page__kpi { margin-top: 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }
.kpi { padding: 10px 12px; background: var(--el-fill-color-light); border-radius: 6px; }
.kpi__label { font-size: 12px; color: var(--el-text-color-secondary); }
.kpi__value { margin-top: 4px; font-size: 16px; font-weight: 600; }
.kpi__sub { margin-left: 4px; font-size: 12px; font-weight: 500; color: var(--el-text-color-secondary); }
.detail-page__body { margin-top: 16px; }
.detail-page__total { margin-top: 12px; text-align: right; font-size: 14px; color: var(--el-text-color-regular); }
.detail-page__total b { color: var(--el-color-primary); }
.detail-page__total-sep { margin-left: 16px; }
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
