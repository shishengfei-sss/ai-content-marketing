<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import CrmEntityTags from '../../components/crm/CrmEntityTags.vue'
import CrmEntityAttachments from '../../components/crm/CrmEntityAttachments.vue'
import DynamicField from '../../components/crm/DynamicField.vue'
import { useEntitySchema } from '../../composables/useEntitySchema'
import { formatFieldDisplay } from '../../utils/entityForm'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { fields, loadSchema } = useEntitySchema('product')

const loading = ref(false)
const product = ref(null)
const variants = ref([])
const priceEntries = ref([])
const priceBooks = ref([])
const cpqParams = ref([])
const specModels = ref([])
const activeTab = ref('basic')
const variantDialog = ref(false)
const editingVariant = ref(false)
const entryDialog = ref(false)
const paramDialog = ref(false)
const pricingDialog = ref(false)
const editDialog = ref(false)
const saving = ref(false)
const togglingCpq = ref(false)
const editingParam = ref(false)
const pricingParam = ref(null)
const variantForm = ref({ id: '', sku: '', variant_name: '', list_price: 0, cost_price: null, attributes: '', is_active: true })
const entryForm = ref({ price_book_id: '', unit_price: 0, min_quantity: 1, variant_id: null })
const editForm = ref({
  code: '',
  name: '',
  unit: '',
  list_price: 0,
  cost_price: null,
  default_tax_rate: null,
  price_includes_tax: false,
  category_id: null,
  spec_model_id: null,
  description: '',
  is_active: true,
})
const extraForm = ref({})
const paramForm = ref(emptyParamForm())
const pricingForm = ref({ option_value: '', price_adjustment_type: 'fixed', price_adjustment_value: 0 })

const canManage = () => hasPermission(auth.permissions, 'crm.product.manage')

const customFields = computed(() =>
  (fields.value || []).filter(
    (f) => f.is_active !== false && String(f.field_key || '').startsWith('cf_'),
  ),
)

const ADJUST_TYPE_LABEL = {
  fixed: '固定加价',
  percentage: '百分比',
  multiplier: '倍率',
}

function emptyParamForm() {
  return {
    id: '',
    param_name: '',
    param_type: 'select',
    options: [],
    sort_order: 0,
    is_active: true,
  }
}

const pricingOptionChoices = computed(() => {
  const opts = pricingParam.value?.options
  return Array.isArray(opts) ? opts.map(String) : []
})

async function loadAll() {
  loading.value = true
  try {
    const { data } = await crmApi.getProduct(route.params.id)
    product.value = data
    await Promise.all([loadVariants(), loadEntries(), loadBooks(), loadCpqParams()])
  } catch (e) {
    ElMessage.error(e.message || '加载产品失败')
  } finally {
    loading.value = false
  }
}

async function loadVariants() {
  try {
    const { data } = await crmApi.listProductVariants(route.params.id)
    variants.value = Array.isArray(data) ? data : []
  } catch { variants.value = [] }
}

async function loadEntries() {
  try {
    const { data } = await crmApi.listProductPriceEntries(route.params.id)
    priceEntries.value = Array.isArray(data) ? data : []
  } catch { priceEntries.value = [] }
}

async function loadBooks() {
  try {
    const { data } = await crmApi.listPriceBooks()
    priceBooks.value = Array.isArray(data) ? data : []
  } catch { priceBooks.value = [] }
}

async function loadCpqParams() {
  try {
    const { data } = await crmApi.listCpqProductParams(route.params.id, { include_inactive: true })
    cpqParams.value = Array.isArray(data) ? data : []
  } catch { cpqParams.value = [] }
}

async function toggleCpq(val) {
  if (!product.value || !canManage()) return
  togglingCpq.value = true
  try {
    const { data } = await crmApi.updateProduct(product.value.id, { cpq_enabled: !!val })
    product.value = { ...product.value, ...data }
    ElMessage.success(val ? '已开启 CPQ' : '已关闭 CPQ')
    if (val) activeTab.value = 'cpq'
  } catch (e) {
    product.value.cpq_enabled = !val
    ElMessage.error(e.message || '更新失败')
  } finally {
    togglingCpq.value = false
  }
}

async function loadSpecModels() {
  try {
    const { data } = await crmApi.listProductSpecModels({ active_only: true })
    specModels.value = Array.isArray(data) ? data : []
  } catch {
    specModels.value = []
  }
}

