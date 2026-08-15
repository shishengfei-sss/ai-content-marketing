<script setup>
/**
 * A15-S 短信与领权。对照 PRD 01-管理端UI.html #a15-sms
 * 签名/模板只读；商家可改领权域名与过期天数。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/client'
import ShopSettingsNav from '../../components/shop/ShopSettingsNav.vue'

const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const testing = ref(false)
const data = ref(null)

const form = reactive({
  claim_expire_days: 7,
  claim_landing_base: '',
})

const assigned = computed(() => data.value?.config_status === 'assigned')
const usageText = computed(() => {
  const u = data.value?.usage?.claim_sms_month
  if (!u) return '—'
  const lim = u.limit === 'unlimited' || u.limit == null ? '不限' : u.limit
  return `已用 ${u.used} / 合并上限 ${lim} 条`
})

async function load() {
  loading.value = true
  try {
    const { data: res } = await api.get('/api/v1/shop/settings/sms')
    data.value = res
    form.claim_expire_days = res.claim_expire_days ?? 7
    form.claim_landing_base = res.claim_landing_base || ''
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function checkDomain() {
  if (!(form.claim_landing_base || '').trim()) {
    ElMessage.warning('请填写领权链接域名')
    return
  }
  checking.value = true
  try {
    const { data: res } = await api.post('/api/v1/shop/settings/sms/check-domain', {
      claim_landing_base: form.claim_landing_base.trim(),
    })
    form.claim_landing_base = res.claim_landing_base || form.claim_landing_base
    ElMessage.success('域名可达')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '域名不可达')
  } finally {
    checking.value = false
  }
}

async function save() {
  if (!assigned.value) {
    ElMessage.warning('待平台配置')
    return
  }
  saving.value = true
  try {
    const { data: res } = await api.put('/api/v1/shop/settings/sms', {
      claim_landing_base: form.claim_landing_base.trim(),
      claim_expire_days: Number(form.claim_expire_days),
    })
    data.value = res
    ElMessage.success('领权参数已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  if (!assigned.value) {
    ElMessage.warning('模板未就绪')
    return
  }
  let mobile = ''
  try {
    const { value } = await ElMessageBox.prompt('请输入接收测试短信的手机号', '发送测试短信', {
      confirmButtonText: '发送',
      cancelButtonText: '取消',
      inputPattern: /^1\d{10}$/,
      inputErrorMessage: '请填写正确的手机号',
    })
    mobile = value
  } catch {
    return
  }
  testing.value = true
  try {
    const { data: res } = await api.post('/api/v1/shop/settings/sms/test', { mobile })
    ElMessage.success(res.message || '已发送')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    testing.value = false
  }
}

function contactManager() {
  ElMessage.info('请联系平台管家申请短信签名与领权模板')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card a15s">
    <div class="hd">
      <div>
        <div class="crumb">设置 / <b>短信与领权</b></div>
        <h3>短信与领权</h3>
      </div>
      <el-tag v-if="data" :type="assigned ? 'success' : 'warning'" effect="plain">
        {{ data.config_status_label }}
      </el-tag>
    </div>

    <ShopSettingsNav current="sms" />

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="抖店公域领权"
      description="买家在抖店付款后，系统发送领权短信 → 买家点链进小程序。签名/模板须供应商审核，由平台配置后此处只读展示。"
      style="margin-bottom: 14px"
    />

    <el-alert
      v-if="data && !assigned"
      type="warning"
      :closable="false"
      title="待平台配置"
      description="签名/模板显示「待平台配置」。保存已禁用，请联系管家。"
      style="margin-bottom: 14px"
    />

    <el-form v-if="data" label-position="top" class="form" style="max-width: 640px">
      <el-form-item label="短信签名（只读）">
        <div class="readonly">
          <span>{{ data.sms_signature || '待平台配置' }}</span>
          <el-tag
            size="small"
            :type="data.sms_signature_status === 'approved' ? 'success' : 'info'"
            style="margin-left: 8px"
          >
            {{ data.sms_signature_status === 'approved' ? '已分配' : '待平台配置' }}
          </el-tag>
        </div>
      </el-form-item>
      <el-form-item label="领权短信模板（只读）">
        <div class="readonly">
          <span v-if="data.claim_template_name">
            {{ data.claim_template_name }}
            <code v-if="data.claim_template_code_masked"> · {{ data.claim_template_code_masked }}</code>
          </span>
          <span v-else>待平台配置</span>
        </div>
      </el-form-item>
      <el-form-item label="领权过期天数" required>
        <div class="inline">
          <el-input-number
            v-model="form.claim_expire_days"
            :min="1"
            :max="30"
            :disabled="!assigned"
          />
          <span class="unit">天</span>
        </div>
      </el-form-item>
      <el-form-item label="领权链接域名" required>
        <div class="domain-row">
          <el-input
            v-model="form.claim_landing_base"
            :disabled="!assigned"
            placeholder="https://您的领权落地域名"
          />
          <el-button :disabled="!assigned" :loading="checking" @click="checkDomain">
            校验可达
          </el-button>
        </div>
        <div class="hint">商家可编辑 · 须 HTTPS · 保存前「校验可达」</div>
      </el-form-item>
      <el-form-item label="本月额度（只读）">
        <div class="readonly">
          {{ usageText }}
          <router-link to="/shop/subscription" class="link">（套餐信息）</router-link>
        </div>
      </el-form-item>
    </el-form>

    <div class="actions">
      <el-button v-if="!assigned" @click="contactManager">联系管家</el-button>
      <el-button :disabled="!assigned" :loading="testing" @click="sendTest">
        发送测试短信
      </el-button>
      <el-button type="primary" :disabled="!assigned" :loading="saving" @click="save">
        保存领权参数
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.a15s .hd {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.a15s h3 {
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
.readonly {
  width: 100%;
  padding: 8px 12px;
  background: #fafafa;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  font-size: 13px;
}
.inline {
  display: flex;
  align-items: center;
  gap: 8px;
}
.unit {
  color: #666;
  font-size: 13px;
}
.domain-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.hint {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}
.link {
  color: #1677ff;
  margin-left: 4px;
  text-decoration: none;
}
.actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
code {
  font-size: 12px;
  color: #64748b;
}
</style>
