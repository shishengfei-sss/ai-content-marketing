<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../api/client'

const apiBase = import.meta.env.VITE_API_BASE_URL || ''

const statusMap = {
  draft: { label: '草稿', type: 'info' },
  scheduled: { label: '已排期', type: '' },
  published: { label: '已发布', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  exported: { label: '已导出', type: 'info' },
}

const platformMap = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')
const filterPlatform = ref('')
const searchQ = ref('')

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildPreviewHtml(row) {
  const topic = escapeHtml(row.topic)
  const body = escapeHtml(row.body)
  const statusLabel = escapeHtml(statusMap[row.status]?.label || row.status)
  const platformLabel = escapeHtml(row.platformLabel || row.platform)
  const author = escapeHtml(row.author_phone || row.author_name || '—')
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${topic}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 720px; margin: 40px auto; padding: 0 16px; line-height: 1.8; color: #333; }
    h1 { font-size: 24px; margin-bottom: 24px; }
    .meta { color: #999; font-size: 13px; margin-bottom: 32px; }
    .body { white-space: pre-wrap; }
    .badge { background: #e6f4ff; color: #1677ff; padding: 8px 12px;
             border-radius: 6px; font-size: 13px; margin-bottom: 24px; }
  </style>
</head>
<body>
  <div class="badge">内容预览 — ${statusLabel} · ${platformLabel}</div>
  <h1>${topic}</h1>
  <div class="meta">用户 ${author} · 管理后台预览</div>
  <div class="body">${body || '（暂无正文）'}</div>
</body>
</html>`
}

function openPreview(url) {
  if (!url) return
  window.open(url, '_blank')
}

function previewContent(row) {
  if (row.previewFullUrl) {
    openPreview(row.previewFullUrl)
    return
  }
  const blob = new Blob([buildPreviewHtml(row)], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank')
  if (!win) {
    ElMessage.warning('请允许浏览器弹窗后重试')
    URL.revokeObjectURL(url)
    return
  }
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPlatform.value) params.platform = filterPlatform.value
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    const { data } = await adminApi.listContents(params)
    items.value = (data.items ?? []).map((item) => ({
      ...item,
      platformLabel: platformMap[item.platform] || item.platform,
      previewFullUrl: item.preview_url ? `${apiBase}${item.preview_url}` : '',
    }))
    total.value = data.total ?? 0
  } catch (e) {
    if (isBenignEmptyError(e)) {
      items.value = []
      total.value = 0
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

watch([page, filterStatus, filterPlatform], loadData)
onMounted(loadData)
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="搜索标题..."
        style="width: 220px"
        clearable
        @keyup.enter="loadData"
        @clear="loadData"
      />
      <el-select v-model="filterPlatform" placeholder="平台" clearable style="width: 120px">
        <el-option label="公众号" value="wechat" />
        <el-option label="小红书" value="xhs" />
        <el-option label="抖音" value="douyin" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 120px">
        <el-option label="草稿" value="draft" />
        <el-option label="已发布" value="published" />
        <el-option label="已导出" value="exported" />
      </el-select>
      <el-button type="primary" @click="loadData">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" stripe>
      <el-table-column prop="topic" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column label="平台" width="90">
        <template #default="{ row }">
          <el-tag size="small">{{ row.platformLabel }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="author_phone" label="用户手机" width="120" />
      <el-table-column prop="tenant_name" label="账号" width="120" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
            {{ statusMap[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="发布时间" width="160">
        <template #default="{ row }">
          {{ row.published_at ? new Date(row.published_at).toLocaleString('zh-CN') : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="previewContent(row)">
            预览
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
