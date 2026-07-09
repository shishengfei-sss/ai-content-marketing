<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasAnyPermission, hasPermission } from '@/utils/permissions'
import { usePagedList } from '@/utils/usePagedList'

const { loading, loadingMore, items, total, hasMore, loadFirst, loadMore, reset } = usePagedList(
  (page, pageSize) => {
    const params = { page, page_size: pageSize }
    if (activeViewId.value) params.view_id = activeViewId.value
    return crmApi.listCustomers(params)
  },
  20,
)

const permissions = ref([])
const views = ref([])
const activeViewId = ref('')
const viewPickerVisible = ref(false)

const modalOpen = computed(() => viewPickerVisible.value)

const canList = () =>
  hasAnyPermission(permissions.value, [
    'crm.customer.list_own',
    'crm.customer.list_team',
    'crm.customer.list_territory',
    'crm.customer.list_all',
  ])
const canCreate = () => hasPermission(permissions.value, 'crm.customer.create')

async function loadData() {
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    try {
      views.value = await crmApi.listViews('customer')
      if (!Array.isArray(views.value)) views.value = []
    } catch {
      views.value = []
    }
    if (!canList()) {
      reset()
      return
    }
    await loadFirst()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  }
}

function currentViewLabel() {
  if (!activeViewId.value) return '全部客户'
  const found = views.value.find((v) => v.id === activeViewId.value)
  return found?.name || '已选视图'
}

function openViewPicker() {
  viewPickerVisible.value = true
}

function selectView(viewId) {
  activeViewId.value = viewId
  viewPickerVisible.value = false
  loadData()
}

function openCreate() {
  uni.navigateTo({ url: '/pages/crm/customer-create' })
}

function goDetail(item) {
  uni.navigateTo({ url: `/pages/crm/customer-detail?id=${item.id}` })
}

onShow(loadData)
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="hero__sub">{{ loading ? '加载中…' : `共 ${total} 个客户` }}</text>
      <view class="hero__actions">
        <view class="hero__btn hero__btn--ghost" @click="openViewPicker">
          <text>{{ currentViewLabel() }}</text>
        </view>
        <view v-if="canCreate()" class="hero__btn" @click="openCreate">
          <text class="hero__btn-icon">+</text>
          <text>新建</text>
        </view>
      </view>
    </view>

    <scroll-view
      scroll-y
      class="scroll"
      :class="{ 'scroll--locked': modalOpen }"
      :lower-threshold="100"
      @scrolltolower="loadMore"
    >
      <view v-if="!canList()" class="empty">无客户列表权限</view>
      <view v-else-if="loading" class="empty">加载中…</view>
      <view v-else-if="!items.length" class="empty">暂无客户</view>
      <view v-else class="list">
        <view v-for="item in items" :key="item.id" class="card" @click="goDetail(item)">
          <view class="card__head">
            <text class="card__title">{{ item.company_name }}</text>
            <text class="status">{{ item.status }}</text>
          </view>
          <text class="card__meta">{{ item.mobile || '—' }}</text>
        </view>
        <view v-if="loadingMore" class="list-foot">加载中…</view>
        <view v-else-if="!hasMore && items.length" class="list-foot">没有更多了</view>
      </view>
    </scroll-view>

    <view v-if="viewPickerVisible" class="mask" @tap.self="viewPickerVisible = false">
      <view class="dialog" @tap.stop>
        <text class="dialog__title">切换视图</text>
        <view class="view-item" @click="selectView('')">全部客户</view>
        <view v-for="view in views" :key="view.id" class="view-item" @click="selectView(view.id)">
          {{ view.name }}
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
  background: #f5f5f5;
  padding: 12px;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
}

.scroll--locked {
  overflow: hidden;
}

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.hero__sub {
  font-size: 13px;
  color: #64748b;
}

.hero__actions {
  display: flex;
  gap: 8px;
}

.hero__btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 8px;
  background: #1677ff;
  color: #fff;
  font-size: 13px;
}

.hero__btn--ghost {
  background: #fff;
  color: #334155;
  border: 1px solid #e2e8f0;
}

.hero__btn-icon {
  font-size: 16px;
  font-weight: 600;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 20px;
}

.card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  border: 1px solid #eef2f7;
}

.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card__title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.status {
  font-size: 12px;
  color: #1677ff;
  background: #eef5ff;
  padding: 2px 8px;
  border-radius: 999px;
}

.card__meta {
  display: block;
  margin-top: 8px;
  font-size: 13px;
  color: #64748b;
}

.empty,
.list-foot {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.dialog {
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 14px;
  padding: 16px;
}

.dialog__title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.view-item {
  padding: 12px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
  color: #334155;
}

.view-item:last-child {
  border-bottom: none;
}
</style>
