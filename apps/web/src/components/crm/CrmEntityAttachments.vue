<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { formatDateTime } from '../../utils/datetime'

const props = defineProps({
  entityType: { type: String, required: true },
  entityId: { type: String, required: true },
  editable: { type: Boolean, default: false },
})

const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const uploading = ref(false)
const attachments = ref([])

function formatFileSize(n) {
  if (!n && n !== 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  if (!props.entityId) return
  loading.value = true
  try {
    const { data } = await crmApi.listAttachments({
      entity_type: props.entityType,
      entity_id: props.entityId,
    })
    attachments.value = Array.isArray(data) ? data : []
  } catch {
    attachments.value = []
  } finally {
    loading.value = false
  }
}

async function onUploadFile(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('文件超过 50MB')
    return
  }
  uploading.value = true
  try {
    await crmApi.uploadAttachment(props.entityType, props.entityId, file)
    ElMessage.success('已上传')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
    ev.target.value = ''
  }
}

async function downloadAttachment(att) {
  try {
    const { data } = await crmApi.downloadAttachment(att.id)
    const url = window.URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = att.file_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

async function removeAttachment(att) {
  try {
    await ElMessageBox.confirm(`确定删除附件「${att.file_name}」？`, '删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await crmApi.deleteAttachment(att.id)
    await load()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

watch(
  () => [props.entityType, props.entityId],
  () => load(),
)

onMounted(async () => {
  await loadMembers()
  await load()
})

defineExpose({ reload: load })
</script>

<template>
  <div v-loading="loading" class="crm-entity-attachments">
    <div class="crm-entity-attachments__head">
      <div class="crm-entity-attachments__title">文档附件</div>
      <label v-if="editable" class="crm-entity-attachments__upload">
        <input type="file" :disabled="uploading" @change="onUploadFile" />
        <el-button type="primary" size="small" :loading="uploading">上传附件</el-button>
      </label>
    </div>

    <el-table v-if="attachments.length" :data="attachments" stripe size="small" class="crm-table">
      <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column label="上传人" width="110">
        <template #default="{ row }">{{ resolveMemberName(row.uploaded_by_user_id) }}</template>
      </el-table-column>
      <el-table-column label="上传时间" width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="downloadAttachment(row)">下载</el-button>
          <el-button
            v-if="editable"
            link
            type="danger"
            size="small"
            @click="removeAttachment(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无附件" :image-size="56" />
  </div>
</template>

<style scoped>
.crm-entity-attachments__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  gap: 12px;
}
.crm-entity-attachments__title {
  font-weight: 600;
  font-size: 14px;
}
.crm-entity-attachments__upload {
  position: relative;
  display: inline-flex;
  cursor: pointer;
}
.crm-entity-attachments__upload input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
</style>
