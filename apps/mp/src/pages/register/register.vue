<script setup>
import { onMounted, ref } from 'vue'
import { setToken } from '@/utils/auth'
import { assistantsApi, authApi } from '@/utils/api'

const phone = ref('')
const password = ref('')
const industryCode = ref('finance')
const assistants = ref([])
const loading = ref(false)

const phonePattern = /^1\d{10}$/

onMounted(async () => {
  try {
    const data = await assistantsApi.list()
    assistants.value = data
    if (data.length) industryCode.value = data[0].code
  } catch {
    /* fallback finance */
  }
})

async function handleRegister() {
  if (!phone.value.trim() || !password.value.trim()) {
    uni.showToast({ title: '请填写手机号和密码', icon: 'none' })
    return
  }
  if (!phonePattern.test(phone.value.trim())) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  if (password.value.length < 8) {
    uni.showToast({ title: '密码至少 8 位', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await authApi.register({
      phone: phone.value.trim(),
      password: password.value,
      industry_code: industryCode.value,
    })
    setToken(data.access_token)
    uni.showToast({ title: '注册成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/index/index' })
    }, 400)
  } catch (e) {
    uni.showToast({ title: e.message || '注册失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <view class="page">
    <view class="card">
      <text class="title">注册账号</text>
      <text class="sub">手机号注册，一人一号</text>

      <view class="form-item">
        <text class="label">手机号</text>
        <input v-model="phone" class="input" type="number" maxlength="11" placeholder="11 位手机号" />
      </view>
      <view class="form-item">
        <text class="label">密码</text>
        <input v-model="password" class="input" password placeholder="至少 8 位" />
      </view>
      <view v-if="assistants.length" class="form-item">
        <text class="label">默认 AI 助手</text>
        <picker
          mode="selector"
          :range="assistants"
          range-key="name"
          @change="(e) => (industryCode = assistants[e.detail.value].code)"
        >
          <view class="picker">
            {{ assistants.find((a) => a.code === industryCode)?.name || '请选择' }}
          </view>
        </picker>
      </view>
      <button class="btn" :loading="loading" @click="handleRegister">注册</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 48rpx 32rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx 32rpx;
}

.title {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  margin-bottom: 8rpx;
}

.sub {
  display: block;
  font-size: 26rpx;
  color: #999;
  margin-bottom: 40rpx;
}

.form-item {
  margin-bottom: 28rpx;
}

.label {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 12rpx;
}

.input,
.picker {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}

.btn {
  margin-top: 16rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 12rpx;
  font-size: 32rpx;
}
</style>
