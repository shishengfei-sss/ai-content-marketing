<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('pending')
const q = ref('')
const region = ref('')
const industry = ref('')
const category = ref('')
const procurementMethod = ref('')
const agentName = ref('')
const projectNo = ref('')
const smePreference = ref(null)
const deadlineRange = ref([])
const minScore = ref(null)

const METHOD_OPTIONS = ['公开招标', '询价', '竞争性谈判', '竞争性磋商', '邀请招标', '单一来源']

const canClaim = () => hasPermission(auth.permissions, 'crm.lead.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.lead.edit')

const STATUS = {
  pending: { label: '待处理', type: 'warning' },
  valid: { label: '已纳入', type: 'success' },
  invalid: { label: '已忽略', type: 'info' },
  expired: { label: '已过期', type: 'danger' },
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (q.value.trim()) params.q = q.value.trim()
    if (region.value.trim()) params.region = region.value.trim()
    if (industry.value.trim()) params.industry = industry.value.trim()
    if (category.value.trim()) params.category = category.value.trim()
    if (procurementMethod.value) params.procurement_method = procurementMethod.value
    if (agentName.value.trim()) params.agent_name = agentName.value.trim()
    if (projectNo.value.trim()) params.project_no = projectNo.value.trim()
    if (smePreference.value !== null && smePreference.value !== undefined && smePreference.value !== '') {
      params.sme_preference = smePreference.value
    }
    if (deadlineRange.value?.length === 2) {
      params.deadline_from = deadlineRange.value[0]
      params.deadline_to = deadlineRange.value[1]
    }
    if (minScore.value != null && minScore.value !== '') params.min_score = Number(minScore.value)
    const { data } = await crmApi.listTenderLeads(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  load()
}

function resetFilters() {
  statusFilter.value = 'pending'
  q.value = ''
  region.value = ''
  industry.value = ''
  category.value = ''
  procurementMethod.value = ''
  agentName.value = ''
  projectNo.value = ''
  smePreference.value = null
  deadlineRange.value = []
  minScore.value = null
  onFilterChange()
}

async function claim(row) {
  try {
    await ElMessageBox.confirm(`将「${row.buyer_name}」纳入 CRM 线索？不会创建商机。`, '纳入线索')
    const { data } = await crmApi.claimTenderLead(row.id)
    ElMessage.success('已纳入线索')
    router.push(`/crm/leads/${data.lead_id}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '认领失败')
  }
}

async function ignore(row) {
  try {
    await crmApi.ignoreTenderLead(row.id)
    ElMessage.success('已忽略')
    load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <h2 class="title">招标线索</h2>
      <div class="spacer" />
      <el-button @click="router.push('/settings/icp')">ICP 配置</el-button>
      <el-button @click="router.push('/crm/tender-lead-analytics')">效果看板</el-button>
    </div>

    <div class="toolbar filters">
      <el-input
        v-model="q"
        clearable
        placeholder="关键词：采购方/标的/编号/代理"
        style="width: 220px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="projectNo"
        clearable
        placeholder="项目编号"
        style="width: 140px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="region"
        clearable
        placeholder="地区"
        style="width: 110px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="category"
        clearable
        placeholder="品目"
        style="width: 120px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="industry"
        clearable
        placeholder="行业"
        style="width: 110px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-select
        v-model="procurementMethod"
        clearable
        filterable
        allow-create
        default-first-option
        placeholder="采购方式"
        style="width: 130px"
        @change="onFilterChange"
      >
        <el-option v-for="m in METHOD_OPTIONS" :key="m" :label="m" :value="m" />
      </el-select>
      <el-input
        v-model="agentName"
        clearable
        placeholder="代理单位"
        style="width: 150px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-select v-model="smePreference" clearable placeholder="中小企业" style="width: 130px" @change="onFilterChange">
        <el-option :value="true" label="面向中小企业" />
        <el-option :value="false" label="非面向中小企业" />
      </el-select>
      <el-select v-model="statusFilter" clearable placeholder="状态" style="width: 120px" @change="onFilterChange">
        <el-option v-for="(m, k) in STATUS" :key="k" :label="m.label" :value="k" />
      </el-select>
      <el-input-number
        v-model="minScore"
        :min="0"
        :max="100"
        :controls="false"
        placeholder="最低匹配分"
        style="width: 120px"
        @keyup.enter="onFilterChange"
      />
      <el-date-picker
        v-model="deadlineRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="投标截止起"
        end-placeholder="截止止"
        style="width: 240px"
        @change="onFilterChange"
      />
      <el-button type="primary" @click="onFilterChange">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border>
      <el-table-column label="匹配度" width="90" align="center" sortable>
        <template #default="{ row }">
          <strong>{{ row.match_score }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="buyer_name" label="采购方" min-width="140" show-overflow-tooltip />
      <el-table-column prop="project_no" label="项目编号" width="120" show-overflow-tooltip />
      <el-table-column prop="agent_name" label="代理单位" min-width="120" show-overflow-tooltip />
      <el-table-column prop="product_name" label="标的" min-width="110" show-overflow-tooltip />
      <el-table-column prop="category" label="品目" width="100" show-overflow-tooltip />
      <el-table-column prop="procurement_method" label="采购方式" width="100" />
      <el-table-column prop="region" label="地区" width="90" />
      <el-table-column prop="deadline" label="投标截止" width="110" />
      <el-table-column prop="bid_open_date" label="开标日" width="110" />
      <el-table-column label="中小企业" width="90" align="center">
        <template #default="{ row }">
          <span v-if="row.sme_preference === true">是</span>
          <span v-else-if="row.sme_preference === false">否</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="原文" width="80">
        <template #default="{ row }">
          <el-link v-if="row.source_url" :href="row.source_url" target="_blank" type="primary">打开</el-link>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type || 'info'" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            v-if="canClaim() && row.status === 'pending'"
            link
            type="primary"
            @click="claim(row)"
          >纳入线索</el-button>
          <el-button
            v-if="canEdit() && row.status === 'pending'"
            link
            @click="ignore(row)"
          >忽略</el-button>
          <el-button
            v-if="row.converted_lead_id"
            link
            type="success"
            @click="router.push(`/crm/leads/${row.converted_lead_id}`)"
          >查看线索</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
.filters { row-gap: 10px; }
.title { margin: 0; font-size: 18px; margin-right: 8px; }
.spacer { flex: 1; min-width: 8px; }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
