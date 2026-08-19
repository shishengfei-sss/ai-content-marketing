<script setup>
/**
 * M12 订单详情 + M12-A 退款弹窗 + M12-B 取消确认 + M12-C 退款进度。
 * 对照 PRD 02-买家端UI.html #m12 #m12a #m12b #m12c
 */
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, setShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const orderId = ref('')
const pendingAction = ref('') // refund | progress | ''
const loading = ref(true)
const busy = ref(false)
const order = ref(null)
const refunds = ref([])
const invoice = ref(null)
const openidHint = ref('')

const showRefund = ref(false)
const showProgress = ref(false)
const showCancel = ref(false)
const reasonCode = ref('')
const remark = ref('')

const REFUND_REASONS = [
  { value: 'buyer_request', label: '买家申请' },
  { value: 'quality', label: '质量问题' },
  { value: 'wrong_order', label: '错拍' },
  { value: 'other', label: '其他' },
]

const STATUS_LABEL = {
  pending_payment: '待付款',
  paid: '已付款',
  claim_pending: '待领权',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
}
const ENT_LABEL = {
  pending: '待生效',
  active: '权益生效',
  expired: '已过期',
  revoked: '已撤销',
}
const REFUND_STATUS = {
  processing: '处理中',
  succeeded: '已退款',
  success: '已退款',
  rejected: '已驳回',
  failed: '失败',
}

function typeLabel(t) {
  return { course: '课程', digital: '资料', service: '服务' }[t] || '商品'
}

const statusLabel = computed(() => STATUS_LABEL[order.value?.status] || order.value?.status || '—')
const statusTone = computed(() => {
  const st = order.value?.status
  if (st === 'pending_payment') return 'warn'
  if (st === 'paid' || st === 'claim_pending') return 'ok'
  if (st === 'refunded' || st === 'closed') return 'off'
  return 'muted'
})
const entLabel = computed(() => {
  if (!order.value?.entitlement_status) {
    if (order.value?.status === 'claim_pending') return '待领权'
    if (order.value?.status === 'pending_payment') return '—'
    return '无权益'
  }
  return ENT_LABEL[order.value.entitlement_status] || order.value.entitlement_status
})
const amountText = computed(() => {
  const c = order.value?.paid_amount_cents ?? order.value?.amount_cents ?? 0
  return `¥${(c / 100).toFixed(2)}`
})
const channelText = computed(() => order.value?.channel || '微信小程序')
const latestRefund = computed(() => (refunds.value && refunds.value[0]) || null)
const progressLines = computed(() => {
  const r = latestRefund.value
  if (!r) return []
  const lines = []
  lines.push({
    at: r.created_at,
    text: r.initiated_by === 'buyer' ? '买家提交退款申请' : '商家发起退款',
    done: true,
  })
  if (r.status === 'rejected') {
    lines.push({ at: r.processed_at, text: `已驳回${r.reason ? `：${r.reason}` : ''}`, done: true })
  } else if (r.status === 'succeeded' || r.status === 'success') {
    lines.push({ at: r.processed_at || r.created_at, text: '退款成功，权益已关闭', done: true })
    lines.push({ at: null, text: '微信原路退回（1–3 工作日）', done: true })
  } else {
    lines.push({ at: null, text: '商家审核 / 处理中', done: false })
    lines.push({ at: null, text: '待微信原路退回（1–3 工作日）', done: false })
  }
  return lines
})

