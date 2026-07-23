<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'
import { formatApiError } from '../utils/apiError'
import CrmImportDialog from '../components/crm/CrmImportDialog.vue'

const activeTab = ref('categories')
const loading = ref(false)
const saving = ref(false)

const categories = ref([])
const units = ref([])
const specModels = ref([])

const categoryDialogVisible = ref(false)
const unitDialogVisible = ref(false)
const specDialogVisible = ref(false)
const specImportVisible = ref(false)
const editingCategoryId = ref(null)
const editingUnitId = ref(null)
const editingSpecId = ref(null)

const categoryForm = ref({
  name: '',
  parent_id: null,
  description: '',
  sort_order: 0,
  is_active: true,
})

const unitForm = ref({
  name: '',
  sort_order: 0,
  is_active: true,
})

const specForm = ref({
  name: '',
  code: '',
  description: '',
  sort_order: 0,
  is_active: true,
})

function isNameTaken(list, name, excludeId = null) {
  const n = String(name || '').trim()
  if (!n) return false
  return list.some((row) => row.name === n && row.id !== excludeId)
}
const parentCategoryOptions = computed(() =>
  categories.value.filter((c) => c.id !== editingCategoryId.value),
)

function resetCategoryForm() {
  editingCategoryId.value = null
  categoryForm.value = {
    name: '',
    parent_id: null,
    description: '',
    sort_order: 0,
    is_active: true,
  }
}

function resetUnitForm() {
  editingUnitId.value = null
  unitForm.value = {
    name: '',
    sort_order: 0,
    is_active: true,
  }
}

function resetSpecForm() {
  editingSpecId.value = null
  specForm.value = {
    name: '',
    code: '',
    description: '',
    sort_order: 0,
    is_active: true,
  }
}

function parentCategoryName(parentId) {
  if (!parentId) return '—'
  return categories.value.find((c) => c.id === parentId)?.name || '—'
}

async function loadCategories() {
  const { data } = await crmApi.listProductCategories()
  categories.value = Array.isArray(data) ? data : []
}

async function loadUnits() {
  const { data } = await crmApi.listProductUnits()
  units.value = Array.isArray(data) ? data : []
}

async function loadSpecModels() {
  const { data } = await crmApi.listProductSpecModels()
  specModels.value = Array.isArray(data) ? data : []
}

async function load() {
  loading.value = true
  try {
    await Promise.all([loadCategories(), loadUnits(), loadSpecModels()])
  } catch (e) {
    ElMessage.error(e.message || '加载产品基础数据失败')
  } finally {
    loading.value = false
  }
}

function openCreateCategory() {
  resetCategoryForm()
  categoryDialogVisible.value = true
}

function openEditCategory(row) {
  editingCategoryId.value = row.id
  categoryForm.value = {
    name: row.name,
    parent_id: row.parent_id || null,
    description: row.description || '',
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
  }
  categoryDialogVisible.value = true
}

function openCreateUnit() {
  resetUnitForm()
  unitDialogVisible.value = true
}

function openEditUnit(row) {
  editingUnitId.value = row.id
  unitForm.value = {
    name: row.name,
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
  }
  unitDialogVisible.value = true
}

function openCreateSpec() {
  resetSpecForm()
  specDialogVisible.value = true
}

function openEditSpec(row) {
  editingSpecId.value = row.id
  specForm.value = {
    name: row.name,
    code: row.code || '',
    description: row.description || '',
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
  }
  specDialogVisible.value = true
}

async function saveCategory() {
  if (!categoryForm.value.name.trim()) {
    ElMessage.warning('请填写分类名称')
    return
  }
  if (isNameTaken(categories.value, categoryForm.value.name, editingCategoryId.value)) {
    ElMessage.warning('分类名称已存在')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: categoryForm.value.name.trim(),
      parent_id: categoryForm.value.parent_id || null,
      description: categoryForm.value.description?.trim() || null,
      sort_order: Number(categoryForm.value.sort_order) || 0,
      is_active: categoryForm.value.is_active,
    }
    if (editingCategoryId.value) {
      await crmApi.updateProductCategory(editingCategoryId.value, payload)
      ElMessage.success('分类已更新')
    } else {
      await crmApi.createProductCategory(payload)
      ElMessage.success('分类已创建')
    }
    categoryDialogVisible.value = false
    await loadCategories()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存分类失败'))
  } finally {
    saving.value = false
  }
}

async function saveUnit() {
  if (!unitForm.value.name.trim()) {
    ElMessage.warning('请填写单位名称')
    return
  }
  if (isNameTaken(units.value, unitForm.value.name, editingUnitId.value)) {
    ElMessage.warning('单位名称已存在')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: unitForm.value.name.trim(),
      sort_order: Number(unitForm.value.sort_order) || 0,
      is_active: unitForm.value.is_active,
    }
    if (editingUnitId.value) {
      await crmApi.updateProductUnit(editingUnitId.value, payload)
      ElMessage.success('单位已更新')
    } else {
      await crmApi.createProductUnit(payload)
      ElMessage.success('单位已创建')
    }
    unitDialogVisible.value = false
    await loadUnits()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存单位失败'))
  } finally {
    saving.value = false
  }
}

