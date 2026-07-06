<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../api/client'

const connectionForm = ref({
  provider: 'deepseek',
  base_url: 'https://api.deepseek.com',
  api_key: '',
  model: 'deepseek-chat',
})
const policyForm = ref({
  timeout_sec: 60,
  default_free_quota: 100,
  is_active: true,
})
const maskedKey = ref('')
const savingConnection = ref(false)
const savingPolicy = ref(false)
const testing = ref(false)
const testResult = ref(null)

const providers = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai_compatible', label: 'OpenAI 兼容' },
  { value: 'dashscope', label: '通义千问' },
]

function applyConfig(data) {
  connectionForm.value.provider = data.provider
  connectionForm.value.base_url = data.base_url
  connectionForm.value.model = data.model
  connectionForm.value.api_key = ''
  policyForm.value.timeout_sec = Number(data.timeout_sec)
  policyForm.value.default_free_quota = Number(data.default_free_quota)
  policyForm.value.is_active = data.is_active
  maskedKey.value = data.api_key_masked
}

async function loadConfig() {
  try {
    const { data } = await adminApi.getPlatformLlm()
    applyConfig(data)
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  }
}

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    const payload = {
      provider: connectionForm.value.provider,
      base_url: connectionForm.value.base_url,
      model: connectionForm.value.model,
      timeout_sec: policyForm.value.timeout_sec,
    }
    if (connectionForm.value.api_key) payload.api_key = connectionForm.value.api_key
    const { data } = await adminApi.testPlatformLlm(payload)
    testResult.value = data
    ElMessage.success('连接测试成功')
  } catch (e) {
    ElMessage.error(e.message || '模型连接失败')
  } finally {
    testing.value = false
  }
}

async function handleSaveConnection() {
  savingConnection.value = true
  try {
    const payload = {
      provider: connectionForm.value.provider,
      base_url: connectionForm.value.base_url,
      model: connectionForm.value.model,
    }
    if (connectionForm.value.api_key) payload.api_key = connectionForm.value.api_key
    const { data } = await adminApi.updatePlatformLlm(payload)
    maskedKey.value = data.api_key_masked
    connectionForm.value.api_key = ''
    ElMessage.success('连接配置已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingConnection.value = false
  }
}

async function handleSavePolicy() {
  savingPolicy.value = true
  try {
    const { data } = await adminApi.updatePlatformLlm({
      timeout_sec: policyForm.value.timeout_sec,
      default_free_quota: policyForm.value.default_free_quota,
      is_active: policyForm.value.is_active,
    })
    policyForm.value.timeout_sec = Number(data.timeout_sec)
    policyForm.value.default_free_quota = Number(data.default_free_quota)
    policyForm.value.is_active = data.is_active
    ElMessage.success('额度与超时已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingPolicy.value = false
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="page-card">
    <el-alert
      title="平台默认 API Key 供所有用户使用。每租户默认免费生成正文 100 次（可配置）；方案生成不扣次，仅正文生成成功扣 1 次。"
      type="info"
      :closable="false"
      show-icon
    />

    <div class="section">
      <div class="section-title">模型连接</div>
      <el-form label-width="120px" style="max-width: 640px">
        <el-form-item label="Provider">
          <el-select v-model="connectionForm.provider" style="width: 100%">
            <el-option v-for="p in providers" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="connectionForm.base_url" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="connectionForm.model" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="connectionForm.api_key"
            type="password"
            show-password
            placeholder="留空则使用已保存的 Key"
          />
          <div v-if="maskedKey" class="hint">已保存：{{ maskedKey }}</div>
        </el-form-item>
        <el-form-item>
          <el-button :loading="testing" @click="handleTest">测试连接</el-button>
          <el-button type="primary" :loading="savingConnection" @click="handleSaveConnection">
            保存连接配置
          </el-button>
        </el-form-item>
      </el-form>

      <el-descriptions
        v-if="testResult"
        title="测试结果"
        :column="2"
        border
        style="max-width: 640px; margin-bottom: 8px"
      >
        <el-descriptions-item label="状态">
          <el-tag type="success">成功</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Provider">{{ testResult.provider }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ testResult.model }}</el-descriptions-item>
        <el-descriptions-item label="延迟">{{ testResult.latency_ms }} ms</el-descriptions-item>
        <el-descriptions-item label="回复" :span="2">{{ testResult.message }}</el-descriptions-item>
      </el-descriptions>
      <div class="hint">测试连接时：若 Key 留空，将使用已保存的 Key；若填写新 Key，可先测再保存。</div>
    </div>

    <el-divider />

    <div class="section">
      <div class="section-title">额度与超时</div>
      <el-form label-width="120px" style="max-width: 640px">
        <el-form-item label="默认免费次数">
          <el-input-number
            v-model="policyForm.default_free_quota"
            :min="1"
            :max="100000"
            controls-position="right"
            style="width: 180px"
          />
          <div class="hint">新租户默认额度；已注册租户按各自 used 计数，改此值不影响已用次数</div>
        </el-form-item>
        <el-form-item label="超时(秒)">
          <el-input-number
            v-model="policyForm.timeout_sec"
            :min="10"
            :max="300"
            controls-position="right"
            style="width: 180px"
          />
          <div class="hint">仅影响平台 Key 调用大模型的超时，与额度无关</div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="policyForm.is_active" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingPolicy" @click="handleSavePolicy">
            保存额度与超时
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.section {
  margin-top: 20px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}
.hint {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 6px;
}
</style>
