<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import CrmEntityTags from '../../components/crm/CrmEntityTags.vue'
import CrmEntityAttachments from '../../components/crm/CrmEntityAttachments.vue'
import { formatDate, formatDateTime } from '../../utils/datetime'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const payment = ref(null)
const order = ref(null)
const customer = ref(null)
const refunds = ref([])
const receivables = ref(null)
const activeTab = ref('basic')
const refundDialog = ref(false)
const refundForm = ref({ amount: null, reason: '' })
const saving = ref(false)
const editDialog = ref(false)
const editSaving = ref(false)
const editForm = ref({ amount: null, paid_at: '', method: 'bank', remark: '' })

const canConfirm = () => hasPermission(auth.permissions, 'crm.payment.confirm')
const canReverse = () => hasPermission(auth.permissions, 'crm.payment.reverse')
const canCreate = () => hasPermission(auth.permissions, 'crm.payment.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.payment.edit')
const canDelete = () => hasPermission(auth.permissions, 'crm.payment.delete')

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
const isOwner = computed(() => sameUserId(payment.value?.owner_user_id, auth.user?.id))
const canMutate = computed(() => isOwner.value)
const STATUS_META = {
  pending: { label: '待确认', type: 'warning' },
  confirmed: { label: '已到账', type: 'success' },
  reversed: { label: '已冲销', type: 'info' },
}
const METHOD_META = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }
const REFUND_STATUS = {
  pending: { label: '待审', type: 'warning' },
  approved: { label: '已批准', type: 'success' },
  completed: { label: '已完成', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
}

const orderRefunds = computed(() => refunds.value || [])
const bucketLabel = { current: '未逾期', d30: '1–30天', d60: '31–60天', d90plus: '60天+' }

async function loadAll() {
  loading.value = true
  try {
    const { data } = await crmApi.getPayment(route.params.id)
    payment.value = data
    customer.value = null
    if (data.order_id) {
      try {
        const o = await crmApi.getOrder(data.order_id)
        order.value = o.data
      } catch {
        order.value = null
      }
      await loadRefunds(data.order_id)
    }
    const customerId = data.customer_id || order.value?.customer_id
    if (customerId) {
      try {
        const c = await crmApi.getCustomer(customerId)
        customer.value = c.data
      } catch {
        customer.value = null
      }
    }
    try {
      const r = await crmApi.listReceivables()
      receivables.value = r.data
    } catch {
      receivables.value = null
    }
  } catch (e) {
    ElMessage.error(e.message || '加载回款失败')
  } finally {
    loading.value = false
  }
}

async function loadRefunds(orderId) {
  try {
    const { data } = await crmApi.listOrderRefunds(orderId)
    refunds.value = Array.isArray(data) ? data : []
  } catch {
    refunds.value = []
  }
}

function openEdit() {
  editForm.value = {
    amount: Number(payment.value?.amount || 0),
    paid_at: payment.value?.paid_at ? String(payment.value.paid_at).slice(0, 16) : '',
    method: payment.value?.method || 'bank',
    remark: payment.value?.remark || '',
  }
  editDialog.value = true
}

async function submitEdit() {
  if (editForm.value.amount == null || editForm.value.amount < 0) {
    ElMessage.warning('请填写金额')
    return
  }
  editSaving.value = true
  try {
    const { data } = await crmApi.updatePayment(payment.value.id, {
      amount: editForm.value.amount,
      paid_at: editForm.value.paid_at ? new Date(editForm.value.paid_at).toISOString() : null,
      method: editForm.value.method,
      remark: editForm.value.remark || null,
    })
    payment.value = data
    editDialog.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    editSaving.value = false
  }
}

async function handleConfirm() {
  try {
    await crmApi.confirmPayment(payment.value.id)
    ElMessage.success('已确认到账')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.message || '确认失败')
  }
}

