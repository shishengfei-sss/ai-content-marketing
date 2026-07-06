<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../api/client'

const loading = ref(false)
const tenants = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQ = ref('')

const membersVisible = ref(false)
const membersLoading = ref(false)
const members = ref([])
const currentTenant = ref(null)

const transferVisible = ref(false)
const transferTarget = ref(null)
const transferring = ref(false)

const resetVisible = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')
const resetting = ref(false)

async function loadTenants() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    const { data } = await adminApi.listTenants(params)
    tenants.value = data.items ?? []
    total.value = data.total ?? 0
  } catch (e) {
    if (isBenignEmptyError(e)) {
      tenants.value = []
      total.value = 0
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchQ.value = ''
  page.value = 1
  loadTenants()
}

function handlePageChange(p) {
  page.value = p
  loadTenants()
}

function formatAdmins(row) {
  if (!row.admin_summaries?.length) return '—'
  return row.admin_summaries
    .map((a) => a.phone || a.display_name || '—')
    .join('、')
}

async function openMembers(row) {
  currentTenant.value = row
  membersVisible.value = true
  membersLoading.value = true
  try {
    const { data } = await adminApi.listTenantMembers(row.id)
    members.value = data
  } catch (e) {
    if (isBenignEmptyError(e)) {
      members.value = []
    } else {
      ElMessage.error(e.message || '加载成员失败')
      members.value = []
    }
  } finally {
    membersLoading.value = false
  }
}

function openTransferDialog(member) {
  if (member.role_code === 'admin') {
    ElMessage.info('该成员已是企业管理员')
    return
  }
  if (!member.user_active || !member.membership_active) {
    ElMessage.warning('目标成员或账号未启用')
    return
  }
  transferTarget.value = member
  transferVisible.value = true
}

async function confirmTransfer() {
  if (!currentTenant.value || !transferTarget.value) return
  transferring.value = true
  try {
    await adminApi.transferTenantAdmin(
      currentTenant.value.id,
      transferTarget.value.user_id,
    )
    ElMessage.success('管理员已转移')
    transferVisible.value = false
    await openMembers(currentTenant.value)
    await loadTenants()
  } catch (e) {
    ElMessage.error(e.message || '转移失败')
  } finally {
    transferring.value = false
  }
}

function openResetDialog(member) {
  resetTarget.value = member
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
    await adminApi.resetUserPassword(resetTarget.value.user_id, resetPassword.value)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch (e) {
    ElMessage.error(e.message || '重置失败')
  } finally {
    resetting.value = false
  }
}

async function handleTransferConfirm() {
  const oldAdmin = members.value.find((m) => m.role_code === 'admin')
  const newAdmin = transferTarget.value
  try {
    await ElMessageBox.confirm(
      `将企业「${currentTenant.value?.name}」管理员由「${oldAdmin?.phone || oldAdmin?.display_name || '—'}」转移给「${newAdmin?.phone || newAdmin?.display_name}」。原管理员将变为编辑角色。`,
      '转移管理员',
      { type: 'warning', confirmButtonText: '确认转移', cancelButtonText: '取消' },
    )
    await confirmTransfer()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作取消')
  }
}

onMounted(loadTenants)
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="公司名 / 信用代码 / 管理员手机号"
        style="width: 280px"
        clearable
        @keyup.enter="loadTenants"
        @clear="loadTenants"
      />
      <el-button type="primary" @click="loadTenants">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="tenants" stripe style="margin-top: 16px">
      <el-table-column prop="name" label="公司名" min-width="140" />
      <el-table-column prop="credit_code" label="信用代码" width="180">
        <template #default="{ row }">{{ row.credit_code || '—' }}</template>
      </el-table-column>
      <el-table-column prop="industry_code" label="行业" width="100" />
      <el-table-column prop="member_count" label="成员数" width="80" align="center" />
      <el-table-column label="管理员" min-width="140">
        <template #default="{ row }">{{ formatAdmins(row) }}</template>
      </el-table-column>
      <el-table-column label="平台额度" width="120">
        <template #default="{ row }">{{ row.quota_used }} / {{ row.quota_limit }}</template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="170">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openMembers(row)">
            成员
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <el-drawer
      v-model="membersVisible"
      :title="currentTenant ? `${currentTenant.name} · 成员` : '成员'"
      size="640px"
    >
      <el-table v-loading="membersLoading" :data="members" stripe>
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="display_name" label="姓名" width="100" />
        <el-table-column prop="role_name" label="企业角色" width="110" />
        <el-table-column label="成员状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.membership_active ? 'success' : 'info'" size="small">
              {{ row.membership_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号" width="80">
          <template #default="{ row }">
            <el-tag :type="row.user_active ? 'success' : 'danger'" size="small">
              {{ row.user_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="加入时间" min-width="160">
          <template #default="{ row }">
            {{ new Date(row.joined_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.role_code !== 'admin'"
              type="primary"
              link
              size="small"
              @click="openTransferDialog(row)"
            >
              设为管理员
            </el-button>
            <el-button type="primary" link size="small" @click="openResetDialog(row)">
              重置密码
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="transferVisible" title="转移管理员" width="480px">
      <p class="dialog-tip">
        确认将「{{ transferTarget?.phone || transferTarget?.display_name }}」设为企业管理员？原管理员将降为编辑。
      </p>
      <template #footer>
        <el-button @click="transferVisible = false">取消</el-button>
        <el-button type="primary" :loading="transferring" @click="handleTransferConfirm">
          确认转移
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="420px">
      <p class="dialog-tip">
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

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.dialog-tip {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
</style>
