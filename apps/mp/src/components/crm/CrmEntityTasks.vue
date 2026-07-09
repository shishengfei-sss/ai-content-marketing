<script setup>
import { computed, ref, watch } from 'vue'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import {
  TASK_STATUS_LABELS,
  TASK_STATUS_CHANGE_MESSAGES,
  TASK_PRIORITY_LABELS,
  TASK_TIME_FIELDS,
  PRIORITY_OPTIONS,
  getTaskStatusActions,
  isActiveTaskStatus,
  formatTaskDateTime,
  formatDueAtRelative,
  datetimeLocalToIso,
} from '@/utils/taskMeta'

const props = defineProps({
  entityType: { type: String, required: true },
  entityId: { type: String, required: true },
})

const emit = defineEmits(['changed'])

const permissions = ref([])
const loading = ref(false)
const submitting = ref(false)
const tasks = ref([])
const taskFilter = ref('open')
const createExpanded = ref(true)
const prioritySheetVisible = ref(false)

const form = ref({
  title: '',
  description: '',
  planned_start_at: '',
  due_at: '',
  priority: 'normal',
})

const canCreate = () => hasPermission(permissions.value, 'crm.task.create')
const canEdit = () => hasPermission(permissions.value, 'crm.task.edit')

const openCount = computed(() => tasks.value.filter((t) => isActiveTaskStatus(t.status)).length)
const holdCount = computed(() => tasks.value.filter((t) => t.status === 'on_hold').length)
const doneCount = computed(() => tasks.value.filter((t) => t.status === 'done').length)

const filteredTasks = computed(() => {
  if (taskFilter.value === 'done') {
    return tasks.value.filter((t) => t.status === 'done' || t.status === 'cancelled')
  }
  if (taskFilter.value === 'hold') {
    return tasks.value.filter((t) => t.status === 'on_hold')
  }
  if (taskFilter.value === 'open') {
    return tasks.value.filter((t) => isActiveTaskStatus(t.status))
  }
  return tasks.value
})

const priorityLabel = computed(
  () => PRIORITY_OPTIONS.find((p) => p.value === form.value.priority)?.label || '普通',
)

function resetForm() {
  form.value = {
    title: '',
    description: '',
    planned_start_at: '',
    due_at: '',
    priority: 'normal',
  }
}

function onTitleInput(e) {
  form.value.title = e.detail?.value ?? e.target?.value ?? ''
}

function onDescInput(e) {
  form.value.description = e.detail?.value ?? e.target?.value ?? ''
}

function onPlannedStartInput(e) {
  form.value.planned_start_at = e.detail?.value ?? e.target?.value ?? ''
}

function onDueInput(e) {
  form.value.due_at = e.detail?.value ?? e.target?.value ?? ''
}

function pickPriority(value) {
  form.value.priority = value
  prioritySheetVisible.value = false
}

