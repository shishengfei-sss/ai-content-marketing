<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { crmApi } from '@/utils/api'
import {
  fieldsWithoutRegionParts,
  groupFormFields,
  hasRegionFields,
  isFormFieldRequired,
} from '@/utils/entityForm'
import CrmFieldInput from './CrmFieldInput.vue'
import MpRegionPicker from '@/components/MpRegionPicker.vue'

const props = defineProps({
  entityType: { type: String, required: true },
  fields: { type: Array, default: () => [] },
  initialValues: { type: Object, default: () => ({}) },
})

const form = reactive({})
const hydrated = ref(false)
const campaigns = ref([])
const picker = ref({
  visible: false,
  fieldKey: '',
  title: '',
  options: [],
  multi: false,
  tempValue: '',
  tempValues: [],
})

function defaultFor(field) {
  if (field.field_type === 'multiselect') return []
  if (field.field_type === 'checkbox') return false
  return ''
}

function applyInitial() {
  const src = props.initialValues || {}
  Object.keys(form).forEach((k) => delete form[k])
  for (const field of props.fields || []) {
    const key = field.field_key
    const val = src[key]
    form[key] = val === undefined || val === null ? defaultFor(field) : val
  }
  for (const key of ['province', 'city', 'district']) {
    if (!(key in form)) form[key] = src[key] || ''
  }
  hydrated.value = true
}

watch(
  () => [props.fields, props.initialValues],
  () => {
    if (!props.fields?.length) return
    if (!hydrated.value) applyInitial()
  },
  { immediate: true, deep: true },
)

const sections = computed(() =>
  groupFormFields(props.fields).map((section) => ({
    ...section,
    fields:
      section.id === 'address' ? fieldsWithoutRegionParts(section.fields) : section.fields,
  })),
)

function fieldRequired(field) {
  return isFormFieldRequired(props.entityType, field)
}

function sectionHasRegion(section) {
  return section.id === 'address' && hasRegionFields(props.fields)
}

function setField(key, val) {
  form[key] = val
}

function displayValue(field) {
  const val = form[field.field_key]
  if (val === undefined || val === null || val === '') return ''
  if (field.field_key === 'campaign_id') {
    const hit = campaigns.value.find((c) => c.id === val)
    return hit?.name || String(val).slice(0, 8)
  }
  if (Array.isArray(val)) return val.join('、')
  return String(val)
}

function isSelectLike(field) {
  return (
    field.field_type === 'select' ||
    field.field_type === 'multiselect' ||
    field.field_key === 'campaign_id' ||
    field.field_key === 'status' ||
    field.field_key === 'source'
  )
}

function optionsFor(field) {
  if (field.field_key === 'campaign_id') {
    return campaigns.value.map((c) => ({ label: c.name, value: c.id }))
  }
  const opts = field.options || []
  return opts.map((o) => (typeof o === 'string' ? { label: o, value: o } : o))
}

function openPicker(field) {
  const multi = field.field_type === 'multiselect'
  const current = form[field.field_key]
  picker.value = {
    visible: true,
    fieldKey: field.field_key,
    title: field.label,
    options: optionsFor(field),
    multi,
    tempValue: multi ? '' : current || '',
    tempValues: multi ? [...(Array.isArray(current) ? current : [])] : [],
  }
}

function closePicker() {
  picker.value.visible = false
}

function toggleMulti(value) {
  const set = new Set(picker.value.tempValues)
  if (set.has(value)) set.delete(value)
  else set.add(value)
  picker.value.tempValues = [...set]
}

function confirmPicker() {
  setField(
    picker.value.fieldKey,
    picker.value.multi ? [...picker.value.tempValues] : picker.value.tempValue,
  )
  closePicker()
}

function pickSingle(value) {
  picker.value.tempValue = value
  confirmPicker()
}

function inputType(field) {
  if (field.field_type === 'phone' || field.field_key === 'mobile') return 'number'
  if (field.field_type === 'number' || field.field_type === 'currency') return 'digit'
  return 'text'
}

function getValues() {
  return { ...form }
}

defineExpose({ getValues })

async function loadCampaigns() {
  if (!props.fields.some((f) => f.field_key === 'campaign_id')) return
  try {
    const data = await crmApi.listCampaigns({ page: 1, page_size: 100 })
    campaigns.value = data.items || []
  } catch {
    campaigns.value = []
  }
}

