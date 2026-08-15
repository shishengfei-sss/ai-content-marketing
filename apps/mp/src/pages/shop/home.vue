<script setup>
/**
 * M02 店首页。对照 PRD 02-买家端UI.html #m02
 */
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom, onShow } from '@dcloudio/uni-app'
import {
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  setShopBuyerTenantId,
  shopBuyerApi,
} from '@/utils/shopApi'

const shopId = ref('')
const tenantId = ref('')
const openidHint = ref('')
const loading = ref(false)
const loadingMore = ref(false)
const store = ref(null)
const products = ref([])
const keyword = ref('')
const typeFilter = ref('')
const sort = ref('default')
const page = ref(1)
const hasMore = ref(false)
const error = ref('')
const PAGE_SIZE = 20

const TYPE_TABS = [
  { key: '', label: '全部' },
  { key: 'course', label: '课程' },
  { key: 'digital', label: '资料' },
  { key: 'service', label: '服务' },
]

const SORT_TABS = [
  { key: 'default', label: '综合' },
  { key: 'price_asc', label: '价格升序' },
  { key: 'price_desc', label: '价格降序' },
  { key: 'sales', label: '销量' },
]

const shopName = computed(() => store.value?.name || '店铺')

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function typeLabel(t) {
  return { course: '课程', digital: '资料', service: '服务' }[t] || t
}

async function fetchPage(nextPage, { append }) {
  const data = await shopBuyerApi.getStore({
    shop_id: shopId.value,
    q: keyword.value.trim() || undefined,
    type: typeFilter.value || undefined,
    sort: sort.value,
    page: nextPage,
    page_size: PAGE_SIZE,
  })
  store.value = data.shop
  const rows = data.products || []
  products.value = append ? products.value.concat(rows) : rows
  page.value = nextPage
  hasMore.value = !!data.has_more
  return data
}

async function load() {
  if (!shopId.value) {
    error.value = '缺少店铺标识'
    return
  }
  loading.value = true
  error.value = ''
  try {
    if (tenantId.value) {
      setShopBuyerTenantId(tenantId.value)
      try {
        await ensureShopBuyerSession(tenantId.value, openidHint.value || undefined)
      } catch {
        /* 浏览可不登录 */
      }
    }
    await fetchPage(1, { append: false })
  } catch (e) {
    error.value = e.message || '加载失败'
    products.value = []
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || loading.value || loadingMore.value) return
  loadingMore.value = true
  try {
    await fetchPage(page.value + 1, { append: true })
  } catch {
    uni.showToast({ title: '加载失败，请重试', icon: 'none' })
  } finally {
    loadingMore.value = false
  }
}

function selectType(key) {
  typeFilter.value = key
  load()
}

function selectSort(key) {
  sort.value = key
  load()
}

function onSearch() {
  load()
}

