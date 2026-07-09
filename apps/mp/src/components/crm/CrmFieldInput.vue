<script>
import { defineComponent, h, ref, watch } from 'vue'

function isH5() {
  // #ifdef H5
  return true
  // #endif
  // #ifndef H5
  return false
  // #endif
}

export default defineComponent({
  name: 'CrmFieldInput',
  props: {
    modelValue: { type: [String, Number], default: '' },
    kind: { type: String, default: 'input' },
    inputType: { type: String, default: 'text' },
    placeholder: { type: String, default: '' },
    maxlength: { type: Number, default: 200 },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const local = ref(props.modelValue == null ? '' : String(props.modelValue))
    const h5 = isH5()

    watch(
      () => props.modelValue,
      (v) => {
        const next = v == null ? '' : String(v)
        if (next !== local.value) local.value = next
      },
    )

    function commit(val) {
      const next = val == null ? '' : String(val)
      if (next === local.value) return
      local.value = next
      emit('update:modelValue', next)
    }

    function htmlType() {
      if (props.inputType === 'number' || props.inputType === 'digit') return 'tel'
      return 'text'
    }

    return () => {
      if (h5) {
        if (props.kind === 'textarea') {
          return h('textarea', {
            class: 'crm-field-control crm-field-control--textarea',
            value: local.value,
            placeholder: props.placeholder || '',
            rows: 3,
            onInput: (e) => commit(e?.target?.value ?? ''),
          })
        }
        return h('input', {
          class: 'crm-field-control',
          type: htmlType(),
          value: local.value,
          placeholder: props.placeholder || '',
          maxLength: props.maxlength,
          autocomplete: 'off',
          onInput: (e) => commit(e?.target?.value ?? ''),
        })
      }

      if (props.kind === 'textarea') {
        return h(
          'textarea',
          {
            class: 'crm-field-control crm-field-control--textarea',
            value: local.value,
            placeholder: props.placeholder || '',
            autoHeight: true,
            adjustPosition: true,
            cursorSpacing: 24,
            onInput: (e) => commit(e?.detail?.value ?? ''),
          },
        )
      }
      return h('input', {
        class: 'crm-field-control',
        type: props.inputType || 'text',
        value: local.value,
        placeholder: props.placeholder || '',
        maxlength: props.maxlength,
        adjustPosition: true,
        cursorSpacing: 24,
        onInput: (e) => commit(e?.detail?.value ?? ''),
      })
    }
  },
})
</script>

<style>
.crm-field-control {
  width: 100%;
  box-sizing: border-box;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  color: #0f172a;
  line-height: 1.4;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
  pointer-events: auto !important;
  -webkit-user-select: text !important;
  user-select: text !important;
}

.crm-field-control:focus {
  border-color: #91caff;
  background: #fff;
}

.crm-field-control--textarea {
  min-height: 84px;
  width: 100%;
  resize: vertical;
  font-family: inherit;
}
</style>
