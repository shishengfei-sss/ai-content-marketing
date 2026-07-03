<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { brandApi } from '../api/client'

const loading = ref(false)
const saving = ref(false)
const form = ref({
  company_display_name: '',
  tone: '专业亲切',
  cta_text: '',
  sample_snippet: '',
})

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await brandApi.get()
    form.value = { ...data }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
})

async function handleSave() {
  saving.value = true
  try {
    await brandApi.update(form.value)
    ElMessage.success('品牌设置已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-card" v-loading="loading">
    <h2 style="margin: 0 0 16px">品牌设置</h2>
    <el-form label-width="120px" style="max-width: 560px">
      <el-form-item label="对外品牌名">
        <el-input v-model="form.company_display_name" placeholder="例如：智汇财税" />
      </el-form-item>
      <el-form-item label="语气风格">
        <el-input v-model="form.tone" placeholder="专业亲切" />
      </el-form-item>
      <el-form-item label="行动号召 CTA">
        <el-input v-model="form.cta_text" placeholder="例如：私信获取免费财税体检" />
      </el-form-item>
      <el-form-item label="范文片段">
        <el-input v-model="form.sample_snippet" type="textarea" :rows="4" placeholder="一段代表品牌语气的示例文案" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>
