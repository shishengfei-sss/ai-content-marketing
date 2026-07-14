<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'

const loading = ref(false)
const pipelines = ref([])

const pipelineDialogVisible = ref(false)
const pipelineForm = ref(emptyPipeline())
const pipelineEditMode = ref('create')

const stageDialogVisible = ref(false)
const stageForm = ref(emptyStage())
const stageEditMode = ref('create')
const stagePipelineId = ref('')

function emptyPipeline() {
  return { id: '', name: '', is_default: false, is_active: true }
}
function emptyStage() {
  return { id: '', name: '', probability: 0, color: '#409EFF', sort_order: 0, is_closed_stage: false, is_won_stage: false, max_stay_days: null }
}

async function loadPipelines() {
  loading.value = true
  try {
    const { data } = await crmApi.listPipelines()
    pipelines.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(e.message || '加载管道失败')
  } finally {
    loading.value = false
  }
}

function openCreatePipeline() {
  pipelineEditMode.value = 'create'
  pipelineForm.value = emptyPipeline()
  pipelineDialogVisible.value = true
}

function openEditPipeline(p) {
  pipelineEditMode.value = 'edit'
  pipelineForm.value = { id: p.id, name: p.name, is_default: p.is_default, is_active: p.is_active }
  pipelineDialogVisible.value = true
}

