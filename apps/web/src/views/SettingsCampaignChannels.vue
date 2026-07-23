<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'
import { formatApiError } from '../utils/apiError'

const loading = ref(false)
const saving = ref(false)
const channels = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({
  name: '',
  code: '',
  sort_order: 0,
  is_active: true,
})

function isTaken(field, value, excludeId = null) {
  const v = String(value || '').trim()
  if (!v) return false
  return channels.value.some((row) => row[field] === v && row.id !== excludeId)
}

function resetForm() {
  editingId.value = null
  form.value = { name: '', code: '', sort_order: 0, is_active: true }
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listCampaignChannels()
    channels.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载渠道失败'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  form.value.sort_order = channels.value.length
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    name: row.name,
    code: row.code,
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
  }
  dialogVisible.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写渠道名称')
    return
  }
  if (isTaken('name', form.value.name, editingId.value)) {
    ElMessage.warning('渠道名称已存在')
    return
  }
  if (form.value.code?.trim() && isTaken('code', form.value.code.trim().toLowerCase(), editingId.value)) {
    ElMessage.warning('渠道编码已存在')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      sort_order: Number(form.value.sort_order) || 0,
      is_active: form.value.is_active,
    }
    if (!editingId.value) {
      payload.code = form.value.code?.trim() || null
    }
    if (editingId.value) {
      await crmApi.updateCampaignChannel(editingId.value, payload)
      ElMessage.success('渠道已更新')
    } else {
      await crmApi.createCampaignChannel(payload)
      ElMessage.success('渠道已创建')
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
      `删除渠道「${row.name}」？活动中已选该渠道将被移除。`,
      '确认删除',
      { type: 'warning' },
    )
    await crmApi.deleteCampaignChannel(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(formatApiError(e, '删除失败'))
  }
}

async function seedDefaults() {
  try {
    const { data } = await crmApi.seedCampaignChannels()
    const n = Array.isArray(data) ? data.length : 0
    ElMessage.success(n ? `已补齐 ${n} 个默认渠道` : '默认渠道已齐全')
    await load()
  } catch (e) {
    ElMessage.error(formatApiError(e, '初始化失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <h2>活动投放渠道</h2>
        <p class="hint">维护营销活动「投放渠道」选项；活动中保存的是渠道编码，改名不影响历史数据。</p>
      </div>
      <div class="actions">
        <el-button @click="seedDefaults">补齐默认渠道</el-button>
        <el-button type="primary" @click="openCreate">新建渠道</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="channels" border>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="sort_order" label="排序" width="80" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑渠道' : '新建渠道'"
      width="480px"
      destroy-on-close
    >
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="100" show-word-limit placeholder="如：公众号" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input
            v-model="form.code"
            maxlength="50"
            placeholder="可选，如 wechat；留空自动生成"
            :disabled="!!editingId"
          />
          <div v-if="editingId" class="field-hint">编码创建后不可在此修改（避免历史活动失联）</div>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :controls="false" style="width: 100%" />
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
.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
