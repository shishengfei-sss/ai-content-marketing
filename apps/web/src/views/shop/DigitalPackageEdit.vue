<script setup>
/**
 * A06 资料包与文件。对照 PRD #a06-edit · #a06a · #a06b · #a06-deliver-mode
 * 真实选文件上传；发布走确认弹窗。文件表头排序、短时签名 URL 未做。站内信本批不接。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../composables/useListColumnSettings'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canWrite = computed(() => hasPermission(auth.permissions || [], 'shop.content.write'))
const loading = ref(false)
const saving = ref(false)
const pkg = ref(null)
const fileQuery = ref('')
const pageMode = computed(() => (route.query.mode === 'view' ? 'view' : 'edit'))
const readonly = computed(
  () => pageMode.value === 'view' || pkg.value?.status === 'off_sale' || !canWrite.value,
)
const canAddFiles = computed(() => !readonly.value && pkg.value?.status === 'draft')
const canPublish = computed(() => !readonly.value && pkg.value?.status === 'draft')
const canDeleteFile = computed(
  () =>
    !readonly.value &&
    (pkg.value?.status === 'draft' ||
      (pkg.value?.status === 'published' && (pkg.value?.ref_product_count || 0) === 0)),
)

const form = reactive({
  title: '',
  deliver_mode: 'download',
  max_downloads: null,
})
const STATUS_LABEL = { draft: '草稿', published: '已发布', off_sale: '已下架' }
const DELIVER_LABEL = { download: '下载', online_view: '在线查看' }
const ALLOWED_EXT = ['.pdf', '.doc', '.docx', '.zip']
const MAX_BYTES = 50 * 1024 * 1024
const MAX_FILES = 20

const COL_STORAGE = 'shop.a06.files'
const ALL_COLS = [
  { key: 'file_name', label: '文件', locked: true, defaultOn: true },
  { key: 'size_bytes', label: '大小', defaultOn: true },
  { key: 'created_at', label: '上传时间', defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const {
  visibleKeys,
  columnDialogVisible: colDialog,
  columnDraft,
  openColumnSettings,
  saveColumnSettings,
  isColVisible,
} = useListColumnSettings(ALL_COLS, COL_STORAGE)

const assets = computed(() => pkg.value?.assets || [])
const filteredAssets = computed(() => {
  const q = fileQuery.value.trim().toLowerCase()
  if (!q) return assets.value
  return assets.value.filter((a) => String(a.file_name || '').toLowerCase().includes(q))
})
const previewableCount = computed(
  () => assets.value.filter((a) => a.previewable).length,
)
const fileCount = computed(() => pkg.value?.file_count || assets.value.length)
const totalBytes = computed(() => assets.value.reduce((s, a) => s + (a.size_bytes || 0), 0))
const onlineViewWarn = computed(
  () => form.deliver_mode === 'online_view' && previewableCount.value < 1,
)

const uploadDlg = reactive({
  visible: false,
  busy: false,
  items: [],
})
const fileInput = ref(null)
const publishDlg = reactive({ visible: false, busy: false })
const removeDlg = reactive({ visible: false, busy: false, row: null })
const docPreviewDlg = reactive({ visible: false, title: '', html: '' })

function extOf(name) {
  const n = String(name || '').toLowerCase()
  const i = n.lastIndexOf('.')
  return i >= 0 ? n.slice(i) : ''
}
function isAllowed(name) {
  return ALLOWED_EXT.includes(extOf(name))
}
function isZip(row) {
  return extOf(row?.file_name) === '.zip' || String(row?.mime || '').includes('zip')
}
function fmtSize(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n}B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)}KB`
  return `${(n / (1024 * 1024)).toFixed(1)}MB`
}
function fmtTime(v) {
  if (!v) return '—'
  const s = String(v).replace('T', ' ')
  const m = s.match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  if (!m) return s.slice(0, 16)
  return `${m[2]}-${m[3]} ${m[4]}:${m[5]}`
}

function publishBlockedReason() {
  if (!form.title.trim()) return '请填写标题'
  if (fileCount.value < 1) return '请添加至少 1 个文件'
  if (form.deliver_mode === 'online_view' && previewableCount.value < 1) {
    return '在线查看须至少 1 个 pdf/doc 文件'
  }
  return ''
}

async function load(options = {}) {
  const { keepForm = false } = options
  loading.value = true
  try {
    const { data } = await api.get(`/api/v1/shop/digital-packages/${route.params.id}`)
    pkg.value = data
    if (!keepForm) {
      form.title = data.title
      form.deliver_mode = data.deliver_mode
      form.max_downloads = data.max_downloads ?? null
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function formDirty() {
  if (!pkg.value) return false
  return (
    form.title.trim() !== (pkg.value.title || '') ||
    form.deliver_mode !== pkg.value.deliver_mode ||
    (form.max_downloads ?? null) !== (pkg.value.max_downloads ?? null)
  )
}

async function save() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return false
  }
  saving.value = true
  try {
    const { data } = await api.patch(`/api/v1/shop/digital-packages/${route.params.id}`, {
      title: form.title.trim(),
      deliver_mode: form.deliver_mode,
      max_downloads: form.max_downloads || null,
    })
    pkg.value = data
    ElMessage.success('已保存')
    return true
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
    return false
  } finally {
    saving.value = false
  }
}

function openPublish() {
  const reason = publishBlockedReason()
  if (reason) {
    ElMessage.warning(reason)
    return
  }
  publishDlg.visible = true
}

async function confirmPublish() {
  const reason = publishBlockedReason()
  if (reason) {
    ElMessage.warning(reason)
    return
  }
  publishDlg.busy = true
  try {
    if (formDirty()) {
      const ok = await save()
      if (!ok) return
    }
    const { data } = await api.post(`/api/v1/shop/digital-packages/${route.params.id}/publish`)
    pkg.value = data
    publishDlg.visible = false
    ElMessage.success('已发布')
    router.push({ name: 'ShopDigitalPackages', query: { status: 'published' } })
  } catch (e) {
    ElMessage.error(e.message || '发布失败')
  } finally {
    publishDlg.busy = false
  }
}

function openUpload() {
  if (!canAddFiles.value) {
    ElMessage.warning(pkg.value?.status === 'published' ? '已发布/已下架不可添加' : '无编辑权限')
    return
  }
  if (fileCount.value >= MAX_FILES) {
    ElMessage.warning('包内最多 20 个文件')
    return
  }
  uploadDlg.items = []
  uploadDlg.visible = true
}

function addPendingFiles(fileList) {
  const room = MAX_FILES - fileCount.value - uploadDlg.items.length
  const files = Array.from(fileList || [])
  for (const file of files.slice(0, Math.max(0, room))) {
    if (!isAllowed(file.name)) {
      ElMessage.warning('仅支持 pdf/doc/docx/zip')
      continue
    }
    if (file.size > MAX_BYTES) {
      ElMessage.warning('文件过大')
      continue
    }
    uploadDlg.items.push({
      uid: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: file.name,
      size: file.size,
      raw: file,
      status: 'ready',
      percent: 0,
      error: '',
    })
  }
  if (files.length > Math.max(0, room)) {
    ElMessage.warning('包内最多 20 个文件')
  }
}

function onFileInput(ev) {
  addPendingFiles(ev.target.files)
  ev.target.value = ''
}

function onDrop(ev) {
  addPendingFiles(ev.dataTransfer?.files)
}

function removePending(uid) {
  uploadDlg.items = uploadDlg.items.filter((x) => x.uid !== uid)
}

async function uploadOne(item) {
  item.status = 'uploading'
  item.percent = 0
  item.error = ''
  const fd = new FormData()
  fd.append('file', item.raw)
  const { data: up } = await api.post('/api/v1/shop/content/files', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total) item.percent = Math.round((e.loaded / e.total) * 100)
    },
  })
  if (!up?.file_id) {
    throw new Error('请先选择并上传文件')
  }
  await api.post(`/api/v1/shop/digital-packages/${route.params.id}/assets`, {
    file_id: up.file_id,
    file_name: up.file_name || item.name,
    file_url: up.file_url,
    mime: up.mime,
    size_bytes: up.size_bytes,
  })
  item.status = 'done'
  item.percent = 100
  if (form.deliver_mode === 'online_view' && extOf(item.name) === '.zip') {
    ElMessage.success('zip 在在线查看模式下买家仅可下载')
  }
}

async function startUpload() {
  if (!uploadDlg.items.length) {
    ElMessage.warning('请选择文件')
    return
  }
  uploadDlg.busy = true
  try {
    for (const item of uploadDlg.items) {
      if (item.status === 'done') continue
      try {
        await uploadOne(item)
      } catch (e) {
        item.status = 'fail'
        item.error = e.message || '上传失败'
      }
    }
    const failed = uploadDlg.items.filter((x) => x.status === 'fail')
    await load({ keepForm: true })
    if (!failed.length) {
      uploadDlg.visible = false
      ElMessage.success('文件已添加')
    }
  } finally {
    uploadDlg.busy = false
  }
}

async function retryOne(item) {
  try {
    await uploadOne(item)
    await load({ keepForm: true })
  } catch (e) {
    item.status = 'fail'
    item.error = e.message || '上传失败'
  }
}

function openRemove(row) {
  if (!canDeleteFile.value) {
    ElMessage.warning(
      (pkg.value?.ref_product_count || 0) > 0 ? '存在商品引用不可删' : '无编辑权限',
    )
    return
  }
  removeDlg.row = row
  removeDlg.visible = true
}

async function confirmRemove() {
  const row = removeDlg.row
  if (!row) return
  removeDlg.busy = true
  try {
    await api.delete(`/api/v1/shop/digital-packages/${route.params.id}/assets/${row.id}`)
    ElMessage.success('已移除')
    removeDlg.visible = false
    await load({ keepForm: true })
  } catch (e) {
    ElMessage.error(e.message || '移除失败')
  } finally {
    removeDlg.busy = false
  }
}

async function preview(row) {
  if (isZip(row)) {
    ElMessage.info('zip 请下载后本地解压')
    return
  }
  const ext = extOf(row.file_name)
  if (ext === '.doc') {
    ElMessage.info('旧版 .doc 请下载后用 Word 打开')
    return
  }
  try {
    if (ext === '.docx') {
      const { data: html } = await api.get(`/api/v1/shop/content/files/${row.file_id}/html-preview`, {
        responseType: 'text',
      })
      docPreviewDlg.title = row.file_name || 'Word 文档'
      docPreviewDlg.html = html || ''
      docPreviewDlg.visible = true
      return
    }
    const res = await api.get(`/api/v1/shop/content/files/${row.file_id}`, { responseType: 'blob' })
    const type = ext === '.pdf' ? 'application/pdf' : res.data?.type || 'application/octet-stream'
    const url = URL.createObjectURL(
      res.data instanceof Blob ? res.data : new Blob([res.data], { type }),
    )
    window.open(url, '_blank')
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" data-testid="shop-package-edit">
    <div class="toolbar">
      <el-button link type="primary" @click="router.push({ name: 'ShopDigitalPackages' })">
        ← 返回列表
      </el-button>
      <strong>{{ pkg?.title || '编辑资料包' }}</strong>
      <el-tag size="small">{{ STATUS_LABEL[pkg?.status] || '' }}</el-tag>
      <span class="meta">{{ fileCount }} 个文件 · 约 {{ fmtSize(totalBytes) }}</span>
      <el-tag v-if="readonly" size="small" type="info">只读</el-tag>
      <div style="flex: 1" />
      <el-button v-if="!readonly" :loading="saving" @click="save">保存</el-button>
      <el-button
        v-if="canPublish"
        type="primary"
        :disabled="!!publishBlockedReason()"
        @click="openPublish"
      >
        发布
      </el-button>
    </div>

    <el-form label-width="120px" style="max-width: 640px; margin-top: 16px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" :disabled="readonly" maxlength="200" />
      </el-form-item>
      <el-form-item label="交付方式">
        <el-radio-group v-model="form.deliver_mode" :disabled="readonly">
          <el-radio value="download">下载</el-radio>
          <el-radio value="online_view">在线查看</el-radio>
        </el-radio-group>
        <div class="hint">在线查看：pdf/doc 可预览 · zip 仅下载</div>
        <el-alert
          v-if="onlineViewWarn"
          title="当前包内无可在线预览文件，买家 zip 仅可下载；建议补充 pdf/doc 或改回下载模式"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 8px"
        />
      </el-form-item>
      <el-form-item label="最大下载次数">
        <el-input-number
          v-model="form.max_downloads"
          :min="1"
          :max="9999"
          :disabled="readonly"
          placeholder="不限"
          :controls="false"
        />
        <span class="hint" style="margin-left: 8px">空=不限；仅约束下载，预览不计次</span>
      </el-form-item>
    </el-form>

    <div class="section-hd">包内文件</div>
    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="fileQuery"
          clearable
          placeholder="搜索文件名"
          style="width: 200px"
        />
      </div>
      <div class="right">
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button v-if="canAddFiles" type="primary" @click="openUpload">+ 添加文件</el-button>
      </div>
    </div>
    <el-table :data="filteredAssets" border stripe size="small" style="margin-top: 8px">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column
        v-if="colKey === 'file_name'"
        prop="file_name"
        label="文件"
        min-width="180"
      />
      <el-table-column v-if="colKey === 'size_bytes'" label="大小" width="100">
        <template #default="{ row }">{{ fmtSize(row.size_bytes) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'created_at'" label="上传时间" width="130">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'ops'" label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="preview(row)">预览</el-button>
          <el-button v-if="canDeleteFile" link type="danger" @click="openRemove(row)">删除</el-button>
        </template>
      </el-table-column>
      </template>
    </el-table>

    <el-dialog
      v-model="uploadDlg.visible"
      :title="`添加文件到「${pkg?.title || ''}」`"
      width="520px"
    >
      <el-form label-width="100px">
        <el-form-item label="上传文件" required>
          <div
            class="drop"
            @click="fileInput?.click()"
            @dragover.prevent
            @drop.prevent="onDrop"
          >
            点击或拖拽上传 · pdf/doc/docx/zip · 单文件 ≤50MB
          </div>
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            multiple
            accept=".pdf,.doc,.docx,.zip,application/pdf,application/zip"
            @change="onFileInput"
          />
          <div v-for="item in uploadDlg.items" :key="item.uid" class="pend">
            <span>{{ item.name }} · {{ fmtSize(item.size) }}</span>
            <el-progress
              v-if="item.status === 'uploading' || item.status === 'done'"
              :percentage="item.percent"
              :status="item.status === 'done' ? 'success' : undefined"
              style="width: 140px"
            />
            <el-tag v-if="item.status === 'fail'" type="danger" size="small">{{ item.error || '失败' }}</el-tag>
            <el-button v-if="item.status === 'fail'" link type="primary" @click="retryOne(item)">重试</el-button>
            <el-button
              v-if="item.status === 'ready'"
              link
              type="danger"
              @click="removePending(item.uid)"
            >
              移除
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDlg.visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="uploadDlg.busy"
          :disabled="!uploadDlg.items.length"
          @click="startUpload"
        >
          开始上传
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="publishDlg.visible"
      :title="`确认发布「${pkg?.title || ''}」？`"
      width="480px"
    >
      <div class="dlg-field">
        <div class="dlg-lab">发布说明（只读）</div>
        <div class="dlg-val">
          包内文件 <b>{{ fileCount }}</b> 个（可预览 {{ previewableCount }} · 仅下载
          {{ Math.max(0, fileCount - previewableCount) }}）；交付方式：<b>{{
            DELIVER_LABEL[form.deliver_mode] || form.deliver_mode
          }}</b>；发布后商品可关联售卖
        </div>
      </div>
      <template #footer>
        <el-button @click="publishDlg.visible = false">取消</el-button>
        <el-button type="primary" :loading="publishDlg.busy" @click="confirmPublish">确认发布</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="removeDlg.visible"
      :title="`确认移除「${removeDlg.row?.file_name || ''}」？`"
      width="420px"
    >
      <div class="dlg-field">
        <div class="dlg-lab">删除影响（只读）</div>
        <div class="dlg-val">删除后不可从本包下载该文件；已购买家下载记录保留</div>
      </div>
      <template #footer>
        <el-button @click="removeDlg.visible = false">取消</el-button>
        <el-button type="danger" :loading="removeDlg.busy" @click="confirmRemove">确认删除</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="docPreviewDlg.visible"
      :title="docPreviewDlg.title || '文档预览'"
      width="720px"
    >
      <div class="doc-preview-body" v-html="docPreviewDlg.html" />
      <template #footer>
        <el-button @click="docPreviewDlg.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="columnDraft"
      @save="() => { saveColumnSettings(); ElMessage.success('列设置已保存') }"
    />

  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.left,
.right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.toolbar .right {
  margin-left: auto;
}
.meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.45;
  margin-top: 4px;
}
.section-hd {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}
.drop {
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
  padding: 24px 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  background: var(--el-fill-color-lighter);
}
.hidden {
  display: none;
}
.pend {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
}
.dlg-field {
  margin-bottom: 8px;
}
.dlg-lab {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.dlg-val {
  line-height: 1.6;
  font-size: 13px;
}
.doc-preview-body {
  max-height: 60vh;
  overflow: auto;
  padding: 4px 8px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
</style>
