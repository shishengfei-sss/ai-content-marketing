<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { PERMISSION_GROUPS } from '../config/permissions'
import { formatApiError, isRouteNotFoundError, teamApi, ROUTE_NOT_FOUND_HINT } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const tab = ref('members')
const loading = ref(false)
const apiUnavailable = ref(false)
const members = ref([])
const roles = ref([])

const memberDialog = ref(false)
const memberForm = ref({ phone: '', display_name: '', password: 'ChangeMe123' })

const roleDialog = ref(false)
const editingRole = ref(null)
const roleForm = ref({ name: '', permissions: [] })

const selectableRoles = computed(() => roles.value.filter((r) => r.code !== 'admin' || r.is_system))

function buildMemberFallback() {
  const user = auth.user
  if (!user?.active_tenant) return []
  const membership = user.tenants?.find((t) => t.id === user.active_tenant?.id)
  return [
    {
      id: 'local-fallback',
      user_id: user.id,
      phone: user.phone,
      display_name: user.display_name,
      role_id: null,
      role_code: membership?.role_code || 'admin',
      role_name: membership?.role_name || '企业管理员',
      is_active: true,
      joined_at: null,
      readonly: true,
    },
  ]
}

function buildRolesFallback() {
  return [
    { id: 'local-admin', code: 'admin', name: '企业管理员', is_system: true, permissions: [], readonly: true },
    { id: 'local-editor', code: 'editor', name: '编辑', is_system: true, permissions: [], readonly: true },
  ]
}

async function loadMembers() {
  try {
    const { data } = await teamApi.listMembers()
    members.value = Array.isArray(data) ? data : []
    return true
  } catch (e) {
    if (isRouteNotFoundError(e)) {
      apiUnavailable.value = true
      members.value = buildMemberFallback()
      return false
    }
    ElMessage.error(formatApiError(e, '成员加载失败'))
    return false
  }
}

async function loadRoles() {
  try {
    const { data } = await teamApi.listRoles()
    roles.value = Array.isArray(data) ? data : []
    return true
  } catch (e) {
    if (isRouteNotFoundError(e)) {
      apiUnavailable.value = true
      roles.value = buildRolesFallback()
      return false
    }
    if (e.status === 403) {
      roles.value = []
      return false
    }
    ElMessage.error(formatApiError(e, '角色加载失败'))
    return false
  }
}

async function loadAll() {
  loading.value = true
  apiUnavailable.value = false
  try {
    if (!auth.user && auth.isLoggedIn) {
      await auth.fetchMe()
    }
    await Promise.all([loadMembers(), loadRoles()])
  } finally {
    loading.value = false
  }
}

const phonePattern = /^1\d{10}$/

async function addMember() {
  if (apiUnavailable.value) {
    ElMessage.error(ROUTE_NOT_FOUND_HINT)
    return
  }
  const phone = memberForm.value.phone.trim()
  if (!phonePattern.test(phone)) {
    ElMessage.warning('请输入正确的 11 位手机号')
    return
  }
  if (!memberForm.value.display_name.trim()) {
    ElMessage.warning('请填写姓名')
    return
  }
  try {
    await teamApi.addMember({
      phone,
      display_name: memberForm.value.display_name.trim(),
      password: memberForm.value.password,
    })
    ElMessage.success('已添加成员')
    memberDialog.value = false
    memberForm.value = { phone: '', display_name: '', password: 'ChangeMe123' }
    await loadMembers()
  } catch (e) {
    ElMessage.error(formatApiError(e, '添加失败'))
  }
}

async function changeRole(member, roleId) {
  if (member.readonly || apiUnavailable.value) return
  try {
    await teamApi.updateMemberRole(member.id, roleId)
    ElMessage.success('角色已更新')
    await loadMembers()
  } catch (e) {
    ElMessage.error(formatApiError(e, '更新失败'))
  }
}

async function disableMember(member) {
  if (member.readonly || apiUnavailable.value) return
  try {
    await ElMessageBox.confirm(`确定禁用 ${member.display_name}？`, '确认')
    await teamApi.disableMember(member.id)
    ElMessage.success('已禁用')
    await loadMembers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(formatApiError(e, '操作失败'))
  }
}

function openRoleDialog(role = null) {
  if (apiUnavailable.value && !role?.readonly) {
    ElMessage.error(formatApiError({ status: 404, message: 'Not Found' }))
    return
  }
  editingRole.value = role
  roleForm.value = role
    ? { name: role.name, permissions: [...(role.permissions || [])] }
    : { name: '', permissions: [] }
  roleDialog.value = true
}

