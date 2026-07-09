<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
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
  formatTaskDateTime,
  getPrimaryTaskAction,
  getSecondaryTaskActions,
  isActiveTaskStatus,
} from '../../utils/taskMeta'

const SEARCH_DEBOUNCE_MS = 300

const DUE_SHORTCUTS = [
  {
    text: '今天 18:00',
    value: () => {
      const d = new Date()
      d.setHours(18, 0, 0, 0)
      return d
    },
  },
  {
    text: '明天 10:00',
    value: () => {
      const d = new Date()
      d.setDate(d.getDate() + 1)
      d.setHours(10, 0, 0, 0)
      return d
    },
  },
  {
    text: '下周同一时间',
    value: () => {
      const d = new Date()
      d.setDate(d.getDate() + 7)
      return d
    },
  },
]

const route = useRoute()
const auth = useAuthStore()
const { loadMembers, resolveMemberName, members: teamMembers } = useTeamMembers()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const appliedSearchKeyword = ref('')
let searchDebounceTimer = null
const statusFilter = ref('')
const priorityFilter = ref('')
const assigneeFilter = ref('')
const dueRange = ref([])
const dueTodayFilter = ref(false)
const dueThisWeekFilter = ref(false)
const overdueFilter = ref(false)

const createVisible = ref(false)
const creating = ref(false)
const linkType = ref('none')
const linkOptions = ref([])
const linkLoading = ref(false)
const campaignOptions = ref([])
const form = ref({
  title: '',
  description: '',
  planned_start_at: '',
  due_at: '',
  priority: 'normal',
  status: 'open',
  assignee_user_id: '',
  link_id: '',
  campaign_id: '',
})

const canCreate = () => hasPermission(auth.permissions, 'crm.task.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.task.edit')
const canAssign = () => hasPermission(auth.permissions, 'crm.task.assign')

const activeQuickFilter = computed(() => {
  if (overdueFilter.value) return 'overdue'
  if (dueTodayFilter.value) return 'today'
  if (dueThisWeekFilter.value) return 'week'
  return ''
})

const hasActiveFilters = computed(() =>
  Boolean(
    appliedSearchKeyword.value.trim() ||
      statusFilter.value ||
      priorityFilter.value ||
      assigneeFilter.value ||
      (dueRange.value && dueRange.value.length === 2) ||
      dueTodayFilter.value ||
      dueThisWeekFilter.value ||
      overdueFilter.value,
  ),
)

async function loadTasks() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    const q = appliedSearchKeyword.value.trim()
    if (q) params.q = q
    if (statusFilter.value) params.status = statusFilter.value
    if (priorityFilter.value) params.priority = priorityFilter.value
    if (assigneeFilter.value) params.assignee_user_id = assigneeFilter.value
    if (dueRange.value?.length === 2) {
      params.due_from = new Date(dueRange.value[0]).toISOString()
      const end = new Date(dueRange.value[1])
      end.setHours(23, 59, 59, 999)
      params.due_to = end.toISOString()
    }
    if (dueTodayFilter.value) params.due_today = true
    if (dueThisWeekFilter.value) params.due_this_week = true
    if (overdueFilter.value) params.overdue = true
    const { data } = await crmApi.listTasks(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  // 自定义日期与快捷筛选互斥
  if (dueRange.value?.length === 2) {
    dueTodayFilter.value = false
    dueThisWeekFilter.value = false
    overdueFilter.value = false
  }
  page.value = 1
  loadTasks()
}

function applySearchNow() {
  const next = searchKeyword.value.trim()
  if (next === appliedSearchKeyword.value && page.value === 1) {
    loadTasks()
    return
  }
  appliedSearchKeyword.value = next
  page.value = 1
  loadTasks()
}

function scheduleSearch() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchDebounceTimer = setTimeout(applySearchNow, SEARCH_DEBOUNCE_MS)
}

