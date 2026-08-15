<script setup>
/**
 * M07 课时目录。对照 PRD #m07
 * 内容来自 product.extra.lessons 或缺省演示大纲
 */
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const entitlementId = ref('')
const loading = ref(true)
const outline = ref(null)

const STATUS_BADGE = {
  done: '已学完',
  learning: '学习中',
  todo: '',
}

async function load() {
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId())
    outline.value = await shopBuyerApi.getOutline(entitlementId.value)
    if (outline.value.entitlement_status !== 'active') {
      uni.showToast({ title: '暂无学习权限', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openLesson(les) {
  if (les.locked) {
    uni.showToast({ title: '购买后可学习', icon: 'none' })
    return
  }
  if (outline.value?.entitlement_status !== 'active' && !les.is_trial) {
    uni.showToast({ title: '暂无学习权限', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/pages/shop/player?entitlement_id=${entitlementId.value}&lesson_id=${les.id}&course_id=${outline.value.course_id}`,
  })
}

onLoad((q) => {
  entitlementId.value = (q?.entitlement_id || '').trim()
})
onShow(() => {
  if (entitlementId.value) load()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="outline">
      <view class="head">
        <text class="title">{{ outline.product_name || '课程目录' }}</text>
        <text class="sub">专栏目录</text>
        <text class="prog-text">
          学习进度 {{ outline.progress_pct }}% · {{ outline.learned_count }}/{{ outline.total_count }} 讲
        </text>
        <view class="bar"><view class="bar-i" :style="{ width: outline.progress_pct + '%' }" /></view>
      </view>
      <view
        v-for="les in outline.lessons"
        :key="les.id"
        class="lesson"
        :class="{ on: les.status === 'learning', locked: les.locked, done: les.status === 'done' }"
        @click="openLesson(les)"
      >
        <view class="left">
          <text class="lt">
            <text v-if="les.status === 'done'">✓ </text>
            <text v-else-if="les.status === 'learning'">▶ </text>
            {{ les.title }}
          </text>
          <text v-if="les.locked" class="lock">🔒 锁定</text>
        </view>
        <view class="right">
          <text v-if="les.is_trial" class="badge trial">试看</text>
          <text v-else-if="STATUS_BADGE[les.status]" class="badge">{{ STATUS_BADGE[les.status] }}</text>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 16px;
}
.head {
  margin-bottom: 14px;
}
.title {
  display: block;
  font-size: 18px;
  font-weight: 700;
}
.sub {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}
.prog-text {
  display: block;
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}
.bar {
  margin-top: 8px;
  height: 6px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}
.bar-i {
  height: 100%;
  background: #1677ff;
}
.lesson {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-left: 3px solid transparent;
}
.lesson.on {
  border-left-color: #1677ff;
  background: #eff6ff;
}
.lesson.done {
  border-left-color: #10b981;
}
.lesson.locked {
  opacity: 0.55;
}
.lt {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}
.lock {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}
.badge {
  font-size: 11px;
  color: #1677ff;
  font-weight: 600;
}
.badge.trial {
  background: #e6f4ff;
  padding: 2px 6px;
  border-radius: 6px;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
