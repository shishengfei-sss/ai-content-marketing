<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { getFormFields, LEAD_STATUS_OPTIONS } from '../../utils/entityForm'
import { formatDateTime } from '../../utils/datetime'
import CrmAssignOwner from '../../components/crm/CrmAssignOwner.vue'
import CrmDetailHero from '../../components/crm/CrmDetailHero.vue'
import CrmDetailShell from '../../components/crm/CrmDetailShell.vue'
import CrmEntityFieldsView from '../../components/crm/CrmEntityFieldsView.vue'
import CrmEntityFormDialog from '../../components/crm/CrmEntityFormDialog.vue'
import CrmEntityTasks from '../../components/crm/CrmEntityTasks.vue'
import CrmEntityTags from '../../components/crm/CrmEntityTags.vue'
import { isActiveTaskStatus } from '../../utils/taskMeta'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('lead')
const { loadMembers, resolveMemberName } = useTeamMembers()

const listPath = computed(() =>
  route.query.from === 'lead-pools' ? '/crm/lead-pools' : '/crm/leads',
)
const entityLabel = computed(() =>
  route.query.from === 'lead-pools' ? '线索公海' : '线索',
)

const loading = ref(false)
const activeTab = ref('profile')
const lead = ref(null)
const campaignName = ref('')
const activities = ref([])
const tasks = ref([])
const attachments = ref([])
const uploading = ref(false)
const activityForm = ref({ activity_type: 'call', content: '', next_follow_up_at: '', status: '' })
const taskPanelRef = ref(null)
const assignVisible = ref(false)
const editVisible = ref(false)
const bantList = ref([])
const bantVisible = ref(false)
const bantSaving = ref(false)
const bantForm = ref({
  budget_score: 3,
  authority_score: 3,
  need_score: 3,
  time_score: 3,
  note: '',
})
const reclaimVisible = ref(false)
const reclaimSaving = ref(false)
const reclaimPools = ref([])
const reclaimPoolId = ref('')
const scoreBusy = ref(false)

const formFields = computed(() => getFormFields(fields.value, 'lead'))

const canWriteActivity = () => hasPermission(auth.permissions, 'crm.activity.create')
const canAssign = () => hasPermission(auth.permissions, 'crm.lead.assign')
const canEdit = () => hasPermission(auth.permissions, 'crm.lead.edit')
const isLeadOwner = () => {
  const a = lead.value?.owner_user_id
  const b = auth.user?.id
  return (
    !!a &&
    !!b &&
    String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
  )
}
/** 编辑 / 退回公海等：权限 + 负责人 */
const canMutateLead = () => canEdit() && isLeadOwner()
const canConvert = () => hasPermission(auth.permissions, 'crm.lead.convert') && isLeadOwner()
const canCpq = () => hasPermission(auth.permissions, 'crm.quote.create')
const isTenantAdmin = () => auth.user?.active_tenant?.role_code === 'admin'

const heroAvatar = computed(() => (lead.value?.company_name || '线').slice(0, 1))

const heroMeta = computed(() => {
  if (!lead.value) return []
  return [
    { label: '联系人', value: lead.value.contact_name || '—' },
    { label: '手机', value: lead.value.mobile || '—' },
    { label: '来源', value: lead.value.source || '—' },
    { label: '评分', value: lead.value.lead_score ?? '—' },
    { label: '线索状态', value: lead.value.status || '—' },
  ]
})

const ownerName = computed(() => resolveMemberName(lead.value?.owner_user_id))

