<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { useTeamMembers } from '../../composables/useTeamMembers'
import { useCrmViewList } from '../../composables/useCrmViewList'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'
import CrmViewSwitcher from '../../components/crm/CrmViewSwitcher.vue'
import CrmAdvancedFilterDialog from '../../components/crm/CrmAdvancedFilterDialog.vue'

const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('product')
const { loadMembers, members } = useTeamMembers()

const activeFilter = ref(null)
const categories = ref([])
const categoryFilter = ref('')
const dialogVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = ref(emptyForm())

function emptyForm() {
  return {
    id: '',
    code: '',
    name: '',
    unit: '',
    list_price: null,
    cost_price: null,
    category_id: null,
    is_active: true,
    description: '',
  }
}

const canManage = () => hasPermission(auth.permissions, 'crm.product.manage')

const {
  loading, items, total, page, pageSize, views, activeViewId, advancedFilters, advancedFilterVisible,
  searchKeyword, saveViewVisible, saveViewName, saveViewPinned, saveViewDefault, saveViewPublic,
  activeView, hasDraftFilters, hasTemporaryFilter, advancedFilterCount, defaultTableSort, tableSortKey,
  canSaveView, canManagePublic, loadViews, load, onSearch, onSearchClear, onViewChange,
  openAdvancedFilter, applyAdvancedFilters, openSaveView, submitSaveView, onViewsRefresh, clearActiveView,
  clearTemporaryFilters, onPageChange, initRouteView, watchRouteView,
} = useCrmViewList({
  entityType: 'product',
  listPath: '/crm/products',
  fields,
  extraParams: computed(() => ({
    is_active: activeFilter.value,
    category_id: categoryFilter.value || undefined,
  })),
  onResetExtra: () => {
    activeFilter.value = null
    categoryFilter.value = ''
  },
  fetcher: async (params) => {
    const { data } = await crmApi.listProducts(params)
    return { items: data.items || [], total: data.total || 0, filters_applied: data.filters_applied }
  },
})

const categoryNameMap = computed(() =>
  Object.fromEntries(categories.value.map((c) => [c.id, c.name])),
)

async function loadCategories() {
  try {
    const { data } = await crmApi.listProductCategories()
    categories.value = Array.isArray(data) ? data : []
  } catch {
    categories.value = []
  }
}

function openCreate() {
  editing.value = false
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  form.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    unit: row.unit || '',
    list_price: Number(row.list_price),
    cost_price: row.cost_price != null ? Number(row.cost_price) : null,
    category_id: row.category_id || null,
    is_active: row.is_active,
    description: row.description || '',
  }
  dialogVisible.value = true
}

function goDetail(row) {
  router.push(`/crm/products/${row.id}`)
}

async function submit() {
  if (!form.value.name?.trim()) { ElMessage.warning('请填写产品名称'); return }
  saving.value = true
  try {
    const payload = {
      code: form.value.code?.trim() || null,
      name: form.value.name.trim(),
      unit: form.value.unit || null,
      list_price: form.value.list_price ?? 0,
      cost_price: form.value.cost_price,
      category_id: form.value.category_id || null,
      is_active: form.value.is_active,
      description: form.value.description || null,
    }
    if (editing.value) {
      await crmApi.updateProduct(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createProduct(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除产品「${row.name}」？`, '删除')
    await crmApi.deleteProduct(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(async () => {
  initRouteView()
  await Promise.all([loadSchema(), loadMembers(), loadCategories()])
  await loadViews()
  load()
  watchRouteView()
})
</script>

<template>
  <div class="page-card">
    <CrmListToolbar
      title="产品"
      :active-view="activeView"
      :filters-locked="!!activeViewId"
      :show-filter-hint="hasTemporaryFilter"
      @clear-view="clearActiveView"
      @clear-filters="clearTemporaryFilters"
    >
      <template #actions>
        <el-button v-if="canManage()" type="primary" @click="openCreate">新建产品</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          all-label="全部产品"
          list-path="/crm/products"
          :can-save="canSaveView()"
          :has-draft-filters="hasDraftFilters"
          @change="onViewChange"
          @save="openSaveView"
          @refresh="onViewsRefresh"
        />
      </template>

      <template #filters>
        <el-select
          v-model="activeFilter"
          clearable
          placeholder="启用状态"
          class="crm-list-status-filter"
          :disabled="!!activeViewId"
          @change="() => { page = 1; load() }"
        >
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-select
          v-model="categoryFilter"
          clearable
          filterable
          placeholder="分类"
          class="crm-list-category-filter"
          :disabled="!!activeViewId"
          @change="() => { page = 1; load() }"
        >
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索编码/名称"
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
        <el-table-column prop="code" label="编码" width="160" fixed="left" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click.stop="goDetail(row)">{{ row.code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="分类" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ categoryNameMap[row.category_id] || '—' }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column label="标价" width="130" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.list_price) }}</template>
        </el-table-column>
        <el-table-column label="成本价" width="130" align="right">
          <template #default="{ row }">{{ row.cost_price != null ? '¥' + formatAmount(row.cost_price) : '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="canManage()" link type="primary" @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="canManage()" link type="danger" @click.stop="handleDelete(row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑产品' : '新建产品'" width="520px">
      <el-form label-width="88px">
        <el-form-item label="编码">
          <el-input v-model="form.code" maxlength="50" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="200" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category_id" clearable filterable placeholder="选择分类" style="width: 100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" maxlength="30" />
        </el-form-item>
        <el-form-item label="标价">
          <el-input-number v-model="form.list_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number v-model="form.cost_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
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
.crm-list-category-filter { width: 140px; }
</style>
