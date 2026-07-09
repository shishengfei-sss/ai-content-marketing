<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import {
  formValuesToPayload,
  getFormFields,
  LEAD_STATUS_OPTIONS,
  validateLeadMobile,
} from '@/utils/entityForm'
import MpFormInput from '@/components/MpFormInput.vue'
import MpFormTextarea from '@/components/MpFormTextarea.vue'
import MpRegionPicker from '@/components/MpRegionPicker.vue'

const { fields, loadSchema } = useEntitySchema('lead')
const saving = ref(false)
const ready = ref(false)
const permissions = ref([])
const campaignId = ref('')
const campaigns = ref([])
const picker = ref({ visible: false, key: '', title: '', options: [] })

const form = reactive({
  company_name: '',
  credit_code: '',
  contact_name: '',
  mobile: '',
  phone: '',
  wechat: '',
  qq: '',
  email: '',
  website: '',
  province: '',
  city: '',
  district: '',
  address: '',
  industry: '',
  company_scale: '',
  annual_revenue: '',
  taxpayer_type: '',
  main_business: '',
  accounting_need: '',
  source: '',
  source_detail: '',
  status: '待跟进',
  intention_level: '',
  campaign_id: '',
  remark: '',
})

const formFields = computed(() => getFormFields(fields.value, 'lead'))
const fieldMap = computed(() =>
  Object.fromEntries((formFields.value || []).map((f) => [f.field_key, f])),
)

function opts(key) {
  const f = fieldMap.value[key]
  const raw = f?.options || []
  return raw.map((o) => (typeof o === 'string' ? { label: o, value: o } : o))
}

function openSelect(key, title, options) {
  picker.value = { visible: true, key, title, options: options || [] }
}

function closePicker() {
  picker.value.visible = false
}

function pickOption(value) {
  form[picker.value.key] = value
  closePicker()
}

function setField(key, val) {
  form[key] = val
}

function displaySelect(key, fallback = '请选择') {
  const val = form[key]
  if (!val) return fallback
  if (key === 'campaign_id') {
    const hit = campaigns.value.find((c) => c.id === val)
    return hit?.name || String(val).slice(0, 8)
  }
  return String(val)
}

async function init() {
  try {
    const user = await ensureSession()
    if (!user) return
    permissions.value = user.permissions || []
    if (!hasPermission(permissions.value, 'crm.lead.create')) {
      uni.showToast({ title: '无新建权限', icon: 'none' })
      setTimeout(() => uni.navigateBack(), 500)
      return
    }
    await loadSchema()
    try {
      const data = await crmApi.listCampaigns({ page: 1, page_size: 100 })
      campaigns.value = data.items || []
    } catch {
      campaigns.value = []
    }
    if (campaignId.value) form.campaign_id = campaignId.value
    if (!form.status) form.status = '待跟进'
    ready.value = true
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  }
}

