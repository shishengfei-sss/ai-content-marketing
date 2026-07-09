<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  columns: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:visible', 'update:columns', 'save'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const localColumns = ref([])

function syncLocalColumns() {
  localColumns.value = props.columns.map((c) => ({
    ...c,
    visible: c.list_locked ? true : c.visible,
  }))
}

watch(
  () => props.visible,
  (open) => {
    if (open) syncLocalColumns()
  },
)

const visibleCount = computed(() => localColumns.value.filter((c) => c.visible).length)
const totalCount = computed(() => localColumns.value.length)

function reorder(from, to) {
  if (from === to || from < 0 || to < 0 || from >= localColumns.value.length || to >= localColumns.value.length) {
    return
  }
  const next = [...localColumns.value]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  localColumns.value = next
}

function jumpToPosition(fromIdx, targetPos) {
  const pos = Number(targetPos)
  if (!Number.isFinite(pos) || pos < 1) return
  const targetIdx = Math.round(pos) - 1
  reorder(fromIdx, Math.max(0, Math.min(targetIdx, localColumns.value.length - 1)))
}

function handleCancel() {
  dialogVisible.value = false
}

function handleSave() {
  emit(
    'update:columns',
    localColumns.value.map((c) => ({
      ...c,
      visible: c.list_locked ? true : c.visible,
    })),
  )
  emit('save')
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="列设置" width="440px" class="crm-column-settings-dialog">
    <p class="column-settings-tip">
      勾选控制是否在列表中显示；输入目标序号后按回车或点击其他区域生效（序号越小越靠前）。带「固定」标签的列无法隐藏
    </p>
    <p class="column-settings-meta">已显示 {{ visibleCount }} / {{ totalCount }} 列</p>

    <el-empty v-if="!localColumns.length" description="暂无可用列，请检查表单字段配置" />

    <div v-else class="column-settings-list">
      <div class="column-settings-head">
        <span class="column-settings-head__show">显示</span>
        <span class="column-settings-head__name">列名</span>
        <span class="column-settings-head__order">序号</span>
      </div>
      <div
        v-for="(col, idx) in localColumns"
        :key="col.field_key"
        class="column-settings-item"
        :class="{ 'is-hidden': !col.visible, 'is-locked': col.list_locked }"
      >
        <el-checkbox
          v-model="col.visible"
          class="column-settings-checkbox"
          :disabled="col.list_locked"
        />
        <div class="column-settings-name">
          <span class="column-settings-label">{{ col.label }}</span>
          <el-tag v-if="col.list_locked" size="small" type="info" effect="plain">固定</el-tag>
        </div>
        <input
          type="text"
          inputmode="numeric"
          class="column-settings-order-input"
          :value="String(idx + 1)"
          @keydown.enter="(e) => jumpToPosition(idx, e.target.value)"
          @blur="(e) => jumpToPosition(idx, e.target.value)"
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :disabled="!localColumns.length" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.column-settings-tip {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.column-settings-meta {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.column-settings-list {
  max-height: min(52vh, 420px);
  overflow-y: auto;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-bg-color);
}

.column-settings-head {
  display: grid;
  grid-template-columns: 44px 1fr 64px;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-lighter);
  position: sticky;
  top: 0;
  z-index: 1;
}

.column-settings-head__show {
  text-align: center;
}

.column-settings-head__order {
  text-align: center;
}

.column-settings-item {
  display: grid;
  grid-template-columns: 44px 1fr 64px;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  transition: opacity 0.15s ease;
}

.column-settings-item:last-child {
  border-bottom: none;
}

.column-settings-item.is-locked {
  background: var(--el-fill-color-lighter);
}

.column-settings-item.is-hidden {
  opacity: 0.65;
}

.column-settings-checkbox {
  justify-self: center;
}

.column-settings-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.column-settings-label {
  font-size: 14px;
  line-height: 1.4;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-settings-order-input {
  width: 56px;
  height: 28px;
  padding: 0 6px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  font-size: 14px;
  text-align: center;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  box-sizing: border-box;
}

.column-settings-order-input:focus {
  outline: none;
  border-color: var(--el-color-primary);
}
</style>
