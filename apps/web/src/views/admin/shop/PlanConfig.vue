<script setup>
/**
 * P10 套餐配置。对照 PRD 06-平台端UI.html #p10-dict · #p10f · #p10a · #p10e · #p10b · #p10g
 * · #p10-plans · #p10h · #p10i · #p10j · #p10k · #p10c · #p10d
 * 缺口：站内信未接通。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../../api/client'
import CrmColumnSettingsDialog from '../../../components/crm/CrmColumnSettingsDialog.vue'
import { useListColumnSettings } from '../../../composables/useListColumnSettings'
import { useAuthStore } from '../../../stores/auth'
import { formatDateTime } from '../../../utils/datetime'

const router = useRouter()
const auth = useAuthStore()
const canManage = computed(() => auth.hasPlatformShopPermission('platform.shop.plan.manage'))

const tab = ref('features')
const loading = ref(false)
const submitting = ref(false)

const featureTree = ref([])
const featureFlat = ref([])
const featView = ref('tree')
const featQ = ref('')
const featNode = ref('')
const featCat = ref('')
const featValType = ref('')
const featStatus = ref('')
const featAdv = ref(false)
const featPage = ref(1)
const featPageSize = ref(20)

const plans = ref([])
const planTotal = ref(0)
const planPage = ref(1)
const planPageSize = ref(20)
const planQ = ref('')
const planType = ref('')
const planPublished = ref('')
const planAdv = ref(false)
const planReplaceGroup = ref('')

const FEAT_COLS = [
  { key: 'name', label: '名称 / 编码', locked: true, defaultVisible: true },
  { key: 'node_type', label: '节点', defaultVisible: true },
  { key: 'category', label: '分类', defaultVisible: true },
  { key: 'value_type', label: '类型', defaultVisible: true },
  { key: 'aggregate_mode', label: '叠加模式', defaultVisible: true },
  { key: 'usage_period', label: '周期', defaultVisible: true },
  { key: 'meter_key', label: '埋点标识', defaultVisible: true },
  { key: 'status', label: '状态', locked: true, defaultVisible: true },
  { key: 'updated_at', label: '更新时间', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'created_by', label: '创建人', defaultVisible: false },
  { key: 'sort_order', label: '排序号', defaultVisible: false },
  { key: 'parent_path', label: '父分组路径', defaultVisible: false },
]
const PLAN_COLS = [
  { key: 'name', label: '套餐', locked: true, defaultVisible: true },
  { key: 'stackable', label: '可叠加', defaultVisible: true },
  { key: 'replace_group', label: '互斥组', defaultVisible: true },
  { key: 'billing_period', label: '周期', defaultVisible: true },
  { key: 'price', label: '售价', defaultVisible: true },
  { key: 'shops', label: '店铺', defaultVisible: true },
  { key: 'products', label: '商品', defaultVisible: true },
  { key: 'review', label: '每日提审', defaultVisible: true },
  { key: 'doudian', label: '抖店', defaultVisible: true },
  { key: 'entity', label: '适用主体', defaultVisible: true },
  { key: 'public', label: '上架', locked: true, defaultVisible: true },
  { key: 'updated_at', label: '更新时间', defaultVisible: true },
  { key: 'ops', label: '操作', locked: true, defaultVisible: true },
  { key: 'code', label: '套餐编码', defaultVisible: false },
  { key: 'created_by', label: '创建人', defaultVisible: false },
  { key: 'updated_by', label: '最后修改人', defaultVisible: false },
]
const {
  visibleKeys: featVisibleKeys,
  columnDialogVisible: featColDialog,
  columnDraft: featColDraft,
  openColumnSettings: openFeatCol,
  saveColumnSettings: saveFeatCol,
} = useListColumnSettings(FEAT_COLS, 'shop-plan-feat-columns')
const {
  visibleKeys: planVisibleKeys,
  columnDialogVisible: planColDialog,
  columnDraft: planColDraft,
  openColumnSettings: openPlanCol,
  saveColumnSettings: savePlanCol,
} = useListColumnSettings(PLAN_COLS, 'shop-plan-plan-columns')

const NODE_LABEL = { group: '分组', leaf: '子功能' }
const CAT_LABEL = { quota: '配额', usage: '用量', feature: '功能' }
const VAL_LABEL = { int: '存量 int', usage: '周期次数', bool: '开关', unlimited: '不限量' }
const AGG_LABEL = { max: '取最大值', sum: '累加', any: '任一满足' }
const PERIOD_LABEL = { daily: '每日', monthly: '每月', subscription: '按订阅周期', yearly: '年' }
const BILL_LABEL = { yearly: '年', monthly: '月', custom_days: '自定义' }
const ENTITY_LABEL = { personal: '个人', individual_business: '个体', enterprise: '企业' }

const groupDlg = ref(false)
const leafDlg = ref(false)
const featEditDlg = ref(false)
const featViewOnly = ref(false)
const deactDlg = ref(false)
const deactTarget = ref(null)
const deactRemove = ref(false)
const planDlg = ref(false)
const planMode = ref('create')
const planReadOnly = ref(false)
const currentFeat = ref(null)
const currentPlan = ref(null)
const pickerLeaves = ref([])

const groupForm = reactive({
  code_source: 'auto',
  code: '',
  name: '',
  parent_id: null,
  sort_order: 10,
  description: '',
})
const leafForm = reactive({
  code_source: 'auto',
  code: '',
  name: '',
  parent_id: null,
  category: 'quota',
  value_type: 'int',
  aggregate_mode: 'max',
  sort_order: 10,
  usage_period: '',
  meter_key: '',
  unit: '',
  description: '',
})
const featEditForm = reactive({
  name: '',
  parent_id: null,
  aggregate_mode: 'sum',
  sort_order: 0,
  usage_period: '',
  meter_key: '',
  unit: '',
  description: '',
  sync_to_templates: false,
  uniform_on: false,
  uniform_limit_value: 0,
})
const planForm = reactive({
  plan_type: 'main',
  code_source: 'auto',
  code: '',
  name: '',
  replace_group: 'main',
  billing_period: 'yearly',
  price_yuan: 0,
  sort_order: 10,
  allowed_entity_types: ['personal', 'individual_business', 'enterprise'],
  publish_after_save: false,
  description: '',
  feature_values: {},
})
const pickerQ = ref('')
const pickerCat = ref('')
const pickerGroup = ref('')
const pickerSelectedOnly = ref(false)

function flattenTree(nodes, acc = []) {
  for (const n of nodes || []) {
    acc.push(n)
    if (n.children?.length) flattenTree(n.children, acc)
  }
  return acc
}

const groups = computed(() => featureFlat.value.filter((f) => f.node_type === 'group'))
const filteredFeatRows = computed(() => {
  const src = featView.value === 'tree' ? featureTree.value : featureFlat.value
  const walk = (rows) => {
    const out = []
    for (const r of rows || []) {
      const kids = walk(r.children || [])
      const hit =
        (!featQ.value || `${r.name}${r.code}`.toLowerCase().includes(featQ.value.trim().toLowerCase())) &&
        (!featNode.value || r.node_type === featNode.value) &&
        (!featCat.value || r.category === featCat.value) &&
        (!featValType.value || r.value_type === featValType.value) &&
        (featStatus.value === '' || (featStatus.value === '1' ? r.is_active : !r.is_active))
      if (featView.value === 'tree') {
        if (hit || kids.length) out.push({ ...r, children: kids })
      } else if (hit) out.push(r)
    }
    return out
  }
  return walk(src)
})
const pagedFeatRows = computed(() => {
  if (featView.value === 'tree') return filteredFeatRows.value
  const start = (featPage.value - 1) * featPageSize.value
  return filteredFeatRows.value.slice(start, start + featPageSize.value)
})
const featTotal = computed(() =>
  featView.value === 'tree' ? flattenTree(filteredFeatRows.value).length : filteredFeatRows.value.length,
)

const pickerVisibleLeaves = computed(() => {
  return pickerLeaves.value.filter((f) => {
    if (pickerQ.value && !`${f.name}${f.code}`.toLowerCase().includes(pickerQ.value.trim().toLowerCase())) {
      return false
    }
    if (pickerCat.value && f.category !== pickerCat.value) return false
    if (pickerGroup.value && String(f.parent_id) !== String(pickerGroup.value)) return false
    if (pickerSelectedOnly.value && planForm.feature_values[f.code] === undefined) return false
    return true
  })
})
const pickerGroupsView = computed(() => {
  const by = {}
  for (const f of pickerVisibleLeaves.value) {
    const g = groups.value.find((x) => x.id === f.parent_id)
    const key = g?.id || 'none'
    if (!by[key]) by[key] = { group: g || { name: '未分组', id: 'none' }, leaves: [] }
    by[key].leaves.push(f)
  }
  return Object.values(by)
})
const selectedCount = computed(() => Object.keys(planForm.feature_values).length)

function centsYuan(c) {
  return ((Number(c) || 0) / 100).toFixed(2)
}
function fmtVal(v) {
  if (v === true) return '✓'
  if (v === 'unlimited') return '∞'
  if (v === false || v == null || v === '') return '—'
  return v
}
function planBag(row, code) {
  return row?.quotas?.[code] ?? row?.usage_limits?.[code] ?? row?.features?.[code]
}
function entityText(row) {
  const arr = row?.allowed_entity_types || []
  if (!arr.length || arr.length >= 3) return '全类型'
  return arr.map((x) => ENTITY_LABEL[x] || x).join('、')
}
function refsForCode(code) {
  return plans.value.filter((p) => planBag(p, code) !== undefined && planBag(p, code) !== null)
}

async function loadFeatures() {
  const { data } = await adminApi.listShopFeatureDictionary({ tree: true })
  featureTree.value = Array.isArray(data) ? data : []
  const { data: flat } = await adminApi.listShopFeatureDictionary({})
  featureFlat.value = Array.isArray(flat) ? flat : []
}

async function loadPlans() {
  const { data } = await adminApi.listShopPlanTemplates({
    page: planPage.value,
    page_size: planPageSize.value,
    q: planQ.value.trim() || undefined,
    plan_type: planType.value || undefined,
    published: planPublished.value === '' ? undefined : planPublished.value === '1',
    replace_group: planReplaceGroup.value || undefined,
    is_active: true,
  })
  plans.value = data.items || []
  planTotal.value = data.total || 0
}

async function load() {
  loading.value = true
  try {
    await Promise.all([loadFeatures(), loadPlans()])
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function downloadCsv(filename, header, rows) {
  const lines = [header.join(','), ...rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))]
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
function exportFeat() {
  const rows = flattenTree(filteredFeatRows.value)
  downloadCsv(
    '功能字典.csv',
    ['名称', '编码', '节点', '分类', '类型', '叠加模式', '周期', '埋点标识', '状态'],
    rows.map((r) => [
      r.name,
      r.code,
      NODE_LABEL[r.node_type] || r.node_type,
      CAT_LABEL[r.category] || r.category || '',
      VAL_LABEL[r.value_type] || r.value_type || '',
      AGG_LABEL[r.aggregate_mode] || r.aggregate_mode || '',
      PERIOD_LABEL[r.usage_period] || r.usage_period || '',
      r.meter_key || '',
      r.is_active ? '启用' : '停用',
    ]),
  )
}
function exportPlans() {
  downloadCsv(
    '套餐模板.csv',
    ['套餐', '编码', '可叠加', '互斥组', '周期', '售价', '上架'],
    plans.value.map((r) => [
      r.name,
      r.code,
      r.stackable ? '是' : '否',
      r.replace_group || '',
      BILL_LABEL[r.billing_period] || r.billing_period,
      centsYuan(r.price_cents),
      r.is_public ? '是' : '否',
    ]),
  )
}

function resetGroup() {
  Object.assign(groupForm, { code_source: 'auto', code: '', name: '', parent_id: null, sort_order: 10, description: '' })
}
function resetLeaf(parentId = null) {
  Object.assign(leafForm, {
    code_source: 'auto',
    code: '',
    name: '',
    parent_id: parentId,
    category: 'quota',
    value_type: 'int',
    aggregate_mode: 'max',
    sort_order: 10,
    usage_period: '',
    meter_key: '',
    unit: '',
    description: '',
  })
}

async function refreshFeatureCode(form) {
  if (form.code_source !== 'auto') return
  try {
    const { data } = await adminApi.previewShopFeatureCode()
    form.code = data.code || ''
  } catch {
    /* ignore */
  }
}
async function refreshPlanCode() {
  if (planForm.code_source !== 'auto' || planMode.value !== 'create') return
  try {
    const { data } = await adminApi.previewShopPlanCode()
    planForm.code = data.code || ''
  } catch {
    /* ignore */
  }
}
function goSubscriptions(plan) {
  const code = plan?.code
  router.push(code ? `/admin/shop/subscriptions?plan_code=${encodeURIComponent(code)}` : '/admin/shop/subscriptions')
}
function auditText(name, at) {
  const who = name || '—'
  return at ? `${who} · ${formatDateTime(at)}` : who
}

