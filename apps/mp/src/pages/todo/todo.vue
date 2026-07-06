<template>
  <view class="page">
    <view class="hero">
      <view class="hero__left">
        <text class="hero__sub">{{ loading ? '加载中…' : `共 ${total} 条内容` }}</text>
      </view>
      <view class="hero__btn" @click="goCreate">
        <text class="hero__btn-icon">+</text>
        <text>去创作</text>
      </view>
    </view>

    <scroll-view
      scroll-y
      class="scroll"
      :lower-threshold="100"
      @scrolltolower="loadMore"
    >
      <view v-if="loading" class="skeleton-list">
        <view v-for="n in 3" :key="n" class="skeleton-card">
          <view class="skeleton-line skeleton-line--short" />
          <view class="skeleton-line skeleton-line--long" />
          <view class="skeleton-line skeleton-line--mid" />
        </view>
      </view>

      <view v-else-if="!items.length" class="empty">
        <view class="empty__icon">📦</view>
        <text class="empty__title">还没有内容</text>
        <text class="empty__desc">在创作页生成方案并选定后，内容会出现在这里</text>
        <view class="empty__btn" @click="goCreate">开始创作</view>
      </view>

      <view v-else class="list">
        <view
          v-for="item in items"
          :key="item.id"
          class="card"
          :class="`card--${item.platformCode}`"
        >
          <view class="card__head">
            <view class="card__meta">
              <text class="card__platform-icon">{{ platformIcon(item.platformCode) }}</text>
              <text class="card__platform-name">{{ item.platform }}</text>
              <text class="card__format">{{ item.formatLabel }}</text>
              <view class="status" :class="`status--${item.status}`">
                {{ item.statusLabel }}
              </view>
            </view>
            <view class="card__acts">
              <text
                class="link"
                :class="{ 'link--disabled': acting }"
                @click="!acting && handleCopy(item)"
              >
                复制
              </text>
              <text
                v-if="canAutoPublish(item)"
                class="link link--primary"
                :class="{ 'link--disabled': acting }"
                @click="!acting && handlePublish(item)"
              >
                发布
              </text>
              <text
                v-if="canExportXhs(item)"
                class="link link--primary"
                :class="{ 'link--disabled': acting }"
                @click="!acting && handleExport(item, 'xhs')"
              >
                导出
              </text>
              <text
                v-if="canExportScript(item)"
                class="link link--primary"
                :class="{ 'link--disabled': acting }"
                @click="!acting && handleExport(item, 'script')"
              >
                导出
              </text>
            </view>
          </view>

          <text class="card__title">{{ item.title }}</text>
          <text class="card__time">{{ item.time }}</text>
        </view>

        <view v-if="loadingMore" class="list-foot">加载中…</view>
        <view v-else-if="!hasMore && items.length" class="list-foot">没有更多了</view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { BASE_URL, contentApi, wechatApi } from '@/utils/api'
import { toastUnlessEmpty, isBenignEmptyError } from '@/utils/apiError'
import { ensureSession } from '@/utils/session'

const PAGE_SIZE = 10

const loading = ref(false)
const loadingMore = ref(false)
const acting = ref(false)
const page = ref(1)
const total = ref(0)
const items = ref([])
const wechatSettings = ref({ can_auto_publish: false })

const hasMore = computed(() => items.value.length < total.value)

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }
const formatMap = { article: '图文', note: '笔记', video_script: '视频脚本' }
const statusMap = {
  draft: '草稿',
  scheduled: '已排期',
  published: '已发布',
  failed: '失败',
  exported: '已导出',
}

