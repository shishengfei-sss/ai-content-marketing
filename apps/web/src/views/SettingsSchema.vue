<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'

const ENTITY_TABS = [
  { key: 'lead', label: '线索' },
  { key: 'customer', label: '客户' },
  { key: 'contact', label: '联系人' },
  { key: 'product', label: '产品' },
]

const FIELD_TYPE_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '多行文本', value: 'textarea' },
  { label: '数字', value: 'number' },
  { label: '金额', value: 'currency' },
  { label: '下拉', value: 'select' },
  { label: '手机', value: 'phone' },
  { label: '邮箱', value: 'email' },
]

const activeEntity = ref('lead')
const loading = ref(false)
const fields = ref([])
const saving = ref(false)

const dialogVisible = ref(false)
const editing = ref(false)
const form = ref(emptyForm())

function emptyForm() {
  return {
    field_key: 'cf_',
    label: '',
    field_type: 'text',
    is_required: false,
    show_in_list_default: false,
    options: [],
    placeholder: '',
  }
}

async function loadFields() {
  loading.value = true
  try {
    const { data } = await crmApi.getSchema(activeEntity.value)
    fields.value = data.fields || []
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onTabChange() {
  loadFields()
}

function openAdd() {
  editing.value = false
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  form.value = {
    field_key: row.field_key,
    label: row.label || '',
    field_type: row.field_type || 'text',
    is_required: !!row.is_required,
    show_in_list_default: !!row.show_in_list_default,
    options: Array.isArray(row.options) ? row.options.map(String) : [],
    placeholder: row.placeholder || '',
  }
  dialogVisible.value = true
}

function needsOptions(type) {
  return type === 'select' || type === 'multiselect'
}

async function submitForm() {
  if (!form.value.label.trim()) {
    ElMessage.warning('请填写显示名称')
    return
  }
  if (!editing.value) {
    if (!form.value.field_key.startsWith('cf_') || form.value.field_key.length < 4) {
      ElMessage.warning('自定义字段 key 须以 cf_ 开头')
      return
    }
  }
  if (needsOptions(form.value.field_type) && !form.value.options.length) {
    ElMessage.warning('下拉类型请至少配置一个选项')
    return
  }

  saving.value = true
  try {
    if (editing.value) {
      await crmApi.updateSchemaField(activeEntity.value, form.value.field_key, {
        label: form.value.label.trim(),
        is_required: form.value.is_required,
        show_in_list_default: form.value.show_in_list_default,
        options: needsOptions(form.value.field_type) ? form.value.options : undefined,
        placeholder: form.value.placeholder || null,
      })
      ElMessage.success('已保存')
    } else {
      await crmApi.createSchemaField(activeEntity.value, {
        field_key: form.value.field_key,
        label: form.value.label.trim(),
        field_type: form.value.field_type,
        is_required: form.value.is_required,
        show_in_list_default: form.value.show_in_list_default,
        options: needsOptions(form.value.field_type) ? form.value.options : [],
        placeholder: form.value.placeholder || null,
      })
      ElMessage.success('已添加')
    }
    dialogVisible.value = false
    await loadFields()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeField(row) {
  if (row.is_system) {
    ElMessage.warning('系统字段不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`删除自定义字段「${row.label}」？`, '确认')
    await crmApi.deleteSchemaField(activeEntity.value, row.field_key)
    ElMessage.success('已删除')
    loadFields()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function formatOptions(row) {
  if (!Array.isArray(row.options) || !row.options.length) return '—'
  return row.options.map(String).join('、')
}

function typeLabel(v) {
  return FIELD_TYPE_OPTIONS.find((o) => o.value === v)?.label || v
}

onMounted(loadFields)
</script>

<template>
  <div class="page-card">
    <div class="page-header">
      <div class="page-title">表单字段</div>
      <el-button type="primary" @click="openAdd">新增自定义字段</el-button>
    </div>

    <el-tabs v-model="activeEntity" @tab-change="onTabChange">
      <el-tab-pane v-for="tab in ENTITY_TABS" :key="tab.key" :label="tab.label" :name="tab.key" />
    </el-tabs>

    <el-table v-loading="loading" :data="fields" stripe>
      <el-table-column prop="field_key" label="字段 Key" width="180" />
      <el-table-column prop="label" label="显示名称" min-width="140" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ typeLabel(row.field_type) }}</template>
      </el-table-column>
      <el-table-column label="选项" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ formatOptions(row) }}</template>
      </el-table-column>
      <el-table-column label="系统字段" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_system ? 'info' : 'success'" size="small">
            {{ row.is_system ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="列表默认" width="100">
        <template #default="{ row }">{{ row.show_in_list_default ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="!row.is_system" link type="danger" @click="removeField(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑字段' : '新增自定义字段'"
      width="520px"
    >
      <el-form label-width="100px">
        <el-form-item label="字段 Key" required>
          <el-input
            v-model="form.field_key"
            placeholder="cf_xxx"
            :disabled="editing"
          />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="form.label" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select
            v-model="form.field_type"
            style="width: 100%"
            :disabled="editing"
          >
            <el-option
              v-for="o in FIELD_TYPE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="needsOptions(form.field_type)" label="选项" required>
          <el-select
            v-model="form.options"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车添加选项"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="占位提示">
          <el-input v-model="form.placeholder" placeholder="可选" />
        </el-form-item>
        <el-form-item label="必填">
          <el-switch v-model="form.is_required" />
        </el-form-item>
        <el-form-item label="列表默认">
          <el-switch v-model="form.show_in_list_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
}
</style>
