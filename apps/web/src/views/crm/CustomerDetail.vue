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
import { validateLeadMobile } from '../../utils/entityForm'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('customer')
const { loadMembers, resolveMemberName } = useTeamMembers()

const listPath = computed(() =>
  route.query.from === 'customer-pools' ? '/crm/customer-pools' : '/crm/customers',
)
const listLabel = computed(() => (route.query.from === 'customer-pools' ? '客户公海' : '客户'))

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
  contact_role: null,
  reports_to_contact_id: null,
})
const contactVisible = ref(false)
const contactSaving = ref(false)
const decisionChain = ref(null)
const bizLookup = ref(null)
const bizLoading = ref(false)
const assignVisible = ref(false)
const editVisible = ref(false)
const reclaimVisible = ref(false)
const reclaimSaving = ref(false)
const reclaimPools = ref([])
const reclaimPoolId = ref('')
const attachments = ref([])
const uploading = ref(false)
const relatedDeals = ref([])
const relatedQuotes = ref([])
const relatedContracts = ref([])
const relatedOrders = ref([])
const relatedPayments = ref([])

const CONTACT_ROLE_OPTIONS = ['决策者', '影响者', '使用者', '评估者']

const formFields = computed(() => getFormFields(fields.value, 'customer'))

const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.customer.edit')
const canAssign = () => hasPermission(auth.permissions, 'crm.customer.assign')
const isCustomerOwner = () => {
  const a = customer.value?.owner_user_id
  const b = auth.user?.id
  return (
    !!a &&
    !!b &&
    String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
  )
}
/** 编辑 / 退回公海等：权限 + 负责人 */
const canMutateCustomer = () => canEdit() && isCustomerOwner()
/** 写跟进：需跟进权限且为负责人（无负责人/公海不可写） */
const canWriteCustomerActivity = () => canWriteActivity() && isCustomerOwner()
const isTenantAdmin = () => auth.user?.active_tenant?.role_code === 'admin'

const heroAvatar = computed(() => (customer.value?.company_name || '客').slice(0, 1))

const heroMeta = computed(() => {
  if (!customer.value) return []
  return [
    { label: '手机', value: customer.value.mobile || '—' },
    { label: '邮箱', value: customer.value.email || '—' },
    { label: '来源', value: customer.value.source || '—' },
    { label: '客户状态', value: customer.value.status || '—' },
    { label: '联系人', value: `${contacts.value.length} 人` },
  ]
})

const ownerName = computed(() => resolveMemberName(customer.value?.owner_user_id))

const heroStats = computed(() => [
  { label: '联系人', value: contacts.value.length },
  { label: '跟进记录', value: activities.value.length },
  {
    label: '累计成交',
    value: customer.value?.total_revenue != null ? `¥${Number(customer.value.total_revenue).toLocaleString()}` : '—',
  },
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
    try {
      const { data: chain } = await crmApi.getDecisionChain(route.params.id)
      decisionChain.value = chain
    } catch {
      decisionChain.value = null
    }
    await loadAttachments()
    await loadRelated()
    await taskPanelRef.value?.reload()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
    router.replace('/crm/customers')
  } finally {
    loading.value = false
  }
}

async function loadRelated() {
  const id = route.params.id
  try {
    const [dealsRes, quotesRes, contractsRes, ordersRes, paymentsRes] = await Promise.all([
      crmApi.listDeals({ customer_id: id, page_size: 50 }),
      crmApi.listQuotes({ customer_id: id, page_size: 50 }),
      crmApi.listContracts({ customer_id: id, page_size: 50 }),
      crmApi.listOrders({ customer_id: id, page_size: 50 }),
      crmApi.listPayments({ customer_id: id, page_size: 50 }),
    ])
    relatedDeals.value = dealsRes.data?.items || []
    relatedQuotes.value = quotesRes.data?.items || []
    relatedContracts.value = contractsRes.data?.items || []
    relatedOrders.value = ordersRes.data?.items || []
    relatedPayments.value = paymentsRes.data?.items || []
  } catch {
    relatedDeals.value = []
    relatedQuotes.value = []
    relatedContracts.value = []
    relatedOrders.value = []
    relatedPayments.value = []
  }
}

