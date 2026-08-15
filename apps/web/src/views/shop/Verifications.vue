<script setup>
/**
 * 核销台 / 核销记录。对照 PRD 01-管理端UI.html #a08 / #a08-log / #a08b / #a08-clerk
 * 到店核销：6 位码 + 结果卡；核销记录：默认列 + 日期 Chip + 操作人 + 导出 + 列设置
 * 店员壳：侧栏仅核销台、记录 list_own；扫码枪专项驱动未接；站内信/短信本批不接（导出在页内下载）；Phase 1 不可撤销核销。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'

const { currentId } = useCurrentShop()
const auth = useAuthStore()
const canExecute = computed(() => hasPermission(auth.permissions, 'shop.redemption.execute'))
const canListAll = computed(() => hasPermission(auth.permissions, 'shop.redemption.list_all'))

const tab = ref('redeem')
const looking = ref(false)
const executing = ref(false)
const codeDigits = ref(['', '', '', '', '', ''])
const result = ref(null)
const codeInputs = ref([])

const loading = ref(false)
const exporting = ref(false)
const exportDialog = ref(false)
const exportTask = ref(null)
const records = ref([])
const total = ref(0)
const operators = ref([])
const query = reactive({
  page: 1,
  page_size: 20,
  q: '',
  dateRange: '7d',
  created_from: '',
  created_to: '',
  operator_id: '',
})
const COL_STORAGE = 'shop.a08.columns'
const ALL_COLS = [
  { key: 'created_at', label: '核销时间', locked: true, defaultOn: true },
  { key: 'verify_code', label: '核销码', locked: true, defaultOn: true },
  { key: 'buyer', label: '买家', locked: true, defaultOn: true },
  { key: 'product_name', label: '商品', locked: true, defaultOn: true },
  { key: 'booking_slot', label: '预约时段', locked: true, defaultOn: true },
  { key: 'operator_name', label: '操作人', locked: true, defaultOn: true },
  { key: 'deducted_count', label: '扣次', locked: false, defaultOn: false },
  { key: 'ops', label: '操作', locked: true, defaultOn: true },
]
const DATE_CHIPS = [
  { key: 'today', label: '今日' },
  { key: '7d', label: '近7天' },
  { key: '30d', label: '近30天' },
  { key: 'custom', label: '自定义' },
]
function loadColPrefs() {
  try {
    const raw = localStorage.getItem(COL_STORAGE)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return Object.fromEntries(ALL_COLS.map((c) => [c.key, c.defaultOn]))
}
const colVisible = reactive(loadColPrefs())
const colDialog = ref(false)
const colDraft = reactive({ ...colVisible })
const detailVisible = ref(false)
const detail = ref(null)

const codeStr = computed(() => codeDigits.value.join(''))

function fmtLocalDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}
function applyDateChip(key) {
  query.dateRange = key
  const today = startOfToday()
  if (key === 'today') {
    query.created_from = fmtLocalDate(today)
    query.created_to = fmtLocalDate(today)
  } else if (key === '7d') {
    const from = startOfToday()
    from.setDate(from.getDate() - 6)
    query.created_from = fmtLocalDate(from)
    query.created_to = fmtLocalDate(today)
  } else if (key === '30d') {
    const from = startOfToday()
    from.setDate(from.getDate() - 29)
    query.created_from = fmtLocalDate(from)
    query.created_to = fmtLocalDate(today)
  }
}

function onDigitInput(i, e) {
  const v = String(e.target.value || '').replace(/\D/g, '').slice(-1)
  codeDigits.value[i] = v
  if (v && i < 5) codeInputs.value[i + 1]?.focus()
}

function onDigitKeydown(i, e) {
  if (e.key === 'Backspace' && !codeDigits.value[i] && i > 0) {
    codeInputs.value[i - 1]?.focus()
  }
  if (e.key === 'Enter') lookup()
}

function onPaste(e) {
  const text = (e.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6)
  if (!text) return
  e.preventDefault()
  for (let i = 0; i < 6; i++) codeDigits.value[i] = text[i] || ''
  if (text.length === 6) lookup()
}

function clearAll() {
  codeDigits.value = ['', '', '', '', '', '']
  result.value = null
  codeInputs.value[0]?.focus()
}

async function lookup() {
  const code = codeStr.value
  if (code.length !== 6) {
    ElMessage.warning('请输入有效核销码')
    return
  }
  looking.value = true
  result.value = null
  try {
    const { data } = await api.post('/api/v1/shop/verifications/lookup', { verify_code: code })
    result.value = data
  } catch (e) {
    ElMessage.error(e.message || '查询失败')
  } finally {
    looking.value = false
  }
}

async function confirmExecute() {
  const item = result.value?.item
  if (!item) return
  executing.value = true
  try {
    await api.post('/api/v1/shop/verifications/execute', {
      entitlement_id: item.entitlement_id,
      booking_id: item.booking_id || undefined,
      deducted_count: 1,
      idempotency_key: `ui-${Date.now()}-${item.entitlement_id}`,
    })
    ElMessage.success('核销成功')
    clearAll()
    if (tab.value === 'log') await loadRecords()
  } catch (e) {
    ElMessage.error(e.message || '核销失败')
  } finally {
    executing.value = false
  }
}

function listParams(extra = {}) {
  return {
    q: query.q || undefined,
    created_from: query.created_from || undefined,
    created_to: query.created_to || undefined,
    operator_id: query.operator_id || undefined,
    shop_id: currentId.value || undefined,
    ...extra,
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/shop/verifications', {
      params: listParams({ page: query.page, page_size: query.page_size }),
    })
    records.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadOperators() {
  if (!canListAll.value) {
    operators.value = []
    return
  }
  try {
    const { data } = await api.get('/api/v1/shop/verifications/operators', {
      params: { shop_id: currentId.value || undefined },
    })
    operators.value = data.items || []
  } catch {
    operators.value = []
  }
}

async function exportCsv() {
  exporting.value = true
  try {
    const { data } = await api.post('/api/v1/shop/verifications/export', listParams())
    exportTask.value = data
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
    const res = await api.get(`/api/v1/shop/verifications/export-tasks/${exportTask.value.id}/file`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'text/csv; charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportTask.value.file_name || 'verifications.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function openColSettings() {
  Object.assign(colDraft, colVisible)
  colDialog.value = true
}
function saveCols() {
  Object.assign(colVisible, colDraft)
  localStorage.setItem(COL_STORAGE, JSON.stringify({ ...colVisible }))
  colDialog.value = false
}
function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 16)
}
function deductText(row) {
  if (row.remaining_before != null && row.remaining_after != null) {
    return `${row.remaining_before} → ${row.remaining_after}`
  }
  return row.deducted_count != null ? String(row.deducted_count) : '—'
}
async function openDetail(row) {
  try {
    const { data } = await api.get(`/api/v1/shop/verifications/${row.id}`)
    detail.value = data
    detailVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '无查看权限')
  }
}

function selectLogTab() {
  tab.value = 'log'
  applyDateChip(query.dateRange || '7d')
  query.page = 1
  loadOperators()
  loadRecords()
}

function onDateChip(key) {
  applyDateChip(key)
  query.page = 1
  loadRecords()
}

watch(currentId, () => {
  query.page = 1
  if (tab.value === 'log') {
    loadOperators()
    loadRecords()
  }
})

onMounted(() => {
  applyDateChip('7d')
})
</script>

<template>
  <div class="a08" data-testid="shop-verifications">
    <div class="tabs">
      <button type="button" class="tab" :class="{ on: tab === 'redeem' }" @click="tab = 'redeem'">到店核销</button>
      <button type="button" class="tab" :class="{ on: tab === 'log' }" @click="selectLogTab">核销记录</button>
    </div>

    <div v-if="tab === 'redeem'" class="redeem">
      <p class="hint">请买家打开小程序「我的预约」，出示 6 位核销码</p>
      <div class="card">
        <label>核销码</label>
        <div class="digits" @paste="onPaste">
          <input
            v-for="(d, i) in codeDigits"
            :key="i"
            :ref="(el) => (codeInputs[i] = el)"
            maxlength="1"
            inputmode="numeric"
            :value="d"
            @input="onDigitInput(i, $event)"
            @keydown="onDigitKeydown(i, $event)"
          />
        </div>
        <div class="actions">
          <el-button type="primary" :loading="looking" @click="lookup">查询</el-button>
        </div>

        <div v-if="result" class="result">
          <template v-if="result.result === 'can_redeem' && result.item">
            <div class="ok-head">
              <el-tag type="success">可核销</el-tag>
              <b>校验通过</b>
            </div>
            <div class="kv"><span>买家</span><span>{{ result.item.buyer_mobile_masked || '—' }}</span></div>
            <div class="kv"><span>商品</span><span>{{ result.item.product_name || '—' }}</span></div>
            <div class="kv"><span>预约</span><span>{{ result.item.booking_slot || '—' }}</span></div>
            <div class="kv">
              <span>剩余次数</span>
              <span>
                <b>{{ result.item.remaining_count ?? '—' }}</b>
                → 核销后
                <b>{{ Math.max(0, (result.item.remaining_count ?? 1) - 1) }}</b>
              </span>
            </div>
            <div class="actions">
              <el-button v-if="canExecute" type="success" :loading="executing" @click="confirmExecute">确认核销</el-button>
              <el-button @click="clearAll">清空</el-button>
            </div>
          </template>
          <el-alert
            v-else
            :title="result.result === 'already_used' ? '已核销' : result.result === 'refunded' ? '权益已关闭' : result.result === 'exhausted' ? '次数用尽' : '无法核销'"
            :type="result.result === 'already_used' ? 'warning' : 'error'"
            :description="result.message"
            show-icon
            :closable="false"
          />
        </div>
      </div>
      <p class="subhint">支持扫码枪/粘贴 · 回车触发查询</p>
    </div>

    <div v-else v-loading="loading">
      <div class="toolbar">
        <div class="left">
          <el-input
            v-model="query.q"
            clearable
            placeholder="核销码 / 买家手机"
            style="width: 200px"
            @keyup.enter="() => { query.page = 1; loadRecords() }"
          />
          <div class="chips">
            <button
              v-for="c in DATE_CHIPS"
              :key="c.key"
              type="button"
              class="chip"
              :class="{ on: query.dateRange === c.key }"
              @click="onDateChip(c.key)"
            >
              {{ c.label }}
            </button>
          </div>
          <template v-if="query.dateRange === 'custom'">
            <el-date-picker
              v-model="query.created_from"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="起"
              style="width: 140px"
            />
            <span class="sep">—</span>
            <el-date-picker
              v-model="query.created_to"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="止"
              style="width: 140px"
              @change="() => { query.page = 1; loadRecords() }"
            />
          </template>
          <el-select
            v-if="canListAll"
            v-model="query.operator_id"
            clearable
            placeholder="操作人"
            style="width: 140px"
            @change="() => { query.page = 1; loadRecords() }"
          >
            <el-option
              v-for="op in operators"
              :key="op.user_id"
              :label="op.display_name"
              :value="op.user_id"
            />
          </el-select>
        </div>
        <div class="right">
          <el-dropdown v-if="canListAll" trigger="click" @command="(cmd) => cmd === 'current' && exportCsv()">
            <el-button :loading="exporting">导出 ▾</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="current">当前筛选</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button @click="openColSettings">列设置</el-button>
        </div>
      </div>
      <el-table :data="records" border stripe size="small" style="margin-top: 12px">
        <el-table-column v-if="colVisible.created_at" label="核销时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="colVisible.verify_code" prop="verify_code" label="核销码" width="100" />
        <el-table-column v-if="colVisible.buyer" prop="buyer_mobile_masked" label="买家" width="120" />
        <el-table-column v-if="colVisible.product_name" prop="product_name" label="商品" min-width="140" />
        <el-table-column v-if="colVisible.booking_slot" prop="booking_slot" label="预约时段" min-width="160" />
        <el-table-column v-if="colVisible.operator_name" prop="operator_name" label="操作人" width="100" />
        <el-table-column v-if="colVisible.deducted_count" label="扣次" width="90">
          <template #default="{ row }">{{ deductText(row) }}</template>
        </el-table-column>
        <el-table-column v-if="colVisible.ops" label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看</el-button>
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
          @current-change="loadRecords"
          @size-change="loadRecords"
        />
      </div>
    </div>

    <el-dialog v-model="exportDialog" title="导出任务" width="420px">
      <el-form v-if="exportTask" label-width="100px">
        <el-form-item label="范围">当前筛选</el-form-item>
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

    <el-dialog v-model="colDialog" title="列设置" width="360px">
      <el-checkbox
        v-for="c in ALL_COLS"
        :key="c.key"
        v-model="colDraft[c.key]"
        :disabled="c.locked"
        style="display: block; margin: 6px 0"
      >
        {{ c.label }}
      </el-checkbox>
      <template #footer>
        <el-button @click="colDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCols">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="420px">
      <template #header>
        <span>核销详情 · {{ detail?.verification_no || '' }}</span>
      </template>
      <el-form v-if="detail" label-width="100px">
        <el-form-item label="核销时间">{{ fmtTime(detail.created_at) }}</el-form-item>
        <el-form-item label="操作人">{{ detail.operator_name || '—' }}</el-form-item>
        <el-form-item label="买家">{{ detail.buyer_mobile_masked || '—' }}</el-form-item>
        <el-form-item label="商品">{{ detail.product_name || '—' }}</el-form-item>
        <el-form-item label="预约时段">{{ detail.booking_slot || '—' }}</el-form-item>
        <el-form-item label="核销码">{{ detail.verify_code || '—' }}</el-form-item>
        <el-form-item label="扣次">{{ deductText(detail) }}</el-form-item>
        <el-form-item>
          <el-button @click="detailVisible = false">关闭</el-button>
        </el-form-item>
      </el-form>
    </el-drawer>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 16px;
}
.tab {
  border: 0;
  background: transparent;
  padding: 8px 14px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
}
.tab.on {
  color: var(--el-color-primary);
  font-weight: 700;
  border-bottom: 2px solid var(--el-color-primary);
}
.redeem {
  max-width: 520px;
  margin: 0 auto;
}
.hint {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 20px 24px;
}
.card label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}
.digits {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-bottom: 16px;
}
.digits input {
  width: 44px;
  height: 52px;
  border: 2px solid var(--el-color-primary);
  border-radius: 8px;
  text-align: center;
  font-size: 22px;
  font-weight: 800;
}
.actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 12px;
}
.result {
  border-top: 1px solid var(--el-border-color-lighter);
  margin-top: 16px;
  padding-top: 14px;
}
.ok-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.kv {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  line-height: 1.85;
  color: var(--el-text-color-regular);
}
.kv span:first-child {
  color: var(--el-text-color-secondary);
}
.subhint {
  text-align: center;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 10px;
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
.chips {
  display: flex;
  gap: 4px;
}
.chip {
  border: 1px solid var(--el-border-color);
  background: #fff;
  border-radius: 14px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
}
.chip.on {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
  background: #f0f7ff;
  font-weight: 600;
}
.sep {
  color: #999;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
