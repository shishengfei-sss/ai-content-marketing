<script setup>
import { computed } from 'vue'
import { regionLabelOptions } from '../../utils/regionData'

const props = defineProps({
  province: { type: String, default: '' },
  city: { type: String, default: '' },
  district: { type: String, default: '' },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:province', 'update:city', 'update:district', 'change'])

const options = regionLabelOptions

const selected = computed(() => [props.province, props.city, props.district].filter(Boolean))

function onUpdate(path) {
  const [province = '', city = '', district = ''] = Array.isArray(path) ? path : []
  // 一次回写三省市区，避免分三次 emit 时父级 spread 互相覆盖
  emit('change', { province, city, district })
  emit('update:province', province)
  emit('update:city', city)
  emit('update:district', district)
}
</script>

<template>
  <el-cascader
    :model-value="selected"
    :options="options"
    :disabled="readonly"
    clearable
    filterable
    placeholder="请选择省 / 市 / 区"
    style="width: 100%"
    @update:model-value="onUpdate"
  />
</template>
