<script setup>
/**
 * 类目与费率。对照 PRD 06-平台端UI.html
 * #p04 · #p04-list · #p04a · #p04b · #p04c · #p04d · #p04e
 * 缺口：禁入启用站内信未接通。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../../api/client'
import { useAuthStore } from '../../../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  q: '',
  view: 'all',
  settlement_rule: '',
  pending_enable: false,
  parent_id: null,
  sort_by: 'updated_at',
  sort_dir: 'desc',
})
const adv = ref(false)

const COLS = [
  { key: 'name', label: '类目', locked: true, defaultVisible: true },
  { key: 'code', label: '类目编码', locked: true, defaultVisible: true },
  { key: 'fee', label: '平台费率', defaultVisible: true },
  { key: 'quals', label: '需资质', defaultVisible: true },
  { key: 'updated_at', label: '更新时间', defaultVisible: true },
  { key: 'status', label: '状态', locked: true, defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'updated_by', label: '更新人', defaultVisible: false },
  { key: 'settlement', label: '分账规则', defaultVisible: false },
]
const visibleCols = ref(COLS.filter((c) => c.defaultVisible).map((c) => c.key))
const colDialog = ref(false)
const colDraft = ref([])

const disableVisible = ref(false)
const disableSaving = ref(false)
const disableTarget = ref(null)
const disableForm = reactive({
  reason_type: '政策调整',
  reason: '',
  on_sale_ref_count: 0,
})
const REASON_TYPES = ['政策调整', '费率重议', '其他']

const drawer = ref(false)
const drawerMode = ref('create') // create | edit | view
const saving = ref(false)
const form = reactive({
  parent_id: null,
  name: '',
  code_source: 'auto',
  code: '',
  platform_fee_pct: 2,
  settlement_rule: 'standard',
  require_qualifications: [],
  description: '',
})
const editingId = ref(null)
const parentOptions = ref([])

/** P04-D 启用审批抽屉 */
const enableDrawer = ref(false)
const enableSaving = ref(false)
const enableMode = ref('apply') // apply | review
const enableTarget = ref(null)
const enableApp = ref(null)
const enableForm = reactive({
  platform_fee_pct: 2,
  require_qualifications: [],
  reason: '',
})

/** P04-E 类目编码规则（快捷） */
const codeDrawer = ref(false)
const codeSaving = ref(false)
const codeRule = reactive({
  prefix: 'cat.',
  date_format: '',
  seq_width: 3,
  reset_period: 'once',
  inherit_parent_code: true,
  separator: '.',
  enabled: true,
  preview: 'cat.001',
  suffix: '',
})

const STATUS_LABEL = { enabled: '启用', blocked: '禁入' }
const RULE_LABEL = {
  standard: '标准抽成',
  platform_plus_channel: '平台抽成 + 渠道费',
}
const QUAL_OPTS = ['办学许可证', 'ICP备案', '其他']

/** 对照 #p04e：fee.manage 可预览；保存须平台超管（未绑子角色）。 */
const canSaveCodeRule = computed(
  () => auth.isPlatformAdmin && !auth.user?.platform_shop_role,
)

function blockedStatusText() {
  if (enableApp.value?.status_label) return enableApp.value.status_label
  const row = enableTarget.value
  if (!row) return '禁入'
  if (row.blocked_status_label) return row.blocked_status_label
  const day = fmtTime(row.updated_at)
  const who = row.updated_by_name
  if (day && who) return `禁入（${day} 由${who}禁用）`
  if (day) return `禁入（${day}）`
  return '禁入'
}

function localCodePreview() {
  const w = Math.max(1, Math.min(Number(codeRule.seq_width) || 3, 8))
  const seq = String(1).padStart(w, '0')
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  let datePart = ''
  if (codeRule.date_format === '%Y%m%d') datePart = `${y}${m}${d}`
  else if (codeRule.date_format === '%Y%m') datePart = `${y}${m}`
  else if (codeRule.date_format === '%Y') datePart = String(y)
  return `${codeRule.prefix || ''}${datePart}${seq}${codeRule.suffix || ''}`
}

