<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/datetime'

const loading = ref(false)
const saving = ref(false)
const pools = ref([])
const territories = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({
  name: '',
  territory_id: null,
  industry_filter: '',
  auto_reclaim_days: null,
})

function resetForm() {
  editingId.value = null
  form.value = {
    name: '',
    territory_id: null,
    industry_filter: '',
    auto_reclaim_days: null,
  }
}

function territoryName(id) {
  if (!id) return '—'
  return territories.value.find((t) => t.id === id)?.name || '—'
}

async function loadTerritories() {
  try {
    const { data } = await crmApi.listTerritories()
    territories.value = Array.isArray(data) ? data : (data?.items || [])
  } catch {
    territories.value = []
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listLeadPools()
    pools.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载公海失败'))
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
  form.value = {
    name: row.name || '',
    territory_id: row.territory_id || null,
    industry_filter: row.industry_filter || '',
    auto_reclaim_days: row.auto_reclaim_days ?? null,
  }
  dialogVisible.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写公海名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      territory_id: form.value.territory_id || null,
      industry_filter: form.value.industry_filter?.trim() || null,
      auto_reclaim_days: form.value.auto_reclaim_days || null,
    }
    if (editingId.value) {
      await crmApi.updateLeadPool(editingId.value, payload)
      ElMessage.success('公海已更新')
    } else {
      await crmApi.createLeadPool(payload)
      ElMessage.success('公海已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `删除公海「${row.name}」？池内仍有未认领线索时将无法删除。`,
      '确认删除',
      { type: 'warning' },
    )
    await crmApi.deleteLeadPool(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(formatApiError(e, '删除失败'))
  }
}

onMounted(async () => {
  await loadTerritories()
  await load()
})
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <h2>线索公海</h2>
        <p class="hint">
          维护线索公海池；退回公海后的线索会出现在
          <router-link to="/crm/lead-pools">客户管理 → 线索公海</router-link>
          ，同事可认领。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新建公海</el-button>
    </div>

    <el-table v-loading="loading" :data="pools" border>
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="归属地区" width="140">
        <template #default="{ row }">{{ territoryName(row.territory_id) }}</template>
      </el-table-column>
      <el-table-column prop="industry_filter" label="行业筛选" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.industry_filter || '—' }}</template>
      </el-table-column>
      <el-table-column label="自动回收(天)" width="120" align="center">
        <template #default="{ row }">{{ row.auto_reclaim_days ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !pools.length" description="暂无公海，请先新建" />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑公海' : '新建公海'"
      width="480px"
      destroy-on-close
    >
      <el-form label-width="110px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="100" show-word-limit placeholder="如：华东公海" />
        </el-form-item>
        <el-form-item label="归属地区">
          <el-select v-model="form.territory_id" clearable filterable placeholder="可选" style="width: 100%">
            <el-option v-for="t in territories" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业筛选">
          <el-input v-model="form.industry_filter" maxlength="100" placeholder="可选，如：财税" />
        </el-form-item>
        <el-form-item label="自动回收天数">
          <el-input-number
            v-model="form.auto_reclaim_days"
            :min="1"
            :controls="false"
            placeholder="可选"
            style="width: 100%"
          />
          <div class="field-hint">认领后超过该天数未跟进可自动退回（需服务端回收任务开启）</div>
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
.hint a {
  color: var(--el-color-primary);
}
.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
