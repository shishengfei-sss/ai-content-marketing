<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { formatFieldDisplay, getFormFields, LEAD_STATUS_OPTIONS } from '../../utils/entityForm'
import CrmAssignOwner from '../../components/crm/CrmAssignOwner.vue'
import CrmDetailHero from '../../components/crm/CrmDetailHero.vue'
import CrmDetailShell from '../../components/crm/CrmDetailShell.vue'
import CrmEntityFieldsView from '../../components/crm/CrmEntityFieldsView.vue'
import CrmEntityFormDialog from '../../components/crm/CrmEntityFormDialog.vue'
import CrmEntityTasks from '../../components/crm/CrmEntityTasks.vue'
import { isActiveTaskStatus } from '../../utils/taskMeta'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('lead')
const { loadMembers, resolveMemberName } = useTeamMembers()

const loading = ref(false)
const activeTab = ref('profile')
const lead = ref(null)
const campaignName = ref('')
const activities = ref([])
const tasks = ref([])
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '', status: '' })
const taskPanelRef = ref(null)
const assignVisible = ref(false)
const editVisible = ref(false)

const formFields = computed(() => getFormFields(fields.value, 'lead'))

const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canConvert = () => hasPermission(auth.permissions, 'crm.lead.convert')
const canAssign = () => hasPermission(auth.permissions, 'crm.lead.assign')
const canEdit = () => hasPermission(auth.permissions, 'crm.lead.edit')
const isTenantAdmin = () => auth.user?.active_tenant?.role_code === 'admin'

const heroAvatar = computed(() => (lead.value?.company_name || '线').slice(0, 1))

const heroMeta = computed(() => {
  if (!lead.value) return []
  return [
    { label: '联系人', value: lead.value.contact_name || '—' },
    { label: '手机', value: lead.value.mobile || '—' },
    { label: '来源', value: lead.value.source || '—' },
    { label: '线索状态', value: lead.value.status || '—' },
  ]
})

const ownerName = computed(() => resolveMemberName(lead.value?.owner_user_id))

const heroStats = computed(() => [
  { label: '跟进记录', value: activities.value.length },
  { label: '待办任务', value: tasks.value.filter((t) => isActiveTaskStatus(t.status)).length },
  {
    label: '意向等级',
    value: formatFieldDisplay({ field_key: 'intention_level', field_type: 'select' }, lead.value),
  },
  { label: '市场活动', value: campaignName.value || '—' },
])

function leadStatusType(status) {
  const map = {
    待跟进: 'info',
    跟进中: 'primary',
    有意向: 'success',
    无意向: 'warning',
    已转化: 'success',
    无效: 'danger',
  }
  return map[status] || 'info'
}

async function loadCampaignName() {
  if (!lead.value?.campaign_id) {
    campaignName.value = ''
    return
  }
  try {
    const { data } = await crmApi.getCampaign(lead.value.campaign_id)
    campaignName.value = data.name || ''
  } catch {
    campaignName.value = ''
  }
}

async function loadDetail() {
  loading.value = true
  try {
    await loadSchema()
    const [{ data: leadData }, { data: timeline }] = await Promise.all([
      crmApi.getLead(route.params.id),
      crmApi.listActivities({ lead_id: route.params.id }),
    ])
    lead.value = leadData
    activities.value = Array.isArray(timeline) ? timeline : []
    await loadCampaignName()
    await taskPanelRef.value?.reload()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
    router.replace('/crm/leads')
  } finally {
    loading.value = false
  }
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    ElMessage.warning('请填写跟进内容')
    return
  }
  try {
    const body = {
      lead_id: route.params.id,
      activity_type: activityForm.value.activity_type,
      content: activityForm.value.content,
    }
    if (activityForm.value.next_follow_up_at) {
      body.next_follow_up_at = new Date(activityForm.value.next_follow_up_at).toISOString()
    }
    if (canEdit() && activityForm.value.status) {
      body.status = activityForm.value.status
    }
    await crmApi.createActivity(body)
    ElMessage.success('已添加跟进')
    activityForm.value = {
      activity_type: 'call',
      content: '',
      next_follow_up_at: '',
      status: lead.value?.status || '待跟进',
    }
    const { data: timeline } = await crmApi.listActivities({ lead_id: route.params.id })
    activities.value = Array.isArray(timeline) ? timeline : []
    const { data: leadData } = await crmApi.getLead(route.params.id)
    lead.value = leadData
    if (!activityForm.value.status) {
      activityForm.value.status = leadData.status || '待跟进'
    }
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  }
}

function canDeleteActivity(item) {
  return item.created_by_user_id === auth.user?.id || isTenantAdmin()
}

