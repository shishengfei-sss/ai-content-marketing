<script setup>
import { computed, ref } from 'vue'
import { crmApi } from '@/utils/api'
import { formatMoney } from '@/utils/crmConstants'
import { useTeamMembers } from '@/utils/useTeamMembers'

const emit = defineEmits(['go-detail'])

const loading = ref(false)
const deals = ref([])
const pipelines = ref([])
const { loadMembers, resolveMemberNameSync } = useTeamMembers()

const stages = computed(() => {
  const all = []
  for (const p of pipelines.value) {
    for (const s of p.stages || []) {
      all.push({ ...s, pipeline_name: p.name })
    }
  }
  return all.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
})

const stageDeals = computed(() => {
  const map = {}
  for (const s of stages.value) map[s.id] = []
  for (const d of deals.value) {
    if (map[d.stage_id]) map[d.stage_id].push(d)
  }
  return map
})

const stageTotals = computed(() => {
  const map = {}
  for (const s of stages.value) {
    const rows = stageDeals.value[s.id] || []
    map[s.id] = {
      count: rows.length,
      amount: rows.reduce((acc, d) => acc + Number(d.amount || 0), 0),
    }
  }
  return map
})

async function loadData() {
  loading.value = true
  try {
    await loadMembers()
    const [pipeData, dealData] = await Promise.all([
      crmApi.listPipelines(),
      crmApi.listDeals({ page: 1, page_size: 9999, status: 'open' }),
    ])
    pipelines.value = Array.isArray(pipeData) ? pipeData : []
    deals.value = (dealData?.items || []).filter((d) => d.status === 'open')
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function ownerName(id) {
  return resolveMemberNameSync(id, { empty: '—' })
}

function goDetail(deal) {
  emit('go-detail', deal)
}

defineExpose({ reload: loadData })
</script>

<template>
  <view class="kanban-wrap">
    <view v-if="loading" class="kanban-empty">看板加载中…</view>
    <view v-else-if="!stages.length" class="kanban-empty">暂无销售管道阶段</view>
    <scroll-view v-else scroll-x class="kanban-scroll" :show-scrollbar="false">
      <view class="kanban">
        <view v-for="stage in stages" :key="stage.id" class="kanban-col">
          <view class="kanban-col__head">
            <text class="kanban-col__name">{{ stage.name }}</text>
            <text class="kanban-col__sub">{{ stageTotals[stage.id]?.count || 0 }} 个 · {{ formatMoney(stageTotals[stage.id]?.amount || 0) }}</text>
          </view>
          <view class="kanban-col__body">
            <view
              v-for="deal in stageDeals[stage.id] || []"
              :key="deal.id"
              class="kanban-card"
              :class="{ 'kanban-card--overdue': deal.is_stage_overdue }"
              @tap="goDetail(deal)"
            >
              <text class="kanban-card__title">{{ deal.title }}</text>
              <text class="kanban-card__amount">{{ formatMoney(deal.amount) }}</text>
              <view class="kanban-card__foot">
                <text class="kanban-card__owner">{{ ownerName(deal.owner_user_id) }}</text>
                <text v-if="deal.is_stage_overdue" class="kanban-card__warn">超时</text>
                <text v-else-if="deal.stage_stay_days != null" class="kanban-card__days">{{ deal.stage_stay_days }}天</text>
              </view>
            </view>
            <view v-if="!(stageDeals[stage.id] || []).length" class="kanban-col__empty">暂无商机</view>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<style scoped>
.kanban-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.kanban-scroll {
  flex: 1;
  min-height: 0;
  white-space: nowrap;
}

.kanban {
  display: inline-flex;
  gap: 10px;
  padding: 0 2px 16px;
  min-height: 100%;
}

.kanban-col {
  display: inline-flex;
  flex-direction: column;
  width: 280px;
  vertical-align: top;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.kanban-col__head {
  padding: 12px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.kanban-col__name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.kanban-col__sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.kanban-col__body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 120px;
}

.kanban-card {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.kanban-card--overdue {
  border-color: #fecaca;
  background: #fff5f5;
}

.kanban-card__title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.4;
  white-space: normal;
}

.kanban-card__amount {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  color: #1677ff;
  font-weight: 600;
}

.kanban-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  gap: 6px;
}

.kanban-card__owner {
  font-size: 12px;
  color: #64748b;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kanban-card__days,
.kanban-card__warn {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 999px;
}

.kanban-card__days {
  background: #f1f5f9;
  color: #64748b;
}

.kanban-card__warn {
  background: #fee2e2;
  color: #dc2626;
}

.kanban-col__empty,
.kanban-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px 12px;
}
</style>
