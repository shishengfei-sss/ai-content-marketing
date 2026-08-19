<script setup>
/**
 * A03 商品新建/编辑。对照 PRD 01-管理端UI.html #a03 · #a03-course · #a03-digital · #a03-service
 * 类型保存后锁定；课→专栏 / 资料→资料包 / 服务→服务定义。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useCurrentShop } from '../../composables/useCurrentShop'
import { authShopFileUrl } from '../../utils/shopContentUrl'

const route = useRoute()
const router = useRouter()
const { currentId } = useCurrentShop()
const loading = ref(false)
const saving = ref(false)
const product = ref(null)
const isNew = computed(() => route.name === 'ShopProductNew' || route.params.id === 'new')
const pageMode = computed(() => (route.query.mode === 'view' ? 'view' : 'edit'))
const readonly = computed(() => {
  if (pageMode.value === 'view') return true
  const s = product.value?.status
  return s === 'pending_review' || s === 'approved' || s === 'on_sale'
})
const coverPreviewUrl = computed(() => authShopFileUrl(form.cover_url))

const form = reactive({
  type: 'course',
  name: '',
  subtitle: '',
  intro: '',
  price_yuan: 199,
  line_price_yuan: null,
  refund_policy: 'before_fulfill',
  category_id: '',
  ref_id: '',
  cover_url: '',
  cover_name: '',
})

const columns = ref([])
const packages = ref([])
const offers = ref([])
const categories = ref([])
const uploading = ref(false)
const fileInput = ref(null)

const STATUS_LABEL = {
  draft: '草稿',
  pending_review: '审核中',
  approved: '已通过',
  on_sale: '在售',
  rejected: '已驳回',
  off_sale: '已下架',
}
const TYPE_CARDS = [
  { type: 'course', title: '课程', desc: '专栏 / 单课' },
  { type: 'digital', title: '数字资料', desc: '资料包下载' },
  { type: 'service', title: '服务', desc: '预约 / 次数卡' },
]
const REF_TYPE = { course: 'column', digital: 'digital_package', service: 'service_offer' }

const refundOptions = computed(() => {
  if (form.type === 'service') {
    return [
      { value: 'before_fulfill', label: '未使用可退' },
      { value: 'always_allow', label: '随时可退' },
      { value: 'manual_only', label: '仅人工审核' },
    ]
  }
  return [
    { value: 'before_fulfill', label: '履约前可退' },
    { value: 'always_allow', label: '随时可退' },
    { value: 'manual_only', label: '仅人工审核' },
  ]
})

const selectedColumn = computed(() => columns.value.find((c) => c.id === form.ref_id))
const selectedPackage = computed(() => packages.value.find((p) => p.id === form.ref_id))
const selectedOffer = computed(() => offers.value.find((o) => o.id === form.ref_id))

const columnSummary = computed(() => {
  const c = selectedColumn.value
  if (!c) return '请选择已发布专栏'
  return `${c.lesson_count || 0} 课时 · ${c.published_lesson_count || 0} 节已发布 · 状态：已发布`
})
const packageSummary = computed(() => {
  const p = selectedPackage.value
  if (!p) return '请选择已发布资料包'
  const mode = p.deliver_mode === 'online_view' ? '在线查看' : '下载'
  return `交付：${mode} · ${p.file_count || 0} 个文件 · 状态：已发布`
})
const offerSummary = computed(() => {
  const o = selectedOffer.value
  if (!o) return '请选择已发布服务'
  if (o.mode === 'times_card') {
    return `模式：次数卡 · ${o.total_times || '-'} 次 / ${o.valid_days || '-'} 天 · 单次 ${o.duration_minutes || 60} 分 · 已发布`
  }
  return `模式：预约 · 单次 ${o.duration_minutes || 60} 分 · 已发布`
})

async function loadCategories() {
  const { data } = await api.get('/api/v1/shop/platform-categories', {
    params: { status: 'enabled' },
  })
  categories.value = data.items || []
  if (!form.category_id && categories.value.length) {
    form.category_id = categories.value[0].id
  }
}

async function loadOptions() {
  const shopParams = { status: 'published', page_size: 100, shop_id: currentId.value || undefined }
  const [c, p, o] = await Promise.all([
    api.get('/api/v1/shop/columns', { params: shopParams }),
    api.get('/api/v1/shop/digital-packages', { params: shopParams }),
    api.get('/api/v1/shop/service-offers', { params: shopParams }),
  ])
  columns.value = c.data.items || []
  packages.value = p.data.items || []
  offers.value = o.data.items || []
}

function yuanToCents(v) {
  if (v === null || v === undefined || v === '') return null
  return Math.round(Number(v) * 100)
}
function centsToYuan(c) {
  if (c === null || c === undefined) return null
  return Number(c) / 100
}

async function load() {
  loading.value = true
  try {
    await Promise.all([loadOptions(), loadCategories()])
    if (isNew.value) {
      product.value = null
      return
    }
    const { data } = await api.get(`/api/v1/shop/products/${route.params.id}`)
    product.value = data
    form.type = data.type
    form.name = data.name || ''
    form.subtitle = data.subtitle || ''
    form.intro = (data.extra && data.extra.intro) || ''
    form.price_yuan = centsToYuan(data.price_cents) ?? 0
    form.line_price_yuan = centsToYuan(data.line_price_cents)
    form.refund_policy = data.refund_policy || 'before_fulfill'
    form.category_id = data.category_id || form.category_id || ''
    form.ref_id = data.ref_id || ''
    form.cover_url = data.cover_url || ''
    form.cover_name = data.cover_url ? '已上传封面' : ''
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => form.type,
  () => {
    if (isNew.value && !product.value) form.ref_id = ''
  }
)

function selectType(t) {
  if (!isNew.value || product.value) return
  form.type = t
  form.ref_id = ''
}

function buildBody() {
  const price_cents = yuanToCents(form.price_yuan)
  const line_price_cents = yuanToCents(form.line_price_yuan)
  if (!form.name.trim()) throw new Error('请填写名称')
  if (price_cents === null || price_cents < 0) throw new Error('请填写售价')
  if (line_price_cents != null && line_price_cents < price_cents) throw new Error('划线价不能低于售价')
  const body = {
    name: form.name.trim(),
    subtitle: form.subtitle || null,
    price_cents,
    line_price_cents,
    refund_policy: form.refund_policy,
    category_id: form.category_id || null,
    cover_url: form.cover_url || null,
    ref_type: REF_TYPE[form.type],
    ref_id: form.ref_id || null,
    extra: { intro: (form.intro || '').slice(0, 500) || null },
  }
  return body
}

async function saveDraft({ silent = false } = {}) {
  saving.value = true
  try {
    const body = buildBody()
    if (isNew.value && !product.value) {
      if (!currentId.value) {
        throw new Error('请先在顶栏选择当前店铺')
      }
      const { data } = await api.post('/api/v1/shop/products', {
        type: form.type,
        shop_id: currentId.value,
        ...body,
      })
      product.value = data
      if (!silent) ElMessage.success('已存草稿')
      await router.replace({ name: 'ShopProductEdit', params: { id: data.id }, query: { mode: 'edit' } })
    } else {
      const id = product.value?.id || route.params.id
      const { data } = await api.patch(`/api/v1/shop/products/${id}`, body)
      product.value = data
      if (!silent) ElMessage.success('已存草稿')
    }
    return product.value
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
    throw e
  } finally {
    saving.value = false
  }
}

async function submitReview() {
  if (!form.cover_url) {
    ElMessage.warning('请补全封面')
    return
  }
  if (!form.category_id) {
    ElMessage.warning('请补全平台类目')
    return
  }
  if (!form.ref_id) {
    const tip =
      form.type === 'course' ? '请选择关联专栏' : form.type === 'digital' ? '请选择关联资料包' : '请选择关联服务'
    ElMessage.warning(tip)
    return
  }
  try {
    const saved = await saveDraft({ silent: true })
    const id = saved?.id
    if (!id) return
    await api.post(`/api/v1/shop/products/${id}/submit-review`, {})
    ElMessage.success('已提交，预计 1 工作日')
    router.push({ name: 'ShopProducts', query: { status: 'pending_review' } })
  } catch (e) {
    if (e?.message && !String(e.message).includes('保存')) {
      ElMessage.error(e.message || '提交审核失败')
    }
  }
}

async function publish() {
  try {
    const { data } = await api.post(`/api/v1/shop/products/${product.value.id}/publish`)
    product.value = data
    ElMessage.success('已上架')
    router.push({ name: 'ShopProducts' })
  } catch (e) {
    ElMessage.error(e.message || '上架失败')
  }
}

async function onCover(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('封面不能超过 2MB')
    return
  }
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    ElMessage.warning('请上传 jpg/png')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post('/api/v1/shop/content/files', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.cover_url = data.file_url
    form.cover_name = data.file_name
    ElMessage.success('封面已上传')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="a03">
    <div class="head">
      <el-button link type="primary" @click="router.push({ name: 'ShopProducts' })">← 返回列表</el-button>
      <span v-if="product" class="status">状态：{{ STATUS_LABEL[product.status] || product.status }}</span>
    </div>

    <div class="type-cards">
      <button
        v-for="c in TYPE_CARDS"
        :key="c.type"
        type="button"
        class="type-card"
        :class="{ on: form.type === c.type, locked: !isNew || !!product }"
        :disabled="(!isNew || !!product) && form.type !== c.type"
        @click="selectType(c.type)"
      >
        <b>{{ c.title }}</b>
        <div class="desc">{{ c.desc }}</div>
      </button>
    </div>

    <el-form label-width="120px" class="form" style="max-width: 720px">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" :disabled="readonly" maxlength="200" />
      </el-form-item>
      <el-form-item label="副标题">
        <el-input v-model="form.subtitle" :disabled="readonly" maxlength="300" />
      </el-form-item>
      <el-form-item label="平台类目" required>
        <el-select
          v-model="form.category_id"
          filterable
          :disabled="readonly"
          placeholder="提交审核时必填"
          style="width: 100%"
        >
          <el-option
            v-for="c in categories"
            :key="c.id"
            :label="c.path_label || c.name"
            :value="c.id"
          />
        </el-select>
        <div class="hint">来源平台类目；新建默认继承店铺默认类目，可改选；禁售类目不可提交。</div>
      </el-form-item>
      <el-form-item label="商品简介">
        <el-input
          v-model="form.intro"
          type="textarea"
          :rows="3"
          :disabled="readonly"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="售价" required>
        <el-input-number
          v-model="form.price_yuan"
          :min="0"
          :precision="2"
          :step="1"
          :disabled="readonly"
        />
        <span class="unit">元</span>
      </el-form-item>
      <el-form-item label="划线价">
        <el-input-number
          v-model="form.line_price_yuan"
          :min="0"
          :precision="2"
          :step="1"
          :disabled="readonly"
        />
        <span class="unit">元</span>
      </el-form-item>

      <template v-if="form.type === 'course'">
        <el-form-item label="关联专栏" required>
          <el-select
            v-model="form.ref_id"
            :disabled="readonly"
            filterable
            clearable
            placeholder="选已发布专栏"
            style="width: 100%"
          >
            <el-option v-for="c in columns" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
          <div class="hint">无合适专栏 → 内容 · 专栏 新建并发布后再选。</div>
        </el-form-item>
        <el-form-item label="专栏摘要">
          <div class="summary">{{ columnSummary }}</div>
        </el-form-item>
      </template>

      <template v-else-if="form.type === 'digital'">
        <el-form-item label="关联资料包" required>
          <el-select
            v-model="form.ref_id"
            :disabled="readonly"
            filterable
            clearable
            placeholder="选已发布资料包"
            style="width: 100%"
          >
            <el-option v-for="p in packages" :key="p.id" :label="p.title" :value="p.id" />
          </el-select>
          <div class="hint">须已发布且包内 ≥1 文件。</div>
        </el-form-item>
        <el-form-item label="资料摘要">
          <div class="summary">{{ packageSummary }}</div>
        </el-form-item>
      </template>

      <template v-else>
        <el-form-item label="关联服务" required>
          <el-select
            v-model="form.ref_id"
            :disabled="readonly"
            filterable
            clearable
            placeholder="选已发布服务"
            style="width: 100%"
          >
            <el-option v-for="o in offers" :key="o.id" :label="o.title" :value="o.id" />
          </el-select>
          <div class="hint">预约模式另须配置开放时段。</div>
        </el-form-item>
        <el-form-item label="服务摘要">
          <div class="summary">{{ offerSummary }}</div>
        </el-form-item>
      </template>

      <el-form-item label="退款策略" required>
        <el-select v-model="form.refund_policy" :disabled="readonly" style="width: 100%">
          <el-option v-for="o in refundOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>

      <el-form-item label="封面" required>
        <div class="cover-field">
          <div v-if="form.cover_url" class="cover-preview">
            <img :src="coverPreviewUrl" alt="封面预览" />
          </div>
          <div class="upload-row">
            <el-button :disabled="readonly" :loading="uploading" @click="fileInput?.click()">
              {{ form.cover_url ? '更换封面' : '上传 jpg/png · ≤2MB' }}
            </el-button>
            <span v-if="form.cover_name" class="file-name">{{ form.cover_name }}</span>
            <span v-else-if="form.cover_url" class="file-name">已上传封面</span>
            <span v-else class="hint">提交审核时必填 · 未选择文件</span>
          </div>
          <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="onCover" />
        </div>
      </el-form-item>
    </el-form>

    <div v-if="product?.status === 'rejected'" class="reject-box">
      <b>驳回原因</b>：请按审核意见修改后重新提交审核。
    </div>

    <div class="foot">
      <el-button @click="router.push({ name: 'ShopProducts' })">取消</el-button>
      <el-button
        v-if="!readonly && (!product || ['draft', 'rejected', 'off_sale'].includes(product.status))"
        :loading="saving"
        @click="saveDraft"
      >
        存草稿
      </el-button>
      <el-button
        v-if="!readonly && (!product || ['draft', 'rejected', 'off_sale'].includes(product.status))"
        type="primary"
        @click="submitReview"
      >
        提交审核
      </el-button>
      <el-button
        v-if="product?.status === 'approved'"
        type="success"
        @click="publish"
      >
        上架
      </el-button>
      <el-button disabled title="功能即将开放">从创作顾问导入（Phase 2）</el-button>
    </div>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.status { color: var(--el-text-color-secondary); }
.type-cards { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.type-card {
  flex: 1; min-width: 140px; text-align: left; padding: 12px 14px;
  border: 1px solid var(--el-border-color); border-radius: 8px; background: #fff; cursor: pointer;
}
.type-card.on { border-color: var(--el-color-primary); box-shadow: 0 0 0 1px var(--el-color-primary) inset; }
.type-card.locked:not(.on) { opacity: 0.45; cursor: not-allowed; }
.type-card .desc { color: #666; font-size: 12px; margin-top: 4px; }
.unit { margin-left: 8px; color: var(--el-text-color-secondary); }
.hint { font-size: 12px; color: #64748b; margin-top: 4px; line-height: 1.45; }
.summary {
  width: 100%; padding: 8px 10px; background: #f8fafc; border-radius: 6px;
  font-size: 12px; color: #334155; line-height: 1.5;
}
.upload-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cover-field { display: flex; flex-direction: column; gap: 10px; }
.cover-preview {
  width: 120px;
  height: 120px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}
.cover-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.file-name { color: var(--el-color-success); font-size: 13px; }
.hidden { display: none; }
.reject-box {
  margin: 12px 0; padding: 10px 12px; border-radius: 8px;
  border: 1px solid #ffccc7; background: #fff2f0; font-size: 12px; color: #cf1322;
}
.foot { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; margin-top: 16px; }
</style>
