<script setup>
/**
 * 权益列表 + 详情抽屉。对照 PRD 01-管理端UI.html #a12 / #a12a / #a12-select-spec
 * 默认列：买家·商品·类型·状态·次数·订单·开通时间·到期时间·操作
 * 列设置可选：店铺
 * 只读：无手工改状态；退款自动撤销。
 * 缺口：站内信/短信本批不接（导出在页内下载，不发站内通知）。线框顶栏未画导出 ▾，本页按列表完备性保留导出。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { submitShopExport, SHOP_EXPORT_SCOPE_LABELS } from '../../utils/shopExport'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../composables/useListColumnSettings'
import { useCurrentShop } from '../../composables/useCurrentShop'

const route = useRoute()
const router = useRouter()
const { currentId } = useCurrentShop()
const loading = ref(false)
const exporting = ref(false)
const advOpen = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const drawer = ref(false)
const detail = ref(null)
const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  product_type: '',
  activated_from: '',
  activated_to: '',
  expires_from: '',
  expires_to: '',
})

const COL_STORAGE = 'shop.a12.columns'
const ALL_COLS = [
  { key: 'buyer', label: '买家', locked: true, defaultOn: true },
  { key: 'product_name', label: '商品', defaultOn: true },
  { key: 'product_type', label: '类型', defaultOn: true },
  { key: 'status', label: '状态', defaultOn: true },
  { key: 'times', label: '次数', defaultOn: true },
  { key: 'order_no', label: '订单', defaultOn: true },
  { key: 'activated_at', label: '开通时间', defaultOn: true },
  { key: 'expires_at', label: '到期时间', defaultOn: true },
  { key: 'shop_name', label: '店铺', defaultOn: false },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys,
  columnDialogVisible: colDialog,
  columnDraft,
  openColumnSettings,
  saveColumnSettings,
  isColVisible,
} = useListColumnSettings(ALL_COLS, COL_STORAGE)

const STATUS_LABEL = {
  pending: '待生效',
  active: '生效中',
  revoked: '已撤销',
  expired: '已过期',
  consumed: '已用尽',
}
const TYPE_LABEL = { course: '课程', digital: '资料', service: '服务' }
const TABS = [
  { key: '', label: '全部权益' },
  { key: 'pending', label: '待生效' },
  { key: 'active', label: '生效中' },
  { key: 'consumed', label: '已用尽' },
  { key: 'revoked', label: '已撤销' },
  { key: 'expired', label: '已过期' },
]

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}
function buyerLabel(row) {
  const nick = (row.buyer_nickname || '').trim()
  const mobile = (row.buyer_mobile_masked || '').trim()
  if (nick && mobile) return `${nick} ${mobile}`
  return nick || mobile || '—'
}
function timesText(row) {
  if (row.remaining_count == null) return '—'
  return `${row.remaining_count}/${row.total_count ?? '—'}`
}
function statusText(row) {
  if (row.status === 'consumed') return STATUS_LABEL.consumed
  if (row.remaining_count === 0 && row.status !== 'revoked' && row.remaining_count != null) {
    return STATUS_LABEL.consumed
  }
  return STATUS_LABEL[row.status] || row.status
}
function detailHint(d) {
  if (!d) return ''
  if (d.status === 'pending') return '待支付或待领权后生效，不可核销/学习'
  if (d.status === 'revoked') return d.revoke_reason || '已随退款撤销'
  if (d.status === 'consumed' || (d.remaining_count === 0 && d.status !== 'revoked' && d.remaining_count != null)) {
    return '次数已用尽'
  }
  if (d.status === 'expired') return '已过期，不可使用'
  if (d.status === 'active' && d.remaining_count === 0) return '次数已用尽'
  return '生效中，可履约'
}

function listParams(extra = {}) {
  return {
    status: query.status || undefined,
    q: query.q || undefined,
    product_type: query.product_type || undefined,
    shop_id: currentId.value || undefined,
    activated_from: query.activated_from || undefined,
    activated_to: query.activated_to || undefined,
    expires_from: query.expires_from || undefined,
    expires_to: query.expires_to || undefined,
    ...extra,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/entitlements', {
      params: listParams({ page: query.page, page_size: query.page_size }),
    })
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function selectTab(key) {
  query.status = key
  query.page = 1
  load()
}

function resetAdv() {
  query.activated_from = ''
  query.activated_to = ''
  query.expires_from = ''
  query.expires_to = ''
  query.page = 1
  load()
}

async function openDetail(row) {
  try {
    const { data } = await api.get(`/api/v1/shop/entitlements/${row.id}`)
    detail.value = data
    drawer.value = true
  } catch (e) {
    ElMessage.error(e.message || '无权益查看权限')
  }
}

async function exportCsv() {
  exporting.value = true
  try {
    await submitShopExport(
      '/api/v1/shop/entitlements/export',
      listParams(),
      '/api/v1/shop/entitlements/export-tasks',
      'shop-entitlements.csv',
      total.value,
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}


function goOrder(orderId) {
  if (!orderId) return
  drawer.value = false
  router.push({ name: 'ShopOrderDetail', params: { id: orderId } })
}

watch(currentId, () => {
  query.page = 1
  load()
})

watch(
  () => route.query.id,
  async (id) => {
    if (id) await openDetail({ id })
  }
)

onMounted(async () => {
  await load()
  if (route.query.id) await openDetail({ id: route.query.id })
})
</script>

<template>
  <div v-loading="loading" data-testid="shop-entitlements">
    <div class="tabs">
      <button
        v-for="t in TABS"
        :key="t.key || 'all'"
        type="button"
        class="tab"
        :class="{ on: query.status === t.key }"
        @click="selectTab(t.key)"
      >
        {{ t.label }}
        <span class="cnt">{{ tabCount(t.key === '' ? 'all' : t.key) }}</span>
      </button>
    </div>
    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="手机 / 订单号"
          style="width: 200px"
          @keyup.enter="() => { query.page = 1; load() }"
        />
        <el-select
          v-model="query.product_type"
          clearable
          placeholder="类型"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="课程" value="course" />
          <el-option label="资料" value="digital" />
          <el-option label="服务" value="service" />
        </el-select>
        <el-select
          v-model="query.status"
          clearable
          placeholder="状态"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="待生效" value="pending" />
          <el-option label="生效中" value="active" />
          <el-option label="已用尽" value="consumed" />
          <el-option label="已撤销" value="revoked" />
          <el-option label="已过期" value="expired" />
        </el-select>
        <el-button :type="advOpen ? 'primary' : 'default'" plain @click="advOpen = !advOpen">
          高级筛选
        </el-button>
      </div>
      <div class="right">
        <el-dropdown trigger="click" @command="(cmd) => cmd === 'current' && exportCsv()">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">{{ SHOP_EXPORT_SCOPE_LABELS.filtered }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnSettings">列设置</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-date-picker
          v-model="query.activated_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="开通起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.activated_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="开通止"
          style="width: 140px"
        />
        <el-date-picker
          v-model="query.expires_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="到期起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.expires_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="到期止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 覆盖待生效/生效中/已用尽/已撤销/已过期</span>
      </div>
    </div>

    <el-table :data="items" border stripe size="small" style="margin-top: 12px">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column v-if="colKey === 'buyer'" label="买家" min-width="160">
        <template #default="{ row }">
          {{ buyerLabel(row) }}
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'product_name'" prop="product_name" label="商品" min-width="140" />
      <el-table-column v-if="colKey === 'product_type'" label="类型" width="80">
        <template #default="{ row }">{{ TYPE_LABEL[row.product_type] || row.product_type }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'status'" label="状态" width="90">
        <template #default="{ row }">{{ statusText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'times'" label="次数" width="90">
        <template #default="{ row }">{{ timesText(row) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'order_no'" label="订单" min-width="150">
        <template #default="{ row }">
          <el-button
            v-if="row.order_id"
            link
            type="primary"
            @click="goOrder(row.order_id)"
          >
            {{ row.order_no }}
          </el-button>
          <span v-else>{{ row.order_no || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'activated_at'" label="开通时间" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.activated_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'expires_at'" label="到期时间" min-width="140">
        <template #default="{ row }">{{ fmtTime(row.expires_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'shop_name'" label="店铺" min-width="120">
        <template #default="{ row }">{{ row.shop_name || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'ops'" label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
      </template>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="load"
      />
    </div>

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="columnDraft"
      @save="() => { saveColumnSettings(); ElMessage.success('列设置已保存') }"
    />


    <el-drawer v-model="drawer" title="权益详情" size="420px">
      <template v-if="detail">
        <h3 style="margin-top: 0">
          {{ detail.product_name || '权益' }}
          <el-tag size="small" style="margin-left: 8px">{{ statusText(detail) }}</el-tag>
        </h3>
        <p>买家：{{ buyerLabel(detail) }}</p>
        <p>
          订单：
          <el-button
            v-if="detail.order_id"
            link
            type="primary"
            @click="goOrder(detail.order_id)"
          >
            {{ detail.order_no }}
          </el-button>
          <span v-else>{{ detail.order_no || '—' }}</span>
        </p>
        <p>剩余次数：{{ timesText(detail) }}</p>
        <p>到期：{{ fmtTime(detail.expires_at) }}</p>
        <p>开通：{{ fmtTime(detail.activated_at) }}</p>
        <p v-if="detail.status === 'pending'">生效起：{{ fmtTime(detail.activated_at) }}</p>
        <p v-if="detail.status === 'revoked'">撤销原因：{{ detail.revoke_reason || '订单退款' }}</p>
        <p v-if="detail.shop_name">店铺：{{ detail.shop_name }}</p>
        <p class="hint">{{ detailHint(detail) }}</p>
        <div class="drawer-foot">
          <el-button @click="drawer = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--el-border-color);
  margin-bottom: 12px;
}
.tab {
  border: 0;
  background: transparent;
  padding: 8px 14px;
  cursor: pointer;
  color: #666;
  font-size: 13px;
}
.tab.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom: 2px solid #1677ff;
}
.cnt {
  margin-left: 4px;
  font-size: 12px;
  color: #999;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
}
.left,
.right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.adv {
  margin-top: 10px;
  border: 1px solid #91caff;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f0f7ff;
  font-size: 12px;
}
.adv-t {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.adv-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.sep {
  color: #999;
}
.hint {
  color: #64748b;
  font-size: 12px;
  margin-top: 8px;
}
.drawer-foot {
  text-align: right;
  margin-top: 16px;
}
</style>