function formatFileSize(n) {
  if (!n && n !== 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function loadAttachments() {
  try {
    const { data } = await crmApi.listAttachments({ entity_type: 'customer', entity_id: route.params.id })
    attachments.value = Array.isArray(data) ? data : []
  } catch {
    attachments.value = []
  }
}

async function onUploadFile(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('文件超过 50MB')
    return
  }
  uploading.value = true
  try {
    await crmApi.uploadAttachment('customer', route.params.id, file)
    ElMessage.success('已上传')
    await loadAttachments()
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
    ev.target.value = ''
  }
}

async function downloadAttachment(att) {
  try {
    const { data } = await crmApi.downloadAttachment(att.id)
    const url = window.URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = att.file_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

async function removeAttachment(att) {
  try {
    await ElMessageBox.confirm(`确定删除附件「${att.file_name}」？`, '删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await crmApi.deleteAttachment(att.id)
    await loadAttachments()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function submitActivity() {
  if (!canWriteCustomerActivity()) {
    ElMessage.warning('仅负责人可写跟进')
    return
  }
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

function contactNameById(id) {
  if (!id) return '—'
  const c = contacts.value.find((x) => String(x.id) === String(id))
  return c?.name || '—'
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
    contact_role: null,
    reports_to_contact_id: null,
  }
  contactVisible.value = true
}

async function submitContact() {
  if (!contactForm.value.name.trim()) {
    ElMessage.warning('请填写联系人姓名')
    return
  }
  const mobileErr = validateLeadMobile(contactForm.value.mobile, { required: true })
  if (mobileErr) {
    ElMessage.warning(mobileErr)
    return
  }
  contactSaving.value = true
  try {
    const payload = {
      name: contactForm.value.name.trim(),
      mobile: contactForm.value.mobile.trim(),
      phone: contactForm.value.phone.trim() || null,
      email: contactForm.value.email.trim() || null,
      wechat: contactForm.value.wechat.trim() || null,
      title: contactForm.value.title.trim() || null,
      department: contactForm.value.department.trim() || null,
      is_primary: !!contactForm.value.is_primary,
      contact_role: contactForm.value.contact_role || null,
      reports_to_contact_id: contactForm.value.reports_to_contact_id || null,
    }
    await crmApi.createContact(route.params.id, payload)
    ElMessage.success('已添加联系人')
    contactVisible.value = false
    const [{ data }, { data: chain }] = await Promise.all([
      crmApi.listContacts(route.params.id),
      crmApi.getDecisionChain(route.params.id),
    ])
    contacts.value = Array.isArray(data) ? data : []
    decisionChain.value = chain
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    contactSaving.value = false
  }
}

async function lookupBusiness() {
  if (!customer.value?.company_name) return
  bizLoading.value = true
  try {
    const { data } = await crmApi.businessLookup(customer.value.company_name)
    bizLookup.value = data
    if (data?.available) ElMessage.success('已查询工商信息（stub）')
    else ElMessage.warning(data?.detail || '工商查询不可用')
  } catch (e) {
    ElMessage.error(e.message || '查询失败')
  } finally {
    bizLoading.value = false
  }
}

async function openReclaim() {
  try {
    const { data: pools } = await crmApi.listCustomerPools()
    reclaimPools.value = Array.isArray(pools) ? pools : []
    if (!reclaimPools.value.length) {
      try {
        await ElMessageBox.confirm('暂无客户公海，是否前往设置创建？', '退回公海', {
          type: 'warning',
          confirmButtonText: '去设置',
          cancelButtonText: '取消',
        })
        router.push('/settings/customer-pools')
      } catch {
        /* cancel */
      }
      return
    }
    reclaimPoolId.value = reclaimPools.value[0].id
    reclaimVisible.value = true
  } catch (e) {
    ElMessage.error(e.message || '加载公海失败')
  }
}

async function submitReclaim() {
  if (!reclaimPoolId.value) {
    ElMessage.warning('请选择公海')
    return
  }
  reclaimSaving.value = true
  try {
    await crmApi.reclaimCustomerToPool(route.params.id, { pool_id: reclaimPoolId.value })
    ElMessage.success('已退回公海')
    reclaimVisible.value = false
    router.push('/crm/customers')
  } catch (e) {
    ElMessage.error(e.message || '退回失败')
  } finally {
    reclaimSaving.value = false
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
    :list-path="listPath"
    :entity-label="listLabel"
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
        <el-button v-if="canMutateCustomer()" :loading="bizLoading" @click="lookupBusiness">工商查询</el-button>
        <el-button v-if="canMutateCustomer()" @click="editVisible = true">编辑资料</el-button>
        <el-button v-if="canAssign()" @click="assignVisible = true">分配负责人</el-button>
        <el-button v-if="canMutateCustomer()" type="warning" plain @click="openReclaim">退回公海</el-button>
      </template>
    </CrmDetailHero>

    <section v-if="bizLookup?.available" class="page-card biz-card">
      <div class="crm-panel__title">工商信息（{{ bizLookup.provider }}）</div>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="信用代码">{{ bizLookup.credit_code }}</el-descriptions-item>
        <el-descriptions-item label="法人">{{ bizLookup.legal_representative }}</el-descriptions-item>
        <el-descriptions-item label="注册资本">{{ bizLookup.registered_capital }}</el-descriptions-item>
        <el-descriptions-item label="成立日期">{{ bizLookup.established_date }}</el-descriptions-item>
        <el-descriptions-item label="经营范围" :span="2">{{ bizLookup.business_scope }}</el-descriptions-item>
      </el-descriptions>
    </section>

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
              <el-button v-if="canMutateCustomer()" type="primary" @click="openContactDialog">新建联系人</el-button>
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
            <el-table-column label="标签" width="160">
              <template #default="{ row }">
                <el-tag v-if="row.is_primary" size="small" type="primary" effect="light" round>首要</el-tag>
                <el-tag
                  v-if="row.contact_role"
                  size="small"
                  type="warning"
                  effect="plain"
                  round
                  style="margin-left: 4px"
                >
                  {{ row.contact_role }}
                </el-tag>
                <span v-if="!row.is_primary && !row.contact_role">—</span>
              </template>
            </el-table-column>
            <el-table-column label="汇报给" min-width="120">
              <template #default="{ row }">{{ contactNameById(row.reports_to_contact_id) }}</template>
            </el-table-column>
          </el-table>
          <div v-if="decisionChain?.edges?.length" class="chain-box">
            <div class="crm-panel__title">决策链</div>
            <div v-for="(edge, idx) in decisionChain.edges" :key="idx" class="chain-line">
              {{ contactNameById(edge.from) }} → {{ contactNameById(edge.to) }}
            </div>
          </div>
          <el-empty v-else-if="!contacts.length" description="暂无联系人，点击上方按钮添加" />
        </el-tab-pane>

        <el-tab-pane label="跟进" name="activities">
          <div v-if="canWriteCustomerActivity()" class="crm-panel">
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

        <el-tab-pane label="商机" name="deals">
          <el-table v-if="relatedDeals.length" :data="relatedDeals" stripe class="crm-table" @row-click="(row) => router.push(`/crm/deals/${row.id}`)">
            <el-table-column prop="title" label="标题" min-width="180" />
            <el-table-column prop="amount" label="金额" width="120" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="expected_close_date" label="预计成交" width="140" />
          </el-table>
          <el-empty v-else description="暂无关联商机" />
        </el-tab-pane>

        <el-tab-pane label="报价单" name="quotes">
          <el-table v-if="relatedQuotes.length" :data="relatedQuotes" stripe class="crm-table" @row-click="(row) => router.push(`/crm/quotes/${row.id}`)">
            <el-table-column prop="quote_number" label="编号" width="140" />
            <el-table-column prop="title" label="标题" min-width="160" />
            <el-table-column prop="total_amount" label="金额" width="120" />
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
          <el-empty v-else description="暂无报价单" />
        </el-tab-pane>

        <el-tab-pane label="合同" name="contracts">
          <el-table v-if="relatedContracts.length" :data="relatedContracts" stripe class="crm-table" @row-click="(row) => router.push(`/crm/contracts/${row.id}`)">
            <el-table-column prop="contract_number" label="编号" width="140" />
            <el-table-column prop="title" label="标题" min-width="160" />
            <el-table-column prop="amount" label="金额" width="120" />
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
          <el-empty v-else description="暂无合同" />
        </el-tab-pane>

        <el-tab-pane label="订单" name="orders">
          <el-table v-if="relatedOrders.length" :data="relatedOrders" stripe class="crm-table" @row-click="(row) => router.push(`/crm/orders/${row.id}`)">
            <el-table-column prop="order_number" label="编号" width="140" />
            <el-table-column prop="title" label="标题" min-width="160" />
            <el-table-column prop="total_amount" label="金额" width="120" />
            <el-table-column prop="status" label="状态" width="100" />
          </el-table>
          <el-empty v-else description="暂无订单" />
        </el-tab-pane>

        <el-tab-pane label="回款" name="payments">
          <el-table v-if="relatedPayments.length" :data="relatedPayments" stripe class="crm-table">
            <el-table-column prop="payment_number" label="编号" width="140" />
            <el-table-column prop="amount" label="金额" width="120" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="paid_at" label="回款日期" width="160" />
          </el-table>
          <el-empty v-else description="暂无回款" />
        </el-tab-pane>

        <el-tab-pane label="文档" name="attachments">
          <div class="crm-panel">
            <div class="crm-panel__head">
              <div class="crm-panel__title">文档附件</div>
              <label v-if="canMutateCustomer()" class="crm-upload-btn">
                <input type="file" :disabled="uploading" @change="onUploadFile" />
                <el-button type="primary" size="small" :loading="uploading">上传附件</el-button>
              </label>
            </div>
          </div>
          <el-table v-if="attachments.length" :data="attachments" stripe class="crm-table">
            <el-table-column prop="file_name" label="文件名" min-width="220" show-overflow-tooltip />
            <el-table-column label="大小" width="110">
              <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
            </el-table-column>
            <el-table-column label="上传人" width="120">
              <template #default="{ row }">{{ resolveMemberName(row.uploaded_by_user_id) }}</template>
            </el-table-column>
            <el-table-column label="上传时间" width="160">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="downloadAttachment(row)">下载</el-button>
                <el-button v-if="canMutateCustomer()" link type="danger" size="small" @click="removeAttachment(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无附件" />
        </el-tab-pane>

        <el-tab-pane label="任务" name="tasks">
          <CrmEntityTasks
            ref="taskPanelRef"
            entity-type="customer"
            :entity-id="route.params.id"
            :default-assignee-id="customer.owner_user_id"
            :allow-create="isCustomerOwner()"
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
            <el-form-item label="手机" required>
              <el-input v-model="contactForm.mobile" placeholder="11 位手机号" maxlength="11" />
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
            <el-form-item label="组织角色">
              <el-select v-model="contactForm.contact_role" clearable placeholder="选择角色" style="width: 100%">
                <el-option v-for="role in CONTACT_ROLE_OPTIONS" :key="role" :label="role" :value="role" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="汇报给">
              <el-select
                v-model="contactForm.reports_to_contact_id"
                clearable
                placeholder="选择上级联系人"
                style="width: 100%"
              >
                <el-option v-for="c in contacts" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标签">
              <el-checkbox v-model="contactForm.is_primary">首要联系人</el-checkbox>
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

    <el-dialog v-model="reclaimVisible" title="退回公海" width="420px" destroy-on-close>
      <el-form label-width="72px">
        <el-form-item label="公海" required>
          <el-select v-model="reclaimPoolId" placeholder="选择公海" style="width: 100%">
            <el-option v-for="p in reclaimPools" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reclaimVisible = false">取消</el-button>
        <el-button type="warning" :loading="reclaimSaving" @click="submitReclaim">确认退回</el-button>
      </template>
    </el-dialog>
  </CrmDetailShell>
</template>

<style scoped>
.crm-detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.biz-card {
  margin-top: 12px;
  margin-bottom: 12px;
  padding: 14px 16px;
}

.chain-box {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.chain-line {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
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

.crm-upload-btn {
  position: relative;
  display: inline-flex;
  cursor: pointer;
}

.crm-upload-btn input[type='file'] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
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