watch(
  () => [
    codeRule.prefix,
    codeRule.suffix,
    codeRule.date_format,
    codeRule.seq_width,
  ],
  () => {
    if (codeDrawer.value) codeRule.preview = localCodePreview()
  },
)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/admin/shop/categories', {
      params: {
        page: query.page,
        page_size: query.page_size,
        status: query.status || undefined,
        q: query.q || undefined,
        root_only: query.view === 'root' || undefined,
        settlement_rule: query.settlement_rule || undefined,
        pending_enable: query.pending_enable || undefined,
        parent_id: query.parent_id || undefined,
        sort_by: query.sort_by,
        sort_dir: query.sort_dir,
      },
    })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadParents() {
  try {
    const { data } = await api.get('/api/v1/admin/shop/categories', {
      params: { page_size: 100, status: 'enabled' },
    })
    parentOptions.value = data.items || []
  } catch {
    parentOptions.value = []
  }
}

async function refreshCode() {
  if (form.code_source !== 'auto') return
  try {
    const { data } = await api.post('/api/v1/admin/shop/categories/preview-code', {
      parent_id: form.parent_id || null,
      name: form.name || 'new',
    })
    form.code = data.code
  } catch {
    /* ignore */
  }
}

function openCreate() {
  drawerMode.value = 'create'
  editingId.value = null
  Object.assign(form, {
    parent_id: null,
    name: '',
    code_source: 'auto',
    code: '',
    platform_fee_pct: 2,
    settlement_rule: 'standard',
    require_qualifications: [],
    description: '',
  })
  loadParents()
  refreshCode()
  drawer.value = true
}

function openEdit(row, mode = 'edit') {
  drawerMode.value = mode
  editingId.value = row.id
  Object.assign(form, {
    parent_id: row.parent_id,
    name: row.name,
    code_source: row.code_source || 'auto',
    code: row.code,
    platform_fee_pct: (row.platform_fee_bps || 0) / 100,
    settlement_rule: row.settlement_rule || 'standard',
    require_qualifications: [...(row.require_qualifications || [])],
    description: row.description || '',
  })
  loadParents()
  drawer.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写类目名称')
    return
  }
  saving.value = true
  try {
    const feeBps = Math.round(Number(form.platform_fee_pct) * 100)
    if (drawerMode.value === 'create') {
      await api.post('/api/v1/admin/shop/categories', {
        parent_id: form.parent_id || null,
        name: form.name.trim(),
        code_source: form.code_source,
        code: form.code_source === 'manual' ? form.code : undefined,
        platform_fee_bps: feeBps,
        settlement_rule: form.settlement_rule,
        require_qualifications: form.require_qualifications,
        description: form.description || null,
      })
      ElMessage.success('已新增类目')
    } else {
      await api.patch(`/api/v1/admin/shop/categories/${editingId.value}`, {
        name: form.name.trim(),
        platform_fee_bps: feeBps,
        settlement_rule: form.settlement_rule,
        require_qualifications: form.require_qualifications,
        description: form.description || null,
      })
      ElMessage.success('已保存')
    }
    drawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function disableRow(row) {
  disableTarget.value = row
  Object.assign(disableForm, {
    reason_type: '政策调整',
    reason: '',
    on_sale_ref_count: row.on_sale_ref_count || 0,
  })
  try {
    const { data } = await api.get(`/api/v1/admin/shop/categories/${row.id}`)
    disableForm.on_sale_ref_count = data.on_sale_ref_count || 0
  } catch {
    /* 列表已带引用数 */
  }
  disableVisible.value = true
}

async function confirmDisable() {
  if (!disableTarget.value) return
  if ((disableForm.reason || '').trim().length < 4) {
    ElMessage.warning('说明至少 4 字')
    return
  }
  disableSaving.value = true
  try {
    await api.post(`/api/v1/admin/shop/categories/${disableTarget.value.id}/disable`, {
      reason_type: disableForm.reason_type,
      reason: disableForm.reason.trim(),
    })
    ElMessage.success('已禁用')
    disableVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '禁用失败')
  } finally {
    disableSaving.value = false
  }
}