async function handleReverse() {
  try {
    await ElMessageBox.confirm('确定冲销该回款？', '冲销')
    await crmApi.reversePayment(payment.value.id)
    ElMessage.success('已冲销')
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '冲销失败')
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定删除该回款记录？', '删除', { type: 'warning' })
    await crmApi.deletePayment(payment.value.id)
    ElMessage.success('已删除')
    router.push('/crm/payments')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function openRefund() {
  refundForm.value = {
    amount: Number(payment.value?.amount || 0),
    reason: '',
  }
  refundDialog.value = true
}

async function submitRefund() {
  if (refundForm.value.amount == null || refundForm.value.amount <= 0) {
    ElMessage.warning('请填写退款金额')
    return
  }
  saving.value = true
  try {
    await crmApi.createRefund({
      order_id: payment.value.order_id,
      original_payment_id: payment.value.id,
      amount: refundForm.value.amount,
      reason: refundForm.value.reason || null,
    })
    ElMessage.success('退款申请已提交')
    refundDialog.value = false
    await loadRefunds(payment.value.order_id)
    activeTab.value = 'refunds'
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    saving.value = false
  }
}

async function approveRefund(row) {
  try {
    await crmApi.approveRefund(row.id)
    ElMessage.success('已批准')
    await loadRefunds(payment.value.order_id)
  } catch (e) {
    ElMessage.error(e.message || '批准失败')
  }
}

async function completeRefund(row) {
  try {
    await crmApi.completeRefund(row.id)
    ElMessage.success('已完成退款')
    await loadRefunds(payment.value.order_id)
  } catch (e) {
    ElMessage.error(e.message || '完成失败')
  }
}

async function rejectRefund(row) {
  try {
    await ElMessageBox.confirm('确定驳回该退款？', '驳回')
    await crmApi.rejectRefund(row.id)
    ElMessage.success('已驳回')
    await loadRefunds(payment.value.order_id)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '驳回失败')
  }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(async () => {
  await loadMembers()
  loadAll()
})
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="detail-page__back">
      <el-button link @click="router.push('/crm/payments')">
        <el-icon><ArrowLeft /></el-icon> 返回回款列表
      </el-button>
    </div>

    <div v-if="payment" class="page-card detail-page__head">
      <div>
        <h2 class="detail-page__title">{{ payment.payment_number }}</h2>
        <div class="detail-page__meta">
          <el-tag :type="STATUS_META[payment.status]?.type">{{ STATUS_META[payment.status]?.label }}</el-tag>
          <span class="detail-page__amount">¥{{ formatAmount(payment.amount) }}</span>
          <span>{{ METHOD_META[payment.method] || payment.method }}</span>
          <span>负责人：{{ resolveMemberName(payment.owner_user_id) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button
          v-if="canEdit() && canMutate && payment.status === 'pending'"
          @click="openEdit"
        >编辑</el-button>
        <el-button
          v-if="canDelete() && canMutate && payment.status === 'pending'"
          type="danger"
          @click="handleDelete"
        >删除</el-button>
        <el-button
          v-if="canConfirm() && canMutate && payment.status === 'pending'"
          type="success"
          @click="handleConfirm"
        >确认到账</el-button>
        <el-button
          v-if="canReverse() && canMutate && payment.status === 'confirmed'"
          type="warning"
          @click="handleReverse"
        >冲销</el-button>
        <el-button
          v-if="canCreate() && canMutate && payment.status === 'confirmed'"
          type="primary"
          @click="openRefund"
        >申请退款</el-button>
      </div>
    </div>

    <div v-if="payment" class="detail-page__body page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <div style="margin-bottom: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">标签</div>
            <CrmEntityTags
              entity-type="payment"
              :entity-id="payment.id"
              :editable="canEdit() && canMutate"
            />
          </div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="回款号">{{ payment.payment_number }}</el-descriptions-item>
            <el-descriptions-item label="客户">
              <el-link
                v-if="customer"
                type="primary"
                @click="router.push(`/crm/customers/${customer.id}`)"
              >{{ customer.company_name }}</el-link>
              <span v-else-if="payment.customer_id || order?.customer_id">{{ payment.customer_id || order?.customer_id }}</span>
              <span v-else>—</span>
            </el-descriptions-item>
            <el-descriptions-item label="关联订单">
              <el-link
                v-if="order"
                type="primary"
                @click="router.push(`/crm/orders/${order.id}`)"
              >{{ order.order_number }} · {{ order.title }}</el-link>
              <span v-else>{{ payment.order_id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="金额">¥{{ formatAmount(payment.amount) }}</el-descriptions-item>
            <el-descriptions-item label="到账日">{{ formatDate(payment.paid_at) }}</el-descriptions-item>
            <el-descriptions-item label="收款方式">{{ METHOD_META[payment.method] || payment.method }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ STATUS_META[payment.status]?.label }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ payment.remark || '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(payment.created_at, { withSeconds: false }) }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-top: 16px">
            <CrmEntityAttachments
              entity-type="payment"
              :entity-id="payment.id"
              :editable="canEdit() && canMutate"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane :label="`退款（${orderRefunds.length}）`" name="refunds">
          <el-table :data="orderRefunds" border size="small" empty-text="暂无退款单">
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
                  v-if="canConfirm() && row.status === 'pending'"
                  link
                  type="success"
                  @click="approveRefund(row)"
                >批准</el-button>
                <el-button
                  v-if="canConfirm() && (row.status === 'pending' || row.status === 'approved')"
                  link
                  type="primary"
                  @click="completeRefund(row)"
                >完成</el-button>
                <el-button
                  v-if="canConfirm() && row.status === 'pending'"
                  link
                  type="danger"
                  @click="rejectRefund(row)"
                >驳回</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="应收概览" name="receivables">
          <div v-if="receivables" class="recv-summary">
            <div class="recv-summary__item">
              <span>合计应收</span>
              <strong>¥{{ formatAmount(receivables.total_outstanding) }}</strong>
            </div>
            <div
              v-for="(label, key) in bucketLabel"
              :key="key"
              class="recv-summary__item"
            >
              <span>{{ label }}</span>
              <strong>¥{{ formatAmount(receivables.buckets?.[key] || 0) }}</strong>
            </div>
          </div>
          <el-table
            v-if="receivables"
            :data="receivables.items || []"
            border
            size="small"
            empty-text="暂无应收明细"
            class="recv-table"
          >
            <el-table-column prop="order_number" label="订单号" width="150" />
            <el-table-column prop="order_title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="期数" width="70" align="center">
              <template #default="{ row }">{{ row.installment_no }}</template>
            </el-table-column>
            <el-table-column label="计划日" width="120">
              <template #default="{ row }">{{ formatDate(row.plan_date) }}</template>
            </el-table-column>
            <el-table-column label="计划金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.plan_amount) }}</template>
            </el-table-column>
            <el-table-column label="未收" width="110" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.outstanding) }}</template>
            </el-table-column>
            <el-table-column label="账龄" width="90" align="center">
              <template #default="{ row }">{{ bucketLabel[row.aging_bucket] || row.aging_bucket }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="无法加载应收" :image-size="64" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="refundDialog" title="申请退款" width="420px">
      <el-form label-width="88px">
        <el-form-item label="退款金额" required>
          <el-input-number v-model="refundForm.amount" :min="0.01" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="refundForm.reason" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="refundDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRefund">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialog" title="编辑回款" width="460px">
      <el-form label-width="88px">
        <el-form-item label="金额" required>
          <el-input-number v-model="editForm.amount" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到账日">
          <el-date-picker
            v-model="editForm.paid_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="editForm.method" style="width: 100%">
            <el-option label="银行" value="bank" />
            <el-option label="微信" value="wechat" />
            <el-option label="支付宝" value="alipay" />
            <el-option label="现金" value="cash" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEdit">保存</el-button>
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
.recv-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.recv-summary__item {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.recv-summary__item span {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.recv-summary__item strong { font-size: 15px; }
.recv-table { margin-top: 4px; }
@media (max-width: 960px) {
  .recv-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
