<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import { LEAD_STATUS_OPTIONS } from '@/utils/crmConstants'
import CrmEntityTasks from '@/components/crm/CrmEntityTasks.vue'
import { formatDateTime } from '@/utils/datetime'

const leadId = ref('')
const loading = ref(false)
const lead = ref(null)
const activities = ref([])
const tasks = ref([])
const taskPanelRef = ref(null)
const permissions = ref([])
const members = ref([])

const { fields, loadSchema, formatCell } = useEntitySchema('lead')

const activityForm = ref({ content: '', status: '' })
const activityStatusSheetVisible = ref(false)
const assignVisible = ref(false)
const selectedOwner = ref('')
const scoreBusy = ref(false)

const canActivity = () => hasPermission(permissions.value, 'crm.activity.create')
const canEditPerm = () => hasPermission(permissions.value, 'crm.lead.edit')
const currentUserId = ref('')
const sameUserId = (a, b) =>
  !!a && !!b && String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
const isLeadOwner = () => sameUserId(lead.value?.owner_user_id, currentUserId.value)
const canEditLead = () => canEditPerm() && isLeadOwner()
const canConvert = () => hasPermission(permissions.value, 'crm.lead.convert') && isLeadOwner()
const canAssign = () => hasPermission(permissions.value, 'crm.lead.assign')
const canDeleteLead = () => hasPermission(permissions.value, 'crm.lead.delete') && isLeadOwner()
const isConverted = () =>
  lead.value?.status === '已转化' || !!lead.value?.converted_customer_id
const reclaimVisible = ref(false)
const reclaimSaving = ref(false)
const reclaimPools = ref([])
const reclaimPoolId = ref('')

const extraFields = computed(() => {
  const extra = lead.value?.extra_data || {}
  return (fields.value || [])
    .filter((f) => f.is_active !== false && f.show_in_form && extra[f.field_key] != null && extra[f.field_key] !== '')
    .map((f) => ({
      label: f.label,
      value: formatCell(lead.value, f.field_key, f.field_type),
    }))
})

const ownerLabel = computed(() => {
  if (!lead.value?.owner_user_id) return '未分配'
  const m = members.value.find((x) => x.user_id === lead.value.owner_user_id)
  return m?.display_name || m?.phone || '负责人'
})

const selectedOwnerLabel = computed(() => {
  if (!selectedOwner.value) return '请选择负责人'
  const m = members.value.find((x) => String(x.user_id) === String(selectedOwner.value))
  return m?.display_name || m?.phone || '请选择负责人'
})