async function submit() {
  if (!String(form.company_name || '').trim()) {
    uni.showToast({ title: '请填写公司名称', icon: 'none' })
    return
  }
  if (!String(form.contact_name || '').trim()) {
    uni.showToast({ title: '请填写联系人姓名', icon: 'none' })
    return
  }
  const mobileErr = validateLeadMobile(form.mobile)
  if (mobileErr) {
    uni.showToast({ title: mobileErr, icon: 'none' })
    return
  }
  saving.value = true
  try {
    const payload = formValuesToPayload('lead', { ...form }, formFields.value)
    if (payload.mobile) payload.mobile = String(payload.mobile).trim()
    if (!payload.status) payload.status = '待跟进'
    await crmApi.createLead(payload)
    uni.showToast({ title: '已创建', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 400)
  } catch (e) {
    uni.showToast({ title: e.message || '创建失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function cancel() {
  uni.navigateBack()
}

onLoad((query) => {
  campaignId.value = query?.campaign_id || ''
  init()
})
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="hero__title">新建线索</text>
      <text class="hero__sub">完善联系方式、地址与来源信息，便于后续跟进转化</text>
    </view>

    <view v-if="!ready" class="loading">加载表单中…</view>

    <view v-else class="content">
      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">基本信息</text>
        </view>
        <view class="field">
          <text class="field__label"><text class="req">*</text>公司名称</text>
          <MpFormInput
            :model-value="form.company_name"
            placeholder="请输入公司名称"
            @update:model-value="(v) => setField('company_name', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">统一社会信用代码</text>
          <MpFormInput
            :model-value="form.credit_code"
            placeholder="请输入统一社会信用代码"
            @update:model-value="(v) => setField('credit_code', v)"
          />
        </view>
      </view>

      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">联系方式</text>
        </view>
        <view class="field">
          <text class="field__label"><text class="req">*</text>联系人姓名</text>
          <MpFormInput
            :model-value="form.contact_name"
            placeholder="请输入联系人姓名"
            @update:model-value="(v) => setField('contact_name', v)"
          />
        </view>
        <view class="field">
          <text class="field__label"><text class="req">*</text>手机</text>
          <MpFormInput
            :model-value="form.mobile"
            type="number"
            :maxlength="11"
            placeholder="请输入手机"
            @update:model-value="(v) => setField('mobile', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">电话</text>
          <MpFormInput
            :model-value="form.phone"
            placeholder="请输入电话"
            @update:model-value="(v) => setField('phone', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">微信</text>
          <MpFormInput
            :model-value="form.wechat"
            placeholder="请输入微信"
            @update:model-value="(v) => setField('wechat', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">QQ</text>
          <MpFormInput
            :model-value="form.qq"
            placeholder="请输入QQ"
            @update:model-value="(v) => setField('qq', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">邮箱</text>
          <MpFormInput
            :model-value="form.email"
            placeholder="请输入邮箱"
            @update:model-value="(v) => setField('email', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">网址</text>
          <MpFormInput
            :model-value="form.website"
            placeholder="请输入网址"
            @update:model-value="(v) => setField('website', v)"
          />
        </view>
      </view>

      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">地址信息</text>
        </view>
        <view class="field">
          <text class="field__label">省市区</text>
          <MpRegionPicker
            :province="form.province"
            :city="form.city"
            :district="form.district"
            @update:province="(v) => setField('province', v)"
            @update:city="(v) => setField('city', v)"
            @update:district="(v) => setField('district', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">详细地址</text>
          <MpFormInput
            :model-value="form.address"
            placeholder="请输入详细地址"
            @update:model-value="(v) => setField('address', v)"
          />
        </view>
      </view>

      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">业务信息</text>
        </view>
        <view class="field">
          <text class="field__label">行业</text>
          <view class="picker" @click="openSelect('industry', '行业', opts('industry'))">
            <text :class="{ ph: !form.industry }">{{ displaySelect('industry', '请选择行业') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">公司规模</text>
          <view class="picker" @click="openSelect('company_scale', '公司规模', opts('company_scale'))">
            <text :class="{ ph: !form.company_scale }">{{ displaySelect('company_scale', '请选择公司规模') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">年营业额</text>
          <MpFormInput
            :model-value="form.annual_revenue"
            type="digit"
            placeholder="请输入年营业额"
            @update:model-value="(v) => setField('annual_revenue', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">纳税人类型</text>
          <view class="picker" @click="openSelect('taxpayer_type', '纳税人类型', opts('taxpayer_type'))">
            <text :class="{ ph: !form.taxpayer_type }">{{ displaySelect('taxpayer_type', '请选择纳税人类型') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">主营业务</text>
          <MpFormTextarea
            :model-value="form.main_business"
            placeholder="请输入主营业务"
            @update:model-value="(v) => setField('main_business', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">代账需求</text>
          <view class="picker" @click="openSelect('accounting_need', '代账需求', opts('accounting_need'))">
            <text :class="{ ph: !form.accounting_need }">{{ displaySelect('accounting_need', '请选择代账需求') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">线索来源</text>
          <view class="picker" @click="openSelect('source', '线索来源', opts('source'))">
            <text :class="{ ph: !form.source }">{{ displaySelect('source', '请选择线索来源') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">来源说明</text>
          <MpFormInput
            :model-value="form.source_detail"
            placeholder="请输入来源说明"
            @update:model-value="(v) => setField('source_detail', v)"
          />
        </view>
      </view>

      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">销售跟进</text>
        </view>
        <view class="field">
          <text class="field__label"><text class="req">*</text>线索状态</text>
          <view
            class="picker"
            @click="openSelect('status', '线索状态', (opts('status').length ? opts('status') : LEAD_STATUS_OPTIONS.map((s) => ({ label: s, value: s }))))"
          >
            <text :class="{ ph: !form.status }">{{ displaySelect('status', '请选择线索状态') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">意向等级</text>
          <view class="picker" @click="openSelect('intention_level', '意向等级', opts('intention_level'))">
            <text :class="{ ph: !form.intention_level }">{{ displaySelect('intention_level', '请选择意向等级') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">市场活动</text>
          <view
            class="picker"
            @click="openSelect('campaign_id', '市场活动', campaigns.map((c) => ({ label: c.name, value: c.id })))"
          >
            <text :class="{ ph: !form.campaign_id }">{{ displaySelect('campaign_id', '请选择市场活动') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">备注</text>
          <MpFormTextarea
            :model-value="form.remark"
            placeholder="请输入备注"
            @update:model-value="(v) => setField('remark', v)"
          />
        </view>
      </view>
    </view>

    <view class="footer">
      <button class="btn" hover-class="none" @click="cancel">取消</button>
      <button class="btn btn--primary" hover-class="none" :loading="saving" @click="submit">创建线索</button>
    </view>

    <view v-if="picker.visible" class="mask" @click="closePicker">
      <view class="sheet" @click.stop>
        <view class="sheet__bar">
          <text class="sheet__cancel" @click="closePicker">取消</text>
          <text class="sheet__title">{{ picker.title }}</text>
          <text class="sheet__ok" @click="closePicker">关闭</text>
        </view>
        <scroll-view scroll-y class="sheet__scroll">
          <view
            v-for="opt in picker.options"
            :key="String(opt.value)"
            class="opt"
            :class="{ 'opt--on': form[picker.key] === opt.value }"
            @click="pickOption(opt.value)"
          >
            <text>{{ opt.label }}</text>
            <text v-if="form[picker.key] === opt.value" class="opt__check">✓</text>
          </view>
          <view v-if="!picker.options.length" class="empty">暂无可选项</view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(180deg, #eef5ff 0%, #f5f7fb 160px, #f5f7fb 100%);
  padding: 12px 12px 88px;
  box-sizing: border-box;
}

.hero {
  padding: 8px 4px 14px;
}

.hero__title {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.hero__sub {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: #64748b;
}

.loading {
  padding: 40px 0;
  text-align: center;
  color: #94a3b8;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 12px;
}

.section {
  padding: 14px 14px 6px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #eef2f7;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.section__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.section__bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: #1677ff;
}

.section__title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.field {
  margin-bottom: 12px;
}

.field__label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.req {
  color: #ef4444;
  margin-right: 2px;
}

.picker {
  width: 100%;
  box-sizing: border-box;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  color: #0f172a;
  line-height: 1.4;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ph {
  color: #94a3b8;
}

.arrow {
  color: #94a3b8;
  font-size: 12px;
}

.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 10px;
  padding: 12px 12px calc(12px + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid #eef2f7;
  z-index: 10;
}

.btn {
  flex: 1;
  height: 44px;
  line-height: 44px;
  border-radius: 12px;
  font-size: 15px;
  background: #fff;
  color: #334155;
  border: 1px solid #e2e8f0;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
  font-weight: 600;
}

.mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
}

.sheet {
  width: 100%;
  max-height: 60vh;
  background: #fff;
  border-radius: 16px 16px 0 0;
  overflow: hidden;
}

.sheet__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}

.sheet__title {
  font-size: 15px;
  font-weight: 600;
}

.sheet__cancel,
.sheet__ok {
  font-size: 14px;
  color: #1677ff;
  min-width: 40px;
}

.sheet__scroll {
  max-height: 48vh;
}

.opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f8fafc;
  font-size: 14px;
  color: #334155;
}

.opt--on {
  color: #1677ff;
  background: #f0f7ff;
}

.opt__check {
  color: #1677ff;
  font-weight: 700;
}

.empty {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}
</style>
