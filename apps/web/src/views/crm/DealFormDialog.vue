<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'

const props = defineProps({
  visible: { type: Boolean, default: false },
  pipelines: { type: Array, default: () => [] },
  record: { type: Object, default: null },
  mode: { type: String, default: 'create' },
})
const emit = defineEmits(['update:visible', 'saved'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)
const customerOptions = ref([])
const customerLoading = ref(false)
const contactOptions = ref([])
const contactLoading = ref(false)
const form = ref(emptyForm())

function emptyForm() {
  return {
    title: '',
    customer_id: '',
    contact_id: '',
    pipeline_id: '',
    stage_id: '',
    amount: null,
    expected_close_date: '',
    probability: null,
    status: 'open',
    source: '',
    loss_reason: '',
    description: '',
    next_step: '',
    deal_type: '',
    priority: 'medium',
    competitor: '',
    contact_role: '',
    lines: [],
  }
}

const stages = computed(() => {
  const p = props.pipelines.find((x) => String(x.id) === String(form.value.pipeline_id))
  return p?.stages || []
})

const isEdit = computed(() => props.mode === 'edit' && props.record?.id)
const dialogTitle = computed(() => (isEdit.value ? '编辑商机' : '新建商机'))

async function searchCustomers(q = '') {
  customerLoading.value = true
  try {
    const { data } = await crmApi.listCustomers({ page: 1, page_size: 50, q })
    customerOptions.value = (data.items || []).map((c) => ({
      id: c.id,
      company_name: c.company_name,
    }))
  } catch (e) {
    customerOptions.value = []
  } finally {
    customerLoading.value = false
  }
}

async function loadContacts(customerId) {
  if (!customerId) { contactOptions.value = []; return }
  contactLoading.value = true
  try {
    const { data } = await crmApi.listContacts(customerId)
    contactOptions.value = (data || []).map((c) => ({
      id: c.id,
      label: c.name || c.contact_name || '(未命名)',
    }))
  } catch (e) {
    contactOptions.value = []
  } finally {
    contactLoading.value = false
  }
}

const productOptions = ref([])
const productLoading = ref(false)
async function loadProducts() {
  productLoading.value = true
  try {
    const { data } = await crmApi.listProducts({ page: 1, page_size: 200 })
    productOptions.value = (data.items || []).map((p) => ({
      id: p.id, name: p.name, unit: p.unit, price: Number(p.list_price || 0),
    }))
  } catch { productOptions.value = [] } finally { productLoading.value = false }
}

function emptyLine() {
  return { product_id: '', product_name: '', unit: '', quantity: 1, unit_price: 0, discount_percent: 0, subtotal: 0 }
}
function addLine() { form.value.lines.push(emptyLine()) }
function removeLine(idx) { form.value.lines.splice(idx, 1) }
function onLineProductChange(line) {
  const p = productOptions.value.find((x) => String(x.id) === String(line.product_id))
  if (p) {
    line.product_name = p.name
    line.unit = p.unit || ''
    if (!line.unit_price) line.unit_price = p.price
  }
  computeLineSubtotal(line)
}
function computeLineSubtotal(line) {
  const q = Number(line.quantity) || 0
  const up = Number(line.unit_price) || 0
  const d = Number(line.discount_percent) || 0
  line.subtotal = Math.round(q * up * (1 - d / 100) * 100) / 100
}
const linesTotal = computed(() => Math.round(form.value.lines.reduce((s, l) => s + (Number(l.subtotal) || 0), 0) * 100) / 100)

async function onCustomerChange() {
  form.value.contact_id = ''
  await loadContacts(form.value.customer_id)
}

function syncStageProbability() {
  const stage = stages.value.find((s) => String(s.id) === String(form.value.stage_id))
  if (stage?.probability != null) form.value.probability = stage.probability
}

function onPipelineChange() {
  form.value.stage_id = stages.value[0]?.id || ''
  syncStageProbability()
}

function onStageChange() {
  syncStageProbability()
}

function resetForm() {
  form.value = emptyForm()
  if (props.pipelines.length) {
    const def = props.pipelines.find((p) => p.is_default) || props.pipelines[0]
    form.value.pipeline_id = def?.id || ''
    form.value.stage_id = def?.stages?.[0]?.id || ''
    syncStageProbability()
  }
  form.value.status = 'open'
  contactOptions.value = []
}

async function loadDeal() {
  if (!props.record?.id) { resetForm(); return }
  try {
    const { data } = await crmApi.getDeal(props.record.id)
    form.value = {
      title: data.title || '',
      customer_id: data.customer_id || '',
      contact_id: data.contact_id || '',
      pipeline_id: data.pipeline_id || '',
      stage_id: data.stage_id || '',
      amount: data.amount ?? null,
      expected_close_date: data.expected_close_date || '',
      probability: data.probability ?? null,
      status: data.status || 'open',
      source: data.source || '',
      loss_reason: data.loss_reason || '',
      description: data.description || '',
      next_step: data.next_step || '',
      deal_type: data.deal_type || '',
      priority: data.priority || 'medium',
      competitor: data.competitor || '',
      contact_role: data.contact_role || '',
      lines: (data.lines || []).map((l) => ({
        product_id: l.product_id || '',
        product_name: l.product_name || '',
        unit: l.unit || '',
        quantity: Number(l.quantity) || 1,
        unit_price: Number(l.unit_price) || 0,
        discount_percent: Number(l.discount_percent) || 0,
        subtotal: Number(l.subtotal) || 0,
      })),
    }
    if (data.customer_id) {
      customerOptions.value = [{ id: data.customer_id, company_name: data.customer_name || '(已绑定客户)' }]
      await loadContacts(data.customer_id)
    }
  } catch (e) {
    ElMessage.error(e.message || '加载商机失败')
    resetForm()
  }
}

async function submit() {
  if (!form.value.title?.trim()) { ElMessage.warning('请填写商机名称'); return }
  if (!form.value.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!form.value.pipeline_id) { ElMessage.warning('请选择销售管道'); return }
  if (!form.value.stage_id) { ElMessage.warning('请选择阶段'); return }

  const payload = {
    title: form.value.title.trim(),
    customer_id: form.value.customer_id,
    pipeline_id: form.value.pipeline_id,
    stage_id: form.value.stage_id,
    amount: form.value.amount === '' ? null : form.value.amount,
    expected_close_date: form.value.expected_close_date || null,
    probability: form.value.probability === '' ? null : form.value.probability,
    status: form.value.status,
    source: form.value.source || null,
    loss_reason: form.value.loss_reason || null,
    description: form.value.description || null,
    next_step: form.value.next_step || null,
    deal_type: form.value.deal_type || null,
    priority: form.value.priority || 'medium',
    competitor: form.value.competitor || null,
    contact_role: form.value.contact_role || null,
    lines: form.value.lines.map((l) => ({
      product_id: l.product_id || null,
      product_name: l.product_name || '',
      unit: l.unit || null,
      quantity: Number(l.quantity) || 0,
      unit_price: Number(l.unit_price) || 0,
      discount_percent: Number(l.discount_percent) || 0,
      subtotal: Number(l.subtotal) || 0,
    })),
  }
  if (form.value.contact_id) payload.contact_id = form.value.contact_id

  saving.value = true
  try {
    if (isEdit.value) {
      await crmApi.updateDeal(props.record.id, payload)
      ElMessage.success('已保存')
    } else {
      await crmApi.createDeal(payload)
      ElMessage.success('商机已创建')
    }
    dialogVisible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

watch(dialogVisible, async (v) => {
  if (!v) return
  if (isEdit.value) {
    await loadDeal()
  } else {
    resetForm()
    if (!customerOptions.value.length) searchCustomers('')
  }
  if (!productOptions.value.length) loadProducts()
})

const statusOptions = [
  { value: 'open', label: '进行中' },
  { value: 'won', label: '赢单' },
  { value: 'lost', label: '输单' },
  { value: 'abandoned', label: '放弃' },
]
const sourceOptions = [
  '官网', '公众号', '小红书', '抖音', '线下', '转介绍', '电话', '导入', '营销活动', '其他',
].map((v) => ({ value: v, label: v }))
const dealTypeOptions = [
  { value: '新业务', label: '新业务' },
  { value: '续约', label: '续约' },
  { value: '升级', label: '升级' },
  { value: '交叉销售', label: '交叉销售' },
]
const priorityOptions = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]
const contactRoleOptions = [
  { value: '决策者', label: '决策者' },
  { value: '影响者', label: '影响者' },
  { value: '使用者', label: '使用者' },
  { value: '评估者', label: '评估者' },
]
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="760px"
    destroy-on-close
    align-center
    class="deal-form-dialog"
  >
    <el-form label-width="100px" :model="form" class="deal-form">
      <section class="deal-form__section">
        <h4 class="deal-form__section-title">基本信息</h4>
        <el-form-item label="商机名称" required>
          <el-input v-model="form.title" placeholder="请输入商机名称" maxlength="200" />
        </el-form-item>
        <el-form-item label="客户" required>
          <el-select
            v-model="form.customer_id"
            filterable
            remote
            :remote-method="searchCustomers"
            :loading="customerLoading"
            placeholder="选择客户"
            style="width: 100%"
            @change="onCustomerChange"
          >
            <el-option
              v-for="c in customerOptions"
              :key="c.id"
              :label="c.company_name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人">
          <div class="deal-form__field-with-tag">
            <el-select
              v-model="form.contact_id"
              clearable
              :loading="contactLoading"
              :placeholder="form.customer_id ? '选择联系人' : '请先选择客户'"
              :disabled="!form.customer_id"
              style="width: 100%"
            >
              <el-option v-for="c in contactOptions" :key="c.id" :label="c.label" :value="c.id" />
            </el-select>
            <el-tag class="deal-form__new" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="商机类型">
          <div class="deal-form__field-with-tag">
            <el-select v-model="form.deal_type" clearable placeholder="请选择" style="width: 100%">
              <el-option v-for="o in dealTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-tag class="deal-form__new" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
      </section>

      <section class="deal-form__section">
        <h4 class="deal-form__section-title">销售信息</h4>
        <el-form-item label="销售管道" required>
          <el-select v-model="form.pipeline_id" placeholder="默认管道" style="width: 100%" @change="onPipelineChange">
            <el-option v-for="p in pipelines" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="阶段" required>
          <el-select v-model="form.stage_id" style="width: 100%" @change="onStageChange">
            <el-option v-for="s in stages" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <div class="deal-form__amount-row">
          <el-form-item label="商机金额" class="deal-form__amount">
            <el-input-number
              v-model="form.amount"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="0.00"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="概率" class="deal-form__probability">
            <div class="deal-form__probability-input">
              <el-input-number
                v-model="form.probability"
                :min="0"
                :max="100"
                :precision="0"
                :controls="false"
                style="width: 100%"
              />
              <span class="deal-form__percent">%</span>
            </div>
          </el-form-item>
        </div>
        <el-form-item label="预计成交日">
          <el-date-picker
            v-model="form.expected_close_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择日期"
            style="width: 100%"
          />
        </el-form-item>
      </section>

      <section class="deal-form__section">
        <h4 class="deal-form__section-title">分类与跟踪</h4>
        <el-form-item label="优先级">
          <div class="deal-form__field-with-tag">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option v-for="o in priorityOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-tag class="deal-form__new" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="form.source" clearable placeholder="请选择" style="width: 100%">
            <el-option v-for="s in sourceOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="竞争对手">
          <div class="deal-form__field-with-tag">
            <el-input v-model="form.competitor" maxlength="200" placeholder="主要竞争对手名称" />
            <el-tag class="deal-form__new" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="联系人角色">
          <div class="deal-form__field-with-tag">
            <el-select v-model="form.contact_role" clearable placeholder="请选择" style="width: 100%">
              <el-option v-for="o in contactRoleOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-tag class="deal-form__new" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
        <template v-if="isEdit">
          <el-form-item label="商机状态">
            <el-select v-model="form.status" style="width: 100%">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.status === 'lost'" label="输单原因">
            <el-input v-model="form.loss_reason" maxlength="200" />
          </el-form-item>
        </template>
      </section>

      <section class="deal-form__section">
        <h4 class="deal-form__section-title">描述与下一步</h4>
        <el-form-item label="下一步行动">
          <div class="deal-form__field-with-tag">
            <el-input v-model="form.next_step" maxlength="200" placeholder="如：周三约客户演示方案" />
            <el-tag class="deal-form__new" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="商机描述" class="deal-form__description">
          <div class="deal-form__description-wrap">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="4"
              maxlength="2000"
              show-word-limit
              placeholder="请输入商机详细背景、需求摘要..."
            />
            <el-tag class="deal-form__new deal-form__new--top" size="small" effect="plain">NEW</el-tag>
          </div>
        </el-form-item>
      </section>

      <section class="deal-form__section deal-form__section--last">
        <h4 class="deal-form__section-title">产品明细</h4>
        <div class="deal-lines">
          <el-table :data="form.lines" size="small" border>
            <el-table-column label="产品" min-width="180">
              <template #default="{ row }">
                <el-select
                  v-model="row.product_id"
                  filterable
                  clearable
                  placeholder="选择产品"
                  :loading="productLoading"
                  style="width: 100%"
                  @change="onLineProductChange(row)"
                >
                  <el-option v-for="p in productOptions" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="150">
              <template #default="{ row }">
                <el-input v-model="row.product_name" size="small" placeholder="明细名称" />
              </template>
            </el-table-column>
            <el-table-column label="单位" width="80">
              <template #default="{ row }">
                <el-input v-model="row.unit" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="数量" width="100">
              <template #default="{ row }">
                <el-input-number v-model="row.quantity" :min="0" :precision="2" :controls="false" size="small" style="width: 100%" @change="computeLineSubtotal(row)" />
              </template>
            </el-table-column>
            <el-table-column label="单价" width="110">
              <template #default="{ row }">
                <el-input-number v-model="row.unit_price" :min="0" :precision="2" :controls="false" size="small" style="width: 100%" @change="computeLineSubtotal(row)" />
              </template>
            </el-table-column>
            <el-table-column label="折扣%" width="90">
              <template #default="{ row }">
                <el-input-number v-model="row.discount_percent" :min="0" :max="100" :precision="2" :controls="false" size="small" style="width: 100%" @change="computeLineSubtotal(row)" />
              </template>
            </el-table-column>
            <el-table-column label="小计" width="110" align="right">
              <template #default="{ row }">
                <span class="deal-lines__subtotal">{{ row.subtotal }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeLine($index)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="deal-lines__footer">
            <el-button size="small" @click="addLine">+ 添加明细</el-button>
            <span class="deal-lines__total">合计：¥{{ linesTotal }}</span>
          </div>
        </div>
      </section>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.deal-form__section {
  margin-bottom: 16px;
  padding: 14px 16px 2px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: linear-gradient(180deg, #fcfdff 0%, #f8fafc 100%);
}

.deal-form__section--last {
  margin-bottom: 0;
}

.deal-form__section-title {
  margin: 0 0 14px;
  padding-left: 10px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.deal-form__field-with-tag {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.deal-form__field-with-tag > :first-child {
  flex: 1;
  min-width: 0;
}

.deal-form__new {
  flex-shrink: 0;
  border-color: #b3d8ff;
  color: var(--el-color-primary);
  background: #ecf5ff;
}

.deal-form__new--top {
  align-self: flex-start;
  margin-top: 8px;
}

.deal-form__description-wrap {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
}

.deal-form__description-wrap :deep(.el-textarea) {
  flex: 1;
}

.deal-form__amount-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.deal-form__amount {
  flex: 1;
  min-width: 0;
}

.deal-form__probability {
  width: 160px;
  flex-shrink: 0;
}

.deal-form__probability :deep(.el-form-item__label) {
  width: 48px !important;
  padding-right: 8px;
}

.deal-form__probability-input {
  display: flex;
  align-items: center;
  gap: 4px;
}

.deal-form__percent {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.deal-lines { width: 100%; }
.deal-lines__subtotal { font-variant-numeric: tabular-nums; }
.deal-lines__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.deal-lines__total { font-weight: 600; color: var(--el-color-primary); }

.deal-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.deal-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>
