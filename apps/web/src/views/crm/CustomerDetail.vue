<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { getFormFields } from '../../utils/entityForm'
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
const { fields, loadSchema } = useEntitySchema('customer')
const { loadMembers, resolveMemberName } = useTeamMembers()

const loading = ref(false)
const activeTab = ref('profile')
const customer = ref(null)
const contacts = ref([])
const activities = ref([])
const tasks = ref([])
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '' })
const taskPanelRef = ref(null)
const contactForm = ref({
  name: '',
  mobile: '',
  phone: '',
  email: '',
  wechat: '',
  title: '',
  department: '',
  is_primary: false,
  is_decision_maker: false,
})
const contactVisible = ref(false)
const contactSaving = ref(false)
const assignVisible = ref(false)
const editVisible = ref(false)

const formFields = computed(() => getFormFields(fields.value, 'customer'))

const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.customer.edit')
const canAssign = () => hasPermission(auth.permissions, 'crm.customer.assign')
const isTenantAdmin = () => auth.user?.active_tenant?.role_code === 'admin'

const heroAvatar = computed(() => (customer.value?.company_name || '客').slice(0, 1))

const heroMeta = computed(() => {
  if (!customer.value) return []
  return [
    { label: '手机', value: customer.value.mobile || '—' },
    { label: '邮箱', value: customer.value.email || '—' },
    { label: '客户状态', value: customer.value.status || '—' },
    { label: '联系人', value: `${contacts.value.length} 人` },
  ]
})

const ownerName = computed(() => resolveMemberName(customer.value?.owner_user_id))

const heroStats = computed(() => [
  { label: '联系人', value: contacts.value.length },
  { label: '跟进记录', value: activities.value.length },
  { label: '待办任务', value: tasks.value.filter((t) => isActiveTaskStatus(t.status)).length },
  { label: '客户级别', value: customer.value?.extra_data?.customer_level || '—' },
])

function customerStatusType(status) {
  const map = { 潜在: 'info', 意向: 'primary', 成交: 'success', 在服: 'success', 暂停: 'warning', 流失: 'danger' }
  return map[status] || 'info'
}

