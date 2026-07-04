<script setup>

import { onMounted, ref } from 'vue'

import { ElMessage } from 'element-plus'

import { wechatApi } from '../api/client'



const loading = ref(false)

const saving = ref(false)

const settings = ref({

  bound: false,

  account_name: '',

  account_type: 'service',

  can_auto_publish: false,

  mode: 'mock',

  is_mock: true,

})

const accountName = ref('测试财税公众号')

const accountType = ref('service')



const typeOptions = [

  { value: 'service', label: '服务号（支持自动发布图文）' },

  { value: 'subscription', label: '订阅号（仅复制/下载，手动发表）' },

]



onMounted(async () => {

  loading.value = true

  try {

    const { data } = await wechatApi.get()

    settings.value = data

    if (data.account_name) accountName.value = data.account_name

    if (data.account_type) accountType.value = data.account_type

  } catch (e) {

    ElMessage.error(e.message || '加载失败')

  } finally {

    loading.value = false

  }

})



async function handleBindMock() {

  saving.value = true

  try {

    const { data } = await wechatApi.bindMock(accountName.value.trim(), accountType.value)

    settings.value = data

    ElMessage.success('绑定成功')

  } catch (e) {

    ElMessage.error(e.message || '绑定失败')

  } finally {

    saving.value = false

  }

}

</script>



<template>

  <div class="wechat-settings page-card" v-loading="loading">

    <div class="wechat-settings__header">

      <h2>公众号绑定</h2>

      <el-tag :type="settings.mode === 'mock' ? 'warning' : 'success'">

        {{ settings.mode === 'mock' ? 'Mock 模式' : '真实模式' }}

      </el-tag>

    </div>



    <el-alert

      type="info"

      :closable="false"

      show-icon

      title="账号类型决定发布能力"

      description="服务号：图文内容可 Mock/真实自动发布。订阅号与视频脚本：请使用复制或下载，到微信公众平台手动发表。"

      style="margin-bottom: 24px"

    />



    <el-descriptions :column="1" border>

      <el-descriptions-item label="绑定状态">

        <el-tag :type="settings.bound ? 'success' : 'info'">

          {{ settings.bound ? '已绑定' : '未绑定' }}

        </el-tag>

      </el-descriptions-item>

      <el-descriptions-item v-if="settings.bound" label="账号名称">

        {{ settings.account_name }}

      </el-descriptions-item>

      <el-descriptions-item v-if="settings.bound" label="账号类型">

        {{ settings.account_type === 'subscription' ? '订阅号' : '服务号' }}

      </el-descriptions-item>

      <el-descriptions-item label="自动发布">

        <el-tag :type="settings.can_auto_publish ? 'success' : 'info'">

          {{ settings.can_auto_publish ? '服务号图文可自动发' : '请复制/下载后手动发表' }}

        </el-tag>

      </el-descriptions-item>

      <el-descriptions-item label="发布器">

        {{ settings.is_mock ? 'MockWeChatPublisher' : 'RealWeChatPublisher' }}

      </el-descriptions-item>

    </el-descriptions>



    <div v-if="settings.mode === 'mock'" class="wechat-settings__form">

      <el-form label-width="100px" style="margin-top: 24px; max-width: 520px">

        <el-form-item label="账号类型">

          <el-radio-group v-model="accountType">

            <el-radio v-for="opt in typeOptions" :key="opt.value" :value="opt.value">

              {{ opt.label }}

            </el-radio>

          </el-radio-group>

        </el-form-item>

        <el-form-item label="公众号名称">

          <el-input v-model="accountName" placeholder="例如：XX财税公众号" />

        </el-form-item>

        <el-form-item>

          <el-button type="primary" :loading="saving" @click="handleBindMock">

            {{ settings.bound ? '更新绑定' : 'Mock 绑定' }}

          </el-button>

        </el-form-item>

      </el-form>

    </div>

  </div>

</template>



<style scoped>

.wechat-settings__header {

  display: flex;

  align-items: center;

  gap: 12px;

  margin-bottom: 16px;

}



.wechat-settings__header h2 {

  margin: 0;

  font-size: 18px;

}

</style>


