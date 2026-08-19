<script setup>
/**
 * A07 服务列表。对照 PRD 01-管理端UI.html #a07 · #a07d · 04#select-common
 * 默认列：标题·模式·引用商品·状态·更新时间·操作
 * 缺口：导出完成站内信本批不接；已下架服务再发布本批不接。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { submitShopExport, SHOP_EXPORT_COLUMN_MODE_LABELS } from '../../utils/shopExport'
import { useCurrentShop } from '../../composables/useCurrentShop'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import CrmColumnSettingsDialog from '../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../composables/useListColumnSettings'

const router = useRouter()
const auth = useAuthStore()
const { currentId } = useCurrentShop()
const canWrite = computed(() => hasPermission(auth.permissions || [], 'shop.content.write'))
const loading = ref(false)
const exporting = ref(false)
const creating = ref(false)
const items = ref([])
const total = ref(0)
const statusCounts = ref({})
const createVisible = ref(false)
const form = reactive({
  title: '',
  mode: 'booking',
  total_times: 3,
  valid_days: 90,
  duration_minutes: 60,
})

const dlg = reactive({
  visible: false,
  kind: '', // publish | delete | off
  row: null,
  busy: false,
})

const query = reactive({ page: 1, page_size: 20, status: '', mode: '', q: '' })

const COL_STORAGE = 'shop.a07.columns'
const ALL_COLS = [
  { key: 'title', label: '标题', locked: true, defaultOn: true },
  { key: 'mode', label: '模式', defaultOn: true },
  { key: 'ref_product_count', label: '引用商品', defaultOn: true },
  { key: 'status', label: '状态', defaultOn: true },
  { key: 'updated_at', label: '更新时间', defaultOn: true },
  { key: 'open_slot_count', label: '开放时段', defaultOn: false },
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

const STATUS_LABEL = { draft: '草稿', published: '已发布', off_sale: '已下架' }
const MODE_LABEL = { booking: '预约', times_card: '次数卡' }
const STATUS_TABS = [
  { key: '', label: '全部服务' },
  { key: 'draft', label: '草稿' },
  { key: 'published', label: '已发布' },
  { key: 'off_sale', label: '已下架' },
]
function listParams() {
  return {
    page: query.page,
    page_size: query.page_size,
    status: query.status || undefined,
    mode: query.mode || undefined,
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

function canPublish(row) {
  if (!row || row.status !== 'draft') return false
  if (!(row.title || '').trim()) return false
  if (row.mode === 'booking') return (row.open_slot_count || 0) >= 1
  if (row.mode === 'times_card') return Boolean(row.total_times) && Boolean(row.valid_days)
  return false
}

function publishBlockedReason(row) {
  if (!(row?.title || '').trim()) return '请填写标题'
  if (row.mode === 'booking' && (row.open_slot_count || 0) < 1) return '请配置时段'
  if (row.mode === 'times_card' && (!row.total_times || !row.valid_days)) return '请填写次数与有效期'
  return ''
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/service-offers', { params: listParams() })
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
  form.mode = 'booking'
  form.total_times = 3
  form.valid_days = 90
  form.duration_minutes = 60
  createVisible.value = true
}

async function createOffer() {
  const title = form.title.trim()
  if (!title) {
    ElMessage.warning('请填写标题')
    return
  }
  creating.value = true
  try {
    const body = {
      title,
      mode: form.mode,
      duration_minutes: form.duration_minutes,
      shop_id: currentId.value || undefined,
    }
    if (form.mode === 'times_card') {
      body.total_times = form.total_times
      body.valid_days = form.valid_days
    }
    const { data } = await api.post('/api/v1/shop/service-offers', body)
    ElMessage.success('已创建草稿')
    createVisible.value = false
    router.push({ name: 'ShopServiceOfferEdit', params: { id: data.id }, query: { mode: 'edit' } })
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

function openPublish(row) {
  const reason = publishBlockedReason(row)
  if (reason) {
    ElMessage.warning(reason)
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
      await api.post(`/api/v1/shop/service-offers/${row.id}/publish`)
      ElMessage.success('已发布')
    } else if (dlg.kind === 'delete') {
      await api.delete(`/api/v1/shop/service-offers/${row.id}`)
      ElMessage.success('已删除')
    } else if (dlg.kind === 'off') {
      await api.post(`/api/v1/shop/service-offers/${row.id}/off-sale`)
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
  router.push({ name: 'ShopServiceOfferEdit', params: { id: row.id }, query: { mode: 'view' } })
}
function goEdit(row) {
  router.push({ name: 'ShopServiceOfferEdit', params: { id: row.id }, query: { mode: 'edit' } })
}

function visibleExportColumns() {
  return visibleKeys.value.filter((k) => k !== 'ops')
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
    await submitShopExport(
      '/api/v1/shop/service-offers/export',
      body,
      '/api/v1/shop/service-offers/export-tasks',
      'shop-service-offers.csv',
      total.value,
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}


watch(currentId, () => {
  query.page = 1
  load()
})

onMounted(load)
</script>

<template>
  <div v-loading="loading" data-testid="shop-offers">
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
          v-model="query.mode"
          clearable
          placeholder="模式"
          style="width: 120px"
          @change="() => { query.page = 1; load() }"
        >
          <el-option label="预约" value="booking" />
          <el-option label="次数卡" value="times_card" />
        </el-select>
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
              <el-dropdown-item command="current">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.allColumns }}</el-dropdown-item>
              <el-dropdown-item command="columns">{{ SHOP_EXPORT_COLUMN_MODE_LABELS.visibleColumns }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="openColumnSettings">列设置</el-button>
        <el-button v-if="canWrite" type="primary" @click="openCreate">+ 新建服务</el-button>
      </div>
    </div>

    <el-table :data="items" border stripe size="small" style="margin-top: 12px">
      <template v-for="colKey in visibleKeys" :key="colKey">
      <el-table-column v-if="colKey === 'title'" prop="title" label="标题" min-width="160" />
      <el-table-column v-if="colKey === 'mode'" label="模式" width="130">
        <template #default="{ row }">
          {{ MODE_LABEL[row.mode] || row.mode }}
          <span v-if="row.mode === 'times_card' && row.total_times"> · {{ row.total_times }}次</span>
        </template>
      </el-table-column>
      <el-table-column v-if="colKey === 'ref_product_count'" prop="ref_product_count" label="引用商品" width="100" />
      <el-table-column v-if="colKey === 'status'" label="状态" width="100">
        <template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template>
      </el-table-column>
      <el-table-column v-if="colKey === 'updated_at'" prop="updated_at" label="更新时间" min-width="160" />
      <el-table-column v-if="colKey === 'open_slot_count'" prop="open_slot_count" label="开放时段" width="100" />
      <el-table-column v-if="colKey === 'ops'" label="操作" width="240" fixed="right">
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
            :disabled="!canPublish(row)"
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
      </template>
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

    <el-drawer v-model="createVisible" title="新建服务" size="420px" destroy-on-close>
      <el-form label-width="110px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="200" placeholder="请输入服务标题" />
        </el-form-item>
        <el-form-item label="模式" required>
          <el-radio-group v-model="form.mode">
            <el-radio value="booking">预约</el-radio>
            <el-radio value="times_card">次数卡</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.mode === 'times_card'">
          <el-form-item label="次数" required>
            <el-input-number v-model="form.total_times" :min="1" />
          </el-form-item>
          <el-form-item label="有效天数" required>
            <el-input-number v-model="form.valid_days" :min="1" />
          </el-form-item>
        </template>
        <el-form-item label="单次时长(分)">
          <el-input-number v-model="form.duration_minutes" :min="15" :step="15" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createOffer">创建并编辑</el-button>
      </template>
    </el-drawer>

    <el-dialog
      v-model="dlg.visible"
      :title="
        dlg.kind === 'publish'
          ? `确认发布服务「${dlg.row?.title || ''}」？`
          : dlg.kind === 'delete'
            ? `确认删除「${dlg.row?.title || ''}」？`
            : `确认下架服务「${dlg.row?.title || ''}」？`
      "
      width="480px"
    >
      <div v-if="dlg.kind === 'publish'" class="dlg-field">
        <div class="dlg-lab">发布说明（只读）</div>
        <div class="dlg-val">
          模式：<b>{{ MODE_LABEL[dlg.row?.mode] || dlg.row?.mode }}</b>
          <template v-if="dlg.row?.mode === 'booking'">；开放时段 <b>{{ dlg.row?.open_slot_count || 0 }}</b></template>
          <template v-else-if="dlg.row?.mode === 'times_card'">；次数 <b>{{ dlg.row?.total_times || 0 }}</b> · 有效天数 <b>{{ dlg.row?.valid_days || 0 }}</b></template>
          ；发布后商品可关联售卖
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
          · 新建服务类商品不可再选本服务<br>
          · 已关联商品 <b>{{ dlg.row?.ref_product_count || 0 }}</b> 个：引用保留<br>
          · 已购买家可继续预约/核销（权益不关）<br>
          · 买家不可新约开放时段<br>
          · 编辑页变为只读；不可再发布
        </div>
      </div>
      <template #footer>
        <el-button @click="dlg.visible = false">取消</el-button>
        <el-button
          v-if="dlg.kind === 'publish'"
          type="primary"
          :loading="dlg.busy"
          :disabled="!canPublish(dlg.row)"
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

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="columnDraft"
      @save="() => { saveColumnSettings(); ElMessage.success('列设置已保存') }"
    />
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
