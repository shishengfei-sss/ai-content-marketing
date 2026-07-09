<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, User } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import {
  TASK_PRIORITY_LABELS,
  TASK_PRIORITY_TYPES,
  TASK_STATUS_CHANGE_MESSAGES,
  TASK_STATUS_LABELS,
  TASK_STATUS_TYPES,
  getPrimaryTaskAction,
  getSecondaryTaskActions,
  isActiveTaskStatus,
  formatDueAtRelative,
  formatTaskDateTime,
  TASK_TIME_FIELDS,
} from '../../utils/taskMeta'

const props = defineProps({
  entityType: { type: String, required: true },
  entityId: { type: String, required: true },
  defaultAssigneeId: { type: String, default: '' },
})

const emit = defineEmits(['changed'])

const auth = useAuthStore()
const { loadMembers, resolveMemberName, members: teamMembers } = useTeamMembers()

const loading = ref(false)
const submitting = ref(false)
const tasks = ref([])
const taskFilter = ref('open')

const form = ref({
  title: '',
  description: '',
  planned_start_at: '',
  due_at: '',
  priority: 'normal',
  assignee_user_id: '',
})

const STATUS_LABELS = TASK_STATUS_LABELS

const openCount = computed(() => tasks.value.filter((t) => isActiveTaskStatus(t.status)).length)
const doneCount = computed(() => tasks.value.filter((t) => t.status === 'done').length)
const holdCount = computed(() => tasks.value.filter((t) => t.status === 'on_hold').length)

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

function resetForm() {
  form.value = {
    title: '',
    description: '',
    planned_start_at: '',
    due_at: '',
    priority: 'normal',
    assignee_user_id: props.defaultAssigneeId || auth.user?.id || '',
  }
}

