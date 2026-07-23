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
import CrmImportDialog from '../../components/crm/CrmImportDialog.vue'
import DynamicField from '../../components/crm/DynamicField.vue'

const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('product')
const { loadMembers, members } = useTeamMembers()

const activeFilter = ref(null)
const categories = ref([])
const units = ref([])
const specModels = ref([])
const categoryFilter = ref('')
const dialogVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = ref(emptyForm())
const extraForm = ref({})
const importVisible = ref(false)

function emptyForm() {
  return {
    id: '',
    code: '',
    name: '',
    unit: '',
    list_price: null,
    cost_price: null,
    default_tax_rate: null,
    price_includes_tax: false,
    category_id: null,
    spec_model_id: null,
    is_active: true,
    cpq_enabled: false,
    description: '',
  }
}

const canManage = () => hasPermission(auth.permissions, 'crm.product.manage')
const canImport = () =>
  hasPermission(auth.permissions, 'crm.product.import')
  || hasPermission(auth.permissions, 'crm.product.manage')

const customFields = computed(() =>
  (fields.value || []).filter(
    (f) => f.is_active !== false && String(f.field_key || '').startsWith('cf_'),
  ),
)

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

const unitOptions = computed(() => {
  const names = units.value.map((u) => u.name)
  const current = form.value.unit?.trim()
  if (current && !names.includes(current)) {
    return [{ id: `legacy-${current}`, name: current }, ...units.value]
  }
  return units.value
})

function resetExtraForm(recordExtra = {}) {
  const next = {}
  for (const f of customFields.value) {
    const key = f.field_key
    if (recordExtra[key] !== undefined && recordExtra[key] !== null) {
      next[key] = recordExtra[key]
    } else if (f.field_type === 'checkbox') {
      next[key] = false
    } else if (f.field_type === 'multiselect') {
      next[key] = []
    } else {
      next[key] = f.default_value ?? ''
    }
  }
  extraForm.value = next
}

async function loadCategories() {
  try {
    const { data } = await crmApi.listProductCategories({ active_only: true })
    categories.value = Array.isArray(data) ? data : []
  } catch {
    categories.value = []
  }
}

async function loadUnits() {
  try {
    const { data } = await crmApi.listProductUnits({ active_only: true })
    units.value = Array.isArray(data) ? data : []
  } catch {
    units.value = []
  }
}

async function loadSpecModels() {
  try {
    const { data } = await crmApi.listProductSpecModels({ active_only: true })
    specModels.value = Array.isArray(data) ? data : []
  } catch {
    specModels.value = []
  }
}

