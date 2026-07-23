<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { contentApi, crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import {
  CAMPAIGN_CURRENCY_OPTIONS,
  CAMPAIGN_STATUS_OPTIONS,
  CAMPAIGN_TYPE_OPTIONS,
  CHANNEL_CONTENT_TYPE_OPTIONS,
  CHANNEL_EXECUTION_STATUS_OPTIONS,
  buildChannelLabelMap,
  campaignDateToIso,
  campaignStatusLabel,
  campaignStatusTagType,
  campaignTypeLabel,
  channelContentTypeLabel,
  channelExecutionStatusLabel,
  channelsToOptions,
  formatCampaignChannels,
  formatCampaignPeriod,
  showCampaignLocation,
  toCampaignDateValue,
} from '../../utils/campaignMeta'
import {
  TASK_PRIORITY_LABELS,
  TASK_PRIORITY_TYPES,
  TASK_STATUS_LABELS,
  TASK_STATUS_TYPES,
  formatTaskDateTime,
} from '../../utils/taskMeta'
import CrmDetailShell from '../../components/crm/CrmDetailShell.vue'
import CrmEntityFormDialog from '../../components/crm/CrmEntityFormDialog.vue'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { formatDateTime } from '../../utils/datetime'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers, members } = useTeamMembers()
const assignableMembers = ref([])
const assigneeOptions = computed(() =>
  assignableMembers.value.filter((m) => m.is_active !== false),
)

async function loadAssignableAssignees(includeUserId = '') {
  try {
    const { data } = await crmApi.listAssignableOwners({
      include_user_id: includeUserId || undefined,
    })
    assignableMembers.value = Array.isArray(data) ? data : []
  } catch {
    assignableMembers.value = []
  }
}

const loading = ref(false)
const activeTab = ref('overview')
const campaign = ref(null)
const territories = ref([])
const segments = ref([])
const channelRows = ref([])
const channelOptions = computed(() => channelsToOptions(channelRows.value))
const channelLabelMap = computed(() => buildChannelLabelMap(channelRows.value))

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
const executions = ref([])
const executionsLoading = ref(false)
const performance = ref(null)
const execDialog = ref(false)
const execSaving = ref(false)
const editingExecId = ref('')
const execForm = ref({ channel: '', content_type: 'post', cost: 0, impressions: 0, clicks: 0, leads_generated: 0, status: 'planned' })

const editVisible = ref(false)
const editSaving = ref(false)
const editForm = ref({
  name: '',
  status: 'draft',
  campaign_type: null,
  start_at: null,
  end_at: null,
  goal: '',
  channels: [],
  description: '',
  budget: null,
  currency: 'CNY',
  expected_leads: null,
  location: '',
  owner_user_id: null,
  territory_id: null,
  target_segment_id: null,
})

const locationVisible = computed(() => showCampaignLocation(editForm.value.campaign_type))

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
  planned_start_at: '',
  due_at: '',
  priority: 'normal',
  assignee_user_id: '',
  link_id: '',
})
const taskLinkType = ref('none')
const taskLinkOptions = ref([])
const taskLinkLoading = ref(false)

const canEdit = () => hasPermission(auth.permissions, 'crm.campaign.edit')
const canManage = () => hasPermission(auth.permissions, 'crm.campaign.manage')
const canCreateLead = () => hasPermission(auth.permissions, 'crm.lead.create')
const canEditLead = () => hasPermission(auth.permissions, 'crm.lead.edit')
const canCreateTask = () => hasPermission(auth.permissions, 'crm.task.create')
const canAssignTask = () => hasPermission(auth.permissions, 'crm.task.assign')
const canCreateContent = () => hasPermission(auth.permissions, 'content.create')
const canViewContent = () =>
  hasPermission(auth.permissions, 'content.view_own') ||
  hasPermission(auth.permissions, 'content.view_all')

const platformLabels = { wechat: '公众号', xhs: '小红书', douyin: '抖音' }
const contentStatusLabels = {
  draft: '草稿',
  scheduled: '已排期',
  publishing: '发布中',
  published: '已发布',
  failed: '发布失败',
  exported: '已导出',
}

