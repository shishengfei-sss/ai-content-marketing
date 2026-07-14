<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import CrmListToolbar from '../../components/crm/CrmListToolbar.vue'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
let searchDebounceTimer = null
const SEARCH_DEBOUNCE_MS = 400

const dialogVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = ref(emptyForm())

function emptyForm() {
  return { id: '', code: '', name: '', unit: '', list_price: null, cost_price: null, is_active: true, description: '' }
}

const canManage = () => hasPermission(auth.permissions, 'crm.product.manage')

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    const q = searchKeyword.value.trim()
    if (q) params.q = q
    const { data } = await crmApi.listProducts(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); searchDebounceTimer = null }
  searchDebounceTimer = setTimeout(() => { page.value = 1; load() }, SEARCH_DEBOUNCE_MS)
}

function onSearchClear() {
  if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); searchDebounceTimer = null }
  page.value = 1
  load()
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
    is_active: row.is_active,
    description: row.description || '',
  }
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.code?.trim()) { ElMessage.warning('请填写产品编码'); return }
  if (!form.value.name?.trim()) { ElMessage.warning('请填写产品名称'); return }
  saving.value = true
  try {
    const payload = {
      code: form.value.code.trim(),
      name: form.value.name.trim(),
      unit: form.value.unit || null,
      list_price: form.value.list_price ?? 0,
      cost_price: form.value.cost_price,
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

function onPageChange(p) { page.value = p; load() }
function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(() => { load() })
</script>

<template>
  <div class="page-card">
    <CrmListToolbar title="产品" :show-filter-hint="!!searchKeyword.trim()" @clear-filters="onSearchClear">
      <template #actions>
        <el-button v-if="canManage()" type="primary" @click="openCreate">新建产品</el-button>
      </template>

      <template #view>
        <span class="crm-list-all-label">全部产品</span>
      </template>

      <template #filters>
        <el-input
          v-model="searchKeyword"
          class="crm-list-search"
          placeholder="搜索编码/名称"
          prefix-icon="Search"
          clearable
          @clear="onSearchClear"
          @keyup.enter="onSearch"
        />
      </template>
    </CrmListToolbar>

    <div class="crm-list-table-wrap">
      <el-table
        v-loading="loading"
        :data="items"
        border
        class="crm-list-table"
        :header-cell-class-name="() => 'crm-list-table__header-cell'"
        @row-click="openEdit"
      >
        <el-table-column prop="code" label="编码" width="160" fixed="left" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
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
        <el-table-column label="操作" width="130" fixed="right" align="center" @click.stop>
          <template #default="{ row }">
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

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑产品' : '新建产品'" width="520px">
      <el-form label-width="88px">
        <el-form-item label="编码" required>
          <el-input v-model="form.code" maxlength="50" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="200" />
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
.crm-list-all-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}
</style>