const heroStats = computed(() => [
  { label: '跟进记录', value: activities.value.length },
  { label: '待办任务', value: tasks.value.filter((t) => isActiveTaskStatus(t.status)).length },
  { label: '职位', value: lead.value?.title || '—' },
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

async function loadDetail({ afterAssign = false } = {}) {
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
    await loadAttachments()
    await loadBant()
    await taskPanelRef.value?.reload()
  } catch (e) {
    const forbidden = e.status === 403 || String(e.message || '').includes('无权访问')
    if (afterAssign && forbidden) {
      // 分配组件已提示成功；失去可见权时安静回列表，避免再弹「无权访问」
      router.replace('/crm/leads')
      return
    }
    ElMessage.error(e.message || '加载失败')
    router.replace('/crm/leads')
  } finally {
    loading.value = false
  }
}

async function onAssignDone() {
  await loadDetail({ afterAssign: true })
}

async function loadBant() {
  try {
    const { data } = await crmApi.listBant(route.params.id)
    bantList.value = Array.isArray(data) ? data : []
  } catch {
    bantList.value = []
  }
}

function openBantDialog() {
  bantForm.value = {
    budget_score: 3,
    authority_score: 3,
    need_score: 3,
    time_score: 3,
    note: '',
  }
  bantVisible.value = true
}

async function submitBant() {
  bantSaving.value = true
  try {
    await crmApi.createBant(route.params.id, {
      budget_score: bantForm.value.budget_score,
      authority_score: bantForm.value.authority_score,
      need_score: bantForm.value.need_score,
      time_score: bantForm.value.time_score,
      note: bantForm.value.note.trim() || null,
    })
    ElMessage.success('BANT 已保存')
    bantVisible.value = false
    await loadBant()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    bantSaving.value = false
  }
}

async function recalculateScore() {
  scoreBusy.value = true
  try {
    await crmApi.recalculateLeadScore(route.params.id)
    ElMessage.success('评分已重算')
    await loadDetail()
  } catch (e) {
    ElMessage.error(e.message || '重算失败')
  } finally {
    scoreBusy.value = false
  }
}

async function openReclaim() {
  try {
    const { data: pools } = await crmApi.listLeadPools()
    reclaimPools.value = Array.isArray(pools) ? pools : []
    if (!reclaimPools.value.length) {
      try {
        await ElMessageBox.confirm('暂无线索公海，是否前往设置创建？', '退回公海', {
          type: 'warning',
          confirmButtonText: '去设置',
          cancelButtonText: '取消',
        })
        router.push('/settings/lead-pools')
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
    await crmApi.reclaimLeadToPool(route.params.id, { pool_id: reclaimPoolId.value })
    ElMessage.success('已退回公海')
    reclaimVisible.value = false
    router.push('/crm/leads')
  } catch (e) {
    ElMessage.error(e.message || '退回失败')
  } finally {
    reclaimSaving.value = false
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
    const { data } = await crmApi.listAttachments({ entity_type: 'lead', entity_id: route.params.id })
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
    await crmApi.uploadAttachment('lead', route.params.id, file)
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
    if (canMutateLead() && activityForm.value.status) {
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
      '线索转化为客户后会出现在客户列表。可同时创建商机。',
      '转化客户',
      { confirmButtonText: '继续', cancelButtonText: '取消' },
    )
    let createDeal = false
    try {
      await ElMessageBox.confirm('是否同步创建商机？', '创建商机', {
        confirmButtonText: '创建商机',
        cancelButtonText: '仅转客户',
        distinguishCancelAndClose: true,
      })
      createDeal = true
    } catch (e) {
      if (e === 'close') return
      createDeal = false
    }

    const tryConvert = async (body) => {
      try {
        return await crmApi.convertLead(route.params.id, body)
      } catch (err) {
        const detail = err?.response?.data?.detail
        if (err?.response?.status === 409 && detail?.duplicate_candidates?.length) {
          return { duplicate: detail }
        }
        throw err
      }
    }

    let result = await tryConvert({ force_create: false, create_deal: createDeal })
    if (result.duplicate) {
      const candidates = result.duplicate.duplicate_candidates
      try {
        await ElMessageBox.confirm(
          `发现疑似重复客户（${candidates.length} 个）。合并到已有客户，或强制新建？`,
          '去重提示',
          { confirmButtonText: '合并到已有', cancelButtonText: '强制新建', distinguishCancelAndClose: true },
        )
        result = await crmApi.convertLead(route.params.id, {
          force_create: false,
          merge_into_customer_id: candidates[0],
          create_deal: createDeal,
        })
      } catch (e) {
        if (e === 'close') return
        if (e === 'cancel') {
          result = await crmApi.convertLead(route.params.id, {
            force_create: true,
            create_deal: createDeal,
          })
        } else {
          throw e
        }
      }
    }

    const data = result.data || result
    ElMessage.success(
      data.deal_id
        ? data.merged
          ? '已合并到客户并创建商机'
          : '已转化为客户并创建商机'
        : data.merged
          ? '已合并到已有客户'
          : '已转化为客户',
    )
    await loadDetail()
    router.push(`/crm/customers/${data.customer_id}`)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.message || '转化失败')
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
    :list-path="listPath"
    :entity-label="entityLabel"
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
        <el-button
          v-if="canCpq() && lead.converted_customer_id"
          type="primary"
          plain
          @click="router.push({
            path: '/crm/quotes/cpq/new',
            query: { customer_id: lead.converted_customer_id, lead_id: lead.id },
          })"
        >
          CPQ 报价
        </el-button>
        <el-button v-if="canMutateLead()" @click="editVisible = true">编辑资料</el-button>
        <el-tooltip
          v-if="canMutateLead()"
          content="按设置中的评分规则重新计算并覆盖当前分；BANT 仅在更高时抬升"
          placement="bottom"
        >
          <el-button :loading="scoreBusy" @click="recalculateScore">重算评分</el-button>
        </el-tooltip>
        <el-button v-if="canAssign()" @click="assignVisible = true">分配负责人</el-button>
        <el-button v-if="canMutateLead()" type="warning" plain @click="openReclaim">退回公海</el-button>
        <el-button v-if="canConvert() && lead.status !== '已转化'" type="primary" @click="handleConvert">
          转化客户
        </el-button>
      </template>
    </CrmDetailHero>

    <section v-if="lead" class="page-card crm-detail-tabs">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="资料" name="profile">
          <div class="crm-panel" style="margin-bottom: 16px">
            <div class="crm-panel__title">标签</div>
            <CrmEntityTags
              entity-type="lead"
              :entity-id="route.params.id"
              :editable="canMutateLead()"
            />
          </div>
          <CrmEntityFieldsView
            :record="lead"
            :fields="formFields"
            :campaign-name="campaignName"
            :owner-name="ownerName"
          />
        </el-tab-pane>

        <el-tab-pane label="BANT" name="bant">
          <div class="crm-panel">
            <div class="crm-panel__head">
              <div>
                <div class="crm-panel__title">BANT 评估</div>
                <div class="crm-panel__hint">
                  预算(Budget) / 决策权(Authority) / 需求(Need) / 时间(Time)，各 1–5 分
                </div>
              </div>
              <el-button v-if="canMutateLead()" type="primary" @click="openBantDialog">新增评估</el-button>
            </div>
          </div>
          <el-table v-if="bantList.length" :data="bantList" stripe class="crm-table">
            <el-table-column label="时间" width="160">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="budget_score" label="预算" width="80" align="center" />
            <el-table-column prop="authority_score" label="决策权" width="90" align="center" />
            <el-table-column prop="need_score" label="需求" width="80" align="center" />
            <el-table-column prop="time_score" label="时间" width="80" align="center" />
            <el-table-column prop="total_score" label="总分" width="80" align="center" />
            <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
            <el-table-column label="评估人" width="120">
              <template #default="{ row }">{{ resolveMemberName(row.created_by_user_id) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无 BANT 评估" />
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
                v-if="canMutateLead()"
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
              :timestamp="formatDateTime(item.created_at)"
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

        <el-tab-pane label="文档" name="attachments">
          <div class="crm-panel">
            <div class="crm-panel__head">
              <div class="crm-panel__title">文档附件</div>
              <label v-if="canMutateLead()" class="crm-upload-btn">
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
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="downloadAttachment(row)">下载</el-button>
                <el-button v-if="canMutateLead()" link type="danger" size="small" @click="removeAttachment(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无附件" />
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
      @done="onAssignDone"
    />

    <el-dialog v-model="bantVisible" title="新增 BANT 评估" width="520px" destroy-on-close>
      <el-form label-position="top" class="bant-form">
        <el-form-item required>
          <template #label>
            <span>预算（Budget）</span>
            <span class="bant-form__desc">客户是否有明确采购预算、预算是否充足</span>
          </template>
          <el-input-number v-model="bantForm.budget_score" :min="1" :max="5" />
        </el-form-item>
        <el-form-item required>
          <template #label>
            <span>决策权（Authority）</span>
            <span class="bant-form__desc">对接人是否具备拍板/强力影响决策的权力</span>
          </template>
          <el-input-number v-model="bantForm.authority_score" :min="1" :max="5" />
        </el-form-item>
        <el-form-item required>
          <template #label>
            <span>需求（Need）</span>
            <span class="bant-form__desc">业务痛点是否清晰、对方案需求是否强烈</span>
          </template>
          <el-input-number v-model="bantForm.need_score" :min="1" :max="5" />
        </el-form-item>
        <el-form-item required>
          <template #label>
            <span>时间（Time）</span>
            <span class="bant-form__desc">是否有明确采购/上线时间表、紧迫程度如何</span>
          </template>
          <el-input-number v-model="bantForm.time_score" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="bantForm.note"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="补充评估依据或跟进建议（选填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bantVisible = false">取消</el-button>
        <el-button type="primary" :loading="bantSaving" @click="submitBant">保存</el-button>
      </template>
    </el-dialog>

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

.crm-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
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

.crm-panel__title {
  margin-bottom: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.crm-panel__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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

.bant-form :deep(.el-form-item__label) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  line-height: 1.4;
}

.bant-form__desc {
  font-size: 12px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}
</style>
