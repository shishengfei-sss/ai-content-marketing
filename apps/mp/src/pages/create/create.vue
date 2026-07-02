<template>
  <view class="page">
    <view class="chat-header">
      <view class="chat-header__avatar">AI</view>
      <view>
        <text class="chat-header__title">智营 AI 创作助手</text>
        <text class="chat-header__sub">对话式生成</text>
      </view>
    </view>

    <scroll-view scroll-y class="chat-body" :scroll-into-view="scrollInto">
      <view v-for="(msg, idx) in messages" :key="idx" class="msg-row" :class="'msg-row--' + msg.role">
        <view v-if="msg.role === 'assistant'" class="avatar avatar--ai">AI</view>

        <view class="msg-content">
          <view v-if="msg.type === 'text'" class="bubble">{{ msg.content }}</view>

          <view v-else-if="msg.type === 'quick'" class="quick-list">
            <view
              v-for="item in msg.items"
              :key="item.text"
              class="quick-item"
              @click="handleQuick(item)"
            >
              {{ item.text }}
            </view>
          </view>

          <view v-else-if="msg.type === 'result'" class="result">
            <text class="result__text">{{ msg.content }}</text>
            <view class="result__actions">
              <button class="btn-outline" size="mini" disabled>已保存草稿</button>
              <button
                class="btn-primary"
                size="mini"
                :disabled="msg.status && msg.status !== 'draft'"
                @click="handleSubmitReview(msg)"
              >
                {{ msg.status === 'pending_review' ? '已提交' : '提交审核' }}
              </button>
            </view>
          </view>
        </view>

        <view v-if="msg.role === 'user'" class="avatar avatar--me">我</view>
      </view>

      <view v-if="generating" class="msg-row msg-row--assistant">
        <view class="avatar avatar--ai">AI</view>
        <view class="bubble bubble--typing">正在创作中...</view>
      </view>
      <view id="bottom" />
    </scroll-view>

    <view class="chat-footer">
      <scroll-view scroll-x class="toolbar">
        <text
          v-for="p in platforms"
          :key="p.value"
          class="chip"
          :class="{ 'chip--active': platform === p.value }"
          @click="platform = p.value"
        >
          {{ p.label }}
        </text>
      </scroll-view>
      <view class="input-row">
        <input
          v-model="inputText"
          class="input"
          placeholder="描述想创作的内容..."
          confirm-type="send"
          @confirm="handleSend"
        />
        <button class="send-btn" :loading="generating" @click="handleSend">发送</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'

import { contentApi } from '@/utils/api'

const platform = ref('wechat')
const inputText = ref('')
const generating = ref(false)
const scrollInto = ref('')

const platforms = [
  { value: 'wechat', label: '公众号' },
  { value: 'xhs', label: '小红书' },
  { value: 'douyin', label: '抖音' },
]

const quickStarts = [
  { text: '公众号报税提醒', platform: 'wechat' },
  { text: '小红书代账介绍', platform: 'xhs' },
  { text: '抖音注册指南脚本', platform: 'douyin' },
]

const messages = ref([
  {
    role: 'assistant',
    type: 'text',
    content: '您好！直接告诉我您想创作什么，或点选下方快捷选题。',
  },
  { role: 'assistant', type: 'quick', items: quickStarts },
])

function handleQuick(item) {
  platform.value = item.platform
  inputText.value = item.text
  handleSend()
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || generating.value) return

  messages.value = messages.value.filter((m) => m.type !== 'quick')
  messages.value.push({ role: 'user', type: 'text', content: text })
  inputText.value = ''
  generating.value = true
  scrollInto.value = 'bottom'

  try {
    const data = await contentApi.generate({
      industry_code: 'finance',
      platform: platform.value,
      scene: 'tax_deadline_reminder',
      topic: text,
    })
    messages.value.push({
      role: 'assistant',
      type: 'result',
      content: data.body,
      contentId: data.id,
      status: data.status,
    })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      type: 'text',
      content: `生成失败：${e.message || '请检查 API 与模型配置'}`,
    })
  } finally {
    generating.value = false
    scrollInto.value = 'bottom'
  }
}

async function handleSubmitReview(msg) {
  if (!msg.contentId || (msg.status && msg.status !== 'draft')) return
  try {
    const data = await contentApi.submitReview(msg.contentId)
    msg.status = data.status
    uni.showToast({ title: '已提交审核', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: e.message || '提交失败', icon: 'none' })
  }
}
</script>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 24rpx;
  background: #fff;
  border-bottom: 1rpx solid #eee;
}

.chat-header__avatar {
  width: 72rpx;
  height: 72rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 600;
}

.chat-header__title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
}

.chat-header__sub {
  font-size: 22rpx;
  color: #999;
}

.chat-body {
  flex: 1;
  padding: 24rpx;
  overflow: hidden;
}

.msg-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
  align-items: flex-start;
}

.msg-row--user {
  flex-direction: row-reverse;
}

.avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  flex-shrink: 0;
}

.avatar--ai {
  background: #1677ff;
  color: #fff;
}

.avatar--me {
  background: #52c41a;
  color: #fff;
}

.msg-content {
  max-width: 75%;
}

.bubble {
  background: #fff;
  padding: 20rpx 24rpx;
  border-radius: 16rpx;
  font-size: 28rpx;
  line-height: 1.6;
}

.msg-row--user .bubble {
  background: #e6f4ff;
}

.bubble--typing {
  color: #999;
  font-size: 26rpx;
}

.quick-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.quick-item {
  background: #fff;
  border: 1rpx solid #e8e8e8;
  padding: 20rpx 24rpx;
  border-radius: 24rpx;
  font-size: 26rpx;
}

.result {
  background: #fff;
  border-radius: 16rpx;
  overflow: hidden;
  border: 1rpx solid #e8e8e8;
}

.result__text {
  display: block;
  padding: 24rpx;
  font-size: 28rpx;
  line-height: 1.6;
}

.result__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12rpx;
  padding: 16rpx 24rpx;
  border-top: 1rpx solid #f0f0f0;
  background: #fafafa;
}

.btn-outline {
  background: #fff;
  color: #666;
  font-size: 24rpx;
  border: 1rpx solid #ddd;
}

.btn-primary {
  background: #1677ff;
  color: #fff;
  font-size: 24rpx;
}

.chat-footer {
  background: #fff;
  border-top: 1rpx solid #eee;
  padding: 16rpx 24rpx 24rpx;
}

.toolbar {
  white-space: nowrap;
  margin-bottom: 16rpx;
}

.chip {
  display: inline-block;
  padding: 8rpx 20rpx;
  margin-right: 12rpx;
  border-radius: 20rpx;
  border: 1rpx solid #e8e8e8;
  font-size: 24rpx;
  color: #666;
}

.chip--active {
  background: #e6f4ff;
  border-color: #1677ff;
  color: #1677ff;
}

.input-row {
  display: flex;
  gap: 12rpx;
  align-items: center;
}

.input {
  flex: 1;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 16rpx 20rpx;
  font-size: 28rpx;
}

.send-btn {
  background: #1677ff;
  color: #fff;
  font-size: 28rpx;
  padding: 0 28rpx;
  border-radius: 12rpx;
  line-height: 72rpx;
}
</style>
