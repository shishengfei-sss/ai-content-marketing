<script setup>
/**
 * 买家详情（只读五 Tab）。对照 PRD 01-管理端UI.html #a11a
 * 订单 #a11a-orders · 权益 #a11a-entitlements · 预约 #a11a-bookings
 * 开票 #a11a-invoices · 学习进度 #a11a-progress
 * 封禁顶栏 Phase1 无落库，恒「正常」。
 */
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View } from '@element-plus/icons-vue'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'

const route = useRoute()
const router = useRouter()
const { stores, loadStores } = useCurrentShop()
const loading = ref(false)
const buyer = ref(null)
const revealed = ref('')
const tab = ref('orders')
const filterShopId = ref('')
const orders = ref([])
const entitlements = ref([])
const bookings = ref([])
const invoices = ref([])
const learning = ref([])

const STATUS_ORDER = {
  pending_payment: '待付款',
  paid: '已付款',
  claim_pending: '待领权',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
}
const STATUS_ENT = {
  pending: '待生效',
  active: '生效中',
  revoked: '已撤销',
  expired: '已过期',
  consumed: '已用尽',
}
const STATUS_INV = { submitted: '待处理', pending: '待处理', issued: '已开票', rejected: '已驳回' }
const TYPE_LABEL = { course: '课程', digital: '资料', service: '服务' }
const TITLE_TYPE = { person: '个人', company: '企业' }