function togglePerm(code) {
  const set = new Set(roleForm.value.permissions)
  if (set.has(code)) set.delete(code)
  else set.add(code)
  roleForm.value.permissions = [...set]
}

async function saveRole() {
  if (apiUnavailable.value) {
    ElMessage.error(formatApiError({ status: 404, message: 'Not Found' }))
    return
  }
  try {
    if (editingRole.value) {
      await teamApi.updateRole(editingRole.value.id, roleForm.value)
    } else {
      await teamApi.createRole(roleForm.value)
    }
    ElMessage.success('角色已保存')
    roleDialog.value = false
    await loadRoles()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存失败'))
  }
}

async function removeRole(role) {
  if (role.readonly || apiUnavailable.value) return
  try {
    await ElMessageBox.confirm(`删除角色「${role.name}」？`, '确认')
    await teamApi.deleteRole(role.id)
    ElMessage.success('已删除')
    await loadRoles()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(formatApiError(e, '删除失败'))
  }
}

onMounted(loadAll)
</script>

<template>
  <div v-loading="loading" class="page-card">
    <el-alert
      v-if="apiUnavailable"
      type="warning"
      :closable="false"
      show-icon
      title="团队接口暂不可用"
      description="当前连接的后端缺少 /team 接口（多为旧 API 未重启）。请双击运行 scripts/restart-api.cmd（或指定端口：restart-api.cmd 8002），然后硬刷新页面（Ctrl+Shift+R）。"
      style="margin-bottom: 16px"
    />

    <el-tabs v-model="tab">
      <el-tab-pane label="成员" name="members">
        <div style="margin-bottom: 12px">
          <el-button type="primary" :disabled="apiUnavailable" @click="memberDialog = true">
            添加成员
          </el-button>
        </div>
        <el-table :data="members" stripe>
          <el-table-column prop="display_name" label="姓名" />
          <el-table-column prop="phone" label="手机号" />
          <el-table-column prop="role_name" label="角色" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-select
                v-if="row.role_code !== 'admin' && !row.readonly"
                :model-value="row.role_id"
                size="small"
                style="width: 120px; margin-right: 8px"
                @change="(v) => changeRole(row, v)"
              >
                <el-option v-for="r in selectableRoles" :key="r.id" :label="r.name" :value="r.id" />
              </el-select>
              <el-button
                v-if="row.role_code !== 'admin' && row.is_active && !row.readonly"
                link
                type="danger"
                @click="disableMember(row)"
              >
                禁用
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="角色与权限" name="roles">
        <div style="margin-bottom: 12px">
          <el-button type="primary" :disabled="apiUnavailable" @click="openRoleDialog()">
            新建角色
          </el-button>
        </div>
        <el-table :data="roles" stripe>
          <el-table-column prop="name" label="角色" />
          <el-table-column prop="code" label="标识" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.is_system" size="small">系统内置</el-tag>
              <span v-else>自定义</span>
            </template>
          </el-table-column>
          <el-table-column label="权限数" width="90">
            <template #default="{ row }">{{ row.permissions?.length || (row.is_system ? '—' : 0) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button
                v-if="row.code !== 'admin' && !row.readonly"
                link
                type="primary"
                @click="openRoleDialog(row)"
              >
                编辑
              </el-button>
              <el-button v-if="!row.is_system && !row.readonly" link type="danger" @click="removeRole(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="memberDialog" title="添加成员" width="420px">
      <el-form label-width="80px">
        <el-form-item label="手机号">
          <el-input v-model="memberForm.phone" maxlength="11" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="memberForm.display_name" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="memberForm.password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberDialog = false">取消</el-button>
        <el-button type="primary" :disabled="apiUnavailable" @click="addMember">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialog" :title="editingRole ? '编辑角色' : '新建角色'" width="560px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="roleForm.name" :disabled="editingRole?.is_system && editingRole?.code === 'admin'" />
        </el-form-item>
      </el-form>
      <div v-for="group in PERMISSION_GROUPS" :key="group.label" class="perm-group">
        <div class="perm-group__title">{{ group.label }}</div>
        <el-checkbox
          v-for="item in group.items"
          :key="item.code"
          :model-value="roleForm.permissions.includes(item.code)"
          :disabled="item.requires && !roleForm.permissions.includes(item.requires)"
          @change="togglePerm(item.code)"
        >
          {{ item.label }}
        </el-checkbox>
      </div>
      <template #footer>
        <el-button @click="roleDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.perm-group {
  margin-bottom: 16px;
}
.perm-group__title {
  font-weight: 600;
  margin-bottom: 8px;
}
.perm-group :deep(.el-checkbox) {
  display: block;
  margin-bottom: 4px;
}
</style>
