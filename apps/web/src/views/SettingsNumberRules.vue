<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'

const ENTITY_LABELS = {
  lead: '线索',
  customer: '客户',
  task: '任务',
  campaign: '活动',
  deal: '商机',
  quote: '报价单',
  contract: '合同',
  order: '订单',
  payment: '回款单',
  product: '产品',
}

const RESET_PERIOD_OPTIONS = [
  { value: 'once', label: '永不重置' },
  { value: 'daily', label: '每日' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
  { value: 'yearly', label: '每年' },
]

const DATE_FORMAT_OPTIONS = [
  { value: '%Y%m%d', label: '年月日 (20260713)', sample: '20260713' },
  { value: '%Y%m', label: '年月 (202607)', sample: '202607' },
  { value: '%Y', label: '年 (2026)', sample: '2026' },
  { value: '', label: '不含日期', sample: '' },
]

const loading = ref(false)
const saving = ref('')
const deleting = ref('')
const rules = ref([])
const createVisible = ref(false)
const creating = ref(false)
const createForm = ref({
  entity_type: '',
  prefix: '',
  suffix: '',
  date_format: '%Y%m%d',
  seq_width: 3,
  reset_period: 'daily',
  enabled: true,
})

const existingTypes = computed(() => new Set(rules.value.map((r) => r.entity_type)))
const availableEntityTypes = computed(() =>
  Object.keys(ENTITY_LABELS).filter((k) => !existingTypes.value.has(k)),
)

function resetLabel(v) {
  return RESET_PERIOD_OPTIONS.find((o) => o.value === v)?.label || v
}

function preview(r) {
  const date = r.date_format ? new Date().toISOString().slice(0, 10).replace(/-/g, '').slice(0, 8) : ''
  const seq = '1'.padStart(r.seq_width, '0')
  return `${r.prefix || ''}${r.date_format ? date : ''}${seq}${r.suffix || ''}`
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listNumberRules()
    rules.value = (data || []).map((r) => ({
      ...r,
      suffix: r.suffix || '',
      _resetLabel: resetLabel(r.reset_period),
    }))
  } catch (e) {
    ElMessage.error(e.message || '加载编号规则失败')
  } finally {
    loading.value = false
  }
}

async function save(r) {
  saving.value = r.entity_type
  try {
    const payload = {
      prefix: r.prefix,
      suffix: r.suffix || '',
      date_format: r.date_format,
      seq_width: r.seq_width,
      reset_period: r.reset_period,
      enabled: r.enabled,
    }
    await crmApi.updateNumberRule(r.entity_type, payload)
    ElMessage.success(`${ENTITY_LABELS[r.entity_type] || r.entity_type} 编号规则已保存`)
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = ''
  }
}

async function removeRule(r) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${ENTITY_LABELS[r.entity_type] || r.entity_type}」编号规则？`,
      '删除',
      { type: 'warning' },
    )
    deleting.value = r.entity_type
    await crmApi.deleteNumberRule(r.entity_type)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  } finally {
    deleting.value = ''
  }
}

function openCreate() {
  if (!availableEntityTypes.value.length) {
    ElMessage.warning('所有实体类型均已配置编号规则')
    return
  }
  createForm.value = {
    entity_type: availableEntityTypes.value[0],
    prefix: '',
    suffix: '',
    date_format: '%Y%m%d',
    seq_width: 3,
    reset_period: 'daily',
    enabled: true,
  }
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.value.entity_type) {
    ElMessage.warning('请选择实体类型')
    return
  }
  creating.value = true
  try {
    await crmApi.createNumberRule({
      entity_type: createForm.value.entity_type,
      prefix: createForm.value.prefix || '',
      suffix: createForm.value.suffix || '',
      date_format: createForm.value.date_format,
      seq_width: createForm.value.seq_width,
      reset_period: createForm.value.reset_period,
      enabled: createForm.value.enabled,
    })
    ElMessage.success('规则已创建')
    createVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(() => { load() })
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="pipeline-header">
      <div>
        <h2 class="pipeline-header__title">编号规则</h2>
        <p class="pipeline-header__desc">
          为线索、客户、商机、合同、订单等配置自动编号规则，编号在租户内唯一。修改后仅对新增记录生效。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新增规则</el-button>
    </div>

    <el-table :data="rules" border size="small" class="number-rules-table">
      <el-table-column label="实体" width="110">
        <template #default="{ row }">
          <span class="number-rules-entity">{{ ENTITY_LABELS[row.entity_type] || row.entity_type }}</span>
        </template>
      </el-table-column>
      <el-table-column label="前缀" width="120">
        <template #default="{ row }">
          <el-input v-model="row.prefix" size="small" maxlength="10" placeholder="如 XS" />
        </template>
      </el-table-column>
      <el-table-column label="后缀" width="120">
        <template #default="{ row }">
          <el-input v-model="row.suffix" size="small" maxlength="10" placeholder="可选" />
        </template>
      </el-table-column>
      <el-table-column label="日期格式" width="180">
        <template #default="{ row }">
          <el-select v-model="row.date_format" size="small">
            <el-option
              v-for="o in DATE_FORMAT_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="序列宽度" width="110" align="center">
        <template #default="{ row }">
          <el-input-number
            v-model="row.seq_width"
            size="small"
            :min="1"
            :max="8"
            controls-position="right"
            style="width: 88px"
          />
        </template>
      </el-table-column>
      <el-table-column label="重置周期" width="140">
        <template #default="{ row }">
          <el-select v-model="row.reset_period" size="small">
            <el-option
              v-for="o in RESET_PERIOD_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" />
        </template>
      </el-table-column>
      <el-table-column label="预览" min-width="160">
        <template #default="{ row }">
          <span class="number-rules-preview">{{ preview(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            :loading="saving === row.entity_type"
            @click="save(row)"
          >保存</el-button>
          <el-button
            type="danger"
            size="small"
            link
            :loading="deleting === row.entity_type"
            @click="removeRule(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" title="新增编号规则" width="480px" destroy-on-close>
      <el-form label-width="88px">
        <el-form-item label="实体类型" required>
          <el-select v-model="createForm.entity_type" style="width: 100%">
            <el-option
              v-for="k in availableEntityTypes"
              :key="k"
              :label="ENTITY_LABELS[k]"
              :value="k"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="前缀">
          <el-input v-model="createForm.prefix" maxlength="10" placeholder="如 XS" />
        </el-form-item>
        <el-form-item label="后缀">
          <el-input v-model="createForm.suffix" maxlength="10" placeholder="可选" />
        </el-form-item>
        <el-form-item label="日期格式">
          <el-select v-model="createForm.date_format" style="width: 100%">
            <el-option
              v-for="o in DATE_FORMAT_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="序列宽度">
          <el-input-number v-model="createForm.seq_width" :min="1" :max="8" />
        </el-form-item>
        <el-form-item label="重置周期">
          <el-select v-model="createForm.reset_period" style="width: 100%">
            <el-option
              v-for="o in RESET_PERIOD_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="createForm.enabled" />
        </el-form-item>
        <el-form-item label="预览">
          <span class="number-rules-preview">{{ preview(createForm) }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pipeline-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.pipeline-header__title { margin: 0 0 4px 0; font-size: 18px; font-weight: 600; }
.pipeline-header__desc { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.number-rules-table {
  margin-top: 12px;
}
.number-rules-entity {
  font-weight: 600;
}
.number-rules-preview {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  color: #409eff;
  letter-spacing: 0.5px;
}
</style>