watch(
  () => leafForm.category,
  (c) => {
    if (c === 'feature') {
      leafForm.value_type = 'bool'
      leafForm.aggregate_mode = 'any'
    } else if (c === 'usage') {
      leafForm.value_type = 'usage'
      leafForm.aggregate_mode = 'sum'
      leafForm.usage_period = leafForm.usage_period || 'daily'
    } else if (c === 'quota' && leafForm.value_type === 'bool') {
      leafForm.value_type = 'int'
      leafForm.aggregate_mode = 'max'
    }
  },
)
watch(
  () => leafForm.value_type,
  (t) => {
    if (t === 'bool') leafForm.aggregate_mode = 'any'
  },
)

function openGroup(row = null) {
  currentFeat.value = row
  if (row) {
    Object.assign(groupForm, {
      code_source: 'manual',
      code: row.code,
      name: row.name,
      parent_id: row.parent_id,
      sort_order: row.sort_order,
      description: row.description || '',
    })
  } else {
    resetGroup()
    refreshFeatureCode(groupForm)
  }
  groupDlg.value = true
}
function openLeaf(parentId = null) {
  currentFeat.value = null
  resetLeaf(parentId)
  refreshFeatureCode(leafForm)
  leafDlg.value = true
}
function openFeatEdit(row, readOnly = false) {
  currentFeat.value = row
  featViewOnly.value = readOnly || !row.is_active
  Object.assign(featEditForm, {
    name: row.name,
    parent_id: row.parent_id,
    aggregate_mode: row.aggregate_mode || 'sum',
    sort_order: row.sort_order,
    usage_period: row.usage_period || '',
    meter_key: row.meter_key || '',
    unit: row.unit || '',
    description: row.description || '',
    sync_to_templates: false,
    uniform_on: false,
    uniform_limit_value: 0,
  })
  featEditDlg.value = true
}

