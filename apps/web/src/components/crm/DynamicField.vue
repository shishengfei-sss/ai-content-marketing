<script setup>
import { computed } from 'vue'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, null], default: null },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const value = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const inputType = computed(() => {
  const t = props.field?.field_type
  if (t === 'email') return 'email'
  if (t === 'phone' && props.field.field_key === 'mobile') return 'tel'
  if (t === 'number' || t === 'currency') return 'number'
  if (t === 'url') return 'url'
  if (t === 'date') return 'date'
  if (t === 'datetime') return 'datetime-local'
  return 'text'
})

const inputPlaceholder = computed(() => {
  if (props.field?.placeholder) return props.field.placeholder
  if (props.field?.field_key === 'mobile') return '11 位手机号'
  if (props.field?.field_type === 'phone') return '联系电话'
  return undefined
})
</script>

<template>
  <el-select
    v-if="field.field_type === 'select'"
    v-model="value"
    :disabled="readonly"
    :placeholder="field.placeholder || '请选择'"
    style="width: 100%"
  >
    <el-option v-for="opt in field.options || []" :key="opt" :label="opt" :value="opt" />
  </el-select>
  <el-select
    v-else-if="field.field_type === 'multiselect'"
    v-model="value"
    multiple
    :disabled="readonly"
    :placeholder="field.placeholder || '请选择'"
    style="width: 100%"
  >
    <el-option v-for="opt in field.options || []" :key="opt" :label="opt" :value="opt" />
  </el-select>
  <el-switch
    v-else-if="field.field_type === 'checkbox'"
    v-model="value"
    :disabled="readonly"
  />
  <el-input
    v-else-if="field.field_type === 'textarea'"
    v-model="value"
    type="textarea"
    :rows="3"
    :disabled="readonly"
    :placeholder="field.placeholder"
  />
  <el-date-picker
    v-else-if="field.field_type === 'datetime'"
    v-model="value"
    type="datetime"
    :disabled="readonly"
    :placeholder="field.placeholder || '选择日期时间'"
    style="width: 100%"
    value-format="YYYY-MM-DDTHH:mm:ss"
  />
  <el-date-picker
    v-else-if="field.field_type === 'date'"
    v-model="value"
    type="date"
    :disabled="readonly"
    :placeholder="field.placeholder || '选择日期'"
    style="width: 100%"
    value-format="YYYY-MM-DD"
  />
  <el-input
    v-else-if="field.field_key === 'annual_revenue'"
    v-model="value"
    type="number"
    :disabled="readonly"
    :placeholder="field.placeholder || '请输入金额'"
  >
    <template #append>万元</template>
  </el-input>
  <el-input
    v-else
    v-model="value"
    :type="inputType"
    :disabled="readonly"
    :placeholder="inputPlaceholder"
    :maxlength="field.field_key === 'mobile' ? 11 : undefined"
  />
</template>
