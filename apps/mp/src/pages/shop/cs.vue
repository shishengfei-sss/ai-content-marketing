<script setup>
/**
 * M15-A 联系客服。对照 PRD 02-买家端UI.html #m15a
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getShopBuyerShopId, shopBuyerApi } from '@/utils/shopApi'

const shopId = ref('')
const store = ref(null)
const loading = ref(false)
const error = ref('')

const phone = computed(() => store.value?.service_phone || '')
const hours = '工作日 9:00–18:00'

async function load() {
  if (!shopId.value) {
    error.value = '缺少店铺标识'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await shopBuyerApi.getStore({ shop_id: shopId.value, page: 1, page_size: 1 })
    store.value = data.shop || null
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCs() {
  if (phone.value) {
    uni.makePhoneCall({
      phoneNumber: phone.value,
      fail() {
        uni.showToast({ title: '暂无客服入口', icon: 'none' })
      },
    })
    return
  }
  uni.showToast({ title: '暂无客服入口', icon: 'none' })
}

function goBack() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/shop/mine' }) })
}

onLoad((q) => {
  shopId.value = (q?.shop_id || '').trim() || getShopBuyerShopId()
  load()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="card">加载中…</view>
    <view v-else-if="error" class="card">{{ error }}</view>
    <view v-else class="card">
      <view class="field">
        <text class="label">在线客服</text>
        <text class="val">{{ phone ? '可拨打客服电话' : '商家未配置' }}</text>
      </view>
      <view class="field">
        <text class="label">客服电话</text>
        <text class="val">{{ phone || '—' }}</text>
      </view>
      <view class="field">
        <text class="label">工作时间</text>
        <text class="val">{{ hours }}</text>
      </view>
    </view>
    <view class="actions">
      <button class="btn-primary" @click="openCs">打开客服</button>
      <button class="btn-ghost" @click="goBack">返回</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding: 16px;
}
.card {
  background: #fff;
  border-radius: 16px;
  padding: 4px 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.field {
  padding: 14px 0;
  border-bottom: 1px solid #f1f5f9;
}
.field:last-child {
  border-bottom: none;
}
.label {
  display: block;
  font-size: 12px;
  color: #64748b;
}
.val {
  display: block;
  margin-top: 4px;
  font-size: 15px;
  color: #0f172a;
}
.actions {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  border-radius: 999px;
  font-weight: 700;
}
.btn-ghost {
  background: #fff;
  color: #334155;
  border-radius: 999px;
}
</style>
