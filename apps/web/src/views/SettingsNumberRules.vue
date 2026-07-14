<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
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
const rules = ref([])

function resetLabel(v) {
  return RESET_PERIOD_OPTIONS.find((o) => o.value === v)?.label || v
}

function preview(r) {
  const date = r.date_format ? new Date().toISOString().slice(0, 10).replace(/-/g, '').slice(0, 8) : ''
  const seq = '1'.padStart(r.seq_width, '0')
  return `${r.prefix || ''}${r.date_format ? date : ''}${seq}`
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listNumberRules()
    rules.value = (data || []).map((r) => ({ ...r, _resetLabel: resetLabel(r.reset_period) }))
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
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            :loading="saving === row.entity_type"
            @click="save(row)"
          >保存</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
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
