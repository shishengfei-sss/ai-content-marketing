<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../api/client'
import { formatDateTime } from '../../utils/datetime'

const route = useRoute()
const loading = ref(false)
const users = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQ = ref('')
const filterRole = ref('')
const filterShopRole = ref('')
const filterActive = ref('')
const savingId = ref(null)
const resetVisible = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')
const resetting = ref(false)

const permVisible = ref(false)
const permSaving = ref(false)
const permTarget = ref(null)
const permRole = ref('')
const permChecked = ref([])
const permAudits = ref([])
const permAuditsLoading = ref(false)
const catalog = ref({ permissions: [], roles: [] })

const roleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '平台管理员', value: 'platform_admin' },
]
const shopRoleOptions = [
  { label: '（未绑 · 等同超管）', value: 'superadmin' },
  { label: '日常运营', value: 'platform_shop_ops' },
  { label: '商家管家', value: 'platform_shop_cs' },
  { label: '财务结算', value: 'platform_shop_finance' },
]

const SHOP_ROLE_LABEL = {
  platform_shop_ops: '日常运营',
  platform_shop_cs: '商家管家',
  platform_shop_finance: '财务结算',
}

const permChoices = computed(() => {
  if (!permRole.value) {
    return (catalog.value.permissions || []).map((p) => ({
      code: p.code,
      label: p.label || p.code,
    }))
  }
  const role = (catalog.value.roles || []).find((r) => r.code === permRole.value)
  return (role?.matrix || [])
    .filter((r) => r.granted)
    .map((r) => ({ code: r.code, label: r.label }))
})

function shopRoleLabel(row) {
  if (row.role !== 'platform_admin') return '—'
  if (!row.platform_shop_role) return '（未绑 · 等同超管）'
  return SHOP_ROLE_LABEL[row.platform_shop_role] || row.platform_shop_role
}

