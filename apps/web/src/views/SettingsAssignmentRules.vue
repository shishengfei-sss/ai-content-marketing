<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'
import { useTeamMembers } from '../composables/useTeamMembers'

const loading = ref(false)
const saving = ref(false)
const rules = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const { members, loadMembers } = useTeamMembers()

const form = ref({
  name: '',
  field: 'source',
  operator: 'contains',
  value: '',
  assign_type: 'fixed_user',
  target_id: '',
  priority: 0,
  is_active: true,
})

const ASSIGN_LABELS = {
  fixed_user: '指定用户',
  round_robin: '轮询',
  load_balanced: '负载均衡',
}

function resetForm() {
  editingId.value = null
  form.value = {
    name: '',
    field: 'source',
    operator: 'contains',
    value: '',
    assign_type: 'fixed_user',
    target_id: '',
    priority: 0,
    is_active: true,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listAssignmentRules()
    rules.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e.message || '加载分配规则失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  const cond = row.condition_json || {}
  form.value = {
    name: row.name,
    field: cond.field || 'source',
    operator: cond.operator || cond.op || 'contains',
    value: cond.value ?? '',
    assign_type: row.assign_type || 'fixed_user',
    target_id: row.target_id || '',
    priority: row.priority ?? 0,
    is_active: row.is_active !== false,
  }
  dialogVisible.value = true
}

function memberName(id) {
  if (!id) return '—'
  const m = members.value.find((x) => x.user_id === id)
  return m?.display_name || m?.phone || String(id).slice(0, 8)
}

function conditionText(row) {
  const c = row.condition_json || {}
  if (!c.field) return '—'
  return `${c.field} ${c.operator || c.op || ''} ${c.value ?? ''}`
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  if (form.value.assign_type === 'fixed_user' && !form.value.target_id) {
    ElMessage.warning('请选择指派用户')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      condition_json: {
        field: form.value.field,
        operator: form.value.operator,
        value: form.value.value,
      },
      assign_type: form.value.assign_type,
      target_id: form.value.target_id || null,
      priority: Number(form.value.priority) || 0,
      is_active: form.value.is_active,
    }
    if (editingId.value) {
      await crmApi.updateAssignmentRule(editingId.value, payload)
      ElMessage.success('规则已更新')
    } else {
      await crmApi.createAssignmentRule(payload)
      ElMessage.success('规则已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除规则「${row.name}」？`, '确认', { type: 'warning' })
    await crmApi.deleteAssignmentRule(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function toggleActive(row) {
  try {
    await crmApi.updateAssignmentRule(row.id, { is_active: !row.is_active })
    await load()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}

onMounted(async () => {
  await loadMembers()
  await load()
})
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="header">
      <div>
        <h2 class="title">线索分配规则</h2>
        <p class="desc">新建线索时按优先级匹配条件，自动指派负责人</p>
      </div>
      <el-button type="primary" @click="openCreate">新建规则</el-button>
    </div>

    <el-table :data="rules" stripe>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="条件" min-width="180">
        <template #default="{ row }">{{ conditionText(row) }}</template>
      </el-table-column>
      <el-table-column label="指派方式" width="110">
        <template #default="{ row }">{{ ASSIGN_LABELS[row.assign_type] || row.assign_type }}</template>
      </el-table-column>
      <el-table-column label="目标用户" width="120">
        <template #default="{ row }">{{ memberName(row.target_id) }}</template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="80" align="right" />
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active" @change="toggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑分配规则' : '新建分配规则'"
      width="520px"
      destroy-on-close
    >
      <el-form label-width="96px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item label="条件字段">
          <el-select v-model="form.field" style="width: 100%">
            <el-option value="source" label="来源 source" />
            <el-option value="company_name" label="公司名" />
            <el-option value="lead_score" label="线索评分" />
            <el-option value="status" label="状态" />
          </el-select>
        </el-form-item>
        <el-form-item label="运算符">
          <el-select v-model="form.operator" style="width: 100%">
            <el-option value="contains" label="包含" />
            <el-option value="equals" label="等于" />
            <el-option value="gt" label="大于" />
            <el-option value="lt" label="小于" />
            <el-option value="gte" label="大于等于" />
            <el-option value="lte" label="小于等于" />
          </el-select>
        </el-form-item>
        <el-form-item label="条件值">
          <el-input v-model="form.value" placeholder="空字符串 + 包含 ≈ 全匹配" />
        </el-form-item>
        <el-form-item label="指派方式">
          <el-select v-model="form.assign_type" style="width: 100%">
            <el-option value="fixed_user" label="指定用户" />
            <el-option value="round_robin" label="轮询" />
            <el-option value="load_balanced" label="负载均衡" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.assign_type === 'fixed_user'" label="指派用户" required>
          <el-select v-model="form.target_id" filterable clearable style="width: 100%" placeholder="选择成员">
            <el-option
              v-for="m in members"
              :key="m.user_id"
              :label="m.display_name || m.phone"
              :value="m.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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
</style>