function goProduct(row) {
  if (row.status && row.status !== 'on_sale') {
    uni.showToast({ title: '商品已下架', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/pages/shop/product?id=${row.id}&tenant_id=${tenantId.value || getShopBuyerTenantId()}`,
  })
}

function goEntitlements() {
  const tid = tenantId.value || getShopBuyerTenantId()
  uni.navigateTo({
    url: `/pages/shop/entitlements?tenant_id=${tid}${openidHint.value ? `&openid=${openidHint.value}` : ''}`,
  })
}

function goOrders() {
  const tid = tenantId.value || getShopBuyerTenantId()
  uni.navigateTo({ url: `/pages/shop/orders?tenant_id=${tid}` })
}

onLoad((q) => {
  shopId.value = (q?.shop_id || '').trim()
  tenantId.value = (q?.tenant_id || '').trim()
  openidHint.value = (q?.openid || '').trim()
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
})

onShow(() => {
  load()
})

onPullDownRefresh(async () => {
  try {
    await load()
  } catch {
    uni.showToast({ title: '刷新失败，请重试', icon: 'none' })
  } finally {
    uni.stopPullDownRefresh()
  }
})

onReachBottom(() => {
  loadMore()
})
</script>

<template>
  <view class="page">
    <view v-if="store" class="hero">
      <view class="hero-name">{{ shopName }}</view>
      <view v-if="store.intro" class="hero-intro">{{ store.intro }}</view>
    </view>

    <view class="search-bar">
      <input
        v-model="keyword"
        class="search-input"
        placeholder="搜索商品"
        confirm-type="search"
        @confirm="onSearch"
      />
      <button class="search-btn" size="mini" @click="onSearch">搜索</button>
    </view>

    <scroll-view scroll-x class="type-tabs">
      <view
        v-for="tab in TYPE_TABS"
        :key="tab.key"
        class="type-tab"
        :class="{ active: typeFilter === tab.key }"
        @click="selectType(tab.key)"
      >
        {{ tab.label }}
      </view>
    </scroll-view>

    <scroll-view scroll-x class="sort-tabs">
      <view
        v-for="tab in SORT_TABS"
        :key="tab.key"
        class="sort-tab"
        :class="{ active: sort === tab.key }"
        @click="selectSort(tab.key)"
      >
        {{ tab.label }}
      </view>
    </scroll-view>

    <view v-if="loading && !products.length" class="hint">加载中…</view>
    <view v-else-if="error" class="error">{{ error }}</view>
    <view v-else-if="!products.length" class="empty">
      <view class="empty-title">暂无在售内容</view>
      <view class="empty-sub">店铺正在筹备，稍后再来看看</view>
      <button class="search-btn" size="mini" @click="load">刷新看看</button>
    </view>

    <view class="product-list">
      <view
        v-for="row in products"
        :key="row.id"
        class="product-card"
        :class="{ gray: row.status && row.status !== 'on_sale' }"
        @click="goProduct(row)"
      >
        <view class="cover">
          <image v-if="row.cover_url" :src="row.cover_url" mode="aspectFill" class="cover-img" />
          <view v-else class="cover-placeholder">{{ typeLabel(row.type) }}</view>
        </view>
        <view class="info">
          <view class="name">{{ row.name }}</view>
          <view v-if="row.subtitle" class="subtitle">{{ row.subtitle }}</view>
          <view class="meta">已售 {{ row.sales_count || 0 }}</view>
          <view class="price-row">
            <text class="price">{{ fmtMoney(row.price_cents) }}</text>
            <text v-if="row.line_price_cents" class="line-price">{{ fmtMoney(row.line_price_cents) }}</text>
          </view>
        </view>
      </view>
    </view>
    <view v-if="products.length && hasMore" class="more" @click="loadMore">
      {{ loadingMore ? '加载中…' : '上拉加载更多' }}
    </view>
    <view v-else-if="products.length && !hasMore" class="more muted">没有更多了</view>

    <view class="bottom-nav">
      <view class="nav-item active">首页</view>
      <view class="nav-item" @click="goEntitlements">已购</view>
      <view class="nav-item" @click="goOrders">订单</view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 72px;
}
.hero {
  background: linear-gradient(135deg, #1677ff, #69b1ff);
  color: #fff;
  padding: 20px 16px 16px;
}
.hero-name {
  font-size: 20px;
  font-weight: 600;
}
.hero-intro {
  margin-top: 6px;
  font-size: 13px;
  opacity: 0.9;
}
.search-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
}
.search-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  background: #f5f7fa;
  border-radius: 18px;
  font-size: 14px;
}
.search-btn {
  background: #1677ff;
  color: #fff;
}
.type-tabs,
.sort-tabs {
  white-space: nowrap;
  background: #fff;
  padding: 0 12px 12px;
}
.sort-tabs {
  padding-top: 0;
  border-bottom: 1px solid #f1f5f9;
}
.type-tab,
.sort-tab {
  display: inline-block;
  padding: 6px 14px;
  margin-right: 8px;
  border-radius: 16px;
  font-size: 13px;
  color: #64748b;
  background: #f1f5f9;
}
.type-tab.active,
.sort-tab.active {
  color: #1677ff;
  background: #e6f4ff;
}
.hint,
.error,
.empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 14px;
}
.empty-title {
  color: #334155;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
}
.empty-sub {
  margin-bottom: 12px;
  font-size: 13px;
}
.error {
  color: #cf1322;
}
.product-list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.product-card {
  display: flex;
  gap: 12px;
  background: #fff;
  border-radius: 12px;
  padding: 12px;
}
.product-card.gray {
  opacity: 0.45;
  filter: grayscale(0.85);
}
.cover {
  width: 96px;
  height: 72px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}
.cover-img {
  width: 100%;
  height: 100%;
}
.cover-placeholder {
  width: 100%;
  height: 100%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.info {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 500;
  color: #1e293b;
}
.subtitle,
.meta {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.price-row {
  margin-top: 8px;
}
.price {
  color: #cf1322;
  font-size: 16px;
  font-weight: 600;
}
.line-price {
  margin-left: 6px;
  color: #94a3b8;
  font-size: 12px;
  text-decoration: line-through;
}
.more {
  text-align: center;
  padding: 8px 16px 16px;
  font-size: 12px;
  color: #1677ff;
}
.more.muted {
  color: #94a3b8;
}
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 56px;
  display: flex;
  background: #fff;
  border-top: 1px solid #e2e8f0;
}
.nav-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #64748b;
}
.nav-item.active {
  color: #1677ff;
  font-weight: 500;
}
</style>
