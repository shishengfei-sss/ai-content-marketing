<script setup>
/**
 * P08 角色与编码。对照 06-平台端UI.html #p08 · #p08a · #p08f
 * 账号生命周期在主站「账号管理」；本页：内置角色只读 + 编码规则。
 * 缺口：站内信未接通。保存商城权限的变更记录在主站账号管理抽屉。
 * 展示名原文：平台超管 / 日常运营 / 商家管家 / 财务结算
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'

const route = useRoute()
const router = useRouter()
const activeTab = ref(route.query.tab === 'codes' ? 'codes' : 'roles')
const loading = ref(false)
const saving = ref('')
const rules = ref([])
const roles = ref([])
const permDrawer = ref(false)
const permRole = ref(null)

const CODE_COL_STORAGE = 'shop-p08-code-columns'
const CODE_COLS = [
  { key: 'entity_label', label: '实体', locked: true, defaultVisible: true },
  { key: 'entity_type', label: 'entity_type', locked: true, defaultVisible: true },
  { key: 'prefix', label: '前缀', defaultVisible: true },
  { key: 'date_format', label: '日期段', defaultVisible: true },
  { key: 'seq_width', label: '序号宽度', defaultVisible: true },
  { key: 'reset_period', label: '重置周期', defaultVisible: true },
  { key: 'inherit_parent_code', label: '继承父 code', defaultVisible: true },
  { key: 'enabled', label: '启用', locked: true, defaultVisible: true },
  { key: 'preview', label: '预览', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
]
const {
  visibleKeys: visibleCols,
  columnDialogVisible: colDialog,
  columnDraft: colDraft,
  openColumnSettings: openCol,
  saveColumnSettings: saveCol,
} = useListColumnSettings(CODE_COLS, CODE_COL_STORAGE)
const page = ref(1)
const pageSize = ref(20)

const RESET_PERIOD_OPTIONS = [
  { value: 'once', label: '永不' },
  { value: 'daily', label: '每日' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
  { value: 'yearly', label: '每年' },
]
const DATE_FORMAT_OPTIONS = [
  { value: '%Y%m%d', label: '年月日' },
  { value: '%Y%m', label: '年月' },
  { value: '%Y', label: '年' },
  { value: '%G%V', label: 'ISO 年周' },
  { value: '', label: '不含' },
]

const pagedRules = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rules.value.slice(start, start + pageSize.value)
})

function downloadCsv(filename, header, rows) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const blob = new Blob(['\ufeff' + [header.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\n')], {
    type: 'text/csv;charset=utf-8',
  })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
function exportList() {
  const dateLabel = (v) => DATE_FORMAT_OPTIONS.find((o) => o.value === (v || ''))?.label || v || '不含'
  const resetLabel = (v) => RESET_PERIOD_OPTIONS.find((o) => o.value === v)?.label || v
  downloadCsv(
    '编码规则.csv',
    ['实体', 'entity_type', '前缀', '日期段', '序号宽度', '重置周期', '启用', '预览'],
    rules.value.map((r) => [
      r.entity_label,
      r.entity_type,
      r.prefix,
      dateLabel(r.date_format),
      r.seq_width,
      resetLabel(r.reset_period),
      r.enabled ? '是' : '否',
      r.preview,
    ]),
  )
}

function isoWeekPart(now) {
  const tmp = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()))
  const dayNum = tmp.getUTCDay() || 7
  tmp.setUTCDate(tmp.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((tmp - yearStart) / 86400000 + 1) / 7)
  return `${tmp.getUTCFullYear()}${String(week).padStart(2, '0')}`
}

function localPreview(row) {
  const w = Math.max(1, Math.min(Number(row.seq_width) || 3, 8))
  const seq = String(row.next_seq || 1).padStart(w, '0')
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  let datePart = ''
  if (row.date_format === '%Y%m%d') datePart = `${y}${m}${d}`
  else if (row.date_format === '%Y%m') datePart = `${y}${m}`
  else if (row.date_format === '%Y') datePart = String(y)
  else if (row.date_format === '%G%V') datePart = isoWeekPart(now)
  return `${row.prefix || ''}${datePart}${seq}${row.suffix || ''}`
}

function touchPreview(row) {
  row.preview = localPreview(row)
}

async function refreshPreview(row) {
  try {
    const { data } = await adminApi.previewShopNumberRule(row.entity_type, {
      prefix: row.prefix,
      date_format: row.date_format || '',
      seq_width: row.seq_width,
      reset_period: row.reset_period,
      suffix: row.suffix || '',
    })
    row.preview = data.code
    if (data.next_seq) row.next_seq = data.next_seq
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  }
}

async function loadRoles() {
  try {
    const { data } = await adminApi.getShopPermissionCatalog()
    roles.value = data.roles || []
  } catch (e) {
    ElMessage.error(e.message || '加载角色失败')
  }
}

async function loadRules() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopNumberRules()
    rules.value = (data.items || []).map((r) => ({ ...r }))
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save(row) {
  saving.value = row.entity_type
  try {
    const { data } = await adminApi.updateShopNumberRule(row.entity_type, {
      prefix: row.prefix,
      suffix: row.suffix || '',
      date_format: row.date_format || '',
      seq_width: row.seq_width,
      reset_period: row.reset_period,
      inherit_parent_code: !!row.inherit_parent_code,
      separator: row.separator || '.',
      enabled: !!row.enabled,
    })
    Object.assign(row, data)
    ElMessage.success(`${row.entity_label || row.entity_type} 已保存`)
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = ''
  }
}

async function resetDefaults() {
  try {
    await ElMessageBox.confirm('将全部实体规则恢复为迁移种子默认值？', '恢复全部默认', {
      type: 'warning',
    })
    const { data } = await adminApi.resetShopNumberRules()
    rules.value = data.items || []
    ElMessage.success('已恢复默认')
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

function onTab(name) {
  activeTab.value = name
  router.replace({ query: { ...route.query, tab: name === 'roles' ? 'roles' : 'codes' } })
}

function openPerm(role) {
  permRole.value = role
  permDrawer.value = true
}

function bindAccounts(role) {
  const shopRole = role.code || 'superadmin'
  router.push({ path: '/admin/users', query: { shop_role: shopRole } })
}

const csRole = computed(() => roles.value.find((r) => r.code === 'platform_shop_cs'))
const opsRole = computed(() => roles.value.find((r) => r.code === 'platform_shop_ops'))

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === 'codes' || tab === 'roles') activeTab.value = tab
  },
)

onMounted(() => {
  loadRoles()
  loadRules()
})
</script>

<template>
  <div class="page-card" data-testid="shop-roles-codes" v-loading="loading">
    <div class="hd">
      <h3>角色与编码</h3>
      <p class="sub">内置角色只读；运营账号在主站「账号管理」维护。编码规则修改后仅对新增记录生效。</p>
    </div>

    <el-tabs :model-value="activeTab" @tab-change="onTab">
      <el-tab-pane label="角色" name="roles">
        <div class="role-grid">
          <div
            v-for="role in roles"
            :key="role.code_label"
            class="role-card"
            :class="{ highlight: role.code === 'platform_shop_cs' }"
          >
            <div class="role-title">
              {{ role.name }}
              <el-tag size="small" type="success">启用</el-tag>
            </div>
            <div class="role-code"><code>{{ role.code_label }}</code></div>
            <div class="role-summary">{{ role.summary }}</div>
            <div class="role-actions">
              <el-button link type="primary" @click="openPerm(role)">查看权限</el-button>
              <el-button link type="primary" @click="bindAccounts(role)">绑定账号 ({{ role.bound_count }})</el-button>
            </div>
          </div>
        </div>

        <div v-if="csRole" class="matrix-block">
          <div class="matrix-title">商家管家 · 默认权限（platform_shop_cs）</div>
          <el-table :data="csRole.matrix" border size="small">
            <el-table-column prop="code" label="权限码" min-width="280">
              <template #default="{ row }"><code>{{ row.code }}</code></template>
            </el-table-column>
            <el-table-column prop="label" label="说明" min-width="200" />
            <el-table-column label="默认" width="80" align="center">
              <template #default="{ row }">{{ row.granted ? '✓' : '—' }}</template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="opsRole" class="matrix-block">
          <div class="matrix-title">日常运营 · 默认权限（勾选只读示意；绑定时可微调）</div>
          <el-table :data="opsRole.matrix" border size="small">
            <el-table-column prop="code" label="权限码" min-width="280">
              <template #default="{ row }"><code>{{ row.code }}</code></template>
            </el-table-column>
            <el-table-column prop="label" label="说明" min-width="200" />
            <el-table-column label="默认" width="80" align="center">
              <template #default="{ row }">{{ row.granted ? '✓' : '—' }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="编码规则" name="codes">
        <p class="hint">为商家、申请单、套餐、类目等配置自动编号；修改后仅对新增记录生效。实体类型内置固定，不可新增行。</p>
        <div class="toolbar">
          <span class="spacer" />
          <el-button @click="openCol">列设置</el-button>
          <el-button @click="exportList">导出</el-button>
        </div>
        <el-table :data="pagedRules" border size="small">
          <template v-for="colKey in visibleCols" :key="colKey">
          <el-table-column v-if="colKey === 'entity_label'" prop="entity_label" label="实体" width="110" />
          <el-table-column v-if="colKey === 'entity_type'" prop="entity_type" label="entity_type" min-width="150">
            <template #default="{ row }"><code>{{ row.entity_type }}</code></template>
          </el-table-column>
          <el-table-column v-if="colKey === 'prefix'" label="前缀" width="100">
            <template #default="{ row }">
              <el-input v-model="row.prefix" size="small" @change="touchPreview(row)" />
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'date_format'" label="日期段" width="130">
            <template #default="{ row }">
              <el-select v-model="row.date_format" size="small" style="width: 100%" @change="touchPreview(row)">
                <el-option
                  v-for="o in DATE_FORMAT_OPTIONS"
                  :key="String(o.value)"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'seq_width'" label="序号宽度" width="90">
            <template #default="{ row }">
              <el-input-number v-model="row.seq_width" :min="1" :max="8" size="small" controls-position="right" @change="touchPreview(row)" />
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'reset_period'" label="重置周期" width="120">
            <template #default="{ row }">
              <el-select v-model="row.reset_period" size="small" style="width: 100%" @change="touchPreview(row)">
                <el-option
                  v-for="o in RESET_PERIOD_OPTIONS"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'inherit_parent_code'" label="继承父 code" width="110" align="center">
            <template #default="{ row }">
              <el-checkbox
                v-if="row.entity_type === 'shop_category'"
                v-model="row.inherit_parent_code"
              />
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'enabled'" label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'preview'" label="预览" min-width="140">
            <template #default="{ row }"><code>{{ row.preview }}</code></template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="refreshPreview(row)">刷新预览</el-button>
              <el-button
                link
                type="primary"
                :loading="saving === row.entity_type"
                @click="save(row)"
              >
                保存
              </el-button>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="ft">
          <el-button @click="resetDefaults">恢复全部默认</el-button>
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="rules.length"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            background
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="permDrawer" :title="permRole ? `查看权限 · ${permRole.name}` : '查看权限'" size="480px">
      <el-table v-if="permRole" :data="permRole.matrix" border size="small">
        <el-table-column prop="code" label="权限码" min-width="220">
          <template #default="{ row }"><code>{{ row.code }}</code></template>
        </el-table-column>
        <el-table-column prop="label" label="说明" min-width="140" />
        <el-table-column label="默认" width="70" align="center">
          <template #default="{ row }">{{ row.granted ? '✓' : '—' }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="permDrawer = false">关闭</el-button>
      </template>
    </el-drawer>

    <CrmColumnSettingsDialog
      v-model:visible="colDialog"
      v-model:columns="colDraft"
      @save="saveCol"
    />
  </div>
</template>

<style scoped>
.page-card {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
}
.hd h3 {
  margin: 0 0 4px;
  font-size: 16px;
}
.sub,
.hint {
  margin: 0 0 12px;
  color: #666;
  font-size: 13px;
}
.role-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 8px 0 16px;
}
.role-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}
.role-card.highlight {
  border-color: #91caff;
  background: #e6f4ff;
}
.role-title {
  font-weight: 700;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.role-code {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}
.role-summary {
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}
.role-actions {
  margin-top: 10px;
}
.matrix-block {
  margin-bottom: 16px;
}
.matrix-title {
  font-size: 13px;
  font-weight: 600;
  margin: 8px 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.spacer {
  flex: 1;
}
.ft {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.col-row {
  margin-bottom: 6px;
}
code {
  font-size: 12px;
}
</style>