async function loadTasks() {
  if (!props.entityId) return
  loading.value = true
  try {
    const params = { page_size: 50 }
    if (props.entityType === 'lead') params.lead_id = props.entityId
    else params.customer_id = props.entityId
    const data = await crmApi.listTasks(params)
    tasks.value = data.items || []
    emit('changed', tasks.value)
  } catch (e) {
    uni.showToast({ title: e.message || '任务加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  if (!form.value.title.trim()) {
    uni.showToast({ title: '请填写任务标题', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      priority: form.value.priority,
      status: 'open',
    }
    if (form.value.description.trim()) payload.description = form.value.description.trim()
    const planned = datetimeLocalToIso(form.value.planned_start_at)
    const due = datetimeLocalToIso(form.value.due_at)
    if (planned) payload.planned_start_at = planned
    if (due) payload.due_at = due
    if (props.entityType === 'lead') payload.lead_id = props.entityId
    else payload.customer_id = props.entityId
    await crmApi.createTask(payload)
    uni.showToast({ title: '任务已创建', icon: 'success' })
    resetForm()
    await loadTasks()
  } catch (e) {
    uni.showToast({ title: e.message || '创建失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

async function updateTaskStatus(item, status) {
  if (!canEdit()) return
  try {
    await crmApi.updateTask(item.id, { status })
    uni.showToast({ title: TASK_STATUS_CHANGE_MESSAGES[status] || '已更新', icon: 'success' })
    await loadTasks()
  } catch (e) {
    uni.showToast({ title: e.message || '更新失败', icon: 'none' })
  }
}

function isOverdue(item) {
  if (!item.due_at || !isActiveTaskStatus(item.status) || item.status === 'on_hold') return false
  return new Date(item.due_at).getTime() < Date.now()
}

function statusClass(status) {
  return {
    open: 'task-status--open',
    in_progress: 'task-status--progress',
    on_hold: 'task-status--hold',
    done: 'task-status--done',
    cancelled: 'task-status--cancel',
  }[status] || ''
}

function actionClass(act) {
  if (act.primary) return 'task-action--primary'
  if (act.muted) return 'task-action--muted'
  if (act.next === 'done') return 'task-action--done'
  return 'task-action--hold'
}

watch(
  () => props.entityId,
  () => {
    resetForm()
    loadTasks()
  },
)

async function init() {
  const user = await ensureSession()
  permissions.value = user?.permissions || []
  resetForm()
  loadTasks()
}

init()

defineExpose({ reload: loadTasks })
</script>

<template>
  <view class="entity-tasks">
    <view class="entity-tasks__filters">
      <view
        class="entity-tasks__filter"
        :class="{ 'entity-tasks__filter--active': taskFilter === 'open' }"
        @tap="taskFilter = 'open'"
      >
        <text>待办</text>
        <text v-if="openCount" class="entity-tasks__badge">{{ openCount }}</text>
      </view>
      <view
        class="entity-tasks__filter"
        :class="{ 'entity-tasks__filter--active': taskFilter === 'hold' }"
        @tap="taskFilter = 'hold'"
      >
        <text>挂起</text>
        <text v-if="holdCount" class="entity-tasks__badge entity-tasks__badge--hold">{{ holdCount }}</text>
      </view>
      <view
        class="entity-tasks__filter"
        :class="{ 'entity-tasks__filter--active': taskFilter === 'done' }"
        @tap="taskFilter = 'done'"
      >
        <text>已完成</text>
        <text v-if="doneCount" class="entity-tasks__badge entity-tasks__badge--muted">{{ doneCount }}</text>
      </view>
    </view>

    <view v-if="canCreate()" class="entity-tasks__create">
      <view class="entity-tasks__create-head" @tap="createExpanded = !createExpanded">
        <text class="entity-tasks__create-title">新建任务</text>
        <text class="entity-tasks__create-toggle">{{ createExpanded ? '收起 ▴' : '展开 ▾' }}</text>
      </view>
      <view v-if="createExpanded" class="entity-tasks__form">
        <input
          :value="form.title"
          class="input"
          type="text"
          placeholder="任务标题，如：发送方案、电话回访"
          :adjust-position="true"
          :cursor-spacing="20"
          @input="onTitleInput"
        />
        <textarea
          :value="form.description"
          class="textarea textarea--sm"
          placeholder="备注说明（选填）"
          :adjust-position="true"
          :cursor-spacing="20"
          @input="onDescInput"
        />
        <view class="entity-tasks__form-row">
          <view class="entity-tasks__field">
            <text class="entity-tasks__label">计划开始</text>
            <input
              :value="form.planned_start_at"
              class="input input--dt"
              type="datetime-local"
              @input="onPlannedStartInput"
            />
          </view>
          <view class="entity-tasks__field">
            <text class="entity-tasks__label">计划完成</text>
            <input
              :value="form.due_at"
              class="input input--dt"
              type="datetime-local"
              @input="onDueInput"
            />
          </view>
        </view>
        <view class="status-pick" @tap="prioritySheetVisible = true">
          <text class="status-pick__label">优先级</text>
          <text class="status-pick__value">{{ priorityLabel }}</text>
          <text class="status-pick__arrow">▾</text>
        </view>
        <view class="entity-tasks__form-actions">
          <view class="btn btn--ghost" hover-class="none" @tap="resetForm">重置</view>
          <view class="btn btn--primary" hover-class="none" @tap="submitCreate">
            {{ submitting ? '创建中…' : '创建任务' }}
          </view>
        </view>
      </view>
    </view>

    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="filteredTasks.length" class="entity-tasks__list">
      <view
        v-for="item in filteredTasks"
        :key="item.id"
        class="task-card"
        :class="{
          'task-card--done': item.status === 'done',
          'task-card--hold': item.status === 'on_hold',
          'task-card--overdue': isOverdue(item),
        }"
      >
        <view class="task-card__head">
          <text class="task-card__title" :class="{ 'task-card__title--done': item.status === 'done' }">
            {{ item.title }}
          </text>
          <text class="task-status" :class="statusClass(item.status)">
            {{ TASK_STATUS_LABELS[item.status] || item.status }}
          </text>
        </view>
        <text v-if="item.description" class="task-card__desc">{{ item.description }}</text>
        <view class="task-card__times">
          <view v-for="field in TASK_TIME_FIELDS" :key="field.key" class="task-card__time-row">
            <text class="task-card__time-label">{{ field.label }}</text>
            <text
              class="task-card__time-value"
              :class="{
                'task-card__time-value--actual': field.actual && item[field.key],
                'task-card__time-value--overdue': field.key === 'due_at' && isOverdue(item),
              }"
            >
              {{
                field.key === 'due_at' && item.due_at
                  ? formatDueAtRelative(item.due_at)
                  : formatTaskDateTime(item[field.key], { empty: '—' })
              }}
            </text>
          </view>
        </view>
        <view class="task-card__meta">
          <text class="task-card__priority">优先级：{{ TASK_PRIORITY_LABELS[item.priority] || item.priority }}</text>
        </view>
        <view v-if="canEdit() && getTaskStatusActions(item.status).length" class="task-card__actions">
          <view
            v-for="act in getTaskStatusActions(item.status)"
            :key="act.key"
            class="task-action"
            :class="actionClass(act)"
            hover-class="none"
            @tap="updateTaskStatus(item, act.next)"
          >
            {{ act.label }}
          </view>
        </view>
      </view>
    </view>
    <view v-else class="empty">
      {{ taskFilter === 'done' ? '暂无已完成任务' : taskFilter === 'hold' ? '暂无挂起任务' : '暂无待办任务' }}
    </view>

    <view v-if="prioritySheetVisible" class="select-sheet" @tap.stop>
      <view class="select-sheet__bar">
        <text class="select-sheet__cancel" @tap="prioritySheetVisible = false">取消</text>
        <text class="select-sheet__title">选择优先级</text>
        <text class="select-sheet__ok" @tap="prioritySheetVisible = false">完成</text>
      </view>
      <scroll-view scroll-y class="select-sheet__scroll">
        <view
          v-for="opt in PRIORITY_OPTIONS"
          :key="opt.value"
          class="select-sheet__opt"
          :class="{ 'select-sheet__opt--active': form.priority === opt.value }"
          @tap="pickPriority(opt.value)"
        >
          {{ opt.label }}
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<style scoped>
.entity-tasks__filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 3px;
  background: #f1f5f9;
  border-radius: 10px;
}

.entity-tasks__filter {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 34px;
  border-radius: 8px;
  font-size: 13px;
  color: #64748b;
}

.entity-tasks__filter--active {
  background: #fff;
  color: #1677ff;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.entity-tasks__badge {
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #e6f4ff;
  color: #1677ff;
  font-size: 11px;
  text-align: center;
}

.entity-tasks__badge--hold {
  background: #fef3c7;
  color: #d97706;
}

.entity-tasks__badge--muted {
  background: #e2e8f0;
  color: #64748b;
}

.entity-tasks__create {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.entity-tasks__create-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.entity-tasks__create-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.entity-tasks__create-toggle {
  font-size: 12px;
  color: #94a3b8;
}

.entity-tasks__form {
  margin-top: 12px;
}

.entity-tasks__form-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 8px;
}

.entity-tasks__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.entity-tasks__label {
  font-size: 12px;
  color: #64748b;
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

.input--dt {
  height: auto;
  min-height: 40px;
  font-size: 13px;
}

.textarea--sm {
  min-height: 64px;
}

.entity-tasks__form-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.btn {
  flex: 1;
  height: 40px;
  line-height: 40px;
  text-align: center;
  border-radius: 8px;
  font-size: 14px;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
}

.btn--ghost {
  background: #fff;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.entity-tasks__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-card {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}

.task-card--hold {
  border-color: #fcd34d;
  background: linear-gradient(180deg, #fffbeb 0%, #fff 40%);
}

.task-card--overdue {
  border-color: #fecaca;
  background: linear-gradient(180deg, #fff5f5 0%, #fff 40%);
}

.task-card--done {
  opacity: 0.75;
  background: #f8fafc;
}

.task-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.task-card__title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.4;
}

.task-card__title--done {
  text-decoration: line-through;
  color: #94a3b8;
}

.task-status {
  flex-shrink: 0;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
}

.task-status--open {
  background: #e6f4ff;
  color: #1677ff;
}

.task-status--progress {
  background: #dbeafe;
  color: #2563eb;
}

.task-status--hold {
  background: #fef3c7;
  color: #d97706;
}

.task-status--done {
  background: #dcfce7;
  color: #16a34a;
}

.task-status--cancel {
  background: #f1f5f9;
  color: #64748b;
}

.task-card__desc {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.task-card__times {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin-top: 10px;
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.task-card__time-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.task-card__time-label {
  font-size: 11px;
  color: #94a3b8;
}

.task-card__time-value {
  font-size: 12px;
  color: #334155;
  word-break: break-all;
}

.task-card__time-value--actual {
  color: #1677ff;
  font-weight: 500;
}

.task-card__time-value--overdue {
  color: #ef4444;
  font-weight: 500;
}

.task-card__meta {
  margin-top: 8px;
}

.task-card__priority {
  font-size: 12px;
  color: #64748b;
}

.task-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.task-action {
  flex: 1;
  min-width: calc(50% - 4px);
  height: 34px;
  line-height: 34px;
  text-align: center;
  border-radius: 8px;
  font-size: 13px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  box-sizing: border-box;
}

.task-action--primary {
  border-color: #1677ff;
  background: #1677ff;
  color: #fff;
}

.task-action--done {
  border-color: #22c55e;
  color: #16a34a;
}

.task-action--hold {
  border-color: #fcd34d;
  color: #d97706;
}

.task-action--muted {
  color: #94a3b8;
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

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 16px 0;
  font-size: 13px;
}
</style>