async function deleteActivity(item) {
  try {
    await ElMessageBox.confirm('确定删除这条跟进记录？', '删除')
    await crmApi.deleteActivity(item.id)
    ElMessage.success('已删除')
    const { data: timeline } = await crmApi.listActivities({ lead_id: route.params.id })
    activities.value = Array.isArray(timeline) ? timeline : []
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function handleConvert() {
  try {
    await ElMessageBox.confirm(
      '线索需转化为客户后，才会出现在客户列表。确定现在转化？',
      '转化客户',
      { confirmButtonText: '转化', cancelButtonText: '取消' },
    )
    const { data } = await crmApi.convertLead(route.params.id)
    ElMessage.success('已转化为客户')
    await loadDetail()
    router.push(`/crm/customers/${data.customer_id}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '转化失败')
  }
}

function onTasksChanged(list) {
  tasks.value = list
}

const activityLabels = {
  call: '电话',
  visit: '拜访',
  wechat: '微信',
  email: '邮件',
  other: '其他',
}

onMounted(async () => {
  await loadMembers(true)
  loadDetail()
})
</script>

<template>
  <CrmDetailShell
    :loading="loading"
    list-path="/crm/leads"
    entity-label="线索"
    :title="lead?.company_name || ''"
  >
    <CrmDetailHero
      v-if="lead"
      :title="lead.company_name"
      :subtitle="lead.remark || '暂无备注'"
      :avatar-text="heroAvatar"
      :status="lead.status"
      :status-type="leadStatusType(lead.status)"
      :owner-name="ownerName"
      :meta="heroMeta"
      :stats="heroStats"
    >
      <template #actions>
        <el-button
          v-if="lead.converted_customer_id"
          type="primary"
          @click="router.push(`/crm/customers/${lead.converted_customer_id}`)"
        >
          查看客户
        </el-button>
        <el-button v-if="canEdit()" @click="editVisible = true">编辑资料</el-button>
        <el-button v-if="canAssign()" @click="assignVisible = true">分配负责人</el-button>
        <el-button v-if="canConvert() && lead.status !== '已转化'" type="primary" @click="handleConvert">
          转化客户
        </el-button>
      </template>
    </CrmDetailHero>

    <section v-if="lead" class="page-card crm-detail-tabs">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="资料" name="profile">
          <CrmEntityFieldsView
            :record="lead"
            :fields="formFields"
            :campaign-name="campaignName"
            :owner-name="ownerName"
          />
        </el-tab-pane>

        <el-tab-pane label="跟进" name="activities">
          <div v-if="canWriteActivity()" class="crm-panel">
            <div class="crm-panel__title">写跟进</div>
            <div class="activity-form">
              <el-select v-model="activityForm.activity_type" style="width: 120px">
                <el-option label="电话" value="call" />
                <el-option label="拜访" value="visit" />
                <el-option label="微信" value="wechat" />
                <el-option label="邮件" value="email" />
                <el-option label="其他" value="other" />
              </el-select>
              <el-input v-model="activityForm.content" placeholder="记录本次沟通要点…" />
              <el-date-picker
                v-model="activityForm.next_follow_up_at"
                type="datetime"
                placeholder="下次跟进"
                style="width: 190px"
              />
              <el-select
                v-if="canEdit()"
                v-model="activityForm.status"
                placeholder="线索状态"
                style="width: 120px"
              >
                <el-option
                  v-for="item in LEAD_STATUS_OPTIONS"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
              <el-button type="primary" @click="submitActivity">提交</el-button>
            </div>
          </div>

          <el-timeline v-if="activities.length" class="crm-timeline">
            <el-timeline-item
              v-for="item in activities"
              :key="item.id"
              :timestamp="new Date(item.created_at).toLocaleString('zh-CN')"
              placement="top"
            >
              <div class="crm-timeline__card">
                <el-tag size="small" type="info">{{ activityLabels[item.activity_type] || item.activity_type }}</el-tag>
                <p class="crm-timeline__content">{{ item.content }}</p>
                <el-button
                  v-if="canDeleteActivity(item)"
                  link
                  type="danger"
                  size="small"
                  @click="deleteActivity(item)"
                >
                  删除
                </el-button>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无跟进记录，写一条跟进开始吧" />
        </el-tab-pane>

        <el-tab-pane label="任务" name="tasks">
          <CrmEntityTasks
            ref="taskPanelRef"
            entity-type="lead"
            :entity-id="route.params.id"
            :default-assignee-id="lead.owner_user_id"
            @changed="onTasksChanged"
          />
        </el-tab-pane>
      </el-tabs>
    </section>

    <CrmEntityFormDialog
      v-model:visible="editVisible"
      entity-type="lead"
      mode="edit"
      :record="lead"
      @saved="loadDetail"
    />

    <CrmAssignOwner
      v-model:visible="assignVisible"
      entity-type="lead"
      :entity-id="route.params.id"
      :owner-user-id="lead?.owner_user_id"
      @done="loadDetail"
    />
  </CrmDetailShell>
</template>

<style scoped>
.crm-detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.crm-detail-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
}

.crm-panel {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
}

.crm-panel__title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.activity-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.activity-form .el-input {
  flex: 1;
  min-width: 200px;
}

.crm-timeline {
  margin-top: 4px;
  padding-left: 4px;
}

.crm-timeline__card {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
}

.crm-timeline__content {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

.crm-table {
  margin-top: 4px;
}
</style>
