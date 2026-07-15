<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { hasPermission } from '../../config/permissions'
import { useAuthStore } from '../../stores/auth'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { useCrmViewList } from '../../composables/useCrmViewList'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'
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
const { fields, loadSchema } = useEntitySchema('campaign')
const { resolveMemberName, loadMembers, members } = useTeamMembers()

const statusFilter = ref('')
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

const {
  loading, items, total, page, pageSize, views, activeViewId, advancedFilters, advancedFilterVisible,
  searchKeyword, saveViewVisible, saveViewName, saveViewPinned, saveViewDefault, saveViewPublic,
  activeView, hasDraftFilters, hasTemporaryFilter, advancedFilterCount, defaultTableSort, tableSortKey,
  canSaveView, canManagePublic, loadViews, load, onSearch, onSearchClear, onViewChange,
  openAdvancedFilter, applyAdvancedFilters, openSaveView, submitSaveView, onViewsRefresh, clearActiveView,
  clearTemporaryFilters, onPageChange, initRouteView, watchRouteView,
} = useCrmViewList({
  entityType: 'campaign',
  listPath: '/crm/campaigns',
  fields,
  extraParams: computed(() => ({ status: statusFilter.value })),
  onResetExtra: () => { statusFilter.value = '' },
  fetcher: async (params) => {
    const { data } = await crmApi.listCampaigns(params)
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

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
    load()
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
    load()
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
    load()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err.message || '删除失败')
  }
}

onMounted(async () => {
  initRouteView()
  await Promise.all([loadSchema(), loadMembers()])
  await loadViews()
  load()
  watchRouteView()
})
</script>

<template>
  <div class="page-card">
    <CrmListToolbar
      title="营销活动"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-button v-if="canCreate()" type="primary" @click="openCreate">新建活动</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部活动"
          list-path="/crm/campaigns"
          :can-save="canSaveView()"
          :has-draft-filters="hasDraftFilters"
          @change="onViewChange"
          @save="openSaveView"
          @refresh="onViewsRefresh"
        />
      </template>

      <template #filters>
        <el-select
          v-model="statusFilter"
          clearable
          placeholder="状态"
          class="crm-list-status-filter"
          :disabled="!!activeViewId"
          @change="() => { page = 1; load() }"
        >
          <el-option
            v-for="item in CAMPAIGN_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索活动名称/编号"
          prefix-icon="Search"
          clearable
          :disabled="!!activeViewId"
          @clear="onSearchClear"
          @keyup.enter="onSearch"
        />
        <el-button class="crm-adv-filter-btn" :disabled="!!activeViewId" @click="openAdvancedFilter">
          高级筛选
          <el-badge v-if="advancedFilterCount" :value="advancedFilterCount" class="crm-adv-filter-badge" />
        </el-button>
        <el-button v-if="canSaveView() && hasDraftFilters && !activeViewId" link type="primary" @click="openSaveView">
          保存为视图
        </el-button>
      </template>
    </CrmListToolbar>

    <CrmAdvancedFilterDialog
      v-model:visible="advancedFilterVisible"
      :fields="fields"
      :members="members"
      :model-value="advancedFilters"
      @apply="applyAdvancedFilters"
    />

    <div class="crm-list-table-wrap">
      <el-table
        :key="tableSortKey"
        v-loading="loading"
        :data="items"
        border
        class="crm-list-table"
        :default-sort="defaultTableSort"
        :header-cell-class-name="() => 'crm-list-table__header-cell'"
        @row-click="goDetail"
      >
        <el-table-column prop="campaign_number" label="编号" width="150" show-overflow-tooltip />
        <el-table-column prop="name" label="活动名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
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
        <el-table-column label="负责人" width="100">
          <template #default="{ row }">{{ resolveMemberName(row.owner_user_id) }}</template>
        </el-table-column>
        <el-table-column prop="lead_count" label="线索" width="72" align="center" />
        <el-table-column prop="task_count" label="任务" width="72" align="center" />
        <el-table-column prop="content_count" label="内容" width="72" align="center" />
        <el-table-column label="更新时间" width="156">
          <template #default="{ row }">{{ formatUpdatedAt(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="canEdit()" link type="primary" @click.stop="openEdit(row, $event)">编辑</el-button>
            <el-button
              v-if="canManage() && row.status === 'draft'"
              link
              type="success"
              @click.stop="changeStatus(row, 'active', $event)"
            >启动</el-button>
            <el-button
              v-if="canManage() && row.status === 'active'"
              link
              type="warning"
              @click.stop="changeStatus(row, 'ended', $event)"
            >结束</el-button>
            <el-button v-if="canDelete()" link type="danger" @click.stop="handleDelete(row, $event)">删除</el-button>
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

    <el-dialog v-model="saveViewVisible" title="保存视图" width="400px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="saveViewName" placeholder="视图名称" />
        </el-form-item>
        <el-form-item label="钉选">
          <el-checkbox v-model="saveViewPinned">钉选到侧栏</el-checkbox>
        </el-form-item>
        <el-form-item label="默认">
          <el-checkbox v-model="saveViewDefault">设为默认视图</el-checkbox>
        </el-form-item>
        <el-form-item v-if="canManagePublic()" label="公开">
          <el-checkbox v-model="saveViewPublic">团队可见</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveViewVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSaveView">保存</el-button>
      </template>
    </el-dialog>

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
          <el-date-picker v-model="form.start_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="form.end_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="投放渠道">
          <el-select v-model="form.channels" multiple collapse-tags style="width: 100%">
            <el-option
              v-for="item in CAMPAIGN_CHANNEL_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="活动目标">
          <el-input v-model="form.goal" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="策划说明">
          <el-input v-model="form.description" type="textarea" :rows="3" />
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
.crm-adv-filter-btn { position: relative; }
.crm-adv-filter-badge { margin-left: 4px; }
.crm-adv-filter-badge :deep(.el-badge__content) {
  position: static;
  transform: none;
  vertical-align: middle;
}
.crm-list-status-filter { width: 120px; }
</style>
