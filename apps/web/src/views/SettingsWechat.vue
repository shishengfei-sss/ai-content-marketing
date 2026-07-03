<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { wechatApi } from '../api/client'

const loading = ref(false)
const saving = ref(false)
const settings = ref({
  bound: false,
  account_name: '',
  mode: 'mock',
  is_mock: true,
})
const accountName = ref('测试财税服务号')

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await wechatApi.get()
    settings.value = data
    if (data.account_name) accountName.value = data.account_name
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
})

async function handleBindMock() {
  saving.value = true
  try {
    const { data } = await wechatApi.bindMock(accountName.value.trim())
    settings.value = data
    ElMessage.success('Mock 绑定成功')
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
      title="开发期使用 Mock 发布"
      description="审核通过的公众号内容可 Mock 发布到本地 HTML 预览。部署后切换 WECHAT_PUBLISHER=real 并绑定真实服务号。"
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
      <el-descriptions-item label="发布器">
        {{ settings.is_mock ? 'MockWeChatPublisher' : 'RealWeChatPublisher' }}
      </el-descriptions-item>
    </el-descriptions>

    <div v-if="settings.mode === 'mock'" class="wechat-settings__form">
      <el-form label-width="100px" style="margin-top: 24px; max-width: 480px">
        <el-form-item label="服务号名称">
          <el-input v-model="accountName" placeholder="例如：XX财税服务号" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleBindMock">
            {{ settings.bound ? '更新 Mock 绑定' : 'Mock 绑定' }}
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
