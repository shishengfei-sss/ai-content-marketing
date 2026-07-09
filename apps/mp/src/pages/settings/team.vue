<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { teamApi } from '@/utils/api'
import { formatApiError, isRouteNotFoundError, ROUTE_NOT_FOUND_HINT } from '@/utils/apiError'
import { invalidateTeamMembersCache } from '@/utils/useTeamMembers'
import { PERMISSION_GROUPS, hasPermission, isPermDisabled } from '@/utils/permissions'
import { ensureSession, fetchMe } from '@/utils/session'

const tab = ref('members')
const loading = ref(false)
const apiUnavailable = ref(false)
const members = ref([])
const roles = ref([])
const permissions = ref([])
const cachedUser = ref(null)

const showAdd = ref(false)
const addForm = ref({ phone: '', display_name: '', password: 'ChangeMe123' })

const showRoleEdit = ref(false)
const editingRole = ref(null)
const roleForm = ref({ name: '', permissions: [] })

const phonePattern = /^1\d{10}$/

const canManageMembers = computed(() => hasPermission(permissions.value, 'team.member.manage'))
const canManageRoles = computed(() => hasPermission(permissions.value, 'team.role.manage'))
const selectableRoles = computed(() => roles.value.filter((r) => r.code !== 'admin'))

function buildMemberFallback(user) {
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

async function loadMembers(user) {
  try {
    members.value = await teamApi.listMembers()
    return true
  } catch (e) {
    if (isRouteNotFoundError(e)) {
      apiUnavailable.value = true
      members.value = buildMemberFallback(user)
      return false
    }
    uni.showToast({ title: formatApiError(e, '成员加载失败'), icon: 'none' })
    return false
  }
}

async function loadRoles() {
  if (!canManageRoles.value) {
    roles.value = []
    return true
  }
  try {
    roles.value = await teamApi.listRoles()
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
    uni.showToast({ title: formatApiError(e, '角色加载失败'), icon: 'none' })
    return false
  }
}

async function loadAll() {
  loading.value = true
  apiUnavailable.value = false
  try {
    const user = await ensureSession()
    if (!user) return
    cachedUser.value = await fetchMe()
    permissions.value = cachedUser.value?.permissions || []
    if (
      !permissions.value.some((p) =>
        ['team.member.view', 'team.role.manage', 'team.member.manage'].includes(p),
      )
    ) {
      uni.showToast({ title: '无权限', icon: 'none' })
      setTimeout(() => uni.navigateBack(), 500)
      return
    }
    await loadMembers(cachedUser.value)
    await loadRoles()
  } finally {
    loading.value = false
  }
}

function openAdd() {
  if (apiUnavailable.value) {
    uni.showToast({ title: ROUTE_NOT_FOUND_HINT, icon: 'none', duration: 3000 })
    return
  }
  addForm.value = { phone: '', display_name: '', password: 'ChangeMe123' }
  showAdd.value = true
}

async function submitAdd() {
  const phone = addForm.value.phone.trim()
  if (!phonePattern.test(phone)) {
    uni.showToast({ title: '请输入正确的 11 位手机号', icon: 'none' })
    return
  }
  if (!addForm.value.display_name.trim()) {
    uni.showToast({ title: '请填写姓名', icon: 'none' })
    return
  }
  try {
    await teamApi.addMember({
      phone,
      display_name: addForm.value.display_name.trim(),
      password: addForm.value.password,
    })
    showAdd.value = false
    uni.showToast({ title: '已添加成员', icon: 'success' })
    invalidateTeamMembersCache()
    await loadMembers(cachedUser.value)
  } catch (e) {
    uni.showToast({ title: formatApiError(e, '添加失败'), icon: 'none' })
  }
}

function pickMemberRole(member) {
  if (member.readonly || !canManageMembers.value || member.role_code === 'admin') return
  const options = selectableRoles.value
  if (!options.length) return
  uni.showActionSheet({
    itemList: options.map((r) => r.name),
    success: async (res) => {
      const role = options[res.tapIndex]
      try {
        await teamApi.updateMemberRole(member.id, role.id)
        uni.showToast({ title: '角色已更新', icon: 'success' })
        await loadMembers(cachedUser.value)
      } catch (e) {
        uni.showToast({ title: formatApiError(e, '更新失败'), icon: 'none' })
      }
    },
  })
}

function confirmDisable(member) {
  if (member.readonly || !canManageMembers.value || member.role_code === 'admin') return
  uni.showModal({
    title: '禁用成员',
    content: `确定禁用 ${member.display_name}？`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        await teamApi.disableMember(member.id)
        uni.showToast({ title: '已禁用', icon: 'success' })
        await loadMembers(cachedUser.value)
      } catch (e) {
        uni.showToast({ title: formatApiError(e, '操作失败'), icon: 'none' })
      }
    },
  })
}

