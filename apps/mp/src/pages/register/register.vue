<script setup>
import { ref } from 'vue'
import { setToken } from '@/utils/auth'
import { authApi } from '@/utils/api'

const displayName = ref('')
const phone = ref('')
const password = ref('')
const tenantName = ref('')
const loading = ref(false)

const phonePattern = /^1\d{10}$/

async function handleRegister() {
  const name = displayName.value.trim()
  const workspace = tenantName.value.trim()
  if (!name || !phone.value.trim() || !password.value.trim() || !workspace) {
    uni.showToast({ title: '请填写昵称、手机号、密码和工作台名称', icon: 'none' })
    return
  }
  if (name.length < 2) {
    uni.showToast({ title: '昵称至少 2 个字符', icon: 'none' })
    return
  }
  if (workspace.length < 2) {
    uni.showToast({ title: '工作台名称至少 2 个字符', icon: 'none' })
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
      tenant_name: workspace,
      display_name: name,
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
      <text class="sub">手机号注册 · 创建智营工作台</text>

      <view class="form-item">
        <text class="label">昵称</text>
        <input v-model="displayName" class="input" maxlength="100" placeholder="团队内显示的名称" />
      </view>
      <view class="form-item">
        <text class="label">登录手机号</text>
        <input v-model="phone" class="input" type="number" maxlength="11" placeholder="用于登录与接收重要通知" />
      </view>
      <view class="form-item">
        <text class="label">密码</text>
        <input v-model="password" class="input" password placeholder="至少 8 位" />
      </view>
      <view class="form-item">
        <text class="label">工作台名称</text>
        <input v-model="tenantName" class="input" maxlength="200" placeholder="团队对外称呼，可与营业执照名称不同" />
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

.input {
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