async function loadDetail() {
  if (!leadId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    currentUserId.value = user?.id || ''
    await loadSchema()
    const [leadData, timeline] = await Promise.all([
      crmApi.getLead(leadId.value),
      crmApi.listActivities({ lead_id: leadId.value }),
    ])
    lead.value = leadData
    activityForm.value.status = leadData.status || '待跟进'
    activities.value = Array.isArray(timeline) ? timeline : []
    if (canAssign()) {
      try {
        members.value = await crmApi.listAssignableOwners({
          include_user_id: leadData.owner_user_id || undefined,
        })
        if (!Array.isArray(members.value)) members.value = []
      } catch {
        members.value = []
      }
    }
    await taskPanelRef.value?.reload()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openAssign() {
  selectedOwner.value = lead.value?.owner_user_id || ''
  assignVisible.value = true
}

async function recalculateScore() {
  if (!canEditLead() || scoreBusy.value) return
  scoreBusy.value = true
  try {
    const data = await crmApi.recalculateLeadScore(leadId.value)
    lead.value = data
    uni.showToast({ title: '评分已重算', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: e.message || '重算失败', icon: 'none' })
  } finally {
    scoreBusy.value = false
  }
}

async function submitAssign() {
  if (!selectedOwner.value) {
    uni.showToast({ title: '请选择负责人', icon: 'none' })
    return
  }
  try {
    await crmApi.updateLead(leadId.value, { owner_user_id: selectedOwner.value })
    assignVisible.value = false
    try {
      const leadData = await crmApi.getLead(leadId.value)
      lead.value = leadData
      uni.showToast({ title: '已分配', icon: 'success' })
      if (canAssign()) {
        members.value = await crmApi.listAssignableOwners({
          include_user_id: leadData.owner_user_id || undefined,
        }).catch(() => [])
        if (!Array.isArray(members.value)) members.value = []
      }
    } catch (e) {
      const msg = e.message || ''
      if (e.status === 403 || msg.includes('无权访问')) {
        uni.showToast({ title: '已分配，已不在可见范围', icon: 'none' })
        setTimeout(() => {
          uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/crm/leads' }) })
        }, 400)
        return
      }
      uni.showToast({ title: msg || '分配后刷新失败', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: e.message || '分配失败', icon: 'none' })
  }
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    uni.showToast({ title: '请填写跟进内容', icon: 'none' })
    return
  }
  try {
    const body = {
      lead_id: leadId.value,
      activity_type: 'call',
      content: activityForm.value.content,
    }
    if (canEditLead() && activityForm.value.status) {
      body.status = activityForm.value.status
    }
    await crmApi.createActivity(body)
    uni.showToast({ title: '已添加跟进', icon: 'success' })
    activityForm.value.content = ''
    closeActivityStatusSheet()
    const [timeline, leadData] = await Promise.all([
      crmApi.listActivities({ lead_id: leadId.value }),
      crmApi.getLead(leadId.value),
    ])
    activities.value = Array.isArray(timeline) ? timeline : []
    lead.value = leadData
    activityForm.value.status = leadData.status || '待跟进'
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  }
}

function openActivityStatusSheet() {
  activityStatusSheetVisible.value = true
}

function closeActivityStatusSheet() {
  activityStatusSheetVisible.value = false
}

function pickActivityStatus(value) {
  activityForm.value = { ...activityForm.value, status: value }
  closeActivityStatusSheet()
}

function onTasksChanged(list) {
  tasks.value = list
}

async function handleConvert() {
  if (!canConvert()) return
  try {
    const { confirm } = await new Promise((resolve) => {
      uni.showModal({
        title: '转化客户',
        content: '是否同时创建商机？',
        confirmText: '创建商机',
        cancelText: '仅转客户',
        success: resolve,
        fail: () => resolve({ confirm: false, cancel: true }),
      })
    })
    const createDeal = !!confirm

    const doConvert = (body) => crmApi.convertLead(leadId.value, body)

    let data
    try {
      data = await doConvert({ force_create: false, create_deal: createDeal })
    } catch (err) {
      const candidates = err?.detail?.duplicate_candidates
      if (err.status === 409 && Array.isArray(candidates) && candidates.length) {
        const choice = await new Promise((resolve) => {
          uni.showModal({
            title: '发现重复客户',
            content: `疑似重复 ${candidates.length} 个。合并到已有客户，或强制新建？`,
            confirmText: '合并',
            cancelText: '强制新建',
            success: (r) => resolve(r.confirm ? 'merge' : r.cancel ? 'force' : 'close'),
            fail: () => resolve('close'),
          })
        })
        if (choice === 'close') return
        if (choice === 'merge') {
          data = await doConvert({
            force_create: false,
            merge_into_customer_id: candidates[0],
            create_deal: createDeal,
          })
        } else {
          data = await doConvert({ force_create: true, create_deal: createDeal })
        }
      } else {
        throw err
      }
    }

    uni.showToast({
      title: data?.deal_id ? '已转化并创建商机' : data?.merged ? '已合并到客户' : '已转化为客户',
      icon: 'success',
    })
    if (data?.customer_id) {
      setTimeout(() => {
        uni.navigateTo({ url: `/pages/crm/customer-detail?id=${data.customer_id}` })
      }, 400)
    } else {
      loadDetail()
    }
  } catch (e) {
    if (e.status === 409 && String(e.message || '').includes('已转化')) {
      loadDetail()
    }
    uni.showToast({ title: e.message || '转化失败', icon: 'none' })
  }
}

async function openReclaim() {
  if (!canEditLead()) return
  try {
    const pools = await crmApi.listLeadPools()
    reclaimPools.value = Array.isArray(pools) ? pools : []
    if (!reclaimPools.value.length) {
      uni.showToast({ title: '暂无线索公海，请先在 Web 设置中创建', icon: 'none' })
      return
    }
    reclaimPoolId.value = reclaimPools.value[0].id
    reclaimVisible.value = true
  } catch (e) {
    uni.showToast({ title: e.message || '加载公海失败', icon: 'none' })
  }
}

async function submitReclaim() {
  if (!reclaimPoolId.value) {
    uni.showToast({ title: '请选择公海', icon: 'none' })
    return
  }
  reclaimSaving.value = true
  try {
    await crmApi.reclaimLeadToPool(leadId.value, { pool_id: reclaimPoolId.value })
    uni.showToast({ title: '已退回公海', icon: 'success' })
    reclaimVisible.value = false
    setTimeout(() => uni.navigateBack(), 400)
  } catch (e) {
    uni.showToast({ title: e.message || '退回失败', icon: 'none' })
  } finally {
    reclaimSaving.value = false
  }
}

async function handleDelete() {
  if (!canDeleteLead()) return
  const { confirm } = await new Promise((resolve) => {
    uni.showModal({
      title: '删除线索',
      content: `确定删除「${lead.value?.company_name || ''}」？`,
      success: resolve,
      fail: () => resolve({ confirm: false }),
    })
  })
  if (!confirm) return
  try {
    await crmApi.deleteLead(leadId.value)
    uni.showToast({ title: '已删除', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 400)
  } catch (e) {
    uni.showToast({ title: e.message || '删除失败', icon: 'none' })
  }
}

function openConvertedCustomer() {
  const id = lead.value?.converted_customer_id
  if (!id) return
  uni.navigateTo({ url: `/pages/crm/customer-detail?id=${id}` })
}

onLoad((query) => {
  leadId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="lead" class="card">
      <view class="head">
        <text class="title">{{ lead.company_name }}</text>
        <text class="status">{{ lead.status }}</text>
      </view>
      <text class="meta">{{ lead.contact_name || '—' }} · {{ lead.mobile || '—' }}</text>
      <text class="meta">来源：{{ lead.source || '—' }} · 评分：{{ lead.lead_score ?? '—' }}</text>
      <text v-if="lead.utm_source || lead.landing_url" class="meta">
        UTM：{{ lead.utm_source || '—' }}
        <text v-if="lead.utm_campaign"> / {{ lead.utm_campaign }}</text>
      </text>
      <text v-if="lead.landing_url" class="meta utm-url">落地页：{{ lead.landing_url }}</text>
      <text v-if="lead.title || lead.department" class="meta">
        {{ [lead.title, lead.department].filter(Boolean).join(' · ') }}
      </text>
      <text class="meta">负责人：{{ ownerLabel }}</text>
      <view v-if="extraFields.length" class="extra">
        <text v-for="item in extraFields" :key="item.label" class="extra__line">
          {{ item.label }}：{{ item.value }}
        </text>
      </view>
      <view class="acts">
        <button v-if="canEditLead()" class="btn" size="mini" :loading="scoreBusy" @click="recalculateScore">
          重算评分
        </button>
        <button v-if="canAssign()" class="btn" size="mini" @click="openAssign">分配负责人</button>
        <button v-if="canEditLead()" class="btn" size="mini" @click="openReclaim">退回公海</button>
        <button
          v-if="lead.converted_customer_id"
          class="btn btn--primary"
          size="mini"
          @click="openConvertedCustomer"
        >
          查看客户
        </button>
        <button v-if="canConvert() && !isConverted()" class="btn btn--primary" size="mini" @click="handleConvert">
          转化客户
        </button>
        <button v-if="canDeleteLead()" class="btn btn--danger" size="mini" @click="handleDelete">删除</button>
      </view>
    </view>

    <view class="section">
      <text class="section__title">跟进</text>
      <view v-if="canActivity()" class="form">
        <textarea
          v-model="activityForm.content"
          class="textarea"
          placeholder="跟进内容"
          :adjust-position="true"
          :cursor-spacing="20"
        />
        <view
          v-if="canEditLead() && !isConverted()"
          class="status-pick"
          @tap="openActivityStatusSheet"
        >
          <text class="status-pick__label">线索状态</text>
          <text class="status-pick__value">{{ activityForm.status || '请选择' }}</text>
          <text class="status-pick__arrow">▾</text>
        </view>
        <view v-else-if="isConverted()" class="status-pick status-pick--readonly">
          <text class="status-pick__label">线索状态</text>
          <text class="status-pick__value">已转化</text>
        </view>
        <button class="btn btn--primary" size="mini" hover-class="none" @tap="submitActivity">提交</button>
      </view>
      <view v-for="item in activities" :key="item.id" class="line">
        <text class="line__time">{{ formatDateTime(item.created_at) }}</text>
        <text>{{ item.content }}</text>
      </view>
      <view v-if="!activities.length" class="empty">暂无跟进</view>
    </view>

    <view class="section">
      <text class="section__title">任务</text>
      <CrmEntityTasks
        ref="taskPanelRef"
        entity-type="lead"
        :entity-id="leadId"
        @changed="onTasksChanged"
      />
    </view>

    <view v-if="activityStatusSheetVisible" class="select-sheet" @tap.stop>
      <view class="select-sheet__bar">
        <text class="select-sheet__cancel" @tap="closeActivityStatusSheet">取消</text>
        <text class="select-sheet__title">选择线索状态</text>
        <text class="select-sheet__ok" @tap="closeActivityStatusSheet">完成</text>
      </view>
      <scroll-view scroll-y class="select-sheet__scroll">
        <view
          v-for="opt in LEAD_STATUS_OPTIONS"
          :key="opt"
          class="select-sheet__opt"
          :class="{ 'select-sheet__opt--active': opt === activityForm.status }"
          @tap="pickActivityStatus(opt)"
        >
          {{ opt }}
        </view>
      </scroll-view>
    </view>

    <view v-if="assignVisible" class="mask" @click="assignVisible = false">
      <view class="dialog" @click.stop>
        <text class="dialog__title">分配负责人</text>
        <text class="dialog__hint">仅可分配给本人、下属或同级别销售经理</text>
        <picker
          mode="selector"
          :range="members.map((m) => m.display_name || m.phone)"
          @change="(e) => (selectedOwner = members[e.detail.value]?.user_id || '')"
        >
          <view class="picker">{{ selectedOwnerLabel }}</view>
        </picker>
        <view class="dialog__acts">
          <button class="btn" @click="assignVisible = false">取消</button>
          <button class="btn btn--primary" @click="submitAssign">保存</button>
        </view>
      </view>
    </view>

    <view v-if="reclaimVisible" class="mask" @click="reclaimVisible = false">
      <view class="dialog" @click.stop>
        <text class="dialog__title">退回公海</text>
        <picker
          mode="selector"
          :range="reclaimPools.map((p) => p.name)"
          @change="(e) => (reclaimPoolId = reclaimPools[e.detail.value]?.id || '')"
        >
          <view class="picker">
            {{ reclaimPools.find((p) => p.id === reclaimPoolId)?.name || '选择公海' }}
          </view>
        </picker>
        <view class="dialog__acts">
          <button class="btn" @click="reclaimVisible = false">取消</button>
          <button class="btn btn--primary" :loading="reclaimSaving" @click="submitReclaim">确认退回</button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 12px;
}

.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.status {
  font-size: 12px;
  color: #1677ff;
}

.meta {
  display: block;
  margin-top: 8px;
  color: #64748b;
  font-size: 13px;
}

.extra {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.extra__line {
  display: block;
  font-size: 13px;
  color: #475569;
  margin-top: 4px;
}

.acts {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}

.section__title {
  font-weight: 600;
  margin-bottom: 10px;
  display: block;
}

.form {
  margin-bottom: 10px;
}

.input,
.textarea {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 14px;
  box-sizing: border-box;
  background: #fff;
  color: #1e293b;
  pointer-events: auto;
}

.input {
  min-height: 40px;
  height: 40px;
  line-height: 20px;
}

.textarea {
  min-height: 80px;
}

.line {
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
}

.line__time {
  display: block;
  color: #94a3b8;
  font-size: 12px;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
}

.btn--danger {
  background: #fff1f0;
  color: #cf1322;
  border: 1px solid #ffa39e;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 16px 0;
}

.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.dialog {
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
}

.dialog__title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  display: block;
}

.dialog__hint {
  display: block;
  font-size: 12px;
  color: #8c8c8c;
  margin: -4px 0 12px;
  line-height: 1.4;
}

.picker {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 12px;
}

.status-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 12px;
  margin-bottom: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-sizing: border-box;
}

.status-pick--readonly {
  background: #f8fafc;
  border-style: dashed;
}

.status-pick__label {
  flex-shrink: 0;
  font-size: 14px;
  color: #64748b;
}

.status-pick__value {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: #1e293b;
  font-weight: 500;
  text-align: right;
}

.status-pick__arrow {
  flex-shrink: 0;
  font-size: 12px;
  color: #94a3b8;
}

.select-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1102;
  background: #fff;
  border-radius: 16px 16px 0 0;
  max-height: 52vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.12);
}

.select-sheet__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.select-sheet__title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.select-sheet__cancel {
  color: #64748b;
  font-size: 15px;
}

.select-sheet__ok {
  color: #1677ff;
  font-size: 15px;
  font-weight: 600;
}

.select-sheet__scroll {
  flex: 1;
  min-height: 0;
  max-height: calc(52vh - 48px);
}

.select-sheet__opt {
  padding: 14px 16px;
  font-size: 15px;
  color: #334155;
  border-bottom: 1px solid #f8fafc;
  text-align: center;
}

.select-sheet__opt--active {
  color: #1677ff;
  font-weight: 600;
  background: #f0f7ff;
}

.dialog__acts {
  display: flex;
  gap: 10px;
}

.btn {
  flex: 1;
  font-size: 14px;
}
</style>