const linkContentVisible = ref(false)
const linkContentLoading = ref(false)
const linkContentSaving = ref(false)
const linkContentOptions = ref([])
const linkContentId = ref('')

const summaryCards = computed(() => {
  const actualLeads = campaign.value?.lead_count ?? leadsTotal.value ?? 0
  const expected = campaign.value?.expected_leads
  return [
    {
      label: '线索（预期/实际）',
      value: expected != null ? `${expected} / ${actualLeads}` : actualLeads,
    },
    { label: '关联任务', value: campaign.value?.task_count ?? tasksTotal.value ?? 0 },
    { label: '关联内容', value: campaign.value?.content_count ?? contents.value.length ?? 0 },
    {
      label: '预算/花费',
      value: campaign.value?.budget != null
        ? `¥${Number(campaign.value.budget).toLocaleString()} / ¥${Number(campaign.value.spent || 0).toLocaleString()}`
        : `花费 ¥${Number(campaign.value?.spent || 0).toLocaleString()}`,
    },
  ]
})

const leadInitialValues = computed(() => ({
  campaign_id: route.params.id,
}))

function territoryName(id) {
  if (!id) return '—'
  return territories.value.find((t) => t.id === id)?.name || '—'
}

function segmentName(id) {
  if (!id) return '—'
  return segments.value.find((s) => s.id === id)?.name || '—'
}

async function loadLookups() {
  try {
    const [terrRes, segRes, chRes] = await Promise.all([
      crmApi.listTerritories(),
      crmApi.listSegments(),
      crmApi.listCampaignChannels({ active_only: true }),
    ])
    territories.value = Array.isArray(terrRes.data) ? terrRes.data : (terrRes.data?.items || [])
    segments.value = Array.isArray(segRes.data) ? segRes.data : (segRes.data?.items || [])
    channelRows.value = Array.isArray(chRes.data) ? chRes.data : []
  } catch {
    territories.value = []
    segments.value = []
    channelRows.value = []
  }
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
    contents.value = (data.items || []).map((item) => ({
      ...item,
      title: item.topic || item.title || '—',
    }))
  } catch {
    contents.value = []
  } finally {
    contentsLoading.value = false
  }
}

function goCreateContent() {
  router.push({ path: '/create', query: { campaign_id: route.params.id } })
}

function openLinkContent() {
  linkContentId.value = ''
  linkContentOptions.value = []
  linkContentVisible.value = true
}

async function searchLinkContents(query) {
  linkContentLoading.value = true
  try {
    const { data } = await contentApi.list({
      q: query?.trim() || undefined,
      page: 1,
      page_size: 30,
    })
    const linked = new Set(contents.value.map((c) => c.id))
    linkContentOptions.value = (data.items || [])
      .filter((item) => !linked.has(item.id))
      .map((item) => ({
        id: item.id,
        label: `${item.topic || '未命名'} · ${platformLabels[item.platform] || item.platform || '—'}`,
      }))
  } catch {
    linkContentOptions.value = []
  } finally {
    linkContentLoading.value = false
  }
}

async function submitLinkContent() {
  if (!linkContentId.value) {
    ElMessage.warning('请选择要关联的内容')
    return
  }
  linkContentSaving.value = true
  try {
    await crmApi.linkCampaignContent(route.params.id, linkContentId.value)
    ElMessage.success('已关联内容')
    linkContentVisible.value = false
    await Promise.all([loadContents(), loadCampaign()])
  } catch (e) {
    ElMessage.error(e.message || '关联失败')
  } finally {
    linkContentSaving.value = false
  }
}

async function unlinkContent(row) {
  try {
    await crmApi.unlinkCampaignContent(route.params.id, row.id)
    ElMessage.success('已取消关联')
    await Promise.all([loadContents(), loadCampaign()])
  } catch (e) {
    ElMessage.error(e.message || '取消关联失败')
  }
}

async function loadExecutions() {
  executionsLoading.value = true
  try {
    const { data } = await crmApi.listCampaignExecutions(route.params.id)
    executions.value = Array.isArray(data) ? data : []
  } catch {
    executions.value = []
  } finally {
    executionsLoading.value = false
  }
}

