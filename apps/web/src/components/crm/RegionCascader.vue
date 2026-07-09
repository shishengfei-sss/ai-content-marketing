<script setup>
import { computed } from 'vue'
import { regionLabelOptions } from '../../utils/regionData'

const props = defineProps({
  province: { type: String, default: '' },
  city: { type: String, default: '' },
  district: { type: String, default: '' },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:province', 'update:city', 'update:district'])

const options = regionLabelOptions

const selected = computed({
  get() {
    return [props.province, props.city, props.district].filter(Boolean)
  },
  set(path) {
    const [province = '', city = '', district = ''] = path || []
    emit('update:province', province)
    emit('update:city', city)
    emit('update:district', district)
  },
})
</script>

<template>
  <el-cascader
    v-model="selected"
    :options="options"
    :disabled="readonly"
    clearable
    filterable
    placeholder="请选择省 / 市 / 区"
    style="width: 100%"
  />
</template>
