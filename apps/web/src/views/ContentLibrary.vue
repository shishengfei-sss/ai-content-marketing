<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { contentApi } from '../api/client'

const router = useRouter()

const statusMap = {
  draft: { label: '草稿', type: 'info' },
  pending_review: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  scheduled: { label: '已排期', type: '' },
  published: { label: '已发布', type: 'success' },
  exported: { label: '已导出', type: 'info' },
}

const platformMap = {
  wechat: '公众号',
  xhs: '小红书',
  douyin: '抖音',
}

const sceneMap = {
  tax_deadline_reminder: '报税提醒',
  bookkeeping_intro: '代理记账',
  small_company_register: '注册指南',
  case_penalty_story: '处罚案例',
}

const loading = ref(false)
const contents = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const searchQ = ref('')
const filterPlatform = ref('')
const filterStatus = ref('')

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

async function loadContents() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPlatform.value) params.platform = filterPlatform.value
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    const { data } = await contentApi.list(params)
    contents.value = data.items.map((item) => ({
      id: item.id,
      title: item.topic,
      platform: platformMap[item.platform] || item.platform,
      platformCode: item.platform,
      scene: sceneMap[item.scene] || item.scene,
      status: item.status,
      author: item.author_name || '—',
      updated: formatTime(item.updated_at || item.created_at),
    }))
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleSubmitReview(row) {
  try {
    await contentApi.submitReview(row.id)
    ElMessage.success('已提交审核')
    loadContents()
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  }
}

watch([page, filterPlatform, filterStatus], () => loadContents())

onMounted(loadContents)
</script>

<template>
  <div class="contents-page">
    <div class="page-card">
      <div class="contents-page__toolbar">
        <el-input
          v-model="searchQ"
          placeholder="搜索标题..."
          prefix-icon="Search"
          style="width: 240px"
          clearable
          @keyup.enter="loadContents"
          @clear="loadContents"
        />
        <el-select v-model="filterPlatform" placeholder="平台" style="width: 120px" clearable>
          <el-option label="公众号" value="wechat" />
          <el-option label="小红书" value="xhs" />
          <el-option label="抖音" value="douyin" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" style="width: 120px" clearable>
          <el-option label="草稿" value="draft" />
          <el-option label="待审核" value="pending_review" />
          <el-option label="已通过" value="approved" />
          <el-option label="已发布" value="published" />
        </el-select>
        <el-button type="primary" icon="Plus" @click="router.push('/create')">新建内容</el-button>
      </div>

      <el-table v-loading="loading" :data="contents" stripe>
        <el-table-column type="selection" width="48" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.platform }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="scene" label="场景" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="author" label="创建人" width="100" />
        <el-table-column prop="updated" label="更新时间" width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'draft'"
              type="primary"
              link
              size="small"
              @click="handleSubmitReview(row)"
            >
              提交审核
            </el-button>
            <el-button type="primary" link size="small" disabled>导出</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="contents-page__pagination">
        <el-pagination
          v-model:current-page="page"
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.contents-page__toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.contents-page__pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
