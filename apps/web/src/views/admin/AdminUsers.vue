<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api/client'

const loading = ref(false)
const users = ref([])
const searchQ = ref('')
const filterRole = ref('')
const filterActive = ref('')
const savingId = ref(null)
const resetVisible = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')
const resetting = ref(false)

const roleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '平台管理员', value: 'platform_admin' },
]

async function loadUsers() {
  loading.value = true
  try {
    const params = {}
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    if (filterRole.value) params.role = filterRole.value
    if (filterActive.value !== '') params.is_active = filterActive.value
    const { data } = await adminApi.listUsers(params)
    users.value = data
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchQ.value = ''
  filterRole.value = ''
  filterActive.value = ''
  loadUsers()
}

async function updateUser(row, patch) {
  savingId.value = row.id
  try {
    const { data } = await adminApi.updateUser(row.id, patch)
    Object.assign(row, data)
    ElMessage.success('已更新')
  } catch (e) {
    ElMessage.error(e.message || '更新失败')
  } finally {
    savingId.value = null
  }
}

function openResetDialog(row) {
  resetTarget.value = row
  resetPassword.value = ''
  resetVisible.value = true
}

async function confirmResetPassword() {
  if (!resetTarget.value) return
  if (resetPassword.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  resetting.value = true
  try {
    await adminApi.resetUserPassword(resetTarget.value.id, resetPassword.value)
    ElMessage.success(`已重置 ${resetTarget.value.phone || resetTarget.value.display_name} 的密码`)
    resetVisible.value = false
  } catch (e) {
    ElMessage.error(e.message || '重置失败')
  } finally {
    resetting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.phone || row.display_name}」？将同时删除其全部内容与租户数据，且不可恢复。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await adminApi.deleteUser(row.id)
    users.value = users.value.filter((item) => item.id !== row.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(loadUsers)
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="手机号 / 昵称 / 租户名"
        style="width: 240px"
        clearable
        @keyup.enter="loadUsers"
        @clear="loadUsers"
      />
      <el-select v-model="filterRole" placeholder="角色" clearable style="width: 140px">
        <el-option
          v-for="opt in roleOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-select v-model="filterActive" placeholder="状态" clearable style="width: 120px">
        <el-option label="启用" :value="true" />
        <el-option label="禁用" :value="false" />
      </el-select>
      <el-button type="primary" @click="loadUsers">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="users" stripe style="margin-top: 16px">
      <el-table-column prop="phone" label="手机号" width="130" />
      <el-table-column prop="display_name" label="昵称" width="120" />
      <el-table-column prop="tenant_name" label="租户名" width="130" />
      <el-table-column label="角色" width="160">
        <template #default="{ row }">
          <el-select
            :model-value="row.role"
            size="small"
            :disabled="savingId === row.id"
            @change="(v) => updateUser(row, { role: v })"
          >
            <el-option
              v-for="opt in roleOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_active"
            :disabled="savingId === row.id"
            @change="(v) => updateUser(row, { is_active: v })"
          />
        </template>
      </el-table-column>
      <el-table-column label="注册时间" min-width="170">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openResetDialog(row)">
            重置密码
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="resetVisible" title="重置密码" width="420px">
      <p class="reset-tip">
        为用户「{{ resetTarget?.phone || resetTarget?.display_name }}」设置新密码
      </p>
      <el-input
        v-model="resetPassword"
        type="password"
        show-password
        placeholder="新密码，至少 8 位"
        maxlength="128"
        @keyup.enter="confirmResetPassword"
      />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetting" @click="confirmResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.reset-tip {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  font-size: 14px;
}
</style>
