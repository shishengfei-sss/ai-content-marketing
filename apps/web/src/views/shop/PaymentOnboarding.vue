<script setup>
/**
 * A15 支付与进件。对照 PRD 01-管理端UI.html #a15 · #a15a
 * 商家只提交材料/看状态；证书与回调不可见。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import ShopSettingsNav from '../../components/shop/ShopSettingsNav.vue'

const loading = ref(false)
const submitting = ref(false)
const testing = ref(false)
const data = ref(null)
const drawer = ref(false)
const viewOnly = ref(false)

const form = reactive({
  settlement_bank: '',
  settlement_account: '',
  settlement_account_name: '',
  remark: '',
})

const statusType = computed(() => {
  const s = data.value?.onboarding_status
  if (s === 'approved') return 'success'
  if (s === 'submitted') return 'warning'
  if (s === 'rejected') return 'danger'
  return 'info'
})

const canSubmit = computed(() => data.value?.can_submit)
const canTest = computed(() => (data.value?.actions || []).includes('test_payment'))
const canView = computed(() => (data.value?.actions || []).includes('view_materials'))

async function load() {
  loading.value = true
  try {
    const { data: res } = await api.get('/api/v1/shop/settings/payment')
    data.value = res
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openSubmit() {
  viewOnly.value = false
  const ent = data.value?.entity || {}
  const set = data.value?.settlement || {}
  form.settlement_bank = set.settlement_bank || ''
  form.settlement_account = ''
  form.settlement_account_name = set.settlement_account_name || ent.legal_name || ''
  form.remark = set.remark || ''
  drawer.value = true
}

function openView() {
  viewOnly.value = true
  const set = data.value?.settlement || {}
  form.settlement_bank = set.settlement_bank || ''
  form.settlement_account = set.settlement_account_masked || ''
  form.settlement_account_name = set.settlement_account_name || ''
  form.remark = set.remark || ''
  drawer.value = true
}

async function submitOnboarding() {
  if (!form.settlement_bank) {
    ElMessage.warning('请选择结算开户行')
    return
  }
  if (!/^\d{8,32}$/.test((form.settlement_account || '').replace(/\s/g, ''))) {
    ElMessage.warning('结算账号须为 8–32 位数字')
    return
  }
  if (!(form.settlement_account_name || '').trim()) {
    ElMessage.warning('请填写开户名')
    return
  }
  submitting.value = true
  try {
    const { data: res } = await api.post('/api/v1/shop/settings/payment/onboarding', {
      settlement_bank: form.settlement_bank,
      settlement_account: form.settlement_account.replace(/\s/g, ''),
      settlement_account_name: form.settlement_account_name.trim(),
      remark: (form.remark || '').trim() || null,
    })
    data.value = res
    drawer.value = false
    ElMessage.success('进件材料已提交，请等待平台审核')
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function testPay() {
  testing.value = true
  try {
    const { data: res } = await api.post('/api/v1/shop/settings/payment/test')
    ElMessage.success(res.message || '测试支付已发起')
  } catch (e) {
    ElMessage.error(e.message || '测试失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card a15">
    <div class="hd">
      <div>
        <div class="crumb">设置 / <b>支付与进件</b></div>
        <h3>支付与进件</h3>
      </div>
      <el-tag v-if="data" :type="statusType" effect="plain">
        {{ data.onboarding_status_label }}
      </el-tag>
    </div>

    <ShopSettingsNav current="payment" />

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="商家做什么？"
      description="提交/补充进件材料（主体与入驻同源）→ 等平台代提微信子商户 → 通过后可用「测试支付」验链路。不需配置证书或回调。"
      style="margin-bottom: 14px"
    />

    <el-alert
      v-if="data?.state === 'not_onboarded'"
      type="error"
      :closable="false"
      title="请先完成入驻"
      description="入驻通过后方可提交支付进件材料。"
      style="margin-bottom: 14px"
    />

    <template v-else-if="data">
      <el-alert
        v-if="data.onboarding_status === 'rejected' && data.reject_reason"
        type="error"
        :closable="false"
        :title="'已驳回：' + data.reject_reason"
        style="margin-bottom: 14px"
      />

      <el-descriptions :column="1" border class="desc">
        <el-descriptions-item label="进件状态">
          <el-tag :type="statusType" size="small">{{ data.onboarding_status_label }}</el-tag>
          <span v-if="data.approved_at" class="muted"> · {{ data.approved_at.slice(0, 16).replace('T', ' ') }} 审核通过</span>
          <span v-else-if="data.submitted_at" class="muted"> · {{ data.submitted_at.slice(0, 16).replace('T', ' ') }} 已提交</span>
        </el-descriptions-item>
        <el-descriptions-item v-if="data.onboarding_status === 'approved'" label="微信子商户号（只读）">
          {{ data.wx_sub_mch_id_masked || '—' }} · 平台代申请下发
        </el-descriptions-item>
        <el-descriptions-item v-if="data.mch_name" label="商户名称（只读）">
          {{ data.mch_name }}
        </el-descriptions-item>
        <el-descriptions-item v-if="data.settlement" label="结算账户（只读）">
          {{ data.settlement.settlement_bank }}
          {{ data.settlement.settlement_account_masked }}
          · {{ data.settlement.settlement_account_name }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="actions">
        <el-button
          v-if="canSubmit"
          type="primary"
          @click="openSubmit"
        >
          {{ data.onboarding_status === 'rejected' ? '补充材料并重新提交' : '提交进件材料' }}
        </el-button>
        <el-button
          v-if="canTest"
          type="primary"
          :loading="testing"
          @click="testPay"
        >
          测试 0.01 元
        </el-button>
        <el-button v-if="canView" @click="openView">查看进件材料</el-button>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="平台维护（商家不可见）"
        description="微信支付服务商 AppID/证书、统一回调与子商户绑定均由平台统一配置，商家本页不可见、不可改。"
        style="margin-top: 16px"
      />
    </template>

    <el-drawer
      v-model="drawer"
      :title="viewOnly ? '查看进件材料' : '提交进件材料'"
      size="480px"
      destroy-on-close
    >
      <el-alert
        type="info"
        :closable="false"
        title="字段与入驻材料同源；已入驻商家预填只读项，仅需补结算账户等支付专字段。"
        style="margin-bottom: 14px"
      />
      <el-form label-position="top" class="a15a-form">
        <el-form-item label="主体类型（只读）">
          <el-input :model-value="data?.entity?.entity_type_label || '—'" disabled />
        </el-form-item>
        <el-form-item label="主体名称（只读）">
          <el-input :model-value="data?.entity?.legal_name || '—'" disabled />
        </el-form-item>
        <el-form-item
          v-if="data?.entity?.entity_type !== 'personal'"
          label="统一社会信用代码（只读）"
        >
          <el-input :model-value="data?.entity?.unified_social_credit_code || '—'" disabled />
        </el-form-item>
        <el-form-item
          v-if="data?.entity?.entity_type !== 'personal'"
          label="法人姓名（只读）"
        >
          <el-input :model-value="data?.entity?.legal_rep_name || '—'" disabled />
        </el-form-item>
        <el-form-item label="结算开户行" required>
          <el-select
            v-model="form.settlement_bank"
            :disabled="viewOnly"
            placeholder="请选择"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="b in data?.banks || []"
              :key="b"
              :label="b"
              :value="b"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="结算账号" required>
          <el-input
            v-model="form.settlement_account"
            :disabled="viewOnly"
            :placeholder="viewOnly ? '' : '8–32 位数字'"
            maxlength="32"
          />
        </el-form-item>
        <el-form-item label="开户名" required>
          <el-input
            v-model="form.settlement_account_name"
            :disabled="viewOnly"
            maxlength="200"
          />
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="3"
            :disabled="viewOnly"
            placeholder="选填"
            maxlength="500"
          />
        </el-form-item>
      </el-form>
      <template v-if="!viewOnly" #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOnboarding">
          提交进件
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.a15 .hd {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.a15 h3 {
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
.desc {
  max-width: 640px;
}
.actions {
  margin-top: 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.muted {
  color: #64748b;
  font-size: 12px;
  margin-left: 6px;
}
</style>
