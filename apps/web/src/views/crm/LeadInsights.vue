<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'

const loading = ref(false)
const activeTab = ref('funnel')
const funnel = ref(null)
const roiItems = ref([])
const lifecycle = ref(null)
const nurtureRules = ref([])
const running = ref(false)
const ruleForm = ref({
  name: '',
  field: 'lead_score',
  operator: 'lt',
  value: 40,
  action_type: 'create_task',
})

const funnelStages = computed(() => funnel.value?.stages || [])
const lifecycleBuckets = computed(() => {
  const b = lifecycle.value?.buckets || {}
  return Object.entries(b).map(([label, count]) => ({ label, count }))
})

async function loadFunnel() {
  const { data } = await crmApi.leadFunnel()
  funnel.value = data
}

async function loadRoi() {
  const { data } = await crmApi.sourceRoi()
  roiItems.value = Array.isArray(data?.items) ? data.items : []
}

async function loadLifecycle() {
  const { data } = await crmApi.lifecycleReport()
  lifecycle.value = data
}

async function loadNurture() {
  const { data } = await crmApi.listNurtureRules()
  nurtureRules.value = Array.isArray(data) ? data : []
}

async function loadActive() {
  loading.value = true
  try {
    if (activeTab.value === 'funnel') await loadFunnel()
    else if (activeTab.value === 'roi') await loadRoi()
    else if (activeTab.value === 'lifecycle') await loadLifecycle()
    else await loadNurture()
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function createRule() {
  if (!ruleForm.value.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  try {
    const raw = ruleForm.value.value
    const value =
      ruleForm.value.field === 'lead_score' || ['gt', 'lt', 'gte', 'lte'].includes(ruleForm.value.operator)
        ? Number(raw)
        : raw
    await crmApi.createNurtureRule({
      name: ruleForm.value.name.trim(),
      condition_json: {
        field: ruleForm.value.field,
        operator: ruleForm.value.operator,
        value,
      },
      action_type: ruleForm.value.action_type,
      action_config: { title: `培育跟进：${ruleForm.value.name.trim()}` },
      is_active: true,
    })
    ElMessage.success('已创建培育规则')
    ruleForm.value.name = ''
    await loadNurture()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  }
}

async function removeRule(id) {
  try {
    await crmApi.deleteNurtureRule(id)
    ElMessage.success('已删除')
    await loadNurture()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function runRules() {
  running.value = true
  try {
    const { data } = await crmApi.runNurtureRules({ limit: 200 })
    ElMessage.success(`扫描 ${data.leads_scanned}，命中 ${data.matched}，动作 ${data.actions}`)
  } catch (e) {
    ElMessage.error(e.message || '执行失败')
  } finally {
    running.value = false
  }
}

onMounted(loadActive)
</script>

<template>
  <div v-loading="loading" class="page-card lead-insights">
    <div class="lead-insights__header">
      <div>
        <h2 class="lead-insights__title">线索洞察</h2>
        <p class="lead-insights__desc">全链路漏斗、来源 ROI、客户生命周期与培育规则</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-change="loadActive">
      <el-tab-pane label="线索漏斗" name="funnel" />
      <el-tab-pane label="来源 ROI" name="roi" />
      <el-tab-pane label="生命周期" name="lifecycle" />
      <el-tab-pane label="培育规则" name="nurture" />
    </el-tabs>

    <template v-if="activeTab === 'funnel'">
      <div class="metrics">
        <div v-for="s in funnelStages" :key="s.key" class="metric">
          <div class="metric__label">{{ s.label }}</div>
          <div class="metric__value">{{ s.count }}</div>
        </div>
      </div>
      <p v-if="funnel" class="hint">线索→客户转化率 {{ funnel.lead_to_customer_rate }}%</p>
      <el-table :data="funnel?.by_source || []" border size="small">
        <el-table-column prop="source" label="来源" min-width="120" />
        <el-table-column prop="leads" label="线索数" width="100" align="right" />
        <el-table-column prop="converted" label="已转化" width="100" align="right" />
        <el-table-column label="转化率" width="100" align="right">
          <template #default="{ row }">{{ row.conversion_rate }}%</template>
        </el-table-column>
      </el-table>
    </template>

    <template v-else-if="activeTab === 'roi'">
      <el-table :data="roiItems" border size="small">
        <el-table-column prop="source" label="来源" min-width="120" />
        <el-table-column prop="leads" label="线索" width="90" align="right" />
        <el-table-column prop="converted" label="转化" width="90" align="right" />
        <el-table-column label="转化率" width="90" align="right">
          <template #default="{ row }">{{ row.conversion_rate }}%</template>
        </el-table-column>
        <el-table-column label="平均周期(天)" width="120" align="right">
          <template #default="{ row }">{{ row.avg_cycle_days ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="总成本" width="100" align="right">
          <template #default="{ row }">{{ row.total_cost }}</template>
        </el-table-column>
        <el-table-column label="CPL" width="90" align="right">
          <template #default="{ row }">{{ row.cpl ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="CPA" width="90" align="right">
          <template #default="{ row }">{{ row.cpa ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="Campaigns" min-width="140">
          <template #default="{ row }">{{ (row.utm_campaigns || []).join(', ') || '—' }}</template>
        </el-table-column>
      </el-table>
    </template>

    <template v-else-if="activeTab === 'lifecycle'">
      <div class="metrics">
        <div v-for="item in lifecycleBuckets" :key="item.label" class="metric">
          <div class="metric__label">{{ item.label }}</div>
          <div class="metric__value">{{ item.count }}</div>
        </div>
      </div>
      <p v-if="lifecycle" class="hint">统计日期 {{ lifecycle.as_of }} · 客户总数 {{ lifecycle.total }}</p>
    </template>

    <template v-else>
      <div class="nurture-head">
        <el-button type="primary" :loading="running" @click="runRules">立即执行培育</el-button>
      </div>
      <el-form inline class="nurture-form">
        <el-form-item label="名称">
          <el-input v-model="ruleForm.name" placeholder="低分培育" style="width: 140px" />
        </el-form-item>
        <el-form-item label="条件">
          <el-select v-model="ruleForm.field" style="width: 120px">
            <el-option label="线索评分" value="lead_score" />
            <el-option label="来源" value="source" />
          </el-select>
          <el-select v-model="ruleForm.operator" style="width: 90px; margin-left: 8px">
            <el-option label="<" value="lt" />
            <el-option label="<=" value="lte" />
            <el-option label="=" value="equals" />
            <el-option label="包含" value="contains" />
          </el-select>
          <el-input v-model="ruleForm.value" style="width: 90px; margin-left: 8px" />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="ruleForm.action_type" style="width: 140px">
            <el-option label="创建任务" value="create_task" />
            <el-option label="通知负责人" value="notify_owner" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" plain @click="createRule">添加规则</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="nurtureRules" border size="small">
        <el-table-column prop="name" label="规则" min-width="140" />
        <el-table-column prop="action_type" label="动作" width="120" />
        <el-table-column prop="priority" label="优先级" width="90" align="right" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">{{ row.is_active ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeRule(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<style scoped>
.lead-insights__header {
  margin-bottom: 12px;
}
.lead-insights__title {
  margin: 0;
  font-size: 18px;
}
.lead-insights__desc {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.metric {
  min-width: 120px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.metric__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.metric__value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 600;
}
.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.nurture-head {
  margin-bottom: 12px;
}
.nurture-form {
  margin-bottom: 12px;
}
</style>
