<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import { LEAD_STATUS_OPTIONS } from '@/utils/crmConstants'
import CrmEntityTasks from '@/components/crm/CrmEntityTasks.vue'

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

const canActivity = () => hasPermission(permissions.value, 'crm.activity.create')
const canEditLead = () => hasPermission(permissions.value, 'crm.lead.edit')
const canConvert = () => hasPermission(permissions.value, 'crm.lead.convert')
const canAssign = () => hasPermission(permissions.value, 'crm.lead.assign')

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

async function loadDetail() {
  if (!leadId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    await loadSchema()
    if (canAssign()) {
      try {
        members.value = await teamApi.listMembers()
        if (!Array.isArray(members.value)) members.value = []
      } catch {
        members.value = []
      }
    }
    const [leadData, timeline] = await Promise.all([
      crmApi.getLead(leadId.value),
      crmApi.listActivities({ lead_id: leadId.value }),
    ])
    lead.value = leadData
    activityForm.value.status = leadData.status || '待跟进'
    activities.value = Array.isArray(timeline) ? timeline : []
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

async function submitAssign() {
  if (!selectedOwner.value) {
    uni.showToast({ title: '请选择负责人', icon: 'none' })
    return
  }
  try {
    await crmApi.updateLead(leadId.value, { owner_user_id: selectedOwner.value })
    uni.showToast({ title: '已分配', icon: 'success' })
    assignVisible.value = false
    loadDetail()
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
    await crmApi.convertLead(leadId.value)
    uni.showToast({ title: '已转化', icon: 'success' })
    loadDetail()
  } catch (e) {
    uni.showToast({ title: e.message || '转化失败', icon: 'none' })
  }
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
      <text class="meta">负责人：{{ ownerLabel }}</text>
      <view v-if="extraFields.length" class="extra">
        <text v-for="item in extraFields" :key="item.label" class="extra__line">
          {{ item.label }}：{{ item.value }}
        </text>
      </view>
      <view class="acts">
        <button v-if="canAssign()" class="btn" size="mini" @click="openAssign">分配负责人</button>
        <button v-if="canConvert() && lead.status !== '已转化'" class="btn btn--primary" size="mini" @click="handleConvert">
          转化客户
        </button>
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
          v-if="canEditLead()"
          class="status-pick"
          @tap="openActivityStatusSheet"
        >
          <text class="status-pick__label">线索状态</text>
          <text class="status-pick__value">{{ activityForm.status || '请选择' }}</text>
          <text class="status-pick__arrow">▾</text>
        </view>
        <button class="btn btn--primary" size="mini" hover-class="none" @tap="submitActivity">提交</button>
      </view>
      <view v-for="item in activities" :key="item.id" class="line">
        <text class="line__time">{{ item.created_at }}</text>
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
        <picker
          mode="selector"
          :range="members.map((m) => m.display_name || m.phone)"
          @change="(e) => (selectedOwner = members[e.detail.value]?.user_id || '')"
        >
          <view class="picker">{{ ownerLabel }}</view>
        </picker>
        <view class="dialog__acts">
          <button class="btn" @click="assignVisible = false">取消</button>
          <button class="btn btn--primary" @click="submitAssign">保存</button>
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
