<script setup>
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'

import { authApi } from '@/utils/api'
import { clearToken, getToken } from '@/utils/auth'

const profile = ref({ name: '未登录', company: '', initial: '?' })

async function loadProfile() {
  if (!getToken()) {
    profile.value = { name: '未登录', company: '', initial: '?' }
    return
  }
  try {
    const data = await authApi.me()
    profile.value = {
      name: data.display_name || data.phone || '用户',
      company: data.phone ? `手机号 ${data.phone}` : data.tenant?.name || '',
      initial: (data.display_name || data.phone || '?').slice(0, 1),
    }
  } catch {
    profile.value = { name: '加载失败', company: '', initial: '?' }
  }
}

function goWechat() {
  uni.navigateTo({ url: '/pages/wechat/wechat' })
}

function handleLogout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出当前账号吗？',
    confirmColor: '#1677ff',
    success(res) {
      if (res.confirm) {
        clearToken()
        uni.showToast({ title: '已退出登录', icon: 'success' })
        setTimeout(() => {
          uni.reLaunch({ url: '/pages/login/login' })
        }, 400)
      }
    },
  })
}

onShow(loadProfile)
</script>

<template>
  <view class="page">
    <view class="profile">
      <view class="avatar">{{ profile.initial }}</view>
      <view>
        <text class="profile__name">{{ profile.name }}</text>
        <text class="profile__company">{{ profile.company }}</text>
      </view>
    </view>

    <view class="logout-wrap">
      <view class="menu">
        <view class="menu-item" @click="goWechat">
          <text>公众号绑定</text>
          <text class="menu-item__arrow">›</text>
        </view>
      </view>
      <button class="btn-logout" @click="handleLogout">退出登录</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 48rpx;
}

.profile {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: #fff;
  padding: 40rpx 32rpx;
  margin-bottom: 24rpx;
}

.avatar {
  width: 96rpx;
  height: 96rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  font-weight: 600;
}

.profile__name {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  margin-bottom: 6rpx;
}

.profile__company {
  font-size: 26rpx;
  color: #999;
}

.menu {
  background: #fff;
  margin-bottom: 24rpx;
}

.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 32rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 30rpx;
}

.menu-item__arrow {
  color: #ccc;
  font-size: 36rpx;
}

.logout-wrap {
  padding: 0 32rpx;
}

.btn-logout {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: #fff;
  color: #ff4d4f;
  font-size: 30rpx;
  border-radius: 12rpx;
  border: 1rpx solid #ffccc7;
}

.btn-logout::after {
  border: none;
}

.preview-tag {
  text-align: center;
  color: #999;
  font-size: 24rpx;
  padding: 40rpx;
}
</style>
