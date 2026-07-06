<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { brandApi, shouldSilenceLoadError } from '../api/client'

const loading = ref(false)
const saving = ref(false)
const instructions = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await brandApi.getUserPrompt()
    instructions.value = data.global_instructions || ''
  } catch (e) {
    if (!shouldSilenceLoadError(e)) {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
})

async function handleSave() {
  saving.value = true
  try {
    await brandApi.updateUserPrompt({ global_instructions: instructions.value })
    ElMessage.success('个人提示词已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-card" v-loading="loading">
    <h2 style="margin: 0 0 8px">我的偏好</h2>
    <p style="color: #666; margin-bottom: 16px">创作时勾选「应用个人提示词」后生效</p>
    <el-input v-model="instructions" type="textarea" :rows="8" placeholder="例如：多用短句，避免术语堆砌，适当使用 emoji" />
    <div style="margin-top: 16px">
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </div>
  </div>
</template>
