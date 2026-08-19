<script setup>
/**
 * A04/A05 专栏编辑 + 课时。对照 PRD 01-管理端UI.html #a04-edit · #a05 · #a05a · #a05-upload-spec
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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

const LESSON_MEDIA_SPEC = {
  video: {
    accept: '.mp4,.mov',
    purpose: 'lesson_video',
    hint: 'mp4 / mov（H.264 推荐）· 单文件 ≤2GB · 单节时长 ≤180 分钟',
    maxBytes: 2 * 1024 * 1024 * 1024,
    exts: ['.mp4', '.mov'],
    reject: '视频仅支持 mp4、mov，且不超过 2GB',
  },
  audio: {
    accept: '.mp3,.m4a,.aac,.wav',
    purpose: 'lesson_audio',
    hint: 'mp3 / m4a / aac / wav · 单文件 ≤200MB',
    maxBytes: 200 * 1024 * 1024,
    exts: ['.mp3', '.m4a', '.aac', '.wav'],
    reject: '音频仅支持 mp3、m4a、aac、wav，且不超过 200MB',
  },
}
const ARTICLE_SPEC =
  '富文本正文 ≤50,000 字；去标签后至少 10 字可发布。内嵌图 jpg/png/gif · ≤5MB/张 · ≤20 张（可用下方插入图片）。'
const ARTICLE_IMAGE_SPEC = {
  accept: '.jpg,.jpeg,.png,.gif',
  purpose: 'article_image',
  maxBytes: 5 * 1024 * 1024,
  exts: ['.jpg', '.jpeg', '.png', '.gif'],
  reject: '内嵌图仅支持 jpg、png、gif，且不超过 5MB',
}
const MAX_VIDEO_DURATION_SEC = 180 * 60
const MAX_CONTENT_BODY = 50000

const lessonVisible = ref(false)
const lessonSaving = ref(false)
const editingLesson = ref(null)
const lessonForm = reactive({
  title: '',
  media_type: 'video',
  media_id: '',
  media_url: '',
  media_name: '',
  content_body: '',
  duration_sec: 0,
  is_trial: false,
  trial_seconds: 180,
})
const uploading = ref(false)
const imageUploading = ref(false)
const fileInput = ref(null)
const imageInput = ref(null)

const mediaSpec = computed(() => LESSON_MEDIA_SPEC[lessonForm.media_type] || null)
const plainTextLen = computed(() => {
  const text = (lessonForm.content_body || '').replace(/<[^>]+>/g, '').trim()
  return text.length
})
const articleImageCount = computed(() => (lessonForm.content_body.match(/<img\b/gi) || []).length)

function extOf(name) {
  const n = String(name || '').toLowerCase()
  const i = n.lastIndexOf('.')
  return i >= 0 ? n.slice(i) : ''
}

function validateMediaFile(file, spec) {
  const ext = extOf(file.name)
  if (!spec.exts.includes(ext)) {
    ElMessage.warning(spec.reject)
    return false
  }
  if (file.size > spec.maxBytes) {
    ElMessage.warning(spec.reject)
    return false
  }
  return true
}

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

function resetLessonMedia() {
  lessonForm.media_id = ''
  lessonForm.media_url = ''
  lessonForm.media_name = ''
}

function openLesson(row = null) {
  editingLesson.value = row
  if (row) {
    lessonForm.title = row.title
    lessonForm.media_type = row.media_type
    lessonForm.media_id = row.media_id || ''
    lessonForm.media_url = row.media_url || ''
    lessonForm.media_name = row.media_id ? row.media_name || '已上传媒体' : ''
    lessonForm.content_body = row.content_body || ''
    lessonForm.duration_sec = row.duration_sec || 0
    lessonForm.is_trial = !!row.is_trial
    lessonForm.trial_seconds = row.trial_seconds || 180
  } else {
    lessonForm.title = ''
    lessonForm.media_type = 'video'
    lessonForm.content_body = ''
    lessonForm.duration_sec = 0
    lessonForm.is_trial = false
    lessonForm.trial_seconds = 180
    resetLessonMedia()
  }
  lessonVisible.value = true
}

watch(
  () => lessonForm.media_type,
  (type, prev) => {
    if (!lessonVisible.value || type === prev) return
    if (type === 'article') {
      resetLessonMedia()
      lessonForm.duration_sec = 0
      lessonForm.is_trial = false
    } else {
      lessonForm.content_body = ''
      if (type !== 'video') lessonForm.is_trial = false
    }
  },
)

async function uploadWithPurpose(file, purpose) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post('/api/v1/shop/content/files', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { purpose },
  })
  return data
}

async function onPickFile(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  const spec = mediaSpec.value
  if (!spec || !validateMediaFile(file, spec)) return
  uploading.value = true
  try {
    const data = await uploadWithPurpose(file, spec.purpose)
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

async function onPickArticleImage(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  if (articleImageCount.value >= 20) {
    ElMessage.warning('内嵌图不能超过 20 张')
    return
  }
  if (!validateMediaFile(file, ARTICLE_IMAGE_SPEC)) return
  imageUploading.value = true
  try {
    const data = await uploadWithPurpose(file, ARTICLE_IMAGE_SPEC.purpose)
    const url = data.file_url || `/api/v1/shop/content/files/${data.file_id}`
    const tag = `<p><img src="${url}" alt="${data.file_name || '图片'}" /></p>`
    lessonForm.content_body = `${lessonForm.content_body || ''}${tag}`
    ElMessage.success('图片已插入正文')
  } catch (e) {
    ElMessage.error(e.message || '图片上传失败')
  } finally {
    imageUploading.value = false
  }
}

function validateLessonForm() {
  if (!lessonForm.title.trim()) {
    ElMessage.warning('请填写课时标题')
    return false
  }
  if (lessonForm.media_type === 'article') {
    if ((lessonForm.content_body || '').length > MAX_CONTENT_BODY) {
      ElMessage.warning('正文不能超过 50000 字')
      return false
    }
    if (plainTextLen.value < 10) {
      ElMessage.warning('图文正文至少 10 字')
      return false
    }
    if (articleImageCount.value > 20) {
      ElMessage.warning('内嵌图不能超过 20 张')
      return false
    }
    return true
  }
  if (!lessonForm.media_id && !lessonForm.media_url) {
    ElMessage.warning('请先上传媒体文件')
    return false
  }
  if (lessonForm.media_type === 'video' && lessonForm.duration_sec > MAX_VIDEO_DURATION_SEC) {
    ElMessage.warning('视频时长不能超过 180 分钟')
    return false
  }
  if (lessonForm.is_trial && lessonForm.media_type === 'video' && !lessonForm.trial_seconds) {
    ElMessage.warning('请填写试看秒数')
    return false
  }
  return true
}

async function saveLesson() {
  if (!validateLessonForm()) return
  lessonSaving.value = true
  try {
    const body = {
      title: lessonForm.title.trim(),
      media_type: lessonForm.media_type,
      duration_sec: lessonForm.media_type === 'article' ? 0 : Number(lessonForm.duration_sec) || 0,
      is_trial: lessonForm.media_type === 'video' ? lessonForm.is_trial : false,
      trial_seconds:
        lessonForm.media_type === 'video' && lessonForm.is_trial
          ? Number(lessonForm.trial_seconds) || 180
          : undefined,
    }
    if (lessonForm.media_type === 'article') {
      body.content_body = lessonForm.content_body || ''
    } else {
      body.media_id = lessonForm.media_id || undefined
      body.media_url = lessonForm.media_url || undefined
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
      width="620px"
      destroy-on-close
    >
      <el-form label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="lessonForm.title" maxlength="200" />
        </el-form-item>
        <el-form-item label="媒体类型" required>
          <el-select
            v-model="lessonForm.media_type"
            style="width: 100%"
            :disabled="!!editingLesson"
          >
            <el-option label="视频" value="video" />
            <el-option label="音频" value="audio" />
            <el-option label="图文" value="article" />
          </el-select>
          <p v-if="editingLesson" class="field-hint">保存后不可修改媒体类型</p>
        </el-form-item>

        <template v-if="lessonForm.media_type === 'article'">
          <el-form-item label="正文" required>
            <el-input
              v-model="lessonForm.content_body"
              type="textarea"
              :rows="8"
              :maxlength="MAX_CONTENT_BODY"
              show-word-limit
              placeholder="请输入图文正文，至少 10 字；支持简单 HTML"
            />
            <p class="field-hint">{{ ARTICLE_SPEC }}</p>
            <p class="field-meta">
              当前正文 {{ plainTextLen }} 字（去标签）· 内嵌图 {{ articleImageCount }} / 20 张
            </p>
            <div class="upload-row">
              <el-button :loading="imageUploading" @click="imageInput?.click()">插入图片</el-button>
              <input
                ref="imageInput"
                type="file"
                class="hidden"
                :accept="ARTICLE_IMAGE_SPEC.accept"
                @change="onPickArticleImage"
              />
            </div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="媒体文件" required>
            <div class="upload-row">
              <el-button :loading="uploading" @click="fileInput?.click()">选择文件上传</el-button>
              <span v-if="lessonForm.media_name || lessonForm.media_id" class="file-name">
                {{ lessonForm.media_name || lessonForm.media_id }}
              </span>
              <span v-else class="hint">未选择文件</span>
            </div>
            <p v-if="mediaSpec" class="field-hint">{{ mediaSpec.hint }}</p>
            <input
              ref="fileInput"
              type="file"
              class="hidden"
              :accept="mediaSpec?.accept"
              @change="onPickFile"
            />
          </el-form-item>
          <el-form-item v-if="lessonForm.media_type === 'video'" label="时长(秒)">
            <el-input-number v-model="lessonForm.duration_sec" :min="0" :max="MAX_VIDEO_DURATION_SEC" />
            <p class="field-hint">视频须填写时长，最长 180 分钟（10800 秒）</p>
          </el-form-item>
          <el-form-item v-else-if="lessonForm.media_type === 'audio'" label="时长(秒)">
            <el-input-number v-model="lessonForm.duration_sec" :min="0" :max="86400" />
          </el-form-item>
        </template>

        <template v-if="lessonForm.media_type === 'video'">
          <el-form-item label="试看">
            <el-switch v-model="lessonForm.is_trial" />
          </el-form-item>
          <el-form-item v-if="lessonForm.is_trial" label="试看秒数">
            <el-select v-model="lessonForm.trial_seconds" style="width: 160px">
              <el-option label="60 秒" :value="60" />
              <el-option label="180 秒（默认）" :value="180" />
              <el-option label="300 秒" :value="300" />
              <el-option label="600 秒" :value="600" />
            </el-select>
          </el-form-item>
        </template>
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
.field-hint { margin: 6px 0 0; font-size: 12px; line-height: 1.5; color: var(--el-text-color-secondary); }
.field-meta { margin: 4px 0 0; font-size: 12px; color: var(--el-text-color-placeholder); }
.hidden { display: none; }
</style>