async function saveGroup() {
  if (!groupForm.name.trim()) {
    ElMessage.error('请填写分组名称')
    return
  }
  submitting.value = true
  try {
    if (currentFeat.value) {
      await adminApi.updateShopFeature(currentFeat.value.id, {
        name: groupForm.name.trim(),
        parent_id: groupForm.parent_id || null,
        sort_order: groupForm.sort_order,
        description: groupForm.description || undefined,
      })
    } else {
      await adminApi.createShopFeature({
        node_type: 'group',
        name: groupForm.name.trim(),
        code: groupForm.code_source === 'manual' ? groupForm.code.trim() || undefined : undefined,
        parent_id: groupForm.parent_id || null,
        sort_order: groupForm.sort_order,
        description: groupForm.description || undefined,
      })
    }
    ElMessage.success('已保存')
    groupDlg.value = false
    await loadFeatures()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function saveLeaf() {
  if (!leafForm.name.trim()) {
    ElMessage.error('请填写名称')
    return
  }
  if (!leafForm.parent_id) {
    ElMessage.error('请选择所属分组')
    return
  }
  submitting.value = true
  try {
    await adminApi.createShopFeature({
      node_type: 'leaf',
      name: leafForm.name.trim(),
      code: leafForm.code_source === 'manual' ? leafForm.code.trim() || undefined : undefined,
      parent_id: leafForm.parent_id,
      category: leafForm.category,
      value_type: leafForm.value_type,
      aggregate_mode: leafForm.aggregate_mode,
      sort_order: leafForm.sort_order,
      usage_period: leafForm.value_type === 'usage' ? leafForm.usage_period || undefined : undefined,
      meter_key: leafForm.value_type === 'usage' ? leafForm.meter_key || undefined : undefined,
      unit: leafForm.unit || undefined,
      description: leafForm.description || undefined,
    })
    ElMessage.success('已保存')
    leafDlg.value = false
    await loadFeatures()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function saveFeatEdit() {
  if (!featEditForm.name.trim()) {
    ElMessage.error('请填写名称')
    return
  }
  submitting.value = true
  try {
    await adminApi.updateShopFeature(currentFeat.value.id, {
      name: featEditForm.name.trim(),
      parent_id: featEditForm.parent_id || undefined,
      aggregate_mode: featEditForm.aggregate_mode,
      sort_order: featEditForm.sort_order,
      usage_period: featEditForm.usage_period || undefined,
      meter_key: featEditForm.meter_key || undefined,
      unit: featEditForm.unit || undefined,
      description: featEditForm.description || undefined,
      sync_to_templates: featEditForm.sync_to_templates,
      uniform_limit_value: featEditForm.sync_to_templates && featEditForm.uniform_on ? featEditForm.uniform_limit_value : undefined,
    })
    ElMessage.success('已保存')
    featEditDlg.value = false
    await Promise.all([loadFeatures(), loadPlans()])
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

function openDeact(row) {
  deactTarget.value = row
  deactRemove.value = false
  deactDlg.value = true
}
async function confirmDeact() {
  submitting.value = true
  try {
    await adminApi.deactivateShopFeature(deactTarget.value.id, { remove_from_templates: deactRemove.value })
    ElMessage.success('已停用')
    deactDlg.value = false
    await Promise.all([loadFeatures(), loadPlans()])
  } catch (e) {
    ElMessage.error(e.message || '停用失败')
  } finally {
    submitting.value = false
  }
}
async function confirmActivate(row) {
  try {
    await ElMessageBox.confirm(
      '新建/编辑套餐模板时可再次勾选；不自动加回任何已有模板；已购权益不变。',
      `启用「${row.name}」？`,
      { confirmButtonText: '确认启用', type: 'success' },
    )
    await adminApi.activateShopFeature(row.id)
    ElMessage.success('已启用')
    await loadFeatures()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

async function loadPickerLeaves() {
  const { data } = await adminApi.listShopFeatureDictionary({ node_type: 'leaf', is_active: true })
  pickerLeaves.value = Array.isArray(data) ? data : []
}

function defaultFeatVal(f) {
  if (f.value_type === 'bool') return true
  if (f.value_type === 'unlimited') return 'unlimited'
  return 0
}
function isChecked(code) {
  return planForm.feature_values[code] !== undefined
}
function toggleFeat(f, on) {
  if (on) planForm.feature_values[f.code] = defaultFeatVal(f)
  else delete planForm.feature_values[f.code]
}
function setGroupCheck(leaves, on) {
  leaves.forEach((f) => toggleFeat(f, on))
}
function groupCheckState(leaves) {
  const n = leaves.filter((f) => isChecked(f.code)).length
  return { all: n === leaves.length && n > 0, some: n > 0 && n < leaves.length, n }
}

function openPlan(type, row = null, readOnly = false) {
  planMode.value = row ? 'edit' : 'create'
  planReadOnly.value = readOnly
  currentPlan.value = row
  pickerQ.value = ''
  pickerCat.value = ''
  pickerGroup.value = ''
  pickerSelectedOnly.value = false
  const bags = { ...(row?.quotas || {}), ...(row?.usage_limits || {}), ...(row?.features || {}) }
  Object.assign(planForm, {
    plan_type: row?.plan_type || type,
    code_source: row ? (row.code_source || 'manual') : 'auto',
    code: row?.code || '',
    name: row?.name || '',
    replace_group: row?.replace_group || (type === 'main' ? 'main' : ''),
    billing_period: row?.billing_period || (type === 'addon' ? 'monthly' : 'yearly'),
    price_yuan: row ? Number(centsYuan(row.price_cents)) : 0,
    sort_order: row?.sort_order || 10,
    allowed_entity_types: row?.allowed_entity_types?.length
      ? [...row.allowed_entity_types]
      : ['personal', 'individual_business', 'enterprise'],
    publish_after_save: false,
    description: row?.description || '',
    feature_values: { ...bags },
  })
  loadPickerLeaves()
  if (!row) refreshPlanCode()
  planDlg.value = true
  if (row?.code) {
    adminApi.getShopPlanTemplate(row.code).then(({ data }) => {
      currentPlan.value = data
    }).catch(() => {})
  }
}

async function savePlan() {
  if (!planForm.name.trim()) {
    ElMessage.error('请完善套餐基础信息')
    return
  }
  if (!Object.keys(planForm.feature_values).length) {
    ElMessage.error('请至少配置一项能力')
    return
  }
  submitting.value = true
  try {
    const body = {
      name: planForm.name.trim(),
      billing_period: planForm.billing_period,
      price_cents: Math.round(Number(planForm.price_yuan || 0) * 100),
      sort_order: planForm.sort_order,
      allowed_entity_types: planForm.allowed_entity_types,
      feature_values: planForm.feature_values,
      description: planForm.description || undefined,
    }
    if (planMode.value === 'create') {
      body.plan_type = planForm.plan_type
      if (planForm.code_source === 'manual' && planForm.code.trim()) body.code = planForm.code.trim()
      if (planForm.plan_type === 'main') body.replace_group = planForm.replace_group || 'main'
      body.publish_after_save = planForm.publish_after_save
      await adminApi.createShopPlanTemplate(body)
    } else {
      if (planForm.plan_type === 'main') body.replace_group = planForm.replace_group || 'main'
      await adminApi.updateShopPlanTemplate(currentPlan.value.code, body)
    }
    ElMessage.success('已保存')
    planDlg.value = false
    await loadPlans()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function togglePublish(row) {
  try {
    if (row.is_public) {
      await ElMessageBox.confirm('下架后新开通不可选，已购权益不变。', `下架「${row.name}」？`, {
        confirmButtonText: '确认下架',
        type: 'warning',
      })
      await adminApi.unpublishShopPlanTemplate(row.code)
      ElMessage.success('已下架')
    } else {
      await adminApi.publishShopPlanTemplate(row.code)
      ElMessage.success('已上架')
    }
    await loadPlans()
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message)
  }
}

const planDlgTitle = computed(() => {
  if (planReadOnly.value) return `套餐详情 · ${planForm.name || ''}`
  if (planMode.value === 'edit') return `编辑套餐 · ${planForm.name || ''}`
  return planForm.plan_type === 'addon' ? '新建加购包' : '新建主套餐'
})

watch(tab, (t) => {
  if (t === 'plans') loadPlans()
  if (t === 'features') loadFeatures()
})
watch([planPage, planPageSize], () => loadPlans())

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card" data-testid="shop-plan-config">
    <el-tabs v-model="tab">
      <el-tab-pane label="功能字典" name="features">
        <div class="toolbar">
          <el-input v-model="featQ" clearable placeholder="搜索 code / 名称" style="width: 200px" />
          <el-select v-model="featNode" clearable placeholder="节点" style="width: 110px">
            <el-option label="分组" value="group" />
            <el-option label="子功能" value="leaf" />
          </el-select>
          <el-select v-model="featCat" clearable placeholder="分类" style="width: 110px">
            <el-option label="配额" value="quota" />
            <el-option label="用量" value="usage" />
            <el-option label="功能" value="feature" />
          </el-select>
          <el-select v-model="featValType" clearable placeholder="类型" style="width: 130px">
            <el-option label="存量 int" value="int" />
            <el-option label="周期次数" value="usage" />
            <el-option label="开关" value="bool" />
            <el-option label="不限量" value="unlimited" />
          </el-select>
          <el-button @click="featAdv = !featAdv">高级筛选</el-button>
          <el-select v-if="featAdv" v-model="featStatus" clearable placeholder="状态" style="width: 110px">
            <el-option label="启用" value="1" />
            <el-option label="停用" value="0" />
          </el-select>
          <span class="spacer" />
          <el-button @click="openFeatCol">列设置</el-button>
          <el-select v-model="featView" style="width: 100px">
            <el-option label="树形" value="tree" />
            <el-option label="平铺" value="flat" />
          </el-select>
          <el-button @click="exportFeat">导出</el-button>
          <el-button v-if="canManage" @click="openGroup()">+ 新增分组</el-button>
          <el-button v-if="canManage" type="primary" @click="openLeaf()">+ 新增子功能</el-button>
        </div>
        <el-table
          :data="pagedFeatRows"
          row-key="id"
          border
          stripe
          default-expand-all
          :tree-props="featView === 'tree' ? { children: 'children' } : { children: 'none' }"
        >
          <template v-for="colKey in featVisibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'name'" label="名称 / 编码" min-width="220">
            <template #default="{ row }">
              <b>{{ row.name }}</b>
              <span class="code"> {{ row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'node_type'" label="节点" width="90">
            <template #default="{ row }">{{ NODE_LABEL[row.node_type] || row.node_type }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'category'" label="分类" width="90">
            <template #default="{ row }">{{ CAT_LABEL[row.category] || row.category || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'value_type'" label="类型" width="110">
            <template #default="{ row }">{{ VAL_LABEL[row.value_type] || row.value_type || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'aggregate_mode'" label="叠加模式" width="110">
            <template #default="{ row }">{{ AGG_LABEL[row.aggregate_mode] || row.aggregate_mode || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'usage_period'" label="周期" width="110">
            <template #default="{ row }">{{ PERIOD_LABEL[row.usage_period] || row.usage_period || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'meter_key'" prop="meter_key" label="埋点标识" min-width="140" />
          <el-table-column v-if="colKey === 'status'" label="状态" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'updated_at'" label="更新时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'created_by'" label="创建人" width="110">
            <template #default="{ row }">{{ row.created_by_name || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'sort_order'" prop="sort_order" label="排序号" width="80" />
          <el-table-column v-if="colKey === 'parent_path'" label="父分组路径" min-width="140">
            <template #default="{ row }">{{ row.parent_path || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <template v-if="row.node_type === 'group'">
                <el-button v-if="canManage" link type="primary" @click="openGroup(row)">编辑分组</el-button>
                <el-button v-if="canManage" link type="primary" @click="openLeaf(row.id)">新增子功能</el-button>
              </template>
              <template v-else-if="row.is_active">
                <el-button v-if="canManage" link type="primary" @click="openFeatEdit(row)">编辑</el-button>
                <el-button v-if="canManage" link type="warning" @click="openDeact(row)">停用</el-button>
              </template>
              <template v-else>
                <el-button link type="primary" @click="openFeatEdit(row, true)">查看</el-button>
                <el-button v-if="canManage" link type="success" @click="confirmActivate(row)">启用</el-button>
              </template>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div v-if="featView === 'flat'" class="pager">
          <el-pagination
            v-model:current-page="featPage"
            v-model:page-size="featPageSize"
            :total="featTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            small
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="套餐模板" name="plans">
        <div class="toolbar">
          <el-input v-model="planQ" clearable placeholder="搜索套餐名" style="width: 180px" @keyup.enter="loadPlans" />
          <el-select v-model="planType" clearable placeholder="类型" style="width: 120px" @change=";(planPage = 1), loadPlans()">
            <el-option label="主套餐" value="main" />
            <el-option label="加购包" value="addon" />
          </el-select>
          <el-select v-model="planPublished" clearable placeholder="上架" style="width: 110px" @change=";(planPage = 1), loadPlans()">
            <el-option label="已上架" value="1" />
            <el-option label="未上架" value="0" />
          </el-select>
          <el-button @click="planAdv = !planAdv">高级筛选</el-button>
          <el-input
            v-if="planAdv"
            v-model="planReplaceGroup"
            clearable
            placeholder="互斥组"
            style="width: 120px"
            @keyup.enter="loadPlans"
          />
          <span class="spacer" />
          <el-button @click="openPlanCol">列设置</el-button>
          <el-button @click="exportPlans">导出</el-button>
          <el-button v-if="canManage" type="primary" @click="openPlan('main')">+ 新建主套餐</el-button>
          <el-button v-if="canManage" @click="openPlan('addon')">+ 新建加购包</el-button>
        </div>
        <el-table :data="plans" border stripe>
          <template v-for="colKey in planVisibleKeys" :key="colKey">
          <el-table-column v-if="colKey === 'name'" label="套餐" min-width="180">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPlan(row.plan_type, row, true)">{{ row.name }}</el-button>
              <el-tag size="small" :type="row.plan_type === 'addon' ? '' : 'info'" class="ml">
                {{ row.plan_type === 'addon' ? '加购包' : '主套餐' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'stackable'" label="可叠加" width="80">
            <template #default="{ row }">{{ row.plan_type === 'addon' ? '是' : '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'replace_group'" label="互斥组" width="90">
            <template #default="{ row }">{{ row.replace_group || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'billing_period'" label="周期" width="70">
            <template #default="{ row }">{{ BILL_LABEL[row.billing_period] || row.billing_period }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'price'" label="售价" width="100">
            <template #default="{ row }">¥{{ centsYuan(row.price_cents) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'shops'" label="店铺" width="70">
            <template #default="{ row }">{{ fmtVal(planBag(row, 'quota.max_shops')) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'products'" label="商品" width="70">
            <template #default="{ row }">{{ fmtVal(planBag(row, 'quota.max_products')) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'review'" label="每日提审" width="90">
            <template #default="{ row }">{{ fmtVal(planBag(row, 'usage.product_review_submit')) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'doudian'" label="抖店" width="70">
            <template #default="{ row }">{{ fmtVal(planBag(row, 'channel.doudian')) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'entity'" label="适用主体" min-width="120">
            <template #default="{ row }">{{ entityText(row) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'public'" label="上架" width="70">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_public ? 'success' : 'info'">{{ row.is_public ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="colKey === 'updated_at'" label="更新时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'code'" prop="code" label="套餐编码" width="120" />
          <el-table-column v-if="colKey === 'created_by'" label="创建人" width="110">
            <template #default="{ row }">{{ row.created_by_name || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'updated_by'" label="最后修改人" width="110">
            <template #default="{ row }">{{ row.updated_by_name || '—' }}</template>
          </el-table-column>
          <el-table-column v-if="colKey === 'ops'" label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPlan(row.plan_type, row, true)">详情</el-button>
              <el-button v-if="canManage" link type="primary" @click="openPlan(row.plan_type, row)">编辑</el-button>
              <el-button v-if="canManage" link type="primary" @click="togglePublish(row)">
                {{ row.is_public ? '下架' : '上架' }}
              </el-button>
            </template>
          </el-table-column>
          </template>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="planPage"
            v-model:page-size="planPageSize"
            :total="planTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            small
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <CrmColumnSettingsDialog
      v-model:visible="featColDialog"
      v-model:columns="featColDraft"
      @save="saveFeatCol"
    />
    <CrmColumnSettingsDialog
      v-model:visible="planColDialog"
      v-model:columns="planColDraft"
      @save="savePlanCol"
    />

    <el-dialog v-model="groupDlg" :title="currentFeat ? '编辑功能分组' : '新增功能分组'" width="480px">
      <el-form label-width="100px">
        <el-form-item label="编码来源">
          <el-radio-group v-model="groupForm.code_source" :disabled="!!currentFeat" @change="refreshFeatureCode(groupForm)">
            <el-radio value="auto">自动</el-radio>
            <el-radio value="manual">手工</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="分组编码" required>
          <el-input v-model="groupForm.code" :disabled="!!currentFeat || groupForm.code_source === 'auto'" placeholder="自动生成">
            <template v-if="!currentFeat && groupForm.code_source === 'auto'" #append>
              <el-button @click="refreshFeatureCode(groupForm)">刷新预览</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="分组名称" required>
          <el-input v-model="groupForm.name" />
        </el-form-item>
        <el-form-item label="上级分组">
          <el-select v-model="groupForm.parent_id" clearable placeholder="无（根分组）" style="width: 100%">
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序" required>
          <el-input-number v-model="groupForm.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="说明（选填）">
          <el-input v-model="groupForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDlg = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveGroup">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="leafDlg" title="新增子功能" width="560px">
      <el-form label-width="120px">
        <el-form-item label="编码来源">
          <el-radio-group v-model="leafForm.code_source" @change="refreshFeatureCode(leafForm)">
            <el-radio value="auto">自动（按规则）</el-radio>
            <el-radio value="manual">手工语义码</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="功能编码" required>
          <el-input v-model="leafForm.code" :disabled="leafForm.code_source === 'auto'" placeholder="自动生成">
            <template v-if="leafForm.code_source === 'auto'" #append>
              <el-button @click="refreshFeatureCode(leafForm)">刷新预览</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="leafForm.name" />
        </el-form-item>
        <el-form-item label="所属分组" required>
          <el-select v-model="leafForm.parent_id" style="width: 100%">
            <el-option v-for="g in groups" :key="g.id" :label="`${g.name} ${g.code}`" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务分类" required>
          <el-select v-model="leafForm.category" style="width: 100%">
            <el-option label="配额" value="quota" />
            <el-option label="用量" value="usage" />
            <el-option label="功能" value="feature" />
          </el-select>
        </el-form-item>
        <el-form-item label="数值类型" required>
          <el-select v-model="leafForm.value_type" style="width: 100%">
            <el-option label="存量 int" value="int" />
            <el-option label="周期次数" value="usage" />
            <el-option label="开关" value="bool" />
            <el-option label="不限量" value="unlimited" />
          </el-select>
        </el-form-item>
        <el-form-item label="叠加合并方式" required>
          <el-select v-model="leafForm.aggregate_mode" :disabled="leafForm.value_type === 'bool'" style="width: 100%">
            <el-option label="取最大值" value="max" />
            <el-option label="累加" value="sum" />
            <el-option label="任一满足" value="any" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="leafForm.sort_order" :min="0" />
        </el-form-item>
        <el-form-item v-if="leafForm.value_type === 'usage'" label="统计周期">
          <el-select v-model="leafForm.usage_period" style="width: 100%">
            <el-option label="每日" value="daily" />
            <el-option label="每月" value="monthly" />
            <el-option label="按订阅周期" value="subscription" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="leafForm.value_type === 'usage'" label="埋点标识">
          <el-input v-model="leafForm.meter_key" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="leafForm.unit" />
        </el-form-item>
        <el-form-item label="初始状态">启用</el-form-item>
        <el-form-item label="说明（选填）">
          <el-input v-model="leafForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="leafDlg = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveLeaf">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="featEditDlg" :title="featViewOnly ? '查看功能项' : '编辑功能项'" width="560px">
      <el-form v-if="currentFeat" label-width="140px">
        <el-form-item label="功能编码（只读）">{{ currentFeat.code }}</el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="featEditForm.name" :disabled="featViewOnly" />
        </el-form-item>
        <el-form-item label="所属分组" required>
          <el-select v-model="featEditForm.parent_id" :disabled="featViewOnly" style="width: 100%">
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务分类（只读）">{{ CAT_LABEL[currentFeat.category] || currentFeat.category }}</el-form-item>
        <el-form-item label="数值类型（只读）">{{ VAL_LABEL[currentFeat.value_type] || currentFeat.value_type }}</el-form-item>
        <el-form-item label="叠加合并方式" required>
          <el-select v-model="featEditForm.aggregate_mode" :disabled="featViewOnly || currentFeat.value_type === 'bool'" style="width: 100%">
            <el-option label="取最大值" value="max" />
            <el-option label="累加" value="sum" />
            <el-option label="任一满足" value="any" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="featEditForm.sort_order" :disabled="featViewOnly" :min="0" />
        </el-form-item>
        <el-form-item v-if="currentFeat.value_type === 'usage'" label="统计周期">
          <el-select v-model="featEditForm.usage_period" :disabled="featViewOnly" style="width: 100%">
            <el-option label="每日" value="daily" />
            <el-option label="每月" value="monthly" />
            <el-option label="按订阅周期" value="subscription" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="currentFeat.value_type === 'usage'" label="埋点标识">
          <el-input v-model="featEditForm.meter_key" :disabled="featViewOnly" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="featEditForm.unit" :disabled="featViewOnly" />
        </el-form-item>
        <el-form-item label="状态">{{ currentFeat.is_active ? '启用' : '停用' }}</el-form-item>
        <el-form-item label="说明">
          <el-input v-model="featEditForm.description" type="textarea" :disabled="featViewOnly" />
        </el-form-item>
        <el-form-item label="仍引用此功能的套餐模板（只读）">
          {{ refsForCode(currentFeat.code).map((p) => p.name).join(' · ') || '无' }}
        </el-form-item>
        <el-form-item label="创建人">{{ currentFeat.created_by_name || '—' }}</el-form-item>
        <el-form-item label="创建时间">{{ formatDateTime(currentFeat.created_at) }}</el-form-item>
        <el-form-item label="最后修改人">{{ currentFeat.updated_by_name || '—' }}</el-form-item>
        <el-form-item label="最后修改时间">{{ formatDateTime(currentFeat.updated_at) }}</el-form-item>
        <template v-if="!featViewOnly && refsForCode(currentFeat.code).length">
          <el-form-item label="套餐模板处理">
            <el-checkbox v-model="featEditForm.sync_to_templates">同步到已有套餐模板</el-checkbox>
            <div v-if="featEditForm.sync_to_templates && ['int', 'usage'].includes(currentFeat.value_type)" class="sync-box">
              <el-checkbox v-model="featEditForm.uniform_on">同时将所有模板内该项数值统一为</el-checkbox>
              <el-input-number v-model="featEditForm.uniform_limit_value" :min="0" :disabled="!featEditForm.uniform_on" />
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="featEditDlg = false">{{ featViewOnly ? '关闭' : '取消' }}</el-button>
        <el-button v-if="!featViewOnly" type="primary" :loading="submitting" @click="saveFeatEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deactDlg" title="停用功能项" width="480px">
      <p v-if="deactTarget">停用「{{ deactTarget.name }} {{ deactTarget.code }}」？</p>
      <el-form label-width="140px">
        <el-form-item label="影响说明">新建/编辑模板时不可再勾选此项；已购权益不变。</el-form-item>
        <el-form-item v-if="deactTarget" label="仍引用此功能的套餐模板（只读）">
          {{ refsForCode(deactTarget.code).map((p) => p.name).join(' · ') || '无' }}
        </el-form-item>
        <el-form-item label="套餐模板处理">
          <el-checkbox v-model="deactRemove">同时从已有套餐模板中移除此功能项</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deactDlg = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="confirmDeact">确认停用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="planDlg" :title="planDlgTitle" width="920px" top="4vh">
      <el-form label-width="120px">
        <div class="plan-grid">
          <el-form-item v-if="planMode === 'create'" label="编码来源">
            <el-radio-group v-model="planForm.code_source" :disabled="planReadOnly" @change="refreshPlanCode">
              <el-radio value="auto">自动（按规则）</el-radio>
              <el-radio value="manual">手工语义码</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="planMode === 'edit' || planReadOnly ? '套餐编码' : '套餐编码'" required>
            <el-input
              v-model="planForm.code"
              :disabled="planReadOnly || planMode === 'edit' || planForm.code_source === 'auto'"
              placeholder="自动生成"
            >
              <template v-if="planMode === 'create' && planForm.code_source === 'auto'" #append>
                <el-button @click="refreshPlanCode">刷新预览</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="planForm.plan_type === 'addon' ? '加购包名称' : '套餐名称'" required>
            <el-input v-model="planForm.name" :disabled="planReadOnly" />
          </el-form-item>
          <el-form-item v-if="planForm.plan_type === 'main'" label="互斥组" required>
            <el-input v-model="planForm.replace_group" :disabled="planReadOnly" />
          </el-form-item>
          <el-form-item v-else label="互斥组">—（加购包无）</el-form-item>
          <el-form-item label="可叠加">{{ planForm.plan_type === 'addon' ? '是（锁定）' : '否（主套餐锁定）' }}</el-form-item>
          <el-form-item label="计费周期" required>
            <el-select v-model="planForm.billing_period" :disabled="planReadOnly" style="width: 100%">
              <el-option label="年" value="yearly" />
              <el-option label="月" value="monthly" />
            </el-select>
          </el-form-item>
          <el-form-item label="售价" required>
            <el-input-number v-model="planForm.price_yuan" :min="0" :precision="2" :disabled="planReadOnly" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="planForm.sort_order" :min="0" :disabled="planReadOnly" />
          </el-form-item>
          <el-form-item label="适用主体类型" required>
            <el-checkbox-group v-model="planForm.allowed_entity_types" :disabled="planReadOnly">
              <el-checkbox value="personal">个人</el-checkbox>
              <el-checkbox value="individual_business">个体</el-checkbox>
              <el-checkbox value="enterprise">企业</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item v-if="planMode === 'create'" label="公开上架">
            <el-checkbox v-model="planForm.publish_after_save">保存后上架</el-checkbox>
          </el-form-item>
          <el-form-item v-else label="公开上架（只读）">
            {{ currentPlan?.is_public ? '是' : '否' }}
          </el-form-item>
          <el-form-item v-if="planReadOnly" label="生效订阅数（只读）">
            {{ currentPlan?.active_subscription_count ?? 0 }} 条 active
            <el-button link type="primary" @click="goSubscriptions(currentPlan)">去订阅台账</el-button>
          </el-form-item>
          <el-form-item v-if="planReadOnly" label="编码来源">
            {{ currentPlan?.code_source === 'auto' ? '自动（按规则）' : '手工语义码' }}
          </el-form-item>
          <el-form-item v-if="planMode !== 'create'" label="创建人 / 时间（只读）">
            {{ auditText(currentPlan?.created_by_name, currentPlan?.created_at) }}
          </el-form-item>
          <el-form-item v-if="planMode !== 'create'" label="最后修改人 / 时间（只读）">
            {{ auditText(currentPlan?.updated_by_name, currentPlan?.updated_at) }}
          </el-form-item>
        </div>
        <div class="picker-hd">
          <b>{{ planForm.plan_type === 'addon' ? '增量能力配置' : '套餐能力配置' }}</b>
          <span>已选 {{ selectedCount }} / 共 {{ pickerLeaves.length }} 项</span>
        </div>
        <div v-if="!planReadOnly" class="toolbar">
          <el-input v-model="pickerQ" clearable placeholder="搜索名称 / code" style="width: 180px" />
          <el-select v-model="pickerCat" clearable placeholder="业务分类" style="width: 120px">
            <el-option label="配额" value="quota" />
            <el-option label="用量" value="usage" />
            <el-option label="功能" value="feature" />
          </el-select>
          <el-select v-model="pickerGroup" clearable placeholder="所属分组" style="width: 160px">
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <el-checkbox v-model="pickerSelectedOnly">仅看已选</el-checkbox>
        </div>
        <div class="picker">
          <div v-for="g in pickerGroupsView" :key="g.group.id" class="picker-g">
            <div class="picker-ghd">
              <el-checkbox
                :model-value="groupCheckState(g.leaves).all"
                :indeterminate="groupCheckState(g.leaves).some"
                :disabled="planReadOnly"
                @change="(v) => setGroupCheck(g.leaves, v)"
              />
              {{ g.group.name }}
              <span class="muted">{{ groupCheckState(g.leaves).n }}/{{ g.leaves.length }}</span>
            </div>
            <div v-for="f in g.leaves" :key="f.code" class="picker-row">
              <el-checkbox :model-value="isChecked(f.code)" :disabled="planReadOnly" @change="(v) => toggleFeat(f, v)" />
              <span class="picker-name">{{ f.name }} <code>{{ f.code }}</code></span>
              <el-tag size="small">{{ CAT_LABEL[f.category] }}</el-tag>
              <template v-if="isChecked(f.code) && f.value_type === 'bool'">开</template>
              <el-input-number
                v-else-if="isChecked(f.code) && f.value_type !== 'unlimited'"
                :model-value="planForm.feature_values[f.code]"
                :disabled="planReadOnly"
                :min="0"
                size="small"
                @change="(v) => (planForm.feature_values[f.code] = v)"
              />
              <span v-else-if="isChecked(f.code)">∞</span>
              <span v-else class="muted">—</span>
              <span class="muted">{{ f.unit || '' }}</span>
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="planDlg = false">{{ planReadOnly ? '关闭' : '取消' }}</el-button>
        <el-button v-if="planReadOnly && canManage" type="primary" @click="openPlan(planForm.plan_type, currentPlan)">编辑</el-button>
        <el-button v-if="!planReadOnly" type="primary" :loading="submitting" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.pager {
  margin-top: 12px;
}
.code {
  color: #8c8c8c;
  font-size: 12px;
}
.ml {
  margin-left: 6px;
}
.plan-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
.picker-hd {
  display: flex;
  justify-content: space-between;
  margin: 12px 0 8px;
  font-size: 13px;
}
.picker {
  max-height: 340px;
  overflow: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
}
.picker-ghd {
  position: sticky;
  top: 0;
  background: #f5f5f5;
  padding: 8px 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1;
}
.picker-row {
  display: grid;
  grid-template-columns: 28px 1fr 72px 120px 40px;
  gap: 8px;
  padding: 8px 10px;
  align-items: center;
  border-bottom: 1px solid #f5f5f5;
  font-size: 12px;
}
.picker-name code {
  color: #8c8c8c;
  font-size: 10px;
  margin-left: 4px;
}
.muted {
  color: #8c8c8c;
  font-size: 12px;
}
.sync-box {
  margin-top: 8px;
  padding: 10px;
  background: #f9f0ff;
  border-radius: 6px;
}
</style>