function openRoleEdit(role = null) {
  if (apiUnavailable.value && !role?.readonly) {
    uni.showToast({ title: ROUTE_NOT_FOUND_HINT, icon: 'none', duration: 3000 })
    return
  }
  if (!canManageRoles.value) return
  editingRole.value = role
  roleForm.value = role
    ? { name: role.name, permissions: [...(role.permissions || [])] }
    : { name: '', permissions: [] }
  showRoleEdit.value = true
}

function togglePerm(code) {
  const set = new Set(roleForm.value.permissions)
  if (set.has(code)) set.delete(code)
  else set.add(code)
  roleForm.value.permissions = [...set]
}

function permDisabled(item) {
  return isPermDisabled(roleForm.value.permissions, item)
}

async function saveRoleEdit() {
  if (!roleForm.value.name.trim()) {
    uni.showToast({ title: '请填写角色名称', icon: 'none' })
    return
  }
  try {
    if (editingRole.value?.id && !String(editingRole.value.id).startsWith('local-')) {
      await teamApi.updateRole(editingRole.value.id, roleForm.value)
    } else if (!editingRole.value) {
      await teamApi.createRole(roleForm.value)
    }
    showRoleEdit.value = false
    uni.showToast({ title: '角色已保存', icon: 'success' })
    await loadRoles()
  } catch (e) {
    uni.showToast({ title: formatApiError(e, '保存失败'), icon: 'none' })
  }
}

function confirmDeleteRole(role) {
  if (role.readonly || role.is_system) return
  uni.showModal({
    title: '删除角色',
    content: `删除角色「${role.name}」？`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        await teamApi.deleteRole(role.id)
        uni.showToast({ title: '已删除', icon: 'success' })
        await loadRoles()
      } catch (e) {
        uni.showToast({ title: formatApiError(e, '删除失败'), icon: 'none' })
      }
    },
  })
}

onShow(loadAll)
</script>

