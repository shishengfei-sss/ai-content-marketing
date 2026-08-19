<script setup>
/**
 * A16 角色与成员。对照 PRD 01-管理端UI.html #a16 · #a16a
 * Phase1：内置角色启用/禁用、成员换绑；权限矩阵只读。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/client'
import ShopSettingsNav from '../../components/shop/ShopSettingsNav.vue'
import { useAuthStore } from '../../stores/auth'
import {
  resolveRoleShopPermissions,
  roleCapabilitySummary,
  SHOP_MATRIX_GROUPS,
  shopPermissionLabel,
} from '../../config/shopPermissionMatrix'

const auth = useAuthStore()
const canManageRoles = computed(() => auth.hasPermission('shop.role.manage'))

const loading = ref(false)
const roles = ref([])
const members = ref([])
const candidates = ref([])
const stores = ref([])
const selectedCode = ref('shop_admin')
const rightTab = ref('members')
const assignOpen = ref(false)
const assigning = ref(false)

const form = reactive({
  user_id: null,
  role_code: 'shop_content',
  store_scope: 'all',
  store_ids: [],
})

const selectedRole = computed(() => roles.value.find((r) => r.code === selectedCode.value) || null)
const roleShopPermissions = computed(() => resolveRoleShopPermissions(selectedRole.value))
const matrixGroups = computed(() =>
  SHOP_MATRIX_GROUPS.map((group) => ({
    ...group,
    items: group.codes.map((code) => ({
      code,
      label: shopPermissionLabel(code),
      granted: roleShopPermissions.value.has(code),
    })),
  })).filter((group) => group.items.length),
)
const filteredMembers = computed(() =>
  members.value.filter((m) => m.role_code === selectedCode.value)
)
const enabledRoles = computed(() => roles.value.filter((r) => r.enabled))

async function load() {
  loading.value = true
  try {
    const [r, m, s] = await Promise.all([
      api.get('/api/v1/shop/roles'),
      api.get('/api/v1/shop/members'),
      api.get('/api/v1/shop/stores', { params: { page: 1, page_size: 100 } }),
    ])
    roles.value = Array.isArray(r.data) ? r.data : r.data?.items || []
    members.value = m.data?.items || []
    stores.value = s.data?.items || []
    if (!roles.value.find((x) => x.code === selectedCode.value) && roles.value.length) {
      selectedCode.value = roles.value[0].code
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadCandidates() {
  try {
    const { data } = await api.get('/api/v1/shop/members/candidates')
    candidates.value = data.items || []
  } catch (e) {
    ElMessage.error(e.message || '成员候选加载失败')
  }
}

function selectRole(code) {
  selectedCode.value = code
  rightTab.value = 'members'
}

async function toggleRole(enable) {
  const role = selectedRole.value
  if (!role || !role.can_disable) return
  try {
    if (!enable) {
      await ElMessageBox.confirm(
        `禁用「${role.name}」后不可再分配；须先确保无成员绑定。`,
        '禁用角色',
        { type: 'warning' }
      )
    }
    const path = enable
      ? `/api/v1/shop/roles/${role.code}/enable`
      : `/api/v1/shop/roles/${role.code}/disable`
    const { data } = await api.post(path)
    const idx = roles.value.findIndex((r) => r.code === data.code)
    if (idx >= 0) roles.value[idx] = data
    ElMessage.success(enable ? '已启用' : '已禁用')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

async function openAssign(prefillRole) {
  if (!canManageRoles.value) {
    ElMessage.warning('无角色管理权限，请联系企业管理员')
    return
  }
  form.user_id = null
  form.role_code = prefillRole || selectedCode.value || 'shop_content'
  form.store_scope = form.role_code === 'shop_clerk' ? 'selected' : 'all'
  form.store_ids = []
  await loadCandidates()
  assignOpen.value = true
}

watch(
  () => form.role_code,
  (code) => {
    if (code === 'shop_clerk') {
      form.store_scope = 'selected'
      if (form.store_ids.length > 1) form.store_ids = form.store_ids.slice(0, 1)
    } else if (code === 'admin') {
      form.store_scope = 'all'
      form.store_ids = []
    }
  }
)

async function confirmAssign() {
  if (!form.user_id) {
    ElMessage.warning('请选择成员')
    return
  }
  if (!form.role_code) {
    ElMessage.warning('请选择绑定角色')
    return
  }
  assigning.value = true
  try {
    await api.post('/api/v1/shop/members', {
      user_id: form.user_id,
      role_code: form.role_code,
      store_scope: form.store_scope,
      store_ids: form.store_scope === 'selected' ? form.store_ids : [],
    })
    ElMessage.success('已分配')
    assignOpen.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '分配失败')
  } finally {
    assigning.value = false
  }
}

async function changeRole(row) {
  const opts = enabledRoles.value.map((r) => r.code).join(' / ')
  try {
    const { value } = await ElMessageBox.prompt(`可选：${opts}`, '换角色', {
      inputValue: row.role_code,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    const code = (value || '').trim()
    if (!enabledRoles.value.find((r) => r.code === code)) {
      ElMessage.warning('角色无效或已禁用')
      return
    }
    const body = { role_code: code, store_scope: code === 'shop_clerk' ? 'selected' : 'all' }
    if (code === 'shop_clerk') {
      const shopId = stores.value[0]?.id
      if (!shopId) {
        ElMessage.warning('请先创建店铺')
        return
      }
      body.store_ids = [shopId]
    }
    await api.patch(`/api/v1/shop/members/${row.user_id}`, body)
    ElMessage.success('已换绑')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

async function removeMember(row) {
  try {
    await ElMessageBox.confirm(`移除「${row.display_name}」的商城角色？`, '移除', { type: 'warning' })
    await api.delete(`/api/v1/shop/members/${row.user_id}`)
    ElMessage.success('已移除')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

function permSummary(role) {
  return roleCapabilitySummary(role)
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card a16">
    <div class="hd">
      <div>
        <div class="crumb">设置 / <b>角色与成员</b></div>
        <h3>角色与成员</h3>
      </div>
      <el-button v-if="canManageRoles" type="primary" @click="openAssign()">+ 分配成员</el-button>
    </div>

    <ShopSettingsNav current="roles" />

    <el-alert
      v-if="!canManageRoles"
      type="info"
      :closable="false"
      show-icon
      title="当前账号仅可查看成员与权限矩阵；分配成员、换绑、启用/禁用角色需企业管理员权限。"
      style="margin-bottom: 10px"
    />

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="Phase 1：仅内置角色；可启用/禁用店铺角色、给成员换绑。不可新建自定义角色、不可改权限矩阵勾选（矩阵只读）。"
      style="margin-bottom: 14px"
    />

    <div class="two">
      <div class="role-list">
        <div class="side-title">内置角色</div>
        <button
          v-for="r in roles"
          :key="r.code"
          type="button"
          class="role-item"
          :class="{ on: r.code === selectedCode, dim: !r.enabled }"
          @click="selectRole(r.code)"
        >
          <div class="name">
            {{ r.name }}
            <el-tag v-if="r.code === 'admin'" size="small" type="info">系统</el-tag>
            <el-tag v-else-if="!r.enabled" size="small" type="info">已禁用</el-tag>
            <el-tag v-else-if="r.code === selectedCode" size="small" type="primary">选中</el-tag>
          </div>
          <div class="meta">
            <code>{{ r.code }}</code>
            · {{ r.enabled ? '启用' : '已禁用' }}
            · {{ r.member_count }} 人
          </div>
        </button>
      </div>

      <div class="right">
        <div class="right-hd">
          <div class="subtabs">
            <button
              type="button"
              :class="{ on: rightTab === 'members' }"
              @click="rightTab = 'members'"
            >
              成员 ({{ filteredMembers.length }})
            </button>
            <button
              type="button"
              :class="{ on: rightTab === 'matrix' }"
              @click="rightTab = 'matrix'"
            >
              权限矩阵
            </button>
          </div>
          <div v-if="selectedRole" class="role-actions">
            角色：{{ selectedRole.name }}
            <template v-if="selectedRole.can_disable && canManageRoles">
              ·
              <el-button
                v-if="selectedRole.enabled"
                link
                type="danger"
                @click="toggleRole(false)"
              >
                禁用此角色
              </el-button>
              <el-button v-else link type="primary" @click="toggleRole(true)">启用</el-button>
            </template>
          </div>
        </div>

        <template v-if="rightTab === 'members'">
          <p class="hint">{{ permSummary(selectedRole) }}</p>
          <el-table :data="filteredMembers" size="small" empty-text="暂无成员">
            <el-table-column prop="display_name" label="成员" min-width="100" />
            <el-table-column label="手机/邮箱" min-width="120">
              <template #default="{ row }">
                {{ row.phone_masked || row.email || '—' }}
              </template>
            </el-table-column>
            <el-table-column label="数据范围" min-width="140">
              <template #default="{ row }">
                {{
                  row.store_scope === 'all'
                    ? '全部店铺'
                    : (row.store_names || []).join('、') || '—'
                }}
              </template>
            </el-table-column>
            <el-table-column v-if="canManageRoles" label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="changeRole(row)">换角色</el-button>
                <el-button link type="danger" @click="removeMember(row)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <div v-else class="matrix">
          <p class="hint">
            只读展示该角色在商城侧的能力；Phase 1 不可编辑勾选。图例：
            <span class="perm-yes">✓</span> 有权限
            <span class="perm-no">—</span> 无权限
          </p>
          <div v-for="group in matrixGroups" :key="group.title" class="matrix-group">
            <div class="matrix-group__title">{{ group.title }}</div>
            <table class="matrix-table">
              <tbody>
                <tr v-for="item in group.items" :key="item.code">
                  <td class="matrix-table__label">{{ item.label }}</td>
                  <td class="matrix-table__state">
                    <span :class="item.granted ? 'perm-yes' : 'perm-no'">
                      {{ item.granted ? '✓' : '—' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="assignOpen" title="分配成员" width="480px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="选择成员" required>
          <el-select
            v-model="form.user_id"
            filterable
            placeholder="搜索姓名 / 手机"
            style="width: 100%"
          >
            <el-option
              v-for="c in candidates"
              :key="c.user_id"
              :label="`${c.display_name} · ${c.phone_masked}`"
              :value="c.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定角色" required>
          <el-select v-model="form.role_code" style="width: 100%">
            <el-option
              v-for="r in enabledRoles"
              :key="r.code"
              :label="`${r.name} (${r.code})`"
              :value="r.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.role_code !== 'admin'" label="店铺范围" required>
          <el-radio-group
            v-model="form.store_scope"
            :disabled="form.role_code === 'shop_clerk'"
          >
            <el-radio value="all">全部店铺</el-radio>
            <el-radio value="selected">指定店铺</el-radio>
          </el-radio-group>
          <el-select
            v-if="form.store_scope === 'selected'"
            v-model="form.store_ids"
            multiple
            :multiple-limit="form.role_code === 'shop_clerk' ? 1 : 0"
            placeholder="选择店铺"
            style="width: 100%; margin-top: 8px"
          >
            <el-option
              v-for="s in stores"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignOpen = false">取消</el-button>
        <el-button type="primary" :loading="assigning" @click="confirmAssign">确认分配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.a16 .hd {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.a16 h3 {
  margin: 0;
  font-size: 18px;
}
.crumb {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.crumb b {
  color: #1677ff;
  font-weight: 600;
}
.two {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 14px;
}
@media (max-width: 900px) {
  .two {
    grid-template-columns: 1fr;
  }
}
.role-list {
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
}
.side-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}
.role-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  padding: 8px;
  border-radius: 6px;
  margin-bottom: 4px;
  cursor: pointer;
}
.role-item.on {
  background: #e6f4ff;
  color: #1677ff;
  font-weight: 500;
}
.role-item.dim {
  opacity: 0.55;
}
.role-item .name {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.role-item .meta {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
}
.right {
  min-width: 0;
}
.right-hd {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--el-border-color);
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.subtabs {
  display: flex;
  gap: 0;
  font-size: 12px;
}
.subtabs button {
  border: none;
  background: transparent;
  padding: 6px 12px;
  color: #666;
  cursor: pointer;
}
.subtabs button.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom: 2px solid #1677ff;
  margin-bottom: -1px;
}
.role-actions {
  margin-left: auto;
  font-size: 11px;
  color: #666;
}
.hint {
  font-size: 12px;
  color: #64748b;
  line-height: 1.7;
  margin: 0 0 8px;
}
.matrix {
  padding: 10px;
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
}
.matrix-group + .matrix-group {
  margin-top: 12px;
}
.matrix-group__title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}
.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.matrix-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.matrix-table__label {
  color: #334155;
}
.matrix-table__state {
  width: 56px;
  text-align: center;
}
.perm-yes {
  color: #389e0d;
  font-weight: 700;
}
.perm-no {
  color: #bfbfbf;
  font-weight: 600;
}
code {
  font-size: 11px;
}
</style>