function openEnableApply(row) {
  enableMode.value = 'apply'
  enableTarget.value = row
  enableApp.value = null
  Object.assign(enableForm, {
    platform_fee_pct: Math.max((row.platform_fee_bps || 0) / 100, 0.1) || 2,
    require_qualifications: [...(row.require_qualifications || [])],
    reason: '',
  })
  enableDrawer.value = true
}

async function openEnableReview(row) {
  if (!row.pending_enable_application_id) return
  enableMode.value = 'review'
  enableTarget.value = row
  try {
    const { data } = await api.get(
      `/api/v1/admin/shop/categories/enable-applications/${row.pending_enable_application_id}`
    )
    enableApp.value = data
    Object.assign(enableForm, {
      platform_fee_pct: (data.proposed_platform_fee_bps || 0) / 100,
      require_qualifications: [...(data.proposed_require_qualifications || [])],
      reason: data.reason || '',
    })
    enableDrawer.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载审批单失败')
  }
}

async function submitEnable() {
  if (!enableTarget.value) return
  if ((enableForm.reason || '').trim().length < 4) {
    ElMessage.warning('启用理由至少 4 字')
    return
  }
  enableSaving.value = true
  try {
    await api.post(`/api/v1/admin/shop/categories/${enableTarget.value.id}/enable`, {
      reason: enableForm.reason.trim(),
      platform_fee_bps: Math.round(Number(enableForm.platform_fee_pct) * 100),
      require_qualifications: enableForm.require_qualifications,
    })
    ElMessage.success('已提交审批')
    enableDrawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    enableSaving.value = false
  }
}

async function approveEnable() {
  if (!enableApp.value?.id) return
  enableSaving.value = true
  try {
    await api.post(
      `/api/v1/admin/shop/categories/enable-applications/${enableApp.value.id}/approve`
    )
    ElMessage.success('已通过，类目已启用')
    enableDrawer.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '通过失败')
  } finally {
    enableSaving.value = false
  }
}

async function rejectEnable() {
  if (!enableApp.value?.id) return
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回原因（≥4字）', '驳回启用审批', {
      inputPlaceholder: '驳回原因',
      inputPattern: /.{4,}/,
      inputErrorMessage: '至少4字',
      confirmButtonText: '确认驳回',
    })
    enableSaving.value = true
    await api.post(
      `/api/v1/admin/shop/categories/enable-applications/${enableApp.value.id}/reject`,
      { reject_reason: value }
    )
    ElMessage.success('已驳回，类目仍禁入')
    enableDrawer.value = false
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  } finally {
    enableSaving.value = false
  }
}

function statusText(row) {
  return row.status_display || STATUS_LABEL[row.status] || row.status
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 10)
}

async function openCodeRule() {
  try {
    const { data } = await api.get('/api/v1/admin/shop/number-rules/shop_category')
    Object.assign(codeRule, {
      prefix: data.prefix || 'cat.',
      date_format: data.date_format || '',
      seq_width: data.seq_width || 3,
      reset_period: data.reset_period || 'once',
      inherit_parent_code: !!data.inherit_parent_code,
      separator: data.separator || '.',
      enabled: !!data.enabled,
      preview: data.preview || '',
      suffix: data.suffix || '',
    })
    codeDrawer.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载编码规则失败')
  }
}