async function loadPerformance() {
  try {
    const { data } = await crmApi.getCampaignPerformance(route.params.id)
    performance.value = data
  } catch {
    performance.value = null
  }
}

async function loadDetail() {
  loading.value = true
  try {
    await loadCampaign()
    await Promise.all([loadLeads(), loadTasks(), loadContents(), loadExecutions(), loadPerformance()])
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
    router.replace('/crm/campaigns')
  } finally {
    loading.value = false
  }
}

function emptyExecForm() {
  return { channel: '', content_type: 'post', cost: 0, impressions: 0, clicks: 0, leads_generated: 0, status: 'planned' }
}

function openExecDialog() {
  editingExecId.value = ''
  execForm.value = emptyExecForm()
  execDialog.value = true
}

function openEditExec(row) {
  editingExecId.value = row.id
  execForm.value = {
    channel: row.channel || '',
    content_type: row.content_type || 'post',
    cost: Number(row.cost || 0),
    impressions: Number(row.impressions || 0),
    clicks: Number(row.clicks || 0),
    leads_generated: Number(row.leads_generated || 0),
    status: row.status || 'planned',
  }
  execDialog.value = true
}

async function submitExec() {
  if (!execForm.value.channel?.trim()) { ElMessage.warning('请选择渠道'); return }
  execSaving.value = true
  try {
    const payload = {
      channel: execForm.value.channel.trim(),
      content_type: execForm.value.content_type,
      cost: execForm.value.cost,
      impressions: execForm.value.impressions,
      clicks: execForm.value.clicks,
      leads_generated: execForm.value.leads_generated,
      status: execForm.value.status,
    }
    if (editingExecId.value) {
      await crmApi.updateCampaignExecution(editingExecId.value, payload)
      ElMessage.success('渠道执行已更新')
    } else {
      await crmApi.createCampaignExecution(route.params.id, payload)
      ElMessage.success('已添加渠道执行')
    }
    execDialog.value = false
    await Promise.all([loadExecutions(), loadPerformance(), loadCampaign()])
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    execSaving.value = false
  }
}