function openEdit() {
  if (!product.value) return
  editForm.value = {
    code: product.value.code || '',
    name: product.value.name || '',
    unit: product.value.unit || '',
    list_price: Number(product.value.list_price || 0),
    cost_price: product.value.cost_price != null ? Number(product.value.cost_price) : null,
    default_tax_rate: product.value.default_tax_rate != null ? Number(product.value.default_tax_rate) : null,
    price_includes_tax: !!product.value.price_includes_tax,
    category_id: product.value.category_id || null,
    spec_model_id: product.value.spec_model_id || null,
    description: product.value.description || '',
    is_active: !!product.value.is_active,
  }
  const next = {}
  for (const f of customFields.value) {
    const key = f.field_key
    const val = product.value.extra_data?.[key]
    if (val !== undefined && val !== null) next[key] = val
    else if (f.field_type === 'checkbox') next[key] = false
    else if (f.field_type === 'multiselect') next[key] = []
    else next[key] = f.default_value ?? ''
  }
  extraForm.value = next
  editDialog.value = true
}

async function submitEdit() {
  if (!editForm.value.code.trim() || !editForm.value.name.trim()) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  saving.value = true
  try {
    const { data } = await crmApi.updateProduct(product.value.id, {
      code: editForm.value.code.trim(),
      name: editForm.value.name.trim(),
      unit: editForm.value.unit || null,
      list_price: editForm.value.list_price,
      cost_price: editForm.value.cost_price,
      default_tax_rate: editForm.value.default_tax_rate,
      price_includes_tax: !!editForm.value.price_includes_tax,
      spec_model_id: editForm.value.spec_model_id || null,
      description: editForm.value.description || null,
      is_active: !!editForm.value.is_active,
      extra_data: { ...extraForm.value },
    })
    product.value = { ...product.value, ...data }
    editDialog.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(`确定删除产品「${product.value.name}」？`, '删除', { type: 'warning' })
    await crmApi.deleteProduct(product.value.id)
    ElMessage.success('已删除')
    router.push('/crm/products')
  } catch (e) {
    if (e === 'cancel') return
    const msg = e.message || '删除失败'
    if (String(msg).includes('无法删除') && product.value?.is_active) {
      try {
        await ElMessageBox.confirm(`${msg}\n是否改为停用该产品？`, '无法删除', {
          confirmButtonText: '停用',
          cancelButtonText: '取消',
          type: 'warning',
        })
        await crmApi.updateProduct(product.value.id, { is_active: false })
        ElMessage.success('已停用')
        await loadAll()
        return
      } catch (e2) {
        if (e2 === 'cancel') return
        ElMessage.error(e2.message || '停用失败')
        return
      }
    }
    ElMessage.error(msg)
  }
}

function openVariant() {
  editingVariant.value = false
  variantForm.value = {
    id: '',
    sku: '',
    variant_name: '',
    list_price: Number(product.value?.list_price || 0),
    cost_price: null,
    attributes: '',
    is_active: true,
  }
  variantDialog.value = true
}

function openEditVariant(row) {
  editingVariant.value = true
  variantForm.value = {
    id: row.id,
    sku: row.sku || '',
    variant_name: row.variant_name || '',
    list_price: Number(row.list_price || 0),
    cost_price: row.cost_price != null ? Number(row.cost_price) : null,
    attributes: row.attributes && Object.keys(row.attributes).length
      ? JSON.stringify(row.attributes, null, 2)
      : '',
    is_active: row.is_active !== false,
  }
  variantDialog.value = true
}

