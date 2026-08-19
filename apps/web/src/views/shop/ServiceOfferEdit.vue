<script setup>
/**
 * A07 服务与时段。对照 PRD #a07-edit · #a07a · #a07b · #a07c
 * 预约名单只读；过期未核销由系统任务；站内信未接通。无商家代取消、无到店标记。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
const offer = ref(null)
const slots = ref([])
const slotStatus = ref('')
const slotView = ref('')
const pageMode = computed(() => (route.query.mode === 'view' ? 'view' : 'edit'))
const readonly = computed(
  () => pageMode.value === 'view' || offer.value?.status === 'off_sale' || !canWrite.value
)

const form = reactive({
  title: '',
  mode: 'booking',
  total_times: 3,
  valid_days: 90,
  duration_minutes: 60,
})

const STATUS_LABEL = { draft: '草稿', published: '已发布', off_sale: '已下架' }
const SLOT_STATUS = { open: '开放', full: '已满', closed: '已关闭' }
const BOOKING_STATUS = { booked: '待服务', completed: '已核销', cancelled: '已取消' }
const BOOKING_SOURCE = {
  expired_unredeemed: '过期未核销',
  slot_closed: '关闭时段',
  buyer_cancel: '买家取消',
}

const COL_STORAGE = 'shop.a07.slots'
const ALL_COLS = [
  { key: 'start_at', label: '开始', locked: true, defaultOn: true },
  { key: 'end_at', label: '结束', defaultOn: true },
  { key: 'capacity', label: '容量', defaultOn: true },
  { key: 'booked_count', label: '已约', defaultOn: true },
  { key: 'status', label: '状态', defaultOn: true },
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

const batchVisible = ref(false)
const batchBusy = ref(false)
const batch = reactive({
  range: [],
  capacity: 3,
  skip_weekends: true,
  skip_overlap: true,
  windows: [{ start: '10:00', end: '12:00' }],
})
const preview = ref(null)
const rosterVisible = ref(false)
const roster = ref([])
const rosterSlot = ref(null)
const closeDlg = reactive({ visible: false, row: null, busy: false })

function addMinutes(hm, minutes) {
  const [h, m] = hm.split(':').map(Number)
  const total = h * 60 + m + minutes
  const hh = String(Math.floor(total / 60) % 24).padStart(2, '0')
  const mm = String(total % 60).padStart(2, '0')
  return `${hh}:${mm}`
}

function fmtDt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function fmtSlotRange(row) {
  if (!row) return ''
  const a = fmtDt(row.start_at)
  const b = fmtDt(row.end_at)
  const endHm = b.slice(6) || b
  return a && endHm ? `${a}–${endHm}` : a
}

async function load() {
  loading.value = true
  try {
    const id = route.params.id
    const { data } = await api.get(`/api/v1/shop/service-offers/${id}`)
    offer.value = data
    form.title = data.title
    form.mode = data.mode
    form.total_times = data.total_times || 3
    form.valid_days = data.valid_days || 90
    form.duration_minutes = data.duration_minutes || 60
    if (data.mode === 'booking') await loadSlots()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadSlots() {
  const { data } = await api.get(`/api/v1/shop/service-offers/${route.params.id}/slots`, {
    params: {
      status: slotStatus.value || undefined,
      view: slotView.value || undefined,
    },
  })
  slots.value = data.items || []
}

async function save() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  saving.value = true
  try {
    const body = {
      title: form.title.trim(),
      mode: form.mode,
      duration_minutes: form.duration_minutes,
    }
    if (form.mode === 'times_card') {
      body.total_times = form.total_times
      body.valid_days = form.valid_days
    }
    const { data } = await api.patch(`/api/v1/shop/service-offers/${route.params.id}`, body)
    offer.value = data
    ElMessage.success('已保存')
    if (data.mode === 'booking') await loadSlots()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function openBatch() {
  if (offer.value?.status === 'off_sale') {
    ElMessage.warning('服务已下架')
    return
  }
  batch.windows = [{ start: '10:00', end: addMinutes('10:00', form.duration_minutes) }]
  preview.value = null
  batchVisible.value = true
}

function defaultNextStart() {
  const candidates = ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '19:00']
  const used = new Set(batch.windows.map((w) => w.start).filter(Boolean))
  const free = candidates.find((t) => !used.has(t))
  if (free) return free
  const last = batch.windows[batch.windows.length - 1]
  if (last?.start) return addMinutes(last.start, form.duration_minutes)
  return '10:00'
}

function addWindow(start) {
  const s = (start || defaultNextStart()).trim()
  if (!s) {
    ElMessage.warning('请选择开始时间')
    return
  }
  if (batch.windows.some((w) => w.start === s)) {
    ElMessage.warning('该开始时间已在列表中')
    return
  }
  batch.windows.push({ start: s, end: addMinutes(s, form.duration_minutes) })
  preview.value = null
}

function removeWindow(index) {
  if (batch.windows.length <= 1) {
    ElMessage.warning('至少保留 1 个时段')
    return
  }
  batch.windows.splice(index, 1)
  preview.value = null
}

function onStartChange(w) {
  w.end = addMinutes(w.start, form.duration_minutes)
  preview.value = null
}

function rangeDays() {
  if (!batch.range?.length) return 0
  const a = new Date(`${batch.range[0]}T00:00:00`)
  const b = new Date(`${batch.range[1]}T00:00:00`)
  return Math.round((b - a) / 86400000)
}

async function doPreview() {
  if (!batch.range?.length) {
    ElMessage.warning('请选择日期范围')
    return
  }
  if (rangeDays() > 90) {
    ElMessage.warning('日期范围不可超过 90 天')
    return
  }
  if (!batch.windows.length) {
    ElMessage.warning('请添加每日时段')
    return
  }
  try {
    const { data } = await api.post(
      `/api/v1/shop/service-offers/${route.params.id}/slots/batch-preview`,
      {
        date_from: batch.range[0],
        date_to: batch.range[1],
        daily_windows: batch.windows,
        capacity: batch.capacity,
        skip_weekends: batch.skip_weekends,
        skip_overlap: batch.skip_overlap,
      }
    )
    preview.value = data
    if (!data.will_create) ElMessage.warning('预览 0 条')
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

async function confirmBatch() {
  if (!preview.value?.will_create) {
    ElMessage.warning('请先生成预览且条数 > 0')
    return
  }
  batchBusy.value = true
  try {
    await api.post(`/api/v1/shop/service-offers/${route.params.id}/slots/batch`, {
      date_from: batch.range[0],
      date_to: batch.range[1],
      daily_windows: batch.windows,
      capacity: batch.capacity,
      skip_weekends: batch.skip_weekends,
      skip_overlap: batch.skip_overlap,
    })
    ElMessage.success('已生成时段')
    batchVisible.value = false
    await loadSlots()
    const { data } = await api.get(`/api/v1/shop/service-offers/${route.params.id}`)
    offer.value = data
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    batchBusy.value = false
  }
}

function openClose(row) {
  closeDlg.row = row
  closeDlg.visible = true
}

async function confirmClose() {
  const row = closeDlg.row
  if (!row) return
  closeDlg.busy = true
  try {
    await api.post(`/api/v1/shop/service-offers/${route.params.id}/slots/${row.id}/close`)
    ElMessage.success('已关闭')
    closeDlg.visible = false
    await loadSlots()
  } catch (e) {
    ElMessage.error(e.message || '关闭失败')
  } finally {
    closeDlg.busy = false
  }
}

async function openRoster(row) {
  rosterSlot.value = row
  try {
    const { data } = await api.get(
      `/api/v1/shop/service-offers/${route.params.id}/slots/${row.id}/bookings`
    )
    roster.value = data || []
    rosterVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载名单失败')
  }
}

watch([slotStatus, slotView], () => {
  if (form.mode === 'booking') loadSlots()
})

onMounted(load)
</script>

<template>
  <div v-loading="loading" data-testid="shop-offer-edit">
    <div class="toolbar">
      <el-button link type="primary" @click="router.push({ name: 'ShopServiceOffers' })">← 返回列表</el-button>
      <strong>{{ offer?.title || '编辑服务' }}</strong>
      <el-tag size="small">{{ STATUS_LABEL[offer?.status] || '' }}</el-tag>
      <el-tag v-if="readonly" size="small" type="info">只读</el-tag>
      <div style="flex: 1" />
      <el-button v-if="!readonly" type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <el-form label-width="120px" style="max-width: 640px; margin-top: 16px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" :disabled="readonly" maxlength="200" />
      </el-form-item>
      <el-form-item label="模式">
        <el-radio-group v-model="form.mode" :disabled="readonly">
          <el-radio value="booking">预约</el-radio>
          <el-radio value="times_card">次数卡</el-radio>
        </el-radio-group>
      </el-form-item>
      <template v-if="form.mode === 'times_card'">
        <el-form-item label="次数" required>
          <el-input-number v-model="form.total_times" :min="1" :disabled="readonly" />
        </el-form-item>
        <el-form-item label="有效天数" required>
          <el-input-number v-model="form.valid_days" :min="1" :disabled="readonly" />
        </el-form-item>
      </template>
      <el-form-item label="单次时长(分)">
        <el-input-number v-model="form.duration_minutes" :min="15" :step="15" :disabled="readonly" />
      </el-form-item>
    </el-form>

    <template v-if="form.mode === 'booking'">
      <div class="section-hd">可预约时段</div>
      <div class="toolbar">
        <div class="left">
          <el-select v-model="slotView" placeholder="全部时段" style="width: 130px">
            <el-option label="全部时段" value="" />
            <el-option label="未来时段" value="upcoming" />
            <el-option label="历史时段" value="past" />
          </el-select>
          <el-select v-model="slotStatus" clearable placeholder="状态" style="width: 120px">
            <el-option label="开放" value="open" />
            <el-option label="已满" value="full" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </div>
        <div class="right">
          <el-button @click="openColumnSettings">列设置</el-button>
          <el-button v-if="!readonly" type="primary" @click="openBatch">批量生成</el-button>
        </div>
      </div>
      <el-table :data="slots" border stripe size="small" style="margin-top: 8px">
        <template v-for="colKey in visibleKeys" :key="colKey">
        <el-table-column v-if="colKey === 'start_at'" label="开始" min-width="140">
          <template #default="{ row }">{{ fmtDt(row.start_at) }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'end_at'" label="结束" width="100">
          <template #default="{ row }">{{ fmtDt(row.end_at).slice(6) }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'capacity'" prop="capacity" label="容量" width="80" />
        <el-table-column v-if="colKey === 'booked_count'" prop="booked_count" label="已约" width="80" />
        <el-table-column v-if="colKey === 'status'" label="状态" width="90">
          <template #default="{ row }">{{ SLOT_STATUS[row.status] || row.status }}</template>
        </el-table-column>
        <el-table-column v-if="colKey === 'ops'" label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRoster(row)">预约名单</el-button>
            <el-button
              v-if="!readonly && (row.status === 'open' || row.status === 'full')"
              link
              type="danger"
              @click="openClose(row)"
            >
              关闭时段
            </el-button>
          </template>
        </el-table-column>
        </template>
      </el-table>
    </template>
    <div v-else class="times-hint">次数卡 · 无「可预约时段」区块</div>

    <el-dialog v-model="batchVisible" title="批量生成可预约时段" width="520px">
      <el-form label-width="100px">
        <el-form-item label="日期范围" required>
          <el-date-picker
            v-model="batch.range"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始"
            end-placeholder="结束"
          />
          <div class="hint">≤90 天</div>
        </el-form-item>
        <el-form-item label="每日时段" required>
          <div class="hint">结束时间默认 = 开始 + 单次时长 {{ form.duration_minutes }} 分（可改）</div>
          <div v-for="(w, i) in batch.windows" :key="i" class="win-row">
            <el-time-select v-model="w.start" start="08:00" step="00:30" end="22:00" placeholder="开始" @change="onStartChange(w)" />
            <span>—</span>
            <el-time-select v-model="w.end" start="08:00" step="00:30" end="23:00" placeholder="结束" />
            <el-button link type="danger" @click="removeWindow(i)">删除</el-button>
          </div>
          <div style="margin-top: 8px">
            <el-button size="small" @click="addWindow()">+ 添加时段</el-button>
            <span class="hint" style="margin: 0 6px">快捷：</span>
            <el-button size="small" @click="addWindow('10:00')">上午 10:00</el-button>
            <el-button size="small" @click="addWindow('14:00')">下午 14:00</el-button>
          </div>
        </el-form-item>
        <el-form-item label="容量" required>
          <el-input-number v-model="batch.capacity" :min="1" />
          <span class="hint" style="margin-left: 8px">人/时段</span>
        </el-form-item>
        <el-form-item label="生成规则（选填）">
          <el-checkbox v-model="batch.skip_weekends">跳过周末</el-checkbox>
          <el-checkbox v-model="batch.skip_overlap">跳过与已有重叠时段</el-checkbox>
        </el-form-item>
        <el-alert
          v-if="preview"
          :title="`将新增 ${preview.will_create} 个时段（跳过周末 ${preview.skipped_weekend}；重叠 ${preview.skipped_overlap}）`"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button @click="doPreview">生成预览</el-button>
        <el-button type="primary" :loading="batchBusy" :disabled="!preview?.will_create" @click="confirmBatch">确认生成</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="closeDlg.visible"
      :title="`确认关闭时段 ${fmtSlotRange(closeDlg.row)}？`"
      width="480px"
    >
      <div class="dlg-field">
        <div class="dlg-lab">关闭影响（只读）</div>
        <div class="dlg-val warn">
          买家不可新约；该时段待服务预约由系统批量取消；已核销记录保留
        </div>
      </div>
      <template #footer>
        <el-button @click="closeDlg.visible = false">取消</el-button>
        <el-button type="warning" :loading="closeDlg.busy" @click="confirmClose">确认关闭</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="rosterVisible"
      :title="rosterSlot ? `预约名单 · ${fmtSlotRange(rosterSlot)}` : '预约名单'"
      size="420px"
    >
      <div v-if="rosterSlot" class="roster-meta">
        容量 {{ rosterSlot.capacity }} · 已约 {{ rosterSlot.booked_count }} ·
        {{ SLOT_STATUS[rosterSlot.status] }}
      </div>
      <el-table :data="roster" size="small">
        <el-table-column prop="buyer_mobile_masked" label="买家" min-width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ BOOKING_STATUS[row.status] || row.status }}</template>
        </el-table-column>
        <el-table-column label="来源" min-width="100">
          <template #default="{ row }">
            {{ row.status === 'cancelled' ? BOOKING_SOURCE[row.cancel_reason] || '—' : '—' }}
          </template>
        </el-table-column>
      </el-table>
      <p v-if="rosterSlot?.status === 'closed'" class="hint">已关闭时段：名单只读</p>
      <p class="hint">名单只读，无商家代取消、无到店标记</p>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="columnDraft"
      @save="() => { saveColumnSettings(); ElMessage.success('列设置已保存') }"
    />

  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.left, .right { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.toolbar .right { margin-left: auto; }
.section-hd { margin: 20px 0 8px; font-weight: 700; color: #334155; }
.times-hint {
  margin: 16px 0;
  padding: 12px;
  text-align: center;
  color: #94a3b8;
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
  background: #f8fafc;
  font-size: 12px;
}
.win-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.roster-meta { font-size: 12px; color: #64748b; margin-bottom: 12px; }
.hint { font-size: 11px; color: #64748b; margin-top: 4px; }
.dlg-field { margin-bottom: 12px; }
.dlg-lab { font-size: 12px; color: #666; margin-bottom: 4px; }
.dlg-val {
  font-size: 13px;
  line-height: 1.6;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fafafa;
}
.dlg-val.warn { background: #fffbe6; }
</style>