async function removeExec(row) {
  try {
    await crmApi.deleteCampaignExecution(row.id)
    ElMessage.success('已删除')
    await Promise.all([loadExecutions(), loadPerformance(), loadCampaign()])
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function formatMoney(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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
    campaign_type: campaign.value.campaign_type || null,
    start_at: toCampaignDateValue(campaign.value.start_at),
    end_at: toCampaignDateValue(campaign.value.end_at),
    goal: campaign.value.goal || '',
    channels: [...(campaign.value.channels || [])],
    description: campaign.value.description || '',
    budget: campaign.value.budget != null ? Number(campaign.value.budget) : null,
    currency: campaign.value.currency || 'CNY',
    expected_leads: campaign.value.expected_leads != null ? Number(campaign.value.expected_leads) : null,
    location: campaign.value.location || '',
    owner_user_id: campaign.value.owner_user_id || null,
    territory_id: campaign.value.territory_id || null,
    target_segment_id: campaign.value.target_segment_id || null,
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
      campaign_type: editForm.value.campaign_type || null,
      start_at: campaignDateToIso(editForm.value.start_at),
      end_at: campaignDateToIso(editForm.value.end_at),
      goal: editForm.value.goal?.trim() || null,
      channels: editForm.value.channels || [],
      description: editForm.value.description?.trim() || null,
      budget: editForm.value.budget,
      currency: editForm.value.currency || 'CNY',
      expected_leads: editForm.value.expected_leads,
      location: locationVisible.value ? (editForm.value.location?.trim() || null) : null,
      owner_user_id: editForm.value.owner_user_id || null,
      territory_id: editForm.value.territory_id || null,
      target_segment_id: editForm.value.target_segment_id || null,
    }
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
  await Promise.all([loadLeads(), loadCampaign(), loadPerformance()])
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
    await Promise.all([loadLeads(), loadCampaign(), loadPerformance()])
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
    await Promise.all([loadLeads(), loadCampaign(), loadPerformance()])
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function openCreateTask() {
  taskForm.value = {
    title: '',
    description: '',
    planned_start_at: '',
    due_at: '',
    priority: 'normal',
    assignee_user_id: auth.user?.id || '',
    link_id: '',
  }
  taskLinkType.value = 'none'
  taskLinkOptions.value = []
  taskCreateVisible.value = true
  await loadAssignableAssignees(auth.user?.id)
}

function onTaskLinkTypeChange() {
  taskForm.value.link_id = ''
  taskLinkOptions.value = []
  if (taskLinkType.value === 'lead' || taskLinkType.value === 'customer') {
    searchTaskLinkOptions('')
  }
}

async function searchTaskLinkOptions(query) {
  if (taskLinkType.value === 'none') return
  taskLinkLoading.value = true
  try {
    const params = { page: 1, page_size: 20 }
    if (query?.trim()) params.q = query.trim()
    const { data } =
      taskLinkType.value === 'lead'
        ? await crmApi.listLeads(params)
        : await crmApi.listCustomers(params)
    taskLinkOptions.value = (data.items || []).map((item) => {
      if (taskLinkType.value === 'lead') {
        const parts = [item.company_name, item.contact_name, item.phone || item.mobile].filter(Boolean)
        return { id: item.id, label: parts.join(' · ') || String(item.id).slice(0, 8) }
      }
      const parts = [item.company_name, item.phone || item.mobile].filter(Boolean)
      return { id: item.id, label: parts.join(' · ') || String(item.id).slice(0, 8) }
    })
  } catch {
    taskLinkOptions.value = []
  } finally {
    taskLinkLoading.value = false
  }
}

async function submitCreateTask() {
  if (!taskForm.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  if (taskLinkType.value !== 'none' && !taskForm.value.link_id) {
    ElMessage.warning(taskLinkType.value === 'lead' ? '请选择关联线索' : '请选择关联客户')
    return
  }
  taskCreating.value = true
  try {
    const payload = {
      title: taskForm.value.title.trim(),
      priority: taskForm.value.priority || 'normal',
      status: 'open',
      campaign_id: route.params.id,
      assignee_user_id: taskForm.value.assignee_user_id || auth.user?.id,
    }
    if (taskForm.value.description.trim()) {
      payload.description = taskForm.value.description.trim()
    }
    if (taskForm.value.planned_start_at) {
      payload.planned_start_at = new Date(taskForm.value.planned_start_at).toISOString()
    }
    if (taskForm.value.due_at) {
      payload.due_at = new Date(taskForm.value.due_at).toISOString()
    }
    if (taskLinkType.value === 'lead' && taskForm.value.link_id) {
      payload.lead_id = taskForm.value.link_id
    }
    if (taskLinkType.value === 'customer' && taskForm.value.link_id) {
      payload.customer_id = taskForm.value.link_id
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

onMounted(async () => {
  await Promise.all([loadMembers(), loadLookups()])
  await loadDetail()
})

watch(activeTab, (tab) => {
  if (tab === 'roi') loadPerformance()
})
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
            <span>负责人：{{ resolveMemberName(campaign.owner_user_id) }}</span>
          </div>
        </div>
        <div class="detail-actions">
          <el-button v-if="canManage() && campaign.status === 'draft'" type="success" @click="changeStatus('active')">
            启动活动
          </el-button>
          <el-button v-if="canManage() && campaign.status === 'active'" type="warning" plain @click="changeStatus('paused')">
            暂停活动
          </el-button>
          <el-button v-if="canManage() && campaign.status === 'paused'" type="success" @click="changeStatus('active')">
            恢复活动
          </el-button>
          <el-button
            v-if="canManage() && (campaign.status === 'active' || campaign.status === 'paused')"
            @click="changeStatus('ended')"
          >
            结束活动
          </el-button>
          <el-button v-if="canEdit() && campaign.status !== 'ended'" @click="openEdit">编辑</el-button>
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
            <el-descriptions-item label="活动类型">{{ campaignTypeLabel(campaign?.campaign_type) }}</el-descriptions-item>
            <el-descriptions-item label="活动周期">{{ formatCampaignPeriod(campaign) }}</el-descriptions-item>
            <el-descriptions-item label="投放渠道">
              {{ formatCampaignChannels(campaign?.channels, channelLabelMap) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="showCampaignLocation(campaign?.campaign_type)" label="活动地点">
              {{ campaign?.location || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="负责人">{{ resolveMemberName(campaign?.owner_user_id) }}</el-descriptions-item>
            <el-descriptions-item label="归属地区">{{ territoryName(campaign?.territory_id) }}</el-descriptions-item>
            <el-descriptions-item label="目标细分">{{ segmentName(campaign?.target_segment_id) }}</el-descriptions-item>
            <el-descriptions-item label="预期线索">{{ campaign?.expected_leads ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="预算">
              {{ campaign?.budget != null ? '¥' + formatMoney(campaign.budget) : '—' }}
              <span v-if="campaign" class="muted"> / 已花 ¥{{ formatMoney(campaign.spent) }}</span>
              <span v-if="campaign?.currency" class="muted"> · {{ campaign.currency }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">
              {{ formatDateTime(campaign?.updated_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="活动目标" :span="2">{{ campaign?.goal || '—' }}</el-descriptions-item>
            <el-descriptions-item label="策划说明" :span="2">{{ campaign?.description || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="内容" name="contents">
          <div class="tab-toolbar">
            <div class="tab-toolbar__hint">将创作内容归属到本活动，便于统计关联内容数</div>
            <div class="tab-toolbar__actions">
              <el-button v-if="canEdit() && canViewContent()" @click="openLinkContent">关联已有内容</el-button>
              <el-button v-if="canCreateContent()" type="primary" :icon="Plus" @click="goCreateContent">
                去创作
              </el-button>
            </div>
          </div>
          <el-table v-loading="contentsLoading" :data="contents" stripe @row-click="goContent">
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column label="平台" width="100">
              <template #default="{ row }">{{ platformLabels[row.platform] || row.platform || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">{{ contentStatusLabels[row.status] || row.status || '—' }}</template>
            </el-table-column>
            <el-table-column label="更新时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.updated_at) }}
              </template>
            </el-table-column>
            <el-table-column v-if="canEdit()" label="操作" width="100" fixed="right" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click.stop="unlinkContent(row)">取消关联</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-if="!contentsLoading && !contents.length"
            description="暂无关联内容，可关联已有内容或去创作"
          />
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
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="TASK_STATUS_TYPES[row.status] || 'info'" effect="light" round>
                  {{ TASK_STATUS_LABELS[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="80" align="center">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="TASK_PRIORITY_TYPES[row.priority] || 'info'"
                  :effect="row.priority === 'high' ? 'dark' : 'plain'"
                >
                  {{ TASK_PRIORITY_LABELS[row.priority] || row.priority }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="执行人" width="110" show-overflow-tooltip>
              <template #default="{ row }">{{ resolveMemberName(row.assignee_user_id) }}</template>
            </el-table-column>
            <el-table-column label="计划开始" width="150">
              <template #default="{ row }">{{ formatTaskDateTime(row.planned_start_at) }}</template>
            </el-table-column>
            <el-table-column label="计划完成" width="150">
              <template #default="{ row }">{{ formatTaskDateTime(row.due_at) }}</template>
            </el-table-column>
            <el-table-column label="更新时间" width="150">
              <template #default="{ row }">{{ formatTaskDateTime(row.updated_at) }}</template>
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

        <el-tab-pane :label="`渠道执行（${executions.length}）`" name="executions">
          <div v-if="canEdit()" style="margin-bottom: 12px">
            <el-button type="primary" @click="openExecDialog">添加渠道执行</el-button>
          </div>
          <el-table v-loading="executionsLoading" :data="executions" border size="small" empty-text="暂无渠道执行">
            <el-table-column prop="channel" label="渠道" width="120" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">{{ channelContentTypeLabel(row.content_type) }}</template>
            </el-table-column>
            <el-table-column label="成本" width="110" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.cost) }}</template>
            </el-table-column>
            <el-table-column prop="impressions" label="曝光" width="90" align="right" />
            <el-table-column prop="clicks" label="点击" width="90" align="right" />
            <el-table-column prop="leads_generated" label="线索" width="90" align="right" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">{{ channelExecutionStatusLabel(row.status) }}</template>
            </el-table-column>
            <el-table-column v-if="canEdit()" label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditExec(row)">编辑</el-button>
                <el-button link type="danger" @click="removeExec(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="ROI 分析" name="roi">
          <div v-if="performance" class="roi-grid">
            <div class="roi-card"><span>总投入</span><strong>¥{{ formatMoney(performance.total_cost) }}</strong></div>
            <div class="roi-card"><span>关联线索</span><strong>{{ performance.leads_count }}</strong></div>
            <div class="roi-card"><span>转化客户</span><strong>{{ performance.customers_count }}</strong></div>
            <div class="roi-card"><span>ROI</span><strong>{{ performance.roi }}%</strong></div>
            <div class="roi-card"><span>CPL</span><strong>¥{{ formatMoney(performance.cost_per_lead) }}</strong></div>
            <div class="roi-card"><span>转化率</span><strong>{{ performance.conversion_rate }}%</strong></div>
          </div>
          <el-table v-if="performance" :data="performance.by_channel || []" border size="small" empty-text="暂无渠道数据" style="margin-top: 12px">
            <el-table-column prop="channel" label="渠道" />
            <el-table-column label="投入" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.cost) }}</template>
            </el-table-column>
            <el-table-column prop="impressions" label="曝光" align="right" />
            <el-table-column prop="clicks" label="点击" align="right" />
            <el-table-column prop="leads_generated" label="填报线索" align="right" />
            <el-table-column label="CPL" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.cost_per_lead) }}</template>
            </el-table-column>
          </el-table>
          <p v-if="performance" class="field-hint" style="margin-top: 8px">
            「关联线索」来自活动下 CRM 线索；渠道表「填报线索」来自渠道执行手工录入，两者口径不同。
          </p>
          <el-empty v-else description="暂无效果数据" :image-size="64" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="editVisible" title="编辑活动" width="640px" destroy-on-close>
      <el-form label-width="96px">
        <el-form-item label="活动名称" required>
          <el-input v-model="editForm.name" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="活动类型">
          <el-select v-model="editForm.campaign_type" clearable placeholder="请选择" style="width: 100%">
            <el-option
              v-for="item in CAMPAIGN_TYPE_OPTIONS"
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
              v-for="item in channelOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <div class="field-hint">
            可在
            <router-link to="/settings/campaign-channels">设置 → 活动投放渠道</router-link>
            维护选项
          </div>
        </el-form-item>
        <el-form-item v-if="locationVisible" label="活动地点">
          <el-input v-model="editForm.location" placeholder="城市 / 场馆" maxlength="200" />
        </el-form-item>
        <el-form-item label="预算">
          <div class="form-inline-row">
            <el-input-number v-model="editForm.budget" :min="0" :precision="2" :controls="false" style="flex: 1" />
            <el-select v-model="editForm.currency" style="width: 100px">
              <el-option
                v-for="item in CAMPAIGN_CURRENCY_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="预期线索">
          <el-input-number v-model="editForm.expected_leads" :min="0" :precision="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="editForm.owner_user_id" filterable clearable style="width: 100%">
            <el-option
              v-for="m in members"
              :key="m.user_id"
              :label="m.display_name || m.phone || m.user_id"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="归属地区">
          <el-select v-model="editForm.territory_id" filterable clearable placeholder="可选" style="width: 100%">
            <el-option v-for="t in territories" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标细分">
          <el-select v-model="editForm.target_segment_id" filterable clearable placeholder="可选" style="width: 100%">
            <el-option v-for="s in segments" :key="s.id" :label="s.name" :value="s.id" />
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

    <el-dialog
      v-model="execDialog"
      :title="editingExecId ? '编辑渠道执行' : '添加渠道执行'"
      width="480px"
      destroy-on-close
    >      <el-form label-width="96px">
        <el-form-item label="渠道" required>
          <el-select
            v-model="execForm.channel"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入渠道"
            style="width: 100%"
          >
            <el-option
              v-for="item in channelOptions"
              :key="item.value"
              :label="item.label"
              :value="item.label"
            />
          </el-select>
          <div class="field-hint">
            选项来自
            <router-link to="/settings/campaign-channels">设置 → 活动投放渠道</router-link>
          </div>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="execForm.content_type" style="width: 100%">
            <el-option
              v-for="item in CHANNEL_CONTENT_TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="成本"><el-input-number v-model="execForm.cost" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="曝光"><el-input-number v-model="execForm.impressions" :min="0" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="点击"><el-input-number v-model="execForm.clicks" :min="0" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="线索数"><el-input-number v-model="execForm.leads_generated" :min="0" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="execForm.status" style="width: 100%">
            <el-option
              v-for="item in CHANNEL_EXECUTION_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="execDialog = false">取消</el-button>
        <el-button type="primary" :loading="execSaving" @click="submitExec">保存</el-button>
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

    <el-dialog
      v-model="linkContentVisible"
      title="关联已有内容"
      width="520px"
      destroy-on-close
      @opened="searchLinkContents('')"
    >
      <el-form label-position="top">
        <el-form-item label="选择内容" required>
          <el-select
            v-model="linkContentId"
            filterable
            remote
            clearable
            :remote-method="searchLinkContents"
            :loading="linkContentLoading"
            placeholder="搜索主题/标题"
            style="width: 100%"
          >
            <el-option
              v-for="opt in linkContentOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkContentVisible = false">取消</el-button>
        <el-button type="primary" :loading="linkContentSaving" @click="submitLinkContent">关联</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="taskCreateVisible" title="新建活动任务" width="600px" destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitCreateTask">
        <el-form-item label="任务标题" required>
          <el-input
            v-model="taskForm.title"
            maxlength="200"
            show-word-limit
            placeholder="例如：活动回访、资料发送"
          />
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            :rows="2"
            maxlength="2000"
            show-word-limit
            placeholder="补充背景、注意事项等（选填）"
          />
        </el-form-item>
        <div class="task-create-row">
          <el-form-item v-if="canAssignTask()" label="执行人" class="task-create-row__col">
            <el-select
              v-model="taskForm.assignee_user_id"
              filterable
              placeholder="选择执行人（本组织范围）"
              style="width: 100%"
            >
              <el-option
                v-for="m in assigneeOptions"
                :key="m.user_id"
                :label="m.display_name || m.phone || m.user_id"
                :value="m.user_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级" class="task-create-row__col">
            <el-select v-model="taskForm.priority" style="width: 100%">
              <el-option label="低" value="low" />
              <el-option label="普通" value="normal" />
              <el-option label="高" value="high" />
            </el-select>
          </el-form-item>
        </div>
        <div class="task-create-row">
          <el-form-item label="计划开始" class="task-create-row__col">
            <el-date-picker
              v-model="taskForm.planned_start_at"
              type="datetime"
              placeholder="计划何时开始"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="计划完成" class="task-create-row__col">
            <el-date-picker
              v-model="taskForm.due_at"
              type="datetime"
              placeholder="计划何时完成"
              style="width: 100%"
            />
          </el-form-item>
        </div>
        <el-form-item label="关联对象">
          <el-radio-group v-model="taskLinkType" @change="onTaskLinkTypeChange">
            <el-radio-button value="none">不关联</el-radio-button>
            <el-radio-button value="lead">线索</el-radio-button>
            <el-radio-button value="customer">客户</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="taskLinkType !== 'none'" :label="taskLinkType === 'lead' ? '选择线索' : '选择客户'" required>
          <el-select
            v-model="taskForm.link_id"
            filterable
            remote
            clearable
            :remote-method="searchTaskLinkOptions"
            :loading="taskLinkLoading"
            :placeholder="taskLinkType === 'lead' ? '搜索线索' : '搜索客户'"
            style="width: 100%"
          >
            <el-option
              v-for="opt in taskLinkOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
        <div class="field-hint">本任务将自动关联当前营销活动</div>
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

.muted { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 6px; }
.form-inline-row { display: flex; gap: 8px; width: 100%; align-items: center; }
.field-hint { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
.field-hint a { color: var(--el-color-primary); }
.roi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.roi-card {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.roi-card span {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.roi-card strong { font-size: 16px; }

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .roi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