async function loadCatalog() {
  try {
    const { data } = await adminApi.getShopPermissionCatalog()
    catalog.value = data || { permissions: [], roles: [] }
  } catch {
    catalog.value = { permissions: [], roles: [] }
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    if (filterRole.value) params.role = filterRole.value
    if (filterShopRole.value) params.platform_shop_role = filterShopRole.value
    if (filterActive.value !== '') params.is_active = filterActive.value
    const { data } = await adminApi.listUsers(params)
    if (Array.isArray(data)) {
      users.value = data
      total.value = data.length
      ElMessage.warning('账号列表接口格式异常（疑似 API 未重启），已临时展示；请硬重启 API')
    } else {
      users.value = Array.isArray(data?.items) ? data.items : []
      total.value = data?.total ?? 0
    }
  } catch (e) {
    if (isBenignEmptyError(e)) {
      users.value = []
      total.value = 0
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  currentPage.value = p
  loadUsers()
}

function handleSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadUsers()
}

function resetFilters() {
  searchQ.value = ''
  filterRole.value = ''
  filterShopRole.value = ''
  filterActive.value = ''
  currentPage.value = 1
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
      `确定删除账号「${row.phone || row.display_name}」？将移除其全部公司成员关系，企业与内容数据保留，且不可恢复。`,
      '删除账号',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await adminApi.deleteUser(row.id)
    if (users.value.length <= 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    loadUsers()
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function defaultPermsFor(roleCode) {
  if (!roleCode) return (catalog.value.permissions || []).map((p) => p.code)
  const role = (catalog.value.roles || []).find((r) => r.code === roleCode)
  return (role?.default_permissions || []).slice()
}

function openPermDrawer(row) {
  if (row.role !== 'platform_admin') {
    ElMessage.warning('仅平台管理员可绑定商城角色')
    return
  }
  if (!row.is_active) {
    ElMessage.warning('仅启用账号可编辑商城权限')
    return
  }
  permTarget.value = row
  permRole.value = row.platform_shop_role || ''
  permChecked.value = (row.platform_shop_permissions || []).slice()
  if (!permChecked.value.length) permChecked.value = defaultPermsFor(permRole.value)
  permAudits.value = []
  permVisible.value = true
  loadPermAudits()
}

async function loadPermAudits() {
  if (!permTarget.value) return
  permAuditsLoading.value = true
  try {
    const { data } = await adminApi.listShopPermissionAudits(permTarget.value.id)
    permAudits.value = data.items || []
  } catch (e) {
    if (!isBenignEmptyError(e)) {
      permAudits.value = []
    }
  } finally {
    permAuditsLoading.value = false
  }
}

function onPermRoleChange(code) {
  permChecked.value = defaultPermsFor(code)
}

async function savePerm() {
  if (!permTarget.value) return
  permSaving.value = true
  try {
    const { data } = await adminApi.updateUser(permTarget.value.id, {
      platform_shop_role: permRole.value || null,
      platform_shop_permissions: permRole.value ? permChecked.value : null,
    })
    Object.assign(permTarget.value, data)
    ElMessage.success('已保存')
    await loadPermAudits()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    permSaving.value = false
  }
}

watch(
  () => route.query.shop_role,
  (v) => {
    if (typeof v === 'string' && v) {
      filterShopRole.value = v
      filterRole.value = 'platform_admin'
    }
  },
  { immediate: true },
)

onMounted(async () => {
  await loadCatalog()
  loadUsers()
})
</script>

<template>
  <div class="page-card" data-testid="admin-users">
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="手机号 / 昵称 / 租户名"
        style="width: 240px"
        clearable
        @keyup.enter="loadUsers"
        @clear="loadUsers"
      />
      <el-select v-model="filterRole" placeholder="平台角色" clearable style="width: 140px">
        <el-option
          v-for="opt in roleOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-select v-model="filterShopRole" placeholder="获客商城角色" clearable style="width: 180px">
        <el-option
          v-for="opt in shopRoleOptions"
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
      <el-table-column label="所属公司" min-width="200">
        <template #default="{ row }">
          <template v-if="row.memberships?.length">
            <el-tag
              v-for="m in row.memberships"
              :key="`${m.tenant_id}-${m.role_code}`"
              size="small"
              style="margin: 2px 4px 2px 0"
            >
              {{ m.tenant_name }} · {{ m.role_name }}
            </el-tag>
          </template>
          <span v-else>{{ row.tenant_name || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="平台角色" width="160">
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
      <el-table-column label="获客商城角色" width="160">
        <template #default="{ row }">
          <span v-if="row.role !== 'platform_admin'">—</span>
          <el-tag v-else size="small" :type="row.platform_shop_role ? 'primary' : 'info'">
            {{ shopRoleLabel(row) }}
          </el-tag>
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
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openResetDialog(row)">
            重置密码
          </el-button>
          <el-button
            v-if="row.role === 'platform_admin' && row.is_active"
            type="primary"
            link
            size="small"
            @click="openPermDrawer(row)"
          >
            编辑商城权限
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

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

    <el-drawer
      v-model="permVisible"
      :title="permTarget ? `编辑权限 · ${permTarget.display_name || permTarget.phone}` : '编辑权限'"
      size="520px"
    >
      <div v-if="permTarget" data-testid="shop-edit-shop-perms">
        <div class="field">
          <label>账号</label>
          <div class="val">{{ permTarget.phone || permTarget.display_name }}（只读）</div>
        </div>
        <div class="field">
          <label>角色 <span class="req">*</span></label>
          <el-select v-model="permRole" style="width: 100%" @change="onPermRoleChange">
            <el-option label="平台超管（未绑）" value="" />
            <el-option label="日常运营 (platform_shop_ops)" value="platform_shop_ops" />
            <el-option label="商家管家 (platform_shop_cs)" value="platform_shop_cs" />
            <el-option label="财务结算 (platform_shop_finance)" value="platform_shop_finance" />
          </el-select>
        </div>
        <p class="hint">在角色默认权限上微调（取消勾选即收回）：</p>
        <el-checkbox-group v-model="permChecked" class="perm-list">
          <el-checkbox v-for="p in permChoices" :key="p.code" :label="p.code">
            {{ p.code }}　{{ p.label }}
          </el-checkbox>
        </el-checkbox-group>
        <div class="audit-block" data-testid="shop-perm-audit-timeline">
          <div class="audit-title">变更记录</div>
          <p class="hint">保存后写入本账号的权限变更，只读不可删。站内信未接通。</p>
          <el-table v-if="permAudits.length" :data="permAudits" size="small" v-loading="permAuditsLoading">
            <el-table-column label="时间" width="158">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作人" width="96" prop="operator_name" show-overflow-tooltip />
            <el-table-column label="变更" prop="summary" show-overflow-tooltip />
          </el-table>
          <el-empty v-else description="暂无变更记录" :image-size="48" />
        </div>
        <div class="drawer-ft">
          <el-button @click="permVisible = false">取消</el-button>
          <el-button type="primary" :loading="permSaving" @click="savePerm">保存</el-button>
        </div>
      </div>
    </el-drawer>
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

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.field {
  margin-bottom: 12px;
}
.field label {
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
  color: #606266;
}
.val {
  font-size: 13px;
  color: #303133;
}
.req {
  color: #f56c6c;
}
.hint {
  font-size: 12px;
  color: #666;
  margin: 8px 0;
}
.perm-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 180px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 8px;
}
.drawer-ft {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.audit-block {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}
.audit-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #303133;
}
</style>
