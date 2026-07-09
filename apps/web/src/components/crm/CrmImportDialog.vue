<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import { formatApiError } from '../../utils/apiError'

const props = defineProps({
  visible: { type: Boolean, default: false },
  entityType: { type: String, default: 'lead' },
})

const emit = defineEmits(['update:visible', 'done'])

const step = ref(1)
const loading = ref(false)
const jobId = ref('')
const columns = ref([])
const mapping = ref({})
const suggestedMapping = ref({})
const preview = ref(null)
const result = ref(null)
const fileRef = ref(null)
const onDuplicate = ref('skip')

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

function reset() {
  step.value = 1
  jobId.value = ''
  columns.value = []
  mapping.value = {}
  suggestedMapping.value = {}
  preview.value = null
  result.value = null
  onDuplicate.value = 'skip'
}

watch(
  () => props.visible,
  (v) => {
    if (v) reset()
  }
)

async function downloadTemplate() {
  try {
    const blob = await crmApi.downloadImportTemplate(props.entityType)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${props.entityType}_template.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(formatApiError(e, '下载失败'))
  }
}

async function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  loading.value = true
  try {
    const data = await crmApi.uploadImportJob(props.entityType, file)
    jobId.value = data.job_id
    columns.value = data.columns || []
    suggestedMapping.value = data.suggested_mapping || {}
    mapping.value = { ...suggestedMapping.value }
    step.value = 2
  } catch (err) {
    ElMessage.error(formatApiError(err, '上传失败'))
  } finally {
    loading.value = false
    if (fileRef.value) fileRef.value.value = ''
  }
}

async function saveMapping() {
  loading.value = true
  try {
    await crmApi.patchImportJob(jobId.value, {
      mapping: mapping.value,
      options: {
        duplicate_key: 'mobile',
        on_duplicate: onDuplicate.value,
        default_source: '导入',
      },
    })
    const data = await crmApi.previewImportJob(jobId.value)
    preview.value = data
    step.value = 3
  } catch (e) {
    ElMessage.error(formatApiError(e, '预览失败'))
  } finally {
    loading.value = false
  }
}

async function runImport() {
  loading.value = true
  try {
    const data = await crmApi.runImportJob(jobId.value)
    result.value = data
    step.value = 4
    emit('done')
  } catch (e) {
    ElMessage.error(formatApiError(e, '导入失败'))
  } finally {
    loading.value = false
  }
}

async function downloadErrors() {
  try {
    const blob = await crmApi.downloadImportErrors(jobId.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'import_errors.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(formatApiError(e, '下载失败'))
  }
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="导入数据" width="640px" destroy-on-close>
    <div v-if="step === 1" v-loading="loading">
      <p class="hint">支持 CSV（UTF-8）文件，可先下载模板填写。</p>
      <div class="actions">
        <el-button @click="downloadTemplate">下载模板</el-button>
        <label class="upload-btn">
          <input ref="fileRef" type="file" accept=".csv,.xlsx" @change="onFileChange" />
          选择文件上传
        </label>
      </div>
    </div>

    <div v-else-if="step === 2" v-loading="loading">
      <p class="hint">确认列映射后进入预览</p>
      <el-table :data="columns.map((c) => ({ col: c, field: mapping[c] || '' }))" size="small">
        <el-table-column prop="col" label="文件列" />
        <el-table-column label="映射字段">
          <template #default="{ row }">
            <el-input v-model="mapping[row.col]" placeholder="field_key" size="small" />
          </template>
        </el-table-column>
      </el-table>
      <div class="dup-options">
        <span class="hint">重复处理（按手机号）：</span>
        <el-radio-group v-model="onDuplicate" size="small">
          <el-radio value="skip">跳过</el-radio>
          <el-radio value="update">更新已有</el-radio>
        </el-radio-group>
      </div>
      <div class="footer-actions">
        <el-button type="primary" @click="saveMapping">预览</el-button>
      </div>
    </div>

    <div v-else-if="step === 3" v-loading="loading">
      <p class="hint">
        预览前 {{ preview?.preview_rows?.length || 0 }} 行，错误 {{ preview?.error_count || 0 }} 条
      </p>
      <el-table :data="preview?.preview_rows || []" size="small" max-height="280">
        <el-table-column prop="row_number" label="行" width="60" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="error_message" label="说明" />
      </el-table>
      <div class="footer-actions">
        <el-button type="primary" @click="runImport">确认导入</el-button>
      </div>
    </div>

    <div v-else-if="step === 4">
      <el-result icon="success" title="导入完成">
        <template #sub-title>
          成功 {{ result?.success_count }} · 跳过 {{ result?.skip_count }} · 失败
          {{ result?.error_count }}
        </template>
        <template #extra>
          <el-button v-if="result?.error_count" @click="downloadErrors">下载错误行</el-button>
          <el-button type="primary" @click="dialogVisible = false">关闭</el-button>
        </template>
      </el-result>
    </div>
  </el-dialog>
</template>

<style scoped>
.hint {
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}

.actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.upload-btn {
  display: inline-block;
  padding: 8px 16px;
  background: var(--el-color-primary);
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.upload-btn input {
  display: none;
}

.footer-actions {
  margin-top: 16px;
  text-align: right;
}

.dup-options {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
</style>
