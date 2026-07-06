<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { tenantApi } from '@/utils/api'
import { shouldSilenceLoadError, toastApiError } from '@/utils/apiError'
import { ensureSession } from '@/utils/session'

const form = ref({ name: '', industry_code: 'finance', credit_code: '' })
const industries = [
  { label: '财税 / 代理记账', value: 'finance' },
  { label: '法律', value: 'legal' },
]
let activeTenant = null

function applyActiveTenantFallback() {
  if (!activeTenant) return false
  form.value = {
    name: activeTenant.name || '',
    industry_code: activeTenant.industry_code || 'finance',
    credit_code: form.value.credit_code || '',
  }
  return true
}

function onIndustryChange(e) {
  form.value.industry_code = industries[e.detail.value].value
}

const industryLabel = computed(
  () => industries.find((i) => i.value === form.value.industry_code)?.label || '请选择',
)

onLoad(async () => {
  const user = await ensureSession()
  if (!user?.permissions?.includes('tenant.manage')) {
    uni.showToast({ title: '无权限', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 500)
    return
  }
  activeTenant = user.active_tenant
  try {
    const data = await tenantApi.getProfile()
    form.value = {
      name: data.name,
      industry_code: data.industry_code,
      credit_code: data.credit_code || '',
    }
  } catch (e) {
    if (shouldSilenceLoadError(e)) {
      applyActiveTenantFallback()
      return
    }
    toastApiError(e, '加载失败')
  }
})

async function save() {
  if (!form.value.name.trim()) {
    uni.showToast({ title: '请填写公司名称', icon: 'none' })
    return
  }
  if (form.value.name.trim().length < 2) {
    uni.showToast({ title: '公司名称至少 2 个字符', icon: 'none' })
    return
  }
  try {
    await tenantApi.updateProfile({
      name: form.value.name.trim(),
      industry_code: form.value.industry_code,
      credit_code: form.value.credit_code || null,
    })
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e) {
    toastApiError(e, '保存失败')
  }
}
</script>

<template>
  <view class="page">
    <view class="card">
      <view class="field">
        <text class="label">公司名称</text>
        <input v-model="form.name" class="input" maxlength="200" />
      </view>
      <view class="field">
        <text class="label">主行业</text>
        <picker mode="selector" :range="industries" range-key="label" @change="onIndustryChange">
          <view class="picker">{{ industryLabel }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="label">统一社会信用代码</text>
        <input v-model="form.credit_code" class="input" maxlength="18" placeholder="选填，18 位" />
      </view>
      <button class="btn-primary" @click="save">保存</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  padding: 24rpx;
  background: #f5f5f5;
  min-height: 100vh;
}
.card {
  background: #fff;
  border-radius: 12rpx;
  padding: 32rpx;
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
.input,
.picker {
  width: 100%;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 20rpx;
  box-sizing: border-box;
  font-size: 28rpx;
}
.picker {
  min-height: 68rpx;
  line-height: 68rpx;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  border-radius: 12rpx;
  margin-top: 16rpx;
  font-size: 30rpx;
}
</style>
