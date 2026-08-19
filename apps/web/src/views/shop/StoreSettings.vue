<script setup>
/**
 * A19 单店设置。对照 PRD 01-管理端UI.html #a19
 * Tab：本店展示 · 退款默认
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import ShopSettingsNav from '../../components/shop/ShopSettingsNav.vue'
import { useCurrentShop } from '../../composables/useCurrentShop'

const route = useRoute()
const { currentId } = useCurrentShop()
const loading = ref(false)
const savingDisplay = ref(false)
const savingRefund = ref(false)
const logoUploading = ref(false)
const logoInput = ref(null)
const activeTab = ref('display')
const categories = ref([])

const form = reactive({
  shop_id: null,
  name: '',
  logo_url: '',
  intro: '',
  service_phone: '',
  theme_color: '#1677ff',
  close_order_minutes: 30,
  default_category_id: null,
  default_refund_policy: 'before_fulfill',
  status: '',
})

const REFUND_OPTS = [
  {
    value: 'always_allow',
    title: '随时可退',
    desc: '买家付款后至履约完成前均可自助申请退款（课程类常用）',
  },
  {
    value: 'before_fulfill',
    title: '履约前可退',
    desc: '零履约前可自助退；履约/使用后仅人工审核',
  },
  {
    value: 'manual_only',
    title: '仅人工审核',
    desc: '买家端不展示自助退款；须商家在订单页人工发起',
  },
]

async function load() {
  loading.value = true
  try {
    const shopId = currentId.value || route.query.shop_id || undefined
    const [{ data }, { data: cats }] = await Promise.all([
      api.get('/api/v1/shop/stores/settings', { params: shopId ? { shop_id: shopId } : undefined }),
      api.get('/api/v1/shop/platform-categories', { params: { status: 'enabled' } }),
    ])
    categories.value = cats.items || []
    Object.assign(form, {
      shop_id: data.shop_id,
      name: data.name || '',
      logo_url: data.logo_url || '',
      intro: data.intro || '',
      service_phone: data.service_phone || '',
      theme_color: data.theme_color || '#1677ff',
      close_order_minutes: data.close_order_minutes ?? 30,
      default_category_id: data.default_category_id || null,
      default_refund_policy: data.default_refund_policy || 'before_fulfill',
      status: data.status || '',
    })
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const LOGO_ACCEPT = 'image/jpeg,image/png,image/webp'
const LOGO_MAX_BYTES = 2 * 1024 * 1024

async function uploadLogo(ev) {
  const file = ev.target?.files?.[0]
  if (!file) return
  if (file.size > LOGO_MAX_BYTES) {
    ElMessage.warning('Logo 不能超过 2MB')
    if (logoInput.value) logoInput.value.value = ''
    return
  }
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    ElMessage.warning('请上传 jpg / png / webp 格式图片')
    if (logoInput.value) logoInput.value.value = ''
    return
  }
  logoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post('/api/v1/shop/content/files', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    form.logo_url = data.file_url || data.url || ''
    ElMessage.success('Logo 已上传')
  } catch (e) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    logoUploading.value = false
    if (logoInput.value) logoInput.value.value = ''
  }
}

async function saveDisplay() {
  if (!(form.name || '').trim()) {
    ElMessage.warning('请填写店铺名称（对外）')
    return
  }
  savingDisplay.value = true
  try {
    const { data } = await api.patch('/api/v1/shop/stores/settings/display', {
      shop_id: form.shop_id,
      name: form.name.trim(),
      logo_url: form.logo_url || '',
      intro: form.intro,
      service_phone: form.service_phone,
      theme_color: form.theme_color,
      close_order_minutes: form.close_order_minutes,
      default_category_id: form.default_category_id || undefined,
      clear_default_category: !form.default_category_id,
    })
    form.default_category_id = data.default_category_id || null
    ElMessage.success('已保存本店展示')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingDisplay.value = false
  }
}

async function saveRefund() {
  savingRefund.value = true
  try {
    await api.patch('/api/v1/shop/stores/settings/refund', {
      shop_id: form.shop_id,
      default_refund_policy: form.default_refund_policy,
    })
    ElMessage.success('已保存退款默认')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingRefund.value = false
  }
}

onMounted(load)

watch(currentId, () => {
  load()
})
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="hd">
      <div>
        <div class="crumb">设置 / <b>单店设置</b></div>
        <h3>单店设置</h3>
      </div>
      <el-tag v-if="form.name" size="small" type="primary">当前店 · {{ form.name }}</el-tag>
    </div>
    <ShopSettingsNav current="store" />
    <el-alert
      type="success"
      :closable="false"
      show-icon
      title="此处配置只影响当前这家店在买家端的展示与新建商品默认策略；不改历史已售订单。"
      style="margin-bottom: 14px"
    />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="本店展示" name="display">
        <el-form label-position="top" style="max-width: 560px">
          <el-form-item label="店铺名称（对外）" required>
            <el-input v-model="form.name" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="店铺 Logo">
            <div class="logo-row">
              <button
                type="button"
                class="logo-box"
                :disabled="logoUploading"
                @click="logoInput?.click()"
              >
                <img v-if="form.logo_url" :src="form.logo_url" alt="Logo" />
                <span v-else>上传</span>
              </button>
              <div>
                <input
                  ref="logoInput"
                  type="file"
                  :accept="LOGO_ACCEPT"
                  hidden
                  @change="uploadLogo"
                />
                <el-button :loading="logoUploading" @click="logoInput?.click()">
                  选择文件
                </el-button>
                <el-button v-if="form.logo_url" link type="danger" @click="form.logo_url = ''">
                  清除
                </el-button>
              </div>
            </div>
            <div class="hint">
              支持 jpg / png / webp，单张不超过 2MB；建议 200×200 像素以上正方形，买家端按 1:1 展示。
            </div>
          </el-form-item>
          <el-form-item label="店铺简介">
            <el-input v-model="form.intro" type="textarea" :rows="3" maxlength="500" show-word-limit />
          </el-form-item>
          <el-form-item label="客服电话（展示）">
            <el-input v-model="form.service_phone" style="width: 220px" placeholder="如 020-12345678" />
          </el-form-item>
          <el-form-item label="买家端主题色">
            <el-color-picker v-model="form.theme_color" />
            <span class="color-val">{{ form.theme_color }}</span>
          </el-form-item>
          <el-form-item label="未支付关单(分钟)">
            <el-input-number v-model="form.close_order_minutes" :min="5" :max="1440" />
          </el-form-item>
          <el-form-item label="默认平台类目">
            <el-select
              v-model="form.default_category_id"
              clearable
              filterable
              placeholder="新建商品默认继承"
              style="width: 100%"
            >
              <el-option
                v-for="c in categories"
                :key="c.id"
                :label="c.path_label || c.name"
                :value="c.id"
              />
            </el-select>
            <div class="hint">新建商品未选手动类目时继承此处；来源平台启用类目。</div>
          </el-form-item>
          <el-button type="primary" :loading="savingDisplay" @click="saveDisplay">保存本店展示</el-button>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="退款默认" name="refund">
        <p class="hint" style="margin-bottom: 12px">
          未单独设退款策略的商品继承此处默认。新建商品可在编辑页逐品覆盖。
        </p>
        <el-radio-group v-model="form.default_refund_policy" class="refund-group">
          <div
            v-for="opt in REFUND_OPTS"
            :key="opt.value"
            class="refund-card"
            :class="{ on: form.default_refund_policy === opt.value }"
            @click="form.default_refund_policy = opt.value"
          >
            <el-radio :value="opt.value">
              <b>{{ opt.title }}</b>
              <div class="desc">{{ opt.desc }}</div>
            </el-radio>
          </div>
        </el-radio-group>
        <el-button type="primary" :loading="savingRefund" style="margin-top: 14px" @click="saveRefund">
          保存退款默认
        </el-button>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page-card {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
}
.hd {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.hd h3 {
  margin: 0;
  font-size: 16px;
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
.logo-row {
  display: flex;
  gap: 12px;
  align-items: center;
}
.logo-box {
  width: 80px;
  height: 80px;
  border: 1px dashed #ccc;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #999;
  overflow: hidden;
  background: #fafafa;
  padding: 0;
  cursor: pointer;
}
.logo-box:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}
.logo-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.color-val {
  margin-left: 10px;
  color: #666;
  font-size: 13px;
}
.hint {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin-top: 4px;
}
.refund-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 560px;
}
.refund-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  background: #fff;
}
.refund-card.on {
  border-color: #d3adf7;
  background: #f9f0ff;
}
.refund-card .desc {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
  font-weight: normal;
  white-space: normal;
}
</style>