function platformIcon(code) {
  return { wechat: '💬', xhs: '📕', douyin: '🎬' }[code] || '📄'
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function mapItem(item) {
  return {
    id: item.id,
    title: item.topic,
    body: item.body,
    platform: platformMap[item.platform] || item.platform,
    platformCode: item.platform,
    contentFormat: item.content_format || 'article',
    formatLabel: formatMap[item.content_format] || item.content_format,
    status: item.status,
    statusLabel: statusMap[item.status] || item.status,
    time: formatTime(item.updated_at || item.created_at),
  }
}

function canAutoPublish(item) {
  return (
    item.platformCode === 'wechat' &&
    item.contentFormat === 'article' &&
    wechatSettings.value.can_auto_publish &&
    (item.status === 'draft' || item.status === 'failed')
  )
}

function canExportXhs(item) {
  return item.contentFormat === 'note' && item.platformCode === 'xhs'
}

function canExportScript(item) {
  return item.contentFormat === 'video_script'
}

async function loadWechatSettings() {
  try {
    wechatSettings.value = await wechatApi.get()
  } catch {
    wechatSettings.value = { can_auto_publish: false }
  }
}

async function fetchPage(pageNum, append = false) {
  const data = await contentApi.list({ page: pageNum, page_size: PAGE_SIZE })
  total.value = data.total ?? 0
  const mapped = data.items.map(mapItem)
  items.value = append ? [...items.value, ...mapped] : mapped
  page.value = pageNum
}

async function loadItems() {
  const user = await ensureSession()
  if (!user) {
    items.value = []
    total.value = 0
    page.value = 1
    return
  }
  loading.value = true
  try {
    await fetchPage(1, false)
  } catch (e) {
    if (isBenignEmptyError(e)) {
      items.value = []
      total.value = 0
      page.value = 1
    } else {
      toastUnlessEmpty(e)
    }
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loading.value || loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    await fetchPage(page.value + 1, true)
  } catch (e) {
    toastUnlessEmpty(e)
  } finally {
    loadingMore.value = false
  }
}

function goCreate() {
  uni.switchTab({ url: '/pages/create/create' })
}

function handleCopy(item) {
  uni.setClipboardData({
    data: item.body || item.title,
    success: () => uni.showToast({ title: '已复制', icon: 'success' }),
  })
}

async function handlePublish(item) {
  acting.value = true
  try {
    const data = await contentApi.publish(item.id)
    uni.showToast({ title: '发布成功', icon: 'success' })
    // #ifdef H5
    if (data.preview_url) window.open(BASE_URL + data.preview_url, '_blank')
    // #endif
    await fetchPage(1, false)
  } catch (e) {
    uni.showToast({ title: e.message || '发布失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

async function handleExport(item, type) {
  acting.value = true
  try {
    let data
    if (type === 'xhs') data = await contentApi.exportXhs(item.id)
    else data = await contentApi.exportScript(item.id)
    uni.showToast({ title: '导出成功', icon: 'success' })
    // #ifdef H5
    window.open(BASE_URL + data.download_url, '_blank')
    // #endif
    await fetchPage(1, false)
  } catch (e) {
    uni.showToast({ title: e.message || '导出失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

onShow(async () => {
  await loadWechatSettings()
  await loadItems()
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
  background: #f0f2f5;
  overflow: hidden;
}

.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 32rpx 24rpx;
  background: linear-gradient(135deg, #1677ff 0%, #0958d9 100%);
  color: #fff;
  flex-shrink: 0;
}

.hero__sub {
  font-size: 28rpx;
  opacity: 0.92;
}

.hero__btn {
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 10rpx 24rpx;
  background: rgba(255, 255, 255, 0.2);
  border: 1rpx solid rgba(255, 255, 255, 0.35);
  border-radius: 999rpx;
  font-size: 24rpx;
}

.hero__btn-icon {
  font-size: 28rpx;
  line-height: 1;
}

.scroll {
  flex: 1;
  height: 0;
  min-height: 0;
}

.list {
  padding: 20rpx 24rpx 32rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 22rpx 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.05);
  border-left: 5rpx solid #1677ff;
}

.card--wechat {
  border-left-color: #07c160;
}

.card--xhs {
  border-left-color: #ff2442;
}

.card--douyin {
  border-left-color: #161823;
}

.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 12rpx;
}

.card__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8rpx;
  flex: 1;
  min-width: 0;
}

.card__platform-icon {
  font-size: 24rpx;
}

.card__platform-name {
  font-size: 22rpx;
  color: #64748b;
}

.card__format {
  font-size: 20rpx;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
}

.status {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
}

.status--draft {
  color: #1677ff;
  background: #e6f4ff;
}

.status--scheduled {
  color: #d48806;
  background: #fff7e6;
}

.status--published {
  color: #389e0d;
  background: #f6ffed;
}

.status--exported {
  color: #722ed1;
  background: #f9f0ff;
}

.status--failed {
  color: #cf1322;
  background: #fff1f0;
}

.card__acts {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex-shrink: 0;
}

.link {
  font-size: 24rpx;
  color: #64748b;
}

.link--primary {
  color: #1677ff;
}

.link--disabled {
  opacity: 0.45;
}

.card__title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
  margin-bottom: 8rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card__time {
  font-size: 22rpx;
  color: #94a3b8;
}

.list-foot {
  text-align: center;
  font-size: 24rpx;
  color: #94a3b8;
  padding: 16rpx 0 24rpx;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 48rpx 80rpx;
}

.empty__icon {
  font-size: 96rpx;
  margin-bottom: 24rpx;
}

.empty__title {
  font-size: 34rpx;
  font-weight: 600;
  color: #334155;
  margin-bottom: 12rpx;
}

.empty__desc {
  font-size: 26rpx;
  color: #94a3b8;
  text-align: center;
  line-height: 1.6;
  margin-bottom: 40rpx;
}

.empty__btn {
  padding: 20rpx 64rpx;
  background: linear-gradient(135deg, #1677ff, #0958d9);
  color: #fff;
  font-size: 28rpx;
  border-radius: 999rpx;
}

.skeleton-list {
  padding: 20rpx 24rpx;
}

.skeleton-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
}

.skeleton-line {
  height: 24rpx;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
  border-radius: 8rpx;
  margin-bottom: 12rpx;
}

.skeleton-line--short {
  width: 40%;
}

.skeleton-line--mid {
  width: 60%;
}

.skeleton-line--long {
  width: 90%;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
