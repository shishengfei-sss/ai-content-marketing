<script setup>
import { ref } from 'vue'
import { authApi } from '@/utils/api'
import { afterAuth } from '@/utils/session'

const loginMode = ref('password')
const phone = ref('')
const password = ref('')
const smsCode = ref('')
const loading = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
const mockHint = ref('')
let countdownTimer = null

const phonePattern = /^1\d{10}$/

function startCountdown() {
  countdown.value = 60
  clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) clearInterval(countdownTimer)
  }, 1000)
}

function goForgot() {
  uni.navigateTo({ url: '/pages/forgot/forgot' })
}

async function handlePasswordLogin() {
  if (!phone.value.trim() || !password.value.trim()) {
    uni.showToast({ title: '请输入手机号和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await authApi.login(phone.value.trim(), password.value)
    uni.showToast({ title: '登录成功', icon: 'success' })
    await afterAuth(data)
  } catch (e) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleSendCode() {
  if (!phonePattern.test(phone.value.trim())) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  if (countdown.value > 0) return
  sendingCode.value = true
  try {
    const data = await authApi.sendSmsCode(phone.value.trim())
    mockHint.value = data.mock_hint || ''
    uni.showToast({ title: data.message || '验证码已发送', icon: 'success' })
    startCountdown()
  } catch (e) {
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
  } finally {
    sendingCode.value = false
  }
}

async function handleSmsLogin() {
  if (!phonePattern.test(phone.value.trim())) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  if (!smsCode.value.trim()) {
    uni.showToast({ title: '请输入验证码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await authApi.loginBySms(phone.value.trim(), smsCode.value.trim())
    uni.showToast({ title: '登录成功', icon: 'success' })
    await afterAuth(data)
  } catch (e) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function handleLogin() {
  if (loginMode.value === 'password') {
    handlePasswordLogin()
  } else {
    handleSmsLogin()
  }
}

function goRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
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

      <view class="mode-tabs">
        <view
          class="mode-tab"
          :class="{ 'mode-tab--active': loginMode === 'password' }"
          @click="loginMode = 'password'"
        >
          密码登录
        </view>
        <view
          class="mode-tab"
          :class="{ 'mode-tab--active': loginMode === 'sms' }"
          @click="loginMode = 'sms'"
        >
          验证码登录
        </view>
      </view>

      <view class="form">
        <view class="form-item">
          <text class="form-label">手机号</text>
          <input
            v-model="phone"
            class="form-input"
            type="number"
            maxlength="11"
            placeholder="请输入 11 位手机号"
          />
        </view>

        <view v-if="loginMode === 'password'" class="form-item">
          <text class="form-label">密码</text>
          <input
            v-model="password"
            class="form-input"
            password
            placeholder="请输入密码"
          />
        </view>

        <view v-else class="form-item">
          <text class="form-label">验证码</text>
          <view class="sms-row">
            <input
              v-model="smsCode"
              class="form-input sms-input"
              type="number"
              maxlength="6"
              placeholder="请输入验证码"
            />
            <button
              class="btn-code"
              :disabled="countdown > 0 || sendingCode"
              :loading="sendingCode"
              @click="handleSendCode"
            >
              {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
            </button>
          </view>
          <text v-if="mockHint" class="mock-hint">{{ mockHint }}</text>
        </view>

        <button class="btn-login" :loading="loading" @click="handleLogin">登录</button>
        <view class="form-footer">
          <text class="link" @click="goForgot">忘记密码</text>
          <text style="margin: 0 12rpx">·</text>
          还没有账号？
          <text class="link" @click="goRegister">立即注册</text>
        </view>
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
  margin-bottom: 36rpx;
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

.mode-tabs {
  display: flex;
  gap: 8rpx;
  padding: 6rpx;
  background: #eef0f3;
  border-radius: 16rpx;
  margin-bottom: 32rpx;
}

.mode-tab {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 26rpx;
  color: #666;
  border-radius: 12rpx;
}

.mode-tab--active {
  background: #fff;
  color: #1677ff;
  font-weight: 600;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.06);
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

.sms-row {
  display: flex;
  gap: 16rpx;
  align-items: center;
}

.sms-input {
  flex: 1;
}

.btn-code {
  flex-shrink: 0;
  min-width: 200rpx;
  height: 88rpx;
  line-height: 88rpx;
  padding: 0 20rpx;
  background: #fff;
  color: #1677ff;
  border: 1rpx solid #91caff;
  border-radius: 12rpx;
  font-size: 26rpx;
  margin: 0;
}

.btn-code[disabled] {
  color: #999;
  border-color: #ddd;
}

.mock-hint {
  display: block;
  margin-top: 12rpx;
  font-size: 22rpx;
  color: #999;
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

.form-footer {
  margin-top: 28rpx;
  text-align: center;
  font-size: 26rpx;
  color: #999;
}

.link {
  color: #1677ff;
  margin-left: 8rpx;
}
</style>
