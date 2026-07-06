<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { brandApi } from '@/utils/api'
import { shouldSilenceLoadError, toastApiError } from '@/utils/apiError'
import { ensureSession } from '@/utils/session'

const text = ref('')

onLoad(async () => {
  const user = await ensureSession()
  if (!user?.permissions?.includes('preference.manage')) {
    uni.showToast({ title: '无权限', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 500)
    return
  }
  try {
    const data = await brandApi.getUserPrompt()
    text.value = data.global_instructions || ''
  } catch (e) {
    if (!shouldSilenceLoadError(e)) {
      toastApiError(e, '加载失败')
    }
  }
})

async function save() {
  try {
    await brandApi.updateUserPrompt(text.value)
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e) {
    toastApiError(e, '保存失败')
  }
}
</script>

<template>
  <view class="page">
    <textarea v-model="text" class="area" placeholder="个人风格与提示词" />
    <button class="btn-primary" @click="save">保存</button>
  </view>
</template>

<style scoped>
.page {
  padding: 24rpx;
  background: #f5f5f5;
  min-height: 100vh;
}
.area {
  width: 100%;
  min-height: 320rpx;
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-sizing: border-box;
  font-size: 28rpx;
}
.btn-primary {
  margin-top: 24rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 12rpx;
}
</style>
