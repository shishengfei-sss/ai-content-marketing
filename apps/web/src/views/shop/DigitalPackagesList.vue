<script setup>
/**
 * A06 资料包列表。对照 PRD 01-管理端UI.html #a06 · #a06b · #a06d · 04#select-common
 * 默认列：标题·文件数·引用商品·状态·更新时间·操作；交付方式进列设置（可选）。
 * 缺口：导出完成站内信本批不接；已下架资料包再发布本批不接。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'

const router = useRouter()
const auth = useAuthStore()
const { currentId } = useCurrentShop()
const canWrite = computed(() => hasPermission(auth.permissions || [], 'shop.content.write'))
const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const exportScope = ref('当前筛选')
const creating = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const createVisible = ref(false)
const form = reactive({ title: '', deliver_mode: 'download', max_downloads: undefined })

const dlg = reactive({
  visible: false,
  kind: '', // publish | delete | off
  row: null,
  busy: false,
})

const query = reactive({ page: 1, page_size: 20, status: '', q: '' })

const COL_STORAGE = 'shop.a06.packages'
const ALL_COLS = [
  { key: 'title', label: '标题', locked: true, defaultOn: true },
  { key: 'deliver_mode', label: '交付方式', locked: false, defaultOn: true },
  { key: 'file_count', label: '文件数', locked: true, defaultOn: true },
  { key: 'ref_product_count', label: '引用商品', locked: true, defaultOn: true },
  { key: 'status', label: '状态', locked: true, defaultOn: true },
  { key: 'updated_at', label: '更新时间', locked: true, defaultOn: true },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
function loadColPrefs() {
  try {
    const raw = localStorage.getItem(COL_STORAGE)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return Object.fromEntries(ALL_COLS.map((c) => [c.key, c.defaultOn]))
}
const colVisible = reactive(loadColPrefs())
const colDialog = ref(false)
const colDraft = reactive({ ...colVisible })
const STATUS_LABEL = { draft: '草稿', published: '已发布', off_sale: '已下架' }
const DELIVER_LABEL = { download: '下载', online_view: '在线查看' }
const STATUS_TABS = [
  { key: '', label: '全部资料包' },
  { key: 'draft', label: '草稿' },
  { key: 'published', label: '已发布' },
  { key: 'off_sale', label: '已下架' },
]
const visibleCols = computed(() => ALL_COLS.filter((c) => colVisible[c.key] || c.locked))

function listParams() {
  return {
    page: query.page,
    page_size: query.page_size,
    status: query.status || undefined,
    q: query.q || undefined,
    shop_id: currentId.value || undefined,
  }
}

function tabCount(key) {
  if (!key) return statusCounts.value.all ?? total.value
  return statusCounts.value[key] ?? 0
}

function setTab(key) {
  query.status = key
  query.page = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/digital-packages', { params: listParams() })
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.title = ''
  form.deliver_mode = 'download'
  form.max_downloads = undefined
  createVisible.value = true
}

async function createPkg() {
  const title = form.title.trim()
  if (!title) {
    ElMessage.warning('请填写标题')
    return
  }
  creating.value = true
  try {
    const body = {
      title,
      deliver_mode: form.deliver_mode,
      shop_id: currentId.value || undefined,
    }
    if (form.deliver_mode === 'download' && form.max_downloads) {
      body.max_downloads = form.max_downloads
    }
    const { data } = await api.post('/api/v1/shop/digital-packages', body)
    ElMessage.success('已创建草稿')
    createVisible.value = false
    router.push({ name: 'ShopDigitalPackageEdit', params: { id: data.id }, query: { mode: 'edit' } })
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

function openPublish(row) {
  if ((row.file_count || 0) < 1) {
    ElMessage.warning('请添加至少 1 个文件')
    return
  }
  if (row.deliver_mode === 'online_view' && (row.previewable_count || 0) < 1) {
    ElMessage.warning('在线查看须至少 1 个 pdf/doc 文件')
    return
  }
  dlg.kind = 'publish'
  dlg.row = row
  dlg.visible = true
}

function openDelete(row) {
  dlg.kind = 'delete'
  dlg.row = row
  dlg.visible = true
}

function openOffSale(row) {
  dlg.kind = 'off'
  dlg.row = row
  dlg.visible = true
}

async function confirmDlg() {
  const row = dlg.row
  if (!row) return
  dlg.busy = true
  try {
    if (dlg.kind === 'publish') {
      await api.post(`/api/v1/shop/digital-packages/${row.id}/publish`)
      ElMessage.success('已发布')
    } else if (dlg.kind === 'delete') {
      await api.delete(`/api/v1/shop/digital-packages/${row.id}`)
      ElMessage.success('已删除')
    } else if (dlg.kind === 'off') {
      await api.post(`/api/v1/shop/digital-packages/${row.id}/off-sale`)
      ElMessage.success('已下架')
    }
    dlg.visible = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    dlg.busy = false
  }
}

function goView(row) {
  router.push({ name: 'ShopDigitalPackageEdit', params: { id: row.id }, query: { mode: 'view' } })
}
function goEdit(row) {
  router.push({ name: 'ShopDigitalPackageEdit', params: { id: row.id }, query: { mode: 'edit' } })
}
function saveCols() {
  Object.assign(colVisible, colDraft)
  localStorage.setItem(COL_STORAGE, JSON.stringify(colVisible))
  colDialog.value = false
}

function visibleExportColumns() {
  return ALL_COLS.filter((c) => c.key !== 'ops' && colVisible[c.key]).map((c) => c.key)
}

async function exportCsv(mode) {
  exporting.value = true
  try {
    const body = { ...listParams() }
    delete body.page
    delete body.page_size
    if (mode === 'columns') {
      body.columns = visibleExportColumns()
    }
    const { data } = await api.post('/api/v1/shop/digital-packages/export', body)
    exportTask.value = data
    exportScope.value = mode === 'columns' ? '列配置' : '当前筛选'
    exportDialog.value = true
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function downloadExportFile() {
  if (!exportTask.value?.id) return
  try {
    const res = await api.get(`/api/v1/shop/digital-packages/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-digital-packages.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

watch(currentId, () => {
  query.page = 1
  load()
})

onMounted(load)
</script>

<template>
  <div v-loading="loading" data-testid="shop-packages">
    <div class="tabs">
      <button
        v-for="t in STATUS_TABS"
        :key="t.key || 'all'"
        type="button"
        class="tab"
        :class="{ on: query.status === t.key }"
        @click="setTab(t.key)"
      >
        {{ t.label }}
        <span v-if="t.key" class="cnt">{{ tabCount(t.key) }}</span>
      </button>
    </div>

    <div class="toolbar">
      <div class="left">
        <el-input
          v-model="query.q"
          clearable
          placeholder="搜索标题"
          style="width: 200px"
          @change="() => { query.page = 1; load() }"
        />
        <el-select
          v-model="query.status"
          clearable
          placeholder="状态"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="已下架" value="off_sale" />
        </el-select>
      </div>
      <div class="right">
        <el-dropdown trigger="click" @command="exportCsv">
          <el-button :loading="exporting">导出 ▾</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="current">当前筛选</el-dropdown-item>
              <el-dropdown-item command="columns">列配置</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="colDialog = true">列设置</el-button>
        <el-button v-if="canWrite" type="primary" @click="openCreate">+ 新建资料包</el-button>
      </div>
    </div>

    <el-table :data="items" border stripe size="small" style="margin-top: 12px">
      <el-table-column v-if="visibleCols.some((c) => c.key === 'title')" prop="title" label="标题" min-width="160" />
      <el-table-column v-if="visibleCols.some((c) => c.key === 'deliver_mode')" label="交付方式" width="110">
        <template #default="{ row }">{{ DELIVER_LABEL[row.deliver_mode] || row.deliver_mode }}</template>
      </el-table-column>
      <el-table-column v-if="visibleCols.some((c) => c.key === 'file_count')" prop="file_count" label="文件数" width="90" />
      <el-table-column v-if="visibleCols.some((c) => c.key === 'ref_product_count')" prop="ref_product_count" label="引用商品" width="100" />
      <el-table-column v-if="visibleCols.some((c) => c.key === 'status')" label="状态" width="100">
        <template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template>
      </el-table-column>
      <el-table-column v-if="visibleCols.some((c) => c.key === 'updated_at')" prop="updated_at" label="更新时间" min-width="160" />
      <el-table-column v-if="visibleCols.some((c) => c.key === 'ops')" label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goView(row)">查看</el-button>
          <el-button
            v-if="canWrite && row.status !== 'off_sale'"
            link
            type="primary"
            @click="goEdit(row)"
          >编辑</el-button>
          <el-button
            v-if="canWrite && row.status === 'draft'"
            link
            type="primary"
            :disabled="(row.file_count || 0) < 1"
            @click="openPublish(row)"
          >发布</el-button>
          <el-button
            v-if="canWrite && row.status === 'published'"
            link
            type="warning"
            @click="openOffSale(row)"
          >下架</el-button>
          <el-button
            v-if="canWrite && row.status === 'draft'"
            link
            type="danger"
            @click="openDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="load"
      />
    </div>

    <el-drawer v-model="createVisible" title="新建资料包" size="420px" destroy-on-close>
      <el-form label-width="110px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="200" placeholder="请输入资料包标题" />
        </el-form-item>
        <el-form-item label="交付方式" required>
          <el-select v-model="form.deliver_mode" style="width: 100%">
            <el-option label="下载" value="download" />
            <el-option label="在线查看" value="online_view" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.deliver_mode === 'download'" label="最大下载次数">
          <el-input-number v-model="form.max_downloads" :min="1" :max="9999" :controls="false" placeholder="不限" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createPkg">创建并编辑</el-button>
      </template>
    </el-drawer>

    <el-dialog
      v-model="dlg.visible"
      :title="
        dlg.kind === 'publish'
          ? `确认发布「${dlg.row?.title || ''}」？`
          : dlg.kind === 'delete'
            ? `确认删除「${dlg.row?.title || ''}」？`
            : `确认下架资料包「${dlg.row?.title || ''}」？`
      "
      width="480px"
    >
      <div v-if="dlg.kind === 'publish'" class="dlg-field">
        <div class="dlg-lab">发布说明（只读）</div>
        <div class="dlg-val">
          包内文件 <b>{{ dlg.row?.file_count || 0 }}</b> 个（可预览 {{ dlg.row?.previewable_count || 0 }} · 仅下载 {{ Math.max(0, (dlg.row?.file_count || 0) - (dlg.row?.previewable_count || 0)) }}）；交付方式：<b>{{ DELIVER_LABEL[dlg.row?.deliver_mode] || dlg.row?.deliver_mode }}</b>；发布后商品可关联售卖
        </div>
      </div>
      <div v-else-if="dlg.kind === 'delete'" class="dlg-field">
        <div class="dlg-lab">删除影响（只读）</div>
        <div class="dlg-val danger">
          删除后不可恢复；须无商品引用（当前引用商品 <b>{{ dlg.row?.ref_product_count || 0 }}</b>）
        </div>
      </div>
      <div v-else-if="dlg.kind === 'off'" class="dlg-field">
        <div class="dlg-lab">下架影响（只读）</div>
        <div class="dlg-val warn">
          · 新建数字商品不可再选本包<br>
          · 已关联商品 <b>{{ dlg.row?.ref_product_count || 0 }}</b> 个：引用保留<br>
          · 已购买家可继续下载（权益不关）<br>
          · 编辑页变为只读；不可再发布
        </div>
      </div>
      <template #footer>
        <el-button @click="dlg.visible = false">取消</el-button>
        <el-button
          v-if="dlg.kind === 'publish'"
          type="primary"
          :loading="dlg.busy"
          :disabled="(dlg.row?.file_count || 0) < 1"
          @click="confirmDlg"
        >确认发布</el-button>
        <el-button
          v-else-if="dlg.kind === 'delete'"
          type="danger"
          :loading="dlg.busy"
          :disabled="(dlg.row?.ref_product_count || 0) > 0"
          @click="confirmDlg"
        >确认删除</el-button>
        <el-button
          v-else
          type="warning"
          :loading="dlg.busy"
          @click="confirmDlg"
        >确认下架</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="colDialog" title="列设置" width="360px">
      <el-checkbox v-for="c in ALL_COLS" :key="c.key" v-model="colDraft[c.key]" :disabled="c.locked" style="display: block; margin: 6px 0">
        {{ c.label }}
      </el-checkbox>
      <template #footer>
        <el-button @click="colDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCols">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog" title="导出任务" width="420px">
      <el-form v-if="exportTask" label-width="100px">
        <el-form-item label="范围">{{ exportScope }}</el-form-item>
        <el-form-item label="条数">{{ exportTask.row_count ?? 0 }} 条</el-form-item>
        <el-form-item label="状态">{{ exportTask.status === 'done' ? '已完成' : (exportTask.status || '—') }}</el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :disabled="exportTask?.status !== 'done'" @click="downloadExportFile">
          下载
        </el-button>
        <el-button @click="exportDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color);
  flex-wrap: wrap;
}
.tab {
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  font-size: 13px;
}
.tab.on {
  color: var(--el-color-primary);
  font-weight: 700;
  border-bottom: 2px solid var(--el-color-primary);
  margin-bottom: -1px;
}
.cnt {
  margin-left: 4px;
  font-size: 11px;
  color: #999;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
}
.left,
.right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.dlg-field {
  margin-bottom: 12px;
}
.dlg-lab {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}
.dlg-val {
  font-size: 13px;
  line-height: 1.6;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fafafa;
}
.dlg-val.warn {
  background: #fffbe6;
}
.dlg-val.danger {
  background: #fff2f0;
}
</style>