function setQuickFilter(type) {
  dueTodayFilter.value = type === 'today'
  dueThisWeekFilter.value = type === 'week'
  overdueFilter.value = type === 'overdue'
  if (type) dueRange.value = []
  page.value = 1
  loadTasks()
}

function clearFilters() {
  searchKeyword.value = ''
  appliedSearchKeyword.value = ''
  statusFilter.value = ''
  priorityFilter.value = ''
  assigneeFilter.value = ''
  dueRange.value = []
  dueTodayFilter.value = false
  dueThisWeekFilter.value = false
  overdueFilter.value = false
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  page.value = 1
  loadTasks()
}

function onPageChange(p) {
  page.value = p
  loadTasks()
}

watch(searchKeyword, () => {
  scheduleSearch()
})

onUnmounted(() => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
})

function openCreate() {
  form.value = {
    title: '',
    description: '',
    planned_start_at: '',
    due_at: '',
    priority: 'normal',
    status: 'open',
    assignee_user_id: auth.user?.id || '',
    link_id: '',
    campaign_id: route.query.campaign_id ? String(route.query.campaign_id) : '',
  }
  linkType.value = 'none'
  linkOptions.value = []
  createVisible.value = true
  loadCampaignOptions()
}

function onLinkTypeChange() {
  form.value.link_id = ''
  linkOptions.value = []
  if (linkType.value === 'lead' || linkType.value === 'customer') searchLinkOptions('')
}

async function loadCampaignOptions() {
  try {
    const { data } = await crmApi.listCampaigns({ page: 1, page_size: 100 })
    campaignOptions.value = data.items || []
  } catch {
    campaignOptions.value = []
  }
}

async function searchLinkOptions(query) {
  if (linkType.value === 'none') return
  linkLoading.value = true
  try {
    const params = { page: 1, page_size: 20 }
    if (query?.trim()) params.q = query.trim()
    const { data } =
      linkType.value === 'lead'
        ? await crmApi.listLeads(params)
        : await crmApi.listCustomers(params)
    linkOptions.value = (data.items || []).map((item) => {
      if (linkType.value === 'lead') {
        const parts = [item.company_name, item.contact_name, item.phone].filter(Boolean)
        return { id: item.id, label: parts.join(' · ') || String(item.id).slice(0, 8) }
      }
      const parts = [item.company_name, item.phone].filter(Boolean)
      return { id: item.id, label: parts.join(' · ') || String(item.id).slice(0, 8) }
    })
  } catch {
    linkOptions.value = []
  } finally {
    linkLoading.value = false
  }
}

