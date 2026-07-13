<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isBenignEmptyError, knowledgeApi } from '../api/client'
import { formatApiError } from '../utils/apiError'

const loading = ref(false)
const uploading = ref(false)
const documents = ref([])
const pasteVisible = ref(false)
const pasteForm = ref({ title: '', text: '' })

async function loadDocs() {
  loading.value = true
  try {
    const { data } = await knowledgeApi.list()
    documents.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (isBenignEmptyError(e)) {
      documents.value = []
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

async function beforeUpload(file) {
  uploading.value = true
  try {
    const form = new FormData()
    form.append('title', file.name.replace(/\.[^.]+$/, ''))
    form.append('file', file)
    await knowledgeApi.uploadFile(form)
    ElMessage.success('上传成功')
    loadDocs()
  } catch (e) {
    ElMessage.error(formatApiError(e, '上传失败'))
  } finally {
    uploading.value = false
  }
  return false
}

async function submitPaste() {
  if (!pasteForm.value.title.trim() || !pasteForm.value.text.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  uploading.value = true
  try {
    await knowledgeApi.uploadText(pasteForm.value)
    ElMessage.success('已添加')
    pasteVisible.value = false
    pasteForm.value = { title: '', text: '' }
    loadDocs()
  } catch (e) {
    ElMessage.error(formatApiError(e, '添加失败'))
  } finally {
    uploading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」？`, '删除文档')
    await knowledgeApi.remove(row.id)
    ElMessage.success('已删除')
    loadDocs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(loadDocs)
</script>

<template>
  <div class="knowledge-page">
    <div class="page-card">
      <div class="knowledge-page__header">
        <div class="page-title">知识库</div>
        <div class="knowledge-page__actions">
          <el-button @click="pasteVisible = true">粘贴文本</el-button>
          <el-upload :show-file-list="false" accept=".txt,.md" :before-upload="beforeUpload">
            <el-button type="primary" :loading="uploading">上传 TXT/MD</el-button>
          </el-upload>
        </div>
      </div>
      <el-alert
        title="租户私有知识库优先于平台行业库，用于 AI 生成时 RAG 检索引用。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-table v-loading="loading" :data="documents" stripe>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column label="分块数" width="100">
          <template #default="{ row }">{{ row.chunk_count }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'parsed' ? 'success' : 'warning'" size="small">
              {{ row.status === 'parsed' ? '已解析' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="pasteVisible" title="粘贴知识库文本" width="560px">
      <el-form label-width="60px">
        <el-form-item label="标题">
          <el-input v-model="pasteForm.title" placeholder="例如：公司服务价目表" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="pasteForm.text" type="textarea" :rows="10" placeholder="粘贴 TXT/Markdown 内容..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pasteVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitPaste">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.knowledge-page__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.knowledge-page__header .page-title {
  margin-bottom: 0;
}

.knowledge-page__actions {
  display: flex;
  gap: 8px;
}
</style>
