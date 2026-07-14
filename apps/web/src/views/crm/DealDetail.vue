<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import DealFormDialog from './DealFormDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { resolveMemberName, loadMembers, members: memberOptions } = useTeamMembers()

const loading = ref(false)
const deal = ref(null)
const customer = ref(null)
const pipelines = ref([])
const territories = ref([])
const stageLogs = ref([])
const activities = ref([])
const activityForm = ref({ activity_type: 'call', subject: '', content: '' })
const activitySaving = ref(false)
const attachments = ref([])
const uploading = ref(false)
const teamMembers = ref([])
const addTeamVisible = ref(false)
const addTeamForm = ref({ user_id: '', role: 'member' })
const closeVisible = ref(false)
const closeForm = ref({ status: 'won', amount: null, reason: '', competitor: '', detail: '', improvement: '' })
const editVisible = ref(false)

const canEdit = computed(() => hasPermission(auth.permissions, 'crm.deal.edit'))
const canClose = computed(() => hasPermission(auth.permissions, 'crm.deal.close'))
const canConvert = computed(() => hasPermission(auth.permissions, 'crm.deal.convert'))
const canGenerateQuote = computed(() => hasPermission(auth.permissions, 'crm.quote.edit'))
const canWriteActivity = computed(() => hasPermission(auth.permissions, 'crm.activity.create'))

const activityLabels = {
  call: '电话',
  visit: '拜访',
  wechat: '微信',
  email: '邮件',
  other: '其他',
}
const activityTypeOptions = Object.entries(activityLabels).map(([value, label]) => ({ value, label }))

const currentPipeline = computed(() =>
  pipelines.value.find((p) => String(p.id) === String(deal.value?.pipeline_id)),
)
const stages = computed(() => currentPipeline.value?.stages || [])
const currentStage = computed(() =>
  stages.value.find((s) => String(s.id) === String(deal.value?.stage_id)),
)
const isClosed = computed(() => ['won', 'lost', 'abandoned'].includes(deal.value?.status))
const territoryName = computed(() => {
  const t = territories.value.find((x) => String(x.id) === String(deal.value?.territory_id))
  return t?.name || ''
})
const priorityLabel = (v) => ({ high: '高', medium: '中', low: '低' })[v] || v || '-'
const priorityTagType = (v) => ({ high: 'danger', medium: 'warning', low: 'info' })[v] || ''

async function loadDeal() {
  loading.value = true
  try {
    const { data } = await crmApi.getDeal(route.params.id)
    deal.value = data
    if (data.customer_id) {
      try {
        const c = await crmApi.getCustomer(data.customer_id)
        customer.value = c.data
      } catch { customer.value = null }
    }
    await loadStageLogs()
    await loadActivities()
    await loadAttachments()
    await loadTeam()
  } catch (e) {
    ElMessage.error(e.message || '加载商机失败')
  } finally {
    loading.value = false
  }
}

async function loadPipelines() {
  try {
    const { data } = await crmApi.listPipelines()
    pipelines.value = Array.isArray(data) ? data : []
  } catch { pipelines.value = [] }
}

async function loadTerritories() {
  try {
    const { data } = await crmApi.listTerritories()
    territories.value = Array.isArray(data) ? data : []
  } catch { territories.value = [] }
}

async function loadStageLogs() {
  try {
    const { data } = await crmApi.listDealStageLogs(route.params.id)
    stageLogs.value = Array.isArray(data) ? data : []
  } catch { stageLogs.value = [] }
}

async function loadActivities() {
  try {
    const { data } = await crmApi.listDealActivities(route.params.id)
    activities.value = Array.isArray(data) ? data : []
  } catch { activities.value = [] }
}

async function submitActivity() {
  if (!activityForm.value.content?.trim()) { ElMessage.warning('请填写跟进内容'); return }
  activitySaving.value = true
  try {
    await crmApi.createDealActivity(route.params.id, {
      activity_type: activityForm.value.activity_type,
      subject: activityForm.value.subject || null,
      content: activityForm.value.content.trim(),
    })
    ElMessage.success('已添加跟进')
    activityForm.value = { activity_type: 'call', subject: '', content: '' }
    await loadActivities()
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    activitySaving.value = false
  }
}