async function submitPipeline() {
  if (!pipelineForm.value.name?.trim()) { ElMessage.warning('请填写管道名称'); return }
  const payload = {
    name: pipelineForm.value.name.trim(),
    is_default: pipelineForm.value.is_default,
    is_active: pipelineForm.value.is_active,
  }
  try {
    if (pipelineEditMode.value === 'edit') {
      await crmApi.updatePipeline(pipelineForm.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createPipeline(payload)
      ElMessage.success('已创建')
    }
    pipelineDialogVisible.value = false
    await loadPipelines()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function deletePipeline(p) {
  try {
    await ElMessageBox.confirm(`确定删除管道「${p.name}」？仅删除未被使用的管道`, '删除')
    await crmApi.deletePipeline(p.id)
    ElMessage.success('已删除')
    await loadPipelines()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function openCreateStage(pipelineId) {
  stageEditMode.value = 'create'
  stagePipelineId.value = pipelineId
  const p = pipelines.value.find((x) => String(x.id) === String(pipelineId))
  const nextOrder = (p?.stages || []).length
  stageForm.value = emptyStage()
  stageForm.value.sort_order = nextOrder
  stageDialogVisible.value = true
}

function openEditStage(pipelineId, stage) {
  stageEditMode.value = 'edit'
  stagePipelineId.value = pipelineId
  stageForm.value = {
    id: stage.id,
    name: stage.name,
    probability: stage.probability ?? 0,
    color: stage.color || '#409EFF',
    sort_order: stage.sort_order ?? 0,
    is_closed_stage: !!stage.is_closed_stage,
    is_won_stage: !!stage.is_won_stage,
    max_stay_days: stage.max_stay_days ?? null,
  }
  stageDialogVisible.value = true
}

async function submitStage() {
  if (!stageForm.value.name?.trim()) { ElMessage.warning('请填写阶段名称'); return }
  const payload = {
    name: stageForm.value.name.trim(),
    probability: Number(stageForm.value.probability) || 0,
    color: stageForm.value.color,
    sort_order: Number(stageForm.value.sort_order) || 0,
    is_closed_stage: stageForm.value.is_closed_stage,
    is_won_stage: stageForm.value.is_won_stage,
    max_stay_days: stageForm.value.max_stay_days || null,
  }
  try {
    if (stageEditMode.value === 'edit') {
      await crmApi.updatePipelineStage(stagePipelineId.value, stageForm.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createPipelineStage(stagePipelineId.value, payload)
      ElMessage.success('已创建')
    }
    stageDialogVisible.value = false
    await loadPipelines()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function deleteStage(pipelineId, stage) {
  try {
    await ElMessageBox.confirm(`确定删除阶段「${stage.name}」？仅删除未被使用的阶段`, '删除')
    await crmApi.deletePipelineStage(pipelineId, stage.id)
    ElMessage.success('已删除')
    await loadPipelines()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function moveStage(pipelineId, stage, direction) {
  const p = pipelines.value.find((x) => String(x.id) === String(pipelineId))
  if (!p) return
  const stages = [...(p.stages || [])].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  const idx = stages.findIndex((s) => String(s.id) === String(stage.id))
  if (idx < 0) return
  const targetIdx = idx + direction
  if (targetIdx < 0 || targetIdx >= stages.length) return
  const current = stages[idx]
  const target = stages[targetIdx]
  const curOrder = current.sort_order ?? idx
  const tgtOrder = target.sort_order ?? targetIdx
  try {
    await Promise.all([
      crmApi.updatePipelineStage(pipelineId, current.id, { sort_order: tgtOrder }),
      crmApi.updatePipelineStage(pipelineId, target.id, { sort_order: curOrder }),
    ])
    await loadPipelines()
  } catch (e) {
    ElMessage.error(e.message || '调整顺序失败')
  }
}

const sortedStages = (p) => [...(p.stages || [])].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))

onMounted(() => { loadPipelines() })
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="pipeline-header">
      <div>
        <h2 class="pipeline-header__title">销售管道</h2>
        <p class="pipeline-header__desc">配置商机阶段、成交概率与颜色，用于看板视图与销售漏斗。</p>
      </div>
      <el-button type="primary" @click="openCreatePipeline">新建管道</el-button>
    </div>

    <div v-if="!pipelines.length && !loading" class="pipeline-empty">
      <el-empty description="尚未配置销售管道" />
    </div>

    <div v-else class="pipeline-list">
      <el-card v-for="p in pipelines" :key="p.id" class="pipeline-card" shadow="never">
        <template #header>
          <div class="pipeline-card__head">
            <div class="pipeline-card__title">
              <span class="pipeline-card__name">{{ p.name }}</span>
              <el-tag v-if="p.is_default" type="success" size="small">默认</el-tag>
              <el-tag v-if="!p.is_active" type="info" size="small">已停用</el-tag>
            </div>
            <div class="pipeline-card__actions">
              <el-button link type="primary" @click="openCreateStage(p.id)">添加阶段</el-button>
              <el-button link @click="openEditPipeline(p)">编辑管道</el-button>
              <el-button link type="danger" @click="deletePipeline(p)">删除</el-button>
            </div>
          </div>
        </template>

        <el-table :data="sortedStages(p)" border size="small">
          <el-table-column label="顺序" width="80" align="center">
            <template #default="{ row, $index }">
              <div class="pipeline-stage-order">
                <el-button
                  link
                  size="small"
                  :disabled="$index === 0"
                  @click="moveStage(p.id, row, -1)"
                >↑</el-button>
                <span>{{ $index + 1 }}</span>
                <el-button
                  link
                  size="small"
                  :disabled="$index === sortedStages(p).length - 1"
                  @click="moveStage(p.id, row, 1)"
                >↓</el-button>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="阶段" min-width="160">
            <template #default="{ row }">
              <span class="pipeline-stage-dot" :style="{ background: row.color || '#909399' }" />
              {{ row.name }}
            </template>
          </el-table-column>
          <el-table-column label="成交概率" width="120" align="center">
            <template #default="{ row }">{{ row.probability ?? 0 }}%</template>
          </el-table-column>
          <el-table-column label="停留上限" width="100" align="center">
            <template #default="{ row }">{{ row.max_stay_days ? `${row.max_stay_days}天` : '-' }}</template>
          </el-table-column>
          <el-table-column label="类型" width="160" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_won_stage" type="success" size="small">赢单阶段</el-tag>
              <el-tag v-else-if="row.is_closed_stage" type="info" size="small">结束阶段</el-tag>
              <span v-else class="pipeline-stage-type">进行中</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditStage(p.id, row)">编辑</el-button>
              <el-button link type="danger" @click="deleteStage(p.id, row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-dialog v-model="pipelineDialogVisible" :title="pipelineEditMode === 'edit' ? '编辑管道' : '新建管道'" width="460px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="pipelineForm.name" maxlength="100" />
        </el-form-item>
        <el-form-item label="默认">
          <el-switch v-model="pipelineForm.is_default" />
          <span class="pipeline-tip">设为默认后，新建商机将自动选用该管道</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="pipelineForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pipelineDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPipeline">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="stageDialogVisible" :title="stageEditMode === 'edit' ? '编辑阶段' : '新建阶段'" width="460px">
      <el-form label-width="88px">
        <el-form-item label="阶段名称" required>
          <el-input v-model="stageForm.name" maxlength="50" />
        </el-form-item>
        <el-form-item label="成交概率">
          <el-input-number v-model="stageForm.probability" :min="0" :max="100" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="stageForm.color" />
        </el-form-item>
        <el-form-item label="顺序">
          <el-input-number v-model="stageForm.sort_order" :min="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="赢单阶段">
          <el-switch v-model="stageForm.is_won_stage" />
          <span class="pipeline-tip">进入此阶段即视为赢单</span>
        </el-form-item>
        <el-form-item label="结束阶段">
          <el-switch v-model="stageForm.is_closed_stage" />
          <span class="pipeline-tip">结束阶段不再统计为进行中商机</span>
        </el-form-item>
        <el-form-item label="停留上限">
          <el-input-number v-model="stageForm.max_stay_days" :min="1" :controls="false" placeholder="天数" style="width: 100%" />
          <span class="pipeline-tip">超过天数在看板标红预警（留空不限制）</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stageDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStage">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pipeline-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.pipeline-header__title { margin: 0 0 4px 0; font-size: 18px; font-weight: 600; }
.pipeline-header__desc { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.pipeline-empty { padding: 40px 0; }
.pipeline-list { display: flex; flex-direction: column; gap: 16px; }
.pipeline-card { margin-bottom: 0; }
.pipeline-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pipeline-card__title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.pipeline-card__actions { display: flex; gap: 4px; }
.pipeline-stage-order {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.pipeline-stage-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}
.pipeline-stage-type { color: var(--el-text-color-secondary); font-size: 12px; }
.pipeline-tip {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