async function loadTasks() {
  if (!props.entityId) return
  loading.value = true
  try {
    const params = { page_size: 50 }
    if (props.entityType === 'lead') params.lead_id = props.entityId
    else params.customer_id = props.entityId
    const { data } = await crmApi.listTasks(params)
    tasks.value = data.items || []
    emit('changed', tasks.value)
  } catch (e) {
    ElMessage.error(e.message || '任务加载失败')
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
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
    if (form.value.planned_start_at) {
      payload.planned_start_at = new Date(form.value.planned_start_at).toISOString()
    }
    if (form.value.due_at) payload.due_at = new Date(form.value.due_at).toISOString()
    if (form.value.assignee_user_id) payload.assignee_user_id = form.value.assignee_user_id
    if (props.entityType === 'lead') payload.lead_id = props.entityId
    else payload.customer_id = props.entityId
    await crmApi.createTask(payload)
    ElMessage.success('任务已创建')
    resetForm()
    await loadTasks()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

const canCreate = () => hasPermission(auth.permissions, 'crm.task.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.task.edit')
const canAssign = () => hasPermission(auth.permissions, 'crm.task.assign')

async function updateTaskStatus(row, status) {
  if (!canEdit()) return
  try {
    await crmApi.updateTask(row.id, { status })
    ElMessage.success(TASK_STATUS_CHANGE_MESSAGES[status] || '状态已更新')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}

function isOverdue(row) {
  if (!row.due_at || !isActiveTaskStatus(row.status) || row.status === 'on_hold') return false
  return new Date(row.due_at).getTime() < Date.now()
}

function statusTagType(status) {
  return TASK_STATUS_TYPES[status] || 'info'
}

function primaryAction(item) {
  return getPrimaryTaskAction(item.status)
}

function secondaryActions(item) {
  return getSecondaryTaskActions(item.status)
}

function actionButtonType(act) {
  if (!act) return 'primary'
  if (act.primary) return 'primary'
  if (act.success) return 'success'
  if (act.muted) return 'info'
  return 'warning'
}

watch(
  () => props.defaultAssigneeId,
  (id) => {
    if (id && !form.value.assignee_user_id) form.value.assignee_user_id = id
  },
)

watch(
  () => props.entityId,
  () => {
    resetForm()
    loadTasks()
  },
)

onMounted(async () => {
  await loadMembers(true)
  resetForm()
  loadTasks()
})

defineExpose({ reload: loadTasks, openCount })
</script>

<template>
  <div v-loading="loading" class="entity-tasks">
    <div class="entity-tasks__toolbar">
      <div class="entity-tasks__filters">
        <button
          type="button"
          class="entity-tasks__filter"
          :class="{ 'entity-tasks__filter--active': taskFilter === 'open' }"
          @click="taskFilter = 'open'"
        >
          待办
          <span v-if="openCount" class="entity-tasks__filter-count">{{ openCount }}</span>
        </button>
        <button
          type="button"
          class="entity-tasks__filter"
          :class="{ 'entity-tasks__filter--active': taskFilter === 'hold' }"
          @click="taskFilter = 'hold'"
        >
          挂起
          <span v-if="holdCount" class="entity-tasks__filter-count entity-tasks__filter-count--hold">
            {{ holdCount }}
          </span>
        </button>
        <button
          type="button"
          class="entity-tasks__filter"
          :class="{ 'entity-tasks__filter--active': taskFilter === 'done' }"
          @click="taskFilter = 'done'"
        >
          已完成
          <span v-if="doneCount" class="entity-tasks__filter-count entity-tasks__filter-count--muted">
            {{ doneCount }}
          </span>
        </button>
        <button
          type="button"
          class="entity-tasks__filter"
          :class="{ 'entity-tasks__filter--active': taskFilter === 'all' }"
          @click="taskFilter = 'all'"
        >
          全部
        </button>
      </div>
    </div>

    <div v-if="canCreate()" class="entity-tasks__create">
      <div class="entity-tasks__create-head">
        <span class="entity-tasks__create-title">新建任务</span>
        <span class="entity-tasks__create-hint">安排跟进、回访或资料发送</span>
      </div>
      <el-form label-position="top" class="entity-tasks__form" @submit.prevent="submitCreate">
        <el-form-item label="任务标题" required>
          <el-input v-model="form.title" placeholder="例如：发送产品方案、电话回访确认需求" />
        </el-form-item>
        <div class="entity-tasks__form-row">
          <el-form-item label="计划开始" class="entity-tasks__form-col">
            <el-date-picker
              v-model="form.planned_start_at"
              type="datetime"
              placeholder="计划何时开始"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="计划完成" class="entity-tasks__form-col">
            <el-date-picker
              v-model="form.due_at"
              type="datetime"
              placeholder="计划何时完成"
              style="width: 100%"
              :shortcuts="[
                { text: '今天 18:00', value: () => { const d = new Date(); d.setHours(18, 0, 0, 0); return d } },
                { text: '明天 10:00', value: () => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(10, 0, 0, 0); return d } },
                { text: '下周同一时间', value: () => { const d = new Date(); d.setDate(d.getDate() + 7); return d } },
              ]"
            />
          </el-form-item>
          <el-form-item label="优先级" class="entity-tasks__form-col entity-tasks__form-col--sm">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option label="低" value="low" />
              <el-option label="普通" value="normal" />
              <el-option label="高" value="high" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="canAssign()" label="执行人" class="entity-tasks__form-col">
            <el-select
              v-model="form.assignee_user_id"
              placeholder="选择执行人"
              filterable
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="m in teamMembers.filter((x) => x.is_active)"
                :key="m.user_id"
                :label="m.display_name || m.phone"
                :value="m.user_id"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="备注说明">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="补充任务背景、注意事项等（选填）"
          />
        </el-form-item>
        <div class="entity-tasks__form-actions">
          <el-button @click="resetForm">重置</el-button>
          <el-button type="primary" :loading="submitting" @click="submitCreate">创建任务</el-button>
        </div>
      </el-form>
    </div>

    <div v-if="filteredTasks.length" class="entity-tasks__list">
      <article
        v-for="item in filteredTasks"
        :key="item.id"
        class="task-card"
        :class="{
          'task-card--done': item.status === 'done',
          'task-card--hold': item.status === 'on_hold',
          'task-card--overdue': isOverdue(item),
        }"
      >
        <button
          v-if="canEdit() && isActiveTaskStatus(item.status)"
          type="button"
          class="task-card__check"
          title="标记完成"
          @click="updateTaskStatus(item, 'done')"
        >
          <span class="task-card__check-ring" />
        </button>
        <div v-else class="task-card__check task-card__check--static">
          <el-icon v-if="item.status === 'done'" class="task-card__check-done"><CircleCheck /></el-icon>
        </div>

        <div class="task-card__body">
          <div class="task-card__head">
            <h4 class="task-card__title">{{ item.title }}</h4>
            <el-tag size="small" :type="statusTagType(item.status)">
              {{ STATUS_LABELS[item.status] || item.status }}
            </el-tag>
          </div>
          <p v-if="item.description" class="task-card__desc">{{ item.description }}</p>
          <div class="task-card__times">
            <div v-for="field in TASK_TIME_FIELDS" :key="field.key" class="task-card__time-row">
              <span class="task-card__time-label">{{ field.label }}</span>
              <span
                class="task-card__time-value"
                :class="{
                  'task-card__time-value--muted': !item[field.key],
                  'task-card__time-value--overdue': field.key === 'due_at' && isOverdue(item),
                  'task-card__time-value--actual': field.key === 'started_at' || field.key === 'completed_at',
                }"
              >
                {{
                  field.key === 'due_at' && item.due_at
                    ? formatDueAtRelative(item.due_at)
                    : formatTaskDateTime(item[field.key])
                }}
              </span>
            </div>
          </div>
          <div class="task-card__meta">
            <span class="task-card__meta-item">
              <el-tag size="small" :type="TASK_PRIORITY_TYPES[item.priority] || 'info'" effect="plain">
                {{ TASK_PRIORITY_LABELS[item.priority] || item.priority }}
              </el-tag>
            </span>
            <span class="task-card__meta-item">
              <el-icon><User /></el-icon>
              {{ resolveMemberName(item.assignee_user_id, { withSelfTag: false }) }}
            </span>
          </div>
        </div>

        <div v-if="canEdit() && primaryAction(item)" class="task-card__actions">
          <el-button
            size="small"
            :type="actionButtonType(primaryAction(item))"
            @click="updateTaskStatus(item, primaryAction(item).next)"
          >
            {{ primaryAction(item).label }}
          </el-button>
          <el-dropdown
            v-if="secondaryActions(item).length"
            trigger="click"
            @command="(status) => updateTaskStatus(item, status)"
          >
            <el-button size="small" text class="task-card__more">
              更多
              <span class="task-card__more-caret">▾</span>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="act in secondaryActions(item)"
                  :key="act.key"
                  :command="act.next"
                  :divided="act.key === 'cancel'"
                >
                  {{ act.label }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </article>
    </div>

    <el-empty
      v-else
      :description="
        taskFilter === 'done'
          ? '暂无已完成任务'
          : taskFilter === 'hold'
            ? '暂无挂起任务'
            : '暂无待办任务，创建一条任务开始跟进吧'
      "
    />
  </div>
</template>

<style scoped>
.entity-tasks {
  min-height: 120px;
}

.entity-tasks__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.entity-tasks__filters {
  display: inline-flex;
  padding: 3px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
}

.entity-tasks__filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.entity-tasks__filter--active {
  background: var(--el-bg-color);
  color: var(--el-color-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.entity-tasks__filter-count {
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 600;
}

.entity-tasks__filter-count--muted {
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
}

.entity-tasks__create {
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--el-fill-color-lighter) 0%, var(--el-bg-color) 100%);
}

.entity-tasks__create-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
}

