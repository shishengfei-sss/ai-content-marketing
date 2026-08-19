<script setup>
/**
 * M13 申请开票 / M13b 查看。对照 PRD #m13 · #m13b · 03#f5
 * 驳回后同页改抬头重提（更新同一申请）。站内信/短信本批不接。
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, setShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const orderId = ref('')
const viewOnly = ref(false)
const loading = ref(true)
const submitting = ref(false)
const order = ref(null)
const existing = ref(null)
const openidHint = ref('')
const titleType = ref('person') // person | company
const title = ref('')
const taxNo = ref('')
const email = ref('')

const amountText = computed(() => `¥${(((order.value?.amount_cents) || 0) / 100).toFixed(2)}`)

const STATUS_LABEL = {
  submitted: '待商家开具',
  pending: '待商家开具',
  issued: '已开票',
  rejected: '已驳回',
}

async function load() {
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId(), openidHint.value || undefined)
    order.value = await shopBuyerApi.getOrder(orderId.value)
    const invs = await shopBuyerApi.listInvoices({ page: 1, page_size: 50 })
    existing.value = (invs.items || []).find((i) => i.order_id === orderId.value) || null
    if (existing.value?.status === 'issued') viewOnly.value = true
    if (existing.value?.status === 'rejected') {
      title.value = existing.value.title || ''
      titleType.value = existing.value.title_type || 'person'
      taxNo.value = existing.value.tax_no || ''
      email.value = existing.value.email || ''
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!title.value.trim()) {
    uni.showToast({ title: '请填写抬头', icon: 'none' })
    return
  }
  if (!email.value.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    uni.showToast({ title: '邮箱格式错误', icon: 'none' })
    return
  }
  if (titleType.value === 'company') {
    const tax = taxNo.value.trim()
    if (!tax) {
      uni.showToast({ title: '请填写税号', icon: 'none' })
      return
    }
    if (tax.length < 15 || tax.length > 20) {
      uni.showToast({ title: '税号须为 15–20 位', icon: 'none' })
      return
    }
  }
  submitting.value = true
  try {
    const inv = await shopBuyerApi.createInvoice({
      order_id: orderId.value,
      title_type: titleType.value,
      title: title.value.trim(),
      tax_no: titleType.value === 'company' ? taxNo.value.trim() : undefined,
      email: email.value.trim(),
    })
    existing.value = inv
    uni.showToast({ title: '已提交', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: e.message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function copyInvoiceNo() {
  if (!existing.value?.invoice_no) return
  uni.setClipboardData({
    data: existing.value.invoice_no,
    success: () => uni.showToast({ title: '已复制', icon: 'success' }),
  })
}

function openUrl() {
  if (!existing.value?.invoice_url) {
    uni.showToast({ title: '暂无发票链接', icon: 'none' })
    return
  }
  // #ifdef H5
  window.open(existing.value.invoice_url, '_blank')
  // #endif
  // #ifndef H5
  uni.setClipboardData({
    data: existing.value.invoice_url,
    success: () => uni.showToast({ title: '链接已复制', icon: 'success' }),
  })
  // #endif
}

onLoad((q) => {
  orderId.value = (q?.order_id || '').trim()
  viewOnly.value = q?.view === '1'
  const tid = (q?.tenant_id || '').trim()
  if (tid) setShopBuyerTenantId(tid)
  openidHint.value = (q?.openid || '').trim()
  if (!orderId.value) {
    uni.showToast({ title: '缺少订单', icon: 'none' })
    loading.value = false
    return
  }
  load()
})
</script>

<template>
  <view class="page">
    <view class="head">
      <text class="title">{{ existing?.status === 'issued' ? '电子发票' : '申请开票' }}</text>
    </view>

    <view v-if="loading" class="empty">加载中…</view>

    <template v-else-if="existing && (existing.status === 'issued' || existing.status === 'submitted' || existing.status === 'pending')">
      <view class="card">
        <text class="line"><text class="k">状态</text>{{ STATUS_LABEL[existing.status] || existing.status }}</text>
        <text class="line"><text class="k">抬头</text>{{ existing.title }}</text>
        <text class="line"><text class="k">金额</text>{{ amountText }}</text>
        <text v-if="existing.invoice_no" class="line"><text class="k">发票号</text>{{ existing.invoice_no }}</text>
        <text v-if="existing.reject_reason" class="line danger">驳回：{{ existing.reject_reason }}</text>
        <view v-if="existing.status === 'issued'" class="ops">
          <button class="btn-primary" @click="openUrl">打开 PDF / 链接</button>
          <button class="btn-ghost" @click="copyInvoiceNo">复制发票号</button>
        </view>
        <view v-else class="hint">待商家在后台开具，请稍后在订单中查看</view>
      </view>
    </template>

    <template v-else>
      <view class="seg">
        <text class="seg-item" :class="{ on: titleType === 'person' }" @click="titleType = 'person'">个人</text>
        <text class="seg-item" :class="{ on: titleType === 'company' }" @click="titleType = 'company'">企业</text>
      </view>
      <view class="field">
        <text class="label">抬头 <text class="req">*</text></text>
        <input v-model="title" class="input" :placeholder="titleType === 'person' ? '姓名' : '企业名称'" />
      </view>
      <view v-if="titleType === 'company'" class="field">
        <text class="label">税号 <text class="req">*</text></text>
        <input v-model="taxNo" class="input" placeholder="15–20 位税号" />
      </view>
      <view class="field">
        <text class="label">邮箱 <text class="req">*</text></text>
        <input v-model="email" class="input" placeholder="email" />
      </view>
      <view class="field">
        <text class="label">金额（只读）</text>
        <text class="readonly">{{ amountText }}</text>
      </view>
      <text v-if="existing?.status === 'rejected'" class="danger">上次驳回：{{ existing.reject_reason || '—' }}，可修改后重提</text>
      <view class="footer">
        <button class="btn-primary" :loading="submitting" @click="submit">提交</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding: 16px 16px 100px;
  box-sizing: border-box;
}
.head {
  margin-bottom: 14px;
}
.title {
  font-size: 20px;
  font-weight: 700;
}
.seg {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.seg-item {
  flex: 1;
  text-align: center;
  padding: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #64748b;
}
.seg-item.on {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
  font-weight: 600;
}
.field {
  background: #fff;
  border-radius: 16px;
  padding: 12px;
  margin-bottom: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}
.label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.req {
  color: #ef4444;
}
.input {
  font-size: 15px;
}
.readonly {
  font-size: 16px;
  font-weight: 700;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
}
.line {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
}
.k {
  color: #64748b;
  margin-right: 8px;
}
.danger {
  display: block;
  color: #dc2626;
  font-size: 12px;
  margin: 8px 0;
}
.ops {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hint {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: #fff;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 999px;
  font-weight: 700;
}
.btn-ghost {
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  color: #334155;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
