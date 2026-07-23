<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'

const loading = ref(false)
const saving = ref(false)
const rules = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)

const form = ref({
  name: '',
  field: 'source',
  operator: 'contains',
  value: '',
  score_value: 10,
  priority: 0,
  is_active: true,
})

function resetForm() {
  editingId.value = null
  form.value = {
    name: '',
    field: 'source',
    operator: 'contains',
    value: '',
    score_value: 10,
    priority: 0,
    is_active: true,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listLeadScoringRules()
    rules.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e.message || '加载评分规则失败')
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
  let value = cond.value ?? ''
  if (Array.isArray(value)) value = value.join(',')
  form.value = {
    name: row.name,
    field: cond.field || 'source',
    operator: cond.operator || cond.op || 'contains',
    value: value === null || value === undefined ? '' : String(value),
    score_value: row.score_value ?? 0,
    priority: row.priority ?? 0,
    is_active: row.is_active !== false,
  }
  dialogVisible.value = true
}

function conditionText(row) {
  const c = row.condition_json || {}
  if (!c.field) return '—'
  const v = Array.isArray(c.value) ? c.value.join(',') : (c.value ?? '')
  return `${c.field} ${c.operator || c.op || ''} ${v}`
}

function parseConditionValue(operator, raw) {
  const text = String(raw ?? '').trim()
  if (operator === 'in') {
    return text
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  if (['gt', 'lt', 'gte', 'lte'].includes(operator) && text !== '' && !Number.isNaN(Number(text))) {
    return Number(text)
  }
  return text
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  if (form.value.score_value === null || form.value.score_value === undefined) {
    ElMessage.warning('请填写分值')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      condition_json: {
        field: form.value.field,
        operator: form.value.operator,
        value: parseConditionValue(form.value.operator, form.value.value),
      },
      score_value: Number(form.value.score_value),
      priority: Number(form.value.priority) || 0,
      is_active: form.value.is_active,
    }
    if (editingId.value) {
      await crmApi.updateLeadScoringRule(editingId.value, payload)
      ElMessage.success('规则已更新')
    } else {
      await crmApi.createLeadScoringRule(payload)
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
    await crmApi.deleteLeadScoringRule(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function toggleActive(row) {
  try {
    await crmApi.updateLeadScoringRule(row.id, { is_active: !row.is_active })
    await load()
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="header">
      <div>
        <h2 class="title">线索评分规则</h2>
        <p class="desc">
          启用规则按优先级匹配累加分值（0–100）。线索详情「重算评分」按此结果覆盖；BANT 评估仅在更高时抬升分数。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新建规则</el-button>
    </div>

    <el-table :data="rules" stripe>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="条件" min-width="200">
        <template #default="{ row }">{{ conditionText(row) }}</template>
      </el-table-column>
      <el-table-column prop="score_value" label="分值" width="90" align="right" />
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

    <el-empty v-if="!loading && !rules.length" description="暂无规则：重算评分将得到 0 分" />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑评分规则' : '新建评分规则'"
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
            <el-option value="status" label="状态" />
            <el-option value="industry" label="行业" />
            <el-option value="title" label="职位" />
            <el-option value="department" label="部门" />
            <el-option value="country" label="国家" />
            <el-option value="source_detail" label="来源详情" />
            <el-option value="utm_source" label="utm_source" />
          </el-select>
        </el-form-item>
        <el-form-item label="运算符">
          <el-select v-model="form.operator" style="width: 100%">
            <el-option value="contains" label="包含" />
            <el-option value="equals" label="等于" />
            <el-option value="in" label="属于（逗号分隔）" />
            <el-option value="gt" label="大于" />
            <el-option value="lt" label="小于" />
            <el-option value="gte" label="大于等于" />
            <el-option value="lte" label="小于等于" />
            <el-option value="regex" label="正则" />
          </el-select>
        </el-form-item>
        <el-form-item label="条件值">
          <el-input
            v-model="form.value"
            :placeholder="form.operator === 'in' ? '如：官网,展会' : '匹配值'"
          />
        </el-form-item>
        <el-form-item label="分值" required>
          <el-input-number v-model="form.score_value" :min="-100" :max="100" />
          <span class="hint">命中后累加；可为负分</span>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="0" :max="999" />
          <span class="hint">数字越小越先匹配（均会累加）</span>
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
  gap: 12px;
}
.title {
  margin: 0;
  font-size: 20px;
}
.desc {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  max-width: 640px;
  line-height: 1.5;
}
.hint {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
