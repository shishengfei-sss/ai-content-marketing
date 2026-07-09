<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'

const ENTITY_TABS = [
  { key: 'lead', label: '线索' },
  { key: 'customer', label: '客户' },
  { key: 'contact', label: '联系人' },
]

const activeEntity = ref('lead')
const loading = ref(false)
const fields = ref([])

const addVisible = ref(false)
const addForm = ref({
  field_key: 'cf_',
  label: '',
  field_type: 'text',
  is_required: false,
  show_in_list_default: false,
})

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
  addForm.value = {
    field_key: 'cf_',
    label: '',
    field_type: 'text',
    is_required: false,
    show_in_list_default: false,
  }
  addVisible.value = true
}

async function submitAdd() {
  if (!addForm.value.field_key.startsWith('cf_') || addForm.value.field_key.length < 4) {
    ElMessage.warning('自定义字段 key 须以 cf_ 开头')
    return
  }
  if (!addForm.value.label.trim()) {
    ElMessage.warning('请填写显示名称')
    return
  }
  try {
    await crmApi.createSchemaField(activeEntity.value, addForm.value)
    ElMessage.success('已添加')
    addVisible.value = false
    loadFields()
  } catch (e) {
    ElMessage.error(e.message || '添加失败')
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
      <el-table-column prop="field_type" label="类型" width="120" />
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
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="!row.is_system" link type="danger" @click="removeField(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="addVisible" title="新增自定义字段" width="480px">
      <el-form label-width="100px">
        <el-form-item label="字段 Key" required>
          <el-input v-model="addForm.field_key" placeholder="cf_xxx" />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="addForm.label" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="addForm.field_type" style="width: 100%">
            <el-option label="文本" value="text" />
            <el-option label="多行文本" value="textarea" />
            <el-option label="数字" value="number" />
            <el-option label="金额" value="currency" />
            <el-option label="下拉" value="select" />
            <el-option label="手机" value="phone" />
            <el-option label="邮箱" value="email" />
          </el-select>
        </el-form-item>
        <el-form-item label="必填">
          <el-switch v-model="addForm.is_required" />
        </el-form-item>
        <el-form-item label="列表默认">
          <el-switch v-model="addForm.show_in_list_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdd">保存</el-button>
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
