<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, assistantsApi, isBenignEmptyError } from '../../api/client'

const loading = ref(false)
const uploading = ref(false)
const documents = ref([])
const assistants = ref([])
const pasteVisible = ref(false)
const pasteForm = ref({ title: '', text: '', industry_code: 'finance' })

async function loadDocs() {
  loading.value = true
  try {
    const { data } = await adminApi.listKnowledge()
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

async function loadAssistants() {
  try {
    const { data } = await assistantsApi.list()
    assistants.value = data
    if (data.length && !data.some((a) => a.code === pasteForm.value.industry_code)) {
      pasteForm.value.industry_code = data[0].code
    }
  } catch {
    /* ignore */
  }
}

function assistantName(code) {
  return assistants.value.find((a) => a.code === code)?.name || code || '-'
}

async function submitPaste() {
  if (!pasteForm.value.title.trim() || !pasteForm.value.text.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  uploading.value = true
  try {
    await adminApi.uploadKnowledgeText(pasteForm.value)
    ElMessage.success('已添加公共知识')
    pasteVisible.value = false
    pasteForm.value = { title: '', text: '', industry_code: pasteForm.value.industry_code || 'finance' }
    loadDocs()
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    uploading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除公共文档「${row.title}」？`, '删除')
    await adminApi.removeKnowledge(row.id)
    ElMessage.success('已删除')
    loadDocs()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(async () => {
  await loadAssistants()
  await loadDocs()
})
</script>

<template>
  <div class="page-card">
    <div class="header">
      <el-alert
        title="平台公共知识库按 AI 助手（行业）隔离，生成时 RAG 仅检索对应 industry_code 的文档（租户私有库优先）。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-button type="primary" style="margin-top: 16px" @click="pasteVisible = true">
        添加公共文档
      </el-button>
    </div>

    <el-table v-loading="loading" :data="documents" stripe style="margin-top: 16px">
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column label="所属助手" width="140">
        <template #default="{ row }">{{ assistantName(row.industry_code) }}</template>
      </el-table-column>
      <el-table-column label="分块" width="80">
        <template #default="{ row }">{{ row.chunk_count }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'parsed' ? 'success' : 'warning'" size="small">
            {{ row.status === 'parsed' ? '已解析' : row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="pasteVisible" title="添加公共知识" width="520px">
      <el-form label-position="top">
        <el-form-item label="所属 AI 助手">
          <el-select v-model="pasteForm.industry_code" style="width: 100%">
            <el-option
              v-for="a in assistants"
              :key="a.code"
              :label="a.name"
              :value="a.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="pasteForm.title" placeholder="如：代理记账 FAQ" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="pasteForm.text" type="textarea" :rows="10" placeholder="粘贴知识正文..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pasteVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitPaste">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