async function saveCodeRule() {
  codeSaving.value = true
  try {
    const { data } = await api.put('/api/v1/admin/shop/number-rules/shop_category', {
      prefix: codeRule.prefix,
      suffix: codeRule.suffix || '',
      date_format: codeRule.date_format || '',
      seq_width: codeRule.seq_width,
      reset_period: codeRule.reset_period,
      inherit_parent_code: !!codeRule.inherit_parent_code,
      separator: codeRule.separator || '.',
      enabled: !!codeRule.enabled,
    })
    Object.assign(codeRule, data)
    ElMessage.success('类目编码规则已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    codeSaving.value = false
  }
}

async function resetCodeRule() {
  try {
    const { data } = await api.put('/api/v1/admin/shop/number-rules/shop_category', {
      prefix: 'cat.',
      suffix: '',
      date_format: '',
      seq_width: 3,
      reset_period: 'once',
      inherit_parent_code: true,
      separator: '.',
      enabled: true,
    })
    Object.assign(codeRule, data)
    ElMessage.success('已恢复类目默认规则')
  } catch (e) {
    ElMessage.error(e.message || '恢复失败')
  }
}

function goFullCodeRules() {
  router.push({ name: 'AdminShopRolesAndCodes', query: { tab: 'codes' } })
}

function isCol(key) {
  return visibleCols.value.includes(key)
}
function openCol() {
  colDraft.value = [...visibleCols.value]
  colDialog.value = true
}
function saveCol() {
  const locked = COLS.filter((c) => c.locked).map((c) => c.key)
  visibleCols.value = [...new Set([...locked, ...colDraft.value])]
  colDialog.value = false
  ElMessage.success('列设置已保存')
}
function sortIcon(key) {
  if (query.sort_by !== key) return '↕'
  return query.sort_dir === 'asc' ? '↑' : '↓'
}
function toggleSort(key) {
  if (query.sort_by === key) {
    query.sort_dir = query.sort_dir === 'asc' ? 'desc' : 'asc'
  } else {
    query.sort_by = key
    query.sort_dir = key === 'name' ? 'asc' : 'desc'
  }
  load()
}
function resetAdv() {
  query.settlement_rule = ''
  query.pending_enable = false
  query.parent_id = null
  query.page = 1
  load()
}
function downloadCsv(filename, header, rows) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const blob = new Blob(
    ['\ufeff' + [header.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\n')],
    { type: 'text/csv;charset=utf-8' },
  )
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
function exportList() {
  downloadCsv(
    '类目与费率.csv',
    ['类目', '类目编码', '平台费率', '需资质', '更新时间', '状态', '更新人'],
    items.value.map((r) => [
      r.name,
      r.code,
      r.status === 'blocked' && !r.platform_fee_bps ? '—' : r.platform_fee_label,
      r.require_qualifications_label,
      fmtTime(r.updated_at),
      statusText(r),
      r.updated_by_name || '—',
    ]),
  )
}

onMounted(() => {
  loadParents()
  load()
})
</script>

<template>
  <div class="page-card" data-testid="shop-categories" v-loading="loading">
    <div class="hd">
      <h3>类目与费率</h3>
      <p class="sub">类目费率影响平台抽成；禁入阻止新商品挂载，启用须审批。</p>
    </div>
    <div class="toolbar">
      <el-select
        v-model="query.view"
        placeholder="全部类目"
        style="width: 140px"
        @change="() => { query.page = 1; load() }"
      >
        <el-option label="全部类目" value="all" />
        <el-option label="仅根类目" value="root" />
      </el-select>
      <el-input
        v-model="query.q"
        clearable
        placeholder="搜索类目名"
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
        <el-option label="启用" value="enabled" />
        <el-option label="禁入" value="blocked" />
      </el-select>
      <el-button @click="adv = !adv">高级筛选</el-button>
      <span class="spacer" />
      <el-button @click="openCol">列设置</el-button>
      <el-button @click="exportList">导出</el-button>
      <el-button @click="openCodeRule">编码规则</el-button>
      <el-button link type="primary" @click="goFullCodeRules">编码规则 ↗</el-button>
      <el-button type="primary" @click="openCreate">+ 新增类目</el-button>
    </div>
    <div v-if="adv" class="adv">
      <el-select
        v-model="query.parent_id"
        clearable
        placeholder="父类目"
        style="width: 200px"
        @change="() => { query.page = 1; load() }"
      >
        <el-option
          v-for="p in parentOptions"
          :key="p.id"
          :label="p.name"
          :value="p.id"
        />
      </el-select>
      <el-select
        v-model="query.settlement_rule"
        clearable
        placeholder="分账规则"
        style="width: 180px"
        @change="() => { query.page = 1; load() }"
      >
        <el-option
          v-for="(lab, key) in RULE_LABEL"
          :key="key"
          :label="lab"
          :value="key"
        />
      </el-select>
      <el-checkbox v-model="query.pending_enable" @change="() => { query.page = 1; load() }">
        仅待启用审批
      </el-checkbox>
      <el-button type="primary" @click="() => { query.page = 1; load() }">查询</el-button>
      <el-button @click="resetAdv">重置</el-button>
    </div>

    <el-table :data="items" border stripe size="small" style="margin-top: 12px">
      <el-table-column v-if="isCol('name')" min-width="140">
        <template #header>
          <span class="sortable" @click.stop="toggleSort('name')">类目 {{ sortIcon('name') }}</span>
        </template>
        <template #default="{ row }">{{ row.name }}</template>
      </el-table-column>
      <el-table-column v-if="isCol('code')" label="类目编码" min-width="160">
        <template #default="{ row }"><code>{{ row.code }}</code></template>
      </el-table-column>
      <el-table-column v-if="isCol('fee')" label="平台费率" width="100">
        <template #default="{ row }">
          {{ row.status === 'blocked' && !row.platform_fee_bps ? '—' : row.platform_fee_label }}
        </template>
      </el-table-column>
      <el-table-column v-if="isCol('quals')" label="需资质" min-width="140">
        <template #default="{ row }">{{ row.require_qualifications_label }}</template>
      </el-table-column>
      <el-table-column v-if="isCol('updated_at')" width="130">
        <template #header>
          <span class="sortable" @click.stop="toggleSort('updated_at')">更新时间 {{ sortIcon('updated_at') }}</span>
        </template>
        <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column v-if="isCol('updated_by')" label="更新人" width="110">
        <template #default="{ row }">{{ row.updated_by_name || '—' }}</template>
      </el-table-column>
      <el-table-column v-if="isCol('settlement')" label="分账规则" width="150">
        <template #default="{ row }">{{ RULE_LABEL[row.settlement_rule] || row.settlement_rule }}</template>
      </el-table-column>
      <el-table-column v-if="isCol('status')" label="状态" width="110">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.pending_enable_application_id ? 'warning' : row.status === 'enabled' ? 'success' : 'info'"
          >
            {{ statusText(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="isCol('ops')" label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'enabled'">
            <el-button link type="primary" @click="openEdit(row, 'edit')">编辑</el-button>
            <el-button link type="warning" @click="disableRow(row)">禁用</el-button>
          </template>
          <template v-else-if="row.pending_enable_application_id">
            <el-button link type="primary" @click="openEdit(row, 'view')">查看</el-button>
            <el-button link type="primary" @click="openEnableReview(row)">审批启用</el-button>
          </template>
          <template v-else>
            <el-button link type="primary" @click="openEdit(row, 'view')">查看</el-button>
            <el-button link type="primary" @click="openEnableApply(row)">启用（需审批）</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !items.length" description="暂无类目" />

    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 12px"
      @current-change="load"
      @size-change="() => { query.page = 1; load() }"
    />

    <el-drawer
      v-model="drawer"
      :title="drawerMode === 'create' ? '新增平台类目' : drawerMode === 'view' ? '查看类目' : '编辑类目'"
      size="480px"
    >
      <el-form label-position="top" :disabled="drawerMode === 'view'">
        <el-form-item v-if="drawerMode === 'create'" label="父类目" required>
          <el-select
            v-model="form.parent_id"
            clearable
            placeholder="根"
            style="width: 100%"
            @change="refreshCode"
          >
            <el-option label="根" :value="null" />
            <el-option
              v-for="p in parentOptions"
              :key="p.id"
              :label="`${p.name} (${p.code})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="drawerMode === 'create'" label="编码来源">
          <el-radio-group v-model="form.code_source" @change="refreshCode">
            <el-radio value="auto">自动（按规则）</el-radio>
            <el-radio value="manual">手工录入</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="类目名称" required>
          <el-input v-model="form.name" maxlength="100" @change="refreshCode" />
        </el-form-item>
        <el-form-item label="类目编码" :required="drawerMode === 'create'">
          <el-input
            v-model="form.code"
            :disabled="drawerMode !== 'create' || form.code_source === 'auto'"
          >
            <template v-if="drawerMode === 'create' && form.code_source === 'auto'" #append>
              <el-button @click="refreshCode">刷新预览</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="平台费率" required>
          <el-input-number v-model="form.platform_fee_pct" :min="0" :max="30" :precision="1" />
          <span class="unit">%</span>
        </el-form-item>
        <el-form-item label="分账规则" required>
          <el-select v-model="form.settlement_rule" style="width: 100%">
            <el-option
              v-for="(lab, key) in RULE_LABEL"
              :key="key"
              :label="lab"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="需资质（选填）">
          <el-checkbox-group v-model="form.require_qualifications">
            <el-checkbox v-for="q in QUAL_OPTS" :key="q" :value="q" :label="q" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item v-if="drawerMode === 'create'" label="初始状态">
          <div class="ro">启用</div>
        </el-form-item>
        <el-form-item label="说明（选填）">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <div v-if="drawerMode !== 'view'" class="ft">
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button @click="drawer = false">取消</el-button>
      </div>
      <div v-else class="ft">
        <el-button @click="drawer = false">关闭</el-button>
      </div>
    </el-drawer>

    <!-- P04-D 启用审批 -->
    <el-drawer
      v-model="enableDrawer"
      :title="enableMode === 'apply' ? `申请启用「${enableTarget?.name || ''}」` : `审批启用「${enableTarget?.name || ''}」`"
      size="480px"
    >
      <el-form label-position="top">
        <el-form-item label="当前状态（只读）">
          <div class="ro">{{ blockedStatusText() }}</div>
        </el-form-item>
        <el-form-item label="拟设费率" required>
          <el-input-number
            v-model="enableForm.platform_fee_pct"
            :min="0"
            :max="30"
            :precision="1"
            :disabled="enableMode === 'review'"
          />
          <span class="unit">%</span>
        </el-form-item>
        <el-form-item label="需资质" required>
          <el-checkbox-group
            v-model="enableForm.require_qualifications"
            :disabled="enableMode === 'review'"
          >
            <el-checkbox v-for="q in QUAL_OPTS" :key="q" :value="q" :label="q" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="启用理由" required>
          <el-input
            v-model="enableForm.reason"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            :disabled="enableMode === 'review'"
            placeholder="至少 4 字"
          />
        </el-form-item>
        <el-form-item label="审批人（只读）">
          <div class="ro">{{ enableApp?.approver_label || '平台超管（单级审批）' }}</div>
        </el-form-item>
      </el-form>
      <div v-if="enableMode === 'apply'" class="ft">
        <el-button type="primary" :loading="enableSaving" @click="submitEnable">提交审批</el-button>
        <el-button @click="enableDrawer = false">取消</el-button>
      </div>
      <div v-else class="ft">
        <el-button type="primary" :loading="enableSaving" @click="approveEnable">通过</el-button>
        <el-button type="danger" :loading="enableSaving" @click="rejectEnable">驳回</el-button>
        <el-button @click="enableDrawer = false">取消</el-button>
      </div>
    </el-drawer>

    <!-- 类目编码（快捷） -->
    <el-drawer v-model="codeDrawer" title="类目编码规则" size="520px">
      <p class="hint">
        实体：平台类目 <code>shop_category</code>。子类目可继承父 code（如
        <code>cat.vocational.002</code>）。全站规则见「角色与编码」。
        <span v-if="!canSaveCodeRule">本页仅预览，保存须平台超管。</span>
      </p>
      <el-form label-position="top">
        <el-form-item label="前缀">
          <el-input v-model="codeRule.prefix" :disabled="!canSaveCodeRule" />
        </el-form-item>
        <el-form-item label="日期段">
          <el-select v-model="codeRule.date_format" style="width: 100%" :disabled="!canSaveCodeRule">
            <el-option label="不含日期" value="" />
            <el-option label="年月日" value="%Y%m%d" />
            <el-option label="年月" value="%Y%m" />
            <el-option label="年" value="%Y" />
          </el-select>
        </el-form-item>
        <el-form-item label="序号宽度">
          <el-input-number v-model="codeRule.seq_width" :min="1" :max="8" :disabled="!canSaveCodeRule" />
        </el-form-item>
        <el-form-item label="重置周期">
          <el-select v-model="codeRule.reset_period" style="width: 100%" :disabled="!canSaveCodeRule">
            <el-option label="永不重置" value="once" />
            <el-option label="每日" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
            <el-option label="每年" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="继承父 code">
          <el-checkbox v-model="codeRule.inherit_parent_code" :disabled="!canSaveCodeRule">
            子类目在父 code 后拼接序号
          </el-checkbox>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="codeRule.enabled" :disabled="!canSaveCodeRule" />
          <span class="hint-inline">关闭后新增须手工填写 code</span>
        </el-form-item>
        <el-form-item label="预览">
          <code data-testid="category-code-preview">{{ codeRule.preview }}</code>
          <span v-if="codeRule.inherit_parent_code" class="hint-inline"> / 子级如 cat.vocational.002</span>
        </el-form-item>
      </el-form>
      <div class="ft">
        <el-button
          v-if="canSaveCodeRule"
          type="primary"
          :loading="codeSaving"
          @click="saveCodeRule"
        >
          保存规则
        </el-button>
        <el-button v-if="canSaveCodeRule" @click="resetCodeRule">恢复默认</el-button>
        <el-button @click="goFullCodeRules">打开全站编码规则</el-button>
      </div>
    </el-drawer>

    <el-dialog
      v-model="disableVisible"
      :title="disableTarget ? `禁用「${disableTarget.name}」？` : '禁用类目'"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item label="影响说明（只读）">
          <div class="ro">新商品不可选此类目；已上架商品不受影响，建议运营通知商家迁移</div>
        </el-form-item>
        <el-form-item label="告警（只读）">
          <div class="ro warn">当前有 {{ disableForm.on_sale_ref_count }} 个在售商品引用此类目</div>
        </el-form-item>
        <el-form-item label="原因类型" required>
          <el-select v-model="disableForm.reason_type" style="width: 100%">
            <el-option v-for="t in REASON_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input
            v-model="disableForm.reason"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="至少 4 字"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="disableVisible = false">取消</el-button>
        <el-button type="warning" :loading="disableSaving" @click="confirmDisable">确认禁用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="colDialog" title="列设置" width="360px">
      <el-checkbox-group v-model="colDraft">
        <div v-for="c in COLS" :key="c.key" class="col-row">
          <el-checkbox :label="c.key" :disabled="c.locked">{{ c.label }}</el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="colDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCol">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-card {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
}
.hd h3 {
  margin: 0 0 4px;
  font-size: 16px;
}
.sub {
  margin: 0 0 12px;
  color: #666;
  font-size: 13px;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.spacer {
  flex: 1;
}
.adv {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 10px;
}
.sortable {
  cursor: pointer;
  user-select: none;
}
.unit {
  margin-left: 8px;
  color: #666;
}
.ft {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}
.ro {
  color: #606266;
  line-height: 1.5;
}
.warn {
  background: #fffbe6;
  padding: 8px 10px;
  border-radius: 4px;
}
.col-row {
  margin-bottom: 6px;
}
.hint {
  font-size: 13px;
  color: #666;
  margin: 0 0 12px;
  line-height: 1.5;
}
.hint-inline {
  margin-left: 8px;
  font-size: 12px;
  color: #999;
}
code {
  font-size: 12px;
}
</style>