async function submitCreate() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  if (linkType.value !== 'none' && !form.value.link_id) {
    ElMessage.warning(linkType.value === 'lead' ? '请选择关联线索' : '请选择关联客户')
    return
  }
  creating.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      priority: form.value.priority || 'normal',
      status: form.value.status || 'open',
    }
    if (form.value.description.trim()) payload.description = form.value.description.trim()
    if (form.value.assignee_user_id) payload.assignee_user_id = form.value.assignee_user_id
    if (form.value.planned_start_at) {
      payload.planned_start_at = new Date(form.value.planned_start_at).toISOString()
    }
    if (form.value.due_at) payload.due_at = new Date(form.value.due_at).toISOString()
    if (linkType.value === 'lead' && form.value.link_id) payload.lead_id = form.value.link_id
    if (linkType.value === 'customer' && form.value.link_id) payload.customer_id = form.value.link_id
    if (form.value.campaign_id) payload.campaign_id = form.value.campaign_id
    await crmApi.createTask(payload)
    ElMessage.success('任务已创建')
    createVisible.value = false
    page.value = 1
    loadTasks()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function updateTaskStatus(row, status) {
  if (!canEdit()) return
  try {
    await crmApi.updateTask(row.id, { status })
    ElMessage.success(TASK_STATUS_CHANGE_MESSAGES[status] || '状态已更新')
    loadTasks()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}

function actionButtonType(act) {
  if (!act) return 'primary'
  if (act.primary) return 'primary'
  if (act.success) return 'success'
  if (act.muted) return 'info'
  return 'warning'
}

function primaryAction(row) {
  return getPrimaryTaskAction(row.status)
}

function secondaryActions(row) {
  return getSecondaryTaskActions(row.status)
}

function isOverdue(row) {
  if (!row.due_at || !isActiveTaskStatus(row.status) || row.status === 'on_hold') return false
  return new Date(row.due_at).getTime() < Date.now()
}

onMounted(async () => {
  if (route.query.due === 'today') dueTodayFilter.value = true
  if (route.query.overdue === '1') overdueFilter.value = true
  await loadMembers(true)
  loadTasks()
})
</script>

<template>
  <div class="page-card tasks-page">
    <div class="tasks-toolbar">
      <div class="tasks-toolbar__head">
        <div>
          <h2 class="tasks-toolbar__title">任务</h2>
          <p class="tasks-toolbar__subtitle">跟进待办、安排回访与资料发送</p>
        </div>
        <el-button v-if="canCreate()" type="primary" :icon="Plus" @click="openCreate">
          新建任务
        </el-button>
      </div>

      <div class="tasks-toolbar__bar">
        <el-input
          v-model="searchKeyword"
          class="tasks-search"
          clearable
          placeholder="搜索标题、备注"
          :prefix-icon="Search"
          @keyup.enter="applySearchNow"
          @clear="applySearchNow"
        />

        <div class="tasks-toolbar__filters">
          <el-select
            v-model="assigneeFilter"
            class="tasks-filter-select"
            placeholder="执行人"
            clearable
            filterable
            @change="onFilterChange"
          >
            <el-option
              v-for="m in teamMembers.filter((x) => x.is_active)"
              :key="m.user_id"
              :label="m.display_name || m.phone"
              :value="m.user_id"
            />
          </el-select>
          <el-select
            v-model="statusFilter"
            class="tasks-filter-select tasks-filter-select--sm"
            placeholder="状态"
            clearable
            @change="onFilterChange"
          >
            <el-option label="待办" value="open" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已挂起" value="on_hold" />
            <el-option label="已完成" value="done" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
          <el-select
            v-model="priorityFilter"
            class="tasks-filter-select tasks-filter-select--sm"
            placeholder="优先级"
            clearable
            @change="onFilterChange"
          >
            <el-option label="高" value="high" />
            <el-option label="普通" value="normal" />
            <el-option label="低" value="low" />
          </el-select>
          <el-date-picker
            v-model="dueRange"
            class="tasks-due-range"
            type="daterange"
            unlink-panels
            range-separator="至"
            start-placeholder="计划完成起"
            end-placeholder="计划完成止"
            value-format="YYYY-MM-DD"
            clearable
            @change="onFilterChange"
          />
        </div>

        <div class="tasks-toolbar__divider" aria-hidden="true" />

        <div class="tasks-toolbar__quick">
          <button
            type="button"
            class="tasks-quick-chip"
            :class="{ 'tasks-quick-chip--active': activeQuickFilter === 'today' }"
            @click="setQuickFilter(activeQuickFilter === 'today' ? '' : 'today')"
          >
            今日到期
          </button>
          <button
            type="button"
            class="tasks-quick-chip"
            :class="{ 'tasks-quick-chip--active': activeQuickFilter === 'week' }"
            @click="setQuickFilter(activeQuickFilter === 'week' ? '' : 'week')"
          >
            本周到期
          </button>
          <button
            type="button"
            class="tasks-quick-chip tasks-quick-chip--danger"
            :class="{ 'tasks-quick-chip--active': activeQuickFilter === 'overdue' }"
            @click="setQuickFilter(activeQuickFilter === 'overdue' ? '' : 'overdue')"
          >
            已逾期
          </button>
          <el-button v-if="hasActiveFilters" link type="primary" @click="clearFilters">
            清空条件
          </el-button>
        </div>

        <span class="tasks-toolbar__count">共 {{ total }} 条</span>
      </div>
    </div>

    <div class="crm-list-table-wrap">
      <el-table v-loading="loading" :data="items" border class="crm-list-table tasks-table">
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="tasks-table__title-cell">
              <span class="tasks-table__title" :class="{ 'tasks-table__title--done': row.status === 'done' }">
                {{ row.title }}
              </span>
              <span v-if="row.description" class="tasks-table__desc">{{ row.description }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="执行人" width="110" show-overflow-tooltip>
          <template #default="{ row }">
            {{ resolveMemberName(row.assignee_user_id) }}
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="84" align="center">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="TASK_PRIORITY_TYPES[row.priority] || 'info'"
              :effect="row.priority === 'high' ? 'dark' : 'plain'"
              round
            >
              {{ TASK_PRIORITY_LABELS[row.priority] || row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="92" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="TASK_STATUS_TYPES[row.status] || 'info'" effect="light" round>
              {{ TASK_STATUS_LABELS[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计划开始" width="138">
          <template #default="{ row }">
            <span class="tasks-table__time">{{ formatTaskDateTime(row.planned_start_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="实际开始" width="138">
          <template #default="{ row }">
            <span class="tasks-table__time tasks-table__time--actual">
              {{ formatTaskDateTime(row.started_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="计划完成" width="138">
          <template #default="{ row }">
            <span
              class="tasks-table__time"
              :class="{ 'tasks-table__time--overdue': isOverdue(row) }"
            >
              {{ formatTaskDateTime(row.due_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="实际完成" width="138">
          <template #default="{ row }">
            <span class="tasks-table__time tasks-table__time--actual">
              {{ formatTaskDateTime(row.completed_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="148" fixed="right" align="center">
          <template #default="{ row }">
            <div v-if="canEdit() && primaryAction(row)" class="tasks-table__actions">
              <el-button
                size="small"
                :type="actionButtonType(primaryAction(row))"
                @click="updateTaskStatus(row, primaryAction(row).next)"
              >
                {{ primaryAction(row).label }}
              </el-button>
              <el-dropdown
                v-if="secondaryActions(row).length"
                trigger="click"
                @command="(status) => updateTaskStatus(row, status)"
              >
                <el-button size="small" text class="tasks-table__more">
                  更多
                  <span class="tasks-table__more-caret">▾</span>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="act in secondaryActions(row)"
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
            <span v-else class="tasks-table__empty-action">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>

    <el-dialog
      v-model="createVisible"
      width="680px"
      destroy-on-close
      class="tasks-create-dialog"
      align-center
    >
      <template #header>
        <div class="tasks-create-dialog__header">
          <div class="tasks-create-dialog__icon" aria-hidden="true">✓</div>
          <div>
            <h3 class="tasks-create-dialog__title">新建任务</h3>
            <p class="tasks-create-dialog__subtitle">安排跟进、回访或资料发送，便于团队协作</p>
          </div>
        </div>
      </template>

      <el-form label-position="top" class="tasks-create-form" @submit.prevent="submitCreate">
        <section class="tasks-create-section">
          <div class="tasks-create-section__head">
            <span class="tasks-create-section__title">基本信息</span>
          </div>
          <el-form-item label="任务标题" required>
            <el-input
              v-model="form.title"
              maxlength="200"
              show-word-limit
              size="large"
              placeholder="例如：发送产品方案、电话回访确认需求"
            />
          </el-form-item>
          <el-form-item label="备注说明">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              maxlength="2000"
              show-word-limit
              placeholder="补充任务背景、注意事项、沟通要点等（选填）"
            />
          </el-form-item>
        </section>

        <section class="tasks-create-section">
          <div class="tasks-create-section__head">
            <span class="tasks-create-section__title">执行安排</span>
          </div>
          <div class="tasks-create-form__row">
            <el-form-item v-if="canAssign()" label="执行人" class="tasks-create-form__col">
              <el-select
                v-model="form.assignee_user_id"
                placeholder="选择执行人"
                filterable
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
            <el-form-item label="优先级" class="tasks-create-form__col">
              <div class="tasks-priority-group" role="radiogroup" aria-label="优先级">
                <button
                  v-for="opt in [
                    { value: 'low', label: '低' },
                    { value: 'normal', label: '普通' },
                    { value: 'high', label: '高' },
                  ]"
                  :key="opt.value"
                  type="button"
                  class="tasks-priority-chip"
                  :class="{
                    'tasks-priority-chip--active': form.priority === opt.value,
                    [`tasks-priority-chip--${opt.value}`]: form.priority === opt.value,
                  }"
                  @click="form.priority = opt.value"
                >
                  {{ opt.label }}
                </button>
              </div>
            </el-form-item>
          </div>
          <div class="tasks-create-form__row">
            <el-form-item label="计划开始" class="tasks-create-form__col">
              <el-date-picker
                v-model="form.planned_start_at"
                type="datetime"
                placeholder="计划何时开始"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="计划完成" class="tasks-create-form__col">
              <el-date-picker
                v-model="form.due_at"
                type="datetime"
                placeholder="计划何时完成"
                style="width: 100%"
                :shortcuts="DUE_SHORTCUTS"
              />
            </el-form-item>
          </div>
        </section>

        <section class="tasks-create-section tasks-create-section--last">
          <div class="tasks-create-section__head">
            <span class="tasks-create-section__title">关联业务</span>
            <span class="tasks-create-section__hint">可选，关联后可在线索/客户/活动详情中查看</span>
          </div>
          <el-form-item label="营销活动">
            <el-select
              v-model="form.campaign_id"
              clearable
              filterable
              placeholder="可选，关联营销活动"
              style="width: 100%"
            >
              <el-option
                v-for="c in campaignOptions"
                :key="c.id"
                :label="c.name"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <div class="tasks-create-form__row">
            <el-form-item label="关联对象" class="tasks-create-form__col tasks-create-form__col--sm">
              <el-radio-group v-model="linkType" class="tasks-link-type" @change="onLinkTypeChange">
                <el-radio-button value="none">不关联</el-radio-button>
                <el-radio-button value="lead">线索</el-radio-button>
                <el-radio-button value="customer">客户</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item
              v-if="linkType !== 'none'"
              :label="linkType === 'lead' ? '选择线索' : '选择客户'"
              class="tasks-create-form__col"
              required
            >
              <el-select
                v-model="form.link_id"
                filterable
                remote
                clearable
                :remote-method="searchLinkOptions"
                :loading="linkLoading"
                :placeholder="linkType === 'lead' ? '搜索线索名称/公司' : '搜索客户名称/公司'"
                style="width: 100%"
              >
                <el-option
                  v-for="opt in linkOptions"
                  :key="opt.id"
                  :label="opt.label"
                  :value="opt.id"
                />
              </el-select>
            </el-form-item>
          </div>
        </section>
      </el-form>

      <template #footer>
        <div class="tasks-create-dialog__footer">
          <el-button @click="createVisible = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="submitCreate">创建任务</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tasks-page {
  padding: 20px 22px;
}

.tasks-toolbar {
  margin-bottom: 16px;
}

.tasks-toolbar__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.tasks-toolbar__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--el-text-color-primary);
}

.tasks-toolbar__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.tasks-toolbar__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  background: linear-gradient(180deg, #fafbfd 0%, #f5f7fb 100%);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.tasks-search {
  width: 220px;
  flex-shrink: 0;
}

.tasks-search :deep(.el-input__wrapper) {
  min-height: 32px;
}

.tasks-toolbar__filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.tasks-filter-select {
  width: 140px;
}

.tasks-filter-select--sm {
  width: 110px;
}

.tasks-filter-select :deep(.el-select__wrapper) {
  min-height: 32px;
}

.tasks-due-range {
  width: 260px;
}

.tasks-due-range :deep(.el-input__wrapper) {
  min-height: 32px;
}

.tasks-toolbar__divider {
  width: 1px;
  height: 28px;
  background: var(--el-border-color);
  flex-shrink: 0;
}

.tasks-toolbar__quick {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.tasks-quick-chip {
  height: 32px;
  padding: 0 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 16px;
  background: #fff;
  color: var(--el-text-color-regular);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.tasks-quick-chip:hover {
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
}

.tasks-quick-chip--active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 500;
}

.tasks-quick-chip--danger.tasks-quick-chip--active {
  border-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.tasks-toolbar__count {
  flex-shrink: 0;
  margin-left: auto;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.tasks-table__title {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.tasks-table__title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.tasks-table__title--done {
  color: var(--el-text-color-secondary);
  text-decoration: line-through;
}

.tasks-table__desc {
  font-size: 12px;
  line-height: 1.4;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tasks-table__time {
  font-size: 13px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

.tasks-table__time--actual {
  color: var(--el-color-primary);
  font-weight: 500;
}

.tasks-table__time--overdue {
  color: var(--el-color-danger);
  font-weight: 500;
}

.tasks-table__actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  gap: 4px;
  white-space: nowrap;
}

.tasks-table__actions :deep(.el-button) {
  margin: 0;
}

.tasks-table__more {
  padding: 5px 6px;
  color: var(--el-text-color-secondary);
}

.tasks-table__more-caret {
  margin-left: 2px;
  font-size: 11px;
}

.tasks-table__empty-action {
  color: var(--el-text-color-placeholder);
}

.tasks-create-form {
  padding: 0 2px 4px;
}

.tasks-create-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.tasks-create-form :deep(.el-form-item__label) {
  margin-bottom: 6px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.tasks-create-section {
  margin-bottom: 18px;
  padding: 16px 16px 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: linear-gradient(180deg, #fcfdff 0%, #f8fafc 100%);
}

.tasks-create-section--last {
  margin-bottom: 0;
}

.tasks-create-section__head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.tasks-create-section__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  letter-spacing: 0.02em;
}

.tasks-create-section__hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.tasks-create-form__row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.tasks-create-form__col {
  flex: 1;
  min-width: 0;
}

.tasks-create-form__col--sm {
  flex: 0 0 auto;
}

.tasks-priority-group {
  display: inline-flex;
  width: 100%;
  padding: 3px;
  gap: 4px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
}

.tasks-priority-chip {
  flex: 1;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}

.tasks-priority-chip:hover {
  color: var(--el-color-primary);
}

.tasks-priority-chip--active {
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
  font-weight: 600;
}

.tasks-priority-chip--low.tasks-priority-chip--active {
  color: #64748b;
}

.tasks-priority-chip--normal.tasks-priority-chip--active {
  color: var(--el-color-primary);
}

.tasks-priority-chip--high.tasks-priority-chip--active {
  color: var(--el-color-danger);
}

.tasks-link-type :deep(.el-radio-button__inner) {
  padding: 8px 14px;
}

.tasks-create-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 640px) {
  .tasks-create-form__row {
    flex-direction: column;
    gap: 0;
  }

  .tasks-create-form__col--sm {
    width: 100%;
  }
}
</style>

<style>
.tasks-create-dialog.el-dialog {
  border-radius: 16px;
  overflow: hidden;
}

.tasks-create-dialog .el-dialog__header {
  margin: 0;
  padding: 20px 24px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.tasks-create-dialog .el-dialog__body {
  padding: 18px 24px 8px;
}

.tasks-create-dialog .el-dialog__footer {
  padding: 12px 24px 20px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: #fafbfc;
}

.tasks-create-dialog__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding-right: 24px;
}

.tasks-create-dialog__icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(145deg, var(--el-color-primary-light-7), var(--el-color-primary-light-9));
  color: var(--el-color-primary);
  font-size: 16px;
  font-weight: 700;
}

.tasks-create-dialog__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--el-text-color-primary);
}

.tasks-create-dialog__subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-text-color-secondary);
}