function openCreate() {
  editing.value = false
  form.value = emptyForm()
  resetExtraForm()
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
    default_tax_rate: row.default_tax_rate != null ? Number(row.default_tax_rate) : null,
    price_includes_tax: !!row.price_includes_tax,
    category_id: row.category_id || null,
    spec_model_id: row.spec_model_id || null,
    is_active: row.is_active,
    cpq_enabled: !!row.cpq_enabled,
    description: row.description || '',
  }
  resetExtraForm(row.extra_data || {})
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
      default_tax_rate: form.value.default_tax_rate,
      price_includes_tax: !!form.value.price_includes_tax,
      category_id: form.value.category_id || null,
      spec_model_id: form.value.spec_model_id || null,
      is_active: form.value.is_active,
      cpq_enabled: !!form.value.cpq_enabled,
      description: form.value.description || null,
      extra_data: { ...extraForm.value },
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
    if (e === 'cancel') return
    const msg = e.message || '删除失败'
    if (String(msg).includes('无法删除') && row.is_active) {
      try {
        await ElMessageBox.confirm(`${msg}\n是否改为停用该产品？`, '无法删除', {
          confirmButtonText: '停用',
          cancelButtonText: '取消',
          type: 'warning',
        })
        await crmApi.updateProduct(row.id, { is_active: false })
        ElMessage.success('已停用')
        load()
        return
      } catch (e2) {
        if (e2 === 'cancel') return
        ElMessage.error(e2.message || '停用失败')
        return
      }
    }
    ElMessage.error(msg)
  }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(async () => {
  initRouteView()
  await Promise.all([loadSchema(), loadMembers(), loadCategories(), loadUnits(), loadSpecModels()])
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
        <el-button v-if="canImport()" @click="importVisible = true">导入</el-button>
        <el-button v-if="canManage()" type="primary" @click="openCreate">新建产品</el-button>
      </template>

      <template #view>
        <CrmViewSwitcher
          v-model="activeViewId"
          :views="views"
          list-path="/crm/products"
          @change="onViewChange"
          @refresh="onViewsRefresh"
        />
      </template>

      <template #filters>
        <el-select
          v-model="activeFilter"
          class="crm-list-status-filter"
          clearable
          placeholder="状态"
          :disabled="!!activeViewId"
          @change="() => { page = 1; load() }"
        >
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-select
          v-model="categoryFilter"
          class="crm-list-category-filter"
          clearable
          filterable
          placeholder="分类"
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

    <CrmImportDialog v-model:visible="importVisible" entity-type="product" @done="load" />

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
        <el-table-column label="规格型号" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec_model_name || '—' }}</template>
        </el-table-column>
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
        <el-table-column label="CPQ" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.cpq_enabled" type="warning" size="small">开</el-tag>
            <span v-else class="muted">—</span>
          </template>
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

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑产品' : '新建产品'" width="560px">
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
          <p v-if="!categories.length" class="form-hint">
            暂无分类，请先到
            <router-link to="/settings/product-master-data">设置 → 产品基础数据</router-link>
            维护
          </p>
        </el-form-item>
        <el-form-item label="规格型号">
          <el-select v-model="form.spec_model_id" clearable filterable placeholder="选择规格型号" style="width: 100%">
            <el-option v-for="s in specModels" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <p v-if="!specModels.length" class="form-hint">
            暂无规格型号，请先到
            <router-link to="/settings/product-master-data">设置 → 产品基础数据</router-link>
            维护
          </p>
        </el-form-item>
        <el-form-item label="单位">
          <el-select v-model="form.unit" clearable filterable placeholder="选择单位" style="width: 100%">
            <el-option v-for="u in unitOptions" :key="u.id" :label="u.name" :value="u.name" />
          </el-select>
          <p v-if="!units.length" class="form-hint">
            暂无单位，请先到
            <router-link to="/settings/product-master-data">设置 → 产品基础数据</router-link>
            维护
          </p>
        </el-form-item>
        <el-form-item label="标价">
          <el-input-number v-model="form.list_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="标价含税">
          <el-switch v-model="form.price_includes_tax" />
        </el-form-item>
        <el-form-item label="默认税率%">
          <div style="display:flex;gap:8px;align-items:center;width:100%">
            <el-input-number
              v-model="form.default_tax_rate"
              :min="0"
              :max="100"
              :precision="2"
              :controls="false"
              style="flex:1"
            />
            <el-button-group>
              <el-button size="small" @click="form.default_tax_rate = 13">13</el-button>
              <el-button size="small" @click="form.default_tax_rate = 9">9</el-button>
              <el-button size="small" @click="form.default_tax_rate = 6">6</el-button>
              <el-button size="small" @click="form.default_tax_rate = 0">0</el-button>
            </el-button-group>
          </div>
          <p v-if="form.list_price != null && form.default_tax_rate != null" class="form-hint">
            参考：未税
            ¥{{
              formatAmount(
                form.price_includes_tax
                  ? Number(form.list_price) / (1 + Number(form.default_tax_rate) / 100)
                  : form.list_price,
              )
            }}
            ／ 含税
            ¥{{
              formatAmount(
                form.price_includes_tax
                  ? form.list_price
                  : Number(form.list_price) * (1 + Number(form.default_tax_rate) / 100),
              )
            }}
          </p>
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number v-model="form.cost_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="CPQ">
          <el-switch v-model="form.cpq_enabled" />
          <p class="form-hint">开启后可在产品详情配置参数与价差</p>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <template v-if="customFields.length">
          <div class="extra-title">扩展信息</div>
          <el-form-item
            v-for="field in customFields"
            :key="field.field_key"
            :label="field.label"
            :required="!!field.is_required"
          >
            <DynamicField v-model="extraForm[field.field_key]" :field="field" />
          </el-form-item>
        </template>
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
.form-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.form-hint a {
  color: var(--el-color-primary);
}
.extra-title {
  margin: 8px 0 12px;
  padding-left: 8px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
}
.muted { color: var(--el-text-color-placeholder); }
</style>