.entity-tasks__create-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.entity-tasks__create-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.entity-tasks__form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.entity-tasks__form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.entity-tasks__form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.entity-tasks__form-col {
  flex: 1;
  min-width: 180px;
  margin-bottom: 0 !important;
}

.entity-tasks__form-col--sm {
  flex: 0 0 120px;
  min-width: 120px;
}

.entity-tasks__form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 2px;
}

.entity-tasks__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-bg-color);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.task-card:hover {
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.entity-tasks__filter-count--hold {
  background: var(--el-color-warning-light-8);
  color: var(--el-color-warning);
}

.task-card--hold {
  border-color: var(--el-color-warning-light-5);
  background: linear-gradient(90deg, #fffbeb 0%, var(--el-bg-color) 28%);
}

.task-card--done {
  opacity: 0.72;
  background: var(--el-fill-color-lighter);
}

.task-card--overdue {
  border-color: var(--el-color-danger-light-5);
  background: linear-gradient(90deg, #fff5f5 0%, var(--el-bg-color) 28%);
}

.task-card__check {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

.task-card__check-ring {
  display: block;
  width: 20px;
  height: 20px;
  border: 2px solid var(--el-border-color);
  border-radius: 50%;
  transition: border-color 0.15s, background 0.15s;
}

.task-card__check:hover .task-card__check-ring {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.task-card__check--static {
  cursor: default;
}

.task-card__check-done {
  font-size: 22px;
  color: var(--el-color-success);
}

.task-card__body {
  flex: 1;
  min-width: 0;
}

.task-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.task-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--el-text-color-primary);
}

.task-card--done .task-card__title {
  text-decoration: line-through;
  color: var(--el-text-color-secondary);
}

.task-card__desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-regular);
}

.task-card__times {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.task-card__time-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.task-card__time-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.task-card__time-value {
  font-size: 12px;
  color: var(--el-text-color-primary);
  line-height: 1.4;
  word-break: break-all;
}

.task-card__time-value--muted {
  color: var(--el-text-color-placeholder);
}

.task-card__time-value--actual {
  color: var(--el-color-primary);
  font-weight: 500;
}

.task-card__time-value--overdue {
  color: var(--el-color-danger);
  font-weight: 500;
}

.task-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  margin-top: 10px;
}

.task-card__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.task-card__meta-item--overdue {
  color: var(--el-color-danger);
  font-weight: 500;
}

.task-card__actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  padding-top: 2px;
  min-width: 72px;
}

.task-card__more {
  padding: 4px 8px;
  color: var(--el-text-color-secondary);
}

.task-card__more-caret {
  margin-left: 2px;
  font-size: 11px;
}
</style>
