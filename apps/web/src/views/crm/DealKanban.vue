<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import { useTeamMembers } from '../../composables/useTeamMembers'

const props = defineProps({
  pipelines: { type: Array, default: () => [] },
  stageFilter: { type: String, default: '' },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['changed', 'go-detail'])
const { resolveMemberName, loadMembers } = useTeamMembers()

const loading = ref(false)
const deals = ref([])
const dragDealId = ref('')
const dragFromStageId = ref('')

const stages = computed(() => {
  const all = []
  for (const p of props.pipelines) {
    for (const s of p.stages || []) {
      all.push({ ...s, pipeline_name: p.name })
    }
  }
  if (props.stageFilter) return all.filter((s) => s.id === props.stageFilter)
  return all
})

const stageDeals = computed(() => {
  const m = {}
  for (const s of stages.value) m[s.id] = []
  for (const d of deals.value) {
    if (m[d.stage_id]) m[d.stage_id].push(d)
  }
  return m
})

const totalAmountByStage = computed(() => {
  const m = {}
  for (const s of stages.value) {
    m[s.id] = (stageDeals.value[s.id] || []).reduce((acc, d) => acc + Number(d.amount || 0), 0)
  }
  return m
})

const totalCountByStage = computed(() => {
  const m = {}
  for (const s of stages.value) m[s.id] = (stageDeals.value[s.id] || []).length
  return m
})

async function loadDeals() {
  loading.value = true
  try {
    const params = { page: 1, page_size: 9999 }
    const { data } = await crmApi.listDeals(params)
    deals.value = (data.items || []).filter((d) => d.status === 'open' || d.status === 'in_progress')
  } catch (e) {
    ElMessage.error(e.message || '加载商机失败')
  } finally {
    loading.value = false
  }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function onDragStart(e, deal, stageId) {
  if (!props.canEdit) { e.preventDefault(); return }
  dragDealId.value = deal.id
  dragFromStageId.value = stageId
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', deal.id)
}

function onDragOver(e) {
  if (!props.canEdit) return
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
}

async function onDrop(e, targetStageId) {
  e.preventDefault()
  const dealId = dragDealId.value || e.dataTransfer.getData('text/plain')
  dragDealId.value = ''
  dragFromStageId.value = ''
  if (!dealId) return
  if (!props.canEdit) { ElMessage.warning('无编辑权限'); return }
  const deal = deals.value.find((d) => String(d.id) === String(dealId))
  if (!deal) return
  if (String(deal.stage_id) === String(targetStageId)) return
  try {
    await crmApi.changeDealStage(deal.id, { stage_id: targetStageId })
    deal.stage_id = targetStageId
    ElMessage.success('已移动')
    emit('changed')
  } catch (e2) {
    ElMessage.error(e2.message || '移动失败')
  }
}

function onDragEnd() {
  dragDealId.value = ''
  dragFromStageId.value = ''
}

function goDetail(deal) {
  emit('go-detail', deal)
}

function statusTagType(status) {
  if (status === 'won') return 'success'
  if (status === 'lost') return 'danger'
  if (status === 'abandoned') return 'info'
  return ''
}

function priorityTagType(v) {
  return ({ high: 'danger', medium: 'warning', low: 'info' })[v] || ''
}
function priorityLabel(v) {
  return ({ high: '高', medium: '中', low: '低' })[v] || ''
}
function ownerInitial(name) {
  if (!name) return '?'
  return String(name).trim().slice(0, 1)
}
function stayDays(deal) {
  if (deal.stage_stay_days != null) return deal.stage_stay_days
  const createdAt = deal.created_at
  if (!createdAt) return ''
  const d = new Date(createdAt)
  if (Number.isNaN(d.getTime())) return ''
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86400000))
}
function isOverdue(deal, stage) {
  if (deal.is_stage_overdue) return true
  const max = stage?.max_stay_days || deal.stage_max_stay_days
  const stay = stayDays(deal)
  return max && stay !== '' && stay >= max
}
function isNearTimeout(deal, stage) {
  const max = stage?.max_stay_days || deal.stage_max_stay_days
  const stay = stayDays(deal)
  if (!max || stay === '') return false
  return stay >= max - 2 && stay < max
}

onMounted(() => { loadMembers(); loadDeals() })
watch(() => props.pipelines, () => { /* stage 数据已通过 prop 提供 */ })
watch(() => props.stageFilter, () => { /* 仅过滤列 */ })

defineExpose({ reload: loadDeals })
</script>