async function loadDetail() {
  loading.value = true
  try {
    await loadSchema()
    const [{ data: cust }, { data: contactList }, { data: timeline }] = await Promise.all([
      crmApi.getCustomer(route.params.id),
      crmApi.listContacts(route.params.id),
      crmApi.listActivities({ customer_id: route.params.id }),
    ])
    customer.value = cust
    contacts.value = Array.isArray(contactList) ? contactList : []
    activities.value = Array.isArray(timeline) ? timeline : []
    await taskPanelRef.value?.reload()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
    router.replace('/crm/customers')
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
      customer_id: route.params.id,
      activity_type: activityForm.value.activity_type,
      content: activityForm.value.content,
    }
    if (activityForm.value.next_follow_up_at) {
      body.next_follow_up_at = new Date(activityForm.value.next_follow_up_at).toISOString()
    }
    await crmApi.createActivity(body)
    ElMessage.success('已添加跟进')
    activityForm.value = { activity_type: 'call', content: '', next_follow_up_at: '' }
    const { data: timeline } = await crmApi.listActivities({ customer_id: route.params.id })
    activities.value = Array.isArray(timeline) ? timeline : []
    const { data: cust } = await crmApi.getCustomer(route.params.id)
    customer.value = cust
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
    const { data: timeline } = await crmApi.listActivities({ customer_id: route.params.id })
    activities.value = Array.isArray(timeline) ? timeline : []
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function onTasksChanged(list) {
  tasks.value = list
}

function openContactDialog() {
  contactForm.value = {
    name: '',
    mobile: '',
    phone: '',
    email: '',
    wechat: '',
    title: '',
    department: '',
    is_primary: contacts.value.length === 0,
    is_decision_maker: false,
  }
  contactVisible.value = true
}

async function submitContact() {
  if (!contactForm.value.name.trim()) {
    ElMessage.warning('请填写联系人姓名')
    return
  }
  contactSaving.value = true
  try {
    const payload = {
      name: contactForm.value.name.trim(),
      mobile: contactForm.value.mobile.trim() || null,
      phone: contactForm.value.phone.trim() || null,
      email: contactForm.value.email.trim() || null,
      wechat: contactForm.value.wechat.trim() || null,
      title: contactForm.value.title.trim() || null,
      department: contactForm.value.department.trim() || null,
      is_primary: !!contactForm.value.is_primary,
      is_decision_maker: !!contactForm.value.is_decision_maker,
    }
    await crmApi.createContact(route.params.id, payload)
    ElMessage.success('已添加联系人')
    contactVisible.value = false
    const { data } = await crmApi.listContacts(route.params.id)
    contacts.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    contactSaving.value = false
  }
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
    list-path="/crm/customers"
    entity-label="客户"
    :title="customer?.company_name || ''"
  >
    <CrmDetailHero
      v-if="customer"
      :title="customer.company_name"
      :subtitle="customer.remark || '暂无备注'"
      :avatar-text="heroAvatar"
      :status="customer.status"
      :status-type="customerStatusType(customer.status)"
      :owner-name="ownerName"
      :meta="heroMeta"
      :stats="heroStats"
    >
      <template #actions>
        <el-button v-if="canEdit()" @click="editVisible = true">编辑资料</el-button>
        <el-button v-if="canAssign()" @click="assignVisible = true">分配负责人</el-button>
      </template>
    </CrmDetailHero>

    <section v-if="customer" class="page-card crm-detail-tabs">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="资料" name="profile">
          <CrmEntityFieldsView :record="customer" :fields="formFields" :owner-name="ownerName" />
        </el-tab-pane>

        <el-tab-pane label="联系人" name="contacts">
          <div class="crm-panel crm-panel--contacts">
            <div class="crm-panel__head">
              <div>
                <div class="crm-panel__title">联系人</div>
                <div class="crm-panel__hint">一位客户可维护多位联系人，便于跟进不同角色</div>
              </div>
              <el-button v-if="canEdit()" type="primary" @click="openContactDialog">新建联系人</el-button>
            </div>
          </div>
          <el-table v-if="contacts.length" :data="contacts" stripe class="crm-table">
            <el-table-column prop="name" label="姓名" min-width="100" />
            <el-table-column prop="title" label="职位" min-width="100" />
            <el-table-column prop="department" label="部门" min-width="100" />
            <el-table-column prop="mobile" label="手机" min-width="120" />
            <el-table-column prop="phone" label="电话" min-width="110" />
            <el-table-column prop="email" label="邮箱" min-width="140" show-overflow-tooltip />
            <el-table-column prop="wechat" label="微信" min-width="100" />
            <el-table-column label="标签" width="140">
              <template #default="{ row }">
                <el-tag v-if="row.is_primary" size="small" type="primary" effect="light" round>首要</el-tag>
                <el-tag
                  v-if="row.is_decision_maker"
                  size="small"
                  type="warning"
                  effect="plain"
                  round
                  style="margin-left: 4px"
                >
                  决策人
                </el-tag>
                <span v-if="!row.is_primary && !row.is_decision_maker">—</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无联系人，点击上方按钮添加" />
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
          <el-empty v-else description="暂无跟进记录" />
        </el-tab-pane>

        <el-tab-pane label="任务" name="tasks">
          <CrmEntityTasks
            ref="taskPanelRef"
            entity-type="customer"
            :entity-id="route.params.id"
            :default-assignee-id="customer.owner_user_id"
            @changed="onTasksChanged"
          />
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="contactVisible" title="添加联系人" width="560px" destroy-on-close>
      <el-form label-width="72px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="姓名" required>
              <el-input v-model="contactForm.name" placeholder="联系人姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职位">
              <el-input v-model="contactForm.title" placeholder="如：财务经理" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机">
              <el-input v-model="contactForm.mobile" placeholder="11 位手机号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="电话">
              <el-input v-model="contactForm.phone" placeholder="固定电话" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="contactForm.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="微信">
              <el-input v-model="contactForm.wechat" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门">
              <el-input v-model="contactForm.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标签">
              <el-checkbox v-model="contactForm.is_primary">首要联系人</el-checkbox>
              <el-checkbox v-model="contactForm.is_decision_maker">决策人</el-checkbox>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="contactVisible = false">取消</el-button>
        <el-button type="primary" :loading="contactSaving" @click="submitContact">保存</el-button>
      </template>
    </el-dialog>

    <CrmEntityFormDialog
      v-model:visible="editVisible"
      entity-type="customer"
      mode="edit"
      :record="customer"
      @saved="loadDetail"
    />

    <CrmAssignOwner
      v-model:visible="assignVisible"
      entity-type="customer"
      :entity-id="route.params.id"
      :owner-user-id="customer?.owner_user_id"
      @done="loadDetail"
    />
  </CrmDetailShell>
</template>

<style scoped>
.crm-detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.crm-panel {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
}

.crm-panel--contacts {
  background: linear-gradient(180deg, #fcfdff 0%, #f7f9fc 100%);
}

.crm-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.crm-panel__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.crm-panel__title {
  margin-bottom: 0;
  font-size: 13px;
  font-weight: 600;
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
}

.crm-timeline__card {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
}

.crm-timeline__content {
  margin: 8px 0 0;
  line-height: 1.6;
}

.crm-table {
  margin-top: 4px;
}
</style>
