<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import OrderFormDialog from './OrderFormDialog.vue'
import { ArrowLeft } from '@element-plus/icons-vue'

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

const planDialogVisible = ref(false)
const planForm = ref(emptyPlan())
const payDialogVisible = ref(false)
const payForm = ref(emptyPay())

function emptyPlan() { return { installment_no: 1, plan_date: '', plan_amount: null, remark: '' } }
function emptyPay() { return { amount: null, paid_at: '', method: 'bank', status: 'pending', remark: '', plan_id: '' } }

const canEdit = () => hasPermission(auth.permissions, 'crm.order.edit')
const canPlace = () => hasPermission(auth.permissions, 'crm.order.place')
const canDelete = () => hasPermission(auth.permissions, 'crm.order.delete')
const canPaymentCreate = () => hasPermission(auth.permissions, 'crm.payment.create')
const canPaymentConfirm = () => hasPermission(auth.permissions, 'crm.payment.confirm')
const canPaymentReverse = () => hasPermission(auth.permissions, 'crm.payment.reverse')
const canPaymentDelete = () => hasPermission(auth.permissions, 'crm.payment.delete')

const STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '已确认', type: 'success' },
  executing: { label: '执行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
}
const SOURCE_META = { deal: '商机', quote: '报价', contract: '合同' }
const PAY_STATUS_META = { pending: { label: '待确认', type: 'warning' }, confirmed: { label: '已到账', type: 'success' }, reversed: { label: '已冲销', type: 'info' } }
const PAY_METHOD_META = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }

