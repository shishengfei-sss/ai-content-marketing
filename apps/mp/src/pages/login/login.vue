<script setup>
import { ref } from 'vue'
import { setToken } from '@/utils/auth'
import { authApi } from '@/utils/api'

const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!username.value.trim() || !password.value.trim()) {
    uni.showToast({ title: '请输入账号和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await authApi.login(username.value.trim(), password.value)
    setToken(data.access_token)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/index/index' })
    }, 400)
  } catch (e) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <view class="login-page">
    <view class="login-card">
      <view class="brand">
        <view class="brand__logo">AI</view>
        <text class="brand__title">智营获客</text>
        <text class="brand__sub">AI 内容营销 · 移动工作台</text>
      </view>

      <view class="form">
        <view class="form-item">
          <text class="form-label">邮箱</text>
          <input
            v-model="username"
            class="form-input"
            placeholder="admin@example.com"
          />
        </view>
        <view class="form-item">
          <text class="form-label">密码</text>
          <input
            v-model="password"
            class="form-input"
            password
            placeholder="请输入密码"
          />
        </view>
        <button class="btn-login" :loading="loading" @click="handleLogin">
          登录
        </button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #1677ff 0%, #0958d9 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx;
}

.login-card {
  width: 100%;
  background: #fff;
  border-radius: 24rpx;
  padding: 56rpx 40rpx;
  box-shadow: 0 16rpx 48rpx rgba(0, 0, 0, 0.12);
}

.brand {
  text-align: center;
  margin-bottom: 48rpx;
}

.brand__logo {
  width: 96rpx;
  height: 96rpx;
  margin: 0 auto 20rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  font-weight: 700;
}

.brand__title {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  margin-bottom: 8rpx;
}

.brand__sub {
  font-size: 26rpx;
  color: #999;
}

.form-item {
  margin-bottom: 28rpx;
}

.form-label {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 12rpx;
}

.form-input {
  width: 100%;
  height: 88rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}

.btn-login {
  margin-top: 16rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 12rpx;
  font-size: 32rpx;
  height: 88rpx;
  line-height: 88rpx;
}
</style>
