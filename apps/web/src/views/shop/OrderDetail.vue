<script setup>
/**
 * A10 订单详情。对照 PRD 01-管理端UI.html #a10
 * 顶栏随状态显隐；写操作弹窗复用 A09-A/B/C（OrderActionDialogs）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import api from '../../api/client'
import OrderActionDialogs from '../../components/shop/OrderActionDialogs.vue'

const route = useRoute()
const router = useRouter()
const actionDialogs = ref(null)
const loading = ref(false)
const order = ref(null)
const revealedMobile = ref('')
let revealTimer = null

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
  active: '生效中',
  expired: '已过期',
  revoked: '已撤销',
}
const INVOICE_LABEL = {
  none: '未申请',
  pending: '待开票',
  issued: '已开票',
  rejected: '已驳回',
}
const TYPE_LABEL = { course: '课程', digital: '资料', service: '服务' }
const CLAIM_LABEL = { claimed: '已领取', pending: '待领取' }

const statusLabel = computed(() => STATUS_LABEL[order.value?.status] || order.value?.status || '—')
const entLabel = computed(() => {
  if (!order.value?.entitlement_status) {
    if (order.value?.status === 'claim_pending') return '待领权'
    if (order.value?.status === 'pending_payment') return '—'
    return '无'
  }
  return ENT_LABEL[order.value.entitlement_status] || order.value.entitlement_status
})
const invoiceLabel = computed(
  () => INVOICE_LABEL[order.value?.invoice_status] || order.value?.invoice_status || '未申请'
)
const payChannel = computed(() => order.value?.channel || '—')

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function fmtDate(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 10)
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/api/v1/shop/orders/${route.params.id}`)
    order.value = data
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function revealMobile() {
  try {
    const { data } = await api.post(`/api/v1/shop/orders/${route.params.id}/reveal-sensitive`)
    revealedMobile.value = data.buyer_mobile || ''
    if (revealTimer) clearTimeout(revealTimer)
    revealTimer = setTimeout(() => {
      revealedMobile.value = ''
    }, 5 * 60 * 1000)
  } catch (e) {
    ElMessage.error(e.message || '无查看权限')
  }
}

function closeOrder() {
  if (!order.value) return
  actionDialogs.value?.openClose(order.value)
}

function refund() {
  if (!order.value) return
  actionDialogs.value?.openRefund(order.value)
}

function resendNotify() {
  if (!order.value) return
  actionDialogs.value?.openResend(order.value)
}

function goInvoices() {
  if (!order.value) return
  if (order.value.invoice_status === 'none') {
    ElMessage.warning('暂无开票记录')
    return
  }
  router.push({ name: 'ShopInvoices', query: { q: order.value.order_no } })
}

function goProduct() {
  if (!order.value?.product_id) return
  router.push({
    name: 'ShopProductEdit',
    params: { id: order.value.product_id },
    query: { mode: 'view' },
  })
}

onMounted(load)
onUnmounted(() => {
  if (revealTimer) clearTimeout(revealTimer)
})
</script>

<template>
  <div v-loading="loading" class="a10">
    <div class="hd">
      <div class="hd-left">
        <el-button link type="primary" @click="router.push({ name: 'ShopOrders' })">‹ 订单列表</el-button>
        <h3 class="order-no">{{ order?.order_no || '—' }}</h3>
        <el-tag size="small">{{ statusLabel }}</el-tag>
      </div>
      <div class="hd-actions">
        <el-button v-if="order?.status === 'pending_payment'" type="warning" @click="closeOrder">
          关闭订单
        </el-button>
        <template v-if="order?.status === 'paid'">
          <el-button @click="goInvoices">查看开票</el-button>
          <el-button type="danger" @click="refund">退款</el-button>
        </template>
        <el-button v-if="order?.status === 'claim_pending'" type="primary" @click="resendNotify">
          重发短信
        </el-button>
      </div>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="v c-ok">{{ statusLabel }}</div>
        <div class="l">订单状态</div>
      </div>
      <div class="stat">
        <div class="v c-link">{{ entLabel }}</div>
        <div class="l">权益状态</div>
      </div>
      <div class="stat">
        <div class="v c-warn">{{ invoiceLabel }}</div>
        <div class="l">开票状态</div>
      </div>
      <div class="stat">
        <div class="v c-channel">{{ payChannel }}</div>
        <div class="l">支付渠道</div>
      </div>
    </div>

    <div class="grid">
      <el-card shadow="never" class="card">
        <div class="card-h">商品信息</div>
        <div class="product" @click="goProduct">
          <div class="thumb">{{ TYPE_LABEL[order?.type] || order?.type || '商品' }}</div>
          <div class="info">
            <div class="name">{{ order?.product_name || '—' }}</div>
            <div class="price">{{ fmtMoney(order?.amount_cents) }}</div>
            <div class="go">点击查看商品详情 →</div>
          </div>
          <el-button type="primary" size="small" @click.stop="goProduct">查看详情</el-button>
        </div>
        <div class="card-h">订单信息</div>
        <div class="row"><span class="k">实付金额</span><span class="v">{{ fmtMoney(order?.paid_amount_cents ?? order?.amount_cents) }}</span></div>
        <div class="row"><span class="k">下单时间</span><span class="v">{{ fmtTime(order?.created_at) }}</span></div>
        <div class="row"><span class="k">支付时间</span><span class="v">{{ fmtTime(order?.paid_at) }}</span></div>
        <div class="row"><span class="k">外部单号</span><span class="v muted">{{ order?.external_order_no || '—' }}</span></div>
        <div v-if="order?.refund_reason" class="row">
          <span class="k">退款/关闭原因</span><span class="v">{{ order.refund_reason }}</span>
        </div>
      </el-card>

      <el-card shadow="never" class="card">
        <div class="card-h">买家与领权</div>
        <div class="row">
          <span class="k">买家昵称</span>
          <span class="v">
            <el-button
              v-if="order?.buyer_id"
              link
              type="primary"
              @click="router.push({ name: 'ShopBuyerDetail', params: { id: order.buyer_id } })"
            >
              {{ order?.buyer_nickname || '买家' }}
            </el-button>
            <span v-else>—</span>
          </span>
        </div>
        <div class="row">
          <span class="k">买家手机</span>
          <span class="v mobile">
            {{ revealedMobile || order?.buyer_mobile_masked || '—' }}
            <el-button
              v-if="order?.buyer_mobile_masked && !revealedMobile"
              link
              type="primary"
              :icon="View"
              title="查看完整手机号"
              @click="revealMobile"
            />
          </span>
        </div>
        <div class="row">
          <span class="k">领权状态</span>
          <span class="v">
            <el-tag v-if="order?.claim_status" size="small">
              {{ CLAIM_LABEL[order.claim_status] || order.claim_status }}
            </el-tag>
            <span v-else>—</span>
          </span>
        </div>
        <div class="row">
          <span class="k">权益</span>
          <span class="v">
            <el-button
              v-if="order?.entitlement_id"
              link
              type="primary"
              class="mono"
              @click="router.push({ name: 'ShopEntitlements', query: { id: order.entitlement_id } })"
            >
              {{ String(order.entitlement_id).slice(0, 8) }}…
            </el-button>
            <span v-else>—</span>
          </span>
        </div>
        <div class="row">
          <span class="k">权益到期</span>
          <span class="v">{{ fmtDate(order?.entitlement_expires_at) }}</span>
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="card timeline-card">
      <div class="card-h">订单轨迹</div>
      <el-timeline v-if="order?.timeline?.length">
        <el-timeline-item
          v-for="(t, i) in order.timeline"
          :key="i"
          :timestamp="fmtTime(t.at)"
          placement="top"
        >
          {{ t.event }}
        </el-timeline-item>
      </el-timeline>
      <div v-else class="muted">暂无轨迹</div>
    </el-card>

    <OrderActionDialogs ref="actionDialogs" @done="load" />
  </div>
</template>

<style scoped>
.hd {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 16px;
}
.hd-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.order-no { margin: 0; font-size: 18px; font-weight: 600; }
.hd-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px;
}
@media (max-width: 900px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}
.stat {
  background: #fff; border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px; padding: 12px 14px;
}
.stat .v { font-size: 15px; font-weight: 600; }
.stat .l { margin-top: 4px; font-size: 12px; color: #64748b; }
.c-ok { color: #389e0d; }
.c-link { color: #1677ff; }
.c-warn { color: #d46b08; }
.c-channel { color: #334155; }
.grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}
.card { margin-bottom: 0; }
.card-h {
  font-weight: 600; margin: 8px 0 10px; font-size: 14px; color: #334155;
}
.product {
  display: flex; align-items: center; gap: 12px; padding: 10px;
  border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  cursor: pointer; margin-bottom: 8px;
}
.thumb {
  width: 56px; height: 56px; border-radius: 8px; background: #f1f5f9;
  display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;
}
.info { flex: 1; min-width: 0; }
.info .name { font-weight: 600; }
.info .price { color: #cf1322; margin-top: 2px; }
.info .go { font-size: 12px; color: #1677ff; margin-top: 4px; }
.row {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px;
}
.row .k { color: #64748b; }
.row .v { font-weight: 500; text-align: right; }
.row .v.muted, .muted { color: #64748b; font-weight: 400; }
.mobile { display: inline-flex; align-items: center; gap: 4px; }
.mono { font-family: ui-monospace, monospace; font-weight: 400; }
.timeline-card { margin-top: 12px; }
</style>
