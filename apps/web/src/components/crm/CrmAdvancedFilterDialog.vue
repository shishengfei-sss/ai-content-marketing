<script setup>
import { computed, ref, watch } from 'vue'
import {
  buildFiltersPayload,
  createEmptyCondition,
  draftFromFilters,
  getFilterableFields,
  opsForFieldType,
} from '../../utils/crmAdvancedFilter'

const props = defineProps({
  visible: { type: Boolean, default: false },
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({ logic: 'and', conditions: [] }) },
  members: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:visible', 'apply'])

const draft = ref([])

const filterableFields = computed(() => getFilterableFields(props.fields))

watch(
  () => props.visible,
  (open) => {
    if (open) draft.value = draftFromFilters(props.modelValue)
  },
)

function fieldDef(key) {
  return filterableFields.value.find((f) => f.field_key === key)
}

function opsForRow(row) {
  const def = fieldDef(row.field_key)
  return opsForFieldType(def?.field_type)
}

function inputKind(row) {
  const def = fieldDef(row.field_key)
  const ft = def?.field_type
  if (row.op === 'is_empty') return 'none'
  if (ft === 'select') return row.op === 'in' ? 'multiselect' : 'select'
  if (ft === 'user_ref') return 'user'
  if (ft === 'datetime' || ft === 'date') return 'date'
  if (ft === 'number' || ft === 'currency') return 'number'
  if (ft === 'checkbox') return 'checkbox'
  return 'text'
}

function onFieldChange(row) {
  const ops = opsForRow(row)
  if (!ops.find((o) => o.value === row.op)) row.op = ops[0]?.value || 'contains'
  row.value = row.op === 'in' ? [] : ''
}

function addRow() {
  draft.value.push(createEmptyCondition())
}

function removeRow(idx) {
  draft.value.splice(idx, 1)
  if (!draft.value.length) draft.value.push(createEmptyCondition())
}

function resetDraft() {
  draft.value = [createEmptyCondition()]
}

function close() {
  emit('update:visible', false)
}

function apply() {
  const payload = buildFiltersPayload(draft.value, filterableFields.value)
  emit('apply', payload)
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="高级筛选"
    width="720px"
    class="crm-adv-filter-dialog"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="crm-adv-filter__tip">满足以下全部条件（AND）</div>

    <div v-if="!filterableFields.length" class="crm-adv-filter__empty">暂无可用筛选字段</div>

    <div v-else class="crm-adv-filter__rows">
      <div v-for="(row, idx) in draft" :key="idx" class="crm-adv-filter__row">
        <el-select
          v-model="row.field_key"
          placeholder="字段"
          filterable
          class="crm-adv-filter__field"
          @change="onFieldChange(row)"
        >
          <el-option
            v-for="f in filterableFields"
            :key="f.field_key"
            :label="f.label"
            :value="f.field_key"
          />
        </el-select>

        <el-select v-model="row.op" placeholder="条件" class="crm-adv-filter__op">
          <el-option v-for="op in opsForRow(row)" :key="op.value" :label="op.label" :value="op.value" />
        </el-select>

        <div class="crm-adv-filter__value">
          <template v-if="inputKind(row) === 'none'">
            <span class="crm-adv-filter__placeholder">无需填写</span>
          </template>
          <el-select
            v-else-if="inputKind(row) === 'select'"
            v-model="row.value"
            placeholder="请选择"
            clearable
            filterable
          >
            <el-option
              v-for="opt in fieldDef(row.field_key)?.options || []"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
          <el-select
            v-else-if="inputKind(row) === 'multiselect'"
            v-model="row.value"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择"
            filterable
          >
            <el-option
              v-for="opt in fieldDef(row.field_key)?.options || []"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
          <el-select
            v-else-if="inputKind(row) === 'user'"
            v-model="row.value"
            placeholder="选择成员"
            clearable
            filterable
          >
            <el-option
              v-for="m in members"
              :key="m.user_id"
              :label="m.display_name || m.phone"
              :value="m.user_id"
            />
          </el-select>
          <el-date-picker
            v-else-if="inputKind(row) === 'date'"
            v-model="row.value"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择时间"
            style="width: 100%"
          />
          <el-select
            v-else-if="inputKind(row) === 'checkbox'"
            v-model="row.value"
            placeholder="请选择"
            clearable
          >
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
          <el-input
            v-else
            v-model="row.value"
            :type="inputKind(row) === 'number' ? 'number' : 'text'"
            placeholder="请输入"
            clearable
          />
        </div>

        <el-button text type="danger" class="crm-adv-filter__remove" @click="removeRow(idx)">
          删除
        </el-button>
      </div>
    </div>

    <el-button v-if="filterableFields.length" link type="primary" @click="addRow">+ 添加条件</el-button>

    <template #footer>
      <el-button @click="resetDraft">重置</el-button>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="apply">应用筛选</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.crm-adv-filter__tip {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.crm-adv-filter__empty {
  padding: 24px;
  text-align: center;
  color: var(--el-text-color-placeholder);
}

.crm-adv-filter__rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.crm-adv-filter__row {
  display: grid;
  grid-template-columns: 160px 120px 1fr auto;
  gap: 8px;
  align-items: center;
}

.crm-adv-filter__placeholder {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.crm-adv-filter__remove {
  flex-shrink: 0;
}
</style>
