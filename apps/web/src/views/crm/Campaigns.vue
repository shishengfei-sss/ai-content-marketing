<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { hasPermission } from '../../config/permissions'
import { useAuthStore } from '../../stores/auth'
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

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const keyword = ref('')

const formVisible = ref(false)
const formSaving = ref(false)
const editingId = ref('')
const form = ref(emptyForm())

function emptyForm() {
  return {
    name: '',
    status: 'draft',
    start_at: null,
    end_at: null,
    goal: '',
    channels: [],
    description: '',
  }
}

const canCreate = () => hasPermission(auth.permissions, 'crm.campaign.create')
const canEdit = () => hasPermission(auth.permissions, 'crm.campaign.edit')
const canDelete = () => hasPermission(auth.permissions, 'crm.campaign.delete')
const canManage = () => hasPermission(auth.permissions, 'crm.campaign.manage')

function ownerLabel(ownerUserId) {
  if (!ownerUserId) return '—'
  return ownerUserId === auth.user?.id ? '我' : '同事'
}

function formatUpdatedAt(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadCampaigns() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (keyword.value.trim()) params.q = keyword.value.trim()
    const { data } = await crmApi.listCampaigns(params)
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
  loadCampaigns()
}

function onPageChange(p) {
  page.value = p
  loadCampaigns()
}

function goDetail(row) {
  router.push(`/crm/campaigns/${row.id}`)
}

function openCreate() {
  editingId.value = ''
  form.value = emptyForm()
  formVisible.value = true
}

function openEdit(row, e) {
  e?.stopPropagation?.()
  editingId.value = row.id
  form.value = {
    name: row.name || '',
    status: row.status || 'draft',
    start_at: toCampaignDateValue(row.start_at),
    end_at: toCampaignDateValue(row.end_at),
    goal: row.goal || '',
    channels: [...(row.channels || [])],
    description: row.description || '',
  }
  formVisible.value = true
}

function buildPayload() {
  return {
    name: form.value.name.trim(),
    status: form.value.status,
    start_at: campaignDateToIso(form.value.start_at),
    end_at: campaignDateToIso(form.value.end_at),
    goal: form.value.goal?.trim() || null,
    channels: form.value.channels || [],
    description: form.value.description?.trim() || null,
  }
}

async function submitForm() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写活动名称')
    return
  }
  formSaving.value = true
  try {
    if (editingId.value) {
      await crmApi.updateCampaign(editingId.value, buildPayload())
      ElMessage.success('活动已更新')
    } else {
      await crmApi.createCampaign(buildPayload())
      ElMessage.success('活动已创建')
      page.value = 1
    }
    formVisible.value = false
    loadCampaigns()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    formSaving.value = false
  }
}

async function changeStatus(row, status, e) {
  e?.stopPropagation?.()
  if (!canManage()) return
  try {
    await crmApi.updateCampaign(row.id, { status })
    ElMessage.success('状态已更新')
    loadCampaigns()
  } catch (err) {
    ElMessage.error(err.message || '更新失败')
  }
}

async function handleDelete(row, e) {
  e?.stopPropagation?.()
  if (!canDelete()) return
  try {
    await ElMessageBox.confirm(`确定删除活动「${row.name}」？`, '删除活动', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await crmApi.deleteCampaign(row.id)
    ElMessage.success('已删除')
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    loadCampaigns()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message || '删除失败')
  }
}

onMounted(loadCampaigns)
</script>

<template>
  <div class="page-card">
    <div class="page-header">
      <div>
        <div class="page-title">营销活动</div>
        <p class="page-subtitle">策划获客活动，关联内容、线索与任务，追踪转化效果</p>
      </div>
      <el-button v-if="canCreate()" type="primary" @click="openCreate">新建活动</el-button>
    </div>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索活动名称"
        clearable
        style="width: 220px"
        @clear="onFilterChange"
        @keyup.enter="onFilterChange"
      />
      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        clearable
        style="width: 130px"
        @change="onFilterChange"
      >
        <el-option
          v-for="item in CAMPAIGN_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-button @click="onFilterChange">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" stripe @row-click="goDetail">
      <el-table-column prop="campaign_number" label="编号" width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="name-link">{{ row.campaign_number || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="活动名称" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="name-link">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="campaignStatusTagType(row.status)">
            {{ campaignStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="活动周期" min-width="170">
        <template #default="{ row }">{{ formatCampaignPeriod(row) }}</template>
      </el-table-column>
      <el-table-column label="渠道" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ formatCampaignChannels(row.channels) }}</template>
      </el-table-column>
      <el-table-column label="负责人" width="90">
        <template #default="{ row }">{{ ownerLabel(row.owner_user_id) }}</template>
      </el-table-column>
      <el-table-column prop="lead_count" label="线索" width="72" align="center" />
      <el-table-column prop="task_count" label="任务" width="72" align="center" />
      <el-table-column prop="content_count" label="内容" width="72" align="center" />
      <el-table-column label="更新时间" width="156">
        <template #default="{ row }">{{ formatUpdatedAt(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right" @click.stop>
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
          <el-button v-if="canEdit()" link type="primary" @click.stop="openEdit(row, $event)">
            编辑
          </el-button>
          <el-button
            v-if="canManage() && row.status === 'draft'"
            link
            type="success"
            @click.stop="changeStatus(row, 'active', $event)"
          >
            启动
          </el-button>
          <el-button
            v-if="canManage() && row.status === 'active'"
            link
            type="warning"
            @click.stop="changeStatus(row, 'ended', $event)"
          >
            结束
          </el-button>
          <el-button v-if="canDelete()" link type="danger" @click.stop="handleDelete(row, $event)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !items.length" description="暂无营销活动，点击右上角新建" />

    <div v-if="total > 0" class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>

    <el-dialog
      v-model="formVisible"
      :title="editingId ? '编辑活动' : '新建活动'"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="88px">
        <el-form-item label="活动名称" required>
          <el-input v-model="form.name" placeholder="如：2026 Q3 财税获客" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item v-if="editingId && canManage()" label="状态">
          <el-select v-model="form.status" style="width: 100%">
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
            v-model="form.start_at"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择开始日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="form.end_at"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="投放渠道">
          <el-select v-model="form.channels" multiple collapse-tags style="width: 100%" placeholder="选择渠道">
            <el-option
              v-for="item in CAMPAIGN_CHANNEL_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="活动目标">
          <el-input v-model="form.goal" type="textarea" :rows="2" placeholder="如：获取 50 条有效线索" />
        </el-form-item>
        <el-form-item label="策划说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="活动背景、受众、执行要点" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="formSaving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.name-link {
  color: var(--el-color-primary);
  font-weight: 500;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
