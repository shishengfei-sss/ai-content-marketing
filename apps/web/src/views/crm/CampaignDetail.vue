<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { contentApi, crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import {
  CAMPAIGN_CHANNEL_OPTIONS,
  CAMPAIGN_STATUS_OPTIONS,
  campaignDateToIso,
  campaignStatusLabel,
  campaignStatusTagType,
  formatCampaignChannels,
  formatCampaignPeriod,
  toCampaignDateValue,
} from '../../utils/campaignMeta'
import {
  TASK_STATUS_LABELS,
  TASK_STATUS_TYPES,
  formatTaskDateTime,
} from '../../utils/taskMeta'
import CrmDetailShell from '../../components/crm/CrmDetailShell.vue'
import CrmEntityFormDialog from '../../components/crm/CrmEntityFormDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const activeTab = ref('overview')
const campaign = ref(null)

const leads = ref([])
const leadsTotal = ref(0)
const leadsPage = ref(1)
const leadsPageSize = ref(20)
const leadsLoading = ref(false)

const tasks = ref([])
const tasksTotal = ref(0)
const tasksPage = ref(1)
const tasksPageSize = ref(20)
const tasksLoading = ref(false)

const contents = ref([])
const contentsLoading = ref(false)

const editVisible = ref(false)
const editSaving = ref(false)
const editForm = ref({
  name: '',
  status: 'draft',
  start_at: null,
  end_at: null,
  goal: '',
  channels: [],
  description: '',
})

const leadCreateVisible = ref(false)
const linkLeadVisible = ref(false)
const linkLeadLoading = ref(false)
const linkLeadSaving = ref(false)
const linkLeadOptions = ref([])
const linkLeadId = ref('')

const taskCreateVisible = ref(false)
const taskCreating = ref(false)
const taskForm = ref({
  title: '',
  description: '',
  due_at: '',
  priority: 'normal',
})

const canEdit = () => hasPermission(auth.permissions, 'crm.campaign.edit')
const canManage = () => hasPermission(auth.permissions, 'crm.campaign.manage')
const canCreateLead = () => hasPermission(auth.permissions, 'crm.lead.create')
const canEditLead = () => hasPermission(auth.permissions, 'crm.lead.edit')
const canCreateTask = () => hasPermission(auth.permissions, 'crm.task.create')

const platformLabels = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }

const summaryCards = computed(() => [
  { label: '关联线索', value: campaign.value?.lead_count ?? leadsTotal.value ?? 0 },
  { label: '关联任务', value: campaign.value?.task_count ?? tasksTotal.value ?? 0 },
  { label: '关联内容', value: campaign.value?.content_count ?? contents.value.length ?? 0 },
  { label: '活动状态', value: campaignStatusLabel(campaign.value?.status) },
])

const leadInitialValues = computed(() => ({
  campaign_id: route.params.id,
}))

function ownerLabel(ownerUserId) {
  if (!ownerUserId) return '—'
  return ownerUserId === auth.user?.id ? '我' : '同事'
}

async function loadCampaign() {
  const { data } = await crmApi.getCampaign(route.params.id)
  campaign.value = data
}

async function loadLeads() {
  leadsLoading.value = true
  try {
    const { data } = await crmApi.listLeads({
      campaign_id: route.params.id,
      page: leadsPage.value,
      page_size: leadsPageSize.value,
    })
    leads.value = data.items || []
    leadsTotal.value = data.total || 0
  } finally {
    leadsLoading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const { data } = await crmApi.listTasks({
      campaign_id: route.params.id,
      page: tasksPage.value,
      page_size: tasksPageSize.value,
    })
    tasks.value = data.items || []
    tasksTotal.value = data.total || 0
  } finally {
    tasksLoading.value = false
  }
}

async function loadContents() {
  contentsLoading.value = true
  try {
    const { data } = await contentApi.list({
      campaign_id: route.params.id,
      page: 1,
      page_size: 50,
    })
    contents.value = data.items || []
  } catch {
    contents.value = []
  } finally {
    contentsLoading.value = false
  }
}

async function loadDetail() {
  loading.value = true
  try {
    await loadCampaign()
    await Promise.all([loadLeads(), loadTasks(), loadContents()])
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
    router.replace('/crm/campaigns')
  } finally {
    loading.value = false
  }
}

