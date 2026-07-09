<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  maxlength: { type: Number, default: -1 },
})

const emit = defineEmits(['update:modelValue'])

function onInput(e) {
  const val = e?.detail?.value ?? e?.target?.value ?? ''
  emit('update:modelValue', val)
}
</script>

<template>
  <input
    class="mp-input"
    :type="type"
    :value="modelValue == null ? '' : String(modelValue)"
    :placeholder="placeholder"
    :maxlength="maxlength > 0 ? maxlength : 140"
    :adjust-position="true"
    :cursor-spacing="24"
    :hold-keyboard="true"
    @input="onInput"
  />
</template>

<style scoped>
.mp-input {
  width: 100%;
  box-sizing: border-box;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  color: #0f172a;
  line-height: 1.4;
  min-height: 44px;
  height: 44px;
  pointer-events: auto;
}
</style>
