<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { llmApi } from '../api/client'

const form = ref({
  provider: 'deepseek',
  base_url: 'https://api.deepseek.com',
  api_key: '',
  model: 'deepseek-chat',
  timeout_sec: 60,
})
const maskedKey = ref('')
const configSource = ref('env')

const providers = [
  { value: 'deepseek', label: 'DeepSeek（默认）' },
  { value: 'openai_compatible', label: 'OpenAI 兼容' },
  { value: 'dashscope', label: '通义千问（DashScope）' },
]

const testing = ref(false)
const saving = ref(false)
const testResult = ref(null)

onMounted(async () => {
  try {
    const { data } = await llmApi.get()
    form.value.provider = data.provider
    form.value.base_url = data.base_url
    form.value.model = data.model
    form.value.timeout_sec = data.timeout_sec
    maskedKey.value = data.api_key_masked
    configSource.value = data.source
  } catch (e) {
    ElMessage.error(e.message)
  }
})

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    const { data } = await llmApi.test()
    testResult.value = data
    ElMessage.success('连接测试成功')
  } catch (e) {
    ElMessage.error(e.message || '模型连接失败')
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const payload = { ...form.value }
    if (!payload.api_key) delete payload.api_key
    const { data } = await llmApi.update(payload)
    maskedKey.value = data.api_key_masked
    configSource.value = data.source
    form.value.api_key = ''
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-llm">
    <div class="page-card" style="max-width: 640px">
      <div class="page-title">AI 模型配置</div>
      <el-alert
        title="配置 API Key 后即可调用大模型生成内容。密钥将加密存储，界面脱敏展示。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <el-form :model="form" label-width="120px" label-position="left">
        <el-form-item label="当前来源">
          <el-tag size="small">{{ configSource === 'tenant' ? '租户配置' : '环境变量' }}</el-tag>
          <span v-if="maskedKey" class="form-hint" style="margin-left: 8px">
            已保存 Key：{{ maskedKey }}
          </span>
        </el-form-item>

        <el-form-item label="模型提供商">
          <el-select v-model="form.provider" style="width: 100%">
            <el-option
              v-for="p in providers"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="API Base URL">
          <el-input v-model="form.base_url" placeholder="https://api.deepseek.com" />
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="留空则保持已保存的 Key"
          />
        </el-form-item>

        <el-form-item label="模型名称">
          <el-input v-model="form.model" placeholder="deepseek-chat" />
        </el-form-item>

        <el-form-item label="超时（秒）">
          <el-input-number v-model="form.timeout_sec" :min="10" :max="120" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="testing" @click="handleTest">
            测试连接
          </el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>

      <el-descriptions
        v-if="testResult"
        title="测试结果"
        :column="2"
        border
        style="margin-top: 16px"
      >
        <el-descriptions-item label="状态">
          <el-tag type="success">成功</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模型">{{ testResult.model }}</el-descriptions-item>
        <el-descriptions-item label="延迟">{{ testResult.latency_ms }} ms</el-descriptions-item>
        <el-descriptions-item label="回复">{{ testResult.message }}</el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<style scoped>
.form-hint {
  font-size: 12px;
  color: var(--color-text-muted);
}
</style>