<template>
  <div v-loading="loading" class="deal-kanban">
    <div v-if="!stages.length" class="deal-kanban__empty">
      <el-empty description="未配置销售管道阶段" />
    </div>
    <div v-else class="deal-kanban__board">
      <div
        v-for="stage in stages"
        :key="stage.id"
        class="deal-kanban__column"
        @dragover="onDragOver"
        @drop="onDrop($event, stage.id)"
      >
        <div class="deal-kanban__column-head">
          <div class="deal-kanban__column-title">
            <span class="deal-kanban__dot" :style="{ background: stage.color || '#909399' }" />
            {{ stage.name }}
            <span class="deal-kanban__count">{{ totalCountByStage[stage.id] || 0 }}</span>
          </div>
          <div class="deal-kanban__amount">¥{{ formatAmount(totalAmountByStage[stage.id]) }}</div>
        </div>
        <div class="deal-kanban__cards">
          <div
            v-for="deal in stageDeals[stage.id] || []"
            :key="deal.id"
            class="deal-kanban__card"
            :class="{ 'deal-kanban__card--overdue': isOverdue(deal, stage), 'deal-kanban__card--warn': isNearTimeout(deal, stage) }"
            :draggable="canEdit"
            @dragstart="onDragStart($event, deal, stage.id)"
            @dragend="onDragEnd"
            @click="goDetail(deal)"
          >
            <div class="deal-kanban__card-title">{{ deal.title }}</div>
            <div class="deal-kanban__card-amount">¥{{ formatAmount(deal.amount) }}</div>
            <div class="deal-kanban__card-meta">
              <el-tag v-if="deal.priority" size="small" :type="priorityTagType(deal.priority)">{{ priorityLabel(deal.priority) }}</el-tag>
              <el-tag size="small" :type="statusTagType(deal.status)">{{ deal.status }}</el-tag>
              <span v-if="stayDays(deal) !== ''" class="deal-kanban__stay" :class="{ 'deal-kanban__stay--overdue': isOverdue(deal, stage) }">
                {{ stayDays(deal) }}天
              </span>
            </div>
            <div class="deal-kanban__card-owner">
              <span class="deal-kanban__avatar">{{ ownerInitial(resolveMemberName(deal.owner_user_id)) }}</span>
              <span class="deal-kanban__owner-name">{{ resolveMemberName(deal.owner_user_id) }}</span>
              <span v-if="deal.expected_close_date" class="deal-kanban__date">{{ deal.expected_close_date }}</span>
            </div>
          </div>
          <div v-if="!(stageDeals[stage.id] || []).length" class="deal-kanban__empty-col">
            暂无商机
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.deal-kanban { padding: 4px 0; }
.deal-kanban__empty { padding: 60px 0; }
.deal-kanban__board {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
}
.deal-kanban__column {
  flex: 0 0 260px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 8px;
  padding: 10px;
  min-height: 320px;
  display: flex;
  flex-direction: column;
}
.deal-kanban__column-head {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #e4e7ed);
}
.deal-kanban__column-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
}
.deal-kanban__dot {
  width: 10px; height: 10px; border-radius: 50%;
  display: inline-block;
}
.deal-kanban__count {
  background: var(--el-color-info-light-7, #e6e8eb);
  color: var(--el-text-color-secondary, #909399);
  border-radius: 10px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 400;
}
.deal-kanban__amount {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.deal-kanban__cards {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.deal-kanban__card {
  background: var(--el-bg-color, #fff);
  border-radius: 6px;
  padding: 10px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  cursor: grab;
  transition: box-shadow 0.2s;
}
.deal-kanban__card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
.deal-kanban__card--warn { border-left: 3px solid var(--el-color-warning); }
.deal-kanban__card--overdue { border-left: 3px solid var(--el-color-danger); background: var(--el-color-danger-light-9); }
.deal-kanban__card:active { cursor: grabbing; }
.deal-kanban__card-title {
  font-weight: 500;
  font-size: 13px;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.deal-kanban__card-amount {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-color-primary, #409eff);
  margin-bottom: 6px;
}
.deal-kanban__card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.deal-kanban__date { font-size: 12px; }
.deal-kanban__stay {
  font-size: 12px;
  color: var(--el-color-warning, #e6a23c);
}
.deal-kanban__stay--overdue { color: var(--el-color-danger); font-weight: 600; }
.deal-kanban__card-owner {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.deal-kanban__avatar {
  width: 20px; height: 20px;
  border-radius: 50%;
  background: var(--el-color-primary-light-7, #d9e7ff);
  color: var(--el-color-primary, #409eff);
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.deal-kanban__owner-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.deal-kanban__empty-col {
  text-align: center;
  color: var(--el-text-color-placeholder, #c0c4cc);
  font-size: 12px;
  padding: 16px 0;
}
</style>
