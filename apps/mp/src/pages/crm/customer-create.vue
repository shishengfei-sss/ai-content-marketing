<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import {
  CUSTOMER_STATUS_OPTIONS,
  formValuesToPayload,
  getFormFields,
} from '@/utils/entityForm'
import MpFormInput from '@/components/MpFormInput.vue'
import MpFormTextarea from '@/components/MpFormTextarea.vue'
import MpRegionPicker from '@/components/MpRegionPicker.vue'

const { fields, loadSchema } = useEntitySchema('customer')
const saving = ref(false)
const ready = ref(false)
const permissions = ref([])
const picker = ref({ visible: false, key: '', title: '', options: [] })

const form = reactive({
  company_name: '',
  short_name: '',
  customer_level: '',
  status: '潜在',
  mobile: '',
  phone: '',
  email: '',
  wechat: '',
  province: '',
  city: '',
  district: '',
  address: '',
  industry: '',
  company_scale: '',
  credit_code: '',
  taxpayer_type: '',
  legal_representative: '',
  registered_capital: '',
  service_type: '',
  service_start_at: '',
  contract_amount: '',
  remark: '',
})

const formFields = computed(() => getFormFields(fields.value, 'customer'))
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
  return val ? String(val) : fallback
}

async function init() {
  try {
    const user = await ensureSession()
    if (!user) return
    permissions.value = user.permissions || []
    if (!hasPermission(permissions.value, 'crm.customer.create')) {
      uni.showToast({ title: '无新建权限', icon: 'none' })
      setTimeout(() => uni.navigateBack(), 500)
      return
    }
    await loadSchema()
    if (!form.status) form.status = '潜在'
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
  saving.value = true
  try {
    const payload = formValuesToPayload('customer', { ...form }, formFields.value)
    if (!payload.status) payload.status = '潜在'
    await crmApi.createCustomer(payload)
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

onLoad(() => {
  init()
})
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="hero__title">新建客户</text>
      <text class="hero__sub">完善客户级别、联系方式与业务信息，便于团队协作跟进</text>
    </view>

    <view v-if="!ready" class="loading">加载表单中…</view>

    <view v-else class="content">
      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">基本信息</text>
        </view>
        <view class="field">
          <text class="field__label"><text class="req">*</text>客户名称</text>
          <MpFormInput
            :model-value="form.company_name"
            placeholder="请输入客户名称"
            @update:model-value="(v) => setField('company_name', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">客户简称</text>
          <MpFormInput
            :model-value="form.short_name"
            placeholder="请输入客户简称"
            @update:model-value="(v) => setField('short_name', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">客户级别</text>
          <view class="picker" @click="openSelect('customer_level', '客户级别', opts('customer_level'))">
            <text :class="{ ph: !form.customer_level }">{{ displaySelect('customer_level', '请选择客户级别') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">客户状态</text>
          <view
            class="picker"
            @click="openSelect('status', '客户状态', (opts('status').length ? opts('status') : CUSTOMER_STATUS_OPTIONS.map((s) => ({ label: s, value: s }))))"
          >
            <text :class="{ ph: !form.status }">{{ displaySelect('status', '请选择客户状态') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
      </view>

      <view class="section">
        <view class="section__head">
          <view class="section__bar" />
          <text class="section__title">联系方式</text>
        </view>
        <view class="field">
          <text class="field__label">主手机</text>
          <MpFormInput
            :model-value="form.mobile"
            type="number"
            :maxlength="11"
            placeholder="请输入主手机"
            @update:model-value="(v) => setField('mobile', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">主电话</text>
          <MpFormInput
            :model-value="form.phone"
            placeholder="请输入主电话"
            @update:model-value="(v) => setField('phone', v)"
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
          <text class="field__label">微信</text>
          <MpFormInput
            :model-value="form.wechat"
            placeholder="请输入微信"
            @update:model-value="(v) => setField('wechat', v)"
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
          <text class="field__label">统一社会信用代码</text>
          <MpFormInput
            :model-value="form.credit_code"
            placeholder="请输入统一社会信用代码"
            @update:model-value="(v) => setField('credit_code', v)"
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
          <text class="field__label">法定代表人</text>
          <MpFormInput
            :model-value="form.legal_representative"
            placeholder="请输入法定代表人"
            @update:model-value="(v) => setField('legal_representative', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">注册资本</text>
          <MpFormInput
            :model-value="form.registered_capital"
            type="digit"
            placeholder="请输入注册资本"
            @update:model-value="(v) => setField('registered_capital', v)"
          />
        </view>
        <view class="field">
          <text class="field__label">服务类型</text>
          <view class="picker" @click="openSelect('service_type', '服务类型', opts('service_type'))">
            <text :class="{ ph: !form.service_type }">{{ displaySelect('service_type', '请选择服务类型') }}</text>
            <text class="arrow">▾</text>
          </view>
        </view>
        <view class="field">
          <text class="field__label">合同金额</text>
          <MpFormInput
            :model-value="form.contract_amount"
            type="digit"
            placeholder="请输入合同金额"
            @update:model-value="(v) => setField('contract_amount', v)"
          />
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
      <button class="btn btn--primary" hover-class="none" :loading="saving" @click="submit">创建客户</button>
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