<template>
  <view class="page">
    <view v-if="apiUnavailable" class="warn">
      {{ ROUTE_NOT_FOUND_HINT }}
    </view>

    <view class="tabs">
      <view class="tab" :class="{ active: tab === 'members' }" @click="tab = 'members'">成员</view>
      <view
        v-if="canManageRoles"
        class="tab"
        :class="{ active: tab === 'roles' }"
        @click="tab = 'roles'"
      >
        角色与权限
      </view>
    </view>

    <view v-if="tab === 'members'" class="panel">
      <button v-if="canManageMembers" class="btn-add" :disabled="apiUnavailable" @click="openAdd">
        添加成员
      </button>
      <view v-if="!members.length && !loading" class="empty">暂无成员</view>
      <view v-for="m in members" :key="m.id" class="row" @click="pickMemberRole(m)">
        <view class="row__main">
          <text class="name">{{ m.display_name }}</text>
          <text class="sub">{{ m.phone }} · {{ m.role_name }}</text>
        </view>
        <view class="row__right">
          <text class="status" :class="{ off: !m.is_active }">{{ m.is_active ? '启用' : '禁用' }}</text>
          <text
            v-if="canManageMembers && m.role_code !== 'admin' && m.is_active && !m.readonly"
            class="action"
            @click.stop="confirmDisable(m)"
          >
            禁用
          </text>
        </view>
      </view>
    </view>

    <view v-else-if="tab === 'roles'" class="panel">
      <button v-if="canManageRoles" class="btn-add" :disabled="apiUnavailable" @click="openRoleEdit()">
        新建角色
      </button>
      <view v-if="!roles.length && !loading" class="empty">暂无角色</view>
      <view v-for="r in roles" :key="r.id" class="row role-row">
        <view class="row__main">
          <text class="name">{{ r.name }}</text>
          <text class="sub">{{ r.code }} · {{ r.is_system ? '系统内置' : '自定义' }} · 权限 {{ r.permissions?.length || '—' }}</text>
        </view>
        <view v-if="canManageRoles && r.code !== 'admin' && !r.readonly" class="row__actions">
          <text class="action" @click="openRoleEdit(r)">编辑</text>
          <text v-if="!r.is_system" class="action danger" @click="confirmDeleteRole(r)">删除</text>
        </view>
      </view>
    </view>

    <!-- 添加成员 -->
    <view v-if="showAdd" class="mask" @click="showAdd = false">
      <view class="sheet" @click.stop>
        <text class="sheet__title">添加成员</text>
        <view class="field">
          <text class="label">手机号</text>
          <input v-model="addForm.phone" class="input" type="number" maxlength="11" />
        </view>
        <view class="field">
          <text class="label">姓名</text>
          <input v-model="addForm.display_name" class="input" />
        </view>
        <view class="field">
          <text class="label">初始密码</text>
          <input v-model="addForm.password" class="input" password />
        </view>
        <view class="sheet__btns">
          <button class="btn-cancel" @click="showAdd = false">取消</button>
          <button class="btn-primary" @click="submitAdd">确定</button>
        </view>
      </view>
    </view>

    <!-- 编辑角色 -->
    <view v-if="showRoleEdit" class="mask" @click="showRoleEdit = false">
      <view class="sheet sheet--tall" @click.stop>
        <text class="sheet__title">{{ editingRole ? '编辑角色' : '新建角色' }}</text>
        <view class="field">
          <text class="label">名称</text>
          <input v-model="roleForm.name" class="input" :disabled="editingRole?.code === 'admin'" />
        </view>
        <scroll-view scroll-y class="perm-scroll">
          <view v-for="group in PERMISSION_GROUPS" :key="group.label" class="perm-group">
            <text class="perm-group__title">{{ group.label }}</text>
            <template v-for="(row, rowIdx) in group.rows" :key="`${group.label}-${rowIdx}`">
              <view v-if="row.type === 'scope'" class="perm-scope-row">
                <text class="perm-scope-row__menu">{{ row.menu }}</text>
                <view class="perm-scope-row__options">
                  <label
                    v-for="item in row.items"
                    :key="item.code"
                    class="perm-item perm-item--inline"
                    @click="!permDisabled(item) && togglePerm(item.code)"
                  >
                    <checkbox
                      :checked="roleForm.permissions.includes(item.code)"
                      :disabled="permDisabled(item)"
                    />
                    <text>{{ item.label }}</text>
                  </label>
                </view>
              </view>
              <view v-else class="perm-inline-row">
                <label
                  v-for="item in row.items"
                  :key="item.code"
                  class="perm-item perm-item--inline"
                  @click="!permDisabled(item) && togglePerm(item.code)"
                >
                  <checkbox
                    :checked="roleForm.permissions.includes(item.code)"
                    :disabled="permDisabled(item)"
                  />
                  <text>{{ item.label }}</text>
                </label>
              </view>
            </template>
          </view>
        </scroll-view>
        <view class="sheet__btns">
          <button class="btn-cancel" @click="showRoleEdit = false">取消</button>
          <button class="btn-primary" @click="saveRoleEdit">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 48rpx;
}
.warn {
  background: #fff7e6;
  color: #ad6800;
  font-size: 24rpx;
  padding: 20rpx 24rpx;
  line-height: 1.5;
}
.tabs {
  display: flex;
  background: #fff;
  border-bottom: 1rpx solid #f0f0f0;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 24rpx 0;
  font-size: 28rpx;
  color: #666;
}
.tab.active {
  color: #1677ff;
  font-weight: 600;
  border-bottom: 4rpx solid #1677ff;
}
.panel {
  padding-top: 8rpx;
}
.btn-add {
  margin: 24rpx 24rpx 8rpx;
  background: #1677ff;
  color: #fff;
  font-size: 28rpx;
  border-radius: 12rpx;
}
.btn-add[disabled] {
  opacity: 0.5;
}
.empty {
  text-align: center;
  color: #999;
  padding: 80rpx 0;
  font-size: 28rpx;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: 28rpx 32rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.row__main {
  flex: 1;
  min-width: 0;
}
.name {
  display: block;
  font-size: 30rpx;
  margin-bottom: 6rpx;
}
.sub {
  display: block;
  font-size: 24rpx;
  color: #999;
}
.row__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8rpx;
  margin-left: 16rpx;
}
.row__actions {
  display: flex;
  gap: 24rpx;
  margin-left: 16rpx;
}
.status {
  font-size: 24rpx;
  color: #1677ff;
}
.status.off {
  color: #999;
}
.action {
  font-size: 24rpx;
  color: #1677ff;
}
.action.danger {
  color: #ff4d4f;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  padding: 32rpx;
  box-sizing: border-box;
}
.sheet--tall {
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sheet__title {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  margin-bottom: 24rpx;
}
.field {
  margin-bottom: 20rpx;
}
.label {
  display: block;
  font-size: 26rpx;
  color: #666;
  margin-bottom: 8rpx;
}
.input {
  width: 100%;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 20rpx;
  box-sizing: border-box;
  font-size: 28rpx;
}
.sheet__btns {
  display: flex;
  gap: 16rpx;
  margin-top: 16rpx;
  flex-shrink: 0;
}
.btn-cancel,
.btn-primary {
  flex: 1;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.btn-cancel {
  background: #f5f5f5;
  color: #666;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
}
.perm-scroll {
  flex: 1;
  min-height: 0;
  max-height: none;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.perm-group {
  margin-bottom: 24rpx;
}
.perm-group__title {
  display: block;
  font-weight: 600;
  font-size: 28rpx;
  margin-bottom: 12rpx;
}
.perm-scope-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 12rpx;
}
.perm-scope-row__menu {
  width: 140rpx;
  flex-shrink: 0;
  color: #666;
  font-size: 26rpx;
  line-height: 48rpx;
}
.perm-scope-row__options,
.perm-inline-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx 24rpx;
  flex: 1;
}
.perm-inline-row {
  padding-left: 156rpx;
  margin-bottom: 12rpx;
}
.perm-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
  font-size: 26rpx;
}
.perm-item--inline {
  margin-bottom: 0;
}
</style>
