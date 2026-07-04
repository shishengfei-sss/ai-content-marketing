<template>

  <view class="page">

    <view class="card">

      <text class="card__title">公众号绑定</text>

      <text class="card__desc">服务号可自动发布图文；订阅号请复制/下载后手动发表。</text>



      <view class="info-row">

        <text class="info-label">绑定状态</text>

        <text class="info-value">{{ settings.bound ? '已绑定' : '未绑定' }}</text>

      </view>

      <view v-if="settings.bound" class="info-row">

        <text class="info-label">账号类型</text>

        <text class="info-value">{{ settings.account_type === 'subscription' ? '订阅号' : '服务号' }}</text>

      </view>

      <view class="info-row">

        <text class="info-label">自动发布</text>

        <text class="info-value">{{ settings.can_auto_publish ? '服务号图文可发' : '请手动发表' }}</text>

      </view>



      <view class="form">

        <text class="form-label">账号类型</text>

        <radio-group @change="onTypeChange">

          <label class="radio-item">

            <radio value="service" :checked="accountType === 'service'" color="#1677ff" />

            服务号（自动发图文）

          </label>

          <label class="radio-item">

            <radio value="subscription" :checked="accountType === 'subscription'" color="#1677ff" />

            订阅号（复制/下载）

          </label>

        </radio-group>



        <text class="form-label">公众号名称</text>

        <input v-model="accountName" class="input" placeholder="例如：XX财税公众号" />



        <button class="btn-primary" :loading="saving" @click="handleBind">

          {{ settings.bound ? '更新绑定' : 'Mock 绑定' }}

        </button>

      </view>

    </view>

  </view>

</template>



<script setup>

import { onShow } from '@dcloudio/uni-app'

import { ref } from 'vue'



import { wechatApi } from '@/utils/api'



const settings = ref({

  bound: false,

  account_name: '',

  account_type: 'service',

  can_auto_publish: false,

})

const accountName = ref('测试财税公众号')

const accountType = ref('service')

const saving = ref(false)



async function loadSettings() {

  try {

    const data = await wechatApi.get()

    settings.value = data

    if (data.account_name) accountName.value = data.account_name

    if (data.account_type) accountType.value = data.account_type

  } catch (e) {

    uni.showToast({ title: e.message || '加载失败', icon: 'none' })

  }

}



function onTypeChange(e) {

  accountType.value = e.detail.value

}



async function handleBind() {

  saving.value = true

  try {

    const data = await wechatApi.bindMock(accountName.value.trim(), accountType.value)

    settings.value = data

    uni.showToast({ title: '绑定成功', icon: 'success' })

  } catch (e) {

    uni.showToast({ title: e.message || '绑定失败', icon: 'none' })

  } finally {

    saving.value = false

  }

}



onShow(loadSettings)

</script>



<style scoped>

.page {

  min-height: 100vh;

  background: #f5f5f5;

  padding: 24rpx;

}



.card {

  background: #fff;

  border-radius: 16rpx;

  padding: 32rpx;

}



.card__title {

  display: block;

  font-size: 34rpx;

  font-weight: 600;

  margin-bottom: 12rpx;

}



.card__desc {

  display: block;

  font-size: 26rpx;

  color: #666;

  line-height: 1.5;

  margin-bottom: 24rpx;

}



.info-row {

  display: flex;

  justify-content: space-between;

  padding: 16rpx 0;

  border-bottom: 1rpx solid #f0f0f0;

  font-size: 28rpx;

}



.info-label {

  color: #666;

}



.form {

  margin-top: 32rpx;

}



.form-label {

  display: block;

  font-size: 28rpx;

  color: #333;

  margin: 24rpx 0 12rpx;

}



.radio-item {

  display: block;

  font-size: 26rpx;

  margin-bottom: 16rpx;

}



.input {

  background: #f5f5f5;

  border-radius: 12rpx;

  padding: 20rpx;

  font-size: 28rpx;

}



.btn-primary {

  margin-top: 32rpx;

  background: #1677ff;

  color: #fff;

  font-size: 30rpx;

  border-radius: 12rpx;

}

</style>


