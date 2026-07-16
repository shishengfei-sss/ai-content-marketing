<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import OrderFormDialog from './OrderFormDialog.vue'
import CrmEntityTasks from '../../components/crm/CrmEntityTasks.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const order = ref(null)
const customer = ref(null)
const editVisible = ref(false)
const plans = ref([])
const payments = ref([])
const approvals = ref([])
const activities = ref([])
const deliveries = ref([])
const invoices = ref([])
const refunds = ref([])
const revisions = ref([])
const activeTab = ref('basic')
const rejectVisible = ref(false)
const rejectReason = ref('')
const reviseVisible = ref(false)
const reviseReason = ref('')
const deliveryDialogVisible = ref(false)
const deliveryForm = ref({ carrier: '', tracking_number: '', remark: '' })
const invoiceDialogVisible = ref(false)
const invoiceForm = ref({ invoice_type: 'vat', amount: null, tax_amount: 0 })
const matchDialogVisible = ref(false)
const matchingInvoice = ref(null)
const matchForm = ref({ invoice_id: '', payment_id: '', matched_amount: null })
const matchSaving = ref(false)
const refundDialogVisible = ref(false)
const refundForm = ref({ original_payment_id: '', amount: null, reason: '' })
const refundSaving = ref(false)
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '' })
const activityLabels = { call: '电话', visit: '拜访', wechat: '微信', email: '邮件', other: '其他' }
const REFUND_STATUS = {
  pending: { label: '待审', type: 'warning' },
  approved: { label: '已批准', type: 'success' },
  completed: { label: '已完成', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
}

const planDialogVisible = ref(false)
const planForm = ref(emptyPlan())
const payDialogVisible = ref(false)
const payForm = ref(emptyPay())

function emptyPlan() { return { installment_no: 1, plan_date: '', plan_amount: null, remark: '' } }
function emptyPay() { return { amount: null, paid_at: '', method: 'bank', status: 'pending', remark: '', plan_id: '' } }

const canEdit = () => hasPermission(auth.permissions, 'crm.order.edit')
const canPlace = () => hasPermission(auth.permissions, 'crm.order.place')
const canApprove = () => hasPermission(auth.permissions, 'crm.order.approve')
const canDelete = () => hasPermission(auth.permissions, 'crm.order.delete')
const canPaymentCreate = () => hasPermission(auth.permissions, 'crm.payment.create')
const canPaymentConfirm = () => hasPermission(auth.permissions, 'crm.payment.confirm')
const canPaymentReverse = () => hasPermission(auth.permissions, 'crm.payment.reverse')
const canPaymentDelete = () => hasPermission(auth.permissions, 'crm.payment.delete')
const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canDeleteActivity = (item) =>
  hasPermission(auth.permissions, 'crm.activity.create') &&
  (item.created_by_user_id === auth.user?.id || hasPermission(auth.permissions, 'crm.admin'))

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  pending_approval: { label: '待审批', type: 'warning' },
  approved: { label: '已审批', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  confirmed: { label: '已确认', type: 'success' },
  executing: { label: '执行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
  superseded: { label: '已修订', type: 'info' },
}
const SOURCE_META = { deal: '商机', quote: '报价', contract: '合同' }
const PAY_STATUS_META = { pending: { label: '待确认', type: 'warning' }, confirmed: { label: '已到账', type: 'success' }, reversed: { label: '已冲销', type: 'info' } }
const PAY_METHOD_META = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }
const APPROVAL_STATUS_META = {
  pending: { label: '审批中', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}

const paidTotal = computed(() =>
  payments.value.filter((p) => p.status === 'confirmed').reduce((acc, p) => acc + Number(p.amount || 0), 0),
)
const planTotal = computed(() => plans.value.reduce((acc, p) => acc + Number(p.plan_amount || 0), 0))
const taxTotal = computed(() =>
  (order.value?.lines || []).reduce((acc, l) => acc + Number(l.tax_amount || 0), 0),
)
const amountInclTax = computed(() => Number(order.value?.amount || 0) + taxTotal.value)
const unpaid = computed(() => Math.max(0, Number(order.value?.amount || 0) - paidTotal.value))
const confirmedPayments = computed(() => payments.value.filter((p) => p.status === 'confirmed'))

async function loadOrder() {
  loading.value = true
  try {
    const { data } = await crmApi.getOrder(route.params.id)
    order.value = data
    if (data.customer_id) {
      try { const c = await crmApi.getCustomer(data.customer_id); customer.value = c.data } catch { customer.value = null }
    }
    await Promise.all([
      loadPlans(),
      loadPayments(),
      loadApprovals(),
      loadActivities(),
      loadDeliveries(),
      loadInvoices(),
      loadRevisions(),
      loadRefunds(),
    ])
  } catch (e) {
    ElMessage.error(e.message || '加载订单失败')
  } finally {
    loading.value = false
  }
}

async function loadPlans() {
  try {
    const { data } = await crmApi.listOrderPaymentPlans(route.params.id)
    plans.value = Array.isArray(data) ? data : []
  } catch { plans.value = [] }
}

async function loadPayments() {
  try {
    const { data } = await crmApi.listPayments({ order_id: route.params.id, page: 1, page_size: 100 })
    payments.value = data.items || []
  } catch { payments.value = [] }
}

async function loadApprovals() {
  try {
    const { data } = await crmApi.listOrderApprovals(route.params.id)
    approvals.value = Array.isArray(data) ? data : []
  } catch { approvals.value = [] }
}

async function loadActivities() {
  try {
    const { data } = await crmApi.listActivities({
      entity_type: 'order',
      entity_id: route.params.id,
    })
    activities.value = Array.isArray(data) ? data : []
  } catch { activities.value = [] }
}

async function loadDeliveries() {
  try {
    const { data } = await crmApi.listOrderDeliveries(route.params.id)
    deliveries.value = Array.isArray(data) ? data : []
  } catch { deliveries.value = [] }
}

async function loadInvoices() {
  try {
    const { data } = await crmApi.listOrderInvoices(route.params.id)
    invoices.value = Array.isArray(data) ? data : []
  } catch { invoices.value = [] }
}

async function loadRevisions() {
  try {
    const { data } = await crmApi.listOrderRevisions(route.params.id)
    revisions.value = Array.isArray(data) ? data : []
  } catch { revisions.value = [] }
}

async function loadRefunds() {
  try {
    const { data } = await crmApi.listOrderRefunds(route.params.id)
    refunds.value = Array.isArray(data) ? data : []
  } catch {
    refunds.value = []
  }
}

async function handleRevise() {
  if (!reviseReason.value.trim()) { ElMessage.warning('请填写修订原因'); return }
  try {
    const { data } = await crmApi.reviseOrder(order.value.id, { reason: reviseReason.value.trim() })
    ElMessage.success('已生成修订版')
    reviseVisible.value = false
    reviseReason.value = ''
    router.push(`/crm/orders/${data.id}`)
  } catch (e) { ElMessage.error(e.message || '修订失败') }
}

async function submitDelivery() {
  try {
    const firstLine = (order.value.lines || [])[0]
    await crmApi.createOrderDelivery(order.value.id, {
      carrier: deliveryForm.value.carrier || null,
      tracking_number: deliveryForm.value.tracking_number || null,
      remark: deliveryForm.value.remark || null,
      items: firstLine ? [{ order_line_id: firstLine.id, quantity: Number(firstLine.quantity || 1) }] : [],
    })
    ElMessage.success('发货单已创建')
    deliveryDialogVisible.value = false
    await Promise.all([loadDeliveries(), loadOrder()])
  } catch (e) { ElMessage.error(e.message || '创建失败') }
}

async function shipDelivery(row) {
  try { await crmApi.shipDelivery(row.id); ElMessage.success('已发运'); loadDeliveries() }
  catch (e) { ElMessage.error(e.message || '发运失败') }
}
async function completeDelivery(row) {
  try { await crmApi.completeDelivery(row.id); ElMessage.success('已签收'); loadDeliveries() }
  catch (e) { ElMessage.error(e.message || '签收失败') }
}

async function submitInvoice() {
  if (invoiceForm.value.amount == null) { ElMessage.warning('请填写金额'); return }
  try {
    await crmApi.createOrderInvoice(order.value.id, {
      invoice_type: invoiceForm.value.invoice_type,
      amount: invoiceForm.value.amount,
      tax_amount: invoiceForm.value.tax_amount || 0,
    })
    ElMessage.success('发票已创建')
    invoiceDialogVisible.value = false
    loadInvoices()
  } catch (e) { ElMessage.error(e.message || '创建失败') }
}
async function issueInvoice(row) {
  try { await crmApi.issueInvoice(row.id); ElMessage.success('已开具'); loadInvoices() }
  catch (e) { ElMessage.error(e.message || '开具失败') }
}
async function voidInvoice(row) {
  try {
    await ElMessageBox.confirm('确定作废该发票？', '作废')
    await crmApi.voidInvoice(row.id)
    ElMessage.success('已作废')
    loadInvoices()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '作废失败') }
}

function openMatchInvoice(row) {
  matchingInvoice.value = row
  const pay = confirmedPayments.value[0]
  matchForm.value = {
    invoice_id: row.id,
    payment_id: pay?.id || '',
    matched_amount: Number(row.total_amount || row.amount || 0),
  }
  matchDialogVisible.value = true
}

async function submitMatchInvoice() {
  if (!matchForm.value.payment_id) {
    ElMessage.warning('请选择回款')
    return
  }
  if (matchForm.value.matched_amount == null || matchForm.value.matched_amount <= 0) {
    ElMessage.warning('请填写核销金额')
    return
  }
  matchSaving.value = true
  try {
    await crmApi.matchInvoicePayment(matchForm.value.invoice_id, {
      payment_id: matchForm.value.payment_id,
      matched_amount: matchForm.value.matched_amount,
    })
    ElMessage.success('已核销回款')
    matchDialogVisible.value = false
  } catch (e) {
    ElMessage.error(e.message || '核销失败')
  } finally {
    matchSaving.value = false
  }
}

function openRefund() {
  const pay = confirmedPayments.value[0]
  refundForm.value = {
    amount: Number(pay?.amount || unpaid.value || 0) || null,
    reason: '',
    original_payment_id: pay?.id || '',
  }
  refundDialogVisible.value = true
}

async function submitRefund() {
  if (refundForm.value.amount == null || refundForm.value.amount <= 0) {
    ElMessage.warning('请填写退款金额')
    return
  }
  refundSaving.value = true
  try {
    await crmApi.createRefund({
      order_id: order.value.id,
      original_payment_id: refundForm.value.original_payment_id || null,
      amount: refundForm.value.amount,
      reason: refundForm.value.reason || null,
    })
    ElMessage.success('退款申请已提交')
    refundDialogVisible.value = false
    await loadRefunds()
    activeTab.value = 'refunds'
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    refundSaving.value = false
  }
}

async function approveRefund(row) {
  try {
    await crmApi.approveRefund(row.id)
    ElMessage.success('已批准')
    await loadRefunds()
  } catch (e) {
    ElMessage.error(e.message || '批准失败')
  }
}

async function completeRefund(row) {
  try {
    await crmApi.completeRefund(row.id)
    ElMessage.success('已完成退款')
    await loadRefunds()
  } catch (e) {
    ElMessage.error(e.message || '完成失败')
  }
}

async function rejectRefund(row) {
  try {
    await ElMessageBox.confirm('确定驳回该退款？', '驳回')
    await crmApi.rejectRefund(row.id)
    ElMessage.success('已驳回')
    await loadRefunds()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '驳回失败')
  }
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    ElMessage.warning('请填写跟进内容')
    return
  }
  try {
    await crmApi.createActivity({
      entity_type: 'order',
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

async function handleConfirm() {
  try { await crmApi.confirmOrder(order.value.id); ElMessage.success('已确认'); await loadOrder() }
  catch (e) { ElMessage.error(e.message || '确认失败') }
}
async function handleSubmit() {
  try { await crmApi.submitOrder(order.value.id); ElMessage.success('已提交'); await loadOrder() }
  catch (e) { ElMessage.error(e.message || '提交失败') }
}
async function handleApprove() {
  try { await crmApi.approveOrder(order.value.id); ElMessage.success('审批已通过'); await loadOrder() }
  catch (e) { ElMessage.error(e.message || '审批失败') }
}
async function submitReject() {
  if (!rejectReason.value.trim()) { ElMessage.warning('请填写驳回原因'); return }
  try {
    await crmApi.rejectOrder(order.value.id, { reason: rejectReason.value.trim() })
    ElMessage.success('已驳回')
    rejectVisible.value = false
    rejectReason.value = ''
    await loadOrder()
  } catch (e) { ElMessage.error(e.message || '驳回失败') }
}
async function handleCancel() {
  try {
    await ElMessageBox.confirm('确定取消该订单？', '取消订单')
    await crmApi.cancelOrder(order.value.id)
    ElMessage.success('已取消')
    await loadOrder()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '取消失败') }
}
async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定删除该订单？', '删除')
    await crmApi.deleteOrder(order.value.id)
    ElMessage.success('已删除')
    router.push('/crm/orders')
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function openCreatePlan() { planForm.value = emptyPlan(); planDialogVisible.value = true }
async function submitPlan() {
  if (!planForm.value.plan_date) { ElMessage.warning('请选择计划日期'); return }
  try {
    await crmApi.createOrderPaymentPlan(order.value.id, {
      installment_no: planForm.value.installment_no,
      plan_date: planForm.value.plan_date,
      plan_amount: planForm.value.plan_amount ?? 0,
      remark: planForm.value.remark || null,
    })
    ElMessage.success('计划已添加')
    planDialogVisible.value = false
    loadPlans()
  } catch (e) { ElMessage.error(e.message || '添加失败') }
}
async function deletePlan(p) {
  try {
    await ElMessageBox.confirm('确定删除该回款计划？', '删除')
    await crmApi.deleteOrderPaymentPlan(p.id)
    ElMessage.success('已删除')
    loadPlans()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function openCreatePay() { payForm.value = emptyPay(); payDialogVisible.value = true }
async function submitPay() {
  if (payForm.value.amount == null) { ElMessage.warning('请填写回款金额'); return }
  try {
    await crmApi.createPayment({
      order_id: order.value.id,
      plan_id: payForm.value.plan_id || null,
      amount: payForm.value.amount,
      paid_at: payForm.value.paid_at || null,
      method: payForm.value.method,
      status: payForm.value.status,
      remark: payForm.value.remark || null,
    })
    ElMessage.success('回款已登记')
    payDialogVisible.value = false
    loadPayments()
  } catch (e) { ElMessage.error(e.message || '登记失败') }
}
async function confirmPay(p) {
  try { await crmApi.confirmPayment(p.id); ElMessage.success('已确认到账'); loadPayments() }
  catch (e) { ElMessage.error(e.message || '确认失败') }
}
async function reversePay(p) {
  try {
    await ElMessageBox.confirm('确定冲销该回款？', '冲销')
    await crmApi.reversePayment(p.id)
    ElMessage.success('已冲销')
    loadPayments()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '冲销失败') }
}
async function deletePay(p) {
  try {
    await ElMessageBox.confirm('确定删除该回款记录？', '删除')
    await crmApi.deletePayment(p.id)
    ElMessage.success('已删除')
    loadPayments()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function formatAmount(v) { return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' }
function lineInclTax(row) { return Number(row.line_total || 0) + Number(row.tax_amount || 0) }

watch(
  () => route.query.tab,
  (t) => {
    if (
      t &&
      ['basic', 'lines', 'approval', 'payments', 'deliveries', 'invoices', 'refunds', 'revisions', 'activities', 'tasks'].includes(String(t))
    ) {
      activeTab.value = String(t)
    }
  },
  { immediate: true },
)

onMounted(async () => { await loadMembers(); loadOrder() })
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="detail-page__back">
      <el-button link @click="router.push('/crm/orders')"><el-icon><ArrowLeft /></el-icon> 返回订单列表</el-button>
    </div>

    <div v-if="order" class="page-card detail-page__head">
      <div>
        <h2 class="detail-page__title">{{ order.title }}</h2>
        <div class="detail-page__meta">
          <el-tag :type="STATUS_META[order.status]?.type">{{ STATUS_META[order.status]?.label || order.status }}</el-tag>
          <el-tag size="small" type="info">{{ SOURCE_META[order.source] }}</el-tag>
          <span class="detail-page__amount">¥{{ formatAmount(order.amount) }}</span>
          <span v-if="taxTotal">含税 ¥{{ formatAmount(amountInclTax) }}</span>
          <span>{{ order.order_number }}</span>
          <span>负责人：{{ resolveMemberName(order.owner_user_id) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button v-if="canEdit() && (order.status === 'draft' || order.status === 'rejected')" @click="editVisible = true">编辑</el-button>
        <el-button v-if="canPlace() && (order.status === 'draft' || order.status === 'rejected')" type="primary" @click="handleSubmit">提交审批</el-button>
        <el-button v-if="canPlace() && order.status === 'draft'" type="success" @click="handleConfirm">直接确认</el-button>
        <el-button v-if="canApprove() && order.status === 'pending_approval'" type="success" @click="handleApprove">通过</el-button>
        <el-button v-if="canApprove() && order.status === 'pending_approval'" type="danger" @click="rejectVisible = true">驳回</el-button>
        <el-button v-if="canPlace() && (order.status === 'confirmed' || order.status === 'executing')" @click="reviseVisible = true">修订</el-button>
        <el-button v-if="canEdit() && order.status !== 'cancelled' && order.status !== 'completed' && order.status !== 'superseded'" type="warning" @click="handleCancel">取消</el-button>
        <el-button v-if="canDelete()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="order" class="detail-page__kpi page-card">
      <div class="kpi"><div class="kpi__label">订单金额</div><div class="kpi__value">¥{{ formatAmount(order.amount) }}</div></div>
      <div class="kpi"><div class="kpi__label">税额合计</div><div class="kpi__value">¥{{ formatAmount(taxTotal) }}</div></div>
      <div class="kpi"><div class="kpi__label">计划回款</div><div class="kpi__value">¥{{ formatAmount(planTotal) }}</div></div>
      <div class="kpi"><div class="kpi__label">已到账</div><div class="kpi__value kpi__value--ok">¥{{ formatAmount(paidTotal) }}</div></div>
      <div class="kpi"><div class="kpi__label">待回款</div><div class="kpi__value">¥{{ formatAmount(unpaid) }}</div></div>
    </div>

    <div v-if="order" class="detail-page__body page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="订单号">{{ order.order_number }}</el-descriptions-item>
            <el-descriptions-item label="客户">
              <el-link v-if="customer" type="primary" @click="router.push(`/crm/customers/${customer.id}`)">{{ customer.company_name }}</el-link>
              <span v-else>{{ order.customer_id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{ SOURCE_META[order.source] }}</el-descriptions-item>
            <el-descriptions-item label="下单日期">{{ formatDate(order.order_date) }}</el-descriptions-item>
            <el-descriptions-item v-if="order.deal_id" label="来源商机">
              <el-link type="primary" @click="router.push(`/crm/deals/${order.deal_id}`)">查看商机</el-link>
            </el-descriptions-item>
            <el-descriptions-item v-if="order.quote_id" label="来源报价">
              <el-link type="primary" @click="router.push(`/crm/quotes/${order.quote_id}`)">查看报价</el-link>
            </el-descriptions-item>
            <el-descriptions-item v-if="order.contract_id" label="来源合同">
              <el-link type="primary" @click="router.push(`/crm/contracts/${order.contract_id}`)">查看合同</el-link>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(order.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="版本">v{{ order.version || 1 }}</el-descriptions-item>
            <el-descriptions-item v-if="order.parent_order_id" label="父订单">
              <el-link type="primary" @click="router.push(`/crm/orders/${order.parent_order_id}`)">查看原单</el-link>
            </el-descriptions-item>
            <el-descriptions-item v-if="order.revision_reason" label="修订原因">{{ order.revision_reason }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="订单明细" name="lines">
          <el-table :data="order.lines || []" border size="small">
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
          <div class="detail-page__total">
            未税合计：<b>¥{{ formatAmount(order.amount) }}</b>
            <span class="detail-page__total-sep">含税合计：<b>¥{{ formatAmount(amountInclTax) }}</b></span>
          </div>
        </el-tab-pane>

        <el-tab-pane label="审批" name="approval">
          <el-empty v-if="!approvals.length" description="暂无审批记录；草稿可「提交审批」或无规则时「直接确认」" :image-size="64" />
          <div v-for="inst in approvals" :key="inst.id" class="approval-card">
            <div class="approval-card__head">
              <el-tag :type="APPROVAL_STATUS_META[inst.status]?.type" size="small">
                {{ APPROVAL_STATUS_META[inst.status]?.label || inst.status }}
              </el-tag>
              <span>提交于 {{ formatDate(inst.submitted_at) }}</span>
              <span v-if="inst.resolved_at">结案于 {{ formatDate(inst.resolved_at) }}</span>
            </div>
            <div v-if="inst.reject_reason" class="approval-card__reason">驳回原因：{{ inst.reject_reason }}</div>
            <el-steps :active="Math.max(0, (inst.current_step || 1) - (inst.status === 'pending' ? 0 : 1))" finish-status="success" align-center>
              <el-step
                v-for="(s, idx) in (inst.steps_json || [])"
                :key="idx"
                :title="s.approver_role || `步骤${idx + 1}`"
                :description="s.status"
                :status="s.status === 'approved' ? 'success' : s.status === 'rejected' ? 'error' : s.status === 'pending' ? 'process' : 'wait'"
              />
            </el-steps>
          </div>
        </el-tab-pane>

        <el-tab-pane label="回款" name="payments">
          <div class="detail-page__card-head">
            <span>回款计划</span>
            <el-button v-if="canPaymentCreate()" size="small" @click="openCreatePlan">添加计划</el-button>
          </div>
          <el-table :data="plans" border size="small" class="mb-table">
            <el-table-column label="期次" width="80" align="center"><template #default="{ row }">第{{ row.installment_no }}期</template></el-table-column>
            <el-table-column label="计划日期" width="140"><template #default="{ row }">{{ formatDate(row.plan_date) }}</template></el-table-column>
            <el-table-column label="计划金额" width="130" align="right"><template #default="{ row }">¥{{ formatAmount(row.plan_amount) }}</template></el-table-column>
            <el-table-column label="备注" min-width="160"><template #default="{ row }">{{ row.remark || '—' }}</template></el-table-column>
            <el-table-column v-if="canPaymentDelete()" label="操作" width="80" align="center">
              <template #default="{ row }"><el-button link type="danger" size="small" @click="deletePlan(row)">删</el-button></template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!plans.length" description="尚未添加回款计划" :image-size="48" />

          <div class="detail-page__card-head mt-head">
            <span>回款记录 <span class="detail-page__paid">已到账：¥{{ formatAmount(paidTotal) }} / ¥{{ formatAmount(order.amount) }}</span></span>
            <el-button v-if="canPaymentCreate()" size="small" type="primary" @click="openCreatePay">登记回款</el-button>
          </div>
          <el-table :data="payments" border size="small">
            <el-table-column prop="payment_number" label="回款号" width="150" />
            <el-table-column label="金额" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.amount) }}</template></el-table-column>
            <el-table-column label="到账日" width="140"><template #default="{ row }">{{ formatDate(row.paid_at) }}</template></el-table-column>
            <el-table-column label="方式" width="80" align="center"><template #default="{ row }">{{ PAY_METHOD_META[row.method] || row.method }}</template></el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }"><el-tag :type="PAY_STATUS_META[row.status]?.type" size="small">{{ PAY_STATUS_META[row.status]?.label }}</el-tag></template>
            </el-table-column>
            <el-table-column label="备注" min-width="140"><template #default="{ row }">{{ row.remark || '—' }}</template></el-table-column>
            <el-table-column label="操作" width="160" align="center">
              <template #default="{ row }">
                <el-button v-if="canPaymentConfirm() && row.status === 'pending'" link type="success" size="small" @click="confirmPay(row)">确认</el-button>
                <el-button v-if="canPaymentReverse() && row.status === 'confirmed'" link type="warning" size="small" @click="reversePay(row)">冲销</el-button>
                <el-button v-if="canPaymentDelete()" link type="danger" size="small" @click="deletePay(row)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!payments.length" description="尚未登记回款" :image-size="48" />
        </el-tab-pane>

        <el-tab-pane label="发货" name="deliveries">
          <div class="detail-page__card-head">
            <span>发货单</span>
            <el-button
              v-if="canEdit() && (order.status === 'confirmed' || order.status === 'executing' || order.status === 'completed')"
              size="small"
              type="primary"
              @click="deliveryDialogVisible = true; deliveryForm = { carrier: '', tracking_number: '', remark: '' }"
            >创建发货</el-button>
          </div>
          <el-table :data="deliveries" border size="small" empty-text="暂无发货单">
            <el-table-column prop="delivery_number" label="发货号" width="150" />
            <el-table-column prop="carrier" label="承运商" width="100" />
            <el-table-column prop="tracking_number" label="运单号" min-width="140" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">{{ { preparing: '备货', shipped: '已发运', delivered: '已签收', returned: '退回' }[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column label="发运时间" width="150"><template #default="{ row }">{{ formatDate(row.shipped_at) || '—' }}</template></el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button v-if="canEdit() && row.status === 'preparing'" link type="primary" @click="shipDelivery(row)">发运</el-button>
                <el-button v-if="canEdit() && (row.status === 'shipped' || row.status === 'preparing')" link type="success" @click="completeDelivery(row)">签收</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="发票" name="invoices">
          <div class="detail-page__card-head">
            <span>发票</span>
            <el-button
              v-if="canEdit() && !['draft','pending_approval','rejected','cancelled','superseded'].includes(order.status)"
              size="small"
              type="primary"
              @click="invoiceDialogVisible = true; invoiceForm = { invoice_type: 'vat', amount: Number(order.amount), tax_amount: taxTotal }"
            >开票</el-button>
          </div>
          <el-table :data="invoices" border size="small" empty-text="暂无发票">
            <el-table-column prop="invoice_number" label="发票号" width="150" />
            <el-table-column label="类型" width="90" align="center">
              <template #default="{ row }">{{ { vat: '专票', normal: '普票', electronic: '电子' }[row.invoice_type] || row.invoice_type }}</template>
            </el-table-column>
            <el-table-column label="未税" width="110" align="right"><template #default="{ row }">¥{{ formatAmount(row.amount) }}</template></el-table-column>
            <el-table-column label="税额" width="100" align="right"><template #default="{ row }">¥{{ formatAmount(row.tax_amount) }}</template></el-table-column>
            <el-table-column label="价税合计" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.total_amount) }}</template></el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">{{ { draft: '草稿', issued: '已开具', void: '已作废' }[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="center">
              <template #default="{ row }">
                <el-button v-if="canEdit() && row.status === 'draft'" link type="primary" @click="issueInvoice(row)">开具</el-button>
                <el-button
                  v-if="canEdit() && row.status === 'issued'"
                  link
                  type="success"
                  @click="openMatchInvoice(row)"
                >核销</el-button>
                <el-button v-if="canEdit() && row.status !== 'void'" link type="danger" @click="voidInvoice(row)">作废</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`退款（${refunds.length}）`" name="refunds">
          <div class="detail-page__card-head">
            <span>退款单</span>
            <el-button
              v-if="canPaymentCreate() && !['draft','pending_approval','rejected','cancelled','superseded'].includes(order.status)"
              size="small"
              type="primary"
              @click="openRefund"
            >申请退款</el-button>
          </div>
          <el-table :data="refunds" border size="small" empty-text="暂无退款单">
            <el-table-column prop="refund_number" label="退款号" width="150" />
            <el-table-column label="金额" width="120" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="REFUND_STATUS[row.status]?.type">
                  {{ REFUND_STATUS[row.status]?.label || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" align="center">
              <template #default="{ row }">
                <el-button
                  v-if="canPaymentConfirm() && row.status === 'pending'"
                  link
                  type="success"
                  @click="approveRefund(row)"
                >批准</el-button>
                <el-button
                  v-if="canPaymentConfirm() && (row.status === 'pending' || row.status === 'approved')"
                  link
                  type="primary"
                  @click="completeRefund(row)"
                >完成</el-button>
                <el-button
                  v-if="canPaymentConfirm() && row.status === 'pending'"
                  link
                  type="danger"
                  @click="rejectRefund(row)"
                >驳回</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="修订" name="revisions">
          <el-table :data="revisions" border size="small" empty-text="暂无修订记录">
            <el-table-column label="版本" width="80" align="center"><template #default="{ row }">v{{ row.version }}</template></el-table-column>
            <el-table-column prop="order_number" label="订单号" width="150" />
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="金额" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.amount) }}</template></el-table-column>
            <el-table-column label="状态" width="110" align="center">
              <template #default="{ row }">{{ STATUS_META[row.status]?.label || row.status }}</template>
            </el-table-column>
            <el-table-column label="修订原因" min-width="140"><template #default="{ row }">{{ row.revision_reason || '—' }}</template></el-table-column>
            <el-table-column label="操作" width="90" align="center">
              <template #default="{ row }">
                <el-button link type="primary" @click="router.push(`/crm/orders/${row.id}`)">查看</el-button>
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
          <el-timeline v-if="activities.length" class="crm-timeline">
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
          <el-alert
            v-if="!order.customer_id"
            type="info"
            :closable="false"
            title="订单未关联客户，无法挂接客户任务"
            style="margin-bottom: 12px"
          />
          <CrmEntityTasks
            v-else
            entity-type="customer"
            :entity-id="order.customer_id"
            :default-assignee-id="order.owner_user_id || ''"
          />
        </el-tab-pane>
      </el-tabs>
    </div>

    <OrderFormDialog v-model:visible="editVisible" :record="order" @saved="loadOrder" />

    <el-dialog v-model="rejectVisible" title="驳回审批" width="440px">
      <el-input v-model="rejectReason" type="textarea" :rows="3" maxlength="500" placeholder="请填写驳回原因" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reviseVisible" title="修订订单" width="440px">
      <el-alert type="info" :closable="false" title="将生成新版本订单并自动提交重审，原单标记为已修订。" style="margin-bottom: 12px" />
      <el-input v-model="reviseReason" type="textarea" :rows="3" maxlength="500" placeholder="修订原因（必填）" />
      <template #footer>
        <el-button @click="reviseVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRevise">确认修订</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deliveryDialogVisible" title="创建发货单" width="440px">
      <el-form label-width="88px">
        <el-form-item label="承运商"><el-input v-model="deliveryForm.carrier" /></el-form-item>
        <el-form-item label="运单号"><el-input v-model="deliveryForm.tracking_number" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="deliveryForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deliveryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDelivery">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="invoiceDialogVisible" title="创建发票" width="440px">
      <el-form label-width="88px">
        <el-form-item label="类型">
          <el-select v-model="invoiceForm.invoice_type">
            <el-option label="专票" value="vat" /><el-option label="普票" value="normal" /><el-option label="电子" value="electronic" />
          </el-select>
        </el-form-item>
        <el-form-item label="未税金额"><el-input-number v-model="invoiceForm.amount" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="税额"><el-input-number v-model="invoiceForm.tax_amount" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="invoiceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitInvoice">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="planDialogVisible" title="添加回款计划" width="440px">
      <el-form label-width="88px">
        <el-form-item label="期次"><el-input-number v-model="planForm.installment_no" :min="1" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="计划日期"><el-date-picker v-model="planForm.plan_date" type="date" value-format="YYYY-MM-DD" style="width: 200px" /></el-form-item>
        <el-form-item label="计划金额"><el-input-number v-model="planForm.plan_amount" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="planForm.remark" maxlength="500" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPlan">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="payDialogVisible" title="登记回款" width="440px">
      <el-form label-width="88px">
        <el-form-item label="关联计划">
          <el-select v-model="payForm.plan_id" clearable placeholder="可选" style="width: 100%">
            <el-option v-for="p in plans" :key="p.id" :label="`第${p.installment_no}期 - ¥${p.plan_amount}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="回款金额"><el-input-number v-model="payForm.amount" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="到账日期"><el-date-picker v-model="payForm.paid_at" type="date" value-format="YYYY-MM-DD" style="width: 200px" /></el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="payForm.method">
            <el-option label="银行" value="bank" /><el-option label="微信" value="wechat" />
            <el-option label="支付宝" value="alipay" /><el-option label="现金" value="cash" /><el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="payForm.status">
            <el-option label="待确认" value="pending" /><el-option label="已到账" value="confirmed" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="payForm.remark" maxlength="500" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPay">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="matchDialogVisible" title="发票核销回款" width="440px">
      <el-form label-width="96px">
        <el-form-item label="回款" required>
          <el-select v-model="matchForm.payment_id" placeholder="选择已确认回款" style="width: 100%">
            <el-option
              v-for="p in confirmedPayments"
              :key="p.id"
              :label="`${p.payment_number} · ¥${formatAmount(p.amount)}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="核销金额" required>
          <el-input-number v-model="matchForm.matched_amount" :min="0.01" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="matchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="matchSaving" @click="submitMatchInvoice">核销</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="refundDialogVisible" title="申请退款" width="440px">
      <el-form label-width="96px">
        <el-form-item label="原回款">
          <el-select v-model="refundForm.original_payment_id" clearable placeholder="可选" style="width: 100%">
            <el-option
              v-for="p in confirmedPayments"
              :key="p.id"
              :label="`${p.payment_number} · ¥${formatAmount(p.amount)}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="退款金额" required>
          <el-input-number v-model="refundForm.amount" :min="0.01" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="refundForm.reason" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="refundSaving" @click="submitRefund">提交</el-button>
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
.detail-page__kpi { margin-top: 12px; display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.kpi { padding: 10px 12px; background: var(--el-fill-color-light); border-radius: 6px; }
.kpi__label { font-size: 12px; color: var(--el-text-color-secondary); }
.kpi__value { margin-top: 4px; font-size: 16px; font-weight: 600; }
.kpi__value--ok { color: var(--el-color-success); }
.detail-page__body { margin-top: 12px; }
.detail-page__total { margin-top: 12px; text-align: right; font-size: 15px; }
.detail-page__total b { color: var(--el-color-primary); font-size: 18px; }
.detail-page__total-sep { margin-left: 16px; }
.detail-page__card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-page__paid { margin-left: 12px; color: var(--el-text-color-secondary); font-size: 13px; font-weight: normal; }
.mb-table { margin-bottom: 8px; }
.mt-head { margin-top: 20px; }
.approval-card { padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; margin-bottom: 12px; }
.approval-card__head { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; font-size: 13px; color: var(--el-text-color-secondary); }
.approval-card__reason { margin-bottom: 10px; color: var(--el-color-danger); font-size: 13px; }
.activity-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.crm-panel { margin-bottom: 16px; }
.crm-panel__title { font-weight: 600; margin-bottom: 8px; }
.crm-timeline__card { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.crm-timeline__content { margin: 0; font-size: 14px; color: var(--el-text-color-regular); }
@media (max-width: 960px) {
  .detail-page__kpi { grid-template-columns: repeat(2, 1fr); }
}
</style>
