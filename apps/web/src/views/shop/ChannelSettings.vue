<script setup>
/**
 * A23 公域对接设置。对照 PRD 01-管理端UI.html #a23 · #a23-t · #a23-s · #a23-webhook
 * 一次性：选链路/路径、绑店、回调验通。日常映射在 A14。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions'
import { formatDateTime } from '../../utils/datetime'

const router = useRouter()
const auth = useAuthStore()
const canWrite = computed(() => hasPermission(auth.permissions || [], 'shop.channel.write'))

const loading = ref(false)
const binding = ref(false)
const saving = ref(false)
const testing = ref(false)
const data = ref(null)

const form = reactive({
  deal_link: '1',
  path_mode: 'A',
  bind_scope: 'tenant',
  douyin_shop_id: '',
  douyin_webhook_secret: '',
})

const badgeType = computed(() => {
  if (data.value?.webhook_verified) return 'success'
  if (data.value?.douyin_shop_id) return 'warning'
  return 'info'
})

function applyData(res) {
  data.value = res
  form.deal_link = res.deal_link || '1'
  form.path_mode = res.path_mode || 'A'
  form.bind_scope = res.bind_scope || 'tenant'
  form.douyin_shop_id = res.douyin_shop_id || ''
  form.douyin_webhook_secret = ''
}

async function load() {
  loading.value = true
  try {
    const { data: res } = await api.get('/api/v1/shop/channel-settings')
    applyData(res)
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function bindShop() {
  if (!form.douyin_shop_id.trim()) {
    ElMessage.warning('请填写外部店铺 ID')
    return
  }
  binding.value = true
  try {
    const body = {
      douyin_shop_id: form.douyin_shop_id.trim(),
      bind_scope: 'tenant',
    }
    if (form.douyin_webhook_secret.trim()) {
      body.douyin_webhook_secret = form.douyin_webhook_secret.trim()
    }
    const { data: res } = await api.post('/api/v1/shop/channel-settings/bind', body)
    applyData(res)
    ElMessage.success('绑定状态已更新为可用')
  } catch (e) {
    ElMessage.error(e.message || '保存绑店失败')
  } finally {
    binding.value = false
  }
}

async function savePrefs() {
  if (!form.douyin_shop_id.trim() && !data.value?.douyin_shop_id) {
    ElMessage.warning('请先完成绑店')
    return
  }
  saving.value = true
  try {
    const body = {
      deal_link: form.deal_link,
      path_mode: form.path_mode,
      bind_scope: 'tenant',
      douyin_shop_id: form.douyin_shop_id.trim() || data.value?.douyin_shop_id,
    }
    if (form.douyin_webhook_secret.trim()) {
      body.douyin_webhook_secret = form.douyin_webhook_secret.trim()
    }
    const { data: res } = await api.post('/api/v1/shop/channel-settings', body)
    applyData(res)
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  testing.value = true
  try {
    const { data: res } = await api.post('/api/v1/shop/channel-settings/send-test')
    applyData(res)
    ElMessage.success('测试已发送')
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    testing.value = false
  }
}

async function copyWebhook() {
  const url = data.value?.webhook_url || ''
  if (!url) {
    ElMessage.warning('回调未配置')
    return
  }
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('已复制')
  } catch {
    ElMessage.info(url)
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card a23">
    <div class="hd">
      <div>
        <div class="crumb">
          <a @click.prevent="router.push('/shop/settings')">设置中心</a>
          / <b>公域对接</b>
          · 日常映射
          <a @click.prevent="router.push('/shop/channel-mappings')">商品映射 →</a>
        </div>
        <h3>公域对接</h3>
      </div>
      <el-tag v-if="data" :type="badgeType" effect="plain">
        {{ data.combo_label }}
      </el-tag>
    </div>

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="怎么用？"
      description="企业管理员在此完成对接中的选链路、选路径、绑店铺、回调验通；店铺管理员在商品映射页做日常上架同步。未开通组合灰显。"
      style="margin-bottom: 16px"
    />

    <section class="card-block">
      <h4>步骤 1–2 · 选链路 / 选路径</h4>
      <p class="sec-title">成交链路 · 买家在哪付钱</p>
      <label class="choice on">
        <input v-model="form.deal_link" type="radio" value="1" :disabled="!canWrite" />
        <span><b>链路 ①</b> 抖店付 → 短信领权 → 小程序履约</span>
      </label>
      <label class="choice disabled">
        <input type="radio" disabled />
        <span>
          <b>链路 ②</b> 挂小程序 → 小程序内微信付
          <em>套餐未开通 · Phase 1 二选一</em>
        </span>
      </label>
      <p class="sec-title">抖店主体 · 与平台渠道配置一致</p>
      <label class="choice on">
        <input v-model="form.path_mode" type="radio" value="A" :disabled="!canWrite" />
        <span><b>路径 A</b> 平台官方店</span>
      </label>
      <label class="choice disabled">
        <input type="radio" disabled />
        <span>
          <b>路径 B</b> 商家自有抖店
          <em>本期未开通</em>
        </span>
      </label>
    </section>

    <section class="card-block">
      <h4>步骤 3 · 绑定外部店铺</h4>
      <el-form label-position="top" style="max-width: 520px">
        <el-form-item label="绑定范围">
          <el-select v-model="form.bind_scope" disabled style="width: 100%">
            <el-option label="租户统一绑平台店（路径 A 默认）" value="tenant" />
            <el-option label="按店" value="per_store" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="外部店铺 ID" required>
          <el-input
            v-model="form.douyin_shop_id"
            :disabled="!canWrite"
            placeholder="请填写外部店铺 ID"
          />
        </el-form-item>
        <el-form-item label="Webhook 密钥">
          <el-input
            v-model="form.douyin_webhook_secret"
            type="password"
            show-password
            :disabled="!canWrite"
            placeholder="留空则不修改已有密钥"
          />
        </el-form-item>
        <el-form-item label="绑定状态">
          <el-tag :type="data?.bind_status === 'available' ? 'success' : 'info'" size="small">
            {{ data?.bind_status_label || '未绑定' }}
          </el-tag>
          <span v-if="data?.last_synced_at" class="muted">
            · 最近同步 {{ formatDateTime(data.last_synced_at, { withSeconds: false }) }}
          </span>
        </el-form-item>
        <el-button v-if="canWrite" type="primary" :loading="binding" @click="bindShop">
          保存绑店
        </el-button>
      </el-form>
    </section>

    <section class="card-block webhook">
      <h4>步骤 5 · 回调验通</h4>
      <p class="webhook-line">
        回调地址：<code>{{ data?.webhook_url || '—' }}</code>
        <el-button size="small" @click="copyWebhook">复制</el-button>
        <el-button
          v-if="canWrite"
          type="primary"
          size="small"
          :loading="testing"
          @click="sendTest"
        >
          发送测试
        </el-button>
      </p>
      <p class="muted">验通后，商品映射页映射商品才可收真实抖店单。</p>
      <el-tag v-if="data?.webhook_verified" type="success" size="small">已验通</el-tag>
    </section>

    <el-button v-if="canWrite" type="primary" :loading="saving" @click="savePrefs">
      保存对接设置
    </el-button>
    <p v-else class="muted">当前角色仅可查看摘要。</p>
  </div>
</template>

<style scoped>
.a23 .hd {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}
.a23 h3 {
  margin: 0;
}
.crumb {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.crumb a {
  color: #1677ff;
  cursor: pointer;
}
.card-block {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 14px;
  max-width: 640px;
  background: #fafafa;
}
.card-block h4 {
  margin: 0 0 10px;
  font-size: 14px;
}
.sec-title {
  font-weight: 600;
  margin: 12px 0 8px;
  font-size: 13px;
}
.choice {
  display: block;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  margin-bottom: 8px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.6;
}
.choice.on {
  border-color: #1677ff;
}
.choice.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.choice em {
  display: block;
  color: #999;
  font-size: 11px;
  font-style: normal;
}
.webhook {
  background: #eff6ff;
  border-color: #91caff;
}
.webhook-line {
  font-size: 13px;
  color: #1e40af;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.webhook-line code {
  font-size: 12px;
  word-break: break-all;
}
.muted {
  color: #909399;
  font-size: 12px;
  margin: 8px 0 0;
}
</style>