function fmtMoney(c) {
  return `¥${((c || 0) / 100).toFixed(2)}`
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function fmtDate(v) {
  if (!v) return '—'
  return String(v).slice(0, 10)
}
function shopParams() {
  return { shop_id: filterShopId.value || undefined }
}
function entStatus(row) {
  if (row.status === 'active' && row.remaining_count === 0 && row.total_count != null) {
    return STATUS_ENT.consumed
  }
  return STATUS_ENT[row.status] || row.status
}
function learnEmpty(row) {
  return ['revoked', 'expired'].includes(row.entitlement_status) && !row.last_learned_at && !row.last_lesson_title
}

async function loadBuyer() {
  const { data } = await api.get(`/api/v1/shop/buyers/${route.params.id}`)
  buyer.value = data
}

async function loadTab() {
  const id = route.params.id
  const extra = { buyer_id: id, page_size: 50, ...shopParams() }
  if (tab.value === 'orders') {
    const { data } = await api.get('/api/v1/shop/orders', { params: extra })
    orders.value = data.items || []
  } else if (tab.value === 'ents') {
    const { data } = await api.get('/api/v1/shop/entitlements', { params: extra })
    entitlements.value = data.items || []
  } else if (tab.value === 'bookings') {
    const { data } = await api.get('/api/v1/shop/bookings', { params: extra })
    bookings.value = data.items || []
  } else if (tab.value === 'invoices') {
    const { data } = await api.get('/api/v1/shop/invoices', { params: extra })
    invoices.value = data.items || []
  } else if (tab.value === 'learning') {
    const { data } = await api.get(`/api/v1/shop/buyers/${id}/learning-progress`, {
      params: shopParams(),
    })
    learning.value = data.items || []
  }
}

async function load() {
  loading.value = true
  try {
    await loadBuyer()
    await loadTab()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function reveal() {
  try {
    const { data } = await api.post(`/api/v1/shop/buyers/${route.params.id}/reveal-sensitive`)
    revealed.value = data.mobile || ''
  } catch (e) {
    ElMessage.error(e.message || '无查看权限')
  }
}

watch(tab, () => loadTab())
watch(filterShopId, () => loadTab())
onMounted(async () => {
  await loadStores()
  await load()
})
</script>

<template>
  <div v-loading="loading" data-testid="shop-buyer-detail">
    <el-button link type="primary" @click="router.push({ name: 'ShopBuyers' })">← 买家列表</el-button>
    <div v-if="buyer" class="head">
      <h3>
        {{ buyer.nickname || '买家' }}
        <span class="badge ok">正常</span>
      </h3>
      <div class="meta">
        <span class="mobile">
          {{ revealed || buyer.mobile_masked || '—' }}
          <el-button
            v-if="buyer.mobile_masked && !revealed"
            link
            type="primary"
            :icon="View"
            @click="reveal"
          />
        </span>
        · 注册 {{ fmtTime(buyer.created_at) }}
      </div>
      <div class="meta">
        订单 {{ buyer.order_count }} · 权益 {{ buyer.entitlement_count }} · 最近下单
        {{ fmtTime(buyer.last_order_at) }} · 来源店铺：{{ buyer.source_shop_name || '—' }}
      </div>
    </div>

    <div class="filter-row">
      <el-select v-model="filterShopId" clearable placeholder="来源店铺" style="width: 200px">
        <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <span class="hint">订单 Tab 可按店铺筛选；其余 Tab 同步当前筛选</span>
    </div>

    <el-tabs v-model="tab">
      <el-tab-pane label="订单" name="orders">
        <el-table :data="orders" border size="small">
          <el-table-column label="单号" min-width="160">
            <template #default="{ row }">
              <el-button link type="primary" @click="router.push({ name: 'ShopOrderDetail', params: { id: row.id } })">
                {{ row.order_no }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="product_name" label="商品" min-width="120" />
          <el-table-column prop="shop_name" label="店铺" width="120">
            <template #default="{ row }">{{ row.shop_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="channel" label="渠道" width="80" />
          <el-table-column label="金额" width="90">
            <template #default="{ row }">{{ fmtMoney(row.amount_cents) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ STATUS_ORDER[row.status] || row.status }}</template>
          </el-table-column>
          <el-table-column label="下单时间" min-width="140">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="router.push({ name: 'ShopOrderDetail', params: { id: row.id } })">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <p class="note">只读：无退款/关单等写操作；单号可进入订单详情。</p>
      </el-tab-pane>
      <el-tab-pane label="权益" name="ents">
        <el-table :data="entitlements" border size="small">
          <el-table-column prop="product_name" label="商品" min-width="120" />
          <el-table-column label="类型" width="80">
            <template #default="{ row }">{{ TYPE_LABEL[row.product_type] || row.product_type }}</template>
          </el-table-column>
          <el-table-column label="店铺" width="120">
            <template #default="{ row }">{{ row.shop_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ entStatus(row) }}</template>
          </el-table-column>
          <el-table-column label="次数" width="90">
            <template #default="{ row }">
              {{ row.remaining_count != null ? `${row.remaining_count}/${row.total_count ?? '—'}` : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="来源订单" min-width="140">
            <template #default="{ row }">
              <el-button
                v-if="row.order_id"
                link
                type="primary"
                @click="router.push({ name: 'ShopOrderDetail', params: { id: row.order_id } })"
              >
                {{ row.order_no }}
              </el-button>
              <span v-else>{{ row.order_no || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="开通时间" min-width="140">
            <template #default="{ row }">{{ fmtTime(row.activated_at) }}</template>
          </el-table-column>
          <el-table-column label="到期" min-width="110">
            <template #default="{ row }">{{ fmtDate(row.expires_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status !== 'revoked'"
                link
                type="primary"
                @click="router.push({ name: 'ShopEntitlements', query: { id: row.id } })"
              >
                详情
              </el-button>
              <span v-else class="muted">只读</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="预约" name="bookings">
        <el-table :data="bookings" border size="small">
          <el-table-column label="预约号" width="120">
            <template #default="{ row }">{{ row.booking_no || '—' }}</template>
          </el-table-column>
          <el-table-column prop="product_name" label="服务" min-width="120" />
          <el-table-column prop="shop_name" label="店铺" width="120" />
          <el-table-column label="时段" min-width="160">
            <template #default="{ row }">{{ row.booked_date }} {{ row.booked_time_slot }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              {{ { booked: '待服务', completed: '已完成', cancelled: '已取消' }[row.status] || row.status }}
            </template>
          </el-table-column>
          <el-table-column label="核销码" width="100">
            <template #default="{ row }">{{ row.verify_code || '—' }}</template>
          </el-table-column>
          <el-table-column label="来源订单" min-width="140">
            <template #default="{ row }">
              <el-button
                v-if="row.order_id"
                link
                type="primary"
                @click="router.push({ name: 'ShopOrderDetail', params: { id: row.order_id } })"
              >
                {{ row.order_no }}
              </el-button>
              <span v-else>{{ row.order_no || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="140">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button
                v-if="row.offer_id && row.status === 'booked'"
                link
                type="primary"
                @click="router.push({ name: 'ShopServiceOfferEdit', params: { id: row.offer_id } })"
              >
                查看名单
              </el-button>
              <span v-else class="muted">只读</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="开票" name="invoices">
        <el-table :data="invoices" border size="small">
          <el-table-column label="申请单" width="120">
            <template #default="{ row }">{{ row.application_no || '—' }}</template>
          </el-table-column>
          <el-table-column label="订单" min-width="140">
            <template #default="{ row }">
              <el-button
                v-if="row.order_id"
                link
                type="primary"
                @click="router.push({ name: 'ShopOrderDetail', params: { id: row.order_id } })"
              >
                {{ row.order_no }}
              </el-button>
              <span v-else>{{ row.order_no || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="抬头" min-width="120" />
          <el-table-column label="类型" width="80">
            <template #default="{ row }">{{ TITLE_TYPE[row.title_type] || row.title_type }}</template>
          </el-table-column>
          <el-table-column label="税号" min-width="140">
            <template #default="{ row }">{{ row.tax_no || '—' }}</template>
          </el-table-column>
          <el-table-column label="金额" width="90">
            <template #default="{ row }">{{ fmtMoney(row.amount_cents) }}</template>
          </el-table-column>
          <el-table-column label="申请时间" min-width="140">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ STATUS_INV[row.status] || row.status }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="router.push({ name: 'ShopInvoices', query: { id: row.id } })">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="学习进度" name="learning">
        <el-table :data="learning" border size="small">
          <el-table-column prop="product_name" label="专栏" min-width="140" />
          <el-table-column prop="shop_name" label="店铺" width="120" />
          <el-table-column label="权益状态" width="90">
            <template #default="{ row }">{{ STATUS_ENT[row.entitlement_status] || row.entitlement_status }}</template>
          </el-table-column>
          <el-table-column label="进度" width="80">
            <template #default="{ row }">{{ learnEmpty(row) ? '—' : `${row.progress_pct}%` }}</template>
          </el-table-column>
          <el-table-column label="已学/总讲" width="100">
            <template #default="{ row }">
              {{ learnEmpty(row) ? '—' : `${row.learned_count}/${row.total_lessons}` }}
            </template>
          </el-table-column>
          <el-table-column label="最近学习" min-width="140">
            <template #default="{ row }">{{ learnEmpty(row) ? '—' : fmtTime(row.last_learned_at) }}</template>
          </el-table-column>
          <el-table-column label="最近课时" min-width="140">
            <template #default="{ row }">{{ learnEmpty(row) ? '—' : (row.last_lesson_title || '—') }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default>只读</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.head { margin: 12px 0 16px; }
.head h3 { margin: 0 0 6px; display: flex; align-items: center; gap: 8px; }
.meta { font-size: 13px; color: #64748b; line-height: 1.6; }
.mobile { display: inline-flex; align-items: center; gap: 4px; color: #334155; }
.badge {
  font-size: 12px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 4px;
}
.badge.ok { background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }
.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.hint { font-size: 11px; color: #64748b; }
.note { font-size: 12px; color: #64748b; margin-top: 8px; }
.muted { color: #94a3b8; font-size: 12px; }
</style>