function fmtTime(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 16)
}

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId(), openidHint.value || undefined)
    order.value = await shopBuyerApi.getOrder(orderId.value)
    try {
      const rf = await shopBuyerApi.listOrderRefunds(orderId.value)
      refunds.value = rf.items || []
    } catch {
      refunds.value = []
    }
    try {
      const invs = await shopBuyerApi.listInvoices({ page: 1, page_size: 50 })
      invoice.value =
        (invs.items || []).find((i) => i.order_id === orderId.value || i.order_no === order.value?.order_no) ||
        null
    } catch {
      invoice.value = null
    }
    if (pendingAction.value === 'refund' && order.value?.status === 'paid') {
      openRefund()
      pendingAction.value = ''
    } else if (pendingAction.value === 'progress') {
      openProgress()
      pendingAction.value = ''
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function copyNo() {
  const no = order.value?.order_no
  if (!no) return
  uni.setClipboardData({
    data: no,
    success: () => uni.showToast({ title: '已复制单号', icon: 'none' }),
  })
}

function goLearn() {
  if (order.value?.status === 'claim_pending') {
    const tok = (order.value.claim_token || '').trim()
    const tid = order.value.tenant_id || getShopBuyerTenantId()
    const qs = tok
      ? `?token=${encodeURIComponent(tok)}${tid ? `&tenant_id=${encodeURIComponent(tid)}` : ''}`
      : ''
    uni.navigateTo({ url: `/pages/shop/claim${qs}` })
    return
  }
  if (order.value?.entitlement_status !== 'active') {
    uni.showToast({ title: '权益已关闭', icon: 'none' })
    return
  }
  const t = order.value?.type
  if (t === 'digital') {
    uni.navigateTo({ url: `/pages/shop/materials?entitlement_id=${order.value.entitlement_id}` })
  } else if (t === 'service') {
    uni.navigateTo({ url: `/pages/shop/booking?entitlement_id=${order.value.entitlement_id}` })
  } else {
    uni.navigateTo({ url: `/pages/shop/learn?entitlement_id=${order.value.entitlement_id}` })
  }
}

function goInvoice() {
  if (order.value?.invoice_status === 'issued') {
    uni.navigateTo({ url: `/pages/shop/invoice?order_id=${orderId.value}&view=1` })
    return
  }
  if (order.value?.invoice_status === 'submitted' || order.value?.invoice_status === 'pending') {
    uni.showToast({ title: '待商家开具', icon: 'none' })
    return
  }
  if (order.value?.status !== 'paid') {
    uni.showToast({ title: '仅已付款可开票', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/shop/invoice?order_id=${orderId.value}` })
}

function openRefund() {
  if (order.value?.status !== 'paid') {
    uni.showToast({ title: '不可退款', icon: 'none' })
    return
  }
  reasonCode.value = ''
  remark.value = ''
  showRefund.value = true
}

function openProgress() {
  if (!latestRefund.value && order.value?.status !== 'refunding' && order.value?.status !== 'refunded') {
    uni.showToast({ title: '暂无退款记录', icon: 'none' })
    return
  }
  showProgress.value = true
}

function openCancel() {
  showCancel.value = true
}

async function submitCancel() {
  busy.value = true
  try {
    await shopBuyerApi.cancelOrder(orderId.value)
    showCancel.value = false
    uni.showToast({ title: '已取消', icon: 'success' })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '取消失败', icon: 'none' })
  } finally {
    busy.value = false
  }
}

async function pay() {
  busy.value = true
  try {
    const data = await shopBuyerApi.payOrder(orderId.value)
    uni.showToast({
      title: data.prepay ? '请完成微信支付' : '支付成功',
      icon: data.prepay ? 'none' : 'success',
    })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '支付失败', icon: 'none' })
  } finally {
    busy.value = false
  }
}

async function submitRefund() {
  if (!reasonCode.value) {
    uni.showToast({ title: '请选择退款原因', icon: 'none' })
    return
  }
  if (reasonCode.value === 'other' && (remark.value || '').trim().length < 4) {
    uni.showToast({ title: '其他原因至少 4 字', icon: 'none' })
    return
  }
  busy.value = true
  try {
    await shopBuyerApi.refundOrder(orderId.value, {
      reason_code: reasonCode.value,
      remark: remark.value || null,
    })
    showRefund.value = false
    uni.showToast({ title: '已提交', icon: 'success' })
    await load()
    showProgress.value = true
  } catch (e) {
    uni.showToast({ title: e.message || '退款失败', icon: 'none' })
  } finally {
    busy.value = false
  }
}

function reapplyRefund() {
  showProgress.value = false
  openRefund()
}

function onReasonPick(e) {
  const idx = Number(e.detail.value)
  reasonCode.value = REFUND_REASONS[idx]?.value || ''
}

onLoad((q) => {
  orderId.value = q?.id || ''
  pendingAction.value = q?.action || ''
  const tid = (q?.tenant_id || '').trim()
  if (tid) setShopBuyerTenantId(tid)
  openidHint.value = (q?.openid || '').trim()
})
onShow(load)
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="order">
      <view class="hero" :class="statusTone">
        <text class="hero-st">{{ statusLabel }}</text>
        <view class="hero-tags">
          <text v-if="order.entitlement_status || order.status === 'claim_pending'" class="badge blue">
            {{ entLabel }}
          </text>
          <text v-if="order.invoice_status === 'issued'" class="badge">已开票</text>
        </view>
      </view>

      <view class="card">
        <view class="prod">
          <view class="thumb" :class="order.type || 'course'">{{ typeLabel(order.type).slice(0, 1) }}</view>
          <view class="prod-info">
            <text class="pname">{{ order.product_name || '商品' }}</text>
            <text class="tag">{{ typeLabel(order.type) }}</text>
          </view>
        </view>
        <view class="amt-row">
          <text class="muted">实付</text>
          <text class="amt">{{ amountText }}</text>
        </view>
        <view class="row" @click="copyNo">
          <text class="muted">单号 {{ order.order_no }}</text>
          <text class="link">复制</text>
        </view>
        <text class="muted ch">{{ channelText }}</text>
      </view>

      <view class="actions">
        <template v-if="order.status === 'pending_payment'">
          <button class="btn primary block" :loading="busy" @click="pay">去支付</button>
          <button class="btn block" @click="openCancel">取消订单</button>
        </template>
        <template v-else-if="order.status === 'paid'">
          <button
            v-if="order.entitlement_status === 'active'"
            class="btn primary block"
            @click="goLearn"
          >
            {{ order.type === 'service' ? '去预约' : order.type === 'digital' ? '去领取' : '去学习' }}
          </button>
          <button
            v-if="order.invoice_status === 'issued'"
            class="btn block"
            @click="goInvoice"
          >
            查看发票
          </button>
          <button v-else class="btn block" @click="goInvoice">申请开票</button>
          <button class="btn danger block" @click="openRefund">申请退款</button>
        </template>
        <template v-else-if="order.status === 'claim_pending'">
          <button class="btn primary block" @click="goLearn">去领权</button>
        </template>
        <template v-else-if="order.status === 'refunding' || order.status === 'refunded'">
          <button class="btn block" @click="openProgress">查看进度</button>
        </template>
      </view>

      <view v-if="order.timeline?.length" class="card tl">
        <text class="sec">订单轨迹</text>
        <view v-for="(t, i) in order.timeline" :key="i" class="tl-item">
          <text class="t">{{ fmtTime(t.at) }}</text>
          <text class="e">{{ t.event }}</text>
        </view>
      </view>
    </template>
    <view v-else class="empty">订单不存在</view>

    <!-- M12-A -->
    <view v-if="showRefund" class="mask" @click="showRefund = false">
      <view class="sheet" @click.stop>
        <view class="sheet-hd">
          <text class="sheet-t">申请退款</text>
          <text v-if="order?.invoice_status === 'issued'" class="badge">已开票</text>
        </view>
        <view v-if="order?.invoice_status === 'issued'" class="warn">
          <text class="warn-t">该订单已开具发票</text>
          <text class="warn-b">
            发票号 {{ invoice?.invoice_no || '—' }} · {{ amountText }}
          </text>
          <text class="warn-h">
            退款成功后，商家须在税务系统办理发票红冲（约 1–3 个工作日）。款项仍按实付全额原路退回，权益将关闭。
          </text>
        </view>
        <view class="field">
          <text class="lab">退款金额 *</text>
          <text class="val">{{ amountText }}（全额，Phase 1 不可改）</text>
        </view>
        <view class="field">
          <text class="lab">退款原因 *</text>
          <picker :range="REFUND_REASONS" range-key="label" @change="onReasonPick">
            <view class="picker">
              {{
                REFUND_REASONS.find((r) => r.value === reasonCode)?.label || '请选择'
              }}
            </view>
          </picker>
        </view>
        <view class="field">
          <text class="lab">说明（选填）</text>
          <textarea
            v-model="remark"
            class="area"
            placeholder="选「其他」时必填且 ≥4 字"
            maxlength="200"
          />
        </view>
        <view class="sheet-ft">
          <button class="btn danger" :loading="busy" @click="submitRefund">提交申请</button>
          <button class="btn" @click="showRefund = false">取消</button>
        </view>
      </view>
    </view>

    <!-- M12-B -->
    <view v-if="showCancel" class="mask" @click="showCancel = false">
      <view class="sheet" @click.stop>
        <text class="sheet-t">确认取消订单？</text>
        <view class="field">
          <text class="lab">取消影响（只读）</text>
          <text class="val danger-bg">取消后订单关闭，需重新下单购买</text>
        </view>
        <view class="sheet-ft">
          <button class="btn danger" :loading="busy" @click="submitCancel">确认取消</button>
          <button class="btn" @click="showCancel = false">返回</button>
        </view>
      </view>
    </view>

    <!-- M12-C -->
    <view v-if="showProgress" class="mask" @click="showProgress = false">
      <view class="sheet" @click.stop>
        <text class="sheet-t">
          退款进度{{ latestRefund ? ` · ${String(latestRefund.id).slice(0, 8)}` : '' }}
        </text>
        <view v-if="!latestRefund" class="empty">暂无退款记录</view>
        <view v-else class="progress">
          <view v-for="(p, i) in progressLines" :key="i" class="p-item" :class="{ muted: !p.done }">
            <text class="p-at">{{ p.at ? fmtTime(p.at) : '待处理' }}</text>
            <text class="p-tx">{{ p.text }}</text>
          </view>
          <text class="muted tip">金额 {{ amountText }} · {{ REFUND_STATUS[latestRefund.status] || latestRefund.status }}</text>
          <button
            v-if="latestRefund.status === 'rejected'"
            class="btn danger"
            style="margin-top: 12px"
            @click="reapplyRefund"
          >
            重新申请
          </button>
        </view>
        <button class="btn block" style="margin-top: 12px" @click="showProgress = false">关闭</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding: 0 14px 48px;
}
.hero {
  margin: 0 -14px 14px;
  padding: 20px 18px 18px;
  background: linear-gradient(135deg, #64748b, #94a3b8);
  color: #fff;
}
.hero.ok {
  background: linear-gradient(135deg, #059669, #34d399);
}
.hero.warn {
  background: linear-gradient(135deg, #d97706, #fbbf24);
}
.hero.off {
  background: linear-gradient(135deg, #64748b, #94a3b8);
}
.hero.muted {
  background: linear-gradient(135deg, #475569, #94a3b8);
}
.hero-st {
  display: block;
  font-size: 22px;
  font-weight: 800;
}
.hero-tags {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
}
.badge.blue {
  background: #e6f4ff;
  color: #1677ff;
}
.hero .badge,
.hero .badge.blue {
  background: rgba(255, 255, 255, 0.24);
  color: #fff;
}
.card {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.prod {
  display: flex;
  gap: 10px;
  align-items: center;
}
.thumb {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  background: #e8f3ff;
  color: #1677ff;
  flex-shrink: 0;
}
.thumb.digital {
  background: #fff7e6;
  color: #d48806;
}
.thumb.service {
  background: #ecfdf5;
  color: #059669;
}
.prod-info {
  flex: 1;
  min-width: 0;
}
.pname {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.tag {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
  color: #1677ff;
  background: #e8f3ff;
  padding: 1px 6px;
  border-radius: 4px;
}
.amt-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 10px;
}
.amt {
  color: #ef4444;
  font-size: 18px;
  font-weight: 700;
}
.row {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
}
.link {
  color: #1677ff;
}
.muted {
  color: #64748b;
  font-size: 12px;
}
.ch {
  display: block;
  margin-top: 4px;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
.btn {
  margin: 0;
  border: none;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 600;
  background: #f1f5f9;
  color: #334155;
}
.btn.block {
  width: 100%;
  padding: 12px;
}
.btn.primary {
  background: #1677ff;
  color: #fff;
}
.btn.danger {
  background: #fff1f0;
  color: #cf1322;
}
.sec {
  display: block;
  font-weight: 600;
  margin-bottom: 8px;
}
.tl-item {
  display: flex;
  gap: 10px;
  font-size: 12px;
  padding: 6px 0;
  border-bottom: 1px solid #f1f5f9;
}
.tl-item .t {
  color: #94a3b8;
  min-width: 110px;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
  z-index: 100;
}
.sheet {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  padding: 16px;
  max-height: 85vh;
  overflow-y: auto;
}
.sheet-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.sheet-t {
  font-size: 16px;
  font-weight: 700;
}
.warn {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 12px;
}
.warn-t {
  display: block;
  font-weight: 600;
  color: #d48806;
  margin-bottom: 4px;
  font-size: 13px;
}
.warn-b,
.warn-h {
  display: block;
  font-size: 12px;
  color: #595959;
  line-height: 1.5;
}
.warn-h {
  margin-top: 6px;
  color: #8c8c8c;
}
.field {
  margin-bottom: 12px;
}
.lab {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.val {
  font-size: 14px;
  color: #0f172a;
}
.danger-bg {
  display: block;
  background: #fff5f5;
  padding: 10px;
  border-radius: 8px;
  color: #cf1322;
  font-size: 13px;
}
.picker {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  color: #0f172a;
}
.area {
  width: 100%;
  min-height: 72px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  box-sizing: border-box;
  font-size: 14px;
}
.sheet-ft {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.progress .p-item {
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}
.p-at {
  display: block;
  font-size: 11px;
  color: #94a3b8;
}
.p-tx {
  display: block;
  font-size: 13px;
  margin-top: 2px;
}
.p-item.muted .p-tx {
  color: #94a3b8;
}
.tip {
  display: block;
  margin-top: 10px;
}
</style>
