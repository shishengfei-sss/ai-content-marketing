<script setup>
import { ref } from 'vue'
import { authApi } from '@/utils/api'

const phone = ref('')
const code = ref('')
const password = ref('')
const confirm = ref('')
const mockHint = ref('测试环境验证码：1111')

async function sendCode() {
  try {
    const data = await authApi.forgotSendCode(phone.value.trim())
    mockHint.value = data.mock_hint || mockHint.value
    uni.showToast({ title: '验证码已发送', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

async function submit() {
  if (password.value !== confirm.value) {
    uni.showToast({ title: '两次密码不一致', icon: 'none' })
    return
  }
  try {
    await authApi.forgotReset({
      phone: phone.value.trim(),
      code: code.value.trim(),
      password: password.value,
    })
    uni.showToast({ title: '密码已重置', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 500)
  } catch (e) {
    uni.showToast({ title: e.message, icon: 'none' })
  }
}
</script>

<template>
  <view class="page">
    <view class="card">
      <text class="title">忘记密码</text>
      <text class="hint">{{ mockHint }}</text>
      <view class="field">
        <text class="label">手机号</text>
        <input v-model="phone" class="input" type="number" maxlength="11" />
      </view>
      <view class="field">
        <text class="label">验证码</text>
        <view class="row">
          <input v-model="code" class="input flex" maxlength="6" />
          <button class="btn-code" @click="sendCode">获取验证码</button>
        </view>
      </view>
      <view class="field">
        <text class="label">新密码</text>
        <input v-model="password" class="input" password />
      </view>
      <view class="field">
        <text class="label">确认密码</text>
        <input v-model="confirm" class="input" password />
      </view>
      <button class="btn-primary" @click="submit">重置密码</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 48rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx;
}
.title {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
}
.hint {
  display: block;
  color: #888;
  font-size: 24rpx;
  margin: 12rpx 0 24rpx;
}
.field {
  margin-bottom: 24rpx;
}
.label {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 8rpx;
}
.input {
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 20rpx 24rpx;
  font-size: 28rpx;
}
.row {
  display: flex;
  gap: 16rpx;
}
.flex {
  flex: 1;
}
.btn-code {
  background: #fff;
  color: #1677ff;
  border: 1rpx solid #91caff;
  font-size: 26rpx;
  padding: 0 20rpx;
  line-height: 72rpx;
  height: 72rpx;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  margin-top: 16rpx;
  border-radius: 12rpx;
}
</style>
