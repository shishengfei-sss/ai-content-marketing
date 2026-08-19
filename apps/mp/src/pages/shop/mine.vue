<script setup>
/**
 * M15 我的。对照 PRD 02-买家端UI.html #m15
 * 菜单原文：我的订单 / 已购内容 / 领权兑换 / 联系客服 / 用户协议 / 隐私
 */
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import ShopTabBar from '@/components/ShopTabBar.vue'
import {
  clearShopBuyerSession,
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  getShopBuyerToken,
  setShopBuyerShopId,
  setShopBuyerTenantId,
  shopBuyerApi,
  shopNavQuery,
} from '@/utils/shopApi'

const shopId = ref('')
const tenantId = ref('')
const openidHint = ref('')
const buyer = ref(null)
const loading = ref(false)
const showLogout = ref(false)

const loggedIn = computed(() => !!buyer.value?.id)
const displayName = computed(() => buyer.value?.nickname || '买家')
const avatarChar = computed(() => (displayName.value || '买').slice(0, 1))
const phoneText = computed(() => buyer.value?.mobile_masked || '未绑定手机')

function qs(extra = {}) {
  return shopNavQuery({
    shopId: extra.shopId ?? shopId.value,
    tenantId: extra.tenantId ?? tenantId.value,
    openid: extra.openid ?? openidHint.value,
  })
}

async function load() {
  loading.value = true
  try {
    if (getShopBuyerToken()) {
      buyer.value = await shopBuyerApi.me()
      return
    }
    buyer.value = null
    const loggedOut = uni.getStorageSync('shop_buyer_logged_out') === '1'
    if (tenantId.value && openidHint.value && !loggedOut) {
      buyer.value = await ensureShopBuyerSession(tenantId.value, openidHint.value)
    }
  } catch {
    buyer.value = null
  } finally {
    loading.value = false
  }
}

async function doLogin() {
  if (!tenantId.value) {
    uni.showToast({ title: '缺少店铺信息', icon: 'none' })
    return
  }
  loading.value = true
  try {
    buyer.value = await ensureShopBuyerSession(tenantId.value, openidHint.value || undefined)
  } catch (e) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function needLoginThen(url) {
  if (!loggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url })
}

function goOrders() {
  needLoginThen(`/pages/shop/orders${qs()}`)
}

function goEntitlements() {
  needLoginThen(`/pages/shop/entitlements${qs()}`)
}

function goClaim() {
  needLoginThen(`/pages/shop/claim${qs()}`)
}

function goCs() {
  uni.navigateTo({ url: `/pages/shop/cs${qs()}` })
}

function goLegal() {
  uni.navigateTo({ url: `/pages/shop/legal${qs()}` })
}

function confirmLogout() {
  clearShopBuyerSession()
  buyer.value = null
  showLogout.value = false
  uni.showToast({ title: '已退出', icon: 'none' })
}

onLoad((q) => {
  shopId.value = (q?.shop_id || '').trim()
  tenantId.value = (q?.tenant_id || '').trim()
  openidHint.value = (q?.openid || '').trim()
  if (!shopId.value) {
    try {
      shopId.value = uni.getStorageSync('shop_buyer_shop_id') || ''
    } catch {
      shopId.value = ''
    }
  }
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
  if (shopId.value) setShopBuyerShopId(shopId.value)
})

onShow(load)
</script>

<template>
  <view class="page">
    <view class="header">
      <view class="avatar">{{ avatarChar }}</view>
      <view v-if="loggedIn" class="meta">
        <text class="name">{{ displayName }}</text>
        <text class="phone">{{ phoneText }}</text>
      </view>
      <view v-else class="meta">
        <text class="name">未登录</text>
        <text class="phone">登录后可购买与学习</text>
        <button class="login-btn" size="mini" @click="doLogin">登录</button>
      </view>
    </view>

    <view class="menu">
      <view class="menu-item" @click="goOrders">
        <text class="mi-ico">🧾</text>
        <text class="mi-lab">我的订单</text>
        <text class="mi-go">›</text>
      </view>
      <view class="menu-item" @click="goEntitlements">
        <text class="mi-ico">📚</text>
        <text class="mi-lab">已购内容</text>
        <text class="mi-go">›</text>
      </view>
      <view class="menu-item" @click="goClaim">
        <text class="mi-ico">🎫</text>
        <text class="mi-lab">领权兑换</text>
        <text class="mi-go">›</text>
      </view>
      <view class="menu-item" @click="goCs">
        <text class="mi-ico">💬</text>
        <text class="mi-lab">联系客服</text>
        <text class="mi-go">›</text>
      </view>
      <view class="menu-item" @click="goLegal">
        <text class="mi-ico">📄</text>
        <text class="mi-lab">用户协议 / 隐私</text>
        <text class="mi-go">›</text>
      </view>
    </view>

    <view v-if="loggedIn" class="logout" @click="showLogout = true">退出登录</view>

    <view v-if="showLogout" class="mask" @click="showLogout = false">
      <view class="sheet" @click.stop>
        <text class="sheet-t">退出登录确认</text>
        <text class="sheet-d">退出后需重新登录才能购买与学习</text>
        <view class="sheet-actions">
          <button class="btn-ghost" @click="showLogout = false">取消</button>
          <button class="btn-danger" @click="confirmLogout">确认退出</button>
        </view>
      </view>
    </view>

    <ShopTabBar
      active="mine"
      :shop-id="shopId"
      :tenant-id="tenantId || getShopBuyerTenantId()"
      :openid="openidHint"
    />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding-bottom: 72px;
}
.header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 28px 20px 26px;
  background: linear-gradient(135deg, #1677ff 0%, #4096ff 55%, #69b1ff 100%);
  color: #fff;
}
.avatar {
  width: 56px;
  height: 56px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.22);
  border: 2px solid rgba(255, 255, 255, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
}
.meta {
  flex: 1;
}
.name {
  display: block;
  font-size: 20px;
  font-weight: 700;
}
.phone {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.82);
}
.login-btn {
  margin-top: 10px;
  background: #fff;
  color: #1677ff;
  border-radius: 999px;
  padding: 0 16px;
  height: 30px;
  line-height: 30px;
  font-weight: 600;
}
.menu {
  margin: -8px 12px 0;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
  position: relative;
  z-index: 1;
}
.menu-item {
  padding: 15px 16px;
  font-size: 15px;
  color: #0f172a;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  gap: 10px;
}
.menu-item:last-child {
  border-bottom: none;
}
.mi-ico {
  font-size: 16px;
  width: 24px;
  text-align: center;
}
.mi-lab {
  flex: 1;
}
.mi-go {
  color: #cbd5e1;
  font-size: 18px;
  line-height: 1;
}
.logout {
  margin: 16px 12px;
  padding: 14px;
  text-align: center;
  color: #64748b;
  background: #fff;
  border-radius: 16px;
  font-size: 15px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 30;
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  padding: 20px 16px 28px;
}
.sheet-t {
  display: block;
  font-size: 16px;
  font-weight: 700;
}
.sheet-d {
  display: block;
  margin: 10px 0 16px;
  font-size: 13px;
  color: #64748b;
  background: #fff5f5;
  padding: 10px 12px;
  border-radius: 8px;
}
.sheet-actions {
  display: flex;
  gap: 8px;
}
.btn-ghost,
.btn-danger {
  flex: 1;
}
.btn-ghost {
  background: #f1f5f9;
  color: #334155;
}
.btn-danger {
  background: #ef4444;
  color: #fff;
}
</style>
