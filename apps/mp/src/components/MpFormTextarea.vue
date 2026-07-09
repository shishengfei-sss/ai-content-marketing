<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

function onInput(e) {
  const val = e?.detail?.value ?? e?.target?.value ?? ''
  emit('update:modelValue', val)
}
</script>

<template>
  <textarea
    class="mp-textarea"
    :value="modelValue || ''"
    :placeholder="placeholder"
    :auto-height="true"
    :adjust-position="true"
    :cursor-spacing="24"
    :hold-keyboard="true"
    @input="onInput"
  />
</template>

<style scoped>
.mp-textarea {
  width: 100%;
  box-sizing: border-box;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  color: #0f172a;
  line-height: 1.4;
  min-height: 84px;
  pointer-events: auto;
}
</style>