async function loadOrder() {
  loading.value = true
  try {
    const { data } = await crmApi.getOrder(route.params.id)
    order.value = data
    if (data.customer_id) {
      try { const c = await crmApi.getCustomer(data.customer_id); customer.value = c.data } catch { customer.value = null }
    }
    await Promise.all([loadPlans(), loadPayments()])
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

const paidTotal = ref(0)
function computePaidTotal() {
  paidTotal.value = payments.value.filter((p) => p.status === 'confirmed').reduce((acc, p) => acc + Number(p.amount || 0), 0)
}

async function handleConfirm() {
  try { await crmApi.confirmOrder(order.value.id); ElMessage.success('已确认'); await loadOrder() }
  catch (e) { ElMessage.error(e.message || '确认失败') }
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

import { watch } from 'vue'
watch(payments, computePaidTotal, { deep: true })

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
          <el-tag :type="STATUS_META[order.status]?.type">{{ STATUS_META[order.status]?.label }}</el-tag>
          <el-tag size="small" type="info">{{ SOURCE_META[order.source] }}</el-tag>
          <span class="detail-page__amount">¥{{ formatAmount(order.amount) }}</span>
          <span>{{ order.order_number }}</span>
          <span>负责人：{{ resolveMemberName(order.owner_user_id) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button v-if="canEdit() && order.status === 'draft'" @click="editVisible = true">编辑</el-button>
        <el-button v-if="canPlace() && order.status === 'draft'" type="success" @click="handleConfirm">确认订单</el-button>
        <el-button v-if="canEdit() && order.status !== 'cancelled' && order.status !== 'completed'" type="warning" @click="handleCancel">取消</el-button>
        <el-button v-if="canDelete()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="order" class="detail-page__body">
      <el-card shadow="never">
        <template #header>基本信息</template>
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
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>订单明细</template>
        <el-table :data="order.lines || []" border size="small">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column label="数量" width="100" align="right"><template #default="{ row }">{{ row.quantity }}</template></el-table-column>
          <el-table-column label="单价" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.unit_price) }}</template></el-table-column>
          <el-table-column label="折扣%" width="80" align="center"><template #default="{ row }">{{ row.discount_rate != null ? row.discount_rate + '%' : '—' }}</template></el-table-column>
          <el-table-column label="小计" width="130" align="right"><template #default="{ row }">¥{{ formatAmount(row.line_total) }}</template></el-table-column>
        </el-table>
        <div class="detail-page__total">合计：<b>¥{{ formatAmount(order.amount) }}</b></div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="detail-page__card-head">
            <span>回款计划</span>
            <el-button v-if="canPaymentCreate()" size="small" @click="openCreatePlan">添加计划</el-button>
          </div>
        </template>
        <el-table :data="plans" border size="small">
          <el-table-column label="期次" width="80" align="center"><template #default="{ row }">第{{ row.installment_no }}期</template></el-table-column>
          <el-table-column label="计划日期" width="140"><template #default="{ row }">{{ formatDate(row.plan_date) }}</template></el-table-column>
          <el-table-column label="计划金额" width="130" align="right"><template #default="{ row }">¥{{ formatAmount(row.plan_amount) }}</template></el-table-column>
          <el-table-column label="备注" min-width="160"><template #default="{ row }">{{ row.remark || '—' }}</template></el-table-column>
          <el-table-column v-if="canPaymentDelete()" label="操作" width="80" align="center"><template #default="{ row }"><el-button link type="danger" size="small" @click="deletePlan(row)">删</el-button></template></el-table-column>
        </el-table>
        <el-empty v-if="!plans.length" description="尚未添加回款计划" :image-size="60" />
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="detail-page__card-head">
            <span>回款记录<span class="detail-page__paid">已到账：¥{{ formatAmount(paidTotal) }} / ¥{{ formatAmount(order.amount) }}</span></span>
            <el-button v-if="canPaymentCreate()" size="small" type="primary" @click="openCreatePay">登记回款</el-button>
          </div>
        </template>
        <el-table :data="payments" border size="small">
          <el-table-column prop="payment_number" label="回款号" width="150" />
          <el-table-column label="金额" width="120" align="right"><template #default="{ row }">¥{{ formatAmount(row.amount) }}</template></el-table-column>
          <el-table-column label="到账日" width="140"><template #default="{ row }">{{ formatDate(row.paid_at) }}</template></el-table-column>
          <el-table-column label="方式" width="80" align="center"><template #default="{ row }">{{ PAY_METHOD_META[row.method] || row.method }}</template></el-table-column>
          <el-table-column label="状态" width="90" align="center"><template #default="{ row }"><el-tag :type="PAY_STATUS_META[row.status]?.type" size="small">{{ PAY_STATUS_META[row.status]?.label }}</el-tag></template></el-table-column>
          <el-table-column label="备注" min-width="140"><template #default="{ row }">{{ row.remark || '—' }}</template></el-table-column>
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button v-if="canPaymentConfirm() && row.status === 'pending'" link type="success" size="small" @click="confirmPay(row)">确认</el-button>
              <el-button v-if="canPaymentReverse() && row.status === 'confirmed'" link type="warning" size="small" @click="reversePay(row)">冲销</el-button>
              <el-button v-if="canPaymentDelete()" link type="danger" size="small" @click="deletePay(row)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!payments.length" description="尚未登记回款" :image-size="60" />
      </el-card>
    </div>

    <OrderFormDialog v-model:visible="editVisible" :record="order" @saved="loadOrder" />

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
            <el-option label="银行" value="bank" />
            <el-option label="微信" value="wechat" />
            <el-option label="支付宝" value="alipay" />
            <el-option label="现金" value="cash" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="payForm.status">
            <el-option label="待确认" value="pending" />
            <el-option label="已到账" value="confirmed" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="payForm.remark" maxlength="500" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPay">保存</el-button>
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
.detail-page__body { margin-top: 16px; display: flex; flex-direction: column; gap: 16px; }
.detail-page__total { margin-top: 12px; text-align: right; font-size: 15px; }
.detail-page__total b { color: var(--el-color-primary); font-size: 18px; }
.detail-page__card-head { display: flex; justify-content: space-between; align-items: center; }
.detail-page__paid { margin-left: 12px; color: var(--el-text-color-secondary); font-size: 13px; font-weight: normal; }
</style>
