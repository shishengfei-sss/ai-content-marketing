<script setup>
/**
 * 资质材料单项：必须先选文件上传，再可选 OCR 识别。
 * 禁止「一点击就显示已上传」。
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { shopApi } from '../../api/client'

const props = defineProps({
  docType: { type: String, required: true },
  title: { type: String, required: true },
  required: { type: Boolean, default: false },
  optional: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  /** 是否支持 OCR 识别填入 */
  ocrEnabled: { type: Boolean, default: false },
  fileId: { type: String, default: '' },
  fileName: { type: String, default: '' },
  /**
   * 自定义上传：(docType, file) => Promise<{ file_id, file_name, size? }>
   * 默认走商家端 /shop/onboarding/files
   */
  uploadFn: { type: Function, default: null },
  /**
   * 自定义 OCR：(payload) => Promise<data>
   * 默认走商家端 OCR
   */
  ocrFn: { type: Function, default: null },
})

const emit = defineEmits(['uploaded', 'ocr-filled', 'cleared'])

const uploading = ref(false)
const recognizing = ref(false)
const inputRef = ref(null)

const hasFile = computed(() => !!props.fileId)

function pickFile() {
  if (props.disabled || uploading.value) return
  inputRef.value?.click()
}

async function doUpload(docType, file) {
  if (props.uploadFn) {
    return props.uploadFn(docType, file)
  }
  const { data } = await shopApi.uploadOnboardingFile(docType, file)
  return data
}

async function doOcr(payload) {
  if (props.ocrFn) {
    return props.ocrFn(payload)
  }
  const { data } = await shopApi.onboardingOcr(payload)
  return data
}

async function onFileChange(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片不能超过 10MB')
    return
  }
  const okTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf']
  if (file.type && !okTypes.includes(file.type)) {
    ElMessage.warning('请上传图片或 PDF')
    return
  }

  uploading.value = true
  try {
    const data = await doUpload(props.docType, file)
    const fileId = data.file_id
    const fileName = data.file_name || file.name
    emit('uploaded', {
      docType: props.docType,
      fileId,
      fileName,
      size: data.size,
    })
    ElMessage.success('上传成功')
    if (props.ocrEnabled) {
      await runOcr(fileId)
    }
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function runOcr(fileId) {
  const id = fileId || props.fileId
  if (!id) {
    ElMessage.warning('请先选择并上传文件')
    return
  }
  recognizing.value = true
  try {
    const data = await doOcr({ doc_type: props.docType, file_id: id })
    emit('ocr-filled', {
      docType: props.docType,
      fileId: id,
      fields: data.fields || {},
      confidence: data.confidence,
      stub: data.stub,
      raw: data,
    })
    ElMessage.success('已识别，请核对自动填入的信息')
  } catch (e) {
    ElMessage.error(e.message || '识别失败，请手动填写')
  } finally {
    recognizing.value = false
  }
}

function clearFile() {
  if (props.disabled) return
  emit('cleared', { docType: props.docType })
}
</script>

<template>
  <div class="material-item" :class="{ 'is-optional': optional }">
    <div class="material-item__meta">
      <div class="material-item__name">
        {{ title }}
        <span v-if="required" class="req">*</span>
      </div>
      <div class="material-item__sub">{{ optional ? '选填' : '必传' }}</div>
      <div v-if="hasFile" class="material-item__file" :title="fileName">
        {{ fileName || '已上传文件' }}
      </div>
    </div>
    <div class="material-item__actions">
      <el-tag v-if="hasFile" type="success" size="small">已上传</el-tag>
      <input
        ref="inputRef"
        type="file"
        class="material-item__input"
        accept="image/*,.pdf,application/pdf"
        :disabled="disabled || uploading"
        @change="onFileChange"
      />
      <el-button
        size="small"
        type="primary"
        plain
        :loading="uploading"
        :disabled="disabled"
        @click="pickFile"
      >
        {{ hasFile ? '重新上传' : '选择文件' }}
      </el-button>
      <el-button
        v-if="ocrEnabled && hasFile"
        size="small"
        :loading="recognizing"
        :disabled="disabled"
        @click="runOcr()"
      >
        识别填入
      </el-button>
      <el-button
        v-if="hasFile && !disabled"
        size="small"
        text
        type="danger"
        @click="clearFile"
      >
        清除
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.material-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  margin-bottom: 0;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 0;
}

.material-item:last-child {
  margin-bottom: 0;
  border-bottom: none;
}

.material-item.is-optional {
  opacity: 1;
}

.material-item__name {
  font-size: 13px;
  color: #262626;
  font-weight: 500;
}

.material-item__name .req {
  color: var(--el-color-danger);
  margin-left: 2px;
}

.material-item__sub {
  font-size: 12px;
  color: #8c8c8c;
  margin-top: 2px;
}

.material-item__file {
  margin-top: 4px;
  font-size: 12px;
  color: #595959;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.material-item__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.material-item__input {
  display: none;
}
</style>
