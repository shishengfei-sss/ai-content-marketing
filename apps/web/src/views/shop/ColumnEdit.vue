<script setup>
/**
 * A04/A05 专栏编辑 + 课时。对照 PRD 01-管理端UI.html #a04-edit · #a05
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/client'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const column = ref(null)
const lessons = ref([])
const pageMode = computed(() => (route.query.mode === 'view' ? 'view' : 'edit'))
const readonly = computed(
  () => pageMode.value === 'view' || column.value?.status === 'off_sale'
)

const form = reactive({ title: '', intro: '' })
const STATUS_LABEL = { draft: '草稿', published: '已发布', off_sale: '已下架' }
const MEDIA_LABEL = { video: '视频', audio: '音频', article: '图文' }
const LESSON_STATUS = { draft: '草稿', published: '已发布', off_sale: '已下架' }

const lessonVisible = ref(false)
const lessonSaving = ref(false)
const editingLesson = ref(null)
const lessonForm = reactive({
  title: '',
  media_type: 'video',
  media_id: '',
  media_url: '',
  media_name: '',
  duration_sec: 0,
  is_trial: false,
  trial_seconds: 60,
})
const uploading = ref(false)
const fileInput = ref(null)

async function load() {
  loading.value = true
  try {
    const id = route.params.id
    const [{ data: col }, { data: les }] = await Promise.all([
      api.get(`/api/v1/shop/columns/${id}`),
      api.get(`/api/v1/shop/columns/${id}/lessons`),
    ])
    column.value = col
    form.title = col.title
    form.intro = col.intro || ''
    lessons.value = les.items || []
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  saving.value = true
  try {
    const { data } = await api.patch(`/api/v1/shop/columns/${route.params.id}`, {
      title: form.title.trim(),
      intro: form.intro || null,
    })
    column.value = data
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function publishColumn() {
  try {
    const { data } = await api.post(`/api/v1/shop/columns/${route.params.id}/publish`)
    column.value = data
    ElMessage.success('专栏已发布')
  } catch (e) {
    ElMessage.error(e.message || '发布失败')
  }
}

function openLesson(row = null) {
  editingLesson.value = row
  if (row) {
    lessonForm.title = row.title
    lessonForm.media_type = row.media_type
    lessonForm.media_id = row.media_id || ''
    lessonForm.media_url = row.media_url || ''
    lessonForm.media_name = row.media_id ? '已绑定媒体' : ''
    lessonForm.duration_sec = row.duration_sec || 0
    lessonForm.is_trial = !!row.is_trial
    lessonForm.trial_seconds = row.trial_seconds || 60
  } else {
    lessonForm.title = ''
    lessonForm.media_type = 'video'
    lessonForm.media_id = ''
    lessonForm.media_url = ''
    lessonForm.media_name = ''
    lessonForm.duration_sec = 0
    lessonForm.is_trial = false
    lessonForm.trial_seconds = 60
  }
  lessonVisible.value = true
}

async function onPickFile(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post('/api/v1/shop/content/files', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    lessonForm.media_id = data.file_id
    lessonForm.media_url = data.file_url
    lessonForm.media_name = data.file_name
    ElMessage.success('媒体已上传')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function saveLesson() {
  if (!lessonForm.title.trim()) {
    ElMessage.warning('请填写课时标题')
    return
  }
  if (lessonForm.media_type !== 'article' && !lessonForm.media_id && !lessonForm.media_url) {
    ElMessage.warning('请先上传媒体文件')
    return
  }
  lessonSaving.value = true
  try {
    const body = {
      title: lessonForm.title.trim(),
      media_type: lessonForm.media_type,
      media_id: lessonForm.media_id || undefined,
      media_url: lessonForm.media_url || undefined,
      duration_sec: Number(lessonForm.duration_sec) || 0,
      is_trial: lessonForm.is_trial,
      trial_seconds: lessonForm.is_trial ? Number(lessonForm.trial_seconds) || 60 : undefined,
    }
    if (editingLesson.value) {
      await api.patch(
        `/api/v1/shop/columns/${route.params.id}/lessons/${editingLesson.value.id}`,
        body
      )
    } else {
      await api.post(`/api/v1/shop/columns/${route.params.id}/lessons`, body)
    }
    ElMessage.success('课时已保存')
    lessonVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存课时失败')
  } finally {
    lessonSaving.value = false
  }
}

async function publishLesson(row) {
  try {
    await api.post(`/api/v1/shop/columns/${route.params.id}/lessons/${row.id}/publish`)
    ElMessage.success('课时已发布')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '发布失败')
  }
}

async function offLesson(row) {
  try {
    await api.post(`/api/v1/shop/columns/${route.params.id}/lessons/${row.id}/off-sale`)
    ElMessage.success('课时已下架')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '下架失败')
  }
}

async function removeLesson(row) {
  try {
    await ElMessageBox.confirm(`确认删除课时「${row.title}」？`, '删除', { type: 'warning' })
    await api.delete(`/api/v1/shop/columns/${route.params.id}/lessons/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="head">
      <el-button link type="primary" @click="router.push({ name: 'ShopColumns' })">← 返回列表</el-button>
      <span v-if="column" class="status">状态：{{ STATUS_LABEL[column.status] || column.status }}</span>
      <div class="actions">
        <el-button v-if="!readonly" :loading="saving" type="primary" @click="save">保存</el-button>
        <el-button
          v-if="!readonly && column?.status === 'draft'"
          type="success"
          @click="publishColumn"
        >
          发布专栏
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="block">
      <template #header>专栏信息</template>
      <el-form label-width="80px" style="max-width: 640px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" :disabled="readonly" maxlength="200" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.intro" type="textarea" :rows="3" :disabled="readonly" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>
        <div class="card-head">
          <span>课时列表</span>
          <el-button v-if="!readonly" type="primary" size="small" @click="openLesson()">新增课时</el-button>
        </div>
      </template>
      <el-table :data="lessons" border stripe size="small">
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ MEDIA_LABEL[row.media_type] || row.media_type }}</template>
        </el-table-column>
        <el-table-column prop="duration_sec" label="时长(秒)" width="100" />
        <el-table-column label="试看" width="80">
          <template #default="{ row }">{{ row.is_trial ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ LESSON_STATUS[row.status] || row.status }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!readonly" link type="primary" @click="openLesson(row)">编辑</el-button>
            <el-button
              v-if="!readonly && row.status === 'draft'"
              link
              type="primary"
              @click="publishLesson(row)"
            >
              发布
            </el-button>
            <el-button
              v-if="!readonly && row.status === 'published'"
              link
              type="warning"
              @click="offLesson(row)"
            >
              下架
            </el-button>
            <el-button
              v-if="!readonly && row.status === 'draft'"
              link
              type="danger"
              @click="removeLesson(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="lessonVisible"
      :title="editingLesson ? '编辑课时' : '新增课时'"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="lessonForm.title" maxlength="200" />
        </el-form-item>
        <el-form-item label="媒体类型" required>
          <el-select v-model="lessonForm.media_type" style="width: 100%">
            <el-option label="视频" value="video" />
            <el-option label="音频" value="audio" />
            <el-option label="图文" value="article" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="lessonForm.media_type !== 'article'" label="媒体文件" required>
          <div class="upload-row">
            <el-button :loading="uploading" @click="fileInput?.click()">选择文件上传</el-button>
            <span v-if="lessonForm.media_name || lessonForm.media_id" class="file-name">
              {{ lessonForm.media_name || lessonForm.media_id }}
            </span>
            <span v-else class="hint">未选择文件</span>
          </div>
          <input ref="fileInput" type="file" class="hidden" @change="onPickFile" />
        </el-form-item>
        <el-form-item label="时长(秒)">
          <el-input-number v-model="lessonForm.duration_sec" :min="0" :max="86400" />
        </el-form-item>
        <el-form-item label="试看">
          <el-switch v-model="lessonForm.is_trial" />
        </el-form-item>
        <el-form-item v-if="lessonForm.is_trial" label="试看秒数">
          <el-input-number v-model="lessonForm.trial_seconds" :min="1" :max="3600" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="lessonVisible = false">取消</el-button>
        <el-button type="primary" :loading="lessonSaving" @click="saveLesson">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.status { color: var(--el-text-color-secondary); }
.actions { margin-left: auto; display: flex; gap: 8px; }
.block { margin-bottom: 12px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.upload-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.file-name { color: var(--el-color-success); }
.hint { color: var(--el-text-color-secondary); font-size: 13px; }
.hidden { display: none; }
</style>