onMounted(loadCampaigns)
watch(() => props.fields, loadCampaigns, { deep: true })
</script>

<template>
  <view class="entity-form">
    <view v-for="section in sections" :key="section.id" class="section">
      <view class="section__head">
        <view class="section__bar" />
        <text class="section__title">{{ section.title }}</text>
      </view>

      <view v-if="sectionHasRegion(section)" class="field">
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

      <view v-for="field in section.fields" :key="field.field_key" class="field">
        <text class="field__label">
          <text v-if="fieldRequired(field)" class="field__req">*</text>{{ field.label }}
        </text>

        <CrmFieldInput
          v-if="field.field_type === 'textarea'"
          :model-value="form[field.field_key]"
          kind="textarea"
          :placeholder="`请输入${field.label}`"
          @update:model-value="(v) => setField(field.field_key, v)"
        />

        <view
          v-else-if="field.field_type === 'checkbox'"
          class="check-row"
          @click="setField(field.field_key, !form[field.field_key])"
        >
          <text class="check-box" :class="{ 'check-box--on': !!form[field.field_key] }">
            {{ form[field.field_key] ? '✓' : '' }}
          </text>
          <text class="check-label">是</text>
        </view>

        <view v-else-if="isSelectLike(field)" class="picker" @click="openPicker(field)">
          <text class="picker__value" :class="{ 'picker__value--ph': !displayValue(field) }">
            {{ displayValue(field) || `请选择${field.label}` }}
          </text>
          <text class="picker__arrow">▾</text>
        </view>

        <CrmFieldInput
          v-else
          :model-value="form[field.field_key]"
          kind="input"
          :input-type="inputType(field)"
          :placeholder="`请输入${field.label}`"
          :maxlength="field.field_key === 'mobile' ? 11 : 200"
          @update:model-value="(v) => setField(field.field_key, v)"
        />
      </view>
    </view>

    <view v-if="picker.visible" class="picker-mask" @click="closePicker">
      <view class="picker-sheet" @click.stop>
        <view class="picker-sheet__bar">
          <text class="picker-sheet__cancel" @click="closePicker">取消</text>
          <text class="picker-sheet__title">{{ picker.title }}</text>
          <text v-if="picker.multi" class="picker-sheet__ok" @click="confirmPicker">完成</text>
          <text v-else class="picker-sheet__ok" @click="closePicker">关闭</text>
        </view>
        <scroll-view scroll-y class="picker-sheet__scroll">
          <view
            v-for="opt in picker.options"
            :key="String(opt.value)"
            class="picker-option"
            :class="{
              'picker-option--active': picker.multi
                ? picker.tempValues.includes(opt.value)
                : picker.tempValue === opt.value,
            }"
            @click="picker.multi ? toggleMulti(opt.value) : pickSingle(opt.value)"
          >
            <text>{{ opt.label }}</text>
            <text
              v-if="
                picker.multi
                  ? picker.tempValues.includes(opt.value)
                  : picker.tempValue === opt.value
              "
              class="picker-option__check"
            >
              ✓
            </text>
          </view>
          <view v-if="!picker.options.length" class="picker-empty">暂无可选项</view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.entity-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
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

.field__req {
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

.picker__value--ph {
  color: #94a3b8;
}

.picker__arrow {
  color: #94a3b8;
  font-size: 12px;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.check-box {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
}

.check-box--on {
  background: #1677ff;
  border-color: #1677ff;
}

.check-label {
  font-size: 14px;
  color: #334155;
}

.picker-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
}

.picker-sheet {
  width: 100%;
  max-height: 60vh;
  background: #fff;
  border-radius: 16px 16px 0 0;
  overflow: hidden;
}

.picker-sheet__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}

.picker-sheet__title {
  font-size: 15px;
  font-weight: 600;
}

.picker-sheet__cancel,
.picker-sheet__ok {
  font-size: 14px;
  color: #1677ff;
  min-width: 40px;
}

.picker-sheet__scroll {
  max-height: 48vh;
}

.picker-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f8fafc;
  font-size: 14px;
  color: #334155;
}

.picker-option--active {
  color: #1677ff;
  background: #f0f7ff;
}

.picker-option__check {
  color: #1677ff;
  font-weight: 700;
}

.picker-empty {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}
</style>
