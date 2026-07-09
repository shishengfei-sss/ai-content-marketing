<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import { formatApiError } from '../../utils/apiError'

const props = defineProps({
  visible: { type: Boolean, default: false },
  entityType: { type: String, default: 'lead' },
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

async function loadJobs() {
  loading.value = true
  try {
    const { data } = await crmApi.listImportJobs({
      page: page.value,
      page_size: pageSize.value,
      entity_type: props.entityType,
    })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      page.value = 1
      loadJobs()
    }
  },
)

async function downloadErrors(jobId) {
  try {
    const blob = await crmApi.downloadImportErrors(jobId)
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

function onPageChange(p) {
  page.value = p
  loadJobs()
}

const statusLabels = {
  draft: '草稿',
  previewing: '预览中',
  importing: '导入中',
  completed: '已完成',
  failed: '失败',
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="导入历史" width="720px" destroy-on-close>
    <el-table v-loading="loading" :data="items" size="small" stripe>
      <el-table-column prop="file_name" label="文件" min-width="160" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          {{ statusLabels[row.status] || row.status }}
        </template>
      </el-table-column>
      <el-table-column label="结果" min-width="160">
        <template #default="{ row }">
          成功 {{ row.success_count }} · 跳过 {{ row.skip_count }} · 失败 {{ row.error_count }}
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">
          {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.error_count" link type="primary" @click="downloadErrors(row.id)">
            错误行
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>
  </el-dialog>
</template>

<style scoped>
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
