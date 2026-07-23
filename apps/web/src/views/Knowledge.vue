<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isBenignEmptyError, knowledgeApi } from '../api/client'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/datetime'

const loading = ref(false)
const uploading = ref(false)
const documents = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')

const pasteVisible = ref(false)
const pasteForm = ref({ title: '', text: '' })

const editVisible = ref(false)
const editSaving = ref(false)
const editForm = ref({ id: '', title: '', text: '' })

let searchTimer = null

async function loadDocs() {
  loading.value = true
  try {
    const { data } = await knowledgeApi.list({
      q: keyword.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    documents.value = Array.isArray(data?.items) ? data.items : []
    total.value = data?.total ?? 0
  } catch (e) {
    if (isBenignEmptyError(e)) {
      documents.value = []
      total.value = 0
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadDocs()
  }, 300)
}

function onPageChange(p) {
  page.value = p
  loadDocs()
}

function onSizeChange(s) {
  pageSize.value = s
  page.value = 1
  loadDocs()
}

async function beforeUpload(file) {
  const name = file.name || ''
  const ok = /\.(txt|md|markdown|pdf|docx)$/i.test(name)
  if (!ok) {
    ElMessage.warning('仅支持 TXT / MD / PDF / DOCX')
    return false
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('title', name.replace(/\.[^.]+$/, ''))
    form.append('file', file)
    await knowledgeApi.uploadFile(form)
    ElMessage.success('上传成功')
    page.value = 1
    await loadDocs()
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
    page.value = 1
    await loadDocs()
  } catch (e) {
    ElMessage.error(formatApiError(e, '添加失败'))
  } finally {
    uploading.value = false
  }
}

async function openEdit(row) {
  try {
    const { data } = await knowledgeApi.get(row.id)
    editForm.value = {
      id: data.id,
      title: data.title || '',
      text: data.raw_text || '',
    }
    editVisible.value = true
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载文档失败'))
  }
}

async function submitEdit() {
  if (!editForm.value.title.trim() || !editForm.value.text.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  editSaving.value = true
  try {
    await knowledgeApi.update(editForm.value.id, {
      title: editForm.value.title.trim(),
      text: editForm.value.text,
    })
    ElMessage.success('已保存并重新索引')
    editVisible.value = false
    await loadDocs()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存失败'))
  } finally {
    editSaving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」？`, '删除文档')
    await knowledgeApi.remove(row.id)
    ElMessage.success('已删除')
    if (documents.value.length === 1 && page.value > 1) page.value -= 1
    await loadDocs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

watch(keyword, onSearchInput)

onMounted(loadDocs)
</script>

<template>
  <div class="knowledge-page">
    <div class="page-card">
      <div class="knowledge-page__header">
        <div class="page-title">知识库</div>
        <div class="knowledge-page__actions">
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索标题 / 文件名"
            style="width: 220px"
          />
          <el-button @click="pasteVisible = true">粘贴文本</el-button>
          <el-upload
            :show-file-list="false"
            accept=".txt,.md,.markdown,.pdf,.docx"
            :before-upload="beforeUpload"
          >
            <el-button type="primary" :loading="uploading">上传 TXT/MD/PDF/DOCX</el-button>
          </el-upload>
        </div>
      </div>
      <el-alert
        title="租户私有知识库优先于平台行业库，用于 AI 生成时 RAG 检索引用。支持 TXT、Markdown、PDF、DOCX。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-table v-loading="loading" :data="documents" stripe>
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="file_name" label="文件名" min-width="140" show-overflow-tooltip />
        <el-table-column label="分块数" width="90">
          <template #default="{ row }">{{ row.chunk_count }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'parsed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ row.status === 'parsed' ? '已解析' : row.status === 'failed' ? '失败' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="knowledge-page__pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
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

    <el-dialog v-model="editVisible" title="编辑知识库文档" width="640px">
      <el-form label-width="60px">
        <el-form-item label="标题" required>
          <el-input v-model="editForm.title" maxlength="300" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="editForm.text" type="textarea" :rows="14" placeholder="修改后将重新分块索引" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEdit">保存</el-button>
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
  gap: 12px;
  flex-wrap: wrap;
}

.knowledge-page__header .page-title {
  margin-bottom: 0;
}

.knowledge-page__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.knowledge-page__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
