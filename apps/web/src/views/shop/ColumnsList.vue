<script setup>
/**
 * A04 专栏列表。对照 PRD 01-管理端UI.html #a04 · #a04a · #a04b · #a04c · #a04d · 04#select-common
 * 默认列：标题·课时数·引用商品·状态·更新时间·操作
 * 缺口：导出完成站内信本批不接；已下架专栏再发布本批不接。
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
const advOpen = ref(false)
const createVisible = ref(false)
const form = reactive({ title: '', intro: '' })

const dlg = reactive({
  visible: false,
  kind: '', // publish | delete | off
  row: null,
  busy: false,
})

const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  ref_min: undefined,
  ref_max: undefined,
  updated_from: '',
  updated_to: '',
})

const COL_STORAGE = 'shop.a04.columns'
const ALL_COLS = [
  { key: 'title', label: '标题', locked: true, defaultOn: true },
  { key: 'lesson_count', label: '课时数', locked: true, defaultOn: true },
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
const STATUS_TABS = [
  { key: '', label: '全部专栏' },
  { key: 'draft', label: '草稿' },
  { key: 'published', label: '已发布' },
  { key: 'off_sale', label: '已下架' },
]
const visibleCols = computed(() => ALL_COLS.filter((c) => colVisible[c.key] || c.locked))

function listParams() {
  const refMin =
    query.ref_min === undefined || query.ref_min === null || query.ref_min === ''
      ? undefined
      : Number(query.ref_min)
  const refMax =
    query.ref_max === undefined || query.ref_max === null || query.ref_max === ''
      ? undefined
      : Number(query.ref_max)
  return {
    page: query.page,
    page_size: query.page_size,
    status: query.status || undefined,
    q: query.q || undefined,
    shop_id: currentId.value || undefined,
    ref_min: Number.isFinite(refMin) ? refMin : undefined,
    ref_max: Number.isFinite(refMax) ? refMax : undefined,
    updated_from: query.updated_from || undefined,
    updated_to: query.updated_to || undefined,
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
    const { data } = await api.get('/api/v1/shop/columns', { params: listParams() })
    items.value = data.items || []
    total.value = data.total || 0
    statusCounts.value = data.status_counts || {}
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function resetAdv() {
  query.ref_min = undefined
  query.ref_max = undefined
  query.updated_from = ''
  query.updated_to = ''
  query.page = 1
  load()
}

function openCreate() {
  form.title = ''
  form.intro = ''
  createVisible.value = true
}

async function createColumn() {
  const title = form.title.trim()
  if (!title) {
    ElMessage.warning('请填写标题')
    return
  }
  creating.value = true
  try {
    const { data } = await api.post('/api/v1/shop/columns', {
      title,
      intro: form.intro || undefined,
      shop_id: currentId.value || undefined,
    })
    ElMessage.success('已创建草稿')
    createVisible.value = false
    router.push({ name: 'ShopColumnEdit', params: { id: data.id }, query: { mode: 'edit' } })
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

function openPublish(row) {
  if ((row.published_lesson_count || 0) < 1) {
    ElMessage.warning('须至少 1 个已发布课时')
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
      await api.post(`/api/v1/shop/columns/${row.id}/publish`)
      ElMessage.success('已发布')
    } else if (dlg.kind === 'delete') {
      await api.delete(`/api/v1/shop/columns/${row.id}`)
      ElMessage.success('已删除')
    } else if (dlg.kind === 'off') {
      await api.post(`/api/v1/shop/columns/${row.id}/off-sale`)
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
  router.push({ name: 'ShopColumnEdit', params: { id: row.id }, query: { mode: 'view' } })
}
function goEdit(row) {
  router.push({ name: 'ShopColumnEdit', params: { id: row.id }, query: { mode: 'edit' } })
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
    const { data } = await api.post('/api/v1/shop/columns/export', body)
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
    const res = await api.get(`/api/v1/shop/columns/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'shop-columns.csv'
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
  <div v-loading="loading" data-testid="shop-columns">
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
        <el-button :type="advOpen ? 'primary' : 'default'" plain @click="advOpen = !advOpen">
          高级筛选
        </el-button>
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
        <el-button v-if="canWrite" type="primary" @click="openCreate">+ 新建专栏</el-button>
      </div>
    </div>

    <div v-if="advOpen" class="adv">
      <div class="adv-t">高级筛选</div>
      <div class="adv-row">
        <el-input-number
          v-model="query.ref_min"
          :min="0"
          :precision="0"
          :controls="false"
          placeholder="引用商品 ≥"
          style="width: 130px"
        />
        <el-input-number
          v-model="query.ref_max"
          :min="0"
          :precision="0"
          :controls="false"
          placeholder="引用商品 ≤"
          style="width: 130px"
        />
        <el-date-picker
          v-model="query.updated_from"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="更新起"
          style="width: 140px"
        />
        <span class="sep">—</span>
        <el-date-picker
          v-model="query.updated_to"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="更新止"
          style="width: 140px"
        />
      </div>
      <div class="adv-row">
        <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
        <el-button @click="resetAdv">重置</el-button>
        <span class="hint">快捷 Tab 已覆盖草稿/已发布/已下架；引用数与时间在高级筛选</span>
      </div>
    </div>

    <el-table :data="items" border stripe size="small" style="margin-top: 12px">
      <el-table-column v-if="visibleCols.some((c) => c.key === 'title')" prop="title" label="标题" min-width="160" />
      <el-table-column v-if="visibleCols.some((c) => c.key === 'lesson_count')" prop="lesson_count" label="课时数" width="90" />
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
            :disabled="(row.published_lesson_count || 0) < 1"
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

    <el-drawer v-model="createVisible" title="新建专栏" size="420px" destroy-on-close>
      <el-form label-width="96px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="200" placeholder="请输入专栏标题" />
        </el-form-item>
        <el-form-item label="简介（选填）">
          <el-input v-model="form.intro" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createColumn">创建并编辑</el-button>
      </template>
    </el-drawer>

    <el-dialog
      v-model="dlg.visible"
      :title="
        dlg.kind === 'publish'
          ? `确认发布专栏「${dlg.row?.title || ''}」？`
          : dlg.kind === 'delete'
            ? `确认删除「${dlg.row?.title || ''}」？`
            : `确认下架专栏「${dlg.row?.title || ''}」？`
      "
      width="480px"
    >
      <div v-if="dlg.kind === 'publish'" class="dlg-field">
        <div class="dlg-lab">发布说明（只读）</div>
        <div class="dlg-val">
          已发布课时 <b>{{ dlg.row?.published_lesson_count || 0 }} / {{ dlg.row?.lesson_count || 0 }}</b>；发布后可在商品编辑中关联本专栏（不等于商品上架）
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
          · 新建课类商品不可再选本专栏<br>
          · 已关联商品 <b>{{ dlg.row?.ref_product_count || 0 }}</b> 个：引用保留，在售商品可继续售<br>
          · 已购买家可继续学习（权益不关）<br>
          · 课时管理变为只读；不可再发布
        </div>
      </div>
      <template #footer>
        <el-button @click="dlg.visible = false">取消</el-button>
        <el-button
          v-if="dlg.kind === 'publish'"
          type="primary"
          :loading="dlg.busy"
          :disabled="(dlg.row?.published_lesson_count || 0) < 1"
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
.adv {
  margin-top: 10px;
  border: 1px solid #91caff;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f0f7ff;
  font-size: 12px;
}
.adv-t {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.adv-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.sep {
  color: #999;
}
.hint {
  color: #666;
  font-size: 11px;
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