async function saveSpec() {
  if (!specForm.value.name.trim()) {
    ElMessage.warning('请填写规格型号名称')
    return
  }
  if (isNameTaken(specModels.value, specForm.value.name, editingSpecId.value)) {
    ElMessage.warning('规格型号名称已存在')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: specForm.value.name.trim(),
      code: specForm.value.code?.trim() || null,
      description: specForm.value.description?.trim() || null,
      sort_order: Number(specForm.value.sort_order) || 0,
      is_active: specForm.value.is_active,
    }
    if (editingSpecId.value) {
      await crmApi.updateProductSpecModel(editingSpecId.value, payload)
      ElMessage.success('规格型号已更新')
    } else {
      await crmApi.createProductSpecModel(payload)
      ElMessage.success('规格型号已创建')
    }
    specDialogVisible.value = false
    await loadSpecModels()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存规格型号失败'))
  } finally {
    saving.value = false
  }
}

async function removeCategory(row) {
  try {
    await ElMessageBox.confirm(`删除分类「${row.name}」？关联产品将解除分类。`, '确认', { type: 'warning' })
    await crmApi.deleteProductCategory(row.id)
    ElMessage.success('已删除')
    await loadCategories()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function removeUnit(row) {
  try {
    await ElMessageBox.confirm(`删除单位「${row.name}」？关联产品将清空单位。`, '确认', { type: 'warning' })
    await crmApi.deleteProductUnit(row.id)
    ElMessage.success('已删除')
    await loadUnits()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function removeSpec(row) {
  try {
    await ElMessageBox.confirm(`删除规格型号「${row.name}」？`, '确认', { type: 'warning' })
    await crmApi.deleteProductSpecModel(row.id)
    ElMessage.success('已删除')
    await loadSpecModels()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function seedDefaultUnits() {
  saving.value = true
  try {
    const { data } = await crmApi.seedProductUnits()
    const count = Array.isArray(data) ? data.length : 0
    if (count > 0) {
      ElMessage.success(`已添加 ${count} 个常用单位`)
    } else {
      ElMessage.info('常用单位已存在，无需重复添加')
    }
    await loadUnits()
  } catch (e) {
    ElMessage.error(e.message || '添加常用单位失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="header">
      <div>
        <h2 class="title">产品基础数据</h2>
        <p class="desc">维护产品分类、计量单位与规格型号，新建产品时可从下拉中选择</p>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="产品分类" name="categories">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateCategory">新建分类</el-button>
        </div>
        <el-table :data="categories" border size="small" stripe>
          <el-table-column prop="name" label="分类名称" min-width="160" />
          <el-table-column label="上级分类" width="140">
            <template #default="{ row }">{{ parentCategoryName(row.parent_id) }}</template>
          </el-table-column>
          <el-table-column prop="sort_order" label="排序" width="80" align="right" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditCategory(row)">编辑</el-button>
              <el-button link type="danger" @click="removeCategory(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !categories.length" description="暂无分类，请先新建" />
      </el-tab-pane>

      <el-tab-pane label="计量单位" name="units">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateUnit">新建单位</el-button>
          <el-button @click="seedDefaultUnits">添加常用单位</el-button>
        </div>
        <el-table :data="units" border size="small" stripe>
          <el-table-column prop="name" label="单位名称" min-width="120" />
          <el-table-column prop="sort_order" label="排序" width="80" align="right" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditUnit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeUnit(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !units.length" description="暂无单位，可添加常用单位或手动新建" />
      </el-tab-pane>

      <el-tab-pane label="规格型号" name="specs">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateSpec">新建规格型号</el-button>
          <el-button @click="specImportVisible = true">导入</el-button>
        </div>
        <el-table :data="specModels" border size="small" stripe>
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="code" label="编码" width="120" show-overflow-tooltip />
          <el-table-column prop="sort_order" label="排序" width="80" align="right" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditSpec(row)">编辑</el-button>
              <el-button link type="danger" @click="removeSpec(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !specModels.length" description="暂无规格型号，请先新建" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="categoryDialogVisible" :title="editingCategoryId ? '编辑分类' : '新建分类'" width="480px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="categoryForm.name" maxlength="100" />
        </el-form-item>
        <el-form-item label="上级分类">
          <el-select v-model="categoryForm.parent_id" clearable filterable placeholder="无" style="width: 100%">
            <el-option v-for="c in parentCategoryOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="categoryForm.sort_order" :min="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="categoryForm.is_active" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="categoryForm.description" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="unitDialogVisible" :title="editingUnitId ? '编辑单位' : '新建单位'" width="420px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="unitForm.name" maxlength="30" placeholder="如：套、个、台" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="unitForm.sort_order" :min="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="unitForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="unitDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUnit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="specDialogVisible" :title="editingSpecId ? '编辑规格型号' : '新建规格型号'" width="480px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="specForm.name" maxlength="100" placeholder="如：标准版 / DN50" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="specForm.code" maxlength="50" placeholder="可选，租户内唯一" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="specForm.sort_order" :min="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="specForm.is_active" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="specForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="specDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSpec">保存</el-button>
      </template>
    </el-dialog>

    <CrmImportDialog
      v-model:visible="specImportVisible"
      entity-type="product_spec_model"
      @done="loadSpecModels"
    />
  </div>
</template>

<style scoped>
.header {
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 20px;
}
.desc {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.tab-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
