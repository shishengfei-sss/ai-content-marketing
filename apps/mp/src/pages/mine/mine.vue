<script setup>
import { clearToken } from '@/utils/auth'

const menus = [
  { title: '个人提示词' },
  { title: '风格偏好' },
  { title: '账号与安全' },
  { title: '关于智营获客' },
]

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
</script>

<template>
  <view class="page">
    <view class="profile">
      <view class="avatar">张</view>
      <view>
        <text class="profile__name">张会计</text>
        <text class="profile__company">某某财务咨询有限公司</text>
      </view>
    </view>

    <view class="menu">
      <view v-for="item in menus" :key="item.title" class="menu-item">
        <text class="menu-item__title">{{ item.title }}</text>
        <text class="menu-item__arrow">›</text>
      </view>
    </view>

    <view class="logout-wrap">
      <button class="btn-logout" @click="handleLogout">退出登录</button>
    </view>

    <view class="preview-tag">静态预览 · 待确认 UI</view>
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