async function submitVariant() {
  if (!variantForm.value.sku.trim() || !variantForm.value.variant_name.trim()) {
    ElMessage.warning('请填写 SKU 与变体名称')
    return
  }
  saving.value = true
  try {
    let attrs = {}
    if (variantForm.value.attributes.trim()) {
      try { attrs = JSON.parse(variantForm.value.attributes) } catch {
        ElMessage.warning('规格 JSON 格式不正确'); return
      }
    }
    const payload = {
      sku: variantForm.value.sku.trim(),
      variant_name: variantForm.value.variant_name.trim(),
      list_price: variantForm.value.list_price,
      cost_price: variantForm.value.cost_price,
      attributes: attrs,
      is_active: !!variantForm.value.is_active,
    }
    if (editingVariant.value) {
      await crmApi.updateProductVariant(variantForm.value.id, payload)
      ElMessage.success('变体已保存')
    } else {
      await crmApi.createProductVariant(route.params.id, payload)
      ElMessage.success('变体已创建')
    }
    variantDialog.value = false
    await loadVariants()
    activeTab.value = 'variants'
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeVariant(row) {
  try {
    await ElMessageBox.confirm('删除该变体？', '删除')
    await crmApi.deleteProductVariant(row.id)
    ElMessage.success('已删除')
    await loadVariants()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function openEntry() {
  entryForm.value = {
    price_book_id: priceBooks.value[0]?.id || '',
    unit_price: Number(product.value?.list_price || 0),
    min_quantity: 1,
    variant_id: null,
  }
  entryDialog.value = true
}

async function ensureBook() {
  if (priceBooks.value.length) return priceBooks.value[0].id
  const { data } = await crmApi.createPriceBook({ name: '标准价目表', is_default: true })
  await loadBooks()
  return data.id
}

async function submitEntry() {
  saving.value = true
  try {
    let bookId = entryForm.value.price_book_id
    if (!bookId) bookId = await ensureBook()
    await crmApi.createPriceBookEntry(bookId, {
      product_id: product.value.id,
      variant_id: entryForm.value.variant_id || null,
      unit_price: entryForm.value.unit_price,
      min_quantity: entryForm.value.min_quantity,
    })
    ElMessage.success('价目条目已添加')
    entryDialog.value = false
    await loadEntries()
    activeTab.value = 'prices'
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeEntry(row) {
  try {
    await ElMessageBox.confirm('删除该价目条目？', '删除')
    await crmApi.deletePriceBookEntry(row.id)
    ElMessage.success('已删除')
    await loadEntries()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function openCreateParam() {
  editingParam.value = false
  paramForm.value = emptyParamForm()
  paramForm.value.sort_order = cpqParams.value.length
  paramDialog.value = true
}

function openEditParam(row) {
  editingParam.value = true
  paramForm.value = {
    id: row.id,
    param_name: row.param_name,
    param_type: row.param_type || 'select',
    options: Array.isArray(row.options) ? [...row.options.map(String)] : [],
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
  }
  paramDialog.value = true
}

async function submitParam() {
  if (!paramForm.value.param_name?.trim()) {
    ElMessage.warning('请填写参数名')
    return
  }
  if (paramForm.value.param_type === 'select' && !paramForm.value.options?.length) {
    ElMessage.warning('选择型参数请至少添加一个选项')
    return
  }
  saving.value = true
  try {
    const payload = {
      param_name: paramForm.value.param_name.trim(),
      param_type: paramForm.value.param_type,
      options: paramForm.value.param_type === 'select' ? paramForm.value.options : null,
      sort_order: paramForm.value.sort_order ?? 0,
      is_active: !!paramForm.value.is_active,
    }
    if (editingParam.value) {
      await crmApi.updateCpqProductParam(paramForm.value.id, payload)
      ElMessage.success('参数已保存')
    } else {
      await crmApi.createCpqProductParam(route.params.id, payload)
      ElMessage.success('参数已创建')
      if (!product.value.cpq_enabled) {
        const { data } = await crmApi.updateProduct(product.value.id, { cpq_enabled: true })
        product.value = { ...product.value, ...data }
      }
    }
    paramDialog.value = false
    await loadCpqParams()
    activeTab.value = 'cpq'
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeParam(row) {
  try {
    await ElMessageBox.confirm(`删除参数「${row.param_name}」及其价差？`, '删除')
    await crmApi.deleteCpqProductParam(row.id)
    ElMessage.success('已删除')
    await loadCpqParams()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function openPricing(row) {
  pricingParam.value = row
  pricingForm.value = {
    option_value: Array.isArray(row.options) && row.options.length ? String(row.options[0]) : '',
    price_adjustment_type: 'fixed',
    price_adjustment_value: 0,
  }
  pricingDialog.value = true
}

async function submitPricing() {
  if (!pricingParam.value) return
  if (!pricingForm.value.option_value?.trim()) {
    ElMessage.warning('请选择或填写选项值')
    return
  }
  saving.value = true
  try {
    await crmApi.createCpqParamPricing(pricingParam.value.id, {
      option_value: pricingForm.value.option_value.trim(),
      price_adjustment_type: pricingForm.value.price_adjustment_type,
      price_adjustment_value: Number(pricingForm.value.price_adjustment_value) || 0,
    })
    ElMessage.success('价差已添加')
    pricingForm.value.price_adjustment_value = 0
    await loadCpqParams()
    const fresh = cpqParams.value.find((p) => p.id === pricingParam.value.id)
    if (fresh) pricingParam.value = fresh
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removePricing(row) {
  try {
    await ElMessageBox.confirm('删除该价差映射？', '删除')
    await crmApi.deleteCpqParamPricing(row.id)
    ElMessage.success('已删除')
    await loadCpqParams()
    if (pricingParam.value) {
      const fresh = cpqParams.value.find((p) => p.id === pricingParam.value.id)
      if (fresh) pricingParam.value = fresh
    }
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function bookName(id) {
  return priceBooks.value.find((b) => b.id === id)?.name || id
}
function formatOptions(row) {
  if (!Array.isArray(row.options) || !row.options.length) return '—'
  return row.options.map(String).join('、')
}
function formatAdjustment(row) {
  const t = row.price_adjustment_type
  const v = Number(row.price_adjustment_value)
  if (t === 'fixed') return `+¥${formatAmount(v)}`
  if (t === 'percentage') return `${v}%`
  if (t === 'multiplier') return `×${v}`
  return String(v)
}

watch(
  () => route.params.id,
  (id) => { if (id) loadAll() },
)

onMounted(async () => {
  await Promise.all([loadSchema(), loadSpecModels()])
  await loadAll()
})
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="detail-page__back">
      <el-button link @click="router.push('/crm/products')">
        <el-icon><ArrowLeft /></el-icon> 返回产品列表
      </el-button>
    </div>

    <div v-if="product" class="page-card detail-page__head">
      <div>
        <h2 class="detail-page__title">{{ product.name }}</h2>
        <div class="detail-page__meta">
          <el-tag :type="product.is_active ? 'success' : 'info'" size="small">
            {{ product.is_active ? '上架' : '下架' }}
          </el-tag>
          <el-tag v-if="product.cpq_enabled" type="warning" size="small">CPQ</el-tag>
          <span>{{ product.code }}</span>
          <span class="detail-page__amount">¥{{ formatAmount(product.list_price) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button
          v-if="product.cpq_enabled"
          type="warning"
          @click="router.push({ path: '/crm/quotes/cpq/new', query: { product_id: product.id } })"
        >CPQ 报价</el-button>
        <el-button v-if="canManage()" @click="openEdit">编辑</el-button>
        <el-button v-if="canManage()" type="primary" @click="openVariant">新增变体</el-button>
        <el-button v-if="canManage()" @click="openEntry">添加价目</el-button>
        <el-button v-if="canManage()" type="danger" @click="handleDelete">删除</el-button>
      </div>
    </div>

    <div v-if="product" class="detail-page__body page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <div style="margin-bottom: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">标签</div>
            <CrmEntityTags
              entity-type="product"
              :entity-id="product.id"
              :editable="canManage()"
            />
          </div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="编码">{{ product.code }}</el-descriptions-item>
            <el-descriptions-item label="规格型号">{{ product.spec_model_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="单位">{{ product.unit || '—' }}</el-descriptions-item>
            <el-descriptions-item label="标价">¥{{ formatAmount(product.list_price) }}</el-descriptions-item>
            <el-descriptions-item label="标价含税">{{ product.price_includes_tax ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="默认税率">{{ product.default_tax_rate != null ? product.default_tax_rate + '%' : '—' }}</el-descriptions-item>
            <el-descriptions-item label="成本">
              {{ product.cost_price != null ? '¥' + formatAmount(product.cost_price) : '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="累计销量">{{ product.total_ordered_quantity || 0 }}</el-descriptions-item>
            <el-descriptions-item label="累计收入">¥{{ formatAmount(product.total_revenue) }}</el-descriptions-item>
            <el-descriptions-item label="CPQ">
              <div class="cpq-toggle-row">
                <el-switch
                  :model-value="!!product.cpq_enabled"
                  :disabled="!canManage() || togglingCpq"
                  :loading="togglingCpq"
                  @change="toggleCpq"
                />
                <span class="hint">{{ product.cpq_enabled ? '已启用轻量配置报价' : '未启用' }}</span>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ product.description || '—' }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="customFields.length" style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">扩展信息</div>
            <el-descriptions :column="2" border>
              <el-descriptions-item
                v-for="field in customFields"
                :key="field.field_key"
                :label="field.label"
              >
                {{ formatFieldDisplay(field, product) }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
          <div style="margin-top: 16px">
            <CrmEntityAttachments
              entity-type="product"
              :entity-id="product.id"
              :editable="canManage()"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane :label="`变体（${variants.length}）`" name="variants">
          <el-table :data="variants" border size="small" empty-text="暂无变体">
            <el-table-column prop="sku" label="SKU" width="140" />
            <el-table-column prop="variant_name" label="名称" min-width="160" />
            <el-table-column label="标价" width="120" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.list_price) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">{{ row.is_active ? '启用' : '停用' }}</template>
            </el-table-column>
            <el-table-column v-if="canManage()" label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditVariant(row)">编辑</el-button>
                <el-button link type="danger" @click="removeVariant(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`价目（${priceEntries.length}）`" name="prices">
          <el-table :data="priceEntries" border size="small" empty-text="暂无价目条目">
            <el-table-column label="价目表" min-width="140">
              <template #default="{ row }">{{ bookName(row.price_book_id) }}</template>
            </el-table-column>
            <el-table-column label="单价" width="120" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.unit_price) }}</template>
            </el-table-column>
            <el-table-column prop="min_quantity" label="起订" width="80" align="center" />
            <el-table-column v-if="canManage()" label="操作" width="90" align="center">
              <template #default="{ row }">
                <el-button link type="danger" @click="removeEntry(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`CPQ（${cpqParams.length}）`" name="cpq">
          <div class="cpq-toolbar">
            <div class="cpq-toolbar__left">
              <el-switch
                :model-value="!!product.cpq_enabled"
                :disabled="!canManage() || togglingCpq"
                :loading="togglingCpq"
                active-text="CPQ 开启"
                inactive-text="CPQ 关闭"
                @change="toggleCpq"
              />
              <span class="hint">基价取自价目表（缺省回落标价），参数选项可叠加价差</span>
            </div>
            <el-button v-if="canManage()" type="primary" @click="openCreateParam">新增参数</el-button>
          </div>

          <el-table :data="cpqParams" border size="small" empty-text="暂无 CPQ 参数">
            <el-table-column prop="param_name" label="参数名" min-width="120" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                {{ row.param_type === 'select' ? '选择' : row.param_type === 'number' ? '数字' : '文本' }}
              </template>
            </el-table-column>
            <el-table-column label="选项" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ formatOptions(row) }}</template>
            </el-table-column>
            <el-table-column label="价差数" width="90" align="center">
              <template #default="{ row }">{{ (row.pricings || []).length }}</template>
            </el-table-column>
            <el-table-column prop="sort_order" label="排序" width="70" align="center" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="canManage()" label="操作" width="200" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditParam(row)">编辑</el-button>
                <el-button
                  v-if="row.param_type === 'select'"
                  link
                  type="primary"
                  @click="openPricing(row)"
                >价差</el-button>
                <el-button link type="danger" @click="removeParam(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="editDialog" title="编辑产品" width="520px">
      <el-form label-width="88px">
        <el-form-item label="编码" required>
          <el-input v-model="editForm.code" maxlength="50" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="editForm.name" maxlength="200" />
        </el-form-item>
        <el-form-item label="规格型号">
          <el-select v-model="editForm.spec_model_id" clearable filterable placeholder="选择规格型号" style="width: 100%">
            <el-option v-for="s in specModels" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="editForm.unit" maxlength="30" />
        </el-form-item>
        <el-form-item label="标价">
          <el-input-number v-model="editForm.list_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="标价含税">
          <el-switch v-model="editForm.price_includes_tax" />
        </el-form-item>
        <el-form-item label="默认税率%">
          <el-input-number
            v-model="editForm.default_tax_rate"
            :min="0"
            :max="100"
            :precision="2"
            :controls="false"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="成本">
          <el-input-number v-model="editForm.cost_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="上架">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <template v-if="customFields.length">
          <div style="margin: 8px 0 12px; padding-left: 8px; border-left: 3px solid var(--el-color-primary); font-weight: 600; font-size: 13px">
            扩展信息
          </div>
          <el-form-item
            v-for="field in customFields"
            :key="field.field_key"
            :label="field.label"
            :required="!!field.is_required"
          >
            <DynamicField v-model="extraForm[field.field_key]" :field="field" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="variantDialog" :title="editingVariant ? '编辑变体' : '新增变体'" width="460px">
      <el-form label-width="88px">
        <el-form-item label="SKU" required><el-input v-model="variantForm.sku" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="variantForm.variant_name" /></el-form-item>
        <el-form-item label="标价"><el-input-number v-model="variantForm.list_price" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="成本"><el-input-number v-model="variantForm.cost_price" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="规格 JSON"><el-input v-model="variantForm.attributes" type="textarea" :rows="2" placeholder='{"规格":"值"}' /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="variantForm.is_active" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="variantDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitVariant">{{ editingVariant ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="entryDialog" title="添加价目" width="460px">
      <el-form label-width="88px">
        <el-form-item label="价目表">
          <el-select v-model="entryForm.price_book_id" clearable placeholder="默认将自动创建标准价目表" style="width: 100%">
            <el-option v-for="b in priceBooks" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="变体">
          <el-select v-model="entryForm.variant_id" clearable placeholder="可选" style="width: 100%">
            <el-option v-for="v in variants" :key="v.id" :label="v.variant_name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="单价"><el-input-number v-model="entryForm.unit_price" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="起订量"><el-input-number v-model="entryForm.min_quantity" :min="1" :controls="false" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="entryDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEntry">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="paramDialog" :title="editingParam ? '编辑参数' : '新增参数'" width="480px">
      <el-form label-width="88px">
        <el-form-item label="参数名" required>
          <el-input v-model="paramForm.param_name" maxlength="100" placeholder="如：材质" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="paramForm.param_type">
            <el-radio-button value="select">选择</el-radio-button>
            <el-radio-button value="number">数字</el-radio-button>
            <el-radio-button value="text">文本</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="paramForm.param_type === 'select'" label="选项" required>
          <el-select
            v-model="paramForm.options"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车添加"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="paramForm.sort_order" :min="0" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="paramForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paramDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitParam">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="pricingDialog"
      :title="pricingParam ? `价差：${pricingParam.param_name}` : '价差'"
      width="560px"
    >
      <el-table
        v-if="pricingParam"
        :data="pricingParam.pricings || []"
        border
        size="small"
        empty-text="暂无价差"
        class="pricing-table"
      >
        <el-table-column prop="option_value" label="选项值" min-width="120" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ ADJUST_TYPE_LABEL[row.price_adjustment_type] || row.price_adjustment_type }}</template>
        </el-table-column>
        <el-table-column label="调整" width="120" align="right">
          <template #default="{ row }">{{ formatAdjustment(row) }}</template>
        </el-table-column>
        <el-table-column v-if="canManage()" label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button link type="danger" @click="removePricing(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-divider v-if="canManage()" content-position="left">新增价差</el-divider>
      <el-form v-if="canManage()" label-width="88px">
        <el-form-item label="选项值" required>
          <el-select
            v-if="pricingOptionChoices.length"
            v-model="pricingForm.option_value"
            filterable
            allow-create
            style="width: 100%"
          >
            <el-option v-for="o in pricingOptionChoices" :key="o" :label="o" :value="o" />
          </el-select>
          <el-input v-else v-model="pricingForm.option_value" placeholder="选项值" />
        </el-form-item>
        <el-form-item label="调整类型">
          <el-select v-model="pricingForm.price_adjustment_type" style="width: 100%">
            <el-option
              v-for="(label, key) in ADJUST_TYPE_LABEL"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="调整值">
          <el-input-number
            v-model="pricingForm.price_adjustment_value"
            :precision="4"
            :controls="false"
            style="width: 100%"
          />
          <p class="hint">
            固定加价：加到单价；百分比：单价 × (1 + 值/100)；倍率：单价 × 值
          </p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pricingDialog = false">关闭</el-button>
        <el-button v-if="canManage()" type="primary" :loading="saving" @click="submitPricing">添加价差</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-page__back { margin-bottom: 8px; }
.detail-page__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.detail-page__title { margin: 0 0 8px 0; font-size: 20px; font-weight: 600; }
.detail-page__meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--el-text-color-secondary); font-size: 13px; }
.detail-page__amount { font-size: 16px; font-weight: 600; color: var(--el-color-primary); }
.detail-page__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-page__body { margin-top: 16px; }
.cpq-toggle-row { display: flex; align-items: center; gap: 10px; }
.cpq-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.cpq-toolbar__left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.hint { font-size: 12px; color: var(--el-text-color-secondary); }
.pricing-table { margin-bottom: 8px; }
</style>