function onLeadsPageChange(p) {
  leadsPage.value = p
  loadLeads()
}

function onTasksPageChange(p) {
  tasksPage.value = p
  loadTasks()
}

function goLead(row) {
  router.push(`/crm/leads/${row.id}`)
}

function goContent() {
  router.push('/contents')
}

function goTasks() {
  router.push('/crm/tasks')
}

function openEdit() {
  if (!campaign.value) return
  editForm.value = {
    name: campaign.value.name || '',
    status: campaign.value.status || 'draft',
    start_at: toCampaignDateValue(campaign.value.start_at),
    end_at: toCampaignDateValue(campaign.value.end_at),
    goal: campaign.value.goal || '',
    channels: [...(campaign.value.channels || [])],
    description: campaign.value.description || '',
  }
  editVisible.value = true
}

async function submitEdit() {
  if (!editForm.value.name.trim()) {
    ElMessage.warning('请填写活动名称')
    return
  }
  editSaving.value = true
  try {
    const payload = {
      name: editForm.value.name.trim(),
      start_at: campaignDateToIso(editForm.value.start_at),
      end_at: campaignDateToIso(editForm.value.end_at),
      goal: editForm.value.goal?.trim() || null,
      channels: editForm.value.channels || [],
      description: editForm.value.description?.trim() || null,
    }
    if (canManage()) payload.status = editForm.value.status
    await crmApi.updateCampaign(route.params.id, payload)
    ElMessage.success('活动已更新')
    editVisible.value = false
    await loadDetail()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    editSaving.value = false
  }
}

