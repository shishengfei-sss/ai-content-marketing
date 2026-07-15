<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const product = ref(null)
const variants = ref([])
const priceEntries = ref([])
const priceBooks = ref([])
const activeTab = ref('basic')
const variantDialog = ref(false)
const entryDialog = ref(false)
const saving = ref(false)
const variantForm = ref({ sku: '', variant_name: '', list_price: 0, cost_price: null, attributes: '' })
const entryForm = ref({ price_book_id: '', unit_price: 0, min_quantity: 1, variant_id: null })

const canManage = () => hasPermission(auth.permissions, 'crm.product.manage')

async function loadAll() {
  loading.value = true
  try {
    const { data } = await crmApi.getProduct(route.params.id)
    product.value = data
    await Promise.all([loadVariants(), loadEntries(), loadBooks()])
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

function openVariant() {
  variantForm.value = { sku: '', variant_name: '', list_price: Number(product.value?.list_price || 0), cost_price: null, attributes: '' }
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
    await crmApi.createProductVariant(route.params.id, {
      sku: variantForm.value.sku.trim(),
      variant_name: variantForm.value.variant_name.trim(),
      list_price: variantForm.value.list_price,
      cost_price: variantForm.value.cost_price,
      attributes: attrs,
    })
    ElMessage.success('变体已创建')
    variantDialog.value = false
    await loadVariants()
    activeTab.value = 'variants'
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
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

function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function bookName(id) {
  return priceBooks.value.find((b) => b.id === id)?.name || id
}

onMounted(loadAll)
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
          <span>{{ product.code }}</span>
          <span class="detail-page__amount">¥{{ formatAmount(product.list_price) }}</span>
        </div>
      </div>
      <div class="detail-page__actions">
        <el-button v-if="canManage()" type="primary" @click="openVariant">新增变体</el-button>
        <el-button v-if="canManage()" @click="openEntry">添加价目</el-button>
      </div>
    </div>

    <div v-if="product" class="detail-page__body page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="编码">{{ product.code }}</el-descriptions-item>
            <el-descriptions-item label="单位">{{ product.unit || '—' }}</el-descriptions-item>
            <el-descriptions-item label="标价">¥{{ formatAmount(product.list_price) }}</el-descriptions-item>
            <el-descriptions-item label="成本">
              {{ product.cost_price != null ? '¥' + formatAmount(product.cost_price) : '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="累计销量">{{ product.total_ordered_quantity || 0 }}</el-descriptions-item>
            <el-descriptions-item label="累计收入">¥{{ formatAmount(product.total_revenue) }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ product.description || '—' }}</el-descriptions-item>
          </el-descriptions>
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
            <el-table-column v-if="canManage()" label="操作" width="90" align="center">
              <template #default="{ row }">
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
      </el-tabs>
    </div>

    <el-dialog v-model="variantDialog" title="新增变体" width="460px">
      <el-form label-width="88px">
        <el-form-item label="SKU" required><el-input v-model="variantForm.sku" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="variantForm.variant_name" /></el-form-item>
        <el-form-item label="标价"><el-input-number v-model="variantForm.list_price" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="成本"><el-input-number v-model="variantForm.cost_price" :min="0" :precision="2" :controls="false" style="width: 100%" /></el-form-item>
        <el-form-item label="规格 JSON"><el-input v-model="variantForm.attributes" type="textarea" :rows="2" placeholder='{"规格":"值"}' /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="variantDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitVariant">创建</el-button>
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
</style>
