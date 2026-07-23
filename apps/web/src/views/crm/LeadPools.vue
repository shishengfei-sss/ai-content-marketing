<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../../api/client'
import { formatApiError } from '../../utils/apiError'
import { hasPermission } from '../../config/permissions'
import { useAuthStore } from '../../stores/auth'
import { formatDateTime } from '../../utils/datetime'

const router = useRouter()
const auth = useAuthStore()

const loadingPools = ref(false)
const loadingLeads = ref(false)
const claimingId = ref('')
const pools = ref([])
const activePoolId = ref('')
const leads = ref([])

const canClaim = () => hasPermission(auth.permissions, 'crm.lead.edit')
const canManagePools = () => hasPermission(auth.permissions, 'crm.lead.edit')

const activePool = computed(() => pools.value.find((p) => p.id === activePoolId.value) || null)

async function loadPools() {
  loadingPools.value = true
  try {
    const { data } = await crmApi.listLeadPools()
    pools.value = Array.isArray(data) ? data : []
    if (!pools.value.length) {
      activePoolId.value = ''
      leads.value = []
      return
    }
    if (!activePoolId.value || !pools.value.some((p) => p.id === activePoolId.value)) {
      activePoolId.value = pools.value[0].id
    }
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载公海失败'))
    pools.value = []
  } finally {
    loadingPools.value = false
  }
}

async function loadLeads() {
  if (!activePoolId.value) {
    leads.value = []
    return
  }
  loadingLeads.value = true
  try {
    const { data } = await crmApi.listLeadPoolLeads(activePoolId.value)
    leads.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载公海线索失败'))
    leads.value = []
  } finally {
    loadingLeads.value = false
  }
}

async function claim(row) {
  if (!canClaim() || !activePoolId.value) return
  try {
    await ElMessageBox.confirm(`认领线索「${row.company_name}」？认领后将归到你名下。`, '认领线索', {
      type: 'info',
      confirmButtonText: '认领',
    })
    claimingId.value = row.id
    await crmApi.claimLeadFromPool(activePoolId.value, row.id)
    ElMessage.success('已认领')
    await loadLeads()
    router.push(`/crm/leads/${row.id}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(formatApiError(e, '认领失败'))
  } finally {
    claimingId.value = ''
  }
}

function goLead(row) {
  router.push({ path: `/crm/leads/${row.id}`, query: { from: 'lead-pools' } })
}

watch(activePoolId, () => {
  loadLeads()
})

onMounted(async () => {
  await loadPools()
  await loadLeads()
})
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <h2>线索公海</h2>
        <p class="hint">查看各公海池中待认领线索；认领后进入「我的线索」跟进。</p>
      </div>
      <el-button v-if="canManagePools()" @click="router.push('/settings/lead-pools')">
        管理公海池
      </el-button>
    </div>

    <div v-loading="loadingPools">
      <el-empty v-if="!pools.length" description="暂无线索公海">
        <el-button v-if="canManagePools()" type="primary" @click="router.push('/settings/lead-pools')">
          去设置创建
        </el-button>
      </el-empty>

      <template v-else>
        <el-radio-group v-model="activePoolId" class="pool-tabs">
          <el-radio-button v-for="p in pools" :key="p.id" :value="p.id">
            {{ p.name }}
          </el-radio-button>
        </el-radio-group>

        <div v-if="activePool" class="pool-meta">
          <span v-if="activePool.industry_filter">行业：{{ activePool.industry_filter }}</span>
          <span v-if="activePool.auto_reclaim_days">自动回收：{{ activePool.auto_reclaim_days }} 天</span>
          <span>待认领 {{ leads.length }} 条</span>
        </div>

        <el-table v-loading="loadingLeads" :data="leads" border class="pool-table">
          <el-table-column prop="company_name" label="公司名称" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <el-button link type="primary" @click="goLead(row)">{{ row.company_name }}</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="contact_name" label="联系人" width="100" />
          <el-table-column label="手机" width="130">
            <template #default="{ row }">{{ row.mobile || row.phone || '—' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="source" label="来源" width="120" show-overflow-tooltip />
          <el-table-column label="评分" width="80" align="center">
            <template #default="{ row }">{{ row.score ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="入库时间" width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column v-if="canClaim()" label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :loading="claimingId === row.id"
                @click="claim(row)"
              >认领</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loadingLeads && !leads.length" description="该公海暂无待认领线索" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.page-head h2 {
  margin: 0 0 6px;
  font-size: 18px;
}
.hint {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.pool-tabs {
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.pool-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.pool-table {
  margin-top: 4px;
}
</style>