async function changeStatus(status) {
  if (!canManage()) return
  try {
    await crmApi.updateCampaign(route.params.id, { status })
    ElMessage.success('状态已更新')
    await loadCampaign()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}

async function onLeadCreated() {
  await Promise.all([loadLeads(), loadCampaign()])
  activeTab.value = 'leads'
}

function openLinkLead() {
  linkLeadId.value = ''
  linkLeadOptions.value = []
  linkLeadVisible.value = true
  searchLinkLeads('')
}

async function searchLinkLeads(query) {
  linkLeadLoading.value = true
  try {
    const params = { page: 1, page_size: 20 }
    if (query?.trim()) params.q = query.trim()
    const { data } = await crmApi.listLeads(params)
    const currentId = String(route.params.id)
    linkLeadOptions.value = (data.items || [])
      .filter((item) => String(item.campaign_id || '') !== currentId)
      .map((item) => {
        const parts = [item.company_name, item.contact_name, item.mobile || item.phone].filter(Boolean)
        return { id: item.id, label: parts.join(' · ') || String(item.id).slice(0, 8) }
      })
  } catch {
    linkLeadOptions.value = []
  } finally {
    linkLeadLoading.value = false
  }
}

async function submitLinkLead() {
  if (!linkLeadId.value) {
    ElMessage.warning('请选择要关联的线索')
    return
  }
  linkLeadSaving.value = true
  try {
    await crmApi.updateLead(linkLeadId.value, { campaign_id: route.params.id })
    ElMessage.success('已关联线索')
    linkLeadVisible.value = false
    await Promise.all([loadLeads(), loadCampaign()])
    activeTab.value = 'leads'
  } catch (e) {
    ElMessage.error(e.message || '关联失败')
  } finally {
    linkLeadSaving.value = false
  }
}

async function unlinkLead(row) {
  try {
    await crmApi.updateLead(row.id, { campaign_id: null })
    ElMessage.success('已取消关联')
    await Promise.all([loadLeads(), loadCampaign()])
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

function openCreateTask() {
  taskForm.value = {
    title: '',
    description: '',
    due_at: '',
    priority: 'normal',
  }
  taskCreateVisible.value = true
}

async function submitCreateTask() {
  if (!taskForm.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  taskCreating.value = true
  try {
    const payload = {
      title: taskForm.value.title.trim(),
      priority: taskForm.value.priority || 'normal',
      status: 'open',
      campaign_id: route.params.id,
      assignee_user_id: auth.user?.id,
    }
    if (taskForm.value.description.trim()) {
      payload.description = taskForm.value.description.trim()
    }
    if (taskForm.value.due_at) {
      payload.due_at = new Date(taskForm.value.due_at).toISOString()
    }
    await crmApi.createTask(payload)
    ElMessage.success('任务已创建并关联到本活动')
    taskCreateVisible.value = false
    await Promise.all([loadTasks(), loadCampaign()])
    activeTab.value = 'tasks'
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    taskCreating.value = false
  }
}

onMounted(loadDetail)
</script>

<template>
  <CrmDetailShell
    :loading="loading"
    list-path="/crm/campaigns"
    entity-label="营销活动"
    :title="campaign?.name || ''"
  >
    <div v-if="campaign" class="page-card detail-card">
      <div class="detail-head">
        <div>
          <div class="page-title">{{ campaign.name }}</div>
          <div class="detail-meta">
            <el-tag size="small" :type="campaignStatusTagType(campaign.status)">
              {{ campaignStatusLabel(campaign.status) }}
            </el-tag>
            <span>{{ formatCampaignPeriod(campaign) }}</span>
            <span>负责人：{{ ownerLabel(campaign.owner_user_id) }}</span>
          </div>
        </div>
        <div class="detail-actions">
          <el-button v-if="canManage() && campaign.status === 'draft'" type="success" @click="changeStatus('active')">
            启动活动
          </el-button>
          <el-button v-if="canManage() && campaign.status === 'active'" @click="changeStatus('ended')">
            结束活动
          </el-button>
          <el-button v-if="canEdit()" @click="openEdit">编辑</el-button>
        </div>
      </div>

      <div class="summary-grid">
        <div v-for="card in summaryCards" :key="card.label" class="summary-card">
          <div class="summary-card__value">{{ card.value }}</div>
          <div class="summary-card__label">{{ card.label }}</div>
        </div>
      </div>
    </div>

    <div class="page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="概况" name="overview">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="活动名称">{{ campaign?.name }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag size="small" :type="campaignStatusTagType(campaign?.status)">
                {{ campaignStatusLabel(campaign?.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="活动周期">{{ formatCampaignPeriod(campaign) }}</el-descriptions-item>
            <el-descriptions-item label="投放渠道">
              {{ formatCampaignChannels(campaign?.channels) }}
            </el-descriptions-item>
            <el-descriptions-item label="负责人">{{ ownerLabel(campaign?.owner_user_id) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">
              {{ campaign?.updated_at ? new Date(campaign.updated_at).toLocaleString('zh-CN') : '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="活动目标" :span="2">{{ campaign?.goal || '—' }}</el-descriptions-item>
            <el-descriptions-item label="策划说明" :span="2">{{ campaign?.description || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="内容" name="contents">
          <el-table v-loading="contentsLoading" :data="contents" stripe @row-click="goContent">
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column label="平台" width="100">
              <template #default="{ row }">{{ platformLabels[row.platform] || row.platform || '—' }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column label="更新时间" width="160">
              <template #default="{ row }">
                {{ row.updated_at ? new Date(row.updated_at).toLocaleString('zh-CN') : '—' }}
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!contentsLoading && !contents.length" description="暂无关联内容，可在创作页选择本活动" />
        </el-tab-pane>

        <el-tab-pane label="线索" name="leads">
          <div class="tab-toolbar">
            <div class="tab-toolbar__hint">将获客线索归属到本活动，便于追踪转化效果</div>
            <div class="tab-toolbar__actions">
              <el-button v-if="canEditLead()" @click="openLinkLead">关联已有线索</el-button>
              <el-button v-if="canCreateLead()" type="primary" :icon="Plus" @click="leadCreateVisible = true">
                新建线索
              </el-button>
            </div>
          </div>
          <el-table v-loading="leadsLoading" :data="leads" stripe>
            <el-table-column prop="company_name" label="公司名称" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <el-button link type="primary" @click="goLead(row)">{{ row.company_name }}</el-button>
              </template>
            </el-table-column>
            <el-table-column prop="contact_name" label="联系人" width="100" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="mobile" label="手机" width="130" />
            <el-table-column v-if="canEditLead()" label="操作" width="100" fixed="right" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click.stop="unlinkLead(row)">取消关联</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!leadsLoading && !leads.length" description="暂无关联线索，可新建或关联已有线索" />
          <div v-if="leadsTotal > leadsPageSize" class="pager">
            <el-pagination
              v-model:current-page="leadsPage"
              :page-size="leadsPageSize"
              :total="leadsTotal"
              layout="total, prev, pager, next"
              @current-change="onLeadsPageChange"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="任务" name="tasks">
          <div class="tab-toolbar">
            <div class="tab-toolbar__hint">为活动安排跟进、回访等任务，统一在活动下追踪</div>
            <div class="tab-toolbar__actions">
              <el-button @click="goTasks">全部任务</el-button>
              <el-button v-if="canCreateTask()" type="primary" :icon="Plus" @click="openCreateTask">
                新建任务
              </el-button>
            </div>
          </div>
          <el-table v-loading="tasksLoading" :data="tasks" stripe>
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="TASK_STATUS_TYPES[row.status] || 'info'" effect="light" round>
                  {{ TASK_STATUS_LABELS[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="计划完成" width="160">
              <template #default="{ row }">
                {{ formatTaskDateTime(row.due_at) }}
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="160">
              <template #default="{ row }">
                {{ formatTaskDateTime(row.updated_at) }}
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!tasksLoading && !tasks.length" description="暂无关联任务，点击上方新建" />
          <div v-if="tasksTotal > tasksPageSize" class="pager">
            <el-pagination
              v-model:current-page="tasksPage"
              :page-size="tasksPageSize"
              :total="tasksTotal"
              layout="total, prev, pager, next"
              @current-change="onTasksPageChange"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="editVisible" title="编辑活动" width="560px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="活动名称" required>
          <el-input v-model="editForm.name" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item v-if="canManage()" label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option
              v-for="item in CAMPAIGN_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="editForm.start_at"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="editForm.end_at"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="投放渠道">
          <el-select v-model="editForm.channels" multiple collapse-tags style="width: 100%">
            <el-option
              v-for="item in CAMPAIGN_CHANNEL_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="活动目标">
          <el-input v-model="editForm.goal" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="策划说明">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <CrmEntityFormDialog
      v-model:visible="leadCreateVisible"
      entity-type="lead"
      mode="create"
      :initial-values="leadInitialValues"
      @saved="onLeadCreated"
    />

    <el-dialog v-model="linkLeadVisible" title="关联已有线索" width="480px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="选择线索" required>
          <el-select
            v-model="linkLeadId"
            filterable
            remote
            clearable
            :remote-method="searchLinkLeads"
            :loading="linkLeadLoading"
            placeholder="搜索公司、联系人、手机"
            style="width: 100%"
          >
            <el-option
              v-for="opt in linkLeadOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkLeadVisible = false">取消</el-button>
        <el-button type="primary" :loading="linkLeadSaving" @click="submitLinkLead">关联</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="taskCreateVisible" title="新建活动任务" width="520px" destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitCreateTask">
        <el-form-item label="任务标题" required>
          <el-input v-model="taskForm.title" maxlength="200" show-word-limit placeholder="例如：活动回访、资料发送" />
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="taskForm.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <div class="task-create-row">
          <el-form-item label="优先级" class="task-create-row__col">
            <el-select v-model="taskForm.priority" style="width: 100%">
              <el-option label="低" value="low" />
              <el-option label="普通" value="normal" />
              <el-option label="高" value="high" />
            </el-select>
          </el-form-item>
          <el-form-item label="计划完成" class="task-create-row__col">
            <el-date-picker v-model="taskForm.due_at" type="datetime" placeholder="计划完成时间" style="width: 100%" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="taskCreateVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskCreating" @click="submitCreateTask">创建并关联</el-button>
      </template>
    </el-dialog>
  </CrmDetailShell>
</template>

<style scoped>
.detail-card .page-title {
  font-size: 20px;
  font-weight: 600;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.summary-card {
  padding: 16px;
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
  text-align: center;
}

.summary-card__value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.summary-card__label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.tab-toolbar__hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.tab-toolbar__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.task-create-row {
  display: flex;
  gap: 14px;
}

.task-create-row__col {
  flex: 1;
  min-width: 0;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .task-create-row {
    flex-direction: column;
    gap: 0;
  }
}
</style>