async function removeActivity(id) {
  try {
    await ElMessageBox.confirm('确定删除这条跟进记录？', '删除', { type: 'warning' })
  } catch { return }
  try {
    await crmApi.deleteActivity(id)
    await loadActivities()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function loadAttachments() {
  try {
    const { data } = await crmApi.listAttachments({ entity_type: 'deal', entity_id: route.params.id })
    attachments.value = Array.isArray(data) ? data : []
  } catch { attachments.value = [] }
}

async function onUploadFile(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  if (file.size > 50 * 1024 * 1024) { ElMessage.warning('文件超过 50MB'); return }
  uploading.value = true
  try {
    await crmApi.uploadAttachment('deal', route.params.id, file)
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
  } catch { return }
  try {
    await crmApi.deleteAttachment(att.id)
    await loadAttachments()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function loadTeam() {
  try {
    const { data } = await crmApi.listDealTeam(route.params.id)
    teamMembers.value = Array.isArray(data) ? data : []
  } catch { teamMembers.value = [] }
}

async function submitAddTeam() {
  if (!addTeamForm.value.user_id) { ElMessage.warning('请选择成员'); return }
  try {
    await crmApi.addDealTeam(route.params.id, {
      user_id: addTeamForm.value.user_id,
      role: addTeamForm.value.role || 'member',
    })
    ElMessage.success('已添加成员')
    addTeamVisible.value = false
    addTeamForm.value = { user_id: '', role: 'member' }
    await loadTeam()
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
  }
}

async function removeTeamMemberApi(m) {
  try {
    await ElMessageBox.confirm(`确定移除成员「${resolveMemberName(m.user_id)}」？`, '移除', { type: 'warning' })
  } catch { return }
  try {
    await crmApi.removeDealTeam(route.params.id, m.id)
    await loadTeam()
    ElMessage.success('已移除')
  } catch (e) {
    ElMessage.error(e.message || '移除失败')
  }
}

async function changeStage(stageId) {
  if (!deal.value) return
  if (String(stageId) === String(deal.value.stage_id)) return
  try {
    await crmApi.changeDealStage(deal.value.id, { stage_id: stageId })
    ElMessage.success('阶段已更新')
    await loadDeal()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}

async function closeDeal(status) {
  if (!deal.value) return
  closeForm.value = {
    status,
    amount: status === 'won' ? Number(deal.value.amount || 0) : null,
    reason: '',
    competitor: deal.value.competitor || '',
    detail: '',
    improvement: '',
  }
  closeVisible.value = true
}

async function submitClose() {
  if (!deal.value) return
  const f = closeForm.value
  if (f.status === 'lost' && !f.reason?.trim()) { ElMessage.warning('请填写输单原因'); return }
  try {
    await crmApi.closeDeal(deal.value.id, {
      status: f.status,
      amount: f.status === 'won' ? Number(f.amount || 0) : null,
      loss_reason: f.reason || null,
      reason: f.reason || null,
      competitor: f.competitor || null,
      detail: f.detail || null,
      improvement: f.improvement || null,
    })
    ElMessage.success('商机已关闭')
    closeVisible.value = false
    await loadDeal()
  } catch (e) {
    ElMessage.error(e.message || '关闭失败')
  }
}

async function cloneDeal() {
  if (!deal.value) return
  try {
    await ElMessageBox.confirm(`复制商机「${deal.value.title}」？`, '克隆商机', { type: 'info' })
    const { data } = await crmApi.cloneDeal(deal.value.id)
    ElMessage.success('已克隆商机')
    if (data?.deal_id) router.push(`/crm/deals/${data.deal_id}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '克隆失败')
  }
}

async function convertToOrder() {
  if (!deal.value) return
  try {
    await ElMessageBox.confirm(
      `将商机「${deal.value.title}」转化为订单？将创建一张草稿订单。`,
      '转化为订单',
      { confirmButtonText: '确定', cancelButtonText: '取消' },
    )
    const { data } = await crmApi.convertDealToOrder(deal.value.id)
    ElMessage.success('已转化为订单')
    if (data?.id) {
      router.push(`/crm/orders/${data.id}`)
    } else {
      await loadDeal()
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '转化失败')
  }
}

async function generateQuote() {
  if (!deal.value) return
  try {
    await ElMessageBox.confirm(
      `将商机「${deal.value.title}」的明细生成报价单？`,
      '生成报价',
      { confirmButtonText: '确定', cancelButtonText: '取消' },
    )
    const { data } = await crmApi.generateDealQuote(deal.value.id)
    ElMessage.success('已生成报价单')
    if (data?.id) router.push(`/crm/quotes/${data.id}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '生成报价失败')
  }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 16)
}

function statusTagType(s) {
  if (s === 'won') return 'success'
  if (s === 'lost') return 'danger'
  if (s === 'abandoned') return 'info'
  return 'warning'
}

function statusLabel(s) {
  return ({ open: '进行中', won: '赢单', lost: '输单', abandoned: '放弃' })[s] || s
}

onMounted(async () => {
  await Promise.all([loadMembers(), loadPipelines(), loadTerritories()])
  await loadDeal()
})
</script>

<template>
  <div v-loading="loading" class="deal-detail">
    <div class="deal-detail__back">
      <el-button link @click="router.push('/crm/deals')">
        <el-icon><ArrowLeft /></el-icon> 返回商机列表
      </el-button>
    </div>

    <div v-if="deal" class="page-card deal-detail__head">
      <div class="deal-detail__head-left">
        <h2 class="deal-detail__title">{{ deal.title }}</h2>
        <div class="deal-detail__meta">
          <el-tag :type="statusTagType(deal.status)">{{ statusLabel(deal.status) }}</el-tag>
          <el-tag v-if="currentStage" type="warning">{{ currentStage.name }}</el-tag>
          <el-tag v-if="deal.priority" :type="priorityTagType(deal.priority)" size="small">优先级：{{ priorityLabel(deal.priority) }}</el-tag>
          <span class="deal-detail__amount">¥{{ formatAmount(deal.amount) }}</span>
          <span class="deal-detail__owner">负责人：{{ resolveMemberName(deal.owner_user_id) }}</span>
        </div>
      </div>
      <div class="deal-detail__head-actions">
        <el-button v-if="canEdit" @click="editVisible = true">编辑</el-button>
        <el-button v-if="canEdit && !isClosed" @click="cloneDeal">克隆</el-button>
        <el-button v-if="canGenerateQuote && !isClosed && (deal.lines?.length || 0)" @click="generateQuote">
          生成报价
        </el-button>
        <el-button v-if="canConvert && !isClosed && !deal.converted_order_id" type="primary" @click="convertToOrder">
          转化为订单
        </el-button>
        <template v-if="canClose && !isClosed">
          <el-button type="success" @click="closeDeal('won')">赢单</el-button>
          <el-button type="danger" @click="closeDeal('lost')">输单</el-button>
        </template>
      </div>
    </div>

    <div v-if="deal" class="deal-detail__body">
      <el-card class="deal-detail__card" shadow="never">
        <template #header>基本信息</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="商机名称">{{ deal.title }}</el-descriptions-item>
          <el-descriptions-item label="客户">
            <el-link v-if="customer" type="primary" @click="router.push(`/crm/customers/${customer.id}`)">
              {{ customer.company_name }}
            </el-link>
            <span v-else>{{ deal.customer_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="销售管道">{{ currentPipeline?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="阶段">
            <el-select
              v-if="canEdit && !isClosed && stages.length"
              :model-value="deal.stage_id"
              size="small"
              style="width: 160px"
              @change="changeStage"
            >
              <el-option v-for="s in stages" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <span v-else>{{ currentStage?.name || deal.stage_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="商机金额">¥{{ formatAmount(deal.amount) }}</el-descriptions-item>
          <el-descriptions-item label="成交概率">{{ deal.probability }}%</el-descriptions-item>
          <el-descriptions-item label="预计成交日">{{ formatDate(deal.expected_close_date) || '-' }}</el-descriptions-item>
          <el-descriptions-item label="商机来源">{{ deal.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="商机类型">{{ deal.deal_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ priorityLabel(deal.priority) }}</el-descriptions-item>
          <el-descriptions-item label="竞争对手">{{ deal.competitor || '-' }}</el-descriptions-item>
          <el-descriptions-item label="联系人角色">{{ deal.contact_role || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属地区">{{ territoryName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(deal.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(deal.updated_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="deal.closed_at" label="成交时间">{{ formatDate(deal.closed_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="deal.loss_reason" label="输单原因">{{ deal.loss_reason }}</el-descriptions-item>
          <el-descriptions-item v-if="deal.converted_order_id" label="转出订单">
            <el-link type="primary" @click="router.push(`/crm/orders/${deal.converted_order_id}`)">
              查看订单
            </el-link>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="deal.next_step || deal.description" class="deal-detail__card" shadow="never">
        <template #header>下一步与需求</template>
        <div v-if="deal.next_step" class="deal-detail__nextstep">
          <span class="deal-detail__nextstep-label">下一步：</span>{{ deal.next_step }}
        </div>
        <div v-if="deal.description" class="deal-detail__desc">{{ deal.description }}</div>
      </el-card>

      <el-card v-if="deal.lines && deal.lines.length" class="deal-detail__card" shadow="never">
        <template #header>产品明细</template>
        <el-table :data="deal.lines" size="small" border>
          <el-table-column prop="product_name" label="名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="unit" label="单位" width="70" />
          <el-table-column label="数量" width="90" align="right">
            <template #default="{ row }">{{ row.quantity }}</template>
          </el-table-column>
          <el-table-column label="单价" width="110" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.unit_price) }}</template>
          </el-table-column>
          <el-table-column label="折扣%" width="80" align="right">
            <template #default="{ row }">{{ row.discount_percent }}%</template>
          </el-table-column>
          <el-table-column label="小计" width="120" align="right">
            <template #default="{ row }">¥{{ formatAmount(row.subtotal) }}</template>
          </el-table-column>
        </el-table>
        <div class="deal-detail__lines-total">合计：¥{{ formatAmount(deal.amount) }}</div>
      </el-card>

      <el-card class="deal-detail__card" shadow="never">
        <template #header>阶段变更记录</template>
        <el-timeline v-if="stageLogs.length">
          <el-timeline-item
            v-for="log in stageLogs"
            :key="log.id"
            :timestamp="formatDate(log.changed_at)"
            placement="top"
          >
            <div class="deal-detail__log">
              <span class="deal-detail__log-from">{{ log.from_stage_name || '初始' }}</span>
              <el-icon><ArrowRight /></el-icon>
              <span class="deal-detail__log-to">{{ log.to_stage_name }}</span>
              <span class="deal-detail__log-user">{{ resolveMemberName(log.changed_by_user_id) }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无阶段变更记录" :image-size="60" />
      </el-card>
    </div>

    <el-card v-if="deal" class="deal-detail__card deal-detail__activities" shadow="never">
      <template #header>跟进记录</template>
      <div v-if="canWriteActivity" class="deal-detail__activity-form">
        <el-select v-model="activityForm.activity_type" style="width: 110px">
          <el-option v-for="o in activityTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-model="activityForm.subject" placeholder="主题（可选）" maxlength="200" style="width: 200px" />
        <el-input
          v-model="activityForm.content"
          type="textarea"
          :rows="1"
          placeholder="跟进内容…"
          style="flex: 1"
        />
        <el-button type="primary" :loading="activitySaving" @click="submitActivity">记录</el-button>
      </div>
      <el-timeline v-if="activities.length" class="deal-detail__activity-list">
        <el-timeline-item
          v-for="item in activities"
          :key="item.id"
          :timestamp="formatDate(item.created_at)"
          placement="top"
        >
          <div class="deal-detail__activity-item">
            <el-tag size="small" type="info">{{ activityLabels[item.activity_type] || item.activity_type }}</el-tag>
            <span v-if="item.subject" class="deal-detail__activity-subject">{{ item.subject }}</span>
            <span class="deal-detail__activity-content">{{ item.content }}</span>
            <span class="deal-detail__activity-user">{{ resolveMemberName(item.created_by_user_id) }}</span>
            <el-button
              v-if="canWriteActivity"
              link
              type="danger"
              size="small"
              @click="removeActivity(item.id)"
            >删除</el-button>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无跟进记录，写一条跟进开始吧" :image-size="60" />
    </el-card>

    <el-card v-if="deal" class="deal-detail__card deal-detail__attachments" shadow="never">
      <template #header>
        <div class="deal-detail__attach-head">
          <span>文档附件</span>
          <label v-if="canEdit" class="deal-detail__upload-btn">
            <input type="file" :disabled="uploading" @change="onUploadFile" />
            <el-button type="primary" size="small" :loading="uploading">上传附件</el-button>
          </label>
        </div>
      </template>
      <el-table v-if="attachments.length" :data="attachments" size="small" border>
        <el-table-column prop="file_name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="上传人" width="120">
          <template #default="{ row }">{{ resolveMemberName(row.uploaded_by_user_id) }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="downloadAttachment(row)">下载</el-button>
            <el-button v-if="canEdit" link type="danger" size="small" @click="removeAttachment(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无附件，上传方案/合同/资料等" :image-size="60" />
    </el-card>

    <el-card v-if="deal" class="deal-detail__card deal-detail__team" shadow="never">
      <template #header>
        <div class="deal-detail__attach-head">
          <span>协作团队</span>
          <el-button v-if="canEdit" type="primary" size="small" @click="addTeamVisible = true">添加成员</el-button>
        </div>
      </template>
      <el-table v-if="teamMembers.length" :data="teamMembers" size="small" border>
        <el-table-column label="成员" min-width="160">
          <template #default="{ row }">{{ resolveMemberName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column label="角色" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="row.role === 'owner' ? 'warning' : 'info'">
              {{ row.role === 'owner' ? '负责人' : row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="加入时间" width="160">
          <template #default="{ row }">{{ formatDate(row.joined_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button v-if="canEdit && row.role !== 'owner'" link type="danger" size="small" @click="removeTeamMemberApi(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无团队成员" :image-size="60" />
    </el-card>

    <el-dialog v-model="addTeamVisible" title="添加团队成员" width="420px" align-center>
      <el-form label-width="80px">
        <el-form-item label="成员">
          <el-select v-model="addTeamForm.user_id" filterable placeholder="选择成员" style="width: 100%">
            <el-option
              v-for="m in memberOptions"
              :key="m.user_id"
              :label="m.display_name || m.phone || m.user_id"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="addTeamForm.role" maxlength="30" placeholder="如 售前/技术/经理" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addTeamVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddTeam">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="closeVisible" title="关闭商机" width="520px" align-center>
      <el-form label-width="88px">
        <el-form-item label="关闭类型">
          <el-tag :type="closeForm.status === 'won' ? 'success' : closeForm.status === 'lost' ? 'danger' : 'info'">
            {{ { won: '赢单', lost: '输单', abandoned: '放弃' }[closeForm.status] }}
          </el-tag>
        </el-form-item>
        <el-form-item v-if="closeForm.status === 'won'" label="成交金额">
          <el-input-number v-model="closeForm.amount" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="closeForm.status === 'lost' ? '输单原因' : '原因'" :required="closeForm.status === 'lost'">
          <el-input v-model="closeForm.reason" maxlength="200" placeholder="如：价格过高、竞品胜出、需求变更" />
        </el-form-item>
        <el-form-item label="竞争对手">
          <el-input v-model="closeForm.competitor" maxlength="200" />
        </el-form-item>
        <el-form-item label="详细说明">
          <el-input v-model="closeForm.detail" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="改进建议">
          <el-input v-model="closeForm.improvement" type="textarea" :rows="2" placeholder="复盘后可填写改进方向" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeVisible = false">取消</el-button>
        <el-button type="primary" @click="submitClose">确认关闭</el-button>
      </template>
    </el-dialog>

    <DealFormDialog
      v-model:visible="editVisible"
      :pipelines="pipelines"
      :record="deal"
      mode="edit"
      @saved="loadDeal"
    />
  </div>
</template>

<style scoped>
.deal-detail__back { margin-bottom: 8px; }
.deal-detail__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.deal-detail__title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
}
.deal-detail__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.deal-detail__amount {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.deal-detail__head-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.deal-detail__body {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}
.deal-detail__card { margin-bottom: 0; }
.deal-detail__log {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.deal-detail__log-to {
  font-weight: 600;
  color: var(--el-color-primary);
}
.deal-detail__log-user {
  margin-left: auto;
  color: var(--el-text-color-secondary);
}
.deal-detail__nextstep {
  font-size: 13px;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
}
.deal-detail__nextstep-label {
  color: var(--el-text-color-secondary);
  margin-right: 4px;
}
.deal-detail__desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  line-height: 1.6;
  background: var(--el-fill-color-light);
  padding: 10px 12px;
  border-radius: 6px;
}
.deal-detail__lines-total {
  margin-top: 10px;
  text-align: right;
  font-weight: 600;
  color: var(--el-color-primary);
}
.deal-detail__activities { margin-top: 16px; }
.deal-detail__activity-form {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.deal-detail__activity-list { padding-left: 4px; }
.deal-detail__activity-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  flex-wrap: wrap;
}
.deal-detail__activity-subject { font-weight: 600; color: var(--el-text-color-primary); }
.deal-detail__activity-content { color: var(--el-text-color-regular); flex: 1; min-width: 200px; }
.deal-detail__activity-user { color: var(--el-text-color-secondary); font-size: 12px; }
.deal-detail__attachments { margin-top: 16px; }
.deal-detail__attach-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.deal-detail__upload-btn { cursor: pointer; }
.deal-detail__upload-btn input[type="file"] { display: none; }

@media (max-width: 960px) {
  .deal-detail__body { grid-template-columns: 1fr; }
}
</style>
