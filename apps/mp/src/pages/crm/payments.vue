<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { PAYMENT_STATUS_LABEL } from '@/utils/crmConstants'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'

const statusTab = ref('')
const permissions = ref([])
const createVisible = ref(false)
const saving = ref(false)
const orderOptions = ref([])
const form = ref({ order_id: '', amount: '', paid_at: '', method: 'bank', remark: '' })

const METHOD_OPTIONS = [
  { value: 'bank', label: '银行' },
  { value: 'wechat', label: '微信' },
  { value: 'alipay', label: '支付宝' },
  { value: 'cash', label: '现金' },
  { value: 'other', label: '其他' },
]

const canCreate = () => hasPermission(permissions.value, 'crm.payment.create')

async function ensurePerms() {
  const user = await ensureSession()
  permissions.value = user?.permissions || []
}

async function openCreate() {
  await ensurePerms()
  if (!canCreate()) return
  form.value = { order_id: '', amount: '', paid_at: '', method: 'bank', remark: '' }
  try {
    const data = await crmApi.listOrders({ page: 1, page_size: 50, status: 'confirmed' })
    orderOptions.value = (data?.items || []).map((o) => ({
      id: o.id,
      label: `${o.order_number} · ${o.title}`,
    }))
  } catch {
    orderOptions.value = []
  }
  createVisible.value = true
}

async function submitPayment() {
  if (!form.value.order_id) {
    uni.showToast({ title: '请选择订单', icon: 'none' })
    return
  }
  if (!form.value.amount) {
    uni.showToast({ title: '请填写金额', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await crmApi.createPayment({
      order_id: form.value.order_id,
      amount: Number(form.value.amount),
      paid_at: form.value.paid_at || null,
      method: form.value.method,
      status: 'pending',
      remark: form.value.remark || null,
    })
    uni.showToast({ title: '已登记待确认', icon: 'success' })
    createVisible.value = false
  } catch (e) {
    uni.showToast({ title: e.message || '登记失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function setStatusTab(tab) {
  statusTab.value = tab
}

onShow(ensurePerms)
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      :key="statusTab || 'all'"
      entity-type="payment"
      entity-label="回款"
      all-view-label="全部回款"
      empty-text="暂无回款记录"
      search-placeholder="搜索回款编号"
      title-field="payment_number"
      :format-status="(s) => PAYMENT_STATUS_LABEL[s] || s"
      :fetch-list="(params) => crmApi.listPayments(params)"
      :extra-params="() => (statusTab ? { status: statusTab } : {})"
    >
      <template #toolbar-top>
        <view class="status-tabs">
          <view class="status-tab" :class="{ 'status-tab--active': !statusTab }" @tap="setStatusTab('')">全部</view>
          <view class="status-tab" :class="{ 'status-tab--active': statusTab === 'pending' }" @tap="setStatusTab('pending')">待确认</view>
        </view>
      </template>
      <template #toolbar-actions>
        <view v-if="canCreate()" class="toolbar-btn toolbar-btn--primary" @tap="openCreate">
          <text class="toolbar-btn__text">登记回款</text>
        </view>
      </template>
    </CrmEntityListPage>

    <view v-if="createVisible" class="mask" @tap.self="createVisible = false">
      <view class="dialog" @tap.stop>
        <text class="dialog__title">登记回款</text>
        <picker
          :range="orderOptions"
          range-key="label"
          @change="(e) => (form.order_id = orderOptions[e.detail.value]?.id || '')"
        >
          <view class="picker">{{ orderOptions.find((o) => o.id === form.order_id)?.label || '选择订单' }}</view>
        </picker>
        <input v-model="form.amount" class="input" type="digit" placeholder="回款金额" />
        <picker :range="METHOD_OPTIONS" range-key="label" @change="(e) => (form.method = METHOD_OPTIONS[e.detail.value].value)">
          <view class="picker">方式：{{ METHOD_OPTIONS.find((m) => m.value === form.method)?.label }}</view>
        </picker>
        <input v-model="form.remark" class="input" placeholder="备注（可选）" />
        <view class="dialog__acts">
          <button class="btn" hover-class="none" @tap="createVisible = false">取消</button>
          <button class="btn btn--primary" hover-class="none" :disabled="saving" @tap="submitPayment">
            {{ saving ? '提交中…' : '提交' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  padding: 12px;
  box-sizing: border-box;
}

.status-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.status-tab {
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  background: #f1f5f9;
  color: #64748b;
}

.status-tab--active {
  background: #e6f4ff;
  color: #1677ff;
  font-weight: 600;
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #1677ff;
  background: #1677ff;
  color: #fff;
  font-size: 13px;
}

.mask {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.dialog {
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
}

.dialog__title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.input,
.picker {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.dialog__acts {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.btn {
  flex: 1;
  font-size: 14px;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
}
</style>
